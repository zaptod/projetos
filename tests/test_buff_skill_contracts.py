"""Regressoes para campos avancados de buffs e fontes magicas."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from neural_fights.core.combat import AreaEffect, Beam, Buff, Projetil, criar_metadata_impacto
from neural_fights.core.skills import get_skill_data
from neural_fights.simulation.simulacao import Simulador
from tests import test_remaining_skill_regressions as _helpers


class BuffSkillContractTests(unittest.TestCase):
    _fighter = staticmethod(_helpers.RemainingSkillRegressionTests._fighter)
    _add_class_skill = staticmethod(
        _helpers.RemainingSkillRegressionTests._add_class_skill
    )

    def test_amplification_is_a_cast_snapshot_for_magic_damage_and_area(self):
        caster = self._fighter("Mage")
        with patch("neural_fights.core.entities.random.random", return_value=1.0):
            physical_baseline, _ = caster.calcular_dano_ataque(10.0)
        caster.buffs_ativos.append(Buff("Amplificar Magia", caster))

        projectile = Projetil("Disparo de Mana", 0.0, 0.0, 0.0, caster)
        area = AreaEffect("Explosão Arcana", 0.0, 0.0, caster)
        persistent_area = AreaEffect("Tentáculos do Vazio", 0.0, 0.0, caster)
        with patch("neural_fights.core.entities.random.random", return_value=1.0):
            physical_damage, _ = caster.calcular_dano_ataque(10.0)

        self.assertAlmostEqual(projectile.dano, 30.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertAlmostEqual(area.dano, 105.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertAlmostEqual(area.raio, 3.25)
        self.assertAlmostEqual(persistent_area.dano_por_segundo, 24.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertAlmostEqual(physical_damage, physical_baseline)

        caster.buffs_ativos.clear()
        self.assertAlmostEqual(projectile.dano, 30.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertAlmostEqual(area.dano, 105.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertAlmostEqual(area.raio, 3.25)

    def test_prediction_consumes_only_two_accepted_hostile_impacts(self):
        attacker = self._fighter("Attacker")
        defender = self._fighter("Seer")
        prediction = Buff("Previsão", defender)
        defender.buffs_ativos.append(prediction)

        # Onda 2: a invencibilidade bloqueia o RE-IMPACTO do mesmo golpe, nao
        # qualquer fonte. O andaime agora reproduz exatamente isso: a mesma
        # fonte tenta bater de novo dentro da janela.
        fonte_repetida = object()
        defender.invencivel_timer = 1.0
        defender._invencivel_chave = ("fonte", fonte_repetida)
        rejected = defender.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=fonte_repetida,
        )
        self.assertEqual(rejected.bloqueado_por, "invencibilidade")
        self.assertEqual(prediction.esquivas_restantes, 2)

        defender.invencivel_timer = 0.0
        for remaining in (1, 0):
            result = defender.resolver_impacto(
                10.0,
                0.0,
                0.0,
                atacante=attacker,
                fonte_impacto=object(),
            )
            self.assertEqual(result.bloqueado_por, "previsao")
            self.assertEqual(prediction.esquivas_restantes, remaining)

        life_before = defender.vida
        result = defender.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=object(),
        )
        self.assertTrue(result.atingiu)
        self.assertLess(defender.vida, life_before)
        self.assertTrue(defender.ve_ataques_hostis())

    def test_shadow_portal_has_delayed_untargetable_exit_and_cast_parity(self):
        for source in ("class", "weapon"):
            with self.subTest(source=source):
                caster = self._fighter(f"Shadow {source}", x=1.0)
                enemy = self._fighter("Enemy", x=20.0)
                data = get_skill_data("Portal Sombrio")
                if source == "class":
                    self._add_class_skill(caster, "Portal Sombrio")
                    cast = lambda: caster.usar_skill_classe("Portal Sombrio")
                else:
                    caster.skills_arma = [
                        {"nome": "Portal Sombrio", "custo": data["custo"], "data": data}
                    ]
                    caster.cd_skills["Portal Sombrio"] = 0.0
                    cast = lambda: caster.usar_skill_arma(0)

                mana_before = caster.mana
                with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
                    self.assertTrue(cast())
                self.assertEqual(caster.pos[0], 1.0)
                self.assertTrue(caster.em_transicao_sombria())
                self.assertAlmostEqual(caster.mana, mana_before - data["custo"])
                self.assertEqual(caster.cd_skills["Portal Sombrio"], 10.0)

                impact = caster.resolver_impacto(
                    20.0,
                    0.0,
                    0.0,
                    atacante=enemy,
                    fonte_impacto=object(),
                )
                self.assertEqual(impact.bloqueado_por, "intangibilidade")
                caster.update(0.25, enemy)
                self.assertEqual(caster.pos[0], 1.0)
                caster.update(0.25, enemy)
                self.assertFalse(caster.em_transicao_sombria())
                self.assertAlmostEqual(caster.pos[0], 9.0)

    def test_shadow_portal_removes_fighter_from_physics_targets_and_rendering(self):
        caster = self._fighter("Shadow", x=1.0)
        enemy = self._fighter("Enemy", x=1.0)
        self._add_class_skill(caster, "Portal Sombrio")

        with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(caster.usar_skill_classe("Portal Sombrio"))

        simulation = Simulador.__new__(Simulador)
        simulation.p1 = caster
        simulation.p2 = enemy
        positions_before = (tuple(caster.pos), tuple(enemy.pos))

        simulation.resolver_fisica_corpos(0.1)
        self.assertEqual((tuple(caster.pos), tuple(enemy.pos)), positions_before)
        self.assertNotIn(caster, simulation._obter_alvos_hostis(enemy))
        self.assertIsNone(simulation.desenhar_lutador(caster))

        caster.update(0.5, enemy)
        self.assertIn(caster, simulation._obter_alvos_hostis(enemy))

    def test_dash_arrival_area_snapshots_magic_amplification_only(self):
        magic_caster = self._fighter("Shadow Mage")
        magic_caster.buffs_ativos.append(Buff("Amplificar Magia", magic_caster))
        portal_data = dict(get_skill_data("Portal Sombrio"))
        portal_data["dano_chegada"] = 10.0
        magic_caster._finalizar_dash_skill(
            "Portal Sombrio",
            portal_data,
            (0.0, 0.0),
            (1.0, 0.0),
            0.0,
        )
        magic_area = magic_caster.buffer_areas[-1]
        self.assertAlmostEqual(magic_area.dano, 15.0)
        self.assertAlmostEqual(magic_area.raio, 1.95)

        physical_caster = self._fighter("Warrior")
        physical_caster.buffs_ativos.append(
            Buff("Amplificar Magia", physical_caster)
        )
        advance_data = get_skill_data("Avanço Brutal")
        physical_caster._finalizar_dash_skill(
            "Avanço Brutal",
            advance_data,
            (0.0, 0.0),
            (1.0, 0.0),
            0.0,
        )
        physical_area = physical_caster.buffer_areas[-1]
        self.assertAlmostEqual(physical_area.dano, 50.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertAlmostEqual(physical_area.raio, 1.5)

    def test_holy_bonuses_apply_only_to_explicit_dark_affinity(self):
        caster = self._fighter("Paladin")
        normal = self._fighter("Normal")
        dark = self._fighter("Dark")
        dark.classe_nome = "Necromante (Trevas)"

        def projectile_damage(target):
            source = Projetil("Smite", 0.0, 0.0, 0.0, caster)
            return target.resolver_impacto(
                source.dano,
                0.0,
                0.0,
                atacante=caster,
                fonte_impacto=source.fonte_impacto,
                metadata_impacto=criar_metadata_impacto(source),
            ).dano

        self.assertAlmostEqual(projectile_damage(dark), projectile_damage(normal) * 1.5)

        dark.invencivel_timer = 0.0
        normal.invencivel_timer = 0.0
        beam_dark = Beam("Raio Sagrado", 0.0, 0.0, 1.0, 0.0, caster)
        beam_normal = Beam("Raio Sagrado", 0.0, 0.0, 1.0, 0.0, caster)
        damage_dark = dark.resolver_impacto(
            beam_dark.dano,
            0.0,
            0.0,
            atacante=caster,
            fonte_impacto=beam_dark,
            metadata_impacto=criar_metadata_impacto(beam_dark),
        ).dano
        damage_normal = normal.resolver_impacto(
            beam_normal.dano,
            0.0,
            0.0,
            atacante=caster,
            fonte_impacto=beam_normal,
            metadata_impacto=criar_metadata_impacto(beam_normal),
        ).dano
        self.assertAlmostEqual(damage_dark, damage_normal * 2.0)

        caster.arma_encantamentos = ["Sagrado"]
        with patch("neural_fights.core.entities.random.random", return_value=1.0):
            normal_melee, _ = caster.calcular_dano_ataque(100.0, normal)
            dark_melee, _ = caster.calcular_dano_ataque(100.0, dark)
        self.assertAlmostEqual(dark_melee, normal_melee * 1.35)

    def test_ember_shield_retaliates_once_per_accepted_melee_source(self):
        attacker = self._fighter("Attacker")
        defender = self._fighter("Defender")
        ember = Buff("Escudo de Brasas", defender)
        defender.buffs_ativos.append(ember)
        source = object()
        life_before = attacker.vida

        first = defender.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=source,
            metadata_impacto={"eh_corpo_a_corpo": True},
        )
        self.assertTrue(first.atingiu)
        self.assertEqual(first.dano, 0.0)
        self.assertAlmostEqual(attacker.vida, life_before - 20.0)  # re-pino O6f2: escala x2

        defender.invencivel_timer = 0.0
        defender.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=source,
            metadata_impacto={"eh_corpo_a_corpo": True},
        )
        self.assertAlmostEqual(attacker.vida, life_before - 20.0)  # re-pino O6f2: escala x2

        defender.invencivel_timer = 0.0
        defender.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=object(),
            metadata_impacto={"eh_skill": True, "eh_projetil": True},
        )
        self.assertAlmostEqual(attacker.vida, life_before - 20.0)  # re-pino O6f2: escala x2

    def test_instant_buffs_are_not_persisted_or_stealable(self):
        healer = self._fighter("Healer")
        self._add_class_skill(healer, "Cura Menor")
        healer.vida -= 50.0
        with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(healer.usar_skill_classe("Cura Menor"))
        self.assertEqual(healer.buffs_ativos, [])

        thief = self._fighter("Thief")
        victim = self._fighter("Victim")
        inert = Buff("Cura Menor", victim)
        persistent = Buff("Acelerar", victim)
        victim.buffs_ativos.extend((inert, persistent))
        thief.rng_runtime = type(
            "FirstChoice",
            (),
            {"choice": staticmethod(lambda values: values[0])},
        )()

        stolen = thief._roubar_buff_do_alvo(victim)
        self.assertIsNot(stolen, persistent)
        self.assertEqual(stolen.nome, persistent.nome)
        self.assertIn(inert, victim.buffs_ativos)
        self.assertNotIn(persistent, victim.buffs_ativos)


if __name__ == "__main__":
    unittest.main()
