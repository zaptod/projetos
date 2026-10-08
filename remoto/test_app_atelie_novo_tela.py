from pathlib import Path
import base64
import io
import json
import os
import shutil
import subprocess
import threading

import pytest
from PIL import Image, ImageDraw


APP = Path(__file__).with_name("app")


@pytest.mark.skipif(shutil.which("node") is None, reason="node nao instalado")
def test_atelie_novo_tem_javascript_valido():
    resultado = subprocess.run(["node", "--check", str(APP / "atelie_novo.js")],
                               text=True, capture_output=True)
    assert resultado.returncode == 0, resultado.stderr


def test_atelie_novo_tem_fluxo_de_animacao_e_nao_carrega_o_legado():
    html = (APP / "index.html").read_text(encoding="utf-8")
    codigo = (APP / "atelie_novo.js").read_text(encoding="utf-8")
    css = (APP / "app.css").read_text(encoding="utf-8")
    assert 'id="atelie-novo"' in html
    for campo in ("anim-progresso", "anim-faltam", "anim-grupos", "anim-busca", "anim-arquivo",
                  "anim-auto", "anim-grade", "anim-folha-canvas", "anim-lista-quadros", "anim-fps",
                  "anim-fps-numero", "anim-segurar", "anim-canvas", "anim-claro", "anim-escuro",
                  "anim-xadrez", "anim-salvar", "anim-substituir", "anim-desfazer", "anim-esconder",
                  "anim-fechar", "anim-novo-nome", "anim-novo-gatilho", "anim-ancora-texto",
                  "anim-ancora-central", "anim-ancora-embaixo", "anim-ordem-folha", "anim-ordem-aviso"):
        assert 'id="' + campo + '"' in html
    assert "anim-ordem-aviso" in html
    for rota in ("/api/animacoes/arvore", "/api/animacoes/gatilhos", "/api/animacoes/subir",
                 "/api/animacoes/salvar", "/api/animacoes/desfazer", "/api/animacoes/criar",
                 "/api/animacoes/esconder", "/api/animacoes/previa-godot"):
        assert rota in codigo
    for comportamento in ("animOrdenarFaltam", "animMiniatura", "animRefatiar", "animMover",
                           "duracao_por_quadro", "animTocar", "pointerdown", "animAtivarCartoes",
                           "Content-Type", "estado_personagem", "animPost", "animReferencia",
                           "A âncora (+) fica", "gira em volta do lutador", "◀ antes", "depois ▶"):
        assert comportamento in codigo
    for comportamento in ("animVerNoGodot", "Renderizando no Godot", "setTimeout", "playsinline"):
        assert comportamento in codigo
    assert ".livro.atelie { padding-top: calc(112px" in css
    assert ".livro.atelie { --fundo: #14161a" in css


@pytest.mark.skipif(not os.environ.get("NF_TESTE_NAVEGADOR"), reason="so com NF_TESTE_NAVEGADOR=1")
def test_atelie_novo_fluxo_completo_no_navegador(tmp_path, monkeypatch):
    """Prova manual automatizada: corpo parado, folha 4x2, salvar, trocar e ocultar."""
    from patchright.sync_api import sync_playwright
    from neural_fights.tools import atelie_animacoes as atelie
    from remoto import api_http

    catalogo = {"pecas": [{"id": "corpo", "grupo": "Lutador", "rotulo": "corpo",
                 "heranca": [], "estados": [{"id": "parado", "rotulo": "parado",
                 "animacoes": [{"id": "respirar", "rotulo": "respirar", "gatilho": "ocioso", "loop": True}]}]}]}
    arquivo = tmp_path / "catalogo.json"; arquivo.write_text(json.dumps(catalogo), encoding="utf-8")
    monkeypatch.setattr(atelie, "CATALOGO", arquivo); monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    monkeypatch.setattr(atelie, "AJUSTES", tmp_path / "ajustes.json"); monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app.json")
    imagem = Image.new("RGBA", (40, 20)); caneta = ImageDraw.Draw(imagem)
    for y in range(2):
        for x in range(4): caneta.rectangle((x * 10 + 1, y * 10 + 1, x * 10 + 8, y * 10 + 8), fill="white")
    bruto = io.BytesIO(); imagem.save(bruto, "PNG")
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True); fio = threading.Thread(target=srv.serve_forever, daemon=True); fio.start()
    try:
        token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
        with sync_playwright() as pw:
            nav = pw.chromium.launch(channel="chrome", headless=True)
            ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
            page = ctx.new_page(); base = f"http://127.0.0.1:{srv.server_address[1]}"
            page.goto(base + "/", wait_until="domcontentloaded"); page.evaluate("t => localStorage.setItem('painel.token', t)", token); page.reload(wait_until="domcontentloaded")
            page.evaluate("atelieMostrar()"); page.locator("#anim-grupos button").first.click(); page.locator("#anim-lista .anim-peca").click(); page.locator("#anim-lista button").first.click(); page.locator(".anim-cartao-abrir").click()
            page.locator("#anim-arquivo").set_input_files({"name": "folha.png", "mimeType": "image/png", "buffer": bruto.getvalue()})
            page.locator("#anim-grade").check(); page.locator("#anim-linhas").fill("2"); page.locator("#anim-colunas").fill("4"); page.locator("#anim-colunas").press("Tab")
            page.locator("#anim-quadros").wait_for(); assert "8 quadros" in page.locator("#anim-quadros").inner_text()
            page.locator("#anim-fps-numero").fill("9"); page.locator("#anim-canvas").click(position={"x": 80, "y": 80}); page.locator("#anim-salvar").click(); page.locator("#anim-aviso").get_by_text("Salvo.").wait_for()
            page.locator("#anim-substituir").click(); page.locator("#anim-desfazer").click()
            page.locator("#anim-fechar").click(); page.get_by_text("+ Nova animação").click(); page.locator("#anim-novo-nome").fill("chorar"); page.locator("#anim-criar-botao").click(); page.get_by_text("chorar").click(); page.locator("#anim-esconder").click()
            nav.close()
    finally:
        srv.shutdown(); srv.server_close()
