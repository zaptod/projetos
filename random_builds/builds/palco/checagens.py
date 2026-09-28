"""O mp4 do palco e o que devia ser? Medido no arquivo, nunca presumido.

- video: h264, resolucao pedida, numero de quadros = o do plano (e a duracao
  = quadros / fps);
- audio: a faixa existe, 48 kHz, e dura o mesmo que o video;
- volume do trecho de luta (o clipe do palco e todo luta): loudness integrada
  (ebur128) e media (volumedetect) acima do piso. So a media, como a guarda
  da publicacao desde 28/09 (6f09b80): silencio entre golpes e luta, nao mudo;
- a imagem nao e um quadro liso (a janela minimizada grava quadro vazio COM
  som e rc 0 — o palco ja sai com rc 4, e isto e a segunda rede).

Tambem o nivel: `ganho_para_alvo` mede a loudness integrada do AVI para a
compressao unica levar a luta ao nivel da mistura da 16A (~-18 LUFS).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _executar(comando: list, *, timeout: float = 300, binario: bool = False):
    return subprocess.run([str(c) for c in comando], capture_output=True, timeout=timeout,
                          creationflags=SEM_JANELA, **({} if binario else
                                                      {"text": True, "encoding": "utf-8", "errors": "replace"}))


def sonda(caminho: Path) -> dict:
    saida = _executar(["ffprobe", "-v", "error", "-show_entries",
                       "format=duration:stream=index,codec_type,codec_name,width,height,pix_fmt,"
                       "nb_frames,sample_rate,channels,duration,r_frame_rate",
                       "-of", "json", caminho], timeout=60)
    try:
        return json.loads(saida.stdout or "{}")
    except ValueError:
        return {}


def audio_mono(caminho: Path, taxa: int = 48000) -> np.ndarray:
    saida = _executar(["ffmpeg", "-v", "error", "-i", caminho, "-vn", "-ac", "1", "-ar", str(taxa),
                       "-f", "f32le", "-"], binario=True)
    return np.frombuffer(saida.stdout or b"", dtype=np.float32)


def energia_ativa_db(amostras: np.ndarray, taxa: int = 48000, janela_s: float = 0.05) -> float | None:
    """dBFS da energia media das janelas ATIVAS (ate 30 dB abaixo da mais
    alta e acima de -60 dBFS). None se nao ha nada ativo (mudo)."""
    tamanho = int(taxa * janela_s)
    if amostras.size < tamanho:
        return None
    n = amostras.size // tamanho
    rms = np.sqrt(np.mean(amostras[:n * tamanho].reshape(n, tamanho).astype(np.float64) ** 2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-9))
    ativas = rms[(db > db.max() - 30.0) & (db > -60.0)]
    if ativas.size == 0:
        return None
    return float(10 * np.log10(np.mean(ativas ** 2)))


def ganho_para_alvo(caminho: Path, *, alvo_lufs: float, ganho_max_db: float) -> tuple[float, float | None]:
    """Ganho (dB) que leva a loudness integrada do trecho de luta ao alvo.

    O alvo e o nivel da luta da 16A (~-18 LUFS). A primeira versao mirava a
    energia ativa em -13 dBFS, como a mistura da 16A diz fazer, e o duelo_00016
    saiu a -20,3 LUFS contra -16,5 do mesmo duelo no ar: 4 LU a menos, e num
    A/B de ouvido o mais alto parece o melhor. Mede-se entao o que se compara.
    Mudo (sem nada ativo) devolve 0 e a conferencia acusa."""
    if energia_ativa_db(audio_mono(caminho)) is None:
        return 0.0, None
    medido = loudness(caminho).get("lufs")
    if medido is None or medido == float("-inf"):
        return 0.0, None
    return float(np.clip(alvo_lufs - medido, -ganho_max_db, ganho_max_db)), medido


def loudness(caminho: Path) -> dict:
    saida = _executar(["ffmpeg", "-v", "info", "-nostats", "-i", caminho, "-vn",
                       "-af", "ebur128=peak=true,volumedetect", "-f", "null", "-"])
    texto = saida.stderr or ""
    resumo = texto[texto.rfind("Summary:"):] if "Summary:" in texto else texto
    medidas = {}
    for chave, padrao in (("lufs", r"I:\s+(-?[\d.]+|-inf) LUFS"), ("pico_dbfs", r"Peak:\s+(-?[\d.]+|-inf) dBFS"),
                          ("lra", r"LRA:\s+(-?[\d.]+) LU")):
        m = re.search(padrao, resumo)
        if m:
            medidas[chave] = float("-inf") if m.group(1) == "-inf" else float(m.group(1))
    m = re.search(r"mean_volume: (-?[\d.]+|-inf) dB", texto)
    if m:
        medidas["media_db"] = float("-inf") if m.group(1) == "-inf" else float(m.group(1))
    return medidas


def quadros_lisos(caminho: Path, duracao: float, *, amostras: int = 3) -> list[float]:
    """Desvio padrao do luma de alguns quadros (0 = quadro liso/vazio)."""
    desvios = []
    for k in range(amostras):
        t = duracao * (k + 1) / (amostras + 1)
        saida = _executar(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", caminho, "-frames:v", "1",
                           "-vf", "scale=108:192,format=gray", "-f", "rawvideo", "-"], binario=True, timeout=60)
        dados = np.frombuffer(saida.stdout or b"", dtype=np.uint8)
        desvios.append(float(dados.std()) if dados.size else 0.0)
    return desvios


def conferir(caminho: Path, *, quadros: int, fps: int, largura: int, altura: int,
             piso_lufs: float, piso_media_db: float) -> tuple[list[str], dict]:
    """(problemas, medidas). Lista vazia = o mp4 e o que devia ser."""
    caminho = Path(caminho)
    problemas: list[str] = []
    if not caminho.is_file():
        return [f"o mp4 nao existe: {caminho}"], {}
    info = sonda(caminho)
    faixas = info.get("streams") or []
    video = next((s for s in faixas if s.get("codec_type") == "video"), None)
    audio = next((s for s in faixas if s.get("codec_type") == "audio"), None)
    medidas: dict = {"ffprobe": info}
    if video is None:
        return ["o mp4 nao tem faixa de video"], medidas
    if (int(video.get("width", 0)), int(video.get("height", 0))) != (largura, altura):
        problemas.append(f"resolucao {video.get('width')}x{video.get('height')}, esperado {largura}x{altura}")
    n = int(video.get("nb_frames") or 0)
    medidas["quadros"] = n
    if n != quadros:
        problemas.append(f"{n} quadros no mp4, o plano pede {quadros}")
    dur_video = float(video.get("duration") or (info.get("format") or {}).get("duration") or 0.0)
    medidas["duracao_video"] = dur_video
    if abs(dur_video - quadros / fps) > 1.5 / fps:
        problemas.append(f"duracao {dur_video:.3f} s, esperado {quadros / fps:.3f} s")
    if audio is None:
        problemas.append("o mp4 nao tem faixa de audio")
    else:
        dur_audio = float(audio.get("duration") or 0.0)
        medidas["duracao_audio"] = dur_audio
        if int(audio.get("sample_rate") or 0) != 48000:
            problemas.append(f"audio a {audio.get('sample_rate')} Hz, esperado 48000")
        if abs(dur_audio - dur_video) > 0.1:
            problemas.append(f"audio com {dur_audio:.2f} s e video com {dur_video:.2f} s")
        nivel = loudness(caminho)
        medidas.update(nivel)
        if nivel.get("lufs") is None or nivel["lufs"] < piso_lufs:
            problemas.append(f"luta muda: {nivel.get('lufs')} LUFS, piso {piso_lufs}")
        if nivel.get("media_db") is None or nivel["media_db"] < piso_media_db:
            problemas.append(f"luta muda: media {nivel.get('media_db')} dB, piso {piso_media_db}")
    lisos = quadros_lisos(caminho, dur_video)
    medidas["desvio_luma"] = [round(d, 2) for d in lisos]
    if any(d < 2.0 for d in lisos):
        problemas.append(f"quadro liso (vazio?) no mp4: desvios {medidas['desvio_luma']}")
    return problemas, medidas
