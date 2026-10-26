# -*- coding: utf-8 -*-
"""26/10/2026: o comentario com a pergunta do episodio, fixado (serie Blue Lock).

Pagina SIMULADA (Chrome headless, `set_content`), com a estrutura que o
YouTube usa na pagina do video: caixa `#placeholder-area` que abre o editor
`#contenteditable-root`, `#submit-button`, `ytd-comment-thread-renderer` com
`#action-menu`, item "Fixar", dialogo `#confirm-button` e o selo
`ytd-pinned-comment-badge-renderer`. Contas de mao:
  - pagina sem comentario: comenta 1 e fixa 1 (laudo comentou+fixou);
  - rodar de novo na mesma pagina: 1 comentario so (idempotente), ja fixado;
  - menu sem "Fixar": levanta (nao diz que fixou);
  - pergunta vazia (caso ZERO) ou com palavra proibida: levanta, sem tocar
    na pagina;
  - TikTok sem opcao de fixar: comenta e devolve fixou=False (melhor esforco).
"""
from __future__ import annotations

import unittest

from builds.publicar import comentario as C

PERGUNTA = "Qual personagem você colocaria no seu time? 👇"

YT = """
<html><body>
<ytd-comment-simplebox-renderer><div id="simple-box">
  <div id="placeholder-area">Adicione um comentário...</div></div>
</ytd-comment-simplebox-renderer>
<div id="threads"></div><div id="popup"></div><div id="dialogo"></div>
<script>
const FIXAR = %s;
document.querySelector('#placeholder-area').onclick = () => {
  if (document.querySelector('ytd-commentbox')) return;
  const b = document.createElement('ytd-commentbox');
  b.innerHTML = '<div id="contenteditable-root" contenteditable="true"></div>' +
                '<div id="submit-button"><button>Comentar</button></div>';
  document.querySelector('#simple-box').appendChild(b);
  b.querySelector('button').onclick = () => {
    const txt = b.querySelector('#contenteditable-root').innerText;
    const t = document.createElement('ytd-comment-thread-renderer');
    t.innerHTML = '<div class="t">' + txt + '</div>' +
      '<div id="action-menu"><button>menu</button></div>';
    t.querySelector('#action-menu button').onclick = () => {
      document.querySelector('#popup').innerHTML = FIXAR ?
        '<ytd-menu-service-item-renderer>Fixar</ytd-menu-service-item-renderer>'
        : '<ytd-menu-service-item-renderer>Excluir</ytd-menu-service-item-renderer>';
      const item = document.querySelector('ytd-menu-service-item-renderer');
      item.onclick = () => {
        document.querySelector('#dialogo').innerHTML =
          '<yt-confirm-dialog-renderer><div id="confirm-button"><button>Fixar</button></div></yt-confirm-dialog-renderer>';
        document.querySelector('#confirm-button button').onclick = () => {
          t.insertAdjacentHTML('afterbegin',
            '<ytd-pinned-comment-badge-renderer>Fixado por @canal</ytd-pinned-comment-badge-renderer>');
          document.querySelector('#dialogo').innerHTML = '';
        };
      };
    };
    document.querySelector('#threads').prepend(t);
    b.remove();
  };
};
</script></body></html>
"""

TT = """
<html><body>
<div data-e2e="comment-input"><div contenteditable="true"></div></div>
<div data-e2e="comment-post">Publicar</div>
<div id="lista"></div>
<script>
document.querySelector('[data-e2e=comment-post]').onclick = () => {
  const txt = document.querySelector('[data-e2e=comment-input] div').innerText;
  const c = document.createElement('div');
  c.setAttribute('data-e2e', 'comment-level-1'); c.innerText = txt;
  document.querySelector('#lista').prepend(c);
};
</script></body></html>
"""


class ComentarioFixadoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from patchright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.navegador = cls.pw.chromium.launch(channel="chrome", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.navegador.close()
        cls.pw.stop()

    def _pagina(self, html):
        page = self.navegador.new_page()
        self.addCleanup(page.close)
        page.set_content(html)
        return page

    def test_comenta_e_fixa(self):
        page = self._pagina(YT % "true")
        laudo = C.comentar_e_fixar_youtube(page, PERGUNTA, lambda *_: None)
        self.assertTrue(laudo["comentou"])
        self.assertTrue(laudo["fixou"])
        self.assertEqual(page.locator("ytd-comment-thread-renderer").count(), 1)
        self.assertIn("Fixado", page.inner_text("ytd-comment-thread-renderer"))
        self.assertIn(PERGUNTA, page.inner_text("ytd-comment-thread-renderer"))

    def test_segunda_vez_nao_duplica(self):
        page = self._pagina(YT % "true")
        C.comentar_e_fixar_youtube(page, PERGUNTA, lambda *_: None)
        laudo = C.comentar_e_fixar_youtube(page, PERGUNTA, lambda *_: None)
        self.assertTrue(laudo["ja_existia"])
        self.assertFalse(laudo["comentou"])
        self.assertTrue(laudo["fixou"])
        self.assertEqual(page.locator("ytd-comment-thread-renderer").count(), 1)

    def test_menu_sem_fixar_levanta(self):
        page = self._pagina(YT % "false")
        with self.assertRaises(C.ComentarioFalhou):
            C.comentar_e_fixar_youtube(page, PERGUNTA, lambda *_: None)

    def test_pergunta_vazia_ou_proibida_nao_toca_na_pagina(self):
        page = self._pagina(YT % "true")
        for ruim in ("", "   ", "Veja no GitHub o código?"):
            with self.assertRaises(C.ComentarioFalhou, msg=ruim):
                C.comentar_e_fixar_youtube(page, ruim, lambda *_: None)
        self.assertEqual(page.locator("ytd-comment-thread-renderer").count(), 0)

    def test_tiktok_comenta_e_sem_fixar_devolve_falso(self):
        page = self._pagina(TT)
        laudo = C.comentar_e_fixar_tiktok(page, PERGUNTA, lambda *_: None)
        self.assertTrue(laudo["comentou"])
        self.assertFalse(laudo["fixou"])
        self.assertEqual(page.locator("[data-e2e=comment-level-1]").count(), 1)

    def test_rodada_sem_pergunta_na_ficha_nao_abre_navegador(self):
        chamadas = []
        original = C.aplicar
        C.aplicar = lambda *a, **k: chamadas.append(a)
        self.addCleanup(setattr, C, "aplicar", original)
        from builds.publicar import serie_bluelock as serie
        antes = serie.pergunta_de
        serie.pergunta_de = lambda n, origem=None: ""
        self.addCleanup(setattr, serie, "pergunta_de", antes)
        antes_ja = C.ja_feito
        C.ja_feito = lambda n, d: False
        self.addCleanup(setattr, C, "ja_feito", antes_ja)
        C.LIGADO = True
        self.addCleanup(setattr, C, "LIGADO", False)
        self.assertEqual(C.aplicar_se_tiver(1, "youtube", video_id="x"),
                         {"pulou": "sem pergunta na ficha"})
        self.assertEqual(chamadas, [])

    def test_chave_desligada_a_rodada_nao_comenta_mesmo_com_pergunta(self):
        """Ordem do Adrian (26/10): o 1o teste comentou com a conta PESSOAL.
        LIGADO fica False; com pergunta na ficha, `aplicar` nao e chamado e
        o navegador nao abre."""
        self.assertIs(C.LIGADO, False)
        chamadas = []
        original = C.aplicar
        C.aplicar = lambda *a, **k: chamadas.append(a)
        self.addCleanup(setattr, C, "aplicar", original)
        from builds.publicar import serie_bluelock as serie
        antes = serie.pergunta_de
        serie.pergunta_de = lambda n, origem=None: PERGUNTA
        self.addCleanup(setattr, serie, "pergunta_de", antes)
        self.assertEqual(C.aplicar_se_tiver(1, "youtube", video_id="x"),
                         {"pulou": "comentario automatico desligado"})
        self.assertEqual(chamadas, [])
        os_env = __import__("os").environ
        self.assertNotEqual(os_env.get("NF_COMENTARIO_LIBERADO"), "1")
        with self.assertRaises(C.ComentarioFalhou):
            original(1, "youtube", PERGUNTA, video_id="x")


if __name__ == "__main__":
    unittest.main()
