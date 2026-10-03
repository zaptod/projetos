# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image

from painel.sprites import importar


def _fundo(cor, tamanho=(80, 30)):
    a = np.zeros((tamanho[1], tamanho[0], 4), np.uint8)
    a[..., :3] = cor
    a[..., 3] = 255
    return a


def test_fundos_e_cor_interna_nao_fura():
    for cor in ((255, 0, 255), (255, 255, 255), (0, 0, 0)):
        a = _fundo(cor)
        a[8:24, 20:55, :3] = (30, 80, 200)
        a[12:18, 30:42, :3] = cor
        r = importar.processar(Image.fromarray(a), modo="auto", ilha_min=1)
        assert r.limpo[0, 0, 3] == 0
        assert r.limpo[14, 35, 3] == 255


def test_xadrez_falso_vira_alfa():
    a = _fundo((220, 220, 220), (40, 30))
    for y in range(30):
        for x in range(40):
            if (x // 4 + y // 4) % 2:
                a[y, x, :3] = (180, 180, 180)
    a[7:24, 13:28, :3] = (20, 100, 200)
    r = importar.processar(Image.fromarray(a), ilha_min=1)
    assert r.limpo[1, 1, 3] == 0 and r.limpo[1, 5, 3] == 0


def test_grade_ordem_pes_espelho_e_pontinho():
    a = _fundo((255, 0, 255), (80, 40))
    for i in range(8):
        x, y = (i % 4) * 20 + 4, (i // 4) * 20 + 2
        a[y:y + 15, x:x + 8, :3] = (i + 1, 0, 0)
    a[1, 1, :3] = (5, 5, 5)
    r = importar.processar(Image.fromarray(a), modo="grade", colunas=4, linhas=2,
                           ilha_min=2)
    assert len(r.alinhado.quadros) == 8
    assert [q[..., 0].max() for q in r.alinhado.quadros] == list(range(1, 9))
    assert len({np.nonzero(q[..., 3])[0].max() for q in r.alinhado.quadros}) == 1
    e = importar.espelhar(r)
    assert np.array_equal(e.alinhado.quadros[0], r.alinhado.quadros[0][:, ::-1])


def test_auto_acha_seis_em_tira_irregular():
    a = _fundo((255, 255, 255), (120, 30))
    for i, x in enumerate((3, 21, 43, 65, 87, 108)):
        a[5 + i % 3:21, x:x + 7, :3] = (40, 100, 200)
    r = importar.processar(Image.fromarray(a), modo="auto", ilha_min=1, juntar=3)
    assert len(r.caixas) == 6
