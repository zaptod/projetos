# -*- coding: utf-8 -*-
"""O veredito do duelo na zona segura (14/10/2026, achado do conferente).

O nome do vencedor era desenhado no MEIO da tela (0,5 da altura) e, com a
camera DIRETOR pos-K.O. enquadrando a festa do vencedor, passava por cima do
rosto dele. Descer para 0,80 o jogava na faixa que o TikTok e o YouTube
Shorts cobrem (legenda, nome do canal e botoes: os ~20% de baixo e a coluna
de ~12% da direita). Agora:

- o veredito fica INTEIRO entre 62% e 76% da altura, longe da faixa direita;
- a camera pos-K.O. poe a festa (rosto, pulo, nome e confete) nos 60% de
  cima e fora da faixa direita (``Camera.diretor_pos_ko_area``);
- o que o duelo ja desenha no alto (HUD, identidade, callouts) nao chega na
  faixa do veredito.
"""
from __future__ import annotations

import unittest

from PIL import Image

from builds.generation.session_generator import load_config
from builds.video.renderer import (VEREDITO_ZONA, ZONA_DAS_PLATAFORMAS,
                                   VideoRenderer)

TOPO, BAIXO = VEREDITO_ZONA
DIREITA = 1.0 - ZONA_DAS_PLATAFORMAS["direita"]


class VereditoNaZonaSeguraTests(unittest.TestCase):
    def _renderer(self, perfil):
        return VideoRenderer(load_config("render.json"), perfil)

    def _caixa(self, perfil, nome="Aurelia Argalacern", cartel="1V-0D"):
        renderer = self._renderer(perfil)
        ver = renderer._veredito_preparado({"veredito": {
            "vencedor": nome, "ko_type": "KO", "cartel_apos": cartel, "de": 0.0}})
        img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
        renderer._desenhar_veredito(img, ver, 1.0)
        return img.getchannel("A").getbbox(), renderer

    def test_o_veredito_fica_inteiro_na_faixa_e_longe_dos_botoes(self):
        for perfil in ("celular", "normal"):
            for nome in ("Aurelia Argalacern", "Kuro", "Genevieve o Destruidor #2"):
                with self.subTest(perfil=perfil, nome=nome):
                    caixa, r = self._caixa(perfil, nome)
                    self.assertIsNotNone(caixa)                    # desenhou algo
                    self.assertGreaterEqual(caixa[1], TOPO * r.height)
                    self.assertLessEqual(caixa[3], BAIXO * r.height)
                    self.assertLessEqual(caixa[2], DIREITA * r.width)
                    # e fora dos 20% de baixo das plataformas
                    self.assertLessEqual(caixa[3], (1 - ZONA_DAS_PLATAFORMAS["baixo"]) * r.height)

    def test_sem_cartel_tambem_cabe(self):
        renderer = self._renderer("celular")
        ver = renderer._veredito_preparado({"veredito": {"vencedor": "Kuro", "de": 0.0}})
        img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
        renderer._desenhar_veredito(img, ver, 1.0)
        caixa = img.getchannel("A").getbbox()
        self.assertGreaterEqual(caixa[1], TOPO * renderer.height)
        self.assertLessEqual(caixa[3], BAIXO * renderer.height)

    def test_a_festa_do_vencedor_fica_acima_do_veredito_e_fora_dos_botoes(self):
        from neural_fights.effects.camera import Câmera

        x0, y0, x1, y1 = Câmera(1080, 1920).diretor_pos_ko_area
        self.assertLessEqual(y1, TOPO)        # o rosto nunca cruza o veredito
        self.assertLessEqual(x1, DIREITA)     # nem a coluna de botoes

    def test_hud_identidade_e_callouts_nao_chegam_na_faixa(self):
        """O que o duelo ja desenha no alto termina antes de 62%."""
        renderer = self._renderer("celular")
        evento = {"callouts": [{"t": 0.0, "texto": "K.O.", "duracao": 1.0},
                               {"t": 0.0, "texto": "ACABOU", "duracao": 1.0}],
                  "identidade": {"ate": 1.5,
                                 "p1": {"arma": "Machado de Guerra", "classe": "Berserker",
                                        "cartel": "0V-0D"},
                                 "p2": {"arma": "Agulhas", "classe": "Assassino",
                                        "cartel": "1V-0D"}}}
        for callout in renderer._callouts_preparados(evento):
            for t in (0.0, 0.05, 0.5):          # com o pop-in de 1,35x
                img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
                renderer._desenhar_callout(img, callout, t)
                caixa = img.getchannel("A").getbbox()
                if caixa:
                    self.assertLess(caixa[3], TOPO * renderer.height)
        ident = renderer._identidade_preparada(evento)
        img = Image.new("RGBA", (renderer.width, renderer.height), (0, 0, 0, 0))
        renderer._desenhar_identidade(img, ident, 0.0)
        self.assertLess(img.getchannel("A").getbbox()[3], TOPO * renderer.height)


if __name__ == "__main__":
    unittest.main()
