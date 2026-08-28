# -*- coding: utf-8 -*-
"""Regressões dos obstáculos destrutíveis (Onda 10D).

`Obstaculo.destrutivel`/`hp` existiam e nunca eram lidos. Área, explosão
ou corpo arremessado quebram caixas/barris; a arena copia os obstáculos
POR LUTA (o catálogo ARENAS nunca muta).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.core.arena import ARENAS, Arena
from neural_fights.simulation.simulacao import Simulador
from tests import test_remaining_skill_regressions as _helpers


def _caixa(arena):
    return next(o for o in arena.obstaculos if o.tipo == "caixa")


class ArenaDestrutivelTests(unittest.TestCase):
    def test_copia_por_luta_e_catalogo_intacto(self):
        a1 = Arena(ARENAS["Cyberpunk"])
        a2 = Arena(ARENAS["Cyberpunk"])
        c1 = _caixa(a1)
        self.assertTrue(a1.danificar_obstaculo(c1, 999.0, None))
        self.assertFalse(c1.solido)
        self.assertEqual(c1.tipo, "caixa_quebrado")
        self.assertEqual(c1.hp, 0)
        self.assertEqual(len(a1.eventos_obstaculo), 1)
        # A outra luta e o catálogo continuam inteiros.
        self.assertTrue(_caixa(a2).solido)
        self.assertTrue(all(o.solido for o in ARENAS["Cyberpunk"].obstaculos if o.tipo == "caixa"))

    def test_so_destrutivel_quebra_e_dano_acumula(self):
        arena = Arena(ARENAS["Cyberpunk"])
        pilar = next((o for o in arena.obstaculos if not o.destrutivel), None)
        if pilar is not None:
            self.assertFalse(arena.danificar_obstaculo(pilar, 999.0, None))
            self.assertTrue(pilar.solido)
        caixa = _caixa(arena)
        hp0 = caixa.hp
        self.assertFalse(arena.danificar_obstaculo(caixa, hp0 * 0.5, None))
        self.assertTrue(caixa.solido)
        self.assertTrue(arena.danificar_obstaculo(caixa, hp0, None))

    def test_obstaculos_no_raio(self):
        arena = Arena(ARENAS["Cyberpunk"])
        caixa = _caixa(arena)
        self.assertIn(caixa, arena.obstaculos_no_raio(caixa.x, caixa.y, 0.5))
        self.assertNotIn(caixa, arena.obstaculos_no_raio(caixa.x + 10.0, caixa.y, 0.5))
        arena.danificar_obstaculo(caixa, 999.0, None)
        self.assertNotIn(caixa, arena.obstaculos_no_raio(caixa.x, caixa.y, 0.5))


class SimuladorObstaculoTests(unittest.TestCase):
    def _sim(self):
        p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=1.0)
        p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=4.0)
        p1.brain = SimpleNamespace(tempo_combate=3.0, tell_atual=None, raiva=0.0)
        p2.brain = SimpleNamespace(tempo_combate=3.0, tell_atual=None, raiva=0.0)
        sim = object.__new__(Simulador)
        sim.p1, sim.p2 = p1, p2
        sim.shockwaves = []
        sim.particulas = []
        sim.cam = SimpleNamespace(aplicar_shake=lambda *a, **k: None,
                                  aplicar_momento=lambda *a, **k: None)
        sim.arena = Arena(ARENAS["Cyberpunk"])
        return sim

    def test_corpo_lancado_quebra_a_caixa_e_o_splat_e_mais_leve(self):
        sim = self._sim()
        p1, p2 = sim.p1, sim.p2
        caixa = _caixa(sim.arena)
        sim.arena.ultimo_obstaculo_colidido[id(p1)] = caixa
        p1.lancado_por = p2
        p1.lancado_timer = 0.5
        vida = p1.vida
        self.assertTrue(sim._processar_wall_splat(p1, 12.0))
        self.assertFalse(caixa.solido)
        self.assertLess(p1.stun_timer, 0.3)           # absorvido pela caixa
        self.assertLess(vida - p1.vida, p1.vida_max * 0.04)
        sim._drenar_eventos_obstaculo()
        self.assertEqual(p2.contadores_luta["obstaculos_destruidos"], 1)
        self.assertEqual(p2.brain.tell_atual["tipo"], "obstaculo")
        self.assertEqual(sim.arena.eventos_obstaculo, [])

    def test_area_ativa_quebra_obstaculo_uma_vez(self):
        sim = self._sim()
        from neural_fights.core.combat import AreaEffect
        caixa = _caixa(sim.arena)
        area = AreaEffect("Explosão Nova", caixa.x, caixa.y, sim.p1)
        area.ativado = True
        area.dano = 999.0
        sim.areas = [area]
        sim.projeteis = []
        sim._atualizar_areas(1 / 60)
        self.assertFalse(caixa.solido)
        self.assertTrue(getattr(area, "_obstaculos_processados", False))


if __name__ == "__main__":
    unittest.main()
