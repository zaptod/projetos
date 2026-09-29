# -*- coding: utf-8 -*-
"""A Vila DOBRADA para o celular em pe (28/09/2026).

O PROBLEMA: o mundo e largo e baixo (704x240), feito para a janela
flutuante. Num celular em pe (390x~640 livres), caber pela altura deixava
a Vila ampliada ~2,3x e mostrava DOIS predios e dois habitantes; os outros
nove predios ficavam fora da tela — com o erro deles junto. Predio que
some e o jeito mais silencioso de mentir.

A SOLUCAO: a mesma Vila, em duas fileiras. A fileira de cima e o mundo de
x=0 a x=DOBRA; a de baixo, de x=DOBRA ate o fim, completada por um pedaco
de campo (EXTRA) para as duas terem a mesma largura. Entre elas, uma sebe;
em cima, o ceu (onde ficam o titulo e o placar do app); embaixo, o pe de
grama que encosta na prateleira.

A DOBRA em x=420 foi escolhida medindo: e a unica faixa em que nenhum
predio, casa ou arvore fica cortado ao meio nas DUAS ruas (a de cima tem
arvore ate 418 e o PicassoIA a partir de 444; a de baixo, a travessa ate
416 e o YouTube a partir de 428). Ha teste disso.

NADA DE SEGUNDO DESENHO: o mundo e o `arte.compor_mundo` e os habitantes
continuam em coordenadas do MUNDO (a vida roda no servidor, igual). O app
so converte (x, y) do mundo para o retrato com `para_retrato`, a mesma
conta que esta aqui.
"""
from __future__ import annotations

import math
import random

from PIL import Image

from . import arte

DOBRA = 420
EXTRA = 2 * DOBRA - arte.LARGURA        # 136 de campo a direita da fileira 2
CEU = 160
SEBE = 16
PE = 90
LARGURA = DOBRA
ALTURA = CEU + 2 * arte.ALTURA + SEBE + PE
LINHA_2 = CEU + arte.ALTURA + SEBE       # y do topo da fileira de baixo

# o campo EXTRA (coordenadas do mundo, x >= 704)
ARVORES_EXTRA = [(716, 6, "#6cc06a"), (770, 30, "#5fb45a"),
                 (798, 128, "#56a86a"), (742, 150, "#5fb45a")]


def geometria() -> dict:
    """O que o app precisa para desenhar e para converter o toque.

    `fileiras`: [x0 do mundo, y no retrato] de cada fileira, de cima para
    baixo. E o que o app usa para converter nos dois arranjos (em pe e
    deitado, `paisagem.geometria`); o resto fica para a casca antiga.
    """
    return {"dobra": DOBRA, "ceu": CEU, "sebe": SEBE, "pe": PE,
            "largura": LARGURA, "altura": ALTURA, "linha2": LINHA_2,
            "fileira": arte.ALTURA, "fileiras": [[0, CEU], [DOBRA, LINHA_2]]}


def para_retrato(x: float, y: float) -> tuple:
    """(x, y) do mundo -> (x, y) no retrato."""
    if x < DOBRA:
        return x, y + CEU
    return x - DOBRA, y + LINHA_2


def para_mundo(x: float, y: float) -> tuple | None:
    """O inverso, para o toque. None fora das fileiras (ceu, sebe, pe)."""
    if CEU <= y < CEU + arte.ALTURA:
        return x, y - CEU
    if LINHA_2 <= y < LINHA_2 + arte.ALTURA:
        return x + DOBRA, y - LINHA_2
    return None


# ================================================================ pedacos
def _degrade(p: arte.Pincel, largura: float, altura: float, topo, base,
             y0: float = 0.0, total: float | None = None) -> None:
    """Degrade vertical de cima para baixo, linha a linha (interno)."""
    k = p.k
    total = total if total is not None else altura
    topo, base = arte.rgb(topo) if isinstance(topo, str) else topo, \
        arte.rgb(base) if isinstance(base, str) else base
    for y in range(int(altura * k)):
        t = (y0 * k + y) / (total * k)
        p.d.line([(0, y), (largura * k, y)],
                 fill=arte.mistura(topo, base, t) + (255,))


def _tufos_e_flores(p: arte.Pincel, rnd: random.Random, largura: float,
                    altura: float, tufos: int, flores: int, livre=None) -> None:
    for _ in range(tufos):
        x, y = rnd.uniform(4, largura - 4), rnd.uniform(5, altura - 3)
        if livre and not livre(x, y):
            continue
        tom = rnd.choice(["#6fb35a", "#5fa14f", "#8fcf72"])
        p.linha([(x - 1.5, y), (x - 2.5, y - 3)], tom, 0.8)
        p.linha([(x, y), (x, y - 4)], tom, 0.8)
        p.linha([(x + 1.5, y), (x + 2.5, y - 3)], tom, 0.8)
    for _ in range(flores):
        x, y = rnd.uniform(6, largura - 6), rnd.uniform(6, altura - 6)
        if livre and not livre(x, y):
            continue
        cor = rnd.choice(["#ff9fb8", "#ffd56b", "#ffffff", "#c9a7ff",
                          "#ff8a7a"])
        for k in range(5):
            a = k * 2 * math.pi / 5
            p.circulo(x + math.cos(a) * 1.5, y + math.sin(a) * 1.5, 1.1, cor)
        p.circulo(x, y, 0.8, "#ffb43c")


def desenhar_campo_extra(noite: bool, escala: int) -> Image.Image:
    """O campo que completa a fileira de baixo: grama, flores e arvores.

    Mesmo degrade do chao do mundo (as duas grama se encostam em x=704) e
    as ruas do mundo terminam ali, com a ponta redonda: e a beira da vila.
    """
    rnd = random.Random(4211)
    p = arte.Pincel(EXTRA, arte.ALTURA, escala)
    _degrade(p, EXTRA, arte.ALTURA, arte.GRAMA_TOPO, arte.GRAMA_BASE)
    _tufos_e_flores(p, rnd, EXTRA, arte.ALTURA, 26, 12)
    campo = p.final()
    if noite:
        campo = arte.noturno(campo)
    fixos = [(y + 44, arte.desenhar_arvore(tom, escala), x, y, "arvore")
             for x, y, tom in ARVORES_EXTRA]
    # a placa na ponta da rua de cima: ali acaba a vila
    fixos.append((arte.RUA_Y[0] - 4, desenhar_placa(escala), 714,
                  arte.RUA_Y[0] - 28, "enfeite"))
    for _base, img, x, y, tipo in sorted(fixos, key=lambda f: f[0]):
        arte.assentar(campo, img, x - arte.LARGURA, y, tipo, noite, escala)
    return campo


def desenhar_placa(escala: int = 1) -> Image.Image:
    """Placa de madeira com a seta de volta para a vila."""
    p = arte.Pincel(22, 26, escala)
    p.ret(10, 8, 12.5, 25, 1, "#8a5a3c", "#6b4226", .5)
    p.poli([(4, 4), (20, 4), (20, 13), (4, 13), (1, 8.5)], "#c9905d",
           "#8a5a3c", .7)
    p.linha([(7, 7), (17, 7)], "#e8c49a", .7)
    p.linha([(10, 10), (17, 10)], "#e8c49a", .7)
    return p.final()


# o ceu do retrato: nuvens (cx, cy, tamanho) e morros (cx, largura, altura)
NUVENS = ((64, 96, 1.0), (214, 118, .8), (352, 78, 1.15), (160, 52, .7))
MORROS_LONGE = ((40, 120, 26), (170, 150, 32), (320, 170, 28), (440, 120, 24))
MORROS_PERTO = ((-10, 150, 14), (130, 170, 17), (270, 150, 13), (410, 170, 16))
LUA = (352, 84)


def desenhar_ceu(noite: bool, escala: int, largura: int = LARGURA,
                 nuvens=NUVENS, morros_longe=MORROS_LONGE,
                 morros_perto=MORROS_PERTO, lua=LUA) -> Image.Image:
    """O ceu com morros ao longe; embaixo ele vira a grama da fileira 1.

    `largura` e o resto existem para a Vila deitada (`paisagem.py`), que usa
    o mesmo ceu com o mundo inteiro embaixo; com os padroes, e o do retrato.
    """
    rnd = random.Random(90 if noite else 17)
    p = arte.Pincel(largura, CEU, escala)
    if noite:
        _degrade(p, largura, CEU, "#10163a", "#34407a")
    else:
        _degrade(p, largura, CEU, "#7cc4ec", "#d4f0fb")
    if noite:
        for _ in range(int(70 * largura / LARGURA)):
            x, y = rnd.uniform(2, largura - 2), rnd.uniform(2, CEU - 34)
            r = rnd.choice((.45, .55, .7, .9))
            p.circulo(x, y, r, arte.mistura("#fff6d8", "#34407a",
                                            rnd.uniform(0, .5)))
        # lua crescente: um circulo claro menos um da cor do ceu
        p.circulo(lua[0], lua[1], 9, "#fff3c4")
        p.circulo(lua[0] + 5, lua[1] - 3, 8,
                  arte.mistura("#10163a", "#34407a", (lua[1] - 3) / CEU))
    else:
        for cx, cy, tam in nuvens:
            _nuvem(p, cx, cy, tam)
    # morros: longe (mais claro, puxado para o ceu) e perto (a grama)
    longe = arte.mistura(arte.GRAMA_TOPO, "#d4f0fb", .45)
    perto = arte.mistura(arte.GRAMA_TOPO, "#ffffff", .08)
    for cx, largura_m, alt in morros_longe:
        p.elipse(cx - largura_m / 2, CEU - alt, cx + largura_m / 2,
                 CEU + alt, longe)
    for cx, largura_m, alt in morros_perto:
        p.elipse(cx - largura_m / 2, CEU - alt, cx + largura_m / 2,
                 CEU + alt, perto)
    p.ret(-2, CEU - 3, largura + 2, CEU + 2, 0, arte.GRAMA_TOPO)
    ceu = p.final()
    if noite:
        # so os morros escurecem como o chao; o ceu ja e de noite
        morros = arte.Pincel(largura, CEU, escala)
        for cx, largura_m, alt in morros_longe:
            morros.elipse(cx - largura_m / 2, CEU - alt, cx + largura_m / 2,
                          CEU + alt, arte.mistura(longe, "#34407a", .3))
        for cx, largura_m, alt in morros_perto:
            morros.elipse(cx - largura_m / 2, CEU - alt, cx + largura_m / 2,
                          CEU + alt, perto)
        morros.ret(-2, CEU - 3, largura + 2, CEU + 2, 0, arte.GRAMA_TOPO)
        camada = arte.noturno(morros.final())
        camada.putalpha(morros.final().getchannel("A"))
        ceu.alpha_composite(camada)
    return ceu


def _nuvem(p: arte.Pincel, cx: float, cy: float, tam: float) -> None:
    partes = ((-14, 2, 9), (-4, -3, 11), (9, -1, 10), (18, 3, 7))
    for dx, dy, r in partes:                       # a sombra de baixo
        p.circulo(cx + dx * tam, cy + (dy + 1.6) * tam, r * tam, "#cfe6f3")
    for dx, dy, r in partes:
        p.circulo(cx + dx * tam, cy + dy * tam, r * tam, "#ffffff")
    p.ret(cx - 22 * tam, cy + 2 * tam, cx + 24 * tam, cy + 10 * tam,
          4 * tam, "#ffffff")


def desenhar_sebe(noite: bool, escala: int) -> Image.Image:
    """A sebe entre as fileiras: moitas redondas com florzinhas.

    Sai com SEBE + 12 de altura: 6 invadem cada fileira, para a emenda
    das duas gramas (uma escura, outra clara) ficar escondida.
    """
    rnd = random.Random(33)
    altura = SEBE + 12
    p = arte.Pincel(LARGURA, altura, escala)
    meio = altura / 2
    p.ret(-4, meio - 7, LARGURA + 4, meio + 7, 7, "#4f9a44")
    x = -6.0
    while x < LARGURA + 8:
        r = rnd.uniform(6.5, 8.5)
        p.circulo(x, meio - rnd.uniform(0, 1.5), r, "#5aa94c", "#3f8a3a", .7)
        x += r * rnd.uniform(1.2, 1.5)
    x = -2.0
    while x < LARGURA + 8:
        r = rnd.uniform(3.5, 5)
        p.circulo(x, meio - 3 - rnd.uniform(0, 1.5), r, "#74c160")
        x += rnd.uniform(9, 15)
    for _ in range(26):
        fx, fy = rnd.uniform(4, LARGURA - 4), meio + rnd.uniform(-4, 3)
        cor = rnd.choice(["#ff9fb8", "#ffffff", "#ffd56b"])
        for k in range(5):
            a = k * 2 * math.pi / 5
            p.circulo(fx + math.cos(a) * 1.1, fy + math.sin(a) * 1.1, .8, cor)
        p.circulo(fx, fy, .6, "#ffb43c")
    sombra = arte.Pincel(LARGURA, altura, escala)
    sombra.ret(-4, meio + 3, LARGURA + 4, meio + 10, 4, (30, 60, 20))
    sombra.desfocar(2.5)
    sombra_img = sombra.final()
    sombra_img.putalpha(sombra_img.getchannel("A").point(lambda a: a * 55 // 255))
    img = Image.new("RGBA", sombra_img.size, (0, 0, 0, 0))
    img.alpha_composite(sombra_img)
    img.alpha_composite(p.final())
    if noite:
        img = arte._escurecer_imagem(img, .45)
    return img


def desenhar_pe(noite: bool, escala: int, largura: int = LARGURA) -> Image.Image:
    """A grama embaixo da fileira 2, que desce ate a prateleira."""
    rnd = random.Random(5150)
    p = arte.Pincel(largura, PE, escala)
    _degrade(p, largura, PE, arte.GRAMA_BASE, "#62a64f")
    _tufos_e_flores(p, rnd, largura, PE, int(60 * largura / LARGURA),
                    int(14 * largura / LARGURA))
    pe = p.final()
    return arte.noturno(pe) if noite else pe


# ================================================================== tudo
def compor_retrato(noite: bool = False, escala: int = 3) -> Image.Image:
    """A Vila inteira em pe, `escala` vezes maior, pronta para o celular."""
    e = max(1, int(escala))
    mundo = arte.compor_mundo(noite, e)
    faixa = Image.new("RGBA", (2 * DOBRA * e, arte.ALTURA * e))
    faixa.paste(mundo, (0, 0))
    faixa.paste(desenhar_campo_extra(noite, e), (arte.LARGURA * e, 0))
    tela = Image.new("RGBA", (LARGURA * e, ALTURA * e), (0, 0, 0, 255))
    tela.paste(desenhar_ceu(noite, e), (0, 0))
    tela.paste(faixa.crop((0, 0, DOBRA * e, arte.ALTURA * e)), (0, CEU * e))
    tela.paste(faixa.crop((DOBRA * e, 0, 2 * DOBRA * e, arte.ALTURA * e)),
               (0, LINHA_2 * e))
    # a faixa da sebe comeca com grama (a cor de baixo da fileira 1)
    base = arte.rgb(arte.GRAMA_BASE)
    if noite:
        base = arte.mistura(base, arte.NOITE, arte.NOITE_CHAO)
    tela.paste(base + (255,), (0, (CEU + arte.ALTURA) * e, LARGURA * e,
                               LINHA_2 * e))
    sebe = desenhar_sebe(noite, e)
    tela.alpha_composite(sebe, (0, (CEU + arte.ALTURA - 6) * e))
    tela.paste(desenhar_pe(noite, e), (0, (LINHA_2 + arte.ALTURA) * e))
    return tela


__all__ = ["ALTURA", "CEU", "DOBRA", "LARGURA", "LINHA_2", "PE", "SEBE",
           "compor_retrato", "geometria", "para_mundo", "para_retrato"]
