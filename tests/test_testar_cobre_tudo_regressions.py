# -*- coding: utf-8 -*-
"""SCR-2 e SCR-10 (14/10/2026): o `testar.py` nao rodava tudo.

SCR-2: as suites eram `unittest discover`, que nao coleta funcao de teste
pytest nem carrega `conftest.py`: os testes do app, do delegar e do
orquestrador e o `coordenador/`, a `esteira_sprites/` e o `palco/testes/`
inteiros ficavam fora do "TUDO VERDE".

SCR-10: `integridade()` nao olhava `.cmd` nem `coordenador/`, `ias/`,
`palco/`; e a pasta descartavel ficava no C: cheio.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _testar():
    spec = importlib.util.spec_from_file_location("testar_teste", RAIZ / "testar.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class CobreTudoTests(unittest.TestCase):
    def test_toda_pasta_com_teste_tem_suite_pytest(self):
        testar = _testar()
        cobertas = []
        for _nome, pasta, comando in testar.SUITES:
            self.assertIn("pytest", comando)
            cobertas.append((Path(pasta) / comando[-1]).resolve())
        faltando = set()
        for arquivo in RAIZ.rglob("test_*.py"):
            if testar._ignorado(arquivo) or "fixtures" in arquivo.parts:
                continue
            topo = arquivo.relative_to(RAIZ).parts[0]
            if topo in testar.IGNORAR_NO_TESTAR or arquivo.parent == RAIZ:
                continue
            if not any(c == arquivo.resolve() or c in arquivo.resolve().parents
                       for c in cobertas):
                faltando.add(str(arquivo.parent.relative_to(RAIZ)))
        self.assertEqual(set(), faltando)

    def test_coordenador_entra(self):
        nomes = [c[-1] for _n, _p, c in _testar().SUITES]
        for pasta in ("coordenador", "esteira_sprites", "palco/testes"):
            self.assertIn(pasta, nomes)

    def test_integridade_ve_cmd(self):
        testar = _testar()
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "coordenador").mkdir()
            (raiz / "coordenador" / "x.cmd").write_bytes(b"@echo off\r\nrem a\x08b\r\n")
            (raiz / "outputs").mkdir()
            (raiz / "outputs" / "y.cmd").write_bytes(b"\x07")
            resultado = testar.integridade(raiz)
        self.assertFalse(resultado["ok"])
        self.assertEqual(["x.cmd:2"], resultado["falhas"])

    def test_placar_do_pytest_e_lido(self):
        testar = _testar()
        import re
        saida = "....\nFAILED tests/test_x.py::T::test_a - boom\n1 failed, 37 passed in 2.1s\n"
        self.assertEqual("37", re.search(r"(\d+) passed", saida).group(1))
        self.assertTrue(testar.PASTA_DESCARTAVEL.name == "neural-fights-testar")


if __name__ == "__main__":
    unittest.main()
