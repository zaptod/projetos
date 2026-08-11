"""Regressoes para o consumo de Previsao pela IA defensiva."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from neural_fights.ai.brain import AIBrain
from neural_fights.core.combat import Buff
from tests import test_remaining_skill_regressions as _helpers


class PredictionAIRegressionTests(unittest.TestCase):
    _fighter = staticmethod(_helpers.RemainingSkillRegressionTests._fighter)

    @staticmethod
    def _brain(parent):
        brain = object.__new__(AIBrain)
        brain.parent = parent
        brain.modo_berserk = False
        brain.confianca = 0.5
        brain.tracos = ["IMPRUDENTE"]
        brain.leitura_oponente = {"ataque_iminente": True}
        brain.rng = Mock()
        brain.rng.uniform.return_value = 0.2
        brain.rng.random.return_value = 1.0
        brain.tempo_reacao_base = 0.2
        brain.variacao_timing = 0.1
        brain.adrenalina = 0.0
        brain.medo = 0.0
        brain.congelamento = 0.0
        return brain

    def test_prediction_bypasses_human_reaction_delay_and_probability(self):
        defender = self._fighter("Seer")
        attacker = self._fighter("Attacker", x=1.0)
        defender.buffs_ativos.append(Buff("Previsão", defender))
        brain = self._brain(defender)

        with (
            patch.object(
                brain,
                "_analisar_projeteis_vindo",
                return_value={"vindo": False, "urgencia": 0.0},
            ),
            patch.object(
                brain,
                "_analisar_areas_perigo",
                return_value={"perigo": False, "urgencia": 0.0},
            ),
            patch.object(brain, "_calcular_direcao_desvio", return_value=90.0),
            patch.object(brain, "_executar_desvio", return_value=True) as executar,
        ):
            reacted = brain._processar_desvio_inteligente(1.0 / 60.0, 1.0, attacker)

        self.assertTrue(reacted)
        brain.rng.uniform.assert_not_called()
        brain.rng.random.assert_not_called()
        executar.assert_called_once()

    def test_without_prediction_preserves_normal_reaction_gate(self):
        defender = self._fighter("Fighter")
        attacker = self._fighter("Attacker", x=1.0)
        brain = self._brain(defender)

        with (
            patch.object(
                brain,
                "_analisar_projeteis_vindo",
                return_value={"vindo": False, "urgencia": 0.0},
            ),
            patch.object(
                brain,
                "_analisar_areas_perigo",
                return_value={"perigo": False, "urgencia": 0.0},
            ),
            patch.object(brain, "_executar_desvio", return_value=True) as executar,
        ):
            reacted = brain._processar_desvio_inteligente(1.0 / 60.0, 1.0, attacker)

        self.assertFalse(reacted)
        brain.rng.uniform.assert_called_once()
        brain.rng.random.assert_called_once()
        executar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
