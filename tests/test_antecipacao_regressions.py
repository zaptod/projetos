# -*- coding: utf-8 -*-
"""Regressões da antecipação (Onda 8D).

Contadores de hábito convergem com observações reais; a punição de whiff
só dispara dentro da janela observável e uma vez por swing; o baiting lê
os contadores de sucesso/falha que eram escritos e nunca lidos.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.ai.brain import AIBrain
from neural_fights.effects.weapon_animations import WEAPON_PROFILES
from tests import test_remaining_skill_regressions as _helpers


class _RngFixo:
    def __init__(self, valor=0.0):
        self.valor = valor

    def random(self):
        return self.valor

    def uniform(self, a, b):
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


def _brain_minimo(parent):
    brain = object.__new__(AIBrain)
    brain.parent = parent
    brain.rng = _RngFixo(0.0)
    brain.tempo_combate = 10.0
    brain._dt_atual = 1.0 / 60.0
    brain.habilidade_leitura = 0.9
    brain.tracos = []
    brain.quirks = []
    brain._obs_cache = None
    brain._obs_cache_tempo = -1.0
    brain._obs_ataque_id_visto = -1
    brain._obs_ataque_mal_lido = False
    brain._ataque_id_avaliado_punicao = -1
    brain.tempo_desde_dano = 5.0
    brain.medo = 0.0
    brain.memoria_oponente = {"padrao_detectado": None}
    brain.janela_ataque = {"aberta": False, "tipo": None}
    brain.leitura_oponente = {
        "ataque_iminente": False,
        "direcao_provavel": 0.0,
        "tempo_para_ataque": 0.0,
        "padrao_movimento": [],
        "padrao_ataque": [],
        "tendencia_esquerda": 0.5,
        "frequencia_pulo": 0.0,
        "agressividade_percebida": 0.5,
        "previsibilidade": 0.5,
    }
    # Escritor único.
    brain._acao_atual = "COMBATE"
    brain._acao_fonte = "init"
    brain._acao_hold_ate = 0.0
    brain._acao_hold_prio = 9
    brain._modo_proposta = False
    brain._contexto_escrita = 1
    brain.contadores = {
        "decisoes": 0,
        "pilha_completa": 0,
        "escritas_aceitas": 0,
        "escritas_seguradas": 0,
    }
    return brain


def _inimigo_em_recovery(x=1.5):
    """Dummy físico no início do recovery (sobra > 0.12s de animação)."""
    profile = WEAPON_PROFILES["Reta"]
    return SimpleNamespace(
        pos=[x, 5.0], vel=[0.0, 0.0], z=0.0,
        vida=100.0, vida_max=100.0,
        atacando=True,
        timer_animacao=profile.recovery_time,  # recovery inteiro pela frente
        ataque_id=7,
        pos_historico=[(x, 5.0)] * 15,
        dados=SimpleNamespace(arma_obj=SimpleNamespace(tipo="Reta")),
    )


class PunicaoWhiffTests(unittest.TestCase):
    _fighter = staticmethod(_helpers.RemainingSkillRegressionTests._fighter)

    def test_recovery_lido_dispara_punicao_uma_vez_por_swing(self):
        defensor = self._fighter("Punidor")
        brain = _brain_minimo(defensor)
        inimigo = _inimigo_em_recovery()

        self.assertTrue(brain._processar_punicao_whiff(1 / 60, 1.5, inimigo))
        self.assertEqual(brain.acao_atual, "CONTRA_ATAQUE")

        # Mesmo swing (mesmo ataque_id): não avalia de novo.
        brain._obs_cache = None
        self.assertFalse(brain._processar_punicao_whiff(1 / 60, 1.5, inimigo))

        # Novo swing: avalia de novo.
        inimigo.ataque_id = 8
        brain._obs_cache = None
        self.assertTrue(brain._processar_punicao_whiff(1 / 60, 1.5, inimigo))

    def test_sem_janela_nao_pune(self):
        defensor = self._fighter("Punidor")
        brain = _brain_minimo(defensor)
        parado = SimpleNamespace(
            pos=[1.5, 5.0], vel=[0.0, 0.0], z=0.0,
            vida=100.0, vida_max=100.0, atacando=False,
            ataque_id=1, pos_historico=[(1.5, 5.0)] * 15,
            dados=SimpleNamespace(arma_obj=SimpleNamespace(tipo="Reta")),
        )
        self.assertFalse(brain._processar_punicao_whiff(1 / 60, 1.5, parado))

    def test_golpe_que_me_acertou_nao_e_whiff(self):
        defensor = self._fighter("Punidor")
        brain = _brain_minimo(defensor)
        brain.tempo_desde_dano = 0.1  # acabei de apanhar desse golpe
        inimigo = _inimigo_em_recovery()
        self.assertFalse(brain._processar_punicao_whiff(1 / 60, 1.5, inimigo))

    def test_longe_demais_nao_pune(self):
        defensor = self._fighter("Punidor")
        brain = _brain_minimo(defensor)
        inimigo = _inimigo_em_recovery(x=15.0)
        self.assertFalse(brain._processar_punicao_whiff(1 / 60, 15.0, inimigo))


class RitmoDeGolpesTests(unittest.TestCase):
    _fighter = staticmethod(_helpers.RemainingSkillRegressionTests._fighter)

    def test_ritmo_converge_e_detecta_padrao(self):
        observador = self._fighter("Leitor")
        brain = _brain_minimo(observador)
        profile = WEAPON_PROFILES["Reta"]
        inimigo = SimpleNamespace(
            pos=[3.0, 5.0], vel=[0.0, 0.0], z=0.0,
            vida=100.0, vida_max=100.0, atacando=True,
            timer_animacao=profile.total_time, ataque_id=0,
            pos_historico=[(3.0, 5.0)] * 15,
            dados=SimpleNamespace(arma_obj=SimpleNamespace(tipo="Reta")),
        )
        # Oponente metronômico: um swing a cada 1.0s.
        for i in range(1, 6):
            inimigo.ataque_id = i
            brain.tempo_combate = 10.0 + i * 1.0
            brain._obs_cache = None
            brain._atualizar_leitura_oponente(1 / 60, 3.0, inimigo)

        leitura = brain.leitura_oponente
        self.assertAlmostEqual(leitura["ritmo_golpes_s"], 1.0, delta=0.05)
        self.assertEqual(
            brain.memoria_oponente["padrao_detectado"], "ritmico"
        )


if __name__ == "__main__":
    unittest.main()
