# -*- coding: utf-8 -*-
"""SCR-9 (14/10/2026): o runtime de teste nao isolava quatro modulos.

Medido: com `NEURAL_FIGHTS_RUNTIME_DIR` apontado para uma pasta de teste,
`remoto.config.runtime_dir()`, `remoto.biblioteca.PASTA`,
`ferramentas.handoff.LOCAL` e `coordenador.estado.pasta()` (fora do pytest)
davam `C:\\Users\\adrian\\AppData\\Local\\neural-fights` — o proximo teste
sem patch gravaria em producao. Roda num subprocesso limpo, como o
`testar.py` (unittest, sem `PYTEST_CURRENT_TEST`).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

CODIGO = r"""
import json, sys
# `-c` com cwd na raiz: a raiz ja e o sys.path[0]
from remoto import config, biblioteca
from coordenador import estado
import importlib.util
spec = importlib.util.spec_from_file_location("handoff_teste", sys.argv[1] + "/ferramentas/handoff.py")
handoff = importlib.util.module_from_spec(spec); spec.loader.exec_module(handoff)
print(json.dumps([str(config.runtime_dir()), str(biblioteca.PASTA),
                  str(handoff.LOCAL), str(estado.pasta())]))
"""


class RuntimeIsoladoTests(unittest.TestCase):
    def test_os_quatro_ficam_sob_o_runtime_de_teste(self):
        with tempfile.TemporaryDirectory() as tmp:
            ambiente = {k: v for k, v in os.environ.items()
                        if k not in ("PYTEST_CURRENT_TEST", "NF_COORDENADOR_PASTA")}
            ambiente["NEURAL_FIGHTS_RUNTIME_DIR"] = tmp
            feito = subprocess.run(
                [sys.executable, "-X", "utf8", "-c", CODIGO, str(RAIZ)],
                capture_output=True, text=True, encoding="utf-8", env=ambiente,
                cwd=str(RAIZ), timeout=120)
            self.assertEqual(0, feito.returncode, feito.stderr)
            caminhos = json.loads(feito.stdout.strip().splitlines()[-1])
            base = str(Path(tmp).resolve()).lower()
            for caminho in caminhos:
                self.assertTrue(str(Path(caminho).resolve()).lower().startswith(base),
                                (caminho, tmp))


if __name__ == "__main__":
    unittest.main()
