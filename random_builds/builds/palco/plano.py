"""A conta dos quadros do palco, em Python: o espelho de `palco/nucleo/plano.gd`.

Serve para conferir o mp4 SEM confiar no Godot: o numero de quadros que o
video tem de ter sai daqui e do relatorio do Godot, e os dois tem de bater.

- Sem remapeamento: um trecho so, [0, duracao, 1].
- Trecho [inicio, duracao, velocidade]: round(duracao / velocidade * fps)
  quadros. O `round` e o do GDScript (meio para longe do zero), nao o
  arredondamento bancario do Python — a diferenca aparece em x,5.
"""
from __future__ import annotations

import math


def arredondar(x: float) -> int:
    """round() do GDScript: 2,5 -> 3 (o do Python daria 2)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def trechos(remapeamento, duracao_total: float) -> list[tuple[float, float, float]]:
    lista = (remapeamento or {}).get("trechos") if isinstance(remapeamento, dict) else remapeamento
    if not lista:
        return [(0.0, float(duracao_total), 1.0)]
    saida = []
    for trecho in lista:
        velocidade = float(trecho[2]) if len(trecho) > 2 else 1.0
        saida.append((float(trecho[0]), float(trecho[1]), velocidade))
    return saida


def quadros(duracao_total: float, remapeamento=None, fps: int = 30) -> int:
    return sum(arredondar(dur / vel * fps) for _ini, dur, vel in trechos(remapeamento, duracao_total))


def mapear(t: float, duracao_total: float, remapeamento=None, fps: int = 30) -> int:
    """Instante da gravacao -> quadro do video (-1 se caiu num corte)."""
    inicio = 0
    for ini, dur, vel in trechos(remapeamento, duracao_total):
        n = arredondar(dur / vel * fps)
        if t < ini - 1e-6:
            return -1
        if t <= ini + dur + 1e-6:
            return inicio + min(max(0, arredondar((t - ini) / vel * fps)), max(0, n - 1))
        inicio += n
    return -1
