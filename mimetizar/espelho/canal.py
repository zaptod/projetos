# -*- coding: utf-8 -*-
"""Etapa 1: a URL de um canal vira um catalogo em disco. Sem baixar um byte.

Cataloga primeiro, baixa depois, e sao comandos separados de proposito: e o
catalogo que responde "sao 312 videos, cerca de 41 GB" ANTES de alguem
comprometer o disco e a madrugada. Um download em massa que comeca sem essa
conta e um download que trava o computador as tres da manha.

Sobre as datas: `--flat-playlist` nao visita a pagina de cada video (por isso
e rapido), e a data exata mora la. O yt-dlp sabe estimar a data pela POSICAO
do video na aba do canal (`approximate_date`), e e o que se usa aqui — bom o
bastante para ler cadencia, e marcado como aproximado para ninguem confundir
depois. A data exata entra sozinha no `baixar`, junto do `info.json`.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import config, estado, ytdlp

# As abas que valem como "o acervo do canal". `videos` primeiro porque e onde
# mora o conteudo longo, que e o que define o formato.
ABAS = ("videos", "shorts", "streams")


class NaoColetou(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


def normalizar_url(url: str, aba: str = "videos") -> str:
    """A URL da aba de videos do canal.

    Uma URL de canal pelada (`youtube.com/@nome`) devolve as ABAS do canal,
    nao os videos — o catalogo sairia com quatro linhas chamadas "Videos",
    "Shorts", "Playlists". Apontar para a aba resolve, e e invisivel para
    quem so colou o endereco da barra do navegador.
    """
    limpa = str(url or "").strip().strip('"').rstrip("/")
    if not limpa:
        raise NaoColetou("faltou a URL do canal.")
    if not limpa.startswith("http"):
        # `@nome` ou `nome` cru: o atalho que todo mundo digita.
        limpa = f"https://www.youtube.com/@{limpa.lstrip('@')}"
    # Ja veio com uma aba: TROCA pela pedida. Sem isto, quem colou
    # `.../@nome/videos` levaria a aba de videos tres vezes, e o catalogo
    # sairia sem shorts nem lives — mudo, porque o dedup por id esconde.
    if re.search(r"/(videos|shorts|streams|playlists|featured)$", limpa):
        return re.sub(r"/(videos|shorts|streams|playlists|featured)$",
                      f"/{aba}", limpa)
    if "/playlist" in limpa or "list=" in limpa:
        return limpa                      # playlist explicita: respeita
    if "/watch" in limpa or "youtu.be/" in limpa:
        raise NaoColetou(
            f"{url!r} e um video, nao um canal. Abra o canal do autor e copie "
            "a URL dele (a que tem @nome ou /channel/UC...).")
    return f"{limpa}/{aba}"


def _entradas(dados: dict) -> list:
    """As entradas de video, achatando a aba intermediaria quando houver."""
    entradas = dados.get("entries") or []
    if len(entradas) == 1 and (entradas[0] or {}).get("entries"):
        entradas = entradas[0]["entries"]
    return [e for e in entradas if isinstance(e, dict) and e.get("id")]


def _data(entrada: dict) -> tuple:
    """(data ISO, aproximada?) do que a entrada achatada oferecer."""
    bruta = entrada.get("upload_date")
    if bruta and re.fullmatch(r"\d{8}", str(bruta)):
        texto = str(bruta)
        return f"{texto[:4]}-{texto[4:6]}-{texto[6:]}", False
    marca = entrada.get("timestamp") or entrada.get("release_timestamp")
    if marca:
        try:
            momento = datetime.fromtimestamp(float(marca), tz=timezone.utc)
            return momento.date().isoformat(), True
        except (OSError, OverflowError, ValueError):
            pass
    return "", True


def _video(entrada: dict, aba: str) -> dict:
    data, aproximada = _data(entrada)
    return {
        "id": entrada.get("id") or "",
        "titulo": (entrada.get("title") or "").strip(),
        "url": entrada.get("url") or
               f"https://www.youtube.com/watch?v={entrada.get('id')}",
        "duracao_s": float(entrada.get("duration") or 0.0),
        "views": int(entrada.get("view_count") or 0),
        "data": data,
        "data_aproximada": aproximada,
        "aba": aba,
        "descricao": (entrada.get("description") or "").strip(),
    }


def coletar_aba(url: str, aba: str, *, log=print) -> tuple:
    """(cabecalho, videos) de uma aba. Aba vazia devolve lista vazia."""
    alvo = normalizar_url(url, aba)
    log(f"[canal] lendo {alvo} ...")
    argumentos = [
        "-J", "--flat-playlist", "--no-warnings",
        # Estima a data pela posicao na aba. Sem isto nao ha data nenhuma no
        # modo achatado, e sem data nao da para ler cadencia de publicacao.
        "--extractor-args", "youtubetab:approximate_date",
        alvo,
    ]
    try:
        dados = ytdlp.json_de(argumentos, timeout=600.0)
    except ytdlp.Falhou as exc:
        texto = str(exc)
        if "does not have a" in texto or "This channel does not have" in texto:
            log(f"[canal] o canal nao tem aba {aba}.")
            return {}, []
        raise NaoColetou(texto) from exc
    return dados, [_video(e, aba) for e in _entradas(dados)]


def catalogar(url: str, *, abas=ABAS, log=print) -> dict:
    """Cataloga o canal inteiro e grava a pasta. Devolve o resumo."""
    ytdlp.exigir()
    cabecalho, videos = coletar_aba(url, abas[0], log=log)
    if not videos and not cabecalho:
        raise NaoColetou(
            f"nao achei videos em {url!r}. Confira se a URL abre no navegador.")
    vistos = {v["id"] for v in videos}
    for aba in abas[1:]:
        try:
            _extra, novos = coletar_aba(url, aba, log=log)
        except NaoColetou as exc:
            log(f"[canal] aba {aba} nao veio: {exc}")
            continue
        acrescentados = [v for v in novos if v["id"] not in vistos]
        vistos.update(v["id"] for v in acrescentados)
        videos.extend(acrescentados)
        if acrescentados:
            log(f"[canal] aba {aba}: +{len(acrescentados)} video(s)")

    if not videos:
        raise NaoColetou(
            f"o canal {url!r} respondeu, mas sem nenhum video publico.")

    canal_id, pasta = config.criar_canal()
    dados = {
        "canal_id": canal_id,
        "url": str(url).strip(),
        "url_coletada": normalizar_url(url, abas[0]),
        "nome": cabecalho.get("channel") or cabecalho.get("uploader")
                or cabecalho.get("title") or "",
        "youtube_id": cabecalho.get("channel_id") or cabecalho.get("id") or "",
        "inscritos": int(cabecalho.get("channel_follower_count") or 0),
        "descricao": (cabecalho.get("description") or "").strip(),
        "n_videos": len(videos),
        "duracao_total_s": round(sum(v["duracao_s"] for v in videos), 1),
        "coletado_em": datetime.now(timezone.utc).astimezone()
                               .isoformat(timespec="seconds"),
        "yt_dlp": ytdlp.versao(),
    }
    (pasta / "canal.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    gravar_videos(pasta, videos)
    estado.marcar(pasta, "canal", n_videos=len(videos), url=dados["url"])
    dados["pasta"] = str(pasta)
    return dados


def gravar_videos(pasta: Path, videos: list) -> Path:
    """`videos.jsonl` — uma linha por video, na ordem em que o canal lista."""
    destino = Path(pasta) / "videos.jsonl"
    linhas = [json.dumps(v, ensure_ascii=False) for v in videos]
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino


def videos(pasta: Path) -> list:
    """As linhas de `videos.jsonl`. Linha corrompida e pulada, nao fatal."""
    caminho = Path(pasta) / "videos.jsonl"
    if not caminho.is_file():
        return []
    encontrados = []
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            dado = json.loads(linha)
        except ValueError:
            continue
        if isinstance(dado, dict) and dado.get("id"):
            encontrados.append(dado)
    return encontrados


def cabecalho(pasta: Path) -> dict:
    """O `canal.json` daquela pasta."""
    caminho = Path(pasta) / "canal.json"
    if not caminho.is_file():
        raise NaoColetou(f"falta o canal.json em {pasta}")
    return json.loads(caminho.read_text(encoding="utf-8-sig"))


def selecionar(lista: list, *, limite: int = 0, criterio: str = "canal") -> list:
    """Quais videos entram nesta passada.

    `canal` respeita a ordem do canal (o mais novo primeiro, como o YouTube
    lista). `views` pega os campeoes, que e o que se quer quando o limite e
    pequeno: o formato que funcionou, nao o que foi publicado ontem.
    """
    escolhidos = list(lista)
    if criterio == "views":
        escolhidos.sort(key=lambda v: v.get("views") or 0, reverse=True)
    elif criterio == "antigos":
        escolhidos.reverse()
    return escolhidos[:limite] if limite and limite > 0 else escolhidos
