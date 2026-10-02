# -*- coding: utf-8 -*-
"""Fundo automatico: descobre QUE fundo a imagem tem e tira, sem furar o desenho.

02/10/2026: sete sprites chegaram a biblioteca e a Vila com o fundo grudado --
o "xadrez de transparencia" DESENHADO pela IA (o elmo do berserker, a bolinha,
o avanco brutal, os predios do DeepSeek, do Grok e do PicassoIA) e um branco
liso (o predio do ChatGPT). A limpeza so tirava a cor-chave pedida (magenta);
quando a IA ignorava o pedido, nada saia, e ninguem conferia.

Tres casos, decididos pelo ANEL da borda (4 px):
  - `transparente`: o anel ja e quase todo alfa baixo -> mantem;
  - `liso`: uma cor domina o anel (branco, preto, magenta, verde...) -> tira
    por preenchimento a partir das bordas (o branco de DENTRO do desenho, que
    nao encosta na borda, fica);
  - `xadrez`: duas cores claras/cinza se alternam no anel -> as duas viram
    candidatas juntas e o preenchimento a partir da borda leva o xadrez todo.

`sobra_de_fundo` mede o que ficou: o PORTAO usa isso para nunca deixar passar
uma imagem com o fundo grudado.
"""
from __future__ import annotations

import numpy as np

from . import limpeza
from .rotulos import rotular

ANEL = 4


def _anel(arr: np.ndarray) -> np.ndarray:
    a = ANEL
    return np.concatenate([arr[:a].reshape(-1, arr.shape[2]), arr[-a:].reshape(-1, arr.shape[2]),
                           arr[:, :a].reshape(-1, arr.shape[2]),
                           arr[:, -a:].reshape(-1, arr.shape[2])])


def _modas(rgb: np.ndarray, n: int = 3) -> list:
    """As n cores mais comuns (degraus de 8), com a fracao de cada uma."""
    q = rgb.astype(np.int32) // 8
    chave = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    valores, contagem = np.unique(chave, return_counts=True)
    ordem = np.argsort(contagem)[::-1][:n]
    total = float(len(chave))
    saida = []
    for i in ordem:
        cor = rgb[chave == valores[i]].mean(0)
        saida.append((tuple(int(round(c)) for c in cor), contagem[i] / total))
    return saida


def _neutra(cor) -> bool:
    """Cinza (claro OU escuro) ou branco: o xadrez de transparencia nunca e colorido."""
    return max(cor) - min(cor) <= 24


def detectar(arr: np.ndarray) -> dict:
    """{"tipo": "transparente"|"liso"|"xadrez", "cores": [...]}"""
    anel = _anel(arr)
    if float((anel[:, 3] < 128).mean()) > 0.5:
        return {"tipo": "transparente", "cores": []}
    opacos = anel[anel[:, 3] >= 128][:, :3]
    modas = _modas(opacos, 3)
    (c1, f1) = modas[0]
    if len(modas) >= 2:
        (c2, f2) = modas[1]
        if (f1 + f2 >= 0.7 and min(f1, f2) >= 0.1 and _neutra(c1) and _neutra(c2)
                and limpeza.distancia(np.asarray([c1], np.float32), c2)[0] >= 12):
            return {"tipo": "xadrez", "cores": [c1, c2]}
    return {"tipo": "liso", "cores": [c1]}


def remover(arr: np.ndarray, tolerancia: float = 24, suavidade: float = 16) -> tuple:
    """(rgba sem fundo, deteccao). Nunca altera `arr`.

    Se o caminho escolhido deixar fundo no anel, tenta o outro (liso <-> xadrez
    com as duas cores mais comuns do anel) e fica com o que sobrou menos."""
    info = detectar(arr)
    if info["tipo"] == "transparente":
        return limpeza.zerar_transparentes(arr.copy()), info
    saida = _remover_com(arr, info, tolerancia, suavidade)
    if sobra_de_fundo(saida) > 0.02:
        anel = _anel(arr)
        modas = _modas(anel[anel[:, 3] >= 128][:, :3], 2)
        if info["tipo"] == "liso" and len(modas) == 2:
            outra = {"tipo": "xadrez", "cores": [modas[0][0], modas[1][0]]}
        else:
            outra = {"tipo": "liso", "cores": [modas[0][0]]}
        tentativa = _remover_com(arr, outra, tolerancia, suavidade)
        if sobra_de_fundo(tentativa) < sobra_de_fundo(saida):
            saida, info = tentativa, outra
    return saida, info


def _remover_com(arr, info, tolerancia, suavidade):
    if info["tipo"] == "liso":
        return limpeza.remover_fundo(arr, "bordas", info["cores"][0],
                                     tolerancia=tolerancia, suavidade=suavidade)
    # xadrez: as duas cores juntas, a partir da borda
    rgb = arr[..., :3].astype(np.float32)
    perto = np.zeros(arr.shape[:2], bool)
    for cor in info["cores"]:
        perto |= limpeza.distancia(rgb, cor) <= tolerancia + suavidade
    comps = rotular(perto)
    ids = list(np.nonzero(comps.tocam_a_borda())[0] + 1)
    # xadrez FECHADO dentro do desenho (a abertura do elmo, 02/10): area que tem
    # as DUAS cores alternando tambem e fundo; o brilho branco do desenho tem uma
    # cor so e fica
    # Area FECHADA so e fundo se seguir uma grade de quadrados, medida DENTRO
    # dela (a IA desenha o xadrez de dentro com outro alinhamento); a sombra de
    # dois tons do desenho (a bola, as paredes) nao segue grade nenhuma.
    limite = tolerancia + suavidade
    classes = np.where(limpeza.distancia(rgb, info["cores"][0]) <= limite, 0,
                       np.where(limpeza.distancia(rgb, info["cores"][1]) <= limite, 1, -1))
    rot = comps.rotulos
    n = int(rot.max())
    area = np.bincount(rot.ravel(), minlength=n + 1)
    for i in range(1, n + 1):
        if i in ids or area[i] < 400:
            continue
        ys, xs = np.nonzero(rot == i)
        if _segue_grade(classes, rot == i, ys, xs):
            ids.append(i)
    fundo = np.isin(rot, ids)
    saida = arr.copy()
    saida[..., 3][fundo] = 0
    return limpeza.zerar_transparentes(saida)


def _periodo(classes: np.ndarray):
    """(lado do quadrado, fase) numa linha de classes 0/1 (-1 = outra cor)."""
    validos = np.nonzero(classes >= 0)[0]
    if len(validos) < 16:
        return None
    seq = classes[validos[0]:validos[-1] + 1]
    trocas = np.nonzero((seq[1:] != seq[:-1]) & (seq[1:] >= 0) & (seq[:-1] >= 0))[0] + 1
    if len(trocas) < 3:
        return None
    # lado com casa decimal: a IA desenha quadrados de ~20,5 px e o erro de um
    # lado inteiro acumula ao longo da imagem (02/10: o miolo do elmo)
    # a 1a e a ultima troca ficam na beirada da area, num quadrado cortado: fora
    if len(trocas) >= 5:
        trocas = trocas[1:-1]
    passos = np.diff(trocas)
    tipico = float(np.median(passos))
    if tipico < 3:
        return None
    quantos = np.maximum(1, np.round(passos / tipico))
    lado = float((trocas[-1] - trocas[0]) / quantos.sum())
    fase = float(validos[0] + trocas[0]) % lado
    return lado, fase


def _segue_grade(classes: np.ndarray, regiao: np.ndarray, ys, xs, minimo: float = 0.8) -> bool:
    """A regiao alterna as duas cores numa grade regular de quadrados?"""
    yc, xc = int(np.median(ys)), int(np.median(xs))
    linha = np.where(regiao[yc], classes[yc], -1)
    coluna = np.where(regiao[:, xc], classes[:, xc], -1)
    pl, pc = _periodo(linha), _periodo(coluna)
    if pl is None or pc is None:
        return False
    paridade = (np.floor((xs - pl[1]) / pl[0]) + np.floor((ys - pc[1]) / pc[0])) % 2
    vistos = classes[ys, xs]
    ok = vistos >= 0
    if ok.mean() < 0.9:
        return False                      # tem outras cores: e desenho
    acerto = float((vistos[ok] == paridade[ok]).mean())
    return max(acerto, 1 - acerto) >= minimo


def sobra_de_fundo(arr: np.ndarray) -> float:
    """Fracao do anel da borda que continua opaca. Sprite limpo ~0."""
    return float((_anel(arr)[:, 3] >= 128).mean())
