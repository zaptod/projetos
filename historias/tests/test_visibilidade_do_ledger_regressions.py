# -*- coding: utf-8 -*-
"""SCR-P7: o ledger das historias gravava `public` fosse qual fosse o config.

Medido em 14/10/2026 no HEAD: `_visibilidade_das_historias()` lia
`visibilidade` na RAIZ de `historias/config/publicacao.json`, mas a chave
mora em `youtube.visibilidade`. Com o config dublado em `private`, devolvia
`public`. Hoje o config diz `public` e os dois batem por coincidencia.

Decisao `publicacao/visibilidade-no-ledger` (14/10): o ledger grava a que o
publicador DE FATO usou. O `youtube_web` escreve `visibilidade` no laudo
quando clica a opcao (`nao_escolhida` quando ela nao estava na tela,
`agendado` no agendamento); o pedido fica em `visibilidade_pedida`.

Caso ZERO: laudo vazio (caminho da API, que nao le a tela) cai na pedida.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_visibilidade",
                                                  POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _Parte:
    id = "historia_00099:celular:p02"
    fonte_id = "historia_00099"
    titulo = "Teste (Parte 2)"
    parte, partes = 2, 6


class PedidaDoConfigTests(unittest.TestCase):
    def test_chave_mora_em_youtube_visibilidade(self):
        m = _postar()
        with mock.patch("contos.publicar.catalogo.carregar_config",
                        return_value={"youtube": {"visibilidade": "private"}}):
            self.assertEqual("private", m._visibilidade_das_historias())

    def test_sem_config_cai_em_public(self):
        m = _postar()
        with mock.patch("contos.publicar.catalogo.carregar_config",
                        return_value={}):
            self.assertEqual("public", m._visibilidade_das_historias())


class UsadaDeFatoTests(unittest.TestCase):
    def test_regra_pura(self):
        from builds.publicar.metricas import visibilidade_usada
        self.assertEqual("unlisted", visibilidade_usada(
            [{"visibilidade": "unlisted"}], "public"))
        self.assertEqual("public", visibilidade_usada([], "public"),
                         "caso zero: sem laudo, a pedida")
        self.assertEqual("public", visibilidade_usada(
            [{"visibilidade": ""}], "public"), "laudo sem a etapa")
        self.assertEqual("mista", visibilidade_usada(
            [{"visibilidade": "public"}, {"visibilidade": "private"}],
            "public"))
        self.assertEqual("nao_escolhida", visibilidade_usada(
            {"visibilidade": "nao_escolhida"}, "public"))

    def test_o_registro_grava_a_do_laudo(self):
        """O laudo diz `private` e o pedido era `public`: o ledger diz `private`."""
        m = _postar()
        m._linha = lambda *_a, **_k: None
        m._cabe_antes_do_proximo = lambda *_a, **_k: True
        m._sem_a_conferir = lambda alvos, canal: list(alvos)
        m._fontes_cheias_hoje = lambda *_a, **_k: set()

        def subir(alvo, visibilidade, provas):
            provas.append({"estado": "publicado", "youtube_id": "abc",
                           "visibilidade": "private",
                           "visibilidade_pedida": visibilidade})
            return "https://youtu.be/abc"
        m._subir_parte_no_youtube = subir
        registros = []
        from contos.publicar import serie
        with mock.patch.object(serie, "ja_publicado", return_value=False), \
                mock.patch.object(serie, "publicados", return_value=[]), \
                mock.patch.object(serie, "registrar",
                                  side_effect=lambda *a: registros.append(a)):
            m._alcance_do_youtube({}, _Parte(), "public")
        self.assertEqual(1, len(registros))
        self.assertEqual("private", registros[0][4]["visibilidade"])


class LaudoDoStudioTests(unittest.TestCase):
    def test_laudo_nasce_com_a_pedida_e_sem_a_aplicada(self):
        """Falha antes da etapa de visibilidade: nada foi aplicado."""
        import tempfile

        from builds.publicar import youtube_web
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "p.mp4"
            arquivo.write_bytes(b"x")
            video = type("V", (), {"id": "x", "caminho": str(arquivo),
                                   "titulo": "t"})()
            laudo: dict = {}
            with mock.patch.object(youtube_web, "_conta_ativa",
                                   return_value="historias"), \
                    mock.patch.object(youtube_web.atividade, "fabrica",
                                      side_effect=RuntimeError("parou")):
                with self.assertRaises(RuntimeError):
                    youtube_web.publicar(
                        video, config={"youtube": {"visibilidade": "unlisted"}},
                        canal="historias", postar=True, prova=laudo)
        self.assertEqual("unlisted", laudo["visibilidade_pedida"])
        self.assertEqual("", laudo["visibilidade"])


if __name__ == "__main__":
    unittest.main()
