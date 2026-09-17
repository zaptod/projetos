# -*- coding: utf-8 -*-
"""`--com-edicao` pede o escopo amplo do YouTube e o grava no json.

17/09/2026: o Adrian decidiu dar a conta neural_fights o escopo de edicao
para tornar publicos, por videos.update, 16 privados que nunca foram ao ar.
Quem publica confere o escopo GRAVADO, entao o pedido ao Google e o json
precisam dizer a mesma coisa — e o reconhecimento tem de ser pelo nome
inteiro: ".../auth/youtube" esta dentro de `youtube.upload`.

Nada abre rede, socket ou navegador.
"""
import io
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from builds import contas
from neural_fights.tools import youtube_oauth as Y

LEITURA = "https://www.googleapis.com/auth/youtube.readonly"
UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"
EDICAO = "https://www.googleapis.com/auth/youtube"


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class ComEdicao(unittest.TestCase):

    def _rodar(self, argv):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        destino = Path(pasta.name) / "youtube_credentials_neural_fights.json"
        abertos = []
        corpo = json.dumps({"refresh_token": "rt"}).encode()
        with mock.patch.object(Y, "porta_ocupada", return_value=""), \
                mock.patch.object(Y, "credenciais_do_app",
                                  return_value=("cid", "sec")), \
                mock.patch.object(Y, "caminho_da_conta",
                                  return_value=destino), \
                mock.patch.object(Y.webbrowser, "open",
                                  side_effect=abertos.append), \
                mock.patch.object(Y, "_receber_codigo", return_value="c"), \
                mock.patch.object(Y.urllib.request, "urlopen",
                                  return_value=_Resposta(corpo)), \
                mock.patch.object(Y, "safe_print"):
            self.assertEqual(0, Y.main(argv))
        pedido = urllib.parse.parse_qs(
            urllib.parse.urlparse(abertos[0]).query)["scope"][0]
        gravado = json.loads(destino.read_text(encoding="utf-8"))["escopo"]
        return pedido, gravado

    def test_soma_a_edicao_sem_tirar_upload_e_analytics(self):
        pedido, gravado = self._rodar(
            ["--conta", "neural_fights", "--com-upload", "--com-analytics",
             "--com-edicao"])
        self.assertEqual(pedido, gravado, "pedido e json tem de bater")
        self.assertEqual({LEITURA, UPLOAD, ANALYTICS, EDICAO},
                         set(gravado.split()))

    def test_sem_a_opcao_nada_muda(self):
        pedido, gravado = self._rodar(
            ["--conta", "neural_fights", "--com-upload", "--com-analytics"])
        self.assertEqual(pedido, gravado)
        self.assertNotIn(EDICAO, gravado.split())
        self.assertEqual(f"{LEITURA} {UPLOAD} {ANALYTICS}", gravado)

    def test_a_constante_e_a_mesma_dos_dois_lados(self):
        # O motor nao importa a fabrica: a string esta repetida de proposito.
        self.assertEqual(Y.ESCOPO_EDICAO, contas.ESCOPO_EDICAO_YOUTUBE)


class ReconheceOEscopo(unittest.TestCase):

    def _com_json(self, escopo):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        arquivo = Path(pasta.name) / "cred.json"
        arquivo.write_text(json.dumps({"escopo": escopo}), encoding="utf-8")
        patcher = mock.patch.object(contas, "credencial_youtube",
                                    return_value=arquivo)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_token_com_edicao_pode_editar(self):
        self._com_json(Y.escopos(True, True, com_edicao=True))
        self.assertIn(EDICAO, contas.escopo_youtube("builds", "neural_fights"))
        self.assertTrue(contas.pode_editar_youtube("builds", "neural_fights"))

    def test_upload_e_leitura_nao_contam_como_edicao(self):
        # ".../auth/youtube" e trecho dos outros dois: por substring, todo
        # token antigo pareceria poder editar.
        self._com_json(Y.escopos(True, True))
        self.assertIn(EDICAO, contas.escopo_youtube("builds", "neural_fights"))
        self.assertFalse(contas.pode_editar_youtube("builds", "neural_fights"))

    def test_sem_arquivo_nao_pode(self):
        with mock.patch.object(contas, "credencial_youtube",
                               return_value=Path("nao_existe.json")):
            self.assertFalse(contas.pode_editar_youtube("builds"))

    def test_upload_continua_reconhecido_com_edicao(self):
        from builds.publicar.youtube import Credenciais
        cred = Credenciais("a", "b", "c", Y.escopos(True, True, True))
        self.assertTrue(cred.tem_upload)


if __name__ == "__main__":
    unittest.main()
