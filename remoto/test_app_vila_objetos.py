# -*- coding: utf-8 -*-
"""A Vila é a tela do app, e as outras áreas são objetos dela (28/09/2026).

A reforma mexeu só na casca (html, css, js). O risco é função perdida: um
botão que sumiu do HTML e que o JavaScript ainda procura (e então falha em
silêncio), ou uma área que ficou sem objeto para abrir. Estes testes leem os
arquivos da PWA e conferem as duas coisas.

Desde 02/10/2026 a prateleira tem QUATRO objetos, um por pergunta (decisão do
Adrian, app-e-bot/app-reorganizar). A lista cravada de cada função antiga e
onde ela ficou mora em `test_app_quatro_objetos.py`.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent / "app"
HTML = (APP / "index.html").read_text(encoding="utf-8")
JS = {n: (APP / n).read_text(encoding="utf-8")
      for n in ("app.js", "vila.js", "comandos.js", "decisoes.js", "orquestrador.js",
                "coordenador.js", "conversa.js", "oficina.js", "biblioteca.js")}

# os quatro objetos da prateleira (02/10/2026): o rótulo e a aba que abre
# da primeira vez (`data-tela`)
OBJETOS = {"agora": ("Agora", "agora"), "decidir": ("Decidir", "decisoes"),
           "mandar": ("Mandar", "comandos"), "ver": ("Ver", "videos"),
           "arena": ("Arena", "arena")}

# o que cada área faz hoje e não pode sumir (id no HTML)
FUNCOES = [
    # o antigo quadro de avisos (em Agora desde 02/10): estado, erros, travas
    "vila-gente", "proxima", "pausa", "previsao", "fabricas", "erros", "vila-travas",
    # o controle (pausar/retomar/parar): junto dos comandos desde 28/09
    "controle", "alvo-pausa", "prazo-pausa", "btn-pausar", "btn-retomar", "btn-parar",
    # o orquestrador (a antiga Mesa de comando, hoje em Agora, Mandar e Decidir)
    "orq-agora", "orq-fila", "orq-pausar-fila", "orq-retomar-fila", "orq-max",
    "orq-mais", "orq-menos", "orq-modos", "orq-teto", "orq-forca", "orq-limites",
    "orq-grafico", "orq-decisoes", "orq-acessos", "orq-fluxo", "orq-mensagem",
    "orq-enviar", "orq-comandos", "orq-faixa", "obj-agora", "orq-carteiro",
    # a conversa com uma IA (fase 2 da Vila das IAs)
    "conversa-ias", "conversa-casa", "conversa-carteiro", "conversa-historico",
    "conversa-texto", "conversa-anexo", "conversa-anexo-nome", "conversa-enviar",
    # pedir imagem (29/09, tarde): Criar, galeria e a tela cheia
    "conversa-modos", "conversa-galeria", "conversa-criar", "conversa-caixa-texto",
    "criar-aviso", "criar-prompt", "criar-proporcao", "criar-modelo", "criar-modelo-rotulo",
    "criar-contagem", "criar-enviar", "imagem-tela", "imagem-tela-img",
    "imagem-tela-legenda", "imagem-baixar", "imagem-compartilhar", "imagem-fechar",
    # o interruptor do Claude (29/09): uma vez só, em Mandar, desde 02/10;
    # a faixa "proibido" fica em Agora
    "claude-faixa", "claude-bancada",
    # o Codex (01/10): o cartao da Mesa, a Oficina e os tres seletores de modelo
    "orq-codex", "orq-abrir-oficina", "orq-modelo-claude", "orq-modelo-codex",
    "orq-modelo-gemini", "orq-modelo-codex-livre", "orq-modelo-codex-nome",
    "tela-oficina", "oficina-lista", "oficina-uso", "oficina-tarefa", "oficina-eventos",
    "oficina-diff", "oficina-testes", "oficina-pedido", "oficina-resposta", "oficina-abas",
    # vila
    "vila-canvas", "vila-placar", "vila-escolhido", "vila-mais", "vila-menos",
    # diário
    "diario", "diario-filtro", "btn-todas",
    # vídeos: gerar, tocar e publicar (a publicação usa o diálogo de destinos)
    "gerar-cartao", "btn-gerar", "restantes", "player", "videos",
    # Arena: dois lutadores, mapa, semente, render e histórico de MP4s
    "arena-p1-busca", "arena-p1-lista", "arena-vs", "arena-p2-busca", "arena-p2-lista",
    "arena-mapa", "arena-semente", "arena-dado", "arena-lutar", "arena-progresso", "arena-lutas",
    # comandos: o histórico ("Últimos que você mandou"), o log e o catálogo
    # (inclui a zona de perigo)
    "comandos-ultimos", "tarefas-lista", "tarefa-log", "btn-fechar-log", "comandos-grupos",
    # relatórios e decisões
    "abas-relatorio", "relatorio", "decisoes-abas", "decisoes-lista",
    "decisao-item", "sprites-lista",
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
    objetos = {o: (rotulo.strip(), aba) for o, aba, rotulo in re.findall(
        r'data-objeto="([^"]+)" data-tela="([^"]+)"><span>[^<]*</span>([^<]+)</button>', HTML)}
    assert objetos == OBJETOS
    for _rotulo, aba in OBJETOS.values():
        assert f'id="tela-{aba}"' in HTML
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
    telas = set(re.findall(r'<section id="tela-([\w-]+)"', HTML)) - {"parear"}
    assert {"vila", "agora", "oficina", "coordenador", "comandos"} <= telas
    for tela in telas:
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
    # v20 = pedir imagem (29/09); v21 = lote da semana (30/09); v22 = modulo
    # que nao chegou (30/09, tarde: o 502 cai na copia guardada); v23 = a
    # Oficina do Codex e os Modelos (01/10); v24 = Biblioteca; v26 = Coordenador;
    # v29 = os quatro objetos, um por pergunta (02/10); v30 = a Vila toca as
    # folhas da esteira (02/10); v31 = Assembleia (02/10); v32 = conferência
    # de sprites pelo celular; v33 = Arena.
    assert "painel-casca-v33" in sw
    assert '"orquestrador.js"' in sw and '"conversa.js"' in sw and '"oficina.js"' in sw
    assert '"biblioteca.js"' in sw
    assert '"coordenador.js"' in sw
    assert '"assembleia.js"' in sw


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


def test_o_controle_mora_junto_dos_comandos():
    # decisão do Adrian (app-e-bot/controle-onde, 28/09/2026): "Na Bancada,
    # junto dos comandos". Desde 02/10 a Bancada é o objeto Mandar; e o
    # antigo quadro de avisos (onde ele morava antes) virou Agora.
    mandar, agora = _secao("comandos"), _secao("agora")
    for i in ("controle", "alvo-pausa", "prazo-pausa", "btn-pausar", "btn-retomar",
              "btn-parar"):
        assert f'id="{i}"' in mandar, i
        assert f'id="{i}"' not in agora, i


def test_as_secoes_da_antiga_mesa_moram_nos_objetos_e_o_servidor_serve_o_js():
    # a Mesa tinha 12 seções e uma fileira de atalhos (data-orq) para rolar
    # até elas; desde 02/10 cada seção mora no objeto da pergunta dela
    onde = {"agora": ("agora", "codex", "fila", "capacidade", "modelos", "limites",
                      "fluxo", "acessos"),
            "comandos": ("mensagem", "comandos"), "decisoes": ("decisoes",)}
    for tela, secoes in onde.items():
        for sec in secoes:
            assert f'id="orq-sec-{sec}"' in _secao(tela), (tela, sec)
    assert "data-orq=" not in HTML
    from remoto import api_http
    assert api_http.ESTATICOS["/orquestrador.js"][0] == "orquestrador.js"
    assert '<script src="orquestrador.js"></script>' in HTML
