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

# O CARTAO NOVO (medido em 02/10/2026 00:0x, conta Plus; o 869758fa ficou 420 s
# em "0 chars" com a imagem na tela). Sem `data-message-author-role` nem
# `section[data-turn]`: o usuario e `div[data-user-message-bubble=true]`, o
# turno do assistente e o div com o `h4[data-conversation-role=assistant]`
# como filho, e a imagem e um item da `generated-image-gallery` com os botoes
# "Editar a imagem gerada 1" e "Compartilhar imagem gerada 1" no mesmo item.
NOVA_ANTIGA = _png(300, 300, (10, 10, 200))
NOVA = _png(330, 330, (255, 0, 255))


def _novo_par(pedido, src, *, pronta=True, anuncio=False):
    botoes = ("""<div><div><div><button type="button" aria-label="Editar a imagem gerada 1">Editar</button></div>
      <div><span data-state="closed"><button type="button" aria-label="Compartilhar imagem gerada 1">
      <svg><path d="M16.6663 10.1681C17.0335"></path></svg></button></span></div></div></div>"""
              if pronta else "")
    extra = (f'<div class="ad"><img src="{ANUNCIO}"><i>Anúncio</i></div>' if anuncio else "")
    return f"""
 <div data-turn-key="u-{len(pedido)}">
  <div class="block-BQZwFn"><h4 class="sr-only">Você disse:</h4>
   <div data-chatgpt-search-unit-key="fallback-turn-0:0:user">
    <div data-user-message-bubble="true"><div dir="auto">{pedido}</div></div></div></div>
  <div class="block-BQZwFn"><span hidden data-chatgpt-agent-turn-start></span>
   <h4 data-conversation-role="assistant" tabindex="-1" class="sr-only">ChatGPT disse:</h4>
   <div data-chatgpt-search-message-ids="a1"><div>
    <div data-testid="generated-image-gallery"><div>
     <div data-image-transparency-backdrop-scope="" class="group/generated-image-preview">
      <button type="button" data-testid="generated-image-preview" aria-label="Imagem 1 gerada">
       <img width="1254" height="1254" alt="Imagem 1 gerada" src="{src}"></button>
      <div></div>{botoes}
     </div></div></div>{extra}</div></div></div>
 </div>"""


_PEDIDO_NOVO = ("Crie uma imagem na proporção 1:1. Responda só com a imagem, sem texto."
                "\n\nCreate ONE square style reference sheet")
CHATGPT_NOVO = f"""<main>
{_novo_par("desenhe um cachorro", NOVA_ANTIGA)}
{_novo_par(_PEDIDO_NOVO, NOVA, anuncio=True)}
</main>"""

CHATGPT_NOVO_GERANDO = f"""<main>
{_novo_par("desenhe um cachorro", NOVA_ANTIGA)}
{_novo_par("Crie uma imagem na proporção 1:1.", NOVA, pronta=False)}
</main>"""

GEMINI = f"""
<user-query>Você disse gere um gato</user-query>
<model-response><div class="markdown">
 <generated-image><single-image class="generated-image large">
  <button class="image-button"><img class="image" alt="gato, AI generated" src="{GATO}"></button>
  <button aria-label="Baixar imagem no tamanho original">baixar</button>
 </single-image></generated-image></div></model-response>
<div class="sugestoes"><img src="{ANUNCIO}"></div>"""


# GROK (medido em 29/09/2026 17:5x, scratchpad/diag_grok2.py, na conversa
# "Circulo de cor vermelha" da conta): a imagem gerada em dois <img> com o
# mesmo src assets.grok.com/users/<conta>/generated/<uuid>/image.jpg dentro de
# `div.group/image`; o anexo do usuario em `/users/<conta>/<uuid>/preview-image`;
# a foto do perfil na barra lateral. Aqui ainda: uma imagem da WEB dentro do
# balao da resposta (busca/previa de link), que o balao inteiro aceitaria.
GROK_CONTA = "https://assets.grok.com/users/203e1714"
GROK_GERADA = f"{GROK_CONTA}/generated/d4c4bfa4/image.jpg"
GROK_ANTIGA = f"{GROK_CONTA}/generated/0a0a0a0a/image.jpg"
GROK_ANEXO = f"{GROK_CONTA}/c46dc88b/preview-image"
GROK_PFP = f"{GROK_CONTA}/fQY8-profile-picture.webp"
GROK_WEB = "https://imagens.exemplo.com/gato-da-web.jpg"


def _grok_bolha_gerada(src):
    return f"""
  <div data-testid="assistant-message" class="message-bubble relative rounded-3xl">
   <div class="thinking-container">Trabalhou por 11s</div>
   <div class="streamdown-chat-md"><div class="not-prose flex flex-col gap-3">
    <div class="flex flex-col sm:flex-row gap-3"><div data-testid="Vyie8" class="min-w-0 w-full">
     <div class="relative group/image sm:w-fit sm:mx-auto">
      <div class="relative rounded-2xl overflow-hidden p-0">
       <div class="absolute inset-0"><img class="absolute object-cover w-full m-0" src="{src}"></div>
       <img class="object-cover relative z-[200] block" alt="Imagem gerada" src="{src}">
      </div></div></div></div></div></div></div>"""


GROK = f"""
<nav><button><span><img alt="pfp" src="{GROK_PFP}"></span></button></nav>
<main>
 <div data-testid="user-message" class="message-bubble">
  <div id="response-1"><button aria-label="Abrir anexo"><img src="{GROK_ANEXO}"></button></div>
  desenhe um cachorro</div>
 {_grok_bolha_gerada(GROK_ANTIGA)}
 <div data-testid="user-message" class="message-bubble">Crie uma imagem na proporção 1:1.
Um gato laranja</div>
 {_grok_bolha_gerada(GROK_GERADA)}
</main>"""

GROK_SO_WEB = f"""
<main>
 <div data-testid="user-message" class="message-bubble">Crie uma imagem na proporção 1:1.
Um gato laranja</div>
 <div data-testid="assistant-message" class="message-bubble">
  <div class="response-content-markdown">Achei estas na web:
   <div class="relative group/image"><div class="rounded-2xl"><img alt="Imagem gerada"
     src="{GROK_WEB}"></div></div></div></div>
</main>"""


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

    def test_chatgpt_cartao_novo_pega_a_do_nosso_turno(self):
        """02/10: o cartao novo da conta Plus. Antes do conserto: ancorado
        False (nenhum `data-message-author-role`), zero imagens, e o carteiro
        ficou 420 s em "0 chars" com a imagem pronta na tela."""
        c = self._cliente("chatgpt", CHATGPT_NOVO)
        achado = c.imagens_da_resposta()
        self.assertTrue(achado["ancorado"])
        self.assertTrue(achado["resposta"])
        self.assertFalse(achado["gerando"])
        self.assertIn("Create ONE square", achado["turno"])
        self.assertNotIn("Você disse", achado["turno"])
        self.assertEqual([i["src"] for i in achado["imagens"]], [NOVA])  # nao a do cachorro
        self.assertEqual(achado["imagens"][0]["alt"], "Imagem 1 gerada")
        self.assertEqual(achado["fora"], 1)                  # o anuncio, ignorado
        prontas = c.imagens_prontas(achado, antes={NOVA_ANTIGA, ANUNCIO})
        self.assertEqual([i["src"] for i in prontas], [NOVA])
        # a que ja estava na pagina antes do envio nao vale
        self.assertEqual(c.imagens_prontas(achado, antes={NOVA}), [])

    def test_chatgpt_cartao_novo_sem_botoes_esta_em_geracao(self):
        c = self._cliente("chatgpt", CHATGPT_NOVO_GERANDO)
        achado = c.imagens_da_resposta()
        self.assertTrue(achado["resposta"])
        self.assertTrue(achado["gerando"])
        self.assertEqual(achado["imagens"], [])
        self.assertEqual(c.imagens_prontas(achado), [])

    def test_chatgpt_cartao_novo_marca_a_previa_do_mesmo_item(self):
        """02/10 (decisao do Adrian, "Visualizador"): quem abre o "Baixar" e a
        previa do item da NOSSA imagem, nunca o "Compartilhar imagem gerada N"."""
        from ias import imagem
        c = self._cliente("chatgpt", CHATGPT_NOVO)
        s = c.sel
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], NOVA, [],
            s["imagem_abrir"]])
        self.assertEqual(marcado, {"imagem": True, "botao": False, "abrir": True})
        abrir = self.page.locator("[data-nf-abrir='1']")
        self.assertEqual(abrir.count(), 1)
        self.assertEqual(abrir.get_attribute("data-testid"), "generated-image-preview")
        self.assertEqual(abrir.get_attribute("aria-label"), "Imagem 1 gerada")
        # a previa marcada e a da NOSSA imagem, nao a do cachorro
        self.assertEqual(abrir.evaluate("b => b.querySelector('img').getAttribute('src')"),
                         NOVA)
        # a imagem do turno antigo nunca e marcada
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], NOVA_ANTIGA, [],
            s["imagem_abrir"]])
        self.assertFalse(marcado["imagem"])

    def test_chatgpt_compartilhar_nunca_e_marcado(self):
        """Mesmo que alguem ponha de volta o seletor do "Compartilhar imagem
        gerada N" (o caminho de e8470c8), o JS nao o marca: `abrir` False e
        quem chama clica na propria imagem."""
        from ias import imagem
        c = self._cliente("chatgpt", CHATGPT_NOVO)
        s = c.sel
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], NOVA, [],
            ["button[aria-label^='Compartilhar imagem gerada']"]])
        self.assertEqual(marcado, {"imagem": True, "botao": False, "abrir": False})
        self.assertEqual(self.page.locator("[data-nf-abrir]").count(), 0)
        # nem como botao de baixar
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], NOVA,
            ["button[aria-label^='Compartilhar imagem gerada']"]])
        self.assertEqual(marcado, {"imagem": True, "botao": False})

    def test_chatgpt_baixa_pelo_visualizador_sem_clicar_em_compartilhar(self):
        """O caminho inteiro num Chrome de verdade: clica na previa, o
        visualizador (`div[role=dialog]` "Previa da imagem", medido em 02/10
        00:07) abre com "Baixar", "Compartilhar" e "Fechar visualizador"; o
        "Baixar" solta o download; Escape fecha. Nenhum "Compartilhar" (nem o
        do item, nem o do visualizador) e clicado."""
        from ias import imagem
        png = imagem.png_de_teste(330, 330, cor=(255, 0, 255))
        b64 = base64.b64encode(png).decode("ascii")
        c = self._cliente("chatgpt", CHATGPT_NOVO)
        self.page.evaluate("""(b64) => {
          window.__compartilhou = 0; window.__baixou = 0;
          document.addEventListener('click', ev => {
            const b = ev.target.closest('button');
            if (b && /compartilh/i.test(b.getAttribute('aria-label') || ''))
              window.__compartilhou++; }, true);
          const abrir = (img) => {
            const d = document.createElement('div');
            d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true');
            d.id = 'visualizador';
            d.innerHTML = '<h2 class="sr-only">Prévia da imagem</h2>'
              + '<button type="button" aria-label="Baixar"><svg></svg></button>'
              + '<button type="button" aria-label="Compartilhar">Compartilhar</button>'
              + '<button type="button" aria-label="Fechar visualizador"></button>'
              + '<img alt="Imagem 1 gerada" src="' + img.src + '">';
            d.querySelector("[aria-label=Baixar]").addEventListener('click', () => {
              window.__baixou++;
              const bytes = Uint8Array.from(atob(b64), ch => ch.charCodeAt(0));
              const a = document.createElement('a');
              a.href = URL.createObjectURL(new Blob([bytes], {type: 'image/png'}));
              a.download = 'ChatGPT Image.png'; document.body.appendChild(a); a.click(); });
            document.body.appendChild(d); };
          for (const p of document.querySelectorAll('[data-testid=generated-image-preview]'))
            p.addEventListener('click', () => abrir(p.querySelector('img')));
          document.addEventListener('keydown', ev => {
            if (ev.key === 'Escape') document.getElementById('visualizador')?.remove(); });
        }""", b64)
        visto = {"src": NOVA, "w": 330, "h": 330}
        corpo = imagem.baixar_pelo_botao(c, visto, timeout_s=15, log=lambda *_a: None)
        self.assertEqual(corpo, png)
        self.assertEqual(self.page.evaluate("window.__baixou"), 1)
        self.assertEqual(self.page.evaluate("window.__compartilhou"), 0)
        self.assertEqual(self.page.locator("#visualizador").count(), 0)   # Escape fechou

    def test_chatgpt_dom_novo_resposta_de_texto(self):
        """02/10: no DOM novo a resposta de TEXTO tambem nao tinha seletor
        (zero `data-message-author-role`): o "APROVADO" do nosso turno e lido,
        o "REPROVADO" do turno anterior nao."""
        def par(pedido, resposta):
            return f"""
 <div class="block-BQZwFn"><h4 class="sr-only">Você disse:</h4>
  <div data-user-message-bubble="true"><div dir="auto">{pedido}</div></div></div>
 <div class="block-BQZwFn"><h4 data-conversation-role="assistant" class="sr-only">ChatGPT disse:</h4>
  <div data-chatgpt-selection-message-id="m-{len(pedido)}" class="group flex">
   <div data-markdown-text-style="assistant-message" dir="auto"><p>{resposta}</p></div></div></div>"""
        html = f"<main>{par('primeira folha', 'REPROVADO')}{par('segunda folha revisada', 'APROVADO')}</main>"
        c = self._cliente("chatgpt", html)
        self.assertEqual(c._resposta_atual().strip(), "APROVADO")
        self.assertTrue(c._ancorado)

    def test_chatgpt_cartao_antigo_sem_abridor_clica_na_imagem(self):
        """O cartao de 29/09 nao tem a previa da galeria: `abrir` False, e
        quem chama clica na imagem como antes."""
        from ias import imagem
        c = self._cliente("chatgpt", CHATGPT)
        s = c.sel
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], GATO, [],
            s["imagem_abrir"]])
        self.assertEqual(marcado, {"imagem": True, "botao": False, "abrir": False})

    def _cliente_grok(self, html):
        from ias.imagem import png_de_teste
        corpo = png_de_teste(320, 320, cor=(200, 120, 40))

        def servir(route):
            route.fulfill(status=200, content_type="image/png", body=corpo)

        self.page.route("https://**/*", servir)
        self.addCleanup(self.page.unroute, "https://**/*")
        return self._cliente("grok", html)

    def test_grok_pega_a_gerada_da_conta_e_nao_anexo_pfp_nem_antiga(self):
        from ias import imagem
        c = self._cliente_grok(GROK)
        achado = c.imagens_da_resposta()
        self.assertTrue(achado["ancorado"])
        self.assertTrue(achado["resposta"])
        self.assertIn("Um gato laranja", achado["turno"])
        self.assertEqual([i["src"] for i in achado["imagens"]], [GROK_GERADA])  # 2 <img>, 1 src
        gerada = achado["imagens"][0]
        self.assertEqual(gerada["alt"], "Imagem gerada")
        self.assertEqual((gerada["w"], gerada["h"]), (320, 320))
        prontas = c.imagens_prontas(achado, antes={GROK_ANTIGA, GROK_ANEXO, GROK_PFP})
        self.assertEqual([i["src"] for i in prontas], [GROK_GERADA])
        s = c.sel
        marcado = self.page.evaluate(imagem._JS_MARCAR, [
            s["turno_usuario"], s["imagem_turno"], s["imagem_gerada"], GROK_GERADA, []])
        self.assertEqual(marcado, {"imagem": True, "botao": False})

    def test_grok_imagem_da_web_no_balao_nao_vale(self):
        c = self._cliente_grok(GROK_SO_WEB)
        achado = c.imagens_da_resposta()
        self.assertTrue(achado["resposta"])
        self.assertEqual(achado["imagens"], [])
        self.assertEqual(achado["fora"], 1)                  # a da web, ignorada
        self.assertEqual(c.imagens_prontas(achado), [])

    def test_sem_turno_do_usuario_caso_zero(self):
        c = self._cliente("chatgpt", "<main><p>nada</p></main>")
        achado = c.imagens_da_resposta()
        self.assertFalse(achado["ancorado"])
        self.assertEqual(achado["imagens"], [])


if __name__ == "__main__":
    unittest.main()
