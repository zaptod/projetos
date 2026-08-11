"""Regressoes E2E para os ultimos campos avancados do catalogo."""

from __future__ import annotations

import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import simulation.simulacao as simulation_module
from core.combat import (
    ArmaProjetil,
    AreaEffect,
    Buff,
    Projetil,
    criar_metadata_impacto,
)
from core.entities import Lutador
from core.skills import get_skill_data
from simulation.simulacao import Simulador


class RemainingSkillRegressionTests(unittest.TestCase):
    @staticmethod
    def _fighter(name: str, x: float = 0.0, y: float = 5.0) -> Lutador:
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
            fighter = Lutador(data, x, y)
        fighter.vida_max = 1000.0
        fighter.vida = fighter.vida_max
        fighter.mana_max = 200.0
        fighter.mana = fighter.mana_max
        fighter._registrar_estado_historico()
        return fighter

    @staticmethod
    def _add_class_skill(fighter: Lutador, name: str) -> None:
        data = get_skill_data(name)
        fighter.skills_classe.append(
            {"nome": name, "custo": data.get("custo", 0.0), "data": data}
        )
        fighter.cd_skills[name] = 0.0

    @staticmethod
    def _simulation(owner: Lutador, target: Lutador) -> Simulador:
        simulation = object.__new__(Simulador)
        simulation.cam = SimpleNamespace(
            x=0.0,
            atualizar=lambda *_args: None,
            aplicar_shake=lambda *_args: None,
        )
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
        simulation.areas = []
        simulation.beams = []
        simulation.summons = []
        simulation.traps = []
        simulation.portais = []
        simulation._verificar_clash_projeteis = lambda: None
        simulation.audio = None
        simulation.vencedor = "fixture-already-finished"
        simulation.movement_anims = None
        simulation.attack_anims = None
        simulation.particulas = []
        simulation.decals = []
        return simulation

    @staticmethod
    def _floating_text_patch():
        return patch.object(
            simulation_module,
            "FloatingText",
            return_value=SimpleNamespace(vida=1.0, update=lambda _dt: None),
        )

    def test_perfect_conjuration_halves_mana_and_removes_skill_cooldown(self):
        caster = self._fighter("Conjurador")
        self._add_class_skill(caster, "Conjuração Perfeita")
        self._add_class_skill(caster, "Disparo de Mana")

        with patch("effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(caster.usar_skill_classe("Conjuração Perfeita"))
            mana_antes = caster.mana
            self.assertTrue(caster.usar_skill_classe("Disparo de Mana"))

        self.assertAlmostEqual(caster.mana, mana_antes - 4.0)
        self.assertEqual(caster.cd_skills["Disparo de Mana"], 0.0)

    def test_revert_restores_only_historical_hp_and_position(self):
        caster = self._fighter("Cronomante", x=1.0, y=2.0)
        self._add_class_skill(caster, "Reverter")
        caster._tempo_runtime = 0.0
        caster.vida = 900.0
        caster.pos[:] = [1.0, 2.0]
        caster._registrar_estado_historico()
        caster._tempo_runtime = 3.0
        caster.vida = 250.0
        caster.pos[:] = [9.0, 8.0]
        caster.vel[:] = [4.0, -2.0]
        caster.mana = 100.0
        caster._registrar_estado_historico()

        with patch("effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(caster.usar_skill_classe("Reverter"))

        self.assertEqual(caster.vida, 900.0)
        self.assertEqual(caster.pos, [1.0, 2.0])
        self.assertEqual(caster.vel, [0.0, 0.0])
        self.assertEqual(caster.mana, 60.0)
        self.assertEqual(caster.cd_skills["Reverter"], 30.0)
        self.assertEqual(caster.buffs_ativos, [])

    def test_mutation_uses_injected_rng_and_reverts_without_base_mutation(self):
        first = self._fighter("Mutante A")
        second = self._fighter("Mutante B")
        base_speed = first.get_velocidade_movimento()
        first.rng_runtime = random.Random(17)
        second.rng_runtime = random.Random(17)

        buff_a = Buff("Mutação", first, rng=first.rng_runtime)
        buff_b = Buff("Mutação", second, rng=second.rng_runtime)
        first.buffs_ativos.append(buff_a)
        second.buffs_ativos.append(buff_b)

        self.assertEqual(buff_a.perfil_stats, buff_b.perfil_stats)
        self.assertEqual(buff_a.modificadores_stats, buff_b.modificadores_stats)
        self.assertNotEqual(first.get_velocidade_movimento(), base_speed)
        first._atualizar_buffs(buff_a.duracao + 0.1)
        self.assertEqual(first.get_velocidade_movimento(), base_speed)
        self.assertEqual(first.mod_defesa, 1.0)

    def test_levitation_grants_temporary_flight_and_ground_immunity(self):
        fighter = self._fighter("Levitante")
        levitation = Buff("Levitar", fighter)
        fighter.buffs_ativos.append(levitation)
        fighter.aplicar_fisica(0.1)

        ground = AreaEffect("Terremoto", fighter.pos[0], fighter.pos[1], None)
        result = fighter.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=None,
            metadata_impacto=criar_metadata_impacto(ground),
        )
        self.assertTrue(fighter.esta_voando())
        self.assertGreater(fighter.z, 0.0)
        self.assertEqual(result.bloqueado_por, "imunidade_ground")

        aerial = AreaEffect("Tempestade", fighter.pos[0], fighter.pos[1], None)
        result = fighter.resolver_impacto(
            10.0,
            metadata_impacto=criar_metadata_impacto(aerial),
        )
        self.assertGreater(result.dano_vida, 0.0)

        fighter._atualizar_buffs(levitation.duracao + 0.1)
        height_before_fall = fighter.z
        fighter.aplicar_fisica(0.1)
        self.assertFalse(fighter.esta_voando())
        self.assertLess(fighter.z, height_before_fall)

    def test_projectile_reflection_changes_owner_once_before_damage(self):
        owner = self._fighter("Atacante", x=0.0)
        defender = self._fighter("Defensor", x=3.0)
        defender.buffs_ativos.append(Buff("Escudo Arcano", defender))
        projectile = Projetil("Disparo de Mana", 3.0, 5.0, 0.0, owner)
        simulation = self._simulation(owner, defender)
        simulation.projeteis = [projectile]

        with self._floating_text_patch():
            simulation.update(0.0)
        self.assertIs(projectile.dono, defender)
        self.assertEqual(projectile.reflexoes, 1)
        self.assertEqual(defender.vida, defender.vida_max)

        projectile.x, projectile.y = owner.pos
        with self._floating_text_patch():
            simulation.update(0.0)
        self.assertLess(owner.vida, owner.vida_max)
        self.assertFalse(projectile.ativo)

    def test_steal_magic_transfers_independent_random_buff(self):
        thief = self._fighter("Ladrão")
        victim = self._fighter("Vítima")
        first = Buff("Acelerar", victim)
        second = Buff("Escudo Arcano", victim)
        remaining = second.vida
        victim.buffs_ativos.extend((first, second))
        thief.rng_runtime = SimpleNamespace(choice=lambda values: values[-1])
        source = Projetil("Roubar Magia", 0.0, 0.0, 0.0, thief)

        result = victim.resolver_impacto(
            source.dano,
            0.0,
            0.0,
            atacante=thief,
            fonte_impacto=source.fonte_impacto,
            metadata_impacto=criar_metadata_impacto(source),
        )

        self.assertTrue(result.atingiu)
        self.assertNotIn(second, victim.buffs_ativos)
        stolen = thief.buffs_ativos[-1]
        self.assertIsNot(stolen, second)
        self.assertIs(stolen.alvo, thief)
        self.assertEqual(stolen.nome, "Escudo Arcano")
        self.assertEqual(stolen.vida, remaining)

    def test_counterspell_reflects_one_hostile_skill_without_recursion(self):
        caster = self._fighter("Caster")
        defender = self._fighter("Counter")
        counterspell = Buff("Contrafeitiço", defender)
        defender.buffs_ativos.append(counterspell)
        metadata = {"eh_skill": True, "refletido": False, "ground": False}

        first = defender.resolver_impacto(
            20.0,
            1.0,
            0.0,
            atacante=caster,
            fonte_impacto=object(),
            metadata_impacto=metadata,
        )
        self.assertEqual(first.bloqueado_por, "skill_refletida")
        self.assertEqual(defender.vida, defender.vida_max)
        self.assertLess(caster.vida, caster.vida_max)
        self.assertFalse(counterspell.reflete_skills_disponivel)

        second = defender.resolver_impacto(
            20.0,
            1.0,
            0.0,
            atacante=caster,
            fonte_impacto=object(),
            metadata_impacto=metadata,
        )
        self.assertTrue(second.atingiu)
        self.assertLess(defender.vida, defender.vida_max)

    def test_arcane_portal_is_bidirectional_without_ping_pong(self):
        caster = self._fighter("Portalista", x=0.0)
        self._add_class_skill(caster, "Portal Arcano")
        caster.angulo_olhar = 0.0
        with patch("effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(caster.usar_skill_classe("Portal Arcano"))

        self.assertEqual(caster.pos[0], 10.0)
        self.assertEqual(len(caster.buffer_portais), 1)
        portal = caster.buffer_portais[0]
        traveller = self._fighter("Viajante", x=0.0)
        portal.atualizar(0.1, (caster, traveller))
        self.assertEqual(caster.pos[0], 10.0)
        self.assertEqual(traveller.pos[0], 10.0)

        portal.atualizar(0.1, (traveller,))
        self.assertEqual(traveller.pos[0], 10.0)
        traveller.pos[0] = 5.0
        portal.atualizar(0.1, (traveller,))
        traveller.pos[0] = 10.0
        portal.atualizar(0.1, (traveller,))
        self.assertEqual(traveller.pos[0], 0.0)

    def test_temporal_echo_duplicates_once_without_recursive_tree(self):
        owner = self._fighter("Cronomante")
        original = Projetil("Eco Temporal", 0.0, 0.0, 0.0, owner)
        event = original.atualizar(1.0, ())
        duplicate = original.criar_duplicata(event)

        self.assertIsNotNone(duplicate)
        self.assertTrue(original.duplicado)
        self.assertTrue(duplicate.duplicado)
        self.assertEqual(duplicate.duplica_apos, 0.0)
        self.assertAlmostEqual(duplicate.dano, original.dano * 0.7)
        self.assertIsNone(duplicate.atualizar(1.1, ()))

    def test_weapon_projectile_runtime_does_not_require_skill_only_fields(self):
        owner = self._fighter("Arremessador", x=0.0)
        target = self._fighter("Alvo", x=3.0)
        projectile = ArmaProjetil(
            "faca",
            target.pos[0],
            target.pos[1],
            0.0,
            owner,
            12.0,
            velocidade=0.0,
        )
        simulation = self._simulation(owner, target)
        simulation.projeteis = [projectile]

        with self._floating_text_patch():
            simulation.update(0.0)

        self.assertFalse(projectile.ativo)
        self.assertLess(target.vida, target.vida_max)


if __name__ == "__main__":
    unittest.main()
