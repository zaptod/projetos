# -*- coding: utf-8 -*-
"""Regressões do eixo mobilidade no motor (Onda 10B).

O eixo 'mobilidade' da personalidade (0-1) passa a existir no corpo: dash
mais barato/frequente/forte, giro mais rápido, um pouco mais de velocidade.
Sem brain (dummy/manual) o corpo é neutro.
"""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from neural_fights.utils.config import (
    COOLDOWN_DASH_S,
    CUSTO_ESTAMINA_DASH,
    DASH_MOB_CD_FATOR,
    DASH_MOB_CUSTO_FATOR,
    DASH_MOB_FORCA_FATOR,
    VEL_MOB_FATOR,
)
from tests import test_remaining_skill_regressions as _helpers


def _lutador(mob=None):
    p = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
    if mob is not None:
        p.brain = SimpleNamespace(perfil={"mobilidade": mob}, dir_circular=1)
    return p


class MobilidadeNoMotorTests(unittest.TestCase):
    def test_sem_brain_e_neutro(self):
        p = _lutador()
        self.assertEqual(p._mobilidade_perfil(), 0.0)
        base = p.velocidade_movimento_base
        self.assertAlmostEqual(p.get_velocidade_movimento(), base, places=6)

    def test_mobilidade_sobe_velocidade(self):
        p = _lutador(mob=1.0)
        base = p.velocidade_movimento_base
        self.assertAlmostEqual(
            p.get_velocidade_movimento(), base * (1.0 + VEL_MOB_FATOR), places=6
        )

    def test_dash_cd_custo_e_forca_escalam_com_mobilidade(self):
        neutro = _lutador(mob=0.0)
        agil = _lutador(mob=0.8)
        for p in (neutro, agil):
            p.estamina = 100.0
            p.dash_cooldown = 0.0
            self.assertTrue(p.iniciar_dash(0.0))
        self.assertAlmostEqual(neutro.dash_cooldown, COOLDOWN_DASH_S, places=6)
        self.assertAlmostEqual(
            agil.dash_cooldown, COOLDOWN_DASH_S * (1.0 - DASH_MOB_CD_FATOR * 0.8), places=6
        )
        self.assertAlmostEqual(100.0 - neutro.estamina, CUSTO_ESTAMINA_DASH, places=6)
        self.assertAlmostEqual(
            100.0 - agil.estamina,
            CUSTO_ESTAMINA_DASH * (1.0 - DASH_MOB_CUSTO_FATOR * 0.8), places=6,
        )
        self.assertAlmostEqual(
            agil.vel[0] / neutro.vel[0], 1.0 + DASH_MOB_FORCA_FATOR * 0.8, places=6
        )

    def test_giro_por_classe_e_mobilidade(self):
        lento = _lutador(mob=0.0)
        rapido = _lutador(mob=1.0)
        alvo = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=0.0, y=10.0)
        for p, giro in ((lento, 10.0), (rapido, 20.0)):
            p.class_data = dict(p.class_data, vel_giro=giro)
            p.angulo_olhar = 0.0
            # Stun pula IA/movimento; o giro do olhar acontece antes.
            p.stun_timer = 1.0
            p.update(1 / 60, alvo)
        # O alvo esta a 90 graus; quem gira mais rapido virou mais.
        self.assertGreater(abs(rapido.angulo_olhar), abs(lento.angulo_olhar) * 1.8)

    def test_perfil_invalido_nao_quebra(self):
        p = _lutador()
        p.brain = SimpleNamespace(perfil=None)
        self.assertEqual(p._mobilidade_perfil(), 0.0)
        p.brain = SimpleNamespace(perfil={"mobilidade": "x"})
        self.assertEqual(p._mobilidade_perfil(), 0.0)
        p.brain = SimpleNamespace(perfil={"mobilidade": 7.0})
        self.assertEqual(p._mobilidade_perfil(), 1.0)


if __name__ == "__main__":
    unittest.main()
