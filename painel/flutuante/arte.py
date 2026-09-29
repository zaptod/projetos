# -*- coding: utf-8 -*-
"""A arte FOFA da Vila: lisa, arredondada, sem pixel. Procedural e fixa.

PEDIDO DO ADRIAN (17/09/2026): "deixe a vila bem mais bonitinha, mude a arte
dela completamente, nao quero isso pixelado".

O Tk nao suaviza poligono nenhum. Entao tudo e desenhado com o Pillow em
QUATRO vezes o tamanho e reduzido com LANCZOS: e o antialias que o Canvas
nao tem. Sai PNG com transparencia de verdade.

Nada aqui baixa arte nem usa IA de imagem (a conta do PicassoIA e da
producao). Tudo e deterministico: `random.Random(semente)`, nunca o
`random` global — gerar duas vezes da os MESMOS bytes, e ha teste disso.

O CONTRATO DE PAPEL continua: a cena pede `predio.<nome>`,
`habitante.<nome>` etc. por NOME; nome desconhecido cai num desenho
generico com a cor de reserva, nunca some.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 4                       # super-amostragem
# ESCALA (28/09/2026): o celular amplia a Vila ate ~7 pixels do aparelho por
# pixel do mundo, e a arte de 1x chegava borrada. Toda funcao de desenho
# aceita `escala` e desenha DE VERDADE nesse tamanho (nada de ampliar a
# imagem pronta). As coordenadas continuam em pixels do MUNDO: so o Pincel
# sabe da escala. Com escala 1 o resultado e byte a byte o de antes (ha
# teste), e e o que a janela flutuante usa.
LARGURA, ALTURA = 704, 240
RUA_Y = (88, 216)           # linha do meio das duas ruas
TRAVESSAS_X = (280, 408)
PREDIO_W, PREDIO_H = 72, 64  # a imagem do predio (o lote e 64x48)
PERSONAGEM_W, PERSONAGEM_H = 26, 32

LOTES = {
    "deepseek": (1, 1), "grok": (5.5, 1), "chatgpt": (10, 1),
    "gemini": (19, 1), "picasso": (28, 1), "digen": (37, 1),
    "estudio": (1, 9), "arena": (7, 9), "youtube": (27, 9),
    "tiktok": (32, 9), "bot": (37, 9),
}
CASA = (20, 9)
TILE = 16
# O GROK (29/09/2026, Vila das IAs fase 2) entrou na unica vaga de 72 px do
# mundo: entre o DeepSeek e o ChatGPT, onde havia uma arvore com um
# caminhozinho em x=112 (o ponto "arvore" do passeio). Meio tile para cair
# no centro da vaga: 8 px de cada telhado vizinho. Lote novo entra nesta
# lista TAMBEM, para o resto da vila continuar byte a byte igual: o sorteio
# das flores (`desenhar_chao`) so tira a cor de quem nasce, e excluir um
# lote novo ANTES da cor embaralharia todas as flores. Aqui a flor sorteia
# igual e so nao e pintada.
LOTES_TARDIOS = ("grok",)

CORES = {
    "deepseek": "#5b7cfa", "chatgpt": "#2fb489", "gemini": "#6f8ff0",
    "picasso": "#c678e6", "digen": "#ec7aa6", "estudio": "#f0a646",
    "arena": "#e2574c", "youtube": "#e8453c", "tiktok": "#3b3748",
    "bot": "#8676e8", "casa": "#e07a5f", "grok": "#5c667c",
}
COR_RESERVA = "#a89684"
PELES = ["#ffe0c7", "#f6d0b1", "#e9b996", "#ffe7d6", "#d9a47f"]
# A pele de cada habitante vem da posicao do nome NESTA ordem (era
# `sorted(CORES)`). Nome novo entra no fim: no meio, mudaria a pele de quem
# ja existe.
ORDEM_DAS_PELES = ["arena", "bot", "casa", "chatgpt", "deepseek", "digen",
                   "estudio", "gemini", "picasso", "tiktok", "youtube",
                   "grok"]

# Pontos de interesse do passeio (a mesma geometria do `vida.py`).
BANCO = (136, 116)
FONTE = (344, 122)
CANTEIRO = (528, 118)
LAGO = (224, 164)
# (tile x, tile y, tom). O tom era `i % 3` na ordem antiga, que tinha uma
# arvore em (6, 1) — hoje o lote do Grok; fixado por arvore para nenhuma
# outra mudar de cor.
ARVORES = [(15, 1, "#6cc06a"), (24, 1, "#56a86a"), (33, 1, "#5fb45a"),
           (42, 1, "#6cc06a"), (42, 9, "#56a86a"), (42, 11, "#5fb45a")]


def rgb(cor: str) -> tuple:
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


def mistura(a, b, t: float) -> tuple:
    a, b = (rgb(a) if isinstance(a, str) else a), (
        rgb(b) if isinstance(b, str) else b)
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a[:3], b[:3]))


def clarear(cor, t=0.35):
    return mistura(cor, (255, 255, 255), t)


def escurecer(cor, t=0.25):
    return mistura(cor, (40, 28, 30), t)


def _c(cor, alfa=255):
    return (rgb(cor) if isinstance(cor, str) else tuple(cor[:3])) + (alfa,)


def fator(escala: int = 1) -> int:
    """Pixels internos por pixel do mundo. 1x: 4 (o de sempre); 2x e 3x:
    super-amostragem 2 sobre a escala, que ja da o antialias e poupa
    memoria (o mundo a 3x com 4 viraria 8448x2880 por camada)."""
    return S if escala <= 1 else int(escala) * 2


class Pincel:
    """ImageDraw em coordenadas do MUNDO (multiplica por `k`)."""

    def __init__(self, largura: float, altura: float, escala: int = 1):
        self.escala = max(1, int(escala))
        self.k = fator(self.escala)
        self.img = Image.new("RGBA", (int(largura * self.k),
                                      int(altura * self.k)), (0, 0, 0, 0))
        # Cor com alfa aqui SUBSTITUI o pixel (a mancha de luz virava um
        # buraco transparente). Quem precisa de translucido desenha numa
        # camada propria e usa `alpha_composite` (ver as manchas do chao).
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pontos):
        k = self.k
        return [(x * k, y * k) for x, y in pontos]

    def elipse(self, x0, y0, x1, y1, cor, borda=None, w=1.0):
        k = self.k
        self.d.ellipse([x0 * k, y0 * k, x1 * k, y1 * k], fill=_c(cor),
                       outline=_c(borda) if borda else None,
                       width=int(w * k) if borda else 0)

    def circulo(self, cx, cy, r, cor, borda=None, w=1.0):
        self.elipse(cx - r, cy - r, cx + r, cy + r, cor, borda, w)

    def ret(self, x0, y0, x1, y1, r, cor, borda=None, w=1.0):
        k = self.k
        self.d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k],
                                 radius=r * k, fill=_c(cor),
                                 outline=_c(borda) if borda else None,
                                 width=int(w * k) if borda else 0)

    def poli(self, pontos, cor, borda=None, w=1.0):
        pts = self._p(pontos)
        self.d.polygon(pts, fill=_c(cor))
        if borda:
            self.d.line(pts + [pts[0]], fill=_c(borda),
                        width=int(w * self.k), joint="curve")

    def linha(self, pontos, cor, w=1.0):
        pts = self._p(pontos)
        self.d.line(pts, fill=_c(cor), width=max(1, int(w * self.k)),
                    joint="curve")
        for x, y in (pts[0], pts[-1]):            # pontas redondas
            r = w * self.k / 2
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=_c(cor))

    def arco(self, x0, y0, x1, y1, ini, fim, cor, w=1.0):
        k = self.k
        self.d.arc([x0 * k, y0 * k, x1 * k, y1 * k], ini, fim, fill=_c(cor),
                   width=max(1, int(w * k)))

    def desfocar(self, raio: float) -> None:
        """Desfoque de `raio` pixels do MUNDO."""
        self.img = self.img.filter(ImageFilter.GaussianBlur(raio * self.k))

    def final(self) -> Image.Image:
        w, h = self.img.size
        if self.escala == 1:            # o caminho de sempre, byte a byte
            return self.img.resize((w // S, h // S), Image.LANCZOS)
        return self.img.resize((w * self.escala // self.k,
                                h * self.escala // self.k), Image.LANCZOS)


def sombra(largura: float, altura: float, alfa: int = 70,
           raio: float = 2.0, escala: int = 1) -> Image.Image:
    """Uma sombra oval desfocada, ja no tamanho final."""
    margem = raio * 2
    p = Pincel(largura + margem * 2, altura + margem * 2, escala)
    p.elipse(margem, margem, margem + largura, margem + altura,
             (30, 36, 20), None)
    p.desfocar(raio)
    img = p.final()
    fator = alfa / 255
    img.putalpha(img.getchannel("A").point(lambda a: int(a * fator)))
    return img


# =================================================================== chao
def _sobre_rua(x: float, y: float, folga: float = 10) -> bool:
    if any(abs(y - ry) < folga for ry in RUA_Y):
        return True
    if any(abs(x - tx) < folga for tx in TRAVESSAS_X) \
            and RUA_Y[0] <= y <= RUA_Y[1]:
        return True
    return False


def _sobre_lote(x: float, y: float, folga: float = 6,
                nomes=None) -> bool:
    """Dentro de algum lote (a casa inclusive). `nomes` restringe a quais."""
    todos = {**LOTES, "casa": CASA}
    for nome in (todos if nomes is None else nomes):
        lx, ly = todos[nome]
        if (lx * TILE - folga <= x <= (lx + 4) * TILE + folga
                and ly * TILE - folga <= y <= (ly + 3) * TILE + 12):
            return True
    return False


def _perto_de(x, y, centro, raio) -> bool:
    return math.hypot(x - centro[0], y - centro[1]) < raio


def portas() -> dict:
    """{nome: (x_da_porta, y_da_calcada)} para predios e casa."""
    saida = {}
    for nome, (lx, ly) in list(LOTES.items()) + [("casa", CASA)]:
        saida[nome] = (int((lx + 2) * TILE), int((ly + 3) * TILE))
    return saida


GRAMA_TOPO, GRAMA_BASE = "#a4d77e", "#7cc265"


def desenhar_chao(escala: int = 1) -> Image.Image:
    rnd = random.Random(2917)
    p = Pincel(LARGURA, ALTURA, escala)
    k = p.k
    # grama em degrade (de cima para baixo)
    topo, base = rgb(GRAMA_TOPO), rgb(GRAMA_BASE)
    for y in range(ALTURA * k):
        p.d.line([(0, y), (LARGURA * k, y)],
                 fill=mistura(topo, base, y / (ALTURA * k)) + (255,))
    # manchas suaves de luz e sombra, numa camada translucida propria
    for claro in (True, False):
        camada = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        cor = (196, 236, 150) if claro else (92, 166, 80)
        for _ in range(45):
            x, y = rnd.uniform(0, LARGURA), rnd.uniform(0, ALTURA)
            r = rnd.uniform(10, 26)
            d.ellipse([(x - r) * k, (y - r * 0.6) * k, (x + r) * k,
                       (y + r * 0.6) * k], fill=cor + (255,))
        camada = camada.filter(ImageFilter.GaussianBlur(4 * k))
        camada.putalpha(camada.getchannel("A").point(lambda a: a * 45 // 255))
        p.img.alpha_composite(camada)
    # tufos de grama
    for _ in range(170):
        x, y = rnd.uniform(4, LARGURA - 4), rnd.uniform(4, ALTURA - 4)
        if _sobre_rua(x, y, 12):
            continue
        tom = rnd.choice(["#6fb35a", "#5fa14f", "#8fcf72"])
        p.linha([(x - 1.5, y), (x - 2.5, y - 3)], tom, 0.8)
        p.linha([(x, y), (x, y - 4)], tom, 0.8)
        p.linha([(x + 1.5, y), (x + 2.5, y - 3)], tom, 0.8)

    # lago (entre a arena e a travessa)
    cx, cy = LAGO
    p.elipse(cx - 34, cy - 23, cx + 34, cy + 23, "#cfe7c0")
    p.elipse(cx - 31, cy - 20, cx + 31, cy + 20, "#6cc0e8")
    p.elipse(cx - 26, cy - 16, cx + 26, cy + 17, "#58b0e0")
    p.arco(cx - 20, cy - 12, cx + 6, cy + 2, 200, 280, "#e8f7ff", 1.4)
    p.arco(cx - 4, cy - 6, cx + 20, cy + 12, 200, 250, "#d6f0ff", 1.0)
    for dx, dy in ((14, 7), (-18, 8)):          # vitorias-regias
        p.elipse(cx + dx - 5, cy + dy - 3, cx + dx + 5, cy + dy + 3,
                 "#6fbf5e", "#4f9a44", 0.6)
    p.circulo(cx + 16, cy + 6, 1.4, "#ffc1d9")

    # ruas: borda mais escura, miolo claro, pedrinhas. Todas as bordas
    # primeiro e so depois os miolos: um por um, a borda da calcada que
    # chega na rua riscava um "U" por cima do miolo dela (28/09/2026).
    ruas = []

    def rua(pontos, largura):
        ruas.append((pontos, largura))

    for ry in RUA_Y:
        rua([(-6, ry), (LARGURA + 6, ry)], 14)
    for tx in TRAVESSAS_X:
        rua([(tx, RUA_Y[0]), (tx, RUA_Y[1])], 12)
    for nome, (px, py) in portas().items():
        destino = RUA_Y[0] if py < 120 else RUA_Y[1]
        rua([(px, py - 2), (px, destino)], 9)
    for x, y in (BANCO, FONTE, CANTEIRO):
        rua([(x, RUA_Y[0]), (x, y - 6)], 8)
    rua([(LAGO[0], LAGO[1] + 24), (LAGO[0], RUA_Y[1])], 8)
    for pontos, largura in ruas:
        p.linha(pontos, "#d9b98a", largura + 3)
    for pontos, largura in ruas:
        p.linha(pontos, "#f0dab0", largura)
    for _ in range(140):
        x, y = rnd.uniform(0, LARGURA), rnd.uniform(0, ALTURA)
        if _sobre_rua(x, y, 5):
            p.circulo(x, y, rnd.uniform(0.5, 1.1),
                      rnd.choice(["#e2c596", "#caa878", "#f7e8c8"]))

    # flores (LOTES_TARDIOS: ver o comentario la em cima)
    antigos = [n for n in list(LOTES) + ["casa"] if n not in LOTES_TARDIOS]
    for _ in range(120):
        x, y = rnd.uniform(6, LARGURA - 6), rnd.uniform(6, ALTURA - 6)
        if _sobre_rua(x, y, 11) or _sobre_lote(x, y, nomes=antigos) \
                or _perto_de(x, y, LAGO, 40) or _perto_de(x, y, FONTE, 26):
            continue
        cor = rnd.choice(["#ff9fb8", "#ffd56b", "#ffffff", "#c9a7ff",
                          "#ff8a7a"])
        if _sobre_lote(x, y, nomes=LOTES_TARDIOS):
            continue                       # sorteou igual; so nao nasce
        for k in range(5):
            a = k * 2 * math.pi / 5
            p.circulo(x + math.cos(a) * 1.5, y + math.sin(a) * 1.5, 1.1, cor)
        p.circulo(x, y, 0.8, "#ffb43c")
    return p.final()


def desenhar_arvore(tom: str = "#5fb45a", escala: int = 1) -> Image.Image:
    p = Pincel(36, 44, escala)
    p.ret(15.5, 24, 20.5, 40, 2, "#a0714a", "#83593a", 0.6)
    for cx, cy, r, t in ((12, 17, 10, 0.0), (24, 16, 10, 0.05),
                         (18, 10, 11, 0.12)):
        p.circulo(cx, cy, r, mistura(tom, "#2f7d3a", 0.25 - t),
                  escurecer(tom, 0.35), 0.8)
    p.circulo(15, 8, 4.5, clarear(tom, 0.35))
    p.circulo(26, 13, 2.2, clarear(tom, 0.25))
    for x, y in ((9, 18), (27, 20), (19, 14)):       # frutinhas
        p.circulo(x, y, 1.2, "#ff7b6b")
    return p.final()


def desenhar_banco(escala: int = 1) -> Image.Image:
    p = Pincel(26, 16, escala)
    p.ret(2, 3, 24, 7, 1.5, "#c9905d", "#9c6a41", 0.6)
    p.ret(2, 8, 24, 11, 1.5, "#d9a06a", "#9c6a41", 0.6)
    for x in (4, 20):
        p.ret(x, 10, x + 2, 15, 0.8, "#7a5234")
    return p.final()


def desenhar_fonte(quadro: int = 0, escala: int = 1) -> Image.Image:
    p = Pincel(40, 30, escala)
    p.elipse(2, 12, 38, 28, "#c9c2d6", "#9a91ad", 0.8)
    p.elipse(5, 14, 35, 25, "#7fcdf0")
    p.ret(17, 6, 23, 18, 2, "#d8d2e3", "#9a91ad", 0.6)
    p.elipse(12, 4, 28, 10, "#d8d2e3", "#9a91ad", 0.6)
    for i, dx in enumerate((-5, 0, 5)):
        altura = 2 + ((i + quadro) % 3)
        p.linha([(20, 5), (20 + dx, 5 - altura), (20 + dx * 1.6, 9)],
                "#bfe9ff", 0.9)
    p.arco(9, 16, 22, 23, 200, 300, "#ffffff", 0.8)
    return p.final()


def desenhar_canteiro(escala: int = 1) -> Image.Image:
    p = Pincel(34, 18, escala)
    p.ret(1, 7, 33, 17, 4, "#a8744c", "#865634", 0.7)
    p.ret(3, 8, 31, 12, 3, "#7a5235")
    rnd = random.Random(4)
    for i in range(7):
        x = 5 + i * 4
        p.linha([(x, 11), (x, 6)], "#4f9a44", 0.7)
        cor = ["#ff8fb1", "#ffd56b", "#b69cff", "#ff7b6b"][i % 4]
        for k in range(5):
            a = k * 2 * math.pi / 5 + rnd.random()
            p.circulo(x + math.cos(a) * 1.6, 5 + math.sin(a) * 1.6, 1.2, cor)
        p.circulo(x, 5, 0.8, "#fff1a8")
    return p.final()


# ================================================================ emblemas
def _emblema(p: Pincel, nome: str, cx: float, cy: float, r: float) -> None:
    """O desenho que diz de quem e o predio. Inspirado, nunca copiado."""
    if nome == "deepseek":                           # baleia
        p.elipse(cx - r * .85, cy - r * .35, cx + r * .45, cy + r * .5,
                 "#4d6bfe")
        p.poli([(cx + r * .3, cy), (cx + r * .95, cy - r * .5),
                (cx + r * .8, cy + r * .1), (cx + r * .95, cy + r * .45)],
               "#4d6bfe")
        p.circulo(cx - r * .45, cy - r * .02, r * .1, "#ffffff")
        for dx in (-.25, 0, .25):
            p.linha([(cx - r * .2, cy - r * .45),
                     (cx - r * .2 + dx * r, cy - r * .85)], "#8fb4ff", r * .1)
    elif nome == "chatgpt":                          # no de tres voltas
        for k in range(3):
            a = math.radians(k * 60)
            pts = []
            for i in range(40):
                t = 2 * math.pi * i / 40
                x, y = r * .72 * math.cos(t), r * .3 * math.sin(t)
                pts.append((cx + x * math.cos(a) - y * math.sin(a),
                            cy + x * math.sin(a) + y * math.cos(a)))
            p.linha(pts + [pts[0]], "#149c73", r * .16)
    elif nome == "gemini":                           # estrela de 4 pontas
        pts = []
        for i in range(16):
            a = math.radians(i * 22.5 - 90)
            raio = r * (.95 if i % 4 == 0 else .38 if i % 2 else .26)
            pts.append((cx + math.cos(a) * raio, cy + math.sin(a) * raio))
        p.poli(pts, "#5b86f0")
        p.circulo(cx, cy, r * .16, "#cfe0ff")
    elif nome == "picasso":                          # paleta e pincel
        p.elipse(cx - r * .9, cy - r * .7, cx + r * .8, cy + r * .7,
                 "#f5deb0", "#c9a36b", .6)
        p.circulo(cx + r * .35, cy + r * .25, r * .17, "#ffffff")
        for (dx, dy), cor in zip(((-.5, -.2), (-.15, -.4), (.2, -.35),
                                  (-.45, .2)),
                                 ("#ff5d7a", "#ffcf3f", "#4db3ff", "#6cd36c")):
            p.circulo(cx + dx * r, cy + dy * r, r * .15, cor)
        p.linha([(cx - r * .1, cy + r * .75), (cx + r * .7, cy - r * .7)],
                "#8a5a3c", r * .12)
        p.circulo(cx + r * .72, cy - r * .72, r * .13, "#c678e6")
    elif nome == "digen":                            # camera de cinema
        p.ret(cx - r * .8, cy - r * .2, cx + r * .35, cy + r * .6, r * .15,
              "#e35b8f")
        p.circulo(cx - r * .45, cy - r * .45, r * .28, "#e35b8f")
        p.circulo(cx + r * .05, cy - r * .45, r * .28, "#e35b8f")
        p.circulo(cx - r * .45, cy - r * .45, r * .1, "#ffffff")
        p.circulo(cx + r * .05, cy - r * .45, r * .1, "#ffffff")
        p.poli([(cx + r * .35, cy + r * .2), (cx + r * .9, cy - r * .05),
                (cx + r * .9, cy + r * .55)], "#e35b8f")
    elif nome == "estudio":                          # claquete
        p.ret(cx - r * .8, cy - r * .15, cx + r * .8, cy + r * .7, r * .1,
              "#3a3340")
        p.poli([(cx - r * .85, cy - r * .2), (cx + r * .75, cy - r * .55),
                (cx + r * .8, cy - r * .3), (cx - r * .8, cy + r * .02)],
               "#3a3340")
        for i in range(4):
            x = cx - r * .6 + i * r * .38
            p.poli([(x, cy - r * .22 - i * r * .08),
                    (x + r * .18, cy - r * .26 - i * r * .08),
                    (x + r * .22, cy - r * .05 - i * r * .08),
                    (x + r * .04, cy - r * .01 - i * r * .08)], "#ffffff")
        p.ret(cx - r * .55, cy + r * .15, cx + r * .55, cy + r * .5, r * .08,
              "#ffcf6b")
    elif nome == "arena":                            # espadas e escudo
        for sinal in (1, -1):
            p.linha([(cx - r * .7 * sinal, cy - r * .7),
                     (cx + r * .55 * sinal, cy + r * .55)], "#aeb8c6",
                    r * .14)
            p.linha([(cx + r * .3 * sinal, cy + r * .62),
                     (cx + r * .62 * sinal, cy + r * .3)], "#e0a93b",
                    r * .14)
        p.poli([(cx - r * .32, cy - r * .3), (cx + r * .32, cy - r * .3),
                (cx + r * .3, cy + r * .1), (cx, cy + r * .42),
                (cx - r * .3, cy + r * .1)], "#e2574c", "#9e3028", .5)
    elif nome == "youtube":                          # botao de play
        p.ret(cx - r * .9, cy - r * .62, cx + r * .9, cy + r * .62, r * .32,
              "#ff2d2d")
        p.poli([(cx - r * .25, cy - r * .32), (cx - r * .25, cy + r * .32),
                (cx + r * .35, cy)], "#ffffff")
    elif nome == "tiktok":                           # nota com eco
        for dx, dy, cor in ((-.09, -.06, "#25f4ee"), (.09, .06, "#fe2c55"),
                            (0, 0, "#1d1b24")):
            x, y = cx + dx * r, cy + dy * r
            p.ret(x + r * .05, y - r * .75, x + r * .25, y + r * .4, r * .08,
                  cor)
            p.circulo(x - r * .12, y + r * .4, r * .3, cor)
            p.linha([(x + r * .15, y - r * .7), (x + r * .6, y - r * .35)],
                    cor, r * .2)
    elif nome == "bot":                              # aviao de papel
        p.poli([(cx - r * .85, cy - r * .05), (cx + r * .85, cy - r * .6),
                (cx + r * .2, cy + r * .75)], "#7a6cf0")
        p.poli([(cx - r * .05, cy + r * .15), (cx + r * .85, cy - r * .6),
                (cx + r * .05, cy + r * .6)], "#b9b0ff")
    elif nome == "grok":                             # foguetinho
        # a chama
        p.poli([(cx - r * .95, cy + r * .9), (cx - r * .55, cy + r * .15),
                (cx - r * .15, cy + r * .55)], "#ffb43c")
        p.poli([(cx - r * .8, cy + r * .75), (cx - r * .5, cy + r * .22),
                (cx - r * .22, cy + r * .5)], "#ff6b6b")
        # as aletas
        p.poli([(cx - r * .5, cy + r * .02), (cx - r * .82, cy + r * .1),
                (cx - r * .6, cy + r * .42)], "#3a4052")
        p.poli([(cx - r * .02, cy + r * .5), (cx - r * .1, cy + r * .82),
                (cx - r * .42, cy + r * .6)], "#3a4052")
        # o corpo, inclinado, com a escotilha
        p.poli([(cx + r * .92, cy - r * .92), (cx + r * .3, cy - r * .88),
                (cx - r * .52, cy + r * .06), (cx - r * .06, cy + r * .52),
                (cx + r * .88, cy - r * .3)], "#eef1f8", "#3a4052", r * .12)
        p.circulo(cx + r * .3, cy - r * .3, r * .2, "#5b86f0", "#3a4052",
                  r * .08)
    elif nome == "casa":                             # coracao
        p.circulo(cx - r * .3, cy - r * .15, r * .38, "#ff6b81")
        p.circulo(cx + r * .3, cy - r * .15, r * .38, "#ff6b81")
        p.poli([(cx - r * .66, cy - r * .02), (cx + r * .66, cy - r * .02),
                (cx, cy + r * .72)], "#ff6b81")
    else:                                            # desconhecido
        p.circulo(cx, cy, r * .5, COR_RESERVA)


def desenhar_predio(nome: str, noite: bool = False,
                    escala: int = 1) -> Image.Image:
    """72x64. O lote de 64x48 fica em (4, 16) desta imagem."""
    cor = CORES.get(nome, COR_RESERVA)
    p = Pincel(PREDIO_W, PREDIO_H, escala)
    parede = "#fff3e2" if nome != "tiktok" else "#f1ecf7"
    p.ret(10, 28, 62, 62, 5, parede, "#dcc3a6", 1.0)
    p.ret(10, 52, 62, 62, 5, mistura(parede, "#e8d2b6", .6))
    # telhado
    if nome == "arena":
        p.elipse(6, 8, 66, 50, cor, escurecer(cor), 1.0)
        p.ret(4, 26, 68, 33, 3, escurecer(cor, .1), escurecer(cor, .35), .8)
        p.linha([(36, 9), (36, 1)], "#8a5a3c", 1.0)
        p.poli([(36, 1), (46, 3.5), (36, 6)], "#ffcf3f")
    else:
        p.poli([(4, 31), (36, 7), (68, 31)], cor, escurecer(cor), 1.2)
        p.poli([(10, 29), (36, 10), (40, 12.5), (16, 29)], clarear(cor, .22))
        p.ret(3, 27, 69, 33, 3, escurecer(cor, .08), escurecer(cor, .35), .8)
    if nome == "bot":                                   # antena
        p.linha([(56, 20), (60, 2)], "#9aa3b5", 1.2)
        p.circulo(60, 2.5, 2.2, "#ff6b6b")
    elif nome not in ("arena", "casa"):                 # chamine
        p.ret(50, 10, 56, 22, 1.5, "#b9a7a0", "#8e7c76", .6)
    # portas
    p.ret(31, 45, 41, 62, 4, "#a8744c", "#7d5234", .8)
    p.circulo(39, 54, .9, "#ffd56b")
    if nome == "casa":
        p.ret(20, 56, 52, 62, 2, "#ff9fb8")
        for x in range(22, 52, 5):
            p.circulo(x, 57, 1.6, "#ff6b81" if x % 2 else "#ffd56b")
    # placa com o emblema
    p.circulo(36, 22, 9.5, "#ffffff", escurecer(cor, .2), 1.2)
    _emblema(p, nome, 36, 22, 7.5)
    corpo = p.final()
    if noite:
        # A casa escurece, a placa e as janelas nao: e isso que faz a noite
        # parecer noite sem esconder de quem e o predio.
        corpo = _escurecer_imagem(corpo, .38)
        placa = Pincel(PREDIO_W, PREDIO_H, escala)
        placa.circulo(36, 22, 9.5, "#fff6e0", escurecer(cor, .2), 1.2)
        _emblema(placa, nome, 36, 22, 7.5)
        corpo.alpha_composite(placa.final())
    janelas = Pincel(PREDIO_W, PREDIO_H, escala)
    vidro = "#ffd98a" if noite else "#c7e9fb"
    for x in (15, 47):
        janelas.ret(x, 38, x + 10, 48, 2.5, vidro, "#c7a57f", .8)
        janelas.linha([(x + 5, 38.5), (x + 5, 47.5)], "#c7a57f", .5)
        if not noite:
            janelas.linha([(x + 2, 40), (x + 4, 40)], "#ffffff", .8)
    img = Image.new("RGBA", corpo.size, (0, 0, 0, 0))
    if noite:
        brilho = Pincel(PREDIO_W, PREDIO_H, escala)
        for x in (20, 52):
            brilho.circulo(x, 43, 11, (255, 200, 110))
        brilho.desfocar(6)
        luz = brilho.final()
        luz.putalpha(luz.getchannel("A").point(lambda a: int(a * .6)))
        img.alpha_composite(luz)
    img.alpha_composite(corpo)
    img.alpha_composite(janelas.final())
    return img


# ============================================================ personagens
ACESSORIOS = {
    "deepseek": "gorro", "chatgpt": "fones", "gemini": "estrela",
    "picasso": "boina", "digen": "bone", "estudio": "cachecol",
    "arena": "faixa", "youtube": "bone", "tiktok": "capuz",
    "bot": "antena", "grok": "bone",
}
POSES = ("parado", "passo1", "passo2", "sentado", "acenar", "feliz",
         "triste", "trabalhar")


def desenhar_personagem(nome: str, pose: str = "parado",
                        olhos: str = "abertos",
                        direcao: str = "dir", escala: int = 1) -> Image.Image:
    """26x32, pes em (13, 31). Cabeca grande, olhinhos, bochecha."""
    cor = CORES.get(nome, COR_RESERVA)
    indice = ORDEM_DAS_PELES.index(nome) if nome in ORDEM_DAS_PELES else 0
    pele = PELES[indice % len(PELES)]
    corpo = clarear(cor, .15)
    contorno = escurecer(cor, .35)
    p = Pincel(PERSONAGEM_W, PERSONAGEM_H, escala)
    k = p.k
    baixo = 3 if pose == "sentado" else 0
    # A sombra vem NO sprite: um item de Canvas a menos por habitante, e o
    # redesenho do Tk era o que pesava na CPU.
    # (translucida: o que vem por cima e opaco e substitui o pixel.)
    p.d.ellipse([5 * k, 28.5 * k, 21 * k, 31.8 * k], fill=(50, 80, 40, 70))

    # pernas
    perna = "#5a4a5e"
    if pose == "sentado":
        p.ret(8, 26, 13, 29, 1.5, perna)
        p.ret(14, 26, 19, 29, 1.5, perna)
    else:
        passo = {"passo1": (-1.5, 1.2), "passo2": (1.5, -1.2)}.get(pose,
                                                                    (0, 0))
        p.ret(8.5 + passo[0], 24 - max(0, passo[1]), 12 + passo[0], 31, 1.6,
              perna)
        p.ret(14 - passo[0], 24 + min(0, passo[1]), 17.5 - passo[0], 31, 1.6,
              perna)
    # corpo
    p.elipse(6, 15 + baixo, 20, 28 + baixo, corpo, contorno, .8)
    p.elipse(9, 20 + baixo, 17, 27 + baixo, clarear(corpo, .25))
    if ACESSORIOS.get(nome) == "cachecol":
        p.ret(7, 15 + baixo, 19, 18 + baixo, 1.5, "#ff7b6b")
        p.ret(15, 16 + baixo, 17.5, 22 + baixo, 1, "#ff7b6b")
    if ACESSORIOS.get(nome) == "capuz":
        p.ret(7, 17 + baixo, 19, 18.5 + baixo, .7, "#25f4ee")
        p.ret(7, 19 + baixo, 19, 20.5 + baixo, .7, "#fe2c55")
    # bracos
    bracos = {
        "acenar": [(4.5, 19, 7.5, 23), (18, 8, 22, 14)],
        "feliz": [(3, 9, 7, 15), (19, 9, 23, 15)],
        "trabalhar": [(15, 19, 21, 22.5), (13, 20, 19, 23.5)],
        "triste": [(5, 20, 8.5, 25), (17.5, 20, 21, 25)],
    }.get(pose, [(3.5, 18, 7.5, 23), (18.5, 18, 22.5, 23)])
    for x0, y0, x1, y1 in bracos:
        p.elipse(x0, y0 + baixo, x1, y1 + baixo, corpo, contorno, .6)
    # cabeca
    y0 = 1 + baixo
    p.elipse(3, y0, 23, y0 + 17, pele, mistura(pele, "#a86b50", .45), .8)
    olho_y = y0 + 9.5
    ox = 1.2                                           # olha para a direita
    if olhos == "fechados":
        for x in (9.5, 16):
            p.arco(x - 1.5 + ox, olho_y - 1, x + 1.5 + ox, olho_y + 1.5,
                   20, 160, "#3b2a2a", .7)
    elif pose == "feliz":
        for x in (9.5, 16):
            p.arco(x - 1.6 + ox, olho_y - .5, x + 1.6 + ox, olho_y + 2.5,
                   200, 340, "#3b2a2a", .8)
    else:
        for x in (9.5, 16):
            p.elipse(x - 1.2 + ox, olho_y - 1.6, x + 1.2 + ox, olho_y + 1.6,
                     "#3b2a2a")
            p.circulo(x - .4 + ox, olho_y - .7, .45, "#ffffff")
        if pose == "triste":
            for x, s in ((9.5, 1), (16, -1)):
                p.linha([(x - 1.6 + ox, olho_y - 2.6 - s * .5),
                         (x + 1.6 + ox, olho_y - 2.6 + s * .5)],
                        "#6a4a3a", .5)
    for x in (7 + ox, 19 + ox):
        p.elipse(x - 1.8, olho_y + 1.8, x + 1.8, olho_y + 3.4,
                 (255, 150, 160))
    boca_y = olho_y + 3.2
    if pose == "triste":
        p.arco(11.5 + ox, boca_y + .8, 14.5 + ox, boca_y + 3, 200, 340,
               "#7a3b3b", .6)
    else:
        abre = 2.2 if pose in ("feliz", "acenar") else 1.4
        p.arco(11.5 + ox, boca_y - 1, 14.5 + ox, boca_y + abre, 20, 160,
               "#7a3b3b", .6)
    _acessorio(p, ACESSORIOS.get(nome, ""), cor, y0)
    img = p.final()
    if direcao == "esq":
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


def _acessorio(p: Pincel, tipo: str, cor, y0: float) -> None:
    escuro = escurecer(cor, .3)
    if tipo == "gorro":
        p.elipse(3.5, y0 - 1, 22.5, y0 + 9, cor, escuro, .6)
        p.ret(3, y0 + 5, 23, y0 + 8, 1.5, clarear(cor, .3))
        p.circulo(13, y0 - 1.5, 2.2, "#ffffff")
    elif tipo == "fones":
        p.arco(3, y0 - 1, 23, y0 + 16, 190, 350, escuro, 1.2)
        p.ret(1.5, y0 + 7, 5, y0 + 12, 1.5, cor)
        p.ret(21, y0 + 7, 24.5, y0 + 12, 1.5, cor)
    elif tipo == "estrela":
        pts = []
        for i in range(10):
            a = math.radians(i * 36 - 90)
            r = 3 if i % 2 == 0 else 1.3
            pts.append((18 + math.cos(a) * r, y0 + 3 + math.sin(a) * r))
        p.poli(pts, "#ffd23f", "#e0a800", .4)
    elif tipo == "boina":
        p.elipse(4, y0 - 1.5, 21, y0 + 6, cor, escuro, .6)
        p.linha([(12.5, y0 - 1.5), (13.5, y0 - 3.5)], escuro, .8)
    elif tipo == "bone":
        p.elipse(4.5, y0 - .5, 21.5, y0 + 8, cor, escuro, .6)
        p.ret(15, y0 + 5, 25, y0 + 8, 1.5, escuro)
    elif tipo == "faixa":
        p.ret(3.2, y0 + 3.5, 22.8, y0 + 6.5, 1.5, cor)
        p.linha([(4, y0 + 5), (1, y0 + 8)], cor, 1.2)
    elif tipo == "capuz":
        p.arco(2, y0 - 1.5, 24, y0 + 18, 150, 390, cor, 1.6)
    elif tipo == "antena":
        p.linha([(13, y0 + 1), (13, y0 - 3.5)], "#9aa3b5", .8)
        p.circulo(13, y0 - 4, 1.6, cor)


# ============================================================ bichinhos
def desenhar_pato(quadro: int = 0, escala: int = 1) -> Image.Image:
    p = Pincel(14, 11, escala)
    p.elipse(1, 4, 12, 10, "#ffffff", "#c8d3dd", .5)
    p.circulo(10, 3.8 + (quadro % 2) * .3, 2.6, "#ffffff", "#c8d3dd", .5)
    p.poli([(12, 3.8), (14, 4.3), (12, 5)], "#ffab2e")
    p.circulo(10.6, 3.2, .45, "#2a2a2a")
    p.arco(3, 5, 8, 9, 200, 330, "#dfe6ec", .6)
    return p.final()


def desenhar_gato(quadro: int = 0) -> Image.Image:
    p = Pincel(22, 14)
    passo = 1 if quadro % 2 else -1
    for x in (5, 8, 14, 17):
        p.ret(x + (passo if x in (5, 14) else -passo) * .6, 9, x + 1.8, 13,
              .8, "#e89a4e")
    p.elipse(3, 5, 17, 11, "#f4ae62", "#c9793a", .5)
    p.linha([(3.5, 7), (1, 3 + passo * .6)], "#f4ae62", 1.4)
    p.circulo(17, 5.5, 3.6, "#f4ae62", "#c9793a", .5)
    p.poli([(14.5, 3.2), (15.5, 0), (17, 2.6)], "#f4ae62")
    p.poli([(17.5, 2.6), (19.5, 0), (20, 3.4)], "#f4ae62")
    p.circulo(16.4, 5.2, .45, "#2a2a2a")
    p.circulo(18.6, 5.2, .45, "#2a2a2a")
    return p.final()


def desenhar_passaro(quadro: int = 0) -> Image.Image:
    p = Pincel(14, 10)
    p.elipse(3, 4, 11, 9, "#6fb7ff", "#3f86d0", .5)
    p.circulo(10.5, 4.6, 2.2, "#6fb7ff")
    p.poli([(12.3, 4.4), (14, 5), (12.3, 5.6)], "#ffab2e")
    p.circulo(11, 4.2, .4, "#1e1e1e")
    if quadro % 2:
        p.poli([(5, 5), (8, 0), (9, 5)], "#9fd0ff")
    else:
        p.poli([(5, 6), (8, 10), (9, 6)], "#9fd0ff")
    return p.final()


def desenhar_vagalume() -> Image.Image:
    p = Pincel(10, 10)
    p.circulo(5, 5, 4, (255, 240, 140))
    p.desfocar(1.5)
    p.circulo(5, 5, 1.2, (255, 255, 210))
    return p.final()


# ======================================================= decoracoes (colecao)
DECORACOES = ("bandeirolas", "lanterna", "balao", "gnomo", "estatua",
              "arco")
LUGAR_DAS_DECORACOES = {
    "bandeirolas": (344, 100), "lanterna": (262, 128), "balao": (430, 120),
    "gnomo": (88, 132), "estatua": (600, 126), "arco": (344, 232),
}


def desenhar_decoracao(nome: str) -> Image.Image:
    if nome == "bandeirolas":
        p = Pincel(110, 16)
        p.arco(2, -12, 108, 10, 20, 160, "#8a6a4a", .6)
        cores = ["#ff6b81", "#ffd56b", "#6fd6a8", "#6fb7ff", "#c9a7ff"]
        for i in range(11):
            x = 6 + i * 9.4
            y = 3 + math.sin(math.pi * (i + .5) / 11) * 5
            p.poli([(x - 3, y), (x + 3, y), (x, y + 6)], cores[i % 5])
        return p.final()
    if nome == "lanterna":
        p = Pincel(12, 28)
        p.linha([(6, 27), (6, 8)], "#6a5a6e", 1.2)
        p.ret(2, 1, 10, 10, 2.5, "#ffcf6b", "#b98a3a", .7)
        p.circulo(6, 5.5, 2, "#fff4c8")
        return p.final()
    if nome == "balao":
        p = Pincel(14, 26)
        p.linha([(7, 25), (7, 12)], "#8a8a8a", .5)
        p.elipse(1, 0, 13, 13, "#ff7aa8", "#d94c7f", .6)
        p.circulo(4.5, 3.5, 1.6, "#ffd0e0")
        return p.final()
    if nome == "gnomo":
        p = Pincel(12, 18)
        p.poli([(1.5, 7), (6, 0), (10.5, 7)], "#e2574c")
        p.circulo(6, 9, 3, "#ffe0c7")
        p.poli([(3, 10), (9, 10), (6, 15)], "#ffffff")
        p.ret(2.5, 12, 9.5, 17.5, 2, "#4d6bfe")
        return p.final()
    if nome == "estatua":
        p = Pincel(16, 22)
        p.ret(2, 15, 14, 21, 1.5, "#c9c2d6", "#9a91ad", .5)
        pts = []
        for i in range(10):
            a = math.radians(i * 36 - 90)
            r = 6 if i % 2 == 0 else 2.6
            pts.append((8 + math.cos(a) * r, 8 + math.sin(a) * r))
        p.poli(pts, "#ffd23f", "#d9a400", .6)
        return p.final()
    if nome == "arco":
        p = Pincel(40, 16)
        for i, cor in enumerate(["#ff8a8a", "#ffc46b", "#fff07a",
                                 "#8fe08a", "#8ac6ff"]):
            p.arco(2 + i * 1.6, 2 + i * 1.6, 38 - i * 1.6, 30 - i * 1.6,
                   180, 360, cor, 1.5)
        return p.final()
    p = Pincel(10, 10)
    p.circulo(5, 5, 4, COR_RESERVA)
    return p.final()


# ================================================================== emotes
@lru_cache(maxsize=64)
def emote(simbolo: str, tamanho: int = 22) -> Image.Image:
    """Um balaozinho branco com um emoji colorido dentro."""
    p = Pincel(tamanho, tamanho + 4)
    p.circulo(tamanho / 2, tamanho / 2, tamanho / 2 - .8, "#ffffff",
              "#d8cfc4", .8)
    p.poli([(tamanho * .38, tamanho - 2), (tamanho * .5, tamanho + 3.5),
            (tamanho * .62, tamanho - 2)], "#ffffff")
    img = p.final()
    try:
        fonte = ImageFont.truetype("seguiemj.ttf", 96)
        glifo = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(glifo).text((64, 64), simbolo, font=fonte,
                                   embedded_color=True, anchor="mm")
        caixa = glifo.getbbox()
        if caixa:
            glifo = glifo.crop(caixa)
        lado = int(tamanho * .64)
        glifo.thumbnail((lado, lado), Image.LANCZOS)
        img.alpha_composite(glifo, ((tamanho - glifo.width) // 2,
                                    (tamanho - glifo.height) // 2))
    except OSError:
        d = ImageDraw.Draw(img)
        d.text((tamanho / 2, tamanho / 2), simbolo[:1], fill=(80, 60, 50),
               anchor="mm")
    return img


# ==================================================================== mundo
NOITE = (24, 30, 72)
NOITE_CHAO = .52


def noturno(img: Image.Image, t: float = NOITE_CHAO) -> Image.Image:
    """O chao (opaco) de noite: o mesmo azul por cima de tudo."""
    return Image.blend(img, Image.new("RGBA", img.size, NOITE + (255,)), t)


def compor_mundo(noite: bool = False, escala: int = 1) -> Image.Image:
    """O cenario estatico inteiro: chao, arvores, lago, predios.

    Com `escala` > 1 a imagem sai `escala` vezes maior, desenhada nesse
    tamanho; as posicoes continuam em pixels do mundo.
    """
    e = max(1, int(escala))
    mundo = desenhar_chao(e)
    if noite:
        mundo = noturno(mundo)
    fixos = []
    for tx, ty, tom in ARVORES:
        fixos.append((ty * TILE + 44, desenhar_arvore(tom, e),
                      (tx * TILE - 2, ty * TILE - 6), "arvore"))
    fixos.append((BANCO[1] + 8, desenhar_banco(e),
                  (BANCO[0] - 13, BANCO[1] - 8), "enfeite"))
    fixos.append((FONTE[1] + 14, desenhar_fonte(0, e),
                  (FONTE[0] - 20, FONTE[1] - 16), "enfeite"))
    fixos.append((CANTEIRO[1] + 9, desenhar_canteiro(e),
                  (CANTEIRO[0] - 17, CANTEIRO[1] - 9), "enfeite"))
    for nome, (lx, ly) in list(LOTES.items()) + [("casa", CASA)]:
        fixos.append(((ly + 3) * TILE, desenhar_predio(nome, noite, e),
                      (lx * TILE - 4, ly * TILE - 16), "predio"))
    for _base, img, (x, y), tipo in sorted(fixos, key=lambda f: f[0]):
        assentar(mundo, img, x, y, tipo, noite, e)
    return mundo


def assentar(fundo: Image.Image, img: Image.Image, x: float, y: float,
             tipo: str, noite: bool, e: int = 1) -> None:
    """Sombra no chao e o objeto por cima, com a noite de cada tipo.

    `img` ja vem desenhada na escala `e`; `x`, `y` em pixels do mundo.
    """
    w = img.width / e                      # largura em pixels do mundo
    sombra_img = sombra(w * .8, 6, 60, escala=e)
    fundo.alpha_composite(
        sombra_img, (int((x + w * .1 - 4) * e),
                     int((y + img.height / e - 7) * e)))
    if noite and tipo == "arvore":         # arvore de noite: mais escura
        img = _escurecer_imagem(img, .45)
    elif noite and tipo == "enfeite":
        img = _escurecer_imagem(img, .4)
    fundo.alpha_composite(img, (int(x * e), int(y * e)))


def _escurecer_imagem(img: Image.Image, t: float) -> Image.Image:
    alfa = img.getchannel("A")
    escuro = Image.new("RGBA", img.size, NOITE + (255,))
    misturado = Image.blend(img, escuro, t)
    misturado.putalpha(alfa)
    return misturado


__all__ = ["CORES", "DECORACOES", "LUGAR_DAS_DECORACOES", "POSES",
           "Pincel", "assentar", "compor_mundo", "desenhar_decoracao",
           "desenhar_personagem", "desenhar_predio", "emote", "fator",
           "noturno", "portas"]
