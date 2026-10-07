# -*- coding: utf-8 -*-
"""O recortador e o Provador no Chrome do celular, pelo caminho natural
(reprovação do conferente, 06/10/2026). Tudo pelo SELETOR de arquivo real
(`expect_file_chooser`), conferido pelo DOM e pelo disco:

1. subir a folha realista de 6 pares de olhos com o destino Sombra (a
   armadilha de 06/10, escolhida de propósito) -> trocar a peça para Olhos
   -> a tela junta os pares sozinha (6, não 12) -> mandar -> a CAIXA de cada
   olho no PNG gravado é a zona do jogo (CONTRATO 2.3);
2. recusar uma folha (fundo azul) não deixa a anterior pronta para mandar;
3. girar e "já visto de cima" pelo seletor do par de olhos;
4. textos: "há", "Mandar para" em peça + carinha (07/10: era uma lista de 83
   que abria em Sombra; agora abre nos Olhos), "Recorte N · LxA px · par de
   olhos", carinha igual no rótulo e no botão, nome do arquivo sem letras
   espaçadas, "Ateliê antigo" com 44 px;
5. Provador: depois de ‹ › o lutador montado continua inteiro na tela, em pé
   e deitado; a faixa presa tem <= 22% da tela e a folha do Godot rola para
   logo abaixo dela; "Ver no Godot" com o PC ocupado diz que pode levar 1–2 min;
6. (07/10) folha nova: o destino pelo nome do arquivo, o par de olhos de
   volta ao padrão, o brilho a 12 px desmarcado NOS OLHOS (e inteiro fora
   deles), "Mandar N selecionados", o último destino lembrado, a junção que
   segue o grupo e a galeria com a peça recortada.
Capturas 390x844 (e 844x390) em <TEMP>/tela_app/recortador/.
"""
from __future__ import annotations

import time

import numpy as np
import pytest
from PIL import Image, ImageDraw

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


def _folha_com_brilho(caminho):
    """Duas bocas numa folha magenta e um brilho (faísca de 19 px) a 12 px da
    segunda: o médio (16 px) o juntava à boca, que encolhia no encaixe."""
    imagem = Image.new("RGB", (640, 300), (255, 0, 255))
    caneta = ImageDraw.Draw(imagem)
    for x in (80, 380):
        caneta.chord((x, 120, x + 160, 260), 0, 180, fill=(20, 20, 26))
        caneta.chord((x + 12, 130, x + 148, 245), 0, 180, fill=(190, 40, 60))
    cx, cy, r = 380 + 160 + 12 + 9, 200, 9
    caneta.polygon([(cx, cy - r), (cx + 2, cy - 2), (cx + r, cy), (cx + 2, cy + 2),
                    (cx, cy + r), (cx - 2, cy + 2), (cx - r, cy), (cx - 2, cy - 2)], fill=(255, 255, 240))
    imagem.save(caminho)
    return caminho


def _olhos_com_brilho(caminho):
    """A folha realista de olhos (magenta, vão de 40 px) com uma faísca de
    19 px a 12 px do olho direito do primeiro par."""
    imagem = Image.fromarray(folha_de_olhos.folha((255, 0, 255), 40), "RGB")
    cx, cy, r = 426 + 12 + 9, 216, 9
    ImageDraw.Draw(imagem).polygon([(cx, cy - r), (cx + 2, cy - 2), (cx + r, cy), (cx + 2, cy + 2),
                                    (cx, cy + r), (cx - 2, cy + 2), (cx - r, cy), (cx - 2, cy - 2)],
                                   fill=(255, 255, 240))
    imagem.save(caminho)
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


def _destino(page):
    """(peça, carinha, junção) como a tela mostra."""
    return tuple(page.evaluate("""() => [document.querySelector('#recortador-peca').selectedOptions[0].textContent,
        document.querySelector('#recortador-destino').selectedOptions[0].textContent,
        document.querySelector('#recortador-juncao').value]"""))


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
        # 07/10 (conferente): "Mandar para" era UMA lista de 83 opções aberta
        # em "Sombra". Agora é a peça (6) e depois a carinha dela (6 principais
        # + "Outras"), e a tela abre nos Olhos, na carinha do painel.
        pecas_ = page.locator("#recortador-peca").evaluate("s => [...s.options].map(o => o.textContent)")
        assert pecas_ == ["Sombra", "Pele (o corpo)", "Olhos", "Sobrancelhas", "Boca", "Detalhe do rosto"], pecas_
        assert _destino(page) == ("Olhos", "neutra", "pares")
        carinhas = page.locator("#recortador-destino").evaluate(
            "s => [...s.querySelectorAll('optgroup')].map(g => [g.label, [...g.children].map(o => o.textContent)])")
        grupos = dict(carinhas)
        assert grupos["Principais"] == ["neutra", "fúria", "animada", "pânico", "dor", "morta"], grupos
        assert len(grupos["Outras carinhas"]) == 18 and "base" not in grupos["Outras carinhas"]
        assert page.locator("#recortador-olhos-caixa").is_visible()
        # A armadilha de 06/10 de propósito: Sombra (peça de um lugar só: sem "Carinha").
        page.locator("#recortador-peca").select_option("Sombra")
        assert _destino(page) == ("Sombra", "Sombra", "medio")
        assert page.locator("#recortador-carinha-caixa").is_hidden()
        assert page.locator("#recortador-olhos-caixa").is_hidden()

        # 1. Sobe com o destino Sombra: 12 recortes crus.
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
        page.locator("#recortador-peca").select_option("Olhos")
        assert page.locator("#recortador-destino").input_value() == OLHOS
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
        page.locator("#recortador-peca").select_option("Sombra")
        page.wait_for_function("() => !['-', 'recortando no PC…'].includes(document.querySelector('#recortador-aviso').innerText)")
        _itens(page, 12)
        assert page.locator("#recortador-juncao").input_value() == "medio"
        assert page.locator("#recortador-olhos-caixa").is_hidden()
        assert not [t for t in page.locator("#tela-atelie button, #tela-atelie select, #tela-atelie summary").evaluate_all(
            "es => es.filter(e => e.offsetParent !== null).map(e => [e.innerText || e.id, Math.round(e.getBoundingClientRect().height)])"
            ".filter(([_, h]) => h < 44)")]

        # 6. (07/10) A folha nova: o destino pelo NOME do arquivo, o par de
        # olhos de volta ao padrão (o "girar" da folha anterior não vale para
        # a seguinte) e, NOS OLHOS, o brilho a 12 px vira pedacinho desmarcado.
        page.locator("#recortador-peca").select_option("Olhos")
        page.locator("#recortador-olhos").select_option("girar")
        _subir(page, _olhos_com_brilho(pecas / "olhos_furia.png"))
        assert _destino(page) == ("Olhos", "fúria", "pares")
        assert page.locator("#recortador-olhos").input_value() == "separar"
        _itens(page, 7)
        marcados = page.locator("#recortador-lista .recortador-item").evaluate_all(
            "ls => ls.map(l => [l.querySelector('span').innerText, l.querySelector('input').checked])")
        soltos = [m for m in marcados if m[0].endswith("pedacinho solto")]
        assert len(soltos) == 1 and soltos[0][1] is False, marcados
        assert sum(1 for _, m in marcados if m) == 6
        assert page.locator("#recortador-fundo").inner_text() == (
            "Fundo magenta · 6 pares de olhos · 1 pedacinho solto (desmarcado)")
        assert page.locator("#recortador-mandar").inner_text() == "Mandar 6 selecionados"
        # Fora dos olhos nada sai do desenho (a v54 amputava a cauda dos
        # projéteis): a boca com o brilho vem inteira, como sempre.
        _subir(page, _folha_com_brilho(pecas / "boca_furia.png"))
        assert _destino(page) == ("Boca", "fúria", "medio")
        textos = _itens(page, 2)
        assert not [t for t in textos if "pedacinho" in t], textos
        assert page.locator("#recortador-mandar").inner_text() == "Mandar 2 selecionados"
        page.locator("#recortador-mandar").click()
        page.wait_for_function("() => document.querySelector('#recortador-aviso').innerText"
                               ".includes('2 recortes viraram variantes novas de boca · fúria')", timeout=60000)
        assert page.evaluate("() => localStorage.getItem('painel.recortador.destino')") == "lutador/boca/comum/_/furia"
        # A junção segue o destino a cada troca de grupo (v54: Lutador →
        # Habilidades ficava em "pares de olhos" e o Refazer recortava como olhos).
        page.locator("#recortador-peca").select_option("Olhos")
        page.wait_for_function("() => document.querySelector('#recortador-juncao').value === 'pares'"
                               " && document.querySelector('#recortador-fundo').innerText.includes('olho')", timeout=60000)
        page.locator("#modular-grupo").select_option("skill")
        page.wait_for_function("() => document.querySelector('#recortador-juncao').value === 'medio'"
                               " && /\\d+ recortes?$/.test(document.querySelector('#recortador-fundo').innerText)", timeout=60000)
        page.locator("#modular-grupo").select_option("lutador")
        _quieto(page)
        # a galeria dos Olhos mostra a peça RECORTADA (antes: o gabarito 1024 inteiro, olho de ~15 px)
        _quieto(page)
        page.locator("#modular-expressoes button", has_text="neutra").first.click()
        _quieto(page)
        tamanhos = page.locator("#modular-slots .modular-slot").filter(
            has=page.locator("strong", has_text="Olhos · neutra")).first.locator(".modular-variante img").evaluate_all(
            "is => is.filter(i => i.complete && i.naturalWidth).map(i => [i.naturalWidth, i.naturalHeight])")
        assert tamanhos and all(max(t) == 160 and min(t) < 160 for t in tamanhos), tamanhos

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
        # 07/10 (conferente): presa em pé, a prévia ocupava ~37% da tela e
        # cobria o topo da folha do Godot. Agora é uma faixa (<= 22%) e a folha
        # rola para logo abaixo dela, com o topo à vista.
        faixa = page.locator("#provador .provador-palco").evaluate("e => e.getBoundingClientRect().height")
        assert faixa <= 0.22 * 844, faixa
        page.wait_for_function("""() => { const i = document.querySelector('#provador-folha'), r = i.getBoundingClientRect();
            return i.complete && r.top > 0 && r.top < innerHeight / 2
                && document.elementFromPoint(r.left + r.width / 2, r.top + 6) === i; }""", timeout=5000)
        foto("06b_folha_logo_abaixo_da_previa")
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


# Os 29 nomes do conferente (07/10, reprovação da v54: "olhos-animada",
# "boca-morta" e "boca-tonta" não eram reconhecidos, "surface" virava rosto
# por "face", "sobrancelha_olho" virava Olhos e "olhos.png" em Boca · fúria
# perdia a fúria). Destino esperado com a tela em Olhos · neutra e em
# Boca · fúria; "" = o nome não diz a peça (a tela fica onde está). O
# detalhe do rosto não tem neutra: vai à primeira na ordem dos botões (fúria).
D = "lutador/{}/comum/_/{}".format
NOMES_ESPERADOS = {
    "olhos-furia.png": (D("olhos", "furia"),) * 2,
    "olhos-fúria.png": (D("olhos", "furia"),) * 2,
    "OLHOS_FURIA.PNG": (D("olhos", "furia"),) * 2,
    "olhos-neutra.png": (D("olhos", "neutro"),) * 2,
    "olhos-animada.png": (D("olhos", "animado"),) * 2,
    "boca-morta.png": (D("boca", "morto"),) * 2,
    "boca-tonta.png": (D("boca", "tonto"),) * 2,
    "olhos.png": (D("olhos", "neutro"), D("olhos", "furia")),
    "boca.png": (D("boca", "neutro"), D("boca", "furia")),
    "sobrancelhas-raiva.png": (D("sobrancelhas", "neutro"), D("sobrancelhas", "furia")),
    "sombrancelha_furia.png": (D("sobrancelhas", "furia"),) * 2,
    "lagrimas.png": (D("detalhe_rosto", "furia"),) * 2,
    "pele.png": (D("pele", "base"),) * 2,
    "sombra.png": (D("sombra", "base"),) * 2,
    "ChatGPT Image 7 de out. de 2026, 11_20_33.png": ("",) * 2,
    "Gemini_Generated_Image_abc123.png": ("",) * 2,
    "11243.png": ("",) * 2,
    "sprites_transparentes.png": ("",) * 2,
    "dorso.png": ("",) * 2,
    "olhos_dor.png": (D("olhos", "dor"),) * 2,
    "olhos_determinado.png": (D("olhos", "determinado"),) * 2,
    "boca_aberta_euforico.png": (D("boca", "euforico"),) * 2,
    "detalhe_rosto_bochecha.png": (D("detalhe_rosto", "furia"),) * 2,
    "eyes_angry.png": (D("olhos", "neutro"), D("olhos", "furia")),
    "surface.png": ("",) * 2,
    "interface_olhos.png": (D("olhos", "neutro"), D("olhos", "furia")),
    "facebook_boca.png": (D("boca", "neutro"), D("boca", "furia")),
    "corpo_olhos.png": (D("pele", "base"),) * 2,                 # a primeira palavra que é peça manda
    "sobrancelha_olho.png": (D("sobrancelhas", "neutro"), D("sobrancelhas", "furia")),
}


def test_o_nome_do_arquivo_escolhe_o_destino(provador_isolado):  # noqa: F811
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    srv = provador_isolado["srv"]
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        page = nav.new_page(viewport={"width": 390, "height": 844})
        page.goto(f"http://127.0.0.1:{srv.server_address[1]}/", wait_until="domcontentloaded")
        page.evaluate("([t]) => { localStorage.setItem('painel.token', t);"
                      " localStorage.setItem('painel.atelie.modo', 'montar'); }", [token])
        page.reload(wait_until="domcontentloaded")
        _abrir_atelie(page)
        page.locator("#modular-slots .modular-slot").first.wait_for()
        _quieto(page)
        errados = []
        for i, atual in enumerate((D("olhos", "neutro"), D("boca", "furia"))):
            for nome, esperado in NOMES_ESPERADOS.items():
                # isolated_context=False: as funções da página (o contexto
                # isolado do patchright não as enxerga)
                achado = page.evaluate("([n, a]) => { recortadorEscolher(a); return recortadorPeloNome(n); }",
                                       [nome, atual], isolated_context=False)
                if achado != esperado[i]:
                    errados.append((atual, nome, achado, esperado[i]))
        nav.close()
    assert not errados, errados
