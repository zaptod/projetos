# -*- coding: utf-8 -*-
"""Parte com imagem faltando nao renderiza na pasta de verdade.

17/09/2026: o 09003 p1 renderizou com 11 de 14 imagens (a aba do navegador
fechou no meio da geracao). A agenda ja pulava parte assim; `tudo()`,
`main.py video` e o botao "So video" do painel (que chama `main.py video`)
nao pulavam.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.pipeline import controller

ROTEIRO = {"partes": [{"n": 1}, {"n": 2}, {"n": 3}]}


def _resumo(faltam: dict):
    return lambda _hid, _rot=None: [
        {"parte": n, "faltam": faltam.get(n, 0)} for n in (1, 2, 3)]


class TravaDoRender(unittest.TestCase):

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.outputs = Path(pasta.name)
        for alvo, valor in (("OUTPUTS", self.outputs),):
            patcher = mock.patch.object(controller, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(controller.R, "carregar",
                                    return_value=ROTEIRO)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _faltam(self, faltam):
        return mock.patch.object(controller.fila, "resumo_por_parte",
                                 side_effect=_resumo(faltam))

    def test_parte_pedida_com_imagem_faltando_e_recusada_com_o_motivo(self):
        with self._faltam({1: 3}):
            with self.assertRaises(controller.ImagensFaltando) as ctx:
                controller.Pipeline().render("historia_teste_sem_img",
                                             parte=1, log=lambda *_: None)
        self.assertIn("parte 1", str(ctx.exception))
        self.assertIn("3 imagem(ns) faltando", str(ctx.exception))
        # Recusou antes de tocar a pasta da historia.
        self.assertFalse((self.outputs / "historia_teste_sem_img").exists())

    def test_sem_numero_renderiza_so_as_completas(self):
        linhas = []
        with self._faltam({2: 1}):
            prontas = controller.Pipeline._partes_com_imagens(
                "h", ROTEIRO, [1, 2, 3], log=linhas.append)
        self.assertEqual([1, 3], prontas)
        self.assertIn("p2 (1)", " ".join(linhas))

    def test_nenhuma_completa_levanta(self):
        with self._faltam({1: 1, 2: 1, 3: 1}):
            with self.assertRaises(controller.ImagensFaltando):
                controller.Pipeline._partes_com_imagens(
                    "h", ROTEIRO, [1, 2, 3], log=lambda *_: None)

    def test_parte_completa_passa(self):
        with self._faltam({2: 4}):
            self.assertEqual([1], controller.Pipeline._partes_com_imagens(
                "h", ROTEIRO, [1], pedida=1, log=lambda *_: None))

    def test_prova_e_forcar_nao_passam_pela_trava(self):
        fonte = inspect.getsource(controller.Pipeline._render)
        self.assertIn("if not saida and not forcar:", fonte)
        self.assertLess(fonte.index("_partes_com_imagens("),
                        fonte.index("pasta.mkdir("))

    def test_tudo_nao_quebra_e_diz_o_motivo(self):
        linhas = []
        pipe = controller.Pipeline()
        with mock.patch.object(controller.fila, "resumo",
                               return_value={"faltam": 0}), \
                mock.patch.object(pipe, "render",
                                  side_effect=controller.ImagensFaltando("x")):
            saida = pipe.tudo("h", log=linhas.append)
        self.assertEqual([], saida["video"]["videos"])
        self.assertEqual("x", saida["video"]["erro"])
        self.assertIn("nao renderizei", " ".join(linhas))


class LinhaDeComando(unittest.TestCase):

    def test_video_devolve_2_com_o_motivo(self):
        caminho = Path(controller.__file__).resolve().parents[2] / "main.py"
        spec = importlib.util.spec_from_file_location("_main_historias",
                                                      caminho)
        main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main)
        pipe = mock.Mock()
        pipe.render.side_effect = controller.ImagensFaltando("p1: faltam")
        args = argparse.Namespace(historia_id="h", preview=False, parte=1,
                                  prova=None, velocidade=None, layout=None,
                                  forcar=False)
        with mock.patch("builtins.print") as impresso:
            self.assertEqual(2, main.cmd_video(args, pipe))
        self.assertIn("p1: faltam", str(impresso.call_args))
        self.assertIs(False, pipe.render.call_args.kwargs["forcar"])


if __name__ == "__main__":
    unittest.main()
