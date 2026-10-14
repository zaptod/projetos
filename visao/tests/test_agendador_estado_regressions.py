# -*- coding: utf-8 -*-
"""SCR-P10: a conferencia do Agendador era cega a tarefa DESLIGADA.

Medido em 14/10/2026: `tarefas_windows.conferir` lia so os tres ajustes de
bateria, nao o `State`; um `NeuralFights_postar_17` desligado passava como
"confiavel". E as duas listas (panorama e relatorio do bot) diferiam entre si,
nenhuma tinha o `NeuralFights_coordenador`, e as duas cobravam o bot como
tarefa ligada depois de b1ef6f7 (bot, app e Vila sao do coordenador e as
tarefas deles estao Disabled de proposito).

Nada aqui chama o Agendador: `conferir` e o `_rodar` sao dublados.
"""
import unittest
from unittest import mock

from builds import tarefas_windows
from panorama import recursos


class EstadoDaTarefaTests(unittest.TestCase):
    def test_conferir_le_o_state(self):
        with mock.patch.object(tarefas_windows, "_rodar",
                               return_value=(0, "False;False;True;Disabled\n", "")):
            ficha = tarefas_windows.conferir("NeuralFights_postar_17")
        self.assertTrue(ficha["confiavel"])
        self.assertFalse(ficha["ligada"])
        self.assertEqual("Disabled", ficha["estado"])

    def test_postar_desligada_e_fraca(self):
        def conferir(nome):
            estado = "Disabled" if nome in (
                "NeuralFights_postar_17", *recursos.DESLIGADAS_DE_PROPOSITO) else "Ready"
            return {"confiavel": True, "estado": estado,
                    "ligada": estado != "Disabled"}
        with mock.patch.object(tarefas_windows, "conferir", conferir):
            ficha = recursos._agendador()
        self.assertEqual(["NeuralFights_postar_17"], ficha["fracas"])
        self.assertEqual([], ficha["faltando"])

    def test_bot_religado_sem_dever_e_fraco(self):
        def conferir(nome):
            return {"confiavel": True, "estado": "Ready", "ligada": True}
        with mock.patch.object(tarefas_windows, "conferir", conferir):
            ficha = recursos._agendador()
        self.assertEqual(sorted(recursos.DESLIGADAS_DE_PROPOSITO),
                         sorted(ficha["fracas"]))

    def test_desligada_de_proposito_ausente_nao_falta(self):
        def conferir(nome):
            if nome in recursos.DESLIGADAS_DE_PROPOSITO:
                return {}
            return {"confiavel": True, "estado": "Ready", "ligada": True}
        with mock.patch.object(tarefas_windows, "conferir", conferir):
            ficha = recursos._agendador()
        self.assertEqual([], ficha["faltando"])
        self.assertEqual([], ficha["fracas"])

    def test_lista_unica_tem_o_coordenador(self):
        esperadas = recursos.tarefas_esperadas()
        self.assertEqual("ligada", esperadas["NeuralFights_coordenador"])
        self.assertEqual("desligada", esperadas["NeuralFights_bot_telegram"])

    def test_o_relatorio_do_bot_confere_o_mesmo_conjunto(self):
        from remoto import relatorios
        pedidas = []

        def conferir(nome):
            pedidas.append(nome)
            return {"confiavel": True, "estado": "Ready", "ligada": True}
        with mock.patch.object(tarefas_windows, "conferir", conferir):
            relatorios._linhas_do_agendador()
        self.assertEqual(set(recursos.tarefas_esperadas()), set(pedidas))

    def test_caso_zero_nenhuma_tarefa_lida(self):
        """Agendador fora: nada falta, nada e fraco, TUDO sem leitura."""
        def explode(nome):
            raise OSError("fora")
        with mock.patch.object(tarefas_windows, "conferir", explode):
            ficha = recursos._agendador()
        self.assertEqual(ficha["total"], len(ficha["sem_leitura"]))


if __name__ == "__main__":
    unittest.main()
