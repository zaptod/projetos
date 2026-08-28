# -*- coding: utf-8 -*-
"""Regressões do wall-splat (Onda 10A).

Corpo LANÇADO (arremesso ou knockback forte) que bate na parede estatela:
stun extra, dano e um momento de câmera. Sem o estado 'lançado', bater na
parede continua sendo só som e partícula.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.effects.camera import Câmera
from neural_fights.simulation.simulacao import Simulador
from neural_fights.utils.config import (
    LANCADO_KNOCKBACK_MIN,
    WALL_SPLAT_INTENSIDADE_MIN,
)
from tests import test_remaining_skill_regressions as _helpers


class _Cam:
    def __init__(self):
        self.shakes = []
        self.momentos = []

    def aplicar_shake(self, *a, **k):
        self.shakes.append(a)

    def aplicar_momento(self, duracao=0.4):
        self.momentos.append(duracao)


def _sim():
    p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=1.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=4.0)
    p1.brain = SimpleNamespace(tempo_combate=3.0, tell_atual=None, raiva=0.0)
    sim = object.__new__(Simulador)
    sim.p1, sim.p2 = p1, p2
    sim.shockwaves = []
    sim.particulas = []
    sim.cam = _Cam()
    sim.arena = None
    return sim


class WallSplatTests(unittest.TestCase):
    def test_so_com_estado_lancado(self):
        sim = _sim()
        vida = sim.p1.vida
        self.assertFalse(sim._processar_wall_splat(sim.p1, 15.0))
        self.assertEqual(sim.p1.vida, vida)
        self.assertEqual(sim.p1.stun_timer, 0.0)

    def test_lancado_estatela_com_stun_dano_contador_e_momento(self):
        sim = _sim()
        p1, p2 = sim.p1, sim.p2
        p1.lancado_por = p2
        p1.lancado_timer = 0.5
        vida = p1.vida
        self.assertTrue(sim._processar_wall_splat(p1, 12.0))
        self.assertGreaterEqual(p1.stun_timer, 0.3)
        self.assertLess(p1.vida, vida)
        self.assertLessEqual(vida - p1.vida, p1.vida_max * 0.08 + 1e-6)
        self.assertEqual(p2.contadores_luta["wall_splats"], 1)
        self.assertEqual(p1.brain.tell_atual["tipo"], "wall_splat")
        self.assertEqual(len(sim.cam.momentos), 1)
        # Um splat por lançamento.
        self.assertEqual(p1.lancado_timer, 0.0)
        self.assertIsNone(p1.lancado_por)
        self.assertFalse(sim._processar_wall_splat(p1, 12.0))

    def test_impacto_fraco_nao_estatela(self):
        sim = _sim()
        sim.p1.lancado_por = sim.p2
        sim.p1.lancado_timer = 0.5
        self.assertFalse(sim._processar_wall_splat(sim.p1, WALL_SPLAT_INTENSIDADE_MIN - 1.0))
        # O estado continua armado para o impacto de verdade.
        self.assertGreater(sim.p1.lancado_timer, 0.0)

    def test_knockback_forte_arma_o_estado_lancado(self):
        p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=1.0)
        p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=2.0)
        p1.tomar_dano(80.0, 1.0, 0.0, "NORMAL", atacante=p2,
                      metadata_impacto={"eh_corpo_a_corpo": True})
        self.assertGreater(p1.lancado_timer, 0.0)
        self.assertIs(p1.lancado_por, p2)
        self.assertGreaterEqual(LANCADO_KNOCKBACK_MIN, 15.0)

    def test_estado_lancado_expira(self):
        p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=1.0)
        p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=2.0)
        p1.lancado_por = p2
        p1.lancado_timer = 0.1
        for _ in range(12):
            p1.update(1 / 60, p2)
        self.assertEqual(p1.lancado_timer, 0.0)
        self.assertIsNone(p1.lancado_por)


class CameraMomentoTests(unittest.TestCase):
    def test_momento_e_push_in_curto_so_no_diretor(self):
        cam = Câmera(1080, 1920)
        cam.modo = "DIRETOR"
        cam.aplicar_momento(0.4)
        self.assertGreaterEqual(cam._momento_timer, 0.4)
        p1 = SimpleNamespace(pos=[6.0, 8.0], morto=False, z=0.0, vel=[0.0, 0.0])
        p2 = SimpleNamespace(pos=[9.0, 8.0], morto=False, z=0.0, vel=[0.0, 0.0])
        for _ in range(30):
            cam.atualizar(1 / 60, p1, p2)
        self.assertLess(cam._momento_timer, 0.4)
        # A câmera só lê: as posições dos lutadores não mudam.
        self.assertEqual(p1.pos, [6.0, 8.0])
        self.assertEqual(p2.pos, [9.0, 8.0])


if __name__ == "__main__":
    unittest.main()
