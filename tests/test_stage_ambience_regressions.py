# -*- coding: utf-8 -*-
"""Contratos do Passe 7 do programa de arte (o palco e os dois formatos).

O que se trava aqui: TODAS as arenas do catálogo desenham sem explodir
(cobre os 11 tipos de obstáculo que caíam no retângulo genérico e o chão
retangular em camadas); o clima ambiental respeita o teto e some quando
a arena não declara efeitos; e o --portrait do CLI liga o portrait_mode
que era hardcoded False.
"""

import unittest
from types import SimpleNamespace

import pygame

from neural_fights.cli.live import _montar_config, build_parser
from neural_fights.core.arena import ARENAS, Arena
from neural_fights.effects import Câmera
from neural_fights.simulation.simulacao import Simulador


class TodasAsArenasDesenhamTests(unittest.TestCase):
    def test_nenhuma_arena_explode_o_desenho(self) -> None:
        """Cada arena com seus obstáculos reais (altar, cripta, ossos,
        console, rocha...) renderiza — obstáculo novo sem desenho cai no
        fallback, nunca em exceção."""
        surface = pygame.Surface((800, 600))
        cam = Câmera(800, 600)
        for nome, config in ARENAS.items():
            arena = Arena(config)
            arena.desenhar(surface, cam)


class ClimaAmbientalTests(unittest.TestCase):
    def _sim_fake(self, efeitos, bounds=(0.0, 30.0, 0.0, 20.0)):
        min_x, max_x, min_y, max_y = bounds
        arena = SimpleNamespace(
            config=SimpleNamespace(efeitos_especiais=list(efeitos)),
            min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y,
        )
        return SimpleNamespace(
            arena=arena, TETO_AMBIENTE=Simulador.TETO_AMBIENTE
        )

    def test_clima_respeita_o_teto(self) -> None:
        fake = self._sim_fake(["neve", "chuva"])
        for _ in range(600):
            Simulador._atualizar_ambiente(fake, 1 / 60)
        self.assertLessEqual(len(fake._clima), Simulador.TETO_AMBIENTE)
        self.assertGreater(len(fake._clima), 0)

    def test_arena_sem_efeitos_nao_tem_clima(self) -> None:
        fake = self._sim_fake([])
        Simulador._atualizar_ambiente(fake, 1 / 60)
        self.assertEqual(fake._clima, [])

    def test_particulas_ficam_dentro_do_palco(self) -> None:
        """Reciclagem: quem sai dos bounds da arena volta pelo outro
        lado — o clima nunca escorre para fora do palco."""
        fake = self._sim_fake(["chuva"])
        for _ in range(1200):
            Simulador._atualizar_ambiente(fake, 1 / 30)
        for p in fake._clima:
            self.assertGreaterEqual(p["x"], fake.arena.min_x - 1e-6)
            self.assertLessEqual(p["x"], fake.arena.max_x + 1e-6)
            self.assertGreaterEqual(p["y"], fake.arena.min_y - 1e-6)
            self.assertLessEqual(p["y"], fake.arena.max_y + 1e-6)


class PortraitCliTests(unittest.TestCase):
    def test_flag_liga_o_portrait_mode(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--portrait"])
        cfg = _montar_config(["A", "B"], "Arena", False, args.portrait)
        self.assertTrue(cfg["portrait_mode"])

    def test_padrao_continua_16x9(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        cfg = _montar_config(["A", "B"], "Arena", False, args.portrait)
        self.assertFalse(cfg["portrait_mode"])


if __name__ == "__main__":
    unittest.main()
