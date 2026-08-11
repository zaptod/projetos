"""End-to-end regressions for death-triggered skills and kill ownership."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neural_fights.ai.brain import AIBrain
from neural_fights.ai.skill_strategy import SkillStrategySystem
from neural_fights.core.combat import AreaEffect, Buff, Projetil, criar_metadata_impacto
from neural_fights.core.entities import Lutador
from neural_fights.core.skills import get_skill_data


class DeathSkillRegressionTests(unittest.TestCase):
    @staticmethod
    def _fighter(name: str, x: float = 0.0) -> Lutador:
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
            fighter = Lutador(data, x, 0.0)
        fighter.vida_max = 100.0
        fighter.vida = fighter.vida_max
        fighter.mana_max = 200.0
        fighter.mana = fighter.mana_max
        return fighter

    @staticmethod
    def _add_class_skill(fighter: Lutador, name: str) -> None:
        data = get_skill_data(name)
        fighter.skills_classe.append(
            {"nome": name, "custo": data.get("custo", 0.0), "data": data}
        )
        fighter.cd_skills[name] = 0.0

    @staticmethod
    def _hit(attacker: Lutador, target: Lutador, damage: float = 200.0):
        target.invencivel_timer = 0.0
        return target.resolver_impacto(
            damage,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=object(),
        )

    def test_last_breath_has_priority_then_resurrection_spends_real_resources(self):
        attacker = self._fighter("Attacker")
        target = self._fighter("Survivor")
        self._add_class_skill(target, "Ressurreição")
        self._add_class_skill(target, "Último Suspiro")

        first = self._hit(attacker, target)

        self.assertFalse(first.morreu)
        self.assertFalse(target.morto)
        self.assertEqual(target.vida, 50.0)
        self.assertEqual(target.cd_skills["Último Suspiro"], 90.0)
        self.assertEqual(target.cd_skills["Ressurreição"], 0.0)
        self.assertEqual(target.mana, 200.0)

        second = self._hit(attacker, target)

        self.assertFalse(second.morreu)
        self.assertFalse(target.morto)
        self.assertEqual(target.vida, 30.0)
        self.assertEqual(target.cd_skills["Ressurreição"], 120.0)
        self.assertEqual(target.mana, 120.0)

        third = self._hit(attacker, target)

        self.assertTrue(third.morreu)
        self.assertTrue(target.morto)
        self.assertEqual(target.vida, 0.0)

    def test_resurrection_does_not_trigger_without_mana_or_while_on_cooldown(self):
        attacker = self._fighter("Attacker")

        no_mana = self._fighter("No mana")
        self._add_class_skill(no_mana, "Ressurreição")
        no_mana.mana = 79.0
        result = self._hit(attacker, no_mana)
        self.assertTrue(result.morreu)
        self.assertTrue(no_mana.morto)
        self.assertEqual(no_mana.mana, 79.0)
        self.assertEqual(no_mana.cd_skills["Ressurreição"], 0.0)

        on_cooldown = self._fighter("On cooldown")
        self._add_class_skill(on_cooldown, "Ressurreição")
        on_cooldown.cd_skills["Ressurreição"] = 1.0
        result = self._hit(attacker, on_cooldown)
        self.assertTrue(result.morreu)
        self.assertTrue(on_cooldown.morto)
        self.assertEqual(on_cooldown.mana, 200.0)
        self.assertEqual(on_cooldown.cd_skills["Ressurreição"], 1.0)

    def test_death_cooldown_is_canonical_with_zero_cd_buff_and_duplicate_slot(self):
        attacker = self._fighter("Attacker")
        target = self._fighter("Duplicate passive")
        self._add_class_skill(target, "Último Suspiro")
        passive_data = get_skill_data("Último Suspiro")
        target.skills_arma.append(
            {
                "nome": "Último Suspiro",
                "custo": passive_data["custo"],
                "data": passive_data,
            }
        )
        target.skill_arma_nome = "Último Suspiro"
        target.buffs_ativos.append(Buff("Conjuração Perfeita", target))

        first = self._hit(attacker, target)

        self.assertFalse(first.morreu)
        self.assertEqual(target.vida, 50.0)
        self.assertEqual(target.cd_skills["Último Suspiro"], 90.0)
        self.assertEqual(target.cd_skill_arma, 90.0)

        second = self._hit(attacker, target)

        self.assertTrue(second.morreu)
        self.assertTrue(target.morto)

    def test_death_passives_cannot_be_cast_or_materialize_inert_buffs(self):
        fighter = self._fighter("Passive owner")
        for skill_name in ("Último Suspiro", "Ressurreição"):
            with self.subTest(skill=skill_name):
                self._add_class_skill(fighter, skill_name)
                mana_before = fighter.mana
                with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
                    self.assertFalse(fighter.usar_skill_classe(skill_name))
                self.assertEqual(fighter.mana, mana_before)
                self.assertEqual(fighter.cd_skills[skill_name], 0.0)
                self.assertFalse(
                    fighter._aplicar_buff_skill(
                        skill_name,
                        get_skill_data(skill_name),
                        Buff,
                    )
                )
                self.assertEqual(fighter.buffs_ativos, [])

    def test_harvest_heals_flat_amount_only_after_a_terminal_owned_kill(self):
        owner = self._fighter("Reaper")
        owner.vida = 10.0

        survivor = self._fighter("Survivor")
        survivor.vida = 40.0
        self._add_class_skill(survivor, "Último Suspiro")
        first_harvest = AreaEffect("Colheita de Almas", 0.0, 0.0, owner)
        first = survivor.resolver_impacto(
            first_harvest.dano,
            0.0,
            0.0,
            first_harvest.tipo_efeito,
            atacante=owner,
            fonte_impacto=first_harvest.fonte_impacto,
            metadata_impacto=criar_metadata_impacto(first_harvest),
        )

        self.assertFalse(first.morreu)
        self.assertEqual(survivor.vida, 50.0)
        self.assertEqual(owner.vida, 10.0)

        victim = self._fighter("Victim")
        victim.vida = 40.0
        second_harvest = AreaEffect("Colheita de Almas", 0.0, 0.0, owner)
        second = victim.resolver_impacto(
            second_harvest.dano,
            0.0,
            0.0,
            second_harvest.tipo_efeito,
            atacante=owner,
            fonte_impacto=second_harvest.fonte_impacto,
            metadata_impacto=criar_metadata_impacto(second_harvest),
        )

        self.assertTrue(second.morreu)
        self.assertEqual(owner.vida, 60.0)
        self.assertFalse(victim.morrer())
        self.assertEqual(owner.vida, 60.0)

    def test_harvest_ownership_survives_soul_link_damage(self):
        owner = self._fighter("Reaper")
        owner.vida = 10.0
        primary = self._fighter("Primary")
        linked = self._fighter("Linked")
        linked.vida = 20.0
        self.assertTrue(
            primary._aplicar_efeito_status(
                "LINK_ALMA",
                origem=linked,
                duracao=5.0,
                percentual_efeito=0.5,
            )
        )
        harvest = AreaEffect("Colheita de Almas", 0.0, 0.0, owner)

        impact = primary.resolver_impacto(
            harvest.dano,
            0.0,
            0.0,
            harvest.tipo_efeito,
            atacante=owner,
            fonte_impacto=harvest.fonte_impacto,
            metadata_impacto=criar_metadata_impacto(harvest),
        )

        self.assertFalse(impact.morreu)
        self.assertFalse(primary.morto)
        self.assertTrue(linked.morto)
        self.assertEqual(owner.vida, 60.0)

    def test_dot_keeps_original_attacker_and_source_until_terminal_death(self):
        owner = self._fighter("Poisoner")
        victim = self._fighter("Poisoned")
        victim.vida = 0.5
        source = Projetil("Dardo Venenoso", 0.0, 0.0, 0.0, owner)
        notification = Mock(wraps=owner._notificar_morte_causada)
        owner._notificar_morte_causada = notification

        applied = victim.resolver_impacto(
            0.0,
            0.0,
            0.0,
            source.tipo_efeito,
            atacante=owner,
            fonte_impacto=source,
            metadata_impacto=criar_metadata_impacto(source),
        )
        self.assertTrue(applied.efeito_aplicado)
        self.assertEqual(len(victim.dots_ativos), 1)

        victim.dots_ativos[0].atualizar(0.5)

        self.assertTrue(victim.morto)
        notification.assert_called_once()
        context = notification.call_args.args[1]
        self.assertIs(context.atacante, owner)
        self.assertIs(context.fonte, source)
        self.assertEqual(context.nome_skill, "Dardo Venenoso")

    def test_reflection_reassigns_kill_credit_and_is_idempotent(self):
        attacker = self._fighter("Attacker")
        attacker.vida = 20.0
        reflector = self._fighter("Reflector")
        reflector.buffs_ativos.append(
            SimpleNamespace(
                ativo=True,
                mod_dano_recebido=1.0,
                escudo_atual=0.0,
                refletir=1.0,
            )
        )
        notification = Mock(wraps=reflector._notificar_morte_causada)
        reflector._notificar_morte_causada = notification

        reflector.resolver_impacto(30.0, 0.0, 0.0, atacante=attacker)

        self.assertTrue(attacker.morto)
        notification.assert_called_once()
        context = notification.call_args.args[1]
        self.assertIs(context.atacante, reflector)
        self.assertTrue(context.metadata["refletido"])

    def test_ai_layers_exclude_death_passives_from_active_candidates(self):
        passive_data = get_skill_data("Último Suspiro")
        info = {
            "nome": "Último Suspiro",
            "data": passive_data,
            "fonte": "classe",
            "custo": 0.0,
        }

        brain = object.__new__(AIBrain)
        brain.skills_por_tipo = {
            skill_type: []
            for skill_type in (
                "PROJETIL",
                "BEAM",
                "AREA",
                "DASH",
                "BUFF",
                "SUMMON",
                "TRAP",
                "TRANSFORM",
                "CHANNEL",
            )
        }
        brain._adicionar_skill(info["nome"], passive_data, "classe")
        self.assertEqual(brain.skills_por_tipo["BUFF"], [])
        self.assertFalse(brain._avaliar_uso_skill(passive_data, 1.0, None))

        strategy = object.__new__(SkillStrategySystem)
        strategy.skills = {}
        strategy.skills_por_tipo = {"BUFF": []}
        strategy._analisar_skill(info, "classe")
        self.assertEqual(strategy.skills, {})
        self.assertEqual(strategy.skills_por_tipo["BUFF"], [])


if __name__ == "__main__":
    unittest.main()
