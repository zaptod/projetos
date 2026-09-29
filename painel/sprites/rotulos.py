# -*- coding: utf-8 -*-
"""Componentes conectados de uma mascara, sem scipy e sem laco por pixel.

POR QUE ASSIM. O scipy nao esta instalado, e o `ImageDraw.floodfill` do
Pillow anda pixel a pixel em Python (uma folha de 1942x809 tem 1,5 milhao).
Aqui a mascara vira CORRIDAS (trechos horizontais seguidos), duas corridas de
linhas vizinhas que se tocam viram um par, e os pares se juntam por "enganchar
e comprimir" com numpy. Uma folha inteira sai em dezenas de milissegundos.

Vizinhanca de 8: pixel na diagonal e do mesmo componente (a gota que encosta
na bola pela quina e da bola).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Componentes:
    """O resultado. `rotulos` tem 0 no fundo e 1..n nos componentes."""
    rotulos: np.ndarray          # int32 HxW
    n: int
    areas: np.ndarray            # (n,) pixels de cada componente
    caixas: np.ndarray           # (n, 4) x0, y0, x1, y1 (x1/y1 exclusivos)

    def tocam_a_borda(self) -> np.ndarray:
        """(n,) bool: o componente encosta na moldura da imagem?"""
        altura, largura = self.rotulos.shape
        c = self.caixas
        return ((c[:, 0] == 0) | (c[:, 1] == 0)
                | (c[:, 2] == largura) | (c[:, 3] == altura))


def corridas(mascara: np.ndarray):
    """(linha, x0, x1) de cada trecho seguido de True, em ordem de leitura."""
    altura, largura = mascara.shape
    borda = np.zeros((altura, largura + 2), np.int8)
    borda[:, 1:-1] = mascara
    passo = np.diff(borda, axis=1)
    linhas, x0 = np.nonzero(passo == 1)
    _l, x1 = np.nonzero(passo == -1)
    return linhas.astype(np.int64), x0.astype(np.int64), x1.astype(np.int64)


def _pares(linhas, x0, x1, largura: int):
    """Pares (a, b) de corridas de linhas vizinhas que se tocam (8-viz.)."""
    k = largura + 2
    chave_fim = linhas * k + x1
    chave_ini = linhas * k + x0
    abaixo = (linhas + 1) * k
    # a primeira corrida da linha de baixo que termina depois do meu inicio
    lo = np.searchsorted(chave_fim, abaixo + x0, side="left")
    # e a primeira que comeca depois do meu fim (diagonal conta: <=)
    hi = np.searchsorted(chave_ini, abaixo + x1, side="right")
    quantos = np.maximum(hi - lo, 0)
    total = int(quantos.sum())
    if not total:
        vazio = np.zeros(0, np.int64)
        return vazio, vazio
    a = np.repeat(np.arange(len(linhas)), quantos)
    desloc = np.arange(total) - np.repeat(np.cumsum(quantos) - quantos, quantos)
    b = np.repeat(lo, quantos) + desloc
    return a, b


def _juntar(n: int, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Enganchar e comprimir: cada corrida acaba apontando para a menor raiz."""
    pai = np.arange(n, dtype=np.int64)
    if not len(a):
        return pai
    while True:
        ra, rb = pai[a], pai[b]
        diferentes = ra != rb
        if not diferentes.any():
            break
        ra, rb = ra[diferentes], rb[diferentes]
        menor = np.minimum(ra, rb)
        np.minimum.at(pai, ra, menor)
        np.minimum.at(pai, rb, menor)
        while True:                               # comprime os caminhos
            avo = pai[pai]
            if np.array_equal(avo, pai):
                break
            pai = avo
    return pai


def rotular(mascara: np.ndarray) -> Componentes:
    """Os componentes conectados (8-vizinhanca) de uma mascara booleana."""
    mascara = np.asarray(mascara, bool)
    altura, largura = mascara.shape
    linhas, x0, x1 = corridas(mascara)
    n_corridas = len(linhas)
    rotulos = np.zeros(altura * largura, np.int32)
    if not n_corridas:
        return Componentes(rotulos.reshape(altura, largura), 0,
                           np.zeros(0, np.int64), np.zeros((0, 4), np.int64))
    a, b = _pares(linhas, x0, x1, largura)
    raiz = _juntar(n_corridas, a, b)
    _unicas, comp = np.unique(raiz, return_inverse=True)
    comp = comp.astype(np.int64)
    n = int(comp.max()) + 1

    tamanho = x1 - x0
    inicio = linhas * largura + x0
    total = int(tamanho.sum())
    desloc = np.arange(total) - np.repeat(np.cumsum(tamanho) - tamanho,
                                          tamanho)
    rotulos[np.repeat(inicio, tamanho) + desloc] = np.repeat(comp + 1, tamanho)

    areas = np.bincount(comp, weights=tamanho, minlength=n).astype(np.int64)
    caixas = np.empty((n, 4), np.int64)
    caixas[:, 0] = largura
    caixas[:, 1] = altura
    caixas[:, 2] = 0
    caixas[:, 3] = 0
    np.minimum.at(caixas[:, 0], comp, x0)
    np.minimum.at(caixas[:, 1], comp, linhas)
    np.maximum.at(caixas[:, 2], comp, x1)
    np.maximum.at(caixas[:, 3], comp, linhas + 1)
    return Componentes(rotulos.reshape(altura, largura), n, areas, caixas)


__all__ = ["Componentes", "corridas", "rotular"]
