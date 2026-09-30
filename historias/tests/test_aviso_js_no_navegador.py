# -*- coding: utf-8 -*-
"""O JS do aviso do site (`ClienteLLM.aviso_do_site`) num Chrome DE VERDADE
(headless, pagina sintetica em `set_content`, sem rede e sem conta).

So roda com `NF_TESTE_NAVEGADOR=1` (a suite normal nao abre navegador). As
bolhas copiam a estrutura MEDIDA do Grok em 29/09/2026 (scratchpad/
diag_grok2.py: `div[data-testid=user-message]`, `div[data-testid=
assistant-message]` com `div.thinking-container` antes da resposta); o card e
o toast sao os da tela de 29/09 17:49 (historias/outputs/_logs/llm_calado/
grok_20260929_174936.png). O DOM do card em si NAO foi medido (ele nao estava
mais na conversa em 30/09): aqui ele mora no turno do assistente, fora do
markdown — o que o log de 29/09 mostra (0 chars lidos pelo seletor de
resposta, com um turno do assistente depois do nosso).
"""
from __future__ import annotations

import os
import unittest

from contos.llm import cliente as llm_cliente                      # noqa: E402

LIGADO = os.environ.get("NF_TESTE_NAVEGADOR") == "1"

USUARIO = ('<div dir="auto" role="article" aria-label="Você" data-testid="user-message" '
           'class="message-bubble relative">{t}</div>')
ASSIST = ('<div dir="auto" role="article" aria-label="Grok" data-testid="assistant-message" '
          'class="message-bubble relative rounded-3xl">'
          '<div class="thinking-container mb-1"><div class="flex flex-col">Trabalhou por 3s'
          '</div></div>{corpo}</div>')
MD = '<div class="response-content-markdown"><p>{t}</p></div>'
CARD = ('<div class="card"><div><svg></svg><span>Alta procura</span></div>'
        '<p>Por favor, tente novamente em breve, ou atualize para um acesso com maior '
        'prioridade</p><button>Aprimorar</button></div>')
ACOES = '<div><button aria-label="Copiar"></button><button aria-label="Regenerar"></button></div>'
TOAST = ('<div role="status"><span>Grok is experiencing issues. We are working on restoring '
         'service as quickly as possible.</span></div>')
LATERAL = '<nav><a href="/c/1">Friendly Portuguese greeting</a><a href="/c/2">Plugins</a></nav>'
COMPOSITOR = ('<div data-testid="chat-input"><div role="textbox" contenteditable="true" '
              'aria-label="Ask Grok anything"></div><button>Fast</button></div>')
LONGA = "Gatos laranja estão em alta procura nas redes: " + "isso vale para fotos. " * 30
GATO = USUARIO.format(t="Um gato laranja dormindo enrolado numa almofada azul.")


def _pagina(*turnos, toast=False, fora=""):
    return ("<html><body>" + (TOAST if toast else "") + LATERAL + "<main>"
            + USUARIO.format(t="Ola")
            + ASSIST.format(corpo=MD.format(t="Olá! Como posso ajudar você hoje?"))
            + "".join(turnos) + fora + "</main>" + COMPOSITOR + "</body></html>")


@unittest.skipUnless(LIGADO, "abre um Chrome headless: NF_TESTE_NAVEGADOR=1")
class AvisoNoNavegador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from patchright.sync_api import sync_playwright
        cls._pw = sync_playwright().start()
        try:
            cls._navegador = cls._pw.chromium.launch(channel="chrome", headless=True)
        except Exception:                                      # noqa: BLE001
            cls._navegador = cls._pw.chromium.launch(headless=True)
        cls.page = cls._navegador.new_page()

    @classmethod
    def tearDownClass(cls):
        cls._navegador.close()
        cls._pw.stop()

    def _aviso(self, html):
        self.page.set_content(html)
        return llm_cliente.ClienteLLM("grok", None, self.page,
                                      log=lambda *_a: None).aviso_do_site()

    def test_card_no_lugar_da_resposta_com_o_toast(self):
        aviso = self._aviso(_pagina(GATO, ASSIST.format(corpo=CARD + ACOES), toast=True))
        self.assertIn("Alta procura", aviso["texto"])
        self.assertIn("maior prioridade", aviso["texto"])
        self.assertNotIn("Trabalhou", aviso["texto"], "o raciocinio sai do turno")
        self.assertTrue(aviso["pagina"])

    def test_card_sem_o_toast(self):
        aviso = self._aviso(_pagina(GATO, ASSIST.format(corpo=CARD + ACOES)))
        self.assertIn("Alta procura", aviso["texto"])
        self.assertFalse(aviso["pagina"])

    def test_resposta_que_cita_alta_procura_nao_e_aviso(self):
        for texto in (LONGA, "Sim, está em alta procura."):
            aviso = self._aviso(_pagina(GATO, ASSIST.format(corpo=MD.format(t=texto))))
            self.assertEqual("", aviso["texto"], texto[:40])

    def test_card_do_turno_anterior_nao_vale(self):
        aviso = self._aviso(_pagina(
            GATO, ASSIST.format(corpo=CARD), USUARIO.format(t="de novo"),
            ASSIST.format(corpo=MD.format(t="Aqui está o seu gato laranja."))))
        self.assertEqual("", aviso["texto"])

    def test_so_o_toast_sem_resposta(self):
        aviso = self._aviso(_pagina(GATO, toast=True))
        self.assertEqual("", aviso["texto"])
        self.assertTrue(aviso["pagina"])

    def test_card_fora_do_turno_do_assistente_nao_e_lido(self):
        # limite conhecido: se o card morar FORA do assistant-message, nao e
        # lido (a espera volta a gastar o prazo, como antes)
        self.assertEqual("", self._aviso(_pagina(GATO, fora=CARD))["texto"])


if __name__ == "__main__":
    unittest.main()
