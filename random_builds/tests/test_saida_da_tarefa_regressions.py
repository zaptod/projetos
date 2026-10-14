# -*- coding: utf-8 -*-
"""SCR-12 (14/10/2026): `--saida` sem valor ou com a pasta do log apagada.

Nos cinco programas das tarefas (`historias/main.py`, `random_builds/main.py`,
`postar.py`, `remoto/__main__.py`, `remoto/api_http.py`): `--saida` no fim
devolvia `(argv[:i], None)` e a saida ia ao console do Agendador (onde o
`print` trava); com `outputs/_logs` apagada, o `open` levantava antes do
`main()` e a rodada morria sem rastro. Agora a regra mora num lugar so.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from builds import atividade, saida_da_tarefa

RAIZ = Path(__file__).resolve().parents[2]


class SaidaDaTarefaTests(unittest.TestCase):
    def test_pasta_do_log_apagada_e_criada(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "nao_existe" / "x.txt"
            argv, arquivo = saida_da_tarefa.abrir(
                ["main.py", "auto", "--saida", str(alvo)])
            try:
                self.assertEqual(["main.py", "auto"], argv)
                arquivo.write("linha\n")
            finally:
                arquivo.close()
            self.assertTrue(alvo.is_file())

    def test_saida_sem_valor_sai_2_e_avisa(self):
        avisos = []
        with mock.patch.object(atividade, "registrar",
                               side_effect=lambda *a, **k: avisos.append(a)):
            for argv in (["main.py", "auto", "--saida"],
                         ["main.py", "--saida", "--ver"]):
                with self.assertRaises(SystemExit) as caso:
                    saida_da_tarefa.abrir(argv, "historias")
                self.assertEqual(2, caso.exception.code)
        self.assertEqual(2, len(avisos))
        self.assertEqual(("historias", "erro"), avisos[0][:2])

    def test_caso_zero_sem_a_opcao(self):
        self.assertEqual((["main.py"], None), saida_da_tarefa.abrir(["main.py"]))

    def test_os_cinco_programas_usam_a_regra(self):
        for caminho in ("ferramentas/postar.py", "remoto/__main__.py",
                        "remoto/api_http.py", "historias/main.py",
                        "random_builds/main.py"):
            fonte = (RAIZ / caminho).read_text(encoding="utf-8")
            self.assertIn("saida_da_tarefa.abrir(", fonte, caminho)


if __name__ == "__main__":
    unittest.main()
