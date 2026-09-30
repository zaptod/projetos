# -*- coding: utf-8 -*-
"""A Vila é a tela do app, e as outras áreas são objetos dela (28/09/2026).

A reforma mexeu só na casca (html, css, js). O risco é função perdida: um
botão que sumiu do HTML e que o JavaScript ainda procura (e então falha em
silêncio), ou uma área que ficou sem objeto para abrir. Estes testes leem os
arquivos da PWA e conferem as duas coisas.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent / "app"
HTML = (APP / "index.html").read_text(encoding="utf-8")
JS = {n: (APP / n).read_text(encoding="utf-8")
      for n in ("app.js", "vila.js", "comandos.js", "decisoes.js", "orquestrador.js",
                "conversa.js")}

# as áreas de antes da reforma, cada uma com o seu objeto na vila
OBJETOS = {"quadro": "Avisos", "diario": "Diário", "videos": "Cinema",
           "comandos": "Bancada", "relatorios": "Pergaminhos",
           "decisoes": "Grimório", "orquestrador": "Comando"}

# o que cada área faz hoje e não pode sumir (id no HTML)
FUNCOES = [
    # quadro de avisos: estado, erros, travas
    "vila-gente", "proxima", "pausa", "previsao", "fabricas", "erros", "vila-travas",
    # o controle (pausar/retomar/parar): na Bancada desde 28/09
    "controle", "alvo-pausa", "prazo-pausa", "btn-pausar", "btn-retomar", "btn-parar",
    # mesa de comando (o orquestrador)
    "orq-agora", "orq-fila", "orq-pausar-fila", "orq-retomar-fila", "orq-max",
    "orq-mais", "orq-menos", "orq-modos", "orq-teto", "orq-forca", "orq-limites",
    "orq-grafico", "orq-decisoes", "orq-acessos", "orq-fluxo", "orq-mensagem",
    "orq-enviar", "orq-comandos", "orq-faixa", "obj-orquestrador", "orq-carteiro",
    # a conversa com uma IA (fase 2 da Vila das IAs)
    "conversa-ias", "conversa-casa", "conversa-carteiro", "conversa-historico",
    "conversa-texto", "conversa-anexo", "conversa-anexo-nome", "conversa-enviar",
    # pedir imagem (29/09, tarde): Criar, galeria e a tela cheia
    "conversa-modos", "conversa-galeria", "conversa-criar", "conversa-caixa-texto",
    "criar-aviso", "criar-prompt", "criar-proporcao", "criar-modelo", "criar-modelo-rotulo",
    "criar-contagem", "criar-enviar", "imagem-tela", "imagem-tela-img",
    "imagem-tela-legenda", "imagem-baixar", "imagem-compartilhar", "imagem-fechar",
    # o interruptor do Claude (29/09): no topo da Mesa e na Bancada
    "claude-mesa", "claude-faixa", "claude-bancada",
    # vila
    "vila-canvas", "vila-placar", "vila-escolhido", "vila-mais", "vila-menos",
    # diário
    "diario", "diario-filtro", "btn-todas",
    # vídeos: gerar, tocar e publicar (a publicação usa o diálogo de destinos)
    "gerar-cartao", "btn-gerar", "restantes", "player", "videos",
    # comandos: tarefas, log e o catálogo (inclui a zona de perigo)
    "tarefas-lista", "tarefa-log", "btn-fechar-log", "comandos-grupos",
    # relatórios e decisões
    "abas-relatorio", "relatorio", "decisoes-abas", "decisoes-lista",
    "decisao-item",
    # confirmação em dois passos e campos das fichas
    "dialogo", "dialogo-texto", "dialogo-destinos", "dialogo-sim",
    "dialogo-prazo", "dialogo-campos", "campos-corpo", "btn-campos-ok",
    # pareamento, conexão, voltar
    "codigo", "btn-parear", "aviso", "btn-tentar", "conexao", "toast",
    "btn-voltar",
]


def _ids(texto):
    return set(re.findall(r'id="([^"]+)"', texto))


def test_cada_area_tem_objeto_na_vila_e_uma_secao():
    telas = dict(re.findall(
        r'data-tela="([^"]+)"><span>[^<]*</span>([^<]+)</button>', HTML))
    assert telas == OBJETOS
    for tela in OBJETOS:
        assert f'id="tela-{tela}"' in HTML
    # a vila é a tela de fundo, sem objeto para ela mesma
    assert 'id="tela-vila"' in HTML and 'data-tela="vila"' not in HTML


def test_nenhuma_funcao_sumiu_do_html():
    faltam = [i for i in FUNCOES if i not in _ids(HTML)]
    assert not faltam, faltam
    for destino in ("youtube", "tiktok", "ambos"):
        assert f'value="{destino}"' in HTML


def test_todo_id_que_o_js_procura_existe():
    ids = _ids(HTML)
    for nome, fonte in JS.items():
        usados = (set(re.findall(r'\$\("([^"]+)"\)', fonte))
                  | set(re.findall(r'getElementById\("([^"]+)"\)', fonte)))
        assert not usados - ids, (nome, sorted(usados - ids))


def test_titulos_e_cargas_cobrem_todas_as_areas():
    fonte = JS["app.js"]
    titulos = re.search(r"const TITULOS = \{(.*?)\};", fonte, re.S).group(1)
    cargas = re.search(r"const CARGAS = \{(.*?)\};", fonte, re.S).group(1)
    for tela in [*OBJETOS, "vila"]:
        assert re.search(rf"\b{tela}:", titulos), tela
        assert re.search(rf"\b{tela}:", cargas), tela


def test_a_zona_de_perigo_e_a_publicacao_continuam_ligadas():
    # a zona de perigo vem do catálogo do servidor e a tela Bancada a monta
    assert "perigo" in JS["comandos.js"]
    assert "digite" in JS["comandos.js"].lower() or "digitar" in JS["comandos.js"].lower()
    # publicar: só com o servidor dizendo que pode, e sempre pelo diálogo
    assert "publicarLigado" in JS["app.js"] and "pedirPublicacao" in JS["app.js"]
    assert '"/api/acao/confirmar"' in JS["app.js"]


def test_o_cache_da_casca_mudou_de_versao():
    # sem trocar o nome do cache, o celular seguiria com a casca antiga
    sw = (APP / "sw.js").read_text(encoding="utf-8")
    assert "painel-casca-v21" in sw        # v20 = pedir imagem (29/09); v21 = lote da semana (30/09)
    assert '"orquestrador.js"' in sw and '"conversa.js"' in sw


def test_o_icone_novo_esta_no_manifest_na_casca_e_no_servidor():
    # 29/09: o cérebro de circuitos com as casinhas. Os PNGs são gerados de
    # uma fonte FORA do repositório (5,5 MB); aqui conferimos o que o celular
    # recebe: tamanhos certos, um maskable, o apple-touch e o favicon.
    import json

    from PIL import Image

    from remoto import api_http
    manifest = json.loads((APP / "manifest.webmanifest").read_text(encoding="utf-8"))
    vistos = {}
    for icone in manifest["icons"]:
        arq = APP / icone["src"]
        with Image.open(arq) as im:
            lado = f"{im.size[0]}x{im.size[1]}"
        assert lado == icone["sizes"], icone
        assert icone["type"] == "image/png"
        vistos.setdefault(icone["purpose"], []).append(lado)
        assert "/" + icone["src"] in api_http.ESTATICOS, icone["src"]
    assert sorted(vistos["any"]) == ["192x192", "512x512"]
    assert vistos["maskable"] == ["512x512"]
    # o maskable é opaco (o Android recorta o círculo/gota dele por cima)
    with Image.open(APP / "icones" / "icone-maskable-512.png") as im:
        assert im.mode == "RGB"
    assert manifest["theme_color"] == manifest["background_color"] == "#09256f"
    assert "icone.svg" not in HTML and "icone.svg" not in json.dumps(manifest)
    assert 'rel="apple-touch-icon" href="icones/apple-touch-icon.png"' in HTML
    assert 'href="icones/favicon-32.png"' in HTML
    for nome, lado in (("apple-touch-icon.png", 180), ("favicon-32.png", 32),
                       ("favicon-16.png", 16)):
        with Image.open(APP / "icones" / nome) as im:
            assert im.size == (lado, lado), nome
    assert api_http.ESTATICOS["/favicon.ico"][0] == "icones/favicon.ico"
    assert (APP / "icones" / "favicon.ico").exists()
    # a fonte grande NÃO entra no repositório
    assert not list((APP / "icones").glob("fonte*"))
    sw = (APP / "sw.js").read_text(encoding="utf-8")
    assert '"icones/icone-192.png"' in sw and "icone.svg" not in sw


def test_a_vila_deitada_tem_arranjo_proprio():
    # decisão vila-zoom-celular (28/09): "suporte se eu deitar o celular".
    # A classe do CSS e o arranjo da arte saem da MESMA pergunta, e girar
    # não recarrega nem desmarca (o cartão é redesenhado, não re-tocado).
    vila = JS["vila.js"]
    css = (APP / "app.css").read_text(encoding="utf-8")
    assert 'matchMedia("(orientation: landscape)")' in vila
    assert 'classList.toggle("deitado"' in vila
    assert "/vilanova-${vilaArranjoDesenhado()}.webp" in vila
    assert "location.reload" not in vila
    assert "vilaMostrarEscolhido()" in vila.split("function vilaGirou")[1][:400]
    for seletor in ("body.deitado nav.prateleira", "header .placar",
                    "body.deitado #tela-vila .vila-caixa", "body.deitado .livro"):
        assert seletor in css, seletor
    from remoto import api_http
    assert "/vilanova-paisagem.webp" in open(api_http.__file__, encoding="utf-8").read()


def _secao(tela):
    inicio = HTML.index(f'id="tela-{tela}"')
    fim = HTML.index("</section>", inicio)
    return HTML[inicio:fim]


def test_o_controle_mora_na_bancada():
    # decisão do Adrian (app-e-bot/controle-onde, 28/09/2026): "Na Bancada"
    bancada, avisos = _secao("comandos"), _secao("quadro")
    for i in ("controle", "alvo-pausa", "prazo-pausa", "btn-pausar", "btn-retomar",
              "btn-parar"):
        assert f'id="{i}"' in bancada, i
        assert f'id="{i}"' not in avisos, i


def test_a_mesa_tem_as_oito_secoes_e_o_servidor_serve_o_js():
    mesa = _secao("orquestrador")
    for sec in ("agora", "fila", "capacidade", "limites", "decisoes", "acessos",
                "fluxo", "mensagem"):
        assert f'id="orq-sec-{sec}"' in mesa, sec
        assert f'data-orq="orq-sec-{sec}"' in mesa, sec
    from remoto import api_http
    assert api_http.ESTATICOS["/orquestrador.js"][0] == "orquestrador.js"
    assert '<script src="orquestrador.js"></script>' in HTML
