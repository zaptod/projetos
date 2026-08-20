"""Regressoes do contrato unico de atributos de personagem."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from neural_fights.models.characters import Personagem


class CharacterStatsRegressionTests(unittest.TestCase):
    CLASS_DATA = {
        "mod_forca": 1.2,
        "mod_velocidade": 1.25,
        "mod_vida": 1.5,
        "mod_mana": 1.1,
        "regen_mana": 3.0,
    }

    def _character(self, weapon_weight: float = 2.0) -> Personagem:
        with patch("neural_fights.models.characters.get_class_data", return_value=self.CLASS_DATA):
            return Personagem("Teste", 2, 5, 4, peso_arma_cache=weapon_weight)

    def test_life_modifier_is_applied_exactly_once(self) -> None:
        character = self._character()

        # Re-pino O4-O6: ESCALA_VIDA_GLOBAL = 2.8 (knob global de TTK,
        # varrido no harness a cada fase; a escala de dano de skill x2 da
        # fase 2 acelera as lutas ~20% e o escalar compensa ate o sweep
        # final da onda). Formula: 195.0 * 2.8.
        self.assertEqual(546.0, character.get_vida_max())
        self.assertEqual(15.0, character.resistencia)

    def test_weapon_weight_reduces_runtime_movement_speed(self) -> None:
        light = self._character(weapon_weight=0.0)
        heavy = self._character(weapon_weight=8.0)

        self.assertGreater(light.velocidade, heavy.velocidade)
        self.assertGreater(
            light.get_velocidade_movimento(),
            heavy.get_velocidade_movimento(),
        )

    def test_mana_uses_the_same_contract_exposed_to_runtime(self) -> None:
        character = self._character()

        self.assertAlmostEqual(99.0, character.get_mana_max())


if __name__ == "__main__":
    unittest.main()
