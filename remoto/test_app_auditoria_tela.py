# -*- coding: utf-8 -*-
"""Prova de tela dos consertos da auditoria profunda do app (11/10/2026).

Cada teste reproduz, no Chrome a 390x844 como Android e CLICANDO, um defeito
do relatorio `docs/auditoria/2026-10-11-profunda/app-celular.md`. O servidor
e o mesmo da prova de tela (`tela_isolada`): estado em pasta temporaria, nada
le o estado real nem a porta 8931, e nada publica, apaga, pareia conta real
ou manda mensagem a IA (o unico dialogo aberto e cancelado).

Medido em 14/10, antes do conserto (codigo de e7ea729): os 7 falham; na
entrega do Codex (pedido c7e0c0d9) ainda falhavam a faixa, o "O que falta"
e a previa do Godot.
"""
from __future__ import annotations

import contextlib
import time

import pytest

from remoto import api_http, painel_dados
from remoto.test_app_tela import CAPTURAS, NAVEGADOR, tela_isolada  # noqa: F401

pytestmark = pytest.mark.skipif(not NAVEGADOR, reason="so com NF_TESTE_NAVEGADOR=1")


@contextlib.contextmanager
def _pagina(servidor, parear=True, erros=None):
    from patchright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{servidor.server_address[1]}"
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    erros = [] if erros is None else erros
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
        ctx.set_default_timeout(8000)
        page = ctx.new_page()
        page.on("pageerror", lambda erro: erros.append(str(erro)))
        page.goto(base + "/", wait_until="domcontentloaded")
        if parear:
            token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
            page.evaluate("([token]) => localStorage.setItem('painel.token', token)", [token])
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("document.body.classList.contains('pareado')")
        try:
            yield page
        finally:
            nav.close()
    assert not erros, erros


def _abrir_objeto(page, objeto, tela):
    page.locator(f"#obj-{objeto}").wait_for(state="visible")
    page.evaluate("o => document.querySelector('#obj-' + o).click()", objeto)
    page.locator(f"#tela-{tela}:not(.oculto)").wait_for(state="visible")


def _abrir_aba(page, de, para):
    page.evaluate("([de, para]) => document.querySelector("
                  "`#tela-${de} [data-aba-tela='${para}']`).click()", [de, para])
    page.locator(f"#tela-{para}:not(.oculto)").wait_for(state="visible")


def _pc_fora(servidor, monkeypatch):
    """Com `fora["sim"]`, toda /api/ responde 502 em texto: o que o
    `tailscale serve` devolve com o servidor do app parado. (O `page.route`
    do patchright deixava escapar pedidos e a faixa sumia no meio da prova.)"""
    fora = {"sim": False}
    classe = servidor.RequestHandlerClass

    def embrulhar(original):
        def metodo(self):
            if fora["sim"] and self.path.startswith("/api/"):
                corpo = b"Bad Gateway"
                self.send_response(502)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
                return None
            return original(self)
        return metodo

    monkeypatch.setattr(classe, "do_GET", embrulhar(classe.do_GET))
    monkeypatch.setattr(classe, "do_POST", embrulhar(classe.do_POST))
    return fora


# ---------------------------------------------------------------- item 1 e 9
def test_faixa_sem_pc_nao_cobre_as_abas_e_o_titulo_fica_numa_linha(tela_isolada,  # noqa: F811
                                                                    monkeypatch):
    """Item 1: com o PC fora, a faixa "Não consegui falar com o PC" (fixa,
    z-index 21) ficava em cima da fileira de abas do objeto aberto e engolia o
    toque (o patchright: `#aviso subtree intercepts pointer events`). Item 9:
    "Agora · Coordenador" com "sem conexão desde" quebrava o título em duas
    linhas e empurrava tudo para baixo."""
    fora = _pc_fora(tela_isolada, monkeypatch)
    with _pagina(tela_isolada) as page:
        # a carga da Vila assenta antes: um 200 atrasado dela apagaria a faixa
        page.wait_for_load_state("networkidle")
        fora["sim"] = True
        _abrir_objeto(page, "agora", "agora")
        _abrir_aba(page, "agora", "oficina")
        page.locator("#aviso:not(.oculto)").wait_for(state="visible")
        page.wait_for_timeout(500)
        faixa = page.locator("#aviso").bounding_box()
        abas = page.locator("#tela-oficina .abas-objeto").bounding_box()
        assert abas["y"] >= faixa["y"] + faixa["height"] - 1, (faixa, abas)
        page.screenshot(path=str(CAPTURAS / "auditoria-faixa-sem-pc-390x844.png"))
        # o toque de verdade: o patchright recusa se outro elemento o intercepta
        page.locator("#tela-oficina [data-aba-tela='coordenador']").click(timeout=3000)
        page.locator("#tela-coordenador:not(.oculto)").wait_for(state="visible")
        page.wait_for_timeout(500)
        assert "off" in (page.locator("#conexao").get_attribute("class") or "")
        titulo = page.locator("#titulo").bounding_box()
        assert titulo["height"] < 30, titulo                       # uma linha só
        cabeca = page.locator("header").bounding_box()
        faixa = page.locator("#aviso").bounding_box()
        abas = page.locator("#tela-coordenador .abas-objeto").bounding_box()
        assert faixa["y"] >= cabeca["y"] + cabeca["height"] - 1, (cabeca, faixa)
        assert abas["y"] >= faixa["y"] + faixa["height"] - 1, (faixa, abas)
        page.screenshot(path=str(CAPTURAS / "auditoria-faixa-sem-pc-coordenador-390x844.png"))
        # o PC voltou: a faixa some e o objeto volta ao lugar
        fora["sim"] = False
        page.locator("#btn-tentar").click(timeout=3000)
        page.locator("#aviso.oculto").wait_for(state="attached")
        page.wait_for_timeout(300)
        abas = page.locator("#tela-coordenador .abas-objeto").bounding_box()
        assert abas["y"] < faixa["y"] + faixa["height"] - 1, abas  # subiu de volta


# ---------------------------------------------------------------- item 3
def test_cinema_diz_carregando_enquanto_a_lista_nao_chega(tela_isolada, monkeypatch):  # noqa: F811
    """Item 3: o /api/videos frio leva 11-30 s e o Cinema ficava em branco."""
    def lento(n=40):
        time.sleep(3)
        return []
    monkeypatch.setattr(painel_dados, "videos", lento)
    with _pagina(tela_isolada) as page:
        _abrir_objeto(page, "ver", "videos")
        page.wait_for_function("() => document.querySelector('#videos')"
                               ".innerText.includes('carregando os vídeos')", timeout=1500)
        page.screenshot(path=str(CAPTURAS / "auditoria-cinema-carregando-390x844.png"))
        page.wait_for_function("() => document.querySelector('#videos')"
                               ".innerText.includes('nenhum vídeo pronto')", timeout=8000)
        assert "carregando" not in page.locator("#videos").inner_text()


# ---------------------------------------------------------------- item 4
def test_a_vila_so_pede_o_icone_dos_objetos_que_tem_arte(tela_isolada, monkeypatch):  # noqa: F811
    """Item 4: 4 x 404 em /arte-vila/atelie/objetos/*.png a cada carga do
    mundo. Agora o mundo diz quais têm folha e só esses são pedidos."""
    from remoto import vila_nova
    monkeypatch.setattr(vila_nova, "mundo", lambda: {
        "retrato": {"escala": 1, "versao": "teste"}, "versao": "teste",
        "objetos_do_atelie": ["mandar"]})
    pedidos = []
    with _pagina(tela_isolada) as page:
        page.wait_for_timeout(2500)                         # a carga do pareamento assenta
        page.on("request", lambda r: pedidos.append(r.url.split("?", 1)[0])
                if "/arte-vila/atelie/objetos/" in r.url else None)
        page.reload(wait_until="domcontentloaded")          # uma carga, contada inteira
        page.wait_for_function("document.body.classList.contains('pareado')")
        page.wait_for_timeout(2500)
        assert page.locator("#obj-agora").is_visible()
    assert [p.rsplit("/", 1)[-1] for p in pedidos] == ["mandar.png"], pedidos


# ---------------------------------------------------------------- item 5
def test_o_que_falta_mostra_a_busca_o_caminho_certo_e_filtra(tela_isolada):  # noqa: F811
    """Item 5: "O que falta" com um estado aberto deixava o caminho velho
    ("Lutador › Assassino › Base") e a busca escondida, sem filtro possível."""
    with _pagina(tela_isolada) as page:
        _abrir_objeto(page, "arena", "arena")
        _abrir_aba(page, "arena", "atelie")
        page.locator("#anim-grupos button").first.wait_for(state="visible")
        page.locator("#anim-grupos button").first.click()
        page.locator("#anim-lista .anim-peca").first.click()
        page.locator("#anim-lista button").first.click()          # um estado aberto
        assert page.locator("#anim-busca").is_hidden()
        page.locator("#anim-faltam").click()
        page.locator("#anim-busca").wait_for(state="visible")
        assert page.locator("#anim-caminho").inner_text() == "O que falta desenhar"
        lista = page.locator("#anim-lista")
        assert lista.locator("h2").first.inner_text() == "O que falta desenhar"
        todos = lista.locator("button").count()
        assert todos > 1
        primeiro = lista.locator("button").first.inner_text()
        page.screenshot(path=str(CAPTURAS / "auditoria-atelie-faltam-390x844.png"))
        termo = primeiro.split(" › ")[-1]
        page.locator("#anim-busca").fill(termo)
        page.wait_for_timeout(200)
        assert lista.locator("h2").first.inner_text() == "O que falta desenhar"
        filtrados = lista.locator("button").count()
        assert 1 <= filtrados < todos, (filtrados, todos)
        assert all(termo.lower() in t.lower()
                   for t in lista.locator("button").all_inner_texts())
        page.screenshot(path=str(CAPTURAS / "auditoria-atelie-faltam-busca-390x844.png"))
        # tocar num grupo sai do "O que falta"
        page.locator("#anim-busca").fill("")
        page.locator("#anim-grupos button").first.click()
        assert lista.locator(".anim-peca").count() > 0
        assert page.locator("#anim-caminho").inner_text() != "O que falta desenhar"


# ---------------------------------------------------------------- item 7
def test_previa_do_godot_para_ao_sair_e_retoma_ao_voltar(tela_isolada):  # noqa: F811
    """Item 7: a consulta da prévia (a cada 3 s) seguia com o Ateliê fechado,
    e o `atelieParar` era vazio. Agora sair para a consulta e voltar retoma o
    MESMO trabalho, sem perder o resultado (o Godot leva ~1 min)."""
    consultas = []
    pronto = {"sim": False}

    def godot(rota):
        pedido = rota.request
        if pedido.method == "POST":
            return rota.fulfill(json={"id": "trabalho-de-teste", "situacao": "rodando"})
        consultas.append(pedido.url)
        if pronto["sim"]:
            return rota.fulfill(json={"situacao": "pronto", "video": "/v/inexistente.mp4"})
        return rota.fulfill(json={"situacao": "rodando"})

    with _pagina(tela_isolada) as page:
        page.route("**/api/animacoes/previa-godot**", godot)
        page.route("**/v/inexistente.mp4", lambda rota: rota.fulfill(status=204))
        _abrir_objeto(page, "arena", "arena")
        _abrir_aba(page, "arena", "atelie")
        page.locator("#anim-grupos button").first.wait_for(state="visible")
        page.locator("#anim-grupos button").first.click()
        page.locator("#anim-lista .anim-peca").first.click()
        page.locator("#anim-lista button").first.click()
        page.locator("#anim-lista .anim-cartao-abrir").first.click()
        page.locator("#anim-editor:not(.oculto)").wait_for(state="visible")
        assert page.locator("#anim-godot").inner_text() == "Ver no Godot"
        page.locator("#anim-godot").click()
        page.wait_for_timeout(500)
        assert len(consultas) == 1
        page.locator("#btn-voltar").click()                        # volta à Vila
        page.locator("#tela-atelie.oculto").wait_for(state="attached")
        page.wait_for_timeout(7000)                                # 2 ciclos de 3 s
        assert len(consultas) == 1, consultas                      # parou
        pronto["sim"] = True
        _abrir_objeto(page, "arena", "atelie")                     # volta ao Ateliê
        page.locator(".anim-video-godot video").wait_for(state="attached", timeout=8000)
        assert len(consultas) == 2, consultas                      # retomou o mesmo
        assert all(c.endswith("/previa-godot/trabalho-de-teste") for c in consultas)
        page.screenshot(path=str(CAPTURAS / "auditoria-atelie-previa-retomada-390x844.png"))


# ---------------------------------------------------------------- item 8
def test_parear_com_o_pc_fora_diz_o_que_fazer(tela_isolada):  # noqa: F811
    """Item 8: sem rede aparecia "Failed to fetch"; com o 502 do serve em HTML,
    "Unexpected token '<'"."""
    with _pagina(tela_isolada, parear=False) as page:
        page.locator("#tela-parear:not(.oculto)").wait_for(state="visible")
        page.route("**/api/parear", lambda rota: rota.abort())
        page.locator("#codigo").fill("123456")
        page.locator("#btn-parear").click()
        page.wait_for_function("() => document.querySelector('#parear-msg').innerText !== '…'")
        assert page.locator("#parear-msg").inner_text() == (
            "Não consegui falar com o PC. Confira o Tailscale neste celular.")
        page.screenshot(path=str(CAPTURAS / "auditoria-parear-sem-pc-390x844.png"))
        page.unroute("**/api/parear")
        page.route("**/api/parear", lambda rota: rota.fulfill(
            status=502, body="<html>Bad Gateway</html>", content_type="text/html"))
        page.locator("#btn-parear").click()
        page.wait_for_function("() => document.querySelector('#parear-msg')"
                               ".innerText.includes('502')")
        assert page.locator("#parear-msg").inner_text() == "O PC respondeu com erro 502."


# ---------------------------------------------------------------- item 10
def test_continuar_espera_a_lista_de_builds(tela_isolada, monkeypatch):  # noqa: F811
    """Item 10: o "Continuar" do diálogo ficava ativo com a lista em
    "carregando…" e o pedido saía com `geracao: ""` (409). O diálogo é
    CANCELADO no fim: nenhuma ação sai."""
    def lento(n=40):
        time.sleep(2)
        return [{"canal": "builds", "id": "generation_00099", "titulo": "t", "perfil": "",
                 "origem": "", "variante": "", "parte": None, "partes": None,
                 "bytes": 1, "quando": 1.0, "pendencias": []}]
    monkeypatch.setattr(painel_dados, "videos", lento)
    monkeypatch.setattr(tela_isolada.RequestHandlerClass.estado, "com_acoes", True)
    acoes = []
    with _pagina(tela_isolada) as page:
        page.on("request", lambda r: acoes.append(r.url) if "/api/acao" in r.url
                and r.method == "POST" else None)
        _abrir_objeto(page, "mandar", "comandos")
        page.locator("[data-acao='rerender'] button").first.click()
        page.locator("#dialogo-campos[open]").wait_for(state="attached")
        assert page.locator("#btn-campos-ok").is_disabled()
        page.screenshot(path=str(CAPTURAS / "auditoria-dialogo-carregando-390x844.png"))
        page.wait_for_function("() => !document.querySelector('#btn-campos-ok').disabled",
                               timeout=8000)
        assert page.locator("#campos-corpo select").input_value() == "generation_00099"
        page.locator("#dialogo-campos button[value='cancelar']").click()
        page.locator("#dialogo-campos:not([open])").wait_for(state="attached")
    assert not acoes, acoes
