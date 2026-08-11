"""Regressões das mecânicas especiais integradas ao combate real."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import neural_fights.simulation.simulacao as simulation_module
from neural_fights.core.combat import AreaEffect, DotEffect, Projetil
from neural_fights.core.entities import Lutador
from neural_fights.core.skills import get_skill_data
from neural_fights.simulation.simulacao import Simulador


class SpecialStatusRegressionTests(unittest.TestCase):
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
            fighter = Lutador(data, x, 5.0)
        fighter.vida_max = 1000.0
        fighter.vida = 1000.0
        return fighter

    @staticmethod
    def _simulation(owner: Lutador, target: Lutador, area: AreaEffect) -> Simulador:
        simulation = object.__new__(Simulador)
        simulation.cam = SimpleNamespace(
            atualizar=lambda _dt, _p1, _p2: None,
            aplicar_shake=lambda *_args, **_kwargs: None,
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
        simulation.areas = [area]
        simulation._verificar_clash_projeteis = lambda: None
        simulation.audio = None
        simulation.vencedor = "fixture-already-finished"
        simulation.movement_anims = None
        simulation.attack_anims = None
        simulation.particulas = []
        simulation.decals = []
        return simulation

    @staticmethod
    def _add_class_skill(fighter: Lutador, name: str) -> None:
        data = get_skill_data(name)
        fighter.skills_classe.append(
            {"nome": name, "custo": data.get("custo", 0.0), "data": data}
        )
        fighter.cd_skills[name] = 0.0

    def test_zero_damage_area_uses_explicit_impact_result_for_metadata(self) -> None:
        owner = self._fighter("Caster")
        target = self._fighter("Target", x=5.1)
        area = AreaEffect("Nenhuma", owner.pos[0], owner.pos[1], owner)
        area.dano = 0.0
        area.tipo_efeito = "NORMAL"
        area.raio = 2.0
        area.duracao = 3.0
        area.vida = 3.0
        area.slow_fator = 0.3
        simulation = self._simulation(owner, target, area)

        with patch.object(
            simulation_module,
            "FloatingText",
            return_value=SimpleNamespace(vida=1.0, update=lambda _dt: None),
        ):
            simulation.update(0.1)

        self.assertTrue(target.ultimo_resultado_impacto.atingiu)
        self.assertEqual(target.ultimo_resultado_impacto.dano, 0.0)
        self.assertAlmostEqual(target.slow_fator, 0.3)
        self.assertAlmostEqual(target.slow_timer, 3.0)

    def test_bomb_keeps_source_payload_and_scales_damage_only_once(self) -> None:
        owner = self._fighter("Bomber")
        target = self._fighter("Marked", x=5.1)
        owner.get_dano_modificado = lambda damage: damage * 2.0

        impact = target.resolver_impacto(
            160.0,
            0.0,
            0.0,
            "BOMBA_RELOGIO",
            atacante=owner,
            duracao_efeito=3.0,
            raio_efeito=4.25,
        )

        self.assertTrue(impact.atingiu)
        self.assertEqual(impact.dano, 0.0)
        self.assertEqual(target.bomba_relogio_dano, 160.0)
        self.assertEqual(target.bomba_relogio_raio, 4.25)
        self.assertEqual(target.bomba_relogio_timer, 3.0)

        target.update(3.0, owner)
        self.assertEqual(len(target.buffer_areas), 1)
        explosion = target.buffer_areas.pop()
        self.assertTrue(explosion.dano_precalculado)
        self.assertEqual(explosion.dano, 160.0)
        self.assertEqual(explosion.raio, 4.25)
        self.assertEqual((explosion.x, explosion.y), tuple(target.pos))

        simulation = self._simulation(owner, target, explosion)
        with patch.object(
            simulation_module,
            "FloatingText",
            return_value=SimpleNamespace(vida=1.0, update=lambda _dt: None),
        ):
            life_before = target.vida
            simulation.update(0.1)

        self.assertAlmostEqual(life_before - target.vida, 160.0)

    def test_projectiles_carry_the_canonical_special_configuration(self) -> None:
        owner = self._fighter("Source")

        bomb = Projetil("Bomba Relógio", 0.0, 0.0, 0.0, owner)
        link = Projetil("Link de Vida", 0.0, 0.0, 0.0, owner)
        possession = Projetil("Possessão", 0.0, 0.0, 0.0, owner)

        self.assertEqual(bomb.delay_explosao, 3.0)
        self.assertEqual(bomb.raio_explosao, 2.5)
        self.assertEqual(link.percentual_efeito, 0.5)
        self.assertEqual(possession.duracao_efeito, 3.0)

    def test_soul_link_splits_direct_damage_and_dot_without_recursion(self) -> None:
        source = self._fighter("Link source")
        target = self._fighter("Linked target")

        result = target.resolver_impacto(
            0.0,
            0.0,
            0.0,
            "LINK_ALMA",
            atacante=source,
            duracao_efeito=6.0,
            percentual_efeito=0.5,
        )
        self.assertTrue(result.efeito_aplicado)

        # Um vínculo recíproco não pode redistribuir a parcela indefinidamente.
        self.assertTrue(
            source._aplicar_efeito_status(
                "LINK_ALMA",
                origem=target,
                duracao=6.0,
                percentual_efeito=0.5,
            )
        )
        source_life = source.vida
        target_life = target.vida
        target.invencivel_timer = 0.0
        impact = target.resolver_impacto(100.0, 0.0, 0.0, atacante=source)

        self.assertEqual(impact.dano, 50.0)
        self.assertAlmostEqual(target_life - target.vida, 50.0)
        self.assertAlmostEqual(source_life - source.vida, 50.0)

        target.invencivel_timer = 0.0
        source_life = source.vida
        target_life = target.vida
        dot = DotEffect("TEST", target, 20.0, 0.5, (50, 200, 50))
        dot.atualizar(0.5)

        # DotEffect preserva o redutor histórico de 50%: 10, dividido em 5/5.
        self.assertAlmostEqual(target_life - target.vida, 5.0)
        self.assertAlmostEqual(source_life - source.vida, 5.0)

    def test_soul_link_also_splits_reflected_damage(self) -> None:
        attacker = self._fighter("Attacker")
        partner = self._fighter("Reflection partner")
        reflector = self._fighter("Reflector")
        self.assertTrue(
            attacker._aplicar_efeito_status(
                "LINK_ALMA",
                origem=partner,
                duracao=6.0,
                percentual_efeito=0.5,
            )
        )
        reflector.buffs_ativos.append(
            SimpleNamespace(
                ativo=True,
                mod_dano_recebido=1.0,
                escudo_atual=0.0,
                refletir=0.3,
            )
        )
        attacker_life = attacker.vida
        partner_life = partner.vida

        reflector.resolver_impacto(100.0, 0.0, 0.0, atacante=attacker)

        self.assertAlmostEqual(attacker_life - attacker.vida, 15.0)
        self.assertAlmostEqual(partner_life - partner.vida, 15.0)

    def test_swap_is_atomic_and_preserves_non_positional_state(self) -> None:
        caster = self._fighter("Swapper", x=2.0)
        target = self._fighter("Target", x=9.0)
        caster.pos[1], target.pos[1] = 3.0, 7.0
        caster.vel, target.vel = [1.0, 2.0], [-3.0, 4.0]
        caster.z, target.z = 1.5, 2.5
        self._add_class_skill(caster, "Troca de Almas")
        mana_before = caster.mana

        with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(caster.usar_skill_classe("Troca de Almas", alvo=target))

        self.assertEqual(caster.pos[:2], [9.0, 7.0])
        self.assertEqual(target.pos[:2], [2.0, 3.0])
        self.assertEqual(caster.vel, [1.0, 2.0])
        self.assertEqual(target.vel, [-3.0, 4.0])
        self.assertEqual((caster.z, target.z), (1.5, 2.5))
        self.assertLess(caster.mana, mana_before)
        self.assertGreater(caster.cd_skills["Troca de Almas"], 0.0)

        invalid = self._fighter("Invalid swapper")
        dead_target = self._fighter("Dead target")
        dead_target.morrer()
        self._add_class_skill(invalid, "Troca de Almas")
        state_before = (list(invalid.pos), invalid.mana, invalid.cd_skills["Troca de Almas"])
        self.assertFalse(invalid.usar_skill_classe("Troca de Almas", alvo=dead_target))
        self.assertEqual(
            (invalid.pos, invalid.mana, invalid.cd_skills["Troca de Almas"]),
            state_before,
        )

    def test_charm_cancels_channel_and_blocks_all_owned_damage_until_expiry(self) -> None:
        caster = self._fighter("Charmer")
        charmed = self._fighter("Charmed")
        victim = self._fighter("Victim")
        channel = SimpleNamespace(ativo=True, interromper=Mock())
        charmed.channel_ativo = channel
        charmed.canalizando = True
        charmed.atacando = True

        impact = charmed.resolver_impacto(
            0.0,
            0.0,
            0.0,
            "CHARME",
            atacante=caster,
            duracao_efeito=2.0,
        )

        self.assertTrue(impact.efeito_aplicado)
        channel.interromper.assert_called_once_with()
        self.assertIsNone(charmed.channel_ativo)
        self.assertFalse(charmed.canalizando)
        self.assertFalse(charmed.atacando)
        victim_life = victim.vida
        blocked = victim.resolver_impacto(40.0, 0.0, 0.0, atacante=charmed)
        self.assertFalse(blocked.atingiu)
        self.assertEqual(blocked.bloqueado_por, "controle_mental_atacante")
        self.assertEqual(victim.vida, victim_life)

        charmed.update(2.0, caster)
        self.assertEqual(charmed.charme_timer, 0.0)
        victim.invencivel_timer = 0.0
        allowed = victim.resolver_impacto(40.0, 0.0, 0.0, atacante=charmed)
        self.assertTrue(allowed.atingiu)

    def test_possession_has_source_duration_and_suspends_autonomous_offense(self) -> None:
        caster = self._fighter("Possessor")
        possessed = self._fighter("Possessed")
        victim = self._fighter("Victim")
        possessed.vel = [8.0, -4.0]

        impact = possessed.resolver_impacto(
            0.0,
            0.0,
            0.0,
            "POSSESSO",
            atacante=caster,
            duracao_efeito=3.0,
        )
        self.assertTrue(impact.efeito_aplicado)
        self.assertIs(possessed.possesso_origem, caster)
        self.assertEqual(possessed.possesso_timer, 3.0)

        possessed.update(1.0, caster)
        self.assertEqual(possessed.vel, [0.0, 0.0])
        self.assertEqual(possessed.possesso_timer, 2.0)
        blocked = victim.resolver_impacto(10.0, 0.0, 0.0, atacante=possessed)
        self.assertFalse(blocked.atingiu)

        possessed.update(2.0, caster)
        self.assertEqual(possessed.possesso_timer, 0.0)
        self.assertIsNone(possessed.possesso_origem)

    def test_non_positive_special_durations_are_rejected_and_cleaned(self) -> None:
        source = self._fighter("Source")
        target = self._fighter("Target")

        for effect, kwargs in (
            ("CHARME", {}),
            ("POSSESSO", {}),
            ("LINK_ALMA", {"percentual_efeito": 0.5}),
            ("BOMBA_RELOGIO", {"dano_efeito": 80.0, "raio_efeito": 2.5}),
        ):
            with self.subTest(effect=effect):
                self.assertFalse(
                    target._aplicar_efeito_status(
                        effect,
                        origem=source,
                        duracao=0.0,
                        **kwargs,
                    )
                )

        target.charme_timer = -1.0
        target.charme_origem = source
        target.possesso_timer = -1.0
        target.possesso_origem = source
        target.link_alma_timer = -1.0
        target.link_alma_alvo = source
        target.bomba_relogio_timer = -1.0
        target.bomba_relogio_origem = source
        target._atualizar_efeitos_especiais(0.0)

        self.assertEqual(target.charme_timer, 0.0)
        self.assertIsNone(target.charme_origem)
        self.assertEqual(target.possesso_timer, 0.0)
        self.assertIsNone(target.possesso_origem)
        self.assertEqual(target.link_alma_timer, 0.0)
        self.assertIsNone(target.link_alma_alvo)
        self.assertEqual(target.bomba_relogio_timer, 0.0)
        self.assertIsNone(target.bomba_relogio_origem)


if __name__ == "__main__":
    unittest.main()
