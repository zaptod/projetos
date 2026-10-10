# -*- coding: utf-8 -*-
"""A PAUSA dos canais de historias (10/10/2026).

Pedido do Adrian: "quero que voce de uma parada nos canais de historias".
Nao existia chave para isso: a postagem so sabia rodar os dois canais.
Agora `pausa_historias.json` no runtime para YouTube e TikTok das historias:
a rodada pula o canal com uma linha (sem "falhou" no Telegram a cada
horario), a recuperacao do TikTok tambem, e `catalogo.publicar_*` recusa
por qualquer outro caminho. Builds seguem iguais.
"""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.publicar import catalogo

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_pausa", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class PausaTests(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        trocar = mock.patch.dict(os.environ,
                                 {"NEURAL_FIGHTS_RUNTIME_DIR": str(self.pasta)})
        trocar.start()
        self.addCleanup(trocar.stop)

    def _pausar(self, **dados):
        (self.pasta / "pausa_historias.json").write_text(
            json.dumps({"pausada": True, **dados}), encoding="utf-8")

    def test_sem_arquivo_publica(self):
        self.assertEqual("", catalogo.pausada())

    def test_false_publica(self):
        self._pausar(pausada=False)
        self.assertEqual("", catalogo.pausada())

    def test_pausada_diz_o_motivo_e_desde_quando(self):
        self._pausar(motivo="pausada pelo Adrian", desde="2026-10-10T01:30:00")
        self.assertEqual("pausada pelo Adrian (desde 2026-10-10 01:30)",
                         catalogo.pausada())

    def test_os_dois_destinos_recusam_antes_de_subir(self):
        self._pausar()
        bomba = mock.Mock(side_effect=AssertionError("subiu com a pausa"))
        with mock.patch.object(catalogo._rb_publicar_youtube,
                               "publicar_como_configurado", bomba), \
             mock.patch.object(catalogo._rb_publicar_tiktok, "publicar", bomba):
            with self.assertRaises(catalogo.PublicacaoPausada):
                catalogo.publicar_youtube(mock.Mock())
            with self.assertRaises(catalogo.PublicacaoPausada):
                catalogo.publicar_tiktok(mock.Mock(), postar=True)
        bomba.assert_not_called()

    def test_a_rodada_pula_historias_e_publica_builds(self):
        self._pausar()
        m = _postar()
        linhas, avisos, recuperados = [], [], []
        m._linha = lambda *a, **_k: linhas.append(" ".join(map(str, a)))
        m.esperar_a_rede = lambda **k: True
        m.avisar = avisos.append
        m.avisar_lote_nao_fechou = lambda *a, **k: None
        m.estoque_do_lote = lambda *a, **k: {}
        m.linhas_do_estoque = lambda lote: []
        m.frescor_do_estoque = lambda *a, **k: {}
        m.retidos_por_canal = lambda: {}
        m.consertadas_por_canal = lambda: {}
        m.reserva_do_tiktok = lambda *a, **k: []
        m.recuperar_no_tiktok = lambda **k: recuperados.append(k["canal"]) or {"fila": 0}
        m.recuperar_no_youtube = lambda **k: {"fila": 0}
        m.publicar_da_reserva = lambda **k: {}
        m.postar_historia = mock.Mock(side_effect=AssertionError("historias rodou"))
        m.postar_build = lambda **k: {"canal": "builds", "feito": False,
                                      "veria": "generation_1", "motivo": "so vendo"}
        self.assertEqual(0, m.main(["--ver"]))
        m.postar_historia.assert_not_called()
        self.assertEqual(["builds"], recuperados)
        self.assertTrue(any("historias: pausada pelo Adrian" in l for l in linhas))


if __name__ == "__main__":
    unittest.main()
