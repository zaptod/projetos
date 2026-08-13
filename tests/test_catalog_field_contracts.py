"""Contratos E2E dos campos mecanicos restantes do catalogo de skills."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.core.combat import AreaEffect, Buff, Projetil, Trap, Transform
from neural_fights.core.skills import get_skill_data
from tests import test_remaining_skill_regressions as helpers


class CatalogFieldContractTests(unittest.TestCase):
    _fighter = staticmethod(helpers.RemainingSkillRegressionTests._fighter)
    _simulation = staticmethod(helpers.RemainingSkillRegressionTests._simulation)
    _floating_text_patch = staticmethod(
        helpers.RemainingSkillRegressionTests._floating_text_patch
    )
    _add_class_skill = staticmethod(
        helpers.RemainingSkillRegressionTests._add_class_skill
    )

    def _resolve_area(self, skill_name: str):
        owner = self._fighter(f"{skill_name} caster", x=0.0)
        target = self._fighter(f"{skill_name} target", x=0.1)
        area = AreaEffect(skill_name, 0.0, 5.0, owner)
        area.raio_atual = area.raio
        simulation = self._simulation(owner, target)
        simulation.areas = [area]
        with self._floating_text_patch():
            simulation.update(0.0)
        return owner, target, area

    def test_avatar_ice_aura_uses_declared_radius_and_slow_factor(self):
        owner = self._fighter("Avatar", x=0.0)
        inside = self._fighter("Inside", x=2.0)
        transform = Transform("Avatar de Gelo", owner)
        simulation = self._simulation(owner, inside)

        with self._floating_text_patch():
            simulation.update(0.1)

        self.assertIs(owner.transformacao_ativa, transform)
        self.assertAlmostEqual(transform.aura_raio, 3.0)
        self.assertAlmostEqual(inside.slow_fator, 0.6)
        self.assertGreater(inside.slow_timer, 0.0)

        outside = self._fighter("Outside", x=3.1)
        outside_simulation = self._simulation(owner, outside)
        with self._floating_text_patch():
            outside_simulation.update(0.1)
        self.assertEqual(outside.slow_fator, 1.0)

    def test_trap_blocks_movement_and_repeats_declared_contact_damage(self):
        owner = self._fighter("Wall owner", x=20.0)
        target = self._fighter("Wall target", x=0.1)
        catalog_data = dict(get_skill_data("Muralha de Gelo"))
        catalog_data["dano"] = 10.0

        with patch(
            "neural_fights.core.combat.get_skill_data",
            return_value=catalog_data,
        ):
            trap = Trap("Muralha de Gelo", 0.0, 5.0, owner)

        simulation = self._simulation(owner, target)
        simulation.traps = [trap]
        # A parede expulsa o alvo no primeiro subpasso; cada nova entrada
        # recebe exatamente o dano proporcional ao tempo de contato.
        expected_tick = owner.get_dano_modificado(10.0 * 0.1)
        with self._floating_text_patch():
            simulation.update(0.1)
        self.assertGreaterEqual(abs(target.pos[0] - trap.x), trap.largura / 2)
        self.assertAlmostEqual(target.vida_max - target.vida, expected_tick)

        target.pos[:] = [0.1, 5.0]
        with self._floating_text_patch():
            simulation.update(0.1)
        self.assertAlmostEqual(target.vida_max - target.vida, expected_tick * 2.0)

    def test_blood_pact_pays_health_then_buffs_damage_and_real_lifesteal(self):
        owner = self._fighter("Blood caster")
        target = self._fighter("Blood target")
        self._add_class_skill(owner, "Pacto de Sangue")
        owner.vida = 800.0
        base_damage = owner.get_dano_modificado(10.0)

        with patch(
            "neural_fights.effects.audio.AudioManager.get_instance",
            return_value=None,
        ):
            self.assertTrue(owner.usar_skill_classe("Pacto de Sangue"))

        self.assertAlmostEqual(owner.vida, 770.0)
        buffed_damage = owner.get_dano_modificado(10.0)
        self.assertAlmostEqual(buffed_damage, base_damage * 1.8)
        result = target.resolver_impacto(
            buffed_damage,
            0.0,
            0.0,
            atacante=owner,
            fonte_impacto=object(),
        )
        self.assertTrue(result.atingiu)
        self.assertAlmostEqual(owner.vida, 770.0 + result.dano * 0.2)

    def test_speed_buff_aliases_change_final_speed_attack_rate_and_damage_taken(self):
        accelerated = self._fighter("Accelerated")
        base_speed = accelerated.get_velocidade_movimento()
        accelerated.buffs_ativos.append(Buff("Velocidade Arcana", accelerated))
        self.assertAlmostEqual(
            accelerated.get_velocidade_movimento(),
            base_speed * 1.5,
        )

        overloaded = self._fighter("Overloaded")
        attacker = self._fighter("Attacker")
        overloaded.buffs_ativos.append(Buff("Sobrecarga", overloaded))
        self.assertAlmostEqual(
            overloaded.get_velocidade_movimento(),
            overloaded.velocidade_movimento_base * 1.3,
        )
        self.assertAlmostEqual(
            overloaded._get_modificador_velocidade_ataque_buff(),
            1.5,
        )
        result = overloaded.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=object(),
        )
        self.assertAlmostEqual(result.dano, 12.0)

    def test_projectile_conditions_change_real_damage_and_execute_low_health(self):
        owner = self._fighter("Conditional caster", x=-5.0)
        burning = self._fighter("Burning target", x=0.0)
        burning._aplicar_efeito_status("QUEIMANDO")
        combustion = Projetil("Combustão Espontânea", 0.0, 5.0, 0.0, owner)
        simulation = self._simulation(owner, burning)
        simulation.projeteis = [combustion]
        expected = owner.get_dano_modificado(combustion.dano) * 2.0
        with self._floating_text_patch():
            simulation.update(0.0)
        self.assertAlmostEqual(burning.vida_max - burning.vida, expected)

        victim = self._fighter("Execution target", x=0.0)
        victim.vida = victim.vida_max * 0.25
        execution = Projetil("Morte Glacial", 0.0, 5.0, 0.0, owner)
        execution_simulation = self._simulation(owner, victim)
        execution_simulation.projeteis = [execution]
        self.assertEqual(execution.verificar_condicao(victim), 10.0)
        with self._floating_text_patch():
            execution_simulation.update(0.0)
        self.assertTrue(victim.morto)

    def test_sacrifice_pays_declared_max_health_percentage_and_creates_area(self):
        owner = self._fighter("Sacrifice caster")
        self._add_class_skill(owner, "Sacrifício")
        with patch(
            "neural_fights.effects.audio.AudioManager.get_instance",
            return_value=None,
        ):
            self.assertTrue(owner.usar_skill_classe("Sacrifício"))
        self.assertAlmostEqual(owner.vida, owner.vida_max * 0.5)
        self.assertEqual(len(owner.buffer_areas), 1)
        self.assertEqual(owner.buffer_areas[0].nome, "Sacrifício")

    def test_chaos_projectile_consumes_injected_element_and_damage_rolls(self):
        owner = self._fighter("Chaos caster")
        owner.rng_runtime = SimpleNamespace(
            choice=lambda _options: "RAIO",
            uniform=lambda _low, _high: 2.0,
        )
        projectile = Projetil("Chama Caótica", 0.0, 5.0, 0.0, owner)
        self.assertEqual(projectile.elemento, "RAIO")
        self.assertEqual(projectile.cor, (255, 255, 100))
        self.assertAlmostEqual(projectile.dano, 60.0)

    def test_area_catalog_durations_and_slow_reach_target_runtime(self):
        _, frozen, absolute_zero = self._resolve_area("Zero Absoluto")
        self.assertAlmostEqual(absolute_zero.duracao_stun, 3.0)
        self.assertAlmostEqual(frozen.stun_timer, 3.0)

        _, afraid, deep_fear = self._resolve_area("Medo Profundo")
        self.assertAlmostEqual(deep_fear.duracao_fear, 2.5)
        self.assertAlmostEqual(afraid.medo_timer, 2.5)

        charmer, charmed, spores = self._resolve_area("Esporos Alucinógenos")
        self.assertAlmostEqual(spores.duracao_charme, 2.0)
        self.assertAlmostEqual(charmed.charme_timer, 2.0)
        self.assertIs(charmed.charme_origem, charmer)

        _, slowed, blizzard = self._resolve_area("Nevasca")
        self.assertAlmostEqual(blizzard.slow_fator, 0.4)
        self.assertAlmostEqual(slowed.slow_fator, 0.4)
        self.assertAlmostEqual(slowed.slow_timer, 3.0)

    def test_arcane_missile_homing_turns_toward_nearest_hostile(self):
        owner = self._fighter("Missile caster", x=-5.0)
        target = self._fighter("Homing target", x=0.0, y=10.0)
        projectile = Projetil("Mísseis Arcanos", 0.0, 5.0, 0.0, owner)
        projectile.atualizar(0.1, [owner, target])
        self.assertIs(projectile.alvo, target)
        self.assertAlmostEqual(projectile.angulo, 18.0)

    def test_shadow_sphere_heals_from_projectile_damage_actually_applied(self):
        owner = self._fighter("Drain caster", x=-5.0)
        target = self._fighter("Drain target", x=0.0)
        owner.vida = 700.0
        projectile = Projetil("Esfera Sombria", 0.0, 5.0, 0.0, owner)
        simulation = self._simulation(owner, target)
        simulation.projeteis = [projectile]
        before_owner = owner.vida
        before_target = target.vida
        with self._floating_text_patch():
            simulation.update(0.0)
        applied = before_target - target.vida
        self.assertGreater(applied, 0.0)
        self.assertAlmostEqual(owner.vida - before_owner, applied * 0.3)

    def test_mirrored_reflection_returns_declared_fraction_of_accepted_damage(self):
        defender = self._fighter("Mirror defender")
        attacker = self._fighter("Mirror attacker")
        defender.buffs_ativos.append(Buff("Reflexo Espelhado", defender))
        result = defender.resolver_impacto(
            20.0,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=object(),
        )
        self.assertAlmostEqual(result.dano, 20.0)
        self.assertAlmostEqual(attacker.vida_max - attacker.vida, 10.0)


if __name__ == "__main__":
    unittest.main()
