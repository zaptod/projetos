"""Contratos end-to-end de areas persistentes e estruturas."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.core.combat import AreaEffect, Buff, Trap
from tests import test_remaining_skill_regressions as _remaining_helpers


class AreaStructureSkillRegressionTests(unittest.TestCase):
    _fighter = staticmethod(_remaining_helpers.RemainingSkillRegressionTests._fighter)
    _simulation = staticmethod(
        _remaining_helpers.RemainingSkillRegressionTests._simulation
    )
    _floating_text_patch = staticmethod(
        _remaining_helpers.RemainingSkillRegressionTests._floating_text_patch
    )

    def test_toxic_cloud_stacks_only_for_each_targets_exposure(self):
        owner = self._fighter("Caster", x=0.0)
        first = self._fighter("First", x=0.1)
        second = self._fighter("Second", x=20.0)
        area = AreaEffect("Nuvem Tóxica", 0.0, 5.0, owner)
        area.raio_atual = area.raio

        self.assertEqual(
            sum("status_stack" in item for item in area.atualizar(0.6, [first, second])),
            0,
        )
        first.pos[0] = 20.0
        second.pos[0] = 0.1
        self.assertEqual(
            sum("status_stack" in item for item in area.atualizar(0.6, [first, second])),
            0,
        )
        first.pos[0] = 0.1
        results = area.atualizar(0.4, [first, second])
        stacked = [item["alvo"] for item in results if item.get("status_stack")]

        self.assertEqual(stacked, [first, second])

    def test_area_periodic_damage_is_step_independent_and_stops_at_expiry(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=0.1)

        coarse = AreaEffect("Inferno", 0.0, 5.0, owner)
        coarse.raio_atual = coarse.raio
        coarse_results = coarse.atualizar(10.0, [target])

        fine = AreaEffect("Inferno", 0.0, 5.0, owner)
        fine.raio_atual = fine.raio
        fine_results = []
        for _ in range(50):
            fine_results.extend(fine.atualizar(0.1, [target]))

        coarse_damage = sum(item.get("dano", 0.0) for item in coarse_results)
        fine_damage = sum(item.get("dano", 0.0) for item in fine_results)
        self.assertAlmostEqual(coarse_damage, 50.0)
        self.assertAlmostEqual(fine_damage, coarse_damage)
        self.assertTrue(all(item.get("tipo") == "NORMAL" for item in coarse_results))
        self.assertFalse(coarse.ativo)

    def test_celestial_pillars_share_one_impact_identity(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=0.1)
        area = AreaEffect("Julgamento Celestial", 0.0, 5.0, owner)
        area.delay = 0.0
        area.ativado = True
        area.posicoes_pilares = [tuple(target.pos)] * area.pilares
        simulation = self._simulation(owner, target)
        simulation.areas = [area]
        life_before = target.vida

        with self._floating_text_patch():
            simulation.update(0.0)
            self.assertEqual(len(simulation.areas), 5)
            sources = {id(child.fonte_impacto) for child in simulation.areas}
            self.assertEqual(sources, {id(area)})
            simulation.update(0.01)

        self.assertLess(target.vida, life_before)
        self.assertEqual(len(target._fontes_impacto_recentes), 1)

    def test_repulsion_consumes_configured_force_without_changing_damage(self):
        def resolve(force):
            owner = self._fighter("Caster", x=0.0)
            target = self._fighter("Target", x=0.5)
            area = AreaEffect("Repulsão", 0.0, 5.0, owner)
            area.raio_atual = area.raio
            area.forca_empurrao = force
            simulation = self._simulation(owner, target)
            simulation.areas = [area]
            with self._floating_text_patch():
                simulation.update(0.0)
            return target.vida, target.vel[0]

        base_life, base_velocity = resolve(0.0)
        pushed_life, pushed_velocity = resolve(2.0)

        self.assertAlmostEqual(pushed_life, base_life)
        self.assertAlmostEqual(pushed_velocity - base_velocity, 2.0)

    def test_ice_wall_intercepts_fast_hostile_projectiles_until_destroyed(self):
        owner = self._fighter("Wall owner", x=0.0)
        enemy = self._fighter("Enemy", x=5.0)
        hostile_source = object()
        wall = Trap("Muralha de Gelo", 2.0, 5.0, owner)
        simulation = self._simulation(owner, enemy)
        simulation.traps = [wall]

        def projectile(damage=60.0, projectile_owner=hostile_source):
            return SimpleNamespace(
                ativo=True,
                cone=False,
                x=4.0,
                y=5.0,
                raio=0.2,
                dano=damage,
                dono=projectile_owner,
            )

        first = projectile()
        self.assertTrue(simulation._resolver_colisao_projetil_traps(first, 0.0, 5.0))
        self.assertFalse(first.ativo)
        self.assertAlmostEqual(wall.vida, 40.0)

        second = projectile()
        self.assertTrue(simulation._resolver_colisao_projetil_traps(second, 0.0, 5.0))
        self.assertFalse(wall.ativo)

        third = projectile()
        self.assertFalse(simulation._resolver_colisao_projetil_traps(third, 0.0, 5.0))
        self.assertTrue(third.ativo)

        friendly = projectile(projectile_owner=owner)
        fresh_wall = Trap("Muralha de Gelo", 2.0, 5.0, owner)
        simulation.traps = [fresh_wall]
        self.assertFalse(
            simulation._resolver_colisao_projetil_traps(friendly, 0.0, 5.0)
        )
        self.assertEqual(fresh_wall.vida, fresh_wall.vida_max)

    def test_counterspell_reflects_area_periodic_tick_with_metadata(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Counter", x=0.1)
        target.buffs_ativos.append(Buff("Contrafeitiço", target))
        area = AreaEffect("Inferno", 0.0, 5.0, owner)
        area.raio_atual = area.raio
        area.tick_timer = 0.4
        area.alvos_atingidos.add(target)
        simulation = self._simulation(owner, target)
        simulation.areas = [area]

        with self._floating_text_patch():
            simulation.update(0.1)

        self.assertLess(owner.vida, owner.vida_max)
        self.assertEqual(target.vida, target.vida_max)
        counterspell = next(
            buff for buff in target.buffs_ativos if buff.nome == "Contrafeitiço"
        )
        self.assertFalse(counterspell.reflete_skills_disponivel)

    def test_time_stop_consumes_duration_and_caster_targeting_contracts(self):
        owner = self._fighter("Chronomancer", x=0.0)
        target = self._fighter("Target", x=0.1)
        area = AreaEffect("Parar o Tempo", 0.0, 5.0, owner)
        simulation = self._simulation(owner, target)
        simulation.areas = [area]

        with self._floating_text_patch():
            simulation.update(0.1)

        self.assertEqual(area.duracao_stop, 2.0)
        self.assertFalse(area.afeta_caster)
        self.assertEqual(owner.tempo_parado_timer, 0.0)
        self.assertEqual(target.tempo_parado_timer, 2.0)


if __name__ == "__main__":
    unittest.main()
