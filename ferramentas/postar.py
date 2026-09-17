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
import subprocess
import sys
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
    sys.stdout.buffer.write((texto + "\n").encode("utf-8", "replace"))


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


def esperar_a_rede(*, limite: float = ESPERA_DE_REDE_S, log=None) -> bool:
    """Espera o DNS resolver. `False` quando desiste.

    POR QUE ISTO EXISTE: em 11/09/2026 a queda de energia derrubou o PC. Ele
    voltou as 03:34, as tarefas das 06:07, 07:07 e 08:07 dispararam em dia,
    e as tres morreram em `net::ERR_NAME_NOT_RESOLVED` — a rede nao tinha
    voltado junto. Tres horarios perdidos por uma coisa que se resolve
    esperando.

    Resolver o NOME e o teste certo, e nao abrir o navegador: e barato, e e
    exatamente o passo que falhava. Espera crescente para nao martelar o
    resolvedor enquanto ele ainda sobe.
    """
    import socket
    import time

    log = log or _linha
    fim = time.monotonic() + max(0.0, float(limite))
    espera, avisou = 1.0, False
    while True:
        faltou = ""
        for alvo in ALVOS_DE_REDE:
            try:
                socket.getaddrinfo(alvo, 443)
            except OSError:
                faltou = alvo
                break
        if not faltou:
            if avisou:
                log("[rede] voltou; sigo com a postagem.")
            return True
        if time.monotonic() >= fim:
            log(f"[rede] {faltou} nao resolve depois de {limite:.0f}s; "
                "desisto deste horario.")
            return False
        if not avisou:
            log(f"[rede] {faltou} ainda nao resolve; espero ate "
                f"{limite:.0f}s.")
            avisou = True
        time.sleep(min(espera, max(0.0, fim - time.monotonic())))
        espera = min(espera * 2, 15.0)


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

    publicados = [l for l in serie.publicados() if l.get("url")]
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
    pendentes = [v for v in videos if v.id not in ja
                 and all((v.fonte_id, n) in tem
                         for n in range(1, int(v.parte or 1)))]
    fila = sorted(pendentes, key=lambda v: (
        0 if v.fonte_id in comecadas else 1,   # terminar antes de comecar
        v.fonte_id if v.fonte_id in comecadas  # entre as comecadas: a mais velha
        else _ao_contrario(v.fonte_id),        # entre as novas: a mais nova
        v.parte or 0))
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
    novos, repetidos = _sem_titulo_repetido(fila, "historias")
    if repetidos:
        _linha(f"[postar] {len(repetidos)} parte(s) fora da fila por titulo "
               f"ja publicado: {', '.join(v.id for v in repetidos[:3])}"
               f"{'...' if len(repetidos) > 3 else ''}")
    if novos:
        return novos
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
    # TRES RODADAS E SAI. Veto vencido nao e perguntado de novo: perguntar
    # daria a mesma reprovacao e travaria o horario outra vez.
    if _veto_vencido(alvo):
        _linha(f"[parecer] {alvo.id}: a IA reprovou, mas as rodadas de "
               "conserto acabaram; sai assim.")
        return ""
    ficha = parecer.lembrado(alvo)
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
    """Tres rodadas de conserto e a IA ainda reprova: sai assim.

    A regra mora em `contos.publicar.qualidade.veto_vencido`, a mesma que a
    auditoria e o freio de estoque consultam.
    """
    try:
        from contos.publicar import qualidade
        return qualidade.veto_vencido(alvo)
    except Exception:                                          # noqa: BLE001
        return False


def _veto_lembrado(alvo) -> str:
    """O veto da IA ja gravado para este arquivo, se ainda vale. `""` se nao.

    E LER UM ARQUIVO, e nao decodificar o mp4, e por isso nao gasta
    `TENTATIVAS`. Em 13/09/2026 os seis primeiros da fila eram os seis
    barrados, o teto de seis se esgotava neles, e onze aprovados logo atras
    nunca eram vistos: nenhuma historia saiu nos horarios.
    """
    try:
        from contos.publicar import parecer
        # O veto e do VIDEO: re-render sem conserto nao o apaga (15/09/2026).
        ficha = parecer.lembrado(alvo) or parecer.veto_por_id(alvo)
    except Exception:                                          # noqa: BLE001
        return ""
    if not ficha or ficha.get("aprovado") or _veto_vencido(alvo):
        return ""
    motivos = "; ".join(ficha.get("motivos") or [])[:300]
    return f"{alvo.id}: a IA REPROVOU — {motivos}"


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
    vetados = []
    # A SERIE ESPERA A PARTE BARRADA. Pedido dele em 14/09/2026, depois de a
    # historia 10 publicar a parte 6 antes da 5: parte barrada (veto ou
    # vistoria) segura as seguintes da MESMA historia, e a grade publica outra
    # serie no lugar. A seguinte so sai como ultimo recurso, la embaixo.
    bloqueadas, adiadas = set(), []
    from builds import travas
    for alvo in fila_de_historias():
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
        if examinados >= TENTATIVAS:
            break
        examinados += 1
        roteiro = R.carregar(alvo.fonte_id)
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
    # ficar sem video". Nenhum candidato limpo: sai o primeiro que so tem o
    # veto da IA contra ele, desde que o ARQUIVO esteja inteiro. Video mudo
    # ou sem imagem nao sai nem assim.
    for alvo in vetados[:3]:
        roteiro = R.carregar(alvo.fonte_id)
        laudo = qualidade.vistoriar_parte(alvo.fonte_id, alvo.parte,
                                          alvo.caminho, roteiro)
        if laudo["ok"]:
            _linha(f"[postar] {alvo.id}: nenhum video limpo na fila; sai "
                   "este, com o veto da IA, para o horario nao ficar vazio.")
            return alvo, recusados
    # ULTIMO RECURSO: a parte seguinte de uma serie parada, fora de ordem, so
    # quando nada acima pode sair — o horario vazio continua sendo pior.
    for alvo in adiadas[:3]:
        if _veto_lembrado(alvo):
            continue
        roteiro = R.carregar(alvo.fonte_id)
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
    tiktok_agora = _tiktok_neste_horario()
    if ja_yt and (ja_tk or not tiktok_agora):
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
    url, cota, falha_yt = "", None, None
    provas: list = []
    try:
        url = catalogo.publicar_youtube(alvo, visibilidade, provas=provas)
        serie.registrar(alvo, url, "youtube", None,
                        {"por": "postar.py", "visibilidade": visibilidade,
                         "prova": provas,
                         "prova_ok": _prova_ok(provas)})
    except Exception as exc:                                   # noqa: BLE001
        if _e_limite_diario(exc):
            cota = str(exc)
            _linha(f"[postar] historias: YouTube na cota ({exc}). "
                   "Sigo para o TikTok — ele nao tem esse limite.")
            avisar_limite_diario(f"canal historias: {exc}")
        else:
            # QUALQUER FALHA DO YOUTUBE SEGUE PARA O TIKTOK (auditoria de
            # 15/09/2026). Subir aqui deixava o TikTok daquele horario vazio
            # para sempre. Se o TikTok subir, a parte sai da fila como na cota:
            # o YouTube fica sem ela ate existir fila por plataforma.
            falha_yt = f"{type(exc).__name__}: {exc}"[:200]
            _linha(f"[postar] historias: YouTube falhou ({falha_yt}). "
                   "Sigo para o TikTok.")
    ficha = {"canal": "historias", "feito": bool(url), "alvo": alvo.id,
             "titulo": alvo.titulo, "url": url,
             "parte": alvo.parte, "partes": alvo.partes,
             "visibilidade": visibilidade, "recusados": recusados}
    if _veto_vencido(alvo):
        ficha["veto_vencido"] = True
    elif _veto_lembrado(alvo):
        ficha["veto_ignorado"] = True
    if titulo_repetido(alvo, "historias"):
        ficha["titulo_repetido"] = True
    if cota:
        ficha["motivo"] = f"YouTube na cota: {cota}"[:200]
        ficha["cota_youtube"] = True
    if falha_yt:
        ficha["motivo"] = f"YouTube falhou: {falha_yt}"[:200]
        ficha["youtube_falhou"] = True
    if not tiktok_agora:
        # FORA DA GRADE DO TIKTOK, e nao falha: ele posta seis por dia.
        ficha["tiktok"] = ""
        ficha["tiktok_fora_da_grade"] = True
        _linha("[postar] historias: este horario nao e da grade do TikTok.")
    else:
        ficha["tiktok"] = "" if ja_tk else _tiktok_das_historias(alvo)
    # Deu TikTok e nao deu YouTube: a rodada fez alguma coisa, e o relatorio
    # tem que dizer isso em vez de chamar tudo de falha. So com o post
    # CONFIRMADO: "cliquei mas o TikTok nao confirmou" nao e publicacao
    # (revisao de 15/09/2026).
    if _tiktok_confirmado(ficha["tiktok"]):
        ficha["feito"] = True
    _registrar_valvula(ficha)
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
RECUPERACAO_LIGADA = False
RESERVA_LIGADA = False

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


def _fontes_cheias_hoje(publicados, plataforma: str = "tiktok") -> set:
    """As fontes que ja bateram o teto do dia naquele destino.

    Conta pelo LEDGER e por DATA, e nao por rodada: a rodada normal e a
    recuperacao publicam por caminhos diferentes, e o teto so faz sentido se
    for sobre o que o perfil recebeu no dia, venha de onde vier.

    A fonte sai do `video_id` (`historia_00003:celular:p04` -> `historia_00003`)
    porque a linha do ledger nem sempre tem `fonte_id`.
    """
    from collections import Counter
    from datetime import datetime
    hoje = datetime.now().strftime("%Y-%m-%d")
    contagem = Counter()
    for linha in publicados or ():
        if linha.get("plataforma") != plataforma:
            continue
        if not (linha.get("quando") or "").startswith(hoje):
            continue
        vid = str(linha.get("video_id") or "")
        if vid:
            contagem[vid.split(":")[0]] += 1
    return {fonte for fonte, n in contagem.items()
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

# O CLIQUE SAIU. Qualquer estado com isto significa que o post PODE estar no
# ar, e reenviar duplicaria no perfil — onde o publico ve.
MARCAS_DE_CLIQUE = ("cliquei em publicar",)

# Falha que nao e do video: a maquina, a rede, a sessao. Contar isto como
# defeito do video abandonaria, depois de tres rodadas, um video sem problema
# nenhum. Aconteceu de verdade em 16/09/2026 as 20:47 — a maquina estava
# sobrecarregada, o Chrome nao abriu, e a rodada de historias perdeu o video.
MARCAS_DE_INFRAESTRUTURA = (
    "nao consegui abrir o chrome", "perfilocupado", "perfil esta em uso",
    "pediu login", "nao esta valida neste perfil",
    "err_name_not_resolved", "err_connection", "err_internet",
    "net::err", "nao achei o campo de arquivo",
)


def desfecho_do_tiktok(estado, falha: dict | None = None,
                       laudo: dict | None = None) -> str:
    """"publicado", "sem_confirmacao", "infraestrutura" ou "falha".

    Ate hoje so havia duas respostas — confirmou ou nao — e o "nao" juntava
    tres coisas que pedem reacoes OPOSTAS:

    - **sem_confirmacao**: o clique saiu e o aviso de sucesso nao apareceu. O
      post pode estar no ar. Reenviar duplica, e duplicata o publico ve. Sai
      da fila e espera conferencia humana; nunca volta sozinho.
    - **infraestrutura**: Chrome que nao abre, perfil ocupado, login vencido,
      rede fora. Nao e do video: nao conta para a desistencia e continua na
      fila, porque a proxima rodada pode simplesmente funcionar.
    - **falha**: legenda que nao fica, arquivo recusado. E dela, e so dela,
      que o contador de tres tentativas fala.

    A ORDEM IMPORTA: se o clique saiu, o que aconteceu depois nao muda o
    risco. Um erro de infraestrutura DEPOIS do clique continua sendo
    "sem_confirmacao", porque o post pode ter subido do mesmo jeito.

    E POR ISSO `laudo["clicou"]` VEM ANTES DO TEXTO: a frase de retorno se
    perde quando algo levanta depois do clique (o ledger preso, o Chrome
    fechando), e ai sobrava `""` — classificado como "falha" e reenviado ate
    tres vezes, sobre um post que ja podia estar no ar. A marca do laudo e
    escrita no instante do clique e sobrevive a excecao.
    """
    if _tiktok_confirmado(estado):
        return "publicado"
    if (laudo or {}).get("clicou"):
        return "sem_confirmacao"
    texto = _sem_acentos(str(estado or ""))
    if any(m in texto for m in MARCAS_DE_CLIQUE):
        return "sem_confirmacao"
    motivo = _sem_acentos(" ".join(str(v) for v in (falha or {}).values()))
    if any(m in motivo for m in MARCAS_DE_INFRAESTRUTURA):
        return "infraestrutura"
    return "falha"


def _sem_acentos(texto: str) -> str:
    """Minusculas e sem acento, para as marcas casarem de verdade.

    A marca "nao achei o campo de arquivo" nunca casava: o `tiktok.py`
    escreve "nao" COM acento, e a comparacao era byte a byte. Uma marca que
    nunca casa e pior que marca ausente — ela da a impressao de estar coberto.
    """
    import unicodedata
    normal = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in normal if not unicodedata.combining(c))


def a_conferir_no_tiktok(canal: str = "historias") -> set:
    """Videos cujo clique saiu sem confirmacao: ficam FORA da fila.

    Nao sao desistencia (o video nao tem defeito) nem atraso (pode estar no
    ar). Sao um terceiro estado, que so sai daqui por conferencia — humana ou
    pela conferencia do Studio.
    """
    import json
    try:
        caminho = _arquivo_a_conferir(canal)
        if not caminho.is_file():
            return set()
        return set(json.loads(caminho.read_text(encoding="utf-8")))
    except Exception:                                          # noqa: BLE001
        return set()


def _arquivo_a_conferir(canal: str):
    from builds.publicar import metricas
    return metricas.registro_do_canal(canal).parent / "_tiktok_a_conferir.json"


def _resolver_desfecho(canal: str, alvo, estado: str, laudo: dict,
                       falha: dict | None) -> str:
    """Classifica e REAGE, dentro do publicador. Devolve o estado, intacto.

    Mora aqui, e nao em quem chama, porque ha SETE caminhos que publicam no
    TikTok (rodada normal dos dois canais, "so TikTok", escoamento,
    recuperacao, reserva) e o conserto anterior so cobriu dois. O buraco que
    sobrou era real e na mesma rodada: a rodada normal recebia "cliquei mas
    nao confirmou", nada ia para o ledger, e a recuperacao — chamada logo
    depois, no mesmo `main` — via um video com YouTube e sem TikTok e o
    postava DE NOVO.

    Uma funcao que os publicadores chamam sempre e a unica forma de isto nao
    depender de alguem lembrar no oitavo caminho.
    """
    desfecho = desfecho_do_tiktok(estado, falha, laudo)
    if desfecho == "sem_confirmacao":
        _marcar_para_conferir(canal, getattr(alvo, "id", ""), estado or
                              "o clique saiu e nao veio confirmacao")
    return estado


def _marcar_para_conferir(canal: str, video_id: str, estado: str) -> None:
    """Tira da fila e AVISA. Erro no diario, nao aviso no log."""
    import json
    from datetime import datetime
    try:
        caminho = _arquivo_a_conferir(canal)
        dados = {}
        if caminho.is_file():
            try:
                dados = json.loads(caminho.read_text(encoding="utf-8"))
            except ValueError:
                dados = {}
        if video_id in dados:
            return                       # ja avisado; nao repete no diario
        dados[video_id] = {"quando": datetime.now().isoformat(timespec="seconds"),
                           "estado": str(estado)[:200]}
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        from builds import atividade
        atividade.registrar(
            "publicacao", atividade.ERRO,
            f"{video_id}: cliquei em publicar no TikTok e nao veio "
            f"confirmacao. Pode estar no ar — NAO reenvio sozinho para nao "
            f"duplicar. Precisa de conferencia no perfil.",
            canal, etapa="publicar.tiktok.sem_confirmacao", ref=video_id)
    except Exception:                                          # noqa: BLE001
        pass


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


def atrasados_no_tiktok(limite: int = 40, canal: str = "historias") -> list:
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
    """
    return _fila_do_tiktok(canal, limite, reserva=False)


def _fila_do_tiktok(canal: str, limite: int, *, reserva: bool) -> list:
    """O corpo comum de `atrasados_no_tiktok` e `reserva_do_tiktok`.

    As duas filas sao o MESMO calculo sobre faixas de data complementares:
    atraso e o que falhou depois do corte, reserva e o que nunca teve chance
    antes dele. Uma so implementacao para que um crivo novo (desistencia,
    titulo) nunca exista em uma e falte na outra.
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
    for l in publicados:
        if l.get("plataforma") != "tiktok" or not l.get("url"):
            continue
        no_tiktok.add(l.get("video_id"))
        chave = titulos.chave(l.get("titulo"))
        if chave:
            titulos_no_tiktok.setdefault(chave, l.get("video_id"))

    # Desistidos E os que esperam conferencia saem antes da deduplicacao, pelo
    # mesmo motivo: se o A esta fora, o B precisa poder assumir o titulo.
    desistidos = desistencias_do_tiktok(canal) | a_conferir_no_tiktok(canal)
    candidatos, vistos = [], set()
    for linha in publicados:                     # ledger ja vem em ordem
        if linha.get("plataforma") != "youtube" or not linha.get("url"):
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
    """
    if not RECUPERACAO_LIGADA:
        return {"feito": False, "fila": 0, "canal": canal,
                "motivo": "recuperacao desligada (ver RECUPERACAO_LIGADA)"}
    fila = atrasados_no_tiktok(canal=canal)
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
    desfecho = desfecho_do_tiktok(estado, falha)
    feito = desfecho == "publicado"
    if feito:
        _esquecer_falhas_no_tiktok(canal, alvo.id)
    elif desfecho == "falha":
        _anotar_falha_no_tiktok(canal, alvo.id)
    # "infraestrutura" nao conta nada: o video continua na fila e a proxima
    # rodada tenta de novo, porque o defeito nao e dele.
    return {"feito": feito, "desfecho": desfecho, "fila": len(fila),
            "alvo": alvo.id, "titulo": getattr(alvo, "titulo", ""),
            "canal": canal, "tiktok": estado}


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
    if not so_ver and publicou_neste_horario("builds", "tiktok"):
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
    desfecho = desfecho_do_tiktok(estado, falha)
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
        _linha(f"   tiktok: NAO subiu ({type(exc).__name__}: {exc})"[:200])
        # A EXCECAO NAO PULA A CLASSIFICACAO: se o clique ja tinha saido (o
        # `laudo` guarda isso), o video precisa ir para "a conferir" mesmo
        # que o erro tenha vindo depois.
        return _resolver_desfecho("historias", alvo, "", laudo, falha)
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
    return _resolver_desfecho("historias", alvo, estado, laudo, falha)


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
# Quantos dos 8 disparos diarios cada formato deve ocupar. Sem este bloco no
# `publicacao.json`, a escolha volta a ser o FIFO cego de antes.
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
    "veto_vencido": "veto da IA venceu (as rodadas de conserto acabaram)",
    "veto_ignorado": "veto da IA ignorado (nao havia outro video pronto)",
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


def _servidos_recentes(n: int = JANELA_DA_GRADE) -> dict:
    """Quantas das ultimas `n` publicacoes foram de cada formato."""
    from builds.publicar import metricas

    contagem: dict[str, int] = {}
    linhas = [l for l in metricas.publicados() if l.get("url")]
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

    melhor = min(por_origem,
                 key=lambda o: (atraso(o), por_origem[o][0].quando))
    return por_origem[melhor][0]


LIMIAR_MUDO_DB = -60.0
# Fracao do video em silencio (abaixo de -50 dB por mais de 0,5 s) a partir da
# qual ele conta como mudo. A MEDIA sozinha so pegava o render 100% calado: a
# revisao de 15/09/2026 achou estreias do render antigo mudas quase inteiras e
# com som so no fim, media -27 a -30 dB. Medido nos 23 builds prontos: 20 com
# 0% de silencio, e as tres estreias defeituosas com 93%, 95% e 100%.
FRACAO_MUDA = 0.5


def _audio_mudo(video) -> str:
    """O motivo quando o mp4 sai calado (inteiro ou quase); "" quando tem som.

    Ferramenta que falha NAO barra: sem ffprobe/ffmpeg a grade inteira ficaria
    vazia por um problema da maquina, e nao do video.
    """
    import re
    import subprocess
    try:
        from contos.publicar import qualidade
    except Exception:                                          # noqa: BLE001
        return ""
    caminho = Path(str(getattr(video, "caminho", "") or ""))
    if not caminho.is_file():
        return ""
    dados = qualidade._ffprobe(caminho)
    faixas = dados.get("streams") if isinstance(dados, dict) else None
    if faixas and not any(f.get("codec_type") == "audio" for f in faixas):
        return "o mp4 nao tem faixa de audio"
    try:
        duracao = float(((dados or {}).get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        duracao = 0.0
    try:
        saida = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(caminho), "-vn", "-af",
             "silencedetect=n=-50dB:d=0.5,volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return ""
    texto = saida.stderr or ""
    media = re.search(r"mean_volume: (-?[\d.]+) dB", texto)
    if media and float(media.group(1)) < LIMIAR_MUDO_DB:
        return f"o audio esta mudo (media {float(media.group(1)):.1f} dB)"
    if duracao > 0:
        calado = sum(float(x) for x in re.findall(r"silence_duration: ([\d.]+)", texto))
        inicios = re.findall(r"silence_start: (-?[\d.]+)", texto)
        if len(inicios) > len(re.findall(r"silence_end:", texto)):
            # silencio que vai ate o fim do arquivo pode nao ganhar fechamento
            calado += max(0.0, duracao - float(inicios[-1]))
        fracao = min(1.0, calado / duracao)
        if fracao >= FRACAO_MUDA:
            return (f"o video fica calado em {fracao:.0%} do tempo "
                    f"({calado:.0f} de {duracao:.0f} s)")
    return ""


def _tiktok_confirmado(estado) -> bool:
    """O TikTok CONFIRMOU o post? Frase de "cliquei mas nao confirmou" nao conta."""
    if not estado:
        return False
    try:
        from builds.publicar import tiktok as _tk
        return bool(_tk.confirmado(estado))
    except Exception:                                          # noqa: BLE001
        return bool(estado)


def proximo_build(config=None):
    """O proximo video de builds, alternando entre os FORMATOS.

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
    """
    from builds.publicar import catalogo as C
    from builds.publicar import metricas

    # Qualquer plataforma conta (ver `fila_de_historias`): contando so o
    # YouTube, a cota repetia o mesmo video em todo horario e o TikTok ficava
    # vazio.
    ja = {l.get("video_id") for l in metricas.publicados() if l.get("url")}
    pendentes = [v for v in C.listar()
                 if v.id not in ja and getattr(v, "perfil", "") == "celular"]
    if not pendentes:
        return None

    # BUILD COM PENDENCIA NAO ENTRA NA FILA. O catalogo ja calcula isto
    # (`pendencias_da_build`: sem payoff, sem imagem do personagem, sem a luta
    # no fim, render defasado) e o painel ja mostra — o publicador era o unico
    # que nao olhava. Medido em 11/09/2026: 23 dos 66 pendentes tinham
    # pendencia e podiam sair a qualquer horario. E o mesmo criterio que
    # `proxima_historia` aplica ao pular o que a vistoria reprova.
    prontos = [v for v in pendentes if not getattr(v, "pendencias", None)]
    barrados = [v for v in pendentes if getattr(v, "pendencias", None)]
    if barrados:
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
    pendentes = prontos
    if not pendentes:
        return None

    # TITULO JA NO AR NAO VOLTA. Medido em 16/09/2026 contra o ledger: das
    # 63 chaves de titulo publicadas no canal, 21 sairam DUAS vezes. A causa
    # e a variante "gancho B", que tem id com sufixo `:B` e o mesmo titulo —
    # para a deduplicacao por `video_id` sao dois videos, para o YouTube sao
    # dois iguais, competindo pelo mesmo termo de busca.
    novos, repetidos = _sem_titulo_repetido(pendentes, "builds", config)
    if repetidos:
        _linha(f"[postar] {len(repetidos)} build(s) fora da fila por titulo "
               f"ja publicado: {', '.join(v.id for v in repetidos[:4])}"
               f"{'...' if len(repetidos) > 4 else ''}")
    if novos:
        pendentes = novos
    elif repetidos:
        # A VALVULA FECHOU EM 17/09/2026. Ela liberava "o menos pior" com a
        # fila inteira repetida — e o menos pior era republicar um titulo que
        # ja estava no ar. Foi assim que as variantes A e B de cinco geracoes
        # (00067, 00069, 00071, 00081, 00082) sairam as duas, nos dois
        # destinos, com titulo identico. O Adrian viu.
        #
        # Repetir e pior que nao postar. Aqui ha uma saida melhor que o
        # horario em branco, e ela ja existe: a RESERVA leva um build antigo
        # ao TikTok quando a fila normal nao tem nada. O YouTube fica sem, e
        # fica sem de proposito.
        _linha("[postar] builds: TODOS os pendentes tem titulo ja publicado; "
               "o horario fica SEM post (a valvula fechou).")
        return None

    # o mais ANTIGO primeiro: o catalogo vem do mais novo para o mais velho
    pendentes.reverse()
    servidos, cota = _servidos_recentes(), cota_da_grade(config)
    # VIDEO MUDO NAO SAI (auditoria de 15/09/2026): a estreia da
    # generation_00065 media -91 dB e estava marcada para as 10:07, nas duas
    # plataformas. So o ESCOLHIDO e medido: uma decodificacao por horario.
    while pendentes:
        alvo = escolher_por_cota(pendentes, servidos, cota)
        motivo = _audio_mudo(alvo)
        if not motivo:
            return alvo
        _linha(f"[postar] {alvo.id} fora da fila: {motivo}")
        pendentes = [v for v in pendentes if v.id != alvo.id]
    return None


def postar_build(*, so_ver: bool = False) -> dict:
    from builds.publicar import youtube

    # Uma guarda por DESTINO, igual as historias: o YouTube ter saido nesta
    # hora nao pode cancelar o TikTok.
    ja_yt = None if so_ver else publicou_neste_horario("builds", "youtube")
    ja_tk = None if so_ver else publicou_neste_horario("builds", "tiktok")
    tiktok_agora = _tiktok_neste_horario()
    if ja_yt and (ja_tk or not tiktok_agora):
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
    url, falha_yt, cota = "", None, False
    try:
        url = youtube.publicar_como_configurado(alvo, canal="builds",
                                                visibilidade="public",
                                                log=_linha)
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
    if not tiktok_agora:
        # FORA DA GRADE DO TIKTOK, e nao falha: ele posta seis por dia.
        ficha["tiktok"] = ""
        ficha["tiktok_fora_da_grade"] = True
        _linha("[postar] builds: este horario nao e da grade do TikTok.")
    else:
        ficha["tiktok"] = "" if ja_tk else _tiktok_dos_builds(alvo)
    if _tiktok_confirmado(ficha["tiktok"]):
        ficha["feito"] = True
    _registrar_valvula(ficha)
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
        return any(l.get("video_id") == video_id and l.get("url")
                   and l.get("plataforma") == "tiktok"
                   for l in metricas.publicados())
    except Exception:                                          # noqa: BLE001
        return False


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
    # O `laudo` E PREENCHIDO NO LUGAR pelo `tiktok.publicar`, e e por isso que
    # ele nasce aqui fora do `try`: a marca `clicou` escrita la dentro precisa
    # sobreviver a uma excecao levantada depois do clique.
    laudo: dict = {}
    try:
        # `postar=True` EXPLICITO. O config tem `postar_automatico: false`, que
        # e o certo para o botao do painel — la a ultima palavra e dele. A
        # grade automatica nao tem quem clique, entao ela diz o que quer.
        estado = _tk.publicar(alvo, postar=True, canal="builds",
                              progresso=lambda t: _linha(f"   {t}"),
                              prova=laudo)
    except Exception as exc:                                   # noqa: BLE001
        # Ver o mesmo comentario em `_tiktok_das_historias`: sem a causa,
        # infraestrutura e defeito do video viram a mesma coisa.
        if falha is not None:
            falha["tipo"] = type(exc).__name__
            falha["mensagem"] = str(exc)[:300]
        _linha(f"   tiktok: NAO subiu ({type(exc).__name__}: {exc})"[:200])
        estado = ""
    return _resolver_desfecho("builds", alvo, estado, laudo, falha)


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
    return [instalar(grade.horario(h), nome=nome_da_tarefa(h)) for h in horas]


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
        # O MESMO FUNIL DO `proximo_build`, e nao uma contagem propria.
        # Contando so `catalogo - ja`, a gordura dizia "2 dias" enquanto
        # `proximo_build` devolvia None: ficavam de fora as pendencias (as 20
        # estreias impossiveis) e os titulos repetidos. O alerta "ABAIXO DO
        # PISO" nunca disparava na hora certa, porque o numero que ele olha
        # nao era o numero que sai.
        from builds.publicar import catalogo as C, metricas
        ja = {l.get("video_id") for l in metricas.publicados()
              if metricas.publicado(l)}
        pendentes = [v for v in C.listar()
                     if v.id not in ja
                     and getattr(v, "perfil", "") == "celular"
                     and not getattr(v, "pendencias", None)]
        prontos, _repetidos = _sem_titulo_repetido(pendentes, "builds")
        saida["builds"] = len(prontos)
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


def estoque_por_formato(por_dia: int | None = None) -> dict:
    """Dias de estoque de CADA formato de builds, pela cota dele.

    O total do canal esconde o que importa depois da Onda 15E: com a grade
    alternando formatos, o duelo pode secar enquanto o numero geral segue
    confortavel — e a comparacao para de ter os dois lados sem ninguem
    perceber. Cada formato e medido contra a cota DELE, nao contra os 8
    disparos do dia.
    """
    por_dia = int(por_dia or len(HORAS_PADRAO)) or 1
    cota = cota_da_grade()
    total_cota = sum(cota.values()) or 1
    try:
        from builds.publicar import catalogo as C
        from builds.publicar import metricas
        ja = {l.get("video_id") for l in metricas.publicados() if l.get("url")}
        pendentes = [v for v in C.listar()
                     if v.id not in ja and getattr(v, "perfil", "") == "celular"]
    except Exception:                                          # noqa: BLE001
        return {}
    contagem: dict[str, int] = {}
    for video in pendentes:
        origem = str(getattr(video, "origem", ""))
        contagem[origem] = contagem.get(origem, 0) + 1
    saida = {}
    for origem, peso in cota.items():
        if peso <= 0:
            continue  # cota zero nao tem ritmo proprio para medir
        saidas_por_dia = max(1e-9, por_dia * peso / total_cota)
        saida[origem] = int(contagem.get(origem, 0) // saidas_por_dia)
    return saida


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
        if r.get("so_tiktok"):
            linhas.append("    ▸ YouTube   já saiu neste horário")
        elif r.get("cota_youtube"):
            linhas.append("    ▸ YouTube   🚫 limite diário da conta")
        elif r.get("youtube_falhou"):
            motivo = str(r.get("motivo") or "").split(": ", 1)[-1]
            linhas.append(f"    ▸ YouTube   ❌ falhou: {motivo[:100]} "
                          "(a parte volta no próximo horário)")
        else:
            linhas.append("    ▸ YouTube   "
                          f"{_estado_da_plataforma(r.get('url'))}"
                          f" · {r.get('visibilidade') or '?'}")
        if r.get("tiktok_fora_da_grade"):
            linhas.append("    ▸ TikTok    ⏸ fora da grade do TikTok "
                          "neste horário")
        else:
            linhas.append("    ▸ TikTok    "
                          f"{_estado_da_plataforma(r.get('tiktok'))}"
                          f" · {_conta_do_destino('tiktok', canal)}")
        linhas.append(f"    `{r.get('alvo', '')}`")
        if r.get("veto_vencido"):
            linhas.append("    ⚠ saiu com veto da IA: as 3 rodadas de "
                          "conserto acabaram")
        if r.get("veto_ignorado"):
            linhas.append("    ⚠ saiu com veto da IA: nao havia outro video "
                          "pronto e o horario nao podia ficar vazio")
        if r.get("titulo_repetido"):
            linhas.append("    ⚠ saiu com titulo JA PUBLICADO: nao havia "
                          "outro video na fila. Os dois competem entre si.")
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
        secos = [o for o, n in por_formato.items() if n < PISO_DE_ALERTA]
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

    # A REDE ANTES DE QUALQUER NAVEGADOR. Abrir o Chrome para descobrir que o
    # DNS nao resolve custa minutos e termina em `ERR_NAME_NOT_RESOLVED`;
    # resolver um nome custa milissegundos e responde a mesma pergunta.
    if not args.ver and not esperar_a_rede():
        avisar([{"canal": c, "feito": False,
                 "motivo": "a rede nao voltou a tempo deste horario"}
                for c in ("historias", "builds")])
        return 1

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
            if r.get("tiktok_fora_da_grade"):
                estado = "fora da grade do TikTok neste horario"
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
        try:
            recuperado = recuperar_no_tiktok(so_ver=args.ver, canal=canal)
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

    # A RESERVA E A ULTIMA A FALAR. Ela so existe para buraco: se a rodada e a
    # recuperacao ja levaram um build ao TikTok, nao ha buraco nenhum.
    if args.so in (None, "builds"):
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
    for canal, dias in estoque().items():
        alerta = "  <<< ABAIXO DO PISO" if 0 <= dias < PISO_DE_ALERTA else ""
        _linha(f"  gordura {canal:<10} {dias:>4} dia(s){alerta}")
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
    tentou = bool(resultados)
    if tentou and not any(r.get("feito") for r in resultados):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
