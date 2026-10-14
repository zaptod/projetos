# -*- coding: utf-8 -*-
"""SCR-3: o CI nunca rodou um passo (87 runs, 19/08 -> 14/10/2026, em 0 s).

A causa: `${{ runner.temp }}` no `env:` de JOB, onde o contexto `runner` nao
existe ("workflow file issue"). O 9844a93 tirou de la e definiu a pasta num
passo; este teste impede a volta. E o ruff limpo, que tambem barrava o CI
(F821 real em `view_torneio.py`: `str(error)` num lambda depois do except).
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
WORKFLOWS = RAIZ / ".github" / "workflows"


class WorkflowTests(unittest.TestCase):
    def test_env_de_job_nao_usa_runner(self):
        try:
            import yaml
        except ImportError:                                   # pragma: no cover
            self.skipTest("sem pyyaml")
        ruins = []
        for arquivo in sorted(WORKFLOWS.glob("*.yml")):
            dados = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
            for nome, job in (dados.get("jobs") or {}).items():
                for chave, valor in ((job or {}).get("env") or {}).items():
                    if "runner." in str(valor):
                        ruins.append(f"{arquivo.name}:{nome}.env.{chave}")
        self.assertEqual([], ruins)

    def test_ruff_limpo(self):
        feito = subprocess.run([sys.executable, "-m", "ruff", "check", "."],
                               cwd=str(RAIZ), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        if "No module named ruff" in (feito.stderr or ""):
            self.skipTest("sem ruff")
        self.assertEqual(0, feito.returncode, feito.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
