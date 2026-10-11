# -*- coding: utf-8 -*-
"""Nao conseguir verificar NUNCA e o mesmo que estar tudo bem (11/10/2026).

Auditoria de 11/10/2026 (`docs/auditoria/2026-10-11/painel-e-vila.md`), o
defeito que ja custou caro aqui mais de uma vez: a tela diz "tudo em dia"
quando nem conseguiu olhar.

1. `auditoria.veredito` ignorava o campo `erro` de qualidade e metas. Com a
   vistoria e as metas ilegiveis, devolvia
   `{'cor': 'ok', 'frase': 'tudo em dia', 'problemas': []}` — e e esse o
   veredito que vai para o topo da pagina e para o Telegram.
2. `recursos._agendador` engolia a excecao de `tarefas_windows.conferir` com
   `continue`: com o Agendador fora, saia `{'total': 34, 'faltando': [],
   'fracas': []}`, que e exatamente o retrato de 34 tarefas saudaveis.

Nada aqui toca estado real nem o Agendador: tudo dublado.

    python -m pytest visao/tests/test_verificacao_impossivel_regressions.py -q
"""
from __future__ import annotations

import unittest

from builds import tarefas_windows
from panorama import auditoria, recursos


def _explode(*_a, **_k):
    raise OSError("agendador indisponivel")


class VereditoNaoVerificado(unittest.TestCase):

    def test_qualidade_e_metas_ilegiveis_nao_sao_tudo_em_dia(self):
        """A prova da auditoria, byte a byte."""
        dados = {"qualidade": {"erro": "vistoria indisponivel"},
                 "metas": {"erro": "ledger indisponivel"},
                 "recursos": {"alertas": []}}
        veredito = auditoria.veredito(dados)
        self.assertNotEqual("ok", veredito["cor"])
        self.assertNotEqual("tudo em dia", veredito["frase"])
        texto = " | ".join(veredito["problemas"])
        self.assertIn("vistoria indisponivel", texto)
        self.assertIn("ledger indisponivel", texto)
        self.assertTrue(all("nao consegui verificar" in p
                            for p in veredito["problemas"]))

    def test_cada_controle_ilegivel_vira_um_problema(self):
        bom = {"qualidade": {"liberados": 5, "barrados": 0, "fila": []},
               "metas": {"faltando": 0}, "recursos": {"alertas": []}}
        self.assertEqual("ok", auditoria.veredito(dict(bom))["cor"])
        for familia in ("qualidade", "metas", "recursos"):
            dados = dict(bom)
            dados[familia] = {"erro": f"{familia} caiu"}
            veredito = auditoria.veredito(dados)
            self.assertNotEqual("ok", veredito["cor"], familia)
            self.assertTrue(any(f"{familia} caiu" in p
                                for p in veredito["problemas"]), veredito)

    def test_controle_ausente_tambem_nao_e_verde(self):
        """Familia que nem veio (None) e familia que nao foi verificada."""
        dados = {"qualidade": {"liberados": 5, "barrados": 0, "fila": []},
                 "metas": None, "recursos": {"alertas": []}}
        self.assertNotEqual("ok", auditoria.veredito(dados)["cor"])

    def test_qualidade_ilegivel_nao_finge_fila_vazia(self):
        """Sem ler a fila, "nenhum video liberado" seria outra mentira."""
        dados = {"qualidade": {"erro": "x"}, "metas": {"faltando": 0},
                 "recursos": {"alertas": []}}
        problemas = auditoria.veredito(dados)["problemas"]
        self.assertFalse(any(p.startswith("nenhum video") for p in problemas))


class RecursosNaoVerificados(unittest.TestCase):
    """Os pedacos de `recursos` com `erro` viram alerta — e o veredito, que so
    le os alertas de recursos, deixa de ser verde."""

    def _com(self, **pedacos):
        reais = {n: getattr(recursos, n) for n in
                 ("_disco", "_travas", "_freio", "_credenciais")}
        self.addCleanup(lambda: [setattr(recursos, n, f)
                                 for n, f in reais.items()])
        recursos._disco = lambda: {"livre_gb": 100.0, "total_gb": 500.0,
                                   "situacao": "ok"}
        recursos._travas = lambda: {"ocupadas": [], "quantas": 0,
                                    "conhecidas": 3}
        recursos._freio = lambda: {"situacao": "rodando", "pausado": False,
                                   "alvos": [], "resumo": ""}
        recursos._credenciais = lambda: {
            "builds": {"youtube": True, "picasso": True, "tiktok": True}}
        for nome, valor in pedacos.items():
            setattr(recursos, nome, lambda v=valor: v)
        return recursos.situacao()

    def test_tudo_lido_nao_inventa_alerta(self):
        self.assertEqual([], self._com()["alertas"])

    def test_disco_freio_travas_ilegiveis_viram_alerta(self):
        for nome, rotulo in (("_disco", "disco"), ("_freio", "freio"),
                             ("_travas", "travas"),
                             ("_credenciais", "credenciais")):
            alertas = self._com(**{nome: {"erro": "OSError: sumiu"}})["alertas"]
            self.assertTrue(any("nao consegui verificar" in a and "sumiu" in a
                                for a in alertas), (rotulo, alertas))

    def test_login_que_nao_deu_para_conferir_vira_alerta(self):
        alertas = self._com(_credenciais={
            "builds": {"youtube": None, "picasso": True, "tiktok": True}})[
                "alertas"]
        self.assertTrue(any("youtube" in a and "nao consegui verificar" in a
                            for a in alertas), alertas)


class AgendadorSemLeitura(unittest.TestCase):

    def setUp(self):
        reais = (tarefas_windows.conferir, recursos._horas_de_criacao,
                 recursos._tarefas_de_geracao)
        self.addCleanup(self._restaurar, reais)
        recursos._horas_de_criacao = lambda: []
        recursos._tarefas_de_geracao = lambda: []

    @staticmethod
    def _restaurar(reais):
        (tarefas_windows.conferir, recursos._horas_de_criacao,
         recursos._tarefas_de_geracao) = reais

    def test_agendador_fora_nao_e_lista_saudavel(self):
        """A prova da auditoria: excecao em todas virava `faltando: []`."""
        tarefas_windows.conferir = _explode
        ficha = recursos._agendador()
        self.assertEqual(ficha["total"], len(ficha["sem_leitura"]))
        self.assertGreater(ficha["total"], 0)
        self.assertEqual([], ficha["faltando"])
        self.assertEqual([], ficha["fracas"])

    def test_uma_que_falhou_entra_so_ela(self):
        def conferir(nome):
            if nome == "NeuralFights_bot_telegram":
                raise OSError("timeout")
            return {"confiavel": True}

        tarefas_windows.conferir = conferir
        ficha = recursos._agendador()
        self.assertEqual(["NeuralFights_bot_telegram"], ficha["sem_leitura"])

    def _completo(self):
        reais = (recursos.situacao, recursos._oauth_vivo)
        self.addCleanup(lambda: setattr(recursos, "situacao", reais[0])
                        or setattr(recursos, "_oauth_vivo", reais[1]))
        recursos.situacao = lambda: {"alertas": []}
        recursos._oauth_vivo = lambda: {"builds": {"ok": True},
                                        "historias": {"ok": True}}
        return recursos.completo()

    def test_agendador_que_nao_respondeu_vira_alerta(self):
        tarefas_windows.conferir = _explode
        alertas = self._completo()["alertas"]
        self.assertTrue(any("Agendador" in a and "nao respondeu" in a
                            for a in alertas), alertas)
        veredito = auditoria.veredito(
            {"qualidade": {"liberados": 5, "barrados": 0, "fila": []},
             "metas": {"faltando": 0}, "recursos": {"alertas": alertas}})
        self.assertNotEqual("ok", veredito["cor"])

    def test_algumas_sem_leitura_viram_alerta_com_os_nomes(self):
        def conferir(nome):
            if nome == "NeuralFights_bot_telegram":
                raise OSError("timeout")
            return {"confiavel": True}

        tarefas_windows.conferir = conferir
        alertas = self._completo()["alertas"]
        self.assertTrue(any("NeuralFights_bot_telegram" in a
                            and "nao consegui verificar" in a
                            for a in alertas), alertas)

    def test_agendador_que_nem_importa_vira_alerta(self):
        reais = recursos._agendador
        self.addCleanup(setattr, recursos, "_agendador", reais)
        recursos._agendador = lambda: {"erro": "ImportError: sem builds"}
        alertas = self._completo()["alertas"]
        self.assertTrue(any("sem builds" in a for a in alertas), alertas)

    def test_oauth_que_nem_importa_vira_alerta(self):
        tarefas_windows.conferir = lambda nome: {"confiavel": True}
        reais = (recursos.situacao, recursos._oauth_vivo)
        self.addCleanup(lambda: setattr(recursos, "situacao", reais[0])
                        or setattr(recursos, "_oauth_vivo", reais[1]))
        recursos.situacao = lambda: {"alertas": []}
        recursos._oauth_vivo = lambda: {"erro": "ImportError: sem contas"}
        alertas = recursos.completo()["alertas"]
        self.assertTrue(any("sem contas" in a for a in alertas), alertas)


if __name__ == "__main__":
    unittest.main()
