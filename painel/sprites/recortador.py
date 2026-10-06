# -*- coding: utf-8 -*-
"""Recorta uma folha de IA com fundo verde ou magenta liso.

Esta nao e outra limpeza generica: a entrada e deliberadamente estreita. O
fundo sai por conexao com a borda, portanto um verde dentro de um olho numa
folha magenta continua no desenho.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from . import limpeza
from .rotulos import rotular

FUNDOS = {"verde": (0, 255, 0), "magenta": (255, 0, 255)}
JUNCAO = {"pouco": 8, "medio": 16, "muito": 32}
ZONAS = {
    "olhos": (480, 340, 645, 684),
    "sobrancelhas": (360, 342, 530, 682),
    "boca": (640, 405, 740, 620),
    "detalhe_rosto": (294, 415, 680, 727),
    "sombra": (256, 532, 768, 748),
    "acessorio_cabeca": (0, 0, 512, 1024),
    "acessorio_costas": (0, 0, 1024, 1024),
}


@dataclass
class Recorte:
    imagem: np.ndarray
    caixa: tuple[int, int, int, int]
    area: int


@dataclass
class Resultado:
    limpo: np.ndarray
    fundo: str
    recortes: list[Recorte]
    avisos: list[str]
    cor_chave_dentro: int


def _borda(arr: np.ndarray) -> np.ndarray:
    h, w = arr.shape[:2]
    a = min(4, h, w)
    return np.concatenate((arr[:a, :, :3].reshape(-1, 3),
                           arr[-a:, :, :3].reshape(-1, 3),
                           arr[:, :a, :3].reshape(-1, 3),
                           arr[:, -a:, :3].reshape(-1, 3)))


def detectar_fundo(arr: np.ndarray) -> str:
    """Devolve verde/magenta; outros fundos recebem uma frase para o Adrian."""
    borda = _borda(arr)
    melhor, fracao = None, 0.0
    for nome, cor in FUNDOS.items():
        perto = limpeza.distancia(borda, cor) <= 42
        atual = float(perto.mean())
        if atual > fracao:
            melhor, fracao = nome, atual
    if melhor is None or fracao < 0.60:
        raise ValueError("o fundo precisa ser verde ou magenta liso")
    return melhor


def _grupos(mascara: np.ndarray, juntar: int, area_min: int):
    """Componentes proximos viram um desenho; poeira isolada nao vira arte."""
    comps = rotular(mascara)
    if not comps.n:
        return []
    caixas = comps.caixas.astype(np.int64)
    pai = np.arange(comps.n)

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    x0, y0, x1, y1 = caixas.T
    dx = np.maximum(0, np.maximum(x0[:, None] - x1[None, :],
                                  x0[None, :] - x1[:, None]))
    dy = np.maximum(0, np.maximum(y0[:, None] - y1[None, :],
                                  y0[None, :] - y1[:, None]))
    pares = np.argwhere((np.maximum(dx, dy) <= int(juntar))
                         & (np.arange(comps.n)[:, None] < np.arange(comps.n)[None, :]))
    for a, b in pares:
        ra, rb = raiz(int(a)), raiz(int(b))
        if ra != rb:
            pai[max(ra, rb)] = min(ra, rb)
    grupos: dict[int, list[int]] = {}
    for i in range(comps.n):
        grupos.setdefault(raiz(i), []).append(i)
    saida = []
    for membros in grupos.values():
        area = int(comps.areas[membros].sum())
        if area < int(area_min):
            continue
        c = caixas[membros]
        caixa = (int(c[:, 0].min()), int(c[:, 1].min()),
                 int(c[:, 2].max()), int(c[:, 3].max()))
        saida.append((caixa, membros, area))
    # Ordem de leitura, sem importar o metodo interno dos rotulos.
    return sorted(saida, key=lambda item: (item[0][1], item[0][0]))


def recortar(origem, *, juntar: int = JUNCAO["medio"], area_min: int = 50,
             margem: int = 8, tolerancia: float = 34, suavidade: float = 22) -> Resultado:
    """Limpa e separa a folha, sem apagar a cor-chave fechada num desenho."""
    arr = limpeza.para_array(origem)
    fundo = detectar_fundo(arr)
    cor = FUNDOS[fundo]
    # `bordas` e a protecao importante: so o candidato conectado ao fundo sai.
    limpo = limpeza.remover_fundo(arr, "bordas", cor, tolerancia, suavidade,
                                  descontaminar=True)
    limpo = limpeza.alfa_minimo(limpo, 8)
    mascara = limpo[..., 3] >= 16
    grupos = _grupos(mascara, juntar, area_min)
    h, w = mascara.shape
    recortes = []
    rotulos = rotular(mascara).rotulos
    for caixa, membros, area in grupos:
        x0, y0, x1, y1 = caixa
        x0, y0 = max(0, x0 - int(margem)), max(0, y0 - int(margem))
        x1, y1 = min(w, x1 + int(margem)), min(h, y1 + int(margem))
        q = limpo[y0:y1, x0:x1].copy()
        # Uma coisa que passou perto nao vaza para o recorte do vizinho.
        pertence = np.isin(rotulos[y0:y1, x0:x1], np.asarray(membros) + 1)
        q[~pertence] = 0
        recortes.append(Recorte(q, (x0, y0, x1, y1), area))
    perto_chave = (limpo[..., 3] >= 16) & (limpeza.distancia(limpo[..., :3], cor) <= tolerancia)
    dentro = int(perto_chave.sum())
    visiveis = max(1, int(mascara.sum()))
    avisos = []
    if dentro > max(24, visiveis // 100):
        avisos.append(f"ha bastante {fundo} parecido dentro de um desenho; confira antes de mandar")
    return Resultado(limpo, fundo, recortes, avisos, dentro)


def no_gabarito(recorte: np.ndarray, parte: str) -> np.ndarray:
    """Encaixa proporcionalmente no quadrado 1024, na zona da parte escolhida."""
    x0, y0, x1, y1 = ZONAS.get(str(parte), (256, 256, 768, 768))
    alfa = recorte[..., 3]
    ys, xs = np.nonzero(alfa >= 16)
    tela = np.zeros((1024, 1024, 4), np.uint8)
    if not len(xs):
        return tela
    corte = recorte[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    escala = min((x1 - x0) / corte.shape[1], (y1 - y0) / corte.shape[0])
    tamanho = (max(1, round(corte.shape[1] * escala)), max(1, round(corte.shape[0] * escala)))
    imagem = Image.fromarray(corte, "RGBA").resize(tamanho, Image.Resampling.LANCZOS)
    q = np.asarray(imagem, np.uint8)
    py = y0 + ((y1 - y0) - q.shape[0]) // 2
    px = x0 + ((x1 - x0) - q.shape[1]) // 2
    tela[py:py + q.shape[0], px:px + q.shape[1]] = q
    return tela


__all__ = ["FUNDOS", "JUNCAO", "Recorte", "Resultado", "detectar_fundo", "no_gabarito", "recortar"]
