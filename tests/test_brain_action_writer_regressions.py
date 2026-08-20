# -*- coding: utf-8 -*-
"""Evidência de runtime do escritor único de ação (Onda 5B) e dos
consumidores dos eixos órfãos (Onda 5A).

Antes da Onda 5: 214 escritores soltos de ``acao_atual``, ação mediana de
16,7ms e 66% das trocas durando <=2 frames — tremor, não intenção. O
escritor único (``_definir_acao``) impõe min-hold por prioridade; a pilha
de personalidade roda em toda decisão via modo-proposta.
"""

import unittest
from types import SimpleNamespace

from neural_fights.ai.brain import AIBrain


class RngFixo:
    """RNG determinístico para os testes (mesmo padrão da suíte de eco)."""

    def __init__(self, valor: float = 0.0):
        self.valor = valor

    def random(self) -> float:
        return self.valor

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


def brain_minimo(acao: str = "NEUTRO", tempo: float = 0.0) -> AIBrain:
    """Fake do padrão da casa: object.__new__ + só o estado do contrato."""
    brain = object.__new__(AIBrain)
    brain._acao_atual = acao
    brain._acao_fonte = "init"
    brain._acao_hold_ate = 0.0
    brain._acao_hold_prio = 9
    brain._modo_proposta = False
    brain._contexto_escrita = 2
    brain.tempo_combate = tempo
    brain.contadores = {
        "decisoes": 0,
        "pilha_completa": 0,
        "escritas_aceitas": 0,
        "escritas_seguradas": 0,
    }
    brain.rng = RngFixo(0.0)
    return brain


def injetar_perfil(brain: AIBrain, **eixos) -> None:
    """``perfil`` é property que deriva dos traços com cache por chave;
    o fake injeta direto no cache (tracos=[] casa com a chave vazia)."""
    brain.tracos = []
    brain._perfil_chave = ()
    brain._perfil_cache = dict(eixos)


class EscritorUnicoTests(unittest.TestCase):
    def test_min_hold_segura_escrita_legada(self) -> None:
        """Duas escritas legadas no mesmo instante: a segunda é segurada."""
        brain = brain_minimo()
        brain.acao_atual = "COMBATE"       # commit + hold P2 (0,4s)
        brain.acao_atual = "RECUAR"        # mesmo instante -> segurada
        self.assertEqual(brain.acao_atual, "COMBATE")
        self.assertEqual(brain.contadores["escritas_seguradas"], 1)

    def test_hold_expira_com_o_relogio_do_combate(self) -> None:
        brain = brain_minimo()
        brain.acao_atual = "COMBATE"
        brain.tempo_combate = 0.6          # alem do hold P2 de 0,55s (O5E)
        brain.acao_atual = "RECUAR"
        self.assertEqual(brain.acao_atual, "RECUAR")

    def test_prioridade_forte_interrompe_hold(self) -> None:
        """Instinto/portão (P1) atravessa o hold de uma escrita legada."""
        brain = brain_minimo()
        brain.acao_atual = "COMBATE"
        aceito = brain._definir_acao("FUGIR", fonte="instinto", prioridade=1)
        self.assertTrue(aceito)
        self.assertEqual(brain.acao_atual, "FUGIR")

    def test_decisao_agendada_substitui_a_propria_decisao(self) -> None:
        """P3 pode trocar P3: o tick de decisão nunca é engolido pelo
        próprio hold."""
        brain = brain_minimo()
        brain._definir_acao("COMBATE", fonte="decisao", prioridade=3)
        aceito = brain._definir_acao("PRESSIONAR", fonte="decisao", prioridade=3)
        self.assertTrue(aceito)
        self.assertEqual(brain.acao_atual, "PRESSIONAR")

    def test_mesma_acao_nao_renova_hold(self) -> None:
        brain = brain_minimo()
        brain.acao_atual = "COMBATE"
        hold_antes = brain._acao_hold_ate
        brain.acao_atual = "COMBATE"       # no-op
        self.assertEqual(brain._acao_hold_ate, hold_antes)
        self.assertEqual(brain.contadores["escritas_aceitas"], 1)

    def test_modo_proposta_e_rascunho_livre(self) -> None:
        """Dentro da pilha (modo-proposta) não há hold: a cadeia transforma
        a proposta em paz, como sempre fez."""
        brain = brain_minimo()
        brain.acao_atual = "COMBATE"       # inicia hold
        brain._modo_proposta = True
        brain.acao_atual = "MATAR"
        brain.acao_atual = "POKE"
        self.assertEqual(brain.acao_atual, "POKE")
        brain._modo_proposta = False


class EixosOrfaosTests(unittest.TestCase):
    def test_agressividade_efetiva_le_preset_eixo_e_humor(self) -> None:
        """agressividade_base (presets) + eixo agressao + humor — o leitor
        vivo que faltava desde a migração dos 162 traços."""
        brain = brain_minimo()
        brain.agressividade_base = 0.5
        injetar_perfil(brain, agressao=1.0)
        brain.humor = "FURIOSO"
        self.assertAlmostEqual(brain.agressividade_efetiva(), 0.95)
        brain.humor = "NEUTRO"
        self.assertAlmostEqual(brain.agressividade_efetiva(), 0.75)

    def test_eixo_mobilidade_reposiciona_proposta_estatica(self) -> None:
        brain = brain_minimo()
        brain._modo_proposta = True
        brain.acao_atual = "COMBATE"
        injetar_perfil(brain, mobilidade=1.0, perseguicao=0.0)
        brain._aplicar_eixos_orfaos(3.0, SimpleNamespace(brain=None))
        self.assertIn(brain.acao_atual, ("CIRCULAR", "FLANQUEAR"))

    def test_eixo_perseguicao_responde_a_fuga(self) -> None:
        brain = brain_minimo()
        brain._modo_proposta = True
        brain.acao_atual = "COMBATE"
        injetar_perfil(brain, mobilidade=0.0, perseguicao=1.0)
        inimigo = SimpleNamespace(brain=SimpleNamespace(acao_atual="FUGIR"))
        brain._aplicar_eixos_orfaos(6.0, inimigo)
        self.assertIn(brain.acao_atual, ("PRESSIONAR", "APROXIMAR"))


if __name__ == "__main__":
    unittest.main()
