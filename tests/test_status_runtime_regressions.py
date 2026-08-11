"""Regression tests for healing, cleansing, and debuff immunity."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.core.combat import AreaEffect, Buff
from neural_fights.core.entities import Lutador
from neural_fights.core.skills import get_skill_data


class StatusRuntimeRegressionTests(unittest.TestCase):
    @staticmethod
    def _fighter(name: str) -> Lutador:
        data = SimpleNamespace(
            nome=name,
            tamanho=1.7,
            forca=5.0,
            mana=5.0,
            resistencia=5.0,
            velocidade=5.0,
            classe="Guerreiro (Forca Bruta)",
            personalidade="Aleatorio",
            nome_arma="",
            arma_obj=None,
        )
        with patch("neural_fights.ai.AIBrain", return_value=None):
            return Lutador(data, 5.0, 5.0)

    def _cast_class_buff(self, fighter: Lutador, skill_name: str) -> None:
        skill_data = get_skill_data(skill_name)
        fighter.skills_classe.append(
            {"nome": skill_name, "custo": 0.0, "data": skill_data}
        )
        fighter.cd_skills[skill_name] = 0.0

        with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(fighter.usar_skill_classe(skill_name))

    @staticmethod
    def _active_timer_families(fighter: Lutador, timers: tuple[str, ...]) -> int:
        return sum(getattr(fighter, timer, 0.0) > 0.0 for timer in timers)

    def test_receber_cura_returns_only_health_actually_restored(self) -> None:
        fighter = self._fighter("Capped healing")
        fighter.vida = fighter.vida_max - 5.0

        self.assertAlmostEqual(fighter.receber_cura(20.0), 5.0)
        self.assertEqual(fighter.vida, fighter.vida_max)
        self.assertEqual(fighter.receber_cura(20.0), 0.0)

    def test_necrosis_blocks_healing_and_expires(self) -> None:
        fighter = self._fighter("Necrotic target")
        enemy = self._fighter("Enemy")
        fighter.vida = fighter.vida_max - 30.0
        fighter._aplicar_efeito_status("NECROSE", duracao=0.1)

        life_before = fighter.vida
        self.assertEqual(fighter.receber_cura(20.0), 0.0)
        self.assertEqual(fighter.vida, life_before)

        fighter.update(0.2, enemy)

        self.assertAlmostEqual(fighter.receber_cura(10.0), 10.0)

    def test_healing_reduction_statuses_use_strongest_modifier_without_compounding(self) -> None:
        status_combinations = (
            ("ENVENENADO", "ENVENENADO"),
            ("MALDITO", "MALDITO"),
            ("ENVENENADO", "MALDITO"),
        )
        for statuses in status_combinations:
            with self.subTest(statuses=statuses):
                fighter = self._fighter(f"Healing reduction {statuses}")
                for status in statuses:
                    fighter._aplicar_efeito_status(status, duracao=5.0)
                fighter.vida = fighter.vida_max - 50.0

                self.assertAlmostEqual(fighter.receber_cura(20.0), 10.0)
                self.assertAlmostEqual(fighter.vida, fighter.vida_max - 40.0)

    def test_regeneration_buff_accepts_cura_tick_alias(self) -> None:
        fighter = self._fighter("Regenerating target")
        fighter.vida = fighter.vida_max - 20.0
        buff = Buff("Regeneração", fighter)

        buff.atualizar(1.0)

        self.assertAlmostEqual(fighter.vida, fighter.vida_max - 12.0)

    def test_purify_clears_debuff_families_and_grants_immunity(self) -> None:
        fighter = self._fighter("Purified target")
        for status in (
            "ENVENENADO",
            "NECROSE",
            "FRACO",
            "VULNERAVEL",
            "ENRAIZADO",
            "CEGO",
            "MEDO",
        ):
            fighter._aplicar_efeito_status(status, duracao=10.0)
        fighter.vida = fighter.vida_max - 20.0

        self._cast_class_buff(fighter, "Purificar")

        self.assertFalse(fighter.dots_ativos)
        for timer in (
            "fraco_timer",
            "vulneravel_timer",
            "enraizado_timer",
            "cego_timer",
            "medo_timer",
        ):
            self.assertEqual(getattr(fighter, timer, 0.0), 0.0, timer)
        self.assertEqual(fighter.slow_fator, 1.0)
        self.assertEqual(fighter.dano_reduzido, 1.0)
        self.assertEqual(fighter.vulnerabilidade, 1.0)
        self.assertAlmostEqual(fighter.receber_cura(5.0), 5.0)
        self.assertAlmostEqual(fighter.imune_debuffs_timer, 3.0)

    def test_cura_maior_removes_only_two_debuff_families(self) -> None:
        fighter = self._fighter("Major heal target")
        timers = ("fraco_timer", "vulneravel_timer", "exposto_timer")
        fighter._aplicar_efeito_status("FRACO", duracao=3.0)
        fighter._aplicar_efeito_status("VULNERAVEL", duracao=2.0)
        fighter._aplicar_efeito_status("EXPOSTO", duracao=1.0)
        self.assertEqual(self._active_timer_families(fighter, timers), 3)

        self._cast_class_buff(fighter, "Cura Maior")

        self.assertEqual(self._active_timer_families(fighter, timers), 1)

    def test_cura_maior_cleanses_necrosis_before_healing(self) -> None:
        fighter = self._fighter("Major heal versus necrosis")
        fighter._aplicar_efeito_status("NECROSE")
        fighter._aplicar_efeito_status("FRACO")
        fighter.vida = fighter.vida_max - 70.0

        self._cast_class_buff(fighter, "Cura Maior")

        self.assertEqual(fighter.cura_bloqueada_timer, 0.0)
        self.assertFalse(any(dot.tipo == "NECROSE" for dot in fighter.dots_ativos))
        self.assertAlmostEqual(fighter.vida, fighter.vida_max - 10.0)

    def test_immunity_blocks_status_and_area_metadata_but_not_damage(self) -> None:
        fighter = self._fighter("Immune target")
        enemy = self._fighter("Enemy")
        fighter.imune_debuffs_timer = 3.0

        fighter._aplicar_efeito_status("ENVENENADO")
        fighter._aplicar_efeito_status("FRACO")
        self.assertFalse(fighter.dots_ativos)
        self.assertEqual(fighter.fraco_timer, 0.0)

        area = AreaEffect("Nenhuma", fighter.pos[0], fighter.pos[1], None)
        area.duracao = 2.0
        area.slow_fator = 0.5
        area.duracao_stun = 1.25
        area.chance_stun = 1.0
        area.duracao_fear = 1.5
        area.tipo_efeito = "ENRAIZADO"
        area.efeito2 = "ENVENENADO"

        with patch("neural_fights.core.combat.random.random", return_value=0.0):
            area.aplicar_efeitos_alvo(fighter)

        self.assertEqual(fighter.slow_timer, 0.0)
        self.assertEqual(fighter.slow_fator, 1.0)
        self.assertEqual(fighter.stun_timer, 0.0)
        self.assertEqual(getattr(fighter, "medo_timer", 0.0), 0.0)
        self.assertEqual(fighter.enraizado_timer, 0.0)
        self.assertFalse(fighter.dots_ativos)

        fighter.invencivel_timer = 0.0
        life_before = fighter.vida
        fighter.tomar_dano(10.0, 0.0, 0.0, "ENVENENADO")
        self.assertLess(fighter.vida, life_before)
        self.assertFalse(fighter.dots_ativos)

        fighter.update(3.1, enemy)
        self.assertEqual(fighter.imune_debuffs_timer, 0.0)
        fighter._aplicar_efeito_status("FRACO")
        self.assertGreater(fighter.fraco_timer, 0.0)


if __name__ == "__main__":
    unittest.main()
