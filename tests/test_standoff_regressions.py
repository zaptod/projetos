# -*- coding: utf-8 -*-
"""Regressões do detector de standoff (Onda 10A).

Cara-a-cara = os dois na faixa de confronto sem HIT REAL. O Simulador
escala: iniciativa → (mais 1s) agarrão se perto / segunda dose se longe.
"""

from __future__ import annotations

import random
import unittest
from types import SimpleNamespace

from neural_fights.ai.brain import AIBrain
from neural_fights.simulation.simulacao import Simulador
from neural_fights.utils.config import (
    STANDOFF_ESCALADA_S,
    STANDOFF_JANELA_S,
)
from tests import test_remaining_skill_regressions as _helpers


class _RngFixo:
    def __init__(self, valor=0.3):
        self.valor = valor

    def random(self):
        return self.valor

    def uniform(self, a, b):
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


class _BrainEspiao:
    """Brain de contrato: registra as iniciativas pedidas pelo Simulador."""

    def __init__(self, agressao=0.5, alcance=1.5):
        self.chamadas = []
        self._agressao = agressao
        self._alcance = alcance
        self.tempo_combate = 5.0
        self.tell_atual = None

    def agressividade_efetiva(self):
        return self._agressao

    def _calcular_alcance_efetivo(self):
        return self._alcance

    def forcar_iniciativa(self, distancia, inimigo, *, permitir_dash=True, hold_s=0.6):
        self.chamadas.append((distancia, permitir_dash, hold_s))
        return True


def _sim(dist=2.0, agressao=(0.7, 0.3)):
    p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=dist)
    p1.brain = _BrainEspiao(agressao[0])
    p2.brain = _BrainEspiao(agressao[1])
    for p in (p1, p2):
        p.rng_runtime = _RngFixo(0.3)
    sim = object.__new__(Simulador)
    sim.p1, sim.p2 = p1, p2
    sim.shockwaves = []
    sim.particulas = []
    sim.cam = SimpleNamespace(aplicar_shake=lambda *a, **k: None,
                              aplicar_momento=lambda *a, **k: None)
    sim._tempo_clinch = 0.0
    sim._clinch_cooldown = 0.0
    sim._agarrao = None
    sim._agarrao_cooldown = 0.0
    sim._standoff_t = 0.0
    sim._standoff_t_fase = 0.0
    sim._standoff_fase = 0
    sim._standoff_fora = 0.0
    sim._standoff_cooldown = 0.0
    sim._standoff_ids = (0, 0)
    sim._standoff_hp_ant = None
    sim.standoff_estado = {"em_range": False, "ninguem_atacando": False,
                           "fase": 0, "t": 0.0}
    sim.arena = None
    return sim


def _rodar(sim, segundos):
    frames = int(round(segundos * 60))
    for _ in range(frames):
        sim._detectar_standoff(1 / 60)


class DetectorTests(unittest.TestCase):
    def test_em_faixa_sem_hit_escala_para_iniciativa_do_mais_afoito(self):
        sim = _sim(dist=2.0, agressao=(0.7, 0.3))
        _rodar(sim, STANDOFF_JANELA_S + 0.1)
        self.assertEqual(len(sim.p1.brain.chamadas), 1)
        self.assertEqual(len(sim.p2.brain.chamadas), 0)
        self.assertEqual(sim.standoff_estado["fase"], 1)
        self.assertTrue(sim.standoff_estado["em_range"])

    def test_hit_real_zera_o_relogio(self):
        sim = _sim(dist=2.0)
        _rodar(sim, 1.0)
        self.assertGreater(sim.standoff_estado["t"], 0.9)
        sim.p2.contadores_luta["hits_sofridos"] = sim.p2.contadores_luta.get("hits_sofridos", 0) + 1
        sim._detectar_standoff(1 / 60)
        self.assertEqual(sim.standoff_estado["t"], 0.0)
        self.assertEqual(sim.standoff_estado["fase"], 0)
        self.assertEqual(len(sim.p1.brain.chamadas), 0)

    def test_segunda_escalada_vira_agarrao_quando_perto(self):
        sim = _sim(dist=2.0)
        _rodar(sim, STANDOFF_JANELA_S + STANDOFF_ESCALADA_S + 0.2)
        self.assertEqual(len(sim.p1.brain.chamadas), 1)
        self.assertIsNotNone(sim._agarrao)
        self.assertEqual(sim._agarrao["origem"], "standoff")

    def test_longe_escala_para_os_dois_aproximarem(self):
        sim = _sim(dist=6.0)
        _rodar(sim, 2 * STANDOFF_JANELA_S + STANDOFF_ESCALADA_S + 0.2)
        self.assertGreaterEqual(len(sim.p1.brain.chamadas), 1)
        self.assertGreaterEqual(len(sim.p2.brain.chamadas), 1)
        self.assertIsNone(sim._agarrao)

    def test_fora_de_9m_nao_conta(self):
        sim = _sim(dist=11.0)
        _rodar(sim, 4.0)
        self.assertEqual(sim.standoff_estado["t"], 0.0)
        self.assertEqual(len(sim.p1.brain.chamadas), 0)

    def test_ranged_so_e_perto_ate_3m(self):
        """Arqueiro a 3,5 m: não é faixa de confronto (sem agarrão), mas
        é banda LONGE — o kiting sem hit também convoca iniciativa."""
        sim = _sim(dist=3.5)
        sim.p1.dados.arma_obj = SimpleNamespace(tipo="Arco")
        _rodar(sim, 2 * STANDOFF_JANELA_S + STANDOFF_ESCALADA_S + 0.2)
        self.assertFalse(sim.standoff_estado["em_range"])
        self.assertEqual(sim.standoff_estado["banda"], "longe")
        self.assertIsNone(sim._agarrao)
        self.assertGreaterEqual(len(sim.p1.brain.chamadas) + len(sim.p2.brain.chamadas), 2)

    def test_cooldown_impede_metralhadora(self):
        sim = _sim(dist=2.0)
        _rodar(sim, STANDOFF_JANELA_S + 0.1)
        self.assertEqual(len(sim.p1.brain.chamadas), 1)
        # Standoff dissolve e volta: dentro do cooldown, nada.
        sim.p2.contadores_luta["hits_sofridos"] = sim.p2.contadores_luta.get("hits_sofridos", 0) + 1
        _rodar(sim, STANDOFF_JANELA_S + 0.1)
        self.assertEqual(len(sim.p1.brain.chamadas), 1)


class ForcarIniciativaTests(unittest.TestCase):
    def _brain(self, lutador):
        brain = object.__new__(AIBrain)
        brain.parent = lutador
        brain.rng = random.Random(3)
        brain.tempo_combate = 4.0
        brain._acao_atual = "CIRCULAR"
        brain.contadores = {"escritas_aceitas": 0, "escritas_seguradas": 0}
        brain.tell_atual = None
        return brain

    def test_escreve_p1_e_conta(self):
        p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
        p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=1.0)
        p1.alcance_ideal = 1.5
        brain = self._brain(p1)
        self.assertTrue(brain.forcar_iniciativa(1.0, p2, permitir_dash=False))
        self.assertEqual(brain.acao_atual, "MATAR")
        self.assertEqual(brain._acao_hold_prio, 1)
        self.assertGreater(brain._acao_hold_ate, brain.tempo_combate)
        self.assertEqual(p1.contadores_luta["iniciativas"], 1)
        self.assertEqual(brain.tell_atual["tipo"], "iniciativa")

    def test_meia_distancia_da_dash_de_aproximacao(self):
        p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
        p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=3.5)
        p1.alcance_ideal = 1.5
        brain = self._brain(p1)
        dashes_antes = p1.contadores_luta.get("dashes", 0)
        brain.forcar_iniciativa(3.5, p2, permitir_dash=True)
        self.assertEqual(p1.contadores_luta.get("dashes", 0), dashes_antes + 1)
        self.assertEqual(brain.acao_atual, "PRESSIONAR")
        self.assertGreater(p1.vel[0], 0.0)


if __name__ == "__main__":
    unittest.main()
