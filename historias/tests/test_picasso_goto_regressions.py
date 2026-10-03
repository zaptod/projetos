# -*- coding: utf-8 -*-
"""O `goto` do PicassoIA que estoura e a passada que morre calada (03/10/2026).

  - historia_00053, 14:19: "Page.goto: Timeout 60000ms exceeded" ao abrir a
    pagina de criacao, e a passada inteira morreu num estouro so. Agora o
    `ensure_logged_in` abre de novo a mesma URL uma vez.
  - historia_00054: `inicio` das imagens as 09:18, refeita da p01_cena_10 as
    09:25, e depois nada no diario, com o processo morto. Agora a passada
    seguinte registra o `erro` da que morreu sem fim.

Nada aqui abre navegador nem escreve no diario de verdade.

Rode de dentro de historias/:
    python -m unittest tests.test_picasso_goto_regressions -v
"""
from __future__ import annotations

import unittest
from unittest import mock

from builds.identity import session                                # noqa: E402
from contos.pipeline import controller                             # noqa: E402


class TimeoutError(Exception):                     # noqa: A001
    """O nome e o que importa: e o do Playwright/patchright."""


class _Seletores:
    PROVEDOR = "picasso"
    URL_CRIACAO = "https://picassoia.com/pt/collection/text-to-image/x"


class _Pagina:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.urls = []

    def goto(self, url, wait_until=None, timeout=None):
        self.urls.append(url)
        resposta = self.respostas.pop(0) if self.respostas else None
        if isinstance(resposta, BaseException):
            raise resposta


class OGoto(unittest.TestCase):

    def setUp(self):
        for alvo, valor in (("esperar_hidratacao", lambda *a, **k: True),
                            ("pausa_humana", lambda *a, **k: None),
                            ("sessao_viva", lambda *a, **k: True)):
            remendo = mock.patch.object(session, alvo, valor)
            remendo.start()
            self.addCleanup(remendo.stop)

    def _abrir(self, pagina):
        session.ensure_logged_in(pagina, {"navigation_timeout": 60},
                                 sel=_Seletores, provedor="picasso")

    def test_estouro_uma_vez_abre_de_novo(self):
        pagina = _Pagina(TimeoutError("Page.goto: Timeout 60000ms exceeded."))
        self._abrir(pagina)
        self.assertEqual([_Seletores.URL_CRIACAO] * 2, pagina.urls)

    def test_estouro_duas_vezes_desiste(self):
        pagina = _Pagina(TimeoutError("1"), TimeoutError("2"))
        with self.assertRaises(TimeoutError):
            self._abrir(pagina)
        self.assertEqual(2, len(pagina.urls))

    def test_outra_falha_nao_repete(self):
        pagina = _Pagina(RuntimeError("net::ERR_NAME_NOT_RESOLVED"))
        with self.assertRaises(RuntimeError):
            self._abrir(pagina)
        self.assertEqual(1, len(pagina.urls))

    def test_sem_estouro_abre_uma_vez(self):
        pagina = _Pagina()
        self._abrir(pagina)
        self.assertEqual(1, len(pagina.urls))


def _ev(status, ref="historia_00054", etapa="imagens", pid=111,
        ts="2026-10-03T12:18:00+00:00", canal="historias"):
    return {"ts": ts, "pid": pid, "fabrica": "picasso", "canal": canal,
            "status": status, "etapa": etapa, "ref": ref, "detalhe": ""}


class APassadaMorta(unittest.TestCase):

    def setUp(self):
        self.registros = []
        self.eventos = []          # do mais velho para o mais novo
        self.vivos = set()
        at = controller._rb_atividade
        remendos = (
            mock.patch.object(at, "recentes",
                              lambda n=60, fabrica=None:
                              list(reversed(self.eventos))),
            mock.patch.object(at, "_vivo", lambda pid: pid in self.vivos),
            mock.patch.object(at, "registrar",
                              lambda *a, **k: self.registros.append((a, k))),
            mock.patch.object(controller.R, "carregar", lambda hid: {}),
            mock.patch.object(controller.fila, "pendentes",
                              lambda hid, rot, parte: [1] * 74),
        )
        for remendo in remendos:
            remendo.start()
            self.addCleanup(remendo.stop)

    def _apurar(self):
        return controller.apurar_passadas_mortas(log=lambda *_a: None)

    def test_inicio_sem_fim_de_processo_morto_vira_erro(self):
        self.eventos = [_ev("inicio"),
                        _ev("log", etapa="imagens.refeita",
                            ref="historia_00054:p01_cena_10")]
        mortas = self._apurar()
        self.assertEqual(1, len(mortas))
        (args, kw), = self.registros
        self.assertEqual(("picasso", "erro"), args[:2])
        self.assertEqual("imagens.morreu_calada", kw["etapa"])
        self.assertEqual("historia_00054", kw["ref"])
        self.assertIn("pid 111", args[2])
        self.assertIn("74 cena(s) pendente(s)", args[2])

    def test_ja_apurada_nao_repete(self):
        self.eventos = [_ev("inicio"),
                        _ev("erro", etapa="imagens.morreu_calada", pid=222)]
        self.assertEqual([], self._apurar())
        self.assertEqual([], self.registros)

    def test_passada_que_terminou_nao_e_morta(self):
        for fim in ("ok", "erro"):
            self.registros.clear()
            self.eventos = [_ev("inicio"), _ev(fim)]
            self.assertEqual([], self._apurar())
            self.assertEqual([], self.registros)

    def test_processo_vivo_nao_e_morte(self):
        self.vivos = {111}
        self.eventos = [_ev("inicio")]
        self.assertEqual([], self._apurar())

    def test_builds_nao_entra(self):
        self.eventos = [_ev("inicio", canal="builds")]
        self.assertEqual([], self._apurar())

    def test_interrupcao_tambem_vai_ao_diario(self):
        from contos.imagens import worker

        def interrompe(*_a, **_k):
            raise KeyboardInterrupt

        with mock.patch.object(worker, "gerar", interrompe):
            with self.assertRaises(KeyboardInterrupt):
                controller.Pipeline.imagens(
                    controller.Pipeline.__new__(controller.Pipeline),
                    "historia_00054", log=lambda *_a: None)
        status = [a[1] for a, _k in self.registros]
        self.assertEqual(["inicio", "erro"], status)
        self.assertEqual("KeyboardInterrupt", self.registros[-1][0][2])


if __name__ == "__main__":
    unittest.main()
