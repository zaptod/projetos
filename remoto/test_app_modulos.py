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
const interceptado = resposta !== undefined;
Promise.resolve(resposta).then((r) => console.log(JSON.stringify(
  {corpo: r ? r.corpo : null, guardado: !!guardado[url], interceptado})));
"""


# 14/10 (auditoria 11/10, item 2): só a CASCA (a lista ARQUIVOS) passa pelo
# service worker; o resto é rede pura e nunca entra no cache. Antes cada
# versão das imagens da Vila (`?v=`) ficava guardada para sempre.
@pytest.mark.parametrize("cenario,url,esperado", [
    ("502", "https://pc/conversa.js",
     {"corpo": "guardado", "guardado": True, "interceptado": True}),
    ("rede_caiu", "https://pc/conversa.js",
     {"corpo": "guardado", "guardado": True, "interceptado": True}),
    ("ok", "https://pc/conversa.js", {"corpo": "novo", "guardado": True, "interceptado": True}),
    # da casca, ainda sem cópia: o erro segue para a página
    ("502", "https://pc/oficina.js",
     {"corpo": "Bad Gateway", "guardado": False, "interceptado": True}),
    ("ok", "https://pc/app.js", {"corpo": "novo", "guardado": True, "interceptado": True}),
    ("ok", "https://pc/", {"corpo": "novo", "guardado": True, "interceptado": True}),
    # fora da casca: o service worker nem toca
    ("ok", "https://pc/vilanova-retrato.webp?v=nova",
     {"corpo": None, "guardado": False, "interceptado": False}),
    ("ok", "https://pc/vilanova-atlas.png?escala=3&v=x",
     {"corpo": None, "guardado": False, "interceptado": False}),
    ("ok", "https://pc/arte-vila/atelie/objetos/agora.png?v=x",
     {"corpo": None, "guardado": False, "interceptado": False}),
    ("ok", "https://pc/p/bilhete123", {"corpo": None, "guardado": False, "interceptado": False}),
    ("ok", "https://pc/api/vila", {"corpo": None, "guardado": False, "interceptado": False}),
    ("502", "https://pc/nao-guardado.js",
     {"corpo": None, "guardado": False, "interceptado": False}),
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


# ------------------------------------- achados do conferente (14/10, casca v70)
CSS = (APP / "app.css").read_text(encoding="utf-8")


def _bloco(seletor: str) -> str:
    achado = re.search(r"(?m)^" + re.escape(seletor) + r"\s*\{([^}]*)\}", CSS)
    assert achado, f"app.css perdeu a regra {seletor}"
    return achado.group(1)


def test_o_estilo_do_codigo_de_pareamento_so_vale_no_codigo():
    """A busca do Ateliê saía "n o m e  d a  p e ç a" e o FPS "1 2": a regra
    `input` (24px, .3em, centro) era do código de pareamento."""
    comum = _bloco("input")
    assert "letter-spacing: normal" in comum and "text-align: left" in comum
    assert ".3em" not in comum and "24px" not in comum
    codigo = _bloco("input#codigo")
    assert "letter-spacing: .3em" in codigo and "text-align: center" in codigo
    assert 'id="codigo"' in HTML


def test_deitado_com_a_faixa_usa_a_base_de_em_pe():
    assert "classList.toggle(\"com-faixa\"" in APP_JS
    assert "calc(64px + env(safe-area-inset-top) + var(--faixa-alto" in _bloco(
        "body.deitado.com-faixa .livro")


def test_coordenador_sem_dados_diz_por_que():
    js = (APP / "coordenador.js").read_text(encoding="utf-8")
    assert "Dados indisponíveis" in js and "function coordSemDados" in js
    # os tres cartoes do painel
    corpo = js.split("function coordSemDados", 1)[1].split("\n}\n", 1)[0]
    for alvo in ("coord-trabalho", "coord-servicos", "coord-eventos"):
        assert alvo in corpo


# ------------------------------------- achados do conferente (14/10, casca v71)
def test_coordenador_ligado_sem_eventos_diz_nada_de_novo():
    """Com o PC ligado e `eventos` vazio, O QUE ACONTECEU ficava em branco."""
    js = (APP / "coordenador.js").read_text(encoding="utf-8")
    desenhar = js.split("function coordDesenhar", 1)[1].split("\n}\n", 1)[0]
    assert "Nada de novo desde" in desenhar and "dados.desde" in desenhar
    assert "Nenhum serviço publicado pelo coordenador." in desenhar


def test_a_moldura_da_agora_sai_da_conta_com_a_faixa():
    """A Agora (`.livro.mesa`, moldura de 12 px) tinha vão de 22 px até as
    abas com a faixa "sem conexão"; as outras, 10 px. Desde a v72 a moldura
    sai da conta também sem a faixa (topo→abas 25,7 contra 13,7 px)."""
    assert "border: 12px solid" in _bloco(".livro.mesa")
    for seletor, base in ((r"\.livro\.mesa", 64), (r"body\.deitado \.livro\.mesa", 56),
                          (r"body\.deitado\.com-faixa \.livro\.mesa", 64)):
        regras = re.findall(r"(?m)^" + seletor + r"\s*\{([^}]*)\}", CSS)
        esperado = (f"padding-top: calc({base}px - 12px + env(safe-area-inset-top)"
                    f" + var(--faixa-alto, 0px))")
        assert any(esperado in r for r in regras), seletor


# ------------------------------------- achados do conferente (14/10, casca v72)
def test_rotulo_do_seletor_de_arquivo_e_botao():
    """"Escolher folha" (label.acao com input file escondido) era texto solto
    com alvo de 20 px; só o button.acao tinha o visual."""
    bloco = _bloco("label.acao:has(> input[type=file])")
    for regra in ("min-height: 44px", "border: 1px solid var(--linha)", "background: var(--cartao)",
                  "cursor: pointer"):
        assert regra in bloco, regra


def test_folha_do_atelie_nasce_escondida():
    html = (APP / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<canvas id="anim-folha-canvas"[^>]*\shidden>', html)
    js = (APP / "atelie_novo.js").read_text(encoding="utf-8")
    assert "c.hidden = !AnimAtelie.imagem" in js.split("function animFolha", 1)[1].split("\n}\n", 1)[0]


def test_agora_sem_resposta_do_pc_diz_sem_dados():
    js = (APP / "orquestrador.js").read_text(encoding="utf-8")
    carregar = js.split("async function orqCarregar()", 1)[1].split("\n}\n", 1)[0]
    assert "orqSemDados(err)" in carregar
    corpo = js.split("function orqSemDados", 1)[1].split("\n}\n", 1)[0]
    for alvo in ("orq-principal", "orq-agora", "sem dados — ", "coordMesaSemDados",
                 # 2ª rodada da v72: a Fila, os resumos e os botões também
                 "orq-fila-situacao", "orq-fila", "orq-capacidade-resumo", "orq-modelos-resumo",
                 "orqControlesSemPC(true)", "pedidosSemDados", "diagnosticoPC(err)"):
        assert alvo in corpo, alvo
    assert "orqControlesSemPC(false)" in carregar                 # o PC voltou: religa
    coord = (APP / "coordenador.js").read_text(encoding="utf-8")
    # a leitura que falhou não afirma FORA DO AR: isso só com `vivo: false`
    linha = coord.split("function coordMesaSemDados", 1)[1].split("\n}\n", 1)[0]
    assert "FORA DO AR" not in linha and "sem dados — " in linha
    assert "pedidosSemDados(err)" in coord.split("async function pedidosCarregar", 1)[1].split(
        "\n}\n", 1)[0]


def test_um_diagnostico_so_para_a_faixa_e_os_cartoes():
    """Com 502 a faixa dizia "o servidor do app está parado" e a Agora "PC fora
    do ar" na mesma tela (conferente, 14/10, v72)."""
    assert "diagnosticoPC(err)" in APP_JS.split("function conexao", 1)[1].split("\n}\n", 1)[0]
    coord = (APP / "coordenador.js").read_text(encoding="utf-8")
    assert "diagnosticoPC(err).motivo" in coord.split("async function coordCarregar", 1)[1]
    for nome in ("orquestrador.js", "coordenador.js"):
        assert "PC fora do ar" not in (APP / nome).read_text(encoding="utf-8"), nome


def test_a_agora_nao_redesenha_o_estado_guardado_como_se_fosse_de_agora():
    """Até a v72 o catch do carregarAgora redesenhava o último /api/estado
    guardado (Próxima postagem, Fábricas) como se o PC tivesse respondido."""
    corpo = APP_JS.split("async function carregarAgora", 1)[1].split("\n}\n", 1)[0]
    falha = corpo.split("} catch (err) {", 1)[1]
    assert "desenharEstado(" not in falha
    assert 'cartoesSemDados(["fabricas", "erros", "vila-gente", "vila-travas"]' in falha


def test_toda_tela_parada_tem_area_sem_pc_e_pulso():
    """Varredura da v72: as telas que não releem sozinhas entram nas áreas
    "sem dados" e ganham o pulso leve; a conexao dispara as duas pontas."""
    for tela in ("sprites", "assembleias", "decisoes", "comandos", "conversa", "videos",
                 "biblioteca", "relatorios", "diario", "arena", "atelie", "coordenador"):
        assert f'telas: ["{tela}"]' in APP_JS, tela
    conexao = APP_JS.split("function conexao", 1)[1].split("\n}\n", 1)[0]
    assert "areasSemPC(err)" in conexao and "areasDeVolta()" in conexao
    assert 'diag.tipo !== "erro"' in conexao                   # erro N de uma rota não apaga tudo
    assert "setInterval(pulsoPC, PULSO_PC_MS)" in APP_JS
    for nome, marca in (("vila.js", "vilaSemDados(err)"), ("oficina.js", "cartoesSemDados("),
                        ("equipe.js", "cartoesSemDados(")):
        assert marca in (APP / nome).read_text(encoding="utf-8"), nome


def test_v73_vila_sem_dado_velho_no_canvas_e_cartao_sem_null():
    vila = (APP / "vila.js").read_text(encoding="utf-8")
    desenhar = vila.split("function vilaDesenhar()", 1)[1].split("\n}\n", 1)[0]
    assert "const velho = !!Vila.falha" in desenhar
    assert "if (!velho) vilaDesenharCorreio(ctx)" in desenhar
    assert "!h.emote || velho" in desenhar
    cartao = vila.split("function vilaMostrarEscolhido", 1)[1].split("\n}\n", 1)[0]
    assert ".filter((x) => x != null)" in cartao
    assert "#tela-vila .placar > .orq-sem-dados" in CSS


def test_v73_pergaminho_fora_do_pre_e_religa_tudo_na_volta():
    assert '<div id="relatorio-sem-dados" class="oculto"' in HTML
    assert 'aviso: "relatorio-sem-dados", esconder: ["relatorio"], relerSempre: true' in APP_JS
    volta = APP_JS.split("function areasDeVolta", 1)[1].split("\n}\n", 1)[0]
    assert 'document.querySelectorAll("[data-sem-pc]")' in volta
    conversa = (APP / "conversa.js").read_text(encoding="utf-8")
    assert "Conversa.lidoEm" in conversa and 'trocar: ["conversa-casa", "conversa-carteiro"]' in APP_JS


def test_editor_deitado_tem_a_sobra_na_ultima_linha():
    """Deitado, a folha em `grid-row: 1 / span 8` esticava a coluna da direita
    ("Escolher folha" de y=109 para y=366). A folha atravessa as 10 linhas e a
    última (1fr) leva a sobra: a conta tem de bater com os filhos do editor."""
    assert "grid-template-rows: repeat(9, auto) 1fr" in CSS
    assert "#anim-editor .anim-folha { grid-column: 1; grid-row: 1 / -1;" in CSS
    from html.parser import HTMLParser

    vazios = {"input", "img", "br", "meta", "link", "source", "hr"}

    class Filhos(HTMLParser):
        def __init__(self):
            super().__init__()
            self.pilha, self.filhos = [], []

        def handle_starttag(self, tag, attrs):
            if self.pilha == ["anim-editor"]:
                self.filhos.append(tag)
            if self.pilha or dict(attrs).get("id") == "anim-editor":
                if tag not in vazios:
                    self.pilha.append(dict(attrs).get("id") or tag)

        def handle_endtag(self, tag):
            if self.pilha and tag not in vazios:
                self.pilha.pop()

    leitor = Filhos()
    leitor.feed(HTML)
    assert len(leitor.filhos) == 11, leitor.filhos           # 10 controles + a folha


def test_caixinha_nao_herda_a_largura_do_campo_comum():
    """`input {width: 100%}` punha a caixinha EM CIMA do rótulo no Ateliê."""
    assert "width: auto" in _bloco("input[type=checkbox], input[type=radio]")
    assert "min-height: 44px" in _bloco(
        "label.acao:has(> input[type=checkbox], > input[type=radio])")
