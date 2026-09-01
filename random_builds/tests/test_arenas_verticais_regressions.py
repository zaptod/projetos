# -*- coding: utf-8 -*-
"""As arenas do video sao 9:16, existem no motor e tem o mesmo tamanho.

`runner.ARENAS_DE_VIDEO` repete os nomes em vez de importar de
`neural_fights.core.arena` (importar o motor puxaria pygame para quem so gera
dados). Estes testes sao o contrato que substitui aquele import: se alguem
renomear, redimensionar ou mudar a proporcao de uma arena vertical no motor,
falha aqui em vez de sair um video com o lutador do tamanho de uma formiga.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
from builds.tournament.runner import ARENAS_DE_ESTREIA, ARENAS_DE_VIDEO  # noqa: E402

# 1080x1920: a proporcao que a camera presa precisa encaixar sem faixa morta.
RAZAO_9_16 = 9 / 16
TOLERANCIA = 0.001


def _arenas():
    from neural_fights.core.arena import ARENAS, ARENAS_VERTICAIS
    return ARENAS, ARENAS_VERTICAIS


class ArenasVerticaisTests(unittest.TestCase):
    def test_as_arenas_do_video_existem_no_motor(self):
        arenas, _ = _arenas()
        for nome in ARENAS_DE_VIDEO:
            self.assertIn(nome, arenas,
                          f"{nome} sumiu de core.arena.ARENAS")

    def test_runner_e_motor_concordam_na_lista(self):
        """A duplicacao dos nomes so e aceitavel enquanto as duas baterem."""
        _, verticais = _arenas()
        self.assertEqual(tuple(ARENAS_DE_VIDEO), tuple(verticais))

    def test_proporcao_e_9_por_16(self):
        arenas, _ = _arenas()
        for nome in ARENAS_DE_VIDEO:
            cfg = arenas[nome]
            razao = cfg.largura / cfg.altura
            self.assertAlmostEqual(
                razao, RAZAO_9_16, delta=TOLERANCIA,
                msg=(f"{nome} e {cfg.largura}x{cfg.altura} (razao {razao:.4f}); "
                     f"fora de 9:16 a camera presa deixa faixa morta"))

    def test_todas_tem_o_mesmo_tamanho(self):
        """Tamanhos diferentes = legibilidade diferente a cada estreia."""
        arenas, _ = _arenas()
        tamanhos = {(arenas[n].largura, arenas[n].altura) for n in ARENAS_DE_VIDEO}
        self.assertEqual(len(tamanhos), 1,
                         f"as verticais divergiram de tamanho: {tamanhos}")

    def test_a_camera_presa_usa_o_zoom_todo(self):
        """A arena precisa CABER e ENCHER: zoom no teto, sem sobra grosseira."""
        import pygame
        pygame.init()
        from neural_fights.effects.camera import Câmera
        from neural_fights.utils.config import PPM

        arenas, _ = _arenas()
        largura_tela, altura_tela = 1080, 1920
        for nome in ARENAS_DE_VIDEO:
            cfg = arenas[nome]
            cam = Câmera(largura_tela, altura_tela)
            cam.set_arena_bounds(cfg.largura / 2, cfg.altura / 2,
                                 cfg.largura, cfg.altura)
            # Cabe: a arena inteira dentro do quadro.
            self.assertLessEqual(cfg.largura * PPM * cam.zoom, largura_tela + 1)
            self.assertLessEqual(cfg.altura * PPM * cam.zoom, altura_tela + 1)
            # Enche: >=70% dos DOIS eixos. O clamp antigo (zoom <= 1.0) dava
            # 47% da largura e e exatamente o que este teste impede de voltar.
            self.assertGreaterEqual(cfg.largura * PPM * cam.zoom / largura_tela, 0.70,
                                    f"{nome} nao enche a largura")
            self.assertGreaterEqual(cfg.altura * PPM * cam.zoom / altura_tela, 0.70,
                                    f"{nome} nao enche a altura")

    def test_estreia_sorteia_do_catalogo_vertical(self):
        for nome in ARENAS_DE_ESTREIA:
            self.assertIn(nome, ARENAS_DE_VIDEO)


class CameraPorPerfilTests(unittest.TestCase):
    def test_estreia_no_celular_e_camera_presa(self):
        from builds.tournament.runner import camera_do_perfil, config_gameplay
        cfg = config_gameplay(None)
        self.assertEqual(camera_do_perfil(cfg, "estreia", "celular"), "ARENA")

    def test_o_resto_continua_no_diretor(self):
        from builds.tournament.runner import camera_do_perfil, config_gameplay
        cfg = config_gameplay(None)
        self.assertEqual(camera_do_perfil(cfg, "estreia", "normal"), "DIRETOR")
        self.assertEqual(camera_do_perfil(cfg, "torneio", "celular"), "DIRETOR")
        self.assertEqual(camera_do_perfil(cfg, "luta", "celular"), "DIRETOR")


if __name__ == "__main__":
    unittest.main()
