# -*- coding: utf-8 -*-
"""As tarefas de geracao de duelos tambem sao conferidas no Agendador.

`NeuralFights_gerar_01` a `_05` (01:02 a 05:02) nasceram em 27/09/2026 e
`panorama.recursos` nao as listava: se o Agendador as perdesse, a geracao
pararia sem nenhuma tela dizer — o builds ja ficou sem estoque de 22 a 26/09.
Nada aqui chama `schtasks`: `tarefas_windows.conferir` e dublado.
"""
import unittest

from builds import tarefas_windows
from builds.pipeline import noite
from panorama import recursos


class AsTarefasDeGeracao(unittest.TestCase):

    def setUp(self):
        reais = (tarefas_windows.conferir, noite.carregar,
                 recursos._horas_de_criacao)
        self.addCleanup(self._restaurar, reais)
        self.existem = set()
        tarefas_windows.conferir = (
            lambda nome: {"confiavel": True} if nome in self.existem else None)
        recursos._horas_de_criacao = lambda: []
        self.config = {"ativo": True, "horas": [1, 2, 3, 4, 5]}
        noite.carregar = lambda caminho=None: dict(self.config)

    @staticmethod
    def _restaurar(reais):
        (tarefas_windows.conferir, noite.carregar,
         recursos._horas_de_criacao) = reais

    def test_as_cinco_de_madrugada_entram_na_conta(self):
        esperadas = [f"NeuralFights_gerar_{h:02d}" for h in range(1, 6)]
        self.assertEqual(esperadas, recursos._tarefas_de_geracao())
        agendador = recursos._agendador()
        self.assertEqual(esperadas,
                         [n for n in agendador["faltando"]
                          if n.startswith("NeuralFights_gerar")])

    def test_a_que_sumiu_aparece_e_as_outras_nao(self):
        self.existem = {f"NeuralFights_gerar_{h:02d}" for h in (1, 2, 4, 5)}
        faltando = recursos._agendador()["faltando"]
        self.assertIn("NeuralFights_gerar_03", faltando)
        self.assertNotIn("NeuralFights_gerar_01", faltando)

    def test_as_horas_vem_do_config_e_nao_de_uma_lista_fixa(self):
        self.config["horas"] = [2, 4]
        self.assertEqual(["NeuralFights_gerar_02", "NeuralFights_gerar_04"],
                         recursos._tarefas_de_geracao())

    def test_geracao_desligada_nao_cobra_tarefa(self):
        self.config["ativo"] = False
        self.assertEqual([], recursos._tarefas_de_geracao())
        self.assertFalse(any(n.startswith("NeuralFights_gerar")
                             for n in recursos._agendador()["faltando"]))

    def test_config_que_nao_carrega_nao_derruba_a_tela(self):
        def explode(caminho=None):
            raise OSError("config sumiu")

        noite.carregar = explode
        self.assertEqual([], recursos._tarefas_de_geracao())
        self.assertIn("total", recursos._agendador())


if __name__ == "__main__":
    unittest.main()
