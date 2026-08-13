"""E2E regressions for the remaining executable catalog mechanics."""

from __future__ import annotations

import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.core.combat import AreaEffect, Projetil, Summon
from neural_fights.core.skills import get_skill_data
from tests import test_remaining_skill_regressions as helpers


class CatalogRemainingMechanicsTests(unittest.TestCase):
    _fighter = staticmethod(helpers.RemainingSkillRegressionTests._fighter)
    _simulation = staticmethod(helpers.RemainingSkillRegressionTests._simulation)
    _floating_text_patch = staticmethod(
        helpers.RemainingSkillRegressionTests._floating_text_patch
    )

    def test_ice_spear_pierces_each_hostile_fighter_and_summon_once(self):
        owner = self._fighter("Cryomancer", x=0.0)
        target = self._fighter("Target", x=0.0)
        enemy_summon = Summon("Ira da Floresta", 0.0, 5.0, target)
        projectile = Projetil("Lança de Gelo", 0.0, 5.0, 0.0, owner)
        simulation = self._simulation(owner, target)
        simulation.summons = [enemy_summon]
        simulation.projeteis = [projectile]
        target_before = target.vida
        summon_before = enemy_summon.vida

        with self._floating_text_patch():
            simulation.update(0.0)

        target_after_first = target.vida
        summon_after_first = enemy_summon.vida
        self.assertLess(target_after_first, target_before)
        self.assertLess(summon_after_first, summon_before)
        self.assertTrue(projectile.ativo)
        self.assertEqual(
            projectile.alvos_perfurados,
            {id(target), id(enemy_summon)},
        )

        simulation.hit_stop_timer = 0.0
        with self._floating_text_patch():
            simulation.update(0.0)

        self.assertEqual(target.vida, target_after_first)
        self.assertEqual(enemy_summon.vida, summon_after_first)

    def test_gravity_field_blocks_new_jumps_while_active(self):
        owner = self._fighter("Gravity")
        target = self._fighter("Jumper")
        target.brain = SimpleNamespace(
            acao_atual="APROXIMAR",
            tracos={"SALTADOR"},
            dir_circular=1,
            medo=0.0,
        )
        area = AreaEffect("Campo de Gravidade", 0.0, 5.0, owner)
        area.aplicar_efeitos_alvo(target)

        with (
            patch("neural_fights.core.entities.random.random", return_value=0.0),
            patch("neural_fights.core.entities.random.uniform", return_value=12.0),
        ):
            target.executar_movimento(0.1, 2.0)
            self.assertEqual(target.vel_z, 0.0)
            self.assertFalse(target.pode_pular())

            target.pulo_bloqueado_timer = 0.0
            target.executar_movimento(0.1, 2.0)

        self.assertEqual(target.vel_z, 12.0)

    def test_brutal_advance_hits_entire_segment_without_double_hitting_destination(self):
        def run_at(target_x):
            owner = self._fighter("Vanguard", x=0.0)
            target = self._fighter("Target", x=target_x)
            data = get_skill_data("Avanço Brutal")
            owner._finalizar_dash_skill(
                "Avanço Brutal",
                data,
                (0.0, 5.0),
                (4.0, 5.0),
                0.0,
            )
            area = owner.buffer_areas.pop()
            simulation = self._simulation(owner, target)
            simulation.areas = [area]
            with (
                patch.object(
                    target,
                    "resolver_impacto",
                    wraps=target.resolver_impacto,
                ) as resolver,
                self._floating_text_patch(),
            ):
                simulation.update(0.0)
            return target.vida_max - target.vida, resolver.call_count, area

        middle_damage, middle_calls, middle_area = run_at(2.0)
        destination_damage, destination_calls, destination_area = run_at(4.0)

        self.assertEqual(middle_area.segmento_impacto, ((0.0, 5.0), (4.0, 5.0)))
        self.assertEqual(destination_area.segmento_impacto, middle_area.segmento_impacto)
        self.assertGreater(middle_damage, 0.0)
        self.assertAlmostEqual(middle_damage, destination_damage)
        self.assertEqual(middle_calls, 1)
        self.assertEqual(destination_calls, 1)

    def test_instability_split_schedule_is_step_independent_and_uses_runtime_rng(self):
        def run(chunks):
            owner = self._fighter("Chaos")
            owner.rng_runtime = random.Random(123)
            projectile = Projetil("Instabilidade", 0.0, 5.0, 0.0, owner)
            angles = []
            with patch(
                "neural_fights.core.combat.random.random",
                side_effect=AssertionError("global RNG must not drive splits"),
            ):
                for dt in chunks:
                    event = projectile.atualizar(dt, [])
                    if event and event.get("split"):
                        angles.extend(event["angulos"])
            return (
                tuple(angles),
                projectile.splits_feitos,
                projectile.ativo,
                owner.rng_runtime.getstate(),
            )

        coarse = run([3.0])
        fine = run([0.05] * 60)

        self.assertEqual(coarse, fine)
        self.assertEqual(coarse[1], 4)
        self.assertEqual(len(coarse[0]), 4)
        self.assertFalse(coarse[2])

    def test_mjolnir_returns_after_impact_without_harming_owner(self):
        owner = self._fighter("Thor", x=0.0)
        target = self._fighter("Target", x=2.0)
        projectile = Projetil("Mjolnir", 2.0, 5.0, 0.0, owner)
        simulation = self._simulation(owner, target)
        simulation.projeteis = [projectile]
        owner_before = owner.vida
        target_before = target.vida

        with self._floating_text_patch():
            simulation.update(0.0)

        self.assertLess(target.vida, target_before)
        self.assertEqual(owner.vida, owner_before)
        self.assertTrue(projectile.retornando)
        self.assertTrue(projectile.ativo)

        simulation.hit_stop_timer = 0.0
        with self._floating_text_patch():
            simulation.update(0.2)

        self.assertNotIn(projectile, simulation.projeteis)
        self.assertEqual(owner.vida, owner_before)

    def test_treant_explicitly_protects_nearby_owner(self):
        def projectile_damage(with_treant):
            attacker = self._fighter("Attacker", x=2.0)
            defender = self._fighter("Druid", x=0.0)
            projectile = Projetil("Estilhaço de Gelo", 0.0, 5.0, 180.0, attacker)
            simulation = self._simulation(attacker, defender)
            simulation.projeteis = [projectile]
            treant = None
            if with_treant:
                treant = Summon("Ira da Floresta", 0.0, 5.0, defender)
                simulation.summons = [treant]
                self.assertTrue(treant.protege(defender))
            with self._floating_text_patch():
                simulation.update(0.0)
            return defender.vida_max - defender.vida, treant

        unprotected_damage, _ = projectile_damage(False)
        protected_damage, treant = projectile_damage(True)

        self.assertEqual(treant.summon_tipo, "TREANT")
        self.assertGreater(unprotected_damage, 0.0)
        self.assertAlmostEqual(protected_damage, unprotected_damage * 0.75)


if __name__ == "__main__":
    unittest.main()
