# -*- coding: utf-8 -*-
"""Moldura desenhada em volta da foto sai no render (15/09/2026).

Nas fotos 1:1 o gerador as vezes entrega a cena como foto IMPRESSA (borda
branca) ou fotograma de filme (borda escura). Medido em 147 imagens: o
detector marcou 8, todas com moldura de verdade, e nenhuma foto normal.

Rode de dentro de historias/:
    python -m unittest tests.test_moldura_regressions -v
"""
from __future__ import annotations

import inspect
import unittest

from PIL import Image, ImageDraw

from contos.imagens import composicao
from contos.video import renderer


def _cena(tamanho=1024, cor=(40, 90, 120)):
    imagem = Image.new("RGB", (tamanho, tamanho), cor)
    desenho = ImageDraw.Draw(imagem)
    for i in range(0, tamanho, 37):
        desenho.line((i, 0, tamanho - i, tamanho), fill=(200, 120, 60), width=5)
    return imagem


def _com_moldura(cor, espessura=50, tamanho=1024):
    imagem = Image.new("RGB", (tamanho, tamanho), cor)
    miolo = _cena(tamanho - 2 * espessura)
    imagem.paste(miolo, (espessura, espessura))
    return imagem


class MolduraTests(unittest.TestCase):

    def test_moldura_branca_e_cortada(self):
        imagem = _com_moldura((238, 236, 230))
        self.assertIsNotNone(composicao.moldura(imagem))
        cortada = composicao.sem_moldura(imagem)
        self.assertLess(cortada.size[0], 1024 - 90)
        self.assertGreater(cortada.size[0], 1024 - 140)

    def test_moldura_escura_de_filme_e_cortada(self):
        imagem = _com_moldura((8, 8, 8), espessura=30)
        self.assertIsNotNone(composicao.moldura(imagem))
        self.assertLess(composicao.sem_moldura(imagem).size[1], 1024 - 55)

    def test_foto_sem_moldura_fica_igual(self):
        imagem = _cena()
        self.assertIsNone(composicao.moldura(imagem))
        self.assertIs(imagem, composicao.sem_moldura(imagem))

    def test_parede_clara_num_lado_so_nao_e_moldura(self):
        imagem = _cena()
        ImageDraw.Draw(imagem).rectangle((0, 0, 1023, 120), fill=(240, 240, 240))
        self.assertIsNone(composicao.moldura(imagem))

    def test_o_render_tira_a_moldura_ao_abrir_a_cena(self):
        fonte = inspect.getsource(renderer.VideoRenderer._cena_frames)
        self.assertLess(fonte.index("Image.open(caminho)"),
                        fonte.index("sem_moldura(fonte)"))


if __name__ == "__main__":
    unittest.main()
