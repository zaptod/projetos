"""Regression tests for temporary area effects and damage-over-time timing."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import neural_fights.simulation.simulacao as simulation_module
from neural_fights.core.combat import AreaEffect, DotEffect
from neural_fights.core.entities import Lutador
from neural_fights.simulation.simulacao import Simulador


class AreaEffectRegressionTests(unittest.TestCase):
    @staticmethod
    def _fighter(name: str, x: float = 5.0) -> Lutador:
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
            return Lutador(data, x, 5.0)

    @staticmethod
    def _simulation(owner: Lutador, target: Lutador, area: AreaEffect) -> Simulador:
        simulation = object.__new__(Simulador)
        simulation.cam = SimpleNamespace(atualizar=lambda _dt, _p1, _p2: None)
        simulation.p1 = owner
        simulation.p2 = target
        simulation.paused = False
        simulation.textos = []
        simulation.shockwaves = []
        simulation.game_feel = None
        simulation.hit_stop_timer = 0.0
        simulation.impact_flashes = []
        simulation.magic_clashes = []
        simulation.block_effects = []
        simulation.dash_trails = []
        simulation.hit_sparks = []
        simulation.magic_vfx = None
        simulation.projeteis = []
        simulation.areas = [area]
        simulation._verificar_clash_projeteis = lambda: None
        simulation.audio = None
        simulation.vencedor = "fixture-already-finished"
        simulation.movement_anims = None
        simulation.attack_anims = None
        simulation.particulas = []
        simulation.decals = []
        return simulation

    def test_area_collision_applies_secondary_without_reapplying_primary(self) -> None:
        owner = self._fighter("Caster")
        target = self._fighter("Target", x=5.1)
        area = AreaEffect("Wrath of Nature", owner.pos[0], owner.pos[1], owner)
        self.assertEqual(area.atualizar(area.delay, [owner, target]), [])
        simulation = self._simulation(owner, target, area)

        with patch.object(
            target,
            "_aplicar_efeito_status",
            wraps=target._aplicar_efeito_status,
        ) as apply_status, patch.object(
            simulation_module,
            "FloatingText",
            return_value=SimpleNamespace(vida=1.0, update=lambda _dt: None),
        ):
            simulation.update(0.1)

        applied_effects = [call.args[0] for call in apply_status.call_args_list]
        self.assertEqual(applied_effects.count("ENRAIZADO"), 1)
        self.assertEqual(applied_effects.count("ENVENENADO"), 1)

    def test_area_applies_control_metadata_with_no_brain(self) -> None:
        area = AreaEffect("Nenhuma", 0.0, 0.0, None)
        area.duracao = 2.0
        area.slow_fator = 0.5
        area.duracao_stun = 1.25
        area.chance_stun = 1.0
        area.duracao_fear = 1.5
        area.gravidade_aumentada = 4.0
        area.tipo_efeito = "PARALISIA"
        area.efeito2 = "ENVENENADO"

        apply_status = Mock()
        target = SimpleNamespace(
            slow_timer=0.0,
            slow_fator=1.0,
            stun_timer=0.0,
            medo_timer=0.0,
            brain=None,
            vel_z=5.0,
            _aplicar_efeito_status=apply_status,
        )

        with patch("neural_fights.core.combat.random.random", return_value=0.0):
            area.aplicar_efeitos_alvo(target, aplicar_efeito_principal=False)

        self.assertEqual(target.slow_timer, 2.0)
        self.assertEqual(target.slow_fator, 0.25)
        self.assertEqual(target.stun_timer, 1.25)
        self.assertEqual(target.medo_timer, 1.5)
        self.assertEqual(target.vel_z, 0.0)
        apply_status.assert_called_once_with("ENVENENADO")

    def test_area_does_not_bypass_damage_invulnerability_with_secondary_effects(self) -> None:
        owner = self._fighter("Caster")
        target = self._fighter("Target", x=5.1)
        area = AreaEffect("Wrath of Nature", owner.pos[0], owner.pos[1], owner)
        self.assertEqual(area.atualizar(area.delay, [owner, target]), [])
        target.invencivel_timer = 1.0
        simulation = self._simulation(owner, target, area)

        with patch.object(
            target,
            "_aplicar_efeito_status",
            wraps=target._aplicar_efeito_status,
        ) as apply_status, patch.object(
            simulation_module,
            "FloatingText",
            return_value=SimpleNamespace(vida=1.0, update=lambda _dt: None),
        ):
            simulation.update(0.1)

        apply_status.assert_not_called()

    def test_time_stop_expires_and_restores_movement(self) -> None:
        fighter = self._fighter("Stopped")
        enemy = self._fighter("Enemy")

        fighter._aplicar_efeito_status("TEMPO_PARADO", duracao=0.1)
        self.assertTrue(fighter.tempo_parado)
        self.assertEqual(fighter.slow_fator, 0.0)

        fighter.update(0.2, enemy)

        self.assertEqual(fighter.tempo_parado_timer, 0.0)
        self.assertFalse(fighter.tempo_parado)
        self.assertEqual(fighter.slow_fator, 1.0)


class DotEffectRegressionTests(unittest.TestCase):
    class Target:
        def __init__(self) -> None:
            self.vida = 100.0
            self.morto = False

        def morrer(self) -> None:
            self.morto = True

    @classmethod
    def _run_dot(cls, steps: list[float], duration: float = 3.0):
        target = cls.Target()
        dot = DotEffect("ENVENENADO", target, 10.0, duration, (0, 255, 0))
        for dt in steps:
            dot.atualizar(dt)
        return target, dot

    def test_dot_damage_is_independent_of_update_step(self) -> None:
        fine_target, fine_dot = self._run_dot([0.5] * 6)
        coarse_target, coarse_dot = self._run_dot([1.0] * 3)
        single_target, single_dot = self._run_dot([3.0])

        self.assertEqual(fine_target.vida, 70.0)
        self.assertEqual(coarse_target.vida, fine_target.vida)
        self.assertEqual(single_target.vida, fine_target.vida)
        self.assertFalse(fine_dot.ativo)
        self.assertFalse(coarse_dot.ativo)
        self.assertFalse(single_dot.ativo)

    def test_dot_does_not_tick_past_its_duration(self) -> None:
        target, dot = self._run_dot([10.0], duration=0.75)

        self.assertEqual(target.vida, 95.0)
        self.assertFalse(dot.ativo)

        dot.atualizar(10.0)
        self.assertEqual(target.vida, 95.0)


if __name__ == "__main__":
    unittest.main()
