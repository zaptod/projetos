# -*- coding: utf-8 -*-
"""O recortador e o Provador no Chrome do celular, pelo caminho natural
(reprovação do conferente, 06/10/2026). Tudo pelo SELETOR de arquivo real
(`expect_file_chooser`), conferido pelo DOM e pelo disco:

1. subir a folha realista de 6 pares de olhos com o destino que a tela abre
   (Sombra) -> trocar o destino para "Olhos · neutra" -> a tela junta os
   pares sozinha (6, não 12) -> mandar -> a CAIXA de cada olho no PNG gravado
   é a zona do jogo (CONTRATO 2.3); antes os olhos caíam na zona da sombra;
2. recusar uma folha (fundo azul) não deixa a anterior pronta para mandar;
3. girar e "já visto de cima" pelo seletor do par de olhos;
4. textos: "há", "Mandar para" por peça e com acento, "Recorte N · LxA px ·
   par de olhos", carinha igual no rótulo e no botão, nome do arquivo sem
   letras espaçadas, "Ateliê antigo" com 44 px;
5. Provador: depois de ‹ › o lutador montado continua inteiro na tela, em pé
   e deitado; "Ver no Godot" com o PC ocupado diz que pode levar 1–2 min.
Capturas 390x844 (e 844x390) em <TEMP>/tela_app/recortador/.
"""
from __future__ import annotations

import time

import numpy as np
import pytest
from PIL import Image

from painel.sprites import folha_de_olhos
from remoto import api_http
from remoto.test_app_provador_tela import _abrir_atelie, _quieto, provador_isolado  # noqa: F401 (fixture)
from remoto.test_app_sprites_tela import sprites_isolados  # noqa: F401 (fixture)
from remoto.test_app_tela import CAPTURAS, NAVEGADOR, tela_isolada  # noqa: F401 (fixture)

OLHOS = "lutador/olhos/comum/_/neutro"
OLHO_CIMA = (480, 340, 645, 500)
OLHO_BAIXO = (480, 524, 645, 684)
ZONA_OLHOS = (480, 340, 645, 684)
ZONA_SOMBRA = (256, 532, 768, 748)


def _salvar_folha(caminho, fundo, vao):
    Image.fromarray(folha_de_olhos.folha(fundo, vao), "RGB").save(caminho)
    return caminho


def _caixa(img: np.ndarray):
    ys, xs = np.nonzero(img[..., 3] >= 16)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None


def _dentro(caixa, zona):
    return (caixa is not None and caixa[0] >= zona[0] and caixa[1] >= zona[1]
            and caixa[2] <= zona[2] and caixa[3] <= zona[3])


def _olhos_gravados(raiz, variante):
    arr = np.asarray(Image.open(raiz / f"partes/lutador/olhos/comum/_/{variante}/neutro.png").convert("RGBA"))
    cima, baixo = arr.copy(), arr.copy()
    cima[512:] = 0
    baixo[:512] = 0
    return _caixa(arr), _caixa(cima), _caixa(baixo)


def _variantes(raiz):
    pasta = raiz / "partes/lutador/olhos/comum/_"
    return sorted(p.name for p in pasta.iterdir() if p.name.startswith("v")) if pasta.is_dir() else []


def _subir(page, caminho):
    """Pelo seletor de verdade: o toque no campo abre o seletor do sistema."""
    page.locator("#recortador-folha").scroll_into_view_if_needed()
    page.locator("#recortador-aviso").evaluate("e => { e.textContent = '-'; }")      # marca: a resposta troca
    with page.expect_file_chooser() as escolha:
        page.locator("#recortador-arquivo").click()
    escolha.value.set_files(str(caminho))
    page.wait_for_function("() => !['-', 'recortando no PC…'].includes(document.querySelector('#recortador-aviso').innerText)",
                           timeout=60000)


def _itens(page, n):
    page.wait_for_function("(n) => document.querySelectorAll('#recortador-lista .recortador-item').length === n"
                           " && [...document.querySelectorAll('#recortador-lista img')].every(i => i.complete && i.naturalWidth > 0)",
                           arg=n, timeout=60000)
    return page.locator("#recortador-lista .recortador-item span").all_inner_texts()


def _visivel_inteira(page, seletor):
    """A imagem inteira na tela e por cima de tudo (nada a cobre)."""
    return page.locator(seletor).evaluate("""i => { const r = i.getBoundingClientRect();
        const pontos = [[r.left + r.width / 2, r.top + 4], [r.left + r.width / 2, r.bottom - 4],
                        [r.left + 4, r.top + r.height / 2], [r.left + r.width / 2, r.top + r.height / 2]];
        return {topo: Math.round(r.top), base: Math.round(r.bottom), altura: innerHeight,
                inteira: r.top >= 0 && r.bottom <= innerHeight && r.height > 100,
                por_cima: pontos.every(([x, y]) => document.elementFromPoint(x, y) === i)}; }""")


@pytest.mark.parametrize("tema", ["light", "dark"])
def test_recortador_pelo_caminho_natural_e_provador_preso(provador_isolado, tema, monkeypatch):  # noqa: F811
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    srv, pecas, raiz = provador_isolado["srv"], provador_isolado["pecas"], provador_isolado["raiz"]
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    magenta40 = _salvar_folha(pecas / "folha_magenta_gap40.png", (255, 0, 255), 40)
    verde24 = _salvar_folha(pecas / "folha_verde_gap24.png", (0, 255, 0), 24)
    azul = _salvar_folha(pecas / "folha_azul_gap40.png", (30, 60, 220), 40)
    if not provador_isolado["godot_real"]:
        # o PC ocupado: a folha do Godot demora 10 s (o conferente mediu 62 s)
        def godot_lento(classe, personagem, biblioteca, saida, cor=None):
            time.sleep(10)
            Image.new("RGBA", (540, 960), (27, 30, 39, 255)).save(saida)
            return {"estado": "pronta", "arquivo": str(saida)}
        monkeypatch.setattr(api_http, "_godot_folha", godot_lento)
    pasta = CAPTURAS / "recortador"
    pasta.mkdir(parents=True, exist_ok=True)
    erros, dialogos = [], []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                              service_workers="block", color_scheme=tema, device_scale_factor=2)
        ctx.set_default_timeout(20000)
        page = ctx.new_page()
        page.on("pageerror", lambda e: erros.append(str(e)))
        # O 400 da folha azul é a recusa esperada (o Chrome o loga como erro de recurso).
        page.on("console", lambda m: erros.append(m.text) if m.type == "error" and "400" not in m.text else None)
        page.on("dialog", lambda d: (dialogos.append(d.message), d.accept()))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([t]) => { localStorage.setItem('painel.token', t);"
                      " localStorage.setItem('painel.atelie.modo', 'montar'); }", [token])
        page.reload(wait_until="domcontentloaded")
        _abrir_atelie(page)
        page.locator("#modular-slots .modular-slot").first.wait_for()
        _quieto(page)
        foto = lambda nome, inteira=False: page.screenshot(path=str(pasta / f"{tema}_{nome}.png"), full_page=inteira)  # noqa: E731

        # 4. Textos e toques que o conferente apontou.
        assert page.locator("#modular-expressao-nome").inner_text() == "neutra"
        assert page.locator("#modular-expressoes button[aria-pressed='true']").inner_text() == "✓ neutra"
        resumo = page.locator("#atelie-montar > details > summary")
        assert resumo.evaluate("e => e.getBoundingClientRect().height") >= 44
        assert page.locator("#recortador-arquivo").evaluate("e => getComputedStyle(e).letterSpacing") == "normal"
        destinos = page.locator("#recortador-destino").evaluate(
            "s => [...s.querySelectorAll('optgroup')].map(g => [g.label, [...g.children].map(o => o.textContent)])")
        grupos = dict(destinos)
        assert grupos["Sombra"] == ["Sombra"]
        assert "Olhos · neutra" in grupos["Olhos"] and "Olhos · fúria" in grupos["Olhos"]
        assert "Olhos · pânico" in grupos["Olhos"] and len(grupos["Olhos"]) == 24
        for _, textos in destinos:
            for texto in textos:
                partes = texto.split(" · ")
                assert len(partes) <= 2 and "base" not in partes, texto
        assert page.locator("#recortador-destino").evaluate("s => s.selectedOptions[0].textContent") == "Sombra"
        assert page.locator("#recortador-olhos-caixa").is_hidden()

        # 1. Sobe com o destino que a tela abre (Sombra): 12 recortes crus.
        _subir(page, magenta40)
        textos = _itens(page, 12)
        assert textos[0] == "Recorte 1 · 167×127 px", textos
        aviso = page.locator("#recortador-aviso").inner_text()
        assert aviso.startswith("há bastante magenta"), aviso
        nome_arquivo = page.locator("#recortador-arquivo").evaluate("e => e.files[0].name")
        assert nome_arquivo == "folha_magenta_gap40.png"
        foto("01_sombra_12_recortes")

        # 2. Recusar uma folha não deixa a anterior pronta para mandar.
        _subir(page, azul)
        page.wait_for_function("() => document.querySelector('#recortador-aviso').innerText.includes('verde ou magenta')")
        assert page.locator("#recortador-lista .recortador-item").count() == 0
        assert page.locator("#recortador-folha-caixa").is_hidden()
        page.locator("#recortador-mandar").click()
        page.wait_for_function("() => document.querySelector('#recortador-aviso').innerText.includes('Escolha pelo menos um recorte')")
        assert _variantes(raiz) == []
        foto("02_folha_azul_recusada")

        # 1 (cont.). De novo a folha boa; depois troca o destino para Olhos · neutra.
        _subir(page, magenta40)
        _itens(page, 12)
        page.locator("#recortador-aviso").evaluate("e => { e.textContent = '-'; }")
        page.locator("#recortador-destino").select_option(OLHOS)
        page.wait_for_function("() => !['-', 'recortando no PC…'].includes(document.querySelector('#recortador-aviso').innerText)")
        textos = _itens(page, 6)                     # a tela juntou os pares sozinha
        assert page.locator("#recortador-juncao").input_value() == "pares"
        assert all(t.endswith(" px · par de olhos") for t in textos), textos
        assert textos[0] == "Recorte 1 · 357×127 px · par de olhos", textos
        assert page.locator("#recortador-fundo").inner_text() == "Fundo magenta · 6 pares de olhos"
        assert page.locator("#recortador-olhos-caixa").is_visible()
        assert page.locator("#recortador-olhos").input_value() == "separar"
        page.locator("#recortador-folha").scroll_into_view_if_needed()
        foto("03_olhos_seis_pares")
        page.locator("#recortador-mandar").click()
        page.wait_for_function("() => document.querySelector('#recortador-aviso').innerText"
                               ".includes('6 recortes viraram variantes novas de olhos · neutra')", timeout=60000)
        assert _variantes(raiz) == [f"v{i:02d}" for i in range(1, 7)]
        for variante in _variantes(raiz):
            total, cima, baixo = _olhos_gravados(raiz, variante)
            assert _dentro(cima, OLHO_CIMA), (variante, cima)
            assert _dentro(baixo, OLHO_BAIXO), (variante, baixo)
            assert not _dentro(total, ZONA_SOMBRA)
        _quieto(page)
        page.locator("#recortador-folha").scroll_into_view_if_needed()
        foto("04_mandou_seis")

        # 3. Girar o par (verde, 24 px entre os olhos): só os 2 primeiros.
        _subir(page, verde24)
        textos = _itens(page, 6)
        assert all(t.endswith("par de olhos") for t in textos)
        page.locator("#recortador-olhos").select_option("girar")
        for caixa in page.locator("#recortador-lista input[type=checkbox]").all()[2:]:
            caixa.uncheck()
        page.locator("#recortador-mandar").click()
        page.wait_for_function("() => /viraram|virou|Não deu/.test(document.querySelector('#recortador-aviso').innerText)",
                               timeout=60000)
        assert "2 recortes viraram" in page.locator("#recortador-aviso").inner_text(),             page.locator("#recortador-aviso").inner_text()
        for variante in ("v07", "v08"):
            total, cima, baixo = _olhos_gravados(raiz, variante)
            assert _dentro(total, ZONA_OLHOS), (variante, total)
            assert cima is not None and baixo is not None and cima[3] <= 512 <= baixo[1] + 30, (cima, baixo)
        # "já visto de cima": não mexe, encaixa como veio (continua deitado)
        page.locator("#recortador-olhos").select_option("vista-de-cima")
        for i, caixa in enumerate(page.locator("#recortador-lista input[type=checkbox]").all()):
            caixa.set_checked(i == 0)
        page.locator("#recortador-mandar").click()
        page.wait_for_function("() => document.querySelector('#recortador-aviso').innerText.includes('1 recorte virou')",
                               timeout=60000)
        total, _, _ = _olhos_gravados(raiz, "v09")
        assert _dentro(total, ZONA_OLHOS) and total[2] - total[0] > total[3] - total[1], total
        # saiu dos olhos: volta ao médio sozinho
        page.locator("#recortador-aviso").evaluate("e => { e.textContent = '-'; }")
        page.locator("#recortador-destino").select_option("lutador/sombra/comum/_/base")
        page.wait_for_function("() => !['-', 'recortando no PC…'].includes(document.querySelector('#recortador-aviso').innerText)")
        _itens(page, 12)
        assert page.locator("#recortador-juncao").input_value() == "medio"
        assert page.locator("#recortador-olhos-caixa").is_hidden()
        assert not [t for t in page.locator("#tela-atelie button, #tela-atelie select, #tela-atelie summary").evaluate_all(
            "es => es.filter(e => e.offsetParent !== null).map(e => [e.innerText || e.id, Math.round(e.getBoundingClientRect().height)])"
            ".filter(([_, h]) => h < 44)")]

        # 5. O Provador: o lutador montado continua inteiro na tela depois de ‹ ›.
        page.locator("#atelie-modo-provador").click()
        page.locator("#provador-busca").fill("julia")
        page.locator("#provador-lista .provador-item", has_text="Júlia a Abençoada").click()
        page.locator("#provador-palco-caixa:not(.oculto)").wait_for()
        page.wait_for_function("() => { const i = document.querySelector('#provador-previa'); return i.complete && i.naturalWidth > 0; }")
        assert page.locator("#provador-expressao-nome").inner_text() == "neutra"
        assert page.locator("#provador-expressoes button[aria-pressed='true']").inner_text() == "✓ neutra"
        seta = page.locator("#provador-pecas [data-parte='olhos'] button.provador-seta").last
        seta.scroll_into_view_if_needed()
        seta.click()
        page.wait_for_function("() => document.querySelector('#provador-aviso').innerText.includes('Só na tela')")
        page.wait_for_timeout(400)
        lugar = _visivel_inteira(page, "#provador-previa")
        assert lugar["inteira"] and lugar["por_cima"], lugar
        foto("05_provador_seta_em_pe")

        # 5 (cont.). Ver no Godot com o PC ocupado: a frase de 1–2 min e a folha no fim.
        page.locator("#provador-ver-godot").scroll_into_view_if_needed()
        page.locator("#provador-ver-godot").click()
        if not provador_isolado["godot_real"]:
            page.wait_for_function("() => document.querySelector('#provador-aviso').innerText"
                                   ".includes('o PC está ocupado, pode levar 1–2 min')", timeout=20000)
            foto("06_godot_ocupado")
        page.locator("#provador-folha").wait_for(state="visible", timeout=200000)
        assert "Júlia a Abençoada" in page.locator("#provador-aviso").inner_text()
        ctx.close()

        # Deitado (844x390): a prévia fica na coluna da esquerda, presa.
        ctx = nav.new_context(viewport={"width": 844, "height": 390}, is_mobile=True, has_touch=True,
                              service_workers="block", color_scheme=tema, device_scale_factor=2)
        ctx.set_default_timeout(20000)
        page = ctx.new_page()
        page.on("pageerror", lambda e: erros.append(str(e)))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([t]) => { localStorage.setItem('painel.token', t);"
                      " localStorage.setItem('painel.atelie.modo', 'provador');"
                      " localStorage.setItem('painel.provador.lutador', 'julia_a_abencoada'); }", [token])
        page.reload(wait_until="domcontentloaded")
        _abrir_atelie(page)
        page.locator("#provador-palco-caixa:not(.oculto)").wait_for()
        page.wait_for_function("() => { const i = document.querySelector('#provador-previa'); return i.complete && i.naturalWidth > 0; }")
        seta = page.locator("#provador-pecas [data-parte='olhos'] button.provador-seta").last
        seta.scroll_into_view_if_needed()
        seta.click()
        page.wait_for_function("() => document.querySelector('#provador-aviso').innerText.includes('Só na tela')")
        page.wait_for_timeout(400)
        lugar = _visivel_inteira(page, "#provador-previa")
        assert lugar["inteira"] and lugar["por_cima"], lugar
        page.screenshot(path=str(pasta / f"{tema}_07_provador_seta_deitado.png"))
        ctx.close()
        nav.close()
    assert not erros, erros
