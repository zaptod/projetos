# -*- coding: utf-8 -*-
"""Evidência de runtime dos instintos (Onda 5D).

Antes: 8/15 instintos referenciavam sinais que o runtime nunca despachou
(ataque_baixo/alto num jogo top-down, chave sendo_combo inexistente,
acao_atual lido do lutador em vez do brain) e as ações chamavam
p.iniciar_dash()/p.pular() — métodos que nunca existiram — ou escreviam
p.movimento_x, que o motor nunca leu. RECUAR era 98,7% dos disparos
porque condições de nível sem cooldown monopolizavam o loop.
"""

import unittest
from types import SimpleNamespace

from neural_fights.ai.brain import AIBrain
from neural_fights.ai.personalities import INSTINTOS
from neural_fights.tools.auditoria_personalidades import (
    _validar_instintos_vs_runtime,
)


class RngFixo:
    def __init__(self, valor: float = 0.0):
        self.valor = valor

    def random(self) -> float:
        return self.valor

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


def brain_minimo() -> AIBrain:
    brain = object.__new__(AIBrain)
    brain.parent = SimpleNamespace(
        vida=100.0,
        vida_max=100.0,
        pos=[0.0, 0.0],
        angulo_olhar=0.0,
        atacando=False,
    )
    brain.rng = RngFixo(0.0)
    brain.tracos = []
    brain._perfil_chave = ()
    brain._perfil_cache = {}
    brain._acao_atual = "COMBATE"
    brain._acao_hold_ate = 0.0
    brain._acao_hold_prio = 9
    brain._modo_proposta = False
    # Espelha o wrapper de atualizar(): instinto escreve com prioridade 1.
    brain._contexto_escrita = 1
    brain.tempo_combate = 10.0
    brain.cd_instintos = {}
    brain.instintos = []
    brain.ultimo_bloqueio = 99.0
    brain.ultimo_dano_recebido = 0.0
    brain.janela_ataque = {"aberta": False, "tipo": None}
    brain.leitura_oponente = {}
    brain.contadores = {
        "decisoes": 0,
        "pilha_completa": 0,
        "escritas_aceitas": 0,
        "escritas_seguradas": 0,
    }
    return brain


def inimigo_parado():
    return SimpleNamespace(
        vida=100.0,
        vida_max=100.0,
        pos=[3.0, 0.0],
        atacando=False,
        brain=None,
    )


class TriggersReaisTests(unittest.TestCase):
    """Cada trigger consertado avalia True sob o estado real que o gera."""

    def test_oponente_recuando_le_o_brain_do_inimigo(self) -> None:
        """A versão antiga lia acao_atual do LUTADOR — sempre None."""
        brain = brain_minimo()
        inimigo = inimigo_parado()
        inimigo.brain = SimpleNamespace(acao_atual="FUGIR")
        self.assertTrue(
            brain._avaliar_trigger_instinto(
                "oponente_recuando", 5.0, inimigo, 1.0, 1.0
            )
        )
        inimigo.brain = SimpleNamespace(acao_atual="MATAR")
        self.assertFalse(
            brain._avaliar_trigger_instinto(
                "oponente_recuando", 5.0, inimigo, 1.0, 1.0
            )
        )

    def test_sendo_comboado_e_levar_hits_em_sequencia(self) -> None:
        """A chave combo_state['sendo_combo'] nunca existiu."""
        brain = brain_minimo()
        brain.hits_recebidos_recente = 3
        brain.tempo_desde_dano = 0.4
        self.assertTrue(
            brain._avaliar_trigger_instinto("sendo_comboado", 2.0, None, 1.0, 1.0)
        )

    def test_janela_punicao_usa_o_vocabulario_real(self) -> None:
        """Era comparado com 'whiff', tipo que não existe nas janelas."""
        brain = brain_minimo()
        brain.janela_ataque = {"aberta": True, "tipo": "pos_ataque"}
        self.assertTrue(
            brain._avaliar_trigger_instinto("janela_punicao", 2.0, None, 1.0, 1.0)
        )
        brain.janela_ataque = {"aberta": True, "tipo": "fugindo"}
        self.assertFalse(
            brain._avaliar_trigger_instinto("janela_punicao", 2.0, None, 1.0, 1.0)
        )

    def test_bloqueio_sucesso_tem_escritor_agora(self) -> None:
        """ultimo_bloqueio não tinha NENHUM escritor no projeto."""
        brain = brain_minimo()
        brain.ultimo_bloqueio = 0.2
        self.assertTrue(
            brain._avaliar_trigger_instinto("bloqueio_sucesso", 2.0, None, 1.0, 1.0)
        )

    def test_ataque_traseiro_por_geometria_real(self) -> None:
        brain = brain_minimo()  # olhando para +x
        atras = SimpleNamespace(
            vida=100.0, vida_max=100.0, pos=[-3.0, 0.0], atacando=True
        )
        frente = SimpleNamespace(
            vida=100.0, vida_max=100.0, pos=[3.0, 0.0], atacando=True
        )
        self.assertTrue(
            brain._avaliar_trigger_instinto("ataque_traseiro", 3.0, atras, 1.0, 1.0)
        )
        self.assertFalse(
            brain._avaliar_trigger_instinto("ataque_traseiro", 3.0, frente, 1.0, 1.0)
        )

    def test_projetil_vindo_usa_o_detector_real(self) -> None:
        brain = brain_minimo()
        brain._detectar_projetil_vindo = lambda inimigo: True
        self.assertTrue(
            brain._avaliar_trigger_instinto("projetil_vindo", 8.0, None, 1.0, 1.0)
        )

    def test_ataque_iminente_perto_le_a_leitura(self) -> None:
        brain = brain_minimo()
        brain.leitura_oponente = {"ataque_iminente": True}
        self.assertTrue(
            brain._avaliar_trigger_instinto(
                "ataque_iminente_perto", 2.0, None, 1.0, 1.0
            )
        )
        self.assertFalse(
            brain._avaliar_trigger_instinto(
                "ataque_iminente_perto", 8.0, None, 1.0, 1.0
            )
        )


class PrioridadeECooldownTests(unittest.TestCase):
    def test_reflexo_p1_vence_postura_p2(self) -> None:
        """RECUAR dominava 98,7% porque o primeiro da lista vencia; agora
        o candidato de prioridade mais forte rola primeiro."""
        brain = brain_minimo()
        brain.parent.vida = 30.0  # hp_baixo (DEFESA_FINAL, P2) ativo
        brain._detectar_projetil_vindo = lambda inimigo: True  # PULO (P1)
        brain.instintos = ["DEFESA_FINAL", "PULO_PERIGO"]
        consumiu = brain._processar_instintos(1 / 60, 8.0, inimigo_parado())
        self.assertTrue(consumiu)
        self.assertEqual(brain.acao_atual, "DESVIO")  # P1, não RECUAR

    def test_cooldown_por_instinto_impede_spam(self) -> None:
        brain = brain_minimo()
        brain.parent.vida = 10.0  # hp_critico
        brain.instintos = ["DASH_PANICO"]
        self.assertTrue(brain._processar_instintos(1 / 60, 8.0, inimigo_parado()))
        self.assertEqual(brain.acao_atual, "FUGIR")
        # mesmo estado, frame seguinte: cooldown segura
        brain.tempo_combate += 1 / 60
        self.assertFalse(brain._processar_instintos(1 / 60, 8.0, inimigo_parado()))
        # depois do cooldown (5s), dispara de novo
        brain.tempo_combate += 6.0
        self.assertTrue(brain._processar_instintos(1 / 60, 8.0, inimigo_parado()))

    def test_instinto_p1_interrompe_hold_de_decisao(self) -> None:
        """O poder do instinto é o commit P1 no escritor único."""
        brain = brain_minimo()
        brain._definir_acao("MATAR", fonte="decisao", prioridade=3)
        brain.parent.vida = 10.0
        brain.instintos = ["DASH_PANICO"]
        brain._processar_instintos(1 / 60, 8.0, inimigo_parado())
        self.assertEqual(brain.acao_atual, "FUGIR")


class CatalogoVsRuntimeTests(unittest.TestCase):
    def test_toda_entrada_do_catalogo_tem_despacho_real(self) -> None:
        """O contrato da auditoria, provado direto: catálogo íntegro."""
        erros: list = []
        avisos: list = []
        _validar_instintos_vs_runtime({"INSTINTOS": INSTINTOS}, erros, avisos)
        self.assertEqual(erros, [])

    def test_auditoria_pega_trigger_e_acao_fantasmas(self) -> None:
        """Prova com catálogo quebrado de propósito (padrão da casa)."""
        quebrado = {
            "INSTINTOS": {
                "FANTASMA": {
                    "trigger": "ataque_baixo",  # a ficção original
                    "acao": "auto_jump",
                    "chance": 0.5,
                    "prioridade": 1,
                    "cooldown": 1.0,
                }
            }
        }
        erros: list = []
        avisos: list = []
        _validar_instintos_vs_runtime(quebrado, erros, avisos)
        self.assertEqual(len(erros), 2)
        self.assertIn("sem despacho no runtime", erros[0])
        self.assertIn("sem executor no runtime", erros[1])


if __name__ == "__main__":
    unittest.main()
