# -*- coding: utf-8 -*-
"""Gera o cenario BASE da Vila: folha de sprites procedural + mapa pronto.

A Vila em sprites so existe se houver arte — e o Adrian ainda vai gerar a
dele. Este script fabrica uma folha de pixel art procedural (PIL, de graca)
com tudo que o motor precisa: chao, arvores, os 8 predios, o bot andando e
os efeitos. Sai bonitinho o suficiente para a Vila ja rodar em modo sprite
HOJE, e serve de gabarito: a arte final dele so precisa substituir a folha
(ou entrar como folha nova na Oficina) mantendo os papeis.

    python -m vila.gerar_base            # so cria se nao existir config
    python -m vila.gerar_base --forcar   # sobrescreve folha, papeis e mapa

Determinismo proposital (seed fixa): rodar duas vezes da o MESMO mundo.
"""
from __future__ import annotations

import random
import sys

from PIL import Image, ImageDraw

from . import motor

TILE = 16
COLS = 16          # celulas por linha da folha
LINHAS = 11
SEED = 7

CORES_FABRICA = {
    "chatgpt": "#10a37f", "gemini": "#4e8cf7", "picasso": "#c05be3",
    "digen": "#e35b8f", "estudio": "#e0a63b", "arena": "#d9483b",
    "publicacao": "#3ba55d", "casa": "#b5502e",
}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _sombra(cor, fator):
    return tuple(max(0, min(255, int(c * fator))) for c in cor)


class Folha:
    def __init__(self):
        self.img = Image.new("RGBA", (COLS * TILE, LINHAS * TILE), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.rnd = random.Random(SEED)

    def base(self, idx, cor):
        x, y = (idx % COLS) * TILE, (idx // COLS) * TILE
        self.d.rectangle([x, y, x + TILE - 1, y + TILE - 1], fill=cor + (255,))
        return x, y

    def pontilhar(self, x, y, cores, n):
        for _ in range(n):
            px = x + self.rnd.randrange(TILE)
            py = y + self.rnd.randrange(TILE)
            self.d.point((px, py), fill=self.rnd.choice(cores) + (255,))


def _chao(f: Folha):
    grama = _rgb("#3e7a3a")
    claro, escuro = _sombra(grama, 1.25), _sombra(grama, 0.8)
    for i in range(4):                                   # 0-3 grama
        x, y = f.base(i, grama)
        f.pontilhar(x, y, [claro, escuro], 14 + i * 3)
    for i, flor in enumerate(("#e75480", "#f2d14e")):    # 4-5 grama com flor
        x, y = f.base(4 + i, grama)
        f.pontilhar(x, y, [claro, escuro], 12)
        for _ in range(2):
            px = x + 2 + f.rnd.randrange(TILE - 5)
            py = y + 2 + f.rnd.randrange(TILE - 5)
            f.d.point([(px, py - 1), (px - 1, py), (px + 1, py), (px, py + 1)],
                      fill=_rgb(flor) + (255,))
            f.d.point((px, py), fill=(255, 255, 255, 255))
    areia = _rgb("#c9a969")
    for i in range(2):                                   # 6-7 caminho
        x, y = f.base(6 + i, areia)
        f.pontilhar(x, y, [_sombra(areia, 0.82), _sombra(areia, 1.12)], 16)
        for _ in range(3):
            px, py = x + f.rnd.randrange(TILE - 3), y + f.rnd.randrange(TILE - 2)
            f.d.rectangle([px, py, px + 2, py + 1],
                          fill=_sombra(areia, 0.7) + (255,))
    agua = _rgb("#2e5f9e")
    for i in range(2):                                   # 8-9 agua
        x, y = f.base(8 + i, agua)
        f.pontilhar(x, y, [_sombra(agua, 1.3)], 6)
        for j in range(2):
            wy = y + 4 + j * 7 + (i * 2)
            f.d.line([x + 2 + i * 3, wy, x + 7 + i * 3, wy],
                     fill=_sombra(agua, 1.5) + (255,))
    pedra = _rgb("#8a8d90")                              # 10 pedra de chao
    x, y = f.base(10, pedra)
    f.pontilhar(x, y, [_sombra(pedra, 0.8), _sombra(pedra, 1.2)], 18)
    terra = _rgb("#7a5b3a")                              # 11 terra
    x, y = f.base(11, terra)
    f.pontilhar(x, y, [_sombra(terra, 0.85), _sombra(terra, 1.15)], 16)


def _arvore(f: Folha, idx, tom):
    """2x2 tiles: copa redonda com brilho + tronco."""
    x, y = (idx % COLS) * TILE, (idx // COLS) * TILE
    w = h = TILE * 2
    copa = _rgb(tom)
    f.d.rectangle([x + w // 2 - 2, y + h - 9, x + w // 2 + 1, y + h - 1],
                  fill=_rgb("#6b4a2f") + (255,))
    f.d.ellipse([x + 2, y + 1, x + w - 3, y + h - 8], fill=copa + (255,))
    f.d.ellipse([x + 5, y + 3, x + w - 12, y + h - 16],
                fill=_sombra(copa, 1.25) + (255,))
    for _ in range(6):
        px = x + 4 + f.rnd.randrange(w - 9)
        py = y + 3 + f.rnd.randrange(h - 13)
        f.d.point((px, py), fill=_sombra(copa, 0.75) + (255,))


def _decor(f: Folha):
    _arvore(f, 16, "#2f6b33")        # 16 arvore (2x2, ocupa 16-17/32-33)
    _arvore(f, 18, "#4c7a2e")        # 18 arvore clara
    x, y = (20 % COLS) * TILE, (20 // COLS) * TILE      # 20 pedra decorativa
    f.d.ellipse([x + 2, y + 6, x + 13, y + 14], fill=_rgb("#9aa0a6") + (255,))
    f.d.ellipse([x + 4, y + 7, x + 9, y + 11], fill=_rgb("#c4c9ce") + (255,))
    x, y = (21 % COLS) * TILE, (21 // COLS) * TILE      # 21 cerca
    cor = _rgb("#a9825a")
    for px in (x + 2, x + 12):
        f.d.rectangle([px, y + 4, px + 1, y + 14], fill=cor + (255,))
    f.d.rectangle([x, y + 6, x + 15, y + 7], fill=_sombra(cor, 1.15) + (255,))
    f.d.rectangle([x, y + 11, x + 15, y + 12], fill=_sombra(cor, 0.85) + (255,))
    x, y = (22 % COLS) * TILE, (22 // COLS) * TILE      # 22 arbusto
    f.d.ellipse([x + 1, y + 6, x + 14, y + 15], fill=_rgb("#356e2c") + (255,))
    f.d.ellipse([x + 3, y + 7, x + 9, y + 12], fill=_rgb("#4c8a3a") + (255,))


def _predio(f: Folha, idx, cor_tema):
    """4x3 tiles (64x48): telhado colorido, parede clara, porta e janelas."""
    x, y = (idx % COLS) * TILE, (idx // COLS) * TILE
    w, h = TILE * 4, TILE * 3
    tema = _rgb(cor_tema)
    parede = _rgb("#e6d7b4")
    # parede com tabuas
    f.d.rectangle([x + 4, y + 16, x + w - 5, y + h - 1], fill=parede + (255,))
    for ty in range(y + 20, y + h - 1, 6):
        f.d.line([x + 4, ty, x + w - 5, ty], fill=_sombra(parede, 0.88) + (255,))
    # telhado
    f.d.polygon([x, y + 18, x + w - 1, y + 18, x + w - 9, y + 2, x + 8, y + 2],
                fill=tema + (255,))
    f.d.polygon([x, y + 18, x + 8, y + 2, x + 11, y + 2, x + 3, y + 18],
                fill=_sombra(tema, 1.3) + (255,))
    f.d.line([x, y + 18, x + w - 1, y + 18], fill=_sombra(tema, 0.6) + (255,))
    # chamine
    f.d.rectangle([x + w - 16, y, x + w - 12, y + 8],
                  fill=_rgb("#6d6a75") + (255,))
    # porta
    f.d.rectangle([x + w // 2 - 4, y + h - 12, x + w // 2 + 3, y + h - 1],
                  fill=_rgb("#5b3d24") + (255,))
    f.d.point((x + w // 2 + 2, y + h - 7), fill=_rgb("#f2d14e") + (255,))
    # janelas acesas
    for wx in (x + 9, x + w - 17):
        f.d.rectangle([wx, y + h - 26, wx + 7, y + h - 19],
                      fill=_rgb("#ffd27a") + (255,))
        f.d.rectangle([wx, y + h - 26, wx + 7, y + h - 19],
                      outline=_sombra(parede, 0.6) + (255,))
    # placa com a cor do tema (a "marca" da fabrica)
    f.d.rectangle([x + 6, y + h - 11, x + 12, y + h - 5], fill=tema + (255,))
    f.d.rectangle([x + 6, y + h - 11, x + 12, y + h - 5],
                  outline=_sombra(tema, 0.6) + (255,))


def _bot(f: Folha, idx, direcao, quadro):
    """16x16: cabeca, tunica e pernas que alternam (a caminhada)."""
    x, y = (idx % COLS) * TILE, (idx // COLS) * TILE
    pele, cabelo = _rgb("#f0c49a"), _rgb("#4a3120")
    tunica = _rgb("#3b6ea5")
    passo = 1 if quadro else -1
    # pernas
    f.d.rectangle([x + 5 + (passo if direcao in ("esq", "dir") else 0), y + 12,
                   x + 6 + (passo if direcao in ("esq", "dir") else 0), y + 15],
                  fill=_rgb("#2c2c34") + (255,))
    f.d.rectangle([x + 9, y + 12 + (1 if quadro else 0),
                   x + 10, y + 15], fill=_rgb("#2c2c34") + (255,))
    # corpo
    f.d.rectangle([x + 4, y + 7, x + 11, y + 12], fill=tunica + (255,))
    f.d.rectangle([x + 4, y + 7, x + 11, y + 8], fill=_sombra(tunica, 1.2) + (255,))
    # cabeca
    f.d.ellipse([x + 4, y + 1, x + 11, y + 8], fill=pele + (255,))
    if direcao == "cima":
        f.d.ellipse([x + 4, y + 1, x + 11, y + 6], fill=cabelo + (255,))
    else:
        f.d.rectangle([x + 4, y + 1, x + 11, y + 3], fill=cabelo + (255,))
        if direcao == "baixo":
            f.d.point([(x + 6, y + 5), (x + 9, y + 5)], fill=(20, 20, 26, 255))
        elif direcao == "esq":
            f.d.point((x + 6, y + 5), fill=(20, 20, 26, 255))
        else:
            f.d.point((x + 9, y + 5), fill=(20, 20, 26, 255))


def _fx(f: Folha):
    for q in range(2):                                   # 160-161 engrenagem
        x, y = ((160 + q) % COLS) * TILE, ((160 + q) // COLS) * TILE
        cinza = _rgb("#c9ccd1")
        f.d.ellipse([x + 3, y + 3, x + 12, y + 12], fill=cinza + (255,))
        f.d.ellipse([x + 6, y + 6, x + 9, y + 9], fill=(40, 42, 48, 255))
        dentes = ([(7, 1), (7, 13), (1, 7), (13, 7)] if q == 0
                  else [(3, 3), (11, 3), (3, 11), (11, 11)])
        for dx, dy in dentes:
            f.d.rectangle([x + dx, y + dy, x + dx + 1, y + dy + 1],
                          fill=cinza + (255,))
    for q in range(2):                                   # 162-163 alerta
        x, y = ((162 + q) % COLS) * TILE, ((162 + q) // COLS) * TILE
        amarelo = _rgb("#f2c94c") if q == 0 else _rgb("#ff9d3c")
        f.d.polygon([x + 8, y + 1, x + 14, y + 13, x + 1, y + 13],
                    fill=amarelo + (255,))
        f.d.rectangle([x + 7, y + 4, x + 8, y + 9], fill=(120, 20, 20, 255))
        f.d.rectangle([x + 7, y + 11, x + 8, y + 12], fill=(120, 20, 20, 255))


def gerar_folha() -> Image.Image:
    f = Folha()
    _chao(f)
    _decor(f)
    ordem = ["chatgpt", "gemini", "picasso", "digen",
             "estudio", "arena", "publicacao", "casa"]
    for i, nome in enumerate(ordem):
        linha, coluna = divmod(i, 4)
        _predio(f, (3 + linha * 3) * COLS + coluna * 4, CORES_FABRICA[nome])
    for i, direcao in enumerate(("baixo", "cima", "esq", "dir")):
        for quadro in range(2):
            _bot(f, 144 + i * 2 + quadro, direcao, quadro)
    _fx(f)
    return f.img


def _papeis() -> dict:
    def p(frames, **extra):
        dados = {"folha": "base", "frames": frames}
        dados.update(extra)
        return dados
    papeis = {
        "chao.grama": p([0, 1, 2, 3], variar=True),
        "chao.flor": p([4, 5], variar=True),
        "chao.caminho": p([6, 7], variar=True),
        "chao.agua": p([8, 9], variar=True),
        "chao.pedra": p([10]), "chao.terra": p([11]),
        "decor.arvore": p([16], larg=2, alt=2),
        "decor.arvore2": p([18], larg=2, alt=2),
        "decor.pedra": p([20]), "decor.cerca": p([21]), "decor.arbusto": p([22]),
        "bot.baixo": p([144, 145], fps=6), "bot.cima": p([146, 147], fps=6),
        "bot.esq": p([148, 149], fps=6), "bot.dir": p([150, 151], fps=6),
        "fx.trabalho": p([160, 161], fps=3), "fx.erro": p([162, 163], fps=2),
    }
    ordem = ["chatgpt", "gemini", "picasso", "digen",
             "estudio", "arena", "publicacao", "casa"]
    for i, nome in enumerate(ordem):
        linha, coluna = divmod(i, 4)
        papeis[f"predio.{nome}"] = p([(3 + linha * 3) * COLS + coluna * 4],
                                     larg=4, alt=3)
    return papeis


PREDIOS_NO_MAPA = {
    "chatgpt": (3, 2), "gemini": (12, 2), "picasso": (21, 2), "digen": (30, 2),
    "estudio": (4, 10), "arena": (37, 8), "publicacao": (34, 17),
}
CASA = (20, 14)
LARG, ALT = 44, 26


def gerar_mapa() -> dict:
    rnd = random.Random(SEED)
    paleta = ["chao.grama", "chao.flor", "chao.caminho", "chao.agua"]
    mapa = motor.mapa_novo(LARG, ALT, paleta)
    chao = mapa["chao"]

    for y in range(ALT):                                  # flores esparsas
        for x in range(LARG):
            if rnd.random() < 0.06:
                chao[y][x] = 1
    for y in range(20, 25):                               # lagoa
        for x in range(2, 11):
            if (x - 6) ** 2 / 18 + (y - 22) ** 2 / 5 <= 1:
                chao[y][x] = 3

    ocupado = set()
    for nome, (px, py) in PREDIOS_NO_MAPA.items():
        for dy in range(3):
            for dx in range(4):
                ocupado.add((px + dx, py + dy))
    for dy in range(3):
        for dx in range(4):
            ocupado.add((CASA[0] + dx, CASA[1] + dy))

    def caminho(x0, y0, x1, y1):
        x, y = x0, y0
        while x != x1:
            chao[y][x] = 2
            x += 1 if x1 > x else -1
        while y != y1:
            chao[y][x] = 2
            y += 1 if y1 > y else -1
        chao[y][x] = 2

    porta_casa = (CASA[0] + 2, CASA[1] + 3)
    for nome, (px, py) in PREDIOS_NO_MAPA.items():
        caminho(px + 2, py + 3, porta_casa[0], porta_casa[1])

    arvores = []
    for _ in range(160):                                  # bosque nas bordas
        x, y = rnd.randrange(LARG - 1), rnd.randrange(ALT - 1)
        borda = x < 3 or y < 2 or x > LARG - 5 or y > ALT - 5
        celulas_arvore = {(x + dx, y + dy) for dx in range(2) for dy in range(2)}
        livre = (not celulas_arvore & ocupado
                 and all(chao[cy][cx] in (0, 1) for cx, cy in celulas_arvore))
        if (borda or rnd.random() < 0.3) and livre:
            papel = "decor.arvore" if rnd.random() < 0.7 else "decor.arvore2"
            arvores.append({"x": x, "y": y, "papel": papel})
            ocupado |= celulas_arvore
    for _ in range(30):                                   # arbustos e pedras
        x, y = rnd.randrange(LARG), rnd.randrange(ALT)
        if (x, y) not in ocupado and chao[y][x] in (0, 1):
            arvores.append({"x": x, "y": y,
                            "papel": rnd.choice(["decor.arbusto", "decor.pedra"])})
            ocupado.add((x, y))

    mapa["decor"] = arvores
    mapa["predios"] = {n: {"x": x, "y": y}
                       for n, (x, y) in PREDIOS_NO_MAPA.items()}
    mapa["casa"] = {"x": CASA[0], "y": CASA[1]}
    return mapa


def gerar(forcar: bool = False) -> dict:
    if motor.CONFIG.is_file() and not forcar:
        print(f"ja existe {motor.CONFIG} — use --forcar para sobrescrever.")
        return motor.carregar()
    motor.SPRITES.mkdir(parents=True, exist_ok=True)
    folha = gerar_folha()
    folha.save(motor.SPRITES / "base.png")
    cfg = motor.carregar() if motor.CONFIG.is_file() else dict(motor.PADRAO)
    cfg["tile"] = TILE
    cfg["folhas"]["base"] = {"arquivo": "sprites/base.png", "tile_w": TILE,
                             "tile_h": TILE, "margem": 0, "espaco": 0,
                             "chave": None}
    cfg["papeis"].update(_papeis())
    cfg["mapa"] = gerar_mapa()
    motor.salvar(cfg)
    print(f"cenario base pronto: {motor.SPRITES / 'base.png'} "
          f"({folha.size[0]}x{folha.size[1]}) + mapa {LARG}x{ALT}")
    return cfg


if __name__ == "__main__":
    gerar(forcar="--forcar" in sys.argv)
