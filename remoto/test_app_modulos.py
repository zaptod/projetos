# -*- coding: utf-8 -*-
"""Um pedaço do app que não chega do PC (30/09/2026, tarefa 74856214).

"Não estou conseguindo conversar nem pedir imagens pras IAs" (13:10). No log
do 8931, a carga da página de 12:01:17 NÃO recebeu o `conversa.js` (a de
14:54:07 de 29/09 perdeu ele e o `vila.js`); sem ele, `conversaAbrir` não
existe e o cartão do prédio mostrava só "Ver no diário" — nenhum "Conversar",
nenhum "Criar", e nada dizendo por quê. Ele passou 1h13 assim (e às 13:06:55
tocou "Ver no diário", o único botão); a carga de 13:15:09 recebeu o arquivo
e a conversa abriu 5 s depois. Reproduzido num Chrome de verdade com o
`conversa.js` respondendo 502 (o que o `tailscale serve` devolve quando o PC
não atende): o cartão do DeepSeek ficou com `['Ver no diário']`.

A causa: a fila de escuta do servidor era 5 (a do socketserver). No Windows
a conexão que passa da fila leva RST, e o `tailscale serve` troca a recusa
por 502. Medido recarregando no `load` (como o app faz), com o surto de /api
da carga anterior em voo: com 5, 22 de 145 cargas perderam um script por
ERR_CONNECTION_REFUSED; com 64, 0 de 170.

O conserto:
- `Servidor.request_queue_size = 64`;
- o service worker: resposta que não é 200 cai na cópia guardada (antes o
  502 ia direto para a página);
- o app confere, no `load`, se cada script chegou; faltando, recarrega uma
  vez sozinho e, se ainda faltar, a faixa `#modulo-faltando` diz qual.

Os testes estáticos rodam sempre; o do service worker roda o `sw.js` no
Node (pula sem Node); os do navegador só com `NF_TESTE_NAVEGADOR=1`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from remoto import api_http
from remoto.test_api_http import _parear, mundo  # noqa: F401

APP = Path(__file__).resolve().parent / "app"
HTML = (APP / "index.html").read_text(encoding="utf-8")
APP_JS = (APP / "app.js").read_text(encoding="utf-8")
NAVEGADOR = os.environ.get("NF_TESTE_NAVEGADOR") == "1"


def _modulos() -> list[tuple[str, str]]:
    bloco = re.search(r"const MODULOS = \[(.*?)\];", APP_JS, re.S)
    assert bloco, "app.js perdeu a lista MODULOS"
    return re.findall(r'\["([\w.]+\.js)", "(\w+)"\]', bloco.group(1))


# ------------------------------------------------------------ estáticos
def test_a_fila_de_escuta_aguenta_a_carga_da_pagina(mundo):        # noqa: F811
    # 5 (o padrão) recusava ~15% das cargas com a recarga no `load`
    assert api_http.Servidor.request_queue_size >= 64
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    try:
        assert srv.request_queue_size >= 64
    finally:
        srv.server_close()


def test_todo_script_da_pagina_e_conferido_no_load():
    scripts = re.findall(r'<script src="([\w.]+\.js)"></script>', HTML)
    assert scripts[0] == "app.js"                  # quem confere vem primeiro
    assert [arq for arq, _ in _modulos()] == scripts[1:]


def test_a_funcao_conferida_existe_no_topo_do_arquivo():
    # renomear a função sem mexer na lista faria o app achar que o arquivo
    # não chegou (recarga + faixa falsa); por isso a lista é conferida aqui
    for arquivo, funcao in _modulos():
        fonte = (APP / arquivo).read_text(encoding="utf-8")
        assert re.search(rf"^(async )?function {funcao}\(", fonte, re.M), (arquivo, funcao)


def test_a_faixa_e_o_botao_existem_no_html():
    assert 'id="modulo-faltando"' in HTML and 'id="modulo-faltando-texto"' in HTML
    assert 'id="btn-recarregar-modulos"' in HTML
    assert '"painel.modulos"' in APP_JS            # a recarga sozinho é uma só


# ------------------------------------------------------------ o sw.js no Node
_SW_HARNESS = r"""
const fs = require("fs");
const ouvintes = {};
const guardado = {"https://pc/conversa.js": {status: 200, type: "basic", corpo: "guardado"}};
global.self = {addEventListener: (nome, f) => { ouvintes[nome] = f; },
               skipWaiting() {}, clients: {claim() {}}};
global.caches = {
  match: async (req) => guardado[req.url],
  open: async () => ({put: async (req, resp) => { guardado[req.url] = resp; }}),
  keys: async () => [], delete: async () => true,
};
const cenario = process.argv[3];
global.fetch = async () => {
  if (cenario === "rede_caiu") throw new TypeError("Failed to fetch");
  if (cenario === "502") return {status: 502, type: "basic", corpo: "Bad Gateway"};
  return {status: 200, type: "basic", corpo: "novo", clone() { return this; }};
};
eval(fs.readFileSync(process.argv[2], "utf8"));
const url = process.argv[4];
let resposta;
ouvintes.fetch({request: {method: "GET", url}, respondWith: (p) => { resposta = p; }});
Promise.resolve(resposta).then((r) => console.log(JSON.stringify(r ? r.corpo : null)));
"""


@pytest.mark.parametrize("cenario,url,esperado", [
    ("502", "https://pc/conversa.js", "guardado"),      # o conserto: 502 -> cópia
    ("rede_caiu", "https://pc/conversa.js", "guardado"),
    ("ok", "https://pc/conversa.js", "novo"),            # rede primeiro, sempre
    ("502", "https://pc/nao-guardado.js", "Bad Gateway"),  # sem cópia, o erro segue
])
def test_o_service_worker_cai_na_copia_quando_o_pc_responde_erro(tmp_path, cenario, url,
                                                                 esperado):
    node = shutil.which("node")
    if not node:
        pytest.skip("sem Node nesta máquina")
    harness = tmp_path / "harness.js"
    harness.write_text(_SW_HARNESS, encoding="utf-8")
    saida = subprocess.run([node, str(harness), str(APP / "sw.js"), cenario, url],
                           capture_output=True, text=True, timeout=30)
    assert saida.returncode == 0, saida.stderr
    assert json.loads(saida.stdout.strip()) == esperado


# ------------------------------------------------------------ no navegador
@pytest.fixture
def pagina(mundo):                                                  # noqa: F811
    if not NAVEGADOR:
        pytest.skip("só com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    fio = threading.Thread(target=srv.serve_forever, daemon=True)
    fio.start()
    token = _parear(srv)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 412, "height": 915}, is_mobile=True,
                              has_touch=True, service_workers="block")
        page = ctx.new_page()
        page.falhas = []
        page.on("requestfailed", lambda r: page.falhas.append(
            (r.url.rsplit("/", 1)[-1], r.failure)))
        page.goto(base + "/")
        page.evaluate(f"localStorage.setItem('painel.token', '{token}')")
        yield page, base
        nav.close()
    srv.shutdown()
    srv.server_close()


def _carregar_com_502(page, base, vezes):
    pedidos = {"n": 0}

    def rota(route):
        pedidos["n"] += 1
        if pedidos["n"] <= vezes:
            return route.fulfill(status=502, body="Bad Gateway", content_type="text/plain")
        return route.continue_()

    page.route("**/conversa.js", rota)
    page.goto(base + "/")
    # a segunda carga (a recarga sozinho) precisa terminar antes da conta
    fim = time.time() + 15
    while time.time() < fim:
        try:
            estado = page.get_attribute("html", "data-modulos")
        except Exception:                                    # noqa: BLE001 (navegando)
            estado = None
        if pedidos["n"] >= 2 and estado:
            break
        time.sleep(0.2)
    time.sleep(1.5)
    return pedidos["n"]


def test_navegador_um_502_no_conversa_js_recarrega_sozinho_e_volta(pagina):
    page, base = pagina
    pedidos = _carregar_com_502(page, base, vezes=1)
    assert pedidos == 2                                  # uma recarga, não um laço
    assert page.get_attribute("html", "data-modulos") == "ok", page.falhas
    assert page.locator("#modulo-faltando.oculto").count() == 1


def test_navegador_502_que_nao_passa_mostra_a_faixa_sem_laco(pagina):
    page, base = pagina
    pedidos = _carregar_com_502(page, base, vezes=99)
    time.sleep(2.0)
    assert pedidos == 2                                  # recarregou UMA vez e parou
    assert page.get_attribute("html", "data-modulos") == "conversa.js", page.falhas
    faixa = page.locator("#modulo-faltando")
    assert faixa.is_visible()
    assert "conversa.js" in faixa.inner_text() and "conversar" in faixa.inner_text()
