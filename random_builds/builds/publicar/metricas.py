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

import contextlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# `titulos` e importado no topo de proposito: `casar_ids` usa `titulos.corte`
# e, sem esta linha, a reconciliacao da madrugada morria com
# `NameError: name 'titulos' is not defined` — so no caminho em que a linha
# tem hora e titulo casavel, que e justamente o caminho util. Ficou assim de
# 17 a 27/09/2026 porque o unico import era local, dentro de outra funcao.
from . import titulos

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
def em_lista(prova) -> list:
    """O campo `prova` do ledger e SEMPRE lista.

    A guarda mora aqui, e nao em cada chamador, porque em 16/09/2026 um deles
    (o registro do TikTok) gravou dicionario enquanto todos os outros
    gravavam lista. Duas formas do mesmo campo no mesmo arquivo e a proxima
    pergunta sem resposta unica — e quem for ler isso na pagina de
    confiabilidade nao tem como saber qual das duas esperar.
    """
    if prova is None:
        return []
    if isinstance(prova, list):
        return prova
    return [prova]


def publicado(linha) -> bool:
    """Esta linha do ledger quer dizer que o video SAIU? A resposta unica.

    Ate 16/09/2026 cada leitor respondia com `bool(linha.get("url"))`. Mas o
    `url` guardava tres coisas — o link, a frase de estado ("publicado no
    YouTube (com a confirmacao extra)") e, no TikTok, sempre a frase — e a
    frase contava como "saiu". E por isso que rascunho e publicacao de
    verdade ficavam identicos para todo filtro do projeto.

    Contrato novo (passo 1 de 2): o campo `publicado`, quando existe, manda.
    Linha antiga sem ele cai no criterio de antes, para nenhum leitor mudar
    de resposta sem que o ledger tenha sido migrado. O passo 2 — reescrever
    as linhas antigas — e decisao do Adrian.
    """
    if not isinstance(linha, dict):
        return False
    if "publicado" in linha:
        return bool(linha["publicado"])
    return bool(linha.get("url"))


def prova_ok(laudo: dict | list | None) -> bool | None:
    """O laudo sustenta a afirmacao "publiquei"?

    TRES estados, e o terceiro nao e detalhe: `None` quer dizer "nao sei",
    e e o que sai para toda linha anterior a esta medicao. Se ausencia de
    prova valesse `False`, o alarme acenderia para o acervo inteiro no
    primeiro dia e ninguem olharia o alarme de novo.

    Prova de verdade e a que o outro lado pode desmentir: id do video, ou ao
    menos a confirmacao vista na tela. "A funcao nao levantou excecao" nao e
    prova — foi exatamente o que 29 rascunhos devolveram entre 10 e 15 de
    setembro de 2026.

    Aceita uma LISTA porque uma parte de historia longa vira dois Shorts: sao
    dois uploads para uma linha de ledger, e meia publicacao nao e publicacao
    — se um pedaco nao tem prova, a linha inteira nao tem.
    """
    if isinstance(laudo, list):
        if not laudo:
            return None
        return all(prova_ok(um) is True for um in laudo)
    if not laudo:
        return None
    if laudo.get("estado") != "publicado":
        return False
    return bool(laudo.get("youtube_id") or laudo.get("url")
                or laudo.get("confirmado"))


# ------------------------------------------------------ trava do ledger
# Todo escritor do ledger usa a MESMA trava, `ledger__<canal>`. Sem ela, uma
# reescrita (a reconciliacao da madrugada, a cura) le o arquivo, pensa, e
# grava por cima — e a linha que a postagem acrescentou no meio SOME.
# Publicacao que aconteceu e sumiu do ledger vira REPOSTAGEM, entao a regra e
# assimetrica:
#   - quem ACRESCENTA uma publicacao espera muito e, se ainda assim nao
#     conseguir, grava do mesmo jeito e avisa no diario;
#   - quem REESCREVE desiste se a trava estiver ocupada, e tenta outro dia.
PACIENCIA_DO_ESCRITOR = 120.0


def nome_da_trava(canal: str) -> str:
    return f"ledger__{canal}"


def acrescentar_ao_ledger(caminho: Path, linha: dict, canal: str,
                          paciencia: float = PACIENCIA_DO_ESCRITOR) -> None:
    """Acrescenta uma linha. NUNCA perde a linha por causa da trava."""
    from .. import travas
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with travas.trava(nome_da_trava(canal), esperar=paciencia) as minha:
        with open(caminho, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    if not minha:
        with contextlib.suppress(Exception):
            from .. import atividade
            atividade.registrar(
                "publicacao", "erro",
                f"gravei no ledger de {canal} SEM a trava (ocupada por "
                f"{paciencia:.0f} s): {linha.get('video_id')} "
                f"({linha.get('plataforma')}). Confira se uma reescrita "
                "simultanea nao apagou esta linha.", canal)


def reescrever_ledger(caminho: Path, linhas: list) -> None:
    """Troca o arquivo inteiro de uma vez. Quem chama segura a trava."""
    temporario = caminho.with_name(f"{caminho.name}.{os.getpid()}.tmp")
    with open(temporario, "w", encoding="utf-8") as fh:
        for linha in linhas:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    os.replace(temporario, caminho)


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
    if "prova" in linha:
        linha["prova"] = em_lista(linha["prova"])
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
    acrescentar_ao_ledger(Path(REGISTRO), linha, "builds")
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
# QUANTAS CHAMADAS CADA COLETA CUSTA. A Data API cobra cota por chamada
# (videos, playlistItems e channels: 1 unidade cada, de 10.000 por dia) e a
# Analytics tem cota propria. Ninguem sabia quanto uma noite gastava; agora
# cada parte da coleta grava o seu numero na marca do dia.
CHAMADAS: dict = {"data": 0, "analytics": 0, "token": 0}

# UMA segunda tentativa para queda de CONEXAO, e so para ela. Das onze
# noites sem metrica do YouTube (17 a 28/09/2026), tres morreram assim: no
# refresh do token (`oauth2.googleapis.com`, 17 e 19/09) e no playlistItems
# (`SSLEOFError`, 17 e 28/09). Resposta ruim do Google (401, 403, 500) nao e
# tentada de novo — ela diz alguma coisa, e repetir so gasta cota.
PAUSA_ANTES_DE_TENTAR_DE_NOVO_S = 5.0


def _get(api: str, url: str, **kwargs):
    """`requests.get` que conta a chamada e tenta de novo UMA vez se a
    conexao cair. Qualquer outra coisa sobe como estava."""
    import time

    import requests
    for tentativa in (1, 2):
        CHAMADAS[api] = CHAMADAS.get(api, 0) + 1
        try:
            return requests.get(url, **kwargs)
        except (requests.ConnectionError, requests.Timeout):
            if tentativa == 2:
                raise
            time.sleep(PAUSA_ANTES_DE_TENTAR_DE_NOVO_S)


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
    import time

    import requests
    for tentativa in (1, 2):
        CHAMADAS["token"] = CHAMADAS.get("token", 0) + 1
        try:
            return token_de_acesso(credenciais), credenciais
        except (requests.ConnectionError, requests.Timeout):
            # O refresh caiu por rede (17 e 19/09/2026), nao foi recusado.
            if tentativa == 2:
                raise
            time.sleep(PAUSA_ANTES_DE_TENTAR_DE_NOVO_S)


def _iso_para_segundos(texto: str) -> float:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", texto or "")
    if not m:
        return 0.0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def estatisticas(youtube_ids: list[str], token: str) -> dict:
    """views/likes/comentarios/duracao por id (Data API v3, escopo readonly)."""
    saida = {}
    for i in range(0, len(youtube_ids), 50):
        lote = youtube_ids[i:i + 50]
        resposta = _get(
            "data", API_VIDEOS, timeout=30,
            # `status` foi acrescentado em 16/09/2026 e e o que torna a
            # conferencia possivel: `privacyStatus == "private"` e a
            # assinatura EXATA do rascunho que passou 5 dias contado como
            # publicado. Mesmo escopo readonly, nenhuma permissao nova.
            params={"part": "statistics,contentDetails,snippet,status",
                    "id": ",".join(lote)},
            headers={"Authorization": f"Bearer {token}"})
        if not resposta.ok:
            raise RuntimeError(f"Data API {resposta.status_code}: {resposta.text[:200]}")
        for item in resposta.json().get("items", []):
            st = item.get("statistics", {})
            detalhes = item.get("contentDetails", {})
            estado = item.get("status", {})
            saida[item["id"]] = {
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comentarios": int(st.get("commentCount", 0)),
                "duracao": _iso_para_segundos(detalhes.get("duration")),
                "publicado_em": item.get("snippet", {}).get("publishedAt"),
                "privacidade": estado.get("privacyStatus"),
                "upload": estado.get("uploadStatus"),
                # "sd" aqui e INDICIO, nao veredito: o campo reflete a melhor
                # renderizacao ja disponivel e demora a virar "hd".
                "definicao": detalhes.get("definition"),
            }
    return saida


class ListaDoCanal(list):
    """Os videos do canal, levando junto quantos PUBLICOS o canal declara
    (`statistics.videoCount`, lido na mesma chamada do `channels`).

    `declarados`: `None` quando a lista nao veio do canal (os dubles dos
    testes, que nao tem o que conferir); `-1` quando o canal nao disse — e
    ai a lista nao pode ser dada por inteira.
    """
    declarados = None


def enviados(token: str, quantos: int | None = None) -> list[dict]:
    """Os videos do canal: `{youtube_id, titulo, publicado_em, privacidade}`.

    Sai das playlists do canal e nao do `search`, porque `search` e eventual:
    video publicado ha minutos costuma nao aparecer nele, e e exatamente esse
    que precisamos casar.

    A PLAYLIST DE ENVIOS NAO TRAZ TODOS OS SHORTS. Medido em 28/09/2026 as
    21:55, canal de builds: `statistics.videoCount` 151 publicos; a leitura
    antiga (so a `UU`) trazia 178 linhas, 143 ids distintos e 125 publicos.
    A lista agora e a UNIAO de envios com Shorts, lida pela MESMA funcao da
    recuperacao (`recuperar._ids_do_canal`: `UU` + `UUSH`, sem repetir,
    passando de novo ate a playlist parar de mexer) — e nao uma copia dela,
    que envelheceria separada. Depois, os videos por id (1 unidade a cada
    50), que dao titulo, hora e privacidade. `publicado_em` e o do video; o
    do item da playlist era igual nos 200 medidos.

    Quem precisa saber se a lista veio inteira pergunta a `conferir_lista`:
    a lista leva `declarados`. `quantos` corta a lista (e ela vai dar curta,
    de proposito); o padrao e o canal inteiro — o teto antigo de 200 ia
    cortar o canal de historias, que ja tem 195.

    As paginas da playlist passam pelo `_get` da recuperacao e NAO entram em
    `CHAMADAS`; so o `channels` e os `videos` daqui entram.
    """
    from . import recuperar
    cabecalho = {"Authorization": f"Bearer {token}"}
    resposta = _get("data", API_CANAIS, timeout=30, headers=cabecalho,
                    params={"part": "contentDetails,statistics",
                            "mine": "true"})
    if not resposta.ok:
        raise RuntimeError(motivo_da_recusa(resposta))
    saida = ListaDoCanal()
    saida.declarados = -1
    itens = resposta.json().get("items") or []
    if not itens:
        return saida
    lista = (itens[0].get("contentDetails", {})
             .get("relatedPlaylists", {}).get("uploads"))
    if not lista:
        return saida
    saida.declarados = recuperar._declarados(itens[0])
    ids = recuperar._ids_do_canal(token, lista)
    if quantos is not None:
        ids = ids[:max(0, int(quantos))]
    for i in range(0, len(ids), 50):
        resposta = _get("data", API_VIDEOS, timeout=30, headers=cabecalho,
                        params={"part": "snippet,status",
                                "id": ",".join(ids[i:i + 50]),
                                "maxResults": 50})
        if not resposta.ok:
            raise RuntimeError(motivo_da_recusa(resposta))
        for item in resposta.json().get("items", []):
            snip = item.get("snippet") or {}
            saida.append({"youtube_id": item.get("id"),
                          "titulo": snip.get("title") or "",
                          "publicado_em": snip.get("publishedAt"),
                          "privacidade": (item.get("status") or {})
                          .get("privacyStatus")})
    return saida


def conferir_lista(lista) -> dict | None:
    """A lista do canal veio inteira? `None` quando nao ha como saber.

    `{videos, publicos, declarados, completa, motivo}`. Conta PUBLICO
    DISTINTO, porque `statistics.videoCount` conta publicos: privado nao
    entra na conta nem do lado do canal. Por isso privado que falta nao tem
    como ser visto aqui — medido em 28/09/2026, oito privados do ledger de
    builds nao estavam em nenhuma das duas listas.

    Caso zero: canal que declara 0 com lista vazia e lista INTEIRA; canal
    que nao declarou (`-1`) nunca e.
    """
    declarados = getattr(lista, "declarados", None)
    if declarados is None:
        return None
    ids, publicos = set(), set()
    for v in lista or ():
        vid = v.get("youtube_id") or v.get("id")
        if not vid:
            continue
        ids.add(vid)
        if v.get("privacidade") == "public":
            publicos.add(vid)
    if declarados < 0:
        motivo = ("o canal nao disse quantos publicos tem: nao da para "
                  "saber se a lista veio inteira")
    elif len(publicos) < declarados:
        motivo = (f"a lista do canal trouxe {len(publicos)} publicos e o "
                  f"canal declara {declarados}")
    else:
        motivo = ""
    return {"videos": len(ids), "publicos": len(publicos),
            "declarados": int(declarados), "completa": not motivo,
            "motivo": motivo}


def _chave_de_titulo(texto: str) -> str:
    """Titulo comparavel. MOVIDA para `titulos.chave`; aqui ficou o apelido.

    Ela nasceu para reconciliar id faltante, e passou a servir tambem para
    barrar titulo repetido na fila. Sao dois usos da MESMA pergunta ("estes
    dois titulos sao o mesmo?"), e responder com dois criterios seria criar
    a proxima divergencia do projeto.
    """
    from .titulos import chave
    return chave(texto)


# Quanto a hora do video no canal pode se afastar da hora da linha. Subir e
# publicar leva minutos; duas horas cobre um Studio lento sem alcancar o
# horario seguinte da grade na maior parte do dia.
FOLGA_DE_CASAMENTO = timedelta(hours=2)


def _instante(texto) -> datetime | None:
    """Um carimbo do ledger (local, sem fuso) ou do YouTube (UTC, com Z),
    sempre como hora LOCAL sem fuso — para os dois poderem ser subtraidos."""
    if not texto:
        return None
    try:
        quando = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    if quando.tzinfo is not None:
        quando = quando.astimezone().replace(tzinfo=None)
    return quando


def casar_ids(linhas: list, videos: list,
              folga: timedelta = FOLGA_DE_CASAMENTO) -> list:
    """Quais linhas sem id ganham qual video. PURA: nao le nem grava nada.

    Casa pelo TITULO, com duas guardas que faltavam (16/09/2026). A linha A
    de `generation_00081` (15/09 21:39) saiu sem link, e a reconciliacao lhe
    deu o id do upload B (16/09 00:39), porque A e B tem o mesmo titulo e o
    canal lista o mais novo primeiro. O ledger passou a afirmar que A foi ao
    ar com o video de B.

      1. HORA: o video tem de ter ido ao ar perto da hora da linha (ou do
         `agendado_para`, quando houve agendamento) — nos DOIS sentidos. No
         caso real o video era tres horas POSTERIOR a linha.
      2. DONO: id que ja pertence a outra linha do ledger nao e dado de novo.
         Tambem nao a duas linhas na mesma rodada.

    Entre candidatos validos, fica o mais proximo da hora da linha. Sem
    candidato valido, a linha fica sem id — "nao sei" e melhor que um id
    errado, que a conferencia depois usaria como prova.
    """
    usados = {str(L.get("youtube_id")) for L in linhas if L.get("youtube_id")}
    por_titulo: dict = {}
    for video in videos or ():
        chave = _chave_de_titulo(video.get("titulo"))
        if chave and video.get("youtube_id"):
            por_titulo.setdefault(chave, []).append(video)

    pares = []
    for indice, linha in enumerate(linhas):
        if linha.get("youtube_id") or not linha.get("titulo"):
            continue
        if linha.get("plataforma", "youtube") != "youtube":
            continue
        referencia = _instante(linha.get("agendado_para")) \
            or _instante(linha.get("quando"))
        if referencia is None:
            continue
        # UM PEDACO NAO E A LINHA INTEIRA, e esta guarda nasceu em 17/09/2026
        # junto com a que fez `titulos.chave` ignorar o sufixo "(1 de 2)".
        # Aquela mudanca era necessaria (sem ela o ledger nunca casava com o
        # canal, e eu cheguei a chamar de "publicacao fantasma" cinco videos
        # que estavam no ar), mas ela tem um efeito colateral aqui: a linha de
        # uma parte passou a casar com UM dos dois Shorts dela, e a
        # reconciliacao gravaria metade da parte como se fosse a parte.
        #
        # A regra: linha sem corte so casa com video sem corte. Linha e video
        # de pedacos casam entre si (um dia o ledger pode guardar o pedaco).
        # Quem sabe juntar os dois pedacos numa linha e a cura, que tem
        # `_pedacos` para isso e exige TODOS eles — meia parte nao e
        # publicacao.
        corte_da_linha = titulos.corte(linha["titulo"])
        candidatos = []
        for video in por_titulo.get(_chave_de_titulo(linha["titulo"]), ()):
            if video["youtube_id"] in usados:
                continue
            if titulos.corte(video.get("titulo")) != corte_da_linha:
                continue
            no_ar = _instante(video.get("publicado_em"))
            if no_ar is None or abs(no_ar - referencia) > folga:
                continue
            candidatos.append((abs(no_ar - referencia), video))
        if not candidatos:
            continue
        _, escolhido = min(candidatos, key=lambda c: c[0])
        usados.add(escolhido["youtube_id"])
        pares.append((indice, escolhido))
    return pares


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
    # A rede vem ANTES da trava: segurar o ledger durante uma chamada a API
    # faria a postagem esperar por ela.
    videos = enviados(token)
    # LISTA CURTA ACUSA, MAS NAO PARA ESTA. Casar e so dar id a linha cujo
    # video foi achado, com hora e dono conferidos: com video faltando, a
    # linha dele fica sem id (e o sinal de cobertura acusa), nunca com o id
    # errado. Parar aqui derrubaria a coleta de metricas da noite inteira.
    conferida = conferir_lista(videos)
    if conferida and not conferida["completa"]:
        log(f"[{canal}] ATENCAO: {conferida['motivo']} — a reconciliacao "
            "pode deixar linha sem id.")
    from .. import travas
    with travas.trava(nome_da_trava(canal), esperar=30.0) as minha:
        if not minha:
            log(f"[{canal}] ledger ocupado por outro escritor; reconcilio "
                "na proxima vez.")
            return 0
        # RELIDO dentro da trava: a postagem pode ter acrescentado linhas
        # enquanto a lista do canal era baixada.
        linhas = publicados(canal)
        achados = 0
        for indice, video in casar_ids(linhas, videos):
            linha = linhas[indice]
            linha["youtube_id"] = video["youtube_id"]
            linha["url"] = f"https://youtu.be/{video['youtube_id']}"
            linha["publicado_em"] = video.get("publicado_em")
            achados += 1
        if achados:
            # Reescrito inteiro porque o ledger e a linha do tempo: ordem e
            # conteudo das outras linhas nao mudam, so os campos preenchidos.
            reescrever_ledger(registro, linhas)
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
        # 401 AQUI NUNCA E REVOGACAO. Refresh revogado falha ANTES, em
        # `token_de_acesso`, com `invalid_grant`. Chegar ate esta chamada
        # quer dizer que o refresh FUNCIONOU e a API recusou o token de
        # acesso que foi mandado. Medido em 16/09/2026: a conferencia mandava
        # a tupla `(token, credenciais)` no cabecalho, esta funcao dizia
        # "token invalido ou revogado", e o Adrian ouviu que as tres
        # credenciais estavam mortas quando duas estavam vivas.
        return (f"o Google recusou o token de acesso enviado "
                f"({resposta.status_code} {razao or 'sem reason'}: "
                f"{recado[:200] or 'sem mensagem'}). O refresh funcionou, "
                "entao nao e credencial revogada: confira o que vai no "
                "cabecalho Authorization. So se persistir, reautorize: "
                f"{comando_oauth()}")
    if razao == "insufficientPermissions":
        return f"falta o escopo yt-analytics.readonly — rode: {comando_oauth()}"
    return f"Analytics API {resposta.status_code} ({razao or 'sem reason'}): {recado[:200]}"


def retencao(youtube_id: str, token: str, desde: str) -> dict:
    """Media de visualizacao e a CURVA (Analytics API). Sem o escopo, devolve
    `erro` explicando o que falta — nunca levanta."""
    hoje = date.today().isoformat()
    base = {"ids": "channel==MINE", "startDate": desde, "endDate": hoje,
            "filters": f"video=={youtube_id}"}
    cab = {"Authorization": f"Bearer {token}"}
    resumo = _get("analytics", API_ANALYTICS, timeout=30, headers=cab, params={
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
    if not linhas[0][0]:
        # LINHA DE ZEROS TAMBEM NAO E MEDIDA. Para video que ninguem viu —
        # os rascunhos privados de 12/09/2026, `ReZ81HQB1pU` e `YS7PiOSlmBc`
        # — a Analytics devolve [0, 0, 0], e isso era gravado como "retencao
        # 0%". Em 28/09 esses dois zeros puxavam a media do duelo de 47,5%
        # para 34,0%. Retencao de zero espectadores nao existe.
        return {"views_analytics": 0,
                "erro": "nenhuma view na Analytics: nao ha retencao para "
                        "medir (nao e 0%)."}
    saida = {"views_analytics": linhas[0][0], "media_segundos": linhas[0][1],
             "media_percentual": linhas[0][2]}
    curva = _get("analytics", API_ANALYTICS, timeout=30, headers=cab, params={
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


def partes() -> list:
    """As PARTES da coleta: cada canal, cada plataforma, cada uma por si."""
    return [(canal, plataforma) for canal in CANAIS
            for plataforma in ("youtube", "tiktok")]


def nome_da_parte(canal: str, plataforma: str) -> str:
    """`builds` / `builds_tiktok`: as chaves que a marca sempre usou."""
    return canal if plataforma == "youtube" else f"{canal}_tiktok"


def coletar_parte(canal: str, plataforma: str, log=print) -> tuple:
    """`(ficha, videos)` de UMA parte. Nunca levanta: a falha vira ficha.

    A ficha diz o que aconteceu com numero — `ok` (mediu videos), `vazio`
    (nao havia o que medir) ou `erro` (com a excecao) — e quanto custou em
    chamadas de API. E o que faltava para "a coleta morreu" deixar de ser
    igual a "a coleta mediu zero".
    """
    import time
    antes = dict(CHAMADAS)
    comeco = time.monotonic()
    resumo: dict = {}
    erro = None
    try:
        if plataforma == "youtube":
            reconciliar(canal, log=log)
            videos = atualizar(log=log, canal=canal)
        else:
            from . import tiktok_metricas
            videos = tiktok_metricas.coletar(canal, log=log, resumo=resumo)
    except Exception as exc:                                  # noqa: BLE001
        videos, erro = [], f"{type(exc).__name__}: {exc}"
        onde = "do TikTok " if plataforma == "tiktok" else ""
        log(f"[{canal}] metrica {onde}nao atualizou: {exc}")
    gasto = {api: CHAMADAS.get(api, 0) - antes.get(api, 0) for api in CHAMADAS}
    # VIDEO, NAO LINHA. O ledger tem linhas com o mesmo id (o mesmo video
    # registrado duas vezes, I9ETJSGR1A0 em 15/09): em 28/09 a marca disse
    # 126 e o disco tinha 121 arquivos. Conta o que o disco guarda — um
    # arquivo por id —, e as linhas ficam a parte.
    chave_do_id = "youtube_id" if plataforma == "youtube" else "tiktok_id"
    ids = {str(v.get(chave_do_id)) for v in videos or ()
           if isinstance(v, dict) and v.get(chave_do_id)}
    ficha = {"estado": "erro" if erro else ("ok" if videos else "vazio"),
             "videos": len(ids) if ids else len(videos or []),
             "linhas": len(videos or []),
             "quando": datetime.now().isoformat(timespec="seconds"),
             "duracao_s": round(time.monotonic() - comeco, 1),
             **resumo}
    if plataforma == "youtube":
        ficha["chamadas"] = {api: n for api, n in gasto.items() if n}
    if erro:
        ficha["erro"] = erro[:300]
    return ficha, videos or []


def atualizar_uma_vez_por_dia(log=print, agora=None,
                              chave: str | None = None) -> bool:
    """A coleta da noite, uma vez por noite POR PARTE. `True` = noite fechada.

    UMA VEZ, e nao a cada disparo: views nao mudam de hora em hora, e cada
    passada custa cota da API do YouTube. Mas uma vez por PARTE, e so a parte
    que DEU CERTO fica feita. Ate 28/09/2026 a marca era gravada depois de
    qualquer passada, com falha ou sem: onze noites seguidas (17 a 28/09) o
    YouTube morreu (NameError, SSLError), a marca disse "feito" e a rodada
    seguinte nem tentou. O log ainda escrevia "metricas da noite
    atualizadas".

    Agora a parte que falha fica pendente — a proxima rodada da mesma noite
    tenta so ela — e vira UMA linha de erro no diario (fabrica `metricas`),
    que chega ao celular. Uma por noite para o mesmo tipo de erro: quatro
    rodadas com o token morto nao sao quatro noticias.

    `chave` substitui a data quando "o dia" nao e o do calendario: a
    madrugada atravessa a meia-noite, e com a chave da noite roda uma vez.

    NUNCA LEVANTA: OAuth vencido, rede fora ou Studio sem login nao podem
    derrubar a rodada da noite.
    """
    from .. import atividade

    agora = agora or datetime.now()
    hoje = chave or agora.strftime("%Y-%m-%d")
    fichas = dict(partes_da_marca(ler_marca()))
    pendentes = [(c, p) for c, p in partes()
                 if not _feita(fichas.get(nome_da_parte(c, p)), hoje)]
    if not pendentes:
        return False
    for canal, plataforma in pendentes:
        nome = nome_da_parte(canal, plataforma)
        anterior = fichas.get(nome) or {}
        ficha, _videos = coletar_parte(canal, plataforma, log=log)
        ficha["chave"] = hoje
        if ficha["estado"] == "erro":
            mesma_noite = (anterior.get("chave") == hoje
                           and anterior.get("estado") == "erro")
            ficha["tentativas"] = (int(anterior.get("tentativas") or 0) + 1
                                   if mesma_noite else 1)
            for campo in ("ultimo_ok", "videos_no_ultimo_ok"):
                if anterior.get(campo):
                    ficha[campo] = anterior[campo]
            tipo = str(ficha.get("erro") or "").split(":")[0]
            if not (mesma_noite and anterior.get("avisado") == tipo):
                rotulo = ("do TikTok" if plataforma == "tiktok"
                          else "do YouTube")
                atividade.registrar(
                    "metricas", atividade.ERRO,
                    f"coleta {rotulo} de {canal} falhou: {ficha.get('erro')}"
                    " — a noite fica pendente e a proxima rodada tenta de novo",
                    canal=canal)
            ficha["avisado"] = tipo
        else:
            ficha["ultimo_ok"] = ficha["quando"]
            ficha["videos_no_ultimo_ok"] = ficha["videos"]
        fichas[nome] = ficha
        # GRAVADA A CADA PARTE: se a rodada for derrubada no meio, o que ja
        # deu certo nao e coletado de novo.
        _gravar_marca(hoje, fichas)
    completa = all(_feita(fichas.get(nome_da_parte(c, p)), hoje)
                   for c, p in partes())
    log("[metricas] " + hoje + ": " + " · ".join(
        _resumo_da_parte(nome_da_parte(c, p), fichas.get(nome_da_parte(c, p)))
        for c, p in partes())
        + ("" if completa else " — noite PENDENTE"))
    return completa


def _feita(ficha, chave: str) -> bool:
    return (isinstance(ficha, dict) and ficha.get("chave") == chave
            and ficha.get("estado") in ("ok", "vazio"))


def partes_da_marca(marca) -> dict:
    """`{parte: ficha}` da marca do dia, no formato novo ou no antigo."""
    if not isinstance(marca, dict):
        return {}
    if isinstance(marca.get("partes"), dict):
        return marca["partes"]
    return _partes_da_marca_antiga(marca)


def _partes_da_marca_antiga(marca: dict) -> dict:
    """A marca de antes de 28/09/2026 so tinha `videos` por parte.

    Zero ali era a assinatura da coleta que morreu (a das 01:20 de 28/09
    gravou `builds: 0`), entao so conta como feita a parte com video.
    """
    saida = {}
    for nome, quantos in (marca.get("videos") or {}).items():
        ficha = {"chave": marca.get("dia"), "videos": int(quantos or 0),
                 "estado": "ok" if quantos else "erro",
                 "quando": marca.get("quando")}
        if quantos:
            ficha["ultimo_ok"] = marca.get("quando")
            ficha["videos_no_ultimo_ok"] = int(quantos)
        saida[nome] = ficha
    return saida


def _resumo_da_parte(nome: str, ficha) -> str:
    ficha = ficha or {}
    texto = f"{nome} {ficha.get('estado', '?')} {ficha.get('videos', 0)}"
    chamadas = ficha.get("chamadas") or {}
    if chamadas:
        texto += " (" + ", ".join(f"{n} {api}" for api, n in
                                  sorted(chamadas.items())) + ")"
    if ficha.get("casados") is not None:
        texto += (f" ({ficha.get('casados')} de {ficha.get('envios')} envios, "
                  f"lista {ficha.get('lista', '?')})")
    return texto


def _gravar_marca(chave: str, fichas: dict) -> None:
    """Grava a marca inteira de uma vez (arquivo provisorio + troca)."""
    completa = all(_feita(fichas.get(nome_da_parte(c, p)), chave)
                   for c, p in partes())
    dados = {
        "dia": chave,
        # `completa` e o que diz se a noite FECHOU. `dia` sozinho ja mentiu.
        "completa": completa,
        "quando": datetime.now().isoformat(timespec="seconds"),
        # O numero de sempre, por parte — agora so da tentativa desta noite.
        "videos": {nome: int((f or {}).get("videos") or 0)
                   for nome, f in fichas.items()},
        "partes": fichas,
    }
    try:
        MARCA_DO_DIA.parent.mkdir(parents=True, exist_ok=True)
        provisorio = MARCA_DO_DIA.with_name(MARCA_DO_DIA.name + ".tmp")
        with open(provisorio, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, ensure_ascii=False, indent=2)
        os.replace(provisorio, MARCA_DO_DIA)
    except OSError:
        pass          # no pior caso a parte roda de novo na proxima rodada


def ler_marca() -> dict | None:
    """A marca do dia como esta no disco. `None` = nao consegui ler."""
    try:
        with open(MARCA_DO_DIA, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def atualizar_tudo(log=print) -> dict:
    """Os dois canais, e o que falhar num nao derruba o outro.

    O TIKTOK NUM `try` PROPRIO (dentro de `coletar_parte`). Ele le o Studio
    pelo navegador, e login caido la e coisa comum — nao pode custar a
    metrica do YouTube. Chave separada para quem conta quantos videos cada
    lado atualizou nao somar plataforma com plataforma.
    """
    saida = {}
    for canal, plataforma in partes():
        _ficha, videos = coletar_parte(canal, plataforma, log=log)
        saida[nome_da_parte(canal, plataforma)] = videos
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
    privados: dict[str, int] = {}
    for d in dados:
        if views_por_dia(d, agora) is None:
            continue
        origem = str(d.get("origem") or "?")
        if str(d.get("privacidade") or "").lower() == "private":
            # RASCUNHO NAO E AMOSTRA DE FORMATO. Ninguem pode ter visto um
            # video privado: em 28/09/2026 dois duelos de 12/09 (rascunhos do
            # "Publicar mesmo assim") entravam com 0 view e 0% de retencao.
            privados[origem] = privados.get(origem, 0) + 1
            continue
        grupos.setdefault(origem, []).append(d)
    saida = []
    for origem, lista in grupos.items():
        taxas = [views_por_dia(d, agora) for d in lista]
        views = sum(d.get("views") or 0 for d in lista)
        duracoes = sorted(float(d["duracao"]) for d in lista if d.get("duracao"))
        # Retencao so entra de quem TEM retencao. Video sem linha da
        # Analytics nao vira 0% na media — e a mesma regra de `retencao()`,
        # que se recusa a gravar zero quando a API nao devolveu nada. E
        # linha de ZERO VIEW tambem nao e retencao: arquivos gravados antes
        # de 28/09 guardaram 0% para video que ninguem viu.
        retencoes = sorted(float(d["media_percentual"]) for d in lista
                           if d.get("media_percentual") is not None
                           and (d.get("views_analytics")
                                if d.get("views_analytics") is not None
                                else d.get("views") or 0) > 0)
        saida.append({
            "origem": origem,
            "videos": len(lista),
            "privados_fora": privados.get(origem, 0),
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
        # `_atualizado_em.json` (a marca do dia) mora na mesma pasta e nao e
        # video: lido como metrica, virava um "video" sem id nas medias. Pelo
        # NOME EXATO, e nao por "comeca com _": id do YouTube pode comecar
        # com sublinhado (`_bHp95XZpgc`, medido em 28/09/2026).
        if arquivo.name == Path(MARCA_DO_DIA).name:
            continue
        try:
            with open(arquivo, encoding="utf-8-sig") as fh:
                dado = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(dado, dict):
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
