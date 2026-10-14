# -*- coding: utf-8 -*-
"""O veredito do duelo no terco de baixo (14/10/2026, achado do conferente).

O nome do vencedor era desenhado no MEIO da tela (0,5 da altura) e, com a
camera DIRETOR pos-K.O. enquadrando a festa do vencedor, passava por cima do
rosto dele. A camera agora poe a festa nos 70% de cima
(``Camera.diretor_pos_ko_area``) e o veredito desce para o terco de baixo.
"""
from __future__ import annotations

import unittest

from PIL import Image

from builds.generation.session_generator import load_config
from builds.video.renderer import VEREDITO_ALTURA, VideoRenderer


class VereditoNoTercoDeBaixoTests(unittest.TestCase):
    def _caixa(self, perfil):
        renderer = VideoRenderer(load_config("render.json"), perfil)
        ver = renderer._veredito_preparado({"veredito": {
            "vencedor": "Aurelia Argalacern", "ko_type": "KO", "cartel_apos": "1V-0D",
            "de": 0.0}})
        img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
        renderer._desenhar_veredito(img, ver, 1.0)
        return img.getchannel("A").getbbox(), renderer.height

    def test_o_veredito_fica_abaixo_da_area_da_festa(self):
        from neural_fights.effects.camera import Câmera

        area_baixo = Câmera(1080, 1920).diretor_pos_ko_area[3]
        for perfil in ("celular", "normal"):
            with self.subTest(perfil=perfil):
                caixa, altura = self._caixa(perfil)
                self.assertIsNotNone(caixa)                 # desenhou algo
                self.assertGreaterEqual(caixa[1], area_baixo * altura)
                self.assertLessEqual(caixa[3], altura)      # e cabe na tela

    def test_a_altura_saiu_do_meio(self):
        self.assertGreater(VEREDITO_ALTURA, 0.7)


if __name__ == "__main__":
    unittest.main()
