# -*- coding: utf-8 -*-
"""SCR-5 (14/10/2026): `--instalar` da Vila religaria a tarefa desligada.

Desde 13/10 (b1ef6f7, decisao `geral/gerente-unico-dos-servicos`) a Vila e do
coordenador e a `NeuralFights_vila_flutuante` fica desligada de proposito.
Sem `--forcar`, `--instalar` nao cria nada.
"""
import unittest
from unittest import mock

from painel.flutuante import tarefa


class InstalarExigeForcarTests(unittest.TestCase):
    def test_sem_forcar_nao_cria(self):
        with mock.patch.object(tarefa, "instalar",
                               side_effect=AssertionError("criou")):
            self.assertEqual(1, tarefa.main(["--instalar"]))

    def test_com_forcar_cria(self):
        with mock.patch.object(tarefa, "instalar",
                               return_value={"ok": True, "mensagem": "x"}) as criar:
            self.assertEqual(0, tarefa.main(["--instalar", "--forcar"]))
        criar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
