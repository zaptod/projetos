# -*- coding: utf-8 -*-
"""Regressoes da auditoria de geracao de builds de 11/10/2026.

Nada daqui usa outputs, ledger ou runtime de verdade.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from builds.arena.ledger import Ledger
from builds.pipeline import controller


class LedgerConcorrenteTests(unittest.TestCase):

    def test_instancias_com_copia_antiga_nao_perdem_luta(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "ledger.json"
            primeiro = Ledger(caminho)
            segundo = Ledger(caminho)
            primeiro.registrar({"match_id": 1, "seed": 1, "p1": "A", "p2": "B"},
                               origem="duelo")
            segundo.registrar({"match_id": 2, "seed": 2, "p1": "C", "p2": "D"},
                              origem="duelo")
            self.assertEqual([1, 2], [luta["seed"] for luta in Ledger(caminho).lutas])


class ReservaDeIdTests(unittest.TestCase):

    def test_proxima_pasta_e_reservada_ao_escolher_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            saida = Path(tmp)
            (saida / "generation_00001").mkdir()
            with mock.patch.object(controller, "OUTPUTS", saida):
                primeiro = controller._next_id()
                segundo = controller._next_id()
            self.assertEqual(("generation_00002", "generation_00003"),
                             (primeiro, segundo))
            self.assertTrue((saida / primeiro).is_dir())
            self.assertTrue((saida / segundo).is_dir())

    def test_numero_de_pasta_apagada_nao_volta(self):
        """generation_00044 foi tirada (arte alheia); o proximo e depois do maior."""
        with tempfile.TemporaryDirectory() as tmp:
            saida = Path(tmp)
            for n in (43, 45):
                (saida / f"generation_{n:05d}").mkdir()
            with mock.patch.object(controller, "OUTPUTS", saida):
                self.assertEqual("generation_00046", controller._next_id())


class CliGeracaoTests(unittest.TestCase):

    def setUp(self):
        spec = importlib.util.spec_from_file_location("main_auditoria", ROOT / "main.py")
        self.main = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(self.main)
        self.argv = sys.argv
        self.addCleanup(lambda: setattr(sys, "argv", self.argv))

    def test_generation_only_nao_enfileira_identidade(self):
        chamadas = []

        class Controlador:
            def generate(self, **kwargs):
                chamadas.append(kwargs)

        with mock.patch.object(self.main, "PipelineController", Controlador):
            sys.argv = ["main.py", "generate-video", "--generation-only"]
            self.main.main()
        self.assertEqual([False], [chamada["identity"] for chamada in chamadas])

    def test_count_zero_ou_negativo_e_erro_de_argumento(self):
        for valor in ("0", "-1"):
            with self.subTest(valor=valor), \
                    mock.patch.object(self.main, "PipelineController") as controlador:
                sys.argv = ["main.py", "generate-video", "--count", valor]
                with self.assertRaises(SystemExit) as erro:
                    self.main.main()
                self.assertEqual(2, erro.exception.code)
                controlador.assert_not_called()


if __name__ == "__main__":
    unittest.main()
