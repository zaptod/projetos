# -*- coding: utf-8 -*-
"""Duas perguntas que o projeto nao sabia responder, e agora sabe.

Diagnostico de 09/09/2026, respondendo "voce esta postando nos horarios
combinados? publicos?".

PERGUNTA 1 — A TAREFA VAI MESMO DISPARAR?

As dez tarefas do projeto estavam com os PADROES do Windows, e o `schtasks
/Create` nao expoe nenhum dos tres:

    DisallowStartIfOnBatteries=True   na bateria a tarefa RECUSA iniciar. E o
                                      `0x800710E0` que aparecia em TODAS elas.
    StopIfGoingOnBatteries=True       cair para bateria no meio MATA a tarefa.
    StartWhenAvailable=False          horario perdido NUNCA e recuperado.

O pedido era "pelo menos um video novo por dia". Com o terceiro desligado, um
cochilo da maquina as 17:07 custa o dia inteiro, em silencio.

PERGUNTA 2 — O QUE FOI PUBLICADO, E COMO?

O `publicados.jsonl` e a unica resposta que existe, e ele estava com **322 de
358 linhas de lixo**: `tests/test_modo_navegador_regressions.py` dubla
`youtube.publicar` mas nao o registro, entao toda rodada da suite gravava ~7
publicacoes falsas em producao (`video_id: null`, `url: https://youtu.be/ok`).

E as 36 linhas reais tinham dois defeitos proprios: cada publicacao gravada
DUAS vezes (o `ferramentas/postar.py` chamava `registrar_publicado` depois de
`publicar_como_configurado`, que ja registra), a segunda sem `visibilidade`; e
o lado das historias gravava `visibilidade: null` em toda linha.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from builds import tarefas_windows
from builds.publicar import metricas

RAIZ = Path(__file__).resolve().parents[2]


class Video:
    """O que os caminhos de publicacao de verdade passam: item de catalogo."""
    id = "generation_00001:build:celular"
    fonte_id = "generation_00001"
    origem = "build"
    perfil = "celular"
    variante = "A"
    titulo = "um titulo"


class LedgerRecusaLixoTests(unittest.TestCase):
    """Publicacao sem video nao e publicacao."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._antes = metricas.REGISTRO
        metricas.REGISTRO = Path(self._tmp.name) / "publicados.jsonl"
        self.addCleanup(lambda: setattr(metricas, "REGISTRO", self._antes))

    def _linhas(self) -> list:
        if not metricas.REGISTRO.is_file():
            return []
        return [json.loads(L) for L in
                metricas.REGISTRO.read_text(encoding="utf-8").splitlines() if L]

    def test_video_de_verdade_entra(self):
        metricas.registrar_publicacao(Video(), "https://youtu.be/abc123")
        self.assertEqual(1, len(self._linhas()))

    def test_caminho_solto_NAO_entra(self):
        """Era este o caso: o dublê passava "video.mp4" e virava linha."""
        with self.assertRaises(ValueError):
            metricas.registrar_publicacao("video.mp4", "https://youtu.be/ok")
        self.assertEqual([], self._linhas())

    def test_a_porta_unica_nao_derruba_a_publicacao_por_causa_do_registro(self):
        """Registro recusado nao pode virar upload perdido."""
        self.assertIsNone(metricas.registrar_publicado(
            "video.mp4", "https://youtu.be/ok", canal="builds"))

    def test_o_arquivo_de_producao_nao_tem_linha_sem_video(self):
        alvo = RAIZ / "random_builds" / "outputs" / "_publicar" / "publicados.jsonl"
        if not alvo.is_file():
            self.skipTest("sem ledger neste ambiente")
        sujas = [L for L in alvo.read_text(encoding="utf-8").splitlines()
                 if L.strip() and not json.loads(L).get("video_id")]
        self.assertEqual([], sujas,
                         "voltou a entrar linha de teste no ledger real")


class RegistroUnicoTests(unittest.TestCase):
    def test_postar_build_NAO_registra_por_fora(self):
        """`publicar_como_configurado` ja registra: chamar de novo duplica."""
        fonte = (RAIZ / "ferramentas" / "postar.py").read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def postar_build("):]
        trecho = trecho[:trecho.index("\ndef ")]
        # so CODIGO: o comentario que explica o defeito cita o nome de
        # proposito, e ele nao pode disparar o alarme.
        codigo = "\n".join(linha for linha in trecho.splitlines()
                           if not linha.lstrip().startswith("#"))
        self.assertNotIn("registrar_publicado(", codigo)

    def test_postar_historia_grava_a_visibilidade(self):
        """"os videos estao publicos?" tem que ter resposta no ledger."""
        fonte = (RAIZ / "ferramentas" / "postar.py").read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def postar_historia("):]
        trecho = trecho[:trecho.index("\ndef _visibilidade_das_historias")]
        self.assertIn('"visibilidade": visibilidade', trecho)
        self.assertNotIn("publicar_youtube(alvo, None)", trecho)


class TarefaConfiavelTests(unittest.TestCase):
    def test_o_ajustador_pede_os_tres(self):
        script = tarefas_windows._SCRIPT
        for opcao in ("-AllowStartIfOnBatteries",
                      "-DontStopIfGoingOnBatteries",
                      "-StartWhenAvailable"):
            self.assertIn(opcao, script)

    def test_ele_preserva_o_que_o_create_ja_tinha_posto(self):
        """Endurecer nao pode afrouxar o limite de tempo nem a instancia unica."""
        script = tarefas_windows._SCRIPT
        self.assertIn("ExecutionTimeLimit", script)
        self.assertIn("MultipleInstances", script)

    def test_o_nome_vai_EMBUTIDO_e_com_escape(self):
        """`-Command` engole `-args`: `$args[0]` fica vazio e nada acontece."""
        self.assertIn("@NOME@", tarefas_windows._SCRIPT)
        self.assertEqual("'a''b'", tarefas_windows._aspas("a'b"))

    def test_endurecer_nunca_levanta(self):
        """Tarefa criada e melhor que nenhuma: falhar aqui nao desfaz o Create."""
        ficha = tarefas_windows.endurecer("NaoExisteEssaTarefa_zzz")
        self.assertFalse(ficha["ok"])
        self.assertTrue(ficha["mensagem"])

    def test_conferir_devolve_vazio_para_tarefa_que_nao_existe(self):
        self.assertEqual({}, tarefas_windows.conferir("NaoExisteEssaTarefa_zzz"))

    def test_os_tres_criadores_de_tarefa_endurecem(self):
        """Um esquecendo seria uma tarefa que some na bateria sem ninguem ver."""
        for caminho in (RAIZ / "historias" / "contos" / "pipeline" / "tarefas.py",
                        RAIZ / "ferramentas" / "postar.py",
                        RAIZ / "remoto" / "tarefa.py"):
            fonte = caminho.read_text(encoding="utf-8")
            self.assertIn("tarefas_windows", fonte, caminho.name)
            self.assertIn("endurecer(", fonte, caminho.name)


if __name__ == "__main__":
    unittest.main()
