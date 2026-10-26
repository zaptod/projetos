# -*- coding: utf-8 -*-
"""Uma postagem por dia: um video de cada canal, publico.

    python ferramentas/postar.py            # posta
    python ferramentas/postar.py --ver      # so diz o que postaria
    python ferramentas/postar.py --instalar # cria a tarefa diaria

Pedido dele em 08/09/2026, depois de o sistema passar o dia inteiro CRIANDO
sem entregar nada: "quero que seja apenas um e que tudo seja public, quero um
video de cada canal".

O QUE MANDA NA ESCOLHA e a ORDEM. Uma serie fora de ordem esta quebrada: quem
cai na parte 4 sem ter visto a 3 sai. Entao a fila e sempre a mesma — a
historia mais ANTIGA que ainda tem parte pendente, e dela a MENOR parte que
falta. So quando ela termina e que a proxima historia comeca.

E o ledger e quem decide o que ja foi: `outputs/_publicar/publicados.jsonl`
das historias e o registro de publicacoes do builds. Sem consultar, o mesmo
video subiria de novo — e video repetido no canal nao tem desfazer bonito.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from builds import grade

RAIZ = Path(__file__).resolve().parents[1]
TAREFA = "NeuralFights_postar"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# UM VIDEO EM CADA HORARIO DA GRADE, e nao um por dia — correcao dele em
# 09/09/2026. Sao os mesmos horarios em que a agenda CRIA historia, e isso e
# de proposito: criar e publicar no mesmo ritmo e o que mantem o estoque
# estavel em vez de crescer sem sair.
#
# A grade mora em `builds.grade`, com o minuto de cada horario (desde
# 15/09/2026 cada hora tem o seu: 06:37, 12:07, 17:57...): a mesma tupla
# estava escrita aqui e em `remoto/relatorios.py`, e duas copias bastam para
# o relatorio dizer que bateu a meta enquanto a postagem trabalha com outro
# horario.
HORAS_PADRAO = grade.HORAS
MINUTO_PADRAO = grade.MINUTO
HORA_PADRAO = grade.horario(17)   # compatibilidade com quem passa --hora


def _linha(texto: str = "") -> None:
    """Uma linha no log. NUNCA levanta: log que derruba a conta e pior que
    log que se perde.

    Era `sys.stdout.buffer.write(...)` seco. Em 05/10/2026 a agenda das
    historias rodava DENTRO da trava com `sys.stdout` trocado por
    `_SaidaNoDiario`, que nao tem `.buffer`: a primeira historia que ja
    tinha saido 2x no dia escrevia uma linha aqui, o `AttributeError`
    subia ate `pendentes_por_canal`, que devolvia -1, e o freio caia no
    plano B contando as RETIDAS como estoque — "59 videos na fila (teto
    20)" contra 1 parte limpa, e tres madrugadas sem historia nova.
    Medido: -1 com o stdout trocado, 1 com o normal.
    """
    texto = str(texto) + "\n"
    saida = sys.stdout
    try:
        buffer = getattr(saida, "buffer", None)
        if buffer is not None:
            buffer.write(texto.encode("utf-8", "replace"))
            return
        try:
            saida.write(texto)
        except UnicodeEncodeError:
            codificacao = getattr(saida, "encoding", None) or "ascii"
            saida.write(texto.encode(codificacao, "replace")
                        .decode(codificacao, "replace"))
    except Exception:                                          # noqa: BLE001
        pass


class _SaidaDatada:
    """Acrescenta data e hora a cada linha do log da rodada (`--saida`).

    Ate 11/10/2026 o `postar.txt` nao datava as linhas, e 4 dias com horario
    vazio (27/09, 29/09, 03/10, 04/10) ficaram sem causa porque nao dava
    para achar a rodada no log. Sem `buffer`, de proposito: `_linha` escreve
    pelo `write` (e e datada); com o `buffer` do arquivo exposto ela
    escreveria bytes por fora, sem data.
    """
    buffer = None

    def __init__(self, saida):
        self.saida = saida
        self.inicio = True

    def write(self, texto):
        from datetime import datetime
        partes = str(texto).splitlines(keepends=True)
        if not partes:
            return 0
        for parte in partes:
            if self.inicio and parte:
                self.saida.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ")
            self.saida.write(parte)
            self.inicio = parte.endswith("\n") or parte.endswith("\r")
        return len(texto)

    def flush(self):
        self.saida.flush()

    def __getattr__(self, nome):
        return getattr(self.saida, nome)


def _voando(canal: str, destino: str):
    """Decora um FUNIL de publicacao: enquanto ele roda, a ficha da trava diz
    o que esta no ar (`_em_voo`, la embaixo, perto da trava da rodada). Os
    quatro funis: `_subir_parte_no_youtube`, `_youtube_dos_builds`,
    `_tiktok_das_historias` e `_tiktok_dos_builds` — todo caminho que sobe
    video passa por um deles (06/10/2026)."""
    import functools

    def decorar(funcao):
        @functools.wraps(funcao)
        def envolta(alvo, *args, **kwargs):
            with _em_voo(canal, getattr(alvo, "id", str(alvo)), destino):
                return funcao(alvo, *args, **kwargs)
        return envolta
    return decorar


def _prova_ok(laudo):
    """A regra mora no ledger de builds; aqui e so a porta.

    Nunca levanta: um laudo mal formado nao pode impedir o REGISTRO da
    publicacao. Perder a linha do ledger e pior do que perder a prova — foi
    a linha faltando que deixou os dois TikToks zerados por 49 publicacoes.
    """
    try:
        from builds.publicar.metricas import prova_ok
        return prova_ok(laudo)
    except Exception:                                          # noqa: BLE001
        return None


# Quanto esperar a rede voltar antes de desistir do horario. Numeros vindos
# do caso real: a maquina voltou de queda de energia as 03:34 e o DNS ainda
# nao resolvia as 06:07 — mas resolvia muito antes das 10:00. Cinco minutos
# de paciencia cobrem religar roteador/modem; mais que isso ja e problema de
# verdade e o horario seguinte tenta de novo.
ESPERA_DE_REDE_S = 300.0
ALVOS_DE_REDE = ("studio.youtube.com", "www.tiktok.com")
# `oauth2.googleapis.com` ENTRA em 05/10/2026: e o token da API (id do video
# pelo canal, capa, conferencia), e na madrugada de 04/10 o 23:37 morreu com
# SSLError justamente nos pedidos a ele. Mas ele e CONFERIDO, nao exigido:
# sem a API o video sai do mesmo jeito (so sem capa e sem o id pelo canal), e
# "nao sei" nunca barra video — exigir aqui trocaria um enfeite pelo horario.
ALVOS_AVISADOS = ("oauth2.googleapis.com",)
PRAZO_DO_TLS_S = 10.0


def _conexao_tls(alvo: str, prazo: float = PRAZO_DO_TLS_S) -> str:
    """`""` se um aperto de mao TLS com `alvo`:443 fecha; senao, o porque.

    Resolver o nome nao basta: na madrugada de 05/10/2026 o DNS respondia e a
    conexao morria no TLS (`SSLEOFError`), e o 23:37 de 04/10 caiu inteiro
    (4 envios) com a guarda de rede dizendo que estava tudo bem.
    """
    import socket
    import ssl
    try:
        socket.getaddrinfo(alvo, 443)
    except OSError as exc:
        return f"nao resolve ({type(exc).__name__})"
    try:
        contexto = ssl.create_default_context()
        with socket.create_connection((alvo, 443), timeout=prazo) as bruto:
            with contexto.wrap_socket(bruto, server_hostname=alvo):
                pass
    except (OSError, ssl.SSLError) as exc:
        return f"TLS falhou ({type(exc).__name__}: {str(exc)[:80]})"
    return ""


def esperar_a_rede(*, limite: float = ESPERA_DE_REDE_S, log=None) -> bool:
    """Espera a rede de VERDADE (DNS e TLS). `False` quando desiste.

    POR QUE ISTO EXISTE: em 11/09/2026 a queda de energia derrubou o PC. Ele
    voltou as 03:34, as tarefas das 06:07, 07:07 e 08:07 dispararam em dia,
    e as tres morreram em `net::ERR_NAME_NOT_RESOLVED` — a rede nao tinha
    voltado junto. Tres horarios perdidos por uma coisa que se resolve
    esperando.

    Ate 05/10/2026 isto so resolvia o NOME. Na madrugada de 05/10 o DNS
    respondia e o TLS morria (`SSLEOFError`): a guarda dizia "rede ok" e o
    Chrome estourava 90 s depois. Agora cada alvo precisa fechar um aperto
    de mao TLS (`_conexao_tls`) — ainda barato (milissegundos), e e o passo
    que falhava. Espera crescente para nao martelar a rede enquanto sobe.
    """
    import time

    log = log or _linha
    fim = time.monotonic() + max(0.0, float(limite))
    espera, avisou = 1.0, False
    while True:
        faltou, porque = "", ""
        for alvo in ALVOS_DE_REDE:
            porque = _conexao_tls(alvo)
            if porque:
                faltou = alvo
                break
        if not faltou:
            if avisou:
                log("[rede] voltou; sigo com a postagem.")
            for opcional in ALVOS_AVISADOS:
                motivo = _conexao_tls(opcional)
                if motivo:
                    log(f"[rede] {opcional}: {motivo}; publico assim mesmo "
                        "(sem a API: sem capa e sem o id pelo canal).")
            return True
        if time.monotonic() >= fim:
            log(f"[rede] {faltou}: {porque} depois de {limite:.0f}s; "
                "desisto deste horario.")
            return False
        if not avisou:
            log(f"[rede] {faltou}: {porque}; espero ate {limite:.0f}s.")
            avisou = True
        time.sleep(min(espera, max(0.0, fim - time.monotonic())))
        espera = min(espera * 2, 15.0)


# --------------------------------------------------------------- historias
# Quantos candidatos a fila pode descartar antes de desistir do dia. Um teto
# existe porque cada vistoria decodifica o mp4: sem ele, um acervo todo
# reprovado viraria meia hora de ffmpeg no meio da noite.
TENTATIVAS = 6


def _tipo_da_fonte(fonte_id: str) -> str:
    """O tipo (favela, normal, babaca) daquela historia. `""` se nao der.

    O tipo esta no roteiro, e ler roteiro custa disco: a fila tem dezenas de
    partes e poucas historias, entao a resposta e lembrada por fonte durante
    a rodada. Sem tipo nao e erro — historia feita antes dos tipos existirem
    e classificada pelo molde, e o que sobrar fica no fim da fila, na ordem
    em que veio.
    """
    if fonte_id in _TIPOS_LEMBRADOS:
        return _TIPOS_LEMBRADOS[fonte_id]
    tipo = ""
    try:
        from contos.roteiro import roteiro as R, serie as S
        tipo = S.tipo_da_historia(R.carregar(fonte_id)) or ""
    except Exception:                                          # noqa: BLE001
        tipo = ""
    _TIPOS_LEMBRADOS[fonte_id] = tipo
    return tipo


_TIPOS_LEMBRADOS: dict = {}


def _no_rodizio_dos_tipos(fila: list, publicados: list) -> list:
    """A fila reordenada pela vez de cada tipo. So a ORDEM muda.

    Decisao do Adrian (17/09/2026): tres tipos de historia no ar ao mesmo
    tempo — favela, normal e babaca — com os horarios em rodizio entre eles.
    Sem isto a fila esgota uma serie inteira antes de tocar na proxima, e
    quem abre o perfil ve seis partes do mesmo tipo em seguida.

    O PEDIDO MANUAL CONTINUA VENCENDO, e e por isso que isto nao e uma
    chamada direta: `_prioridades()` e um pedido de pessoa ("quero ver este
    video no ar ja"), e o rodizio, aplicado por cima, o desfaria em
    silencio. Entao os pedidos ficam grudados na frente e o rodizio ordena o
    resto.

    A ORDEM DAS PARTES SOBREVIVE por construcao: todas as partes de uma
    historia tem o mesmo `fonte_id`, logo o mesmo roteiro e o mesmo tipo, e
    `ordenar_por_tipo` preserva a ordem relativa DENTRO de cada tipo. A
    guarda de ordem no destino continua valendo por cima disso.
    """
    try:
        from contos.publicar import tipos as T
    except Exception:                                          # noqa: BLE001
        return fila
    pedidos = set(_prioridades())
    frente = [v for v in fila if v.id in pedidos]
    resto = [v for v in fila if v.id not in pedidos]
    try:
        # O MESMO CALLBACK NOS DOIS, e isto nao e economia: ate 17/09/2026
        # `ordenar_por_tipo` pedia o tipo do VIDEO e `tipos_das_ultimas` o da
        # FONTE, e quem passasse a mesma funcao nos dois (o caminho obvio)
        # tinha a fila inteira caindo no balde "sem tipo". O contrato foi
        # unificado no modulo: uma pergunta, uma assinatura.
        ultimos = T.tipos_das_ultimas(publicados, _tipo_da_fonte,
                                      "youtube", publicado=_saiu)
        # O TETO POR FONTE JA FOI APLICADO acima (`_sem_fonte_cheia`), entao
        # `cheias` aqui e vazio de proposito: passar a lista de novo seria
        # dois donos para a mesma regra, e o segundo envelhece.
        resto = T.ordenar_por_tipo(resto, ultimos, _tipo_da_fonte)
    except Exception as exc:                                   # noqa: BLE001
        # ORDENAR E MELHORIA, e nunca motivo de horario vazio.
        _linha(f"[postar] o rodizio de tipo falhou ({type(exc).__name__}); "
               f"a fila segue na ordem anterior.")
        return fila
    return frente + resto


def fila_de_historias() -> list:
    """As partes pendentes, NA ORDEM em que devem sair.

    DUAS REGRAS, nesta prioridade:

    1. TERMINA O QUE COMECOU. Serie com parte no ar e compromisso: quem viu a
       parte 2 e nunca recebe a 3 e o pior resultado possivel, pior do que
       qualquer atraso. Entao historia ja iniciada vem primeiro, sempre.
    2. DEPOIS, A MAIS NOVA. Entre as que ainda nao comecaram, sai a MAIS
       RECENTE — e onde esta o conteudo feito com a abordagem nova. Postar da
       mais antiga para a mais nova (como era) faria as melhorias de 08/09
       aparecerem so depois de 38 dias de estoque velho.
       EXCETO a que vai passar do prazo de frescor (6 dias, decisao
       `lote-frescor` de 30/09/2026): essa vem antes das outras novas, a mais
       velha primeiro (`_ordenar_pela_serie`).

    Dentro de uma historia, sempre a MENOR parte que falta.
    """
    from contos.publicar import catalogo, serie

    linhas = serie.publicados()
    publicados = [l for l in linhas if _saiu(l)]
    # O apagado do canal nunca volta a fila (21/10/2026, ver `_builds_prontos`).
    from builds.publicar import metricas as _metricas
    apagados = _metricas.apagados(linhas, None)
    # QUALQUER PLATAFORMA CONTA. Em 15/09/2026 a fila passou a contar so o
    # YouTube (para a parte que so foi ao TikTok nao sumir do YouTube), e a
    # revisao adversarial mediu o preco: com o YouTube na cota o dia inteiro,
    # a mesma parte voltava a frente em todo horario, o TikTok ja a tinha e
    # postava 1 de 6 (antes, 6 de 6). Horario vazio e pior que buraco no
    # YouTube. O conserto de verdade e uma fila POR PLATAFORMA.
    ja = {l.get("video_id") for l in publicados}
    videos = [v for v in catalogo.listar() if v.perfil == "celular"]
    comecadas = {v.fonte_id for v in videos if v.id in ja}
    # SEM BURACO NA SERIE. O catalogo lista cada mp4 assim que ele existe, e a
    # agenda renderiza as partes seguintes mesmo quando uma falha (imagem que
    # nao veio, tela dividida que nao montou). Sem isto a parte 3 ia ao ar sem
    # a 2 existir. A parte anterior conta se tem mp4 OU se ja esta no ar — mp4
    # apagado depois de publicado nao pode travar a serie para sempre.
    tem = {(v.fonte_id, int(v.parte or 0)) for v in videos}
    tem |= {(str(l.get("fonte_id")), int(l.get("parte") or 0))
            for l in publicados}
    pendentes = [v for v in videos if v.id not in ja and v.id not in apagados
                 and all((v.fonte_id, n) in tem
                         for n in range(1, int(v.parte or 1)))]
    # A QUE VAI PASSAR DO PRAZO DE FRESCOR vem antes das outras novas
    # (30/09/2026, decisao `lote-frescor`): ver `_ordenar_pela_serie`.
    criado = {f: _criado_da_fonte(f, [v for v in videos if v.fonte_id == f])
              for f in {v.fonte_id for v in pendentes}}
    fila = _ordenar_pela_serie(pendentes, comecadas, criado)
    # FURAR A FILA PELO CAMINHO NORMAL. Pedido dele em 14/09/2026: ver o
    # formato novo no ar ja, e nao depois de tres series terminarem. O video
    # pedido vai para a frente e passa pelas MESMAS guardas (vistoria, parecer,
    # um-por-horario, grade do TikTok); se nao passar, a fila segue como era.
    # O pedido se apaga sozinho: publicado, o video deixa de estar pendente.
    ordem = {video_id: i for i, video_id in enumerate(_prioridades())}
    if ordem:
        fila.sort(key=lambda v: (0, ordem[v.id]) if v.id in ordem else (1, 0))

    # TITULO JA NO AR TAMBEM SAI DAQUI. Nas historias isto quase nunca
    # dispara — o titulo carrega "(Parte N/6)", entao duas partes nunca
    # colidem. Entra pela simetria e por UM caso real possivel: uma historia
    # recriada com outro numero sai com o mesmo titulo da anterior, e o id
    # novo passaria pela deduplicacao sem ninguem notar.
    # O TETO POR HISTORIA VALE PARA O PERFIL INTEIRO, e nao so para a
    # recuperacao (decisao do Adrian, 17/09/2026). Esta fila prefere
    # "terminar a serie comecada" — entao, sozinha, uma historia ocupava ate
    # seis horarios num dia. Foi parte do que ele viu no perfil em 16/09, e
    # nao so a recuperacao. Desde 19/10/2026 esta e a fila do YOUTUBE (o
    # TikTok tem a sua, `_vez_do_tiktok_historias`), e o teto que ela confere
    # e o do YouTube; o do TikTok mora na fila dele.
    #
    # A ordem das partes DENTRO da serie continua sagrada: o teto so decide
    # QUAL serie anda hoje, nunca em que ordem as partes dela saem.
    fila = _sem_a_conferir(fila, "historias")
    fila = _sem_fonte_cheia(fila, "historias", plataformas=("youtube",))

    novos, repetidos = _sem_titulo_repetido(fila, "historias")
    if repetidos:
        _linha(f"[postar] {len(repetidos)} parte(s) fora da fila por titulo "
               f"ja publicado: {', '.join(v.id for v in repetidos[:3])}"
               f"{'...' if len(repetidos) > 3 else ''}")
    if novos:
        return _no_rodizio_dos_tipos(novos, publicados)
    if repetidos:
        # A VALVULA FECHOU EM 17/09/2026, por decisao do Adrian depois de ver
        # conteudo repetido no perfil. Ela liberava "o menos pior" quando a
        # fila ficava vazia — e "o menos pior" era publicar de novo um titulo
        # que ja estava no ar.
        #
        # Repetir e pior que nao postar: o horario vazio custa um post, e o
        # repetido custa a confianca de quem abre o perfil e ve a mesma coisa
        # duas vezes. A regra "nao ficar sem video" continua valendo para
        # estoque e falha — nao para cobrir buraco com repeticao.
        _linha("[postar] historias: TODAS as partes pendentes tem titulo ja "
               "publicado; o horario fica SEM post (a valvula fechou).")
    return []


# `historias/outputs/_publicar/prioridade.json`: {"videos": ["<id>", ...]}.
PRIORIDADE = (Path(__file__).resolve().parents[1] / "historias" / "outputs"
              / "_publicar" / "prioridade.json")


def _prioridades() -> list:
    """Os ids que furam a fila, na ordem pedida. Lista vazia se nao ha pedido."""
    try:
        with open(PRIORIDADE, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return []
    ids = dados.get("videos") if isinstance(dados, dict) else dados
    if not isinstance(ids, list):
        return []
    return [str(i).strip() for i in ids if str(i).strip()]


def _ao_contrario(texto: str) -> str:
    """Chave que ordena ao contrario um id crescente (`historia_00010`).

    `sorted` nao aceita `reverse` por campo, e inverter o numero e mais
    honesto do que multiplicar por -1 um id que nem sempre e numero.
    """
    numero = "".join(c for c in texto if c.isdigit())
    return f"{10 ** 9 - int(numero or 0):012d}"


# ------------------------------------------------------------------ frescor
# "ACEITO VIDEO DE ATE 6 DIAS; mudanca critica ganha re-render" — decisao do
# Adrian em 30/09/2026 (Grimorio `geral/lote-frescor`), junto com o lote
# semanal: as historias da semana nascem de segunda a quarta, e o video de
# domingo foi feito na segunda. E um valor dele, como `TETO_POR_FONTE_NO_DIA`.
PRAZO_DE_FRESCOR_DIAS = 6

# UM DIA DE FOLGA no aviso de "vai vencer", MEDIDO e nao chutado. Simulacao
# de 4 semanas de lote (historias de 6 partes a cada 3h45 de seg a qua,
# 07-22h, ate `agenda.alvo_do_lote`; reposicao abaixo do piso; 10 horarios;
# teto de 2 por serie no dia de grade), contando o que sai com mais de 6
# dias nas semanas 2 a 4 (210 publicacoes):
#   "a mais nova primeiro" (ate 30/09) ....... 24, a pior com 14,8 dias
#   vencendo sem folga (idade + saida >= 6) .. 15, a pior com 7,1 dias
#   vencendo com 1 dia de folga .............. 2, a pior com 6,1 dias
#   a mais VELHA primeiro, sempre (FIFO) ..... 2, a pior com 6,1 dias
# Sem folga, a serie so e vista vencendo quando as comecadas (que vem antes,
# sempre) ja ocupam o dia; com um dia, fica igual ao FIFO. Os 2 que sobram
# sao do volume do lote (o piso feito na quarta sai na terca seguinte), e
# nao da ordem.
FOLGA_DE_FRESCOR_DIAS = 1

_CRIADOS_LEMBRADOS: dict = {}


def _criado_da_fonte(fonte_id: str, partes=()):
    """Quando a historia NASCEU (`datetime`), ou `None` se nao da para saber.

    O `criado_em` do roteiro: "o video de domingo foi feito na segunda" fala
    da historia, e nao do mp4 — o reparo re-renderiza partes todo dia (a
    h34 nasceu em 26/09 e a p01 foi regravada em 29/09), e o mtime faria a
    historia velha parecer nova. Sem roteiro legivel, o mp4 MAIS VELHO da
    serie. Lembrado por fonte durante o processo, como o tipo.
    """
    from datetime import datetime
    if fonte_id in _CRIADOS_LEMBRADOS:
        return _CRIADOS_LEMBRADOS[fonte_id]
    quando = None
    try:
        from contos.roteiro import roteiro as R
        texto = str(R.carregar(fonte_id).get("criado_em") or "")
        quando = datetime.fromisoformat(texto) if texto else None
    except Exception:                                          # noqa: BLE001
        quando = None
    if quando is None:
        marcas = []
        for v in partes or ():
            try:
                marcas.append(float(getattr(v, "quando", 0) or 0))
            except (TypeError, ValueError):
                continue
        marcas = [m for m in marcas if m > 0]
        quando = datetime.fromtimestamp(min(marcas)) if marcas else None
    _CRIADOS_LEMBRADOS[fonte_id] = quando
    return quando


def _idade_em_dias(quando, agora=None):
    """Dias desde `quando` (`datetime`); `None` quando nao se sabe."""
    from datetime import datetime
    if quando is None:
        return None
    try:
        return ((agora or datetime.now()) - quando).total_seconds() / 86400
    except Exception:                                          # noqa: BLE001
        return None


def _series_vencendo(pendentes, criado: dict, agora=None) -> set:
    """As historias cuja ULTIMA parte, no ritmo do teto, passaria do prazo.

    Uma serie de N partes pendentes leva `ceil(N / TETO_POR_FONTE_NO_DIA)`
    dias de grade para sair inteira. Se a idade dela mais esse tempo, mais
    `FOLGA_DE_FRESCOR_DIAS`, chega a `PRAZO_DE_FRESCOR_DIAS`, ela nao pode
    mais esperar atras das mais novas. Conta de mao: nascida seg 10:00, 6
    partes (3 dias) -> vence a partir de qua 10:00 (2 + 3 + 1 = 6).

    ZERO: sem pendente, ou sem data de nascimento, nada vence — "nao sei"
    nunca reordena a fila.
    """
    from collections import Counter
    restam = Counter(v.fonte_id for v in pendentes or ())
    teto = max(1, int(TETO_POR_FONTE_NO_DIA))
    saida = set()
    for fonte, n in restam.items():
        idade = _idade_em_dias(criado.get(fonte), agora)
        if idade is None:
            continue
        if (idade + -(-n // teto) + FOLGA_DE_FRESCOR_DIAS
                >= PRAZO_DE_FRESCOR_DIAS):
            saida.add(fonte)
    return saida


def _ordenar_pela_serie(pendentes, comecadas, criado: dict,
                        agora=None) -> list:
    """A ordem da fila de historias, pura (sem disco): tres grupos.

    0. As COMECADAS, a mais velha primeiro — compromisso com quem ja viu.
    1. As que VAO PASSAR DO PRAZO de frescor (`_series_vencendo`), a que
       nasceu primeiro na frente.
    2. As outras novas, a MAIS NOVA primeiro (a regra de 08/09).

    Dentro de cada historia, a menor parte que falta. O grupo 1 e de
    30/09/2026: com o lote (historias de seg a qua), "a mais nova primeiro"
    empurra a historia de segunda para depois das de quarta a semana
    inteira, e o estoque que sobra da semana (o piso de 20) so saia quando
    nada mais novo existisse — com 12 dias.
    """
    vencendo = _series_vencendo(pendentes, criado, agora)

    def chave(v):
        fonte = v.fonte_id
        if fonte in comecadas:
            return (0, fonte, v.parte or 0)
        if fonte in vencendo:
            nasceu = criado[fonte].strftime("%Y%m%d%H%M%S")
            return (1, f"{nasceu}|{fonte}", v.parte or 0)
        return (2, _ao_contrario(fonte), v.parte or 0)

    return sorted(pendentes, key=chave)


# ------------------------------------------------------- a noite do YouTube
# O VIDEO DA NOITE LEVA O DIA (decisao `publicacao/historias-21h-e-parte-
# seguinte`, 19/10/2026). Medido na analise dos videos (YouTube, historias,
# 24 dias): o mais visto do dia levou 93% das views (mediana) e saiu entre
# 21h e 23h em 23 deles. Medido de novo antes deste codigo (videos de 3 a 40
# dias, 19/10 13:4x): no 21:37 a mediana e 254 views (25 videos, 17 com 100+);
# no 22:37, 6; no 23:37, 4 — o horario e o das 21h.
#
# "O MELHOR VIDEO PRONTO" = A PARTE 1 DE UMA SERIE QUE AINDA NAO COMECOU
# (em nenhum destino), a primeira na ordem da fila (que ja respeita o
# frescor), a limpa antes da retida/vetada. Por que a parte 1: quem ve o
# video da noite nao veio da parte anterior (a seguinte recebe ~0,6 view a
# cada 100 da que bombou), entao o video que mais gente nova ve deve ser a
# porta de entrada da historia. Nos videos das 21h: parte 1, mediana 328,5
# (10 videos, 7 com 100+); outras partes, 210 (15, 10 com 100+). E sinal
# fraco: a diferenca nao passa do acaso (so as 21h, p = 0,93; na noite
# inteira, p = 0,91). O que esta provado e o horario; a parte 1 e a escolha
# por razao (a porta de entrada), e a analise mede.
#
# A RESERVA E SO DE ORDEM, NUNCA TIRA DA FILA: de dia a melhor vai para o fim
# (sai se nada mais puder sair), no primeiro horario da noite ainda sem
# video no YouTube vai para a frente (atras dos pedidos manuais). Tirar da
# fila furaria a valvula de qualidade — com a melhor sendo a unica parte
# limpa, o horario do dia sairia com uma RETIDA, e a retida so sai quando
# nada mais pode (decisao de 27/09). Pela mesma razao, entre as retidas a
# consertada continua na frente (decisao de 05/10).
NOITE_DAS_HISTORIAS = (21, 22, 23)


def _melhor_da_noite(fila: list, comecadas) -> object | None:
    """A parte 1 de serie nao comecada, a primeira da fila; a limpa antes.

    Le o veto e a retencao de arquivo (sem vistoria, sem IA). `None` sem
    nenhuma parte 1 de serie nova.
    """
    novas = [v for v in fila or ()
             if int(getattr(v, "parte", 0) or 0) == 1
             and getattr(v, "fonte_id", None) not in comecadas]
    if not novas:
        return None
    for v in novas:
        try:
            if not _veto_lembrado(v) and not _retencao(v):
                return v
        except Exception:                                      # noqa: BLE001
            continue
    return novas[0]


def _noite_sem_video(publicados, agora=None) -> bool:
    """O horario da rodada e o PRIMEIRO da noite (21h–23h) sem video do
    YouTube neste dia de grade? (No 21:37, sempre; no 22:37, se o 21:37 nao
    saiu; no 23:37, se nenhum dos dois.) Mesma chave de horario da guarda
    (`conferencia.chave_do_horario`); fora da noite, False."""
    from datetime import datetime
    from builds.publicar import conferencia, metricas
    agora = agora or datetime.now()
    dia, hora = conferencia.chave_do_horario(agora, "youtube")
    if hora not in NOITE_DAS_HISTORIAS:
        return False
    for linha in publicados or ():
        if str(linha.get("plataforma") or "youtube").lower() != "youtube":
            continue
        if not metricas.publicado(linha):
            continue
        chave = conferencia.chave_do_horario(linha.get("quando"), "youtube")
        if (chave and chave[0] == dia and chave[1] in NOITE_DAS_HISTORIAS
                and chave[1] < hora):
            return False
    return True


def _reordenar_pela_noite(fila: list, melhor, *, na_noite: bool,
                          de_dia: bool, pedidos=()) -> list:
    """A regra pura: a SERIE de `melhor` (ela e as partes seguintes que estao
    na fila, na mesma ordem) vai a frente — atras dos pedidos manuais — quando
    `na_noite`, ao fim quando `de_dia`; senao a fila fica como esta. Fila de
    um so video, ou sem melhor, nao muda.

    A SERIE INTEIRA, e nao so a parte 1: `proxima_historia` segura as partes
    seguintes de uma serie atras da parte barrada PELA ORDEM da fila — com a
    parte 1 movida sozinha para o fim, a 2 viria antes dela e sairia sem a 1
    (o `test_adiada_nao_sai_limpa` pegou exatamente isso)."""
    if melhor is None or len(fila) < 2 or melhor not in fila:
        return list(fila)
    fonte = getattr(melhor, "fonte_id", None)
    serie = [v for v in fila if getattr(v, "fonte_id", None) == fonte]
    resto = [v for v in fila if getattr(v, "fonte_id", None) != fonte]
    if not resto:
        return list(fila)
    if na_noite:
        frente = [v for v in resto if getattr(v, "id", None) in pedidos]
        return frente + serie + [v for v in resto if v not in frente]
    if de_dia:
        return resto + serie
    return list(fila)


def _reserva_da_noite(fila: list, publicados=None, comecadas=None,
                      agora=None) -> list:
    """A fila do YouTube com a melhor parte guardada para a noite.

    `publicados`/`comecadas` vem do ledger das historias quando nao passados
    (comecada = serie com alguma parte publicada em qualquer destino, o
    criterio de `fila_de_historias`). Nunca levanta e nunca tira ninguem:
    errou, devolve a fila como veio.
    """
    from datetime import datetime
    try:
        if not fila:
            return fila
        agora = agora or datetime.now()
        if publicados is None:
            publicados = [l for l in _publicados_do_canal("historias")
                          if _saiu(l)]
        if comecadas is None:
            comecadas = {str(l.get("fonte_id") or str(l.get("video_id") or "")
                             .split(":")[0]) for l in publicados}
        melhor = _melhor_da_noite(fila, comecadas)
        if melhor is None:
            if grade.slot(agora) == NOITE_DAS_HISTORIAS[0]:
                _linha("[postar] historias: nenhuma parte 1 de serie nova "
                       "para a noite; sai a fila normal.")
            return fila
        na_noite = _noite_sem_video(publicados, agora)
        de_dia = grade.slot(agora) not in NOITE_DAS_HISTORIAS
        nova = _reordenar_pela_noite(fila, melhor, na_noite=na_noite,
                                     de_dia=de_dia, pedidos=set(_prioridades()))
        if na_noite:
            _linha(f"[postar] historias: a melhor parte pronta vai a noite: "
                   f"{melhor.id}.")
        return nova
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[postar] reserva da noite falhou ({type(exc).__name__}); a "
               "fila segue como estava.")
        return fila


# A IA VETA, MAS NAO CALA A GRADE. Quando nao da para PERGUNTAR (conta
# ocupada, site fora do ar, login caido), a vistoria tecnica ja passou e o
# video sai — silencio da IA nao e reprovacao. O veto so vale quando ela
# respondeu REPROVADO de verdade.
PUBLICAR_SEM_PARECER = True

# A POSTAGEM NAO PERGUNTA AO GEMINI (pedido dele em 15/09/2026, 02:25: "o
# gemini parece estar mais atrasando do que ajudando... amanha nos horarios
# certos seja postar"). O parecer e servico da madrugada, uma passada por
# video. Na hora de postar vale o que ficou gravado: veto de pe barra (ate o
# reparo gastar a sua rodada), aprovado sai, e video sem parecer sai com a
# vistoria tecnica. Perguntar aqui chegou a segurar o horario 15 minutos.
PEDIR_PARECER_NA_POSTAGEM = False


def _pela_folha(ficha: dict) -> bool:
    """A aprovacao veio so das miniaturas? Entao ela nao dispensa perguntar.

    Um "aprovado" da folha de contato e fraco: ela nao mostra movimento,
    corte nem audio. Vale como ultimo recurso na hora, nao como cache que
    poupa a pergunta ao Gemini na proxima vez.
    """
    return not str(ficha.get("vista") or "").startswith("video")


def avisar_reprovacao(alvo, veredito: dict) -> bool:
    """Conta no Telegram que a IA barrou um video. Nunca derruba a postagem.

    Um veto silencioso e pior do que nenhum: o horario passa em branco e nao
    ha nada na tela dizendo por que.
    """
    import subprocess
    motivos = "; ".join(veredito.get("motivos") or [])[:400]
    texto = ("🤖 *A IA reprovou um vídeo*\n"
             f"{alvo.id}\n{motivos}\n"
             "Ele fica fora da fila; a grade segue com o próximo.")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "remoto", "--avisar", texto],
            cwd=str(RAIZ), capture_output=True, timeout=90,
            creationflags=NO_WINDOW)
        return proc.returncode == 0
    except Exception:                                          # noqa: BLE001
        return False


def _parecer_da_ia(alvo, roteiro: dict, laudo: dict) -> str:
    """`""` quando pode publicar; o motivo quando a IA vetou."""
    from contos.publicar import parecer

    # O QUE JA FOI DECIDIDO SOBRE ESTE ARQUIVO VALE. Esta funcao perguntava
    # sempre de novo e nunca lia o veredito em disco — o terceiro dono da
    # pergunta "pode sair?", que ficou de fora quando `qualidade.liberado`
    # unificou os outros dois. O preco: em 12/09/2026 o Gemini reprovou a
    # parte 3 da historia 4 as 06:14 depois de assistir 2:23 de video, e as
    # 15:34 ela foi para o YouTube e para o TikTok. Perguntar de novo nao e
    # rigor; e dar uma segunda chance a quem ja foi reprovado, num momento em
    # que a conta boa pode estar ocupada.
    #
    # `lembrado` devolve `None` quando o mp4 mudou desde o veredito, entao um
    # re-render continua merecendo pergunta nova.
    #
    # A PASSADA DE CONSERTO FOI GASTA E SAI (uma so desde 15/09/2026; eram
    # tres rodadas antes). Veto vencido nao e perguntado de novo: perguntar
    # daria a mesma reprovacao e travaria o horario outra vez.
    if _veto_vencido(alvo):
        _linha(f"[parecer] {alvo.id}: a IA reprovou, mas a passada de "
               "conserto ja foi gasta; sai assim.")
        return ""
    try:
        ficha = parecer.lembrado(alvo)
    except Exception as exc:                                   # noqa: BLE001
        # Ilegivel: BARRA (e nao derruba a rodada inteira, que era o que a
        # excecao fazia ate 14/10/2026). Normalmente `_retencao` ja reteve.
        return (f"{alvo.id}: nao consegui ler os pareceres da IA "
                f"({type(exc).__name__}); nao sai sem saber se foi vetada")
    if ficha and not ficha.get("aprovado"):
        motivos = "; ".join(ficha.get("motivos") or [])[:300]
        _linha(f"[parecer] {alvo.id}: veto ja registrado em "
               f"{ficha.get('quando')} ({ficha.get('vista')}).")
        return f"{alvo.id}: a IA REPROVOU — {motivos}"
    if ficha and ficha.get("aprovado") and not _pela_folha(ficha):
        _linha(f"[parecer] {alvo.id}: aprovado em {ficha.get('quando')} "
               f"({ficha.get('vista')}); nao pergunto de novo.")
        return ""
    if not PEDIR_PARECER_NA_POSTAGEM:
        _linha(f"[parecer] {alvo.id}: "
               + ("aprovado pela folha" if ficha else "sem parecer gravado")
               + "; a postagem nao pergunta ao Gemini, sai com a vistoria "
                 "tecnica.")
        return ""

    try:
        veredito = parecer.pedir(alvo, roteiro, alvo.parte, laudo=laudo,
                                 log=_linha)
    except parecer.SemParecer as exc:
        recado = f"{alvo.id}: nao deu para pedir o parecer da IA ({exc})"
        if PUBLICAR_SEM_PARECER:
            _linha(f"[parecer] {recado} — publico assim mesmo, a vistoria "
                   "tecnica passou.")
            return ""
        return recado
    if veredito["aprovado"]:
        return ""
    motivos = "; ".join(veredito["motivos"])[:300]
    avisar_reprovacao(alvo, veredito)
    return f"{alvo.id}: a IA REPROVOU — {motivos}"


def _atualizar_metricas() -> None:
    """Busca views e retencao dos dois canais — uma vez por dia.

    AQUI, e nao na rodada de criacao. A tentacao era pendurar em
    `historias/contos/pipeline/agenda.py`, que tambem dispara oito vezes; mas
    ela SAI CEDO em tres condicoes normais — pipeline pausada, outra rodada em
    andamento, agenda desligada — e nas tres a metrica simplesmente nao
    aconteceria. Gatilho que some quando a maquina esta ocupada nao serve para
    medir.

    A grade de publicacao nao tem esse problema: ela roda nos oito horarios
    aconteca o que acontecer, ja esperou a rede subir e ja sabe avisar no
    Telegram. E o momento e o certo — o `youtube_id` que falta e justamente o
    do video que acabou de subir.

    Depois do `avisar`, de proposito: metrica nao pode atrasar o aviso da
    publicacao. E sem tocar no codigo de saida — ele responde "publiquei?", e
    envenena-lo com falha de metrica faria o Agendador acusar erro num
    horario que deu certo.
    """
    try:
        from builds.publicar import metricas
        if metricas.atualizar_uma_vez_por_dia(log=_linha):
            _linha("[metricas] atualizadas (primeira vez hoje).")
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[metricas] nao atualizei: {type(exc).__name__}: {exc}")


def _veto_vencido(alvo) -> bool:
    """A passada de conserto foi gasta e a IA ainda reprova: sai assim.

    Uma passada so desde 15/09/2026 (eram tres rodadas antes). A regra mora
    em `contos.publicar.qualidade.veto_vencido`, a mesma que a auditoria e o
    freio de estoque consultam.

    A PARTE CONSERTADA NAO E VETO VENCIDO (05/10/2026). O reparo que refez as
    cenas tambem gasta a passada, e ate aqui a parte consertada saia com "o
    veto da IA venceu" — um veto do mp4 ANTIGO. Ela e outra coisa
    (`_consertada`): ninguem viu o mp4 novo ainda.
    """
    if _consertada(alvo):
        return False
    try:
        from contos.publicar import qualidade
        return qualidade.veto_vencido(alvo)
    except Exception:                                          # noqa: BLE001
        return False


def _consertado(alvo) -> bool:
    """A passada do veto foi gasta com um conserto APLICADO (cenas refeitas,
    re-render), e nao com a desistencia da IA?

    A regra mora em `contos.pipeline.reparo.consertado`. Nunca levanta.
    """
    try:
        from contos.pipeline import reparo
        return reparo.consertado(alvo.id)
    except Exception:                                          # noqa: BLE001
        return False


def _veto_lembrado(alvo) -> str:
    """O veto da IA ja gravado para este arquivo, se ainda vale. `""` se nao.

    E LER UM ARQUIVO, e nao decodificar o mp4, e por isso nao gasta
    `TENTATIVAS`. Em 13/09/2026 os seis primeiros da fila eram os seis
    barrados, o teto de seis se esgotava neles, e onze aprovados logo atras
    nunca eram vistos: nenhuma historia saiu nos horarios.

    `parecer.lembrado` primeiro (compara o mtime: e o parecer DESTE mp4). O
    veto de um mp4 antigo so vale se o video nao foi consertado depois dele:
    re-render sem conserto nao apaga o veto (15/09/2026), conserto sim — a
    parte consertada passa pela valvula (`_retencao`), e nao pelo veto.
    """
    try:
        from contos.publicar import parecer
        ficha = parecer.lembrado(alvo)
        if ficha is None and not _consertada(alvo):
            ficha = parecer.veto_por_id(alvo)
    except Exception:                                          # noqa: BLE001
        return ""
    if not ficha or ficha.get("aprovado") or _veto_vencido(alvo):
        return ""
    motivos = "; ".join(ficha.get("motivos") or [])[:300]
    return f"{alvo.id}: a IA REPROVOU — {motivos}"


# A SITUACAO de uma parte reprovada que o reparo REFEZ depois do veto e cujo
# mp4 novo ninguem assistiu. Quem a reconhece e `contos.publicar.parecer`
# (`estado_do_video`/`consertado`: mp4 mais novo que o parecer E "refiz" no
# `_reparos.json` depois dele); aqui so se le a resposta.
CONSERTADA = "consertado"


def _situacao_do_parecer(alvo) -> str:
    """"aprovado" | "reprovado" | "nao_assistido" | "consertado" | "".

    O ultimo parecer do VIDEO, pelo id: um re-render sem parecer novo nao
    apaga o que foi dito dele. "consertado" vem de `parecer.estado_do_video`
    (um criterio so, la); sem ela, a resposta e a de antes
    (`situacao_do_video`). Nunca levanta.
    """
    try:
        from contos.publicar import parecer
        estado = getattr(parecer, "estado_do_video", None)
        if callable(estado):
            return str(estado(alvo) or "")
        return parecer.situacao_do_video(alvo)
    except Exception:                                          # noqa: BLE001
        return ""


def _consertada(alvo) -> bool:
    """Reprovada, consertada depois do veto, e a IA nao viu o mp4 novo?"""
    return _situacao_do_parecer(alvo) == CONSERTADA


# O VETO QUE FALHAVA ABERTO (auditoria de 11/10/2026, verificada em 14/10).
# Desde 11/10 `parecer._lembretes` levanta quando `_pareceres.json` esta
# ilegivel ou trancado, em vez de virar `{}` — mas todo leitor da publicacao
# engolia a excecao e respondia "sem parecer": `_veto_lembrado` dava "",
# `_retencao` dava "" (a `situacao_do_video` do parecer tambem engole), e no
# ultimo recurso fora de ordem (`adiadas`) a parte reprovada saia LIMPA, sem
# marca. Agora "nao sei ler os pareceres" e RETIDA: so sai quando o horario
# ficaria vazio, e sai marcada `[qualidade]` na lista a conferir — a mesma
# classe do "ninguem assistiu". O aviso vai ao diario uma vez por rodada.
_PARECERES_AVISADOS: list = []


def _pareceres_ilegiveis(alvo) -> str:
    """O motivo quando o arquivo dos pareceres NAO se le; "" quando se le.

    A pergunta e feita pela leitura que levanta (`parecer.lembrado`), e nao
    pelas que engolem. Nunca levanta.
    """
    try:
        from contos.publicar import parecer
        parecer.lembrado(alvo)
        return ""
    except Exception as exc:                                   # noqa: BLE001
        motivo = f"{type(exc).__name__}: {exc}"[:160]
    if not _PARECERES_AVISADOS:
        _PARECERES_AVISADOS.append(motivo)
        texto = (f"nao consegui ler os pareceres da IA ({motivo}); toda parte "
                 "de historia fica RETIDA (so sai se o horario ficaria vazio, "
                 "e marcada a conferir) ate o arquivo voltar a se ler")
        _linha(f"[postar] {texto}")
        try:
            from builds import atividade
            atividade.registrar("publicacao", atividade.ERRO, texto,
                                "historias", etapa="publicar.parecer")
        except Exception:                                      # noqa: BLE001
            pass
    return motivo


def _retencao(alvo) -> str:
    """Por que a parte fica RETIDA; `""` quando nao fica.

    A VALVULA DE QUALIDADE, decisao do Adrian no plano de 27/09/2026 (S2):
    "retido = 'a IA reprovou' ou 'parecer so pela folha'; retido so sai
    quando nao houver outro candidato para o horario; quando sair, fica
    marcado na lista 'a conferir'". As duas causas sao lidas de arquivo —
    nao gastam `TENTATIVAS` nem perguntam a ninguem.

    Ate 28/09 o veto VENCIDO (as rodadas de conserto acabaram) saia na hora,
    com "a IA reprovou, mas as rodadas de conserto acabaram; sai assim".
    Medido na fila daquela madrugada: 10 das 19 partes estavam assim, e a
    primeira delas (h32 p05) saiu as 06:37 no lugar de qualquer outra.

    O veto ainda de pe tambem e "a IA reprovou": `proxima_historia` o segura
    antes (`_veto_lembrado`), e aqui ele so importa para a marca, quando sai
    como ultimo recurso. Sem parecer nenhum NAO e retido: a postagem nao
    pergunta ao Gemini, e reter tudo que nao tem ficha pararia o canal.

    A CONSERTADA (05/10/2026) continua retida: o reparo refez as cenas depois
    do veto, mas ninguem assistiu ao mp4 novo, e "consertado" nao e
    "aprovado". Ela so ganha a FRENTE das outras retidas no ultimo recurso
    (`proxima_historia`). Medido na fila de 05/10: 57 de 58 partes retidas,
    37 delas ja consertadas — todas saiam com "o veto venceu", o texto do
    mp4 antigo. A IA NAO olha de novo o mp4 consertado: decisao do Adrian
    de 05/10/2026, 12:32 (`historias/reolhar-depois-do-conserto`, opcao
    "nao" — uma passada so; a consertada so ganha prioridade).
    """
    ilegivel = _pareceres_ilegiveis(alvo)
    if ilegivel:
        return (f"{alvo.id}: nao consegui ler os pareceres da IA "
                f"({ilegivel}); fica retida enquanto o arquivo nao se ler")
    situacao = _situacao_do_parecer(alvo)
    if situacao == CONSERTADA:
        return (f"{alvo.id}: a IA reprovou, o reparo refez as cenas e "
                "ninguem assistiu ao video consertado")
    if situacao == "reprovado":
        return (f"{alvo.id}: a IA reprovou"
                + (" e a passada de conserto ja foi gasta"
                   if _veto_vencido(alvo) else ""))
    if situacao == "nao_assistido":
        return f"{alvo.id}: parecer so pela folha de contato (ninguem assistiu)"
    return ""


# O comeco do `estado` da marca "a conferir" de uma parte que saiu RETIDA. Nao
# sai sozinha como a de audio: quem confere e uma pessoa.
PREFIXO_DA_RETENCAO = "[qualidade] "


def _marcar_retido(alvo, retencao: str,
                   destinos=("youtube", "tiktok")) -> None:
    """A parte retida que SAIU vai para a lista "a conferir" de cada destino
    ONDE ELA SAIU — e so nele.

    Ate 05/10/2026 marcava os dois, "porque a recuperacao do TikTok e extra".
    O preco, medido: `historia_00034:celular:p06` e `historia_00042:celular:
    p06` sairam no YouTube, falharam no TikTok (legenda adiada) e ficaram
    marcadas "a conferir" la — `_fila_do_tiktok` as descarta, entao o fim
    das duas series nunca chegou ao TikTok, e a mensagem do erro prometia
    "volta na fila de atrasados". Marca em destino onde a parte nao esta
    nao protege ninguem de nada: so a esconde da recuperacao. Quem chama
    passa `destinos` = onde saiu de verdade (TikTok so confirmado).

    So DEPOIS de sair: marcar antes tiraria da fila a parte que ainda nao
    foi a lugar nenhum. Nunca levanta: a publicacao ja aconteceu.
    """
    try:
        from builds.publicar import desfecho
    except Exception:                                          # noqa: BLE001
        return
    for plataforma in destinos:
        try:
            desfecho.marcar_para_conferir(
                "historias", alvo.id, PREFIXO_DA_RETENCAO + retencao,
                plataforma, etapa="publicar.qualidade", erro=False,
                aviso=(f"{alvo.id} saiu RETIDA ({retencao[:140]}): nao havia "
                       f"outra parte para o horario. Esta na lista a conferir "
                       f"do {plataforma}."))
        except Exception as exc:                               # noqa: BLE001
            _linha(f"[postar] {alvo.id}: nao consegui por na lista a conferir "
                   f"do {plataforma} ({type(exc).__name__}).")


def _valvula_da_parte(ficha: dict, alvo) -> str:
    """Poe na ficha as marcas da valvula desta parte; devolve a retencao.

    UM LUGAR SO para as marcas (`veto_vencido`, `veto_ignorado`, `retido`,
    `consertada`), porque desde 05/10/2026 ha TRES caminhos que levam uma
    parte de historia ao ar: a rodada inteira (`postar_historia`), o "YouTube
    ja saiu nesta hora; levando so para o TikTok" (que a reposicao por rede
    usa) e a recuperacao do TikTok. So o primeiro marcava. Nunca levanta.
    """
    try:
        if _veto_vencido(alvo):
            ficha["veto_vencido"] = True
        elif _veto_lembrado(alvo):
            ficha["veto_ignorado"] = True
        retencao = _retencao(alvo)
    except Exception:                                          # noqa: BLE001
        return ""
    if retencao:
        ficha["retido"] = retencao
        if _consertada(alvo):
            ficha["consertada"] = True
    return retencao


def _retida_chegou_ao_tiktok(alvo, ficha: dict) -> None:
    """A parte que chega ao TikTok DEPOIS do YouTube passa pela valvula LA.

    Conferente, 05/10/2026: com a marca so onde a parte saiu (item 4 da
    varredura), a retida que saiu no YouTube e falhou no TikTok volta a
    chegar ao TikTok — pela recuperacao ou pelo "levando so para o TikTok".
    Nenhum dos dois marcava "[qualidade]" la nem gravava a valvula no
    diario: a parte reprovada pela IA ia ao ar no TikTok fora da lista que
    uma pessoa confere. Chame SO com o TikTok confirmado. Nunca levanta.
    """
    retencao = _valvula_da_parte(ficha, alvo)
    if retencao:
        _marcar_retido(alvo, retencao, ("tiktok",))
    _registrar_valvula(dict(ficha, feito=True))


def proxima_historia(*, vistoriar: bool = True):
    """A proxima parte PUBLICAVEL. `None` quando nao ha nenhuma.

    PULA o que a vistoria reprova em vez de desistir do dia. A primeira versao
    olhava so a fila e checava a qualidade depois — e a primeira da fila era a
    `historia_00001`, cujas imagens sao placeholder. Um video ruim na frente
    travaria o canal para sempre, e ele seria o primeiro video PUBLICO.
    """
    from contos.publicar import qualidade
    from contos.roteiro import roteiro as R

    recusados = []
    examinados = 0
    vetados, retidos = [], []
    # A SERIE ESPERA A PARTE BARRADA. Pedido dele em 14/09/2026, depois de a
    # historia 10 publicar a parte 6 antes da 5: parte barrada (veto ou
    # vistoria) segura as seguintes da MESMA historia, e a grade publica outra
    # serie no lugar. A seguinte so sai como ultimo recurso, la embaixo.
    bloqueadas, adiadas = set(), []
    from builds import travas
    # A NOITE ESCOLHE PRIMEIRO (19/10/2026): a melhor parte pronta fica para
    # o primeiro horario da noite sem video (`_reserva_da_noite`). E aqui, e
    # nao em `fila_de_historias`, porque e sobre QUAL parte sai AGORA — a
    # ordem da serie e da fila continua a mesma para quem a le.
    for alvo in _reserva_da_noite(fila_de_historias()):
        if not vistoriar:
            return alvo, recusados
        if alvo.fonte_id in bloqueadas:
            adiadas.append(alvo)
            continue
        # HISTORIA SENDO RENDERIZADA NAO SAI NESTE HORARIO. As 15:07 de
        # 14/09/2026 a postagem chegou a h9 p01 minutos depois de o reparo
        # regravar o mp4 dela; mais cedo, teria lido o arquivo no meio da
        # escrita. `Pipeline.render` segura esta trava enquanto escreve.
        if travas.ocupada(f"historias__render__{alvo.fonte_id}"):
            recusados.append(f"{alvo.id}: a historia esta sendo renderizada")
            bloqueadas.add(alvo.fonte_id)
            continue
        # O VETO JA GRAVADO NAO GASTA TENTATIVA. `TENTATIVAS` existe para nao
        # decodificar mp4 sem fim; gasto com veto lido de arquivo, ele deixava
        # os barrados da frente esconderem os aprovados de tras.
        veto = _veto_lembrado(alvo)
        if veto:
            recusados.append(veto)
            vetados.append(alvo)
            bloqueadas.add(alvo.fonte_id)
            continue
        # A VALVULA DE QUALIDADE (28/09/2026): veto vencido ou parecer so pela
        # folha ficam RETIDOS. Lido de arquivo e ANTES da vistoria, pelo mesmo
        # motivo do veto: nao gasta `TENTATIVAS`, senao dez retidas na frente
        # esconderiam a parte limpa de tras e a retida sairia mesmo assim.
        retencao = _retencao(alvo)
        if retencao:
            recusados.append(f"{retencao} — retida")
            retidos.append(alvo)
            bloqueadas.add(alvo.fonte_id)
            continue
        if examinados >= TENTATIVAS:
            break
        examinados += 1
        roteiro = R.carregar(alvo.fonte_id)
        _pulsar()                  # a vistoria pode calar ~10 min
        laudo = qualidade.vistoriar_parte(alvo.fonte_id, alvo.parte,
                                          alvo.caminho, roteiro)
        if not laudo["ok"]:
            recusados.append(f"{alvo.id}: {'; '.join(laudo['erros'])[:120]}")
            bloqueadas.add(alvo.fonte_id)
            continue
        # A VISTORIA PASSOU; FALTA A IA OLHAR. A mecanica responde "o arquivo
        # esta inteiro?"; so quem assiste responde "o video presta?".
        veto = _parecer_da_ia(alvo, roteiro, laudo)
        if veto:
            recusados.append(veto)
            bloqueadas.add(alvo.fonte_id)
            continue
        return alvo, recusados
    # NAO FICAR SEM VIDEO. Pedido dele em 13/09/2026: "a prioridade e nao
    # ficar sem video". Nenhum candidato limpo: sai o menos pior, desde que o
    # ARQUIVO esteja inteiro — video mudo ou sem imagem nao sai nem assim. O
    # menos pior, na ordem: a RETIDA (o conserto ja foi gasto, ou so a folha a
    # viu), depois a VETADA (o veto ainda pode ser consertado; publica-la
    # agora queima o conserto), e so entao a parte seguinte fora de ordem.
    # A retida que sai vai para a lista "a conferir" (`postar_historia`).
    #
    # ENTRE AS RETIDAS, A CONSERTADA PRIMEIRO. Decisao do Adrian em 05/10/2026
    # (Grimorio historias/reolhar-depois-do-conserto): "manter uma passada so
    # — consertada sem nova olhada so ganha prioridade sobre a vetada sem
    # conserto". Medido no mesmo dia: 57 de 58 partes retidas, 37 consertadas,
    # e na ordem da fila os `[:3]` caiam em retidas sem conserto nenhum. O
    # reparo ja refez as cenas que a IA apontou, e a vetada sem conserto sai
    # com o defeito que ela viu. Consertada por qualquer dos dois registros:
    # o parecer (`_consertada`: mp4 mais novo que o veto) ou a ficha do
    # reparo (`_consertado`: a passada foi gasta com conserto APLICADO).
    # Ordenacao ESTAVEL, e so entre retidas: cada uma e a proxima parte da
    # sua serie (a serie para na primeira barrada), entao isto nunca fura a
    # ordem de uma serie; dentro de cada grupo vale a ordem da fila.
    consertadas = {alvo.id for alvo in retidos
                   if _consertada(alvo) or _consertado(alvo)}
    retidos.sort(key=lambda alvo: alvo.id not in consertadas)
    for alvo in retidos[:3]:
        roteiro = R.carregar(alvo.fonte_id)
        _pulsar()                  # a vistoria pode calar ~10 min
        laudo = qualidade.vistoriar_parte(alvo.fonte_id, alvo.parte,
                                          alvo.caminho, roteiro)
        if laudo["ok"]:
            _linha(f"[postar] {alvo.id}: nenhuma parte limpa na fila; sai "
                   "esta, RETIDA"
                   + (" (consertada, sem nova olhada)"
                      if alvo.id in consertadas else "")
                   + ", para o horario nao ficar vazio — e fica "
                   "na lista a conferir.")
            return alvo, recusados
    for alvo in vetados[:3]:
        roteiro = R.carregar(alvo.fonte_id)
        _pulsar()                  # a vistoria pode calar ~10 min
        laudo = qualidade.vistoriar_parte(alvo.fonte_id, alvo.parte,
                                          alvo.caminho, roteiro)
        if laudo["ok"]:
            _linha(f"[postar] {alvo.id}: nenhum video limpo na fila; sai "
                   "este, com o veto da IA, para o horario nao ficar vazio.")
            return alvo, recusados
    # ULTIMO RECURSO: a parte seguinte de uma serie parada, fora de ordem, so
    # quando nada acima pode sair — o horario vazio continua sendo pior.
    for alvo in adiadas[:3]:
        if travas.ocupada(f"historias__render__{alvo.fonte_id}"):
            recusados.append(f"{alvo.id}: a historia esta sendo renderizada")
            continue
        if _veto_lembrado(alvo) or _retencao(alvo):
            continue
        roteiro = R.carregar(alvo.fonte_id)
        _pulsar()                  # a vistoria pode calar ~10 min
        laudo = qualidade.vistoriar_parte(alvo.fonte_id, alvo.parte,
                                          alvo.caminho, roteiro)
        if laudo["ok"]:
            _linha(f"[postar] {alvo.id}: nenhum outro video pode sair; vai "
                   "fora de ordem para o horario nao ficar vazio.")
            return alvo, recusados
    return None, recusados


def publicou_neste_horario(canal: str, plataforma: str = "youtube",
                           agora=None) -> dict | None:
    """Ja publiquei neste MESMO horario, NESTA plataforma? `None` se nao.

    A regra e UM VIDEO EM CADA HORARIO da grade (6, 7, 8, 10, 12, 15, 17, 20),
    e nao um por dia — correcao dele em 09/09/2026, depois de eu ter entendido
    errado e travado o canal no primeiro post do dia.

    Entao o que esta guarda impede e so a REPETICAO no mesmo disparo, que e um
    risco real e recente: em 08/09 sairam dois de cada canal porque uma rodada
    manual cruzou com a agendada (17:06 e 17:12 nas historias, 17:07 e 17:13
    nos builds), e em 09/09 liguei `StartWhenAvailable` nas tarefas — o que e
    certo para nao perder o horario, e que por definicao cria disparo fora da
    hora.

    O HORARIO E O DA GRADE, NAO A HORA DO RELOGIO (decisao dele em
    29/09/2026, `guarda-hora-da-grade`). Ate entao a janela era a hora do
    relogio, e em 28/09 a `historia_00027:p01`, subida a mao as 22:12,
    contou como o post das 22:37: a rodada leu "YouTube ja saiu nesta hora",
    levou essa parte ao TikTok (onde ja estava) e o horario ficou sem video
    novo. Um post pertence ao horario que ele COBRE — o ultimo que ja tinha
    vencido quando a linha foi gravada — e a identidade desse horario e
    `conferencia.chave_do_horario` (dia de grade, hora), a mesma do placar
    de metas e da conferencia. Assim a linha das 22:12 e do 21:37, a
    recuperacao das 00:10 e do 23:37 da vespera, e a rodada das 17:57 que
    grava as 18:01 continua sendo a das 17:57.

    A fonte e o LEDGER, e nao um arquivo de controle novo: ele ja e a verdade
    sobre o que foi publicado, e uma segunda fonte que discordasse dele seria
    pior do que nao ter nenhuma.

    POR PLATAFORMA, e nao so por canal: o mesmo video vai para o YouTube E
    para o TikTok no mesmo horario, e uma guarda cega ao destino faria a
    primeira postagem bloquear a segunda.
    """
    from datetime import datetime
    from builds.publicar import conferencia
    agora = agora or datetime.now()
    alvo = str(plataforma).lower()
    horario = conferencia.chave_do_horario(agora, alvo)
    # FALHA FECHADA (conferente do 4e8df2b, 06/10/2026). Ate aqui o ledger
    # ilegivel virava lista vazia, e "nao sei" virava "nao publiquei": com o
    # ledger preso na volta final, o YouTube da mesma p06 subia de novo. Esta
    # e a guarda contra a REPETICAO, e repetir e pior que nao postar (17/09):
    # sem ledger, a resposta e "ja foi" — com a marca `ledger_ilegivel`, que
    # os chamadores transformam em "nao publico neste horario" e avisam.
    try:
        linhas = _publicados_do_canal(canal)
    except Exception as exc:                                   # noqa: BLE001
        return _ledger_ilegivel(canal, alvo, exc)
    for linha in linhas:
        # Linha antiga, de antes de o registro guardar plataforma, conta como
        # YouTube: era o unico destino que existia.
        if str(linha.get("plataforma") or "youtube").lower() != alvo:
            continue
        # Linha sem data legivel da None, e None nunca e igual a um horario.
        if conferencia.chave_do_horario(linha.get("quando"), alvo) == horario:
            return linha
    return None


class LedgerIlegivel(RuntimeError):
    """O ledger do canal nao pode ser lido agora ("nao sei", e nao "vazio")."""


def _publicados_do_canal(canal: str) -> list:
    """As linhas do ledger do canal. Levanta `LedgerIlegivel` se nao der.

    Ate 06/10/2026 devolvia [] em qualquer excecao, e cada chamador herdava
    a decisao sem saber. Agora cada um escolhe: os crivos de fila (teto,
    titulo, recuperacao) ja tinham o seu `try` e deixam passar, por decisao;
    a guarda de um por horario (`publicou_neste_horario`) falha FECHADA.
    Ledger que nao existe e vazio de verdade, e nao erro.
    """
    try:
        if canal == "historias":
            from contos.publicar import serie
            return serie.publicados()
        from builds.publicar import metricas
        if canal == "bluelock":
            return metricas.publicados("bluelock")
        return metricas.publicados()
    except Exception as exc:                                   # noqa: BLE001
        raise LedgerIlegivel(
            f"{canal}: {type(exc).__name__}: {str(exc)[:160]}") from exc


def _ledger_ilegivel(canal: str, plataforma: str, exc: BaseException) -> dict:
    """A "linha" que a guarda devolve quando nao leu o ledger: BARRA.

    Vai ao log e ao diario (erro), e a rodada transforma em ficha que nao
    publica (`_ficha_do_ledger_ilegivel`), que o Telegram mostra.
    """
    texto = (f"nao consegui ler o ledger de {canal} para saber se o "
             f"{plataforma} ja saiu neste horario ({exc}); NAO publico — "
             "'nao sei' nao vira 'nao publiquei'")
    _linha(f"[postar] {texto}")
    try:
        from builds import atividade
        atividade.registrar("publicacao", atividade.ERRO, texto, canal,
                            etapa="publicar.guarda")
    except Exception:                                          # noqa: BLE001
        pass
    return {"ledger_ilegivel": texto, "plataforma": plataforma,
            "video_id": None, "quando": None}


def _ficha_do_ledger_ilegivel(canal: str, *achados) -> dict | None:
    """A ficha da rodada quando a guarda nao leu o ledger; `None` se leu.

    Barra o CANAL inteiro no horario, e nao so o destino: os dois destinos
    leem o mesmo arquivo, e levar "so o TikTok" pediria o video do YouTube,
    que esta justamente no ledger que nao foi lido.
    """
    for achado in achados:
        if achado and achado.get("ledger_ilegivel"):
            return {"canal": canal, "feito": False, "ledger_ilegivel": True,
                    "motivo": achado["ledger_ilegivel"]}
    return None


def _ja_foi_neste_horario(canal: str, plataforma: str = "youtube",
                          agora=None) -> dict | None:
    """A resposta pronta de "ja publiquei neste disparo".

    `agora` e injetavel para o teste nao depender do relogio da maquina —
    uma guarda que so da para testar as 17h nao e uma guarda testada.
    """
    from builds.publicar import conferencia
    feito = publicou_neste_horario(canal, plataforma, agora)
    if feito is None:
        return None
    hora = str(feito.get("quando") or "")[11:16]
    # A hora do relogio E o horario da grade que ela cobriu: quem le o log
    # da rodada das 22:37 precisa ver que a linha das 22:40 e deste horario.
    chave = conferencia.chave_do_horario(feito.get("quando"), plataforma)
    da_grade = f", horario das {grade.horario(chave[1])}" if chave else ""
    return {"canal": canal, "plataforma": plataforma,
            "feito": False, "repetido": True,
            "motivo": f"ja publiquei as {hora} no {plataforma} "
                      f"({feito.get('video_id')}){da_grade}. "
                      "Nao repito o disparo."}


def _ids_da_parte(provas) -> dict:
    """O que a LINHA do ledger das historias ganha dos laudos de upload.

    `youtube_id`: o do PRIMEIRO arquivo — e o que o campo sempre quis dizer
    quando a parte vira pedacos (`recuperar.id_no_canal`). `youtube_ids`: os
    de TODOS, na ordem do corte, so quando a parte virou mais de um Short e
    todos tem id — com um faltando, a lista deslocaria o outro para a
    posicao errada.

    Por que a linha precisa: `serie.registrar` tira o id da URL, e pelo
    navegador a "URL" e a frase "publicado no YouTube". A linha de 27/09
    20:43 da `historia_00035:celular:p01` tem `youtube_id: null` e o laudo
    dela, `OAjbMHMCutk`.
    """
    ids = [str((p or {}).get("youtube_id") or "") for p in provas or ()]
    if not ids or not ids[0]:
        return {}
    extra = {"youtube_id": ids[0]}
    if len(ids) > 1 and all(ids):
        extra["youtube_ids"] = ids
    return extra


# ------------------------------------------------ parte com pedaco ja no ar
# A PARTE EM PEDACOS QUE CAIU NO MEIO (06/10/2026, conferente do c431c6e).
# `contos.publicar.catalogo.publicar_youtube` sobe a parte longa pedaco a
# pedaco, e a linha do ledger so e gravada DEPOIS do ultimo. Com o pedaco 1
# no ar e o 2 caido por "infraestrutura:", a reposicao por rede rodava o
# canal de novo, a guarda de um-por-horario nao achava linha, a fila
# escolhia a MESMA parte e o pedaco 1 subia de novo, PUBLICO — 3 envios do
# pedaco 1 numa rodada (1 + `TENTATIVAS_POR_REDE`), e mais um no horario
# seguinte. A porta abaixo e por onde os tres caminhos do postar que sobem
# parte de historia passam (rodada, `--so-youtube`, `--tudo`): com algum
# pedaco ja entregue, a falha seguinte nao e "de rede" (nao repoe) e a parte
# vai a lista "a conferir" do YouTube (a fila nao a repete). Repetir e pior
# que nao postar (17/09). Quem tira a marca e uma pessoa.
PREFIXO_DO_PEDACO = "[pedaco] "


class ParteMeioNoAr(RuntimeError):
    """Algum pedaco da parte ja subiu ao YouTube e o seguinte falhou.

    A mensagem NUNCA carrega o texto do erro original — ele pode ter
    "infraestrutura" ou "SSLError", que `_e_de_rede` leria como "repor".
    O original fica em `erro`; os ids do que ja subiu, em `ids`.
    """

    def __init__(self, mensagem: str, *, erro: str = "", ids=()):
        super().__init__(mensagem)
        self.erro = erro
        self.ids = list(ids)


# ------------------------------------------------- a parte seguinte (TESTE)
# LIGAR CADA PARTE A SEGUINTE NO YOUTUBE (decisao `publicacao/historias-21h-
# e-parte-seguinte`, 19/10/2026, como TESTE): na analise, das 18 partes com
# 100+ views, a seguinte teve ~0,6 view a cada 100 da anterior. O que o
# YouTube tem para isso, conferido em 19/10:
#   - "video relacionado" do Shorts: so existe no Studio; a API oficial
#     (Data API v3, `videos`) nao tem o campo. Automatizar o Studio para
#     EDITAR video ja publicado seria um caminho novo, sem ensaio, na conta
#     dele — fica de fora;
#   - comentario fixado: a API cria comentario (escopo `youtube.force-ssl`),
#     mas nao fixa;
#   - descricao: a API edita (`videos.update`, escopo `youtube`), MAS a
#     credencial do canal de historias nao tem esse escopo (medido: so a de
#     builds tem), e reautorizar e mexer na conta — decisao dele.
# Entao, sem mexer em conta: toda parte que tem seguinte sobe com
# `PARTE_SEGUINTE` no fim da descricao, e com o LINK quando a seguinte ja esta
# no YouTube (subida fora de ordem, divida). A ligacao de volta — editar a
# parte N quando a N+1 sai — esta pronta (`_ligar_a_parte_anterior`) e
# DESLIGADA (`LIGAR_PELA_API`): precisa do escopo de edicao no canal de
# historias. A fala (narracao) e da parte Historias, nao daqui.
PARTE_SEGUINTE = "A parte seguinte já está no canal."
PARTE_SEGUINTE_NA_DESCRICAO = True
LIGAR_PELA_API = False


def _link_do_short(youtube_id: str) -> str:
    return f"https://youtube.com/shorts/{youtube_id}" if youtube_id else ""


def _id_da_parte_no_youtube(fonte_id: str, parte: int, publicados=None) -> str:
    """O `youtube_id` da parte `parte` da serie no YouTube, ou "" (ledger)."""
    try:
        if publicados is None:
            publicados = _publicados_do_canal("historias")
    except Exception:                                          # noqa: BLE001
        return ""
    for linha in publicados:
        if (str(linha.get("plataforma") or "youtube").lower() == "youtube"
                and _saiu(linha)
                and str(linha.get("fonte_id") or "") == str(fonte_id)
                and int(linha.get("parte") or 0) == int(parte)
                and linha.get("youtube_id")):
            return str(linha["youtube_id"])
    return ""


def _com_a_parte_seguinte(alvo, publicados=None):
    """Uma COPIA de `alvo` com `PARTE_SEGUINTE` (e o link, se houver) no fim da
    descricao. A ultima parte, a parte unica, e quem ja tem o texto, voltam
    iguais (o proprio objeto). Nunca levanta."""
    import copy
    try:
        parte = int(getattr(alvo, "parte", 0) or 0)
        partes = int(getattr(alvo, "partes", 0) or 0)
        descricao = str(getattr(alvo, "descricao", "") or "")
        if (not PARTE_SEGUINTE_NA_DESCRICAO or partes < 2 or parte < 1
                or parte >= partes or PARTE_SEGUINTE in descricao):
            return alvo
        linhas = [PARTE_SEGUINTE]
        link = _link_do_short(_id_da_parte_no_youtube(
            getattr(alvo, "fonte_id", ""), parte + 1, publicados))
        if link:
            linhas.append(f"Parte {parte + 1}: {link}")
        novo = copy.copy(alvo)
        novo.descricao = (descricao.rstrip() + "\n\n"
                          + "\n".join(linhas)).strip()
        return novo
    except Exception:                                          # noqa: BLE001
        return alvo


def _ligar_a_parte_anterior(alvo, provas, *, editar=None) -> dict:
    """Depois que a parte N sobe, poe o link dela na descricao da N-1.

    DESLIGADA (`LIGAR_PELA_API = False`) e sem escopo nao tenta. Nunca
    levanta e nunca segura a rodada: a parte N ja esta no ar. `editar` e o
    `recuperar.acrescentar_na_descricao` (injetavel para o teste).
    """
    try:
        parte = int(getattr(alvo, "parte", 0) or 0)
        if not LIGAR_PELA_API or parte < 2:
            return {"ligou": False, "motivo": "desligado" if parte >= 2
                    else "parte 1 nao tem anterior"}
        novo_id = next((str((p or {}).get("youtube_id")) for p in provas or ()
                        if (p or {}).get("youtube_id")), "")
        anterior = _id_da_parte_no_youtube(getattr(alvo, "fonte_id", ""),
                                           parte - 1)
        if not novo_id or not anterior:
            return {"ligou": False, "motivo": "falta o id de uma das partes"}
        if editar is None:
            from builds.publicar import recuperar
            editar = recuperar.acrescentar_na_descricao
        r = editar(anterior, f"Parte {parte}: {_link_do_short(novo_id)}",
                   "historias")
        return {"ligou": bool(r.get("mudou")), "motivo": r.get("motivo", "")}
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[postar] nao liguei a parte anterior a {getattr(alvo, 'id', '')}"
               f" ({type(exc).__name__}: {str(exc)[:120]})")
        return {"ligou": False, "motivo": f"{type(exc).__name__}"}


@_voando("historias", "youtube")
def _subir_parte_no_youtube(alvo, visibilidade, provas: list):
    """`catalogo.publicar_youtube`, com a guarda da parte meio no ar.

    `provas` ganha um laudo por pedaco TENTADO, antes da chamada (desde o
    PUB-1, 14/10/2026); o do pedaco que caiu leva `falhou`. Os outros foram
    entregues: se a chamada levantar com algum entregue, levanta
    `ParteMeioNoAr` e marca a parte "a conferir" no YouTube. Se so o pedaco
    que caiu tinha o CLIQUE dado (`clicou`), a parte vai a lista "a conferir"
    e a excecao original sobe — quem chama ve o `clicou` no laudo e nao repoe.
    Sem entregue e sem clique, a excecao sobe intacta (nada foi entregue;
    repetir nao duplica, e a reposicao por rede segue valendo).
    """
    from contos.publicar import catalogo
    antes = len(provas)
    try:
        url = catalogo.publicar_youtube(_com_a_parte_seguinte(alvo),
                                        visibilidade, provas=provas)
        _ligar_a_parte_anterior(alvo, provas)
        return url
    except Exception as exc:                                   # noqa: BLE001
        novos = provas[antes:]
        entregues = [p for p in novos if not (p or {}).get("falhou")]
        clicou = any((p or {}).get("clicou") and (p or {}).get("falhou")
                     for p in novos)
        if not entregues:
            if clicou:
                _garantir_marca(
                    "historias", alvo.id, "youtube",
                    f"cliquei em publicar no YouTube e algo falhou depois "
                    f"({type(exc).__name__}): a parte pode estar no ar — "
                    f"confira no canal.", etapa="publicar.youtube.clique")
            raise
        erro = f"{type(exc).__name__}: {exc}"[:300]
        ids = [str((p or {}).get("youtube_id") or "?") for p in entregues]
        _linha(f"[postar] {alvo.id}: {len(entregues)} pedaco(s) ja no "
               f"YouTube ({', '.join(ids)}) e o seguinte falhou ({erro}).")
        texto = (f"{len(entregues)} pedaco(s) desta parte ja subiram ao "
                 f"YouTube ({', '.join(ids)}) e o seguinte falhou. Nao repito "
                 f"a parte: o pedaco no ar subiria de novo. Precisa de uma "
                 f"pessoa no canal; tirar esta marca devolve a parte INTEIRA "
                 f"a fila (todos os pedacos).")
        # A marca e a guarda da PROXIMA rodada; a desta e a propria
        # `ParteMeioNoAr` (nao repoe). Se o disco recusar, a marca fica na
        # memoria e vai para a ficha da trava (`_garantir_marca`).
        _garantir_marca("historias", alvo.id, "youtube",
                        PREFIXO_DO_PEDACO + texto,
                        etapa="publicar.youtube.pedaco",
                        aviso=f"{alvo.id}: {texto}")
        raise ParteMeioNoAr(texto, erro=erro, ids=ids) from exc


def _garantir_marca(canal: str, alvo_id: str, destino: str, estado: str, *,
                    etapa: str, aviso: str | None = None) -> bool:
    """O CLIQUE QUE SAIU vira marca "a conferir" — ou, no minimo, nao some.

    PUB-1 (auditoria de 11/10/2026, verificada em 14/10): o publicador ja
    tenta a marca quando algo falha depois do clique, mas a falha DELA (trava
    `<destino>_a_conferir` ocupada 20 s, disco) era engolida, e nada duravel
    guardava o clique: o video voltava a fila no horario seguinte. Aqui:

      1. `desfecho.marcar_para_conferir` de novo (idempotente: se o
         publicador ja marcou, nao repete nada; ela mesma tenta duas vezes);
      2. se o disco recusar, a marca fica na memoria desta execucao
         (`desfecho.lembrar_sem_marca`, somada por `desfecho.marcas` — a
         rodada nao escolhe o video de novo) e `_em_voo` a leva para a ficha
         da trava; a rodada seguinte a grava ANTES de escolher, ou nao
         publica (`_pousar_sem_marca`);
      3. avisa (diario e Telegram).

    True quando a marca esta no disco. Nunca levanta.
    """
    try:
        from builds.publicar import desfecho
    except Exception:                                          # noqa: BLE001
        return False
    try:
        desfecho.marcar_para_conferir(canal, alvo_id, estado, destino,
                                      aviso=aviso, etapa=etapa, erro=True)
        return True
    except Exception as exc:                                   # noqa: BLE001
        desfecho.lembrar_sem_marca(canal, alvo_id, estado, destino)
        if _DONA:
            _DONA["sem_marca"] = _marcas_so_na_memoria()
            _pulsar(forcar=True)
        _avisar(f"{alvo_id}: o clique no {destino} saiu e a marca 'a "
                f"conferir' NAO gravou ({type(exc).__name__}: {exc})"[:300]
                + ". Esta rodada nao o escolhe de novo; a seguinte grava a "
                "marca antes de publicar, ou nao publica. Confira o canal.")
        return False


# OS CANAIS QUE PODEM TER UM VOO NA FICHA DA TRAVA, UMA MARCA "A CONFERIR" SEM
# DISCO E UM LEDGER PROPRIO: o `bluelock` entrou em 26/10/2026 (a serie de
# videos do Blue Lock). Um lugar so — quatro checagens liam a tupla escrita
# a mao, e um canal fora dela perderia o clique na queda de energia.
CANAIS_DA_FICHA = ("historias", "builds", "bluelock")


def _marcas_so_na_memoria() -> list:
    """As marcas "a conferir" que o disco recusou nesta execucao. Nunca levanta."""
    try:
        from builds.publicar import desfecho
        return [m for m in desfecho.sem_marca_no_disco()
                if m.get("canal") in CANAIS_DA_FICHA
                and m.get("destino") in ("youtube", "tiktok") and m.get("alvo")]
    except Exception:                                          # noqa: BLE001
        return []


# ------------------------------------------- parte que so saiu no TikTok
# A DIVIDA DO YOUTUBE (06/10/2026, decisao do Adrian
# `publicacao/youtube-caiu-depois-do-tiktok`: "subir a MESMA parte no
# YouTube"). As 00:37 de 06/10 a `historia_00054:celular:p02` saiu so no
# TikTok (o Studio levou 126 s para abrir). A fila conta qualquer destino como
# publicado, entao a reposicao e as rodadas seguintes levavam ao YouTube a
# p03: no canal a serie ficava com a Parte 1 e a 3, sem a 2, para sempre.
# Agora a parte que saiu no TikTok e nao no YouTube e DIVIDA: o YouTube do
# horario sobe ela, e o TikTok segue com a proxima da fila. O YouTube fica um
# horario atras do TikTok — foi o que ele escolheu.
#
# SO DESTA DATA EM DIANTE. As tres de 28/09 (h22 p03, h27 p01, h32 p04) tem
# caminho proprio, `--so-youtube` (decisao `partes-so-no-tiktok`); despeja-las
# pela grade seria decisao de conteudo, e nao conserto. Para incluir as
# antigas, mova a data; nada mais precisa mudar.
# 05/10, E NAO 06/10 (medido no ledger as 23:59 de 06/10): partes no TikTok
# e fora do YouTube eram 4 — h16 p01 (16/09), h54 p01 (05/10 23:50, o 23:37
# que caiu junto com o 00:37 da decisao), h54 p02 (06/10 00:49) e h60 p01
# (06/10 12:10). Com 06/10 a h54 p01 ficava de fora, e a p02 nunca saia (a
# ordem no YouTube pede a p01 antes): a serie da decisao ficaria com buraco
# para sempre. A h16 p01 (16/09) fica de fora do corte: decisao do Adrian em
# 07/10 (`publicacao/h16-p01-so-no-tiktok`) e subi-la pelo `--so-youtube`.
# E a devida RETIDA sobe mesmo havendo parte limpa na fila (decisao
# `publicacao/divida-retida-fura-valvula`, 07/10: "sobe mesmo assim").
CORTE_DA_DIVIDA_DO_YOUTUBE = "2026-10-05"


def _divida_do_youtube() -> tuple:
    """(parte que o YouTube deve, quando ela saiu no TikTok, motivos).

    Sem divida: `(None, "", motivos)`, com o motivo de cada parte devida que
    nao pode sair agora. Nunca levanta: sem a resposta, o YouTube segue com a
    fila normal (o buraco de antes, e nao o horario vazio).

    Divida e a parte que SAIU no TikTok (`_saiu`, linha a partir de
    `CORTE_DA_DIVIDA_DO_YOUTUBE`) e NAO saiu no YouTube, com as partes
    anteriores da serie ja no YouTube — a ordem que vale e a do canal do
    YouTube. Entre series, a de menor parte primeiro; empate, a que saiu antes
    no TikTok.

    As guardas sao as do `--so-youtube` (duplicata pelo ledger e pelo titulo,
    lista "a conferir" do YouTube — e ela que segura a parte com pedaco no ar,
    `ParteMeioNoAr` —, render, mp4 no catalogo e a vistoria mecanica) e o
    teto por fonte NO YOUTUBE. O parecer da IA fica de fora: a parte ja passou
    por ele para ir ao TikTok. A que nao passa nao trava o canal.
    """
    try:
        return _procurar_divida_do_youtube()
    except Exception as exc:                                   # noqa: BLE001
        return None, "", [f"nao consegui procurar a divida do YouTube "
                          f"({type(exc).__name__}: {exc})"[:160]]


def _procurar_divida_do_youtube() -> tuple:
    from contos.publicar import catalogo, qualidade, serie
    from contos.roteiro import roteiro as R
    from builds import travas

    publicados = serie.publicados()
    no_youtube, partes_no_youtube = set(), set()
    for l in publicados:
        # Linha sem plataforma e do YouTube (era o unico destino).
        if (str(l.get("plataforma") or "youtube").lower() != "youtube"
                or not _saiu(l)):
            continue
        vid = str(l.get("video_id") or "")
        no_youtube.add(vid)
        if l.get("parte"):
            fonte = str(l.get("fonte_id") or vid.split(":")[0])
            partes_no_youtube.add((fonte, int(l.get("parte"))))
    # O apagado do canal nao e divida (o mesmo crivo dos builds, 21/10/2026).
    from builds.publicar import metricas as _metricas
    apagados = _metricas.apagados(publicados, "youtube")
    devidas: dict = {}
    for l in publicados:
        quando = str(l.get("quando") or "")
        vid = str(l.get("video_id") or "")
        if (l.get("plataforma") != "tiktok" or not _saiu(l)
                or quando < CORTE_DA_DIVIDA_DO_YOUTUBE
                or not vid or vid in no_youtube or vid in apagados):
            continue
        devidas.setdefault(vid, quando)
    if not devidas:
        return None, "", []

    motivos: list = []
    no_catalogo = {v.id: v for v in catalogo.listar()}
    candidatas = []
    for vid, quando in devidas.items():
        v = no_catalogo.get(vid)
        if v is None:
            motivos.append(f"{vid}: o mp4 nao esta mais no catalogo")
            continue
        candidatas.append((int(v.parte or 0), quando, v))
    candidatas.sort(key=lambda c: (c[0], c[1]))
    try:
        cheias = _fontes_cheias_hoje(publicados, "youtube")
    except Exception:                                          # noqa: BLE001
        cheias = set()                 # "nao sei" nao barra (ver a tabela)
    vistas = set()
    for parte, quando, v in candidatas:
        if v.fonte_id in vistas:
            continue                   # so a MENOR parte devida de cada serie
        vistas.add(v.fonte_id)
        faltam = [n for n in range(1, parte)
                  if (v.fonte_id, n) not in partes_no_youtube]
        if faltam:
            motivo = (f"a parte {faltam[0]} da serie ainda nao esta no "
                      "YouTube")
        elif serie.ja_publicado(v.id, "youtube"):
            motivo = "ja esta no YouTube pelo ledger"
        elif titulo_repetido(v, "historias", "youtube"):
            motivo = "o titulo ja esta no ar no YouTube (ledger)"
        elif not _sem_a_conferir([v], "historias"):
            motivo = "esta na lista 'a conferir' do YouTube"
        elif travas.ocupada(f"historias__render__{v.fonte_id}"):
            motivo = "a historia esta sendo renderizada"
        elif v.fonte_id in cheias:
            motivo = (f"a historia ja saiu {TETO_POR_FONTE_NO_DIA}x hoje no "
                      "YouTube")
        else:
            laudo = qualidade.vistoriar_parte(v.fonte_id, v.parte, v.caminho,
                                              R.carregar(v.fonte_id))
            motivo = ("" if laudo["ok"] else "a vistoria reprovou: "
                      + "; ".join(laudo["erros"])[:120])
        if not motivo:
            return v, quando, motivos
        motivos.append(f"{v.id}: {motivo}")
    return None, "", motivos


def _outra_parte_no_tiktok(ficha: dict, tk_alvo, recusados=None) -> None:
    """A ficha diz qual parte o TikTok levou quando NAO e a do YouTube.

    `alvo`/`titulo`/`parte` da ficha continuam sendo os do YouTube (a parte
    devida); os do TikTok ganham campos proprios, e o relatorio mostra os dois.
    """
    ficha.update({"tiktok_alvo": tk_alvo.id, "tiktok_titulo": tk_alvo.titulo,
                  "tiktok_parte": tk_alvo.parte})
    if recusados:
        ficha["recusados"] = list(recusados)


def _valvula_da_outra_parte(ficha: dict, tk_alvo) -> None:
    """A valvula da parte que foi SO ao TikTok, fora das marcas da ficha (que
    sao da parte do YouTube). Chame so com o TikTok confirmado."""
    marcas = {"canal": "historias", "alvo": tk_alvo.id}
    _retida_chegou_ao_tiktok(tk_alvo, marcas)
    if marcas.get("retido"):
        ficha["tiktok_retido"] = marcas["retido"]


def _alcance_do_youtube(ficha: dict, alvo, visibilidade) -> None:
    """Sobe a segunda parte do YouTube quando havia divida no horario."""
    from contos.publicar import serie

    if not _cabe_antes_do_proximo("a segunda subida do YouTube"):
        ficha["youtube_alcance"] = {"pulado": "sem tempo antes do horario "
                                              "seguinte"}
        return
    if serie.ja_publicado(alvo.id, "youtube"):
        _linha(f"[postar] historias: alcance do YouTube nao repete {alvo.id}; "
               "ja esta no ledger.")
        return
    if not _sem_a_conferir([alvo], "historias"):
        return
    try:
        cheias = _fontes_cheias_hoje(serie.publicados(), "youtube")
    except Exception:                                          # noqa: BLE001
        cheias = set()
    if alvo.fonte_id in cheias:
        _linha(f"[postar] historias: alcance do YouTube nao fura o teto de "
               f"{alvo.fonte_id}.")
        ficha["youtube_alcance"] = {"pulado": "teto por fonte no YouTube"}
        return

    alcance = {"alvo": alvo.id, "titulo": alvo.titulo, "parte": alvo.parte,
               "partes": alvo.partes, "url": ""}
    ficha["youtube_alcance"] = alcance
    provas: list = []
    try:
        url = _subir_parte_no_youtube(alvo, visibilidade, provas)
        alcance["url"] = url
        serie.registrar(alvo, url, "youtube", None,
                        {"por": "postar.py", "visibilidade": _visibilidade_usada(provas, visibilidade),
                         "alcance": True, "prova": provas,
                         "prova_ok": _prova_ok(provas),
                         **_ids_da_parte(provas)})
    except Exception as exc:                                   # noqa: BLE001
        alcance["falhou"] = f"{type(exc).__name__}: {exc}"[:200]
        if isinstance(exc, ParteMeioNoAr):
            alcance["meio_no_ar"] = True
            alcance["ids"] = exc.ids
        _linha(f"[postar] historias: segunda subida do YouTube falhou "
               f"({alcance['falhou']}); {alvo.id} continua pendente.")


def _historias_pausadas() -> str:
    """O motivo da PAUSA das historias (10/10/2026, pedido do Adrian), ou "".

    A rodada pula o canal inteiro com uma linha so, em vez de levar cada
    horario ate a guarda de `catalogo.publicar_*` e avisar "falhou" no
    Telegram dez vezes por dia por uma coisa que ele mesmo pediu.
    """
    try:
        from contos.publicar import catalogo
        return catalogo.pausada()
    except Exception:                                          # noqa: BLE001
        return ""


def postar_historia(*, so_ver: bool = False) -> dict:
    from contos.publicar import serie

    # UMA GUARDA POR DESTINO, e nao uma para a rodada. Se o YouTube ja saiu
    # nesta hora, o TikTok ainda nao — e a versao que retornava aqui fazia o
    # sucesso do primeiro destino cancelar o segundo. Quando so falta o
    # TikTok, o video e o MESMO que foi para o YouTube: os dois canais tem que
    # mostrar a mesma coisa, e assim o TikTok recupera o atraso sozinho.
    ja_yt = None if so_ver else publicou_neste_horario("historias", "youtube")
    ja_tk = None if so_ver else publicou_neste_horario("historias", "tiktok")
    ilegivel = _ficha_do_ledger_ilegivel("historias", ja_yt, ja_tk)
    if ilegivel:
        return ilegivel
    tiktok_agora = _tiktok_neste_horario()
    if ja_yt and (ja_tk or not tiktok_agora):
        return _ja_foi_neste_horario("historias", "youtube")
    if ja_yt:
        alvo = _video_por_id(ja_yt.get("video_id"))
        if alvo is None:
            return {"canal": "historias", "feito": False,
                    "motivo": f"o video {ja_yt.get('video_id')} saiu no "
                              "YouTube mas nao esta mais no catalogo"}
        # O TIKTOK LEVA A VEZ DELE (19/10/2026, fila propria): o que saiu no
        # YouTube e falta ao TikTok, na ordem — e a parte do YouTube deste
        # horario esta nessa fila. A parte do YouTube pode ser DIVIDA
        # (06/10/2026: ja esta no TikTok); entao a vez e a da fila, e com a
        # fila vazia, a proxima parte nova.
        recusados: list = []

        def _nova():
            parte, fora = proxima_historia()
            recusados.extend(fora)
            return parte

        tk_alvo, sem_vez = _vez_do_tiktok_historias(
            _nova if serie.ja_publicado(alvo.id, "tiktok") else alvo)
        tk_alvo = _o_mesmo(tk_alvo, alvo)
        if tk_alvo is None:
            return {"canal": "historias", "feito": False,
                    "motivo": f"o YouTube ja saiu nesta hora com {alvo.id}; "
                              f"TikTok: {sem_vez}"[:300]}
        _linha(f"[postar] historias: YouTube ja saiu nesta hora ({alvo.id}); "
               f"levando {tk_alvo.id} so para o TikTok.")
        falha_tk: dict = {}
        ficha = {"canal": "historias", "feito": True, "alvo": alvo.id,
                 "titulo": alvo.titulo, "url": ja_yt.get("url") or "",
                 "parte": alvo.parte, "partes": alvo.partes,
                 "visibilidade": _visibilidade_das_historias(),
                 "so_tiktok": True,
                 "tiktok": _tiktok_das_historias(tk_alvo, falha_tk)}
        if tk_alvo is not alvo:
            _outra_parte_no_tiktok(ficha, tk_alvo, recusados)
        _anotar_falha_do_tiktok(ficha, falha_tk)
        if _tiktok_confirmado(ficha["tiktok"]):
            if tk_alvo is alvo:
                _retida_chegou_ao_tiktok(alvo, ficha)
            else:
                _valvula_da_outra_parte(ficha, tk_alvo)
        return ficha
    # A DIVIDA DO YOUTUBE VEM ANTES DA FILA (decisao de 06/10/2026, ver
    # `CORTE_DA_DIVIDA_DO_YOUTUBE`): a parte que saiu so no TikTok sobe no
    # YouTube deste horario, e o TikTok leva a proxima da fila — que ja pula
    # a devida, porque ela conta como publicada pelo TikTok.
    divida, divida_quando, motivos_da_divida = _divida_do_youtube()
    for motivo in motivos_da_divida[:3]:
        _linha(f"[postar] historias: divida do YouTube que nao sai agora — "
               f"{motivo}"[:200])
    if divida is not None:
        alvo, recusados = divida, []
        _linha(f"[postar] historias: o YouTube deve {divida.id} (saiu no "
               f"TikTok em {divida_quando[:16]}); sobe ela.")
    else:
        alvo, recusados = proxima_historia()
        if alvo is None:
            motivo = "nao ha parte publicavel"
            if recusados:
                motivo += " — recusadas: " + " | ".join(recusados[:3])
            return {"canal": "historias", "feito": False, "motivo": motivo}

    # A VEZ DO TIKTOK (fila propria, 19/10/2026) e decidida DEPOIS do YouTube
    # — a parte que o YouTube acabou de subir entra na fila de atraso dele —,
    # e so em horario da grade do TikTok. Com divida no YouTube, a parte nova
    # do TikTok e a proxima da fila (como desde 06/10), e o YouTube a alcanca.
    def _parte_nova_do_tiktok():
        if divida is None:
            return alvo
        parte, fora = proxima_historia()
        recusados.extend(fora)
        return parte

    if so_ver:
        veria = {"canal": "historias", "feito": False, "veria": alvo.id,
                 "titulo": alvo.titulo, "recusados": recusados,
                 "motivo": "so vendo"}
        if divida is not None:
            veria["youtube_devido"] = divida_quando
        if tiktok_agora:
            tk_ver, _sem = _vez_do_tiktok_historias(_parte_nova_do_tiktok)
            veria["veria_tiktok"] = tk_ver.id if tk_ver else ""
        return veria
    # EXPLICITO, e registrado. Antes ia `None` nos dois lugares: a publicacao
    # resolvia `public` pelo config (certo) mas o registro gravava `null`
    # (inutil) — e a pergunta "os videos estao publicos?" so tinha resposta
    # abrindo o YouTube. O ledger e o unico lugar onde essa resposta pode
    # ficar guardada, entao ela vai nele.
    visibilidade = _visibilidade_das_historias()
    # A COTA DE UM DESTINO NAO PODE CANCELAR O OUTRO. O YouTube tem limite
    # diario por CANAL; o TikTok nao tem esse limite. Deixar a excecao subir
    # aqui faria o TikTok ficar vazio pelo motivo errado — que e exatamente o
    # que manteve os dois TikToks zerados por 49 publicacoes.
    url, cota, falha_yt, meio_no_ar = "", None, None, None
    provas: list = []
    try:
        url = _subir_parte_no_youtube(alvo, visibilidade, provas)
        serie.registrar(alvo, url, "youtube", None,
                        {"por": "postar.py", "visibilidade": _visibilidade_usada(provas, visibilidade),
                         "prova": provas,
                         "prova_ok": _prova_ok(provas),
                         **_ids_da_parte(provas)})
    except Exception as exc:                                   # noqa: BLE001
        if isinstance(exc, ParteMeioNoAr):
            # Pedaco no ar: a falha NAO e de rede para a rodada (a mensagem
            # nao carrega o erro original) e a ficha diz por que nao repor.
            meio_no_ar = exc
            falha_yt = f"parte meio no ar: {exc}"[:200]
            _linha("[postar] historias: YouTube parou no meio da parte. "
                   "Sigo para o TikTok.")
        elif _e_limite_diario(exc):
            cota = str(exc)
            _linha(f"[postar] historias: YouTube na cota ({exc}). "
                   "Sigo para o TikTok — ele nao tem esse limite.")
            avisar_limite_diario(f"canal historias: {exc}")
        else:
            # QUALQUER FALHA DO YOUTUBE SEGUE PARA O TIKTOK (auditoria de
            # 15/09/2026). Subir aqui deixava o TikTok daquele horario vazio
            # para sempre. Se o TikTok subir, a parte sai da fila como na cota,
            # e o YouTube a sobe depois como DIVIDA (`_divida_do_youtube`,
            # decisao de 06/10/2026), na reposicao ou num horario seguinte.
            falha_yt = f"{type(exc).__name__}: {exc}"[:200]
            _linha(f"[postar] historias: YouTube falhou ({falha_yt}). "
                   "Sigo para o TikTok.")
    ficha = {"canal": "historias", "feito": bool(url), "alvo": alvo.id,
             "titulo": alvo.titulo, "url": url,
             "parte": alvo.parte, "partes": alvo.partes,
             "visibilidade": _visibilidade_usada(provas, visibilidade), "recusados": recusados}
    if divida is not None:
        ficha["youtube_devido"] = divida_quando
    _valvula_da_parte(ficha, alvo)
    if titulo_repetido(alvo, "historias"):
        ficha["titulo_repetido"] = True
    if cota:
        ficha["motivo"] = f"YouTube na cota: {cota}"[:200]
        ficha["cota_youtube"] = True
    if falha_yt:
        ficha["motivo"] = f"YouTube falhou: {falha_yt}"[:200]
        ficha["youtube_falhou"] = True
    if meio_no_ar is not None:
        ficha["youtube_meio_no_ar"] = True
        ficha["youtube_erro"] = meio_no_ar.erro
        ficha["youtube_ids_no_ar"] = meio_no_ar.ids
    if falha_yt and any((p or {}).get("clicou") and (p or {}).get("falhou")
                        for p in provas):
        # O CLIQUE JA TINHA SAIDO (PUB-1, 14/10/2026): o laudo do pedaco que
        # caiu esta em `provas` desde antes da chamada. Repor no mesmo horario
        # seria subir de novo (`_derrubados_pela_rede` respeita), mesmo que a
        # mensagem tenha cara de rede; a marca "a conferir" ja foi tentada
        # por `_subir_parte_no_youtube`.
        ficha["youtube_clicou"] = True
    tk_alvo = None
    if tiktok_agora and not ja_tk:
        tk_alvo, sem_vez = _vez_do_tiktok_historias(_parte_nova_do_tiktok)
        tk_alvo = _o_mesmo(tk_alvo, alvo)
        if tk_alvo is None:
            _linha(f"[postar] historias: TikTok sem parte neste horario — "
                   f"{sem_vez}"[:200])
    if not tiktok_agora:
        # FORA DA GRADE DO TIKTOK, e nao falha: ele posta seis por dia.
        ficha["tiktok"] = ""
        ficha["tiktok_fora_da_grade"] = True
        _linha("[postar] historias: este horario nao e da grade do TikTok.")
    elif ja_tk:
        # O TIKTOK DESTE HORARIO JA SAIU: nao e tentado. A marca e a simetrica
        # de `so_tiktok`, e e por ela que `_juntar_reposicao` junta o YouTube
        # reposto na ficha de antes (06/10/2026).
        ficha["tiktok"] = ""
        ficha["so_youtube"] = True
    elif tk_alvo is None:
        # A fila do TikTok nao tem parte que possa sair agora.
        ficha["tiktok"] = ""
        ficha["tiktok_sem_parte"] = True
    else:
        falha_tk: dict = {}
        if tk_alvo is not alvo:
            _outra_parte_no_tiktok(ficha, tk_alvo, recusados)
        ficha["tiktok"] = _tiktok_das_historias(tk_alvo, falha_tk)
        _anotar_falha_do_tiktok(ficha, falha_tk)
    # Deu TikTok e nao deu YouTube: a rodada fez alguma coisa, e o relatorio
    # tem que dizer isso em vez de chamar tudo de falha. So com o post
    # CONFIRMADO: "cliquei mas o TikTok nao confirmou" nao e publicacao
    # (revisao de 15/09/2026).
    tk_saiu = _tiktok_confirmado(ficha["tiktok"])
    if tk_saiu:
        ficha["feito"] = True
    # A PARTE RETIDA QUE SAIU FICA A CONFERIR (valvula de qualidade): so sai
    # retida quando nao havia outra, e quem confere e uma pessoa.
    # SO ONDE ELA SAIU (05/10/2026): marcada no TikTok sem estar la, a parte
    # some da recuperacao e o fim da serie nunca chega ao TikTok. Com a
    # divida (06/10/2026) o TikTok pode ter levado OUTRA parte: as marcas da
    # ficha sao da parte do YouTube, e a do TikTok passa pela valvula a parte.
    mesmo_no_tiktok = tk_saiu and tk_alvo is alvo
    if ficha.get("retido") and (url or mesmo_no_tiktok):
        onde = (("youtube",) if url else ()) + (
            ("tiktok",) if mesmo_no_tiktok else ())
        _marcar_retido(alvo, ficha["retido"], onde)
    _registrar_valvula(dict(ficha, feito=bool(url) or mesmo_no_tiktok))
    if tk_saiu and tk_alvo is not alvo:
        _valvula_da_outra_parte(ficha, tk_alvo)
    # A falha do TikTok nao segura este envio: a reposicao dele e outro funil.
    if divida is not None and url and tk_alvo is not None and tk_alvo is not alvo:
        _alcance_do_youtube(ficha, tk_alvo, visibilidade)
    return ficha


def _publico_no_canal(alvo, canal: str = "historias") -> str:
    """O id de um video PUBLICO do canal com o mesmo titulo, ou "".

    A pergunta ao CANAL, e nao ao ledger: a parte que so saiu no TikTok pode
    ter subido ao YouTube por um caminho que nao gravou linha (o rascunho
    gemeo de 15/09 e isso). `recuperar.videos_do_canal` le envios + Shorts;
    o criterio de titulo e `titulos.chave`, que guarda o "(Parte N/M)".
    """
    from builds.publicar import recuperar, titulos
    alvo_chave = titulos.chave(getattr(alvo, "titulo", ""))
    for v in recuperar.videos_do_canal(canal):
        if (v.get("privacidade") == "public"
                and titulos.chave(v.get("titulo", "")) == alvo_chave):
            return str(v.get("id") or "?")
    return ""


DURACAO_DE_UM_UPLOAD_MIN = 20


def _horario_que_a_linha_tomaria(agora=None) -> str:
    """A rodada da grade que COMECARIA no meio de um upload avulso feito agora.

    Ate 29/09/2026 `publicou_neste_horario` olhava a hora do relogio, e
    esta trava contava toda hora que o upload tocasse: o caso medido em
    28/09 (a `historia_00027:p01` subiu a mao as 22:04, linha as 22:12, e
    a rodada das 22:37 leu "YouTube ja saiu nesta hora"). Com a guarda
    contando pelo horario da grade (`conferencia.chave_do_horario`), a
    linha das 22:12 cobre o das 21:37 e o das 22:37 fica livre — esse caso
    nao precisa mais de trava.

    O que ainda toma um horario e o upload que ATRAVESSA uma rodada: comecado
    as 22:20, a linha cai as 22:40, no horario das 22:37; a rodada, que
    comecou ao mesmo tempo, ou le a linha e pula (horario sem video novo) ou
    nao le e sai um segundo post no mesmo horario. A linha e gravada no FIM
    do upload (ate `DURACAO_DE_UM_UPLOAD_MIN`). Devolve "HH:MM" da rodada
    que comeca dentro dessa janela, ou "" quando nenhuma comeca.
    """
    from datetime import datetime, timedelta
    agora = agora or datetime.now()
    fim = agora + timedelta(minutes=DURACAO_DE_UM_UPLOAD_MIN)
    zero = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    for dias in (0, 1):                       # a janela pode cruzar a meia-noite
        for h in grade.HORAS:
            rodada = zero + timedelta(days=dias, hours=h, minutes=grade.minuto(h))
            if agora < rodada <= fim:
                return grade.horario(h)
    return ""


def subir_so_no_youtube(video_id: str, *, so_ver: bool = False) -> dict:
    """Leva ao YouTube UMA parte de historia que so saiu no TikTok.

    DECISAO DO ADRIAN (28/09/2026, `partes-so-no-tiktok`): as partes
    `historia_00022:p03`, `00027:p01` e `00032:p04` estao no TikTok e nunca
    vao ao YouTube sozinhas (a fila conta qualquer destino como publicado).
    O caminho que existia, `historias/main.py publicar <id> --youtube`, nao
    passa por guarda nenhuma e registra sem `prova` nem `youtube_id`. Aqui
    passam as que fazem sentido para uma parte avulsa:

      - duplicata: ja no YouTube pelo ledger (`serie.ja_publicado`), titulo
        no ar pelo ledger (`titulo_repetido`) e titulo PUBLICO no canal
        (`_publico_no_canal`);
      - lista "a conferir" do YouTube (a unica guarda que falha fechada);
      - historia sendo renderizada;
      - a vistoria da parte (`qualidade.vistoriar_parte`): audio mudo,
        imagem sem prova de origem, cena sem imagem, narracao cortada.

    Ficam de fora, de proposito, as da GRADE: um-por-horario, teto por fonte,
    ordem da serie (a decisao aceita que a ordem ja se perdeu em h27 e h32) e
    o parecer da IA (a parte ja esta publica no TikTok). A linha do ledger e
    a mesma da rodada, com `prova` e `youtube_id`, mais `por` dizendo de onde
    veio.
    """
    from contos.publicar import qualidade, serie
    from contos.roteiro import roteiro as R
    from builds import travas

    def recusa(motivo: str) -> dict:
        return {"canal": "historias", "feito": False, "alvo": video_id,
                "motivo": motivo}

    tomaria = _horario_que_a_linha_tomaria()
    if tomaria:
        return recusa(f"a linha deste upload cairia na hora da rodada das "
                      f"{tomaria}, e ela acharia que o YouTube ja saiu")
    alvo = _video_por_id(video_id)
    if alvo is None:
        return recusa("a parte nao esta no catalogo")
    ja = serie.ja_publicado(alvo.id, "youtube")
    if ja:
        return recusa(f"ja esta no YouTube pelo ledger ({ja.get('quando')})")
    if titulo_repetido(alvo, "historias", "youtube"):
        return recusa("o titulo ja esta no ar no YouTube (ledger)")
    no_canal = _publico_no_canal(alvo, "historias")
    if no_canal:
        return recusa(f"o canal ja tem um video publico com este titulo "
                      f"({no_canal})")
    if not _sem_a_conferir([alvo], "historias"):
        return recusa("esta na lista 'a conferir' do YouTube")
    if travas.ocupada(f"historias__render__{alvo.fonte_id}"):
        return recusa("a historia esta sendo renderizada")
    laudo = qualidade.vistoriar_parte(alvo.fonte_id, alvo.parte, alvo.caminho,
                                      R.carregar(alvo.fonte_id))
    if not laudo["ok"]:
        return recusa("a vistoria reprovou: "
                      + "; ".join(laudo["erros"])[:300])
    ficha = {"canal": "historias", "feito": False, "alvo": alvo.id,
             "titulo": alvo.titulo, "parte": alvo.parte,
             "partes": alvo.partes, "avisos": laudo.get("avisos", [])}
    retencao = _retencao(alvo)
    if retencao:
        ficha["retido"] = retencao
    if so_ver:
        ficha["motivo"] = "so vendo: passaria pelas guardas"
        return ficha
    visibilidade = _visibilidade_das_historias()
    provas: list = []
    url = _subir_parte_no_youtube(alvo, visibilidade, provas)
    serie.registrar(alvo, url, "youtube", None,
                    {"por": "postar.py --so-youtube",
                     "visibilidade": _visibilidade_usada(provas, visibilidade), "prova": provas,
                     "prova_ok": _prova_ok(provas),
                     **_ids_da_parte(provas)})
    ficha.update({"feito": bool(url), "url": url,
                  "ids": [str((p or {}).get("youtube_id") or "")
                          for p in provas]})
    # A RETIDA QUE SAI FICA A CONFERIR, como na grade (valvula de 28/09):
    # quem decidiu subir foi uma pessoa, mas quem confere o video tambem.
    if retencao and ficha["feito"]:
        _marcar_retido(alvo, retencao, ("youtube",))
    return ficha


def _video_por_id(video_id: str):
    """O item do catalogo com aquele id. `None` se ele nao existe mais."""
    from contos.publicar import catalogo
    try:
        return next((v for v in catalogo.listar() if v.id == video_id), None)
    except Exception:                                          # noqa: BLE001
        return None


# Builds so comecaram a ir ao TikTok em 10/09/2026. Antes disso o `postar.py`
# nao tinha uma linha dele — 49 publicacoes, todas YouTube, zero TikTok. Os 33
# builds anteriores a essa data NAO falharam: nunca tiveram chance. Recupera-
# los seria despejar agosto inteiro no perfil por causa de um conserto de bug,
# e isso e decisao de conteudo, do Adrian. Para recuperar os antigos, mova a
# data; nada mais precisa mudar.
#
# HISTORIAS NAO TEM CORTE, de proposito. A fila delas ja vinha drenando sob
# politica aceita (13 -> 11 no proprio dia 16/09) e tres partes de 09/09 estao
# nela. Uniformizar a regra agora tiraria video de uma fila que funciona, em
# silencio, por causa de um problema que e dos builds.
# DESLIGADAS EM 16/09/2026, as tres de uma vez, depois de repostarem no ar.
#
# A recuperacao confia no LEDGER para saber o que ja esta no TikTok, e o
# ledger NAO TEM as publicacoes antigas de la: as feitas a mao, as da grade
# propria de 13-15/09, os pedaços "1 de 2". Entao ela leu "nunca foi ao
# TikTok" sobre partes que estavam no ar havia dias e as postou de novo. Hoje
# a historia_00003 saiu duas vezes da p01 a p06, e provavelmente a h10 p01 e
# a h16 p01.
#
# O erro de metodo foi meu e tem nome: eu conferi a lista contra o ledger, e
# a pergunta era sobre o CANAL. Media a fonte errada com cuidado.
#
# So volta a ligar depois que a fila for conferida contra a lista COMPLETA do
# Studio do TikTok — por titulo, por parte e por data — e o que ja estiver la
# ganhar linha no ledger. Nao basta consertar a recuperacao: enquanto o
# ledger for cego para o passado, qualquer coisa que dependa dele para dizer
# "nunca foi" vai repetir.
# A versao do contrato do ledger que este publicador entende.
#
# 1 = "saiu?" era `bool(linha["url"])`. E o `url` guardava TRES coisas: o
#     link, a frase de estado ("publicado no YouTube (com a confirmacao
#     extra)") e, no TikTok, sempre a frase. Entao rascunho e publicacao de
#     verdade ficavam identicos para todo filtro do projeto.
# 2 = "saiu?" e `metricas.publicado(linha)`: o campo `publicado` manda quando
#     existe, e linha antiga sem ele cai no criterio de antes.
#
# O `curar_ledger` da d2 recusa gravar enquanto este numero nao for 2, e a
# razao e concreta: a cura tira a frase do `url` das linhas de TikTok, e com
# o publicador lendo `url` a guarda de "ja esta no TikTok" sumiria de 46
# builds e 51 historias — que voltariam a ser postadas. A migracao vem
# ANTES da cura, nunca depois.
CONTRATO_DO_LEDGER = 2


def _saiu(linha) -> bool:
    """Esta linha quer dizer que o video SAIU? A resposta unica do projeto.

    Um atalho para `metricas.publicado`, com import tardio porque o
    `postar.py` roda de dois cwd diferentes. Existe para que nenhum leitor
    daqui volte a perguntar `linha.get("url")` por conta propria — foi assim
    que cada arquivo ganhou o proprio criterio de "publicado".
    """
    try:
        from builds.publicar import metricas
        return metricas.publicado(linha)
    except Exception as exc:                                   # noqa: BLE001
        # NAO HA QUEDA LOCAL, e a ausencia dela e deliberada.
        #
        # Tentei escrever uma, e a varredura da cura a recusou — com razao.
        # Qualquer queda ou volta ao criterio de antes (e ai, depois da cura,
        # diz "nao saiu" para 46 builds e 51 historias, e a recuperacao
        # reposta os noventa e sete), ou olha so o campo `publicado` (e ai
        # diz "nao saiu" para toda linha anterior a cura). As duas erram
        # feio, em silencio, por um caminho raro.
        #
        # E ela nao protege nada: todo chamador de `_saiu` acabou de chamar
        # `metricas.publicados()` ou `serie.publicados()` na linha de cima.
        # Se `metricas` nao importa, a rodada ja esta morta — adivinhar so
        # troca uma falha visivel por uma decisao errada calada.
        try:
            from builds import atividade
            atividade.registrar(
                "publicacao", atividade.ERRO,
                f"nao consegui importar `metricas` para decidir se o video "
                f"saiu ({type(exc).__name__}: {str(exc)[:120]})",
                "builds", etapa="publicar.saiu")
        except Exception:                                      # noqa: BLE001
            pass
        raise


# RELIGADAS EM 17/09/2026, depois de as quatro condicoes existirem:
#
#   1. O ledger enxerga o passado do TikTok (`conciliar_tiktok.py` importou
#      as publicacoes que nunca tinham ganhado linha). Era a causa: a fila
#      lia "nunca foi" sobre partes que estavam no ar havia dias.
#   2. Teto de 2 por historia/geracao por dia, no perfil inteiro — a rodada
#      normal inclusive, que era por onde uma serie ocupava seis horarios.
#   3. Rodizio entre fontes, para a fila nao esgotar uma serie antes de
#      tocar na proxima.
#   4. Desfecho classificado: clique sem confirmacao sai da fila e espera
#      conferencia, em vez de ser reenviado ate tres vezes.
#
# Se alguma delas for desfeita, desligue as duas de novo antes.
RECUPERACAO_LIGADA = True
RESERVA_LIGADA = True

CORTE_DO_TIKTOK = {"builds": "2026-09-10"}

# Quantas partes da MESMA historia (ou variantes da mesma geracao) podem ir
# ao TikTok num dia, contando tudo: a rodada normal e a recuperacao.
#
# Decisao do Adrian em 17/09/2026, depois de ver o perfil. Em 16/09 sairam 16
# posts no TikTok e DUAS historias ocuparam onze deles — a h3 com as partes
# 1 a 6 e a h16 com 1 a 5, alternando a cada rodada. Nenhuma parte repetida:
# a recuperacao andava "uma por rodada" e a fila estava ordenada por data,
# entao ela despejou uma serie inteira em seis horas.
#
# Como as partes de uma serie compartilham o COMECO da legenda (so diferem no
# "Parte N de M" no meio do texto), o perfil ficou com seis blocos de texto
# quase identico. Indistinguivel de repeticao para quem abre.
#
# O comentario original da recuperacao dizia "os 14 de uma vez virariam
# enxurrada". Eu evitei os 14 de uma vez e produzi 6 em seis horas.
TETO_POR_FONTE_NO_DIA = 2


def _fontes_de_atraso(canal: str):
    """O ledger e o catalogo daquele canal. Os dois vivem em lugares
    diferentes: historias em `contos`, builds em `builds`."""
    if canal == "builds":
        from builds.publicar import catalogo as C
        from builds.publicar import metricas
        return metricas.publicados(), {
            v.id: v for v in C.listar()
            if getattr(v, "perfil", "") == "celular"}
    from contos.publicar import catalogo, serie
    return serie.publicados(), {
        v.id: v for v in catalogo.listar()
        if getattr(v, "perfil", "") == "celular"}


VARIANTES = (":B",)


CORTE_NO_ID = re.compile(r":corte\d+$")


def _com_as_raizes(marcados) -> set:
    """Os ids marcados, mais o video INTEIRO de onde cada corte saiu.

    Video longo demais e cortado antes de subir (`cortes._copia`), e cada
    pedaco ganha `id` proprio: `X:corte01`, `X:corte02`. A marca de "a
    conferir" fica com o id do PEDACO, porque e ele que sobe — mas a fila
    escolhe pelo id do video INTEIRO. Comparando so `v.id`, o `X` continuava
    livre e voltava no horario seguinte, reenviando todos os pedacos, os que
    ja tinham saido inclusive. E a fabrica de rascunhos gemeos de novo, pela
    unica porta que ela ainda tinha.

    Bloquear o inteiro por causa de um pedaco e de proposito: reenviar `X`
    duplica os cortes que deram certo. Quem confere solta os dois juntos.

    `:corteNN` sai; `:B` e os outros sufixos ficam — variante e outro video.
    """
    raizes = set()
    for vid in marcados or ():
        vid = str(vid)
        raizes.add(vid)
        raiz = CORTE_NO_ID.sub("", vid)
        if raiz != vid:
            raizes.add(raiz)
    return raizes


def _sem_a_conferir(fila: list, canal: str) -> list:
    """Tira da fila quem subiu ao YouTube sem confirmacao.

    E A FABRICA DE RASCUNHOS GEMEOS. Quando o Studio nao mostra a
    confirmacao, `publicar_como_configurado` nao grava linha no ledger; como
    a fila escolhe pelo que ainda nao foi registrado, o MESMO video volta no
    horario seguinte e sobe DE NOVO. Cada tentativa deixa um rascunho — e sao
    22 no canal.

    No TikTok o defeito so tirava o video da fila; aqui ele o reenviava.

    Se nao der para ler a lista, a fila fica VAZIA: o horario sem post custa
    um video, e reenviar custa mais um rascunho em cima dos 22.
    """
    if not fila:
        return fila
    try:
        marcados = a_conferir_no_tiktok(canal, "youtube")
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[postar] {canal}: nao consegui ler quem esta a conferir no "
               f"YouTube ({type(exc).__name__}); NAO publico nesta rodada.")
        return []
    if not marcados:
        return fila
    marcados = _com_as_raizes(marcados)
    livres = [v for v in fila if v.id not in marcados]
    if len(livres) != len(fila):
        _linha(f"[postar] {len(fila) - len(livres)} video(s) fora da fila: "
               f"subiram ao YouTube sem confirmacao e esperam conferencia.")
    return livres


def _sem_fonte_cheia(fila: list, canal: str, agora=None,
                     plataformas=("youtube",)) -> list:
    """Tira da fila as historias/geracoes que ja bateram o teto HOJE.

    O teto vale por DESTINO (2 por dia de grade NO PERFIL, decisao de
    17/09/2026 e `teto-por-fonte-dia-de-grade`). Ate 19/10/2026 a rodada
    levava o MESMO video aos dois, e por isso esta fila olhava os dois tetos.
    Com a fila propria do TikTok (decisao `tiktok-seis-por-dia`) as filas que
    passam aqui sao do YOUTUBE, e o TikTok confere o dele em
    `_fila_do_tiktok`: olhar o do TikTok aqui faria a serie que o TikTok
    alcanca hoje (atrasado) sumir da fila do YouTube, que esta a frente dela.
    O valor do teto nao muda.

    Se TODAS as fontes estiverem cheias, devolve vazio e o horario fica sem
    post, pela mesma regra do titulo repetido: repetir (ou empilhar a mesma
    serie) e pior que nao postar.
    """
    if not fila:
        return fila
    try:
        publicados = _publicados_do_canal(canal)
    except Exception:                                          # noqa: BLE001
        return fila                    # "nao sei" nao pode barrar a rodada
    cheias = set()
    for plataforma in plataformas:
        cheias |= _fontes_cheias_hoje(publicados, plataforma, agora)
    if not cheias:
        _avisar_variedade(canal, fila, publicados, agora)
        return fila
    livres = [v for v in fila if str(v.id).split(":")[0] not in cheias]
    barradas = len(fila) - len(livres)
    if barradas:
        _linha(f"[postar] {barradas} parte(s) fora da fila: a historia ja "
               f"saiu {TETO_POR_FONTE_NO_DIA}x hoje "
               f"({', '.join(sorted(cheias)[:3])}).")
    # A PRIORIDADE MANUAL TAMBEM E ADIADA PELO TETO, e isso precisa aparecer:
    # o Adrian pede um video para furar a fila e ele simplesmente nao sai.
    # Adiar e o certo (o teto e regra dele), mas em silencio parece defeito.
    try:
        pedidos = set(_prioridades())
    except Exception:                                          # noqa: BLE001
        pedidos = set()
    adiados = [v.id for v in fila if v.id in pedidos and v not in livres]
    for vid in adiados:
        _linha(f"[postar] o pedido {vid} fica para amanha: a historia dele "
               f"ja saiu {TETO_POR_FONTE_NO_DIA}x hoje.")
    _avisar_variedade(canal, livres, publicados, agora)
    return livres


def _horarios_que_restam(publicados, agora=None,
                         plataforma: str = "youtube") -> int:
    """Quantos horarios da grade AINDA vao receber video hoje neste canal.

    "Hoje" e o DIA DE GRADE (06:37 -> 00:37), o mesmo do teto por fonte
    (`_saidas_hoje`, decisao `teto-por-fonte-dia-de-grade` de 29/09/2026):
    a capacidade e os horarios tem de contar o MESMO dia, senao a rodada
    das 00:37 comparava "o dia inteiro pela frente" (10) com a capacidade
    de um dia que ja estava quase fechado, e o aviso falso de 28/09 voltava.

    Os horarios do dia de grade depois do corrente, mais o corrente se nada
    saiu nele ainda (a rodada que esta escolhendo agora e a dele). "Saiu
    nele" e `conferencia.chave_do_horario` da linha igual ao de agora, com
    `metricas.publicado` — os criterios unicos (os mesmos da guarda
    `publicou_neste_horario`), e nao a hora do relogio.

    Conta de mao (sem nada no horario corrente): 21:37 -> 21, 22, 23 e 00:37
    = 4; 00:10 -> o 23:37 da vespera e o 00:37 = 2; 06:37 -> 10.
    """
    from datetime import datetime
    from builds.publicar import conferencia, metricas
    agora = agora or datetime.now()
    corrente = conferencia.chave_do_horario(agora, plataforma)
    abertura, _ = conferencia.abertura_e_fechamento(plataforma)
    ordem = sorted(grade.horas_da_plataforma(plataforma),
                   key=lambda h: (conferencia._minutos(h)
                                  - conferencia._minutos(abertura)) % (24 * 60))
    restam = len(ordem) - ordem.index(corrente[1]) - 1
    for linha in publicados or ():
        if str(linha.get("plataforma") or "youtube").lower() != plataforma:
            continue
        if not metricas.publicado(linha):
            continue
        if conferencia.chave_do_horario(linha.get("quando"),
                                        plataforma) == corrente:
            return restam
    return restam + 1


def _capacidade_de_hoje(fila: list, publicados, agora=None) -> dict | None:
    """O que as series da fila ainda entregam HOJE. `None` = nao sei contar.

    `agenda.series_elegiveis` responde "quantas partes seguidas cada serie
    entrega com o teto do dia" (ordem das partes; a parte que falta segura
    as seguintes). Aqui cada serie e limitada tambem pelo que ela JA levou
    hoje: a que saiu uma vez so entrega mais uma. A contagem de hoje e a de
    `_fontes_cheias_hoje` (`_saidas_hoje`), pelo destino mais cheio.
    Builds (`generation_*`) dao `None`: `series_elegiveis` so conta historia.
    """
    try:
        from contos.pipeline import agenda
    except Exception:                                          # noqa: BLE001
        return None
    conta = agenda.series_elegiveis(fila, publicados, TETO_POR_FONTE_NO_DIA)
    if conta is None:
        return None
    ja = [_saidas_hoje(publicados, p, agora) for p in grade.PLATAFORMAS]
    capacidade, series = 0, 0
    for fonte, dela in conta["por_serie"].items():
        usadas = max(c.get(fonte, 0) for c in ja)
        entrega = max(0, min(dela["entrega"], TETO_POR_FONTE_NO_DIA - usadas))
        capacidade += entrega
        series += 1 if entrega else 0
    return {"capacidade": capacidade, "series": series}


def _avisar_variedade(canal: str, fila: list, publicados, agora=None) -> str:
    """O aviso de falta de VARIEDADE, so quando ela falta para o RESTO do dia.

    POR QUE (28/09/2026): o aviso comparava as series distintas da fila com
    as cinco que o dia INTEIRO precisa (10 horarios / teto 2), a qualquer
    hora. As 21:37, com tres horarios pela frente, "so 4 serie(s)
    elegivel(is) hoje, e o dia precisa de 5" era falso — quatro series
    cobrem tres horarios com folga — e o log tem 164 desses avisos. E sem
    nenhuma fonte cheia ele nem era avaliado (a funcao voltava antes). Agora
    compara a capacidade de hoje (`_capacidade_de_hoje`) com os horarios que
    restam (`_horarios_que_restam`). Com ZERO series e horario pela frente,
    avisa: e o caso em que a falta e total.

    Devolve a frase (vazia quando nao avisa), para o teste.
    """
    try:
        cap = _capacidade_de_hoje(fila, publicados, agora)
        restam = _horarios_que_restam(publicados, agora)
    except Exception:                                          # noqa: BLE001
        return ""                      # aviso nunca derruba a fila
    if cap is None or restam <= 0 or cap["capacidade"] >= restam:
        return ""
    frase = (f"[postar] ATENCAO {canal}: so {cap['series']} serie(s) "
             f"elegivel(is) hoje; elas cobrem {cap['capacidade']} dos "
             f"{restam} horario(s) que restam (teto de "
             f"{TETO_POR_FONTE_NO_DIA} por serie). Falta VARIEDADE, nao "
             f"partes.")
    _linha(frase)
    return frase


def _saidas_hoje(publicados, plataforma: str = "tiktok", agora=None):
    """`Counter` fonte -> quantas vezes saiu HOJE naquele destino.

    Conta pelo LEDGER e por DATA, e nao por rodada: a rodada normal e a
    recuperacao publicam por caminhos diferentes, e o teto so faz sentido se
    for sobre o que o perfil recebeu no dia, venha de onde vier.

    A fonte sai do `video_id` (`historia_00003:celular:p04` -> `historia_00003`)
    porque a linha do ledger nem sempre tem `fonte_id`.

    "HOJE" E O DIA DE GRADE (06:37 -> 00:37 do dia seguinte), pela mesma
    `conferencia.chave_do_horario` da guarda de um por horario — decisao do
    Adrian `teto-por-fonte-dia-de-grade` (29/09/2026). Pelo calendario, a
    rodada das 00:37 abria um dia novo: a `historia_00037` saiu p01 09:43,
    p02 12:10 (28/09) e p03 00:38 (29/09), tres partes no mesmo dia de grade.
    No ledger de historias, desde 17/09, 13 (destino, serie, dia de grade)
    passaram de 2; o calendario so via 3 deles. Linha sem data legivel nao
    conta e nao derruba.
    """
    from collections import Counter
    from datetime import datetime
    from builds.publicar import conferencia, metricas
    hoje = conferencia.chave_do_horario(agora or datetime.now(), plataforma)[0]
    contagem = Counter()
    for linha in publicados or ():
        if linha.get("plataforma") != plataforma:
            continue
        # SO O QUE DE FATO SAIU. Linha de tentativa que nao virou publicacao
        # nao ocupa lugar no perfil, e contar ela fecharia a fonte por causa
        # de uma falha.
        if not metricas.publicado(linha):
            continue
        chave = conferencia.chave_do_horario(linha.get("quando"), plataforma)
        if chave is None or chave[0] != hoje:
            continue
        vid = str(linha.get("video_id") or "")
        if vid:
            contagem[vid.split(":")[0]] += 1
    return contagem


def _fontes_cheias_hoje(publicados, plataforma: str = "tiktok",
                        agora=None) -> set:
    """As fontes que ja bateram o teto do dia (de grade) naquele destino (a
    contagem e `_saidas_hoje`, a mesma que limita a capacidade no aviso de
    variedade). `agora` e para o teste; os chamadores usam o relogio."""
    return {fonte for fonte, n in
            _saidas_hoje(publicados, plataforma, agora).items()
            if n >= TETO_POR_FONTE_NO_DIA}


def _em_rodizio(candidatos: list) -> list:
    """Alterna entre fontes, preservando a ordem das partes DENTRO de cada uma.

    A fila vinha em ordem de ledger, o que e cronologico e agrupa por serie —
    entao a recuperacao esgotava uma historia antes de tocar na proxima. Com
    rodizio, a primeira rodada leva a parte 1 da h3, a segunda a parte 1 da
    h4, e so depois volta para a h3.

    A ORDEM DAS PARTES E SAGRADA e nao e negociada aqui: dentro de cada fonte
    a sequencia original e mantida, porque quem viu a parte 2 e nunca recebe
    a 3 e o pior resultado possivel — pior do que qualquer atraso.
    """
    from collections import OrderedDict
    por_fonte: "OrderedDict[str, list]" = OrderedDict()
    for v in candidatos:
        por_fonte.setdefault(str(v.id).split(":")[0], []).append(v)
    saida = []
    while por_fonte:
        for fonte in list(por_fonte):
            saida.append(por_fonte[fonte].pop(0))
            if not por_fonte[fonte]:
                del por_fonte[fonte]
    return saida


def _e_variante(vid: str) -> bool:
    """Este id e o gancho ALTERNATIVO do mesmo video?

    Existe como funcao nomeada porque a alternativa era confiar no alfabeto:
    `...celular` < `...celular:B` por acidente da ordenacao, e isso inverteria
    no dia em que alguem trocasse o sufixo, em silencio.
    """
    return any(str(vid).endswith(s) for s in VARIANTES)


def desistencias_do_tiktok(canal: str = "historias") -> set:
    """De quem a recuperacao ja desistiu. Vazio se o arquivo nao existe.

    Fica ao lado do ledger que ele complementa. Quem ESCREVE aqui e o passo
    de recuperacao, ao falhar; esta metade so le, e ler um arquivo ausente e
    "ninguem desistiu de nada", nunca um erro.
    """
    import json
    try:
        caminho = _arquivo_de_desistencias(canal)
        if not caminho.is_file():
            return set()
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return {vid for vid, n in dados.items()
                if int(n) >= FALHAS_ATE_DESISTIR}
    except Exception:                                          # noqa: BLE001
        # Estado ilegivel nao pode BARRAR video: "nao sei" deixa passar.
        return set()


FALHAS_ATE_DESISTIR = 3

# A CLASSIFICACAO MUDOU-SE PARA `builds/publicar/desfecho.py` em 17/09/2026.
#
# Ela vivia aqui, e o `main.py publicar <id> --tiktok --postar` — que e o
# `/publicar` do bot e o botao do app — chama `tiktok.publicar` DIRETO: um
# clique sem confirmacao por aquele caminho nao marcava nada, e a recuperacao
# da grade repostava. Agora ela e chamada de dentro do `tiktok.publicar`, que
# e o funil por onde TODOS passam.
#
# Estes atalhos existem para o codigo daqui (e os testes) nao precisarem
# saber onde ela mora.


def desfecho_do_tiktok(estado, falha=None, laudo=None) -> str:
    from builds.publicar.desfecho import classificar
    return classificar(estado, falha, laudo)


def a_conferir_no_tiktok(canal: str = "historias",
                         plataforma: str = "tiktok") -> set:
    """LEVANTA se nao conseguir ler — quem chama nao pode seguir sem a lista."""
    from builds.publicar.desfecho import a_conferir
    return a_conferir(canal, plataforma)


def _anotar_falha_no_tiktok(canal: str, video_id: str) -> int:
    """Conta mais uma falha daquele video e devolve o total. Nunca levanta.

    Sem contador, a recuperacao pega SEMPRE `fila[0]`: um video que falha
    sempre — legenda que nunca entra, arquivo que o TikTok recusa — prende
    todos os atrasados atras dele, para sempre, gastando uma tentativa por
    rodada e nunca avancando. A fila parece andar e nao anda.

    Ao bater o teto vira ERRO no diario, e nao aviso no log: o log e lido por
    ninguem as 3 da manha, e desistir de publicar um video e exatamente o
    tipo de coisa que tem de ser contada pela apuracao.
    """
    import json
    try:
        caminho = _arquivo_de_desistencias(canal)
        dados = {}
        if caminho.is_file():
            try:
                dados = json.loads(caminho.read_text(encoding="utf-8"))
            except ValueError:
                dados = {}            # estado corrompido recomeca do zero
        total = int(dados.get(video_id, 0)) + 1
        dados[video_id] = total
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        if total == FALHAS_ATE_DESISTIR:
            from builds import atividade
            atividade.registrar(
                "publicacao", atividade.ERRO,
                f"desisti do TikTok para {video_id} depois de {total} "
                f"tentativas; ele sai da fila e libera os atrasados atras",
                canal, etapa="publicar.tiktok", ref=video_id)
        return total
    except Exception:                                          # noqa: BLE001
        # Contar e melhoria; falhar em contar nao pode derrubar a rodada.
        return 0


def _esquecer_falhas_no_tiktok(canal: str, video_id: str) -> None:
    """Video que subiu zera o contador: a fila nao guarda rancor."""
    import json
    try:
        caminho = _arquivo_de_desistencias(canal)
        if not caminho.is_file():
            return
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if dados.pop(video_id, None) is None:
            return
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        pass


def _arquivo_de_desistencias(canal: str):
    """Ao lado do `publicados.jsonl` do canal: e estado da mesma familia."""
    from builds.publicar import metricas
    return (metricas.registro_do_canal(canal).parent
            / "_tiktok_desistencias.json")


def reserva_do_tiktok(limite: int = 40) -> list:
    """Os builds de ANTES do corte, que nunca tiveram chance no TikTok.

    Decisao do Adrian em 16/09/2026: os 33 builds de 29/08 a 09/09 que sairam
    so no YouTube nao sao atraso a recuperar — sao **gordura**. Eles nao
    entram na recuperacao (que despejaria agosto inteiro de uma vez); eles
    esperam um buraco. Quando a fila normal de builds nao tem video para o
    TikTok naquele horario, sai um destes, do mais antigo para o mais novo, e
    o YouTube nao repete nada.

    Mesma peneira dos atrasados — catalogo, desistencia, titulo — porque os
    motivos sao os mesmos: 21 dos 33 passam, e os 12 que caem sao variantes
    `:B` com o titulo do proprio principal.
    """
    return _fila_do_tiktok("builds", limite, reserva=True)


def atrasados_no_tiktok(limite: int = 40, canal: str = "historias",
                        extra=()) -> list:
    """Videos que sairam no YouTube e NUNCA chegaram ao TikTok, do mais antigo.

    O buraco que isto fecha (achado pelo Adrian em 16/09/2026, quando ele viu
    que a parte 4 da "Panela da Discordia" nao estava no TikTok): a
    recuperacao que ja existia em `postar_historia` so vale DENTRO DA MESMA
    HORA — se o YouTube saiu neste disparo e o TikTok nao, ela leva o mesmo
    video. Mas quando a rodada TERMINA com o TikTok falhado, a rodada
    seguinte e outra hora, `publicou_neste_horario` devolve `None` e ela segue
    para o proximo video da fila. O que falhou nao e tentado nunca mais.

    Naquele dia eram **14 de 59** partes so no YouTube. A serie no TikTok fica
    com buraco permanente — exatamente o que ele mandou tapar em 15/09.

    BUILDS ENTRARAM EM 16/09, e o buraco era maior do lado deles: a fila de
    builds descarta todo video com `url` em QUALQUER plataforma, entao um
    build que falhasse no TikTok saia da fila para sempre. Eram 8 no periodo em
    que o TikTok ja funcionava, ~1 por dia de postagem, invisiveis.

    A ordem das etapas importa e cada uma existe por um motivo:
    1. so quem ainda esta no catalogo — video fora do disco travaria a fila;
    2. data de corte do canal (ver `CORTE_DO_TIKTOK`);
    3. **desistidos saem ANTES da deduplicacao** — se o A foi abandonado, o B
       precisa poder assumir, senao a desistencia de um VIDEO viraria a
       desistencia do TITULO;
    4. quem ja tem o titulo no TikTok sob OUTRO id nao entra. Nao da para
       reusar `titulo_repetido` aqui: ela conta `url` de qualquer plataforma e
       nao exclui o proprio id, e como todo candidato ja esta no ar no YouTube
       com o proprio titulo, ela recusaria TODOS — uma fila vazia, com os
       testes verdes, que ninguem notaria;
    5. titulo repetido dentro da propria fila fica so com o primeiro.

    `extra`: videos que AINDA NAO SAIRAM em lugar nenhum (a parte da rodada,
    o build novo), que entram no FIM da fila e passam pelos MESMOS crivos —
    e assim que a fila propria do TikTok (`_vez_do_tiktok`, 19/10/2026) leva
    o video novo quando esta em dia, sem um segundo jeito de dizer "pode ir
    ao TikTok".
    """
    return _fila_do_tiktok(canal, limite, reserva=False, extra=extra)


def _em_ordem_no_destino(candidatos: list, partes_no_destino: set,
                         canal: str) -> list:
    """Parte N so sai depois que a N-1 ja esta NESTE destino.

    MEDIDO EM 17/09/2026, todas as series dos dois canais: no YouTube 3 de 13
    sairam fora de ordem — todas anteriores a guarda de 14/09, que ja
    conserta aquele lado. No TIKTOK sao 7 de 13, e ainda acontecendo. A pior
    e a `historia_00003`, que saiu 7, 8, 9, 10 e SO ENTAO 1 a 6: quem comecou
    a acompanhar recebeu o fim primeiro.

    Dois mecanismos produziam isso, e a guarda fecha os dois de uma vez
    porque pergunta pelo DESTINO em vez de pelo ledger:

    - a fila do TikTok e partida em duas por data (`CORTE_DO_TIKTOK`):
      "atraso" depois do corte e "reserva" antes dele. Serie que atravessa o
      corte saia com as partes novas primeiro, por construcao.
    - a fila segue a ordem do ledger, que e a ordem do YOUTUBE. Uma desordem
      la era copiada para ca — para sempre, e mesmo depois de consertada la.

    "A N-1 ESTA NO DESTINO?", e nao "a ordem foi respeitada": as sete series
    ja embaralhadas nao podem travar para sempre. Na `historia_00009` o
    TikTok tem 1, 2, 3, 4 e 6; a parte 5 exige 1 a 4, que estao la, entao ela
    sai — e e exatamente o que conserta a serie.

    SEM ULTIMO RECURSO AQUI, ao contrario do YouTube. La o "fora de ordem" e
    escolha consciente do Adrian para o horario nao ficar vazio; aqui a
    recuperacao e sempre EXTRA, entao pular para outra serie nao custa nada e
    parte fora de ordem custa quem esta acompanhando.

    E O QUE TRAVA APARECE. Se a parte anterior foi abandonada, a serie para
    neste destino — e parar em silencio e o defeito que deixou 20 builds
    esperando duas semanas com o contador parecendo certo.
    """
    livres, presos = [], []
    for video in candidatos:
        parte = int(getattr(video, "parte", 0) or 0)
        fonte = str(getattr(video, "fonte_id", "") or "")
        if parte <= 1 or not fonte:
            livres.append(video)          # build, torneio, ou a propria p01
            continue
        faltam = [n for n in range(1, parte)
                  if (fonte, n) not in partes_no_destino]
        if faltam:
            presos.append((video, faltam))
        else:
            livres.append(video)
    if presos:
        detalhe = "; ".join(
            f"{v.id} espera a(s) parte(s) {','.join(str(n) for n in f)}"
            for v, f in presos[:3])
        _linha(f"[postar] {canal}: {len(presos)} parte(s) fora da fila do "
               f"TikTok por ordem da serie: {detalhe}"
               f"{'...' if len(presos) > 3 else ''}")
    return livres


def _fila_do_tiktok(canal: str, limite: int, *, reserva: bool,
                    extra=()) -> list:
    """O corpo comum de `atrasados_no_tiktok` e `reserva_do_tiktok`.

    As duas filas sao o MESMO calculo sobre faixas de data complementares:
    atraso e o que falhou depois do corte, reserva e o que nunca teve chance
    antes dele. Uma so implementacao para que um crivo novo (desistencia,
    titulo) nunca exista em uma e falte na outra.

    `extra` (so no atraso) entra no fim, depois dos que ja estao no YouTube,
    e passa pelos mesmos crivos; quem ja esta no TikTok ou ja veio do ledger
    nao entra de novo.
    """
    from builds.publicar import titulos

    try:
        publicados, no_catalogo = _fontes_de_atraso(canal)
    except Exception:                                          # noqa: BLE001
        return []

    corte = CORTE_DO_TIKTOK.get(canal, "")
    if reserva and not corte:
        return []                  # canal sem corte nao tem reserva
    no_tiktok, titulos_no_tiktok = set(), {}
    partes_no_tiktok = set()
    for l in publicados:
        if l.get("plataforma") != "tiktok" or not _saiu(l):
            continue
        no_tiktok.add(l.get("video_id"))
        parte = l.get("parte")
        if parte and l.get("fonte_id"):
            partes_no_tiktok.add((str(l.get("fonte_id")), int(parte)))
        chave = titulos.chave(l.get("titulo"))
        if chave:
            titulos_no_tiktok.setdefault(chave, l.get("video_id"))

    # Desistidos E os que esperam conferencia saem antes da deduplicacao, pelo
    # mesmo motivo: se o A esta fora, o B precisa poder assumir o titulo.
    # FALHA FECHADA, e e a unica do projeto: sem a lista de bloqueados eu
    # nao sei quem esta esperando conferencia, e a recuperacao repostaria
    # todos eles. Adiar uma rodada custa um video; repostar custa o perfil.
    desistidos = _com_as_raizes(
        desistencias_do_tiktok(canal) | a_conferir_no_tiktok(canal))
    candidatos, vistos = [], set()
    for linha in publicados:                     # ledger ja vem em ordem
        if linha.get("plataforma") != "youtube" or not _saiu(linha):
            continue
        vid = linha.get("video_id")
        if not vid or vid in no_tiktok or vid in vistos:
            continue
        vistos.add(vid)
        antigo = (linha.get("quando") or "")[:10] < corte
        if corte and antigo != reserva:
            continue
        if vid in desistidos:
            continue
        alvo = no_catalogo.get(vid)
        if alvo is not None:
            candidatos.append(alvo)
    for alvo in (() if reserva else extra or ()):
        vid = getattr(alvo, "id", None)
        if (alvo is None or not vid or vid in no_tiktok or vid in vistos
                or vid in desistidos):
            continue
        vistos.add(vid)
        candidatos.append(alvo)

    # A ORDEM DA SERIE, NESTE DESTINO. Vem antes do rodizio e do teto porque
    # e sobre o video, e nao sobre o dia.
    candidatos = _em_ordem_no_destino(candidatos, partes_no_tiktok, canal)

    # TETO POR FONTE NO DIA: uma historia nao ocupa o perfil inteiro. Aplicado
    # aqui, depois dos outros crivos, porque e sobre o DIA e nao sobre o video.
    cheias = _fontes_cheias_hoje(publicados)
    if cheias:
        candidatos = [v for v in candidatos
                      if str(v.id).split(":")[0] not in cheias]

    # A ORDEM DENTRO DE CADA FONTE CONTINUA SENDO A DO LEDGER (as partes tem
    # de sair em sequencia), mas as fontes ALTERNAM. Antes a fila vinha
    # agrupada por serie e a recuperacao esgotava uma antes de tocar na
    # proxima — foi assim que a h3 ocupou seis horarios num dia.
    candidatos = _em_rodizio(candidatos)

    # A regra "principal antes da variante" e desempate DENTRO do mesmo
    # titulo, nao ordenacao geral.
    principais = {titulos.chave(getattr(v, "titulo", "")) for v in candidatos
                  if not _e_variante(v.id)}
    atrasados, chaves = [], set()
    for alvo in candidatos:
        chave = titulos.chave(getattr(alvo, "titulo", ""))
        if chave and titulos_no_tiktok.get(chave, alvo.id) != alvo.id:
            continue
        if chave and chave in chaves:
            continue
        if chave and _e_variante(alvo.id) and chave in principais:
            continue          # o principal esta pendente: ele vai, este nao
        chaves.add(chave)
        atrasados.append(alvo)
        if len(atrasados) >= limite:
            break
    return atrasados


def recuperar_no_tiktok(so_ver: bool = False,
                        canal: str = "historias") -> dict:
    """Leva UM atrasado por rodada ao TikTok. Nunca derruba a rodada.

    UM, e nao todos, de proposito: os 14 de uma vez virariam enxurrada no
    perfil e enterrariam a serie nova. Com dez horarios por dia a fila
    atrasada se fecha em menos de dois dias, na ordem em que os videos
    sairam no YouTube.

    UM POR CANAL, e nao um no total: com fila unica os builds ficariam atras
    de 11 historias — mais de um dia sem a primeira recuperacao, enquanto
    falhas novas entram. Por canal, cada fila anda uma por rodada, o
    acumulado de builds (8) fecha em um dia e o passo fica ocioso depois. O
    custo maximo e uma postagem de TikTok a mais por rodada, e ele some
    sozinho quando nao ha atraso.

    DESDE 19/10/2026 ELA SO TAPA BURACO (decisao `tiktok-seis-por-dia`): o
    atraso e a cabeca da fila propria do TikTok (`_vez_do_tiktok`), entao a
    rodada ja o leva no horario. Este passo so roda num horario DA GRADE DO
    TIKTOK em que aquele perfil ainda nao recebeu nada — o post da rodada
    falhou e sobrou tempo. Sem isto, os quatro horarios so do YouTube
    virariam quatro posts "recuperados" por dia, e o teste de seis por dia
    postaria dez. Fora da grade ou com o horario ja pago, nada e tentado (e
    nada conta como falha do video).
    """
    if not RECUPERACAO_LIGADA:
        return {"feito": False, "fila": 0, "canal": canal,
                "motivo": "recuperacao desligada (ver RECUPERACAO_LIGADA)"}
    ocupado = _vaga_do_tiktok(canal, so_ver=so_ver)
    if ocupado:
        return {"feito": False, "fila": 0, "canal": canal, "motivo": ocupado}
    fila = atrasados_no_tiktok(canal=canal)
    if fila and canal == "builds":
        # A MESMA ESCOLHA DA RODADA (20/10/2026, `_vez_do_tiktok_builds`): um
        # por dia contra tres do YouTube, o mais NOVO do atraso e de
        # confronto que o TikTok nao levou na semana — o mais velho seria um
        # duelo de dias atras.
        fila = _sem_confronto_repetido(
            sorted(fila, key=_quando_do_video, reverse=True), "tiktok")
    if not fila:
        return {"feito": False, "fila": 0, "canal": canal}
    alvo = fila[0]
    if so_ver:
        return {"feito": False, "fila": len(fila), "veria": alvo.id,
                "canal": canal}
    _linha(f"[postar] recuperando no TikTok ({canal}): {alvo.id} "
           f"({len(fila)} atrasado(s) na fila).")
    # O PUBLICADOR E DIFERENTE POR CANAL e nao da para escolher um so: em
    # builds o registro acontece DENTRO de `tiktok.publicar`, e em historias
    # ele acontece fora, porque `registrar_publicado` descarta tudo que nao e
    # do canal `builds`. Trocar um pelo outro duplicaria linha de um lado e
    # perderia a linha do outro.
    falha: dict = {}
    estado = (_tiktok_dos_builds(alvo, falha) if canal == "builds"
              else _tiktok_das_historias(alvo, falha))
    desfecho = ("recusado" if falha.get("recusa")
                else desfecho_do_tiktok(estado, falha))
    feito = desfecho == "publicado"
    valvula: dict = {"canal": canal, "alvo": alvo.id}
    if feito:
        _esquecer_falhas_no_tiktok(canal, alvo.id)
        # A RETIDA QUE CHEGA AQUI FICA A CONFERIR NO TIKTOK (05/10/2026). A
        # valvula e de historias: builds nao tem parecer de retencao.
        if canal == "historias":
            _retida_chegou_ao_tiktok(alvo, valvula)
    elif desfecho == "falha":
        _anotar_falha_no_tiktok(canal, alvo.id)
    # "infraestrutura" nao conta nada: o video continua na fila e a proxima
    # rodada tenta de novo, porque o defeito nao e dele.
    resultado = {"feito": feito, "desfecho": desfecho, "fila": len(fila),
                 "alvo": alvo.id, "titulo": getattr(alvo, "titulo", ""),
                 "canal": canal, "tiktok": estado}
    if valvula.get("retido"):
        resultado["retido"] = valvula["retido"]
    return resultado


RECUPERACAO_YOUTUBE_LIGADA = True


def _ledger_do_youtube(canal: str) -> dict:
    """{youtube_id: linha} do que o ledger sabe daquele canal.

    E o que liga o video NO CANAL ao video DO PROJETO. Sem isto a recuperacao
    veria titulos e datas e nao saberia de que build cada um saiu — e os
    crivos de fila (a conferir, teto por fonte) sao todos sobre o projeto.
    """
    try:
        publicados = _publicados_do_canal(canal)
    except Exception:                                          # noqa: BLE001
        return {}
    fora = {}
    for linha in publicados:
        vid = linha.get("youtube_id")
        if vid and str(linha.get("plataforma", "youtube")).lower() == "youtube":
            fora[str(vid)] = linha
    return fora


def privados_no_youtube(canal: str = "builds", limite: int = 40) -> list:
    """Os privados que devem voltar ao ar, ja passados pelos crivos da fila.

    `builds.publicar.recuperar` responde "quais fazem sentido NO CANAL"
    (titulo sem gemeo publico, processado, com descricao). Aqui entram os
    crivos que so o projeto conhece:

    - quem espera conferencia NAO volta sozinho. A marca existe porque
      alguem tem de olhar; torna-lo publico por conta propria seria decidir
      justamente o que a marca adiou.
    - o teto por fonte no dia vale igual. Recuperar quatro partes da mesma
      historia de uma vez e a mesma enxurrada que o teto existe para evitar,
      e o publico nao distingue "recuperado" de "postado".
    """
    from builds.publicar import recuperar

    conhecidas = _ledger_do_youtube(canal)
    fila = recuperar.recuperaveis(canal, conhecidos=set(conhecidas))

    try:
        bloqueados = _com_as_raizes(a_conferir_no_tiktok(canal, "youtube"))
    except Exception as exc:                                   # noqa: BLE001
        # FALHA FECHADA, como em `_sem_a_conferir`: sem a lista eu nao sei
        # quem esta esperando conferencia, e tornar publico e irreversivel
        # na pratica (o publico ja viu).
        _linha(f"[postar] {canal}: nao consegui ler quem espera conferencia "
               f"({type(exc).__name__}); NAO recupero nesta rodada.")
        return []

    try:
        cheias = _fontes_cheias_hoje(_publicados_do_canal(canal), "youtube")
    except Exception:                                          # noqa: BLE001
        cheias = set()

    # O APAGADO DO CANAL NAO VOLTA AO AR (21/10/2026, `videos-presos-no-
    # canal`), nem pelo id do YouTube que a linha guardou em `apagado_id`.
    try:
        from builds.publicar import metricas as _metricas
        linhas = _publicados_do_canal(canal)
        apagados = _metricas.apagados(linhas, "youtube")
        ids_apagados = {str(l.get("apagado_id")) for l in linhas
                        if _metricas.apagado_do_canal(l) and l.get("apagado_id")}
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[postar] {canal}: nao consegui ler os apagados do canal "
               f"({type(exc).__name__}); NAO recupero nesta rodada.")
        return []

    fora = []
    for video in fila:
        linha = conhecidas.get(video["id"], {})
        projeto = str(linha.get("video_id") or "")
        if projeto and projeto in bloqueados:
            continue
        if video["id"] in ids_apagados or (projeto and projeto in apagados):
            continue
        fonte = str(linha.get("fonte_id") or projeto.split(":")[0])
        if fonte and fonte in cheias:
            continue
        fora.append(dict(video, video_id=projeto, fonte_id=fonte))
        if len(fora) >= limite:
            break
    return fora


def recuperar_no_youtube(so_ver: bool = False,
                         canal: str = "builds") -> dict:
    """Devolve UM privado ao ar por rodada. Nunca derruba a rodada.

    UM, pela mesma razao do TikTok: dezesseis de uma vez viram enxurrada, e
    foi exatamente esse excesso que fez o perfil parecer repetitivo em
    16/09. Com dez horarios por dia a fila fecha em menos de dois dias, do
    mais antigo para o mais novo.

    ANTES do render novo, e nao depois: estes videos ja existem, ja custaram
    render, ja tem capa e descricao, e estao parados desde 31/08. Gastar um
    horario subindo coisa nova enquanto eles esperam e jogar fora trabalho
    que ja foi pago.

    NAO grava linha nova no ledger quando o video ja tem a dele. A linha que
    existe ja diz "publicado no YouTube" com o id certo — foi ela que
    permitiu achar o video no canal. Uma segunda linha contaria a mesma
    publicacao duas vezes em toda estatistica, e a cura do ledger passaria a
    ver duplicata onde ha conserto. O que e novo e o ACONTECIMENTO, e
    acontecimento vai para o diario.
    """
    if not RECUPERACAO_YOUTUBE_LIGADA:
        return {"feito": False, "fila": 0, "canal": canal,
                "motivo": "recuperacao desligada "
                          "(ver RECUPERACAO_YOUTUBE_LIGADA)"}
    from builds.publicar import recuperar
    try:
        fila = privados_no_youtube(canal)
    except recuperar.FaltaEscopo as exc:
        # O TEXTO SAI UMA VEZ SO, e quem imprime e quem chama. Impresso aqui
        # E devolvido em `detalhe`, ele aparecia duas vezes seguidas na tela —
        # dez linhas repetidas fazem qualquer aviso parecer defeito.
        return {"feito": False, "fila": 0, "canal": canal,
                "motivo": "falta o escopo de edicao", "detalhe": str(exc)}
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[postar] {canal}: nao consegui ler o canal "
               f"({type(exc).__name__}: {exc}).")
        return {"feito": False, "fila": 0, "canal": canal,
                "motivo": f"{type(exc).__name__}: {exc}"[:180]}
    if not fila:
        return {"feito": False, "fila": 0, "canal": canal}

    alvo = fila[0]
    if so_ver:
        return {"feito": False, "fila": len(fila), "canal": canal,
                "veria": alvo["id"], "titulo": alvo["titulo"],
                "lista": fila}
    _linha(f"[postar] recuperando no YouTube ({canal}): {alvo['id']} "
           f"— {alvo['titulo'][:60]} ({len(fila)} na fila).")
    try:
        r = recuperar.tornar_publico(alvo["id"], canal)
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[postar] recuperacao falhou: {exc}"[:200])
        _anotar_no_diario(canal, atividade_erro=True, ref=alvo["id"], texto=(
            f"nao consegui tornar publico {alvo['id']} "
            f"({alvo['titulo'][:60]}): {exc}"[:400]))
        return {"feito": False, "fila": len(fila), "canal": canal,
                "alvo": alvo["id"], "motivo": str(exc)[:180]}

    if not r["mudou"]:
        _linha(f"[postar] {alvo['id']}: {r['motivo']}")
        _anotar_no_diario(canal, atividade_erro=True, ref=alvo["id"], texto=(
            f"pedi publico para {alvo['id']} e o canal nao mudou: "
            f"{r['motivo']}"[:400]))
    else:
        _anotar_no_diario(canal, atividade_erro=False, ref=alvo["id"], texto=(
            f"{alvo['id']} voltou ao ar ({alvo['titulo'][:60]}); estava "
            f"privado desde {alvo['quando'][:10]}. Video do projeto: "
            f"{alvo.get('video_id') or 'fora do ledger'}."))
    return {"feito": r["mudou"], "fila": len(fila), "canal": canal,
            "alvo": alvo["id"], "titulo": alvo["titulo"],
            "video_id": alvo.get("video_id"), "motivo": r["motivo"]}


def _anotar_no_diario(canal: str, texto: str, ref: str = "",
                      atividade_erro: bool = False) -> None:
    """O acontecimento vai para o diario, e nunca para o ledger.

    O ledger responde "o que foi publicado?"; estes videos ja estao nele. O
    diario responde "o que aconteceu?", e uma recuperacao e exatamente isso.
    """
    try:
        from builds import atividade
        atividade.registrar(
            "publicacao",
            atividade.ERRO if atividade_erro else atividade.OK,
            texto, canal, etapa="publicar.youtube.recuperar", ref=ref)
    except Exception:                                          # noqa: BLE001
        pass


def publicar_da_reserva(so_ver: bool = False) -> dict:
    """Tapa um buraco do TikTok com um build da gordura. So o TikTok.

    Roda quando a rodada de builds NAO levou nada ao TikTok neste horario —
    porque a fila acabou, ou porque o video da vez ja estava la. A reserva
    existe para isso: horario do TikTok vazio e alcance jogado fora, e ha 21
    builds de agosto que nunca tiveram chance.

    A condicao e lida do LEDGER, e nao de uma marca passada de mao em mao
    pela `ficha`: "o que de fato saiu neste horario" e a unica pergunta que
    importa, e ela ja tem resposta em disco. Marca carregada por parametro
    envelhece; o ledger nao.

    O YOUTUBE NAO REPETE NADA: estes videos ja estao la desde agosto. Este
    passo e exclusivamente do segundo destino.
    """
    if not RESERVA_LIGADA:
        return {"feito": False, "reserva": 0,
                "motivo": "reserva desligada (ver RESERVA_LIGADA)"}
    if not _tiktok_neste_horario():
        return {"feito": False, "reserva": 0,
                "motivo": "este horario nao e da grade do TikTok"}
    # A GRADE DOS BUILDS (20/10/2026): tres horarios, e a reserva so tapa
    # buraco DENTRO deles — fora, ela poria no TikTok de builds os quatro
    # horarios do TikTok que o canal nao tem mais.
    fora = _fora_da_grade_do_canal("builds", "tiktok")
    if fora:
        return {"feito": False, "reserva": 0, "motivo": fora}
    ja_tk = None if so_ver else publicou_neste_horario("builds", "tiktok")
    if ja_tk and ja_tk.get("ledger_ilegivel"):
        return {"feito": False, "reserva": 0,
                "motivo": ja_tk["ledger_ilegivel"]}
    if ja_tk:
        return {"feito": False, "reserva": 0,
                "motivo": "builds ja foi ao TikTok neste horario"}
    fila = reserva_do_tiktok()
    if not fila:
        return {"feito": False, "reserva": 0}
    alvo = fila[0]
    if so_ver:
        return {"feito": False, "reserva": len(fila), "veria": alvo.id}
    _linha(f"[postar] reserva do TikTok: {alvo.id} "
           f"({len(fila)} na gordura).")
    falha: dict = {}
    estado = _tiktok_dos_builds(alvo, falha)
    desfecho = ("recusado" if falha.get("recusa")
                else desfecho_do_tiktok(estado, falha))
    feito = desfecho == "publicado"
    # A reserva tem a MESMA cabeca de fila que os atrasados, e portanto o
    # mesmo jeito de travar: um video que o TikTok sempre recusa seguraria os
    # outros 20 indefinidamente.
    if feito:
        _esquecer_falhas_no_tiktok("builds", alvo.id)
    elif desfecho == "falha":
        _anotar_falha_no_tiktok("builds", alvo.id)
    return {"feito": feito, "desfecho": desfecho, "reserva": len(fila),
            "alvo": alvo.id, "titulo": getattr(alvo, "titulo", ""),
            "tiktok": estado}


def _tiktok_neste_horario(agora=None) -> bool:
    """Este disparo e horario de TikTok?

    A grade do TikTok mora em `builds.grade.HORAS_POR_PLATAFORMA`. De 13 a
    15/09/2026 ela era mais curta que a do YouTube (sem 7h e 8h), e a fila
    avancava sem ele: a parte desses horarios nunca chegava ao TikTok. Desde
    15/09 ele posta em todos, por decisao dele ("tapar esses buracos").

    O HORARIO E O DA GRADE, e nao a hora do relogio — conserto de 15/09/2026,
    18:01. O disparo das 17:57 publicou a historia as 17:59 (hora 17) e o
    build as 18:01, e a hora 18 nao esta na grade: o build perdeu o TikTok com
    "fora da grade do TikTok neste horario". Na mesma rodada, dois veredictos.
    E nao foi acaso deste dia: :57 mais os ~4 min de upload cruzam a hora
    todo dia. `grade.slot` diz a que horario a rodada pertence.
    """
    from datetime import datetime
    agora = agora or datetime.now()
    return grade.publica_em("tiktok", grade.slot(agora))


# ------------------------------------------- a grade de cada canal (20/10)
# O CANAL DE BUILDS POSTA SO NOS SEUS TRES HORARIOS (`grade.HORAS_POR_CANAL`,
# `docs/PLANO.md` semana 1): 09:37, 17:57 e 21:37, nos dois destinos. As
# historias seguem com a grade inteira de cada plataforma.
#
# OS CAMINHOS que levam um build ao ar sozinhos, contados: a rodada
# (`postar_build`), a recuperacao do TikTok e a reserva (as duas entram pela
# porta `_tiktok_dos_builds` -> `_recusa_do_tiktok` -> `_vaga_do_tiktok`), a
# segunda subida do YouTube na divida (`_alcance_do_youtube_dos_builds`, de
# dentro de `postar_build`) e a recuperacao do YouTube (privado que volta ao
# ar, chamada pela rodada). Os cinco perguntam AQUI — e so aqui o relogio e
# lido para isso, para o teste que nao e sobre o horario fixar uma funcao so
# (a mesma regra do `_vaga_do_tiktok`: nenhum teste depende de que horas sao).
def _fora_da_grade_do_canal(canal: str, plataforma: str, agora=None) -> str:
    """"" quando o horario desta rodada (`grade.slot`) e da grade DAQUELE
    canal naquela plataforma (`grade.publica_no_canal`); senao o motivo.

    Canal SEM grade propria (historias): sempre "" — a grade da plataforma
    e de `_tiktok_neste_horario`, e repeti-la aqui faria a porta do TikTok
    das historias ler o relogio de verdade por um segundo caminho (medido
    no ramo, 20/10: 6 testes vermelhos com o relogio simulado nas 06:30).
    Nunca levanta.
    """
    from datetime import datetime
    if str(canal or "").lower() not in grade.HORAS_POR_CANAL:
        return ""
    try:
        agora = agora or datetime.now()
        hora = grade.slot(agora)
        # A tabela do DIA (`grade.tabela_do_canal`: a de 01/11 em diante e 1 h
        # mais tarde, o fim do horario de verao nos EUA).
        if grade.publica_no_canal(canal, plataforma, hora, agora):
            return ""
        proprios = ", ".join(grade.horarios(plataforma, canal,
                                            agora)) or "nenhum"
        return (f"o horario das {grade.horario(hora)} nao e da grade de "
                f"{canal} no {plataforma} ({proprios})")
    except Exception as exc:                                   # noqa: BLE001
        # "Nao sei" nao barra: a grade e pura, e isto so falharia com o
        # modulo quebrado — as guardas de repeticao continuam de pe.
        _linha(f"[postar] grade do canal ilegivel ({type(exc).__name__}); "
               "sigo pela grade da plataforma.")
        return ""


# ------------------------------------------------ a porta do TikTok (funil)
# SEIS POR DIA E A ORDEM DA SERIE, EM TODO CAMINHO (19/10/2026, decisao
# `tiktok-seis-por-dia`). Contados os caminhos que chegam ao TikTok pelo
# postar: a rodada de historias, a de builds, a recuperacao (dos dois
# canais), a reserva e o escoar (`--tudo`) — seis, e so os dois funis abaixo
# sao comuns a todos. A guarda mora neles, e nao em cada chamada: a regra
# "fora da grade do TikTok nao posta" ja existia na rodada e na reserva, e a
# recuperacao nao a tinha — com a grade de seis ela postaria nos quatro
# horarios so do YouTube.
def _vaga_do_tiktok(canal: str, agora=None, *, so_ver: bool = False) -> str:
    """"" quando ESTE horario e da grade do TikTok e aquele perfil ainda nao
    recebeu nada nele; senao o motivo. UM lugar so para as duas perguntas que
    dependem do RELOGIO e do LEDGER de verdade (a grade de `grade.slot` e
    `publicou_neste_horario`): a porta do TikTok e a recuperacao passam por
    aqui, e o teste que nao e sobre o horario fixa esta funcao — nenhum teste
    pode depender de que horas sao nem do ledger de producao (conferente do
    be9c70ae, 19/10/2026: aplicado as 16:0x, com o 15:37 ja pago no ledger
    real, a recuperacao recusava e 10 testes antigos ficaram vermelhos).

    `so_ver` nao le o ledger (o `--ver` nao barra pelo horario pago). Ledger
    ilegivel = ocupado (falha fechada, como a guarda de um por horario).
    """
    if not _tiktok_neste_horario(agora):
        return "este horario nao e da grade do TikTok"
    fora = _fora_da_grade_do_canal(canal, "tiktok", agora)
    if fora:
        return fora
    if so_ver:
        return ""
    ja = publicou_neste_horario(canal, "tiktok", agora)
    if ja:
        return (ja.get("ledger_ilegivel")
                or f"o TikTok deste perfil ja saiu neste horario "
                   f"({ja.get('video_id')})")
    return ""


def _recusa_do_tiktok(canal: str, alvo, agora=None) -> str:
    """Por que `alvo` NAO pode ir ao TikTok agora; "" quando pode.

    1. o horario da rodada nao e da grade do TikTok (`grade.HORAS_DO_TIKTOK`);
    2. aquele perfil ja recebeu um post neste horario (o mesmo criterio de
       `publicou_neste_horario`: `conferencia.chave_do_horario`) — e o que
       segura o TikTok em UM por horario, seis por dia;
    3. o video espera conferencia no TikTok (clique sem confirmacao, luta
       muda): repostar seria o rascunho gemeo de novo;
    4. (historias) a parte anterior da serie ainda nao esta NO TIKTOK — a
       parte N+1 nunca sai antes da N, por caminho nenhum.

    Ledger ou lista ilegivel RECUSA: as quatro sao guardas contra repetir ou
    embaralhar no perfil, e repetir e pior que nao postar (17/09). Nunca
    levanta.
    """
    try:
        ocupado = _vaga_do_tiktok(canal, agora)
        if ocupado:
            return ocupado
        try:
            marcados = _com_as_raizes(a_conferir_no_tiktok(canal, "tiktok"))
        except Exception as exc:                               # noqa: BLE001
            return (f"nao consegui ler quem espera conferencia no TikTok "
                    f"({type(exc).__name__})")
        if getattr(alvo, "id", None) in marcados:
            return "esta na lista 'a conferir' do TikTok"
        parte = int(getattr(alvo, "parte", 0) or 0)
        fonte = str(getattr(alvo, "fonte_id", "") or "")
        if canal == "historias" and parte > 1 and fonte:
            no_tiktok = {int(l.get("parte") or 0)
                         for l in _publicados_do_canal(canal)
                         if l.get("plataforma") == "tiktok" and _saiu(l)
                         and str(l.get("fonte_id") or "") == fonte}
            faltam = [n for n in range(1, parte) if n not in no_tiktok]
            if faltam:
                return (f"a parte {faltam[0]} da serie ainda nao esta no "
                        f"TikTok")
        return ""
    except Exception as exc:                                   # noqa: BLE001
        return f"nao consegui conferir a porta do TikTok ({type(exc).__name__})"


def _recusar_no_tiktok(canal: str, alvo, falha: dict | None) -> str:
    """Aplica `_recusa_do_tiktok`; devolve o motivo (e o anota em `falha`).

    A recusa nao e falha do video: `falha["recusa"]` faz a recuperacao e a
    reserva nao contarem tentativa (`_anotar_falha_no_tiktok`), senao tres
    recusas virariam uma desistencia de video bom.
    """
    motivo = _recusa_do_tiktok(canal, alvo)
    if motivo:
        _linha(f"   tiktok: {getattr(alvo, 'id', alvo)} nao vai agora — "
               f"{motivo}."[:200])
        if falha is not None:
            falha.update({"tipo": "Recusa", "mensagem": motivo,
                          "recusa": True})
    return motivo


# ------------------------------------------------ a fila propria do TikTok
# COM SEIS HORARIOS CONTRA DEZ, O TIKTOK NAO PODE LEVAR "O VIDEO DA RODADA"
# (19/10/2026, decisao `tiktok-seis-por-dia`). Era a regra desde 10/09: o
# mesmo video nos dois destinos, e a recuperacao (um extra por rodada)
# tapava o que o TikTok perdia. Com a grade de seis, os quatro horarios so do
# YouTube deixam quatro partes por dia fora do TikTok: levando a parte da
# rodada, o TikTok receberia a 3 sem a 2 (a guarda de ordem a barraria e o
# horario ficaria vazio), e a recuperacao postaria dez por dia.
#
# Entao o TikTok tem FILA PROPRIA, e ela e a fila de atraso que ja existia
# (`atrasados_no_tiktok`: o que saiu no YouTube e falta ao TikTok, na ordem
# do YouTube, cada parte so depois da anterior NO TIKTOK, teto de 2 por dia
# NO TIKTOK, rodizio de series, lista "a conferir" e desistencias), com o
# video novo da rodada no fim, pelos mesmos crivos. Quando o TikTok esta em
# dia, a cabeca e a parte da rodada — o comportamento de antes.
def _o_mesmo(achado, alvo):
    """`alvo` quando `achado` e o MESMO video (mesmo id), senao `achado`.

    A fila do TikTok monta os videos de novo a partir do catalogo; quem
    compara "o TikTok levou a parte do YouTube?" por identidade (`is`)
    precisa do mesmo objeto.
    """
    if (achado is not None and alvo is not None
            and getattr(achado, "id", None) == getattr(alvo, "id", None)):
        return alvo
    return achado


def _vez_do_tiktok_historias(novo=None) -> tuple:
    """(parte que o TikTok leva NESTE horario, motivo quando nenhuma).

    `novo`: a parte nova da rodada (ou uma funcao que a devolve, chamada so
    se a fila de atraso estiver vazia — a vistoria custa). Lista "a conferir"
    ilegivel: nenhuma (falha fechada, como na recuperacao).
    """
    try:
        fila = atrasados_no_tiktok(canal="historias")
        if not fila and novo is not None:
            candidato = novo() if callable(novo) else novo
            if candidato is not None:
                fila = atrasados_no_tiktok(canal="historias",
                                           extra=[candidato])
    except Exception as exc:                                   # noqa: BLE001
        return None, (f"nao consegui montar a fila do TikTok "
                      f"({type(exc).__name__}: {exc})")[:200]
    if not fila:
        return None, ("a fila do TikTok esta vazia: nada no YouTube falta ao "
                      "TikTok, e nao ha parte nova que passe nos crivos dele")
    return fila[0], ""


def _quando_do_video(v) -> float:
    """O `quando` (mtime do mp4) como numero; 0 quando nao ha."""
    try:
        return float(getattr(v, "quando", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _vez_do_tiktok_builds(config=None) -> tuple:
    """(build que o TikTok leva NESTE horario, motivo quando nenhum).

    O candidato e o que ja saiu no YouTube e falta ao TikTok (desde
    `CORTE_DO_TIKTOK`), O MAIS NOVO PRIMEIRO (20/10/2026); so sem nenhum
    desses, o build novo, que ainda nao saiu em lugar nenhum, pelos mesmos
    crivos (`_fila_do_tiktok`), o mais antigo primeiro. O confronto ja
    publicado no TikTok nesta semana espera (`_sem_confronto_repetido`). A
    escolha e pela MISTURA DO TIKTOK (`cota_da_plataforma`: desde 20/10 so
    duelo, como o YouTube), contada no que o TIKTOK serviu. Video mudo sai
    da escolha (o publicador o barraria de qualquer jeito).
    """
    _idade = _quando_do_video

    try:
        # UM POR DIA CONTRA TRES DO YOUTUBE (20/10/2026, `grade.HORAS_POR_
        # CANAL`): o TikTok dos builds leva o MAIS NOVO do que o YouTube ja
        # subiu e falta la — em dia normal, o duelo das 21:37, o mesmo da
        # rodada. Na ordem antiga (o mais velho primeiro) a fila dele cresce
        # dois por dia e ele postaria duelos cada vez mais velhos. Build nao
        # tem serie: pular o mais velho nao embaralha nada. So sem nada do
        # YouTube a levar ele vai ao estoque novo (o mais velho primeiro).
        pool = atrasados_no_tiktok(limite=10_000, canal="builds")
        if pool:
            pool.sort(key=_idade, reverse=True)
        else:
            # `_builds_prontos` vem do mais NOVO para o mais velho; a fila e
            # do mais velho (como em `proximo_build`).
            novos = list(reversed(_sem_a_conferir(
                _builds_prontos(config, medir_audio=False), "builds")))
            pool = atrasados_no_tiktok(limite=10_000, canal="builds",
                                       extra=novos)
            pool.sort(key=_idade)
        # SO CONFRONTOS DIFERENTES, contados no que o TIKTOK publicou.
        pool = _sem_confronto_repetido(pool, "tiktok")
    except Exception as exc:                                   # noqa: BLE001
        return None, (f"nao consegui montar a fila do TikTok "
                      f"({type(exc).__name__}: {exc})")[:200]
    servidos = _servidos_recentes(plataforma="tiktok")
    cota = cota_da_plataforma(cota_da_grade(config), "tiktok")
    while pool:
        alvo = escolher_por_cota(pool, servidos, cota)
        motivo = _audio_mudo(alvo)
        if not motivo:
            return alvo, ""
        _linha(f"[postar] {alvo.id} fora da fila do TikTok: {motivo}")
        pool = [v for v in pool if v.id != alvo.id]
    return None, "a fila do TikTok dos builds esta vazia"


@_voando("historias", "tiktok")
def _tiktok_das_historias(alvo, falha: dict | None = None) -> str:
    """Mesmo video, segundo destino. Nunca derruba a postagem do YouTube.

    O TikTok nao tem API de post: e automacao de navegador na conta dele, e
    quebra quando o site muda. Deixar isso derrubar a rodada faria o YouTube
    — que ja subiu — parecer que falhou.
    """
    from contos.publicar import catalogo, serie
    # A MESMA PARTE NAO VAI DUAS VEZES AO TIKTOK. Rede de seguranca: o caminho
    # "YouTube ja saiu nesta hora, levando so para o TikTok" pega o video do
    # ledger do YouTube, e nada ali olhava se o TikTok ja o tinha.
    if serie.ja_publicado(alvo.id, "tiktok"):
        _linha(f"   tiktok: {alvo.id} ja esta no TikTok; nao posto de novo.")
        return ""
    # A PORTA DO TIKTOK (19/10/2026): grade de seis, um por horario, lista
    # "a conferir" e a ordem da serie NO TIKTOK — para todo caminho.
    if _recusar_no_tiktok("historias", alvo, falha):
        return ""
    laudo: dict = {}
    try:
        estado = catalogo.publicar_tiktok(alvo, postar=True, log=_linha,
                                          prova=laudo)
    except Exception as exc:                                   # noqa: BLE001
        # A CAUSA PRECISA SAIR DAQUI. Devolvendo so `""`, quem chama nao
        # consegue distinguir "o Chrome nao abriu" de "o TikTok recusou o
        # video" — e trata as duas como defeito do video, abandonando video
        # bom depois de tres rodadas de maquina ruim.
        if falha is not None:
            falha["tipo"] = type(exc).__name__
            falha["mensagem"] = str(exc)[:300]
            if laudo.get("clicou"):
                falha["clicou"] = True
        _linha(f"   tiktok: NAO subiu ({type(exc).__name__}: {exc})"[:200])
        # A EXCECAO NAO PULA A CLASSIFICACAO: se o clique ja tinha saido (o
        # `laudo` guarda isso), o video precisa ir para "a conferir" mesmo
        # que o erro tenha vindo depois — e a marca que nao grava nao some
        # (`_garantir_marca`, PUB-1).
        if laudo.get("clicou"):
            _garantir_marca("historias", alvo.id, "tiktok",
                            f"cliquei em publicar no TikTok e algo falhou "
                            f"depois ({type(exc).__name__}): o post pode "
                            f"estar no ar — confira no perfil.",
                            etapa="publicar.tiktok.clique")
        return ""
    # O REGISTRO E AQUI, e nao dentro do `tiktok.publicar`. La ele chama
    # `metricas.registrar_publicado(canal="historias")`, que DESCARTA tudo que
    # nao e do canal `builds` — entao uma postagem de historia no TikTok nunca
    # ficava gravada em lugar nenhum, e a guarda de um-por-horario nunca a
    # veria. Foi assim que os dois TikToks passaram 49 publicacoes zerados.
    from builds.publicar import tiktok as _tk
    if _tk.confirmado(estado):
        serie.registrar(alvo, estado, "tiktok", None,
                        {"por": "postar.py", "visibilidade": "public",
                         "prova": [laudo] if laudo else [],
                         "prova_ok": _prova_ok(laudo)})
    return estado


def _visibilidade_das_historias() -> str:
    """A visibilidade PEDIDA pelo config, com `public` como queda — nunca `None`.

    `None` funcionava na publicacao (cada backend resolve pelo config), mas
    era veneno no registro: gravava `null` e a linha deixava de responder a
    unica pergunta que ela existe para responder.

    A chave mora em `youtube.visibilidade` (SCR-P7, 14/10/2026): ate aqui
    lia `visibilidade` na RAIZ do `historias/config/publicacao.json`, que
    nao existe, e devolvia `public` qualquer que fosse o config. O que vai
    ao LEDGER e a usada de fato (`_visibilidade_usada`); esta e so o pedido.
    """
    try:
        from contos.publicar.catalogo import carregar_config
        alvo = ((carregar_config() or {}).get("youtube") or {}).get(
            "visibilidade")
    except Exception:                                          # noqa: BLE001
        alvo = None
    return str(alvo or "public")


def _visibilidade_usada(provas, pedida: str) -> str:
    """A visibilidade que o publicador aplicou (laudos), senao a pedida.

    Decisao `publicacao/visibilidade-no-ledger` (14/10/2026). Nunca levanta:
    o registro da publicacao vale mais que a precisao deste campo.
    """
    try:
        from builds.publicar.metricas import visibilidade_usada
        return visibilidade_usada(provas, pedida) or str(pedida or "public")
    except Exception:                                          # noqa: BLE001
        return str(pedida or "public")


# ------------------------------------------------------------------ builds
# PESOS RELATIVOS de cada formato, e nao contagem de disparos: 4/3/1 quer
# dizer "quatro duelos para cada tres builds e uma estreia", repartidos pelos
# horarios do dia (dez desde 15/09/2026; eram oito quando isto nasceu). Sem
# este bloco no `publicacao.json`, a escolha volta a ser o FIFO cego de antes.
COTA_PADRAO = {"duelo": 4, "build": 3, "estreia": 1, "torneio": 0}

# Quantas publicacoes recentes contam para medir o equilibrio. Duas voltas da
# grade: curto o bastante para reagir a um formato que secou, longo o
# bastante para nao oscilar a cada disparo.
JANELA_DA_GRADE = 16


def repetir_titulo(config=None) -> bool:
    """O interruptor: `true` volta ao comportamento de antes de 16/09/2026.

    Existe porque barrar titulo repetido pode secar a fila num dia ruim, e a
    decisao de deixar a grade vazia nunca deve ser minha.
    """
    if config is None:
        try:
            from builds.publicar import catalogo as C
            config = C.carregar_config()
        except Exception:                                      # noqa: BLE001
            config = {}
    return bool(((config or {}).get("grade") or {}).get("repetir_titulo"))


def _titulos_no_ar(canal: str, plataforma: str | None = None,
                   menos: str = "") -> set:
    """Chaves de titulo ja publicadas naquele canal.

    `plataforma`: so aquele destino. A pergunta util e "ja esta no ar NO
    TIKTOK?", nao "ja esta no ar em algum lugar" — um video no YouTube e nao
    no TikTok deve poder ir ao TikTok.

    `menos`: um `video_id` a ignorar, e este parametro conserta um defeito
    que rodou o dia inteiro. `titulo_repetido` era avaliada DEPOIS de o
    YouTube ter publicado e gravado no ledger, na mesma rodada — entao a
    chave do proprio video ja estava la, posta por ele mesmo segundos antes,
    e a valvula "titulo ja publicado" abria em falso. Abriu quatro vezes em
    16/09/2026, e em nenhuma havia titulo repetido de verdade: conferido nas
    seis partes da h16, todas com chaves distintas.

    Eu mesma tinha escrito o diagnostico deste defeito horas antes, sobre a
    fila de recuperacao — "conta url de qualquer plataforma e nao exclui o
    proprio video_id" — e nao vi que ele valia aqui tambem.
    """
    try:
        from builds.publicar import titulos
        linhas = _publicados_do_canal(canal)
        if plataforma:
            # Linha antiga sem `plataforma` e do YouTube: era o unico destino
            # antes de 10/09. Hoje nenhuma das 269 linhas esta sem o campo,
            # mas assumir o padrao custa nada e evita perder linha velha.
            linhas = [l for l in linhas
                      if (l.get("plataforma") or "youtube") == plataforma]
        if menos:
            linhas = [l for l in linhas if l.get("video_id") != menos]
        return titulos.ja_publicados(linhas)
    except Exception as exc:                                   # noqa: BLE001
        # Sem ledger legivel nao da para saber o que ja saiu — e "nao sei"
        # tem que deixar passar, nunca barrar.
        #
        # Mas tem de APARECER. Com a valvula fechada, este `set()` vazio quer
        # dizer "nao ha repeticao" para quem chama, e um ledger ilegivel
        # liberaria tudo em silencio — exatamente o tipo de "nao sei" que
        # vira afirmacao quando ninguem escreve nada.
        try:
            from builds import atividade
            atividade.registrar(
                "publicacao", atividade.ERRO,
                f"nao consegui ler os titulos ja publicados de {canal} "
                f"({type(exc).__name__}: {str(exc)[:120]}); a guarda de "
                f"titulo repetido fica CEGA nesta rodada",
                canal, etapa="publicar.titulo_repetido")
        except Exception:                                      # noqa: BLE001
            pass
        return set()


# As marcas da ficha que querem dizer "saiu, mas pela valvula". A ordem e a
# da gravidade, e e a que o relatorio mostra.
VALVULAS = {
    "veto_vencido": "veto da IA venceu (a passada de conserto ja foi gasta)",
    "veto_ignorado": "veto da IA ignorado (nao havia outro video pronto)",
    "retido": "saiu RETIDA pela valvula de qualidade (nao havia outra parte)",
    # A valvula fechou em 17/09, entao esta marca mudou de sentido: ela nao
    # e mais "saiu assim mesmo porque nao havia outro", e sim um DETECTOR —
    # se aparecer, algum caminho escapou da guarda e o relatorio tem de
    # gritar. Pelo desenho novo ela deveria ficar em zero para sempre.
    "titulo_repetido": "ESCAPOU: saiu com titulo que outro video ja pos no ar",
}


def _registrar_valvula(ficha: dict) -> None:
    """Grava no diario cada vez que a valvula abriu. Nunca levanta.

    Ate 16/09/2026 a valvula so existia na FICHA, que vira mensagem do
    Telegram e some. "Libera o menos pior com aviso" e a regra do Adrian —
    mas um aviso que ninguem soma deixa a excecao virar rotina sem que
    ninguem perceba. No diario ela passa a ser contavel pela pagina de
    confiabilidade e pelo resumo do dia.

    So conta o que de fato SAIU: valvula de rodada que nao publicou nada nao
    liberou nada.
    """
    try:
        if not ficha or not ficha.get("feito"):
            return
        from builds import atividade
        for marca, motivo in VALVULAS.items():
            if ficha.get(marca):
                atividade.registrar(
                    "publicacao", atividade.LOG, motivo,
                    ficha.get("canal") or "builds", etapa="valvula",
                    ref=f"{ficha.get('alvo', '')}|{marca}")
    except Exception:                                          # noqa: BLE001
        pass


def titulo_repetido(alvo, canal: str, plataforma: str | None = None) -> bool:
    """OUTRO video ja pos este titulo no ar (naquele destino)?

    Recalcula em vez de carregar o estado da escolha: a fila e montada num
    lugar e a ficha em outro, e passar a marca por parametro obrigaria a
    mudar a assinatura de todo o caminho. O ledger tem poucas centenas de
    linhas — recalcular custa menos que a complicacao.

    "OUTRO" e a palavra que faltava: o proprio `video_id` sai da conta. Sem
    isso, todo video que acabava de sair no YouTube se acusava de repetir a
    si mesmo na mesma rodada.
    """
    if repetir_titulo():
        return False
    try:
        from builds.publicar import titulos
        return titulos.repetido(
            getattr(alvo, "titulo", ""),
            _titulos_no_ar(canal, plataforma, menos=getattr(alvo, "id", "")))
    except Exception:                                          # noqa: BLE001
        return False


def _sem_titulo_repetido(pendentes, canal: str, config=None):
    """Tira da fila quem tem titulo ja publicado. Devolve (fila, barrados).

    A VALVULA vive em quem chama: se a fila ficar vazia, o certo e sair com
    o menos pior e avisar, nao deixar o horario em branco.
    """
    if repetir_titulo(config) or not pendentes:
        return pendentes, []
    from builds.publicar import titulos
    ja = _titulos_no_ar(canal)
    if not ja:
        return pendentes, []
    novos, repetidos = [], []
    for v in pendentes:
        # `menos` nao e preciso aqui: quem esta na fila ainda nao publicou
        # nada, entao nao ha como se acusar. A exclusao do proprio id importa
        # em `titulo_repetido`, que roda DEPOIS da publicacao.
        alvo = novos if not titulos.repetido(getattr(v, "titulo", ""), ja) \
            else repetidos
        alvo.append(v)
    return novos, repetidos


def cota_da_grade(config=None) -> dict:
    """A mistura de formatos, do config ou o padrao do modulo."""
    if config is None:
        try:
            from builds.publicar import catalogo as C
            config = C.carregar_config()
        except Exception:                                      # noqa: BLE001
            config = {}
    bruta = ((config or {}).get("grade") or {}).get("mistura")
    if not isinstance(bruta, dict) or not bruta:
        return dict(COTA_PADRAO)
    return {str(k): max(0, int(v)) for k, v in bruta.items()}


# O YOUTUBE DE BUILDS NAO LEVA ESTREIA (decisao `publicacao/duelo-no-lugar-
# da-estreia`, 19/10/2026): na analise dos videos de 19/10, 28 dias, o duelo
# fez 111 views por video (89 videos, 54% assistido) e a estreia 29 (27
# videos, 13%). O peso da estreia passa ao duelo, e a estreia fica com cota
# ZERO — que aqui nunca foi proibicao: "so quando ninguem mais quer"
# (`escolher_por_cota`). Sem duelo, sai o build (roleta, 81 views); a estreia
# so sobe se nao houver nem duelo nem build, para o horario nao ficar vazio.
#
# DESDE 20/10/2026 O CANAL E DE DUELOS, NOS DOIS DESTINOS (`docs/PLANO.md`,
# semana 1: "YouTube 3/dia em horario fixo, so confrontos diferentes"; o
# TikTok, 1-3/dia, nos mesmos tres horarios — `grade.HORAS_POR_CANAL`). O
# build tambem passa o peso ao duelo, e o TikTok troca igual: com os mesmos
# tres horarios, a fila dele (o que o YouTube subiu e falta la) E o duelo do
# YouTube, e a mistura antiga (duelo 4/8) deixaria metade dos duelos do
# YouTube crescendo na fila do TikTok, cada dia mais velhos. Build e estreia
# ficam com cota zero: so saem sem duelo nenhum que possa sair (primeiro o
# build, depois a estreia — `ORDEM_SEM_COTA`), para o horario nao ficar vazio.
TROCAS_NA_COTA = {"youtube": {"estreia": "duelo", "build": "duelo"},
                  "tiktok": {"estreia": "duelo", "build": "duelo"}}
# Quem sai, sem duelo, entre os formatos de cota zero (`escolher_por_cota`).
ORDEM_SEM_COTA = ("build", "estreia")


def _trocado_no_youtube(formato_ou_id) -> bool:
    """O formato (`"estreia"`, ou o id `geracao:estreia:celular`) e um dos
    que o YouTube de builds trocou por outro (`TROCAS_NA_COTA`)?"""
    texto = str(formato_ou_id or "")
    partes = texto.split(":")
    formato = partes[1] if len(partes) > 1 else texto
    return formato in TROCAS_NA_COTA.get("youtube", {})


def cota_da_plataforma(cota: dict, plataforma: str) -> dict:
    """A mistura daquele destino, pura: `TROCAS_NA_COTA` aplicada a `cota`.

    Conta de mao (config de 19/10: duelo 4, build 3, estreia 1, torneio 0),
    desde 20/10/2026: YouTube e TikTok -> duelo 8, build 0, estreia 0,
    torneio 0. Formato trocado por um que nao esta na cota ganha o peso
    inteiro.
    """
    saida = {str(k): max(0, int(v)) for k, v in (cota or {}).items()}
    for de, para in TROCAS_NA_COTA.get(str(plataforma).lower(), {}).items():
        peso = saida.get(de, 0)
        if peso:
            saida[para] = saida.get(para, 0) + peso
            saida[de] = 0
    return saida


def _servidos_recentes(n: int = JANELA_DA_GRADE,
                       plataforma: str | None = None) -> dict:
    """Quantas das ultimas `n` publicacoes foram de cada formato.

    `plataforma`: so as daquele destino (desde 19/10/2026 cada destino tem a
    sua mistura e a sua fila; contando os dois juntos, as estreias do TikTok
    fariam o YouTube achar que ja serviu estreia, e vice-versa). Linha sem
    `plataforma` e do YouTube (era o unico destino antes de 10/09).
    """
    from builds.publicar import metricas

    contagem: dict[str, int] = {}
    linhas = [l for l in metricas.publicados() if _saiu(l)
              and (plataforma is None
                   or str(l.get("plataforma") or "youtube").lower()
                   == plataforma)]
    for linha in linhas[-n:]:
        origem = str(linha.get("origem") or "")
        if origem:
            contagem[origem] = contagem.get(origem, 0) + 1
    return contagem


def escolher_por_cota(pendentes: list, servidos: dict, cota: dict):
    """A regra de escolha, pura: sem disco, sem rede, sem catalogo.

    Entre os formatos que TEM pendente, vence o mais atrasado em relacao a
    propria cota (`servidos / cota`). Empate desempata pelo mais antigo,
    que era a regra de sempre. Cota zero nao e proibicao: e "so quando
    ninguem mais quer".

    `pendentes` chega do mais ANTIGO para o mais novo.
    """
    if not pendentes:
        return None
    if not cota:
        return pendentes[0]
    por_origem: dict[str, list] = {}
    for video in pendentes:
        por_origem.setdefault(str(getattr(video, "origem", "")), []).append(video)

    def atraso(origem: str) -> float:
        peso = cota.get(origem, 0)
        if peso <= 0:
            return float("inf")
        return servidos.get(origem, 0) / peso

    def vez_sem_cota(origem: str) -> int:
        # Entre os de cota zero ("so quando ninguem mais quer"), a ordem de
        # `ORDEM_SEM_COTA` antes da idade: sem duelo sai o build (81 views
        # por video na analise de 19/10), e so depois a estreia (29).
        if atraso(origem) != float("inf"):
            return 0
        return (ORDEM_SEM_COTA.index(origem) if origem in ORDEM_SEM_COTA
                else len(ORDEM_SEM_COTA))

    melhor = min(por_origem,
                 key=lambda o: (atraso(o), vez_sem_cota(o),
                                por_origem[o][0].quando))
    return por_origem[melhor][0]


def _audio_mudo(video) -> str:
    """O motivo quando o video sai calado; "" quando tem som (ou nao se sabe).

    A MEDIDA MORA EM `builds.publicar.audio` desde 28/09/2026, e mede duas
    coisas: o arquivo inteiro (media abaixo de -60 dB, ou calado em metade do
    tempo — a regra de 15/09) e CADA TRECHO DE LUTA antes da mixagem. A
    segunda e nova: 38 de 129 publicacoes desde 15/09 sairam com a luta a
    -91 dB debaixo da musica, e o arquivo inteiro "tinha som".

    Ferramenta que falha NAO barra: sem ffprobe/ffmpeg a grade inteira ficaria
    vazia por um problema da maquina, e nao do video. A medida e lembrada por
    arquivo (tamanho e data) entre processos — os contadores de estoque medem
    todo build pronto, em processo novo a cada relatorio.
    """
    from builds.publicar import audio
    return audio.veredito(video) or ""


def _tiktok_confirmado(estado) -> bool:
    """O TikTok CONFIRMOU o post? Frase de "cliquei mas nao confirmou" nao conta."""
    if not estado:
        return False
    try:
        from builds.publicar import tiktok as _tk
        return bool(_tk.confirmado(estado))
    except Exception:                                          # noqa: BLE001
        # SEM O MODULO, A RESPOSTA E "NAO". A versao anterior devolvia
        # `bool(estado)`, e ai QUALQUER texto virava "publicado" — inclusive
        # "cliquei em publicar, mas o TikTok nao confirmou", que e
        # precisamente o caso em que nao se deve afirmar nada. O ledger
        # ganharia uma linha de publicacao para um post que talvez nao
        # exista, e ninguem iria conferir.
        return False


def _anotar_falha_do_tiktok(ficha: dict, falha: dict) -> None:
    """Poe na ficha POR QUE o TikTok nao saiu, quando houve excecao.

    E o que deixa a rodada (`main`) separar "a rede caiu" — vale tentar de
    novo neste horario — de "o TikTok recusou o video", que nao vale.
    """
    if falha and not _tiktok_confirmado(ficha.get("tiktok")):
        ficha["tiktok_falha"] = (f"{falha.get('tipo', '')}: "
                                 f"{falha.get('mensagem', '')}")[:300]
        if falha.get("clicou"):
            # O CLIQUE JA TINHA SAIDO: o post pode estar no ar. Repor seria
            # publicar de novo no perfil (`_derrubados_pela_rede` respeita).
            ficha["tiktok_clicou"] = True


# -------------------------------------------------- horario que a rede derrubou
# REPOR NO MESMO HORARIO o destino que a REDE derrubou (05/10/2026). O 23:37
# de 04/10 caiu inteiro (4 envios, timeout e SSLError entre 23:44 e 00:00) e
# o TikTok das 09:37 de 05/10 caiu 3 vezes, com o YouTube publicando no mesmo
# minuto: nao havia segunda tentativa, o horario ficava vazio e o video
# empurrava a fila para o seguinte. Agora, quando a falha e de rede, a rodada
# espera, confere a rede e roda o MESMO canal de novo — as guardas de
# um-por-horario por destino fazem o resto (o destino que ja saiu nao sai de
# novo; o que caiu leva o mesmo video, ou o proximo).
#
# A VOLTA FINAL (06/10/2026). Em 06/10, 06:37, a historia_00044 p06 (limpa)
# caiu nas 3 tentativas: Studio em branco 160/107/151 s, TikTok sem abrir
# 6 vezes e o envio sem chegar a 100% na 3a — das 06:37:04 as 07:05:50. Os
# builds rodaram logo depois e sairam nos dois destinos (147 s e 80 s): a
# rede tinha voltado, e o horario de historias ficou vazio porque historias
# roda PRIMEIRO e repete na hora, ainda dentro da rede ruim. Agora o canal
# que a rede derrubou ganha UMA volta no fim da rodada, depois dos canais que
# rodaram atras dele, e so se um deles publicou sem queda de rede (a prova de
# que ela voltou). A volta das 07:10 estaria a 33 min do comeco: a janela de
# 25 min a barrava, por isso a volta tem a sua, de 40. A reposicao comum
# continua com 25: ela roda sem prova de que a rede voltou.
#
# O LIMITE QUE VALE E O HORARIO SEGUINTE, nao o comeco da rodada (conferente
# do 4e8df2b, 06/10/2026). Contar so do comeco deixava uma tentativa comecar
# a poucos minutos do proximo horario — a rodada atrasada pelo Agendador
# (`StartWhenAvailable`) ou pela espera da rede comeca tarde — e uma
# tentativa medida levou 12 min (06:53:54 -> 07:05:50); o conferente mostrou
# que ela pode passar de 30. Entao NENHUMA tentativa (reposicao ou volta)
# comeca a menos de `MARGEM_ANTES_DO_PROXIMO_MIN` do proximo horario
# (`grade.proximo_em`), e isso e conferido de novo depois de cada espera,
# logo antes de publicar. A margem diminui o encontro de duas rodadas, mas
# nao o impede (uma tentativa pode durar mais que ela): quem impede e a
# trava da rodada (`TRAVA_DA_RODADA`, em `main`).
TENTATIVAS_POR_REDE = 2              # tentativas EXTRAS, por canal
PAUSA_ANTES_DE_REPOR_S = 60.0
JANELA_DE_REPOSICAO_MIN = 25         # reposicao comum, do comeco da rodada
JANELA_DA_VOLTA_FINAL_MIN = 40       # volta final (com prova de rede boa)
MARGEM_ANTES_DO_PROXIMO_MIN = 20     # nada comeca mais perto que isto
ESPERA_DE_REDE_NA_REPOSICAO_S = 120.0
# O que diz "foi a rede" — e so isso: login vencido, perfil ocupado ou video
# recusado nao melhoram tentando de novo daqui a um minuto.
MARCAS_DE_REDE = ("infraestrutura", "net::err", "err_name_not_resolved",
                  "err_connection", "err_internet", "err_timed_out",
                  "sslerror", "ssleoferror", "ssl:", "connectionreset",
                  "connection reset", "connectionerror", "timed out",
                  "remotedisconnected", "rede nao voltou")


def _e_de_rede(texto) -> bool:
    baixo = str(texto or "").lower()
    return any(m in baixo for m in MARCAS_DE_REDE)


def _derrubados_pela_rede(r: dict) -> list:
    """Os destinos que a REDE derrubou nesta ficha: [] | ["youtube", "tiktok"].

    Ficha inteira que nao saiu por excecao de rede (o canal levantou antes de
    publicar) conta como os dois.
    """
    if (not r or r.get("repetido") or r.get("veria")
            or r.get("ledger_ilegivel")):
        return []
    caidos = []
    # Pedaco da parte ja no YouTube (`ParteMeioNoAr`): o YouTube desta ficha
    # nunca e "da rede", diga a frase o que disser.
    # Clique ja dado no YouTube (`youtube_clicou`): o video pode estar no ar,
    # e repor seria subir de novo — nunca e "da rede", diga a frase o que
    # disser (a mesma regra do `tiktok_clicou`).
    if (r.get("youtube_falhou") and not r.get("youtube_meio_no_ar")
            and not r.get("youtube_clicou")
            and _e_de_rede(r.get("motivo"))):
        caidos.append("youtube")
    if (not r.get("tiktok_fora_da_grade") and not r.get("tiktok_clicou")
            and not _tiktok_confirmado(r.get("tiktok"))
            and _e_de_rede(r.get("tiktok_falha"))):
        caidos.append("tiktok")
    if (not caidos and not r.get("feito") and not r.get("youtube_falhou")
            and _e_de_rede(r.get("motivo"))):
        caidos = ["youtube", "tiktok"]
    return caidos


def _ainda_no_horario(comeco: float, slot: int, agora=None,
                      relogio=None, janela_min=None) -> bool:
    """Uma tentativa (reposicao ou volta final) ainda pode COMECAR agora?

    Tres condicoes, todas: dentro de `janela_min` do comeco da rodada
    (`JANELA_DE_REPOSICAO_MIN` por padrao; a volta passa
    `JANELA_DA_VOLTA_FINAL_MIN`), no mesmo `grade.slot`, e a pelo menos
    `MARGEM_ANTES_DO_PROXIMO_MIN` do proximo horario (`grade.proximo_em`).
    A ultima e a que segura os horarios de 60 min (20:37 ... 00:37) e a
    rodada que comecou atrasada.
    """
    import time
    from datetime import datetime, timedelta
    relogio = relogio or time.monotonic
    janela = JANELA_DE_REPOSICAO_MIN if janela_min is None else janela_min
    if relogio() - comeco >= janela * 60:
        return False
    agora = agora or datetime.now()
    if grade.slot(agora) != slot:
        return False
    falta = grade.proximo_em(agora) - agora
    return falta >= timedelta(minutes=MARGEM_ANTES_DO_PROXIMO_MIN)


def _cabe_antes_do_proximo(passo: str = "", agora=None) -> bool:
    """Um passo EXTRA (recuperacao, reserva) ainda pode comecar agora?

    So a margem do horario seguinte, sem janela: e ela que limita a duracao
    da rodada saudavel, e o `RODADA_PENDURADA_MIN` conta com isso (06/10).
    """
    from datetime import datetime, timedelta
    agora = agora or datetime.now()
    falta = grade.proximo_em(agora) - agora
    if falta >= timedelta(minutes=MARGEM_ANTES_DO_PROXIMO_MIN):
        return True
    if passo:
        _linha(f"[postar] {passo} fica para a proxima rodada: faltam "
               f"{falta.total_seconds() / 60:.0f} min para o horario "
               "seguinte.")
    return False


def _juntar_reposicao(r: dict, nova: dict) -> tuple:
    """(ficha da rodada, ficha extra ou None) depois de uma reposicao.

    - so faltava o TikTok e ele foi de novo: a mesma ficha, com o TikTok novo;
    - so faltava o YouTube e ele subiu a MESMA parte (a divida de 06/10/2026:
      o TikTok tinha levado a parte e o YouTube caiu): a mesma ficha, com o
      YouTube novo;
    - nada a repor (o horario ja tem os dois): a ficha de antes;
    - um video DIFERENTE saiu (o YouTube caiu e o TikTok tinha ido): as duas.
    """
    if not nova or nova.get("repetido"):
        return r, None
    if nova.get("so_tiktok") and nova.get("alvo") == r.get("alvo"):
        junta = dict(r)
        junta["tiktok"] = nova.get("tiktok", "")
        for chave in ("tiktok_falha", "tiktok_clicou", "tiktok_alvo",
                      "tiktok_titulo", "tiktok_parte", "tiktok_retido"):
            junta.pop(chave, None)
            if nova.get(chave):
                junta[chave] = nova[chave]
        if _tiktok_confirmado(junta["tiktok"]):
            junta["feito"] = True
        junta["reposto"] = True
        return junta, None
    if nova.get("so_youtube") and nova.get("alvo") == r.get("alvo"):
        junta = dict(r)
        junta["url"] = nova.get("url", "")
        for chave in ("youtube_falhou", "motivo", "cota_youtube",
                      "youtube_meio_no_ar", "youtube_erro",
                      "youtube_ids_no_ar", "youtube_devido"):
            junta.pop(chave, None)
            if nova.get(chave):
                junta[chave] = nova[chave]
        if junta["url"]:
            junta["feito"] = True
        junta["reposto"] = True
        return junta, None
    if not r.get("feito"):
        return dict(nova, reposto=True), None
    if nova.get("feito") and nova.get("alvo") != r.get("alvo"):
        return r, dict(nova, reposto=True)
    return r, None


def _dormir(segundos: float) -> None:
    import time
    time.sleep(segundos)


def _rodar_canal(canal: str, funcao, so_ver: bool) -> dict:
    """Uma passada de um canal. Nunca levanta: a excecao vira ficha."""
    try:
        return funcao(so_ver=so_ver)
    except Exception as exc:                                   # noqa: BLE001
        # A COTA AVISA NO TELEGRAM, e e AQUI que isso precisa acontecer:
        # o escoamento (`--tudo`) e coisa de uma vez, e quem roda sozinho
        # nos oito horarios e este caminho. Ter posto o aviso so la seria
        # avisar justamente na hora em que ele ja esta olhando.
        if _e_limite_diario(exc):
            avisar_limite_diario(f"canal {canal}: {exc}")
        # `excecao` e o que o `--ver` conta para sair 1 (ver o fim de `main`).
        return {"canal": canal, "feito": False,
                "excecao": type(exc).__name__,
                "motivo": f"{type(exc).__name__}: {exc}"[:200]}


def _publicar_canal(canal: str, funcao, *, so_ver: bool,
                    comeco: float, slot: int) -> list:
    """O canal, com a reposicao do que a rede derrubou. Devolve as fichas.

    Ficha com pedaco de parte ja no YouTube (`youtube_meio_no_ar`) nunca e
    reposta, nem pelo TikTok que caiu junto: repor roda o canal INTEIRO, e o
    YouTube da parte subiria o pedaco de novo (06/10/2026).
    """
    r = _rodar_canal(canal, funcao, so_ver)
    extras: list = []
    tentativas = 0
    while (not so_ver and tentativas < TENTATIVAS_POR_REDE
           and not r.get("youtube_meio_no_ar")
           and _derrubados_pela_rede(r) and _ainda_no_horario(comeco, slot)):
        tentativas += 1
        caidos = _derrubados_pela_rede(r)
        _linha(f"[postar] {canal}: {' e '.join(caidos)} caiu por REDE; espero "
               f"{PAUSA_ANTES_DE_REPOR_S:.0f}s e tento de novo neste horario "
               f"({tentativas}/{TENTATIVAS_POR_REDE}).")
        _dormir(PAUSA_ANTES_DE_REPOR_S)
        if not _ainda_no_horario(comeco, slot):
            break
        if not esperar_a_rede(limite=ESPERA_DE_REDE_NA_REPOSICAO_S):
            break
        # De novo, LOGO ANTES de publicar: a espera da rede pode ter levado
        # 120 s e empurrado a tentativa para perto do horario seguinte.
        if not _ainda_no_horario(comeco, slot):
            break
        nova = _rodar_canal(canal, funcao, False)
        r, extra = _juntar_reposicao(r, nova)
        if extra:
            # O destino que caiu ganhou OUTRO video neste horario: reposto.
            extras.append(extra)
            break
        if nova.get("repetido"):
            break             # o horario ja tem os dois destinos
        if nova.get("youtube_meio_no_ar"):
            # A REPOSICAO deixou pedaco no ar (o erro ja foi ao diario, com a
            # marca). Sem isto, com a ficha de antes "feita" e ainda
            # derrubada, a volta seguinte rodava o canal de novo.
            break
    return [r] + extras


ORDEM_DO_RELATORIO = ("historias", "builds")


def _ordem_dos_canais(agora=None) -> tuple:
    """Em que ordem a rodada RODA os canais. Os duelos primeiro no horario
    deles (21/10/2026); fora dele, historias e builds como sempre.

    Por que: o plano e o canal de duelos (`docs/PLANO.md`), e os dois canais
    rodam no mesmo processo, um depois do outro. Desde que o `youtube_web`
    segura o navegador ate o arquivo inteiro (decisao
    `esperar-envio-terminar`), as historias passaram a esperar o envio e o
    processamento (de 2 s a 3 min de "tempo restante" lidos no clique, mais o
    teto da qualidade) — e o duelo das 09:37, 17:57 e 21:37 saia depois. Em
    21/10, 09:37, o duelo ja so era entregue as 09:41:17.

    "E o horario dos builds?" tem UMA resposta: `_fora_da_grade_do_canal`
    (a unica leitura de relogio da grade do canal), em qualquer dos dois
    destinos. Fora dele os builds so devolvem `fora_da_grade`, e a ordem de
    sempre fica.

    O QUE MUDA ALEM DA ORDEM, e so isto: a volta final (`_volta_final`) exige
    um canal que rodou DEPOIS; nos horarios dos builds ela passa das
    historias para os builds. Medido no `postar.txt` inteiro em 21/10: 0
    voltas finais disparadas. As fichas saem na ordem do relatorio
    (`ORDEM_DO_RELATORIO`) — Telegram, `[POSTADO]` e codigo de saida iguais;
    recuperacao, reserva e recuperacao do YouTube rodam depois, como antes.
    """
    duelos = ("builds", "historias")
    for plataforma in ("youtube", "tiktok"):
        if not _fora_da_grade_do_canal("builds", plataforma, agora):
            return duelos
    return ORDEM_DO_RELATORIO


def _publicou_sem_queda(ficha: dict) -> bool:
    """A ficha prova que a rede voltou: publicou e nada caiu por rede."""
    return bool(ficha.get("feito")) and not _derrubados_pela_rede(ficha)


def _volta_final(rodados: list, *, so_ver: bool, comeco: float,
                 slot: int) -> list:
    """As fichas da rodada, com UMA volta final do canal que a rede derrubou.

    `rodados`: `[(canal, funcao, fichas)]` na ordem em que rodaram. Um canal
    volta se, depois das reposicoes de `_publicar_canal`, a ficha dele ainda
    tem destino derrubado pela rede E algum canal que rodou DEPOIS dele
    publicou sem queda — a prova de que a rede voltou. "Sem queda" e nos DOIS
    destinos: builds com o YouTube no ar e o TikTok derrubado pela rede nao
    prova nada. Sem essa prova (os dois cairam, ou o canal e o ultimo), nao
    ha volta: seria so mais uma tentativa na mesma rede ruim. Mesmo
    `grade.slot`, janela propria (`JANELA_DA_VOLTA_FINAL_MIN`) e a margem
    antes do proximo horario, conferida antes e depois da espera da rede; as
    guardas de um por horario por destino fazem o resto. Medido em 06/10,
    06:37: historias caiu 3x, builds publicou as 07:05-07:10, a volta teria
    comecado aos 33 min.

    Nunca volta: no `--ver`, com pedaco de parte ja no YouTube
    (`youtube_meio_no_ar`) nem quando a reposicao ja levou OUTRO video ao
    horario (mais de uma ficha do canal).
    """
    saida = []
    for i, (canal, funcao, fichas) in enumerate(rodados):
        fichas = list(fichas)
        depois = [f for _c, _f, outras in rodados[i + 1:] for f in outras]
        r = fichas[0] if fichas else {}
        if (not so_ver and len(fichas) == 1
                and not r.get("youtube_meio_no_ar")
                and _derrubados_pela_rede(r)
                and any(_publicou_sem_queda(f) for f in depois)
                and _ainda_no_horario(comeco, slot,
                                      janela_min=JANELA_DA_VOLTA_FINAL_MIN)
                and esperar_a_rede(limite=ESPERA_DE_REDE_NA_REPOSICAO_S)
                and _ainda_no_horario(comeco, slot,
                                      janela_min=JANELA_DA_VOLTA_FINAL_MIN)):
            caidos = _derrubados_pela_rede(r)
            _linha(f"[postar] {canal}: {' e '.join(caidos)} tinha caido por "
                   "REDE e o canal seguinte publicou; volta final neste "
                   "horario.")
            nova = _rodar_canal(canal, funcao, False)
            r, extra = _juntar_reposicao(r, nova)
            fichas = [r] + ([extra] if extra else [])
        saida.extend(fichas)
    return saida


def _builds_prontos(config=None, *, medir_audio: bool = True,
                    avisar: bool = False) -> list:
    """Os builds que a escolha PODE levar, do mais novo para o mais velho.

    O funil de `proximo_build` sem a escolha — e o motivo de existir e a
    escolha e os contadores responderem a MESMA pergunta. Medido em
    27/09/2026: o aviso do Telegram dizia "build 7d" porque
    `estoque_por_formato` contava `catalogo - publicados` (28 builds: 25
    variantes B com titulo ja no ar e 3 com pendencia; 28 / 3,75 por dia = 7),
    enquanto `proximo_build` nao tinha NENHUM build para levar. Era o defeito
    que `pendentes_por_canal` teve em 16/09, de volta porque o segundo
    contador tinha filtro proprio.

    Os crivos, do mais barato ao mais caro: ja publicado (qualquer destino),
    perfil celular, pendencia, titulo ja no ar e — com `medir_audio` — video
    mudo. O audio fica POR ULTIMO porque decodifica o mp4 (0,3 a 0,65 s por
    video, medido): so e medido quem passou pelos outros. A escolha passa
    `medir_audio=False` e mede so o escolhido.

    Os crivos de MOMENTO — a lista "a conferir" e o teto de 2 por geracao no
    dia — ficam de fora: sao sobre hoje, e o estoque e sobre os proximos dias.
    """
    from builds.publicar import catalogo as C
    from builds.publicar import metricas

    # Qualquer plataforma conta (ver `fila_de_historias`): contando so o
    # YouTube, a cota repetia o mesmo video em todo horario e o TikTok ficava
    # vazio.
    linhas = metricas.publicados()
    ja = {l.get("video_id") for l in linhas if _saiu(l)}
    # O APAGADO DO CANAL NUNCA VOLTA A FILA (21/10/2026, decisao
    # `videos-presos-no-canal`: "apagar e nao reenviar"). A linha apagada tem
    # `publicado: false`, e sem isto o build so com ela voltaria como novo.
    ja |= metricas.apagados(linhas, None)
    pendentes = [v for v in C.listar()
                 if v.id not in ja and getattr(v, "perfil", "") == "celular"]
    if not pendentes:
        return []

    # BUILD COM PENDENCIA NAO ENTRA NA FILA. O catalogo ja calcula isto
    # (`pendencias_da_build`: sem payoff, sem imagem do personagem, sem a luta
    # no fim, render defasado) e o painel ja mostra — o publicador era o unico
    # que nao olhava. Medido em 11/09/2026: 23 dos 66 pendentes tinham
    # pendencia e podiam sair a qualquer horario. E o mesmo criterio que
    # `proxima_historia` aplica ao pular o que a vistoria reprova.
    prontos = [v for v in pendentes if not getattr(v, "pendencias", None)]
    barrados = [v for v in pendentes if getattr(v, "pendencias", None)]
    if barrados and avisar:
        # SEPARA O QUE ESPERA DO QUE ACABOU. Em 16/09/2026 este resumo dizia
        # "22 build(s) fora da fila por pendencia" havia semanas, e 20 delas
        # eram irrecuperaveis (personagem fora do banco). Um numero que nao
        # anda parece fila; dito assim, e o que e: estoque morto, e a unica
        # pergunta aberta e se vale reinserir os personagens.
        perdidos = [v for v in barrados
                    if any("impossivel" in p for p in v.pendencias)]
        esperando = [v for v in barrados if v not in perdidos]
        if esperando:
            _linha(f"[postar] {len(esperando)} build(s) fora da fila por "
                   f"pendencia: {', '.join(v.id for v in esperando[:4])}"
                   f"{'...' if len(esperando) > 4 else ''}")
        if perdidos:
            _linha(f"[postar] {len(perdidos)} build(s) IRRECUPERAVEIS "
                   f"(estreia impossivel): {perdidos[0].pendencias[0]}")
    if not prontos:
        return []

    # TITULO JA NO AR NAO VOLTA. Medido em 16/09/2026 contra o ledger: das
    # 63 chaves de titulo publicadas no canal, 21 sairam DUAS vezes. A causa
    # e a variante "gancho B", que tem id com sufixo `:B` e o mesmo titulo —
    # para a deduplicacao por `video_id` sao dois videos, para o YouTube sao
    # dois iguais, competindo pelo mesmo termo de busca.
    novos, repetidos = _sem_titulo_repetido(prontos, "builds", config)
    if repetidos and avisar:
        _linha(f"[postar] {len(repetidos)} build(s) fora da fila por titulo "
               f"ja publicado: {', '.join(v.id for v in repetidos[:4])}"
               f"{'...' if len(repetidos) > 4 else ''}")
    if not novos:
        if repetidos and avisar:
            # A VALVULA FECHOU EM 17/09/2026. Ela liberava "o menos pior" com
            # a fila inteira repetida — e o menos pior era republicar um
            # titulo que ja estava no ar. Foi assim que as variantes A e B de
            # cinco geracoes (00067, 00069, 00071, 00081, 00082) sairam as
            # duas, nos dois destinos, com titulo identico. O Adrian viu.
            #
            # Repetir e pior que nao postar. Aqui ha uma saida melhor que o
            # horario em branco, e ela ja existe: a RESERVA leva um build
            # antigo ao TikTok quando a fila normal nao tem nada. O YouTube
            # fica sem, e fica sem de proposito.
            _linha("[postar] builds: TODOS os pendentes tem titulo ja "
                   "publicado; o horario fica SEM post (a valvula fechou).")
        return []

    if medir_audio:
        novos = [v for v in novos if not _audio_mudo(v)]
    return novos


# ------------------------------------------------- confrontos diferentes
# "SO CONFRONTOS DIFERENTES" (`docs/PLANO.md`, semana 1, 20/10/2026): o mesmo
# confronto — o par de CLASSE (e do tipo da arma, quando a ficha o tiver) dos
# dois lutadores, sem ordem — nao sai duas vezes no mesmo destino na mesma
# semana, se houver duelo de outro confronto; e nunca no mesmo dia de grade
# se houver qualquer outro video. O titulo "A x B" ja impede o MESMO par de
# lutadores; isto impede "Paladino x Ninja" tres vezes na semana com nomes
# diferentes — que e o que o espectador ve como repetido.
#
# A ficha da luta (`outputs/<duelo>/fight.json`, `luta.p1_ficha`) tem a
# `classe` e o NOME proprio da arma ("Morvostilar"), nao o tipo — medido em
# 20/10 nos 139 duelos: 79 pares de classe distintos. O tipo entra na chave
# quando a ficha trouxer `tipo_arma`/`estilo_arma`.
DIAS_DO_CONFRONTO = 7
_CHAVES_DA_ARMA = ("tipo_arma", "estilo_arma", "arma_tipo", "arma_estilo")
_CONFRONTOS: dict = {}


def _lado_do_confronto(ficha: dict) -> str:
    classe = str((ficha or {}).get("classe") or "").strip()
    if not classe:
        return ""
    arma = next((str(ficha[k]).strip() for k in _CHAVES_DA_ARMA
                 if str((ficha or {}).get(k) or "").strip()), "")
    return f"{classe}/{arma}" if arma else classe


def confronto_da_fonte(fonte_id: str, pasta=None) -> str:
    """`"Mago (Arcano) x Paladino (Sagrado)"` — o confronto do duelo
    `fonte_id`, sem ordem; "" quando nao e duelo ou a ficha nao diz (e "nao
    sei" nunca barra). Lembrado por processo (a ficha nao muda)."""
    fonte = str(fonte_id or "")
    if not fonte.startswith("duelo_"):
        return ""
    if fonte in _CONFRONTOS and pasta is None:
        return _CONFRONTOS[fonte]
    chave = ""
    try:
        if pasta is None:
            from builds.publicar import catalogo as C
            pasta = C.OUTPUTS / fonte
        dados = json.loads((Path(pasta) / "fight.json")
                           .read_text(encoding="utf-8-sig"))
        luta = dados.get("luta") or {}
        lados = [_lado_do_confronto(luta.get("p1_ficha") or {}),
                 _lado_do_confronto(luta.get("p2_ficha") or {})]
        if all(lados):
            chave = " x ".join(sorted(lados))
    except (OSError, ValueError, TypeError, AttributeError):
        chave = ""
    _CONFRONTOS[fonte] = chave
    return chave


def _confronto_do_video(video) -> str:
    if str(getattr(video, "origem", "")) != "duelo":
        return ""
    caminho = getattr(video, "caminho", None)
    pasta = Path(caminho).parent if caminho else None
    return confronto_da_fonte(getattr(video, "fonte_id", "") or
                              str(getattr(video, "id", "")).split(":")[0],
                              pasta)


def confrontos_no_ar(publicados: list, plataforma: str, agora=None,
                     dias: int = DIAS_DO_CONFRONTO) -> tuple:
    """`(da semana, de hoje)`: os confrontos que AQUELE destino publicou nos
    ultimos `dias` dias e no dia de grade de agora. Linha sem data nao conta
    (como no teto por fonte)."""
    from datetime import datetime, timedelta
    agora = agora or datetime.now()
    hoje = conferencia_chave(agora.isoformat(timespec="seconds"),
                             plataforma)
    desde = (agora - timedelta(days=dias)).isoformat(timespec="seconds")
    semana, dia = set(), set()
    for linha in publicados or ():
        if (str(linha.get("plataforma") or "youtube").lower() != plataforma
                or not _saiu(linha) or str(linha.get("origem")) != "duelo"):
            continue
        quando = str(linha.get("quando") or "")
        if not quando or quando < desde:
            continue
        chave = confronto_da_fonte(linha.get("fonte_id")
                                   or str(linha.get("video_id") or "")
                                   .split(":")[0])
        if not chave:
            continue
        semana.add(chave)
        if hoje is not None and conferencia_chave(quando, plataforma) == hoje:
            dia.add(chave)
    return semana, dia


def conferencia_chave(quando, plataforma: str):
    """O dia de grade de `quando` (`conferencia.chave_do_horario`), ou None."""
    from builds.publicar import conferencia
    chave = conferencia.chave_do_horario(quando, plataforma)
    return chave[0] if chave else None


def com_confrontos_diferentes(pendentes: list, semana: set, dia: set) -> list:
    """Pura. Os candidatos sem o confronto repetido, em camadas:

    1. duelos de confronto que nao saiu na semana (com os nao-duelos);
    2. senao, duelos de confronto que nao saiu HOJE (com os nao-duelos);
    3. senao, so os nao-duelos — repetir o confronto no mesmo dia so quando
       nao ha outro video nenhum;
    4. e, sem nao-duelo, a lista inteira.

    Duelo sem confronto conhecido ("nao sei") conta como diferente. A ordem
    de `pendentes` se mantem (a escolha por cota vem depois).
    """
    outros = [v for v in pendentes if str(getattr(v, "origem", "")) != "duelo"]
    duelos = [v for v in pendentes if str(getattr(v, "origem", "")) == "duelo"]
    if not duelos:
        return list(pendentes)
    chaves = {id(v): _confronto_do_video(v) for v in duelos}
    for proibidos in (semana, dia):
        livres = {id(v) for v in duelos
                  if not chaves[id(v)] or chaves[id(v)] not in proibidos}
        if livres:
            return [v for v in pendentes
                    if str(getattr(v, "origem", "")) != "duelo"
                    or id(v) in livres]
    return outros or list(pendentes)


def _sem_confronto_repetido(pendentes: list, plataforma: str) -> list:
    """`com_confrontos_diferentes` contra o ledger daquele destino. Ledger
    ilegivel: a lista como veio ("nao sei" nao barra; a guarda que impede
    REPETIR o video e a de titulo e a de publicado, nao esta)."""
    from builds.publicar import metricas
    try:
        semana, dia = confrontos_no_ar(metricas.publicados(), plataforma)
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[postar] confrontos: nao li o ledger ({type(exc).__name__}); "
               "a fila segue sem essa guarda.")
        return list(pendentes)
    saida = com_confrontos_diferentes(pendentes, semana, dia)
    tirados = len(pendentes) - len(saida)
    if tirados:
        _linha(f"[postar] confrontos ({plataforma}): {tirados} video(s) "
               f"esperam — confronto ja no ar nesta semana ou hoje.")
    return saida


def proximo_build(config=None, *, marcar: bool = False):
    """O proximo video de builds PARA O YOUTUBE, alternando entre os FORMATOS.

    Desde 19/10/2026 esta e a fila do YouTube: a mistura e a dele (a estreia
    trocada pelo duelo, `TROCAS_NA_COTA`) e o teto por geracao e o dele. O
    TikTok escolhe pela fila e pela mistura proprias (`_vez_do_tiktok_builds`).

    `marcar` e so da rodada de VERDADE (`postar_build`): ela poe o video mudo
    na lista "a conferir" do YouTube, com o motivo, e solta a marca de audio
    de quem voltou a ter som. `--ver` e o painel perguntam sem mexer em nada.

    Ate 11/09/2026 isto era FIFO cego: `C.listar()` devolve build, estreia,
    duelo e torneio no mesmo indice, e a unica regra era "o mais antigo que
    ainda nao saiu". Com 8 disparos por dia e um backlog desequilibrado, uma
    semana inteira podia sair de um formato so — e ai a comparacao que a
    Onda 15 existe para fazer simplesmente nao acontece.

    Agora e round-robin PONDERADO: entre os formatos com pendente, vence o
    que estiver mais atrasado em relacao a propria cota (`servidos / cota`).
    Empate desempata pelo mais antigo, que era a regra de sempre. Formato
    sem cota, ou sem pendente, nao trava a grade: os slots dele vao para
    quem tem.

    Os crivos de CONTEUDO (publicado, pendencia, titulo no ar) moram em
    `_builds_prontos`, que os contadores de estoque tambem usam; aqui ficam
    os de MOMENTO (a conferir, teto do dia) e a escolha.
    """
    from builds.publicar import audio

    pendentes = _builds_prontos(config, medir_audio=False, avisar=True)
    if not pendentes:
        return None

    # A MARCA DE AUDIO SAI SOZINHA, e ANTES de a lista tirar os marcados da
    # fila: o re-render muda o arquivo, a medida e refeita, e o video que
    # voltou a ter som volta a concorrer nesta mesma rodada. So a marca que
    # comeca com `[audio] ` — a de clique sem confirmacao nunca sai por aqui.
    if marcar:
        audio.revisar_marcas("builds", pendentes)

    # A mesma guarda das historias: quem subiu ao YouTube sem confirmacao
    # espera conferencia, senao a rodada seguinte reenvia e gera outro
    # rascunho.
    pendentes = _sem_a_conferir(pendentes, "builds")
    if not pendentes:
        return None

    # O mesmo teto das historias, por geracao: 2 por dia NO PERFIL do
    # YouTube — esta e a fila do YouTube; o TikTok tem a dele, com o teto
    # dele (`_vez_do_tiktok_builds`, 19/10/2026).
    pendentes = _sem_fonte_cheia(pendentes, "builds",
                                 plataformas=("youtube",))
    if not pendentes:
        return None
    # SO CONFRONTOS DIFERENTES (PLANO, semana 1): o confronto que o YouTube
    # ja levou nesta semana espera, se houver outro.
    pendentes = _sem_confronto_repetido(pendentes, "youtube")

    # o mais ANTIGO primeiro: o catalogo vem do mais novo para o mais velho
    pendentes.reverse()
    # A MISTURA E A DO YOUTUBE (sem estreia, `TROCAS_NA_COTA`), contada no que
    # o YOUTUBE serviu.
    servidos = _servidos_recentes(plataforma="youtube")
    cota = cota_da_plataforma(cota_da_grade(config), "youtube")
    # VIDEO MUDO NAO SAI (auditoria de 15/09/2026): a estreia da
    # generation_00065 media -91 dB e estava marcada para as 10:07, nas duas
    # plataformas. Desde 28/09 a LUTA muda debaixo da musica tambem nao (38 de
    # 129 publicacoes desde 15/09). A medida e lembrada por arquivo, entao o
    # escolhido de cada horario so decodifica o que mudou desde a ultima vez.
    while pendentes:
        alvo = escolher_por_cota(pendentes, servidos, cota)
        motivo = _audio_mudo(alvo)
        if not motivo:
            return alvo
        _linha(f"[postar] {alvo.id} fora da fila: {motivo}")
        if marcar:
            # O MOTIVO VAI PARA A LISTA "A CONFERIR", que o app e o bot
            # mostram: la o Adrian ve o que esta parado e por que. Marca do
            # YouTube, porque e a lista que esta fila le; a marca sai sozinha
            # (`audio.revisar_marcas`, acima) quando o som voltar.
            audio.marcar("builds", alvo.id, motivo, "youtube")
        pendentes = [v for v in pendentes if v.id != alvo.id]
    return None


# --------------------------------------------- build que so saiu no TikTok
# A DIVIDA DO YOUTUBE DOS BUILDS (decisao do Adrian `publicacao/build-so-no-
# tiktok`, 13/10/2026: "mesma regra das historias" — "o YouTube sobe o build
# devido no proximo horario, junto com o novo, ate zerar"). Quando o YouTube
# dos builds caia e o TikTok confirmava, a reposicao subia OUTRO build no
# YouTube (`_builds_prontos` conta qualquer destino como publicado), e o
# primeiro ficava so no TikTok para sempre: fora da fila, da recuperacao (que
# so trata privados) e da reserva. Agora ele e divida: o YouTube do horario
# sobe ELE, o TikTok leva `proximo_build()`, e o YouTube sobe tambem o build
# novo do TikTok (`_alcance_do_youtube_dos_builds`, como `_alcance_do_youtube`
# das historias, decisao `youtube-atras-do-tiktok`).
#
# SO DESTA DATA EM DIANTE (a da decisao). Medido no ledger em 14/10/2026,
# 02:22: 3 builds so no TikTok, nenhum desde 13/10 — o mais novo e o
# `duelo_00076:duelo:celular` (12/10 16:31); os outros dois sao de antes de
# 10/09 (`CORTE_DO_TIKTOK`, gordura). Decisao `publicacao/duelo-00076-ao-
# youtube` (14/10/2026): levar o de 12/10 tambem — o corte passou para
# 12/10. Medido no ledger em 14/10 08:5x: corte 13/10 = 0 devidos; corte
# 12/10 = 1 (o duelo_00076, 12/10 16:31:22).
CORTE_DA_DIVIDA_DOS_BUILDS = "2026-10-12"


def _divida_do_youtube_dos_builds() -> tuple:
    """(build que o YouTube deve, quando ele saiu no TikTok, motivos).

    Sem divida: `(None, "", motivos)`, com o motivo de cada build devido que
    nao pode sair agora. Nunca levanta: sem a resposta, o YouTube segue com a
    fila normal (o orfao de antes, e nao o horario vazio).

    Divida e o build com linha PUBLICADA (`_saiu`) no TikTok a partir de
    `CORTE_DA_DIVIDA_DOS_BUILDS` e nenhuma no YouTube; o mais antigo primeiro.
    Os crivos sao os da fila (`_builds_prontos` e `proximo_build`), menos o
    "ja publicado em qualquer destino": o mp4 ainda no catalogo, sem
    pendencia, titulo fora do ar no YouTube, fora da lista "a conferir" do
    YouTube, teto da geracao no YouTube e audio que nao e mudo.
    """
    try:
        return _procurar_divida_dos_builds()
    except Exception as exc:                                   # noqa: BLE001
        return None, "", [f"nao consegui procurar a divida do YouTube dos "
                          f"builds ({type(exc).__name__}: {exc})"[:160]]


def _procurar_divida_dos_builds() -> tuple:
    from builds.publicar import catalogo as C
    from builds.publicar import metricas

    publicados = metricas.publicados()
    no_youtube = {str(l.get("video_id") or "") for l in publicados
                  if str(l.get("plataforma") or "youtube").lower() == "youtube"
                  and _saiu(l)}
    # O APAGADO DO CANAL NAO E DIVIDA (21/10/2026, `videos-presos-no-canal`:
    # "apagar e nao reenviar"). Os 5 apagados de 21/10 estao no TikTok e sem
    # YouTube publicado: so a troca de build/estreia por duelo na cota os
    # segurava fora daqui.
    apagados = metricas.apagados(publicados, "youtube")
    devidas: dict = {}
    for l in publicados:
        quando = str(l.get("quando") or "")
        vid = str(l.get("video_id") or "")
        if (l.get("plataforma") != "tiktok" or not _saiu(l)
                or quando < CORTE_DA_DIVIDA_DOS_BUILDS
                or not vid or vid in no_youtube or vid in apagados):
            continue
        # A ESTREIA NAO E DIVIDA (19/10/2026, `duelo-no-lugar-da-estreia`):
        # o YouTube de builds trocou a estreia pelo duelo, e a do TikTok fica
        # so la. Sem isto a divida levaria ao YouTube toda estreia que o
        # TikTok postou, e a troca nao aconteceria.
        if _trocado_no_youtube(l.get("origem") or vid):
            continue
        if vid not in devidas or quando < devidas[vid]:
            devidas[vid] = quando
    if not devidas:
        return None, "", []

    motivos: list = []
    no_catalogo = {v.id: v for v in C.listar()}
    try:
        cheias = _fontes_cheias_hoje(publicados, "youtube")
    except Exception:                                          # noqa: BLE001
        cheias = set()                 # "nao sei" nao barra (ver a tabela)
    for vid, quando in sorted(devidas.items(), key=lambda d: (d[1], d[0])):
        v = no_catalogo.get(vid)
        if v is None:
            motivo = "o mp4 nao esta mais no catalogo"
        elif getattr(v, "pendencias", None):
            motivo = "pendencia: " + "; ".join(v.pendencias)[:100]
        elif titulo_repetido(v, "builds", "youtube"):
            motivo = "o titulo ja esta no ar no YouTube (ledger)"
        elif not _sem_a_conferir([v], "builds"):
            motivo = "esta na lista 'a conferir' do YouTube"
        elif str(v.id).split(":")[0] in cheias:
            motivo = (f"a geracao ja saiu {TETO_POR_FONTE_NO_DIA}x hoje no "
                      "YouTube")
        else:
            motivo = _audio_mudo(v)
        if not motivo:
            return v, quando, motivos
        motivos.append(f"{vid}: {motivo}")
    return None, "", motivos


def _alcance_do_youtube_dos_builds(ficha: dict, alvo) -> None:
    """Sobe ao YouTube tambem o build novo que o TikTok levou no horario com
    divida — "junto com o novo, ate zerar" (decisao `build-so-no-tiktok`)."""
    from builds.publicar import metricas

    if _trocado_no_youtube(getattr(alvo, "origem", "") or alvo.id):
        # A estreia que o TikTok levou nao vai ao YouTube (`TROCAS_NA_COTA`).
        ficha["youtube_alcance"] = {"pulado": "o YouTube de builds nao leva "
                                              "estreia (19/10/2026)"}
        return
    if not _cabe_antes_do_proximo("a segunda subida do YouTube dos builds"):
        ficha["youtube_alcance"] = {"pulado": "sem tempo antes do horario "
                                              "seguinte"}
        return
    try:
        no_ar = any(str(l.get("video_id") or "") == alvo.id and _saiu(l)
                    and str(l.get("plataforma") or "youtube") == "youtube"
                    for l in metricas.publicados())
    except Exception:                                          # noqa: BLE001
        no_ar = True                   # sem ledger, nao arrisca duplicar
    if no_ar:
        _linha(f"[postar] builds: alcance do YouTube nao repete {alvo.id}.")
        return
    if not _sem_a_conferir([alvo], "builds"):
        return
    if not _sem_fonte_cheia([alvo], "builds"):
        ficha["youtube_alcance"] = {"pulado": "teto por geracao"}
        return
    alcance = {"alvo": alvo.id, "titulo": alvo.titulo, "url": ""}
    ficha["youtube_alcance"] = alcance
    laudo: dict = {}
    try:
        alcance["url"] = _youtube_dos_builds(alvo, laudo)
    except Exception as exc:                                   # noqa: BLE001
        alcance["falhou"] = f"{type(exc).__name__}: {exc}"[:200]
        if laudo.get("clicou"):
            alcance["clicou"] = True
            _garantir_marca("builds", alvo.id, "youtube",
                            f"cliquei em publicar no YouTube e algo falhou "
                            f"depois ({alcance['falhou'][:120]}): o video pode "
                            f"estar no ar — confira no Studio.",
                            etapa="publicar.youtube.clique")
        _linha(f"[postar] builds: segunda subida do YouTube falhou "
               f"({alcance['falhou']}); {alvo.id} continua devendo o "
               "YouTube.")


def _so_o_tiktok_dos_builds(so_ver: bool, ja_tk, tiktok_agora: bool,
                            fora_yt: str) -> dict:
    """O horario e do TikTok dos builds e nao do YouTube deles: so a vez do
    TikTok (a fila propria dele), sem nada no YouTube."""
    if ja_tk or not tiktok_agora:
        return {"canal": "builds", "feito": False, "fora_da_grade": True,
                "motivo": fora_yt}
    tk_alvo, sem_vez = _vez_do_tiktok_builds()
    if tk_alvo is None:
        return {"canal": "builds", "feito": False,
                "motivo": f"{fora_yt}; TikTok: {sem_vez}"[:300]}
    if so_ver:
        return {"canal": "builds", "feito": False, "veria": tk_alvo.id,
                "titulo": tk_alvo.titulo, "motivo": "so vendo",
                "veria_tiktok": tk_alvo.id}
    falha_tk: dict = {}
    ficha = {"canal": "builds", "feito": False, "alvo": tk_alvo.id,
             "titulo": tk_alvo.titulo, "url": "", "so_tiktok": True,
             "youtube_fora_da_grade": True,
             "tiktok": _tiktok_dos_builds(tk_alvo, falha_tk)}
    _anotar_falha_do_tiktok(ficha, falha_tk)
    ficha["feito"] = _tiktok_confirmado(ficha["tiktok"])
    return ficha


def postar_build(*, so_ver: bool = False) -> dict:
    # A GRADE DOS BUILDS ANTES DE TUDO (20/10/2026, `grade.HORAS_POR_CANAL`):
    # fora dos tres horarios do canal nao ha o que ler no ledger nem no
    # catalogo. A ficha leva `fora_da_grade`, que a rodada tira do aviso e do
    # codigo de saida: "nao era comigo" nao e falha.
    fora_yt = _fora_da_grade_do_canal("builds", "youtube")
    fora_tk = _fora_da_grade_do_canal("builds", "tiktok")
    if fora_yt and fora_tk:
        return {"canal": "builds", "feito": False, "fora_da_grade": True,
                "motivo": fora_yt}
    # Uma guarda por DESTINO, igual as historias: o YouTube ter saido nesta
    # hora nao pode cancelar o TikTok.
    ja_yt = None if so_ver else publicou_neste_horario("builds", "youtube")
    ja_tk = None if so_ver else publicou_neste_horario("builds", "tiktok")
    ilegivel = _ficha_do_ledger_ilegivel("builds", ja_yt, ja_tk)
    if ilegivel:
        return ilegivel
    tiktok_agora = _tiktok_neste_horario() and not fora_tk
    if fora_yt:
        # So o TikTok tem este horario (nao acontece com a grade de 20/10,
        # que da os mesmos tres aos dois; fica para a grade que separar).
        return _so_o_tiktok_dos_builds(so_ver, ja_tk, tiktok_agora, fora_yt)
    if ja_yt and (ja_tk or not tiktok_agora):
        return _ja_foi_neste_horario("builds", "youtube")
    if ja_yt:
        alvo = _build_por_id(ja_yt.get("video_id"))
        if alvo is None:
            return {"canal": "builds", "feito": False,
                    "motivo": f"o video {ja_yt.get('video_id')} saiu no "
                              "YouTube mas nao esta mais no catalogo"}
        # O TIKTOK LEVA A VEZ DELE (fila e mistura proprias, 19/10/2026).
        tk_alvo, sem_vez = _vez_do_tiktok_builds()
        tk_alvo = _o_mesmo(tk_alvo, alvo)
        if tk_alvo is None:
            return {"canal": "builds", "feito": False,
                    "motivo": f"o YouTube ja saiu nesta hora com {alvo.id}; "
                              f"TikTok: {sem_vez}"[:300]}
        _linha(f"[postar] builds: YouTube ja saiu nesta hora ({alvo.id}); "
               f"levando {tk_alvo.id} so para o TikTok.")
        falha_tk: dict = {}
        # `feito` SO DEPOIS de o TikTok rodar (11/10/2026): nascia `True`, e
        # um TikTok que falhava por motivo que nao e rede saia `[POSTADO]`,
        # codigo 0, e valia como "a rede voltou" para a volta final.
        ficha = {"canal": "builds", "feito": False, "alvo": alvo.id,
                 "titulo": alvo.titulo, "url": ja_yt.get("url") or "",
                 "so_tiktok": True,
                 "tiktok": _tiktok_dos_builds(tk_alvo, falha_tk)}
        if tk_alvo is not alvo:
            ficha.update({"tiktok_alvo": tk_alvo.id,
                          "tiktok_titulo": tk_alvo.titulo})
        _anotar_falha_do_tiktok(ficha, falha_tk)
        ficha["feito"] = _tiktok_confirmado(ficha["tiktok"])
        return ficha
    # A DIVIDA DO YOUTUBE VEM ANTES DA FILA (decisao `build-so-no-tiktok`,
    # 13/10/2026, ver `CORTE_DA_DIVIDA_DOS_BUILDS`): o build que saiu so no
    # TikTok sobe no YouTube deste horario, e o TikTok leva o proximo da fila
    # — que ja pula o devido, porque ele conta como publicado pelo TikTok.
    divida, divida_quando, motivos_da_divida = _divida_do_youtube_dos_builds()
    for motivo in motivos_da_divida[:3]:
        _linha(f"[postar] builds: divida do YouTube que nao sai agora — "
               f"{motivo}"[:200])
    if divida is not None:
        alvo = divida
        _linha(f"[postar] builds: o YouTube deve {divida.id} (saiu no TikTok "
               f"em {divida_quando[:16]}); sobe ele.")
    else:
        alvo = proximo_build(marcar=not so_ver)
        if alvo is None:
            return {"canal": "builds", "feito": False,
                    "motivo": "nao ha video pendente"}
    if so_ver:
        veria = {"canal": "builds", "feito": False, "veria": alvo.id,
                 "titulo": alvo.titulo, "motivo": "so vendo"}
        if divida is not None:
            veria["youtube_devido"] = divida_quando
        if tiktok_agora:
            tk_ver, _sem = _vez_do_tiktok_builds()
            veria["veria_tiktok"] = tk_ver.id if tk_ver else ""
        return veria
    # `publicar_como_configurado` JA REGISTRA — e a porta unica, e o registro
    # mora dentro dela justamente para nenhum chamador esquecer. Chamar
    # `registrar_publicado` aqui de novo gravava a MESMA publicacao duas
    # vezes, e a segunda linha saia sem `visibilidade` (o `extra` e montado la
    # dentro): o ledger dizia `public` numa linha e `null` na seguinte, para o
    # mesmo video. Foi assim nos dois builds de 08/09/2026.
    url, falha_yt, cota = "", None, False
    # O laudo nasce FORA do `try`, como no TikTok: a marca `clicou` escrita
    # dentro do `youtube_web.publicar` precisa sobreviver a excecao.
    laudo_yt: dict = {}
    try:
        url = _youtube_dos_builds(alvo, laudo_yt)
    except Exception as exc:                                   # noqa: BLE001
        # Mesma regra das historias (auditoria de 15/09/2026): falha do
        # YouTube — cota ou qualquer outra — nao deixa o TikTok vazio. Antes
        # a excecao subia ate `main` e `_tiktok_dos_builds` nunca rodava.
        falha_yt = f"{type(exc).__name__}: {exc}"[:200]
        cota = _e_limite_diario(exc)
        _linha(f"[postar] builds: YouTube falhou ({falha_yt}). "
               "Sigo para o TikTok.")
        if cota:
            avisar_limite_diario(f"canal builds: {exc}")
    ficha = {"canal": "builds", "feito": bool(url), "alvo": alvo.id,
             "titulo": alvo.titulo, "url": url}
    if falha_yt and laudo_yt.get("clicou"):
        # O CLIQUE JA TINHA SAIDO: o video pode estar no ar. Repor seria
        # subir de novo. O `youtube_web` ja tentou a marca "a conferir"; se
        # ela nao gravou, `_garantir_marca` tenta de novo e, no pior caso,
        # guarda o clique na memoria e na ficha da trava (PUB-1, 14/10/2026:
        # ate aqui so este horario sabia do clique, e o seguinte reescolhia).
        ficha["youtube_clicou"] = True
        _garantir_marca("builds", alvo.id, "youtube",
                        f"cliquei em publicar no YouTube e algo falhou depois "
                        f"({falha_yt[:120]}): o video pode estar no ar como "
                        f"publicado ou RASCUNHO — confira no Studio.",
                        etapa="publicar.youtube.clique")
    # A VALVULA APARECE NO RELATORIO. "Libera o menos pior com aviso" so
    # funciona se o aviso for somavel: sem esta marca, a excecao vira rotina
    # silenciosa e ninguem descobre que ela virou regra.
    if titulo_repetido(alvo, "builds"):
        ficha["titulo_repetido"] = True
    if falha_yt:
        ficha["motivo"] = (f"YouTube na cota: {falha_yt}" if cota
                           else f"YouTube falhou: {falha_yt}")[:200]
        ficha["youtube_falhou"] = True
        if cota:
            ficha["cota_youtube"] = True
    if divida is not None:
        ficha["youtube_devido"] = divida_quando
    # A VEZ DO TIKTOK, depois do YouTube (fila e mistura proprias, 19/10/2026):
    # o build que o YouTube acabou de subir entra na fila de atraso dele.
    tk_alvo = None
    if tiktok_agora and not ja_tk:
        tk_alvo, sem_vez = _vez_do_tiktok_builds()
        tk_alvo = _o_mesmo(tk_alvo, alvo)
        if tk_alvo is None:
            _linha(f"[postar] builds: TikTok sem video neste horario — "
                   f"{sem_vez}"[:200])
    if not tiktok_agora:
        # FORA DA GRADE DO TIKTOK, e nao falha: ele posta seis por dia.
        ficha["tiktok"] = ""
        ficha["tiktok_fora_da_grade"] = True
        _linha("[postar] builds: este horario nao e da grade do TikTok.")
    elif ja_tk:
        # O TikTok deste horario ja saiu; a marca e a que `_juntar_reposicao`
        # usa para juntar o YouTube reposto na ficha de antes.
        ficha["tiktok"] = ""
        ficha["so_youtube"] = True
    elif tk_alvo is None:
        # A fila do TikTok nao tem build que possa sair agora.
        ficha["tiktok"] = ""
        ficha["tiktok_sem_parte"] = True
    else:
        falha_tk: dict = {}
        if tk_alvo is not alvo:
            ficha.update({"tiktok_alvo": tk_alvo.id,
                          "tiktok_titulo": tk_alvo.titulo})
        ficha["tiktok"] = _tiktok_dos_builds(tk_alvo, falha_tk)
        _anotar_falha_do_tiktok(ficha, falha_tk)
    if _tiktok_confirmado(ficha["tiktok"]):
        ficha["feito"] = True
    _registrar_valvula(ficha)
    # "Junto com o novo, ate zerar": a falha do TikTok nao segura este envio.
    if (divida is not None and url and tk_alvo is not None
            and tk_alvo is not alvo):
        _alcance_do_youtube_dos_builds(ficha, tk_alvo)
    return ficha


def _build_por_id(video_id: str):
    """O item do catalogo de builds com aquele id. `None` se sumiu."""
    from builds.publicar import catalogo as C
    try:
        return next((v for v in C.listar() if v.id == video_id), None)
    except Exception:                                          # noqa: BLE001
        return None


def _build_ja_no_tiktok(video_id: str) -> bool:
    """O build ja saiu no TikTok? Rede de seguranca contra post repetido no
    caminho "YouTube ja saiu nesta hora, levando so para o TikTok"."""
    try:
        from builds.publicar import metricas
        return any(l.get("video_id") == video_id and _saiu(l)
                   and l.get("plataforma") == "tiktok"
                   for l in metricas.publicados())
    except Exception:                                          # noqa: BLE001
        return False


@_voando("builds", "youtube")
def _youtube_dos_builds(alvo, laudo: dict | None = None):
    """O YouTube dos builds — `publicar_como_configurado` registra por dentro.

    `laudo` e preenchido NO LUGAR pelo publicador (`prova=`): e por ele que
    a marca `clicou` chega a `postar_build` quando a excecao vem depois do
    clique.
    """
    from builds.publicar import youtube
    extra = {"prova": laudo} if laudo is not None else {}
    return youtube.publicar_como_configurado(alvo, canal="builds",
                                             visibilidade="public", log=_linha,
                                             **extra)


@_voando("builds", "tiktok")
def _tiktok_dos_builds(alvo, falha: dict | None = None) -> str:
    """Mesmo video, segundo destino. Aqui o registro E de dentro.

    Diferente das historias: `tiktok.publicar` chama
    `metricas.registrar_publicado(canal="builds")`, e para o canal `builds`
    esse registro vale — entao gravar de novo aqui duplicaria a linha, que e
    o defeito que ja custou uma limpeza de ledger em 09/09/2026.
    """
    from builds.publicar import tiktok as _tk
    if _build_ja_no_tiktok(alvo.id):
        _linha(f"   tiktok: {alvo.id} ja esta no TikTok; nao posto de novo.")
        return ""
    if _recusar_no_tiktok("builds", alvo, falha):
        return ""
    # O `laudo` E PREENCHIDO NO LUGAR pelo `tiktok.publicar`, e e por isso que
    # ele nasce aqui fora do `try`: a marca `clicou` escrita la dentro precisa
    # sobreviver a uma excecao levantada depois do clique.
    laudo: dict = {}
    try:
        # `postar=True` EXPLICITO. Sem ele o `tiktok.publicar` para antes de
        # publicar, que e o certo para o botao do painel — la a ultima palavra
        # e dele. A grade automatica nao tem quem clique, entao ela diz o que
        # quer. (A chave `tiktok.postar_automatico` saiu do config em 14/10.)
        estado = _tk.publicar(alvo, postar=True, canal="builds",
                              progresso=lambda t: _linha(f"   {t}"),
                              prova=laudo)
    except Exception as exc:                                   # noqa: BLE001
        # Ver o mesmo comentario em `_tiktok_das_historias`: sem a causa,
        # infraestrutura e defeito do video viram a mesma coisa.
        if falha is not None:
            falha["tipo"] = type(exc).__name__
            falha["mensagem"] = str(exc)[:300]
            if laudo.get("clicou"):
                falha["clicou"] = True
        _linha(f"   tiktok: NAO subiu ({type(exc).__name__}: {exc})"[:200])
        if laudo.get("clicou"):
            _garantir_marca("builds", alvo.id, "tiktok",
                            f"cliquei em publicar no TikTok e algo falhou "
                            f"depois ({type(exc).__name__}): o post pode "
                            f"estar no ar — confira no perfil.",
                            etapa="publicar.tiktok.clique")
        estado = ""
    return estado


# ------------------------------------------------ a serie do Blue Lock
# UM EPISODIO POR DIA, as 20:37, nos dois destinos (26/10/2026, pedido do
# Adrian; `grade.HORAS_DA_SERIE`). A fonte, a ORDEM, o titulo unico, o teto de
# um por dia e as regras de texto moram em `builds.publicar.serie_bluelock`;
# aqui ficam a leitura do relogio (a UNICA: `grade.slot`), a falha fechada do
# ledger e da lista "a conferir", os dois funis (`_voando`) e o registro.
#
# OS CAMINHOS que levam um episodio ao ar, contados: a rodada da grade e o
# `--so bluelock --agora` (o episodio pedido fora de hora). Os dois passam por
# `postar_bluelock`, e so por ela chegam aos funis abaixo; o `main.py publicar`
# le o catalogo de builds e nao enxerga o episodio. A recuperacao, a reserva e
# a divida nao tocam o canal (iteram historias e builds).
#
# SEM EPISODIO APROVADO O HORARIO FICA VAZIO E CALADO: a ficha leva
# `fora_da_grade` (a rodada a tira do Telegram e do codigo de saida). So o que
# TENTOU e falhou aparece.
def _quieta_da_serie(motivo: str) -> dict:
    return {"canal": "bluelock", "feito": False, "fora_da_grade": True,
            "motivo": motivo}


def _horarios_da_serie(plataforma: str) -> str:
    return ", ".join(grade.horario(h)
                     for h in grade.horas_da_serie(plataforma)) or "nenhum"


def postar_bluelock(*, so_ver: bool = False, agora: bool = False) -> dict:
    """O episodio da serie neste horario, nos dois destinos. Nunca levanta
    para quem chama (`_rodar_canal` embrulha)."""
    from datetime import datetime
    from builds.publicar import desfecho
    from builds.publicar import serie_bluelock as serie

    hora = grade.slot(datetime.now())
    if agora:
        destinos = list(serie.DESTINOS)
    else:
        destinos = [d for d in serie.DESTINOS if grade.publica_a_serie(d, hora)]
        if not destinos:
            return _quieta_da_serie(
                f"o horario das {grade.horario(hora)} nao e da serie "
                f"(youtube {_horarios_da_serie('youtube')}; "
                f"tiktok {_horarios_da_serie('tiktok')})")
    aprovados, fora = serie.episodios()
    for motivo in fora:
        _linha(f"[postar] bluelock: fora da fila - {motivo}"[:200])
    if not aprovados:
        return _quieta_da_serie("a serie nao tem episodio aprovado na fila")
    try:
        linhas = _publicados_do_canal("bluelock")
    except LedgerIlegivel as exc:
        return {"canal": "bluelock", "feito": False, "ledger_ilegivel": True,
                "motivo": str(exc)[:200]}

    escolhas, motivos, nao_li, ja_saiu = {}, [], [], set()
    for destino in destinos:
        try:
            marcados = set(desfecho.a_conferir("bluelock", destino))
        except Exception as exc:                               # noqa: BLE001
            nao_li.append(f"{destino}: nao consegui ler a lista 'a conferir' "
                          f"({type(exc).__name__}); nao publico")
            continue
        if not agora and not so_ver:
            ja = publicou_neste_horario("bluelock", destino)
            if ja:
                if ja.get("ledger_ilegivel"):
                    return _ficha_do_ledger_ilegivel("bluelock", ja)
                motivos.append(f"{destino}: ja saiu neste horario "
                               f"({ja.get('video_id')})")
                ja_saiu.add(destino)
                continue
        ep, motivo = serie.escolher(destino, aprovados, linhas, marcados)
        if ep is None:
            motivos.append(f"{destino}: {motivo}")
            continue
        escolhas[destino] = ep
    if nao_li:
        return {"canal": "bluelock", "feito": False,
                "motivo": "; ".join(nao_li)[:300]}
    if not escolhas:
        return _quieta_da_serie("; ".join(motivos) or "nada a publicar")
    if so_ver:
        return {"canal": "bluelock", "feito": False, "motivo": "so vendo",
                "veria": ", ".join(f"{d}: {e.id}" for d, e in escolhas.items()),
                "titulo": next(iter(escolhas.values())).titulo}

    ficha = {"canal": "bluelock", "feito": False}
    if "youtube" in escolhas:
        ep = escolhas["youtube"]
        video = ep.como_video()
        ficha.update({"alvo": ep.id, "titulo": ep.titulo})
        laudo: dict = {}
        try:
            estado = _youtube_da_serie(video, laudo)
        except Exception as exc:                               # noqa: BLE001
            falha = f"{type(exc).__name__}: {exc}"[:200]
            cota = _e_limite_diario(exc)
            _linha(f"[postar] bluelock: YouTube falhou ({falha}). Sigo para "
                   "o TikTok.")
            if cota:
                avisar_limite_diario(f"canal bluelock: {exc}")
                ficha["cota_youtube"] = True
            ficha.update({"youtube_falhou": True,
                          "motivo": (f"YouTube na cota: {falha}" if cota
                                     else f"YouTube falhou: {falha}")})
            if laudo.get("clicou"):
                ficha["youtube_clicou"] = True
                _garantir_marca(
                    "bluelock", ep.id, "youtube",
                    f"cliquei em publicar no YouTube e algo falhou depois "
                    f"({falha[:120]}): o video pode estar no ar como publico "
                    "ou RASCUNHO - confira no Studio.",
                    etapa="publicar.youtube.clique")
        else:
            publico = str(laudo.get("visibilidade") or "") == "public"
            if _youtube_confirmado(estado) and publico:
                serie.registrar(
                    video, estado, "youtube",
                    {"por": "postar.py", "visibilidade": "public",
                     "publicado": True, "estado": "publicado",
                     "episodio": ep.numero, "prova": [laudo],
                     "prova_ok": _prova_ok(laudo),
                     **({"youtube_id": laudo["youtube_id"]}
                        if laudo.get("youtube_id") else {})})
                ficha.update({"feito": True, "url": estado,
                              "visibilidade": "public"})
            else:
                # O CLIQUE SAIU E O YOUTUBE NAO DISSE "PUBLICO": pode ser
                # rascunho ou privado. Nao e "publicado" para o ledger, e o
                # episodio sai da fila (a conferir) em vez de subir de novo.
                ficha.update({"youtube_falhou": True, "youtube_clicou": True,
                              "motivo": "YouTube sem confirmacao de PUBLICO: "
                                        f"{str(estado)[:120]}"})
                _garantir_marca(
                    "bluelock", ep.id, "youtube",
                    "cliquei em publicar no YouTube e nao veio a confirmacao "
                    f"de PUBLICO ({str(estado)[:100]}): pode estar privado ou "
                    "como rascunho - confira no Studio.",
                    etapa="publicar.youtube.clique")
    if "tiktok" in escolhas:
        ep = escolhas["tiktok"]
        video = ep.como_video()
        ficha.setdefault("alvo", ep.id)
        ficha.setdefault("titulo", ep.titulo)
        if ep.id != ficha.get("alvo"):
            ficha.update({"tiktok_alvo": ep.id, "tiktok_titulo": ep.titulo})
        falha_tk: dict = {}
        ficha["tiktok"] = _tiktok_da_serie(video, falha_tk)
        _anotar_falha_do_tiktok(ficha, falha_tk)
        if _tiktok_confirmado(ficha["tiktok"]):
            ficha["feito"] = True
    elif "tiktok" in ja_saiu:
        # O TIKTOK DESTE HORARIO JA SAIU (reposicao do YouTube que a rede
        # derrubou): `_juntar_reposicao` junta pela marca `so_youtube`.
        ficha["tiktok"] = ""
        ficha["so_youtube"] = True
    elif "tiktok" in destinos:
        ficha["tiktok"] = ""
        ficha["tiktok_sem_parte"] = True
    else:
        ficha["tiktok"] = ""
        ficha["tiktok_fora_da_grade"] = True
    if "youtube" not in escolhas and not ficha.get("youtube_falhou"):
        ficha["so_tiktok"] = True
    return ficha


def _youtube_confirmado(estado) -> bool:
    """O YouTube CONFIRMOU a publicacao? Frase de "cliquei e nao confirmou"
    nao conta (a mesma regra de `_tiktok_confirmado`). Sem o modulo: "nao"."""
    try:
        from builds.publicar import youtube_web
        return bool(youtube_web.confirmado(estado))
    except Exception:                                          # noqa: BLE001
        return False


@_voando("bluelock", "youtube")
def _youtube_da_serie(alvo, laudo: dict | None = None):
    """O YouTube da serie, `PUBLICO` (decisao do Adrian, 26/10/2026).

    `publicar_como_configurado` NAO registra aqui: o registro dele e do canal
    `builds` (`metricas.registrar_publicado` descarta os outros) — quem chama
    grava no ledger proprio da serie so depois de ver `public` e a confirmacao.
    """
    from builds.publicar import youtube
    extra = {"prova": laudo} if laudo is not None else {}
    return youtube.publicar_como_configurado(alvo, canal="bluelock",
                                             visibilidade="public", log=_linha,
                                             **extra)


@_voando("bluelock", "tiktok")
def _tiktok_da_serie(alvo, falha: dict | None = None) -> str:
    """O TikTok da serie. Registra no ledger PROPRIO depois da confirmacao
    (o `tiktok.publicar` so registra o canal `builds`)."""
    from builds.publicar import serie_bluelock as serie
    from builds.publicar import tiktok as _tk
    laudo: dict = {}
    try:
        estado = _tk.publicar(alvo, postar=True, canal="bluelock",
                              progresso=lambda t: _linha(f"   {t}"),
                              prova=laudo)
    except Exception as exc:                                   # noqa: BLE001
        if falha is not None:
            falha["tipo"] = type(exc).__name__
            falha["mensagem"] = str(exc)[:300]
            if laudo.get("clicou"):
                falha["clicou"] = True
        _linha(f"   tiktok: NAO subiu ({type(exc).__name__}: {exc})"[:200])
        if laudo.get("clicou"):
            _garantir_marca("bluelock", alvo.id, "tiktok",
                            f"cliquei em publicar no TikTok e algo falhou "
                            f"depois ({type(exc).__name__}): o post pode "
                            f"estar no ar - confira no perfil.",
                            etapa="publicar.tiktok.clique")
        return ""
    if _tk.confirmado(estado):
        serie.registrar(alvo, estado, "tiktok",
                        {"por": "postar.py", "visibilidade": "public",
                         "publicado": True, "estado": "publicado",
                         "episodio": int(alvo.id.rsplit("ep", 1)[-1]),
                         "prova": [laudo] if laudo else [],
                         "prova_ok": _prova_ok(laudo)})
    return estado


# ------------------------------------------------------------------ tarefa
def escrever_lancador() -> Path:
    destino = RAIZ / "postar.cmd"
    saida = RAIZ / "outputs" / "postar.txt"
    saida.parent.mkdir(parents=True, exist_ok=True)
    # `newline=""` (SCR-11, 14/10/2026): o texto ja vem em CRLF, e o modo
    # texto do Windows trocava cada \n por \r\n de novo — o `postar.cmd`
    # ficava com CR CR LF (`cat -A`: ^M^M$).
    with open(destino, "w", encoding="utf-8", newline="") as fh:
        fh.write(
            "@echo off\r\n"
            "rem Postagem diaria: um video de cada canal.\r\n"
            "rem Gerado por: python ferramentas/postar.py --instalar\r\n"
            f'cd /d "{RAIZ}"\r\n'
            f'"{sys.executable}" -u -X utf8 ferramentas\\postar.py '
            f'--saida "{saida}" > NUL 2>&1\r\n')
    return destino


def nome_da_tarefa(hora: int) -> str:
    return f"{TAREFA}_{int(hora):02d}"


# O Agendador encerra a TAREFA (o wscript) depois disto, mas nao o python
# filho (medido em 06/10/2026): a dona pendurada morre pela rodada seguinte.
LIMITE_DA_TAREFA = "PT2H"


def instalar_grade(horas=None) -> list[dict]:
    """Uma tarefa por HORARIO da grade. Devolve o que deu em cada uma."""
    horas = list(horas or HORAS_PADRAO)
    # A antiga era uma so, sem numero no nome. Se ela ficar, o dia ganha uma
    # postagem a mais as 17:07 alem da tarefa `_17` — duas no mesmo horario.
    subprocess.run(["schtasks", "/Delete", "/TN", TAREFA, "/F"],
                   capture_output=True, timeout=60, creationflags=NO_WINDOW)
    return [instalar(grade.horario(h), nome=nome_da_tarefa(h)) for h in horas]


def instalar(hora: str = HORA_PADRAO, *, nome: str | None = None) -> dict:
    from builds import tarefas_windows
    lancador = escrever_lancador()
    # SEM SUFIXO NUNCA (SCR-4, 14/10/2026): `NeuralFights_postar` e a tarefa
    # antiga que `instalar_grade` APAGA para nao haver postagem dobrada; o
    # `--hora` a recriava.
    nome = nome or nome_da_tarefa(int(str(hora)[:2]))
    # SEM `text=True`: o schtasks escreve na pagina de codigo do console
    # (cp850/cp1252 aqui) e o Python assume UTF-8 — o "Ê" de "ÊXITO" virava
    # `UnicodeDecodeError` dentro da thread leitora do subprocess, no meio de
    # uma instalacao que tinha dado certo. Mesma familia do `-X utf8` que o
    # resto do projeto ja carrega.
    # A ACAO OCULTA (SCR-4): era o unico instalador sem `wscript //B
    # oculto.vbs`; reinstalar voltava com 10 janelas pretas por dia.
    proc = subprocess.run(
        ["schtasks", "/Create", "/TN", nome,
         "/TR", tarefas_windows.acao_oculta(lancador),
         "/SC", "DAILY", "/ST", hora, "/RL", "LIMITED", "/F"],
        capture_output=True, timeout=60, creationflags=NO_WINDOW)
    saida = (proc.stdout or b"").decode("oem", "replace")
    erro = (proc.stderr or b"").decode("oem", "replace")
    ficha = {"tarefa": nome, "hora": hora, "ok": proc.returncode == 0,
             "mensagem": (saida or erro).strip()}
    if ficha["ok"]:
        # Sem isto a postagem diaria herda os padroes do Windows: na bateria
        # ela nem comeca, e um horario perdido nunca volta — que e o oposto
        # de "pelo menos um video novo por dia". Ver builds/tarefas_windows.py.
        ajuste = tarefas_windows.endurecer(nome)
        ficha["ajustada"] = ajuste["ok"]
        if not ajuste["ok"]:
            ficha["mensagem"] = (
                f"{ficha['mensagem']} (criada, mas os ajustes de bateria e de "
                f"horario perdido falharam: {ajuste['mensagem']})").strip()
        # 72 h (o padrao do /Create) prendia o horario do dia seguinte na
        # regra IgnoreNew; ver `tarefas_windows.limitar_execucao` (06/10).
        limite = tarefas_windows.limitar_execucao(nome, LIMITE_DA_TAREFA)
        ficha["limite"] = limite["ok"]
        if not limite["ok"]:
            ficha["mensagem"] = (
                f"{ficha['mensagem']} (limite de execucao nao aplicado: "
                f"{limite['mensagem']})").strip()
    return ficha


# Abaixo do PISO o canal corre risco de ficar sem video novo. Nao e o momento
# de agir — e o momento de AVISAR, porque uma historia leva ~4h para nascer e
# o build depende do outro projeto: descobrir no dia em que acabou e tarde.
#
# O PISO E O DE REPOSICAO DECIDIDO, lido do config de quem cria, e nao um
# numero daqui. Historico: 14 dias ate 10/09/2026; 1 dia ("gordura de apenas
# um dia em tudo") ate 30/09/2026, quando o lote semanal trouxe a decisao
# `geral/lote-piso-de-reposicao`: "2 dias = 20 videos" — abaixo disso qui-dom
# voltam a criar. Alertar com outro numero seria o alerta e a criacao
# discordando sobre o que e "pouco". Mora em `historias/config/agenda.json`
# (`piso_de_reposicao`); o de builds, em `random_builds/config/geracao.json`
# se a parte Builds o puser la, e senao o mesmo (a decisao e geral).
#
# Sem config legivel: os mesmos 2 dias da decisao, em horarios da grade.
DIAS_DO_PISO_SEM_CONFIG = 2

# "Sem estoque de um FORMATO" (builds): menos de um dia da cota dele. Nao e o
# piso do canal — e o aviso de que a grade vai passar a cota para os outros.
DIAS_DE_FORMATO_SECO = 1


def piso_de_alerta(canal: str) -> int:
    """O piso de reposicao do canal, em VIDEOS. Nunca levanta."""
    if canal == "builds":
        try:
            from builds.pipeline import noite
            valor = noite.carregar().get("piso_de_reposicao")
            if valor is not None:
                return max(0, int(valor))
        except Exception:                                      # noqa: BLE001
            pass
    try:
        from contos.pipeline import agenda
        return agenda.piso_de_reposicao(agenda.carregar())
    except Exception:                                          # noqa: BLE001
        return DIAS_DO_PISO_SEM_CONFIG * (len(HORAS_PADRAO) or 1)


def pendentes_por_canal() -> dict:
    """Quantos VIDEOS prontos cada canal ainda tem para publicar."""
    saida = {}
    try:
        # RETIDA NAO E ESTOQUE (28/09/2026). A parte que a IA reprovou, ou que
        # so a folha de contato viu (`nao_assistido`), so sai no lugar do
        # horario vazio (`_retencao`, a valvula de qualidade). Contada aqui,
        # ela virava "dias de gordura" que a escolha nao usa; ela aparece a
        # parte, em `retidos_por_canal`.
        saida["historias"] = len([v for v in fila_de_historias()
                                  if not _retencao(v)])
    except Exception as exc:                                   # noqa: BLE001
        # O -1 TEM DE DEIXAR RASTRO. Em 05/10/2026 ele era engolido aqui, e
        # quem le (o freio da agenda) caiu no plano B contando as retidas:
        # tres madrugadas sem historia nova, e nenhuma linha dizendo por que.
        _contagem_falhou("historias", exc)
        saida["historias"] = -1
    try:
        # O MESMO FUNIL DO `proximo_build`, e nao uma contagem propria.
        # Contando so `catalogo - ja`, a gordura dizia "2 dias" enquanto
        # `proximo_build` devolvia None: ficavam de fora as pendencias (as 20
        # estreias impossiveis) e os titulos repetidos. O alerta "ABAIXO DO
        # PISO" nunca disparava na hora certa, porque o numero que ele olha
        # nao era o numero que sai. Desde 27/09/2026 e literalmente a mesma
        # funcao (`_builds_prontos`), com o audio mudo junto.
        saida["builds"] = len(_builds_prontos())
    except Exception as exc:                                   # noqa: BLE001
        _contagem_falhou("builds", exc)
        saida["builds"] = -1
    return saida


def _contagem_falhou(canal: str, exc: BaseException) -> None:
    """A contagem do estoque quebrou: log E diario, e nunca levanta.

    O -1 que sai daqui e "nao sei", e "nao sei" calado ja virou numero
    errado uma vez (o plano B da agenda). O diario e o que o bot de apuracao
    e a pagina de confiabilidade leem.
    """
    texto = (f"nao consegui contar o estoque de {canal} "
             f"({type(exc).__name__}: {str(exc)[:160]}); devolvo -1")
    _linha(f"[estoque] {texto}")
    try:
        from builds import atividade
        atividade.registrar("publicacao", atividade.ERRO, texto, canal,
                            etapa="publicar.estoque")
    except Exception:                                          # noqa: BLE001
        pass


def retidos_por_canal() -> dict:
    """Quantas partes estao RETIDAS pela valvula de qualidade, por canal.

    A parte, e nunca somadas a gordura: elas so saem quando o horario ia
    ficar vazio. Builds nao tem valvula de qualidade (sem parecer de IA), e
    so aparece o canal que tem. `-1` quando nao deu para contar.
    """
    try:
        return {"historias": len([v for v in fila_de_historias()
                                  if _retencao(v)])}
    except Exception:                                          # noqa: BLE001
        return {"historias": -1}


def consertadas_por_canal() -> dict:
    """Quantas das retidas ja foram CONSERTADAS e esperam so alguem assistir.

    Em 05/10/2026, 37 das 57 retidas. Elas NAO voltam ao estoque limpo: o
    Adrian decidiu manter uma passada so (`historias/reolhar-depois-do-
    conserto`, opcao "nao", 05/10 12:32) — a consertada so ganha a frente
    entre as retidas. O numero fica no `--ver` para se ver o tamanho da fila
    que espera alguem assistir. `-1` quando nao deu para contar.
    """
    try:
        return {"historias": len([v for v in fila_de_historias()
                                  if _consertada(v)])}
    except Exception:                                          # noqa: BLE001
        return {"historias": -1}


def estoque(por_dia: int | None = None) -> dict:
    """Quantos DIAS de video pronto cada canal tem.

    A CONTA MUDOU EM 09/09/2026 e a antiga passaria a mentir por 8x. Ela dizia
    "um video por dia, entao um pendente = um dia" — e a grade passou a ter
    OITO horarios (6, 7, 8, 10, 12, 15, 17, 20). Os mesmos 55 pendentes que
    eram "55 dias" viraram sete.

    Dividir e o conserto obvio, e ele importa porque o piso de alerta existe
    justamente para avisar ANTES de faltar: com a conta velha o alerta so
    dispararia quando ja faltasse menos de dois dias de verdade.
    """
    dias = {}
    for canal, quantos in pendentes_por_canal().items():
        # Por CANAL desde 20/10/2026: builds posta 3 por dia no YouTube.
        n = int(por_dia or grade.meta_diaria(canal, "youtube")) or 1
        dias[canal] = quantos if quantos < 0 else quantos // n
    return dias


def estoque_do_lote(agora=None, pendentes: dict | None = None) -> dict:
    """Por canal: videos prontos, dias, piso e o que falta ate SEGUNDA 07h.

    `{canal: {"videos", "dias", "piso", "magro", "fim", "horarios", "alvo",
    "faltam"}}`. O lote semanal (decisoes de 30/09/2026) produz de segunda a
    quarta para cobrir ate a proxima segunda 07h mais o piso; a pergunta que
    importa no meio da semana e "o estoque chega la?".

    O FIM E O ALVO SAO OS DA AGENDA de historias (`fim_da_cobertura`,
    `postagens_entre`, `alvo_do_lote.mais_o_piso`): o aviso e a criacao
    medem com a mesma regua. So o piso e o de cada canal.

    `videos` e o funil da escolha (`pendentes_por_canal`), sem retidos.
    `-1` quando nao deu para contar; `magro` e so para conta que deu
    (ZERO videos e magro). Sem a agenda, `fim`/`alvo`/`faltam` ficam `None`.
    """
    from datetime import datetime
    agora = agora or datetime.now()
    por_dia = len(HORAS_PADRAO) or 1
    if pendentes is None:
        pendentes = pendentes_por_canal()
    fim, horarios, mais_o_piso = None, None, True
    try:
        from contos.pipeline import agenda
        config = agenda.carregar()
        fim = agenda.fim_da_cobertura(config, agora)
        horarios = agenda.postagens_entre(agora, fim)
        mais_o_piso = bool((config.get("alvo_do_lote") or {})
                           .get("mais_o_piso", True))
    except Exception:                                          # noqa: BLE001
        fim, horarios = None, None
    saida = {}
    for canal, videos in pendentes.items():
        piso = piso_de_alerta(canal)
        contou = videos is not None and videos >= 0
        # A REGUA DE CADA CANAL (20/10/2026): builds tem 3 horarios por dia
        # no YouTube, e "dias" e "horarios ate segunda" contam os dele.
        do_canal = grade.meta_diaria(canal, "youtube", agora) or por_dia
        horarios_do_canal = horarios
        if (horarios is not None and fim is not None
                and canal in grade.HORAS_POR_CANAL):
            # Dia a dia pela tabela DE CADA DIA (antes de 20/10 os dez).
            horarios_do_canal = _horarios_do_canal_entre(canal, agora, fim)
        ficha = {"videos": videos,
                 "dias": (videos / do_canal) if contou else -1,
                 "piso": piso, "magro": bool(contou and videos < piso),
                 "fim": fim, "horarios": horarios_do_canal,
                 "por_dia": do_canal,
                 "alvo": None, "faltam": None}
        if horarios_do_canal is not None:
            ficha["alvo"] = horarios_do_canal + (piso if mais_o_piso else 0)
            if contou:
                ficha["faltam"] = max(0, ficha["alvo"] - videos)
        saida[canal] = ficha
    return saida


def _horarios_do_canal_entre(canal: str, inicio, fim,
                             plataforma: str = "youtube") -> int:
    """Quantos horarios DAQUELE canal caem em (inicio, fim]. Pura."""
    from datetime import datetime, timedelta
    total, dia = 0, inicio.date()
    while dia <= fim.date():
        for hora in grade.horas_do_canal(canal, plataforma, dia):
            momento = datetime(dia.year, dia.month, dia.day, int(hora),
                               grade.minuto(hora))
            if inicio < momento <= fim:
                total += 1
        dia += timedelta(days=1)
    return total


def _dias(n: float) -> str:
    """`1,2` — dias com uma casa, virgula brasileira."""
    return f"{n:.1f}".replace(".", ",")


def linhas_do_estoque(lote: dict) -> list:
    """O estoque por canal em texto, para o log e para o `--ver`."""
    semana = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
    linhas = []
    for canal, f in lote.items():
        if f["videos"] is None or f["videos"] < 0:
            linhas.append(f"  gordura {canal:<10} nao deu para contar")
            continue
        alerta = (f"  <<< ABAIXO DO PISO ({f['piso']} videos)"
                  if f["magro"] else "")
        linhas.append(f"  gordura {canal:<10} {f['videos']:>4} video(s) = "
                      f"{_dias(f['dias'])} dia(s){alerta}")
        if f["fim"] is not None:
            por_dia = f.get("por_dia") or len(HORAS_PADRAO) or 1
            quando = (f"{semana[f['fim'].weekday()]} "
                      f"{f['fim']:%d/%m %Hh}")
            linhas.append(
                f"          ate {quando}: {f['horarios']} horario(s) = "
                f"{_dias(f['horarios'] / por_dia)} dia(s); com o piso, "
                f"alvo {f['alvo']} -> "
                + (f"faltam {f['faltam']}" if f["faltam"] else "cobre"))
    return linhas


def frescor_do_estoque(agora=None) -> dict:
    """`{canal: {"mais_velho": dias | None, "acima": n, "videos": n}}`.

    O prazo e `PRAZO_DE_FRESCOR_DIAS` (6, decisao `lote-frescor`). Historias
    pela data em que a historia nasceu (`_criado_da_fonte`), sem as retidas
    (nao sao estoque); builds pelo mp4 (`quando`), no funil da escolha.
    So o `--ver` pergunta: e mais uma passada no catalogo. Canal que nao deu
    para ler fica de fora.
    """
    from datetime import datetime
    agora = agora or datetime.now()
    saida = {}
    try:
        fila = [v for v in fila_de_historias() if not _retencao(v)]
        idades = [_idade_em_dias(_criado_da_fonte(v.fonte_id, [v]), agora)
                  for v in fila]
        saida["historias"] = idades
    except Exception:                                          # noqa: BLE001
        pass
    try:
        idades = []
        for v in _builds_prontos():
            try:
                idades.append(_idade_em_dias(
                    datetime.fromtimestamp(float(v.quando)), agora))
            except (TypeError, ValueError, OSError):
                idades.append(None)
        saida["builds"] = idades
    except Exception:                                          # noqa: BLE001
        pass
    fichas = {}
    for canal, idades in saida.items():
        sabidas = [i for i in idades if i is not None]
        fichas[canal] = {
            "videos": len(idades),
            "mais_velho": max(sabidas) if sabidas else None,
            "acima": len([i for i in sabidas if i > PRAZO_DE_FRESCOR_DIAS])}
    return fichas


def estoque_por_formato(por_dia: int | None = None) -> dict:
    """Dias de estoque de CADA formato de builds, pela cota dele.

    O total do canal esconde o que importa depois da Onda 15E: com a grade
    alternando formatos, o duelo pode secar enquanto o numero geral segue
    confortavel — e a comparacao para de ter os dois lados sem ninguem
    perceber. Cada formato e medido contra a cota DELE, nao contra os 8
    disparos do dia.

    CONTA O QUE A ESCOLHA PODE LEVAR (`_builds_prontos`), e nao o catalogo.
    Medido em 27/09/2026: dizia `build 7` com zero builds publicaveis — 25
    variantes B com titulo no ar e 3 com pendencia entravam na conta. Um
    formato a zero aparece como zero (e o aviso "sem estoque" dispara); so
    a falha de leitura devolve `{}`.
    """
    try:
        pendentes = _builds_prontos()
    except Exception:                                          # noqa: BLE001
        return {}
    contagem: dict[str, int] = {}
    for video in pendentes:
        origem = str(getattr(video, "origem", ""))
        contagem[origem] = contagem.get(origem, 0) + 1
    saida = {}
    for origem, saidas_por_dia in consumo_por_formato(
            cota_da_grade(), por_dia).items():
        saida[origem] = int(contagem.get(origem, 0)
                            // max(1e-9, saidas_por_dia))
    return saida


def consumo_por_formato(cota: dict, por_dia: int | None = None) -> dict:
    """Quantos videos NOVOS de cada formato saem por dia, pura.

    Desde 19/10/2026 cada destino tem a sua mistura e os seus horarios: o
    YouTube (dez, `por_dia`) sem estreia, o TikTok (seis) com a do config. O
    TikTok leva quase sempre o que o YouTube ja subiu (a fila de atraso dele),
    entao o formato gasta o MAIOR dos dois ritmos, nao a soma. Conta de mao
    (duelo 4, build 3, estreia 1): YouTube duelo 10*5/8 = 6,25, build 3,75;
    TikTok estreia 6*1/8 = 0,75. Formato com cota zero nos dois nao entra.
    """
    # Desde 20/10/2026 os horarios sao os DO CANAL de builds (YouTube 3,
    # TikTok 1) e as duas misturas so tem duelo: duelo 3/dia, o resto 0.
    ritmos: dict = {}
    for plataforma in grade.PLATAFORMAS:
        horas = (int(por_dia) if (por_dia and plataforma == "youtube")
                 else grade.meta_diaria("builds", plataforma))
        dela = cota_da_plataforma(cota, plataforma)
        total = sum(dela.values()) or 1
        for origem, peso in dela.items():
            if peso > 0:
                ritmos[origem] = max(ritmos.get(origem, 0.0),
                                     horas * peso / total)
    return ritmos


CANAIS = {"historias": {"emoji": "📖", "rotulo": "histórias"},
          "builds": {"emoji": "⚔️", "rotulo": "builds"},
          "bluelock": {"emoji": "⚽", "rotulo": "Blue Lock (série)"}}


def _conta_do_destino(servico: str, canal: str) -> str:
    """O NOME DA CONTA e o destino — a doutrina do registro de contas.

    Sem ele o aviso diz "postei" e nao diz ONDE, e "para qual canal isso foi"
    e a pergunta que so se responde abrindo o navegador. Publicar no canal
    errado nao tem desfazer bonito.
    """
    try:
        from builds import contas
        return contas.ativa(servico, canal)
    except Exception:                                          # noqa: BLE001
        return "?"


def _estado_da_plataforma(estado: str) -> str:
    """Uma linha legivel a partir do que o publicador devolveu.

    O YouTube devolve URL quando tem, e a FRASE de sucesso quando o Studio nao
    entrega link — e nesse caso ela vem repetida com " | " para cada pedaco
    (uma parte longa vira dois Shorts). Mostrar isso cru era o que fazia o
    aviso dizer "publicado no YouTube | publicado no YouTube".
    """
    estado = str(estado or "").strip()
    if not estado:
        return "🚫 não subiu"
    if estado.startswith("http"):
        return f"✅ {estado[:90]}"
    pedacos = [p for p in estado.split("|") if p.strip()]
    if len(pedacos) > 1:
        return f"✅ publicado ({len(pedacos)} pedaços)"
    return "✅ publicado"


def _proximo_horario(agora=None) -> str:
    return grade.proximo(agora).replace("(amanha)", "(amanhã)")


def avisar(resultados: list) -> None:
    """Conta no Telegram O QUE subiu, ONDE e QUANDO.

    A versao antiga dizia so "postado no YouTube" e despejava o `url` cru —
    que na maioria das vezes e a frase de estado repetida, nao um link. E nao
    mencionava o TikTok em lugar nenhum, mesmo depois de ele entrar na grade
    em 10/09/2026. Pedido dele no mesmo dia: "discrimine bem quando foi, em
    quais plataformas e outras infos".
    """
    from datetime import datetime
    agora = datetime.now()
    linhas = [f"📤 *Postagem* — {agora:%d/%m às %H:%M}", ""]
    for r in resultados:
        canal = r.get("canal", "?")
        ficha = CANAIS.get(canal, {"emoji": "•", "rotulo": canal})
        if not r.get("feito"):
            linhas.append(f"{ficha['emoji']} *{ficha['rotulo']}* — não saiu")
            linhas.append(f"    {str(r.get('motivo', ''))[:150]}")
            linhas.append("")
            continue

        cabeca = f"{ficha['emoji']} *{ficha['rotulo']}*"
        conta = _conta_do_destino("youtube_web", canal)
        if conta and conta != "?":
            cabeca += f" · {conta}"
        linhas.append(cabeca)
        titulo = str(r.get("titulo") or "")[:70]
        if r.get("parte") and r.get("partes"):
            linhas.append(f"    {titulo}  (parte {r['parte']}/{r['partes']})")
        else:
            linhas.append(f"    {titulo}")
        # A DIVIDA DO YOUTUBE (06/10/2026): a parte do YouTube saiu antes no
        # TikTok. Com ela, cada destino pode ter levado uma parte diferente.
        devido = str(r.get("youtube_devido") or "")
        devido = (f" — parte devida (saiu no TikTok às {devido[11:16]})"
                  if devido else "")
        if r.get("youtube_fora_da_grade"):
            linhas.append("    ▸ YouTube   ⏸ fora da grade do canal "
                          "neste horário")
        elif r.get("so_tiktok"):
            linhas.append("    ▸ YouTube   já saiu neste horário")
        elif r.get("cota_youtube"):
            linhas.append("    ▸ YouTube   🚫 limite diário da conta"
                          f"{devido}")
        elif r.get("youtube_meio_no_ar"):
            linhas.append("    ▸ YouTube   ❌ pedaço da parte já no ar e o "
                          "seguinte falhou (a parte espera uma pessoa na "
                          "lista a conferir)")
        elif r.get("youtube_falhou"):
            motivo = str(r.get("motivo") or "").split(": ", 1)[-1]
            linhas.append(f"    ▸ YouTube   ❌ falhou: {motivo[:100]} "
                          f"(a parte volta no próximo horário){devido}")
        else:
            linhas.append("    ▸ YouTube   "
                          f"{_estado_da_plataforma(r.get('url'))}"
                          f" · {r.get('visibilidade') or '?'}{devido}")
        outra = ""
        if r.get("tiktok_alvo"):
            outra = (f" — outra parte: {r.get('tiktok_parte') or '?'}/"
                     f"{r.get('partes') or '?'} (`{r['tiktok_alvo']}`)")
        if r.get("tiktok_fora_da_grade"):
            linhas.append("    ▸ TikTok    ⏸ fora da grade do TikTok "
                          "neste horário")
        elif r.get("so_youtube"):
            linhas.append("    ▸ TikTok    já saiu neste horário")
        elif r.get("tiktok_sem_parte"):
            linhas.append("    ▸ TikTok    🚫 a fila do TikTok não tem "
                          "vídeo que possa sair agora")
        else:
            linhas.append("    ▸ TikTok    "
                          f"{_estado_da_plataforma(r.get('tiktok'))}"
                          f" · {_conta_do_destino('tiktok', canal)}{outra}")
        linhas.append(f"    `{r.get('alvo', '')}`")
        if r.get("veto_vencido"):
            # Uma passada so desde 15/09/2026: "as 3 rodadas" mentia.
            linhas.append("    ⚠ saiu com veto da IA: a passada de "
                          "conserto já foi gasta")
        if r.get("veto_ignorado"):
            linhas.append("    ⚠ saiu com veto da IA: nao havia outro video "
                          "pronto e o horario nao podia ficar vazio")
        if r.get("retido"):
            if r.get("consertada"):
                linhas.append("    ⚠ saiu RETIDA (consertada depois do veto, "
                              "mas ninguem assistiu ao video novo): nao "
                              "havia outra parte. Esta na lista a conferir.")
            else:
                linhas.append("    ⚠ saiu RETIDA (a IA reprovou ou ninguem "
                              "assistiu): nao havia outra parte. Esta na "
                              "lista a conferir.")
        if r.get("tiktok_retido"):
            linhas.append("    ⚠ a parte do TikTok saiu RETIDA: esta na "
                          "lista a conferir do TikTok.")
        if r.get("titulo_repetido"):
            linhas.append("    ⚠ saiu com titulo JA PUBLICADO: nao havia "
                          "outro video na fila. Os dois competem entre si.")
        for recusado in (r.get("recusados") or [])[:2]:
            linhas.append(f"    ⏭ pulei {str(recusado)[:90]}")
        linhas.append("")

    try:
        lote = estoque_do_lote(agora)
    except Exception:                                          # noqa: BLE001
        lote = {}
    linhas.append("*Estoque* — " + " · ".join(
        f"{CANAIS.get(c, {}).get('emoji', '•')} "
        + (f"{f['videos']} vídeo(s), {_dias(f['dias'])} dia(s)"
           if f["videos"] is not None and f["videos"] >= 0
           else "não deu para contar")
        for c, f in lote.items()))
    try:
        retidos = {c: n for c, n in retidos_por_canal().items() if n > 0}
    except Exception:                                          # noqa: BLE001
        retidos = {}
    if retidos:
        linhas.append("    retidos — " + " · ".join(
            f"{CANAIS.get(c, {}).get('emoji', '•')} {n} parte(s)"
            for c, n in retidos.items())
            + " (fora da gordura: so saem no lugar do vazio)")
    magros = [f"{CANAIS.get(c, {}).get('rotulo', c)} ({f['videos']} de "
              f"{f['piso']})" for c, f in lote.items() if f["magro"]]
    if magros:
        linhas.append(f"⚠️ *abaixo do piso de reposição*: "
                      f"{', '.join(magros)} — sem vídeo novo o canal para.")
    # Por FORMATO: o total do canal esconde um formato secando. Com a grade
    # alternando, o duelo pode acabar enquanto o numero geral segue folgado
    # — e a comparacao da Onda 15 perde um dos lados sem ninguem ver.
    try:
        por_formato = estoque_por_formato()
    except Exception:                                          # noqa: BLE001
        por_formato = {}
    if por_formato:
        linhas.append("    por formato — " + " · ".join(
            f"{o} {n}d" for o, n in sorted(por_formato.items())))
        secos = [o for o, n in por_formato.items()
                 if n < DIAS_DE_FORMATO_SECO]
        if secos:
            linhas.append(f"⚠️ sem estoque de *{', '.join(sorted(secos))}*: "
                          "a grade passa a cota para os outros formatos.")
    linhas.append(f"Próximo horário: {_proximo_horario(agora)}")
    try:
        subprocess.run([sys.executable, "-m", "remoto", "--avisar",
                        "\n".join(linhas)], cwd=str(RAIZ), timeout=90,
                       capture_output=True, creationflags=NO_WINDOW)
    except Exception:                                          # noqa: BLE001
        pass


def _e_limite_diario(exc) -> bool:
    """A falha e a cota de envios do YouTube? Por CLASSE, com o texto de rede.

    A classe e a resposta certa; o texto e a rede para quando o aviso vier por
    um caminho que ainda nao levanta `LimiteDiarioDoYouTube`.
    """
    try:
        from builds.publicar.youtube_web import (LIMITE_DIARIO,
                                                 LimiteDiarioDoYouTube)
    except Exception:                                          # noqa: BLE001
        return False
    if isinstance(exc, LimiteDiarioDoYouTube):
        return True
    return any(m in str(exc).lower() for m in LIMITE_DIARIO)


def avisar_limite_diario(detalhe: str, *, publicados: int = 0) -> bool:
    """Manda no Telegram que a cota estourou. Nunca derruba a postagem.

    Pedido dele em 10/09/2026: "quando isso ocorrer no youtube me avise que
    resolvo remotamente com o anydesk". E o tipo de coisa que so uma pessoa
    resolve — nao ha retry, nao ha conserto de codigo, alguem precisa abrir a
    conta. Um aviso que chega no celular vale mais que dez linhas de log.
    """
    import subprocess
    texto = ("🚫 *YouTube: limite diário de envios*\n"
             f"{detalhe[:200]}\n"
             f"Publiquei {publicados} antes de bater a cota; a fila continua "
             "na ordem e retoma quando o YouTube liberar.\n"
             "O TikTok não é afetado.")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "remoto", "--avisar", texto],
            cwd=str(RAIZ), capture_output=True, timeout=90,
            creationflags=NO_WINDOW)
        return proc.returncode == 0
    except Exception:                                          # noqa: BLE001
        return False


def _fechamento_do_lote(config: dict, agora):
    """O fim do ULTIMO dia de lote (qua 22:00) se agora e a noite dele.

    "Noite" vai do fim da janela pesada daquele dia ate ela abrir no dia
    seguinte (qua 22:00 -> qui 07:00): as rodadas das 22:37, 23:37, 00:37 e
    06:37. Uma rodada que falhe (PC desligado) nao leva o aviso junto.
    `None` fora dela, sem dias de lote ou janela no config, e antes de
    `lote_a_partir_de` (`agenda.lote_valendo`: sem lote, nao ha o que fechar).
    """
    from datetime import timedelta
    from contos.pipeline import agenda
    dias = agenda.dias_de_lote(config)
    janela = config.get("janela_pesada") or {}
    if not dias or "fim" not in janela or "inicio" not in janela:
        return None
    ultimo, fim = max(dias), int(janela["fim"]) % 24
    inicio = int(janela["inicio"]) % 24
    for atras in (0, 1):
        fecha = (agora - timedelta(days=atras)).replace(
            hour=fim, minute=0, second=0, microsecond=0)
        if fecha.weekday() != ultimo:
            continue
        abre = (fecha + timedelta(days=1)).replace(hour=inicio)
        if fecha <= agora < abre and agenda.lote_valendo(config, fecha):
            return fecha
    return None


def _arquivo_do_aviso_do_lote(canal: str):
    """Ao lado do `publicados.jsonl` do canal, como as desistencias."""
    from builds.publicar import metricas
    return metricas.registro_do_canal(canal).parent / "_lote_avisado.json"


def _lote_ja_avisado(canal: str, semana: str) -> bool:
    try:
        dados = json.loads(_arquivo_do_aviso_do_lote(canal)
                           .read_text(encoding="utf-8"))
        return isinstance(dados, dict) and dados.get("semana") == semana
    except (OSError, ValueError):
        return False


def _marcar_lote_avisado(canal: str, semana: str) -> None:
    try:
        caminho = _arquivo_do_aviso_do_lote(canal)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps({"semana": semana}), encoding="utf-8")
    except OSError:
        pass


def _mandar_no_telegram(texto: str) -> bool:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "remoto", "--avisar", texto],
            cwd=str(RAIZ), capture_output=True, timeout=90,
            creationflags=NO_WINDOW)
        return proc.returncode == 0
    except Exception:                                          # noqa: BLE001
        return False


def avisar_lote_nao_fechou(agora=None, *, lote: dict | None = None,
                           config: dict | None = None) -> list:
    """Na noite de quarta, avisa se o estoque de algum canal ficou abaixo do alvo.

    Plano do lote semanal (30/09/2026): historias seg-qua, builds seg-ter;
    de quinta a domingo so se repoe abaixo do piso. Se o lote nao chegou ao
    alvo (`estoque_do_lote`: horarios ate a proxima segunda 07h + o piso),
    a semana corre sem gordura — e quarta 22h e a ultima hora em que isso
    ainda e noticia, e nao susto. UMA VEZ POR SEMANA POR CANAL (marca ao
    lado do ledger, gravada so se o Telegram aceitou: aviso que nao chegou
    tenta de novo na rodada seguinte da mesma noite).

    CASO ZERO: estoque zero avisa (0 < alvo). Canal que nao deu para contar
    avisa tambem, dizendo isso — silencio nao pode parecer "fechou". Sem o
    alvo (agenda ilegivel) nao ha regua, e nao avisa.

    Devolve os canais avisados (para o teste e para o log).
    """
    from datetime import datetime
    agora = agora or datetime.now()
    try:
        from contos.pipeline import agenda
        config = config if config is not None else agenda.carregar()
        fecha = _fechamento_do_lote(config, agora)
    except Exception:                                          # noqa: BLE001
        return []
    if fecha is None:
        return []
    semana = fecha.strftime("%Y-%m-%d")
    lote = lote if lote is not None else estoque_do_lote(agora)
    faltando = []
    for canal, f in lote.items():
        if f.get("alvo") is None or _lote_ja_avisado(canal, semana):
            continue
        videos = f.get("videos")
        if videos is not None and videos >= f["alvo"]:
            continue
        faltando.append((canal, f))
    if not faltando:
        return []
    semana_pt = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
    linhas = [f"📦 *O lote da semana não fechou* — "
              f"{semana_pt[fecha.weekday()]} {fecha:%d/%m}, {fecha:%H}h", ""]
    for canal, f in faltando:
        ficha = CANAIS.get(canal, {"emoji": "•", "rotulo": canal})
        fim = f.get("fim")
        ate = (f"até {semana_pt[fim.weekday()]} {fim:%d/%m %H}h"
               if fim is not None else "até segunda")
        if f.get("videos") is None or f["videos"] < 0:
            linhas.append(f"{ficha['emoji']} *{ficha['rotulo']}*: não deu "
                          f"para contar o estoque; o alvo é {f['alvo']}.")
            continue
        linhas.append(f"{ficha['emoji']} *{ficha['rotulo']}*: {f['videos']} "
                      f"vídeo(s) prontos; o alvo era {f['alvo']} "
                      f"({f['horarios']} horários {ate} + piso {f['piso']}). "
                      f"Faltam {f['faltam']}.")
    linhas += ["", "De quinta a domingo a criação só repõe abaixo do piso: "
                   "o que faltar até segunda sai da reposição ou vira "
                   "horário vazio."]
    if not _mandar_no_telegram("\n".join(linhas)):
        _linha("[postar] o aviso 'o lote nao fechou' nao saiu; tento na "
               "proxima rodada desta noite.")
        return []
    for canal, _f in faltando:
        _marcar_lote_avisado(canal, semana)
    _linha(f"[postar] avisei: o lote nao fechou "
           f"({', '.join(c for c, _f in faltando)}).")
    return [c for c, _f in faltando]


def escoar_historias(*, limite: int = 0, so_ver: bool = False) -> dict:
    """Publica TODA a fila de historias, uma atras da outra.

    NAO passa pela guarda de um-por-horario, e isso e de proposito: a guarda
    existe para o disparo AUTOMATICO nao repetir a si mesmo, e aqui quem pediu
    foi uma pessoa, uma vez, sabendo o tamanho. Chamar isso de "furar a regra"
    seria confundir a regra com o motivo dela.

    A ORDEM E A MESMA da fila normal — serie comecada primeiro, e dentro dela
    a menor parte que falta. Escoar nao pode virar bagunca: quem esta vendo a
    parte 3 continua recebendo a 4 antes da 5.

    Para na primeira sequencia de falhas: dois erros seguidos quase sempre
    significam que a plataforma comecou a recusar, e insistir depois disso
    troca "atraso" por "conta com strike".
    """
    from contos.publicar import serie

    fila = fila_de_historias()
    if so_ver:
        return {"total": len(fila), "ids": [v.id for v in fila]}

    visibilidade = _visibilidade_das_historias()
    feitos, falhas, seguidas = [], [], 0
    # PELA MESMA PORTA DA RODADA (11/10/2026): `proxima_historia` — vistoria,
    # veto de pe, retencao, trava de render. Ate aqui o escoar lia a fila
    # crua e subia parte vetada pela IA sem marca e sem `prova` no ledger
    # (prova da auditoria: subiu a p03 vetada, vistoriou nada, marcou nada).
    # Uma parte por volta: cada `serie.registrar` tira a parte da fila, e a
    # proxima chamada ja ve o teto por fonte com ela contada.
    teto = limite or len(fila)
    for i in range(1, teto + 1):
        alvo, _recusados = proxima_historia(vistoriar=True)
        if alvo is None:
            _linha("[escoar] nenhuma parte publicavel; parei.")
            break
        _linha(f"[escoar] {i}/{len(fila)}  {alvo.id}  {alvo.titulo[:52]}")
        try:
            provas: list = []
            url = _subir_parte_no_youtube(alvo, visibilidade, provas)
            serie.registrar(alvo, url, "youtube", None,
                            {"por": "postar.py --tudo",
                             "visibilidade": _visibilidade_usada(provas, visibilidade), "prova": provas,
                             "prova_ok": _prova_ok(provas),
                             **_ids_da_parte(provas)})
            ficha = {"canal": "historias", "feito": True,
                     "alvo": alvo.id, "titulo": alvo.titulo,
                     "url": url, "parte": alvo.parte,
                     "partes": alvo.partes, "prova": provas}
            retencao = _valvula_da_parte(ficha, alvo)
            if retencao:
                _marcar_retido(alvo, retencao, ("youtube",))
            _registrar_valvula(ficha)
            _linha(f"           youtube: {url}"[:110])
            seguidas = 0
        except Exception as exc:                               # noqa: BLE001
            # COTA NAO SE TENTA DE NOVO. Ela nao e "falhou": e "o YouTube nao
            # aceita mais nada hoje", e o proximo da fila bate na mesma
            # parede. Em 10/09/2026 foram dois videos e um minuto de espera
            # cada para descobrir uma coisa que estava escrita na tela.
            if _e_limite_diario(exc):
                _linha(f"[escoar] LIMITE DIARIO DO YOUTUBE: {exc}")
                _linha("[escoar] parei. Nada mais sobe hoje neste canal.")
                falhas.append(f"limite diario do YouTube: {exc}"[:180])
                avisar_limite_diario(str(exc), publicados=len(feitos))
                break
            seguidas += 1
            falhas.append(f"{alvo.id}: {type(exc).__name__}: {exc}"[:180])
            _linha(f"           youtube: FALHOU — {exc}"[:150])
            if seguidas >= 2:
                _linha("[escoar] duas falhas seguidas; PAREI aqui. "
                       "A fila continua na ordem no proximo disparo.")
                break
            continue
        estado = _tiktok_das_historias(alvo)
        _linha(f"           tiktok:  {estado or 'NAO SUBIU'}"[:110])
        feitos.append(alvo.id)
    return {"total": len(fila), "postados": feitos, "falhas": falhas}


# --------------------------------------------------------- uma rodada por vez
# DUAS RODADAS NUNCA PUBLICAM JUNTAS (conferente do 4e8df2b, 06/10/2026). A
# rodada que estoura o seu horario (rede ruim, volta final, Studio lento) e
# a do horario seguinte, disparada pelo Agendador no minuto certo, rodavam
# lado a lado: brigavam pelo perfil `youtube_web` (os dois canais usam a
# MESMA pasta; `PerfilOcupado` tira o YouTube de um deles), podiam escolher
# a MESMA parte (a linha da velha so e gravada no fim do upload, e a guarda
# da nova nao a ve) e a linha atrasada caia no horario seguinte do ledger.
# Agora toda rodada que PUBLICA segura `TRAVA_DA_RODADA` (trava de arquivo
# entre processos, `builds.travas`). A nova espera a velha ate
# `ESPERA_PELA_RODADA_ANTERIOR_S`; se ela nao terminar, a nova NAO publica
# nada (nunca sobe a parte que esta em voo), sai 1 e avisa no Telegram e no
# diario. O `--ver` e o `--instalar` nao publicam e nao esperam. A trava e
# reentrante por THREAD (memoria criacao-automatica-de-historias): dentro do
# mesmo processo ela nao separa nada, e nao precisa — o que ela separa sao
# os processos do Agendador.
#
# A DONA PENDURADA (conferentes do 0b5b6a9 e do 65dc781, 06/10/2026). Um
# Chrome/Playwright preso (`page.evaluate` sem prazo) deixa a rodada VIVA
# segurando a trava; as tarefas tinham `ExecutionTimeLimit` de 72 h, e todo
# horario seguinte esperaria 15 min, sairia 1 e avisaria. Agora quem pega a
# trava mantem a FICHA DA DONA ao lado dela (`postar__rodada.dona.json`,
# escrita atomica): pid, criacao do processo, inicio, horario da grade,
# tipo, PULSO e EM VOO.
#
# O PULSO (e nao so a idade). Toda linha que o processo dono escreve na
# saida — as dele e as dos publicadores, que narram cada passo
# ("[youtube-web] esperando o processamento...") — renova o pulso, gravado
# no maximo a cada `INTERVALO_DO_PULSO_S`. Quem trava num `page.evaluate`
# para de escrever. A rodada nova MATA a dona se, e so se: ela e de um
# horario ANTERIOR (nunca do mesmo), esta viva ha `RODADA_PENDURADA_MIN` ou
# mais, o pulso esta PARADO ha `PULSO_PARADO_MIN` ou mais, o pid ainda e
# dela (mesma hora de criacao) e ela nao e um `--tudo`. Rodada lenta mas
# viva nao morre, por mais que demore: a 1a versao (so a idade) matava uma
# saudavel que tivesse uma tentativa de mais de ~21 min (conta do
# conferente: max(28 + 2A, 42 + A) + 5 min de rede).
#
# POR QUE 20 MIN DE PULSO PARADO. O trecho calado mais longo medido e uma
# vistoria: 596 s (diario, 87 vistorias "lentas"; a postagem vistoria ate
# `TENTATIVAS` partes, e cada uma chama `_pulsar`). A pagina que nao abre
# fala a cada tentativa (90/60/60 s); o envio do TikTok cala ate 240 s.
# 20 min e o dobro do pior trecho calado medido. Os 70 min de idade ficam
# como piso: no diario a rodada mais longa durou 35,8 min, e nos ledgers
# (331 horarios desde 15/09) a ultima linha saiu 35,8 min depois do horario.
#
# EM VOO. Matar depois do clique podia publicar DE NOVO (conferente do
# 65dc781): o `page.evaluate` sem prazo esta depois do clique, nada ia ao
# disco antes da confirmacao, e quem matou escolhia o MESMO video. Agora os
# funis de publicacao (`_subir_parte_no_youtube`, `_youtube_dos_builds`,
# `_tiktok_das_historias`, `_tiktok_dos_builds`) abrem `_em_voo`, e a ficha
# grava a etapa ao ver a frase do publicador ("arquivo entregue", "publicar
# clicado"). A rodada que pega a trava le a ficha ANTERIOR antes de
# escolher qualquer coisa: voo que passou de "arquivo entregue" (a dona
# morreu, foi morta ou caiu com ele no ar) vai para a lista "a conferir"
# daquele destino — que tira o video da fila e da recuperacao — e o aviso
# diz "pode ter saido publico: confira". Se a marca nao gravar, a rodada
# NAO publica (repetir e pior que nao postar) e a ficha velha fica para a
# proxima tentar de novo.
#
# Mata so aquele python (`taskkill /F /PID`, sem /T) e depois os
# `chrome.exe` e `node.exe` DESCENDENTES dele que sobraram — filho so conta
# se nasceu DEPOIS do pai (o Windows guarda o pid do pai morto e o reusa), e
# a identidade de cada um (hora de criacao) e conferida de novo antes do
# taskkill. Nunca o Chrome de quem usa o PC.
TRAVA_DA_RODADA = "postar__rodada"
ESPERA_PELA_RODADA_ANTERIOR_S = 15 * 60.0
INTERVALO_DE_OLHAR_A_DONA_S = 5.0
RODADA_PENDURADA_MIN = 70
PULSO_PARADO_MIN = 20
INTERVALO_DO_PULSO_S = 30.0
FILHOS_QUE_MORREM_JUNTO = ("chrome.exe", "node.exe")
TIPOS_QUE_NUNCA_MORREM = ("tudo",)
DESCRICAO_DA_DONA = {
    "rodada": "a rodada da grade das {horario}",
    "tudo": "o 'escoar' do app (postar.py --tudo)",
    "recuperar": "o 'recuperar video privado' do app (postar.py --recuperar)",
    "so_youtube": "um envio avulso ao YouTube (postar.py --so-youtube)",
}
# A frase do publicador -> a etapa do voo, da mais adiantada para a menos.
# Contrato com `youtube_web.passo` e `tiktok.passo` (ha teste que procura as
# frases no fonte deles).
ETAPAS_DO_VOO = (("publicar clicado", "clicou"),
                 ("arquivo entregue", "entregue"))
_ORDEM_DA_ETAPA = {"escolhido": 0, "entregue": 1, "clicou": 2}

# A ficha em memoria quando ESTE processo segura a trava ({} quando nao).
_DONA: dict = {}


def _tipo_da_chamada(args) -> str:
    if args.tudo:
        return "tudo"
    if args.recuperar:
        return "recuperar"
    if args.so_youtube:
        return "so_youtube"
    return "rodada"


def _inicio_do_horario(agora=None):
    """O instante do horario da grade a que `agora` pertence (`grade.slot`)."""
    from datetime import datetime, timedelta
    agora = agora or datetime.now()
    hora = grade.slot(agora)
    base = agora.replace(hour=hora, minute=grade.minuto(hora), second=0,
                         microsecond=0)
    return base - timedelta(days=1) if base > agora else base


def _criacao_do_processo(pid) -> float | None:
    """Quando o processo `pid` nasceu (epoch), se ele esta VIVO; senao None.

    A hora de criacao e a identidade do processo: o Windows reaproveita pid,
    e a ficha da dona so vale para o processo que a gravou.
    """
    try:
        numero = int(pid)
    except (TypeError, ValueError):
        return None
    if numero <= 0 or os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    alca = k32.OpenProcess(0x1000, False, numero)   # QUERY_LIMITED_INFORMATION
    if not alca:
        return None
    try:
        codigo = wintypes.DWORD()
        if (not k32.GetExitCodeProcess(alca, ctypes.byref(codigo))
                or codigo.value != 259):                 # 259 = STILL_ACTIVE
            return None
        tempos = [wintypes.FILETIME() for _ in range(4)]
        if not k32.GetProcessTimes(alca, *(ctypes.byref(t) for t in tempos)):
            return None
        criado = (tempos[0].dwHighDateTime << 32) | tempos[0].dwLowDateTime
        return criado / 1e7 - 11644473600.0
    finally:
        k32.CloseHandle(alca)


def _arquivo_da_dona():
    from builds import travas
    return travas._pasta() / f"{TRAVA_DA_RODADA}.dona.json"


def _arquivo_da_reserva():
    """A ficha ANTERIOR (`.bak`): a que vale se a principal se perder."""
    caminho = _arquivo_da_dona()
    return caminho.with_name(f"{caminho.name}.bak")


def _gravar_ficha(dados: dict) -> None:
    """Escrita ATOMICA e DURAVEL, com a anterior guardada em `.bak`.

    `.tmp` com flush + `os.fsync` ANTES do `os.replace` (conferente do
    78112e5): sem o fsync, uma queda de energia logo depois da troca podia
    deixar a ficha vazia ou cheia de NUL — e este PC ja caiu (11/09). A
    principal de antes vira `.bak` (troca atomica tambem), e quem le decide
    pela `.bak` quando a principal nao serve (`_voo_anterior`).
    """
    caminho = _arquivo_da_dona()
    temporario = caminho.with_name(f"{caminho.name}.{os.getpid()}.tmp")
    with open(temporario, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(dados))
        fh.flush()
        os.fsync(fh.fileno())
    if caminho.exists():
        os.replace(caminho, _arquivo_da_reserva())
    os.replace(temporario, caminho)


def _pulsar(forcar: bool = False) -> None:
    """Renova o pulso da dona (grava no maximo a cada `INTERVALO_DO_PULSO_S`)."""
    import time
    if not _DONA:
        return
    agora = time.time()
    _DONA["pulso"] = agora
    if not forcar and agora - _DONA.get("_gravado", 0.0) < INTERVALO_DO_PULSO_S:
        return
    try:
        _gravar_ficha({k: v for k, v in _DONA.items() if not k.startswith("_")})
        _DONA["_gravado"] = agora
    except Exception:                                          # noqa: BLE001
        pass


def _gravar_dona(tipo: str) -> None:
    """A ficha de quem acabou de pegar a trava."""
    import time
    agora = time.time()
    _DONA.clear()
    _DONA.update({
        "pid": os.getpid(), "criado": _criacao_do_processo(os.getpid()),
        "inicio": agora, "pulso": agora,
        "horario": _inicio_do_horario().isoformat(timespec="minutes"),
        "tipo": tipo, "comando": " ".join(sys.argv)[:200], "em_voo": None})
    try:
        _gravar_ficha({k: v for k, v in _DONA.items() if not k.startswith("_")})
        _DONA["_gravado"] = agora
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"[postar] nao gravei a ficha da trava ({exc}); se esta "
               "rodada pendurar, a seguinte so vai esperar.")


@contextmanager
def _em_voo(canal: str, alvo_id: str, destino: str):
    """Um publicador vai rodar: a ficha diz o que esta no ar AGORA.

    Fora da trava (teste, `--ver`), nao faz nada. Na saida (normal ou por
    excecao), o voo pousa: daqui o caminho de sempre grava o ledger ou a
    lista "a conferir".
    """
    import time
    if not _DONA:
        yield
        return
    _DONA["em_voo"] = {"canal": canal, "alvo": str(alvo_id),
                       "destino": destino, "etapa": "escolhido",
                       "desde": time.time()}
    _pulsar(forcar=True)
    try:
        yield
    finally:
        _DONA["em_voo"] = None
        # O CLIQUE SEM MARCA VAI PARA A FICHA (PUB-1, 14/10/2026): a marca "a
        # conferir" que o disco recusou dentro deste voo (no publicador ou em
        # `_garantir_marca`) so existe na memoria deste processo; gravada
        # aqui, a rodada seguinte a grava antes de escolher (`_pousar_sem_
        # marca`). Todo caminho que sobe video passa por um dos quatro funis.
        pendentes = _marcas_so_na_memoria()
        if pendentes or _DONA.get("sem_marca"):
            _DONA["sem_marca"] = pendentes
        # O POUSO GRAVA DUAS VEZES (conferente do f79a894, 06/10/2026). A
        # `.bak` e sempre a gravacao ANTERIOR: com uma gravacao so, ela
        # guardava o ultimo "clicou" JA CONFIRMADO, e se a principal se
        # perdesse a rodada seguinte marcava "a conferir" um video que ja
        # tinha saido (medido as 23:47 de 06/10: principal `em_voo: null`,
        # `.bak` com a `generation_00096` no TikTok em "clicou" — e a linha
        # dela no ledger as 23:42:50). A segunda gravacao poe o pouso nas duas.
        _pulsar(forcar=True)
        _pulsar(forcar=True)


def _ao_escrever(texto: str) -> None:
    """Cada linha da saida do dono: pulso, e a etapa do voo se for a frase."""
    if not _DONA:
        return
    voo = _DONA.get("em_voo")
    if voo:
        baixo = str(texto).lower()
        for frase, etapa in ETAPAS_DO_VOO:
            if frase in baixo:
                if _ORDEM_DA_ETAPA[etapa] > _ORDEM_DA_ETAPA.get(voo["etapa"], 0):
                    voo["etapa"] = etapa
                    _pulsar(forcar=True)
                    return
                break
    _pulsar()


class _SaidaComPulso:
    """`sys.stdout` do processo dono: escreve igual e avisa `_ao_escrever`.

    Sem `buffer` de proposito: `_linha` escreve pelo `write` e tambem pulsa.
    """
    buffer = None

    def __init__(self, original):
        self._original = original

    def write(self, texto):
        resultado = self._original.write(texto)
        try:
            _ao_escrever(texto)
        except Exception:                                      # noqa: BLE001
            pass
        return resultado

    def __getattr__(self, nome):
        return getattr(self._original, nome)


def _ficha_valida(dados) -> tuple:
    """(ficha, problema): a ficha com os tipos certos, ou None e o porque."""
    import math
    from datetime import datetime

    def numero(valor):
        return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
                and math.isfinite(valor))
    if not isinstance(dados, dict) or not dados:
        return None, "nao e uma ficha"
    pid = dados.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None, f"pid invalido ({pid!r})"
    for campo in ("criado", "inicio"):
        if not numero(dados.get(campo)):
            return None, f"{campo} invalido ({dados.get(campo)!r})"
    if dados.get("pulso") is not None and not numero(dados["pulso"]):
        return None, f"pulso invalido ({dados['pulso']!r})"
    if not isinstance(dados.get("tipo"), str) or (
            dados["tipo"] not in DESCRICAO_DA_DONA):
        return None, f"tipo invalido ({dados.get('tipo')!r})"
    try:
        horario = datetime.fromisoformat(str(dados.get("horario")))
    except (TypeError, ValueError):
        return None, f"horario invalido ({dados.get('horario')!r})"
    if not isinstance(dados.get("horario"), str) or horario.tzinfo is not None:
        return None, f"horario invalido ({dados.get('horario')!r})"
    voo = dados.get("em_voo")
    if voo is not None and not (
            isinstance(voo, dict) and voo.get("canal") in CANAIS_DA_FICHA
            and isinstance(voo.get("alvo"), str) and voo.get("alvo")
            and voo.get("destino") in ("youtube", "tiktok")
            and isinstance(voo.get("etapa"), str)
            and voo["etapa"] in _ORDEM_DA_ETAPA):
        return None, f"em_voo invalido ({voo!r})"[:160]
    return dict(dados, horario_dt=horario), None


def _ler_dona(caminho=None) -> tuple:
    """(ficha valida ou None, problema ou None). Arquivo ausente: (None, None)."""
    caminho = caminho or _arquivo_da_dona()
    if not caminho.is_file():
        return None, None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except Exception as exc:                                   # noqa: BLE001
        return None, f"ficha ilegivel ({type(exc).__name__})"
    return _ficha_valida(dados)


def _voo_da_ficha(caminho) -> tuple:
    """(estado, voo, ficha valida ou None, problema) de UM arquivo de ficha.

    estado: "ausente" (o arquivo nao existe), "sei" (da para afirmar qual
    era o voo, inclusive "nenhum") ou "nao_sei" (vazio, NUL, ilegivel, voo
    torto).
    """
    if not caminho.is_file():
        return "ausente", None, None, None
    dona, problema = _ler_dona(caminho)
    if dona is not None:
        return "sei", dona.get("em_voo"), dona, None
    voo, sei = _voo_da_ficha_invalida(caminho)
    return ("sei" if sei else "nao_sei"), voo, None, problema


def _voo_anterior() -> tuple:
    """(sei?, voo, ficha para o aviso, texto do bloqueio) da rodada anterior.

    Principal primeiro; se ela sumiu ou nao da para saber, a `.bak`
    (conferente do 78112e5: queda de energia no meio da gravacao). So
    bloqueia quando nenhuma das duas responde. Sem principal e sem `.bak`
    e a primeira rodada: segue.
    """
    principal, reserva = _arquivo_da_dona(), _arquivo_da_reserva()
    estado, voo, dona, problema = _voo_da_ficha(principal)
    if problema:
        _avisar_ficha_invalida(problema)
    if estado == "sei":
        return True, voo, dona or {"em_voo": voo,
                                   "sem_marca": _sem_marca_crua(principal)}, ""
    estado_b, voo_b, dona_b, problema_b = _voo_da_ficha(reserva)
    if estado == "ausente" and estado_b == "ausente":
        return True, None, None, ""
    if estado_b == "sei":
        if estado == "nao_sei":
            _linha("[postar] a ficha da trava nao serve; decidi pela "
                   f"anterior ({reserva.name}).")
        # `pela_reserva`: a `.bak` e uma gravacao ATRAS da que se perdeu, e o
        # voo dela e o MINIMO que aconteceu (`_pousar_voo_perdido`).
        return True, voo_b, dict(dona_b or {"em_voo": voo_b,
                                            "sem_marca": _sem_marca_crua(
                                                reserva)},
                                 pela_reserva=True), ""
    return False, None, None, (
        f"a ficha da rodada anterior ({principal}) "
        + ("sumiu" if estado == "ausente" else f"esta invalida ({problema})")
        + f" e a reserva ({reserva.name}) "
        + ("nao existe" if estado_b == "ausente"
           else f"tambem nao serve ({problema_b})")
        + "; nao da para saber se havia video no ar e este horario NAO "
        "publicou. Confira os canais e apague as duas fichas para liberar")


def _sem_marca_crua(caminho) -> list:
    """O `sem_marca` de uma ficha que NAO validou (lido cru). `[]` se nao ha."""
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return []
    lista = dados.get("sem_marca") if isinstance(dados, dict) else None
    return list(lista) if isinstance(lista, list) else []


def _voo_da_ficha_invalida(caminho=None) -> tuple:
    """(voo que da para pousar ou None, sei?) de uma ficha que NAO validou.

    `sei` e False quando nao da para afirmar que nao havia voo: arquivo
    ilegivel, nao-dicionario, ou `em_voo` presente mas torto (etapa
    desconhecida, canal/alvo/destino faltando). Voo inteiro em `escolhido`
    nao pousa (nada foi entregue); sem `em_voo`, nao havia voo.
    """
    try:
        dados = json.loads((caminho or _arquivo_da_dona()).read_text(
            encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None, False
    if not isinstance(dados, dict):
        return None, False
    voo = dados.get("em_voo")
    if voo is None:
        return None, True
    inteiro = (isinstance(voo, dict)
               and voo.get("canal") in CANAIS_DA_FICHA
               and isinstance(voo.get("alvo"), str) and voo.get("alvo")
               and voo.get("destino") in ("youtube", "tiktok")
               and isinstance(voo.get("etapa"), str)
               and voo["etapa"] in _ORDEM_DA_ETAPA)
    if not inteiro:
        return None, False
    return dict(voo), True


def _avisar_ficha_invalida(problema: str) -> None:
    texto = (f"a ficha da trava da rodada esta invalida ({problema}); trato "
             "como 'sem ficha': espero, nao mato ninguem")
    _linha(f"[postar] {texto}")
    try:
        from builds import atividade
        atividade.registrar("publicacao", "aviso", texto, "builds",
                            etapa="publicar.rodada")
    except Exception:                                          # noqa: BLE001
        pass


def _descrever_dona(dona: dict | None) -> str:
    if not dona:
        return "outra publicacao (sem ficha de quem e)"
    modelo = DESCRICAO_DA_DONA.get(dona.get("tipo"), "outra publicacao")
    horario = str(dona.get("horario") or "")[11:16] or "?"
    texto = modelo.format(horario=horario)
    try:
        from datetime import datetime
        desde = datetime.fromtimestamp(float(dona["inicio"]))
        texto += f" (pid {dona.get('pid')}, desde {desde:%H:%M})"
    except (KeyError, TypeError, ValueError, OSError):
        pass
    return texto


def _pode_matar(dona: dict | None, *, agora=None, meu_horario=None,
                criacao=None) -> tuple:
    """(mata?, por que) — a decisao inteira, sem tocar em processo nenhum.

    `dona` e a ficha JA VALIDADA (`_ficha_valida`); qualquer outra coisa nao
    mata. `criacao` diz quando o pid nasceu (injetavel no teste).
    """
    import time
    if not dona or "horario_dt" not in dona:
        return False, "sem ficha da dona"
    if dona["tipo"] in TIPOS_QUE_NUNCA_MORREM:
        return False, "o escoar do app nunca e morto"
    pid = dona["pid"]
    if pid == os.getpid():
        return False, "a dona sou eu"
    meu_horario = meu_horario or _inicio_do_horario()
    if dona["horario_dt"] >= meu_horario:
        return False, "a dona e do MESMO horario (ou de um seguinte)"
    agora = time.time() if agora is None else agora
    idade_min = (agora - dona["inicio"]) / 60.0
    if idade_min < RODADA_PENDURADA_MIN:
        return False, f"viva ha {idade_min:.0f} min (< {RODADA_PENDURADA_MIN})"
    pulso = dona.get("pulso")
    parado_min = (agora - (dona["inicio"] if pulso is None else pulso)) / 60.0
    if parado_min < PULSO_PARADO_MIN:
        return False, (f"lenta mas viva: pulso de {parado_min:.0f} min atras "
                       f"(< {PULSO_PARADO_MIN})")
    nascido = (criacao or _criacao_do_processo)(pid)
    if nascido is None:
        return False, "o processo ja nao existe"
    if abs(nascido - dona["criado"]) > 2:
        return False, "o pid agora e de outro processo"
    return True, (f"pendurada: viva ha {idade_min:.0f} min, pulso parado ha "
                  f"{parado_min:.0f} min")


def _processos() -> list:
    """[{pid, pai, nome, criado}] de todos os processos (Win32_Process)."""
    script = ("Get-CimInstance Win32_Process | Select-Object ProcessId,"
              "ParentProcessId,Name,@{n='Criado';e={if ($_.CreationDate) "
              "{$_.CreationDate.ToFileTimeUtc()} else {0}}} | "
              "ConvertTo-Json -Compress")
    proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                           "-Command", script], capture_output=True,
                          timeout=60, creationflags=NO_WINDOW)
    dados = json.loads((proc.stdout or b"[]").decode("utf-8", "replace")
                       or "[]")
    if isinstance(dados, dict):
        dados = [dados]
    saida = []
    for d in dados:
        ft = int(d.get("Criado") or 0)
        saida.append({"pid": int(d.get("ProcessId") or 0),
                      "pai": int(d.get("ParentProcessId") or 0),
                      "nome": str(d.get("Name") or "").lower(),
                      "criado": ft / 1e7 - 11644473600.0 if ft else None})
    return saida


def _descendentes(pid: int, processos: list, criado: float | None) -> list:
    """Os descendentes de `pid` — filho so conta se nasceu DEPOIS do pai.

    O Windows guarda o pid do pai morto em `ParentProcessId` e reaproveita
    o numero: sem a hora, o Chrome de OUTRO pai, ja morto, que tivesse o
    mesmo pid, entraria na conta (conferente do 65dc781, `orfao.py`).
    """
    if criado is None:
        return []
    filhos, fila, vistos = [], [(int(pid), criado)], {int(pid)}
    while fila:
        pai, nasceu = fila.pop()
        for p in processos:
            if (p["pai"] == pai and p["pid"] not in vistos
                    and p.get("criado") is not None and p["criado"] >= nasceu):
                vistos.add(p["pid"])
                filhos.append(p)
                fila.append((p["pid"], p["criado"]))
    return filhos


def _taskkill(pid: int) -> None:
    subprocess.run(["taskkill", "/F", "/PID", str(int(pid))],
                   capture_output=True, timeout=60, creationflags=NO_WINDOW)


def _matar_dona(dona: dict, *, prazo_s: float = 15.0) -> dict:
    """Mata a dona pendurada e o que dela sobrou no Chrome. Devolve o laudo."""
    import time
    pid = int(dona["pid"])
    try:
        filhos = [p for p in _descendentes(pid, _processos(), dona["criado"])
                  if p["nome"] in FILHOS_QUE_MORREM_JUNTO]
    except Exception:                                          # noqa: BLE001
        filhos = []
    # A identidade ANTES do tiro: o pid ainda e o da ficha?
    nascido = _criacao_do_processo(pid)
    if nascido is not None and abs(nascido - dona["criado"]) <= 2:
        _taskkill(pid)
    fim = time.monotonic() + prazo_s
    while _criacao_do_processo(pid) is not None and time.monotonic() < fim:
        time.sleep(0.5)
    morreu = _criacao_do_processo(pid) is None
    mortos = []
    for p in filhos:
        agora = _criacao_do_processo(p["pid"])
        if agora is not None and abs(agora - p["criado"]) <= 2:
            _taskkill(p["pid"])
            mortos.append(f"{p['nome']} {p['pid']}")
    return {"pid": pid, "morreu": morreu, "filhos": mortos}


def _avisar(texto: str, *, erro: bool = True) -> None:
    """Log, diario e Telegram, nunca levanta."""
    _linha(f"[postar] {texto}")
    try:
        from builds import atividade
        atividade.registrar("publicacao",
                            atividade.ERRO if erro else "aviso",
                            texto, "builds", etapa="publicar.rodada")
    except Exception:                                          # noqa: BLE001
        pass
    try:
        _mandar_no_telegram(f"⚠ *Postagem* — {texto}")
    except Exception:                                          # noqa: BLE001
        pass


def _avisar_morte(dona: dict, laudo: dict, motivo: str) -> None:
    voo = dona.get("em_voo") or {}
    _avisar(f"matei {_descrever_dona(dona)}: {motivo}; "
            + ("morreu" if laudo["morreu"] else "NAO morreu")
            + (f"; e {len(laudo['filhos'])} processo(s) dela que sobraram "
               f"({', '.join(laudo['filhos'][:6])})" if laudo["filhos"]
               else "; nenhum Chrome dela sobrou")
            + (f". Estava com {voo['alvo']} no {voo['destino']} "
               f"({voo['etapa']})" if voo else "")
            + ". Ela pode ter deixado um rascunho no canal.")


def _voo_no_ledger(voo: dict) -> dict | None:
    """A linha PUBLICADA do voo no ledger, gravada depois do comeco dele.

    Mesmo alvo (`video_id`), mesmo destino (`plataforma`), `_saiu` (o
    criterio unico de "publicado") e `quando` >= `desde` (o segundo em que o
    voo comecou; `quando` e a hora local da escrita, sem fracao). `None`
    quando nao acha OU nao da para saber (ledger ilegivel, voo sem `desde`):
    na duvida, quem chama marca "a conferir".
    """
    from datetime import datetime
    try:
        desde = datetime.fromtimestamp(float(voo["desde"])).replace(
            microsecond=0)
        linhas = _publicados_do_canal(voo["canal"])
        for linha in reversed(linhas):
            if (str(linha.get("video_id") or "") != voo["alvo"]
                    or str(linha.get("plataforma") or "youtube")
                    != voo["destino"]):
                continue
            try:
                quando = datetime.fromisoformat(str(linha.get("quando")))
            except ValueError:
                continue
            if (quando.tzinfo is None and quando >= desde
                    and _saiu(linha)):
                return linha
    except Exception:                                          # noqa: BLE001
        return None
    return None


def _pousar_voo_perdido(anterior: dict | None) -> bool:
    """O voo que a dona anterior deixou no ar vai para "a conferir".

    True quando nao ha nada a fazer ou a marca gravou; False quando havia voo
    e a marca NAO gravou — e entao esta rodada nao publica.

    Duas excecoes ao "voo em `entregue`/`clicou` pousa" (conferente do
    f79a894, 06/10/2026):

    - VOO QUE JA ESTA NO LEDGER nao pousa: linha publicada do mesmo alvo no
      mesmo destino, gravada depois do comeco do voo (`_voo_no_ledger`). O
      video saiu e foi registrado; a fila ja nao o escolhe, e a marca seria
      so alarme falso (com Telegram). Ledger ilegivel: marca, como antes.
    - DECIDIDO PELA `.bak` (`pela_reserva`), `escolhido` tambem pousa: a
      `.bak` e uma gravacao atras da principal que se perdeu, entao o voo
      dela e o MINIMO — a principal podia ja estar em `entregue` ou
      `clicou`, e subir de novo e pior que nao postar.
    """
    voo = (anterior or {}).get("em_voo")
    minimo = 0 if (anterior or {}).get("pela_reserva") else 1
    if not voo or _ORDEM_DA_ETAPA.get(voo.get("etapa"), -1) < minimo:
        return True
    linha = _voo_no_ledger(voo)
    if linha:
        _linha(f"[postar] o voo de {voo['alvo']} no {voo['destino']} que a "
               f"ficha anterior guardava ('{voo['etapa']}') ja esta no ledger "
               f"({str(linha.get('quando'))[:16]}): saiu e foi registrado; "
               "nada a conferir.")
        return True
    etapa = (f"'{voo['etapa']}' ou depois (a ficha principal se perdeu; "
             "decidi pela anterior)" if minimo == 0
             else f"'{voo['etapa']}'")
    texto = (f"a publicacao de {voo['alvo']} no {voo['destino']} parou na "
             f"etapa {etapa} ({_descrever_dona(anterior)} nao "
             "terminou): pode ter saido publico — confira")
    try:
        from builds.publicar import desfecho
        desfecho.marcar_para_conferir(
            voo["canal"], voo["alvo"], texto, voo["destino"],
            aviso=texto, etapa="publicar.rodada", erro=True)
    except Exception as exc:                                   # noqa: BLE001
        _avisar(f"{texto}; e NAO consegui por na lista a conferir "
                f"({type(exc).__name__}: {exc}) — este horario nao publica")
        return False
    _avisar(f"{texto}. Esta na lista a conferir do {voo['destino']}; nao "
            "sobe de novo ate alguem conferir.")
    return True


def _pousar_sem_marca(anterior: dict | None) -> bool:
    """As marcas "a conferir" que a rodada anterior NAO conseguiu gravar.

    A rodada anterior deu o clique, algo falhou depois e o disco recusou a
    marca (PUB-1, 14/10/2026); ela guardou a marca na ficha da trava
    (`sem_marca`, ver `_garantir_marca` e `_em_voo`). Aqui, ANTES de qualquer
    escolha, a marca e gravada. True quando nao ha nada ou todas gravaram;
    False quando alguma NAO gravou — e entao esta rodada nao publica, e a
    ficha velha fica para a proxima tentar (como `_pousar_voo_perdido`).
    Entrada torta (nao e dicionario, canal ou destino desconhecido) e
    ignorada com aviso: nao da para marcar o que nao se sabe o que e.
    """
    pendentes = (anterior or {}).get("sem_marca") or []
    if not isinstance(pendentes, list) or not pendentes:
        return True
    from builds.publicar import desfecho
    for item in pendentes:
        if not (isinstance(item, dict)
                and item.get("canal") in CANAIS_DA_FICHA
                and item.get("destino") in ("youtube", "tiktok")
                and isinstance(item.get("alvo"), str) and item.get("alvo")):
            _linha(f"[postar] marca pendente torta na ficha anterior, "
                   f"ignorada: {item!r}"[:200])
            continue
        texto = (f"a rodada anterior clicou em publicar {item['alvo']} no "
                 f"{item['destino']} e NAO conseguiu gravar a marca a "
                 f"conferir; gravei agora: pode estar no ar — confira")
        try:
            desfecho.marcar_para_conferir(
                item["canal"], item["alvo"],
                str(item.get("estado") or texto)[:200], item["destino"],
                aviso=texto, etapa="publicar.rodada", erro=True)
        except Exception as exc:                               # noqa: BLE001
            _avisar(f"a rodada anterior clicou em publicar {item['alvo']} no "
                    f"{item['destino']} sem gravar a marca a conferir, e de "
                    f"novo ela NAO gravou ({type(exc).__name__}: {exc}) — "
                    "este horario nao publica (repetir e pior que nao postar)")
            return False
    return True


@contextmanager
def _trava_da_rodada(esperar: float | None = None, tipo: str = "rodada"):
    """`with _trava_da_rodada() as vez:` — `vez["minha"]` diz se publica.

    Tenta na hora; ocupada, olha a ficha da dona a cada
    `INTERVALO_DE_OLHAR_A_DONA_S`: pendurada (`_pode_matar`), e morta e a
    trava e tomada; senao espera ate o prazo. Com a trava na mao, o voo que
    a dona anterior deixou no ar vai para "a conferir" ANTES de qualquer
    escolha (`_pousar_voo_perdido`). `vez["dona"]` e a ultima ficha vista (o
    aviso diz QUEM segurou). Erro da propria trava (pasta de travas
    inacessivel) e "nao sei se ha outra rodada": falha FECHADA.
    """
    import time
    from contextlib import ExitStack
    from builds import travas
    prazo = ESPERA_PELA_RODADA_ANTERIOR_S if esperar is None else esperar
    vez = {"minha": False, "dona": None}
    # So a AQUISICAO fica dentro do `try`: uma excecao da rodada (que chega
    # pelo `yield`) nao pode ser confundida com erro da trava.
    pilha = ExitStack()
    try:
        fim = time.monotonic() + prazo
        avisei = invalida = False
        tentei: set = set()
        while True:
            if pilha.enter_context(travas.trava(TRAVA_DA_RODADA)):
                vez["minha"] = True
                break
            pilha.close()
            pilha = ExitStack()
            dona, problema = _ler_dona()
            vez["dona"] = dona
            if problema and not invalida:
                _avisar_ficha_invalida(problema)
                invalida = True
            mata, motivo = _pode_matar(dona)
            if mata and dona["pid"] not in tentei:
                tentei.add(dona["pid"])
                laudo = _matar_dona(dona)
                _avisar_morte(dona, laudo, motivo)
                if laudo["morreu"]:
                    continue                  # a trava caiu com ela
                motivo = "tentei matar e ela NAO morreu"
            if not avisei:
                _linha(f"[postar] {_descrever_dona(dona)} ainda segura a "
                       f"publicacao ({motivo}); espero ate {prazo:.0f} s.")
                avisei = True
            if time.monotonic() >= fim:
                break
            time.sleep(max(0.0, min(INTERVALO_DE_OLHAR_A_DONA_S,
                                    fim - time.monotonic())))
    except OSError as exc:
        pilha.close()
        pilha = ExitStack()
        _linha(f"[postar] nao consegui a trava da rodada ({exc}); nao "
               "publico.")
        vez["minha"] = False
    if vez["minha"]:
        # FICHA QUE NAO SERVE (conferentes do 9025da2 e do 78112e5): o voo
        # dela nao pode ser ignorado. Principal, depois a `.bak`; voo
        # inteiro pousa como qualquer outro; se nenhuma das duas diz, nada
        # sai e as fichas ficam para uma pessoa olhar.
        sei, _voo, anterior, bloqueio = _voo_anterior()
        if not sei:
            vez["minha"] = False
            vez["voo_preso"] = bloqueio
        elif _pousar_voo_perdido(anterior) and _pousar_sem_marca(anterior):
            _gravar_dona(tipo)
        else:
            vez["minha"] = False      # a ficha velha fica: a proxima tenta
            vez["voo_preso"] = True
    with pilha:
        try:
            yield vez
        finally:
            _DONA.clear()


def _rodada_presa(prazo: float, dona: dict | None = None,
                  voo_preso: bool = False) -> int:
    """Quem segura a trava nao terminou no prazo: nada sai, e todo mundo sabe."""
    if isinstance(voo_preso, str):
        texto = voo_preso
    elif voo_preso:
        texto = ("o video que a rodada anterior deixou no ar nao foi para a "
                 "lista a conferir; este horario NAO publicou (repetir e "
                 "pior que nao postar)")
    else:
        texto = (f"{_descrever_dona(dona)} ainda estava rodando depois de "
                 f"{prazo:.0f} s de espera; este horario NAO publicou "
                 "(nunca subo a parte que esta em voo)")
    _linha(f"[postar] {texto}")
    try:
        from builds import atividade
        atividade.registrar("publicacao", atividade.ERRO, texto, "builds",
                            etapa="publicar.rodada")
    except Exception:                                          # noqa: BLE001
        pass
    try:
        avisar([{"canal": c, "feito": False, "motivo": texto}
                for c in ("historias", "builds")])
    except Exception:                                          # noqa: BLE001
        pass
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="postar",
                                     description="uma postagem por dia")
    parser.add_argument("--ver", action="store_true",
                        help="diz o que postaria e sai")
    parser.add_argument("--instalar", action="store_true",
                        help="cria as tarefas da grade no Agendador")
    parser.add_argument("--hora", metavar="HH:MM",
                        help="instala UM horario so, em vez da grade inteira")
    parser.add_argument("--lancador", action="store_true",
                        help="so regrava o postar.cmd (nao mexe no Agendador)")
    parser.add_argument("--so", choices=("historias", "builds", "bluelock"),
                        help="posta so de um canal")
    parser.add_argument("--agora", action="store_true",
                        help="so com `--so bluelock`: leva o proximo episodio "
                             "da serie FORA do horario das 20:37 (todas as "
                             "outras guardas valem: ordem, titulo, um por "
                             "dia, a conferir)")
    parser.add_argument("--tudo", action="store_true",
                        help="escoa a fila INTEIRA de historias, uma atras da "
                             "outra (ignora a guarda de um-por-horario)")
    parser.add_argument("--limite", type=int, default=0, metavar="N",
                        help="com --tudo, para depois de N videos")
    parser.add_argument("--recuperar", action="store_true",
                        help="devolve ao ar UM video que ficou privado no "
                             "canal por defeito nosso (com --ver, lista)")
    parser.add_argument("--so-youtube", metavar="VIDEO_ID",
                        help="leva ao YouTube UMA parte de historia que so "
                             "saiu no TikTok, com as guardas de duplicata e "
                             "a vistoria (com --ver, so confere)")
    args = parser.parse_args(argv)
    if args.agora and args.so != "bluelock":
        parser.error("--agora so vale com --so bluelock")

    if args.ver or args.instalar or args.lancador:
        return _main(args)          # nao publica: nao espera ninguem
    prazo = ESPERA_PELA_RODADA_ANTERIOR_S
    with _trava_da_rodada(prazo, _tipo_da_chamada(args)) as vez:
        if not vez["minha"]:
            return _rodada_presa(prazo, vez["dona"],
                                 vez.get("voo_preso") or False)
        # O PULSO: toda linha da saida (a nossa e a dos publicadores) diz
        # "estou vivo" e marca a etapa do voo (ver `_SaidaComPulso`).
        original = sys.stdout
        sys.stdout = _SaidaComPulso(original)
        try:
            return _main(args)
        finally:
            sys.stdout = original


def _main(args) -> int:
    """O `main` de antes, ja com a trava da rodada (quando publica)."""
    if args.so_youtube:
        r = subir_so_no_youtube(args.so_youtube, so_ver=args.ver)
        _linha(json.dumps(r, ensure_ascii=False, default=str))
        return 0 if r["feito"] or (args.ver and "so vendo" in
                                   str(r.get("motivo"))) else 1

    if args.recuperar:
        r = recuperar_no_youtube(so_ver=args.ver, canal=args.so or "builds")
        if args.ver:
            _linha(f"[recuperar] {r['fila']} video(s) na fila do canal "
                   f"{r['canal']}.")
            for v in r.get("lista", []):
                _linha(f"   {v['quando'][:10]}  {v['id']:<13} "
                       f"{(v.get('video_id') or '(fora do ledger)'):<40} "
                       f"{v['titulo'][:56]}")
            if r.get("motivo"):
                _linha(f"[recuperar] {r['motivo']}")
                if r.get("detalhe"):
                    _linha(r["detalhe"])
            return 0
        if r.get("detalhe"):
            _linha(r["detalhe"])
        _linha(f"[recuperar] {'ok' if r['feito'] else 'nada feito'}"
               + (f" — {r.get('alvo')}" if r.get("alvo") else "")
               + (f" ({r['motivo']})" if r.get("motivo") else ""))
        return 0 if r["feito"] or not r["fila"] else 1

    if args.lancador:
        # SCR-4/SCR-11: regravar o .cmd (CRLF certo) sem recriar as tarefas
        _linha(f"[postar] lancador regravado: {escrever_lancador()}")
        return 0

    if args.instalar:
        fichas = ([instalar(args.hora)] if args.hora
                  else instalar_grade())
        for r in fichas:
            estado = "ok" if r["ok"] else "FALHOU"
            _linha(f"[postar] {r['tarefa']:<24} {r['hora']}  {estado}"
                   + (f"  {r['mensagem'][:70]}" if not r["ok"] else ""))
        return 0 if all(r["ok"] for r in fichas) else 1

    if args.tudo:
        r = escoar_historias(limite=args.limite, so_ver=args.ver)
        _linha()
        if args.ver:
            _linha(f"[escoar] {r['total']} video(s) na fila.")
        else:
            _linha(f"[escoar] {len(r['postados'])} de {r['total']} publicados; "
                   f"{len(r['falhas'])} falha(s).")
            for f in r["falhas"][:5]:
                _linha(f"   ! {f}")
        return 0

    # A REDE ANTES DE QUALQUER NAVEGADOR. Abrir o Chrome para descobrir que o
    # DNS nao resolve custa minutos e termina em `ERR_NAME_NOT_RESOLVED`;
    # resolver um nome custa milissegundos e responde a mesma pergunta.
    #
    # O COMECO DA RODADA E MARCADO ANTES da espera da rede (ate 300 s): as
    # janelas de reposicao contam o tempo que a rodada ja gastou, e a espera
    # e tempo gasto (conferente do 4e8df2b, 06/10/2026).
    import time as _time
    from datetime import datetime as _datetime
    comeco_da_rodada = _time.monotonic()
    slot_da_rodada = grade.slot(_datetime.now())
    if not args.ver and not esperar_a_rede():
        avisar([{"canal": c, "feito": False,
                 "motivo": "a rede nao voltou a tempo deste horario"}
                for c in ("historias", "builds")
                if not (c == "historias" and _historias_pausadas())])
        return 1

    rodados = []
    pausa = _historias_pausadas()
    if pausa and args.so in (None, "historias"):
        _linha(f"[postar] historias: {pausa}; nada sai no YouTube nem no "
               "TikTok (inclusive a recuperacao).")
    import functools
    funcoes = {"historias": postar_historia, "builds": postar_build,
               "bluelock": functools.partial(postar_bluelock,
                                             agora=args.agora)}
    # A SERIE DO BLUE LOCK RODA POR ULTIMO e nunca muda a ordem dos outros dois
    # (`_ordem_dos_canais` segue igual); fora das 20:37 devolve uma ficha
    # calada (`fora_da_grade`) sem ler ledger nem catalogo.
    for canal in (*_ordem_dos_canais(), "bluelock"):
        funcao = funcoes[canal]
        if args.so not in (None, canal):
            continue
        if canal == "historias" and pausa:
            continue
        # Cada canal passa por `_rodar_canal` (que nunca levanta e avisa a
        # cota no Telegram) e, se a REDE derrubou um destino, e reposto
        # neste mesmo horario (`_publicar_canal`, 05/10/2026).
        rodados.append((canal, funcao, _publicar_canal(
            canal, funcao, so_ver=args.ver, comeco=comeco_da_rodada,
            slot=slot_da_rodada)))
    # E o que a rede derrubou volta UMA vez no fim, se um canal de depois
    # publicou sem queda (`_volta_final`, 06/10/2026).
    resultados = _volta_final(rodados, so_ver=args.ver,
                              comeco=comeco_da_rodada, slot=slot_da_rodada)
    # A ORDEM DE RODAR NAO MUDA A FICHA: relatorio, Telegram e codigo de
    # saida continuam historias e depois builds (`_ordem_dos_canais`).
    resultados = sorted(resultados, key=lambda r: ORDEM_DO_RELATORIO.index(
        r.get("canal")) if r.get("canal") in ORDEM_DO_RELATORIO else 99)
    # O CANAL FORA DA SUA GRADE NAO TENTOU (20/10/2026, builds em tres
    # horarios): a ficha dele sai do relatorio, do Telegram e do codigo de
    # saida — sete rodadas por dia avisando "builds: nao saiu" seriam alarme
    # falso, e a rodada so com historias que publicou nao pode sair 1.
    for r in resultados:
        if r.get("fora_da_grade"):
            _linha(f"[-------] {r['canal']:<10} fora da grade: "
                   f"{r.get('motivo', '')}"[:160])
    resultados = [r for r in resultados if not r.get("fora_da_grade")]
    # O TikTok que acabou de cair por REDE nao e chamado de novo nesta
    # rodada pela recuperacao nem pela reserva: em 05/10/2026, as 09:4x, a
    # recuperacao rodou segundos depois do timeout, no mesmo processo, e
    # repetiu o mesmo erro (3 timeouts em 9 min). A proxima rodada tenta.
    tiktok_caiu_por_rede = any("tiktok" in _derrubados_pela_rede(r)
                               for r in resultados)

    for r in resultados:
        marca = "POSTADO" if r.get("feito") else "-------"
        alvo = r.get("alvo") or r.get("veria") or ""
        _linha(f"[{marca}] {r['canal']:<10} {alvo}")
        if r.get("titulo"):
            _linha(f"           {r['titulo'][:76]}")
        if r.get("url"):
            _linha(f"           youtube: {r['url']}")
        if r.get("youtube_devido"):
            # A divida do YouTube (06/10/2026): o alvo acima e o do YouTube.
            _linha(f"           youtube: parte devida (saiu no TikTok em "
                   f"{str(r['youtube_devido'])[:16]})")
        if r.get("tiktok_alvo") or r.get("veria_tiktok"):
            _linha(f"           tiktok leva outra parte: "
                   f"{r.get('tiktok_alvo') or r.get('veria_tiktok')}")
        if r.get("feito"):
            # O TikTok aparece SEMPRE que houve postagem, inclusive quando
            # falhou: um destino que some do relatorio e um destino que passa
            # 49 publicacoes vazio sem ninguem notar.
            estado = r.get("tiktok")
            if r.get("tiktok_fora_da_grade"):
                estado = "fora da grade do TikTok neste horario"
            elif r.get("so_youtube"):
                estado = "ja saiu neste horario"
            _linha(f"           tiktok:  {estado or 'NAO SUBIU'}"[:96])
        if not r.get("feito"):
            _linha(f"           {r.get('motivo', '')}")
        for recusado in r.get("recusados") or []:
            _linha(f"   pulado: {recusado}")
    # A RECUPERACAO VEM DEPOIS das publicacoes do horario, e nunca no lugar
    # delas: o vídeo da vez e o que mantem as duas plataformas em sincronia.
    # Este passo so limpa o atraso que ficou de rodadas em que o TikTok
    # falhou — e falha dele nao era tentada de novo nunca (16/09/2026).
    #
    # UM POR CANAL: builds entraram em 16/09 e tinham o buraco maior — a fila
    # de builds descarta quem ja tem `url` em qualquer plataforma, entao um
    # build que falhasse no TikTok saia dela para sempre.
    for canal in ("historias", "builds"):
        if args.so not in (None, canal):
            continue
        if canal == "historias" and pausa:
            continue
        if tiktok_caiu_por_rede and not args.ver:
            _linha(f"[postar] recuperacao do TikTok ({canal}) fica para a "
                   "proxima rodada: o TikTok acabou de cair por rede.")
            continue
        if not args.ver and not _cabe_antes_do_proximo(
                f"recuperacao do TikTok ({canal})"):
            continue
        try:
            recuperado = recuperar_no_tiktok(so_ver=args.ver, canal=canal)
            if recuperado.get("desfecho") == "infraestrutura":
                # A recuperacao de um canal caiu por maquina/rede: a do
                # proximo canal e a reserva bateriam na mesma parede.
                tiktok_caiu_por_rede = True
            if recuperado.get("fila"):
                if args.ver:
                    _linha(f"[postar] {recuperado['fila']} atrasado(s) no "
                           f"TikTok ({canal}); "
                           f"levaria {recuperado.get('veria')}.")
                else:
                    marca = ("recuperado" if recuperado.get("feito")
                             else "NAO subiu")
                    _linha(f"[postar] TikTok atrasado ({canal}): {marca} "
                           f"{recuperado.get('alvo')} "
                           f"(restam {recuperado['fila'] - 1})")
        except Exception as exc:                               # noqa: BLE001
            _linha(f"[postar] recuperacao do TikTok ({canal}) falhou "
                   f"({type(exc).__name__}: {exc})"[:140])

    # A RECUPERACAO DO YOUTUBE E OUTRA COISA da recuperacao do TikTok, apesar
    # do nome: la o video nunca chegou ao destino; aqui ele CHEGOU e ficou
    # privado, porque o clique em publicar nao foi confirmado e o Studio o
    # deixou como rascunho. Sao 16 videos prontos parados no canal de builds,
    # o mais velho desde 31/08 — render, capa e descricao ja pagos.
    #
    # ELA NAO TIRA O LUGAR DA RODADA, e essa e uma escolha com custo: no
    # horario em que recupera, o canal recebe DOIS videos no YouTube em vez
    # de um. Aceito porque sao ~1,6 dia de dobra, todos de conteudo distinto,
    # num canal que ja posta dez por dia — diferente da enxurrada de 16/09 no
    # TikTok, que era uma serie so ocupando onze horarios. O outro desenho
    # (recuperar NO LUGAR do video novo) deixaria o canal dois dias sem nada
    # novo, que e pior para quem assiste.
    #
    # E o TIKTOK NAO ENTRA: estes videos ja passaram por la, ou vao entrar
    # pela fila de atraso, que le o ledger. Este passo e so do YouTube.
    # SO NOS HORARIOS DOS BUILDS (20/10/2026): o privado que volta ao ar e um
    # video a mais no YouTube do canal; fora dos tres horarios ele furaria o
    # "3 por dia em horario fixo" do plano.
    fora_do_youtube_dos_builds = _fora_da_grade_do_canal("builds", "youtube")
    if args.so in (None, "builds") and fora_do_youtube_dos_builds:
        _linha(f"[postar] recuperacao do YouTube: {fora_do_youtube_dos_builds}"
               [:160])
    elif args.so in (None, "builds") and (
            args.ver or _cabe_antes_do_proximo("recuperacao do YouTube")):
        try:
            volta = recuperar_no_youtube(so_ver=args.ver, canal="builds")
            if volta.get("fila"):
                if args.ver:
                    _linha(f"[postar] {volta['fila']} privado(s) no YouTube; "
                           f"devolveria {volta.get('veria')}.")
                else:
                    marca = "de volta ao ar" if volta.get("feito") else "NAO"
                    _linha(f"[postar] privado no YouTube: {marca} "
                           f"{volta.get('alvo')} "
                           f"(restam {volta['fila'] - 1})")
            elif volta.get("motivo"):
                _linha(f"[postar] recuperacao do YouTube parada: "
                       f"{volta['motivo']}"[:140])
        except Exception as exc:                               # noqa: BLE001
            _linha(f"[postar] recuperacao do YouTube falhou "
                   f"({type(exc).__name__}: {exc})"[:140])

    # A RESERVA E A ULTIMA A FALAR. Ela so existe para buraco: se a rodada e a
    # recuperacao ja levaram um build ao TikTok, nao ha buraco nenhum.
    if args.so in (None, "builds") and tiktok_caiu_por_rede and not args.ver:
        _linha("[postar] reserva do TikTok fica para a proxima rodada: o "
               "TikTok acabou de cair por rede.")
    elif args.so in (None, "builds") and (
            args.ver or _cabe_antes_do_proximo("reserva do TikTok")):
        try:
            da_reserva = publicar_da_reserva(so_ver=args.ver)
            if da_reserva.get("reserva"):
                if args.ver:
                    _linha(f"[postar] reserva do TikTok: "
                           f"{da_reserva['reserva']} build(s) de gordura; "
                           f"levaria {da_reserva.get('veria')}.")
                else:
                    marca = ("publicado" if da_reserva.get("feito")
                             else "NAO subiu")
                    _linha(f"[postar] reserva do TikTok: {marca} "
                           f"{da_reserva.get('alvo')} "
                           f"(restam {da_reserva['reserva'] - 1})")
        except Exception as exc:                               # noqa: BLE001
            _linha(f"[postar] reserva do TikTok falhou "
                   f"({type(exc).__name__}: {exc})"[:140])

    _linha()
    # EM VIDEOS E EM DIAS, e o que falta ate SEGUNDA 07h (o lote semanal,
    # 30/09/2026): "tenho 1 dia" nao diz se a semana fecha.
    try:
        for texto in linhas_do_estoque(estoque_do_lote()):
            _linha(texto)
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"  gordura: nao deu para contar ({type(exc).__name__})")
    if args.ver:
        try:
            for canal, f in frescor_do_estoque().items():
                velho = ("?" if f["mais_velho"] is None
                         else _dias(f["mais_velho"]))
                _linha(f"  frescor {canal:<10} o mais velho tem {velho} "
                       f"dia(s); {f['acima']} de {f['videos']} acima de "
                       f"{PRAZO_DE_FRESCOR_DIAS}")
        except Exception as exc:                               # noqa: BLE001
            _linha(f"  frescor: nao deu para medir ({type(exc).__name__})")
    consertadas = consertadas_por_canal() if args.ver else {}
    for canal, quantos in retidos_por_canal().items():
        if quantos:
            _linha(f"  retidos {canal:<10} {quantos:>4} parte(s) (a IA "
                   "reprovou ou ninguem assistiu; so no lugar do vazio)")
            if consertadas.get(canal, 0) > 0:
                _linha(f"    consertadas      {consertadas[canal]:>4} delas "
                       "(o reparo refez as cenas; falta alguem assistir)")
    # SEPARADA DA GORDURA, nunca somada a ela. Estes builds ja estao no ar no
    # YouTube: eles nao sao estoque para publicar, so alcance que falta ser
    # colhido no segundo destino. Somar os dois numeros faria o painel dizer
    # que ha mais video do que ha.
    try:
        reserva = len(reserva_do_tiktok())
    except Exception:                                          # noqa: BLE001
        reserva = 0
    if reserva:
        estado = ("" if RESERVA_LIGADA else "  <<< DESLIGADA")
        _linha(f"  reserva TikTok    {reserva:>4} build(s) "
               f"(so o segundo destino; ja estao no YouTube){estado}")
    # AVISA SEMPRE, e nao so quando deu certo. Era `if any(feito)`, e foi por
    # isso que a noite de 11/09/2026 passou inteira calada: as rodadas que
    # publicaram ZERO eram justamente as que precisavam avisar.
    if not args.ver:
        avisar(resultados)
        # NA NOITE DE QUARTA, e so nela (a funcao olha o relogio antes de
        # contar qualquer coisa): o lote chegou ao alvo? Nunca derruba a
        # rodada nem mexe no codigo de saida.
        try:
            avisar_lote_nao_fechou()
        except Exception as exc:                               # noqa: BLE001
            _linha(f"[postar] aviso do lote falhou ({type(exc).__name__})")
    # A METRICA SAIU DAQUI em 13/09/2026. A coleta do TikTok segura o Studio
    # por ate 12 minutos, e rodava na postagem das 06:07, no comeco do dia.
    # Agora ela e servico da madrugada (`agenda._servico_da_noite`), junto com
    # o resto do trabalho pesado. `_atualizar_metricas` fica para quem quiser
    # rodar na mao.

    # O CODIGO DE SAIDA DIZ A VERDADE. Era `return 0` fixo, e o Agendador
    # registrou SUCESSO nas tres rodadas que publicaram nada — o historico do
    # Windows era a ultima coisa que ainda podia denunciar, e mentia.
    #
    # `tentou` e o que separa "falhei" de "nao era comigo": com `--so builds`
    # a lista de historias nem roda, e uma rodada que nao tentou nada nao
    # falhou em nada.
    #
    # O `--ver` NAO PUBLICA, entao "nada saiu" nao e falha dele: ate
    # 05/10/2026 a regra abaixo valia tambem aqui e todo retrato saia 1 (o
    # app mostrava "erro / saiu 1"). No `--ver`, o 1 diz uma coisa so: um
    # canal levantou excecao (`_rodar_canal`). Fila vazia e retrato: 0.
    if args.ver:
        return 1 if any(r.get("excecao") for r in resultados) else 0
    tentou = bool(resultados)
    if tentou and not any(r.get("feito") for r in resultados):
        return 1
    return 0


if __name__ == "__main__":
    # `--saida ARQUIVO` pela regra unica (`builds.saida_da_tarefa`, SCR-12):
    # pasta do log criada; `--saida` sem arquivo sai 2 e avisa no diario.
    from builds import saida_da_tarefa
    argumentos, saida = saida_da_tarefa.abrir(sys.argv, "publicacao")
    if saida is not None:
        sys.stdout = sys.stderr = _SaidaDatada(saida)
    raise SystemExit(main(argumentos[1:]))
