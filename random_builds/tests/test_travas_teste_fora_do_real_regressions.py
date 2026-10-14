# -*- coding: utf-8 -*-
"""SCR-M13 (14/10/2026): travas de teste na pasta REAL de locks.

Medido: 93 de 217 arquivos em `%LOCALAPPDATA%\\neural-fights\\locks\\` com
nome de teste (`teste_agenda_*`, `*duble*`...), o mais novo de 06/10. O
pytest isola pelo `conftest.py` da raiz; o caminho que ainda escreveria la e
um `python -m unittest` direto, sem `NEURAL_FIGHTS_RUNTIME_DIR`.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from builds import travas


class TravaDeTesteForaDoRealTests(unittest.TestCase):
    def test_sem_a_variavel_trava_de_teste_levanta(self):
        ambiente = {k: v for k, v in os.environ.items()
                    if k != "NEURAL_FIGHTS_RUNTIME_DIR"}
        with mock.patch.dict(os.environ, ambiente, clear=True):
            with self.assertRaises(RuntimeError):
                with travas.trava("teste_x"):
                    pass

    def test_com_a_variavel_cria_sob_ela(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"NEURAL_FIGHTS_RUNTIME_DIR": tmp}), \
                mock.patch.object(travas, "_pasta",
                                  return_value=Path(tmp) / "locks"):
            (Path(tmp) / "locks").mkdir()
            with travas.trava("teste_x") as minha:
                self.assertTrue(minha)
            self.assertTrue((Path(tmp) / "locks" / "teste_x.lock").is_file())

    def test_trava_de_producao_nao_e_afetada(self):
        ambiente = {k: v for k, v in os.environ.items()
                    if k != "NEURAL_FIGHTS_RUNTIME_DIR"}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, ambiente, clear=True), \
                mock.patch.object(travas, "_pasta", return_value=Path(tmp)):
            with travas.trava("historias__auto") as minha:
                self.assertTrue(minha)


if __name__ == "__main__":
    unittest.main()
