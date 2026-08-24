# -*- coding: utf-8 -*-
"""Contratos do instinto de sobrevivência (pedido do dono, pós-programa).

O que se trava aqui: o medo tem consequência de MOVIMENTO — machucado e
assustado troca intenção de risco por abrir distância (o último estágio
da pilha é um veto de sobrevivência); corajoso saudável não é tocado;
ações já defensivas nunca são "re-decididas"; e o medo AFIA os reflexos
de prioridade 1 (esquiva fica mais provável, não menos).
"""

import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.ai.brain import AIBrain


def _brain(medo, hp_pct, acao, rng_seed=1):
    brain = object.__new__(AIBrain)
    brain.emocoes = SimpleNamespace(medo=medo)
    brain.rng = random.Random(rng_seed)
    brain._modo_proposta = True
    brain.acao_atual = acao
    brain._hp_teste = hp_pct
    return brain


class VetoDeSobrevivenciaTests(unittest.TestCase):
    def test_saudavel_sem_medo_nao_e_tocado(self) -> None:
        brain = _brain(medo=0.0, hp_pct=1.0, acao="MATAR")
        brain._aplicar_instinto_sobrevivencia(distancia=2.0, hp_pct=1.0)
        self.assertEqual(brain.acao_atual, "MATAR")

    def test_ferido_e_apavorado_foge(self) -> None:
        """hp<0,3 + medo>0,5 = FUGIR — quer VIVER, não trocar dano."""
        brain = _brain(medo=0.9, hp_pct=0.2, acao="MATAR")
        with patch.object(brain.rng, "random", return_value=0.0):
            brain._aplicar_instinto_sobrevivencia(distancia=2.0, hp_pct=0.2)
        self.assertEqual(brain.acao_atual, "FUGIR")

    def test_colado_no_perigo_abre_distancia(self) -> None:
        """Com vida ainda ok mas medo alto e colado (d<3), a intenção de
        risco vira recuo/saída de linha — o 'não ficar colado'."""
        brain = _brain(medo=0.95, hp_pct=0.55, acao="PRESSIONAR")
        with patch.object(brain.rng, "random", return_value=0.0), \
             patch.object(brain.rng, "choice", side_effect=lambda ops: ops[0]):
            brain._aplicar_instinto_sobrevivencia(distancia=1.5, hp_pct=0.55)
        self.assertEqual(brain.acao_atual, "RECUAR")

    def test_acao_defensiva_nao_e_redecidida(self) -> None:
        brain = _brain(medo=1.0, hp_pct=0.1, acao="RECUAR")
        with patch.object(brain.rng, "random", return_value=0.0):
            brain._aplicar_instinto_sobrevivencia(distancia=1.0, hp_pct=0.1)
        self.assertEqual(brain.acao_atual, "RECUAR")

    def test_longe_do_perigo_vira_kite(self) -> None:
        brain = _brain(medo=0.95, hp_pct=0.55, acao="APROXIMAR")
        with patch.object(brain.rng, "random", return_value=0.0), \
             patch.object(brain.rng, "choice", side_effect=lambda ops: ops[0]):
            brain._aplicar_instinto_sobrevivencia(distancia=6.0, hp_pct=0.55)
        self.assertEqual(brain.acao_atual, "CIRCULAR")


class ReflexoAfiadoPeloMedoTests(unittest.TestCase):
    def _brain_com_instinto(self, medo):
        brain = object.__new__(AIBrain)
        brain.emocoes = SimpleNamespace(medo=medo)
        brain.rng = random.Random(3)
        brain.instintos = ["ESQUIVA_PROJETIL_T"]
        brain.cd_instintos = {}
        brain.tempo_combate = 10.0
        brain.parent = SimpleNamespace(vida=50.0, vida_max=100.0)
        return brain

    def test_medo_dobra_a_chance_do_reflexo_p1(self) -> None:
        tabela = {
            "ESQUIVA_PROJETIL_T": {
                "trigger": "projetil_vindo", "acao": "esquiva",
                "chance": 0.30, "prioridade": 1, "cooldown": 2.0,
            },
        }
        capturadas = []

        def com_medo(valor):
            brain = self._brain_com_instinto(valor)
            brain._avaliar_trigger_instinto = lambda *a, **k: True
            brain._executar_instinto = lambda *a, **k: True

            def sonda(chance, dt):
                capturadas.append(chance)
                return False

            brain._chance_temporal = sonda
            with patch("neural_fights.ai.brain.INSTINTOS", tabela):
                brain._processar_instintos(
                    1 / 60, 5.0,
                    SimpleNamespace(vida=50.0, vida_max=100.0),
                )

        com_medo(0.0)
        com_medo(1.0)
        self.assertAlmostEqual(capturadas[0], 0.30)
        self.assertAlmostEqual(capturadas[1], 0.60)

    def test_prioridade_2_nao_ganha_com_panico(self) -> None:
        tabela = {
            "ESQUIVA_PROJETIL_T": {
                "trigger": "projetil_vindo", "acao": "esquiva",
                "chance": 0.30, "prioridade": 2, "cooldown": 2.0,
            },
        }
        capturadas = []
        brain = self._brain_com_instinto(1.0)
        brain._avaliar_trigger_instinto = lambda *a, **k: True
        brain._executar_instinto = lambda *a, **k: True

        def sonda(chance, dt):
            capturadas.append(chance)
            return False

        brain._chance_temporal = sonda
        with patch("neural_fights.ai.brain.INSTINTOS", tabela):
            brain._processar_instintos(
                1 / 60, 5.0, SimpleNamespace(vida=50.0, vida_max=100.0)
            )
        self.assertAlmostEqual(capturadas[0], 0.30)


if __name__ == "__main__":
    unittest.main()
