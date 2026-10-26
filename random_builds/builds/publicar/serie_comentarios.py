# -*- coding: utf-8 -*-
"""Os COMENTARIOS da serie "Como eu criei um Blue Lock" — SO LEITURA (26/10/2026).

Para o Adrian responder (ou mandar responder) sem abrir as duas plataformas.
Nada aqui publica resposta nem comentario: nenhuma chamada de escrita, nenhum
clique em "responder".

De onde vem cada um (o que foi MEDIDO em 26/10):

- YouTube, o NUMERO: `commentCount` da Data API (escopo readonly basta). E o
  que avisa que ha comentario novo, mesmo quando o texto nao vem.
- YouTube, o TEXTO: `commentThreads.list`. O token da casa para o canal
  Egoistsoccer tem `youtube.readonly` e a API responde 403
  `ACCESS_TOKEN_SCOPE_INSUFFICIENT` (a lista pede `youtube.force-ssl`, que
  tambem permitiria ESCREVER — nao pedimos). Entao o texto e lido da pagina
  publica do video, num Chrome SEM login (so quando `commentCount` subiu).
  Esse caminho foi provado num video publico com comentarios; no episodio 1 o
  `commentCount` era 0, entao o parser nao viu comentario NOSSO ainda.
- TikTok: o Studio (`/tiktokstudio/comment`, resposta `commentsV2`), lido na
  mesma sessao da coleta do TikTok. Em 26/10 a resposta era
  `{"hasMore":false,"comments":[],"cursor":""}` (sem comentario): o formato de
  um comentario NAO foi medido; o corpo cru fica guardado junto.

As tres perguntas da lei:

- ZERO: "nenhum comentario novo" so sai com a leitura FEITA (e diz quantos
  videos foram lidos e quando); leitura que falhou diz "NAO CONSEGUI LER" e o
  motivo, e nunca vira "sem comentario".
- DENOMINADOR: comentario novo = id que o arquivo ainda nao tinha; resposta
  (reply) nao entra como comentario de topo.
- EXCECAO: o erro volta como texto para o relatorio e vai ao diario (`metricas`,
  uma linha por dia e por tipo).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from . import metricas, serie_metricas

NOME_DO_ARQUIVO = "_comentarios.json"
API_COMENTARIOS = "https://www.googleapis.com/youtube/v3/commentThreads"
URL_COMENTARIO = "https://www.youtube.com/watch?v={video}&lc={comentario}"
MAXIMO_NO_RESUMO = 12
TEXTO_MAXIMO = 280

LER_JS = """() => [...document.querySelectorAll('ytd-comment-thread-renderer')].map(t => {
  const q = (s) => { const e = t.querySelector(s); return e ? e.innerText.trim() : null; };
  const a = t.querySelector('#published-time-text a');
  return {autor: q('#author-text'), texto: q('#content-text'),
          quando: q('#published-time-text'), link: a ? a.getAttribute('href') : null,
          curtidas: q('#vote-count-middle')};
})"""


RELER_DEPOIS_DE_H = 20.0


def _horas_desde(texto, agora: datetime) -> float:
    try:
        return (agora - datetime.fromisoformat(str(texto)[:19])).total_seconds() / 3600.0
    except ValueError:
        return float("inf")


def arquivo() -> Path:
    return serie_metricas.pasta_da_serie() / NOME_DO_ARQUIVO


def carregar() -> dict:
    """O arquivo, ou o esqueleto vazio. Arquivo ilegivel NAO vira vazio em
    silencio: levanta, para o relatorio dizer que nao conseguiu ler."""
    try:
        with open(arquivo(), encoding="utf-8-sig") as fh:
            dado = json.load(fh)
    except FileNotFoundError:
        return {"comentarios": {}, "leituras": {}}
    if not isinstance(dado, dict):
        raise ValueError("_comentarios.json nao e um objeto")
    dado.setdefault("comentarios", {})
    dado.setdefault("leituras", {})
    return dado


def gravar(dado: dict) -> None:
    caminho = arquivo()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    provisorio = caminho.with_name(caminho.name + ".tmp")
    with open(provisorio, "w", encoding="utf-8") as fh:
        json.dump(dado, fh, ensure_ascii=False, indent=1)
    os.replace(provisorio, caminho)


def _agora_txt(agora: datetime | None = None) -> str:
    return (agora or datetime.now()).isoformat(timespec="seconds")


# ----------------------------------------------------------- guardar (puro)
def guardar(dado: dict, plataforma: str, video_id: str, comentarios: list,
            agora: datetime | None = None) -> int:
    """Junta `comentarios` (lista de dicts com `id`, `autor`, `texto`,
    `publicado_em`, `curtidas`, `respostas`) ao arquivo. Devolve quantos eram
    NOVOS (id que o arquivo nao tinha). Comentario sem id ou sem texto e
    ignorado e nao conta."""
    visto = _agora_txt(agora)
    novos = 0
    for c in comentarios or ():
        if not isinstance(c, dict) or not c.get("id") or not str(c.get("texto") or "").strip():
            continue
        chave = f"{plataforma}:{c['id']}"
        if chave in dado["comentarios"]:
            atual = dado["comentarios"][chave]
            for campo in ("curtidas", "respostas"):
                if c.get(campo) is not None:
                    atual[campo] = c[campo]
            continue
        dado["comentarios"][chave] = {
            "plataforma": plataforma, "video_id": str(video_id),
            "id": str(c["id"]), "autor": c.get("autor"),
            "texto": str(c["texto"]).strip(), "publicado_em": c.get("publicado_em"),
            "curtidas": c.get("curtidas"), "respostas": c.get("respostas"),
            "link": c.get("link"), "visto_em": visto, "avisado_em": None}
        novos += 1
    return novos


def registrar_leitura(dado: dict, plataforma: str, video_id: str, *, estado: str,
                      lidos: int = 0, total=None, via: str = "", erro: str = "",
                      agora: datetime | None = None) -> None:
    """Uma leitura por video, com o que aconteceu. `estado`: ok | erro."""
    dado["leituras"][f"{plataforma}:{video_id}"] = {
        "quando": _agora_txt(agora), "estado": estado, "lidos": lidos,
        "total": total, "via": via, **({"erro": erro[:300]} if erro else {})}


# --------------------------------------------------------------- YouTube
def _normalizar_thread(item: dict) -> dict | None:
    """Um item de `commentThreads.list` no formato daqui."""
    topo = ((item.get("snippet") or {}).get("topLevelComment") or {})
    s = topo.get("snippet") or {}
    if not item.get("id"):
        return None
    return {"id": item["id"], "autor": s.get("authorDisplayName"),
            "texto": s.get("textOriginal") or s.get("textDisplay"),
            "publicado_em": s.get("publishedAt"), "curtidas": s.get("likeCount"),
            "respostas": (item.get("snippet") or {}).get("totalReplyCount")}


def _via_api(video_id: str, token: str) -> tuple:
    """`(lista, motivo)`: `lista` None = a API nao deu (motivo diz por que)."""
    resposta = metricas._get(
        "data", API_COMENTARIOS, timeout=30,
        params={"part": "snippet", "videoId": video_id, "order": "time",
                "maxResults": 100, "textFormat": "plainText"},
        headers={"Authorization": f"Bearer {token}"})
    if resposta.status_code in (401, 403):
        return None, f"API {resposta.status_code}: " + metricas.motivo_da_recusa(
            resposta, api="data")[:140]
    if not resposta.ok:
        return None, f"API {resposta.status_code}: {resposta.text[:120]}"
    itens = [_normalizar_thread(i) for i in (resposta.json() or {}).get("items") or []]
    return [i for i in itens if i], ""


def _via_pagina(video_id: str, perfil: Path | None = None) -> list:
    """Le a pagina PUBLICA do video num Chrome sem login. Levanta se o Chrome
    ou a pagina falharem. Ordem: a que a pagina mostra (os mais votados); com
    poucos comentarios e a lista toda."""
    import re

    from ..identity.browser import contexto_persistente, pagina
    perfil = perfil or (serie_metricas.pasta_da_serie() / ".perfil_sem_login")
    perfil.mkdir(parents=True, exist_ok=True)
    with contexto_persistente(headless=False, profile=perfil) as ctx:
        page = pagina(ctx)
        page.goto(f"https://www.youtube.com/watch?v={video_id}",
                  wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(5000)
        for _ in range(4):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(2500)
        brutos = page.evaluate(LER_JS)
    saida = []
    for b in brutos or []:
        achado = re.search(r"[?&]lc=([A-Za-z0-9_.-]+)", str(b.get("link") or ""))
        if not achado or not b.get("texto"):
            continue
        saida.append({"id": achado.group(1), "autor": b.get("autor"),
                      "texto": b.get("texto"), "publicado_em": b.get("quando"),
                      "curtidas": b.get("curtidas"), "link": b.get("link")})
    return saida


def ler_youtube(token: str | None = None, *, agora: datetime | None = None,
                log=print, pagina_do_video=_via_pagina, api=_via_api) -> dict:
    """Le os comentarios dos episodios no YouTube. Devolve
    `{lidos: [video_id], novos: n, falhas: [texto]}`; nunca levanta."""
    agora = agora or datetime.now()
    saida = {"lidos": [], "novos": 0, "falhas": []}
    try:
        ids = [str(l["youtube_id"]) for l in metricas.publicados(serie_metricas.CANAL)
               if l.get("youtube_id") and metricas.publicado(l)
               and str(l.get("plataforma") or "youtube") == "youtube"]
        ids = list(dict.fromkeys(ids))
        if not ids:
            return saida
        if token is None:
            token = metricas._token(serie_metricas.CANAL)[0]
        contagens = metricas.estatisticas(ids, token)
        dado = carregar()
    except Exception as exc:                                   # noqa: BLE001
        saida["falhas"].append(f"{type(exc).__name__}: {str(exc)[:200]}")
        return saida
    for vid in ids:
        total = (contagens.get(vid) or {}).get("comentarios")
        if total is None:
            registrar_leitura(dado, "youtube", vid, estado="erro", agora=agora,
                              erro="a Data API nao devolveu o video")
            saida["falhas"].append(f"{vid}: a Data API nao devolveu o video")
            continue
        ja = sum(1 for c in dado["comentarios"].values()
                 if c["plataforma"] == "youtube" and c["video_id"] == vid)
        anterior = dado["leituras"].get(f"youtube:{vid}") or {}
        if total == 0 or total <= ja:
            # commentCount nao subiu: nada novo (e o numero e MEDIDO).
            registrar_leitura(dado, "youtube", vid, estado="ok", lidos=0,
                              total=total, via="contagem", agora=agora)
            saida["lidos"].append(vid)
            continue
        if (anterior.get("estado") == "ok" and anterior.get("total") == total
                and anterior.get("via") in ("api", "pagina")
                and _horas_desde(anterior.get("quando"), agora) < RELER_DEPOIS_DE_H):
            # O contador diz o mesmo da ultima leitura (que ja abriu a pagina
            # e deixou o aviso "li X de Y"): nao abre o Chrome de novo.
            saida["lidos"].append(vid)
            continue
        via, lista, motivo = "api", None, ""
        try:
            lista, motivo = api(vid, token)
        except Exception as exc:                               # noqa: BLE001
            motivo = f"{type(exc).__name__}: {str(exc)[:120]}"
        if lista is None:
            via = "pagina"
            try:
                lista = pagina_do_video(vid)
            except Exception as exc:                           # noqa: BLE001
                erro = (f"{motivo}; e a pagina publica tambem falhou: "
                        f"{type(exc).__name__}: {str(exc)[:120]}")
                registrar_leitura(dado, "youtube", vid, estado="erro",
                                  total=total, erro=erro, agora=agora)
                saida["falhas"].append(f"{vid}: {erro}")
                continue
        novos = guardar(dado, "youtube", vid, lista, agora)
        saida["novos"] += novos
        registrar_leitura(dado, "youtube", vid, estado="ok", lidos=len(lista),
                          total=total, via=via, agora=agora)
        saida["lidos"].append(vid)
        if len(lista) < total:
            log(f"[serie-comentarios] {vid}: li {len(lista)} de {total} "
                f"comentarios (via {via}).")
    try:
        gravar(dado)
    except OSError as exc:
        saida["falhas"].append(f"nao consegui gravar _comentarios.json: {exc}")
    return saida


# ---------------------------------------------------------------- TikTok
def normalizar_tiktok(corpo: dict) -> list:
    """Os comentarios de uma resposta `commentsV2`, com TOLERANCIA nos nomes:
    o formato de um comentario nao foi medido (a conta nao tinha nenhum em
    26/10), entao procura as chaves provaveis e, sem `id` e `texto`, descarta
    — o corpo cru continua em `_comentarios_tiktok_cru.jsonl`."""
    saida = []
    for c in (corpo or {}).get("comments") or []:
        if not isinstance(c, dict):
            continue
        usuario = c.get("user") or c.get("author") or {}
        saida.append({
            "id": c.get("cid") or c.get("comment_id") or c.get("id"),
            "texto": c.get("text") or c.get("comment") or c.get("content"),
            "autor": (usuario.get("nickname") or usuario.get("unique_id")
                      if isinstance(usuario, dict) else None) or c.get("nickname"),
            "publicado_em": c.get("create_time") or c.get("createTime"),
            "curtidas": c.get("digg_count") or c.get("like_count"),
            "respostas": c.get("reply_comment_total") or c.get("reply_count"),
            "video": str(c.get("aweme_id") or c.get("item_id") or ""),
        })
    return saida


def guardar_do_tiktok(respostas: list, *, agora: datetime | None = None,
                      erro: str = "") -> dict:
    """Guarda o que a pagina de comentarios do Studio trouxe. `respostas` e a
    lista de corpos `commentsV2` (vazia = a pagina nao respondeu: ERRO, nao
    zero comentarios). Devolve `{novos, falhas}`; nunca levanta."""
    agora = agora or datetime.now()
    saida = {"novos": 0, "falhas": []}
    try:
        dado = carregar()
        if erro or not respostas:
            motivo = erro or "o Studio nao respondeu a lista de comentarios"
            registrar_leitura(dado, "tiktok", "conta", estado="erro", erro=motivo,
                              agora=agora)
            saida["falhas"].append(motivo)
        else:
            total = 0
            for corpo in respostas:
                lista = normalizar_tiktok(corpo)
                total += len(lista)
                por_video: dict = {}
                for c in lista:
                    por_video.setdefault(c.get("video") or "", []).append(c)
                for video, itens in por_video.items():
                    saida["novos"] += guardar(dado, "tiktok", video, itens, agora)
            registrar_leitura(dado, "tiktok", "conta", estado="ok", lidos=total,
                              via="studio", agora=agora)
        gravar(dado)
    except Exception as exc:                                   # noqa: BLE001
        saida["falhas"].append(f"{type(exc).__name__}: {str(exc)[:200]}")
    return saida


# --------------------------------------------------------------- resumo
def _curto(texto: str) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= TEXTO_MAXIMO else texto[:TEXTO_MAXIMO - 1] + "…"


def resumo(agora: datetime | None = None, *, marcar: bool = True) -> str:
    """O texto do Telegram: os comentarios ainda nao avisados (e os avisados
    HOJE, para a mensagem repetida no mesmo dia nao sumir com eles).

    `marcar=True` grava `avisado_em` nos novos. So leitura de plataforma: nada
    e publicado.
    """
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    try:
        dado = carregar()
    except Exception as exc:                                   # noqa: BLE001
        return ("💬 *Comentários da série*\n"
                f"⚠ NÃO consegui ler o arquivo dos comentários: "
                f"{type(exc).__name__}: {exc}")
    pendentes, de_hoje = [], []
    for c in dado["comentarios"].values():
        if not c.get("avisado_em"):
            pendentes.append(c)
        elif str(c["avisado_em"])[:10] == hoje:
            de_hoje.append(c)
    mostrar = sorted(pendentes + de_hoje, key=lambda c: str(c.get("visto_em")))
    linhas = ["💬 *Comentários da série*"]
    falhas = [f"{k}: {v.get('erro')}" for k, v in dado["leituras"].items()
              if v.get("estado") == "erro"]
    leituras = dado["leituras"]
    if not leituras:
        linhas.append("⚠ nenhuma leitura de comentários feita ainda "
                      "(isto NÃO quer dizer que não há comentários).")
    else:
        mais_nova = max(str(v.get("quando")) for v in leituras.values())
        ok = sum(1 for v in leituras.values() if v.get("estado") == "ok")
        linhas.append(f"lidos {ok} de {len(leituras)} (última leitura "
                      f"{mais_nova[8:10]}/{mais_nova[5:7]} {mais_nova[11:16]}); "
                      "só leitura — nada foi respondido.")
    for f in falhas:
        linhas.append(f"⚠ NÃO consegui ler {f[:200]}")
    # O contador do YouTube conta TUDO (respostas, e comentario retido para
    # revisao ou do proprio canal que a pagina publica nao mostra). Ler menos
    # que o contador nao e leitura completa: e dito, nunca "tudo lido".
    parcial = False
    for k, v in leituras.items():
        if (v.get("estado") == "ok" and v.get("via") in ("api", "pagina")
                and isinstance(v.get("total"), int) and v["lidos"] < v["total"]):
            parcial = True
            linhas.append(f"⚠ {k.split(':', 1)[1]}: o contador do YouTube diz "
                          f"{v['total']} comentário(s) e eu li {v['lidos']} "
                          "(retido p/ revisão, resposta ou do próprio canal).")
    if not mostrar:
        if leituras and not falhas:
            linhas.append("nenhum comentário novo que eu consiga ler." if parcial
                          else "nenhum comentário novo.")
        return "\n".join(linhas)
    linhas.append(f"{len(mostrar)} comentário(s):")
    for c in mostrar[:MAXIMO_NO_RESUMO]:
        onde = "YouTube" if c["plataforma"] == "youtube" else "TikTok"
        link = (URL_COMENTARIO.format(video=c["video_id"], comentario=c["id"])
                if c["plataforma"] == "youtube" else "")
        linhas.append(f"• {onde} — {c.get('autor') or '?'}: “{_curto(c['texto'])}”"
                      + (f" ({c['curtidas']} curt.)" if c.get("curtidas") else "")
                      + (f"\n  {link}" if link else ""))
    if len(mostrar) > MAXIMO_NO_RESUMO:
        linhas.append(f"… e mais {len(mostrar) - MAXIMO_NO_RESUMO} (estão em "
                      "`_serie_bluelock/_comentarios.json`).")
    if marcar and pendentes:
        agora_txt = _agora_txt(agora)
        for c in pendentes:
            c["avisado_em"] = agora_txt
        try:
            gravar(dado)
        except OSError as exc:
            linhas.append(f"⚠ não consegui marcar como avisados: {exc}")
    return "\n".join(linhas)
