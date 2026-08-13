"""Regressoes E2E para contratos do catalogo que nao podem ficar inertes."""

from __future__ import annotations

import random
import unittest
from unittest.mock import patch

from neural_fights.core.combat import AreaEffect, Buff, Projetil, Summon, Transform
from tests import test_remaining_skill_regressions as helpers


class CatalogSkillRuntimeRegressionTests(unittest.TestCase):
    _fighter = staticmethod(helpers.RemainingSkillRegressionTests._fighter)
    _simulation = staticmethod(helpers.RemainingSkillRegressionTests._simulation)
    _floating_text_patch = staticmethod(
        helpers.RemainingSkillRegressionTests._floating_text_patch
    )

    def test_chaos_area_resolves_one_declared_random_effect_per_cast(self):
        owner = self._fighter("Chaos")
        owner.rng_runtime = random.Random(42)
        areas = [
            AreaEffect("Explos\u00e3o do Caos", 0.0, 5.0, owner)
            for _ in range(20)
        ]
        declared = {
            "QUEIMANDO",
            "CONGELADO",
            "PARALISIA",
            "ENVENENADO",
            "LENTO",
        }

        self.assertTrue(all(area.tipo_efeito in declared for area in areas))
        self.assertGreater(len({area.tipo_efeito for area in areas}), 1)

    def test_necrotic_area_heals_from_damage_actually_applied(self):
        owner = self._fighter("Necromancer", x=0.0)
        target = self._fighter("Target", x=0.1)
        owner.vida = owner.vida_max - 100.0
        area = AreaEffect("Explos\u00e3o Necr\u00f3tica", 0.0, 5.0, owner)
        area.raio_atual = area.raio
        simulation = self._simulation(owner, target)
        simulation.areas = [area]

        before_target = target.vida
        before_owner = owner.vida
        with self._floating_text_patch():
            simulation.update(0.0)

        damage = before_target - target.vida
        self.assertGreater(damage, 0.0)
        self.assertAlmostEqual(owner.vida - before_owner, damage * 0.25)

    def test_gravity_pulse_and_black_hole_emit_nonzero_pull(self):
        owner = self._fighter("Gravity", x=0.0)
        target = self._fighter("Target", x=1.0)
        for skill in ("Pulso Gravitacional", "Buraco Negro"):
            with self.subTest(skill=skill):
                area = AreaEffect(skill, 0.0, 5.0, owner)
                area.raio_atual = area.raio
                pulls = [
                    result
                    for result in area.atualizar(0.1, [target])
                    if result.get("pull")
                ]
                self.assertEqual(len(pulls), 1)
                self.assertGreater(pulls[0]["forca"], 0.0)

    def test_phoenix_revives_exactly_once(self):
        owner = self._fighter("Summoner")
        phoenix = Summon("F\u00eanix", 0.0, 5.0, owner)

        first = phoenix.tomar_dano(phoenix.vida_max * 2.0)
        second = phoenix.tomar_dano(phoenix.vida_max * 2.0)

        self.assertEqual(first["revive"], True)
        self.assertEqual(phoenix.vida, 0.0)
        self.assertEqual(second["morreu"], True)
        self.assertFalse(phoenix.ativo)

    def test_delayed_collapse_explodes_at_declared_time(self):
        owner = self._fighter("Caster")
        projectile = Projetil("Colapso", 0.0, 5.0, 0.0, owner)

        self.assertIsNone(projectile.atualizar(1.99, []))
        event = projectile.atualizar(0.01, [])

        self.assertTrue(event["explodir"])
        self.assertAlmostEqual(event["raio"], 2.5)
        self.assertFalse(projectile.ativo)

        target = self._fighter("Collision target", x=0.0)
        fresh = Projetil("Colapso", 0.0, 5.0, 0.0, owner)
        simulation = self._simulation(owner, target)
        simulation.projeteis = [fresh]
        with self._floating_text_patch():
            simulation.update(0.0)
            self.assertEqual(simulation.areas, [])
            self.assertTrue(fresh.aguardando_explosao)
            self.assertIn(fresh, simulation.projeteis)
            simulation.hit_stop_timer = 0.0
            simulation.update(1.99)
            self.assertEqual(simulation.areas, [])
            simulation.update(0.01)
        self.assertTrue(simulation.areas)

    def test_projectile_explosion_is_not_suppressed_by_parent_hit_recovery(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=0.0)
        projectile = Projetil("Meteoro", 0.0, 5.0, 0.0, owner)
        simulation = self._simulation(owner, target)
        simulation.projeteis = [projectile]
        before = target.vida

        with self._floating_text_patch():
            simulation.update(0.0)

        parent_damage = owner.get_dano_modificado(projectile.dano)
        self.assertGreater(before - target.vida, parent_damage)

    def test_russian_roulette_backfire_targets_owner_end_to_end(self):
        owner = self._fighter("Shooter", x=0.0)
        target = self._fighter("Target", x=5.0)
        owner.rng_runtime = random.Random(1)
        projectile = Projetil("Roleta Russa", 0.0, 5.0, 0.0, owner)
        simulation = self._simulation(owner, target)
        simulation.projeteis = [projectile]
        before_owner = owner.vida

        with self._floating_text_patch():
            simulation.update(0.0)

        self.assertTrue(projectile.backfire)
        self.assertLess(owner.vida, before_owner)
        self.assertEqual(target.vida, target.vida_max)

    def test_transform_contact_damage_is_step_independent(self):
        def run(chunks):
            owner = self._fighter("Lightning", x=0.0)
            target = self._fighter("Target", x=0.5)
            Transform("Forma Rel\u00e2mpago", owner)
            simulation = self._simulation(owner, target)
            with self._floating_text_patch():
                for dt in chunks:
                    simulation.update(dt)
            return target.vida_max - target.vida

        self.assertAlmostEqual(run([1.0]), run([0.05] * 20))
        self.assertGreater(run([1.0]), 0.0)

    def test_summon_damage_uses_owner_modifiers_and_treant_profile(self):
        owner = self._fighter("Druid", x=0.0)
        target = self._fighter("Target", x=0.5)
        owner.mod_dano = 2.0
        summon = Summon("Ira da Floresta", 0.0, 5.0, owner)
        simulation = self._simulation(owner, target)
        simulation.summons = [summon]

        with self._floating_text_patch():
            simulation.update(0.0)

        self.assertEqual(summon.summon_tipo, "TREANT")
        self.assertAlmostEqual(target.vida_max - target.vida, 24.0)

    def test_executor_buff_is_consumed_only_after_accepted_damage(self):
        owner = self._fighter("Executor")
        target = self._fighter("Target")
        baseline = owner.get_dano_modificado(10.0)
        buff = Buff("Golpe do Executor", owner)
        owner.buffs_ativos.append(buff)
        doubled = owner.get_dano_modificado(10.0)
        target.invulnerabilidade_skill_timer = 1.0

        blocked = target.resolver_impacto(doubled, 0.0, 0.0, atacante=owner)
        self.assertFalse(blocked.atingiu)
        self.assertIn(buff, owner.buffs_ativos)

        target.invulnerabilidade_skill_timer = 0.0
        accepted = target.resolver_impacto(doubled, 0.0, 0.0, atacante=owner)
        self.assertTrue(accepted.atingiu)
        self.assertNotIn(buff, owner.buffs_ativos)
        self.assertAlmostEqual(owner.get_dano_modificado(10.0), baseline)

    def test_weapon_purify_can_clean_fear_without_bypassing_other_controls(self):
        owner = self._fighter("Cleric")
        skill = {
            "nome": "Purificar",
            "custo": 12.0,
            "data": __import__(
                "neural_fights.core.skills",
                fromlist=["get_skill_data"],
            ).get_skill_data("Purificar"),
        }
        owner.skills_arma = [skill]
        owner.skill_atual_idx = 0
        owner.cd_skills["Purificar"] = 0.0
        owner.medo_timer = 2.0

        with patch(
            "neural_fights.effects.audio.AudioManager.get_instance",
            return_value=None,
        ):
            self.assertTrue(owner.usar_skill_arma(0))

        self.assertEqual(owner.medo_timer, 0.0)


if __name__ == "__main__":
    unittest.main()
