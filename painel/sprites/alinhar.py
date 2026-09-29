# -*- coding: utf-8 -*-
"""Todos os quadros com a MESMA ancora, na MESMA celula, com margem.

A IA desenha cada quadro onde quer dentro da celula: na 11243 a bola anda
dezenas de pixels de um quadro para o outro, e tocando isso a animacao
treme. Aqui cada quadro e recortado no desenho, a ancora dele e calculada
(centro de massa do alfa, centro da caixa ou o pe) e todos sao colados com
a ancora no mesmo ponto de uma celula de tamanho unico -- que e o que a
`folha_animada.gd` do palco espera (docs/palco/COMO-EDITAR.md).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

ANCORAS = ("massa", "caixa", "pe")


@dataclass
class Alinhado:
    quadros: list            # arrays HxWx4 do mesmo tamanho
    celula: tuple            # (largura, altura)
    ancora: tuple            # (x, y) na celula, px inteiros
    escala: float = 1.0
    ancoras_de_origem: list = None   # (x, y) de cada quadro na folha de origem


def caixa_do_desenho(alfa: np.ndarray, limite: int = 16):
    """(x0, y0, x1, y1) do que e visivel, ou None."""
    ys, xs = np.nonzero(alfa >= limite)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def ancora_de(quadro: np.ndarray, modo: str = "massa", limite: int = 16):
    """A ancora (x, y), em px de subpixel, dentro do quadro."""
    alfa = quadro[..., 3]
    caixa = caixa_do_desenho(alfa, limite)
    if caixa is None:
        h, w = alfa.shape
        return w / 2.0, h / 2.0
    x0, y0, x1, y1 = caixa
    if modo == "caixa":
        return (x0 + x1) / 2.0, (y0 + y1) / 2.0
    if modo == "pe":
        return (x0 + x1) / 2.0, float(y1)
    peso = np.where(alfa >= limite, alfa, 0).astype(np.float64)
    total = peso.sum()
    ys, xs = np.indices(alfa.shape)
    return float((xs * peso).sum() / total), float((ys * peso).sum() / total)


def _reduzir(quadro: np.ndarray, tamanho: tuple) -> np.ndarray:
    """LANCZOS em alfa pre-multiplicado (o Pillow faz isso para RGBA): sem o
    halo escuro que a reducao ingenua deixa na borda."""
    img = Image.fromarray(quadro, "RGBA").resize(tamanho, Image.LANCZOS)
    return np.asarray(img, np.uint8).copy()


def alinhar(arr: np.ndarray, caixas: list, modo: str = "massa",
            margem: int = 4, limite: int = 16, largura_max: int = 512,
            espelhar: bool = False) -> Alinhado:
    """Recorta cada caixa, acha a ancora e cola todos iguais."""
    recortes, ancoras, desenhos, origens = [], [], [], []
    for x0, y0, x1, y1 in caixas:
        q = arr[y0:y1, x0:x1].copy()
        if espelhar:
            q = q[:, ::-1].copy()
        c = caixa_do_desenho(q[..., 3], limite) or (0, 0, q.shape[1],
                                                    q.shape[0])
        ax, ay = ancora_de(q, modo, limite)
        recortes.append(q)
        ancoras.append((ax, ay))
        desenhos.append(c)
        ox = x0 + (q.shape[1] - ax) if espelhar else x0 + ax
        origens.append((round(ox, 1), round(y0 + ay, 1)))
    if not recortes:
        return Alinhado([], (0, 0), (0, 0), 1.0, [])

    esq = max(ax - c[0] for (ax, _), c in zip(ancoras, desenhos))
    dir_ = max(c[2] - ax for (ax, _), c in zip(ancoras, desenhos))
    cima = max(ay - c[1] for (_, ay), c in zip(ancoras, desenhos))
    baixo = max(c[3] - ay for (_, ay), c in zip(ancoras, desenhos))
    margem = max(0, int(margem))
    alvo = (margem + math.ceil(esq), margem + math.ceil(cima))
    largura = alvo[0] + math.ceil(dir_) + margem
    altura = alvo[1] + math.ceil(baixo) + margem

    quadros = []
    for q, (ax, ay), c in zip(recortes, ancoras, desenhos):
        tela = np.zeros((altura, largura, 4), np.uint8)
        dx = int(round(alvo[0] - ax))
        dy = int(round(alvo[1] - ay))
        x0, y0, x1, y1 = c
        # so o desenho: o resto do recorte e vazio (ou lixo de outra celula)
        destino_x0, destino_y0 = x0 + dx, y0 + dy
        sx0 = max(0, -destino_x0)
        sy0 = max(0, -destino_y0)
        sx1 = min(x1 - x0, largura - destino_x0)
        sy1 = min(y1 - y0, altura - destino_y0)
        if sx1 > sx0 and sy1 > sy0:
            tela[destino_y0 + sy0:destino_y0 + sy1,
                 destino_x0 + sx0:destino_x0 + sx1] = \
                q[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1]
        quadros.append(tela)

    escala = 1.0
    if largura_max and largura > int(largura_max):
        escala = int(largura_max) / largura
        novo = (max(1, round(largura * escala)), max(1, round(altura * escala)))
        quadros = [_reduzir(q, novo) for q in quadros]
        alvo = (int(round(alvo[0] * escala)), int(round(alvo[1] * escala)))
        largura, altura = novo
    return Alinhado(quadros, (largura, altura), alvo, escala, origens)


def montar_folha(quadros: list, colunas: int = 0):
    """(array da folha, colunas, linhas). Largura = colunas x celula, em px
    inteiros; celulas vazias so no fim."""
    n = len(quadros)
    if not n:
        return np.zeros((1, 1, 4), np.uint8), 1, 1
    colunas = int(colunas) if colunas and colunas > 0 else \
        math.ceil(math.sqrt(n))
    colunas = max(1, min(colunas, n))
    linhas = math.ceil(n / colunas)
    h, w = quadros[0].shape[:2]
    folha = np.zeros((linhas * h, colunas * w, 4), np.uint8)
    for i, q in enumerate(quadros):
        j, k = divmod(i, colunas)
        folha[j * h:(j + 1) * h, k * w:(k + 1) * w] = q
    return folha, colunas, linhas


__all__ = ["ANCORAS", "Alinhado", "alinhar", "ancora_de", "caixa_do_desenho",
           "montar_folha"]
