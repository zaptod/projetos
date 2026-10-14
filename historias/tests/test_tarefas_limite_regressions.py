# -*- coding: utf-8 -*-
"""SCR-7: as tarefas `Historias_auto_*` ficavam com o PT72H do `/Create`.

A rodada das 07:02 de 12/10 (pid 4332) pendurou no Gemini as 13:09 e segurou
a tarefa e a trava `historias__auto` por 31 h. O instalador passa a limitar
cada tarefa a PT6H; a rodada calada e encerrada pelo vigia do coordenador
(`coordenador/vigia_rodadas.py`), e a ficha dela nasce quando ela pega a
trava (`agenda.rodar`).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from builds import tarefas_windows as TW
from contos.pipeline import tarefas


class _Proc:
    returncode, stdout, stderr = 0, "SUCESSO", ""


class LimiteDasTarefasDeHistoriasTests(unittest.TestCase):
    def test_instalar_limita_cada_tarefa_a_6_h(self):
        limites = []
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(tarefas, "_schtasks", return_value=_Proc()), \
                mock.patch.object(tarefas, "caminho_do_lancador",
                                  return_value=Path(tmp) / "auto.cmd"), \
                mock.patch.object(TW, "endurecer",
                                  return_value={"ok": True, "mensagem": ""}), \
                mock.patch.object(TW, "garantir_vbs",
                                  return_value=Path(tmp) / "oculto.vbs"), \
                mock.patch.object(TW, "limitar_execucao",
                                  side_effect=lambda nome, limite: limites.append(
                                      (nome, limite)) or {"ok": True}):
            fichas = tarefas.instalar([1, 7], {7: 2})
        self.assertEqual([("Historias_auto_01", "PT6H"),
                          ("Historias_auto_07", "PT6H")], limites)
        self.assertTrue(all(f["limitada"] for f in fichas))


class FichaDaRodadaTests(unittest.TestCase):
    def test_o_diario_da_rodada_renova_o_pulso(self):
        """Cada linha do `_SaidaNoDiario` chama `rodada_viva.pulsar`."""
        from builds import rodada_viva
        from contos.pipeline import agenda
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(rodada_viva, "pulsar") as pulsar:
            saida = agenda._SaidaNoDiario(Path(tmp) / "d.txt")
            saida.write("linha sem fim")
            pulsar.assert_not_called()
            saida.write(" e o fim\n")
            pulsar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
