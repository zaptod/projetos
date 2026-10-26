# -*- coding: utf-8 -*-
"""26/10/2026: o 1o upload da conta zombie_surviv0rs abre, UM ATRAS DO OUTRO,
o dialogo "Ativar verificacoes automaticas de conteudo?" e um cartao do editor
de video no canto (telas 20261026_102335 e _105433): a legenda ficava coberta
(TimeoutError 3x). `_fechar_aviso` e GENERICO: enquanto ha sobreposicao fecha
pelo botao de dispensa (nunca pelo que ativa algo), ate 5 rodadas, com captura
de cada uma; Escape quando nao ha botao. Caso ZERO: sem sobreposicao nao faz nada.

O JS roda de verdade em `JsDeVerdadeTests` (Chrome; so com NF_TESTE_NAVEGADOR=1).
"""
import os
import unittest

from builds.publicar import tiktok


class _Teclado:
    def __init__(self, pagina):
        self.p = pagina

    def press(self, tecla):
        self.p.teclas.append(tecla)


class _Pagina:
    """Devolve, a cada `evaluate`, o proximo estado da tela."""

    def __init__(self, estados):
        self.estados, self.teclas = list(estados), []
        self.keyboard = _Teclado(self)
        self.chamadas = 0

    def evaluate(self, js, arg=None):
        self.chamadas += 1
        return self.estados.pop(0) if self.estados else {"sobreposicao": False}


class AvisoTests(unittest.TestCase):
    def setUp(self):
        self._sono = tiktok.__dict__.get("time")

    def _rodar(self, estados):
        pg = _Pagina(estados)
        passos, laudo = [], {}
        feito = tiktok._fechar_aviso(pg, passos.append, laudo)
        return pg, feito, passos, laudo

    def test_dois_avisos_em_sequencia(self):
        pg, feito, passos, laudo = self._rodar([
            {"sobreposicao": True, "clicou": "cancelar"},
            {"sobreposicao": True, "clicou": "entendi"},
            {"sobreposicao": False}])
        self.assertEqual(feito, "cancelar, entendi")
        self.assertEqual(laudo["avisos_fechados"], ["cancelar", "entendi"])
        self.assertEqual(pg.chamadas, 3)
        self.assertEqual(len(passos), 2)

    def test_sem_botao_usa_escape(self):
        pg, feito, _p, _l = self._rodar([
            {"sobreposicao": True, "clicou": "", "vistos": ["experimentar"]},
            {"sobreposicao": False}])
        self.assertEqual(pg.teclas, ["Escape"])
        self.assertEqual(feito, "Escape")

    def test_limite_de_cinco_rodadas(self):
        pg, *_ = self._rodar([{"sobreposicao": True, "clicou": "x"}] * 20)
        self.assertEqual(pg.chamadas, tiktok.RODADAS_DE_AVISO)

    def test_sem_sobreposicao_nao_faz_nada(self):
        pg, feito, passos, laudo = self._rodar([{"sobreposicao": False}])
        self.assertEqual((feito, passos, laudo, pg.teclas), ("", [], {}, []))

    def test_pagina_que_levanta_nao_derruba(self):
        class Quebrada:
            def evaluate(self, *a):
                raise RuntimeError("fechou")
        self.assertEqual(tiktok._fechar_aviso(Quebrada(), lambda t: None), "")

    def test_o_que_ativa_algo_nunca_e_dispensa(self):
        for botao in ("ativar", "ligar", "aceitar", "permitir", "publicar",
                      "continuar", "experimentar"):
            self.assertIn(botao, tiktok.BOTOES_PROIBIDOS)
            self.assertNotIn(botao, tiktok.BOTOES_DE_DISPENSA)


HTML = """<html><body style="height:3000px">
<div id=a role=dialog style="position:fixed;inset:0;background:#0008">
 <div style="background:#fff;margin:50px;padding:20px">Ativar verificacoes?
  <button id=ativar>Ativar</button><button id=cancelar>Cancelar</button></div></div>
<div id=b class="guide-popup" style="position:fixed;right:0;bottom:-120px;width:300px;
 height:300px;background:#eee;display:none"><img><button id=ok>Entendi</button>
 <button id=experimente>Experimentar</button></div>
<script>
document.getElementById('cancelar').onclick=()=>{document.getElementById('a').remove();
 document.getElementById('b').style.display='block'};
document.getElementById('ok').onclick=()=>document.getElementById('b').remove();
document.getElementById('ativar').onclick=()=>window.ATIVOU=true;
document.getElementById('experimente').onclick=()=>window.ATIVOU=true;
</script></body></html>"""


@unittest.skipUnless(os.environ.get("NF_TESTE_NAVEGADOR") == "1",
                     "abre um Chrome: NF_TESTE_NAVEGADOR=1")
class JsDeVerdadeTests(unittest.TestCase):
    def test_dois_popups_e_nunca_o_que_ativa(self):
        import tempfile
        from pathlib import Path
        from builds.identity.browser import contexto_persistente
        with tempfile.TemporaryDirectory() as tmp, \
                contexto_persistente(headless=False, profile=Path(tmp)) as ctx:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_content(HTML)
            feito = tiktok._fechar_aviso(page, lambda t: None)
            self.assertEqual(feito, "cancelar, entendi")
            self.assertFalse(page.evaluate("() => !!window.ATIVOU"))
            self.assertEqual(page.locator("[role=dialog], .guide-popup").count(), 0)


if __name__ == "__main__":
    unittest.main()
