# -*- coding: utf-8 -*-
"""26/10/2026: o destino Instagram (Reels), reutilizavel por canal.

O que cada teste prova (contas de mao no docstring):
  - FLUXO INTEIRO numa pagina simulada (Chrome headless): Criar -> arquivo ->
    pop-up "Reels agora sao compartilhados" (OK) -> corte Original -> capa
    (quadro) -> legenda -> "compartilhar tambem no feed" LIGADO -> Compartilhar
    -> "Seu reel foi compartilhado". O laudo diz capa/feed/corte/identidade.
  - IDENTIDADE ERRADA: menu mostra @pessoal e o canal e @egoistsoccer ->
    ContaErrada ANTES do upload (o arquivo nunca chega, nada e clicado).
    O @ ilegivel (menu sem link Perfil) tambem recusa (falha fechada).
  - DOIS POP-UPS empilhados (um "OK", um "Agora nao" ao lado de "Ativar"): os
    dois saem pelo botao de dispensa e NUNCA se clica em "Ativar" nem se fecha
    a janela de trabalho.
  - CAPA que nao entra (sem a aba Capa): NAO publica (a capa nao se troca).
  - LEGENDA: 2200 caracteres (UTF-16) e hashtags (5 da casa, teto de 30, "#1"
    nao conta); titulo primeiro.
  - SEM CONTA = CALADO: `ligado` False, `status` explica, `conformidade()` sem
    alarme do instagram, a rodada da serie nao ganha o destino e
    `instagram.publicar` recusa antes de abrir o Chrome.
  - GRADE: a serie no Instagram e 20:37; duelos/historias 21:37 prontos mas sem
    conta nao existem; a meta diaria global nao mudou.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from builds import contas, grade
from builds.publicar import instagram as I
from builds.publicar import tiktok

HTML = """
<html><body>
<nav><a href="/" aria-label="Inicio"><span>Pagina inicial</span></a>
  __PERFIL__
  <a href="#" id="criar" onclick="criar()"><svg aria-label="Nova publicação"></svg>
     <span>Criar</span></a></nav>
<div id="menu" style="display:none"><a id="item" href="#" onclick="abrirDialogo()">Publicação</a></div>
<div id="aviso1" role="dialog" style="display:none">
  <p>Os vídeos agora são compartilhados como reels</p><button id="ok1">OK</button></div>
<div id="aviso2" role="dialog" style="display:none">
  <p>Ativar notificações?</p><button id="ativar">Ativar</button>
  <button id="agora">Agora não</button></div>
<div id="dlg" role="dialog" style="display:none">
  <div id="passo-arquivo">Criar nova publicação
     <button>Selecionar do computador</button><input type="file" id="arq"></div>
  <div id="passo-corte" style="display:none">Cortar
     <button aria-label="Selecionar corte" onclick="document.getElementById('cortes').style.display='block'">c</button>
     <div id="cortes" style="display:none"><span onclick="S.corte='original'">Original</span><span>1:1</span></div>
     <div role="button" onclick="ir('passo-edicao')">Avançar</div></div>
  <div id="passo-edicao" style="display:none">Editar
     __ABA_CAPA__
     <div id="capa-box" style="display:none"><input type="file" id="capa"></div>
     <div role="button" onclick="ir('passo-legenda')">Avançar</div></div>
  <div id="passo-legenda" style="display:none">Nova publicação do reel
     <div role="textbox" contenteditable="true" aria-label="Escreva uma legenda..." id="leg"></div>
     <div><span>Compartilhar também no feed</span>
        <div role="switch" id="feed" aria-checked="false"
             onclick="this.setAttribute('aria-checked', this.getAttribute('aria-checked')==='true'?'false':'true')"></div></div>
     <div role="button" onclick="compartilhar()">Compartilhar</div></div>
  <div id="passo-fim" style="display:none"><span id="fim"></span></div>
</div>
<pre id="estado" style="display:none">{}</pre>
<script>
window.S = {arquivo: null, capa: null, corte: null, compartilhado: false,
            ativou: false, fechou: false};
const $ = id => document.getElementById(id);
const salvar = () => { $('estado').textContent = JSON.stringify(S); };
setInterval(salvar, 50);
function criar(){ $('menu').style.display='block'; }
function abrirDialogo(){ $('dlg').style.display='block'; $('menu').style.display='none'; }
function ir(id){ for (const p of ['passo-arquivo','passo-corte','passo-edicao','passo-legenda','passo-fim'])
                   $(p).style.display = (p===id)?'block':'none'; }
$('arq').onchange = e => { S.arquivo = e.target.files[0].name;
   __AVISOS__
   ir('passo-corte'); };
$('ok1').onclick = () => { $('aviso1').style.display='none'; };
$('agora').onclick = () => { $('aviso2').style.display='none'; };
$('ativar').onclick = () => { S.ativou = true; };
if ($('aba-capa')) $('aba-capa').onclick = () => { $('capa-box').style.display='block'; };
$('capa').onchange = e => { S.capa = e.target.files[0].name; };
function compartilhar(){ S.compartilhado = true; S.legenda = $('leg').innerText;
   S.feed = $('feed').getAttribute('aria-checked');
   $('fim').innerText = 'Seu reel foi compartilhado'; ir('passo-fim'); }
</script></body></html>
"""

PERFIL_OK = '<a href="/egoistsoccer/"><img alt="Foto do perfil de egoistsoccer"><span>Perfil</span></a>'
PERFIL_PESSOAL = '<a href="/adrianoliveira9418/"><img alt="Foto do perfil"><span>Perfil</span></a>'
ABA = '<div role="tab" id="aba-capa">Capa</div>'


def pagina_html(*, perfil=PERFIL_OK, aba=ABA, avisos=("aviso1",)):
    mostrar = " ".join(f"$('{a}').style.display='block';" for a in avisos)
    return (HTML.replace("__PERFIL__", perfil).replace("__ABA_CAPA__", aba)
            .replace("__AVISOS__", mostrar))


def estado_da_pagina(page) -> dict:
    import json
    page.wait_for_timeout(150)
    return json.loads(page.evaluate(
        "() => document.getElementById('estado').textContent"))


def video(arquivo: Path, **mais):
    base = dict(id="bluelock_ep01", caminho=arquivo, vertical=True,
                titulo="Esse jogador parou. Ninguém mandou. | Como eu criei um Blue Lock #1",
                descricao="Cada jogador decide sozinho.\n\nQual personagem você colocaria no seu time?",
                hashtags=["#bluelock", "#futebol", "#simulador", "#anime",
                          "#isagi", "#bachira"], capa_s=0.0)
    base.update(mais)
    return SimpleNamespace(**base)


class _Conta:
    """Isola o registro de contas (runtime descartavel) e liga a conta."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        antes = contas.ARQUIVO
        contas.ARQUIVO = str(Path(self.tmp.name) / "contas.json")
        self.addCleanup(setattr, contas, "ARQUIVO", antes)
        self._runtime = contas.runtime_dir
        contas.runtime_dir = lambda: Path(self.tmp.name)
        self.addCleanup(setattr, contas, "runtime_dir", self._runtime)

    def ligar(self, canal="bluelock", conta="egoistsoccer"):
        contas.escolher("instagram", canal, conta)
        contas.identificar("instagram", conta, rotulo=f"@{conta}",
                           identificador=conta,
                           extra={"arroba_esperada": conta})


class FluxoSimuladoTests(_Conta, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from patchright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.navegador = cls.pw.chromium.launch(channel="chrome", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.navegador.close()
        cls.pw.stop()

    def setUp(self):
        super().setUp()
        self.ligar()
        leituras = []

        def hrefs(page, arroba, *_):            # 1a: antes; 2a: depois
            leituras.append(arroba)
            return ({"/reel/ANTIGO/"} if len(leituras) == 1
                    else {"/reel/ANTIGO/", "/reel/NOVO123/"})
        self._trocar(I, "_hrefs_do_perfil", hrefs)
        self._trocar(I, "ESPERA_IDENTIDADE_S", 1.0)
        self._trocar(I, "ESPERA_PROCESSAR_S", 10.0)
        self._trocar(I, "ESPERA_PAGINA_S", 5.0)
        self._trocar(I, "ESPERA_CONFIRMAR_S", 10.0)
        self._trocar(escrita_mod(), "PASTA_DAS_TELAS", Path(self.tmp.name))
        self.arq = Path(self.tmp.name) / "ep01.mp4"
        self.arq.write_bytes(b"video original")
        self.png = Path(self.tmp.name) / "quadro.png"
        self.png.write_bytes(b"\x89PNG\r\n\x1a\n")
        self.passos = []

    def _trocar(self, obj, nome, valor):
        original = getattr(obj, nome)
        setattr(obj, nome, valor)
        self.addCleanup(setattr, obj, nome, original)

    def _pagina(self, html):
        page = self.navegador.new_page()
        self.addCleanup(page.close)
        page.set_content(html)
        return page

    def _rodar(self, page, **mais):
        laudo: dict = {}
        v = video(self.arq)
        estado = I._executar(page, v, self.arq, "bluelock", True,
                             self.passos.append, laudo,
                             quadro=mais.get("quadro", self.png))
        return estado, laudo

    def test_fluxo_inteiro(self):
        page = self._pagina(pagina_html())
        estado, laudo = self._rodar(page)
        self.assertTrue(I.confirmado(estado), estado)
        self.assertIn("/reel/NOVO123/", estado)          # o link, pelo perfil
        s = estado_da_pagina(page)
        self.assertEqual(s["arquivo"], "ep01.mp4")        # o mp4 ORIGINAL
        self.assertEqual(s["capa"], "quadro.png")         # capa escolhida
        self.assertEqual(s["corte"], "original")
        self.assertEqual(s["feed"], "true")               # feed LIGADO
        self.assertTrue(s["compartilhado"])
        self.assertIn("Esse jogador parou", s["legenda"])
        self.assertIn("#bluelock", s["legenda"])
        self.assertEqual(laudo["capa"], "enviada")
        self.assertEqual(laudo["feed"], "ligado")
        self.assertEqual([i["etapa"] for i in laudo["identidade"]],
                         ["antes", "antes_de_publicar"])
        self.assertTrue(all(i["lido"] == "egoistsoccer"
                            for i in laudo["identidade"]))
        self.assertTrue(laudo["clicou"] and laudo["confirmado"])
        self.assertEqual(laudo["avisos_fechados"], ["ok"])
        self.assertTrue(any("arquivo entregue" in p for p in self.passos))
        self.assertTrue(any("publicar clicado" in p for p in self.passos))

    def test_identidade_errada_recusa_antes_do_upload(self):
        page = self._pagina(pagina_html(perfil=PERFIL_PESSOAL))
        with self.assertRaises(I.ContaErrada) as c:
            self._rodar(page)
        self.assertIn("adrianoliveira9418", str(c.exception))
        s = estado_da_pagina(page)
        self.assertIsNone(s["arquivo"])                   # nada foi enviado
        self.assertFalse(s["compartilhado"])

    def test_arroba_ilegivel_recusa(self):
        page = self._pagina(pagina_html(perfil=""))
        with self.assertRaises(I.ContaErrada) as c:
            self._rodar(page)
        self.assertIn("nao consegui ler", str(c.exception))
        self.assertIsNone(estado_da_pagina(page)["arquivo"])

    def test_dois_popups_so_por_dispensa(self):
        page = self._pagina(pagina_html(avisos=("aviso1", "aviso2")))
        estado, laudo = self._rodar(page)
        self.assertTrue(I.confirmado(estado))
        s = estado_da_pagina(page)
        self.assertFalse(s["ativou"], "clicou em 'Ativar'!")
        self.assertEqual(laudo["avisos_fechados"], ["ok", "agora nao"])
        # a janela de trabalho seguiu de pe ate o fim
        self.assertTrue(s["compartilhado"])

    def test_capa_que_nao_entra_nao_publica(self):
        page = self._pagina(pagina_html(aba=""))
        with self.assertRaises(I.InstagramFalhou) as c:
            self._rodar(page)
        self.assertIn("NAO publico sem", str(c.exception))
        s = estado_da_pagina(page)
        self.assertFalse(s["compartilhado"])

    def test_sem_o_quadro_nao_publica(self):
        page = self._pagina(pagina_html())
        with self.assertRaises(I.InstagramFalhou):
            self._rodar(page, quadro=None)
        self.assertFalse(estado_da_pagina(page)["compartilhado"])

    def test_pop_up_nunca_clica_em_botao_proibido(self):
        """O JS do aviso generico, no Chrome: 'Ativar' e 'Seguir' ficam."""
        page = self._pagina("""<div role=dialog><button id=a>Ativar</button>
            <button id=s>Seguir</button></div>""")
        feitos = I._fechar_aviso(page, lambda *_: None, {})
        self.assertNotIn("ativar", feitos)
        self.assertNotIn("seguir", feitos)


def escrita_mod():
    from builds.publicar import escrita
    return escrita


class LegendaTests(unittest.TestCase):
    def test_limites_e_ordem(self):
        v = video(Path("x.mp4"), descricao="palavra " * 600,
                  hashtags=[f"#t{i}" for i in range(40)])
        texto = I.legenda_do_video(v)
        self.assertLessEqual(I._tamanho(texto), 2200)
        self.assertTrue(texto.startswith("Esse jogador parou"))
        self.assertEqual(len(__import__("re").findall(r"#t\d+", texto)),
                         I.HASHTAGS_NA_LEGENDA)
        self.assertTrue(texto.endswith("#t4"))        # hashtags inteiras no fim

    def test_numero_nao_e_hashtag_e_teto_de_30(self):
        v = video(Path("x.mp4"), hashtags=[f"#t{i}" for i in range(40)])
        # "#1" do titulo nao conta; 5 da casa
        self.assertEqual(
            len(__import__("re").findall(r"#t\d+", I.legenda_do_video(v))), 5)
        # mesmo pedindo 99, o teto do site e 30
        todas = I.legenda_do_video(v, hashtags=99)
        self.assertEqual(len(__import__("re").findall(r"#t\d+", todas)), 30)

    def test_emoji_conta_dois_no_limite(self):
        v = video(Path("x.mp4"), titulo="x", descricao="😀" * 1500, hashtags=[])
        self.assertLessEqual(I._tamanho(I.legenda_do_video(v)), 2200)

    def test_sem_hashtags_nem_descricao(self):
        v = video(Path("x.mp4"), descricao="", hashtags=[])
        self.assertEqual(I.legenda_do_video(v), v.titulo)


class SemContaTests(_Conta, unittest.TestCase):
    def test_sem_conta_calado(self):
        for canal in ("bluelock", "builds", "historias"):
            self.assertFalse(I.ligado(canal))
            self.assertIn("desligado", I.status(canal)["motivo"])
        self.assertEqual(
            [a for a in contas.conformidade() if a["servico"] == "instagram"],
            [])

    def test_conta_sem_login_conferido_continua_desligada(self):
        contas.escolher("instagram", "bluelock", "egoistsoccer")
        self.assertFalse(I.ligado("bluelock"))
        self.assertIn("login", I.status("bluelock")["motivo"])

    def test_com_login_conferido_liga_so_aquele_canal(self):
        self.ligar("bluelock", "egoistsoccer")
        self.assertTrue(I.ligado("bluelock"))
        self.assertFalse(I.ligado("builds"))     # nunca herda a conta de outro
        self.assertEqual(I.arroba_esperada("bluelock"), "egoistsoccer")

    def test_funil_recusa_destino_desligado_sem_abrir_chrome(self):
        with self.assertRaises(I.InstagramFalhou) as c:
            I.publicar(video(Path("x.mp4")), postar=True, canal="bluelock")
        self.assertIn("desligado", str(c.exception))

    def ligar(self, canal, conta):
        contas.escolher("instagram", canal, conta)
        contas.identificar("instagram", conta, rotulo=f"@{conta}",
                           identificador=conta)


class GradeTests(unittest.TestCase):
    def test_serie_20_37_e_demais_canais_prontos(self):
        self.assertEqual(grade.horas_do_instagram("bluelock"), (20,))
        self.assertEqual(grade.horario(20), "20:37")
        self.assertEqual(grade.horas_do_instagram("builds"), (21,))
        self.assertEqual(grade.horas_do_instagram("historias"), (21,))
        self.assertEqual(grade.horas_do_instagram("nao_existe"), ())
        self.assertTrue(grade.publica_a_serie("instagram", 20))

    def test_meta_global_nao_mudou(self):
        self.assertNotIn("instagram", grade.META_DIARIA_POR_PLATAFORMA)
        self.assertNotIn("instagram", grade.HORAS_POR_PLATAFORMA)


class ContratoDoPostarTests(unittest.TestCase):
    def test_destino_instagram_vale_na_ficha_de_voo(self):
        import importlib.util
        raiz = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"
        spec = importlib.util.spec_from_file_location("postar_ig", raiz)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertIn("instagram", m.DESTINOS_COM_VOO)
        # as frases do publicador que dao a etapa do voo
        fonte = Path(I.__file__).read_text(encoding="utf-8")
        for etapa, frase in m.ETAPAS_DO_VOO:
            self.assertIn(frase, fonte)
        self.assertFalse(m._instagram_ligado("bluelock"))


if __name__ == "__main__":
    unittest.main()
