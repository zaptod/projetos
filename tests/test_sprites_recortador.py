# -*- coding: utf-8 -*-
"""Folhas sinteticas para o recortador verde/magenta, sem biblioteca real."""
from __future__ import annotations

import time

import numpy as np
import pytest

from painel.sprites import recortador


def _folha(cor_fundo):
    arr = np.zeros((260, 360, 4), np.uint8)
    arr[..., :3] = cor_fundo
    arr[..., 3] = 255
    # Seis desenhos; o primeiro sao dois olhos que precisam virar um so.
    for caixa, cor in [((30, 30, 52, 54), (20, 30, 180)), ((69, 30, 91, 54), (20, 30, 180)),
                       ((135, 26, 178, 70), (240, 70, 50)), ((220, 28, 267, 75), (80, 80, 80)),
                       ((45, 145, 95, 195), (250, 220, 30)), ((150, 145, 204, 198), (40, 180, 220)),
                       ((260, 145, 315, 202), (130, 50, 180))]:
        x0, y0, x1, y1 = caixa
        arr[y0:y1, x0:x1, :3] = cor
    # Verde verdadeiro dentro do desenho so pode sumir quando ele for fundo.
    arr[155:180, 164:190, :3] = (0, 255, 0)
    # Poeira isolada.
    arr[230:233, 20:23, :3] = (10, 10, 10)
    return arr


@pytest.mark.parametrize("fundo", [(0, 255, 0), (255, 0, 255)])
def test_recorta_seis_desenhos_junta_olhos_e_tira_poeira(fundo):
    resultado = recortador.recortar(_folha(fundo), juntar=20, area_min=20)
    assert resultado.fundo == ("verde" if fundo[1] == 255 and fundo[0] == 0 else "magenta")
    assert len(resultado.recortes) == 6
    assert resultado.recortes[0].imagem.shape[1] >= 55  # os dois olhos juntos
    # Fundo nao sobrevive opaco na borda; numa folha magenta o verde de dentro continua.
    chave = np.asarray(fundo, np.uint8)
    borda = np.r_[resultado.limpo[0], resultado.limpo[-1],
                  resultado.limpo[:, 0], resultado.limpo[:, -1]]
    assert not np.any((borda[:, 3] > 0) & np.all(borda[:, :3] == chave, axis=1))
    if fundo == (255, 0, 255):
        assert np.any(np.all(resultado.limpo[..., :3] == (0, 255, 0), axis=2)
                      & (resultado.limpo[..., 3] == 255))


def test_recusa_fundo_azul_com_a_frase_humana():
    with pytest.raises(ValueError, match="fundo precisa ser verde ou magenta liso"):
        recortador.recortar(_folha((30, 80, 220)))


def test_gabarito_de_olhos_preserva_proporcao_e_zona():
    resultado = recortador.recortar(_folha((255, 0, 255)), juntar=20, area_min=20)
    pronto = recortador.no_gabarito(resultado.recortes[0].imagem, "olhos")
    ys, xs = np.nonzero(pronto[..., 3])
    assert pronto.shape == (1024, 1024, 4)
    assert xs.min() >= 480 and xs.max() < 645 and ys.min() >= 340 and ys.max() < 684
    assert xs.max() - xs.min() >= 160


def test_halo_magenta_da_borda_nao_sobra_visivel():
    arr = np.full((64, 64, 4), (255, 0, 255, 255), np.uint8)
    arr[24:40, 24:40, :3] = (30, 80, 210)
    # Antialias/halo de uma folha sem alfa: mistura da cor-chave na borda.
    arr[23:41, 23, :3] = arr[23:41, 40, :3] = (200, 20, 240)
    arr[23, 23:41, :3] = arr[40, 23:41, :3] = (200, 20, 240)
    resultado = recortador.recortar(arr, area_min=20)
    recorte = resultado.recortes[0].imagem
    assert not np.any((recorte[..., 3] > 0) & np.all(recorte[..., :3] == (255, 0, 255), axis=2))


def test_folha_2048_termina_em_menos_de_tres_segundos():
    arr = np.full((2048, 2048, 4), (255, 0, 255, 255), np.uint8)
    for y in range(120, 1900, 280):
        for x in range(120, 1900, 280):
            arr[y:y + 80, x:x + 100, :3] = (25, 70, 200)
    inicio = time.perf_counter()
    resultado = recortador.recortar(arr, area_min=50)
    assert time.perf_counter() - inicio < 3.0
    assert len(resultado.recortes) == 49
