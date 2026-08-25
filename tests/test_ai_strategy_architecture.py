"""Regressões para o contrato temporal e estratégico da IA."""

import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from neural_fights.ai.brain import AIBrain, _obter_brain
from neural_fights.ai.choreographer import CombatChoreographer
from neural_fights.ai.emotions import EmotionSystem
from neural_fights.ai.spatial import SpatialAwarenessSystem
from neural_fights.ai.skill_strategy import (
    BattlePlan,
    CombatSituation,
    SkillProfile,
    SkillPurpose,
    SkillStrategySystem,
)
from neural_fights.core.skills import get_skill_data


def _situacao(
    *,
    distancia=4.0,
    meu_hp=0.8,
    inimigo_hp=0.8,
    inimigo_debuffado=False,
    inimigo_stunado=False,
    inimigo_queimando=False,
    inimigo_congelado=False,
):
    return CombatSituation(
        distancia=distancia,
        meu_hp_percent=meu_hp,
        inimigo_hp_percent=inimigo_hp,
        meu_mana_percent=1.0,
        inimigo_debuffado=inimigo_debuffado,
        inimigo_stunado=inimigo_stunado,
        inimigo_queimando=inimigo_queimando,
        inimigo_congelado=inimigo_congelado,
        tempo_combate=10.0,
    )


def _perfil(nome, tipo, *, distancia_min=0.0, distancia_max=999.0):
    return SkillProfile(
        nome=nome,
        tipo=tipo,
        custo=10.0,
        cooldown=1.0,
        data={"tipo": tipo},
        fonte="classe",
        distancia_min=distancia_min,
        distancia_max=distancia_max,
        alcance_efetivo=distancia_max if distancia_max < 999.0 else 0.0,
    )


class BrainContractTests(unittest.TestCase):
    def test_current_brain_contract_has_priority_and_legacy_alias_still_works(self):
        current = object()
        legacy = object()

        self.assertIs(_obter_brain(SimpleNamespace(brain=current, ai=legacy)), current)
        self.assertIs(_obter_brain(SimpleNamespace(ai=legacy)), legacy)
        self.assertIsNone(_obter_brain(SimpleNamespace()))

    def test_opponent_observation_is_honest_and_works_without_enemy_brain(self):
        """Onda 8A: a memória do oponente conta o que se VÊ (velocidade,
        animação), sem ler o acao_atual do brain adversário — inclusive
        contra um lutador sem brain nenhum."""
        brain = object.__new__(AIBrain)
        brain.parent = SimpleNamespace(pos=[0.0, 0.0])
        brain.rng = random.Random(7)
        brain.tempo_combate = 1.0
        brain.habilidade_leitura = 0.95
        brain._obs_cache = None
        brain._obs_cache_tempo = -1.0
        brain._obs_ataque_id_visto = -1
        brain._obs_ataque_mal_lido = False
        brain.memoria_oponente = {
            "ultima_acao": None,
            "vezes_atacou": 0,
            "vezes_fugiu": 0,
            "estilo_percebido": None,
            "ameaca_nivel": 0.5,
        }
        brain._gerar_reacao_inteligente = Mock()
        # Sem atributo brain: dummy físico avançando na minha direção.
        enemy = SimpleNamespace(
            pos=[2.0, 0.0], vel=[-3.0, 0.0], z=0.0,
            vida=100.0, vida_max=100.0, atacando=False,
            pos_historico=[(2.0, 0.0)] * 15,
            dados=SimpleNamespace(arma_obj=SimpleNamespace(tipo="Reta")),
        )

        brain._observar_oponente(enemy, distancia=2.0)

        self.assertEqual(brain.memoria_oponente["vezes_atacou"], 1)
        brain._gerar_reacao_inteligente.assert_called_once()
        obs = brain._gerar_reacao_inteligente.call_args[0][0]
        self.assertEqual(obs.intencao, "avancando")

    def test_strategy_clock_receives_real_dt_even_when_instinct_ends_frame(self):
        brain = object.__new__(AIBrain)
        brain.parent = SimpleNamespace()
        brain.tempo_combate = 0.0
        brain.skill_strategy = SimpleNamespace(atualizar=Mock())

        no_op_methods = (
            "_atualizar_cooldowns",
            "_detectar_dano",
            "_atualizar_emocoes",
            "_atualizar_humor",
            "_processar_modos_especiais",
            "_atualizar_leitura_oponente",
            "_atualizar_janelas_oportunidade",
            "_atualizar_momentum",
            "_atualizar_estados_humanos",
            "_atualizar_combo_state",
            "_atualizar_consciencia_espacial",
            "_atualizar_percepcao_armas",
            "_atualizar_ritmo",
            "_atualizar_plano",
        )
        for method_name in no_op_methods:
            setattr(brain, method_name, Mock())
        brain._processar_instintos = Mock(return_value=True)

        brain.processar(0.25, 3.0, SimpleNamespace())

        brain.skill_strategy.atualizar.assert_called_once_with(0.25)
        self.assertEqual(brain.tempo_combate, 0.25)
        self.assertEqual(brain._dt_atual, 0.25)

    def test_hesitation_rest_uses_real_dt(self):
        brain = object.__new__(AIBrain)
        brain.descanso_timer = 0.5
        brain.acao_atual = "NEUTRO"

        self.assertTrue(brain._verificar_hesitacao(0.2, 3.0, SimpleNamespace()))

        self.assertAlmostEqual(brain.descanso_timer, 0.3)
        self.assertEqual(brain.acao_atual, "CIRCULAR")

    def test_temporal_probability_is_normalized_to_elapsed_time(self):
        brain = object.__new__(AIBrain)
        brain.rng = SimpleNamespace(random=lambda: 0.15)
        brain._dt_atual = 1.0 / 60.0

        self.assertFalse(brain._chance_temporal(0.1, 1.0 / 60.0))
        self.assertTrue(brain._chance_temporal(0.1, 1.0 / 30.0))

    def test_choreographer_notifies_current_and_legacy_brain_contracts(self):
        current = SimpleNamespace(
            excitacao=0.1,
            tedio=0.1,
            on_ritmo_mudou=Mock(),
        )
        legacy = SimpleNamespace(
            excitacao=0.1,
            tedio=0.1,
            on_ritmo_mudou=Mock(),
        )
        choreographer = CombatChoreographer()
        choreographer.lutador1 = SimpleNamespace(brain=current)
        choreographer.lutador2 = SimpleNamespace(ai=legacy)

        choreographer._notificar_mudanca_ritmo("EXPLOSIVO")

        current.on_ritmo_mudou.assert_called_once_with("EXPLOSIVO")
        legacy.on_ritmo_mudou.assert_called_once_with("EXPLOSIVO")
        self.assertAlmostEqual(current.excitacao, 0.3)
        self.assertAlmostEqual(legacy.excitacao, 0.3)

    def test_choreographer_uses_registered_fighter_runtime_rng(self):
        rng = random.Random(19)
        first = SimpleNamespace(rng_runtime=rng)
        second = SimpleNamespace(rng_runtime=random.Random(23))
        choreographer = CombatChoreographer()

        choreographer.registrar_lutadores(first, second)

        self.assertIs(choreographer.rng, rng)

    def test_auxiliary_ai_systems_honor_injected_rng(self):
        parent = SimpleNamespace(vida=100.0, vida_max=100.0)
        # Re-pino Onda 5C: o motor único lê identidade (rng/traços/
        # perfil) AO VIVO do brain — não guarda cópia que envelhece. O
        # contrato de determinismo agora é "mesmo rng no brain, mesmo
        # humor", injetado pelo dono.
        cerebro_a = SimpleNamespace(
            rng=random.Random(37), tracos=[], parent=parent
        )
        cerebro_b = SimpleNamespace(
            rng=random.Random(37), tracos=[], parent=parent
        )
        emotion_a = EmotionSystem(cerebro_a)
        emotion_b = EmotionSystem(cerebro_b)
        emotion_a.frustracao = emotion_b.frustracao = 0.8

        emotion_a.atualizar_humor()
        emotion_b.atualizar_humor()

        self.assertEqual(emotion_a.humor, emotion_b.humor)
        self.assertEqual(emotion_a.cd_mudanca_humor, emotion_b.cd_mudanca_humor)

    def test_spatial_lateral_shuffle_mutates_the_actual_priority(self):
        rng = Mock()
        rng.shuffle.side_effect = lambda values: values.reverse()
        spatial = SpatialAwarenessSystem(SimpleNamespace(), rng=rng)
        awareness = {
            "caminho_livre": {
                "frente": False,
                "esquerda": True,
                "direita": True,
                "tras": True,
            }
        }

        spatial._calcular_rota_alternativa(None, None, awareness, None)

        rng.shuffle.assert_called_once()
        self.assertEqual(spatial.tatica["rota_alternativa"], "direita")

    def test_emergency_reaction_recognizes_healing_channel(self):
        brain = object.__new__(AIBrain)
        brain.skills_por_tipo = {
            "BUFF": [],
            "CHANNEL": [
                {
                    "nome": "Fotossíntese",
                    "data": get_skill_data("Fotossíntese"),
                    "fonte": "classe",
                }
            ],
        }
        brain.tracos = []
        brain.cd_reagir = 0.0
        brain._usar_skill = Mock(return_value=True)

        self.assertTrue(brain._tentar_cura_emergencia(0.3))
        brain._usar_skill.assert_called_once()
        self.assertEqual(brain.cd_reagir, 0.3)

    def test_skill_gate_checks_life_cost(self):
        # Re-pino Onda 5E: o avaliador legado (_avaliar_uso_skill) morreu
        # junto do caminho legado de skills; o contrato da Combustão
        # (exige alvo QUEIMANDO) vive no caminho estratégico via
        # CombatSituation.inimigo_queimando. Aqui fica o gate VIVO de
        # custo de vida em _usar_skill.
        cast = Mock(return_value=True)
        brain = object.__new__(AIBrain)
        brain.parent = SimpleNamespace(
            mana=100.0,
            vida=30.0,
            vida_max=100.0,
            usar_skill_classe=cast,
        )
        pact = {
            "nome": "Pacto de Sangue",
            "data": get_skill_data("Pacto de Sangue"),
            "fonte": "classe",
        }

        self.assertFalse(brain._usar_skill(pact))
        cast.assert_not_called()
        brain.parent.vida = 30.01
        self.assertTrue(brain._usar_skill(pact))


class SkillStrategyContractTests(unittest.TestCase):
    def _strategy(self, *profiles):
        strategy = object.__new__(SkillStrategySystem)
        strategy.parent = SimpleNamespace(mana=100.0, cd_skills={})
        strategy.brain = SimpleNamespace()
        strategy.rng = random.Random(7)
        strategy.skills = {profile.nome: profile for profile in profiles}
        strategy.cd_global = 0.0
        strategy.cd_por_tipo = {
            "SUMMON": 0.0,
            "TRAP": 0.0,
            "TRANSFORM": 0.0,
            "BUFF": 0.0,
        }
        strategy.plano = BattlePlan(rotacao_neutral=[p.nome for p in profiles])
        strategy.combo_em_andamento = None
        strategy.combo_index = 0
        strategy.fase_atual = None
        strategy.ultima_skill = None
        strategy.skills_usadas = []
        return strategy

    def _analyzed_strategy(self, *skill_names):
        skills = [
            {
                "nome": name,
                "data": get_skill_data(name),
                "custo": get_skill_data(name).get("custo", 15.0),
            }
            for name in skill_names
        ]
        parent = SimpleNamespace(
            skills_arma=[],
            skills_classe=skills,
            mana=100.0,
            mana_max=100.0,
            vida=100.0,
            vida_max=100.0,
            cd_skills={},
        )
        return SkillStrategySystem(
            parent,
            SimpleNamespace(rng=random.Random(7)),
        )

    def test_range_conditions_participate_in_rotation_selection(self):
        close = _perfil("Close", "PROJETIL", distancia_min=2.0, distancia_max=3.0)
        long = _perfil("Long", "PROJETIL", distancia_min=2.0, distancia_max=8.0)
        strategy = self._strategy(close, long)

        result = strategy.obter_melhor_skill(_situacao(distancia=6.0))

        self.assertIsNotNone(result)
        self.assertEqual(result[0].nome, "Long")

    def test_health_conditions_prevent_premature_healing_and_finishing(self):
        heal = _perfil("Heal", "BUFF")
        heal.proposito_principal = SkillPurpose.SUSTAIN
        heal.hp_proprio_max = 0.7
        finisher = _perfil("Execute", "PROJETIL", distancia_max=8.0)
        finisher.proposito_principal = SkillPurpose.FINISHER
        finisher.hp_inimigo_max = 0.3
        strategy = self._strategy(heal, finisher)

        healthy_target = _situacao(meu_hp=0.9, inimigo_hp=0.9)
        self.assertFalse(strategy._pode_usar_skill("Heal", healthy_target))
        self.assertFalse(strategy._pode_usar_skill("Execute", healthy_target))
        self.assertTrue(
            strategy._pode_usar_skill(
                "Execute",
                _situacao(meu_hp=0.9, inimigo_hp=0.2),
            )
        )

    def test_internal_cooldowns_use_real_dt_and_never_become_negative(self):
        strategy = self._strategy()
        strategy.cd_global = 0.2
        strategy.cd_por_tipo["BUFF"] = 0.4

        strategy.atualizar(0.25)

        self.assertEqual(strategy.cd_global, 0.0)
        self.assertAlmostEqual(strategy.cd_por_tipo["BUFF"], 0.15)

    def test_combo_only_advances_after_the_selected_skill_was_executed(self):
        setup = _perfil("Setup", "PROJETIL", distancia_max=8.0)
        payoff = _perfil("Payoff", "PROJETIL", distancia_max=8.0)
        strategy = self._strategy(setup, payoff)
        strategy.plano.combos = [("Setup", "Payoff", "test")]
        situation = _situacao()

        first_selection = strategy.obter_melhor_skill(situation)
        repeated_selection = strategy.obter_melhor_skill(situation)

        self.assertEqual(first_selection[0].nome, "Setup")
        self.assertEqual(repeated_selection[0].nome, "Setup")

        strategy.registrar_uso("Setup")
        strategy.atualizar(0.3)
        second_selection = strategy.obter_melhor_skill(situation)

        self.assertEqual(second_selection[0].nome, "Payoff")

    def test_healing_channel_is_sustain_and_only_selected_when_hurt(self):
        strategy = self._analyzed_strategy("Fotossíntese")
        profile = strategy.skills["Fotossíntese"]

        self.assertEqual(profile.dano_total, 0.0)
        self.assertEqual(profile.proposito_principal, SkillPurpose.SUSTAIN)
        self.assertNotIn(SkillPurpose.BURST, profile.propositos)
        self.assertNotIn(SkillPurpose.POKE, profile.propositos)
        self.assertIn("Fotossíntese", strategy.plano.rotacao_critical)

        self.assertIsNone(strategy.obter_melhor_skill(_situacao(meu_hp=0.9)))
        strategy.parent.vida = 20.0
        selected = strategy.obter_melhor_skill(_situacao(meu_hp=0.2))

        self.assertIsNotNone(selected)
        self.assertEqual(selected[0].nome, "Fotossíntese")

    def test_buff_aliases_drive_semantic_purposes_and_opening_rotation(self):
        strategy = self._analyzed_strategy(
            "Pacto de Sangue",
            "Regeneração",
            "Benção",
            "Acelerar",
            "Grito de Guerra",
            "Determinação",
        )

        self.assertIn(SkillPurpose.BURST, strategy.skills["Pacto de Sangue"].propositos)
        self.assertIn(SkillPurpose.SUSTAIN, strategy.skills["Regeneração"].propositos)
        self.assertIn(SkillPurpose.SUSTAIN, strategy.skills["Benção"].propositos)
        self.assertIn(SkillPurpose.ESCAPE, strategy.skills["Acelerar"].propositos)
        self.assertIn(SkillPurpose.BURST, strategy.skills["Grito de Guerra"].propositos)
        self.assertIn(SkillPurpose.UTILITY, strategy.skills["Determinação"].propositos)
        self.assertIn("Pacto de Sangue", strategy.plano.rotacao_opening)
        self.assertIn("Grito de Guerra", strategy.plano.rotacao_opening)

    def test_damage_estimate_accounts_for_composite_runtime_mechanics(self):
        strategy = self._analyzed_strategy(
            "Espinhos",
            "Mísseis Arcanos",
            "Wrath of Nature",
            "Apocalipse",
            "Corrente em Cadeia",
        )

        self.assertEqual(strategy.skills["Espinhos"].dano_total, 72.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertEqual(strategy.skills["Mísseis Arcanos"].dano_total, 80.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertEqual(strategy.skills["Wrath of Nature"].dano_total, 360.0)  # re-pino O6f2: escala de dano/cura de skill x2
        self.assertEqual(strategy.skills["Apocalipse"].dano_total, 760.0)  # re-pino O6f2: escala de dano/cura de skill x2
        chain_expected = 36.0 * sum(0.8**jump for jump in range(5))  # re-pino O6f2: escala x2
        self.assertAlmostEqual(
            strategy.skills["Corrente em Cadeia"].dano_total,
            chain_expected,
        )

        inert_base = SkillProfile(
            nome="Canal declarativo",
            tipo="CHANNEL",
            custo=10.0,
            cooldown=2.0,
            data={
                "tipo": "CHANNEL",
                "dano": 999.0,
                "dano_por_segundo": 10.0,
                "duracao_max": 4.0,
            },
            fonte="classe",
        )
        strategy._calcular_metricas(inert_base)
        self.assertEqual(inert_base.dano_total, 40.0)

    def test_life_costs_are_checked_with_runtime_precedence_and_strict_limit(self):
        strategy = self._analyzed_strategy("Pacto de Sangue", "Sacrifício")
        situation = _situacao(distancia=1.0)

        strategy.parent.vida = 30.0
        self.assertFalse(strategy._pode_usar_skill("Pacto de Sangue", situation))
        strategy.parent.vida = 30.01
        self.assertTrue(strategy._pode_usar_skill("Pacto de Sangue", situation))

        strategy.parent.vida = 50.0
        self.assertFalse(strategy._pode_usar_skill("Sacrifício", situation))
        strategy.parent.vida = 50.01
        self.assertTrue(strategy._pode_usar_skill("Sacrifício", situation))

    def test_stationary_projectile_requires_contact_range_and_burning_target(self):
        strategy = self._analyzed_strategy("Combustão Espontânea")
        profile = strategy.skills["Combustão Espontânea"]
        close_burning = _situacao(
            distancia=1.0,
            inimigo_debuffado=True,
            inimigo_queimando=True,
        )

        self.assertEqual(profile.alcance_efetivo, 1.25)
        self.assertFalse(
            strategy._pode_usar_skill(
                "Combustão Espontânea",
                _situacao(
                    distancia=4.0,
                    inimigo_debuffado=True,
                    inimigo_queimando=True,
                ),
            )
        )
        self.assertFalse(
            strategy._pode_usar_skill(
                "Combustão Espontânea",
                _situacao(distancia=1.0, inimigo_debuffado=True),
            )
        )
        self.assertTrue(strategy._pode_usar_skill("Combustão Espontânea", close_burning))
        selected = strategy.obter_melhor_skill(close_burning)
        self.assertIsNotNone(selected)
        self.assertEqual(selected[0].nome, "Combustão Espontânea")


if __name__ == "__main__":
    unittest.main()
