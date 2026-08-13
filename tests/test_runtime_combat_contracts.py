"""Regressoes dos contratos canonicos de movimento e combate temporario."""

from __future__ import annotations

import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neural_fights.core.combat import Channel, DotEffect, Transform
from neural_fights.core.entities import Lutador
from neural_fights.core.skills import get_skill_data
from neural_fights.core.status_runtime import STATUS_RUNTIME
from neural_fights.models.characters import Personagem


class _Shield:
    def __init__(self, amount: float) -> None:
        self.ativo = True
        self.escudo_atual = amount
        self.mod_dano_recebido = 1.0

    def absorver_dano(self, damage: float) -> float:
        absorbed = min(self.escudo_atual, max(0.0, damage))
        self.escudo_atual -= absorbed
        return max(0.0, damage - absorbed)


class RuntimeCombatContractTests(unittest.TestCase):
    @staticmethod
    def _fighter(name: str, x: float = 0.0, y: float = 0.0) -> Lutador:
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
        fighter.vida = fighter.vida_max
        return fighter

    @staticmethod
    def _add_class_skill(fighter: Lutador, name: str) -> None:
        data = get_skill_data(name)
        fighter.skills_classe.append(
            {"nome": name, "custo": data.get("custo", 0.0), "data": data}
        )
        fighter.cd_skills[name] = 0.0

    def test_lutador_consumes_canonical_stats_and_weapon_weight_changes_motion(self) -> None:
        light_data = Personagem(
            "Leve",
            tamanho=2.0,
            forca=5.0,
            mana=4.0,
            peso_arma_cache=0.0,
        )
        heavy_data = Personagem(
            "Pesado",
            tamanho=2.0,
            forca=5.0,
            mana=4.0,
            peso_arma_cache=8.0,
        )
        with patch("neural_fights.ai.AIBrain", return_value=None):
            light = Lutador(light_data, 0.0, 0.0)
            heavy = Lutador(heavy_data, 0.0, 0.0)

        self.assertEqual(light.vida_max, light_data.get_vida_max())
        self.assertEqual(light.mana_max, light_data.get_mana_max())
        self.assertEqual(
            light.get_velocidade_movimento(),
            light_data.get_velocidade_movimento(),
        )
        self.assertGreater(
            light.get_velocidade_movimento(),
            heavy.get_velocidade_movimento(),
        )

        brain = SimpleNamespace(acao_atual="APROXIMAR", tracos=set())
        light.brain = brain
        heavy.brain = SimpleNamespace(acao_atual="APROXIMAR", tracos=set())
        with patch("neural_fights.core.entities.random.random", return_value=1.0):
            light.executar_movimento(0.1, 10.0)
            heavy.executar_movimento(0.1, 10.0)
        light.aplicar_fisica(0.1)
        heavy.aplicar_fisica(0.1)

        self.assertGreater(light.vel[0], heavy.vel[0])
        self.assertGreater(light.pos[0], heavy.pos[0])

    def test_gameplay_rng_is_isolated_from_global_visual_randomness(self) -> None:
        first = self._fighter("Assassino A")
        second = self._fighter("Assassino B")
        first.classe_nome = second.classe_nome = "Assassino"
        first.configurar_rng_runtime(random.Random(4242))
        second.configurar_rng_runtime(random.Random(4242))

        expected = [first.get_dano_modificado(10.0) for _ in range(12)]
        observed = []
        for _ in range(12):
            # Particulas, camera shake e audio podem consumir o fluxo global.
            for _ in range(37):
                random.random()
            observed.append(second.get_dano_modificado(10.0))

        self.assertEqual(expected, observed)

    def test_blindness_is_deterministic_and_fear_forces_fleeing(self) -> None:
        blinded = self._fighter("Cego")
        target = self._fighter("Alvo", x=10.0)
        blinded.dados.arma_obj = SimpleNamespace(
            dano=10.0,
            forca_arco=25.0,
            r=100,
            g=80,
            b=60,
        )

        self.assertTrue(blinded._aplicar_efeito_status("CEGO", duracao=1.0))
        self.assertEqual(blinded.get_angulo_mira(0.0), 35.0)
        self.assertEqual(blinded.get_angulo_mira(0.0), 35.0)
        with patch("neural_fights.core.entities.random.uniform", return_value=0.0):
            blinded._disparar_flecha(target)
        self.assertAlmostEqual(blinded.buffer_projeteis[-1].angulo, 35.0)

        afraid = self._fighter("Com medo", x=5.0)
        threat = self._fighter("Ameaca", x=10.0)
        afraid.brain = SimpleNamespace(acao_atual="ATACAR", processar=Mock())
        self.assertTrue(afraid._aplicar_efeito_status("MEDO", duracao=1.0))
        self.assertFalse(afraid.pode_iniciar_acao())
        afraid.update(0.1, threat)

        self.assertEqual(afraid.brain.acao_atual, "FUGIR")
        afraid.brain.processar.assert_not_called()
        self.assertLess(afraid.pos[0], 5.0)

    def test_sleep_owns_its_timer_and_only_real_damage_breaks_it(self) -> None:
        sleeper = self._fighter("Dorminhoco")
        attacker = self._fighter("Atacante")
        sleeper.stun_timer = 3.0
        self.assertTrue(sleeper._aplicar_efeito_status("SONO", duracao=2.0))

        self.assertTrue(sleeper.dormindo)
        self.assertEqual(sleeper.sono_timer, 2.0)
        self.assertEqual(sleeper.stun_timer, 3.0)
        self.assertFalse(sleeper.pode_iniciar_acao())

        sleeper.invencivel_timer = 1.0
        rejected = sleeper.resolver_impacto(10.0, 0.0, 0.0, atacante=attacker)
        self.assertFalse(rejected.atingiu)
        self.assertTrue(sleeper.dormindo)

        sleeper.invencivel_timer = 0.0
        accepted = sleeper.resolver_impacto(10.0, 0.0, 0.0, atacante=attacker)
        self.assertTrue(accepted.atingiu)
        self.assertGreater(accepted.dano, 0.0)
        self.assertFalse(sleeper.dormindo)
        self.assertEqual(sleeper.sono_timer, 0.0)
        self.assertEqual(sleeper.stun_timer, 3.0)

    def test_mark_waits_for_hp_damage_then_amplifies_and_expires(self) -> None:
        marked = self._fighter("Marcado")
        attacker = self._fighter("Atacante")
        shield = _Shield(100.0)
        marked.buffs_ativos.append(shield)
        self.assertTrue(marked._aplicar_efeito_status("MARCADO", duracao=1.0))

        absorbed = marked.resolver_impacto(10.0, 0.0, 0.0, atacante=attacker)
        self.assertEqual(absorbed.dano, 0.0)
        self.assertTrue(marked.marcado)

        marked.buffs_ativos.clear()
        marked.invencivel_timer = 0.0
        amplified = marked.resolver_impacto(10.0, 0.0, 0.0, atacante=attacker)
        self.assertAlmostEqual(amplified.dano, 15.0)
        self.assertFalse(marked.marcado)

        marked.invencivel_timer = 0.0
        regular = marked.resolver_impacto(10.0, 0.0, 0.0, atacante=attacker)
        self.assertAlmostEqual(regular.dano, 10.0)

        self.assertTrue(marked._aplicar_efeito_status("MARCADO", duracao=0.1))
        marked.update(0.2, attacker)
        self.assertFalse(marked.marcado)
        self.assertEqual(marked.marcado_timer, 0.0)

    def test_exhaustion_uses_contract_value_and_restores_regeneration(self) -> None:
        fighter = self._fighter("Exausto")
        target = self._fighter("Alvo")
        normal = fighter.regen_mana_base

        self.assertTrue(fighter._aplicar_efeito_status("EXAUSTO", duracao=0.1))
        self.assertAlmostEqual(
            fighter.regen_mana_base,
            normal * STATUS_RUNTIME["EXAUSTO"]["mod_regen_mana"],
        )
        fighter.update(0.2, target)
        self.assertEqual(fighter.regen_mana_base, normal)

    def test_transform_changes_real_fields_and_reverts_intangibility(self) -> None:
        fighter = self._fighter("Transformado")
        attacker = self._fighter("Atacante")
        originals = (
            fighter.get_velocidade_movimento(),
            fighter.resistencia,
            fighter.mod_defesa,
            fighter.cor_aura,
            fighter.intangivel,
        )
        data = {
            "duracao": 1.0,
            "cor": (1, 2, 3),
            "bonus_resistencia": 0.5,
            "bonus_velocidade": 2.0,
            "intangivel": True,
        }
        with patch("neural_fights.core.combat.get_skill_data", return_value=data):
            transform = Transform("Forma de teste", fighter)

        self.assertAlmostEqual(fighter.get_velocidade_movimento(), originals[0] * 2.0)
        self.assertAlmostEqual(fighter.resistencia, originals[1] * 1.5)
        self.assertAlmostEqual(fighter.mod_defesa, originals[2] / 1.5)
        self.assertEqual(fighter.cor_aura, (1, 2, 3))
        self.assertTrue(fighter.intangivel)
        self.assertFalse(transform._aplicar_transformacao())

        blocked = fighter.resolver_impacto(20.0, 0.0, 0.0, atacante=attacker)
        self.assertFalse(blocked.atingiu)
        self.assertEqual(blocked.bloqueado_por, "intangibilidade")
        transform.atualizar(1.0)

        self.assertFalse(transform.ativo)
        self.assertIsNone(fighter.transformacao_ativa)
        self.assertEqual(
            (
                fighter.get_velocidade_movimento(),
                fighter.resistencia,
                fighter.mod_defesa,
                fighter.cor_aura,
                fighter.intangivel,
            ),
            originals,
        )
        accepted = fighter.resolver_impacto(20.0, 0.0, 0.0, atacante=attacker)
        self.assertTrue(accepted.atingiu)

    def test_replacing_transform_does_not_stack_or_restore_stale_state(self) -> None:
        fighter = self._fighter("Metamorfo")
        original_speed = fighter.get_velocidade_movimento()
        original_resistance = fighter.resistencia
        first_data = {
            "duracao": 5.0,
            "bonus_velocidade": 2.0,
            "bonus_resistencia": 0.5,
            "intangivel": True,
        }
        second_data = {
            "duracao": 5.0,
            "bonus_velocidade": 3.0,
            "bonus_resistencia": 1.0,
            "intangivel": False,
        }
        with patch(
            "neural_fights.core.combat.get_skill_data",
            side_effect=[first_data, second_data],
        ):
            first = Transform("Primeira", fighter)
            second = Transform("Segunda", fighter)

        self.assertFalse(first.ativo)
        self.assertIs(fighter.transformacao_ativa, second)
        self.assertAlmostEqual(fighter.get_velocidade_movimento(), original_speed * 3.0)
        self.assertAlmostEqual(fighter.resistencia, original_resistance * 2.0)
        self.assertFalse(fighter.intangivel)

        first.encerrar()
        self.assertAlmostEqual(fighter.get_velocidade_movimento(), original_speed * 3.0)
        second.encerrar()
        self.assertAlmostEqual(fighter.get_velocidade_movimento(), original_speed)
        self.assertAlmostEqual(fighter.resistencia, original_resistance)

    def test_channel_ticks_are_dt_independent_and_penetrate_shields(self) -> None:
        def run(chunks: list[float]) -> tuple[float, float, list[dict]]:
            owner = self._fighter("Canalizador")
            owner.mod_dano = 2.0
            target = self._fighter("Alvo", x=5.0)
            shield = _Shield(100.0)
            target.buffs_ativos.append(shield)
            owner.angulo_olhar = 0.0
            channel = Channel("Desintegrar", owner)
            results = []
            for dt in chunks:
                results.extend(channel.atualizar(dt, [target]))
            return target.vida, shield.escudo_atual, results

        one_step_life, one_step_shield, results = run([0.3])
        split_life, split_shield, _ = run([0.1, 0.1, 0.1])

        self.assertAlmostEqual(one_step_life, 970.0)
        self.assertAlmostEqual(split_life, one_step_life)
        self.assertEqual(one_step_shield, 100.0)
        self.assertEqual(split_shield, 100.0)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(result["tipo"] == "impacto" for result in results))
        self.assertTrue(all(result["impacto"].atingiu for result in results))

    def test_channel_respects_skill_invulnerability_and_grants_no_hit_recovery(self):
        owner = self._fighter("Canalizador")
        target = self._fighter("Alvo", x=5.0)
        owner.angulo_olhar = 0.0
        channel = Channel("Desintegrar", owner)

        target.invencivel_timer = 1.0
        target.invulnerabilidade_skill_timer = 1.0
        blocked = channel.atualizar(0.1, [target])
        self.assertEqual(target.vida, target.vida_max)
        self.assertFalse(blocked[0]["impacto"].atingiu)
        self.assertEqual(
            blocked[0]["impacto"].bloqueado_por,
            "invulnerabilidade_skill",
        )

        target.invencivel_timer = 0.0
        target.invulnerabilidade_skill_timer = 0.0
        accepted = channel.atualizar(0.1, [target])
        self.assertTrue(accepted[0]["impacto"].atingiu)
        self.assertEqual(target.invencivel_timer, 0.0)

        external = target.resolver_impacto(
            10.0,
            0.0,
            0.0,
            atacante=owner,
            fonte_impacto=object(),
        )
        self.assertTrue(external.atingiu)

    def test_existing_dot_respects_explicit_skill_invulnerability(self):
        target = self._fighter("Alvo")
        target.invencivel_timer = 1.0
        target.invulnerabilidade_skill_timer = 1.0
        dot = DotEffect("ENVENENADO", target, 20.0, 1.0, (0, 255, 0))

        dot.atualizar(0.5)
        self.assertEqual(target.vida, target.vida_max)

        target.invencivel_timer = 0.0
        target.invulnerabilidade_skill_timer = 0.0
        dot.atualizar(0.5)
        self.assertEqual(target.vida, target.vida_max - 10.0)

        target.invulnerabilidade_skill_timer = 1.0
        bypassed = target.aplicar_dano_direto(
            5.0,
            ignorar_invulnerabilidade_skill=True,
        )
        self.assertEqual(bypassed, 5.0)

    def test_channel_cast_blocks_actions_and_interruption_clears_owner(self) -> None:
        owner = self._fighter("Canalizador")
        target = self._fighter("Alvo", x=5.0)
        self._add_class_skill(owner, "Chamas do Dragão")
        self._add_class_skill(owner, "Fotossíntese")
        owner.mana = 100.0

        with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
            self.assertTrue(owner.usar_skill_classe("Chamas do Dragão", alvo=target))

        channel = owner.channel_ativo
        self.assertIsInstance(channel, Channel)
        self.assertFalse(owner.pode_iniciar_acao())
        owner.vel = [8.0, -3.0]
        channel.atualizar(0.1, [target])
        self.assertEqual(owner.vel, [8.0, -3.0])
        owner.atacando = True
        owner.executar_ataques(0.1, 5.0, target)
        self.assertFalse(owner.atacando)
        with patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=None):
            self.assertFalse(owner.usar_skill_classe("Fotossíntese", alvo=target))

        channel.interromper()
        channel.interromper()
        self.assertFalse(channel.ativo)
        self.assertIsNone(owner.channel_ativo)
        self.assertFalse(owner.canalizando)
        self.assertIsNone(owner.skill_canalizando)
        self.assertEqual(owner.tempo_canalizacao, 0.0)


    def test_channel_honors_explicit_movement_lock(self) -> None:
        owner = self._fighter("Canalizador imovel")
        target = self._fighter("Alvo", x=5.0)
        owner.vel = [8.0, -3.0]

        channel = Channel("Fotoss\u00edntese", owner)
        channel.atualizar(0.1, [target])

        self.assertTrue(channel.imobiliza)
        self.assertEqual(owner.vel, [0.0, 0.0])
        channel.interromper()


if __name__ == "__main__":
    unittest.main()
