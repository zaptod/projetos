# -*- coding: utf-8 -*-
"""O JS que acha a imagem da resposta, rodando num Chrome DE VERDADE (headless,
pagina sintetica em `set_content`, sem rede e sem conta).

So roda com `NF_TESTE_NAVEGADOR=1` (a suite normal nao abre navegador). A
pagina copia a estrutura MEDIDA em 29/09/2026 (scratchpad/diag_chatgpt_*.py e
diag_gemini_recipiente.py):

- ChatGPT: `section[data-turn=user|assistant]`; a imagem gerada em
  `div#image-<uuid>.group/imagegen-image` com tres <img> do mesmo src (uma
  sob um fundo borrado); e, no MESMO section do assistente, o ANUNCIO com a
  miniatura 512x512 (a "mesa de som" do d228c94f);
- Gemini: `model-response > ... > generated-image > single-image`, com o
  botao "Baixar imagem no tamanho original" no mesmo `single-image`.
"""
from __future__ import annotations

import base64
import os
import unittest

from contos.llm import cliente as llm_cliente                      # noqa: E402
from contos.llm import seletores                                   # noqa: E402

LIGADO = os.environ.get("NF_TESTE_NAVEGADOR") == "1"


def _png(largura, altura, cor):
    from ias.imagem import png_de_teste
    return "data:image/png;base64," + base64.b64encode(
        png_de_teste(largura, altura, cor=cor)).decode("ascii")


ANTIGA = _png(300, 300, (10, 200, 10))
GATO = _png(320, 320, (200, 120, 40))
ANUNCIO = _png(280, 280, (40, 40, 40))

CHATGPT = f"""
<main>
 <section data-testid="conversation-turn-1" data-turn="user">
  <div data-message-author-role="user">desenhe um cachorro</div></section>
 <section data-testid="conversation-turn-2" data-turn="assistant">
  <div id="image-velha" class="group/imagegen-image relative w-full">
   <img alt="Imagem gerada: Cachorro" src="{ANTIGA}"></div></section>
 <section data-testid="conversation-turn-3" data-turn="user">
  <div data-message-author-role="user">Crie uma imagem na proporção 1:1.

Crie um gato para mim</div></section>
 <section data-testid="conversation-turn-4" data-turn="assistant">
  <div id="image-ce7d03b0" class="group/imagegen-image relative w-full">
   <div class="relative z-0"><img class="absolute top-0 z-1"
      alt="Imagem gerada: Retrato Aconchegante de Gato Tigrado" src="{GATO}"></div>
   <div class="relative z-1 w-full"><img src="{GATO}"></div>
   <div class="absolute inset-0 z-0" style="filter: blur(20px)"><img src="{GATO}"></div>
  </div>
  <div class="_50iAZcETyQ"><div class="_K8y_bAKktO"><img src="{ANUNCIO}">
   <span>CAVN AI</span><b>AI Music Videos</b><i>Anúncio</i></div></div>
 </section>
</main>"""

CHATGPT_GERANDO = f"""
<main>
 <section data-turn="user"><div data-message-author-role="user">Crie um gato</div></section>
 <section data-turn="assistant"><span>Criando imagem</span>
  <div id="image-x" class="group/imagegen-image"><div style="filter: blur(8px)">
   <img src="{GATO}"></div></div></section>
</main>"""

GEMINI = f"""
<user-query>Você disse gere um gato</user-query>
<model-response><div class="markdown">
 <generated-image><single-image class="generated-image large">
  <button class="image-button"><img class="image" alt="gato, AI generated" src="{GATO}"></button>
  <button aria-label="Baixar imagem no tamanho original">baixar</button>
 </single-image></generated-image></div></model-response>
<div class="sugestoes"><img src="{ANUNCIO}"></div>"""


@unittest.skipUnless(LIGADO, "abre um Chrome headless: NF_TESTE_NAVEGADOR=1")
class JSNoNavegador(unittest.TestCase):
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

    def _cliente(self, provedor, html):
        self.page.set_content(html)
        self.page.wait_for_function(
            "() => [...document.images].every(i => i.complete && i.naturalWidth > 0)")
        return llm_cliente.ClienteLLM(provedor, None, self.page, log=lambda *_a: None)

    def test_chatgpt_pega_o_gato_e_nao_o_anuncio_nem_a_antiga(self):
        c = self._cliente("chatgpt", CHATGPT)
        achado = c.imagens_da_resposta()
        self.assertTrue(achado["ancorado"])
        self.assertTrue(achado["resposta"])
        self.assertFalse(achado["gerando"])
        self.assertIn("Crie um gato", achado["turno"])
        self.assertEqual([i["src"] for i in achado["imagens"]], [GATO])  # 3 <img>, 1 src
        gato = achado["imagens"][0]
        self.assertFalse(gato["borrada"], "uma das copias e nitida")
        self.assertTrue(gato["alt"].startswith("Imagem gerada"))
        self.assertEqual((gato["w"], gato["h"]), (320, 320))
        self.assertEqual(achado["fora"], 1)                  # o anuncio, ignorado
        prontas = c.imagens_prontas(achado, antes={ANTIGA})
        self.assertEqual([i["src"] for i in prontas], [GATO])
        # a foto de antes do envio ve as tres (a antiga, o gato e o anuncio)
        self.assertEqual(c._foto_das_imagens(), {ANTIGA, GATO, ANUNCIO})

    def test_chatgpt_gerando_nao_vale(self):
        c = self._cliente("chatgpt", CHATGPT_GERANDO)
        achado = c.imagens_da_resposta()
        self.assertTrue(achado["gerando"])
        self.assertTrue(achado["imagens"][0]["borrada"])
        self.assertEqual(c.imagens_prontas(achado), [])

    def test_gemini_pega_a_do_generated_image_e_marca_o_botao(self):
        from ias import imagem
        c = self._cliente("gemini", GEMINI)
        achado = c.imagens_da_resposta()
        self.assertEqual([i["src"] for i in achado["imagens"]], [GATO])
        self.assertEqual(achado["fora"], 1)
        s = seletores.GEMINI
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], GATO,
            s["imagem_baixar"]])
        self.assertEqual(marcado, {"imagem": True, "botao": True})
        self.assertEqual(self.page.locator("[data-nf-baixar='1']").count(), 1)
        # o anuncio nunca e marcado
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], ANUNCIO,
            s["imagem_baixar"]])
        self.assertEqual(marcado, {"imagem": False, "botao": False})

    def test_chatgpt_marca_so_a_imagem(self):
        from ias import imagem
        c = self._cliente("chatgpt", CHATGPT)
        s = c.sel
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], GATO, []])
        self.assertEqual(marcado, {"imagem": True, "botao": False})
        alt = self.page.locator("[data-nf-imagem='1']").get_attribute("alt")
        self.assertTrue(alt.startswith("Imagem gerada"))
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], ANUNCIO, []])
        self.assertFalse(marcado["imagem"])

    def test_sem_turno_do_usuario_caso_zero(self):
        c = self._cliente("chatgpt", "<main><p>nada</p></main>")
        achado = c.imagens_da_resposta()
        self.assertFalse(achado["ancorado"])
        self.assertEqual(achado["imagens"], [])


if __name__ == "__main__":
    unittest.main()
