# -*- coding: utf-8 -*-
"""Folha de olhos como a IA entrega, para os testes do recortador.

E a mesma folha do conferente de 06/10/2026 (`gerar_folhas.py` da prova
dele): 6 pares de olhos de frente (lado a lado) numa folha 1536x1024 com
fundo liso, desenhada em 4x e reduzida (a borda sai misturada com o fundo,
como na imagem da IA), mais um ruido de +-4. Os pares: 4 normais, 1 so de
pupilas (vao de 94 px com `vao=24`) e 1 com cilios. Tons de iris perto do
magenta e do verde de proposito: a cor-chave fechada no desenho fica.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

K = 4
CONTORNO = (20, 20, 26)
IRIS = [(235, 70, 200), (140, 40, 190), (245, 18, 240), (30, 235, 40), (40, 90, 230), (200, 140, 40)]
ESTILOS = ["normal", "normal", "normal", "normal", "pupila", "cilio"]
LARGURA_OLHO, ALTURA_OLHO = 150, 110


def centros(vao: int) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """[(olho da esquerda, olho da direita)] de cada par, em px da folha."""
    saida = []
    for i in range(6):
        cx, cy = 256 + (i % 3) * 512, 256 + (i // 3) * 512
        meio = LARGURA_OLHO // 2 + vao // 2
        saida.append(((cx - meio, cy), (cx + meio, cy)))
    return saida


def _par(c: ImageDraw.ImageDraw, i: int, vao: int, cores_por_lado=None) -> None:
    w, h = LARGURA_OLHO, ALTURA_OLHO
    estilo = ESTILOS[i]
    for lado, (ex, cy) in enumerate(centros(vao)[i]):
        iris = cores_por_lado[lado] if cores_por_lado else IRIS[i]
        x0, y0, x1, y1 = ex - w // 2, cy - h // 2, ex + w // 2, cy + h // 2
        if estilo == "pupila":
            c.ellipse([K * (ex - 40), K * (cy - 40), K * (ex + 40), K * (cy + 40)], fill=CONTORNO)
            c.ellipse([K * (ex - 22), K * (cy - 26), K * (ex - 4), K * (cy - 8)], fill=(255, 255, 255))
            continue
        c.ellipse([K * x0, K * y0, K * x1, K * y1], fill=CONTORNO)
        c.ellipse([K * (x0 + 7), K * (y0 + 7), K * (x1 - 7), K * (y1 - 7)], fill=(250, 250, 248))
        c.ellipse([K * (ex - 36), K * (cy - 36), K * (ex + 36), K * (cy + 36)], fill=iris)
        c.ellipse([K * (ex - 16), K * (cy - 16), K * (ex + 16), K * (cy + 16)], fill=CONTORNO)
        c.ellipse([K * (ex - 14), K * (cy - 22), K * (ex - 2), K * (cy - 10)], fill=(255, 255, 255))
        if estilo == "cilio":
            for k in range(3):
                bx = x0 + 30 + k * 40
                c.line([K * bx, K * (y0 - 10), K * (bx + 18), K * (y0 - 34)], fill=CONTORNO, width=K * 7)


def folha(fundo=(255, 0, 255), vao: int = 40, *, cores_por_lado=None) -> np.ndarray:
    """RGB uint8 1024x1536. `cores_por_lado` = (iris da esquerda, iris da
    direita) em todos os pares: o teste ve qual olho foi para cima."""
    grande = Image.new("RGB", (1536 * K, 1024 * K), tuple(fundo))
    caneta = ImageDraw.Draw(grande)
    for i in range(6):
        _par(caneta, i, vao, cores_por_lado)
    img = grande.resize((1536, 1024), Image.Resampling.LANCZOS)
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(7)
    return np.clip(arr + rng.integers(-4, 5, arr.shape), 0, 255).astype(np.uint8)
