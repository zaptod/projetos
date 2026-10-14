# -*- coding: utf-8 -*-
"""IAS-5 (auditoria de 11/10/2026): `gravar_casa` sem nova tentativa e
`rodar()` sem protecao.

No Windows, `os.replace` sobre um `casa.json` aberto por outro processo da
`PermissionError`. Em `_um_turno` isso acontecia DEPOIS de a IA responder e
antes de gravar `respondida`, fora do `try`: a resposta se perdia, a
mensagem virava falhou, e uma segunda falha no `except` derrubava o
`rodar()` (o carteiro morria).

Com dublê: nenhum navegador, conta ou Telegram (`NF_IAS_PASTA`).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from ias import carteiro as carteiro_mod, correio, imagem


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._antes = os.environ.get("NF_IAS_PASTA")
        os.environ["NF_IAS_PASTA"] = str(Path(self._tmp.name) / "ias")

    def tearDown(self):
        if self._antes is None:
            os.environ.pop("NF_IAS_PASTA", None)
        else:
            os.environ["NF_IAS_PASTA"] = self._antes
        self._tmp.cleanup()


@contextmanager
def _trava_livre(nome, esperar=0.0):
    yield True


def _carteiro(fabrica=None, **kw):
    logs = []
    c = carteiro_mod.Carteiro(
        fabrica_de_sessao=fabrica or carteiro_mod.fabrica_duble(
            responder=lambda t: "resposta boa"),
        fabrica_imagem=imagem.fabrica_imagem_duble(), trava=_trava_livre,
        nome_da_trava=lambda ia: f"perfil__{ia}__teste", avisar=lambda _t: "entregue",
        avisar_arquivo=lambda *_a: True, log=logs.append, dormir=lambda s: None,
        ajustes={"janela_conversa_s": 0, "espera_conta_max_s": 100}, **kw)
    c._diario = lambda *a: None
    c.logs = logs
    return c


class GravarComNovaTentativa(_Base):
    def test_permission_error_nas_duas_primeiras_e_grava(self):
        real = os.replace
        chamadas = []

        def trancado(origem, destino):
            chamadas.append(destino)
            if len(chamadas) <= 2:
                raise PermissionError(13, "O arquivo já está sendo usado por outro processo")
            return real(origem, destino)
        with mock.patch.object(correio.os, "replace", trancado), \
                mock.patch.object(correio.time, "sleep", lambda s: None):
            correio.gravar_casa("gemini", {"url": "https://gemini.google.com/app/x",
                                           "mensagens": 3})
        self.assertEqual(len(chamadas), 3)
        self.assertEqual(correio.casa("gemini")["mensagens"], 3)

    def test_trancado_sempre_levanta_depois_das_tentativas(self):
        def sempre(origem, destino):
            raise PermissionError(13, "trancado")
        with mock.patch.object(correio.os, "replace", sempre), \
                mock.patch.object(correio.time, "sleep", lambda s: None):
            with self.assertRaises(PermissionError):
                correio.gravar_casa("gemini", {"mensagens": 1})

    def test_estado_e_resumo_tambem_tentam_de_novo(self):
        real = os.replace
        falhas = {"n": 0}

        def uma_vez(origem, destino):
            if falhas["n"] % 2 == 0:
                falhas["n"] += 1
                raise PermissionError(13, "trancado")
            falhas["n"] += 1
            return real(origem, destino)
        with mock.patch.object(correio.os, "replace", uma_vez), \
                mock.patch.object(correio.time, "sleep", lambda s: None):
            correio.gravar_estado_do_carteiro({"situacao": "ocioso"})
            correio.gravar_resumo_da_casa("gemini", "um resumo qualquer")
        self.assertEqual(correio.estado_do_carteiro()["situacao"], "ocioso")
        self.assertIn("um resumo qualquer", correio.resumo_da_casa("gemini"))


class RespostaNaoSePerde(_Base):
    def test_casa_trancada_nao_desfaz_a_resposta(self):
        def trancada(ia, dados):
            raise PermissionError(13, "casa.json trancado")
        c = _carteiro(de_servico=True)
        m = correio.enviar("gemini", "pergunta")
        with mock.patch.object(correio, "gravar_casa", trancada):
            fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "respondida")
        self.assertEqual(fim["resposta"], "resposta boa")
        self.assertEqual(correio.uma("gemini", m["id"])["situacao"], "respondida")
        self.assertTrue(any("casa não foi gravada" in linha for linha in c.logs), c.logs)

    def test_casa_trancada_na_falha_tambem_nao_levanta(self):
        def trancada(ia, dados):
            raise PermissionError(13, "casa.json trancado")
        c = _carteiro(carteiro_mod.fabrica_duble(falhar=RuntimeError("site fora")),
                      de_servico=True)
        m = correio.enviar("gemini", "pergunta")
        with mock.patch.object(correio, "gravar_casa", trancada):
            fim = c.entregar(correio.uma("gemini", m["id"]))
        self.assertEqual(fim["situacao"], "falhou")


class RodarNaoMorre(_Base):
    def test_volta_que_quebra_nao_derruba_o_rodar(self):
        c = _carteiro(de_servico=True)
        voltas = []

        def uma_volta():
            voltas.append(1)
            if len(voltas) == 1:
                raise PermissionError(13, "casa.json trancado")
            return None
        c.uma_volta = uma_volta
        paradas = []

        def parar():
            paradas.append(1)
            return len(voltas) >= 2
        self.assertEqual(c.rodar(parar=parar, intervalo=0), 0)
        self.assertEqual(len(voltas), 2)                  # chegou a 2a volta
        self.assertTrue(any("a volta falhou" in linha for linha in c.logs), c.logs)
        estado = correio.estado_do_carteiro()
        self.assertEqual(estado["situacao"], "ocioso")
        self.assertIn("volta falhou: PermissionError", estado["nota"])


if __name__ == "__main__":
    unittest.main()
