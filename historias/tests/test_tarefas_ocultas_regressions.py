# -*- coding: utf-8 -*-
"""As tarefas do Agendador rodam SEM janela preta (pedido do Adrian,
17/09/2026): a acao e o wscript chamando o .cmd por um .vbs escondido.

Reinstalar (`main.py auto --instalar`) nao pode trazer a janela de volta.
Nada aqui chama o schtasks de verdade.

Rode de dentro de historias/:
    python -m unittest tests.test_tarefas_ocultas_regressions -v
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from builds import tarefas_windows as TW                           # noqa: E402
from contos.pipeline import tarefas                                # noqa: E402


class OVbs(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)

    def test_escreve_quando_falta_e_espera_o_cmd(self):
        caminho = TW.garantir_vbs(self.pasta)
        texto = caminho.read_text(encoding="utf-8")
        self.assertEqual(self.pasta / "oculto.vbs", caminho)
        # 0 = janela escondida; True = espera o .cmd terminar.
        self.assertIn(", 0, True)", texto)
        self.assertIn("WScript.Quit codigo", texto)
        self.assertTrue(texto.isascii(), "o wscript le o .vbs como ANSI")

    def test_nao_sobrescreve_o_que_ja_existe(self):
        caminho = self.pasta / "oculto.vbs"
        caminho.write_bytes(b"' versao ajustada a mao\r\n")
        TW.garantir_vbs(self.pasta)
        self.assertEqual(b"' versao ajustada a mao\r\n", caminho.read_bytes())

    def test_linhas_em_crlf_sem_cr_dobrado(self):
        dados = TW.garantir_vbs(self.pasta).read_bytes()
        self.assertNotIn(b"\r\r", dados)
        self.assertEqual(dados.count(b"\n"), dados.count(b"\r\n"))

    def test_acao_e_o_wscript_com_o_cmd_entre_aspas(self):
        acao = TW.acao_oculta(Path("E:/projetos/historias/auto.cmd"),
                              vbs=Path("C:/rt/oculto.vbs"))
        self.assertTrue(acao.lower().startswith(
            r"c:\windows\system32\wscript.exe //b //nologo"))
        self.assertIn(f'"{Path("C:/rt/oculto.vbs")}"', acao)
        self.assertTrue(acao.endswith(
            f'"{Path("E:/projetos/historias/auto.cmd")}"'))
        self.assertLess(len(acao), 262, "o /TR do schtasks tem limite")


class OInstaladorDasHistorias(unittest.TestCase):

    def test_cria_as_tarefas_com_a_acao_oculta(self):
        chamadas = []

        class Proc:
            returncode, stdout, stderr = 0, "SUCESSO", ""

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        reais = (tarefas._schtasks, TW.endurecer, TW.garantir_vbs)
        tarefas._schtasks = lambda args: chamadas.append(args) or Proc()
        TW.endurecer = lambda nome, **k: {"ok": True, "mensagem": ""}
        TW.garantir_vbs = lambda pasta=None: Path(tmp.name) / "oculto.vbs"

        def restaurar():
            tarefas._schtasks, TW.endurecer, TW.garantir_vbs = reais

        self.addCleanup(restaurar)
        feitas = tarefas.instalar([1, 7], {7: 2})
        self.assertTrue(all(f["ok"] for f in feitas))
        for args in chamadas:
            acao = args[args.index("/TR") + 1]
            self.assertIn("wscript.exe //B //Nologo", acao)
            self.assertTrue(acao.endswith(
                f'"{tarefas.caminho_do_lancador()}"'))


if __name__ == "__main__":
    unittest.main()
