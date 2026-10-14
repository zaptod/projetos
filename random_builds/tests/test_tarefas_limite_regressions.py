# -*- coding: utf-8 -*-
"""SCR-7: as tarefas `NeuralFights_gerar_*` ficavam com o PT72H do `/Create`.

Medido em 14/10/2026 (`Get-ScheduledTask`): 49 tarefas diarias com PT72H
(`Historias_auto_*` e `NeuralFights_gerar_*`), 10 com PT2H (as postagens) e 2
com PT0S. Com IgnoreNew, a tarefa pendurada ignorava os proprios disparos por
3 dias. O instalador passa a limitar a PT6H (o limite devolve a tarefa; quem
encerra a rodada calada e o vigia do coordenador).

E a guarda no funil: dentro de uma suite, `tarefas_windows` nao muda o
Agendador de verdade (os instaladores dublam o `/Create`, mas o ajuste
depois dele usa o nome real da tarefa).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from builds import tarefas_windows
from builds.pipeline import tarefas_noite


class _Proc:
    returncode, stdout, stderr = 0, "OK", ""


class LimiteDasTarefasDeGeracaoTests(unittest.TestCase):
    def test_instalar_limita_cada_tarefa_a_6_h(self):
        limites = []
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(tarefas_noite, "caminho_do_lancador",
                                  return_value=Path(tmp) / "gerar.cmd"), \
                mock.patch.object(tarefas_noite, "caminho_da_saida",
                                  return_value=Path(tmp) / "s.txt"), \
                mock.patch.object(tarefas_noite, "_schtasks",
                                  return_value=_Proc()), \
                mock.patch.object(tarefas_windows, "endurecer",
                                  return_value={"ok": True, "mensagem": ""}), \
                mock.patch.object(tarefas_windows, "acao_oculta",
                                  side_effect=lambda l: f"wscript {l}"), \
                mock.patch.object(tarefas_windows, "limitar_execucao",
                                  side_effect=lambda nome, limite: limites.append(
                                      (nome, limite)) or {"ok": True}):
            fichas = tarefas_noite.instalar([1, 5], minuto=2)
        self.assertEqual([("NeuralFights_gerar_01", "PT6H"),
                          ("NeuralFights_gerar_05", "PT6H")], limites)
        self.assertTrue(all(f["limitada"] for f in fichas))


class FichaDaRodadaDeGeracaoTests(unittest.TestCase):
    def test_o_diario_da_geracao_renova_o_pulso(self):
        """SCR-7: cada linha do `_Diario` chama `rodada_viva.pulsar`."""
        from builds import rodada_viva
        from builds.pipeline import noite
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(rodada_viva, "pulsar") as pulsar:
            diario = noite._Diario(Path(tmp) / "d.txt")
            diario.write("meia linha")
            pulsar.assert_not_called()
            diario.write(" fim\n")
            pulsar.assert_called_once()


class TesteNaoMudaOAgendadorTests(unittest.TestCase):
    def test_ajuste_recusado_dentro_da_suite(self):
        with mock.patch.object(tarefas_windows.subprocess, "run",
                               side_effect=AssertionError("rodou powershell")):
            ficha = tarefas_windows.limitar_execucao("Historias_auto_07", "PT6H")
            self.assertFalse(ficha["ok"])
            self.assertIn("teste", ficha["mensagem"])
            self.assertFalse(tarefas_windows.endurecer("Historias_auto_07")["ok"])


if __name__ == "__main__":
    unittest.main()
