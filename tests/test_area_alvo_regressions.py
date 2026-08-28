# -*- coding: utf-8 -*-
"""Regressões da geometria de cast (Onda 10D).

Área cai no ALVO (posição prevista, até ALCANCE_CAST_PADRAO), não no pé
do conjurador — salvo `centrado_no_caster`. Dash de skill sai na direção
do PROPÓSITO (fugir = longe, engajar = perto parando no alcance,
reposicionar = lateral) e nunca atravessa parede/obstáculo.
"""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from neural_fights.core.skills import get_skill_data
from neural_fights.utils.config import ALCANCE_CAST_PADRAO
from tests import test_remaining_skill_regressions as _helpers


class _ArenaFake:
    """Arena de contrato: só x <= limite é jogável; caixa sólida em (5, 5)."""

    def __init__(self, limite_x=10.0):
        self.limite_x = limite_x

    def ponto_dentro(self, x, y, margem=0.3):
        return 0.0 + margem <= x <= self.limite_x - margem and -50 <= y <= 50

    def colide_obstaculo(self, x, y, raio):
        if abs(x - 5.0) < 0.75 + raio and abs(y - 5.0) < 0.75 + raio:
            return SimpleNamespace(tipo="caixa")
        return None


def _par(dist=3.0):
    p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0, y=0.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=dist, y=0.0)
    p1.alcance_ideal = 1.5
    return p1, p2


class PontoAlvoAreaTests(unittest.TestCase):
    def test_area_cai_no_alvo_previsto(self):
        p1, p2 = _par(3.0)
        p2.vel = [2.0, 0.0]
        data = get_skill_data("Slow Motion")
        x, y = p1._ponto_alvo_area(data, p2)
        self.assertGreater(x, 3.0)          # à frente do alvo (previsão)
        self.assertLess(x, 3.0 + 2.0 * 0.5)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_clamp_no_alcance_de_cast(self):
        p1, p2 = _par(12.0)
        data = dict(get_skill_data("Slow Motion"))
        x, y = p1._ponto_alvo_area(data, p2)
        self.assertAlmostEqual(math.hypot(x - p1.pos[0], y - p1.pos[1]), ALCANCE_CAST_PADRAO, places=5)

    def test_centrado_no_caster_fica_no_pe(self):
        p1, p2 = _par(3.0)
        data = get_skill_data("Explosão Nova")
        self.assertTrue(data.get("centrado_no_caster"))
        self.assertEqual(p1._ponto_alvo_area(data, p2), (p1.pos[0], p1.pos[1]))

    def test_sem_alvo_fica_no_pe(self):
        p1, _ = _par(3.0)
        data = get_skill_data("Slow Motion")
        self.assertEqual(p1._ponto_alvo_area(data, None), (p1.pos[0], p1.pos[1]))

    def test_area_nao_cai_fora_da_arena(self):
        p1, p2 = _par(3.0)
        p2.pos = [11.5, 0.0]
        p1.arena_ref = _ArenaFake(limite_x=10.0)
        x, y = p1._ponto_alvo_area(get_skill_data("Slow Motion"), p2)
        self.assertLessEqual(x, 10.0)

    def test_cast_de_area_pela_skill_de_classe_cai_no_alvo(self):
        p1, p2 = _par(4.0)
        _helpers.RemainingSkillRegressionTests._add_class_skill(p1, "Slow Motion")
        self.assertTrue(p1.usar_skill_classe("Slow Motion", alvo=p2))
        area = p1.buffer_areas[-1]
        self.assertGreater(area.x, 3.0)
        self.assertLess(abs(area.x - p2.pos[0]), 1.0)


class DirecaoDashTests(unittest.TestCase):
    def test_escape_sai_para_longe(self):
        p1, p2 = _par(2.0)
        data = get_skill_data("Teleporte Relâmpago")
        rad, dist = p1._direcao_dash(data, "ESCAPE", p2, 0.0)
        self.assertLess(math.cos(rad), -0.5)
        self.assertAlmostEqual(dist, float(data["distancia"]))

    def test_escape_escolhe_direcao_com_arena(self):
        p1, p2 = _par(2.0)
        p1.pos = [1.0, 0.0]
        p2.pos = [3.0, 0.0]
        p1.arena_ref = _ArenaFake(limite_x=10.0)   # atrás (x<0) não é jogável
        data = get_skill_data("Teleporte Relâmpago")
        rad, dist = p1._direcao_dash(data, "ESCAPE", p2, 0.0)
        px = p1.pos[0] + math.cos(rad) * dist
        py = p1.pos[1] + math.sin(rad) * dist
        self.assertTrue(p1.arena_ref.ponto_dentro(px, py, 0.6))

    def test_engage_vai_ao_alvo_parando_no_alcance(self):
        p1, p2 = _par(5.0)
        data = get_skill_data("Teleporte Relâmpago")
        rad, dist = p1._direcao_dash(data, "ENGAGE", p2, 0.0)
        self.assertGreater(math.cos(rad), 0.99)
        self.assertLessEqual(dist, 5.0 - p1.alcance_ideal * 0.8 + 1e-6)
        self.assertLessEqual(dist, float(data["distancia"]))

    def test_reposicionar_e_lateral(self):
        p1, p2 = _par(3.0)
        p1.brain = SimpleNamespace(dir_circular=1)
        data = get_skill_data("Teleporte Relâmpago")
        rad, _ = p1._direcao_dash(data, "REPOSICIONAR", p2, 0.0)
        self.assertLess(abs(math.cos(rad)), 0.05)

    def test_dash_nao_atravessa_parede(self):
        p1, _ = _par(3.0)
        p1.pos = [8.0, 0.0]
        p1.arena_ref = _ArenaFake(limite_x=10.0)
        destino = p1._destino_dash_valido((8.0, 0.0), (14.0, 0.0))
        self.assertLessEqual(destino[0], 10.0)
        self.assertGreaterEqual(destino[0], 8.0)

    def test_dash_de_fuga_pela_skill_de_classe(self):
        p1, p2 = _par(2.0)
        _helpers.RemainingSkillRegressionTests._add_class_skill(p1, "Teleporte Relâmpago")
        x0 = p1.pos[0]
        self.assertTrue(p1.usar_skill_classe("Teleporte Relâmpago", alvo=p2, proposito="ESCAPE"))
        self.assertLess(p1.pos[0], x0)   # foi para longe do alvo (+x)


if __name__ == "__main__":
    unittest.main()
