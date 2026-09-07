# -*- coding: utf-8 -*-
"""Etapa 2c: a fala do video em texto, com tempos.

Duas fontes, nesta ordem, e a ordem importa:

  A LEGENDA DO YOUTUBE, que ja veio no `baixar`. E gratis, instantanea e
  costuma ser boa. Quando o canal sobe legenda propria, e ate melhor que
  qualquer ASR — foi um humano que escreveu.

  O WHISPER LOCAL, so quando nao ha legenda nenhuma. Opcional de proposito
  (`pip install -e "./mimetizar[transcricao]"`): `torch` sozinho passa de
  2 GB, e quem so quer ler edicao e metadados nao deveria pagar por isso.
  Sem ele, o video segue sem transcricao e o dossie DIZ que segue — nunca se
  finge que houve fala analisada.

O trabalho sujo esta no parser de VTT. A legenda automatica do YouTube e
"rolante": cada bloco repete a linha anterior inteira e acrescenta uma
palavra, e vem salpicada de marcacao de tempo por palavra. Lido cru, um
video de 10 minutos vira 40 mil palavras — e a contagem de palavras por
minuto, que e uma das medidas que a biblia usa, sai seis vezes maior que a
real.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from . import baixar as _baixar
from . import canal as _canal
from . import config, estado

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# `00:01:02.345 --> 00:01:05.678 align:start position:0%`
_TEMPOS = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})")
# `<00:00:00.719>` e `<c>`/`</c>`: marcacao por palavra da legenda automatica.
_TAGS = re.compile(r"<[^>]*>")


class NaoTranscreveu(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


def _segundos(marca: str) -> float:
    horas, minutos, resto = marca.replace(",", ".").split(":")
    return int(horas) * 3600 + int(minutos) * 60 + float(resto)


def _marca(segundos: float) -> str:
    segundos = max(0.0, float(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, resto = divmod(resto, 60)
    inteiros = int(resto)
    milis = int(round((resto - inteiros) * 1000))
    if milis == 1000:                       # 2.9999 nao pode virar :03,1000
        inteiros, milis = inteiros + 1, 0
    return f"{int(horas):02d}:{int(minutos):02d}:{inteiros:02d},{milis:03d}"


def ler_legenda(caminho: Path) -> list:
    """VTT ou SRT -> [{inicio, fim, texto}], sem repeticao rolante."""
    bruto = Path(caminho).read_text(encoding="utf-8-sig", errors="replace")
    blocos = re.split(r"\n\s*\n", bruto.replace("\r\n", "\n"))
    falas, anterior = [], ""
    for bloco in blocos:
        linhas = [linha for linha in bloco.split("\n") if linha.strip()]
        if not linhas:
            continue
        tempos = next((_TEMPOS.search(linha) for linha in linhas
                       if _TEMPOS.search(linha)), None)
        if tempos is None:
            continue
        corpo = [linha for linha in linhas if not _TEMPOS.search(linha)
                 and not linha.strip().isdigit()]
        texto = _limpar(" ".join(corpo))
        if not texto:
            continue
        novo = _so_o_que_e_novo(texto, anterior)
        anterior = texto
        if not novo:
            continue
        falas.append({"inicio": _segundos(tempos.group(1)),
                      "fim": _segundos(tempos.group(2)), "texto": novo})
    return _juntar(falas)


def _limpar(texto: str) -> str:
    limpo = _TAGS.sub("", texto)
    limpo = limpo.replace("&nbsp;", " ").replace("&amp;", "&")
    limpo = limpo.replace("&lt;", "<").replace("&gt;", ">")
    limpo = limpo.replace("&#39;", "'").replace("&quot;", '"')
    return re.sub(r"\s+", " ", limpo).strip()


def _so_o_que_e_novo(texto: str, anterior: str) -> str:
    """A parte do bloco que ainda nao foi dita.

    A legenda automatica repete a linha inteira e acrescenta palavras. Sem
    isto, cada palavra e contada tantas vezes quantas aparecer na rolagem.
    """
    if texto == anterior:
        return ""
    if not anterior:
        return texto
    if texto.startswith(anterior):
        return texto[len(anterior):].strip()
    if anterior.startswith(texto):
        return ""
    # Sobreposicao parcial: o fim do anterior e o comeco deste.
    limite = min(len(texto), len(anterior))
    for tamanho in range(limite, 12, -1):
        if anterior.endswith(texto[:tamanho]):
            return texto[tamanho:].strip()
    return texto


def _juntar(falas: list, minimo: float = 1.2) -> list:
    """Junta fragmentos curtos demais para virar legenda legivel."""
    juntadas = []
    for fala in falas:
        if (juntadas and fala["fim"] - juntadas[-1]["inicio"] < minimo
                and len(juntadas[-1]["texto"]) < 60):
            juntadas[-1]["texto"] = f"{juntadas[-1]['texto']} {fala['texto']}"
            juntadas[-1]["fim"] = fala["fim"]
            continue
        juntadas.append(dict(fala))
    return juntadas


def para_srt(falas: list) -> str:
    linhas = []
    for ordem, fala in enumerate(falas, 1):
        linhas.append(str(ordem))
        linhas.append(f"{_marca(fala['inicio'])} --> {_marca(fala['fim'])}")
        linhas.append(fala["texto"])
        linhas.append("")
    return "\n".join(linhas)


def para_texto(falas: list) -> str:
    return " ".join(f["texto"] for f in falas).strip()


def estatisticas(falas: list, duracao_s: float = 0.0) -> dict:
    """Palavras, palavras por minuto, e o quanto do video tem fala."""
    texto = para_texto(falas)
    palavras = len(texto.split())
    falado = sum(max(0.0, f["fim"] - f["inicio"]) for f in falas)
    minutos_falados = max(falado / 60.0, 1e-6)
    dados = {"palavras": palavras, "falas": len(falas),
             "segundos_falados": round(falado, 1),
             # Por minuto FALADO, nao por minuto de video: um video com
             # trinta segundos de musica no fim nao "fala mais devagar".
             "wpm": round(palavras / minutos_falados, 1)}
    if duracao_s > 0:
        dados["densidade_pct"] = round(100.0 * falado / duracao_s, 1)
        dados["wpm_do_video"] = round(palavras / max(duracao_s / 60.0, 1e-6), 1)
    return dados


def whisper_disponivel() -> bool:
    return importlib.util.find_spec("whisper") is not None


def por_whisper(video: Path, destino: Path, *, modelo: str = "small",
                idioma: str = "", timeout: float = 3600.0, log=print) -> bool:
    """Transcreve com o whisper local. False quando ele nao esta instalado."""
    if not whisper_disponivel():
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    comando = [sys.executable, "-X", "utf8", "-m", "whisper", str(video),
               "--model", modelo, "--output_format", "srt",
               "--output_dir", str(destino.parent), "--verbose", "False"]
    if idioma:
        comando += ["--language", idioma]
    log(f"           whisper ({modelo}) — isto demora alguns minutos...")
    try:
        proc = subprocess.run(comando, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"           ! o whisper nao rodou: {exc}")
        return False
    if proc.returncode != 0:
        log(f"           ! o whisper falhou: {(proc.stderr or '')[-200:]}")
        return False
    # Ele grava com o nome do arquivo de entrada; renomeia para o id.
    gerado = destino.parent / f"{video.stem}.srt"
    if gerado.is_file() and gerado != destino:
        gerado.replace(destino)
    return destino.is_file()


def transcrever(canal_id: str, *, limite: int = 0, refazer: bool = False,
                modelo: str = "small", log=print) -> dict:
    """Transcreve o que esta em disco e ainda nao tem texto."""
    pasta = config.pasta_do_canal(canal_id)
    coleta = config.carregar("coleta")
    idiomas = (coleta.get("legendas") or {}).get("idiomas") or ["pt", "en"]
    destino = pasta / "transcricoes"
    destino.mkdir(parents=True, exist_ok=True)

    catalogo = {v["id"]: v for v in _canal.videos(pasta)}
    prontos = sorted(_baixar.baixados(pasta))
    alvos = prontos if refazer else [
        vid for vid in prontos if not (destino / f"{vid}.srt").is_file()]
    if limite and limite > 0:
        alvos = alvos[:limite]

    if not alvos:
        log("[transcrever] nada a fazer — tudo que esta em disco ja tem texto.")
        return {"transcritos": 0, "por_legenda": 0, "por_whisper": 0,
                "sem_texto": 0}

    log(f"[transcrever] {len(alvos)} video(s).")
    avisou_whisper = False
    por_legenda, por_whisper, sem_texto = 0, 0, []

    for ordem, video_id in enumerate(alvos, 1):
        titulo = (catalogo.get(video_id) or {}).get("titulo", "")[:52]
        log(f"[transcrever] {ordem}/{len(alvos)}  {video_id}  {titulo}")
        legenda = _baixar.legenda_de(pasta, video_id, idiomas)
        falas, origem = [], ""
        if legenda is not None:
            try:
                falas = ler_legenda(legenda)
                origem = f"legenda ({legenda.suffix.lstrip('.')})"
            except (OSError, ValueError) as exc:
                log(f"           ! nao li a legenda: {exc}")
        if not falas:
            video = _baixar.video_de(pasta, video_id)
            if video is None:
                sem_texto.append((video_id, "sem arquivo de video"))
                continue
            if not whisper_disponivel():
                if not avisou_whisper:
                    log("           sem legenda no YouTube e sem whisper "
                        "instalado. Para transcrever estes:\n"
                        '             pip install -e "./mimetizar[transcricao]"')
                    avisou_whisper = True
                sem_texto.append((video_id, "sem legenda e sem whisper"))
                continue
            alvo_srt = destino / f"{video_id}.srt"
            if por_whisper(video, alvo_srt, modelo=modelo, log=log):
                falas = ler_legenda(alvo_srt)
                origem = "whisper"
            if not falas:
                sem_texto.append((video_id, "o whisper nao produziu texto"))
                continue

        medida = _medida(pasta, video_id)
        stats = estatisticas(falas, medida.get("duracao_s", 0.0))
        (destino / f"{video_id}.srt").write_text(para_srt(falas),
                                                 encoding="utf-8")
        (destino / f"{video_id}.txt").write_text(para_texto(falas),
                                                 encoding="utf-8")
        (destino / f"{video_id}.json").write_text(
            json.dumps({"video_id": video_id, "origem": origem, **stats},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        if origem == "whisper":
            por_whisper += 1
        else:
            por_legenda += 1
        log(f"           {stats['palavras']} palavras · {stats['wpm']:.0f} wpm "
            f"· {origem}")

    estado.marcar(pasta, "transcrever", por_legenda=por_legenda,
                  por_whisper=por_whisper, sem_texto=len(sem_texto))
    if sem_texto:
        log(f"\n[transcrever] {len(sem_texto)} ficaram sem texto:")
        for video_id, motivo in sem_texto[:8]:
            log(f"    {video_id}: {motivo}")
    return {"transcritos": por_legenda + por_whisper,
            "por_legenda": por_legenda, "por_whisper": por_whisper,
            "sem_texto": len(sem_texto)}


def _medida(pasta: Path, video_id: str) -> dict:
    from . import medidas
    return medidas.carregar(pasta, video_id)


def carregar(pasta: Path, video_id: str) -> list:
    """As falas gravadas daquele video."""
    caminho = Path(pasta) / "transcricoes" / f"{video_id}.srt"
    if not caminho.is_file():
        return []
    try:
        return ler_legenda(caminho)
    except (OSError, ValueError):
        return []


def stats_de(pasta: Path, video_id: str) -> dict:
    caminho = Path(pasta) / "transcricoes" / f"{video_id}.json"
    if not caminho.is_file():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
