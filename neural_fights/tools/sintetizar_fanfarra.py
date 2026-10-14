"""Fanfarra curta de vitoria, sintetizada (sem asset de fora).

Decisao do Adrian de 14/10/2026 (Grimorio ``builds/som-da-vitoria``: "Uma
fanfarra curta de vitoria"). Ate ali ``arena_victory`` nao tinha arquivo: o
jogo caia no fallback ``arena_start`` (a abertura da arena) e na categoria
"ambiente", que o ``sound_config.json`` do Adrian deixa em 0,03 -- a vitoria
saia quase muda. Nenhum som do pacote e fanfarra; a ordem era sintetizar
curto, como ``random_builds/builds/video/trilha.py`` faz com o resto.

O arquivo sai deterministico (mesma entrada, mesmos bytes): tres notas
ascendentes de metal (Do-Mi-Sol) e o acorde de Do maior sustentado, ~1,4 s.
Rodar de novo so e preciso se a receita mudar::

    python -m neural_fights.tools.sintetizar_fanfarra
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

TAXA = 44100
DESTINO = Path(__file__).resolve().parents[1] / "sounds" / "arena_victory.wav"

# (inicio em s, duracao em s, frequencias em Hz)
NOTAS = (
    (0.00, 0.16, (523.25,)),                    # C5
    (0.15, 0.16, (659.25,)),                    # E5
    (0.30, 0.16, (783.99,)),                    # G5
    (0.46, 0.95, (523.25, 659.25, 783.99, 1046.5)),  # C maior, sustentado
)
PICO = 0.85


def _metal(freq: float, t: float) -> float:
    """Timbre de metal: fundamental + harmonicos impares e pares decrescentes."""
    return (
        math.sin(2 * math.pi * freq * t)
        + 0.55 * math.sin(2 * math.pi * freq * 2 * t)
        + 0.35 * math.sin(2 * math.pi * freq * 3 * t)
        + 0.18 * math.sin(2 * math.pi * freq * 4 * t)
    )


def _envelope(t: float, dur: float) -> float:
    ataque = min(1.0, t / 0.012)
    soltura = min(1.0, max(0.0, (dur - t) / 0.12))
    return ataque * soltura * math.exp(-t * 1.6)


def sintetizar(taxa: int = TAXA) -> list[float]:
    total = max(inicio + dur for inicio, dur, _ in NOTAS)
    amostras = [0.0] * int(total * taxa)
    for inicio, dur, freqs in NOTAS:
        i0 = int(inicio * taxa)
        for k in range(int(dur * taxa)):
            t = k / taxa
            valor = sum(_metal(f, t) for f in freqs) / len(freqs)
            amostras[i0 + k] += valor * _envelope(t, dur)
    pico = max(abs(a) for a in amostras) or 1.0
    return [a * PICO / pico for a in amostras]


def gravar(destino: Path = DESTINO, taxa: int = TAXA) -> Path:
    amostras = sintetizar(taxa)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        quadros = bytearray()
        for a in amostras:
            v = int(round(max(-1.0, min(1.0, a)) * 32767))
            quadros += struct.pack("<hh", v, v)
        arquivo.writeframes(bytes(quadros))
    return destino


if __name__ == "__main__":
    print(gravar())
