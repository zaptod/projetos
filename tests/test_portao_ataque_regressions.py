# -*- coding: utf-8 -*-
"""Regressões do portão de ataque (Onda 10A).

Em alcance, sem ameaça vindo e com vida para arriscar, ninguém segura um
verbo passivo por mais de 0,6s: o teto de passividade vira golpe (P1, com
tell) — o micro-detector local do cara-a-cara.
"""

from __future__ import annotations

import unittest

from neural_fights.ai.brain import AIBrain
from tests import test_remaining_skill_regressions as _helpers


class _RngNuncaAtaca:
    def random(self):
        return 0.999

    def uniform(self, a, b):
        return a

    def choice(self, opcoes):
        return opcoes[0]


def _brain(parent):
    brain = object.__new__(AIBrain)
    brain.parent = parent
    brain.rng = _RngNuncaAtaca()
    brain.tempo_combate = 5.0
    brain._acao_atual = "CIRCULAR"
    brain.janela_ataque = {"aberta": False, "qualidade": 0.0, "tipo": None}
    brain.combo_state = {"em_combo": False, "pode_followup": False,
                         "hits_combo": 0, "timer_followup": 0.0,
                         "ultimo_tipo_ataque": None}
    brain.tracos = []
    brain.quirks = []
    brain.momentum = 0.0
    brain.contadores = {"escritas_aceitas": 0, "escritas_seguradas": 0}
    brain.tell_atual = None
    brain._calcular_alcance_efetivo = lambda: 1.5
    return brain


class PortaoDeAtaqueTests(unittest.TestCase):
    def _cenario(self):
        p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
        p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=1.0)
        p1.atacando = False
        p1.cooldown_ataque = 0.0
        return p1, p2, _brain(p1)

    def test_passividade_em_alcance_vira_golpe_em_0_6s(self):
        p1, p2, brain = self._cenario()
        for _ in range(int(0.7 * 60)):
            brain._avaliar_e_executar_ataque(1 / 60, 1.0, p2)
            brain.tempo_combate += 1 / 60
        self.assertEqual(brain.acao_atual, "MATAR")
        self.assertEqual(brain._acao_hold_prio, 1)
        self.assertEqual(p1.contadores_luta["iniciativas"], 1)
        self.assertEqual(brain.tell_atual["tipo"], "iniciativa")

    def test_nao_forca_com_ameaca_vindo(self):
        p1, p2, brain = self._cenario()
        p2.atacando = True
        for _ in range(int(0.9 * 60)):
            brain._avaliar_e_executar_ataque(1 / 60, 1.0, p2)
            brain.tempo_combate += 1 / 60
        self.assertEqual(brain.acao_atual, "CIRCULAR")
        self.assertEqual(p1.contadores_luta.get("iniciativas", 0), 0)

    def test_nao_forca_com_vida_critica(self):
        p1, p2, brain = self._cenario()
        p1.vida = p1.vida_max * 0.2
        for _ in range(int(0.9 * 60)):
            brain._avaliar_e_executar_ataque(1 / 60, 1.0, p2)
            brain.tempo_combate += 1 / 60
        self.assertEqual(brain.acao_atual, "CIRCULAR")

    def test_verbo_ofensivo_zera_o_relogio(self):
        p1, p2, brain = self._cenario()
        for _ in range(int(0.5 * 60)):
            brain._avaliar_e_executar_ataque(1 / 60, 1.0, p2)
            brain.tempo_combate += 1 / 60
        brain._acao_atual = "PRESSIONAR"
        brain._avaliar_e_executar_ataque(1 / 60, 1.0, p2)
        self.assertEqual(brain.tempo_sem_intencao_ofensiva, 0.0)


if __name__ == "__main__":
    unittest.main()
