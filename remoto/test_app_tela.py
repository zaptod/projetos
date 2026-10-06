# -*- coding: utf-8 -*-
"""A prova de tela do app no Chrome (02/10/2026).

Este e o freio para coisas que passam nos testes de API, mas quebram quando o
celular de fato abre uma tela. Tudo abaixo usa servidor loopback, LOCALAPPDATA
e fichas de sprite temporarios; nunca le os dados que estao rodando no PC.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path

import pytest

from remoto import api_http, biblioteca, decisoes, orquestrador, painel_dados, vila_dados, vila_nova
from remoto.test_api_http import _AtividadeFalsa, _ControleFalso, _GradeFalsa
from esteira_sprites import config as sprites_config


NAVEGADOR = os.environ.get("NF_TESTE_NAVEGADOR") == "1"
CAPTURAS = Path(os.environ.get("TEMP", r"E:\tmp_pytest")) / "tela_app"
TELAS = {
    "agora": ("agora", "oficina", "equipe", "coordenador"),
    "decidir": ("decisoes", "sprites", "assembleias"),
    "mandar": ("comandos", "conversa"),
    "ver": ("videos", "biblioteca", "relatorios", "diario"),
    "arena": ("arena", "atelie"),
}
# Deixe aqui, explicitamente, qualquer 404 que seja normal para uma tela.
# Hoje nao ha nenhum: um novo 404 de API precisa ser explicado antes de entrar.
API_404_ESPERADOS: set[str] = set()
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/"
    "d8zj4QAAAABJRU5ErkJggg==")


def _decisoes_de_fixture():
    projetos = []
    for projeto in decisoes.PROJETOS:
        pendente = int(projeto == "geral")
        projetos.append({"id": projeto, "rotulo": decisoes.ROTULOS[projeto],
                         "contagem": {"bloqueada": 0, "pendente": pendente,
                                      "decidida": 0, "a_rever": 0, "nao_lidas": 0}})
    item = {"id": "decisao-de-tela", "projeto": "geral", "titulo": "Decisao de tela",
            "pergunta": "A tela abriu?", "contexto": "Fixture da prova de navegador.",
            "opcoes": [{"id": "sim", "rotulo": "Sim", "descricao": "A tela abriu."}],
            "situacao": "pendente", "vigente": None, "historico": [], "midias": [],
            "comentario": False, "depende_de": [], "a_rever_se_mudar": [],
            "nao_lidas": 0, "consequencias": [], "criado": "2026-10-02T00:00:00"}
    return {"projetos": projetos,
            "arvores": {p: ([{"id": item["id"], "nivel": 0}] if p == "geral" else [])
                        for p in decisoes.PROJETOS},
            "itens": {item["id"]: item},
            "leitor": {"nao_lidas": 0, "eventos_ilegiveis": 0, "erro_da_mesa": ""}}


def _coordenador_pulsou(local: Path, segundos_atras: float) -> None:
    """O retrato que o coordenador (o servidor) publica a cada pulso."""
    pasta = local / "neural-fights" / "coordenador"
    pasta.mkdir(parents=True, exist_ok=True)
    pulso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - segundos_atras))
    (pasta / "estado.json").write_text(json.dumps(
        {"pid": 11840, "desde": pulso, "pulso_em": pulso, "versao": "teste",
         "servicos": {}, "acoes_pc": [], "eventos": []}), encoding="utf-8")


@pytest.fixture
def tela_isolada(tmp_path, monkeypatch):
    """Servidor e fontes da tela: so fixtures, inclusive LOCALAPPDATA."""
    local = tmp_path / "localappdata"
    local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("NF_IAS_PASTA", str(tmp_path / "ias"))
    monkeypatch.setattr(api_http, "ARQUIVO", local / "app_celular.json")
    monkeypatch.setattr(api_http, "PASTA_ARENA", tmp_path / "arena")      # nunca as lutas reais
    monkeypatch.setattr(biblioteca, "PASTA", local / "biblioteca")
    atividade = _AtividadeFalsa()
    monkeypatch.setattr(painel_dados, "_atividade", lambda: atividade)
    monkeypatch.setattr(painel_dados, "_controle", lambda: _ControleFalso())
    monkeypatch.setattr(painel_dados, "_grade", lambda: _GradeFalsa())
    monkeypatch.setattr(painel_dados._Previsao, "disponivel", staticmethod(lambda: False))
    monkeypatch.setattr(painel_dados, "_RELATORIOS_CACHE", {})
    monkeypatch.setattr(painel_dados, "videos", lambda n=40: [])
    # a Mesa de verdade (04/10), com tudo na pasta do teste: o orquestrador mora
    # no LOCALAPPDATA trocado; o coordenador (o servidor) pulsa ali tambem
    monkeypatch.setattr(orquestrador, "USO_EXTRA", tmp_path / "uso_sessao.json")
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(local / "neural-fights" / "coordenador"))
    _coordenador_pulsou(local, 0)
    monkeypatch.setattr(decisoes, "para_o_app", _decisoes_de_fixture)
    monkeypatch.setattr(vila_dados, "estado", lambda: {"placar": [], "travas": [], "fabricas": []})
    monkeypatch.setattr(vila_nova.MOTOR, "retrato", lambda: {})
    monkeypatch.setattr(vila_nova, "mundo", lambda: {"retrato": {"escala": 1, "versao": "teste"}})

    raiz = tmp_path / "esteira_sprites"
    monkeypatch.setattr(sprites_config, "RAIZ", raiz)
    pasta = raiz / sprites_config.PERFIS["palco"].subpasta / "fogo"
    pasta.mkdir(parents=True)
    (pasta / "limpo.png").write_bytes(PNG_1X1)
    (pasta / "ficha.json").write_text(json.dumps({
        "item_id": "fogo", "perfil": "palco", "estado": "a_conferir",
        "item": {"id": "fogo", "descricao": "Fogo de fixture"},
        "tentativas": [{"caminhos": {"limpo": str(pasta / "limpo.png")},
                        "veredito": {"defeitos": []}, "portao_reprovou": []}],
    }), encoding="utf-8")

    from ias import assembleia
    monkeypatch.setattr(assembleia, "listar", lambda: [{
        "id": "assembleia-de-tela", "pergunta": "A tela abriu?", "situacao": "rodada_1",
        "participantes": ["gemini"], "rodada_1": {"respostas": {}}, "rodada_2": None,
    }])
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    fio = threading.Thread(target=srv.serve_forever, daemon=True)
    fio.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def _esperar_tela(page, nome):
    page.locator(f"#tela-{nome}:not(.oculto)").wait_for(state="visible")
    page.wait_for_timeout(300)
    if nome == "sprites":
        page.wait_for_function("""() => [...document.querySelectorAll('#sprites-lista img')]
            .some((img) => img.src.startsWith('blob:'))""")
    page.wait_for_function("""() => [...document.images].filter((img) =>
        img.getClientRects().length && img.getBoundingClientRect().width).every((img) => img.complete)""")


def _imagens_visiveis_quebradas(page):
    return page.locator("img").evaluate_all("""imagens => imagens.filter((img) =>
        img.getClientRects().length && img.getBoundingClientRect().width && !img.naturalWidth)
        .map((img) => img.alt || img.src)""")


def _abrir_todas_as_telas(page, tamanho):
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    quebradas = []

    def clicar(seletor):
        page.locator(seletor).wait_for(state="visible")
        page.evaluate("seletor => document.querySelector(seletor).click()", seletor)

    def capturar(nome):
        _esperar_tela(page, nome)
        if nome == "equipe":
            page.locator("#tela-equipe details").evaluate_all(
                "cartoes => cartoes.forEach((cartao) => { cartao.open = true; })")
            assert page.locator("#tela-equipe").evaluate("tela => tela.scrollWidth <= tela.clientWidth")
        quebradas.extend(f"{nome}: {imagem}" for imagem in _imagens_visiveis_quebradas(page))
        page.screenshot(path=str(CAPTURAS / f"{tamanho[0]}x{tamanho[1]}-{nome}.png"),
                        full_page=True)

    capturar("vila")
    for objeto, abas in TELAS.items():
        clicar(f"#obj-{objeto}")
        capturar(abas[0])
        atual = abas[0]
        for aba in abas[1:]:
            clicar(f"#tela-{atual} [data-aba-tela='{aba}']")
            capturar(aba)
            atual = aba
        clicar("#btn-voltar")
        _esperar_tela(page, "vila")
    return quebradas


@pytest.mark.parametrize("tamanho", [(390, 844), (844, 390)])
def test_o_app_abre_vila_objetos_e_abas_sem_erros_de_tela(tela_isolada, tamanho):
    """Console, CSP, imagens e respostas de API sao parte da tela entregue."""
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{tela_isolada.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    assert token
    pageerrors, console_errors, api_erros = [], [], []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": tamanho[0], "height": tamanho[1]},
                              is_mobile=True, has_touch=True, service_workers="block")
        ctx.set_default_timeout(5000)
        page = ctx.new_page()
        page.on("pageerror", lambda erro: pageerrors.append(str(erro)))
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        def resposta(resp):
            if resp.status < 400:
                return
            if not resp.url.startswith(base + "/api/"):
                # recurso fora da /api (imagem da Vila, video, arte) tambem conta,
                # e com a URL: so "Failed to load resource 401" nao diz qual (02/10)
                api_erros.append(f"{resp.status} {resp.url[len(base):].split('?', 1)[0]}")
                return
            rota = resp.url[len(base):].split("?", 1)[0]
            if resp.status == 404 and rota in API_404_ESPERADOS:
                return
            api_erros.append(f"{resp.status} {rota}")

        page.on("response", resposta)
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([token]) => localStorage.setItem('painel.token', token)", [token])
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('pareado')")
        imagens_quebradas = _abrir_todas_as_telas(page, tamanho)
        # As promessas de fetch da ultima aba ainda podem terminar depois do clique.
        time.sleep(0.4)
        assert not pageerrors, pageerrors
        assert not console_errors, (console_errors, api_erros)
        assert not imagens_quebradas, imagens_quebradas
        assert not api_erros, api_erros
        nav.close()


def test_agora_mostra_o_servidor_e_nao_a_sessao_fechada(tela_isolada, tmp_path):
    """04/10/2026: com o coordenador pulsando e o VS Code fechado, o Agora diz
    "Servidor no ar", sem faixa nem selo vermelho; com o coordenador sem pulso
    ha 10 min, a faixa e o selo acendem. Conferido pelo DOM, no Chrome."""
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    local = Path(os.environ["LOCALAPPDATA"])
    base = f"http://127.0.0.1:{tela_isolada.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    erros = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
        ctx.set_default_timeout(8000)
        page = ctx.new_page()
        page.on("pageerror", lambda erro: erros.append(str(erro)))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([token]) => localStorage.setItem('painel.token', token)", [token])
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('pareado')")
        page.locator("#obj-agora").wait_for(state="visible")
        page.evaluate("() => document.querySelector('#obj-agora').click()")
        page.locator("#orq-servidor").wait_for(state="visible")
        servidor = page.locator("#orq-servidor").inner_text()
        assert "no ar" in servidor and "Servidor no ar · pulso às" in servidor
        assert "VS Code: fechado" in page.locator("#orq-vscode").inner_text()
        assert "oculto" in (page.locator("#orq-faixa").get_attribute("class") or "")
        assert "selo-alerta" not in (page.locator("#obj-agora").get_attribute("class") or "")
        corpo = page.locator("#tela-agora").inner_text()
        assert "essão fechada" not in corpo and "ouvindo" not in corpo
        page.screenshot(path=str(CAPTURAS / "agora-servidor-no-ar.png"))
        page.screenshot(path=str(CAPTURAS / "agora-servidor-no-ar-inteira.png"), full_page=True)

        # o servidor para de pulsar: isso sim e alarme (a tela rele a cada 10 s)
        _coordenador_pulsou(local, 600)
        page.locator("#orq-faixa:not(.oculto)").wait_for(state="visible", timeout=20000)
        assert "Servidor sem pulso desde" in page.locator("#orq-faixa").inner_text()
        assert "sem pulso" in page.locator("#orq-servidor-selo").inner_text()
        assert "selo-alerta" in (page.locator("#obj-agora").get_attribute("class") or "")
        page.screenshot(path=str(CAPTURAS / "agora-servidor-sem-pulso.png"))
        nav.close()
    assert not erros, erros


@pytest.mark.parametrize("tema", ["light", "dark"])
def test_a_biblioteca_mostra_o_fluxo_de_um_pedido(tela_isolada, tema):
    """05/10/2026: a aba 🧭 Fluxo da Biblioteca (o caminho de um pedido) em
    390x844, clicando: abre, cabe na largura sem rolar de lado, as sete etapas
    e os quatro caminhos de erro aparecem, as setas em SVG tem tamanho, e
    voltar para Paginas esconde o fluxo. Conferido pelo DOM."""
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{tela_isolada.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    erros = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block", color_scheme=tema)
        ctx.set_default_timeout(8000)
        page = ctx.new_page()
        page.on("pageerror", lambda erro: erros.append(str(erro)))
        page.on("console", lambda msg: erros.append(msg.text) if msg.type == "error" else None)
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([token]) => localStorage.setItem('painel.token', token)", [token])
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('pareado')")
        page.evaluate("() => document.querySelector('#obj-ver').click()")
        page.locator("#tela-videos:not(.oculto)").wait_for(state="visible")
        page.evaluate("() => document.querySelector(\"#tela-videos [data-aba-tela='biblioteca']\").click()")
        page.locator("#tela-biblioteca:not(.oculto)").wait_for(state="visible")
        assert page.locator("#biblioteca-fluxo").is_hidden()
        page.locator("#biblioteca-abas button[data-aba='fluxo']").click()
        page.locator("#biblioteca-fluxo").wait_for(state="visible")
        assert page.locator("#biblioteca-lista").is_hidden()
        assert page.locator("#biblioteca-busca").is_hidden()
        assert page.locator("#biblioteca-abas button[data-aba='fluxo']").get_attribute(
            "aria-pressed") == "true"
        assert page.locator("#tela-biblioteca").evaluate("t => t.scrollWidth <= t.clientWidth")
        assert page.locator(".fluxo-passo").count() == 7
        assert page.locator(".fluxo-erro").count() == 4
        larguras = page.locator("#biblioteca-fluxo .fluxo-passo, #biblioteca-fluxo .fluxo-erro, "
                                "#biblioteca-fluxo .fluxo-entrada").evaluate_all(
            "caixas => caixas.map((c) => [c.getBoundingClientRect().left, c.getBoundingClientRect().right])")
        assert all(0 <= esq and dir_ <= 390 for esq, dir_ in larguras), larguras
        setas = page.locator("#biblioteca-fluxo svg").evaluate_all(
            "s => s.map((x) => [x.getBoundingClientRect().width, x.getBoundingClientRect().height])")
        assert len(setas) >= 7 and all(w > 0 and h > 0 for w, h in setas), setas
        texto = page.locator("#biblioteca-fluxo").inner_text()
        for trecho in ("Mesa de pedidos", "Orquestrador", "Permissão", "Despachante", "Vigia",
                       "Conferente", "Resposta", "Limite do Claude", "Espera do Grimório",
                       "Conflito", "reabrir-pedido"):
            assert trecho in texto, trecho
        # a tela rola por dentro (o full_page so pega a 1a dobra): uma
        # captura por dobra, para conferir a pagina inteira no celular
        altura = page.locator("#tela-biblioteca").evaluate("t => t.scrollHeight")
        for n, topo in enumerate(range(0, altura, 760)):
            page.locator("#tela-biblioteca").evaluate("(t, y) => { t.scrollTop = y; }", topo)
            page.wait_for_timeout(100)
            page.screenshot(path=str(CAPTURAS / f"biblioteca-fluxo-{tema}-{n}.png"))
        page.locator("#tela-biblioteca").evaluate("t => { t.scrollTop = 0; }")
        page.locator("#biblioteca-abas button[data-aba='paginas']").click()
        assert page.locator("#biblioteca-fluxo").is_hidden()
        assert page.locator("#biblioteca-lista").is_visible()
        assert page.locator("#biblioteca-busca").is_visible()
        nav.close()
    assert not erros, erros


def test_ligar_o_gerente_fica_ligado(tela_isolada, tmp_path, monkeypatch):
    """05/10/2026: o Adrian marcava "gerente ligado" e o recarregar de 5 s da
    Equipe desmarcava antes do Salvar. Agora a caixinha salva na hora e
    continua marcada depois de dois recarregamentos."""
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    delegados = tmp_path / "delegados"
    delegados.mkdir()
    monkeypatch.setenv("NF_DELEGADOS_PASTA", str(delegados))
    # o app de verdade roda com --acoes; sem isso a Equipe responde 403
    monkeypatch.setattr(tela_isolada.RequestHandlerClass.estado, "com_acoes", True)
    base = f"http://127.0.0.1:{tela_isolada.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    erros = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
        ctx.set_default_timeout(8000)
        page = ctx.new_page()
        page.on("pageerror", lambda erro: erros.append(str(erro)))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([token]) => localStorage.setItem('painel.token', token)", [token])
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('pareado')")
        page.evaluate("() => document.querySelector('#obj-agora').click()")
        page.evaluate("() => document.querySelector(\"#tela-agora [data-aba-tela='equipe']\").click()")
        caixa = page.locator("#equipe-gerente-ligado")
        caixa.wait_for(state="attached")
        page.wait_for_timeout(1500)
        assert not caixa.is_checked()
        page.evaluate("() => document.querySelector('#equipe-gerente-ligado').click()")
        page.wait_for_timeout(11000)          # dois recarregamentos de 5 s
        assert caixa.is_checked()
        assert "Gerente ligado" in (page.locator("#equipe-gerente").text_content() or "")
        page.screenshot(path=str(CAPTURAS / "equipe-gerente-ligado.png"), full_page=True)
        nav.close()
    salvo = json.loads((delegados / "config.json").read_text(encoding="utf-8"))
    assert salvo["gerente_ligado"] is True
    assert not erros, erros


@pytest.mark.parametrize("tema", ["light", "dark"])
def test_responder_no_cartao_do_pedido_vai_ao_mesmo_pedido(tela_isolada, monkeypatch, tema):
    """05/10/2026 (pedido honesto v2): o pedido que parou esperando voce so
    recebe a resposta EXPLICITA. O botao Responder do cartao Pedir abre a
    caixa, e o texto chega ao MESMO pedido (pela rota com o id)."""
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    from coordenador import pedidos
    monkeypatch.setattr(tela_isolada.RequestHandlerClass.estado, "com_acoes", True)
    p = pedidos.registrar("arquive os vídeos antigos no Google Drive", "app", novo=True)
    with pedidos._TRAVA:
        dados = pedidos._ler()
        alvo = next(x for x in dados["pedidos"] if x["id"] == p["id"])
        alvo.update(situacao="esperando_voce", trabalhador=p["id"], ia="codex",
                    motivo="bloqueado: falta o Adrian entrar na conta de 5 TB do Drive")
        pedidos._gravar(dados)
    base = f"http://127.0.0.1:{tela_isolada.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    erros = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block", color_scheme=tema)
        ctx.set_default_timeout(8000)
        page = ctx.new_page()
        page.on("pageerror", lambda erro: erros.append(str(erro)))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([token]) => localStorage.setItem('painel.token', token)", [token])
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('pareado')")
        page.evaluate("() => document.querySelector('#obj-agora').click()")
        cartao = page.locator("#pedido-estado .coord-proposta").first
        cartao.wait_for(state="visible")
        assert "esperando você · arquive" in cartao.inner_text()
        assert "no Grimório" not in cartao.inner_text()          # nao espera nenhum no
        cartao.get_by_role("button", name="Responder").click()
        caixa = page.locator("#pedido-estado .pedido-resposta")
        caixa.wait_for(state="visible")
        caixa.fill("já loguei no Drive")
        page.wait_for_timeout(6000)              # um recarregamento de 5 s nao apaga a caixa
        assert caixa.input_value() == "já loguei no Drive"
        assert page.locator("#tela-agora").evaluate("t => t.scrollWidth <= t.clientWidth")
        cartao.screenshot(path=str(CAPTURAS / f"pedido-responder-390x844-{tema}.png"))
        page.screenshot(path=str(CAPTURAS / f"pedido-responder-tela-390x844-{tema}.png"))
        page.locator("#pedido-estado").get_by_role("button", name="Enviar a este pedido").click()
        page.locator("#pedido-estado .pedido-resposta").wait_for(state="detached")
        nav.close()
    atual = next(x for x in pedidos.para_o_app()["pedidos"] if x["id"] == p["id"])
    assert atual["continuar"] is True and atual["texto"].endswith("já loguei no Drive")
    assert len(pedidos.para_o_app()["pedidos"]) == 1                 # nenhum pedido novo
    assert not erros, erros


def test_a_conversa_responde_como_gente_e_o_pedido_ganha_recibo(tela_isolada, monkeypatch):
    """06/10/2026: "Ola" recebia o retrato com ids e "Orquestrador?" ficava na
    fila de trabalho sem resposta. Clicando na Conversa: a mensagem mostra
    "pensando…", a resposta da thread da conversa aparece sozinha (sem id), e
    o pedido de trabalho ganha na hora o recibo de gente."""
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    from patchright.sync_api import sync_playwright

    from coordenador import pedidos
    monkeypatch.setattr(tela_isolada.RequestHandlerClass.estado, "com_acoes", True)
    monkeypatch.setattr(pedidos.MESA, "conversador",
                        lambda _prompt: "Oi, Adrian! Tô aqui, sem nada rodando agora.")
    base = f"http://127.0.0.1:{tela_isolada.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    erros = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block")
        ctx.set_default_timeout(12000)
        page = ctx.new_page()
        page.on("pageerror", lambda erro: erros.append(str(erro)))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([token]) => localStorage.setItem('painel.token', token)", [token])
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('pareado')")
        page.evaluate("() => document.querySelector('#obj-agora').click()")
        page.locator("#tela-agora [data-aba-tela='coordenador']").click()
        page.locator("#coord-abas [data-aba='conversa']").click()
        page.locator("#coord-texto").fill("Orquestrador?")
        page.locator("#coord-enviar").click()
        mensagens = page.locator("#coord-mensagens")
        page.wait_for_function("() => document.querySelector('#coord-mensagens')"
                               ".innerText.includes('pensando…')")
        assert "Respondendo na Conversa" in page.locator("#toast").inner_text()
        assert pedidos.para_o_app()["pedidos"][0]["papo"] == "pensando"
        pedidos.atender_conversa()                     # a thread `conversa` do pulso
        page.wait_for_function("() => document.querySelector('#coord-mensagens')"
                               ".innerText.includes('Tô aqui, sem nada rodando')")
        texto = mensagens.inner_text()
        assert "pensando…" not in texto and "pedido-" not in texto and "Retrato" not in texto
        page.screenshot(path=str(CAPTURAS / "conversa-gente-390x844.png"))
        page.locator("#toast.oculto").wait_for(state="attached")
        page.locator("#coord-texto").fill("arrume o botão Publicar do app")
        page.locator("#coord-enviar").click()
        page.wait_for_function("() => document.querySelector('#coord-mensagens')"
                               ".innerText.includes('Entendi: «arrume o botão Publicar do app».')")
        texto = mensagens.inner_text()
        assert "te aviso aqui quando ficar pronto" in texto and "pedido-" not in texto
        assert "Entendi" in page.locator("#toast").inner_text()
        assert "pedido-" not in page.locator("#toast").inner_text()
        page.locator("#toast.oculto").wait_for(state="attached")
        mensagens.screenshot(path=str(CAPTURAS / "conversa-recibo-390x844.png"))
        nav.close()
    assert not erros, erros


@pytest.mark.parametrize("tema", ["light", "dark"])
def test_permissao_de_estado_no_cartao_tem_permitir_e_nao_responder(tela_isolada, monkeypatch,
                                                                    tmp_path, tema):
    """Conferente 3 (defeito 7): o cartao "esperando voce · ligue o gerente"
    mostrava Responder, que NEGAVA a permissao. Agora mostra Permitir/Negar
    (a rota de Agora › Equipe), e o caminho real liga o gerente da PASTA DO
    TESTE: delegar de verdade, servidor isolado, Chrome a 390x844."""
    if not NAVEGADOR:
        pytest.skip("so com NF_TESTE_NAVEGADOR=1")
    import json
    import os
    from patchright.sync_api import sync_playwright

    from coordenador import pedidos
    from remoto import delegar
    monkeypatch.setenv("NF_DELEGADOS_PASTA", str(tmp_path / "delegados"))
    monkeypatch.setattr(delegar, "PASTA", None)
    real = os.path.join(os.environ.get("LOCALAPPDATA", ""), "neural-fights", "delegados")
    assert os.path.normcase(str(delegar.pasta())) != os.path.normcase(real)
    delegar.gravar_config({"gerente_ligado": False})
    monkeypatch.setattr(tela_isolada.RequestHandlerClass.estado, "com_acoes", True)
    p = pedidos.registrar("ligue o gerente da equipe", "app")
    ident = p["id"]
    pasta = delegar.pasta_da(ident)
    pasta.mkdir(parents=True)
    (pasta / "estado.json").write_text(json.dumps({
        "id": ident, "situacao": "terminou", "cargo": "orquestrador", "ia": "claude",
        "worktree": str(pasta / "wt")}), encoding="utf-8")
    pp = delegar.registrar_pedido_permissao(ident, {
        "o_que": "o servidor executar `gerente ligar`", "categoria": "estado_do_servidor",
        "por_que": "x", "alvo": "gerente ligar", "avisado": "coordenador"})["pedido_permissao"]
    with pedidos._TRAVA:
        dados = pedidos._ler()
        alvo = next(x for x in dados["pedidos"] if x["id"] == ident)
        alvo.update(situacao="esperando_voce", trabalhador=ident, ia="claude",
                    motivo="o trabalhador pediu `gerente ligar` (estado do servidor): toque "
                           "Permitir ou Negar no pedido",
                    permissao_estado={"nome": "gerente", "args": ["ligar"],
                                      "comando": "gerente ligar", "trabalhador": ident,
                                      "em": pp["em"], "regra": pp["regra"]})
        pedidos._gravar(dados)
    base = f"http://127.0.0.1:{tela_isolada.server_address[1]}"
    token = api_http.trocar_codigo(api_http.novo_codigo(), "chrome-de-teste")
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    erros = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chrome", headless=True)
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                              has_touch=True, service_workers="block", color_scheme=tema)
        ctx.set_default_timeout(8000)
        page = ctx.new_page()
        page.on("pageerror", lambda erro: erros.append(str(erro)))
        page.goto(base + "/", wait_until="domcontentloaded")
        page.evaluate("([token]) => localStorage.setItem('painel.token', token)", [token])
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.body.classList.contains('pareado')")
        page.evaluate("() => document.querySelector('#obj-agora').click()")
        cartao = page.locator("#pedido-estado .coord-proposta").first
        cartao.wait_for(state="visible")
        texto = cartao.inner_text()
        assert "esperando você · ligue o gerente" in texto and ident in texto
        assert cartao.get_by_role("button", name="Responder").count() == 0
        assert cartao.get_by_role("button", name="✅ Permitir").count() == 1
        assert cartao.get_by_role("button", name="❌ Negar").count() == 1
        assert page.locator("#pedido-novo").count() == 0                 # o "Novo assunto" saiu
        assert page.locator("#tela-agora").evaluate("t => t.scrollWidth <= t.clientWidth")
        cartao.screenshot(path=str(CAPTURAS / f"pedido-permissao-390x844-{tema}.png"))
        cartao.get_by_role("button", name="✅ Permitir").click()
        page.wait_for_function("() => document.querySelector('#pedido-estado').innerText"
                               ".includes('Decidido: o servidor cuida')")
        assert cartao.get_by_role("button", name="✅ Permitir").count() == 0   # nao pede de novo
        nav.close()
    ficha = delegar.ler_estado(ident)
    assert ficha["situacao"] == "terminou" and not ficha.get("pedido_permissao")
    assert ficha["permissoes"][-1]["decisao"] == "permitir"
    assert delegar.ler_config()["gerente_ligado"] is False         # quem executa e o pulso
    pedidos.passo()
    atual = next(x for x in pedidos.para_o_app()["pedidos"] if x["id"] == ident)
    assert atual["situacao"] == "respondido", atual
    assert delegar.ler_config()["gerente_ligado"] is True           # da pasta do teste
    assert len(pedidos.para_o_app()["pedidos"]) == 1
    assert not erros, erros
