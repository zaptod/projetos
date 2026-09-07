# -*- coding: utf-8 -*-
"""A porta para o ffmpeg e o ffprobe. Binario no PATH, chamado por subprocess.

Mesma doutrina do resto do repositorio (`builds/video/medidas.py`,
`builds/content/voz.py`): nunca um wrapper Python. E ha um aviso herdado de
la que vale repetir, porque custou tempo — **`returncode == 0` do ffmpeg NAO
prova que o arquivo esta inteiro**. Um mp4 sem `moov atom` (download morto no
meio) faz o ffmpeg sair feliz de varias operacoes e falhar na seguinte. Por
isso `sondar` confere se ha duracao e stream de video antes de dizer que deu
certo.

`CREATE_NO_WINDOW` em toda chamada: sem isso, medir 300 videos abre 300
janelas de console piscando na cara de quem esta usando o computador.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SemFerramenta(RuntimeError):
    """ffmpeg ou ffprobe nao estao no PATH."""


class NaoMediu(RuntimeError):
    """O arquivo existe mas o ffmpeg nao conseguiu ler."""


def faltando() -> list:
    return [nome for nome in ("ffmpeg", "ffprobe") if not shutil.which(nome)]


def exigir() -> None:
    ausentes = faltando()
    if ausentes:
        raise SemFerramenta(
            f"falta {' e '.join(ausentes)} no PATH.\n"
            "  winget install Gyan.FFmpeg\n"
            "  (feche e reabra o terminal depois de instalar.)")


def _rodar(comando: list, timeout: float) -> tuple:
    try:
        proc = subprocess.run(comando, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return 124, "", f"passou de {timeout:.0f}s"
    except OSError as exc:
        raise SemFerramenta(f"nao consegui executar: {exc}") from exc
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def ffprobe(argumentos: list, *, timeout: float = 120.0) -> tuple:
    exigir()
    return _rodar(["ffprobe", "-hide_banner"] + list(argumentos), timeout)


def ffmpeg(argumentos: list, *, timeout: float = 3600.0) -> tuple:
    exigir()
    return _rodar(["ffmpeg", "-hide_banner", "-nostdin"] + list(argumentos),
                  timeout)


def ffmpeg_binario(argumentos: list, *, timeout: float = 3600.0) -> tuple:
    """Como `ffmpeg`, mas devolve o stdout em BYTES.

    Existe para a amostragem de cor: cada frame vira um pixel `rgb24` cru na
    saida padrao. Decodificar isso como texto corromperia os bytes.
    """
    exigir()
    comando = ["ffmpeg", "-hide_banner", "-nostdin"] + list(argumentos)
    try:
        proc = subprocess.run(comando, capture_output=True, timeout=timeout,
                              creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return 124, b"", f"passou de {timeout:.0f}s"
    except OSError as exc:
        raise SemFerramenta(f"nao consegui executar: {exc}") from exc
    erro = (proc.stderr or b"").decode("utf-8", errors="replace")
    return proc.returncode, proc.stdout or b"", erro


def sondar(caminho: Path) -> dict:
    """Duracao, resolucao, fps e se ha audio. Levanta quando o arquivo mente.

    Um mp4 truncado costuma passar por aqui com duracao 0 e nenhum stream —
    e e exatamente o caso que precisa virar erro alto, porque todo o resto da
    medicao dividiria por essa duracao.
    """
    codigo, saida, erro = ffprobe([
        "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(caminho)])
    if codigo != 0 or not saida.strip():
        raise NaoMediu(_queixa(caminho, erro))
    try:
        dados = json.loads(saida)
    except ValueError as exc:
        raise NaoMediu(f"o ffprobe respondeu algo ilegivel para "
                       f"{Path(caminho).name}") from exc

    streams = dados.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    formato = dados.get("format") or {}
    duracao = float(formato.get("duration") or 0.0)
    if video is None or duracao <= 0:
        raise NaoMediu(
            f"{Path(caminho).name} nao tem video utilizavel "
            f"(duracao {duracao:.1f}s). Provavelmente o download morreu no "
            "meio — apague a pasta dele em midia/ e rode `baixar` de novo.")

    return {
        "duracao_s": round(duracao, 2),
        "largura": int(video.get("width") or 0),
        "altura": int(video.get("height") or 0),
        "fps": round(_fracao(video.get("avg_frame_rate")), 3),
        "codec_video": video.get("codec_name") or "",
        "tem_audio": audio is not None,
        "codec_audio": (audio or {}).get("codec_name") or "",
        "bitrate_kbps": round(float(formato.get("bit_rate") or 0) / 1000.0, 1),
        "tamanho_mb": round(float(formato.get("size") or 0) / 1e6, 2),
        "vertical": bool(video.get("height") and video.get("width")
                         and int(video["height"]) > int(video["width"])),
    }


def _conserto_do_truncado(nome: str) -> str:
    return (f"apague a pasta dele em midia/ e rode `baixar` de novo — "
            f"o arquivo {nome} esta incompleto.")


def _queixa(caminho: Path, erro: str) -> str:
    """A recusa do ffprobe, com o conserto quando da para reconhecer.

    O caso MAIS comum e o download morto no meio, e ele se anuncia com
    `moov atom not found`: o indice do mp4 fica no fim do arquivo, entao um
    download interrompido tem todos os bytes menos o que diz o que eles sao.
    Sem esta traducao, a mensagem seria uma linha de ffprobe que nao diz a
    ninguem o que fazer.
    """
    nome = Path(caminho).name
    bruto = (erro or "").strip()
    baixo = bruto.lower()
    if "moov atom not found" in baixo or "invalid data found" in baixo:
        return (f"{nome} nao e um video legivel (o indice do arquivo esta "
                f"faltando). Isso e download interrompido: "
                f"{_conserto_do_truncado(nome)}")
    if "no such file" in baixo or not Path(caminho).exists():
        return f"{nome} nao existe. Rode `baixar` para este canal."
    if "permission denied" in baixo:
        return (f"sem permissao para ler {nome} — provavelmente outro "
                "programa esta com o arquivo aberto.")
    return f"o ffprobe nao leu {nome}: {bruto[-300:]}"


def _fracao(texto) -> float:
    """`30000/1001` -> 29.97. O avg_frame_rate vem sempre assim."""
    try:
        bruto = str(texto or "0/1")
        if "/" in bruto:
            cima, baixo = bruto.split("/", 1)
            return float(cima) / float(baixo) if float(baixo) else 0.0
        return float(bruto)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0
