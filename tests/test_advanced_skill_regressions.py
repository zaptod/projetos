"""Regressões dos campos avançados declarados no catálogo de skills."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import neural_fights.simulation.simulacao as simulation_module
from neural_fights.core.combat import AreaEffect, Beam, Projetil, Summon
from neural_fights.core.entities import Lutador
from neural_fights.core.skills import get_skill_data
from neural_fights.simulation.simulacao import Simulador


class AdvancedSkillRegressionTests(unittest.TestCase):
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
        with patch("neural_fights.ai.AIBrain", return_value=None):
            fighter = Lutador(data, x, y)
        fighter.vida_max = 1000.0
        fighter.vida = 1000.0
        return fighter

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

    def test_advanced_catalog_fields_have_explicit_runtime_contracts(self) -> None:
        cone = get_skill_data("Cone de Gelo")
        shatter = get_skill_data("Shatter")
        chain = get_skill_data("Corrente em Cadeia")
        execute = get_skill_data("Execução")

        self.assertEqual(cone["alcance_cone"], 5.0)
        self.assertEqual(shatter["dano_bonus_condicao"], 1.5)
        self.assertTrue(shatter["remove_congelamento"])
        self.assertEqual(chain["chain_range"], 5.0)
        self.assertEqual(execute["dano_bonus_condicao"], 2.0)
        self.assertIn("ataques básicos", get_skill_data("Cópia Sombria")["descricao"])

    def test_ice_cone_uses_angular_geometry_and_stays_anchored(self) -> None:
        owner = SimpleNamespace(pos=[0.0, 0.0], morto=False)
        cone = Projetil("Cone de Gelo", 0.6, 0.0, 0.0, owner)
        inside = SimpleNamespace(pos=[4.0, 1.0], raio_fisico=0.25, morto=False, ativo=True)
        outside_angle = SimpleNamespace(pos=[4.0, 3.4], raio_fisico=0.25, morto=False, ativo=True)
        outside_range = SimpleNamespace(pos=[6.0, 0.0], raio_fisico=0.25, morto=False, ativo=True)

        before = (cone.x, cone.y)
        cone.atualizar(0.1, [inside])

        self.assertEqual((cone.x, cone.y), before)
        self.assertTrue(cone.colidir(inside))
        self.assertFalse(cone.colidir(outside_angle))
        self.assertFalse(cone.colidir(outside_range))

    def test_ice_cone_runtime_hits_every_hostile_inside_volume(self) -> None:
        owner = self._fighter("Caster", x=0.0)
        primary = self._fighter("Primary", x=3.0)
        secondary = self._fighter("Secondary", x=3.0, y=6.0)
        owner.get_dano_modificado = lambda damage: damage
        cone = Projetil("Cone de Gelo", 0.6, 5.0, 0.0, owner)
        simulation = self._simulation(owner, primary)
        simulation.projeteis = [cone]
        simulation.alvos_adicionais = [secondary]

        with self._floating_text_patch():
            simulation.update(0.01)

        self.assertAlmostEqual(primary.vida, 980.0)
        self.assertAlmostEqual(secondary.vida, 980.0)

    def test_plague_contagion_selects_nearest_and_never_reinfects(self) -> None:
        owner = SimpleNamespace(pos=[0.0, 0.0], morto=False)
        primary = SimpleNamespace(
            pos=[1.0, 0.0], morto=False, ativo=True, resolver_impacto=lambda *_a, **_k: None
        )
        nearest = SimpleNamespace(
            pos=[2.5, 0.0], morto=False, ativo=True, resolver_impacto=lambda *_a, **_k: None
        )
        third = SimpleNamespace(
            pos=[3.2, 0.0], morto=False, ativo=True, resolver_impacto=lambda *_a, **_k: None
        )
        plague = Projetil("Praga", 0.0, 0.0, 0.0, owner)

        first_spread = plague.criar_contagio(primary, [primary, nearest, third])
        self.assertIsNotNone(first_spread)
        self.assertIs(first_spread.alvo_forcado, nearest)

        second_spread = first_spread.criar_contagio(nearest, [primary, nearest, third])
        self.assertIsNotNone(second_spread)
        self.assertIs(second_spread.alvo_forcado, third)
        self.assertIn(id(primary), second_spread.alvos_contagiados)
        self.assertIn(id(nearest), second_spread.alvos_contagiados)

    def test_plague_runtime_enqueues_contagion_for_additional_hostile(self) -> None:
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Primary", x=1.0)
        secondary = self._fighter("Secondary", x=2.5)
        owner.get_dano_modificado = lambda damage: damage
        plague = Projetil("Praga", target.pos[0], target.pos[1], 0.0, owner)
        simulation = self._simulation(owner, target)
        simulation.projeteis = [plague]
        simulation.alvos_adicionais = [secondary]

        with self._floating_text_patch():
            simulation.update(0.001)

        self.assertEqual(len(simulation.projeteis), 1)
        contagion = simulation.projeteis[0]
        self.assertIs(contagion.alvo_forcado, secondary)
        self.assertIn(id(target), contagion.alvos_contagiados)

    def test_chain_beam_decays_and_preserves_visited_targets(self) -> None:
        owner = SimpleNamespace(pos=[0.0, 0.0], morto=False)
        first = SimpleNamespace(pos=[2.0, 0.0], morto=False, ativo=True)
        second = SimpleNamespace(pos=[3.0, 0.0], morto=False, ativo=True)
        beam = Beam("Corrente em Cadeia", 0.0, 0.0, 2.0, 0.0, owner)

        jump = beam.criar_salto(first, [first, second])

        self.assertIsNotNone(jump)
        self.assertIs(jump.alvo_forcado, second)
        self.assertAlmostEqual(jump.dano, 18.0 * 0.8)
        self.assertEqual(jump.chain_count, 1)
        self.assertIn(id(first), jump.chain_targets)

    def test_chain_beam_runtime_creates_segment_for_hostile_summon(self) -> None:
        owner = self._fighter("Caster", x=0.0)
        target = self._fighter("Target", x=2.0)
        owner.get_dano_modificado = lambda damage: damage
        enemy_summon = Summon("Invocação: Espírito", 3.0, 5.0, target)
        beam = Beam("Corrente em Cadeia", 0.0, 5.0, 2.0, 5.0, owner)
        simulation = self._simulation(owner, target)
        simulation.beams = [beam]
        simulation.summons = [enemy_summon]

        with self._floating_text_patch():
            simulation.update(0.01)

        self.assertEqual(len(simulation.beams), 2)
        jump = simulation.beams[1]
        self.assertIs(jump.alvo_forcado, enemy_summon)
        self.assertAlmostEqual(jump.dano, 18.0 * 0.8)

    def test_lightning_teleport_applies_arrival_damage_contract(self) -> None:
        fighter = self._fighter("Teleporter")
        skill = get_skill_data("Teleporte Relâmpago")
        fighter.skills_classe.append(
            {"nome": "Teleporte Relâmpago", "custo": skill["custo"], "data": skill}
        )
        fighter.cd_skills["Teleporte Relâmpago"] = 0.0
        fighter.mana = 100.0
        fighter.angulo_olhar = 0.0

        with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
            used = fighter.usar_skill_classe("Teleporte Relâmpago")

        self.assertTrue(used)
        self.assertAlmostEqual(fighter.pos[0], 5.0)
        self.assertEqual(len(fighter.buffer_areas), 1)
        self.assertEqual(fighter.buffer_areas[0].dano, 15.0)
        self.assertEqual(fighter.invencivel_timer, 0.3)
        self.assertEqual(fighter.invulnerabilidade_skill_timer, 0.3)

        attacker = self._fighter("Attacker")
        bypass_attempt = fighter.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=attacker,
            fonte_impacto=object(),
            ignorar_invencibilidade=True,
        )
        self.assertFalse(bypass_attempt.atingiu)
        self.assertEqual(
            bypass_attempt.bloqueado_por,
            "invulnerabilidade_skill",
        )

    def test_shatter_rewards_and_consumes_freeze_once(self) -> None:
        owner = self._fighter("Caster", x=5.0)
        target = self._fighter("Frozen", x=5.1)
        owner.get_dano_modificado = lambda damage: damage
        target._aplicar_efeito_status("CONGELADO", duracao=3.0)
        area = AreaEffect("Shatter", owner.pos[0], owner.pos[1], owner)
        simulation = self._simulation(owner, target)
        simulation.areas = [area]

        with self._floating_text_patch():
            simulation.update(0.1)

        self.assertAlmostEqual(target.ultimo_resultado_impacto.dano, 90.0)
        self.assertAlmostEqual(target.vida, 910.0)
        self.assertFalse(target.congelado)
        self.assertEqual(target.congelado_timer, 0.0)
        self.assertGreater(target.vulneravel_timer, 0.0)

    def test_taunt_restricts_damage_source_until_duration_expires(self) -> None:
        provoker = self._fighter("Provoker")
        target = self._fighter("Taunted")
        third = self._fighter("Third")
        area = AreaEffect("Provocar", provoker.pos[0], provoker.pos[1], provoker)

        area.aplicar_efeitos_alvo(target, aplicar_efeito_principal=False)

        self.assertTrue(target.pode_causar_dano(provoker))
        self.assertFalse(target.pode_causar_dano(third))
        self.assertIn("PROVOCADO", target.remover_debuffs())
        self.assertTrue(target.pode_causar_dano(third))

        area.aplicar_efeitos_alvo(target, aplicar_efeito_principal=False)
        target.update(3.1, provoker)
        self.assertTrue(target.pode_causar_dano(third))

    def test_shadow_copy_repeats_each_basic_attack_exactly_once(self) -> None:
        weapon = SimpleNamespace(dano=20.0)
        owner = SimpleNamespace(
            pos=[0.0, 0.0],
            morto=False,
            ataque_id=0,
            dados=SimpleNamespace(arma_obj=weapon),
            get_dano_modificado=lambda damage: damage * 2.0,
        )
        target = SimpleNamespace(pos=[1.0, 0.0], morto=False)
        clone = Summon("Cópia Sombria", 0.5, 0.0, owner)

        self.assertEqual(clone.atualizar(0.1, [owner, target]), [])
        owner.ataque_id = 1
        first = clone.atualizar(0.1, [owner, target])
        repeated = clone.atualizar(0.1, [owner, target])

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["tipo"], "ataque")
        self.assertEqual(first[0]["dano"], 40.0)
        self.assertEqual(repeated, [])

    def test_multishot_bypasses_iframe_but_deduplicates_each_source(self) -> None:
        owner = self._fighter("Archer", x=0.0)
        target = self._fighter("Target", x=1.0)
        owner.get_dano_modificado = lambda damage: damage
        simulation = self._simulation(owner, target)
        simulation.projeteis = [
            Projetil("Espinhos", target.pos[0], target.pos[1], angle, owner)
            for angle in (-15.0, 0.0, 15.0)
        ]

        with self._floating_text_patch():
            simulation.update(0.001)

        self.assertAlmostEqual(target.vida, 1000.0 - 36.0)

        target.invencivel_timer = 0.0
        source_a = object()
        source_b = object()
        first = target.resolver_impacto(
            10.0, 0.0, 0.0, atacante=owner,
            fonte_impacto=source_a, ignorar_invencibilidade=True,
        )
        second = target.resolver_impacto(
            10.0, 0.0, 0.0, atacante=owner,
            fonte_impacto=source_b, ignorar_invencibilidade=True,
        )
        duplicate = target.resolver_impacto(
            10.0, 0.0, 0.0, atacante=owner,
            fonte_impacto=source_a, ignorar_invencibilidade=True,
        )

        self.assertTrue(first.atingiu)
        self.assertTrue(second.atingiu)
        self.assertFalse(duplicate.atingiu)
        self.assertEqual(duplicate.bloqueado_por, "fonte_duplicada")


if __name__ == "__main__":
    unittest.main()
