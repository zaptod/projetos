# -*- coding: utf-8 -*-
"""Regressões do PlanoDeLuta e do fix do melee (Onda 8E)."""

from __future__ import annotations

import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.ai.brain import AIBrain
from neural_fights.ai.personalities import ARQUETIPO_DATA
from neural_fights.core.entities import Lutador
from tests import test_remaining_skill_regressions as _helpers


def _brain_planejador(parent, seed=11):
    brain = object.__new__(AIBrain)
    brain.parent = parent
    brain.rng = random.Random(seed)
    brain.tempo_combate = 10.0
    brain._dt_atual = 1.0 / 60.0
    brain.tempo_desde_dano = 5.0
    brain.habilidade_leitura = 0.6
    brain.disciplina_tatica = 0.6
    brain.momentum = 0.0
    brain.medo = 0.0
    brain.agressividade_base = 0.5
    brain.humor = "NEUTRO"
    brain.ritmo_modificadores = {"agressividade": 0}
    brain.tracos = []
    brain.quirks = []
    brain._perfil_chave = ()
    brain._perfil_cache = {}
    brain.skill_strategy = None
    brain.plano = None
    brain._plano_hp_inicial = 1.0
    brain.consciencia_espacial = {}
    brain.percepcao_arma = {}
    brain.contadores = {
        "decisoes": 0,
        "pilha_completa": 0,
        "escritas_aceitas": 0,
        "escritas_seguradas": 0,
    }
    return brain


def _inimigo_fisico(x=4.0):
    return SimpleNamespace(
        pos=[x, 5.0], vel=[0.0, 0.0], z=0.0,
        vida=100.0, vida_max=100.0, atacando=False,
        ataque_id=0, pos_historico=[(x, 5.0)] * 15,
        dados=SimpleNamespace(arma_obj=SimpleNamespace(tipo="Reta")),
    )


class PlanoDeLutaTests(unittest.TestCase):
    _fighter = staticmethod(_helpers.RemainingSkillRegressionTests._fighter)

    def test_ciclo_de_vida_escolhe_expira_reescolhe(self):
        lutador = self._fighter("Planejador")
        brain = _brain_planejador(lutador)
        inimigo = _inimigo_fisico()

        brain._atualizar_plano(1 / 60, 4.0, inimigo)
        plano1 = brain.plano
        self.assertIsNotNone(plano1)
        self.assertIn("tipo", plano1)
        self.assertGreater(plano1["expira_em"], brain.tempo_combate)
        # Duração dentro do contrato 2-6s.
        self.assertLessEqual(plano1["expira_em"] - brain.tempo_combate, 6.01)
        self.assertGreaterEqual(plano1["expira_em"] - brain.tempo_combate, 2.0)

        # Antes de expirar: plano estável.
        brain.tempo_combate += 1.0
        brain._atualizar_plano(1 / 60, 4.0, inimigo)
        self.assertIs(brain.plano, plano1)

        # Depois de expirar: reescolhe.
        brain.tempo_combate = plano1["expira_em"] + 0.01
        brain._atualizar_plano(1 / 60, 4.0, inimigo)
        self.assertIsNot(brain.plano, plano1)
        self.assertEqual(brain.contadores["planos"], 2)

    def test_ciclo_e_deterministico_com_mesma_seed(self):
        tipos = []
        for _ in range(2):
            lutador = self._fighter("Planejador")
            brain = _brain_planejador(lutador, seed=42)
            inimigo = _inimigo_fisico()
            sequencia = []
            for i in range(5):
                brain.tempo_combate = 10.0 + i * 7.0  # força expiração
                brain._atualizar_plano(1 / 60, 4.0, inimigo)
                sequencia.append(brain.plano["tipo"])
            tipos.append(sequencia)
        self.assertEqual(tipos[0], tipos[1])

    def test_hp_baixo_puxa_recuperar(self):
        lutador = self._fighter("Ferido")
        lutador.vida = lutador.vida_max * 0.15
        brain = _brain_planejador(lutador)
        brain.medo = 0.6
        inimigo = _inimigo_fisico()
        escolhas = set()
        for i in range(8):
            brain.tempo_combate = 10.0 + i * 7.0
            brain._atualizar_plano(1 / 60, 4.0, inimigo)
            escolhas.add(brain.plano["tipo"])
        self.assertIn("RECUPERAR", escolhas)

    def test_spike_de_dano_pode_interromper(self):
        lutador = self._fighter("Atingido")
        brain = _brain_planejador(lutador)
        brain.disciplina_tatica = 0.0  # compromisso mínimo (0.4)
        inimigo = _inimigo_fisico()
        brain._atualizar_plano(1 / 60, 4.0, inimigo)
        plano1 = brain.plano

        # Spike: perdeu 20% do HP agora.
        lutador.vida = lutador.vida_max * 0.8
        brain.tempo_desde_dano = 0.1
        trocou = False
        for _ in range(20):  # compromisso 0.4: ~60% de chance por check
            brain._atualizar_plano(1 / 60, 4.0, inimigo)
            if brain.plano is not plano1:
                trocou = True
                break
        self.assertTrue(trocou)

    def test_menu_nao_vazio_para_todo_arquetipo(self):
        """Todo arquétipo do catálogo produz um plano válido."""
        for arquetipo in ARQUETIPO_DATA:
            lutador = self._fighter("Sujeito")
            brain = _brain_planejador(lutador, seed=hash(arquetipo) % 1000)
            brain.arquetipo = arquetipo
            plano = brain._escolher_plano(4.0, _inimigo_fisico())
            self.assertIn(plano["tipo"], (
                "PRESSIONAR", "BAITAR_E_PUNIR", "MANTER_ZONA_MORTA",
                "LEVAR_PARA_PAREDE", "CACAR_JANELA_SKILL", "RECUPERAR",
            ))


class FixDoMeleeTests(unittest.TestCase):
    """Roll de ataque com golpe em cooldown NÃO consome mais o frame."""

    _fighter = staticmethod(_helpers.RemainingSkillRegressionTests._fighter)

    def _brain_em_range(self, lutador):
        brain = _brain_planejador(lutador)
        brain.janela_ataque = {"aberta": False, "tipo": None,
                               "qualidade": 0.0, "duracao": 0.0}
        brain.combo_state = {"em_combo": False, "pode_followup": False}
        brain.raiva = 0.0
        brain._acao_atual = "COMBATE"
        brain._acao_fonte = "init"
        brain._acao_hold_ate = 0.0
        brain._acao_hold_prio = 9
        brain._modo_proposta = False
        brain._contexto_escrita = 2
        brain.rng = SimpleNamespace(
            random=lambda: 0.0,  # roll de ataque sempre passa
            uniform=lambda a, b: a,
            choice=lambda o: o[0],
        )
        return brain

    def test_cooldown_rolando_cai_para_a_decisao(self):
        lutador = self._fighter("Espadachim")
        lutador.cooldown_ataque = 0.8  # golpe indisponível
        lutador.atacando = False
        brain = self._brain_em_range(lutador)
        with patch.object(brain, "_executar_ataque") as executar:
            consumiu = brain._avaliar_e_executar_ataque(
                1 / 60, 1.0, _inimigo_fisico(x=1.0)
            )
        executar.assert_called_once()      # intenção ofensiva escrita...
        self.assertFalse(consumiu)         # ...mas o frame segue vivo.

    def test_golpe_pronto_consome_o_frame(self):
        lutador = self._fighter("Espadachim")
        lutador.cooldown_ataque = 0.0
        lutador.atacando = False
        brain = self._brain_em_range(lutador)
        with patch.object(brain, "_executar_ataque"):
            consumiu = brain._avaliar_e_executar_ataque(
                1 / 60, 1.0, _inimigo_fisico(x=1.0)
            )
        self.assertTrue(consumiu)


class ArquetipoDuelistaTests(unittest.TestCase):
    def test_duelista_resolve_para_o_proprio_arquetipo(self):
        """Bug #2: 'Duelista (Precisão)' caía no fallback por arma."""
        dados = SimpleNamespace(
            nome="Preciso", tamanho=1.7, forca=6.0, mana=5.0,
            resistencia=5.0, velocidade=5.0,
            classe="Duelista (Precisão)", personalidade="Aleatório",
            nome_arma="", arma_obj=None,
        )
        with patch("neural_fights.ai.AIBrain", return_value=None):
            lutador = Lutador(dados, 5.0, 5.0)
        brain = object.__new__(AIBrain)
        brain.parent = lutador
        brain.rng = random.Random(1)
        brain.arquetipo = "GUERREIRO"
        brain.estilo_luta = "BALANCED"
        brain.agressividade_base = 0.5
        brain._definir_arquetipo()
        self.assertEqual(brain.arquetipo, "DUELISTA")

    def test_necromante_e_feiticeiro_nao_sao_mais_sombreados(self):
        for classe, esperado in (
            ("Necromante (Trevas)", "NECROMANTE"),
            ("Feiticeiro (Caos)", "ARCANO"),
        ):
            dados = SimpleNamespace(
                nome="Mistico", tamanho=1.7, forca=5.0, mana=8.0,
                resistencia=5.0, velocidade=5.0,
                classe=classe, personalidade="Aleatório",
                nome_arma="", arma_obj=None,
            )
            with patch("neural_fights.ai.AIBrain", return_value=None):
                lutador = Lutador(dados, 5.0, 5.0)
            brain = object.__new__(AIBrain)
            brain.parent = lutador
            brain.rng = random.Random(1)
            brain.arquetipo = "GUERREIRO"
            brain.estilo_luta = "BALANCED"
            brain.agressividade_base = 0.5
            brain._definir_arquetipo()
            self.assertEqual(brain.arquetipo, esperado)


if __name__ == "__main__":
    unittest.main()
