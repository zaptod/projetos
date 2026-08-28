# -*- coding: utf-8 -*-
"""Regressões do inspetor de skills (Onda 11A) — a interface do MCP interno."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from neural_fights.tools import skill_inspector


def _rodar(argv):
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        codigo = skill_inspector.main(argv)
    return codigo, saida.getvalue()


class SkillInspectorCLITests(unittest.TestCase):
    def test_modulo_e_import_safe_sem_pygame(self):
        # O inspetor consulta contratos sem subir o jogo; só ``checar`` e
        # ``demos`` importam o motor (e o fazem tarde).
        resultado = subprocess.run(
            [
                sys.executable,
                "-c",
                "import neural_fights.tools.skill_inspector, sys; "
                "assert 'pygame' not in sys.modules, 'pygame importado'",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_exportar_gera_json_parseavel_com_todos_os_contratos(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "contratos.json")
            codigo, _ = _rodar(["exportar", "--saida", caminho])
            self.assertEqual(codigo, 0)
            with open(caminho, "r", encoding="utf-8") as arquivo:
                dump = json.load(arquivo)
        self.assertGreaterEqual(len(dump), 100)
        jc = dump["Julgamento Celestial"]
        self.assertEqual(jc["alcance_lancamento"], 8.0)
        self.assertEqual(jc["pilares"], 5)
        self.assertIn("dano", jc["consequencias"])

    def test_explicar_conhece_e_recusa(self):
        codigo, texto = _rodar(["explicar", "Julgamento Celestial"])
        self.assertEqual(codigo, 0)
        self.assertIn("Paladino", texto)
        codigo, _ = _rodar(["explicar", "Skill Inexistente"])
        self.assertEqual(codigo, 1)

    def test_listar_filtra_por_tipo(self):
        codigo, texto = _rodar(["listar", "--tipo", "TRAP"])
        self.assertEqual(codigo, 0)
        self.assertIn("Muralha de Gelo", texto)
        self.assertNotIn("Bola de Fogo", texto)


if __name__ == "__main__":
    unittest.main()
