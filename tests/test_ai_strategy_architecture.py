"""Regressões para o contrato temporal e estratégico da IA."""

import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from neural_fights.ai.brain import AIBrain, _obter_brain
from neural_fights.ai.choreographer import CombatChoreographer
from neural_fights.ai.combat_tactics import CombatTacticsSystem
from neural_fights.ai.skill_strategy import (
    BattlePlan,
    CombatSituation,
    SkillProfile,
    SkillPurpose,
    SkillStrategySystem,
)


def _situacao(*, distancia=4.0, meu_hp=0.8, inimigo_hp=0.8):
    return CombatSituation(
        distancia=distancia,
        meu_hp_percent=meu_hp,
        inimigo_hp_percent=inimigo_hp,
        meu_mana_percent=1.0,
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

    def test_opponent_observation_reads_the_current_brain_attribute(self):
        brain = object.__new__(AIBrain)
        brain.memoria_oponente = {
            "ultima_acao": None,
            "vezes_atacou": 0,
            "vezes_fugiu": 0,
            "estilo_percebido": None,
            "ameaca_nivel": 0.5,
        }
        brain._gerar_reacao_inteligente = Mock()
        enemy = SimpleNamespace(brain=SimpleNamespace(acao_atual="MATAR"))

        brain._observar_oponente(enemy, distancia=2.0)

        self.assertEqual(brain.memoria_oponente["vezes_atacou"], 1)
        brain._gerar_reacao_inteligente.assert_called_once_with("MATAR", 2.0, enemy)

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

    def test_combat_tactics_reads_current_enemy_brain_contract(self):
        tactics = CombatTacticsSystem(
            SimpleNamespace(vida=100.0, vida_max=100.0),
            tracos=[],
            estilo_luta="BALANCED",
        )
        enemy = SimpleNamespace(
            atacando=False,
            cooldown_ataque=1.0,
            vel=[0.0, 0.0],
            z=0.0,
            brain=SimpleNamespace(acao_atual="MATAR"),
        )

        tactics.atualizar_leitura(1.0 / 60.0, 2.0, enemy)

        self.assertTrue(tactics.leitura_oponente["ataque_iminente"])


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


if __name__ == "__main__":
    unittest.main()
