# -*- coding: utf-8 -*-
"""Metricas dos videos publicados, cruzadas com a timeline — de graca.

Sem dado de retencao toda mudanca de edicao e palpite. Este modulo fecha o
ciclo: `youtube.publicar` registra cada upload em
`outputs/_publicar/publicados.jsonl`; `main.py metricas --atualizar` busca
na API do YouTube (Data API v3 para views/likes e Analytics API para a
CURVA de retencao) e grava em `outputs/_metricas/<youtube_id>.json`; o
relatorio le a curva e diz EM QUAL EVENTO do video as pessoas saem —
"queda maior: roulette PESO (38%)" — usando o `timeline.json` da geracao.

Tudo pela API oficial, com o mesmo OAuth do chat da live. A curva exige o
escopo `yt-analytics.readonly` (uma re-autorizacao: ver COMANDO_OAUTH
abaixo); sem ele, o relatorio mostra views/likes e avisa o que falta, em vez
de falhar.

O gancho A/B fecha aqui: dois uploads da mesma geracao com `variante`
diferente aparecem lado a lado com a retencao media de cada um.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
REGISTRO = OUTPUTS / "_publicar" / "publicados.jsonl"
PASTA = OUTPUTS / "_metricas"

# O canal de historias tem ledger, credencial e metricas PROPRIOS. Ate
# 11/09/2026 este modulo so conhecia `builds`, e por isso nenhuma historia
# jamais teve uma metrica: `atualizar()` lia um ledger onde elas nao estao.
# `builds` continua saindo das globais acima, e nao de um dicionario, porque
# tres suites trocam `REGISTRO` e `PASTA` por um tmpdir — ler o valor na hora
# da chamada e o que mantem esse patch funcionando.
CANAIS = ("builds", "historias")
OUTRAS_RAIZES = {"historias": RAIZ.parent / "historias"}

API_UPLOADS = "https://www.googleapis.com/youtube/v3/playlistItems"
API_CANAIS = "https://www.googleapis.com/youtube/v3/channels"


def registro_do_canal(canal: str = "builds") -> Path:
    """O `publicados.jsonl` daquele canal."""
    if canal == "builds":
        return Path(REGISTRO)
    return OUTRAS_RAIZES[canal] / "outputs" / "_publicar" / "publicados.jsonl"


def pasta_do_canal(canal: str = "builds") -> Path:
    """Onde ficam os `<youtube_id>.json` daquele canal."""
    if canal == "builds":
        return Path(PASTA)
    return OUTRAS_RAIZES[canal] / "outputs" / "_metricas"

# O comando que a mensagem de erro manda rodar tem que EXISTIR. Ate
# 11/09/2026 ela dizia `neural-fights youtube-oauth --com-upload
# --com-analytics`, e nada disso era verdade: nao ha entry point
# `youtube-oauth` no pyproject, e a ferramenta exigia --client-id e
# --client-secret, entao a linha so imprimia o `usage` e o navegador nunca
# abria. `{conta}` e preenchido com a conta ATIVA do canal, porque
# reautorizar sem --conta grava por cima do canal errado.
COMANDO_OAUTH = ("python -m neural_fights.tools.youtube_oauth "
                 "--conta {conta} --com-upload --com-analytics")

API_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
API_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
ESCOPO_ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"

SPARK = "▁▂▃▄▅▆▇█"

# O plano descreve o mp4 inteiro; o que subiu pode ser um PEDACO dele
# (corte para Shorts). Fora desta folga, casar evento com segundo da
# curva daria um numero errado com cara de certo.
SPARK_ASCII = "._-=+*#@"

TOLERANCIA_PLANO_S = 2.0


# ------------------------------------------------------------------ registro
def registrar_publicacao(video, url: str, plataforma: str = "youtube",
                         extra: dict | None = None) -> dict:
    """Uma linha por upload. E o unico lugar que sabe qual mp4 virou qual
    video na plataforma — sem isso a metrica nao tem a que se ligar."""
    youtube_id = None
    achado = re.search(r"(?:youtu\.be/|v=)([A-Za-z0-9_-]{6,})", url or "")
    if achado:
        youtube_id = achado.group(1)
    linha = {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "plataforma": plataforma,
        "url": url,
        "youtube_id": youtube_id,
        "video_id": getattr(video, "id", None),
        "fonte_id": getattr(video, "fonte_id", None),
        "origem": getattr(video, "origem", None),
        "perfil": getattr(video, "perfil", None),
        "variante": getattr(video, "variante", "A"),
        "titulo": getattr(video, "titulo", None),
    }
    linha.update(extra or {})
    if not linha.get("video_id"):
        # PUBLICACAO SEM VIDEO NAO E PUBLICACAO. `video` aqui e sempre um item
        # do catalogo, que tem `.id`; quando chega uma string (um caminho solto
        # — ou um dublê de teste), todos os campos saem `None` e a linha nao
        # identifica coisa nenhuma.
        #
        # Nao e hipotese: medido em 09/09/2026, 322 das 358 linhas deste
        # arquivo eram exatamente isso, escritas por
        # `tests/test_modo_navegador_regressions.py`, que dubla
        # `youtube.publicar` mas nao o registro. O ledger e a unica resposta
        # para "o que foi publicado?" — com 90% de lixo ele deixa de
        # responder, e `atualizar()` ainda vai buscar metrica de id nenhum.
        raise ValueError(
            "registro recusado: a linha nao identifica video nenhum "
            f"(video={video!r}). Quem publica passa o item do catalogo, "
            "nao o caminho do arquivo.")
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha


def registrar_publicado(video, url: str, plataforma: str = "youtube", *,
                        canal: str = "builds", extra: dict | None = None):
    """Porta unica de registro: guarda o canal e NUNCA derruba a publicacao.

    Ela existe aqui, e nao dentro de cada backend, porque a chamada morava
    so no caminho da API enquanto o modo padrao era o navegador: 32 videos
    subiram e nenhum entrou no registro por conta propria. Um lugar so, e
    todos os caminhos (API, Studio, TikTok, Kwai) passam por ele.

    A guarda de canal e a mesma de antes: `contos` reusa este modulo e tem
    registro proprio; sem ela, upload de historia entrava no
    `publicados.jsonl` de builds e a metrica ia buscar retencao de um video
    que nao e deste canal.
    """
    if canal != "builds":
        return None
    try:
        return registrar_publicacao(video, url, plataforma, extra)
    except Exception as exc:  # pragma: no cover - so log
        print(f"[publicar] registro falhou: {exc}")
        return None


def publicados(canal: str = "builds") -> list[dict]:
    registro = registro_do_canal(canal)
    if not registro.is_file():
        return []
    saida = []
    with open(registro, encoding="utf-8") as fh:
        for linha in fh:
            linha = linha.strip()
            if not linha:
                continue
            try:
                saida.append(json.loads(linha))
            except ValueError:
                continue
    return saida


# --------------------------------------------------------------------- API
def comando_oauth(canal: str = "builds") -> str:
    """A linha de comando exata, ja com a conta ATIVA daquele canal."""
    try:
        from ..contas import ativa
        conta = ativa("youtube", canal)
    except Exception:
        conta = "principal"
    return COMANDO_OAUTH.format(conta=conta)


def _token(canal: str = "builds"):
    from .youtube import PublicacaoFalhou, carregar_credenciais, token_de_acesso
    credenciais = carregar_credenciais(canal=canal)
    if credenciais is None:
        from .youtube import caminho_credenciais
        raise PublicacaoFalhou(
            f"sem credencial do YouTube em {caminho_credenciais(canal)} — "
            f"rode:\n  {comando_oauth(canal)}")
    return token_de_acesso(credenciais), credenciais


def _iso_para_segundos(texto: str) -> float:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", texto or "")
    if not m:
        return 0.0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def estatisticas(youtube_ids: list[str], token: str) -> dict:
    """views/likes/comentarios/duracao por id (Data API v3, escopo readonly)."""
    import requests
    saida = {}
    for i in range(0, len(youtube_ids), 50):
        lote = youtube_ids[i:i + 50]
        resposta = requests.get(API_VIDEOS, timeout=30,
                                params={"part": "statistics,contentDetails,snippet",
                                        "id": ",".join(lote)},
                                headers={"Authorization": f"Bearer {token}"})
        if not resposta.ok:
            raise RuntimeError(f"Data API {resposta.status_code}: {resposta.text[:200]}")
        for item in resposta.json().get("items", []):
            st = item.get("statistics", {})
            saida[item["id"]] = {
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comentarios": int(st.get("commentCount", 0)),
                "duracao": _iso_para_segundos(item.get("contentDetails", {}).get("duration")),
                "publicado_em": item.get("snippet", {}).get("publishedAt"),
            }
    return saida


def enviados(token: str, quantos: int = 200) -> list[dict]:
    """Os uploads mais recentes do canal: `{youtube_id, titulo, publicado_em}`.

    Sai da playlist de uploads e nao do `search`, porque `search` e eventual:
    video publicado ha minutos costuma nao aparecer nele, e e exatamente esse
    que precisamos casar.
    """
    import requests
    cabecalho = {"Authorization": f"Bearer {token}"}
    resposta = requests.get(API_CANAIS, timeout=30, headers=cabecalho,
                            params={"part": "contentDetails", "mine": "true"})
    if not resposta.ok:
        raise RuntimeError(motivo_da_recusa(resposta))
    itens = resposta.json().get("items") or []
    if not itens:
        return []
    lista = (itens[0].get("contentDetails", {})
             .get("relatedPlaylists", {}).get("uploads"))
    if not lista:
        return []
    saida, pagina = [], None
    while len(saida) < quantos:
        params = {"part": "snippet", "playlistId": lista, "maxResults": 50}
        if pagina:
            params["pageToken"] = pagina
        resposta = requests.get(API_UPLOADS, timeout=30, headers=cabecalho,
                                params=params)
        if not resposta.ok:
            raise RuntimeError(motivo_da_recusa(resposta))
        dados = resposta.json()
        for item in dados.get("items", []):
            snip = item.get("snippet") or {}
            vid = (snip.get("resourceId") or {}).get("videoId")
            if vid:
                saida.append({"youtube_id": vid,
                              "titulo": snip.get("title") or "",
                              "publicado_em": snip.get("publishedAt")})
        pagina = dados.get("nextPageToken")
        if not pagina:
            break
    return saida


def _chave_de_titulo(texto: str) -> str:
    """Titulo comparavel: o Studio devolve o que ele ACEITOU, nao o que foi
    mandado — corta em 100 caracteres, normaliza espaco e mexe em emoji."""
    limpo = re.sub(r"\s+", " ", str(texto or "")).strip().lower()
    limpo = "".join(c for c in limpo if c.isalnum() or c.isspace())
    return re.sub(r"\s+", " ", limpo).strip()[:60]


def reconciliar(canal: str = "builds", log=print) -> int:
    """Preenche o `youtube_id` que faltou no ledger, casando pelo TITULO.

    O caminho de publicacao por navegador (`youtube_web`) quase nunca captura
    o link: o Studio troca o dialogo de confirmacao de tempos em tempos e o
    seletor para de casar. O resultado, medido em 11/09/2026: 18 uploads de
    builds e TODOS os 30 de historias sem id nenhum — ou seja, invisiveis
    para a metrica, e nenhum experimento poderia ser medido.

    Casar pelo titulo depois do fato e mais robusto do que raspar o dialogo,
    porque nao depende do DOM de ninguem, e recupera o passado junto.
    """
    registro = registro_do_canal(canal)
    linhas = publicados(canal)
    faltam = [L for L in linhas
              if L.get("plataforma", "youtube") == "youtube"
              and not L.get("youtube_id") and L.get("titulo")]
    if not faltam:
        log(f"[{canal}] nenhum upload sem id.")
        return 0
    token, _ = _token(canal)
    catalogo = {}
    for video in enviados(token):
        catalogo.setdefault(_chave_de_titulo(video["titulo"]), video)
    achados = 0
    for linha in linhas:
        if linha.get("youtube_id") or not linha.get("titulo"):
            continue
        if linha.get("plataforma", "youtube") != "youtube":
            continue
        video = catalogo.get(_chave_de_titulo(linha["titulo"]))
        if not video:
            continue
        linha["youtube_id"] = video["youtube_id"]
        linha["url"] = f"https://youtu.be/{video['youtube_id']}"
        linha["publicado_em"] = video.get("publicado_em")
        achados += 1
    if achados:
        # Reescrito inteiro porque o ledger e a linha do tempo: ordem e
        # conteudo das outras linhas nao mudam, so os campos preenchidos.
        with open(registro, "w", encoding="utf-8") as fh:
            for linha in linhas:
                fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    log(f"[{canal}] {achados} de {len(faltam)} upload(s) reconciliados.")
    return achados


def motivo_da_recusa(resposta) -> str:
    """Le o MOTIVO que o Google mandou, em vez de chutar sempre o mesmo.

    Ate 11/09/2026 todo 401/403 virava "escopo yt-analytics.readonly
    ausente". O escopo estava certo, o token estava vivo, e a causa real era
    `accessNotConfigured`: a YouTube Analytics API nunca foi LIGADA no
    projeto do Google Cloud. Diagnostico errado com cara de certeza custou
    uma reautorizacao inutil e mandou procurar no lugar errado — o mesmo
    defeito do "esta logado?" que errou dos dois lados (09/09/2026).
    """
    try:
        erro = (resposta.json() or {}).get("error") or {}
        detalhes = erro.get("errors") or [{}]
        razao = str(detalhes[0].get("reason") or "")
        recado = str(erro.get("message") or "")
    except ValueError:
        razao, recado = "", (resposta.text or "")[:200]

    if razao == "accessNotConfigured":
        return ("YouTube Analytics API DESLIGADA no projeto do Google Cloud "
                "(nao e escopo, nao e token). Ligue em "
                "console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com "
                "e espere alguns minutos. Detalhe: " + recado[:200])
    if razao in ("authError", "unauthorized") or resposta.status_code == 401:
        return f"token invalido ou revogado — rode: {comando_oauth()}"
    if razao == "insufficientPermissions":
        return f"falta o escopo yt-analytics.readonly — rode: {comando_oauth()}"
    return f"Analytics API {resposta.status_code} ({razao or 'sem reason'}): {recado[:200]}"


def retencao(youtube_id: str, token: str, desde: str) -> dict:
    """Media de visualizacao e a CURVA (Analytics API). Sem o escopo, devolve
    `erro` explicando o que falta — nunca levanta."""
    import requests
    hoje = date.today().isoformat()
    base = {"ids": "channel==MINE", "startDate": desde, "endDate": hoje,
            "filters": f"video=={youtube_id}"}
    cab = {"Authorization": f"Bearer {token}"}
    resumo = requests.get(API_ANALYTICS, timeout=30, headers=cab, params={
        **base, "metrics": "views,averageViewDuration,averageViewPercentage"})
    if resumo.status_code in (401, 403):
        return {"erro": motivo_da_recusa(resumo)}
    if not resumo.ok:
        return {"erro": f"Analytics API {resumo.status_code}: {resumo.text[:160]}"}
    linhas = resumo.json().get("rows") or []
    if not linhas:
        # SEM LINHAS NAO E ZERO. `ids=channel==MINE` filtra pelo canal DO
        # TOKEN: um video que esta em outro canal do mesmo dono devolve lista
        # vazia, sem erro. Virar `[[0, 0, 0]]` gravava "retencao media 0%"
        # como se fosse medicao — e um numero errado no ledger e pior do que
        # numero nenhum, porque ninguem desconfia dele. Foi o risco criado em
        # 01/09/2026, quando builds e historias passaram a ter canais
        # diferentes mas continuaram com um token so.
        return {"erro": "a Analytics nao devolveu linha para este video: ele "
                        "provavelmente esta em outro canal que nao o do token "
                        "(`channel==MINE`), ou ainda nao tem dado."}
    saida = {"views_analytics": linhas[0][0], "media_segundos": linhas[0][1],
             "media_percentual": linhas[0][2]}
    curva = requests.get(API_ANALYTICS, timeout=30, headers=cab, params={
        **base, "metrics": "audienceWatchRatio,relativeRetentionPerformance",
        "dimensions": "elapsedVideoTimeRatio"})
    if curva.ok:
        saida["curva"] = [(float(r[0]), float(r[1])) for r in curva.json().get("rows") or []]
    return saida


def atualizar(log=print, canal: str = "builds") -> list[dict]:
    """Consulta a API para cada video registrado e grava o resultado."""
    registros = [r for r in publicados(canal) if r.get("youtube_id")]
    if not registros:
        log("nenhum video registrado ainda (publique com `main.py publicar <id> --youtube`).")
        return []
    token, credenciais = _token(canal)
    ids = sorted({r["youtube_id"] for r in registros})
    stats = estatisticas(ids, token)
    pasta = pasta_do_canal(canal)
    pasta.mkdir(parents=True, exist_ok=True)
    salvos = []
    for registro in registros:
        yid = registro["youtube_id"]
        dado = {**registro, **stats.get(yid, {}), "atualizado": datetime.now().isoformat(timespec="seconds")}
        desde = (dado.get("publicado_em") or registro["quando"])[:10]
        dado.update(retencao(yid, token, desde))
        # Gravados junto para o relatorio nao depender de recalcular a idade
        # a cada leitura — e para o arquivo guardar a foto do dia.
        dado["dias_no_ar"] = idade_em_dias(dado)
        dado["views_por_dia"] = views_por_dia(dado)
        dado["canal"] = canal
        with open(pasta / f"{yid}.json", "w", encoding="utf-8") as fh:
            json.dump(dado, fh, ensure_ascii=False, indent=2)
        salvos.append(dado)
    log(f"{len(salvos)} video(s) atualizados em {pasta}")
    return salvos


# A marca do dia. Mora ao lado das metricas, e nao em quem chama, porque quem
# chama pode ser mais de um (a grade das 8 postagens, o botao do painel, a CLI)
# e a pergunta "ja atualizei hoje?" e sempre a mesma.
MARCA_DO_DIA = OUTPUTS / "_metricas" / "_atualizado_em.json"


def atualizar_uma_vez_por_dia(log=print, agora=None) -> bool:
    """`atualizar_tudo`, mas so na primeira vez do dia. `False` = ja tinha ido.

    UMA VEZ, e nao a cada disparo: views nao mudam de hora em hora, e cada
    passada custa uma ida a API do YouTube por canal. Oito por dia seria
    gastar cota para reler o mesmo numero.

    NUNCA LEVANTA. Quem chama e a grade de publicacao; OAuth vencido, rede
    fora ou Analytics desligada nao podem custar o horario. O relatorio diario
    e que denuncia metrica velha — nao esta funcao.
    """
    agora = agora or datetime.now()
    hoje = agora.strftime("%Y-%m-%d")
    try:
        with open(MARCA_DO_DIA, encoding="utf-8-sig") as fh:
            if (json.load(fh) or {}).get("dia") == hoje:
                return False
    except (OSError, ValueError):
        pass
    try:
        resultado = atualizar_tudo(log=log)
    except Exception as exc:                                   # noqa: BLE001
        log(f"[metricas] nao atualizei ({type(exc).__name__}: {exc}).")
        return False
    try:
        MARCA_DO_DIA.parent.mkdir(parents=True, exist_ok=True)
        with open(MARCA_DO_DIA, "w", encoding="utf-8") as fh:
            json.dump({"dia": hoje,
                       "quando": agora.isoformat(timespec="seconds"),
                       "videos": {c: len(v or []) for c, v in resultado.items()}},
                      fh, ensure_ascii=False, indent=2)
    except OSError:
        pass          # a marca e conveniencia: no pior caso roda duas vezes
    return True


def atualizar_tudo(log=print) -> dict:
    """Os dois canais, e o que falhar num nao derruba o outro."""
    saida = {}
    for canal in CANAIS:
        try:
            reconciliar(canal, log=log)
            saida[canal] = atualizar(log=log, canal=canal)
        except Exception as exc:                              # noqa: BLE001
            log(f"[{canal}] metrica nao atualizou: {exc}")
            saida[canal] = []
        # O TIKTOK NUM `try` PROPRIO. Ele le o Studio pelo navegador, e login
        # caido la e coisa comum — nao pode custar a metrica do YouTube, que
        # ja foi gravada acima. Chave separada para quem conta quantos videos
        # cada lado atualizou nao somar plataforma com plataforma.
        try:
            from . import tiktok_metricas
            saida[f"{canal}_tiktok"] = tiktok_metricas.coletar(canal, log=log)
        except Exception as exc:                              # noqa: BLE001
            log(f"[{canal}] metrica do TikTok nao atualizou: {exc}")
            saida[f"{canal}_tiktok"] = []
    return saida


# ------------------------------------------------- comparacao por formato
# Enquanto o canal tem 4-20 views por video, a curva de retencao vem VAZIA
# (a Analytics suprime linha por baixo volume) e `custo_por_cena` nao roda.
# A medicao que sobra, e que nao precisa de escopo nenhum, e views POR DIA
# agregada por origem: normaliza a idade, entao um video de ontem nao perde
# para um de um mes atras so por ter tido menos tempo de existir. Medido em
# 10/09/2026, sem normalizar: build 19,6 e estreia 4,2 views de media.
def idade_em_dias(dado: dict, agora: datetime | None = None) -> float | None:
    """Dias desde a publicacao, com piso de 1 dia.

    Piso porque o divisor de `views_por_dia` nao pode tender a zero: video
    publicado ha uma hora daria uma taxa absurda e envenenaria a media.
    """
    bruto = dado.get("publicado_em") or dado.get("quando")
    if not bruto:
        return None
    try:
        quando = datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
    except ValueError:
        return None
    referencia = agora or datetime.now(quando.tzinfo)
    if referencia.tzinfo is None and quando.tzinfo is not None:
        quando = quando.replace(tzinfo=None)
    return max(1.0, (referencia - quando).total_seconds() / 86400.0)


def views_por_dia(dado: dict, agora: datetime | None = None) -> float | None:
    dias = idade_em_dias(dado, agora)
    if dias is None:
        return None
    return (dado.get("views") or 0) / dias


def comparar_formatos(dados: list[dict], agora: datetime | None = None) -> list[dict]:
    """Agrega por origem: n, views/dia, like-rate e duracao mediana.

    E o numero que decide a Onda 15 — se o formato curto vence o longo. Um
    video sem data de publicacao fica de fora em vez de contar como idade
    zero, pelo mesmo motivo que `retencao()` se recusa a gravar zero quando
    a Analytics nao devolve linha: ausencia nao e zero.
    """
    grupos: dict[str, list[dict]] = {}
    for d in dados:
        if views_por_dia(d, agora) is None:
            continue
        grupos.setdefault(str(d.get("origem") or "?"), []).append(d)
    saida = []
    for origem, lista in grupos.items():
        taxas = [views_por_dia(d, agora) for d in lista]
        views = sum(d.get("views") or 0 for d in lista)
        duracoes = sorted(float(d["duracao"]) for d in lista if d.get("duracao"))
        # Retencao so entra de quem TEM retencao. Video sem linha da
        # Analytics nao vira 0% na media — e a mesma regra de `retencao()`,
        # que se recusa a gravar zero quando a API nao devolveu nada.
        retencoes = sorted(float(d["media_percentual"]) for d in lista
                           if d.get("media_percentual") is not None)
        saida.append({
            "origem": origem,
            "videos": len(lista),
            "views": views,
            "views_por_dia": sum(taxas) / len(taxas),
            "like_rate": (sum(d.get("likes") or 0 for d in lista) / views) if views else None,
            "duracao_mediana": duracoes[len(duracoes) // 2] if duracoes else None,
            "com_retencao": len(retencoes),
            "retencao_media": (sum(retencoes) / len(retencoes)) if retencoes else None,
            "retencao_mediana": (retencoes[len(retencoes) // 2] if retencoes else None),
        })
    # Ordena por RETENCAO quando ela existe: com 4-20 views por video, views
    # por dia e muito mais ruidosa que "quanto do video as pessoas veem".
    return sorted(saida, key=lambda x: (-(x["retencao_media"] or -1),
                                        -x["views_por_dia"]))


def carregar_salvas(canal: str = "builds") -> list[dict]:
    saida = []
    pasta = pasta_do_canal(canal)
    if not pasta.is_dir():
        return saida
    for arquivo in sorted(pasta.glob("*.json")):
        try:
            with open(arquivo, encoding="utf-8-sig") as fh:
                dado = json.load(fh)
        except (OSError, ValueError):
            continue
        dado.setdefault("canal", canal)
        saida.append(dado)
    return saida


def salvas_de_todos() -> list[dict]:
    """As metricas dos dois canais numa lista so, cada uma marcada."""
    saida = []
    for canal in CANAIS:
        saida.extend(carregar_salvas(canal))
    return saida


# ---------------------------------------------------------------- timeline
def timeline_de(fonte_id: str | None, origem: str | None) -> list[dict]:
    """Os eventos do video, para dizer o que estava na tela em cada instante."""
    if not fonte_id:
        return []
    pasta = OUTPUTS / fonte_id
    if origem == "estreia":
        pasta = pasta / "estreia"
    for nome in ("timeline.json", "edit_plan.json"):
        caminho = pasta / nome
        if caminho.is_file():
            try:
                with open(caminho, encoding="utf-8-sig") as fh:
                    dados = json.load(fh)
            except (OSError, ValueError):
                continue
            eventos = dados if isinstance(dados, list) else dados.get("events") or []
            return [e for e in eventos if isinstance(e, dict) and "start" in e]
    return []


def rotulo_do_evento(evento: dict) -> str:
    tipo = evento.get("type", "?")
    if tipo == "roulette":
        return f"roleta {evento.get('category') or (evento.get('roll') or {}).get('category', '')}"
    if tipo in ("image", "video", "identity"):
        return f"revelacao {evento.get('slot', '')}".strip()
    if tipo == "reaction":
        return f"reacao {evento.get('category', '')}".strip()
    return tipo


def evento_em(eventos: list[dict], segundo: float) -> dict | None:
    atual = None
    for evento in eventos:
        if float(evento["start"]) <= segundo:
            atual = evento
        else:
            break
    return atual


def quedas(dado: dict, eventos: list[dict], quantas: int = 3) -> list[dict]:
    """Os maiores tombos da curva, com o evento que estava na tela."""
    curva = dado.get("curva") or []
    duracao = float(dado.get("duracao") or 0.0)
    if not duracao and eventos:
        duracao = max(float(e["start"]) + float(e.get("duration", 0)) for e in eventos)
    if len(curva) < 3 or duracao <= 0:
        return []
    tombos = []
    for (r0, w0), (r1, w1) in zip(curva, curva[1:]):
        # A queda aconteceu ENTRE as duas amostras, entao quem estava na
        # tela e o evento do MEIO do intervalo. Atribuindo por `r1` (o fim),
        # todo tombo que termina numa troca de cena era carimbado na cena
        # SEGUINTE — o relatorio culpava a luta pelo que a roleta fez.
        tombos.append({"fracao": r1, "queda": w0 - w1,
                       "segundo": r1 * duracao,
                       "_meio": (r0 + r1) / 2 * duracao})
    tombos.sort(key=lambda t: -t["queda"])
    saida = []
    for t in tombos[:quantas]:
        evento = evento_em(eventos, t.pop("_meio"))
        saida.append({**t, "evento": rotulo_do_evento(evento) if evento else "?"})
    return saida


def _valor_na_curva(curva: list, fracao: float) -> float | None:
    """Retencao interpolada numa fracao do video (0..1)."""
    if not curva:
        return None
    fracao = max(0.0, min(1.0, float(fracao)))
    anterior = None
    for ponto, valor in curva:
        ponto = float(ponto)
        if ponto >= fracao:
            if anterior is None or ponto == anterior[0]:
                return float(valor)
            p0, v0 = anterior
            peso = (fracao - p0) / (ponto - p0)
            return float(v0) + (float(valor) - float(v0)) * peso
        anterior = (ponto, float(valor))
    return anterior[1] if anterior else None


def custo_por_cena(dados: list[dict]) -> list[dict]:
    """Quanto de audiencia cada TIPO de cena custa, somando todos os videos.

    `quedas()` responde "onde caiu NESTE video". Esta responde a pergunta
    que decide a montagem: a roleta custa mais por segundo de tela do que a
    luta? Uma queda grande numa cena longa pode ser barata, e uma queda
    pequena numa cena curta pode ser cara — o numero comparavel e PONTOS
    POR SEGUNDO, nao a queda bruta.

    Videos cujo plano nao bate com a duracao publicada ficam de fora (o
    corte para Shorts parte o mp4 em pedacos e o `edit_plan` passa a
    descrever outro video); sao contados em `_fora` para o relatorio poder
    dizer quantos ignorou, em vez de calar.
    """
    somas: dict[str, dict] = {}
    fora = 0
    for dado in dados:
        curva = dado.get("curva") or []
        duracao = float(dado.get("duracao") or 0.0)
        eventos = timeline_de(dado.get("fonte_id"), dado.get("origem"))
        if len(curva) < 3 or duracao <= 0 or not eventos:
            continue
        plano = max(float(e["start"]) + float(e.get("duration") or 0)
                    for e in eventos)
        if abs(plano - duracao) > TOLERANCIA_PLANO_S:
            fora += 1
            continue
        for evento in eventos:
            inicio = float(evento["start"])
            dur = float(evento.get("duration") or 0.0)
            if dur <= 0:
                continue
            antes = _valor_na_curva(curva, inicio / duracao)
            depois = _valor_na_curva(curva, (inicio + dur) / duracao)
            if antes is None or depois is None:
                continue
            reg = somas.setdefault(evento.get("type") or "?", {
                "tipo": evento.get("type") or "?", "perdido": 0.0,
                "segundos": 0.0, "ocorrencias": 0, "videos": set()})
            reg["perdido"] += antes - depois
            reg["segundos"] += dur
            reg["ocorrencias"] += 1
            reg["videos"].add(dado.get("youtube_id"))
    saida = []
    for reg in somas.values():
        segundos = reg["segundos"] or 1.0
        saida.append({"tipo": reg["tipo"], "perdido": reg["perdido"],
                      "segundos": reg["segundos"],
                      "ocorrencias": reg["ocorrencias"],
                      "videos": len(reg["videos"]),
                      "pontos_por_s": reg["perdido"] / segundos})
    saida.sort(key=lambda r: -r["pontos_por_s"])
    if saida:
        saida[0]["_fora"] = fora
    return saida


def _alfabeto_do_console() -> str:
    """Blocos quando o console aguenta; ASCII quando nao.

    `print(relatorio(...))` morria com UnicodeEncodeError no console cp1252
    do Windows, e o relatorio de metricas e exatamente o que se roda no
    terminal. Perder o desenho da curva e melhor que perder o comando.
    """
    codec = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        SPARK.encode(codec)
    except (LookupError, UnicodeEncodeError):
        return SPARK_ASCII
    return SPARK


def sparkline(curva: list, colunas: int = 40) -> str:
    if not curva:
        return ""
    valores = [w for _, w in curva]
    colunas = max(1, min(colunas, len(valores)))
    limites = [int(round(i * len(valores) / colunas)) for i in range(colunas + 1)]
    pontos = []
    for a, b in zip(limites, limites[1:]):
        fatia = valores[a:b] or valores[max(0, a - 1):a + 1]
        pontos.append(sum(fatia) / len(fatia))
    teto = max(pontos) or 1.0
    alfabeto = _alfabeto_do_console()
    return "".join(alfabeto[min(7, int(7 * p / teto))] for p in pontos)


# --------------------------------------------------------------- relatorio
def _medio(d: dict) -> str:
    """Duracao media formatada, ou tracinho.

    Existe para tirar uma f-string aninhada com as MESMAS aspas de dentro do
    relatorio: aquilo so compila no Python 3.12+, e este pacote declara
    suportar 3.10.
    """
    segundos = d.get("media_segundos")
    return f"{segundos:6.1f}" if segundos is not None else "    --"


def relatorio(dados: list[dict]) -> str:
    if not dados:
        return ("sem metricas salvas. Publique com `main.py publicar <id> --youtube` "
                "e rode `main.py metricas --atualizar`.")
    linhas = ["  id           views   likes  coment  media%   media s  variante  video"]
    for d in sorted(dados, key=lambda x: -(x.get("views") or 0)):
        media_pct = d.get("media_percentual")
        linhas.append(
            f"  {d.get('youtube_id', '?'):<12}{d.get('views', 0):>6}  {d.get('likes', 0):>6}"
            f"  {d.get('comentarios', 0):>6}  {(f'{media_pct:5.1f}' if media_pct is not None else '   --'):>6}"
            f"  {_medio(d):>8}"
            f"  {str(d.get('variante') or 'A'):<8}  {d.get('fonte_id', '')}:{d.get('perfil', '')}")
    erros = {d.get("erro") for d in dados if d.get("erro")}
    for erro in erros:
        linhas.append(f"\n  retencao indisponivel: {erro}")

    # Por FORMATO, normalizado pela idade. E a unica comparacao que funciona
    # com o volume de hoje, e a que diz se o formato curto vence o longo.
    formatos = comparar_formatos(dados)
    if len(formatos) > 1:
        linhas.append("\n  por formato — o veredito da Onda 15")
        linhas.append("    origem      n  ret%med  ret%mid   (n)  views/dia"
                      "  like%  dur s")
        for f in formatos:
            def _num(valor, casas=1, largura=7):
                return (f"{valor:{largura}.{casas}f}" if valor is not None
                        else " " * (largura - 2) + "--")
            like = _num((f["like_rate"] or 0) * 100, 1, 6) \
                if f["like_rate"] is not None else "    --"
            linhas.append(
                f"    {f['origem']:<10}{f['videos']:>3}{_num(f['retencao_media'])}"
                f"{_num(f['retencao_mediana'])}{f['com_retencao']:>6}"
                f"{f['views_por_dia']:>11.2f}{like}"
                f"{_num(f['duracao_mediana'], 0, 7)}")
        linhas.append("    (retencao e o criterio: com 4-20 views por video, "
                      "views/dia e muito mais ruidosa)")

    for d in dados:
        curva = d.get("curva")
        if not curva:
            continue
        eventos = timeline_de(d.get("fonte_id"), d.get("origem"))
        linhas.append(f"\n  {d.get('youtube_id')}  {d.get('titulo') or ''}")
        linhas.append(f"    retencao  {sparkline(curva)}")
        for q in quedas(d, eventos):
            linhas.append(f"    queda de {q['queda'] * 100:4.1f} pts aos {q['segundo']:4.1f}s "
                          f"({q['fracao'] * 100:3.0f}%): {q['evento']}")

    # O agregado que decide a montagem: custo POR SEGUNDO de cada tipo de
    # cena, somando todos os videos. E o unico numero aqui que fala do
    # FORMATO em vez de falar de um video.
    custos = custo_por_cena(dados)
    if custos:
        fora = custos[0].pop("_fora", 0)
        linhas.append("\n  custo por tipo de cena (todos os videos)")
        linhas.append("    cena            pts/s   perdido   tela s   vezes  videos")
        for c in custos:
            linhas.append(
                f"    {c['tipo']:<14}{c['pontos_por_s'] * 100:6.2f}"
                f"  {c['perdido'] * 100:7.1f}  {c['segundos']:7.1f}"
                f"  {c['ocorrencias']:6}  {c['videos']:6}")
        if fora:
            linhas.append(f"    ({fora} video(s) fora: o plano nao bate com "
                          f"a duracao publicada — provavel corte de Shorts)")

    # A/B: mesma geracao e perfil, variantes diferentes
    grupos: dict[tuple, list[dict]] = {}
    for d in dados:
        grupos.setdefault((d.get("fonte_id"), d.get("perfil")), []).append(d)
    for (fonte, perfil), lista in grupos.items():
        variantes = {d.get("variante") or "A" for d in lista}
        if len(variantes) < 2:
            continue
        linhas.append(f"\n  A/B {fonte}:{perfil}")
        for d in sorted(lista, key=lambda x: str(x.get("variante"))):
            pct = d.get("media_percentual")
            linhas.append(f"    gancho {d.get('variante')}: {d.get('views', 0)} views, "
                          f"retencao media {(f'{pct:.1f}%' if pct is not None else '--')}")
    return "\n".join(linhas)


def cli(atualizar: bool = False, como_json: bool = False) -> int:
    dados = []
    if atualizar:
        try:
            dados = atualizar_com_log()
        except Exception as exc:
            print(f"metricas: {exc}")
            return 1
    if not dados:
        dados = carregar_salvas()
    if como_json:
        print(json.dumps(dados, ensure_ascii=False, indent=2))
    else:
        print(relatorio(dados))
    return 0


def atualizar_com_log() -> list[dict]:
    """Os DOIS canais, reconciliando antes de buscar.

    Era `atualizar(log=print)` — so builds, e sem reconciliar. O comando
    "oficial" (`main.py metricas --atualizar`) era entao o unico caminho que
    NAO fazia o servico completo: quem rodasse ele para conferir o canal de
    historias veria zero e concluiria que nao ha metrica, quando o que falta
    e o `youtube_id` que a reconciliacao por titulo preenche.
    """
    resultado = atualizar_tudo(log=print)
    saida = []
    for canal in CANAIS:
        for dado in resultado.get(canal) or []:
            dado.setdefault("canal", canal)
            saida.append(dado)
    return saida


__all__ = ["ESCOPO_ANALYTICS", "atualizar", "carregar_salvas", "cli", "publicados",
           "custo_por_cena", "quedas", "registrar_publicacao",
           "registrar_publicado", "relatorio",
           "retencao", "sparkline",
           "timeline_de"]
