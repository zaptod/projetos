# -*- coding: utf-8 -*-
"""A Vila DEITADA para o celular na horizontal (28/09/2026).

O Adrian decidiu "perto e grande" para a Vila do celular e pediu suporte ao
celular deitado ("pode mudar as casas de lugar se for mais facil"). Deitado,
a tela e larga (844x390 no aparelho de prova) e o mundo tambem (704x240):
a dobra do retrato (`retrato.py`), que existe para caber EM PE, so atrapalha.
Entao o arranjo deitado e o mundo INTEIRO numa fileira so, sem mudar casa
nenhuma de lugar, com o mesmo ceu de morros em cima e o mesmo pe de grama
embaixo. A prateleira e o placar saem de baixo e de cima (o app os poe numa
coluna e no cabecalho), e a fileira fica com a altura quase toda.

Mesma regra do retrato: nada de segundo desenho. O mundo e o
`arte.compor_mundo`, os habitantes continuam em coordenadas do MUNDO e o app
so soma o ceu no y (`para_paisagem`).
"""
from __future__ import annotations

from PIL import Image

from . import arte, retrato

CEU = retrato.CEU
PE = retrato.PE
LARGURA = arte.LARGURA
ALTURA = CEU + arte.ALTURA + PE

# o ceu tem o dobro de largura do retrato: mais nuvens e morros, a lua a
# direita (onde o celular deitado mostra o ceu livre do placar)
NUVENS = ((64, 96, 1.0), (214, 118, .8), (352, 78, 1.15), (160, 52, .7),
          (492, 110, .9), (620, 64, 1.05), (560, 40, .6))
MORROS_LONGE = retrato.MORROS_LONGE + ((580, 150, 30), (700, 130, 26))
MORROS_PERTO = retrato.MORROS_PERTO + ((550, 160, 15), (690, 170, 13))
LUA = (596, 84)


def geometria() -> dict:
    """O que o app precisa: uma fileira so, o mundo inteiro."""
    return {"ceu": CEU, "pe": PE, "largura": LARGURA, "altura": ALTURA,
            "fileira": arte.ALTURA, "fileiras": [[0, CEU]]}


def para_paisagem(x: float, y: float) -> tuple:
    """(x, y) do mundo -> (x, y) na Vila deitada."""
    return x, y + CEU


def para_mundo(x: float, y: float) -> tuple | None:
    """O inverso, para o toque. None no ceu, no pe e fora do mundo."""
    if 0 <= x < LARGURA and CEU <= y < CEU + arte.ALTURA:
        return x, y - CEU
    return None


def compor_paisagem(noite: bool = False, escala: int = 3) -> Image.Image:
    """A Vila inteira deitada, `escala` vezes maior, pronta para o celular."""
    e = max(1, int(escala))
    tela = Image.new("RGBA", (LARGURA * e, ALTURA * e), (0, 0, 0, 255))
    tela.paste(retrato.desenhar_ceu(noite, e, LARGURA, NUVENS, MORROS_LONGE,
                                    MORROS_PERTO, LUA), (0, 0))
    tela.paste(arte.compor_mundo(noite, e), (0, CEU * e))
    tela.paste(retrato.desenhar_pe(noite, e, LARGURA),
               (0, (CEU + arte.ALTURA) * e))
    return tela


__all__ = ["ALTURA", "CEU", "LARGURA", "PE", "compor_paisagem", "geometria",
           "para_mundo", "para_paisagem"]
