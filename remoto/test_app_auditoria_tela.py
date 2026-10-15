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
def _pagina(servidor, parear=True, erros=None, tema="light", tamanho=(390, 844)):
    from patchright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{servidor.server_address[1]}"
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    erros = [] if erros is None else erros
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": tamanho[0], "height": tamanho[1]},
                              is_mobile=True, has_touch=True, service_workers="block",
                              color_scheme=tema)
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
        # (networkidle nao serve: a Vila consulta o PC em ciclo)
        page.wait_for_timeout(3000)
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
        # a hora da queda aparece inteira (quem encolhe é o título)
        assert page.locator("#conexao").evaluate("c => c.scrollWidth <= c.clientWidth")
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


# ===================================== achados do conferente (14/10, casca v70)
TELAS = [("light", (390, 844)), ("dark", (390, 844)), ("light", (844, 390))]


def _nome(tema, tamanho):
    return f"{'claro' if tema == 'light' else 'escuro'}-{tamanho[0]}x{tamanho[1]}"


def _estilo(locator):
    return locator.evaluate(
        "e => { const s = getComputedStyle(e); return {espaco: s.letterSpacing, "
        "alinhado: s.textAlign, fonte: s.fontSize, largura: e.getBoundingClientRect().width}; }")


@pytest.mark.parametrize("tema,tamanho", TELAS)
def test_busca_e_fps_do_atelie_sem_o_estilo_do_codigo(tela_isolada, tema, tamanho):  # noqa: F811
    """A regra `input {24px; letter-spacing .3em; centro}` era do código de
    pareamento e valia para todo campo: a busca do Ateliê saía
    "n o m e  d a  p e ç a" e o FPS "12", "1 2"."""
    with _pagina(tela_isolada, tema=tema, tamanho=tamanho) as page:
        _abrir_objeto(page, "arena", "arena")
        _abrir_aba(page, "arena", "atelie")
        page.locator("#anim-grupos button").first.wait_for(state="visible")
        page.locator("#anim-faltam").click()
        busca = page.locator("#anim-busca")
        busca.wait_for(state="visible")
        busca.fill("nome da peça")
        estilo = _estilo(busca)
        assert estilo["espaco"] == "normal" and estilo["alinhado"] in ("left", "start"), estilo
        assert estilo["fonte"] == "15px", estilo
        page.screenshot(path=str(CAPTURAS / f"v70-atelie-busca-{_nome(tema, tamanho)}.png"))
        # o FPS mora no editor de uma animação
        busca.fill("")
        page.locator("#anim-grupos button").first.click()
        page.locator("#anim-lista .anim-peca").first.click()
        page.locator("#anim-lista button").first.click()
        page.locator("#anim-lista .anim-cartao-abrir").first.click()
        fps = page.locator("#anim-fps-numero")
        fps.wait_for(state="visible")
        estilo = _estilo(fps)
        assert estilo["espaco"] == "normal" and estilo["alinhado"] in ("left", "start"), estilo
        fps.scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / f"v70-atelie-fps-{_nome(tema, tamanho)}.png"))


@pytest.mark.parametrize("tema,tamanho", TELAS)
def test_o_campo_do_codigo_de_pareamento_continua_igual(tela_isolada, tema, tamanho):  # noqa: F811
    with _pagina(tela_isolada, parear=False, tema=tema, tamanho=tamanho) as page:
        codigo = page.locator("#codigo")
        codigo.wait_for(state="visible")
        codigo.fill("123456")
        estilo = _estilo(codigo)
        assert estilo["fonte"] == "24px" and estilo["alinhado"] == "center", estilo
        assert abs(float(estilo["espaco"].rstrip("px")) - 24 * 0.3) < 0.1, estilo   # .3em
        page.screenshot(path=str(CAPTURAS / f"v70-parear-{_nome(tema, tamanho)}.png"))


def test_faixa_sem_pc_tem_o_mesmo_vao_em_pe_e_deitado(tela_isolada, monkeypatch):  # noqa: F811
    """Conferente, 14/10: deitado (844x390) a faixa terminava em y=118 e as
    abas começavam em y=121 (3 px); em pé o vão era 10 px."""
    fora = _pc_fora(tela_isolada, monkeypatch)
    vaos = {}
    for tamanho in ((390, 844), (844, 390)):
        fora["sim"] = False
        with _pagina(tela_isolada, tamanho=tamanho) as page:
            page.wait_for_timeout(3000)                     # a carga da Vila assenta
            fora["sim"] = True
            _abrir_objeto(page, "agora", "agora")
            _abrir_aba(page, "agora", "coordenador")
            page.locator("#aviso:not(.oculto)").wait_for(state="visible")
            page.wait_for_timeout(500)
            faixa = page.locator("#aviso").bounding_box()
            abas = page.locator("#tela-coordenador .abas-objeto").bounding_box()
            vaos[tamanho] = abas["y"] - (faixa["y"] + faixa["height"])
            page.screenshot(path=str(CAPTURAS / f"v70-faixa-vao-{tamanho[0]}x{tamanho[1]}.png"))
    em_pe, deitado = vaos[(390, 844)], vaos[(844, 390)]
    assert 8 <= em_pe <= 12 and abs(em_pe - deitado) <= 1, vaos


@pytest.mark.parametrize("tema,tamanho", TELAS)
def test_coordenador_com_o_pc_fora_diz_que_os_dados_estao_indisponiveis(  # noqa: F811
        tela_isolada, monkeypatch, tema, tamanho):
    """Conferente, 14/10: com o PC fora, TRABALHO, SERVIÇOS e O QUE ACONTECEU
    ficavam em branco, como se não houvesse nada."""
    fora = _pc_fora(tela_isolada, monkeypatch)
    with _pagina(tela_isolada, tema=tema, tamanho=tamanho) as page:
        page.wait_for_timeout(3000)
        fora["sim"] = True
        _abrir_objeto(page, "agora", "agora")
        _abrir_aba(page, "agora", "coordenador")
        page.wait_for_function("() => document.querySelector('#coord-topo')"
                               ".innerText.includes('SEM DADOS')", timeout=8000)
        for cartao in ("#coord-trabalho", "#coord-servicos", "#coord-eventos"):
            texto = page.locator(cartao).inner_text()
            assert texto.startswith("Dados indisponíveis:") and "servidor do app" in texto, texto
        page.screenshot(path=str(CAPTURAS / f"v70-coordenador-sem-pc-{_nome(tema, tamanho)}.png"),
                        full_page=True)
        # o PC volta: o retrato de verdade substitui o aviso
        fora["sim"] = False
        page.locator("#btn-tentar").click(timeout=3000)
        page.wait_for_function("() => !document.querySelector('#coord-topo')"
                               ".innerText.includes('SEM DADOS')", timeout=8000)
        assert "servidor do app" not in page.locator("#coord-servicos").inner_text()


# ===================================== achados do conferente (14/10, casca v71)
@pytest.mark.parametrize("tema,tamanho", TELAS)
def test_coordenador_com_o_pc_ligado_e_sem_eventos_nao_fica_em_branco(  # noqa: F811
        tela_isolada, tema, tamanho):
    """Conferente, 14/10 (v70): com o PC LIGADO e `eventos` vazio, o cartão
    O QUE ACONTECEU ficava em branco (e o de Serviços também, sem serviço
    publicado). Cartão vazio parece defeito; o certo é dizer que não houve
    nada, e desde quando. O retrato da prova (`tela_isolada`) é o do
    coordenador recém-ligado: `servicos {}` e `eventos []`."""
    with _pagina(tela_isolada, tema=tema, tamanho=tamanho) as page:
        _abrir_objeto(page, "agora", "agora")
        _abrir_aba(page, "agora", "coordenador")
        page.wait_for_function("() => document.querySelector('#coord-topo')"
                               ".innerText.includes('NO AR')", timeout=8000)
        eventos = page.locator("#coord-eventos").inner_text().strip()
        assert eventos.startswith("Nada de novo desde "), eventos
        hora = eventos.removeprefix("Nada de novo desde ")[:5]
        assert hora[2] == ":" and hora.replace(":", "").isdigit(), eventos
        servicos = page.locator("#coord-servicos").inner_text().strip()
        assert servicos == "Nenhum serviço publicado pelo coordenador.", servicos
        assert page.locator("#coord-trabalho").inner_text().strip()
        for cartao in ("#coord-trabalho", "#coord-servicos", "#coord-eventos"):
            assert "Dados indisponíveis" not in page.locator(cartao).inner_text()
        page.locator("#coord-eventos").scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / f"v71-coordenador-com-pc-{_nome(tema, tamanho)}.png"),
                        full_page=True)


@pytest.mark.parametrize("tamanho", [(390, 844), (844, 390)])
def test_faixa_sem_pc_tem_o_mesmo_vao_na_agora_e_no_coordenador(  # noqa: F811
        tela_isolada, monkeypatch, tamanho):
    """Conferente, 14/10 (v70): na aba Agora o vão entre a faixa "sem
    conexão" e as abas era 22 px, por causa da moldura de 12 px do mapa
    (`.livro.mesa`); no Coordenador, 10 px. Em pé e deitado."""
    fora = _pc_fora(tela_isolada, monkeypatch)
    vaos = {}
    with _pagina(tela_isolada, tamanho=tamanho) as page:
        page.wait_for_timeout(3000)                         # a carga da Vila assenta
        fora["sim"] = True
        _abrir_objeto(page, "agora", "agora")
        for tela in ("agora", "coordenador"):
            if tela != "agora":
                _abrir_aba(page, "agora", tela)
            page.locator("#aviso:not(.oculto)").wait_for(state="visible")
            page.wait_for_timeout(500)
            faixa = page.locator("#aviso").bounding_box()
            abas = page.locator(f"#tela-{tela} .abas-objeto").bounding_box()
            vaos[tela] = abas["y"] - (faixa["y"] + faixa["height"])
            page.screenshot(path=str(
                CAPTURAS / f"v71-faixa-vao-{tela}-{tamanho[0]}x{tamanho[1]}.png"))
        # o PC voltou: sem a faixa, a Agora volta ao lugar de sempre. Desde a
        # v72 é o mesmo das outras telas (7,7 px deitado, 13,7 em pé; ver
        # test_sem_faixa_a_agora_tem_o_mesmo_vao_que_o_coordenador); aqui só
        # que as abas não ficam embaixo do cabeçalho
        fora["sim"] = False
        _abrir_aba(page, "coordenador", "agora")
        # o ciclo da própria página pode achar o PC antes do toque: aí a faixa
        # já sumiu e não há o que tocar
        page.evaluate("() => { const b = document.querySelector('#btn-tentar');"
                      " if (b && b.offsetParent) b.click(); }")
        page.locator("#aviso.oculto").wait_for(state="attached")
        page.wait_for_timeout(300)
        topo = page.locator("#tela-agora .abas-objeto").bounding_box()["y"]
        cabeca = page.locator("header").bounding_box()
        assert topo - (cabeca["y"] + cabeca["height"]) >= 5, (topo, cabeca)
    assert 8 <= vaos["agora"] <= 12 and abs(vaos["agora"] - vaos["coordenador"]) <= 1, vaos


@pytest.mark.parametrize("tema,tamanho", TELAS)
def test_caixinhas_do_editor_ao_lado_do_rotulo_e_tocaveis(tela_isolada, tema, tamanho):  # noqa: F811
    """Conferente, 14/10 (v70): "Repetir / Ida e volta / Espelhar" saíam com a
    caixinha EM CIMA do texto (a regra comum `input {width: 100%}` valia para
    o checkbox). Caixa e rótulo na mesma linha, e o alvo inteiro (o rótulo)
    com ≥ 40 px de altura; tocar no texto marca e desmarca."""
    with _pagina(tela_isolada, tema=tema, tamanho=tamanho) as page:
        _abrir_objeto(page, "arena", "arena")
        _abrir_aba(page, "arena", "atelie")
        page.locator("#anim-grupos button").first.wait_for(state="visible")
        page.locator("#anim-grupos button").first.click()
        page.locator("#anim-lista .anim-peca").first.click()
        page.locator("#anim-lista button").first.click()
        page.locator("#anim-lista .anim-cartao-abrir").first.click()
        page.locator("#anim-editor:not(.oculto)").wait_for(state="visible")
        page.locator("#anim-loop").scroll_into_view_if_needed()
        for caixa in ("#anim-loop", "#anim-ida-volta", "#anim-espelho", "#anim-auto", "#anim-grade"):
            entrada = page.locator(caixa)
            rotulo = page.locator(f"label:has({caixa})")
            c, r = entrada.bounding_box(), rotulo.bounding_box()
            meio_c, meio_r = c["y"] + c["height"] / 2, r["y"] + r["height"] / 2
            assert abs(meio_c - meio_r) <= 4, (caixa, c, r)        # mesma linha
            assert c["width"] <= 30, (caixa, c)                    # caixinha, não faixa
            assert r["height"] >= 40, (caixa, r)                   # alvo de dedo
            assert r["height"] < 2 * 40, (caixa, r)                # uma linha só
        for caixa in ("#anim-loop", "#anim-ida-volta", "#anim-espelho"):
            entrada = page.locator(caixa)
            antes = entrada.is_checked()
            page.locator(f"label:has({caixa})").click(position={"x": 60, "y": 20})
            assert entrada.is_checked() != antes, caixa
            page.locator(f"label:has({caixa})").click(position={"x": 60, "y": 20})
            assert entrada.is_checked() == antes, caixa
        page.screenshot(path=str(CAPTURAS / f"v71-atelie-caixinhas-{_nome(tema, tamanho)}.png"))


# ===================================== achados do conferente (14/10, casca v72)
# As capturas saem ANTES das contas: rodando a prova no código de antes, elas
# mostram o defeito (era assim que a prova da v72 foi medida).
def _tentar_de_novo(page):
    """O "Tentar de novo" da faixa, se ela estiver à vista: o ciclo da página
    (10 s na Agora) pode já ter achado o PC antes do toque."""
    page.evaluate("() => { const b = document.querySelector('#btn-tentar');"
                  " if (b && b.offsetParent) b.click(); }")


@pytest.mark.parametrize("tema,tamanho", TELAS)
def test_agora_com_o_pc_fora_diz_sem_dados_e_o_coordenador_fora_do_ar(  # noqa: F811
        tela_isolada, monkeypatch, tema, tamanho):
    """Conferente, 14/10 (v71): com o PC fora, RODANDO AGORA e AGENTES ficavam
    vazios e a linha "Coordenador: carregando…" para sempre (o `orqCarregar`
    só chamava a `conexao` no erro). E com a Agora já carregada, a linha
    seguia "no ar · N/N serviços ok", o retrato velho como se fosse atual."""
    fora = _pc_fora(tela_isolada, monkeypatch)
    nome = _nome(tema, tamanho)
    # v72 (2ª rodada): o diagnóstico é o da faixa; com 502, "servidor parado"
    sem_dados = "sem dados — o servidor do app está parado no PC"
    with _pagina(tela_isolada, tema=tema, tamanho=tamanho) as page:
        page.wait_for_timeout(3000)                         # a carga da Vila assenta
        # 1) o PC cai antes de a Agora carregar (a prova 6 do conferente)
        fora["sim"] = True
        _abrir_objeto(page, "agora", "agora")
        page.locator("#aviso:not(.oculto)").wait_for(state="visible")
        page.wait_for_timeout(1500)
        page.locator("#orq-sec-agora").scroll_into_view_if_needed()   # deitado fica embaixo
        page.screenshot(path=str(CAPTURAS / f"v72-agora-pc-fora-{nome}.png"))
        page.wait_for_function(
            "t => document.querySelector('#orq-agora').innerText.includes(t)", arg=sem_dados,
            timeout=12000)
        for alvo in ("#orq-principal", "#orq-agora"):
            assert sem_dados in page.locator(alvo).inner_text(), alvo
        linha = page.locator("#coord-mesa")
        assert linha.inner_text().startswith("Coordenador: sem dados — o servidor do app")
        assert "FORA DO AR" not in linha.inner_text() and "carregando" not in linha.inner_text()
        assert "velho" in (linha.get_attribute("class") or "")
        # 2) o PC volta: o retrato de verdade substitui o aviso
        fora["sim"] = False
        _tentar_de_novo(page)
        page.wait_for_function("() => document.querySelector('#coord-mesa')"
                               ".innerText.includes('no ar')", timeout=15000)
        page.wait_for_function("t => !document.querySelector('#orq-agora').innerText.includes(t)",
                               arg=sem_dados, timeout=15000)
        assert "velho" not in (linha.get_attribute("class") or "")
        # 3) cai de novo, com a Agora carregada: nada do "no ar" velho
        fora["sim"] = True
        page.wait_for_function(
            "t => document.querySelector('#orq-agora').innerText.includes(t)", arg=sem_dados,
            timeout=15000)
        page.wait_for_timeout(300)
        page.locator("#orq-sec-agora").scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / f"v72-agora-pc-caiu-{nome}.png"))
        agentes = page.locator("#orq-agora").inner_text()
        assert "(último dado às " in agentes, agentes
        hora = agentes.split("(último dado às ", 1)[1][:5]
        assert hora[2] == ":" and hora.replace(":", "").isdigit(), agentes
        assert "no ar ·" not in linha.inner_text() and "sem dados" in linha.inner_text()
        assert "(último às " in linha.inner_text(), linha.inner_text()
        assert "velho" in (linha.get_attribute("class") or "")
        assert not page.locator("#orq-resumo").inner_text().strip()   # as vagas velhas saem


def _abrir_editor_do_atelie(page):
    _abrir_objeto(page, "arena", "arena")
    _abrir_aba(page, "arena", "atelie")
    page.locator("#anim-grupos button").first.wait_for(state="visible")
    page.locator("#anim-grupos button").first.click()
    page.locator("#anim-lista .anim-peca").first.click()
    page.locator("#anim-lista button").first.click()
    page.locator("#anim-lista .anim-cartao-abrir").first.click()
    page.locator("#anim-editor:not(.oculto)").wait_for(state="visible")
    page.wait_for_timeout(300)


@pytest.mark.parametrize("tema,tamanho", TELAS)
def test_escolher_folha_e_botao_e_a_folha_vazia_nao_abre_buraco(  # noqa: F811
        tela_isolada, tmp_path, tema, tamanho):
    """Conferente, 14/10 (v71): "Escolher folha" era texto solto com alvo de
    20 px (o `label.acao` do input de arquivo não ganhava o visual de botão),
    e antes de escolher a folha o `#anim-folha-canvas` abria 180 px
    transparentes entre os campos e a prévia."""
    from PIL import Image

    with _pagina(tela_isolada, tema=tema, tamanho=tamanho) as page:
        _abrir_editor_do_atelie(page)
        botao = page.locator("label.anim-enviar")
        botao.scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / f"v72-atelie-sem-folha-{_nome(tema, tamanho)}.png"))
        caixa = botao.bounding_box()
        estilo = botao.evaluate(
            "e => { const s = getComputedStyle(e); return {borda: s.borderTopWidth,"
            " estilo: s.borderTopStyle, fundo: s.backgroundColor, cursor: s.cursor}; }")
        assert caixa["height"] >= 44, caixa                         # alvo de dedo
        assert estilo["borda"] == "1px" and estilo["estilo"] == "solid", estilo
        assert estilo["fundo"] not in ("rgba(0, 0, 0, 0)", "transparent"), estilo
        assert estilo["cursor"] == "pointer", estilo
        # o mesmo visual dos botões do editor
        assert botao.evaluate("e => getComputedStyle(e).borderRadius") == \
            page.locator("#anim-claro").evaluate("e => getComputedStyle(e).borderRadius")
        # sem folha: nada de buraco entre os campos e a prévia
        folha = page.locator("#anim-folha-canvas")
        assert not folha.is_visible()
        if tamanho[0] < tamanho[1]:                                 # em pé: uma coluna
            campos = page.locator("#anim-espaco").bounding_box()    # a última fileira
            previa = page.locator("#anim-canvas").bounding_box()
            assert previa["y"] - (campos["y"] + campos["height"]) < 40, (campos, previa)
        # tocar abre o seletor de arquivo (o rótulo é o alvo)
        with page.expect_file_chooser(timeout=3000) as escolha:
            botao.click()
        imagem = tmp_path / "folha.png"
        folha_png = Image.new("RGBA", (96, 32), (0, 0, 0, 0))        # 3 quadros num fundo vazio
        for n in range(3):
            folha_png.paste((200, 40, 40, 255), (n * 32 + 6, 6, n * 32 + 26, 26))
        folha_png.save(imagem)
        escolha.value.set_files(str(imagem))
        page.wait_for_function("() => !document.querySelector('#anim-folha-canvas').hidden",
                               timeout=8000)
        folha.scroll_into_view_if_needed()
        assert folha.is_visible() and folha.bounding_box()["height"] > 50
        page.screenshot(path=str(CAPTURAS / f"v72-atelie-com-folha-{_nome(tema, tamanho)}.png"))


@pytest.mark.parametrize("tamanho", [(390, 844), (844, 390)])
def test_sem_faixa_a_agora_tem_o_mesmo_vao_que_o_coordenador(tela_isolada, tamanho):  # noqa: F811
    """Conferente, 14/10 (v71): sem a faixa "sem conexão", a Agora ficava 12 px
    mais baixa que as outras (vão do topo às abas 25,7 contra 13,7 px no
    Coordenador; deitado 19,7 contra 7,7): a moldura de 12 px do mapa
    (`.livro.mesa`) somava ao padding."""
    vaos = {}
    with _pagina(tela_isolada, tamanho=tamanho) as page:
        _abrir_objeto(page, "agora", "agora")
        for tela in ("agora", "coordenador"):
            if tela != "agora":
                _abrir_aba(page, "agora", tela)
            page.wait_for_timeout(700)                      # a animação de abrir
            assert not page.locator("#aviso").is_visible()
            cabeca = page.locator("header").bounding_box()
            abas = page.locator(f"#tela-{tela} .abas-objeto").bounding_box()
            vaos[tela] = abas["y"] - (cabeca["y"] + cabeca["height"])
            page.screenshot(path=str(
                CAPTURAS / f"v72-sem-faixa-vao-{tela}-{tamanho[0]}x{tamanho[1]}.png"))
    assert abs(vaos["agora"] - vaos["coordenador"]) <= 1, vaos
    assert vaos["agora"] >= 5, vaos                       # as abas não somem sob o topo


# ========================== achados do conferente na v72 (14/10, 2ª rodada)
TELAS4 = [("light", (390, 844)), ("dark", (390, 844)), ("light", (844, 390)), ("dark", (844, 390))]
SERVIDOR_PARADO = "o servidor do app está parado no PC"
BOTOES_DE_ACAO = ("#orq-adicionar-fila", "#orq-pausar-fila", "#orq-retomar-fila", "#orq-menos",
                  "#orq-mais", "#orq-teto", "#orq-forca", "#pedido-enviar")


def _desligado(page, alvo):
    return page.locator(alvo).evaluate("e => e.disabled")


@pytest.mark.parametrize("tema,tamanho", TELAS4)
def test_com_o_pc_fora_fila_resumos_e_pedidos_dizem_sem_dados_e_os_botoes_desligam(  # noqa: F811
        tela_isolada, monkeypatch, tema, tamanho):
    """Conferente, 14/10 (v72): com o PC fora, a Fila ("▶ fila andando / A
    fila está vazia" com Pôr na fila/Pausar/Retomar ativos), a lista do PEDIR
    e os resumos de Capacidade e Modelos seguiam com o dado de antes da queda
    como se fosse de agora. E a mesma tela dizia "o servidor do app está
    parado" (faixa) e "PC fora do ar" / "Coordenador: FORA DO AR" (Agora)."""
    fora = _pc_fora(tela_isolada, monkeypatch)
    nome = _nome(tema, tamanho)
    with _pagina(tela_isolada, tema=tema, tamanho=tamanho) as page:
        _abrir_objeto(page, "agora", "agora")
        page.wait_for_function("() => document.querySelector('#orq-fila-situacao')"
                               ".innerText.includes('fila andando')", timeout=15000)
        page.wait_for_function("() => document.querySelector('#pedido-estado').innerText.trim()",
                               timeout=15000)
        fora["sim"] = True
        page.locator("#aviso:not(.oculto)").wait_for(state="visible", timeout=20000)
        page.wait_for_timeout(11000)                         # um ciclo inteiro da Agora
        page.locator("#orq-sec-fila").scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / f"v72b-caiu-fila-{nome}.png"))
        page.locator("#pedir-cartao").scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / f"v72b-caiu-agora-topo-{nome}.png"))
        # um diagnóstico só na tela: o da faixa
        assert "servidor do app está parado" in page.locator("#aviso").inner_text()
        agora = page.locator("#tela-agora").inner_text()
        assert "PC fora do ar" not in agora and "FORA DO AR" not in agora, agora
        for alvo in ("#orq-fila-situacao", "#pedido-estado", "#orq-capacidade-resumo",
                     "#orq-modelos-resumo", "#orq-limites-resumo", "#orq-agora"):
            texto = page.locator(alvo).inner_text()
            assert texto.startswith(f"sem dados — {SERVIDOR_PARADO}"), (alvo, texto)
        assert "(último dado às " in page.locator("#orq-fila-situacao").inner_text()
        assert "fila está vazia" not in page.locator("#orq-fila").inner_text()
        assert page.locator("#coord-mesa").inner_text().startswith(
            f"Coordenador: sem dados — {SERVIDOR_PARADO}")
        for botao in BOTOES_DE_ACAO:
            assert _desligado(page, botao), botao
        assert not _desligado(page, "#pedido-conversa")        # só navega
        # a aba Coordenador diz a mesma coisa
        _abrir_aba(page, "agora", "coordenador")
        page.wait_for_function("() => document.querySelector('#coord-topo')"
                               ".innerText.includes('SEM DADOS')", timeout=8000)
        assert SERVIDOR_PARADO.lower() in page.locator("#coord-topo").inner_text().lower()
        # o PC volta: dado de verdade e os botões religados
        fora["sim"] = False
        _abrir_aba(page, "coordenador", "agora")
        _tentar_de_novo(page)
        page.wait_for_function("() => document.querySelector('#orq-fila-situacao')"
                               ".innerText.includes('fila andando')", timeout=15000)
        for botao in ("#orq-adicionar-fila", "#orq-pausar-fila", "#orq-retomar-fila",
                      "#pedido-enviar"):
            assert not _desligado(page, botao), botao
        assert not page.locator("#orq-capacidade-resumo").inner_text().startswith("sem dados")


def test_fora_do_ar_so_quando_o_coordenador_responde_que_nao_esta_vivo(tela_isolada):  # noqa: F811
    """FORA DO AR é afirmação: só quando o /api/coordenador responde `vivo:
    false` (aqui, o último pulso tem 1 h). Leitura que falha é "sem dados"."""
    import os
    from pathlib import Path

    from remoto.test_app_tela import _coordenador_pulsou

    _coordenador_pulsou(Path(os.environ["LOCALAPPDATA"]), 3600)
    with _pagina(tela_isolada) as page:
        _abrir_objeto(page, "agora", "agora")
        page.wait_for_function("() => document.querySelector('#coord-mesa')"
                               ".innerText.includes('FORA DO AR')", timeout=15000)
        linha = page.locator("#coord-mesa")
        classe = linha.get_attribute("class") or ""
        assert "fora" in classe and "velho" not in classe, classe
        assert "sem dados" not in linha.inner_text()


@pytest.mark.parametrize("tema,tamanho", TELAS4)
def test_editor_deitado_com_folha_deixa_os_controles_no_topo(  # noqa: F811
        tela_isolada, tmp_path, tema, tamanho):
    """Conferente, 14/10 (v72): deitado, com a folha escolhida, "Escolher
    folha" caía de y=109 para y=366: a folha em `grid-row: 1 / span 8`
    esticava as linhas da coluna da direita."""
    from PIL import Image

    nome = _nome(tema, tamanho)
    with _pagina(tela_isolada, tema=tema, tamanho=tamanho) as page:
        _abrir_editor_do_atelie(page)
        titulo = page.locator("#anim-titulo")
        botao = page.locator("label.anim-enviar")
        titulo.scroll_into_view_if_needed()
        antes = botao.bounding_box()["y"] - titulo.bounding_box()["y"]
        imagem = tmp_path / "folha.png"
        folha_png = Image.new("RGBA", (96, 64), (0, 0, 0, 0))     # 3 quadros num fundo vazio
        for n in range(3):
            folha_png.paste((40, 120, 200, 255), (n * 32 + 6, 6, n * 32 + 26, 58))
        folha_png.save(imagem)
        page.locator("#anim-arquivo").set_input_files(str(imagem))
        page.wait_for_function("() => !document.querySelector('#anim-folha-canvas').hidden",
                               timeout=8000)
        page.wait_for_timeout(300)
        titulo.scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / f"v72b-atelie-com-folha-topo-{nome}.png"))
        depois = botao.bounding_box()["y"] - titulo.bounding_box()["y"]
        assert abs(depois - antes) <= 4, (antes, depois)            # não desce com a folha
        if tamanho[0] > tamanho[1]:                                 # deitado: duas colunas
            assert depois < 90, depois                              # logo abaixo do título
            fps = page.locator("#anim-fps-numero").bounding_box()
            folha = page.locator("#anim-folha-canvas").bounding_box()
            assert fps["x"] > folha["x"] + folha["width"], (fps, folha)   # na coluna da direita
