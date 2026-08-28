# -*- coding: utf-8 -*-
"""Regressões dos planos visíveis e adaptativos (Onda 10C).

O plano é objeto (rótulo, verbos, progresso, objetivo), termina por
sucesso/falha, nasce do que o lutador OBSERVA (guarda repetida, fuga, HP
baixo, parede) e governa o portão de ataque — não só o movimento.
"""

from __future__ import annotations

import random
import unittest
from types import SimpleNamespace

from neural_fights.ai import plano_de_luta as pl
from neural_fights.ai.brain import AIBrain
from tests import test_remaining_skill_regressions as _helpers


def _lutador(x=0.0, vida=1.0):
    p = _helpers.RemainingSkillRegressionTests._fighter("Um", x=x)
    p.vida = p.vida_max * vida
    return p


def _brain(parent, seed=11):
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
    brain.contadores = {"decisoes": 0, "pilha_completa": 0,
                        "escritas_aceitas": 0, "escritas_seguradas": 0}
    brain.tell_atual = None
    brain._acao_atual = "CIRCULAR"
    brain._observar = lambda inimigo: SimpleNamespace(intencao="parado", fase_ataque=None)
    return brain


class ObjetoDePlanoTests(unittest.TestCase):
    def test_compat_com_o_dict_da_8e(self):
        plano = pl.criar_plano("PRESSIONAR", 10.0, 3.0, 0.7)
        self.assertEqual(plano["tipo"], "PRESSIONAR")
        self.assertIn("tipo", plano)
        self.assertEqual(plano.get("expira_em"), 13.0)
        self.assertEqual(plano.rotulo, "PRESSÃO")
        self.assertIn("MATAR", plano.verbos)
        self.assertFalse(plano.adaptativo)

    def test_toda_definicao_tem_rotulo_verbos_e_objetivo(self):
        for tipo, definicao in pl.DEFINICOES.items():
            self.assertTrue(definicao.rotulo, tipo)
            self.assertGreaterEqual(len(definicao.verbos), 3, tipo)
            self.assertTrue(definicao.objetivo, tipo)
        self.assertGreaterEqual(len(pl.TIPOS_ADAPTATIVOS), 5)

    def test_sucesso_encerra_e_progresso_sobe(self):
        plano = pl.criar_plano("PRESSIONAR", 0.0, 4.0, 0.7)
        ctx = pl.ContextoPlano(tempo=2.0, hits_dados=1)
        self.assertIsNone(pl.avaliar(plano, ctx))
        self.assertAlmostEqual(plano.progresso, 0.5)
        ctx = pl.ContextoPlano(tempo=2.5, hits_dados=2)
        self.assertEqual(pl.avaliar(plano, ctx), "sucesso")
        self.assertEqual(plano.progresso, 1.0)

    def test_min_duracao_segura_fim_precoce(self):
        plano = pl.criar_plano("PRESSIONAR", 0.0, 4.0, 0.7)
        ctx = pl.ContextoPlano(tempo=0.3, hits_dados=5)
        self.assertIsNone(pl.avaliar(plano, ctx))

    def test_falha_por_objetivo(self):
        plano = pl.criar_plano("QUEBRAR_GUARDA", 0.0, 6.0, 0.7)
        self.assertEqual(pl.avaliar(plano, pl.ContextoPlano(tempo=3.5)), "falha")
        plano = pl.criar_plano("ACABAR", 0.0, 6.0, 0.7)
        self.assertEqual(pl.avaliar(plano, pl.ContextoPlano(tempo=1.0, hp=0.1, medo=0.9)), "falha")
        self.assertEqual(pl.avaliar(plano, pl.ContextoPlano(tempo=1.0, inimigo_morto=True)), "sucesso")


class PlanosAdaptativosTests(unittest.TestCase):
    def _cenario(self, hp_inimigo=1.0, dist=3.0):
        p1 = _lutador(0.0)
        p2 = _lutador(dist, vida=hp_inimigo)
        return p1, p2, _brain(p1)

    def test_quebrar_guarda_apos_duas_guardas_em_quatro_swings(self):
        p1, p2, brain = self._cenario()
        p2.tempo_bloqueando = 0.5
        for i in range(3):
            p1.ataque_id += 1
            brain._observar_para_planos(1 / 60, p2)
        brain._atualizar_plano(1 / 60, 2.0, p2)
        self.assertEqual(brain.plano["tipo"], "QUEBRAR_GUARDA")
        self.assertTrue(brain.plano.adaptativo)
        self.assertEqual(brain.contadores.get("planos_adaptativos"), 1)
        self.assertEqual(brain.tell_atual["rotulo"], "QUEBRAR GUARDA")

    def test_cortar_fuga_apos_recuo_observado(self):
        p1, p2, brain = self._cenario(dist=5.0)
        brain._observar = lambda inimigo: SimpleNamespace(intencao="recuando", fase_ataque=None)
        for _ in range(int(0.7 * 60)):
            brain._observar_para_planos(1 / 60, p2)
        brain._atualizar_plano(1 / 60, 5.0, p2)
        self.assertEqual(brain.plano["tipo"], "CORTAR_FUGA")

    def test_acabar_domina_com_hp_baixo(self):
        for seed in range(6):
            p1, p2, brain = self._cenario(hp_inimigo=0.2)
            brain.rng = random.Random(seed)
            brain._atualizar_plano(1 / 60, 3.0, p2)
            self.assertEqual(brain.plano["tipo"], "ACABAR", seed)

    def test_esmagar_na_parede_quando_oponente_encurralado(self):
        p1, p2, brain = self._cenario(dist=2.0)
        brain.consciencia_espacial = {"oponente_contra_parede": True}
        brain.plano = pl.criar_plano("LEVAR_PARA_PAREDE", 8.5, 3.0, 0.7)
        brain._atualizar_plano(1 / 60, 2.0, p2)
        # LEVAR_PARA_PAREDE cumpriu o objetivo (parede) e emenda ESMAGAR.
        self.assertEqual(brain.contadores.get("planos_sucesso"), 1)
        self.assertEqual(brain.plano["tipo"], "ESMAGAR_NA_PAREDE")

    def test_sucesso_encerra_antes_de_expirar(self):
        p1, p2, brain = self._cenario()
        brain._atualizar_plano(1 / 60, 3.0, p2)
        brain.plano = pl.criar_plano("PRESSIONAR", brain.tempo_combate, 6.0, 0.9,
                                     marcadores={"hits_dados": 0, "hp": 1.0})
        brain.tempo_combate += 2.0
        p2.contadores_luta["hits_sofridos"] = 2
        brain._atualizar_plano(1 / 60, 3.0, p2)
        self.assertGreaterEqual(brain.contadores.get("planos_sucesso", 0), 1)
        self.assertGreater(brain.plano.inicio, 10.0)

    def test_aplicar_plano_mantem_verbo_do_conjunto(self):
        p1, p2, brain = self._cenario()
        brain.plano = pl.criar_plano("PRESSIONAR", 10.0, 4.0, 0.7)
        brain._modo_proposta = True
        brain._acao_atual = "MATAR"          # já serve ao plano
        brain._aplicar_plano_de_luta(3.0, p2)
        self.assertEqual(brain.acao_atual, "MATAR")
        brain.rng = random.Random(0)
        vistos = set()
        for _ in range(20):
            brain._acao_atual = "BLOQUEAR"   # fora do conjunto
            brain._aplicar_plano_de_luta(3.0, p2)
            vistos.add(brain.acao_atual)
        self.assertTrue(vistos <= set(brain.plano.verbos) | {"BLOQUEAR"})
        self.assertGreater(len(vistos - {"BLOQUEAR"}), 0)

    def test_portao_de_ataque_le_o_plano(self):
        p1, p2, brain = self._cenario()
        janela = {"aberta": False}
        brain.plano = pl.criar_plano("ACABAR", 10.0, 4.0, 0.7)
        self.assertGreaterEqual(brain._aplicar_plano_ao_portao(0.5, 1.0, janela), 0.9)
        brain.plano = pl.criar_plano("BAITAR_E_PUNIR", 10.0, 4.0, 0.7)
        self.assertLess(brain._aplicar_plano_ao_portao(0.5, 1.0, janela), 0.5)
        brain.plano = pl.criar_plano("QUEBRAR_GUARDA", 10.0, 4.0, 0.7)
        brain._aplicar_plano_ao_portao(0.5, 1.0, janela)
        self.assertTrue(brain._preferir_esmagar)
        self.assertTrue(brain._pedir_agarrao)

    def test_sequencia_deterministica_por_seed(self):
        def rodar(seed):
            p1, p2, brain = self._cenario()
            brain.rng = random.Random(seed)
            seq = []
            for _ in range(600):
                brain.tempo_combate += 1 / 60
                brain._atualizar_plano(1 / 60, 3.0, p2)
                seq.append(brain.plano["tipo"])
            return seq
        self.assertEqual(rodar(4), rodar(4))
        self.assertGreaterEqual(len(set(rodar(4))), 1)


if __name__ == "__main__":
    unittest.main()
