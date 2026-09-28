# -*- coding: utf-8 -*-
"""O instalador da tarefa que mantem a Vila flutuante no ar.

O que este arquivo trava:

1. SEM CAMINHO DESTA MAQUINA. O .cmd sai do ambiente de quem instala (o
   pythonw ao lado do Python, a raiz dos dados) — nada de `C:\\Python314` ou
   `E:\\projetos` escritos a mao. Apostrofo e `%` no caminho nao quebram.
2. A GUARDA. O .cmd so lanca a Vila se nao houver uma viva, e NA DUVIDA NAO
   ABRE: a consulta de processos que falha sai sem lancar. Testado rodando o
   .cmd de verdade pelo cmd, com o Get-CimInstance e o Start-Process
   trocados por duble (nada e lancado).
3. SEM JANELA PRETA. A tarefa e o `wscript` + `oculto.vbs`; sem eles o
   instalador recusa, em vez de apontar a tarefa direto para o .cmd.
4. A SECO. Sem bandeira, nada e escrito nem criado.

Rode da raiz:  python -m pytest painel/test_tarefa_da_vila.py -q
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from painel.flutuante import tarefa

RAIZ = Path(__file__).resolve().parent.parent
OUTRA_MAQUINA = (Path(r"D:\Ferramentas\Py\pythonw.exe"), Path(r"D:\clone"))


class Lancador(unittest.TestCase):
    def test_caminhos_vem_do_ambiente(self):
        texto = tarefa.texto_do_lancador(*OUTRA_MAQUINA)
        self.assertIn(r"-FilePath 'D:\Ferramentas\Py\pythonw.exe'", texto)
        self.assertIn(r"-WorkingDirectory 'D:\clone'", texto)
        for desta_maquina in ("Python314", r"E:\projetos", "adrian"):
            self.assertNotIn(desta_maquina, texto)

    def test_apostrofo_e_porcento_no_caminho(self):
        texto = tarefa.texto_do_lancador(
            Path(r"C:\O'Neil\100%\pythonw.exe"), Path(r"C:\a%b"))
        self.assertIn(r"'C:\O''Neil\100%%\pythonw.exe'", texto)
        self.assertIn(r"'C:\a%%b'", texto)

    def test_a_guarda_e_a_duvida_estao_no_lancador(self):
        texto = tarefa.texto_do_lancador(*OUTRA_MAQUINA)
        linha = [l for l in texto.splitlines() if l.startswith("powershell")]
        self.assertEqual(len(linha), 1)
        comando = linha[0]
        self.assertIn("'painel.flutuante|vila_flutuante'", comando)
        self.assertIn("if (-not $viva)", comando)
        self.assertIn("-ErrorAction Stop", comando)
        self.assertIn("catch { exit 0 }", comando)
        self.assertIn(f"-OperationTimeoutSec {tarefa.PRAZO_DA_CONSULTA_S}",
                      comando)
        self.assertIn("'--medio'", comando)
        self.assertTrue(texto.endswith("\r\n"))
        self.assertNotIn("\n", texto.replace("\r\n", ""))

    def test_pythonw_ao_lado_do_python(self):
        pasta = Path(tempfile.mkdtemp())
        python = pasta / "python.exe"
        python.write_bytes(b"")
        with self.assertRaises(FileNotFoundError):
            tarefa.pythonw(python)
        (pasta / "pythonw.exe").write_bytes(b"")
        self.assertEqual(tarefa.pythonw(python), pasta / "pythonw.exe")
        self.assertEqual(tarefa.pythonw(pasta / "pythonw.exe"),
                         pasta / "pythonw.exe")

    def test_escrever_e_inteiro_e_sem_sobra(self):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "pythonw.exe").write_bytes(b"")
        destino = tarefa.escrever_lancador(pasta / "pythonw.exe", pasta)
        self.assertEqual(destino, pasta / tarefa.NOME_DO_LANCADOR)
        self.assertIn(b"\r\npowershell ", destino.read_bytes())
        self.assertEqual([p.name for p in pasta.iterdir()
                          if p.name.endswith(".tmp")], [])

    def test_o_gerado_fica_fora_do_git(self):
        ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(tarefa.NOME_DO_LANCADOR, ignorados.splitlines())


@unittest.skipUnless(sys.platform == "win32", "o .cmd e do Windows")
class GuardaDeVerdade(unittest.TestCase):
    """O .cmd gerado, rodado pelo cmd, com dubles no lugar do WMI e do
    Start-Process: prova as aspas (o `|` tem que ficar dentro delas) e a
    logica, sem lancar nada."""

    VIVA = ("function Get-CimInstance { [pscustomobject]@{ CommandLine = "
            "'pythonw.exe -X utf8 -m painel.flutuante --medio ' } }; ")
    MORTA = "function Get-CimInstance { }; "
    # Como o de verdade: erro NAO terminal (so o `-ErrorAction Stop` do .cmd
    # o torna terminal). Com `throw` o teste passaria ate no .cmd antigo, que
    # lancava a Vila quando o WMI falhava.
    WMI_CAIU = ("function Get-CimInstance { [CmdletBinding()] param("
                "[Parameter(Position=0)]$ClassName, $Filter, "
                "$OperationTimeoutSec) Write-Error 'wmi caiu' }; ")
    LANCAR = ("function Start-Process { param($FilePath, $ArgumentList, "
              "$WorkingDirectory) 'LANCOU ' + $FilePath + ' ; ' + "
              "($ArgumentList -join ' ') + ' ; ' + $WorkingDirectory }; ")

    def _rodar(self, duble: str) -> str:
        texto = tarefa.texto_do_lancador(*OUTRA_MAQUINA)
        marca = '-Command "'
        self.assertEqual(texto.count(marca), 1)
        texto = texto.replace(marca, marca + duble + self.LANCAR)
        arquivo = Path(tempfile.mkdtemp()) / "guarda.cmd"
        arquivo.write_bytes(texto.encode("oem"))
        feito = subprocess.run(["cmd", "/c", str(arquivo)],
                               capture_output=True, timeout=120,
                               creationflags=tarefa.NO_WINDOW)
        saida = (feito.stdout or b"").decode("oem", "replace")
        erro = (feito.stderr or b"").decode("oem", "replace")
        self.assertEqual(erro.strip(), "", erro)
        return saida

    def test_com_a_vila_viva_nao_lanca(self):
        self.assertNotIn("LANCOU", self._rodar(self.VIVA))

    def test_sem_vila_lanca_do_jeito_certo(self):
        saida = self._rodar(self.MORTA).strip()
        self.assertEqual(
            saida, r"LANCOU D:\Ferramentas\Py\pythonw.exe ; "
                   r"-X utf8 -m painel.flutuante --medio ; D:\clone")

    def test_na_duvida_nao_abre(self):
        self.assertNotIn("LANCOU", self._rodar(self.WMI_CAIU))


class Instalar(unittest.TestCase):
    def setUp(self):
        self.chamadas = []

        def schtasks(argumentos):
            self.chamadas.append(list(argumentos))
            return subprocess.CompletedProcess(argumentos, 0, "ok", "")

        self.addCleanup(mock.patch.stopall)
        mock.patch.object(tarefa, "_schtasks", schtasks).start()
        mock.patch.object(tarefa, "escrever_lancador",
                          return_value=Path(r"D:\clone\vila_flutuante.cmd")
                          ).start()

    def test_cria_a_tarefa_escondida_de_10_em_10(self):
        acao = (r'C:\Windows\System32\wscript.exe //B //Nologo "D:\rt\oculto.vbs"'
                r' "D:\clone\vila_flutuante.cmd"')
        with mock.patch.object(tarefa, "acao", return_value=acao), \
                mock.patch("builds.tarefas_windows.endurecer",
                           return_value={"ok": True, "mensagem": ""}) as dura:
            ficha = tarefa.instalar()
        self.assertTrue(ficha["ok"], ficha)
        self.assertTrue(ficha["ajustada"])
        dura.assert_called_once_with(tarefa.TAREFA)
        criar = self.chamadas[0]
        self.assertEqual(criar[:3], ["/Create", "/TN", tarefa.TAREFA])
        self.assertEqual(criar[criar.index("/TR") + 1], acao)
        self.assertEqual(criar[criar.index("/SC") + 1], "MINUTE")
        self.assertEqual(criar[criar.index("/MO") + 1], "10")
        self.assertEqual(criar[criar.index("/RL") + 1], "LIMITED")

    def test_sem_oculto_vbs_recusa_em_vez_de_janela_preta(self):
        with mock.patch.object(tarefa, "acao",
                               side_effect=ImportError("sem builds")):
            ficha = tarefa.instalar()
        self.assertFalse(ficha["ok"])
        self.assertIn("nao instalei", ficha["mensagem"])
        self.assertEqual(self.chamadas, [])

    def test_a_seco_nao_escreve_nem_cria(self):
        escrever = tarefa.escrever_lancador
        with mock.patch("builds.tarefas_windows.garantir_vbs",
                        side_effect=AssertionError("escreveu o vbs")), \
                mock.patch("builds.tarefas_windows.endurecer",
                           side_effect=AssertionError("mexeu na tarefa")), \
                mock.patch("builtins.print"):
            self.assertIn(tarefa.main([]), (0, 1))
        escrever.assert_not_called()
        self.assertTrue(all(c[0] == "/Query" for c in self.chamadas),
                        self.chamadas)


if __name__ == "__main__":
    unittest.main()
