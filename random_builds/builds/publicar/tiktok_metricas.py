# -*- coding: utf-8 -*-
"""Metricas do TikTok, lidas do TikTok Studio com o login que ja publica.

POR QUE PELO STUDIO, e nao pela API oficial. A API do TikTok (Display API,
escopo `video.list`) entrega views, curtidas, comentarios e
compartilhamentos — e so. Nao tem tempo assistido nem curva de retencao, e
exige app registrado, sandbox e revisao com video de demonstracao. O Studio,
aberto com o perfil que ja publica, entrega tudo isso e mais, e sem cadastro
nenhum. Medido em 13/09/2026 nas duas contas.

DE ONDE VEM CADA NUMERO. Nada aqui le a tela: a pagina do Studio carrega JSON
por dentro, e este modulo escuta essas respostas.

    creator/manage/item_list   todos os posts: id, hora exata da postagem,
                               legenda, duracao, views, curtidas,
                               comentarios, compartilhamentos, salvamentos
    aweme/v2/data/insight      por video: tempo medio assistido, taxa de
                               conclusao, curva de retencao, origem do
                               trafego, seguidores ganhos

COMO UM POST VIRA UM VIDEO NOSSO. O TikTok nao devolve id nenhum ao publicar,
entao o ledger so guarda a frase de status. O casamento e pela HORA: o
`post_time` do Studio bate com o `quando` do ledger com 1 a 7 segundos de
diferenca (21 de 21 nas historias, 19 de 19 nos builds). E a legenda
confirma: "Parte 3 de 6" tem de ser a parte que o ledger diz. Hora sozinha
erraria no dia em que duas partes saem no mesmo minuto — ja aconteceu, no
escoamento de 10/09.

ONDE GRAVA. Numa pasta PROPRIA, `_metricas_tiktok/`, e nao junto com as do
YouTube. Os experimentos e o painel indexam `_metricas/` pelo `youtube_id`, e
um arquivo sem esse campo no meio corromperia as medias em silencio.

A CURVA fica no mesmo formato da do YouTube — pares (fracao do video,
fracao da audiencia ainda assistindo) — para quem ja sabe ler uma ler a
outra.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

URL_CONTEUDO = "https://www.tiktok.com/tiktokstudio/content"
URL_ANALISE = "https://www.tiktok.com/tiktokstudio/analytics/{item_id}"
LISTA = "creator/manage/item_list"
INSIGHT = "aweme/v2/data/insight"

# Diferenca maxima entre o `quando` do ledger e o `post_time` do Studio.
# O medido foi 1 a 7 s; dez minutos de folga cobrem relogio torto e a
# confirmacao extra do TikTok sem chegar perto do intervalo da grade (1 h).
JANELA_DE_CASAMENTO_S = 600

# O ORCAMENTO DA ANALISE. Ela custa uma pagina por video — 8,8 s medidos em
# 13/09/2026 — e roda DENTRO da tarefa de publicacao das 06:07, com o perfil
# do TikTok travado. Sem teto, 14 dias de grade (8 videos por canal por dia)
# viravam 224 paginas e mais de meia hora, encostando na tarefa das 07:07 que
# precisa do mesmo perfil. Com o teto, o pior caso sao 2 canais x 40 videos
# x 8,8 s: uns 12 minutos.
#
# E so reanalisa quem ainda esta ganhando view: depois de uma semana o
# numero de um short praticamente para.
DIAS_DE_ANALISE = 7
MAXIMO_DE_ANALISES = 40
ESPERA_LISTA_S = 45.0
ESPERA_ANALISE_S = 25.0
ABAS_DA_ANALISE = ("Espectadores", "Engajamento")

# A LISTA INTEIRA, e nao a primeira pagina. Medido em 28/09/2026: o Studio
# pede `item_list` por POST com `{"cursor", "size"}` — 50 na primeira pagina,
# 10 nas seguintes — e responde `cursor` (onde a proxima comeca) e
# `has_more`. A lista mora num DIV com rolagem propria; `mouse.wheel` sem o
# ponteiro em cima dele nao rola nada. De 17 a 28/09 toda noite parou em 50
# ou 60 posts: 60 de 119 envios casados em builds e 50 de 165 em historias.
# Rolando o DIV (e a tecla End), a mesma pagina chegou a 130 com `has_more`
# ainda verdadeiro.
TEMPO_DA_LISTA_S = 180.0
PAUSA_DA_ROLAGEM_MS = 2000
TENTATIVAS_SEM_CRESCER = 6
# Leva todo elemento com rolagem propria ao fim, e a janela junto. Sem nome
# de classe: as do Studio sao geradas (`css-snthx`) e mudam a cada versao.
ROLAR_TUDO_JS = """() => {
  for (const el of document.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') &&
        el.scrollHeight > el.clientHeight + 50) {
      el.scrollTop = el.scrollHeight;
    }
  }
  window.scrollTo(0, document.body.scrollHeight);
}"""

# O que so a pagina de analise traz. Quem nao for analisado nesta rodada
# CARREGA estes campos do arquivo anterior — regravar sem eles apagava a curva
# ja coletada, e a curva e justamente o numero que nao se recupera depois.
CAMPOS_DA_ANALISE = ("media_segundos", "media_percentual",
                     "taxa_de_conclusao", "espectadores_unicos",
                     "seguidores_ganhos", "fracao_de_novos", "curva",
                     "origem_do_trafego", "analisado_em")


# ----------------------------------------------------------- funcoes puras
def _numero(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _valor(campo):
    """O numero de um campo do insight, ou `None` se o TikTok nao tem.

    Os campos vem em dois formatos — `{"status": 0, "value": 8}` e
    `{"value": {"status": 0, "value": 8}}` — e `status` diferente de zero
    quer dizer "sem dado". Sem dado nao e zero.
    """
    for _ in range(3):
        if not isinstance(campo, dict):
            break
        if campo.get("status") not in (None, 0):
            return None
        if "value" not in campo:
            return None
        campo = campo["value"]
    return campo if isinstance(campo, (int, float)) else None


def item_do_studio(bruto: dict) -> dict:
    """Um item de `item_list`, com os nomes que o resto do projeto usa."""
    return {
        "tiktok_id": str(bruto.get("item_id") or ""),
        "post_time": _numero(bruto.get("post_time")),
        "duracao_ms": _numero(bruto.get("duration")),
        "legenda": str(bruto.get("desc") or ""),
        "views": _numero(bruto.get("play_count")),
        "likes": _numero(bruto.get("like_count")),
        "comentarios": _numero(bruto.get("comment_count")),
        "compartilhamentos": _numero(bruto.get("share_count")),
        "salvos": _numero(bruto.get("favorite_count")),
    }


def _instante(publicacao: dict) -> float | None:
    try:
        return datetime.fromisoformat(str(publicacao.get("quando"))).timestamp()
    except (TypeError, ValueError):
        return None


def _parte_confere(publicacao: dict, item: dict) -> bool:
    """A legenda nao contradiz a parte que o ledger registrou.

    Legenda sem marca de parte (build, duelo) nao contradiz nada.
    """
    parte, partes = publicacao.get("parte"), publicacao.get("partes")
    if not parte or not partes:
        return True
    legenda = item.get("legenda") or ""
    if f"Parte {parte} de {partes}" in legenda:
        return True
    return "Parte " not in legenda


def casar(publicacoes: list, itens: list, *,
          janela: float = JANELA_DE_CASAMENTO_S) -> list:
    """`[(linha do ledger, item do Studio)]`, cada item usado uma vez so."""
    pares, usados = [], set()
    ordem = sorted((p for p in publicacoes if _instante(p) is not None),
                   key=_instante)
    for publicacao in ordem:
        t = _instante(publicacao)
        candidatos = sorted(
            (i for i in itens
             if i.get("tiktok_id") not in usados and i.get("post_time")
             and abs(i["post_time"] - t) <= janela),
            key=lambda i: abs(i["post_time"] - t))
        for item in candidatos:
            if _parte_confere(publicacao, item):
                usados.add(item["tiktok_id"])
                pares.append((publicacao, item))
                break
    return pares


def _quando_foi_analisado(anterior: dict | None) -> str:
    """A data da ultima analise, inclusive dos arquivos de antes do campo.

    Os primeiros arquivos (13/09/2026) nao tinham `analisado_em`; neles a
    analise e a propria atualizacao, se ela trouxe o tempo medio.
    """
    anterior = anterior or {}
    if anterior.get("analisado_em"):
        return str(anterior["analisado_em"])
    if "media_segundos" in anterior:
        return str(anterior.get("atualizado") or "")
    return ""


def escolher_para_analise(pares: list, anteriores: dict, *,
                          agora: float | None = None,
                          dias: int = DIAS_DE_ANALISE,
                          maximo: int = MAXIMO_DE_ANALISES) -> set:
    """Os `tiktok_id` que ganham pagina de analise nesta rodada.

    Fora: video mais velho que `dias`, e video ja analisado hoje. Dentro do
    teto, primeiro quem NUNCA foi analisado (e o numero que ainda nao
    existe), depois o mais novo (e o que mais muda).
    """
    agora = time.time() if agora is None else agora
    hoje = datetime.fromtimestamp(agora).strftime("%Y-%m-%d")
    corte = agora - dias * 86400
    fila = []
    for _publicacao, item in pares:
        postado = item.get("post_time") or 0
        if postado < corte:
            continue
        ultima = _quando_foi_analisado(anteriores.get(item.get("tiktok_id")))
        if ultima.startswith(hoje):
            continue
        fila.append((0 if not ultima else 1, -postado, item["tiktok_id"]))
    return {tid for _nunca, _novo, tid in sorted(fila)[:max(0, maximo)]}


def analise_anterior(anterior: dict | None) -> dict:
    """Os campos de analise do arquivo de antes, para nao se perderem."""
    anterior = anterior or {}
    saida = {k: anterior[k] for k in CAMPOS_DA_ANALISE if k in anterior}
    if saida and "analisado_em" not in saida:
        quando = _quando_foi_analisado(anterior)
        if quando:
            saida["analisado_em"] = quando
    return saida


def analise_do_insight(respostas: list, duracao_ms: int | None) -> dict:
    """Junta as respostas de `data/insight` de UM video num dicionario so."""
    campos = {}
    for corpo in respostas or []:
        for chave, valor in (corpo or {}).items():
            if valor is not None:
                campos.setdefault(chave, valor)
    saida = {}
    media = _valor(campos.get("video_per_duration_realtime"))
    if media is not None:
        saida["media_segundos"] = round(float(media), 2)
        if duracao_ms:
            saida["media_percentual"] = round(
                100.0 * float(media) / (duracao_ms / 1000.0), 1)
    conclusao = _valor(campos.get("video_finish_rate_realtime"))
    if conclusao is not None:
        saida["taxa_de_conclusao"] = round(float(conclusao), 4)
    unicos = _valor(campos.get("video_uv"))
    if unicos is not None:
        saida["espectadores_unicos"] = int(unicos)
    seguidores = _valor(campos.get("video_new_followers"))
    if seguidores is not None:
        saida["seguidores_ganhos"] = int(seguidores)
    novos = _valor(campos.get("video_viewer_new_viewer_percent"))
    if novos is not None:
        saida["fracao_de_novos"] = round(float(novos), 4)

    retencao = campos.get("video_retention_rate_realtime") or {}
    pontos = ((retencao.get("value") or {}).get("list")
              if isinstance(retencao, dict) else None) or []
    if pontos and duracao_ms:
        curva = []
        for ponto in pontos:
            ms, fracao = _numero(ponto.get("timestamp")), ponto.get("value")
            if ms is None or not isinstance(fracao, (int, float)):
                continue
            curva.append((round(min(1.0, ms / duracao_ms), 4),
                          round(float(fracao), 4)))
        if curva:
            saida["curva"] = curva

    origem = campos.get("video_traffic_source_percent_realtime") or {}
    lista = (origem.get("value") or {}).get("value") \
        if isinstance(origem, dict) and isinstance(origem.get("value"), dict) \
        else None
    if isinstance(lista, list):
        saida["origem_do_trafego"] = {
            str(o.get("key")): round(float(o.get("value") or 0), 4)
            for o in lista if isinstance(o, dict) and o.get("key")}
    return saida


def montar(publicacao: dict, item: dict, analise: dict | None,
           canal: str, agora: datetime | None = None) -> dict:
    from . import metricas

    agora = agora or datetime.now()
    dado = {**publicacao, **item, **(analise or {}),
            "plataforma": "tiktok", "canal": canal,
            "atualizado": agora.isoformat(timespec="seconds")}
    if item.get("post_time"):
        dado["publicado_em"] = datetime.fromtimestamp(
            item["post_time"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if item.get("duracao_ms"):
        dado["duracao"] = round(item["duracao_ms"] / 1000.0)
    dado["dias_no_ar"] = metricas.idade_em_dias(dado)
    dado["views_por_dia"] = metricas.views_por_dia(dado)
    return dado


def pasta_do_canal(canal: str = "builds") -> Path:
    from . import metricas
    return metricas.pasta_do_canal(canal).with_name("_metricas_tiktok")


def carregar_salvas(canal: str = "builds") -> list:
    saida = []
    pasta = pasta_do_canal(canal)
    if not pasta.is_dir():
        return saida
    for arquivo in sorted(pasta.glob("*.json")):
        try:
            with open(arquivo, encoding="utf-8-sig") as fh:
                saida.append(json.load(fh))
        except (OSError, ValueError):
            continue
    return saida


# ------------------------------------------------------------------- a lista
class Lista:
    """Os posts que o Studio ja mandou, e ate onde a lista foi.

    `fronteira` e o maior `cursor` devolvido e `tem_mais` e o `has_more`
    DAQUELA resposta. As outras chegam fora de ordem: a cada rolagem o Studio
    tambem repede a primeira pagina (cursor 0, que devolve 50 e
    `has_more=true`), e ela nao pode apagar a noticia de que a lista acabou.
    """

    def __init__(self):
        self.itens: dict = {}
        self.fronteira = -1
        self.tem_mais = None

    def receber(self, corpo) -> None:
        if not isinstance(corpo, dict):
            return
        for bruto in corpo.get("item_list") or []:
            if isinstance(bruto, dict):
                item = item_do_studio(bruto)
                if item["tiktok_id"]:
                    self.itens[item["tiktok_id"]] = item
        cursor = _numero(corpo.get("cursor"))
        if cursor is not None and cursor >= self.fronteira:
            self.fronteira = cursor
            self.tem_mais = bool(corpo.get("has_more"))

    def mais_velho(self) -> int | None:
        tempos = [i["post_time"] for i in self.itens.values()
                  if i.get("post_time")]
        return min(tempos) if tempos else None


def ler_a_lista(page, lista: Lista, *, basta_antes_de: float | None = None,
                limite_s: float = TEMPO_DA_LISTA_S,
                pausa_ms: int = PAUSA_DA_ROLAGEM_MS,
                sem_crescer: int = TENTATIVAS_SEM_CRESCER) -> str:
    """Rola a lista ate o fim e diz POR QUE parou.

    `completa`   o Studio respondeu `has_more=false`: nao ha mais post;
    `suficiente` o post mais velho ja e anterior ao envio mais velho do
                 ledger (`basta_antes_de`): o resto nao casaria com nada;
    `parada`     varias rolagens seguidas sem post novo, com `has_more`
                 ainda verdadeiro — a lista ficou INCOMPLETA, e isso aparece;
    `tempo`      o teto de tempo acabou antes (tambem incompleta).

    Alterna o DIV rolado por JS com a tecla End, os dois que funcionaram na
    medicao; `mouse.wheel` sozinho foi o que parou em 50.
    """
    fim = time.time() + float(limite_s)
    parado, vez = 0, 0
    while True:
        if lista.tem_mais is False:
            return "completa"
        velho = lista.mais_velho()
        if basta_antes_de is not None and velho is not None \
                and velho <= basta_antes_de:
            return "suficiente"
        if parado >= sem_crescer:
            return "parada"
        if time.time() >= fim:
            return "tempo"
        antes = len(lista.itens)
        if vez % 2 == 0:
            page.evaluate(ROLAR_TUDO_JS)
        else:
            page.keyboard.press("End")
        vez += 1
        page.wait_for_timeout(pausa_ms)
        parado = parado + 1 if len(lista.itens) == antes else 0


# --------------------------------------------------------------- navegador
def coletar(canal: str = "builds", *, log=print,
            dias_de_analise: int = DIAS_DE_ANALISE,
            maximo_de_analises: int = MAXIMO_DE_ANALISES,
            analisar: bool = True, resumo: dict | None = None) -> list:
    """Abre o Studio do canal, casa os posts com o ledger e grava.

    Abre navegador: nunca chamar de teste sem dublar.

    `resumo`, se vier, recebe quantos posts a lista trouxe, por que ela
    parou, e quantos envios do ledger casaram — o que a marca do dia grava.

    O perfil e aberto por `contexto_persistente`, que PEGA A TRAVA da pasta:
    se a publicacao estiver com o Chrome do TikTok, a coleta espera e depois
    desiste (`PerfilOcupado`) em vez de abrir uma segunda janela na pasta.
    """
    from ..identity.browser import contexto_persistente, pagina
    from . import metricas
    from .tiktok import TikTokFalhou, perfil_da_conta

    resumo = resumo if resumo is not None else {}
    publicacoes = [p for p in metricas.publicados(canal)
                   if p.get("plataforma") == "tiktok"]
    resumo["envios"] = len(publicacoes)
    if not publicacoes:
        log(f"[tiktok-metricas] {canal}: nenhum envio de TikTok no ledger.")
        return []

    lista, insights = Lista(), []
    itens = lista.itens

    def ouvir(resp):
        url = resp.url
        if LISTA not in url and INSIGHT not in url:
            return
        try:
            corpo = resp.json()
        except Exception:                                      # noqa: BLE001
            return
        if LISTA in url:
            lista.receber(corpo)
        else:
            insights.append(corpo)

    # So interessa o post que pode casar com o ledger: o mais velho dele,
    # com a folga do casamento.
    tempos = [t for t in (_instante(p) for p in publicacoes) if t is not None]
    basta_antes_de = (min(tempos) - JANELA_DE_CASAMENTO_S) if tempos else None

    salvos = []
    pasta = pasta_do_canal(canal)
    anteriores = {d.get("tiktok_id"): d for d in carregar_salvas(canal)}
    with contexto_persistente(headless=False,
                              profile=perfil_da_conta(canal)) as ctx:
        page = pagina(ctx)
        page.on("response", ouvir)
        page.goto(URL_CONTEUDO, wait_until="domcontentloaded",
                  timeout=90_000)
        limite = time.time() + ESPERA_LISTA_S
        while not itens and time.time() < limite:
            if "login" in page.url:
                raise TikTokFalhou(
                    f"o TikTok do canal {canal} pediu login; as metricas "
                    "ficam para depois do login pelo painel.")
            page.wait_for_timeout(1000)
        if not itens:
            # LISTA VAZIA NAO E "ZERO POSTS". Com envio no ledger, o Studio
            # tem post; nada chegar e a pagina que nao carregou.
            raise TikTokFalhou(
                f"a lista do Studio do canal {canal} nao carregou nenhum post "
                f"em {ESPERA_LISTA_S:.0f}s ({len(publicacoes)} envio(s) no "
                "ledger).")
        motivo = ler_a_lista(page, lista, basta_antes_de=basta_antes_de)
        resumo.update({"posts": len(itens), "lista": motivo})
        incompleta = motivo in ("parada", "tempo")
        log(f"[tiktok-metricas] {canal}: {len(itens)} post(s) no Studio "
            f"(lista {motivo}"
            + (", INCOMPLETA: o Studio ainda dizia que havia mais"
               if incompleta else "") + ").")

        pares = casar(publicacoes, list(itens.values()))
        resumo["casados"] = len(pares)
        if not pares:
            # ZERO CASADOS NAO E COLETA. Posts no Studio, envios no ledger e
            # nenhum par: o casamento quebrou (conta trocada, relogio), e
            # gravar "0 videos" como noite feita seria o medidor verde.
            raise TikTokFalhou(
                f"nenhum dos {len(publicacoes)} envio(s) do ledger casou com "
                f"os {len(itens)} post(s) do Studio do canal {canal}.")
        escolhidos = (escolher_para_analise(pares, anteriores,
                                            dias=dias_de_analise,
                                            maximo=maximo_de_analises)
                      if analisar else set())
        log(f"[tiktok-metricas] {canal}: {len(pares)} de {len(publicacoes)} "
            f"envio(s) do ledger casados; {len(escolhidos)} analisado(s) "
            "nesta rodada.")
        pasta.mkdir(parents=True, exist_ok=True)
        for publicacao, item in pares:
            anterior = anteriores.get(item["tiktok_id"])
            analise = analise_anterior(anterior)
            if item["tiktok_id"] in escolhidos:
                insights.clear()
                page.goto(URL_ANALISE.format(item_id=item["tiktok_id"]),
                          wait_until="domcontentloaded", timeout=90_000)
                limite = time.time() + ESPERA_ANALISE_S
                while time.time() < limite:
                    page.wait_for_timeout(1000)
                    if any("video_per_duration_realtime" in c
                           for c in insights):
                        break
                for aba in ABAS_DA_ANALISE:
                    try:
                        page.get_by_text(aba, exact=True).first.click(
                            timeout=3000)
                        page.wait_for_timeout(3000)
                    except Exception:                          # noqa: BLE001
                        pass
                nova = analise_do_insight(list(insights),
                                          item.get("duracao_ms"))
                if nova:
                    nova["analisado_em"] = datetime.now().isoformat(
                        timespec="seconds")
                    analise = nova
            dado = montar(publicacao, item, analise, canal)
            with open(pasta / f"{item['tiktok_id']}.json", "w",
                      encoding="utf-8") as fh:
                json.dump(dado, fh, ensure_ascii=False, indent=2)
            salvos.append(dado)
    log(f"[tiktok-metricas] {canal}: {len(salvos)} video(s) gravados em "
        f"{pasta}")
    return salvos


__all__ = ["Lista", "analise_anterior", "analise_do_insight",
           "carregar_salvas", "casar", "coletar", "escolher_para_analise",
           "item_do_studio", "ler_a_lista", "montar", "pasta_do_canal"]
