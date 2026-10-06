# -*- coding: utf-8 -*-
"""O Provador e as variantes no Chrome do celular, clicando de verdade (06/10/2026).

Caminho do Adrian, ponta a ponta, conferido pelo DOM e pelo disco:
1. "+ Nova variante" nos Olhos com TRES arquivos de uma vez (o seletor e
   `multiple`; antes so o primeiro ia) -> a galeria do cartao mostra 3;
2. o recortador manda 2 recortes de uma folha magenta como variantes novas
   dos Olhos -> a galeria mostra 5;
3. o Provador: busca o lutador pelo nome, as setas trocam a variante (a
   miniatura muda de cor), Fixar grava o guarda-roupa, recarregar a pagina
   e continua fixada, as 24 carinhas, Ver no Godot, Voltar ao sorteio;
4. Apagar a variante fixada de alguem: a tela diz em uma frase que ele voltou
   ao sorteio, e o Desfazer traz a variante (e a escolha) de volta.
Capturas 390x844, claro e escuro, em <TEMP>/tela_app/provador/. Biblioteca,
banco de personagens, LOCALAPPDATA e runtime sao temporarios; o Godot so roda
de verdade com NF_TESTE_GODOT=1 (senao um duble devolve a folha).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from remoto import api_http
from remoto.test_app_sprites_tela import _png, sprites_isolados  # noqa: F401 (fixture)
from remoto.test_app_tela import CAPTURAS, NAVEGADOR, tela_isolada  # noqa: F401 (fixture)

PERSONAGENS = [
    {"nome": "Júlia a Abençoada", "classe": "Berserker (Fúria)", "cor_r": 40, "cor_g": 200, "cor_b": 90},
    {"nome": "Lucius a Sombria", "classe": "Guerreiro (Força Bruta)", "cor_r": 216, "cor_g": 54, "cor_b": 69},
    {"nome": "Achilles", "classe": "Monge (Chi)", "cor_r": 10, "cor_g": 20, "cor_b": 250},
]
OLHOS = "lutador/olhos/comum/_/neutro"
# Cores bem distintas por variante: a miniatura e a prova de que a seta trocou.
CORES_OLHOS = [(220, 30, 30, 255), (30, 60, 230, 255), (240, 200, 20, 255)]

COR_MEDIA = """img => { const c = document.createElement('canvas');
  c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext('2d'); g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, c.width, c.height).data;
  let r = 0, v = 0, b = 0, n = 0;
  for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 200) { r += d[i]; v += d[i + 1]; b += d[i + 2]; n++; }
  return n ? [Math.round(r / n), Math.round(v / n), Math.round(b / n)] : null; }"""


# Leituras atomicas: a lista e redesenhada duas vezes seguidas depois de cada
# anexo (a resposta do anexo e a carga completa); ler elemento por elemento
# pegava o primeiro desenho no meio da troca. Cada uma devolve null ate a
# tela estar pronta, e a `wait_for_function` repete.
GALERIA_OLHOS = """(n) => { const cor = COR;
  const c = [...document.querySelectorAll('#modular-slots .modular-slot')].find(c => c.innerText.includes('Olhos'));
  const figs = c ? [...c.querySelectorAll('.modular-variante')] : [];
  if (figs.length !== n) return null;
  const saida = [];
  for (const f of figs) {
    const i = f.querySelector('img');
    if (i.classList.contains('oculto') || !i.complete || !i.naturalWidth) return null;
    saida.push([f.querySelector('figcaption').innerText, cor(i)]);
  }
  return saida; }""".replace("COR", COR_MEDIA)
LINHA_OLHOS = """(esperada) => { const cor = COR;
  const l = document.querySelector("#provador-pecas [data-parte='olhos']");
  const i = l && l.querySelector('img.provador-mini');
  if (!i || !i.complete || !i.naturalWidth) return null;
  const contagem = l.querySelector('.provador-contagem').innerText;
  if (esperada && contagem !== esperada) return null;
  return {contagem, cor: cor(i), selo: l.querySelector('.provador-selo').innerText}; }""".replace("COR", COR_MEDIA)


def _esperar(page, js, arg=None):
    return page.wait_for_function(js, arg=arg).json_value()


def _olhos(caminho: Path, cor) -> Path:
    """O par de olhos nas zonas do gabarito (CONTRATO 2.3), fundo transparente."""
    imagem = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    caneta = ImageDraw.Draw(imagem)
    for y in (420, 604):
        caneta.ellipse((512, y - 51, 614, y + 51), fill=cor)
    imagem.save(caminho)
    return caminho


def _folha_magenta(caminho: Path) -> Path:
    """Folha de IA com fundo magenta liso e dois desenhos separados."""
    imagem = Image.new("RGB", (480, 240), (255, 0, 255))
    caneta = ImageDraw.Draw(imagem)
    caneta.ellipse((40, 60, 200, 180), fill=(20, 140, 60))
    caneta.ellipse((280, 50, 440, 190), fill=(120, 40, 160))
    imagem.save(caminho)
    return caminho


@pytest.fixture
def provador_isolado(sprites_isolados, tmp_path, monkeypatch):  # noqa: F811
    arquivo = tmp_path / "personagens.json"
    arquivo.write_text(json.dumps(PERSONAGENS, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(api_http, "ARQUIVO_PERSONAGENS", arquivo)
    monkeypatch.setattr(api_http, "_PERSONAGENS", {"chave": None, "lista": [], "por_id": {}})
    monkeypatch.setattr(api_http, "_PEDIDOS_GODOT", {})
    chamadas = []
    if not sprites_isolados["godot_real"]:
        def godot(classe, personagem, biblioteca, saida):
            chamadas.append((classe, personagem, sorted(
                str(p.relative_to(biblioteca)).replace("\\", "/") for p in Path(biblioteca).rglob("*.png"))))
            Image.new("RGBA", (540, 960), (27, 30, 39, 255)).save(saida)
            return {"estado": "pronta", "arquivo": str(saida)}
        monkeypatch.setattr(api_http, "_godot_folha", godot)
    return {**sprites_isolados, "godot_chamadas": chamadas}


def _quieto(page):
    page.wait_for_function("() => document.querySelector('#modular-carregando').classList.contains('oculto')")
    page.wait_for_timeout(150)


def _cartao(page, titulo):
    return page.locator("#modular-slots .modular-slot").filter(
        has=page.locator("strong", has_text=titulo)).first


def _linha(page, parte):
    return page.locator(f"#provador-pecas .provador-peca[data-parte='{parte}']")


def _toques_pequenos(page):
    return page.locator("#tela-atelie").evaluate(
        """raiz => [...raiz.querySelectorAll('button, select, input:not([type=checkbox])')]
              .filter(e => e.offsetParent !== null)
              .map(e => [e.innerText || e.id || e.type, Math.round(e.getBoundingClientRect().height)])
              .filter(([_, h]) => h < 44)""")


def _sem_id_na_tela(page):
    texto = page.locator("#tela-atelie").inner_text()
    achados = re.findall(r"\bv\d\d\b|lutador/|partes/|palco|[A-Za-z]:\\|guarda_roupa|_furia|exemplo-", texto)
    assert not achados, achados


def _guarda(raiz):
    arquivo = raiz / "partes" / "guarda_roupa.json"
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None


def _abrir_atelie(page):
    page.wait_for_function("() => document.body.classList.contains('pareado')")
    page.evaluate("() => document.querySelector('#obj-arena').click()")
    page.locator("#tela-arena:not(.oculto)").wait_for()
    page.evaluate("() => document.querySelector(\"#tela-arena [data-aba-tela='atelie']\").click()")
    page.locator("#tela-atelie:not(.oculto)").wait_for()


@pytest.mark.parametrize("tema", ["light", "dark"])
def test_variantes_recortador_e_provador_pela_tela(provador_isolado, tema):
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    srv, pecas, raiz = provador_isolado["srv"], provador_isolado["pecas"], provador_isolado["raiz"]
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    pele = _png(pecas / "pele.png", (255, 255, 255, 255), miolo=False)      # mascara: vira a cor dele
    olhos = [_olhos(pecas / f"olhos_{i}.png", cor) for i, cor in enumerate(CORES_OLHOS, 1)]
    folha = _folha_magenta(pecas / "folha.png")
    pasta = CAPTURAS / "provador"
    pasta.mkdir(parents=True, exist_ok=True)
    def foto(page, nome, inteira=False):
        # Antes de cada captura, toda miniatura do Provador visivel carregada
        # (uma <img> com blob revogado fica com naturalWidth 0 para sempre).
        page.wait_for_function("""() => [...document.querySelectorAll('#provador-pecas img.provador-mini')]
            .every(i => i.complete && i.naturalWidth > 0)""")
        page.screenshot(path=str(pasta / f"{tema}_{nome}.png"), full_page=inteira)
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
        page.evaluate("([t]) => { localStorage.setItem('painel.token', t);"
                      " localStorage.setItem('painel.atelie.modo', 'montar'); }", [token])
        page.reload(wait_until="domcontentloaded")
        _abrir_atelie(page)
        _cartao(page, "Pele (o corpo)").wait_for()
        assert page.locator("#atelie-modo-montar").get_attribute("aria-pressed") == "true"

        # 1. Pele pelo seletor, e TRES olhos de uma vez pelo "+ Nova variante".
        _quieto(page)
        with page.expect_file_chooser() as escolha:
            _cartao(page, "Pele (o corpo)").get_by_role("button", name="Anexar", exact=True).click()
        escolha.value.set_files(str(pele))
        page.wait_for_function("() => document.querySelector('#modular-progresso').innerText.includes('básico: 1 de 3')")
        _quieto(page)
        with page.expect_file_chooser() as escolha:
            _cartao(page, "Olhos").get_by_role("button", name="+ Nova variante").click()
        assert escolha.value.is_multiple()
        escolha.value.set_files([str(o) for o in olhos])
        page.wait_for_function("() => document.querySelector('#modular-aviso').innerText.includes('3 variantes novas')")
        galeria = _esperar(page, GALERIA_OLHOS, 3)
        assert sorted(p.name for p in (raiz / "partes/lutador/olhos/comum/_").iterdir()) == ["v01", "v02", "v03"]
        assert [legenda for legenda, _ in galeria] == ["Variante 1", "Variante 2", "Variante 3"]
        cores = [cor for _, cor in galeria]
        assert [max(range(3), key=lambda k, c=c: c[k]) for c in cores] == [0, 2, 0], cores   # vermelho, azul, amarelo
        _quieto(page)
        _cartao(page, "Olhos").scroll_into_view_if_needed()
        foto(page, "01_tres_variantes_pelo_seletor")

        # 2. O recortador manda 2 recortes da folha magenta como variantes novas.
        page.locator("#recortador-arquivo").set_input_files(str(folha))
        page.wait_for_function("() => document.querySelectorAll('#recortador-lista .recortador-item').length === 2")
        assert "magenta" in page.locator("#recortador-fundo").inner_text()
        page.locator("#recortador-destino").select_option(OLHOS)
        page.locator("#recortador-folha").scroll_into_view_if_needed()
        foto(page, "02_recortador_folha")
        page.locator("#recortador-mandar").click()
        page.wait_for_function("() => document.querySelector('#recortador-aviso').innerText.includes('2 recortes viraram variantes novas')")
        # As 5 miniaturas da galeria carregadas (06/10: 4 de 5 ficavam em branco,
        # a resposta atrasada de um redesenho revogava a imagem do seguinte).
        galeria = _esperar(page, GALERIA_OLHOS, 5)
        assert [legenda for legenda, _ in galeria][3:] == ["Variante 4", "Variante 5"]
        assert sorted(p.name for p in (raiz / "partes/lutador/olhos/comum/_").iterdir()) == [
            "v01", "v02", "v03", "v04", "v05"]
        assert Image.open(raiz / "partes/lutador/olhos/comum/_/v01/neutro.png").getpixel((563, 420))[:3] == (220, 30, 30)
        _quieto(page)
        _cartao(page, "Olhos").scroll_into_view_if_needed()
        foto(page, "03_galeria_com_recortes")
        assert not _toques_pequenos(page), _toques_pequenos(page)
        _sem_id_na_tela(page)

        # 3. O Provador: lista com busca e classe, o lutador montado.
        page.locator("#atelie-modo-provador").click()
        page.locator("#provador-lista .provador-item").first.wait_for()
        assert page.locator("#provador-lista .provador-item").count() == 3
        page.locator("#provador-classe").select_option(label="Berserker (Fúria)")
        itens = page.locator("#provador-lista .provador-item")
        assert itens.count() == 2 and "Lutador de exemplo" in itens.first.inner_text()
        page.locator("#provador-classe").select_option("")
        page.locator("#provador-busca").fill("julia")              # sem acento acha "Júlia"
        assert page.locator("#provador-lista .provador-item").count() == 1
        foto(page, "04_provador_escolher_lutador")
        page.locator("#provador-lista .provador-item", has_text="Júlia a Abençoada").click()
        page.locator("#provador-palco-caixa:not(.oculto)").wait_for()
        assert page.locator("#provador-nome").inner_text() == "Júlia a Abençoada"
        assert page.locator("#provador-classe-nome").inner_text() == "Berserker (Fúria)"
        antes = _esperar(page, LINHA_OLHOS)
        page.wait_for_function("() => { const i = document.querySelector('#provador-previa');"
                               " return i.complete && i.naturalWidth > 0; }")
        contagem = antes["contagem"]
        assert re.fullmatch(r"[1-5] de 5", contagem), contagem
        assert "Sorteada pelo jogo" in antes["selo"]
        linha = _linha(page, "olhos")
        assert "peça comum" in linha.locator(".provador-dono").inner_text()
        assert "Pele (o corpo)" not in page.locator("#provador-sem-desenho").inner_text()
        # A pele comum e mascara: na previa ela vem com a cor da Julia.
        assert page.locator("#provador-previa").evaluate(COR_MEDIA) is not None
        foto(page, "05_provador_montado")

        # 4. A seta troca a variante: contagem e miniatura mudam; nada no disco.
        antes_n = int(contagem.split()[0])
        linha.get_by_role("button", name="Olhos: próxima").click()
        esperado = antes_n % 5 + 1
        depois = _esperar(page, LINHA_OLHOS, f"{esperado} de 5")
        assert depois["cor"] != antes["cor"], (antes, depois)
        assert "Experimentando" in depois["selo"]
        linha = _linha(page, "olhos")
        assert _guarda(raiz) is None
        foto(page, "06_seta_experimentando")

        # 5. Fixar grava o guarda-roupa; recarregar a pagina e continua fixada.
        linha.get_by_role("button", name="Fixar olhos").click()
        page.wait_for_function("() => document.querySelector('#provador-aviso').innerText.includes('Fixado em Júlia')")
        linha = _linha(page, "olhos")
        assert "Fixada por você" in linha.locator(".provador-selo").inner_text()
        fixada = _guarda(raiz)["julia_a_abencoada"]["olhos"]
        assert fixada == f"v{esperado:02d}"
        foto(page, "07_fixada")
        page.reload(wait_until="domcontentloaded")
        _abrir_atelie(page)
        page.locator("#provador-palco-caixa:not(.oculto)").wait_for()
        assert page.locator("#atelie-modo-provador").get_attribute("aria-pressed") == "true"
        recarregada = _esperar(page, LINHA_OLHOS, f"{esperado} de 5")
        assert "Fixada por você" in recarregada["selo"] and recarregada["cor"] == depois["cor"]
        # o lutador montado no palco (pele tingida + os olhos fixados), nao so a linha
        previa = _esperar(page, """() => { const cor = COR; const i = document.querySelector('#provador-previa');
            return i.complete && i.naturalWidth > 0 ? cor(i) : null; }""".replace("COR", COR_MEDIA))
        assert previa is not None and previa[1] > previa[0], previa         # verde da Julia por cima de tudo
        assert "🔒 1 fixada" in page.locator("#provador-legenda").inner_text()
        foto(page, "08_depois_de_recarregar")

        # 6. As 24 carinhas e o Ver no Godot deste lutador.
        page.wait_for_function("() => document.querySelectorAll('#provador-expressoes button').length === 6")
        page.locator("#provador-todas").click()
        page.wait_for_function("() => document.querySelectorAll('#provador-expressoes button').length === 24")
        page.locator("#provador-expressoes button", has_text="fúria").first.click()
        page.wait_for_function("() => document.querySelector('#provador-legenda').innerText.includes('Carinha fúria')")
        assert "Fixada por você" in _linha(page, "olhos").locator(".provador-selo").inner_text()
        page.locator("#provador-ver-godot").click()
        page.locator("#provador-folha").wait_for(state="visible", timeout=60000)
        assert page.locator("#provador-folha").evaluate("i => i.complete && i.naturalWidth > 0")
        assert "Júlia a Abençoada" in page.locator("#provador-aviso").inner_text()
        if provador_isolado["godot_chamadas"]:
            classe, personagem, arquivos = provador_isolado["godot_chamadas"][-1]
            assert (classe, personagem) == ("berserker_furia", "Júlia a Abençoada")
            assert f"partes/lutador/olhos/comum/_/{fixada}/neutro.png" in arquivos
            assert len([a for a in arquivos if "/olhos/" in a]) == 1
        page.wait_for_timeout(400)
        foto(page, "09_ver_no_godot", inteira=True)
        assert not _toques_pequenos(page), _toques_pequenos(page)
        _sem_id_na_tela(page)

        # 7. Voltar ao sorteio (a peca): sai do guarda-roupa.
        _linha(page, "olhos").get_by_role("button", name="Olhos: voltar ao sorteio").click()
        page.wait_for_function("() => document.querySelector('#provador-aviso').innerText.includes('de volta ao sorteio')")
        volta = _esperar(page, LINHA_OLHOS)
        assert "Sorteada pelo jogo" in volta["selo"]
        assert _guarda(raiz) == {}
        # a folha do Godot era da combinacao fixada: com outra peca, ela sai da tela
        assert page.locator("#provador-folha").is_hidden() == (volta["contagem"] != f"{esperado} de 5")
        foto(page, "10_voltou_ao_sorteio")

        # 8. Apagar a variante fixada de alguem: ela volta ao sorteio, e o Desfazer traz tudo de volta.
        _linha(page, "olhos").get_by_role("button", name="Fixar olhos").click()
        page.wait_for_function("() => document.querySelector('#provador-aviso').innerText.includes('Fixado em Júlia')")
        fixada = _guarda(raiz)["julia_a_abencoada"]["olhos"]
        numero = int(fixada[1:])
        page.locator("#atelie-modo-montar").click()
        _cartao(page, "Olhos").wait_for()
        _quieto(page)
        _cartao(page, "Olhos").get_by_role("button", name=f"Apagar a variante {numero}").click()
        page.wait_for_function("() => document.querySelector('#modular-aviso').innerText.includes('voltou ao sorteio')")
        aviso = page.locator("#modular-aviso").inner_text()
        assert f"A variante {numero} de olhos foi apagada" in aviso
        assert "Júlia a Abençoada usava esta variante fixa e voltou ao sorteio." in aviso
        assert any("todas as carinhas dela" in d for d in dialogos)
        # A frase aparece TAMBEM junto da galeria (o aviso do painel fica no fim da lista).
        page.wait_for_function("""() => [...document.querySelectorAll('.modular-galeria-aviso')]
            .some(p => p.innerText.includes('Júlia a Abençoada usava esta variante fixa e voltou ao sorteio.'))""")
        assert _guarda(raiz) == {}
        page.wait_for_function("""() => [...document.querySelectorAll('#modular-slots .modular-slot')]
            .some(c => c.innerText.includes('Olhos') && c.querySelectorAll('.modular-variante').length === 4)""")
        _quieto(page)
        _cartao(page, "Olhos").scroll_into_view_if_needed()
        foto(page, "11_variante_apagada")
        _quieto(page)
        _cartao(page, "Olhos").get_by_role("button", name="Desfazer: trazer a variante apagada").click()
        page.wait_for_function("() => document.querySelector('#modular-aviso').innerText.includes('voltou para Júlia')")
        page.wait_for_function("""() => [...document.querySelectorAll('#modular-slots .modular-slot')]
            .some(c => c.innerText.includes('Olhos') && c.querySelectorAll('.modular-variante').length === 5)""")
        assert _guarda(raiz) == {"julia_a_abencoada": {"olhos": fixada}}
        _quieto(page)
        _cartao(page, "Olhos").scroll_into_view_if_needed()
        foto(page, "12_variante_de_volta")
        assert not _toques_pequenos(page), _toques_pequenos(page)
        assert not erros, erros
        nav.close()
