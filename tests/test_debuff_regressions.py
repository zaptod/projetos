"""Regression tests for temporary outgoing and incoming damage debuffs."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.core.combat import DotEffect
from neural_fights.core.entities import Lutador


class DamageDebuffRegressionTests(unittest.TestCase):
    @staticmethod
    def _fighter(name: str, classe: str = "Guerreiro (Forca Bruta)") -> Lutador:
        data = SimpleNamespace(
            nome=name,
            tamanho=1.7,
            forca=5.0,
            mana=5.0,
            resistencia=5.0,
            velocidade=5.0,
            classe=classe,
            personalidade="Aleatorio",
            nome_arma="",
            arma_obj=None,
        )
        with patch("neural_fights.ai.AIBrain", return_value=None):
            return Lutador(data, 5.0, 5.0)

    @staticmethod
    def _damage_taken(target: Lutador, damage: float, attacker=None, effect="NORMAL") -> float:
        target.invencivel_timer = 0.0
        life_before = target.vida
        target.tomar_dano(damage, 0.0, 0.0, effect, atacante=attacker)
        return life_before - target.vida

    def test_weak_reduces_melee_and_skill_equivalent_damage_with_attacker(self) -> None:
        attacker = self._fighter("Weak attacker")
        attacker._aplicar_efeito_status("FRACO")

        melee_target = self._fighter("Melee target")
        self.assertAlmostEqual(
            self._damage_taken(melee_target, 100.0, attacker=attacker),
            70.0,
        )

        skill_target = self._fighter("Skill target")
        skill_damage = attacker.get_dano_modificado(20.0)
        self.assertAlmostEqual(
            self._damage_taken(skill_target, skill_damage, attacker=attacker),
            skill_damage * 0.7,
        )

        source_less_target = self._fighter("Source-less target")
        self.assertAlmostEqual(
            self._damage_taken(source_less_target, 100.0),
            100.0,
        )

    def test_triggering_hit_is_normal_and_following_hit_is_vulnerable(self) -> None:
        target = self._fighter("Vulnerable target")

        triggering_damage = self._damage_taken(target, 20.0, effect="VULNERAVEL")
        following_damage = self._damage_taken(target, 20.0)

        self.assertAlmostEqual(triggering_damage, 20.0)
        self.assertAlmostEqual(following_damage, 30.0)
        self.assertEqual(target.vulneravel_timer, 4.0)

    def test_incoming_debuffs_use_strongest_modifier_regardless_of_order(self) -> None:
        effects = ["MALDITO", "EXPOSTO", "CORROENDO", "VULNERAVEL"]

        for index, order in enumerate((effects, list(reversed(effects)))):
            with self.subTest(order=order):
                target = self._fighter(f"Ordered target {index}")
                for effect in order:
                    target._aplicar_efeito_status(effect)

                self.assertEqual(target.vulnerabilidade, 2.0)
                self.assertAlmostEqual(self._damage_taken(target, 10.0), 20.0)

        refreshed = self._fighter("Refreshed target")
        refreshed._aplicar_efeito_status("VULNERAVEL", duracao=4.0)
        refreshed._aplicar_efeito_status("VULNERAVEL", duracao=1.0)
        refreshed._aplicar_efeito_status("MALDITO", duracao=6.0)
        refreshed._aplicar_efeito_status("MALDITO", duracao=1.0)

        self.assertEqual(refreshed.vulneravel_timer, 4.0)
        self.assertEqual(refreshed.maldito_timer, 6.0)
        self.assertEqual(
            len([dot for dot in refreshed.dots_ativos if dot.tipo == "MALDITO"]),
            1,
        )

    def test_debuff_timers_expire_and_restore_neutral_modifiers(self) -> None:
        attacker = self._fighter("Timed attacker")
        target = self._fighter("Timed target")
        enemy = self._fighter("Enemy")

        attacker._aplicar_efeito_status("FRACO", duracao=0.1)
        for effect in ("VULNERAVEL", "MALDITO", "CORROENDO", "EXPOSTO"):
            target._aplicar_efeito_status(effect, duracao=0.1)

        attacker.update(0.2, enemy)
        target.update(0.2, enemy)

        self.assertEqual(attacker.fraco_timer, 0.0)
        self.assertEqual(attacker.dano_reduzido, 1.0)
        self.assertEqual(target.vulnerabilidade, 1.0)
        self.assertTrue(
            all(
                getattr(target, timer) == 0.0
                for timer in (
                    "vulneravel_timer", "maldito_timer",
                    "corroendo_timer", "exposto_timer",
                )
            )
        )
        self.assertAlmostEqual(self._damage_taken(target, 10.0, attacker=attacker), 10.0)

    def test_corrosion_preserves_class_defense_and_direct_dot_is_not_amplified(self) -> None:
        corroded = self._fighter("Corroded")
        defense_before = corroded.mod_defesa

        corroded._aplicar_efeito_status("CORROENDO", duracao=4.0)
        corroded._aplicar_efeito_status("CORROENDO", duracao=1.0)

        self.assertEqual(corroded.mod_defesa, defense_before)
        self.assertEqual(corroded.corroendo_timer, 4.0)
        self.assertEqual(
            len([dot for dot in corroded.dots_ativos if dot.tipo == "CORROENDO"]),
            1,
        )

        exposed = self._fighter("Exposed to direct DoT")
        exposed._aplicar_efeito_status("EXPOSTO")
        dot = DotEffect("TEST", exposed, 10.0, 0.5, (255, 255, 255))
        life_before = exposed.vida
        dot.atualizar(0.5)

        self.assertAlmostEqual(life_before - exposed.vida, 5.0)

        area_dot_target = self._fighter("Exposed to area DoT")
        area_dot_target._aplicar_efeito_status("EXPOSTO")
        life_before = area_dot_target.vida
        area_dot_target.tomar_dano(
            10.0,
            0.0,
            0.0,
            "FOGO",
            aplicar_modificadores_debuff=False,
        )

        self.assertAlmostEqual(life_before - area_dot_target.vida, 10.0)
        self.assertAlmostEqual(area_dot_target.ultimo_dano_recebido, 10.0)

    def test_knight_reduction_keeps_the_same_ratio_under_vulnerability(self) -> None:
        # Re-pino Onda 6: a reducao do Cavaleiro virou POSTURA opt-in —
        # o contrato deste teste (a razao 0,75 atravessa a vulnerabilidade
        # sem dupla contagem) exige o escudo ATIVO, entao os cavaleiros do
        # scaffold entram em postura defensiva.
        class _BrainPostura:
            def __init__(self, acao):
                self.acao_atual = acao

            def __getattr__(self, nome):
                return 0.0

        warrior = self._fighter("Warrior")
        knight = self._fighter("Knight", classe="Cavaleiro")
        knight.brain = _BrainPostura("BLOQUEAR")
        baseline_warrior = self._damage_taken(warrior, 40.0)
        baseline_knight = self._damage_taken(knight, 40.0)

        vulnerable_warrior = self._fighter("Vulnerable warrior")
        vulnerable_knight = self._fighter("Vulnerable knight", classe="Cavaleiro")
        vulnerable_knight.brain = _BrainPostura("BLOQUEAR")
        vulnerable_warrior._aplicar_efeito_status("VULNERAVEL")
        vulnerable_knight._aplicar_efeito_status("VULNERAVEL")
        amplified_warrior = self._damage_taken(vulnerable_warrior, 40.0)
        amplified_knight = self._damage_taken(vulnerable_knight, 40.0)

        self.assertAlmostEqual(baseline_knight / baseline_warrior, 0.75)
        self.assertAlmostEqual(amplified_knight / amplified_warrior, 0.75)


if __name__ == "__main__":
    unittest.main()
