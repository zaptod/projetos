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
import sys
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
    return atualizar(log=print)


__all__ = ["ESCOPO_ANALYTICS", "atualizar", "carregar_salvas", "cli", "publicados",
           "custo_por_cena", "quedas", "registrar_publicacao",
           "registrar_publicado", "relatorio",
           "retencao", "sparkline",
           "timeline_de"]
