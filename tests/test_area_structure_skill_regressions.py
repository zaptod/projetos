"""Contratos end-to-end de areas persistentes e estruturas."""

from __future__ import annotations

import unittest
import random
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neural_fights.core.combat import AreaEffect, Buff, Channel, Trap
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
        self.assertAlmostEqual(coarse_damage, 100.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertAlmostEqual(fine_damage, coarse_damage)
        self.assertTrue(all(item.get("tipo") == "NORMAL" for item in coarse_results))
        self.assertFalse(coarse.ativo)

    def test_area_waves_emit_every_configured_wave_with_step_independence(self):
        owner = self._fighter("Caster", x=0.0)

        def emit(chunks):
            area = AreaEffect("Wrath of Nature", 0.0, 5.0, owner)
            area.delay = 0.0
            area.ativado = True
            results = []
            for dt in chunks:
                results.extend(area.atualizar(dt, []))
            return area, [item for item in results if item.get("nova_onda")]

        coarse, coarse_waves = emit([0.5])
        fine, fine_waves = emit([0.1] * 5)

        self.assertEqual(coarse.ondas, 3)
        self.assertEqual(coarse.onda_atual, coarse.ondas)
        self.assertEqual(fine.onda_atual, fine.ondas)
        self.assertEqual(len(coarse_waves), 2)
        self.assertEqual(len(fine_waves), 2)
        self.assertEqual(len({id(item["fonte_impacto"]) for item in coarse_waves}), 2)

    def test_area_waves_apply_base_and_every_child_impact_after_a_coarse_step(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=0.1)
        area = AreaEffect("Wrath of Nature", 0.0, 5.0, owner)
        area.delay = 0.0
        area.ativado = True
        area.raio_atual = area.raio
        simulation = self._simulation(owner, target)
        simulation.areas = [area]

        with self._floating_text_patch():
            simulation.update(area.duracao)
            self.assertEqual(len(simulation.areas), 2)
            simulation.update(0.0)

        self.assertEqual(len(target._fontes_impacto_recentes), 3)
        expected = owner.get_dano_modificado(120.0 + 2 * 120.0 * 0.7)  # re-pino O6f2: escala x2
        self.assertAlmostEqual(target.vida, target.vida_max - expected)

    def test_meteor_shower_emits_every_configured_meteor_with_explicit_payload(self):
        owner = self._fighter("Caster", x=0.0)

        def emit(chunks):
            area = AreaEffect("Apocalipse", 0.0, 5.0, owner)
            area.delay = 0.0
            area.ativado = True
            results = []
            for dt in chunks:
                results.extend(area.atualizar(dt, []))
            return area, [item for item in results if item.get("meteoro")]

        coarse, coarse_meteors = emit([0.5])
        fine, fine_meteors = emit([0.05] * 10)

        self.assertEqual(coarse.meteoros, 10)
        self.assertEqual(coarse.meteoros_spawned, coarse.meteoros)
        self.assertEqual(fine.meteoros_spawned, fine.meteoros)
        self.assertEqual(len(coarse_meteors), 10)
        self.assertEqual(len(fine_meteors), 10)
        self.assertTrue(all(item["dano"] == 60.0 for item in coarse_meteors))
        self.assertTrue(all(item["raio"] == 3.0 for item in coarse_meteors))
        self.assertEqual(
            len({id(item["fonte_impacto"]) for item in coarse_meteors}),
            10,
        )

        target = self._fighter("Distant target", x=20.0)
        owner.rng_runtime = random.Random(6789)
        parent = AreaEffect("Apocalipse", 0.0, 5.0, owner)
        state_after_cast = owner.rng_runtime.getstate()
        parent.delay = 0.0
        parent.ativado = True
        simulation = self._simulation(owner, target)
        simulation.areas = [parent]
        with self._floating_text_patch():
            simulation.update(parent.duracao)

        self.assertEqual(len(simulation.areas), 10)
        self.assertTrue(all(child.elemento == "CAOS" for child in simulation.areas))
        self.assertTrue(all(child.dano == 60.0 for child in simulation.areas))  # re-pino O6f2: escala x2
        self.assertTrue(all(child.raio == 3.0 for child in simulation.areas))
        self.assertEqual(owner.rng_runtime.getstate(), state_after_cast)

        def meteor_positions(chunks):
            seeded_owner = self._fighter("Seeded caster", x=0.0)
            seeded_owner.rng_runtime = random.Random(12345)
            seeded_area = AreaEffect("Apocalipse", 0.0, 5.0, seeded_owner)
            seeded_area.delay = 0.0
            seeded_area.ativado = True
            events = []
            for dt in chunks:
                events.extend(seeded_area.atualizar(dt, []))
            return [
                (event["x"], event["y"])
                for event in events
                if event.get("meteoro")
            ]

        self.assertEqual(meteor_positions([0.5]), meteor_positions([0.05] * 10))

    def test_meteor_shower_damage_is_step_independent_with_visual_rng(self):
        def run(chunks):
            owner = self._fighter("Caster", x=0.0)
            owner.rng_runtime = random.Random(12345)
            target = self._fighter("Target", x=0.1)
            area = AreaEffect("Apocalipse", 0.0, 5.0, owner)
            area.delay = 0.0
            area.ativado = True
            area.raio_atual = area.raio
            simulation = self._simulation(owner, target)
            simulation.areas = [area]
            with self._floating_text_patch():
                for dt in chunks:
                    simulation.update(dt)
                simulation.update(0.0)
            return target.vida_max - target.vida

        self.assertEqual(run([0.5]), run([0.05] * 10))

    def test_delayed_area_exposes_visual_warning_before_activation(self):
        owner = self._fighter("Caster", x=0.0)
        area = AreaEffect("Julgamento de Thor", 0.0, 5.0, owner)

        self.assertFalse(area.ativado)
        self.assertEqual(area.raio_atual, 0.0)
        self.assertEqual(area.get_raio_visual(), area.raio)
        area.atualizar(1.0, [])
        self.assertEqual(area.get_raio_visual(), area.raio)
        area.atualizar(0.5, [])
        self.assertTrue(area.ativado)
        self.assertEqual(area.raio_atual, area.raio)
        self.assertEqual(area.get_raio_visual(), area.raio)

        edge_target = self._fighter("Edge target", x=1.8)
        exact = AreaEffect("Julgamento de Thor", 0.0, 5.0, owner)
        simulation = self._simulation(owner, edge_target)
        simulation.areas = [exact]
        with self._floating_text_patch():
            simulation.update(exact.delay_total)
        self.assertEqual(exact.raio_atual, exact.raio)
        self.assertLess(edge_target.vida, edge_target.vida_max)

    def test_area_chance_stun_controls_primary_paralysis(self):
        def resolve(random_value):
            owner = self._fighter("Caster", x=0.0)
            target = self._fighter("Target", x=0.1)
            area = AreaEffect("Campo Elétrico", 0.0, 5.0, owner)
            area.raio_atual = area.raio
            simulation = self._simulation(owner, target)
            simulation.areas = [area]
            with (
                self._floating_text_patch(),
                patch(
                    "neural_fights.core.combat.random.random",
                    return_value=random_value,
                ),
            ):
                simulation.update(0.0)
            return target

        stunned = resolve(0.29)
        spared = resolve(0.31)

        self.assertGreater(stunned.stun_timer, 0.0)
        self.assertEqual(spared.stun_timer, 0.0)
        self.assertLess(stunned.vida, stunned.vida_max)
        self.assertLess(spared.vida, spared.vida_max)

        with patch(
            "neural_fights.core.combat.get_skill_data",
            return_value={
                "tipo": "AREA",
                "dano": 1.0,
                "raio_area": 1.0,
                "efeito": "ATORDOAR",
                "chance_stun": 0.25,
            },
        ):
            synthetic = AreaEffect("Synthetic stun", 0.0, 5.0, stunned)
        with patch("neural_fights.core.combat.random.random", return_value=0.3):
            self.assertEqual(synthetic.sortear_efeito_principal(), "NORMAL")

    def test_area_periodic_damage_consumes_owner_damage_modifiers(self):
        owner = self._fighter("Caster", x=0.0)
        owner.mod_dano = 2.0
        target = self._fighter("Target", x=0.1)
        area = AreaEffect("Inferno", 0.0, 5.0, owner)
        area.raio_atual = area.raio
        area.tick_timer = 0.4
        area.alvos_atingidos.add(target)
        simulation = self._simulation(owner, target)
        simulation.areas = [area]

        with self._floating_text_patch():
            simulation.update(0.1)

        self.assertAlmostEqual(target.vida, target.vida_max - 20)  # re-pino O6f2

    def test_area_base_and_periodic_damage_are_step_independent_end_to_end(self):
        def run(chunks):
            owner = self._fighter("Caster", x=0.0)
            target = self._fighter("Target", x=0.1)
            area = AreaEffect("Inferno", 0.0, 5.0, owner)
            area.raio_atual = area.raio
            simulation = self._simulation(owner, target)
            simulation.areas = [area]
            with self._floating_text_patch():
                for dt in chunks:
                    simulation.update(dt)
            return target.vida_max - target.vida

        coarse_damage = run([5.0])
        fine_damage = run([0.1] * 50)

        self.assertAlmostEqual(coarse_damage, fine_damage)
        self.assertAlmostEqual(coarse_damage, 110.5)  # re-pino O6f2: escala de dano/cura de skill x2

    def test_periodic_area_cannot_bypass_skill_invulnerability(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=0.1)
        area = AreaEffect("Inferno", 0.0, 5.0, owner)
        area.raio_atual = area.raio
        area.tick_timer = 0.4
        area.alvos_atingidos.add(target)
        target.invencivel_timer = 1.0
        target.invulnerabilidade_skill_timer = 1.0
        simulation = self._simulation(owner, target)
        simulation.areas = [area]

        with self._floating_text_patch():
            simulation.update(0.1)

        self.assertEqual(target.vida, target.vida_max)
        self.assertEqual(
            target.ultimo_resultado_impacto.bloqueado_por,
            "invulnerabilidade_skill",
        )

    def test_area_status_stacks_ignore_only_hit_recovery_with_coarse_steps(self):
        def run(chunks):
            owner = self._fighter("Caster", x=0.0)
            target = self._fighter("Target", x=0.1)
            original_status = target._aplicar_efeito_status
            target._aplicar_efeito_status = Mock(wraps=original_status)
            area = AreaEffect("Nuvem Tóxica", 0.0, 5.0, owner)
            area.raio_atual = area.raio
            simulation = self._simulation(owner, target)
            simulation.areas = [area]
            with self._floating_text_patch():
                for dt in chunks:
                    simulation.update(dt)
            return [
                call.args[0]
                for call in target._aplicar_efeito_status.call_args_list
                if call.args and call.args[0] == "ENVENENADO"
            ]

        self.assertEqual(run([1.0]), ["ENVENENADO", "ENVENENADO"])
        self.assertEqual(run([0.1] * 10), ["ENVENENADO", "ENVENENADO"])

    def test_channel_impact_result_is_consumed_for_visual_feedback(self):
        owner = self._fighter("Caster", x=0.0)
        owner.angulo_olhar = 0.0
        target = self._fighter("Target", x=5.0)
        Channel("Desintegrar", owner)
        simulation = self._simulation(owner, target)

        with patch.object(
            _remaining_helpers.simulation_module,
            "FloatingText",
        ) as floating_text:
            simulation.update(0.1)

        self.assertLess(target.vida, target.vida_max)
        self.assertTrue(floating_text.called)

    def test_expiring_damage_buffs_are_independent_of_external_frame_size(self):
        def run(chunks, source):
            owner = self._fighter("Caster", x=0.0)
            target = self._fighter("Target", x=0.1 if source == "area" else 5.0)
            buff = Buff("Golpe do Executor", owner)
            buff.vida = 0.15
            owner.buffs_ativos.append(buff)
            simulation = self._simulation(owner, target)
            if source == "area":
                area = AreaEffect("Inferno", 0.0, 5.0, owner)
                area.raio_atual = area.raio
                simulation.areas = [area]
            else:
                owner.angulo_olhar = 0.0
                Channel("Desintegrar", owner)
            with self._floating_text_patch():
                for dt in chunks:
                    simulation.update(dt)
            return target.vida

        for source in ("area", "channel"):
            with self.subTest(source=source):
                self.assertAlmostEqual(
                    run([0.3], source),
                    run([0.1, 0.1, 0.1], source),
                )

    def test_celestial_pillars_are_distinct_blows(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=0.1)
        area = AreaEffect("Julgamento Celestial", 0.0, 5.0, owner)
        area.delay = 0.0
        area.ativado = True
        # Geometria controlada é legítima AQUI: o contrato testado é a
        # identidade de impacto, não o sorteio das posições.
        area.posicoes_pilares = [tuple(target.pos)] * area.pilares
        simulation = self._simulation(owner, target)
        simulation.areas = [area]
        life_before = target.vida

        with self._floating_text_patch():
            simulation.update(0.0)
            self.assertEqual(len(simulation.areas), 5)
            sources = {id(child.fonte_impacto) for child in simulation.areas}
            self.assertEqual(len(sources), 5)
            for child in simulation.areas:
                self.assertTrue(child.ignorar_invencibilidade)
                self.assertEqual(child.dano_por_segundo, 0.0)
                self.assertFalse(child.aviso_visual)
            simulation.update(0.01)

        self.assertLess(target.vida, life_before)
        # Cada pilar registra a própria fonte: cinco golpes distintos.
        self.assertEqual(len(target._fontes_impacto_recentes), 5)

    def test_celestial_first_pillar_lands_on_the_cast_anchor(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=0.1)
        area = AreaEffect(
            "Julgamento Celestial", target.pos[0], target.pos[1], owner
        )
        area.delay = 0.0
        area.ativado = True
        simulation = self._simulation(owner, target)
        simulation.areas = [area]
        life_before = target.vida

        # O primeiro pilar cai na âncora do cast (o alvo previsto).
        self.assertEqual(
            area.posicoes_pilares[0], (target.pos[0], target.pos[1])
        )
        with self._floating_text_patch():
            simulation.update(0.0)
            simulation.update(0.01)

        # Alvo parado na âncora É atingido: o "buraco morto" morreu.
        self.assertLess(target.vida, life_before)

    def test_celestial_pillar_damage_splits_the_cast_budget(self):
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=8.0)
        area = AreaEffect("Julgamento Celestial", 0.0, 5.0, owner)
        area.delay = 0.0
        area.ativado = True
        simulation = self._simulation(owner, target)
        simulation.areas = [area]

        with self._floating_text_patch():
            simulation.update(0.0)

        for child in simulation.areas:
            self.assertAlmostEqual(child.dano, area.dano * 0.5)

    def test_celestial_warning_shows_the_real_pillar_volumes(self):
        owner = self._fighter("Caster", x=0.0)
        area = AreaEffect("Julgamento Celestial", 0.0, 5.0, owner)

        self.assertFalse(area.ativado)
        avisos = area.get_avisos_visuais()
        # O aviso desenha os pilares reais, não o raio de sorteio.
        self.assertEqual(len(avisos), area.pilares)
        self.assertEqual(
            [(x, y) for x, y, _ in avisos], area.posicoes_pilares
        )
        for _, _, raio in avisos:
            self.assertAlmostEqual(raio, area.raio_pilar)

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
