# -*- coding: utf-8 -*-
"""Montar sprites no Chrome do celular, anexando DE VERDADE pelo seletor (06/10/2026).

O conferente reprovou a rodada 2 porque o "change" do seletor de arquivo
entregava o Event no lugar do arquivo: Anexar e Trocar nunca funcionavam,
e a prova de tela anterior so passava porque usava o caminho do "soltar".
Aqui o arquivo entra pelo seletor (set_files), como no telefone, e o
resultado e conferido pelo DOM: cartao "Anexado", miniatura, contadores.
Biblioteca, LOCALAPPDATA e runtime sao temporarios; o Godot so roda de
verdade com NF_TESTE_GODOT=1 (senao um duble devolve a folha).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from remoto import api_http
from remoto.test_app_tela import CAPTURAS, NAVEGADOR, tela_isolada  # noqa: F401 (fixture)

MANIFESTO_REAL = Path(__file__).resolve().parents[1] / "palco" / "biblioteca" / "manifesto_slots.json"


def _png(caminho: Path, cor, miolo=True) -> Path:
    imagem = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    from PIL import ImageDraw
    caneta = ImageDraw.Draw(imagem)
    caneta.ellipse((256, 256, 768, 768), fill=cor) if not miolo else caneta.ellipse((560, 380, 700, 640), fill=cor)
    imagem.save(caminho)
    return caminho


@pytest.fixture
def sprites_isolados(tela_isolada, tmp_path, monkeypatch):
    raiz = tmp_path / "palco" / "biblioteca"
    raiz.mkdir(parents=True)
    (raiz / "manifesto_slots.json").write_bytes(MANIFESTO_REAL.read_bytes())
    monkeypatch.setattr(api_http, "PARTES_BIBLIOTECA", raiz)
    monkeypatch.setattr(api_http, "MANIFESTO_SPRITES", raiz / "manifesto_slots.json")
    monkeypatch.setattr(api_http, "_INDICE_SPRITES",
                        {"chave": None, "base": None, "existe": None, "quando": 0.0, "geracao": 0})
    monkeypatch.setattr(api_http, "_PREVIAS_GODOT", {})
    monkeypatch.setattr(api_http, "_FILA_GODOT", [])
    monkeypatch.setattr(api_http, "_GODOT_OCUPADO", {"alvo": None})
    monkeypatch.setenv("NEURAL_FIGHTS_RUNTIME_DIR", str(tmp_path / "runtime"))
    godot_real = os.environ.get("NF_TESTE_GODOT") == "1" and api_http.GODOT_PREVIA.is_file()
    if not godot_real:
        def rodar(alvo, biblioteca):
            saida = tmp_path / f"folha_{alvo}.png"
            Image.new("RGBA", (540, 960), (27, 30, 39, 255)).save(saida)
            return {"estado": "pronta", "arquivo": str(saida)}
        monkeypatch.setattr(api_http, "_rodar_previa_godot", rodar)
        monkeypatch.setattr(api_http, "GODOT_PREVIA", Path(__file__))
    tela_isolada.RequestHandlerClass.estado.com_acoes = True
    pecas = tmp_path / "pecas"
    pecas.mkdir()
    return {"srv": tela_isolada, "raiz": raiz, "pecas": pecas, "godot_real": godot_real}


def _cartao(page, titulo):
    return page.locator("#modular-slots .modular-slot").filter(
        has=page.locator("strong", has_text=titulo)).first


def _anexar_pelo_seletor(page, cartao, botao, arquivo):
    _quieto(page)
    with page.expect_file_chooser() as escolha:
        cartao.get_by_role("button", name=botao, exact=True).click()
    escolha.value.set_files(str(arquivo))


def _toques_pequenos(page):
    # Uma leitura so, dentro da pagina: nada de elemento trocado no meio.
    _quieto(page)
    return page.locator("#sprites-modulares").evaluate(
        """raiz => [...raiz.querySelectorAll('button, select')]
              .filter(e => e.offsetParent !== null)
              .map(e => [e.innerText || e.id, Math.round(e.getBoundingClientRect().height)])
              .filter(([_, h]) => h < 44)""")


def _quieto(page):
    """Espera a lista terminar de carregar (o servidor ja respondeu)."""
    page.wait_for_function("() => document.querySelector('#modular-carregando').classList.contains('oculto')")
    page.wait_for_timeout(150)


@pytest.mark.parametrize("tema", ["light", "dark"])
def test_anexar_trocar_desfazer_apagar_pelo_seletor_de_verdade(sprites_isolados, tema):
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    srv, pecas = sprites_isolados["srv"], sprites_isolados["pecas"]
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    pele = _png(pecas / "pele.png", (230, 230, 230, 255), miolo=False)
    pele2 = _png(pecas / "pele2.png", (120, 200, 255, 255), miolo=False)
    olhos = _png(pecas / "olhos.png", (20, 20, 26, 255))
    olhos_tonto = _png(pecas / "olhos_tonto.png", (200, 40, 160, 255))
    pasta = CAPTURAS / "sprites"
    pasta.mkdir(parents=True, exist_ok=True)
    erros, dialogos = [], []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                              service_workers="block", color_scheme=tema, device_scale_factor=2)
        ctx.set_default_timeout(15000)
        page = ctx.new_page()
        page.on("pageerror", lambda e: erros.append(str(e)))
        page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
        page.on("dialog", lambda d: (dialogos.append(d.message), d.accept()))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([t]) => localStorage.setItem('painel.token', t)", [token])
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("() => document.body.classList.contains('pareado')")
        page.evaluate("() => document.querySelector('#obj-arena').click()")
        page.locator("#tela-arena:not(.oculto)").wait_for()
        page.evaluate("() => document.querySelector(\"#tela-arena [data-aba-tela='atelie']\").click()")
        _cartao(page, "Pele (o corpo)").wait_for()
        progresso = page.locator("#modular-progresso")
        assert progresso.inner_text().split("\n") == [
            "Lutador básico: 0 de 3", "Rosto que reage: 0 de 14", "Classes com identidade: 0 de 16"]
        page.locator("#modular-hoje").wait_for(state="visible")
        assert "desenho de hoje" in page.locator("#modular-previa-legenda").inner_text()
        assert page.locator("#modular-arquivo").get_attribute("capture") is None
        assert not _toques_pequenos(page), _toques_pequenos(page)
        page.screenshot(path=str(pasta / f"{tema}_01_inicio.png"))

        # 1. Anexar pelo seletor: cartao "Anexado", miniatura e contador.
        cartao = _cartao(page, "Pele (o corpo)")
        assert cartao.get_by_role("button", name="Desfazer").count() == 0     # sem versao, sem Desfazer
        _anexar_pelo_seletor(page, cartao, "Anexar", pele)
        page.wait_for_function("""() => [...document.querySelectorAll('#modular-slots .modular-slot')]
            .some(c => c.innerText.includes('Pele (o corpo)') && c.innerText.includes('Anexado'))""")
        cartao = _cartao(page, "Pele (o corpo)")
        cartao.locator("img.modular-mini").wait_for(state="visible")
        assert cartao.locator("img.modular-mini").evaluate("i => i.complete && i.naturalWidth > 0")
        assert "Lutador básico: 1 de 3" in progresso.inner_text()
        assert "Rosto que reage: 1 de 14" in progresso.inner_text()
        _anexar_pelo_seletor(page, _cartao(page, "Olhos"), "Anexar", olhos)
        page.wait_for_function("() => document.querySelector('#modular-progresso').innerText.includes('básico: 2 de 3')")
        page.wait_for_function("() => !document.querySelector('#modular-previa').classList.contains('oculto')")
        # "Carinha" e feminino (conferente, 06/10).
        page.wait_for_function("() => document.querySelector('#modular-previa-legenda').innerText"
                               ".includes('carinha neutra')")
        page.screenshot(path=str(pasta / f"{tema}_02_anexado.png"))

        # 2. Trocar (pede confirmacao) e Desfazer volta a anterior.
        _anexar_pelo_seletor(page, _cartao(page, "Pele (o corpo)"), "Trocar", pele2)
        page.wait_for_function("() => document.querySelector('#modular-aviso').innerText.includes('trocado')")
        assert any("Trocar pelo novo" in d for d in dialogos)
        _cartao(page, "Pele (o corpo)").get_by_role("button", name="Desfazer").wait_for()
        page.screenshot(path=str(pasta / f"{tema}_03_trocado.png"))
        arquivo = sprites_isolados["raiz"] / "partes/lutador/pele/comum/_/base.png"
        assert Image.open(arquivo).getpixel((512, 512))[:3] == (120, 200, 255)
        _quieto(page)
        _cartao(page, "Pele (o corpo)").get_by_role("button", name="Desfazer").click()
        page.wait_for_function("() => document.querySelector('#modular-aviso').innerText.includes('versão anterior')")
        assert Image.open(arquivo).getpixel((512, 512))[:3] == (230, 230, 230)
        page.screenshot(path=str(pasta / f"{tema}_04_desfeito.png"))

        # 3. Apagar tem volta: some o desenho, o Desfazer aparece e o traz de volta.
        _quieto(page)
        _cartao(page, "Olhos").get_by_role("button", name="Apagar").click()
        page.wait_for_function("() => document.querySelector('#modular-aviso').innerText.includes('apagado')")
        page.wait_for_function("() => document.querySelector('#modular-progresso').innerText.includes('básico: 1 de 3')")
        assert "Vazio" in _cartao(page, "Olhos").inner_text()
        page.screenshot(path=str(pasta / f"{tema}_05_apagado.png"))
        _quieto(page)
        _cartao(page, "Olhos").get_by_role("button", name="Desfazer").click()
        page.wait_for_function("() => document.querySelector('#modular-progresso').innerText.includes('básico: 2 de 3')")

        # 4. As 24 carinhas: 'tonto' e anexavel e fica marcada como escolhida.
        page.wait_for_function("() => document.querySelectorAll('#modular-expressoes button').length === 6")
        page.locator("#modular-todas").click()
        page.wait_for_function("() => document.querySelectorAll('#modular-expressoes button').length === 24")
        page.locator("#modular-expressoes button", has_text="tonto").click()
        escolhida = page.locator("#modular-expressoes button.escolhida")
        assert escolhida.count() == 1 and "tonto" in escolhida.inner_text()
        assert escolhida.get_attribute("aria-pressed") == "true"
        assert "Herdando" in _cartao(page, "Olhos · tonto").inner_text()   # cai no neutro comum
        _anexar_pelo_seletor(page, _cartao(page, "Olhos · tonto"), "Anexar", olhos_tonto)
        page.wait_for_function("""() => [...document.querySelectorAll('#modular-slots .modular-slot')]
            .some(c => c.innerText.includes('Olhos · tonto') && c.innerText.includes('Anexado'))""")
        assert not _toques_pequenos(page), _toques_pequenos(page)
        page.screenshot(path=str(pasta / f"{tema}_06_todas_as_24.png"), full_page=True)

        # 5. Estilo de classe: corrida descartada, cartoes so do estilo pedido.
        page.locator("#modular-alvo").select_option("berserker_furia")
        page.locator("#modular-alvo").select_option("monge_chi")
        page.wait_for_function("""() => [...document.querySelectorAll('#modular-slots .modular-slot')]
            .every(c => c.dataset.slot.includes('/monge_chi/'))
            && document.querySelectorAll('#modular-slots .modular-slot').length > 0""")
        page.wait_for_timeout(600)
        ids = page.locator("#modular-slots .modular-slot").evaluate_all("cs => cs.map(c => c.dataset.slot)")
        assert ids and all("/monge_chi/" in i for i in ids), ids
        page.locator("#modular-alvo").select_option("_")
        _cartao(page, "Pele (o corpo)").wait_for()

        # 6. Ver no Godot: a folha do estilo pedido aparece.
        page.locator("#modular-ver-godot").click()
        page.locator("#modular-folha").wait_for(state="visible", timeout=60000)
        assert page.locator("#modular-folha").evaluate("i => i.complete && i.naturalWidth > 0")
        page.wait_for_timeout(500)
        page.screenshot(path=str(pasta / f"{tema}_07_godot.png"), full_page=True)

        # 7. Trocar de grupo limpa o aviso do grupo anterior (conferente, 06/10).
        assert page.locator("#modular-aviso").inner_text().strip()
        page.locator("#modular-grupo").select_option("arma")
        _quieto(page)
        assert page.locator("#modular-aviso").inner_text().strip() == ""
        assert not erros, erros
        nav.close()
