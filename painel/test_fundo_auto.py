# -*- coding: utf-8 -*-
"""O fundo automatico (02/10/2026: sete sprites passaram com o fundo grudado)."""
import numpy as np

from painel.sprites import fundo_auto


def _tela(h=400, w=400, cor=(255, 255, 255)):
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., :3] = cor
    arr[..., 3] = 255
    return arr


def _xadrez(h=400, w=400, lado=20.5, c1=(254, 254, 254), c2=(190, 190, 190), fase=(0, 0)):
    arr = _tela(h, w, c1)
    ys, xs = np.mgrid[0:h, 0:w]
    impar = (np.floor((xs + fase[0]) / lado) + np.floor((ys + fase[1]) / lado)) % 2 == 1
    arr[impar, :3] = c2
    return arr


def _bola(arr, cy=200, cx=200, r=120, contorno=(0, 0, 0), dentro=(240, 240, 240), sombra=(200, 200, 200)):
    """Bola de contorno preto com o MIOLO em dois cinzas (como a bolinha)."""
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    d = np.hypot(ys - cy, xs - cx)
    arr[d <= r + 6, :3] = contorno
    arr[d <= r, :3] = dentro
    arr[(d <= r) & (ys > cy + 20)] = (*sombra, 255)
    return d <= r + 6


def test_fundo_branco_sai_e_o_branco_de_dentro_fica():
    arr = _tela()
    dentro = _bola(arr, dentro=(255, 255, 255))
    limpo, info = fundo_auto.remover(arr)
    assert info["tipo"] == "liso"
    assert fundo_auto.sobra_de_fundo(limpo) == 0
    assert (limpo[dentro, 3] == 255).mean() > 0.98        # o brilho branco nao fura


def test_xadrez_desenhado_sai_mesmo_com_quadrado_de_20_e_meio():
    arr = _xadrez()
    dentro = _bola(arr)
    limpo, info = fundo_auto.remover(arr)
    assert info["tipo"] == "xadrez"
    assert fundo_auto.sobra_de_fundo(limpo) == 0
    assert (limpo[~dentro, 3] == 0).mean() > 0.97
    # a bola de DOIS cinzas (sombra) nao e xadrez: fica inteira
    assert (limpo[dentro, 3] == 255).mean() > 0.98


def test_xadrez_fechado_dentro_do_desenho_sai():
    """A abertura do elmo: xadrez cercado pelo desenho, com outra fase."""
    arr = _xadrez()
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    d = np.hypot(ys - 200, xs - 200)
    anel = (d <= 150) & (d >= 110)
    arr[anel, :3] = (120, 40, 40)                         # o elmo
    miolo = d < 110
    dentro = _xadrez(fase=(7, 3))
    arr[miolo] = dentro[miolo]                             # xadrez com outro alinhamento
    limpo, _ = fundo_auto.remover(arr)
    assert (limpo[miolo, 3] == 0).mean() > 0.95
    assert (limpo[anel, 3] == 255).mean() > 0.98


def test_magenta_liso_e_imagem_ja_transparente():
    arr = _tela(cor=(255, 0, 255))
    dentro = _bola(arr)
    limpo, info = fundo_auto.remover(arr)
    assert info["tipo"] == "liso" and fundo_auto.sobra_de_fundo(limpo) == 0
    assert (limpo[dentro, 3] == 255).mean() > 0.98
    ja = limpo.copy()
    assert fundo_auto.detectar(ja)["tipo"] == "transparente"
