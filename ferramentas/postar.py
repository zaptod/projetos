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
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TAREFA = "NeuralFights_postar"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# UM VIDEO EM CADA HORARIO DA GRADE, e nao um por dia — correcao dele em
# 09/09/2026. Sao os mesmos horarios em que a agenda CRIA historia, e isso e
# de proposito: criar e publicar no mesmo ritmo e o que mantem o estoque
# estavel em vez de crescer sem sair.
#
# O `:07` evita o minuto cheio, em que todo agendador do mundo dispara — e
# tambem afasta a postagem da criacao, que roda em ponto e usa as mesmas
# contas de navegador.
HORAS_PADRAO = (6, 7, 8, 10, 12, 15, 17, 20)
MINUTO_PADRAO = 7
HORA_PADRAO = "17:07"        # compatibilidade com quem passa --hora


def _linha(texto: str = "") -> None:
    sys.stdout.buffer.write((texto + "\n").encode("utf-8", "replace"))


# --------------------------------------------------------------- historias
# Quantos candidatos a fila pode descartar antes de desistir do dia. Um teto
# existe porque cada vistoria decodifica o mp4: sem ele, um acervo todo
# reprovado viraria meia hora de ffmpeg no meio da noite.
TENTATIVAS = 6


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

    Dentro de uma historia, sempre a MENOR parte que falta.
    """
    from contos.publicar import catalogo, serie

    ja = {l.get("video_id") for l in serie.publicados() if l.get("url")}
    videos = [v for v in catalogo.listar() if v.perfil == "celular"]
    comecadas = {v.fonte_id for v in videos if v.id in ja}
    pendentes = [v for v in videos if v.id not in ja]
    return sorted(pendentes, key=lambda v: (
        0 if v.fonte_id in comecadas else 1,   # terminar antes de comecar
        v.fonte_id if v.fonte_id in comecadas  # entre as comecadas: a mais velha
        else _ao_contrario(v.fonte_id),        # entre as novas: a mais nova
        v.parte or 0))


def _ao_contrario(texto: str) -> str:
    """Chave que ordena ao contrario um id crescente (`historia_00010`).

    `sorted` nao aceita `reverse` por campo, e inverter o numero e mais
    honesto do que multiplicar por -1 um id que nem sempre e numero.
    """
    numero = "".join(c for c in texto if c.isdigit())
    return f"{10 ** 9 - int(numero or 0):012d}"


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
    for alvo in fila_de_historias()[:TENTATIVAS]:
        if not vistoriar:
            return alvo, recusados
        laudo = qualidade.vistoriar_parte(alvo.fonte_id, alvo.parte,
                                          alvo.caminho,
                                          R.carregar(alvo.fonte_id))
        if laudo["ok"]:
            return alvo, recusados
        recusados.append(f"{alvo.id}: {'; '.join(laudo['erros'])[:120]}")
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

    A janela e a HORA DO RELOGIO porque a grade nunca tem dois horarios na
    mesma hora: 6, 7 e 8 sao seguidos, e isso basta para separa-los.

    A fonte e o LEDGER, e nao um arquivo de controle novo: ele ja e a verdade
    sobre o que foi publicado, e uma segunda fonte que discordasse dele seria
    pior do que nao ter nenhuma.

    POR PLATAFORMA, e nao so por canal: o mesmo video vai para o YouTube E
    para o TikTok no mesmo horario, e uma guarda cega ao destino faria a
    primeira postagem bloquear a segunda.
    """
    from datetime import datetime
    agora = agora or datetime.now()
    marca = agora.strftime("%Y-%m-%dT%H")
    alvo = str(plataforma).lower()
    for linha in _publicados_do_canal(canal):
        if not str(linha.get("quando") or "").startswith(marca):
            continue
        # Linha antiga, de antes de o registro guardar plataforma, conta como
        # YouTube: era o unico destino que existia.
        if str(linha.get("plataforma") or "youtube").lower() == alvo:
            return linha
    return None


def _publicados_do_canal(canal: str) -> list:
    try:
        if canal == "historias":
            from contos.publicar import serie
            return serie.publicados()
        from builds.publicar import metricas
        return metricas.publicados()
    except Exception:                                          # noqa: BLE001
        return []


def _ja_foi_neste_horario(canal: str, plataforma: str = "youtube",
                          agora=None) -> dict | None:
    """A resposta pronta de "ja publiquei neste disparo".

    `agora` e injetavel para o teste nao depender do relogio da maquina —
    uma guarda que so da para testar as 17h nao e uma guarda testada.
    """
    feito = publicou_neste_horario(canal, plataforma, agora)
    if feito is None:
        return None
    hora = str(feito.get("quando") or "")[11:16]
    return {"canal": canal, "plataforma": plataforma,
            "feito": False, "repetido": True,
            "motivo": f"ja publiquei as {hora} no {plataforma} "
                      f"({feito.get('video_id')}). Nao repito o disparo."}


def postar_historia(*, so_ver: bool = False) -> dict:
    from contos.publicar import catalogo, serie

    # UMA GUARDA POR DESTINO, e nao uma para a rodada. Se o YouTube ja saiu
    # nesta hora, o TikTok ainda nao — e a versao que retornava aqui fazia o
    # sucesso do primeiro destino cancelar o segundo. Quando so falta o
    # TikTok, o video e o MESMO que foi para o YouTube: os dois canais tem que
    # mostrar a mesma coisa, e assim o TikTok recupera o atraso sozinho.
    ja_yt = None if so_ver else publicou_neste_horario("historias", "youtube")
    ja_tk = None if so_ver else publicou_neste_horario("historias", "tiktok")
    if ja_yt and ja_tk:
        return _ja_foi_neste_horario("historias", "youtube")
    if ja_yt:
        alvo = _video_por_id(ja_yt.get("video_id"))
        if alvo is None:
            return {"canal": "historias", "feito": False,
                    "motivo": f"o video {ja_yt.get('video_id')} saiu no "
                              "YouTube mas nao esta mais no catalogo"}
        _linha(f"[postar] historias: YouTube ja saiu nesta hora; "
               f"levando {alvo.id} so para o TikTok.")
        return {"canal": "historias", "feito": True, "alvo": alvo.id,
                "titulo": alvo.titulo, "url": ja_yt.get("url") or "",
                "parte": alvo.parte, "partes": alvo.partes,
                "visibilidade": _visibilidade_das_historias(),
                "so_tiktok": True, "tiktok": _tiktok_das_historias(alvo)}
    alvo, recusados = proxima_historia()
    if alvo is None:
        motivo = "nao ha parte publicavel"
        if recusados:
            motivo += " — recusadas: " + " | ".join(recusados[:3])
        return {"canal": "historias", "feito": False, "motivo": motivo}
    if so_ver:
        return {"canal": "historias", "feito": False, "veria": alvo.id,
                "titulo": alvo.titulo, "recusados": recusados,
                "motivo": "so vendo"}
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
    url, cota = "", None
    try:
        url = catalogo.publicar_youtube(alvo, visibilidade)
        serie.registrar(alvo, url, "youtube", None,
                        {"por": "postar.py", "visibilidade": visibilidade})
    except Exception as exc:                                   # noqa: BLE001
        if not _e_limite_diario(exc):
            raise
        cota = str(exc)
        _linha(f"[postar] historias: YouTube na cota ({exc}). "
               "Sigo para o TikTok — ele nao tem esse limite.")
        avisar_limite_diario(f"canal historias: {exc}")
    ficha = {"canal": "historias", "feito": bool(url), "alvo": alvo.id,
             "titulo": alvo.titulo, "url": url,
             "parte": alvo.parte, "partes": alvo.partes,
             "visibilidade": visibilidade, "recusados": recusados}
    if cota:
        ficha["motivo"] = f"YouTube na cota: {cota}"[:200]
        ficha["cota_youtube"] = True
    ficha["tiktok"] = "" if ja_tk else _tiktok_das_historias(alvo)
    # Deu TikTok e nao deu YouTube: a rodada fez alguma coisa, e o relatorio
    # tem que dizer isso em vez de chamar tudo de falha.
    if ficha["tiktok"]:
        ficha["feito"] = True
    return ficha


def _video_por_id(video_id: str):
    """O item do catalogo com aquele id. `None` se ele nao existe mais."""
    from contos.publicar import catalogo
    try:
        return next((v for v in catalogo.listar() if v.id == video_id), None)
    except Exception:                                          # noqa: BLE001
        return None


def _tiktok_das_historias(alvo) -> str:
    """Mesmo video, segundo destino. Nunca derruba a postagem do YouTube.

    O TikTok nao tem API de post: e automacao de navegador na conta dele, e
    quebra quando o site muda. Deixar isso derrubar a rodada faria o YouTube
    — que ja subiu — parecer que falhou.
    """
    from contos.publicar import catalogo, serie
    try:
        estado = catalogo.publicar_tiktok(alvo, postar=True, log=_linha)
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"   tiktok: NAO subiu ({type(exc).__name__}: {exc})"[:200])
        return ""
    # O REGISTRO E AQUI, e nao dentro do `tiktok.publicar`. La ele chama
    # `metricas.registrar_publicado(canal="historias")`, que DESCARTA tudo que
    # nao e do canal `builds` — entao uma postagem de historia no TikTok nunca
    # ficava gravada em lugar nenhum, e a guarda de um-por-horario nunca a
    # veria. Foi assim que os dois TikToks passaram 49 publicacoes zerados.
    from builds.publicar import tiktok as _tk
    if _tk.confirmado(estado):
        serie.registrar(alvo, estado, "tiktok", None,
                        {"por": "postar.py", "visibilidade": "public"})
    return estado


def _visibilidade_das_historias() -> str:
    """A visibilidade do config, com `public` como queda — nunca `None`.

    `None` funcionava na publicacao (cada backend resolve pelo config), mas
    era veneno no registro: gravava `null` e a linha deixava de responder a
    unica pergunta que ela existe para responder.
    """
    try:
        from contos.publicar.catalogo import carregar_config
        alvo = (carregar_config() or {}).get("visibilidade")
    except Exception:                                          # noqa: BLE001
        alvo = None
    return str(alvo or "public")


# ------------------------------------------------------------------ builds
def proximo_build():
    from builds.publicar import catalogo as C
    from builds.publicar import metricas

    ja = {l.get("video_id") for l in metricas.publicados() if l.get("url")}
    pendentes = [v for v in C.listar()
                 if v.id not in ja and getattr(v, "perfil", "") == "celular"]
    if not pendentes:
        return None
    # o mais ANTIGO primeiro: o catalogo vem do mais novo para o mais velho
    return pendentes[-1]


def postar_build(*, so_ver: bool = False) -> dict:
    from builds.publicar import youtube

    # Uma guarda por DESTINO, igual as historias: o YouTube ter saido nesta
    # hora nao pode cancelar o TikTok.
    ja_yt = None if so_ver else publicou_neste_horario("builds", "youtube")
    ja_tk = None if so_ver else publicou_neste_horario("builds", "tiktok")
    if ja_yt and ja_tk:
        return _ja_foi_neste_horario("builds", "youtube")
    if ja_yt:
        alvo = _build_por_id(ja_yt.get("video_id"))
        if alvo is None:
            return {"canal": "builds", "feito": False,
                    "motivo": f"o video {ja_yt.get('video_id')} saiu no "
                              "YouTube mas nao esta mais no catalogo"}
        _linha(f"[postar] builds: YouTube ja saiu nesta hora; "
               f"levando {alvo.id} so para o TikTok.")
        return {"canal": "builds", "feito": True, "alvo": alvo.id,
                "titulo": alvo.titulo, "url": ja_yt.get("url") or "",
                "so_tiktok": True, "tiktok": _tiktok_dos_builds(alvo)}
    alvo = proximo_build()
    if alvo is None:
        return {"canal": "builds", "feito": False,
                "motivo": "nao ha video pendente"}
    if so_ver:
        return {"canal": "builds", "feito": False, "veria": alvo.id,
                "titulo": alvo.titulo, "motivo": "so vendo"}
    # `publicar_como_configurado` JA REGISTRA — e a porta unica, e o registro
    # mora dentro dela justamente para nenhum chamador esquecer. Chamar
    # `registrar_publicado` aqui de novo gravava a MESMA publicacao duas
    # vezes, e a segunda linha saia sem `visibilidade` (o `extra` e montado la
    # dentro): o ledger dizia `public` numa linha e `null` na seguinte, para o
    # mesmo video. Foi assim nos dois builds de 08/09/2026.
    url = youtube.publicar_como_configurado(alvo, canal="builds",
                                            visibilidade="public", log=_linha)
    ficha = {"canal": "builds", "feito": True, "alvo": alvo.id,
             "titulo": alvo.titulo, "url": url}
    ficha["tiktok"] = "" if ja_tk else _tiktok_dos_builds(alvo)
    return ficha


def _build_por_id(video_id: str):
    """O item do catalogo de builds com aquele id. `None` se sumiu."""
    from builds.publicar import catalogo as C
    try:
        return next((v for v in C.listar() if v.id == video_id), None)
    except Exception:                                          # noqa: BLE001
        return None


def _tiktok_dos_builds(alvo) -> str:
    """Mesmo video, segundo destino. Aqui o registro E de dentro.

    Diferente das historias: `tiktok.publicar` chama
    `metricas.registrar_publicado(canal="builds")`, e para o canal `builds`
    esse registro vale — entao gravar de novo aqui duplicaria a linha, que e
    o defeito que ja custou uma limpeza de ledger em 09/09/2026.
    """
    from builds.publicar import tiktok as _tk
    try:
        # `postar=True` EXPLICITO. O config tem `postar_automatico: false`, que
        # e o certo para o botao do painel — la a ultima palavra e dele. A
        # grade automatica nao tem quem clique, entao ela diz o que quer.
        return _tk.publicar(alvo, postar=True, canal="builds",
                            progresso=lambda t: _linha(f"   {t}"))
    except Exception as exc:                                   # noqa: BLE001
        _linha(f"   tiktok: NAO subiu ({type(exc).__name__}: {exc})"[:200])
        return ""


# ------------------------------------------------------------------ tarefa
def escrever_lancador() -> Path:
    destino = RAIZ / "postar.cmd"
    saida = RAIZ / "outputs" / "postar.txt"
    saida.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        "@echo off\r\n"
        "rem Postagem diaria: um video de cada canal.\r\n"
        "rem Gerado por: python ferramentas/postar.py --instalar\r\n"
        f'cd /d "{RAIZ}"\r\n'
        f'"{sys.executable}" -u -X utf8 ferramentas\\postar.py '
        f'>> "{saida}" 2>&1\r\n',
        encoding="utf-8")
    return destino


def nome_da_tarefa(hora: int) -> str:
    return f"{TAREFA}_{int(hora):02d}"


def instalar_grade(horas=None) -> list[dict]:
    """Uma tarefa por HORARIO da grade. Devolve o que deu em cada uma."""
    horas = list(horas or HORAS_PADRAO)
    # A antiga era uma so, sem numero no nome. Se ela ficar, o dia ganha uma
    # postagem a mais as 17:07 alem da tarefa `_17` — duas no mesmo horario.
    subprocess.run(["schtasks", "/Delete", "/TN", TAREFA, "/F"],
                   capture_output=True, timeout=60, creationflags=NO_WINDOW)
    return [instalar(f"{int(h):02d}:{MINUTO_PADRAO:02d}", nome=nome_da_tarefa(h))
            for h in horas]


def instalar(hora: str = HORA_PADRAO, *, nome: str | None = None) -> dict:
    lancador = escrever_lancador()
    nome = nome or TAREFA
    # SEM `text=True`: o schtasks escreve na pagina de codigo do console
    # (cp850/cp1252 aqui) e o Python assume UTF-8 — o "Ê" de "ÊXITO" virava
    # `UnicodeDecodeError` dentro da thread leitora do subprocess, no meio de
    # uma instalacao que tinha dado certo. Mesma familia do `-X utf8` que o
    # resto do projeto ja carrega.
    proc = subprocess.run(
        ["schtasks", "/Create", "/TN", nome, "/TR", f'"{lancador}"',
         "/SC", "DAILY", "/ST", hora, "/RL", "LIMITED", "/F"],
        capture_output=True, timeout=60, creationflags=NO_WINDOW)
    saida = (proc.stdout or b"").decode("utf-8", "replace")
    erro = (proc.stderr or b"").decode("utf-8", "replace")
    ficha = {"tarefa": nome, "hora": hora, "ok": proc.returncode == 0,
             "mensagem": (saida or erro).strip()}
    if ficha["ok"]:
        # Sem isto a postagem diaria herda os padroes do Windows: na bateria
        # ela nem comeca, e um horario perdido nunca volta — que e o oposto
        # de "pelo menos um video novo por dia". Ver builds/tarefas_windows.py.
        from builds import tarefas_windows
        ajuste = tarefas_windows.endurecer(nome)
        ficha["ajustada"] = ajuste["ok"]
        if not ajuste["ok"]:
            ficha["mensagem"] = (
                f"{ficha['mensagem']} (criada, mas os ajustes de bateria e de "
                f"horario perdido falharam: {ajuste['mensagem']})").strip()
    return ficha


# Abaixo disto o canal corre risco de ficar sem video novo. Nao e o momento
# de agir — e o momento de AVISAR, porque uma historia leva ~2h para nascer e
# o build depende do outro projeto: descobrir no dia em que acabou e tarde.
#
# UM DIA, e nao duas semanas: era 14 ate 10/09/2026, quando ele pediu "gordura
# de apenas um dia em tudo, mas totalmente nova". Com a meta em um dia, alertar
# a partir de duas semanas seria alertar sempre — e alarme que toca sempre
# ninguem escuta. Aqui o piso e o proprio alvo: abaixo de um dia, avisa.
PISO_DE_ALERTA = 1


def pendentes_por_canal() -> dict:
    """Quantos VIDEOS prontos cada canal ainda tem para publicar."""
    saida = {}
    try:
        saida["historias"] = len(fila_de_historias())
    except Exception:                                          # noqa: BLE001
        saida["historias"] = -1
    try:
        from builds.publicar import catalogo as C, metricas
        ja = {l.get("video_id") for l in metricas.publicados() if l.get("url")}
        saida["builds"] = len([v for v in C.listar() if v.id not in ja
                               and getattr(v, "perfil", "") == "celular"])
    except Exception:                                          # noqa: BLE001
        saida["builds"] = -1
    return saida


def estoque(por_dia: int | None = None) -> dict:
    """Quantos DIAS de video pronto cada canal tem.

    A CONTA MUDOU EM 09/09/2026 e a antiga passaria a mentir por 8x. Ela dizia
    "um video por dia, entao um pendente = um dia" — e a grade passou a ter
    OITO horarios (6, 7, 8, 10, 12, 15, 17, 20). Os mesmos 55 pendentes que
    eram "55 dias" viraram sete.

    Dividir e o conserto obvio, e ele importa porque o PISO_DE_ALERTA existe
    justamente para avisar ANTES de faltar: com a conta velha o alerta so
    dispararia quando ja faltasse menos de dois dias de verdade.
    """
    por_dia = int(por_dia or len(HORAS_PADRAO)) or 1
    dias = {}
    for canal, quantos in pendentes_por_canal().items():
        dias[canal] = quantos if quantos < 0 else quantos // por_dia
    return dias


CANAIS = {"historias": {"emoji": "📖", "rotulo": "histórias"},
          "builds": {"emoji": "⚔️", "rotulo": "builds"}}


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
    from datetime import datetime
    agora = agora or datetime.now()
    minuto = agora.hour * 60 + agora.minute
    for h in HORAS_PADRAO:
        if h * 60 + MINUTO_PADRAO > minuto:
            return f"{h:02d}:{MINUTO_PADRAO:02d}"
    return f"{HORAS_PADRAO[0]:02d}:{MINUTO_PADRAO:02d} (amanhã)"


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
        if r.get("so_tiktok"):
            linhas.append("    ▸ YouTube   já saiu neste horário")
        elif r.get("cota_youtube"):
            linhas.append("    ▸ YouTube   🚫 limite diário da conta")
        else:
            linhas.append("    ▸ YouTube   "
                          f"{_estado_da_plataforma(r.get('url'))}"
                          f" · {r.get('visibilidade') or '?'}")
        linhas.append("    ▸ TikTok    "
                      f"{_estado_da_plataforma(r.get('tiktok'))}"
                      f" · {_conta_do_destino('tiktok', canal)}")
        linhas.append(f"    `{r.get('alvo', '')}`")
        for recusado in (r.get("recusados") or [])[:2]:
            linhas.append(f"    ⏭ pulei {str(recusado)[:90]}")
        linhas.append("")

    dias = estoque()
    linhas.append("*Estoque* — " + " · ".join(
        f"{CANAIS.get(c, {}).get('emoji', '•')} {n} dia(s)"
        for c, n in dias.items()))
    magros = [c for c, n in dias.items() if 0 <= n < PISO_DE_ALERTA]
    if magros:
        linhas.append(f"⚠️ *{', '.join(magros)}* abaixo de {PISO_DE_ALERTA} "
                      "dia(s): sem vídeo novo o canal para.")
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
    from contos.publicar import catalogo, serie

    fila = fila_de_historias()
    if limite:
        fila = fila[:limite]
    if so_ver:
        return {"total": len(fila), "ids": [v.id for v in fila]}

    visibilidade = _visibilidade_das_historias()
    feitos, falhas, seguidas = [], [], 0
    for i, alvo in enumerate(fila, 1):
        _linha(f"[escoar] {i}/{len(fila)}  {alvo.id}  {alvo.titulo[:52]}")
        try:
            url = catalogo.publicar_youtube(alvo, visibilidade)
            serie.registrar(alvo, url, "youtube", None,
                            {"por": "postar.py --tudo",
                             "visibilidade": visibilidade})
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="postar",
                                     description="uma postagem por dia")
    parser.add_argument("--ver", action="store_true",
                        help="diz o que postaria e sai")
    parser.add_argument("--instalar", action="store_true",
                        help="cria as tarefas da grade no Agendador")
    parser.add_argument("--hora", metavar="HH:MM",
                        help="instala UM horario so, em vez da grade inteira")
    parser.add_argument("--so", choices=("historias", "builds"),
                        help="posta so de um canal")
    parser.add_argument("--tudo", action="store_true",
                        help="escoa a fila INTEIRA de historias, uma atras da "
                             "outra (ignora a guarda de um-por-horario)")
    parser.add_argument("--limite", type=int, default=0, metavar="N",
                        help="com --tudo, para depois de N videos")
    args = parser.parse_args(argv)

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

    resultados = []
    for canal, funcao in (("historias", postar_historia),
                          ("builds", postar_build)):
        if args.so not in (None, canal):
            continue
        try:
            resultados.append(funcao(so_ver=args.ver))
        except Exception as exc:                               # noqa: BLE001
            # A COTA AVISA NO TELEGRAM, e e AQUI que isso precisa acontecer:
            # o escoamento (`--tudo`) e coisa de uma vez, e quem roda sozinho
            # nos oito horarios e este caminho. Ter posto o aviso so la seria
            # avisar justamente na hora em que ele ja esta olhando.
            if _e_limite_diario(exc):
                avisar_limite_diario(f"canal {canal}: {exc}")
            resultados.append({"canal": canal, "feito": False,
                               "motivo": f"{type(exc).__name__}: {exc}"[:200]})

    for r in resultados:
        marca = "POSTADO" if r.get("feito") else "-------"
        alvo = r.get("alvo") or r.get("veria") or ""
        _linha(f"[{marca}] {r['canal']:<10} {alvo}")
        if r.get("titulo"):
            _linha(f"           {r['titulo'][:76]}")
        if r.get("url"):
            _linha(f"           youtube: {r['url']}")
        if r.get("feito"):
            # O TikTok aparece SEMPRE que houve postagem, inclusive quando
            # falhou: um destino que some do relatorio e um destino que passa
            # 49 publicacoes vazio sem ninguem notar.
            estado = r.get("tiktok")
            _linha(f"           tiktok:  {estado or 'NAO SUBIU'}"[:96])
        if not r.get("feito"):
            _linha(f"           {r.get('motivo', '')}")
        for recusado in r.get("recusados") or []:
            _linha(f"   pulado: {recusado}")
    _linha()
    for canal, dias in estoque().items():
        alerta = "  <<< ABAIXO DO PISO" if 0 <= dias < PISO_DE_ALERTA else ""
        _linha(f"  gordura {canal:<10} {dias:>4} dia(s){alerta}")
    if not args.ver and any(r.get("feito") for r in resultados):
        avisar(resultados)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
