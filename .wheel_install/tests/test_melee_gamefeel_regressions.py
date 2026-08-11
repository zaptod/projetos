"""Regressões do contrato entre hits físicos e Game Feel."""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pygame

from core.entities import Lutador
from core.game_feel import GameFeelManager
from simulation.simulacao import Simulador


class MeleeGameFeelRegressionTests(unittest.TestCase):
    @staticmethod
    def _fighter(name: str, classe: str, x: float, *, armed: bool = False) -> Lutador:
        weapon = None
        if armed:
            weapon = SimpleNamespace(
                nome="Espada de teste",
                tipo="Reta",
                dano=8.0,
                raridade="Comum",
                habilidades=[],
                encantamentos=[],
                r=180,
                g=180,
                b=180,
            )
        data = SimpleNamespace(
            nome=name,
            tamanho=1.7,
            forca=20.0 if armed else 5.0,
            mana=5.0,
            resistencia=5.0,
            velocidade=5.0,
            classe=classe,
            personalidade="Aleatorio",
            nome_arma=weapon.nome if weapon else "",
            arma_obj=weapon,
            cor_r=150,
            cor_g=150,
            cor_b=150,
        )
        with patch("ai.AIBrain", return_value=None):
            return Lutador(data, x, 5.0)

    def setUp(self) -> None:
        pygame.font.init()
        GameFeelManager.reset()

    def tearDown(self) -> None:
        GameFeelManager.reset()
        pygame.font.quit()

    def _combat(self, defender_class: str, *, damage: float = 20.0):
        attacker = self._fighter(
            "Atacante",
            "Mago (Arcano)",
            5.0,
            armed=True,
        )
        defender = self._fighter("Defensor", defender_class, 7.0)
        attacker.calcular_dano_ataque = Mock(return_value=(damage, False))

        # Berserker e Guerreiro ativam armor nesta janela de ataque pesado.
        defender.atacando = True
        defender.timer_animacao = 0.20
        defender.brain = SimpleNamespace(acao_atual="MATAR", raiva=0.0)

        manager = GameFeelManager.get_instance()
        manager.registrar_lutadores(attacker, defender)

        simulator = object.__new__(Simulador)
        simulator.audio = None
        simulator.choreographer = None
        simulator.game_feel = manager
        simulator.attack_anims = None
        simulator.cam = SimpleNamespace(x=0.0)
        simulator.textos = []
        simulator.particulas = []
        simulator.hit_sparks = []
        simulator.impact_flashes = []
        simulator.shockwaves = []
        simulator.spawn_particulas = Mock()
        simulator._criar_knockback_visual = Mock()
        return simulator, attacker, defender, manager

    def test_full_super_armor_resistance_zeroes_actual_displacement(self) -> None:
        simulator, attacker, defender, manager = self._combat("Berserker (Fúria)")
        life_before = defender.vida
        base_knockback = (12.0, 4.0)

        with (
            patch("simulation.simulacao.verificar_hit", return_value=(True, "hit")),
            patch(
                "simulation.simulacao.calcular_knockback_com_forca",
                return_value=base_knockback,
            ) as calculate_knockback,
            patch.object(manager, "processar_hit", wraps=manager.processar_hit) as process_hit,
        ):
            simulator.checar_ataque(attacker, defender)

        calculate_knockback.assert_called_once()
        self.assertEqual(process_hit.call_args.kwargs["knockback"], base_knockback)
        self.assertAlmostEqual(life_before - defender.vida, 10.0)
        self.assertEqual(defender.vel, [0.0, 0.0])
        simulator._criar_knockback_visual.assert_not_called()

    def test_partial_super_armor_resistance_reduces_actual_displacement(self) -> None:
        simulator, attacker, defender, manager = self._combat("Guerreiro (Força Bruta)")
        life_before = defender.vida
        base_knockback = (12.0, 4.0)
        expected_knockback = (2.4, 0.8)  # 80% de resistência da classe.

        with (
            patch("simulation.simulacao.verificar_hit", return_value=(True, "hit")),
            patch(
                "simulation.simulacao.calcular_knockback_com_forca",
                return_value=base_knockback,
            ) as calculate_knockback,
            patch.object(manager, "processar_hit", wraps=manager.processar_hit) as process_hit,
        ):
            simulator.checar_ataque(attacker, defender)

        calculate_knockback.assert_called_once()
        self.assertEqual(process_hit.call_args.kwargs["knockback"], base_knockback)
        self.assertAlmostEqual(life_before - defender.vida, 6.0)
        self.assertAlmostEqual(defender.vel[0], expected_knockback[0])
        self.assertAlmostEqual(defender.vel[1], expected_knockback[1])
        visual_args = simulator._criar_knockback_visual.call_args.args
        self.assertAlmostEqual(visual_args[1], math.atan2(0.8, 2.4))
        self.assertAlmostEqual(visual_args[2], math.hypot(*expected_knockback))

    def test_rejected_impact_applies_neither_knockback_nor_impact_vfx(self) -> None:
        simulator, attacker, defender, _manager = self._combat("Berserker (Fúria)")
        defender.invencivel_timer = 0.2
        life_before = defender.vida

        with (
            patch("simulation.simulacao.verificar_hit", return_value=(True, "hit")),
            patch(
                "simulation.simulacao.calcular_knockback_com_forca",
                return_value=(12.0, 4.0),
            ),
        ):
            simulator.checar_ataque(attacker, defender)

        self.assertEqual(defender.vida, life_before)
        self.assertEqual(defender.vel, [0.0, 0.0])
        self.assertEqual(simulator.hit_sparks, [])
        self.assertEqual(simulator.impact_flashes, [])
        simulator._criar_knockback_visual.assert_not_called()

    def test_zero_damage_does_not_calculate_or_apply_knockback(self) -> None:
        simulator, attacker, defender, manager = self._combat(
            "Berserker (Fúria)",
            damage=0.0,
        )
        life_before = defender.vida

        with (
            patch("simulation.simulacao.verificar_hit", return_value=(True, "hit")),
            patch("simulation.simulacao.calcular_knockback_com_forca") as calculate_knockback,
            patch.object(manager, "processar_hit", wraps=manager.processar_hit) as process_hit,
        ):
            simulator.checar_ataque(attacker, defender)

        calculate_knockback.assert_not_called()
        process_hit.assert_not_called()
        self.assertEqual(defender.vida, life_before)
        self.assertEqual(defender.vel, [0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
