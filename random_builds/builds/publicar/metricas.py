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
escopo `yt-analytics.readonly` (uma re-autorizacao:
`neural-fights youtube-oauth --com-upload --com-analytics`); sem ele, o
relatorio mostra views/likes e avisa o que falta, em vez de falhar.

O gancho A/B fecha aqui: dois uploads da mesma geracao com `variante`
diferente aparecem lado a lado com a retencao media de cada um.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
REGISTRO = OUTPUTS / "_publicar" / "publicados.jsonl"
PASTA = OUTPUTS / "_metricas"

API_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
API_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
ESCOPO_ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"

SPARK = "▁▂▃▄▅▆▇█"


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
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha


def publicados() -> list[dict]:
    if not REGISTRO.is_file():
        return []
    saida = []
    with open(REGISTRO, encoding="utf-8") as fh:
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
def _token():
    from .youtube import PublicacaoFalhou, carregar_credenciais, token_de_acesso
    credenciais = carregar_credenciais()
    if credenciais is None:
        raise PublicacaoFalhou("sem credenciais do YouTube (rode o OAuth no painel).")
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
        return {"erro": "escopo yt-analytics.readonly ausente — rode "
                        "`neural-fights youtube-oauth --com-upload --com-analytics`"}
    if not resumo.ok:
        return {"erro": f"Analytics API {resumo.status_code}: {resumo.text[:160]}"}
    linhas = resumo.json().get("rows") or [[0, 0, 0]]
    saida = {"views_analytics": linhas[0][0], "media_segundos": linhas[0][1],
             "media_percentual": linhas[0][2]}
    curva = requests.get(API_ANALYTICS, timeout=30, headers=cab, params={
        **base, "metrics": "audienceWatchRatio,relativeRetentionPerformance",
        "dimensions": "elapsedVideoTimeRatio"})
    if curva.ok:
        saida["curva"] = [(float(r[0]), float(r[1])) for r in curva.json().get("rows") or []]
    return saida


def atualizar(log=print) -> list[dict]:
    """Consulta a API para cada video registrado e grava o resultado."""
    registros = [r for r in publicados() if r.get("youtube_id")]
    if not registros:
        log("nenhum video registrado ainda (publique com `main.py publicar <id> --youtube`).")
        return []
    token, credenciais = _token()
    ids = sorted({r["youtube_id"] for r in registros})
    stats = estatisticas(ids, token)
    PASTA.mkdir(parents=True, exist_ok=True)
    salvos = []
    for registro in registros:
        yid = registro["youtube_id"]
        dado = {**registro, **stats.get(yid, {}), "atualizado": datetime.now().isoformat(timespec="seconds")}
        desde = (dado.get("publicado_em") or registro["quando"])[:10]
        dado.update(retencao(yid, token, desde))
        with open(PASTA / f"{yid}.json", "w", encoding="utf-8") as fh:
            json.dump(dado, fh, ensure_ascii=False, indent=2)
        salvos.append(dado)
    log(f"{len(salvos)} video(s) atualizados em {PASTA}")
    return salvos


def carregar_salvas() -> list[dict]:
    saida = []
    if not PASTA.is_dir():
        return saida
    for arquivo in sorted(PASTA.glob("*.json")):
        try:
            with open(arquivo, encoding="utf-8-sig") as fh:
                saida.append(json.load(fh))
        except (OSError, ValueError):
            continue
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
        tombos.append({"fracao": r1, "queda": w0 - w1, "segundo": r1 * duracao})
    tombos.sort(key=lambda t: -t["queda"])
    saida = []
    for t in tombos[:quantas]:
        evento = evento_em(eventos, t["segundo"])
        saida.append({**t, "evento": rotulo_do_evento(evento) if evento else "?"})
    return saida


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
    return "".join(SPARK[min(7, int(7 * p / teto))] for p in pontos)


# --------------------------------------------------------------- relatorio
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
            f"  {(f'{d.get('media_segundos', 0):6.1f}' if d.get('media_segundos') is not None else '    --'):>8}"
            f"  {str(d.get('variante') or 'A'):<8}  {d.get('fonte_id', '')}:{d.get('perfil', '')}")
    erros = {d.get("erro") for d in dados if d.get("erro")}
    for erro in erros:
        linhas.append(f"\n  retencao indisponivel: {erro}")

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
    return atualizar(log=print)


__all__ = ["ESCOPO_ANALYTICS", "atualizar", "carregar_salvas", "cli", "publicados",
           "quedas", "registrar_publicacao", "relatorio", "retencao", "sparkline",
           "timeline_de"]
