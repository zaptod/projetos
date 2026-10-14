# -*- coding: utf-8 -*-
"""SCR-11 (14/10/2026): os geradores gravavam CR CR LF nos `.cmd`.

`write_text` com o texto ja em `\\r\\n` passa pelo modo texto do Windows, que
troca cada `\\n` por `\\r\\n` de novo. Medido com `cat -A`: `^M^M$` em
`postar.cmd`, `bot.cmd`, `historias/auto.cmd` e `coordenador.cmd`. (Os
testes do `postar.cmd` e do `bot.cmd` moram com os instaladores deles.)
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.pipeline import tarefas


class LancadorDasHistoriasTests(unittest.TestCase):
    def test_auto_cmd_sem_cr_cr_lf(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(tarefas, "RAIZ", Path(tmp)):
            texto = tarefas.escrever_lancador("C:/py/python.exe").read_bytes()
        self.assertNotIn(b"\r\r\n", texto)
        self.assertIn(b"main.py auto --saida", texto)
        self.assertTrue(texto.endswith(b"> NUL 2>&1\r\n"))


class LancadorDoCoordenadorTests(unittest.TestCase):
    def test_coordenador_cmd_sem_cr_cr_lf(self):
        import coordenador.__main__ as cli
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(cli, "CMD", Path(tmp) / "coordenador.cmd"), \
                mock.patch.dict("os.environ", {"LOCALAPPDATA": tmp}), \
                mock.patch.object(cli, "xml_tarefa", return_value="<Task/>"):
            cli.instalar(rodar=lambda *a, **k: None)
            texto = (Path(tmp) / "coordenador.cmd").read_bytes()
        self.assertNotIn(b"\r\r\n", texto)
        self.assertIn(b"-m coordenador rodar\r\n", texto)


if __name__ == "__main__":
    unittest.main()
