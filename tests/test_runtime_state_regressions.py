"""Regression tests for runtime configuration and temporary combat states."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import simulation.simulacao as simulation_module
from core.entities import Lutador
from simulation.simulacao import Simulador


class MatchConfigurationRegressionTests(unittest.TestCase):
    @staticmethod
    def _character(name: str, weapon_name: str = "") -> SimpleNamespace:
        return SimpleNamespace(nome=name, nome_arma=weapon_name)

    def test_simulator_uses_the_shared_match_config_loader(self) -> None:
        """Both portrait detection and fighter loading must use one config source."""
        config = {
            "p1_nome": "Config P1",
            "p2_nome": "Config P2",
            "cenario": "Coliseu",
            "portrait_mode": True,
        }
        characters = [self._character("Config P1"), self._character("Config P2")]

        def fake_fighter(data, x, y):
            return SimpleNamespace(dados=data, pos=[x, y])

        simulator = object.__new__(Simulador)
        with (
            patch.object(
                simulation_module.database,
                "carregar_match_config",
                return_value=config,
                create=True,
            ) as load_config,
            patch.object(
                simulation_module.database,
                "carregar_personagens",
                return_value=characters,
            ),
            patch.object(
                simulation_module.database,
                "carregar_armas",
                return_value=[],
            ),
            patch.object(simulation_module, "Lutador", side_effect=fake_fighter),
        ):
            self.assertTrue(simulator._check_portrait_mode())
            p1, p2, arena, portrait_mode = simulator.carregar_luta_dados()

        self.assertEqual(load_config.call_count, 2)
        self.assertEqual(p1.dados.nome, "Config P1")
        self.assertEqual(p2.dados.nome, "Config P2")
        self.assertEqual(arena, "Coliseu")
        self.assertTrue(portrait_mode)

    def test_unknown_fighter_in_config_has_an_actionable_error(self) -> None:
        """A stale match config must not fail later as ``Lutador(None)``."""
        config = {
            "p1_nome": "Nao existe",
            "p2_nome": "Existe",
            "cenario": "Arena",
        }
        characters = [self._character("Existe")]
        simulator = object.__new__(Simulador)

        with (
            patch.object(
                simulation_module.database,
                "carregar_match_config",
                return_value=config,
                create=True,
            ),
            patch.object(
                simulation_module.database,
                "carregar_personagens",
                return_value=characters,
            ),
            patch.object(
                simulation_module.database,
                "carregar_armas",
                return_value=[],
            ),
        ):
            with self.assertRaisesRegex(ValueError, "Nao existe"):
                simulator.carregar_luta_dados()


class TemporaryStatusRegressionTests(unittest.TestCase):
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
        with patch("ai.AIBrain", return_value=None):
            return Lutador(data, 5.0, 5.0)

    def test_root_expires_and_restores_movement(self) -> None:
        fighter = self._fighter("Enraizado")
        enemy = self._fighter("Alvo")

        fighter._aplicar_efeito_status("ENRAIZADO", duracao=0.1)
        self.assertEqual(fighter.slow_fator, 0.0)

        fighter.update(0.2, enemy)

        self.assertEqual(fighter.enraizado_timer, 0.0)
        self.assertEqual(fighter.slow_fator, 1.0)

    def test_freeze_flag_clears_when_its_movement_penalty_ends(self) -> None:
        fighter = self._fighter("Congelado")
        enemy = self._fighter("Alvo")

        fighter._aplicar_efeito_status("CONGELADO", duracao=0.1)
        fighter.update(1.2, enemy)

        self.assertFalse(fighter.congelado)
        self.assertEqual(fighter.slow_fator, 1.0)

    def test_silence_blocks_skills_only_until_its_timer_expires(self) -> None:
        fighter = self._fighter("Silenciado")
        enemy = self._fighter("Alvo")
        fighter.skills_arma = [
            {
                "nome": "Skill de Teste",
                "custo": 0.0,
                "data": {"tipo": "NADA", "cooldown": 1.0},
            }
        ]
        fighter.cd_skills["Skill de Teste"] = 0.0

        fighter._aplicar_efeito_status("SILENCIADO", duracao=0.1)
        self.assertFalse(fighter.usar_skill_arma())
        self.assertEqual(fighter.cd_skills["Skill de Teste"], 0.0)

        fighter.update(0.2, enemy)

        self.assertEqual(fighter.silenciado_timer, 0.0)
        self.assertTrue(fighter.usar_skill_arma())


if __name__ == "__main__":
    unittest.main()
