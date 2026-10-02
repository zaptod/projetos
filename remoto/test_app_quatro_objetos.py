# -*- coding: utf-8 -*-
"""Os quatro objetos da prateleira, um por pergunta (02/10/2026).

Pedido do Adrian (02/10, 00:59): "E esse TAREFAS da bancada serve pra que??
Voce realmente acha que o app está bem organizado?". Ele escolheu no Grimório
(`app-e-bot/app-reorganizar` = "por-pergunta"): Agora, Decidir, Mandar e Ver.

A regra da reforma: NADA de funcionalidade se perde. A reescrita do painel
em 01/09 perdeu botões em silêncio (o freio da pipeline, "escolher
atributos"): o painel montava, os testes passavam e o botão não existia mais.
Por isso este arquivo CRAVA a lista de antes (a varredura da casca v28: 207
ids, 34 rotas, 43 handlers por id) e diz onde cada coisa ficou. Um id que
sumir, uma rota que ninguém chama mais, ou uma tela que volte a só abrir por
dentro de outra, quebram aqui.
"""
import re
from html.parser import HTMLParser
from pathlib import Path

APP = Path(__file__).resolve().parent / "app"
HTML = (APP / "index.html").read_text(encoding="utf-8")
CSS = (APP / "app.css").read_text(encoding="utf-8")
JS = {p.name: p.read_text(encoding="utf-8") for p in APP.glob("*.js") if p.name != "sw.js"}
TODO_JS = "\n".join(JS.values())

# ------------------------------------------------- a lista cravada (antes)
# Cada id da casca v28 e o objeto onde ele mora hoje. "fora" = não é de
# objeto nenhum: a Vila, o pareamento, o cabeçalho, os diálogos e o toast.
ONDE_FICOU = {
    "agora": [
        # o antigo Quadro de avisos
        "proxima", "pausa", "previsao", "fabricas", "erros", "vila-gente", "vila-travas",
        # a antiga Mesa: sessão principal, agentes, Codex, fila
        "claude-faixa", "orq-faixa", "orq-sec-agora", "orq-principal", "orq-resumo",
        "orq-agentes-titulo", "orq-agora", "orq-carteiro", "orq-concluidos",
        "orq-sec-codex", "orq-codex", "orq-abrir-oficina",
        "orq-sec-fila", "orq-fila", "orq-fila-situacao", "orq-adicionar-fila",
        "orq-pausar-fila", "orq-retomar-fila",
        # recolhidos no fim: capacidade, modelos, limites, fluxo, acessos
        "orq-sec-capacidade", "orq-max", "orq-mais", "orq-menos", "orq-efetivo", "orq-modos",
        "orq-modo-ajuda", "orq-teto", "orq-forca", "orq-capacidade-pendente", "orq-grimorio",
        "orq-cap-historico",
        "orq-sec-modelos", "orq-modelo-claude", "orq-modelo-claude-nota", "orq-modelo-codex",
        "orq-modelo-codex-livre", "orq-modelo-codex-nome", "orq-modelo-codex-pedir",
        "orq-modelo-codex-nota", "orq-modelo-gemini", "orq-modelo-gemini-nota",
        "orq-modelos-pendente",
        "orq-sec-limites", "orq-teto-aviso", "orq-limites", "orq-grafico", "orq-grafico-leitura",
        "orq-sec-fluxo", "orq-fluxo-trabalho", "orq-fluxo", "orq-sec-acessos", "orq-acessos",
        # a Oficina do Codex (aba Codex)
        "tela-oficina", "oficina-lista-cartao", "oficina-uso", "oficina-erros", "oficina-lista",
        "oficina-tarefa", "oficina-voltar-lista", "oficina-seguir", "oficina-cabeca",
        "oficina-abas", "oficina-eventos", "oficina-diff", "oficina-testes", "oficina-pedido",
        "oficina-resposta",
        # o Coordenador (aba Coordenador; a conversa com ele incluída)
        "coord-mesa", "tela-coordenador", "coord-topo", "coord-abas", "coord-painel",
        "coord-trabalho", "coord-servicos", "coord-eventos", "coord-conversa",
        "coord-propostas", "coord-cerebro", "coord-mensagens", "coord-texto", "coord-enviar",
    ],
    "decidir": [
        "tela-decisoes", "decisoes-listas", "decisoes-abas", "decisoes-lista",
        "decisoes-rodape", "decisao-mudou", "btn-decisao-mudou", "decisao-item",
        # o que o orquestrador decidiu sozinho (com o Contestar)
        "orq-sec-decisoes", "orq-decisoes",
    ],
    "mandar": [
        "tela-comandos", "claude-bancada",
        # o Controle (decisão controle-onde) e o gerar
        "controle", "alvo-pausa", "prazo-pausa", "btn-pausar", "btn-retomar", "btn-parar",
        "gerar-cartao", "btn-gerar", "restantes",
        # o catálogo (com a zona de perigo) e o histórico dos comandos
        "comandos-grupos", "tarefas-lista", "tarefa-caixa", "tarefa-titulo", "tarefa-log",
        "btn-fechar-log",
        # a mensagem para o orquestrador e "O que você mandou"
        "orq-sec-mensagem", "orq-mensagem", "orq-enviar", "orq-sec-comandos", "orq-comandos",
        # o "Controlar o PC" do coordenador
        "coord-acoes", "coord-confirmar",
        # a conversa com as IAs (aba IAs): falar, pedir imagem, galeria
        "tela-conversa", "conversa-ias", "conversa-modos", "conversa-casa",
        "conversa-carteiro", "conversa-historico", "conversa-galeria", "conversa-criar",
        "criar-aviso", "criar-prompt", "criar-proporcao", "criar-modelo-rotulo",
        "criar-modelo", "criar-contagem", "criar-enviar", "conversa-caixa-texto",
        "conversa-texto", "conversa-anexo", "conversa-anexo-nome", "conversa-enviar",
    ],
    "ver": [
        "tela-videos", "player-cartao", "player-titulo", "player", "videos",
        "tela-biblioteca", "biblioteca-listas", "biblioteca-busca", "biblioteca-abas",
        "biblioteca-lista", "biblioteca-leitor", "biblioteca-voltar-lista",
        "biblioteca-titulo", "biblioteca-texto",
        "tela-relatorios", "abas-relatorio", "relatorio",
        "tela-diario", "diario-filtro", "diario-filtro-nome", "btn-todas", "diario",
    ],
    "fora": [
        "btn-voltar", "titulo", "conexao", "aviso", "aviso-texto", "btn-tentar", "casca-nova",
        "btn-recarregar", "modulo-faltando", "modulo-faltando-texto", "btn-recarregar-modulos",
        "tela-parear", "codigo", "btn-parear", "parear-msg",
        "tela-vila", "vila-canvas", "vila-placar", "vila-escolhido", "nav", "vila-menos",
        "vila-mais",
        "dialogo-campos", "campos-corpo", "btn-campos-ok", "dialogo", "dialogo-texto",
        "dialogo-destinos", "dialogo-prazo", "dialogo-sim", "toast",
        "imagem-tela", "imagem-tela-img", "imagem-tela-legenda", "imagem-baixar",
        "imagem-compartilhar", "imagem-fechar",
    ],
}
# o que saiu, e o que faz o papel dele agora
SAIRAM = {
    "tela-quadro": "tela-agora",              # o Quadro de avisos virou Agora
    "tela-orquestrador": "tela-agora",        # a Mesa: Agora + Mandar + Decidir
    "obj-orquestrador": "obj-agora",          # o selo da Mesa vai no objeto Agora
    "claude-mesa": "claude-bancada",          # o interruptor do Claude, uma vez só
    "oficina-voltar-mesa": "tela-agora",      # "‹ Mesa" = a aba Agora
    "orq-abrir-biblioteca": "tela-biblioteca",  # o atalho da Mesa = a aba Biblioteca
    "orq-abrir-coordenador": "coord-mesa",    # o atalho da Mesa = a linha + a aba
}
# as telas de antes e o objeto onde cada uma abre hoje
TELAS_DE_ANTES = {"quadro": "agora", "orquestrador": "agora", "oficina": "agora",
                  "coordenador": "agora", "decisoes": "decidir", "comandos": "mandar",
                  "conversa": "mandar", "videos": "ver", "biblioteca": "ver",
                  "relatorios": "ver", "diario": "ver"}
ROTAS_DE_ANTES = [
    "/api/acao", "/api/acao/confirmar", "/api/acoes", "/api/biblioteca",
    "/api/biblioteca/bilhete/", "/api/biblioteca/doc/", "/api/catalogo", "/api/claude",
    "/api/coordenador", "/api/coordenador/comando", "/api/coordenador/conversa",
    "/api/coordenador/falar", "/api/coordenador/proposta/", "/api/correio", "/api/correio/",
    "/api/assembleia", "/api/assembleias", "/api/decisao/", "/api/decisao/responder", "/api/decisoes", "/api/delegados",
    "/api/diario", "/api/erros", "/api/estado", "/api/imagens", "/api/orquestrador",
    "/api/orquestrador/comando", "/api/orquestrador/contestar", "/api/orquestrador/fluxo",
    "/api/relatorio/", "/api/tarefa/", "/api/tarefas", "/api/video/", "/api/videos",
    "/api/vila", "/api/vilanova",
]
HANDLERS_DE_ANTES = [
    "biblioteca-abas:click", "biblioteca-busca:input", "biblioteca-voltar-lista:click",
    "btn-campos-ok:click", "btn-decisao-mudou:click", "btn-fechar-log:click",
    "btn-gerar:click", "btn-parar:click", "btn-parear:click", "btn-pausar:click",
    "btn-recarregar-modulos:click", "btn-recarregar:click", "btn-retomar:click",
    "btn-tentar:click", "btn-todas:click", "btn-voltar:click", "conversa-anexo:change",
    "conversa-enviar:click", "conversa-texto:keydown", "coord-enviar:click",
    "criar-enviar:click", "criar-prompt:input", "criar-proporcao:change",
    "imagem-baixar:click", "imagem-compartilhar:click", "imagem-fechar:click",
    "imagem-tela:click", "oficina-seguir:click", "oficina-voltar-lista:click",
    "orq-abrir-oficina:click", "orq-adicionar-fila:click", "orq-enviar:click",
    "orq-mais:click", "orq-menos:click", "orq-modelo-codex-pedir:click",
    "orq-pausar-fila:click", "orq-retomar-fila:click", "player:error", "vila-mais:click",
    "vila-menos:click",
]


# ------------------------------------------------------------ leitores
class _Secoes(HTMLParser):
    """id -> a <section id="tela-..."> onde ele mora (ou None)."""

    def __init__(self):
        super().__init__()
        self.pilha, self.onde = [], {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        secao = a.get("id") if tag == "section" else None
        if a.get("id"):
            self.onde[a["id"]] = secao or next(
                (s for _t, s in reversed(self.pilha) if s), None)
        if tag not in ("input", "img", "meta", "link", "br", "canvas"):
            self.pilha.append((tag, secao))

    def handle_endtag(self, tag):
        while self.pilha:
            if self.pilha.pop()[0] == tag:
                break


def _onde():
    p = _Secoes()
    p.feed(HTML)
    return p.onde


def _objetos():
    """O OBJETOS do app.js: {objeto: [tela, ...]} (a primeira é a de abrir)."""
    bloco = re.search(r"const OBJETOS = \{(.*?)\n\};", JS["app.js"], re.S)
    assert bloco, "app.js perdeu o mapa OBJETOS"
    saida = {}
    for nome, corpo in re.findall(r"(\w+): \[((?:\s*\[[^\]]*\],?)+)\]", bloco.group(1)):
        saida[nome] = re.findall(r'\["([\w-]+)",', corpo)
    return saida


def _secao(tela):
    inicio = HTML.index(f'id="tela-{tela}"')
    return HTML[inicio:HTML.index("</section>", inicio)]


# ----------------------------------------------------------------- testes
def test_a_lista_cravada_cobre_os_207_ids_de_antes_sem_repetir():
    todos = [i for lista in ONDE_FICOU.values() for i in lista] + list(SAIRAM)
    assert len(todos) == len(set(todos)) == 207


def test_os_quatro_objetos_e_nada_mais_na_prateleira():
    objetos = _objetos()
    assert list(objetos) == ["agora", "decidir", "mandar", "ver"]
    assert objetos["agora"] == ["agora", "oficina", "coordenador"]
    assert objetos["decidir"] == ["decisoes", "assembleias"]
    assert objetos["mandar"] == ["comandos", "conversa"]
    assert objetos["ver"] == ["videos", "biblioteca", "relatorios", "diario"]
    botoes = re.findall(r'<button class="objeto" id="obj-(\w+)" data-objeto="(\w+)" '
                        r'data-tela="([\w-]+)"><span>[^<]*</span>([^<]+)</button>', HTML)
    assert [(o, rotulo) for o, _d, _t, rotulo in botoes] == [
        ("agora", "Agora"), ("decidir", "Decidir"), ("mandar", "Mandar"), ("ver", "Ver")]
    for obj_id, objeto, aba, _rotulo in botoes:
        assert obj_id == objeto and aba == objetos[objeto][0]
    assert HTML.count('class="objeto"') == 4


def test_nenhuma_tela_so_abre_por_dentro_de_outra():
    # toda tela (fora a Vila e o pareamento) é aba de um dos quatro objetos;
    # antes, Coordenador, Biblioteca, Oficina e Conversa só abriam por dentro
    abas = {t for lista in _objetos().values() for t in lista}
    telas = set(re.findall(r'<section id="tela-([\w-]+)"', HTML)) - {"vila", "parear"}
    assert telas == abas
    for tela, objeto in TELAS_DE_ANTES.items():
        novo = "agora" if tela in ("quadro", "orquestrador") else tela
        assert novo in _objetos()[objeto], (tela, objeto)


def test_cada_funcao_antiga_existe_e_mora_no_objeto_certo():
    onde = _onde()
    objetos = _objetos()
    for objeto, ids in ONDE_FICOU.items():
        for i in ids:
            assert i in onde, f"sumiu do HTML: {i}"
            secao = onde[i]
            if objeto == "fora":
                assert secao in (None, "tela-vila", "tela-parear"), (i, secao)
            else:
                assert secao and secao[len("tela-"):] in objetos[objeto], (i, objeto, secao)
    for velho, novo in SAIRAM.items():
        assert velho not in onde, f"{velho} devia ter saído"
        assert novo in onde, f"{velho} saiu e o substituto {novo} não existe"


def test_toda_rota_de_antes_ainda_e_chamada():
    for rota in ROTAS_DE_ANTES:
        assert re.search(r'api\(\s*[`"]' + re.escape(rota), TODO_JS), rota


def test_todo_handler_de_antes_ainda_esta_ligado():
    for chave in HANDLERS_DE_ANTES:
        id_, evento = chave.split(":")
        assert re.search(r'\$\("' + re.escape(id_) + r'"\)\.(addEventListener\("'
                         + evento + r'"|on' + evento + r"\s*=)", TODO_JS), chave
    # os três atalhos que só existiam para abrir telas escondidas viraram abas
    for velho in ("oficina-voltar-mesa", "orq-abrir-biblioteca", "orq-abrir-coordenador"):
        assert velho not in TODO_JS
    assert "montarAbasDosObjetos();" in JS["app.js"]
    assert '$("coord-mesa").addEventListener("click"' in JS["app.js"]


def test_agora_junta_o_que_esta_rodando_e_recolhe_capacidade_modelos_limites():
    agora = _secao("agora")
    ordem = [agora.index(f'id="{i}"') for i in (
        "orq-sec-agora", "orq-sec-codex", "orq-sec-fila", "agora-postagem", "agora-fabricas",
        "orq-sec-capacidade", "orq-sec-modelos", "orq-sec-limites")]
    assert ordem == sorted(ordem)
    for sec in ("capacidade", "modelos", "limites", "fluxo", "acessos"):
        assert re.search(rf'<details class="cartao recolhido" id="orq-sec-{sec}"', agora), sec
    # fábricas, erros e paralelismo num lugar só
    fab = agora[agora.index('id="agora-fabricas"'):agora.index('id="orq-sec-capacidade"')]
    for i in ("fabricas", "erros", "vila-travas"):
        assert f'id="{i}"' in fab, i
    # nem os Avisos nem o Diário repetem os erros recentes
    assert HTML.count('id="erros"') == 1


def test_o_interruptor_do_claude_aparece_uma_vez_so_em_mandar():
    assert HTML.count('class="claude-chave"') == 1
    assert 'class="claude-chave"' in _secao("comandos")
    assert 'const CLAUDE_INTERRUPTORES = ["claude-bancada"];' in JS["app.js"]
    assert "claude-mesa" not in TODO_JS
    # Agora mantém só a faixa que diz que está proibido (não é interruptor)
    assert 'id="claude-faixa"' in _secao("agora")


def test_tarefas_virou_historico_abaixo_dos_botoes_e_nunca_vazio_em_cima():
    mandar = _secao("comandos")
    assert ">Tarefas<" not in HTML and "nenhuma tarefa ainda" not in JS["comandos.js"]
    # "Últimos que você mandou" vem DEPOIS de todos os botões, e nasce escondido
    ultimos = mandar.index('id="comandos-ultimos"')
    for antes in ("controle", "gerar-cartao", "comandos-grupos", "orq-sec-mensagem",
                  "coord-controlar"):
        assert mandar.index(f'id="{antes}"') < ultimos, antes
    assert '<div class="cartao oculto" id="comandos-ultimos">' in mandar
    assert "Últimos que você mandou" in mandar
    fonte = JS["comandos.js"]
    # vazio some; cada comando ganha o seu histórico logo abaixo do botão
    assert '$("comandos-ultimos").classList.toggle("oculto", !Comandos.tarefas.length)' in fonte
    assert '"data-historico": acao.nome' in fonte
    assert "t.acao === caixa.dataset.historico" in fonte
    # "O que você mandou" (ao orquestrador) fica logo abaixo do botão Enviar
    msg = mandar[mandar.index('id="orq-sec-mensagem"'):mandar.index('id="coord-controlar"')]
    assert msg.index('id="orq-enviar"') < msg.index('id="orq-comandos"')


def test_os_selos_seguem_os_objetos():
    # o contador de escolhas do Grimório vai no Decidir
    assert 'button.objeto[data-tela="decisoes"]' in JS["decisoes.js"]
    assert re.search(r'id="obj-decidir" data-objeto="decidir" data-tela="decisoes"', HTML)
    assert "selo-contador" in CSS
    # o selo da antiga Mesa (teto, fora do ar, pendente) vai no Agora
    assert '$("obj-agora")' in JS["orquestrador.js"]


def test_trocar_de_aba_nao_empilha_historico_nem_repete_a_animacao():
    fonte = JS["app.js"]
    assert "history.replaceState({tela: nova}" in fonte
    assert 'secao.classList.toggle("sem-abrir"' in fonte
    assert ".livro.sem-abrir:not(.oculto) { animation: none !important; }" in CSS
    # o objeto abre a última aba usada
    assert "ABA_DO_OBJETO[botao.dataset.objeto] || botao.dataset.tela" in fonte
