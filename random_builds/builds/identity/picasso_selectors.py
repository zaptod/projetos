"""Seletores do PicassoIA (picassoia.com).

Levantados do DOM REAL em 24/08/2026, logado, com `identity probe --provedor
picasso --url ...`. Nada aqui e chute.

O motor (`encontrar`, `resolver`, `primeiro_visivel`, `SeletorNaoEncontrado`)
vem de `selectors.py`: e o mesmo para todo provedor, so os dados mudam. Os
NOMES dos atributos espelham os de la de proposito — o diagnostico resolve por
getattr sobre string, e um nome diferente ficaria sem cobertura em silencio.
"""
from __future__ import annotations

import re

from .selectors import (SeletorNaoEncontrado, encontrar,  # noqa: F401
                        primeiro_visivel, resolver)

PROVEDOR = "picasso"

BASE_URL = "https://picassoia.com"
# A pagina de "colecao" do modelo E o criador quando se esta logado. Deslogado
# ela parece institucional, e foi isso que enganou a leitura inicial de fora.
URL_CRIACAO = f"{BASE_URL}/pt/collection/text-to-image/picassoia-image"
URL_LOGIN = f"{BASE_URL}/pt/account"

# Editor Pro: mesma casca do criador (textarea#prompt, #submit-button, selects)
# mais uma zona de IMAGENS que aceita VARIAS — e a diferenca que importa. E ele
# que junta personagem e arma numa imagem so, porque o composer do Digen aceita
# um arquivo apenas.
URL_EDITOR = f"{BASE_URL}/pt/collection/text-to-image/picassoia-image-editor-pro"

# Presenca de QUALQUER um destes = sessao viva (o composer esta na tela).
SESSAO_VIVA = [
    ("css", "textarea#prompt"),
    ("css", 'textarea[name="prompt"]'),
    ("css", "#submit-button"),
]

TELA_LOGIN = [
    ("css", "input[type='email']"),
    ("css", "input[name='email']"),
    ("placeholder", "Email"),
    ("placeholder", "E-mail"),
]

CAMPO_EMAIL = [
    ("css", "input[type='email']"),
    ("css", "input[name='email']"),
    ("placeholder", "Email"),
]

CAMPO_SENHA = [
    ("css", "input[type='password']"),
    ("css", "input[name='password']"),
    ("placeholder", "Senha"),
]

BOTAO_LOGIN = [
    ("role", "button|Entrar"),
    ("role", "button|Sign in"),
    ("role", "button|Log in"),
    ("css", "button[type='submit']"),
]

DESAFIO = [
    ("css", "iframe[src*='recaptcha']"),
    ("css", "iframe[src*='hcaptcha']"),
    ("css", "iframe[title*='challenge']"),
    ("css", "iframe[src*='turnstile']"),
]

# `textarea` de verdade, com id e name — nada de contenteditable aqui.
CAMPO_PROMPT = [
    ("css", "textarea#prompt"),
    ("css", 'textarea[name="prompt"]'),
    ("placeholder", "Descreva o que"),
]

# Nasce com aria-disabled=true e so habilita quando ha texto: e essa virada
# que confirma que o prompt entrou, sem precisar ler o valor do campo.
BOTAO_GERAR = [
    ("css", "#submit-button"),
    ("css", 'button[type="submit"][form="feature-form"]'),
    ("css", 'button[type="submit"]'),
]

# Proporcao e quantidade sao <select> NATIVOS. Nao sao popover: `<option>`
# nunca e "visivel" para o Playwright, e clicar nela estoura em timeout. Quem
# mexe e `select_option`. Os dois sao achados pelo CONTEUDO das opcoes, e nao
# por id/name (eles nao tem nenhum dos dois).
OPCOES_ASPECTO = ("1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3")
ASPECTOS_VERTICAIS = ("9:16", "2:3", "3:4")
OPCOES_QUANTIDADE = ("1", "2")

# O botao estilizado ESPELHA o select; serve para conferir o que ficou.
BOTAO_ASPECTO = [
    ("css", 'button[aria-label^="Propor"]'),
    ("css", 'button[aria-label*="spect"]'),
]
BOTAO_QUANTIDADE = [
    ("css", 'button[aria-label*="mero de"]'),
    ("css", 'button[aria-label*="utput"]'),
]

# A imagem pronta e servida direto de um bucket publico. E por isso que nao
# existe (nem faz falta) botao de download: com a URL na mao, `ctx.request.get`
# baixa reusando os cookies da sessao.
PADRAO_RESULTADO = re.compile(
    r"https://pub-[0-9a-f]+\.r2\.dev/text-to-image/[^/]+/[^/]+/[^\"'\s]+", re.I)

JS_IMAGENS = """() => Array.from(document.images).map(i => ({
  src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight}))"""

# Texto VISIVEL da pagina. Serve para achar o aviso de conteudo recusado sem
# depender de seletor (o site mostra isso em toast, banner ou modal conforme
# o caso). `innerText` ja ignora o que esta escondido, e o valor do textarea
# nao entra — importante, senao o proprio prompt daria falso positivo.
JS_TEXTO_VISIVEL = """() => document.body ? document.body.innerText : ''"""


def texto_visivel(page) -> str:
    try:
        return page.evaluate(JS_TEXTO_VISIVEL) or ""
    except Exception:
        return ""


# O bloqueio de conteudo do PicassoIA e um ICONE, nao uma frase: um escudo
# com exclamacao (lucide `shield-alert`, pintado de `text-destructive`).
# Visto na tela do Adrian em 31/08/2026 — por isso a deteccao por texto
# passou batido e a cena voltou a queimar o timeout inteiro.
#
# Duas forcas, e a diferenca importa: o ESCUDO e bloqueio de conteudo (a
# resposta e reescrever o prompt); `text-destructive` sozinho e so "deu
# ruim" — pode ser falta de credito, rede, qualquer coisa — e ai reescrever
# nao adianta. Devolver as duas coisas separadas deixa quem chama decidir.
JS_BLOQUEIO = """() => {
  const visivel = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const textoPerto = (el) => {
    let no = el;
    for (let i = 0; i < 5 && no; i++) {
      no = no.parentElement;
      const t = no && no.innerText ? no.innerText.trim() : '';
      if (t) return t.slice(0, 300);
    }
    return '';
  };
  const classe = (el) => (el.getAttribute('class') || '') + ' ' +
                         (el.className && el.className.baseVal || '');
  for (const el of document.querySelectorAll('svg, [class*="shield"]')) {
    if (!visivel(el)) continue;
    if (/shield[-_]?alert|shield[-_]?ban|shield[-_]?x/i.test(classe(el))) {
      return {escudo: true, texto: textoPerto(el)};
    }
  }
  for (const el of document.querySelectorAll('[class*="text-destructive"]')) {
    if (visivel(el)) return {escudo: false, texto: textoPerto(el)};
  }
  return null;
}"""


def bloqueio_na_tela(page) -> dict | None:
    """{escudo: bool, texto: str} quando ha sinal de bloqueio/erro na tela."""
    try:
        return page.evaluate(JS_BLOQUEIO)
    except Exception:
        return None

# A zona de upload do Editor Pro. Sondada de novo em 26/08/2026: o site
# TROCOU o formulario — o input perdeu o `multiple` ("Carregar imagem" no
# singular) e a segunda imagem passou a SUBSTITUIR a primeira. O botao abre o
# seletor de arquivo DIRETO (nao ha menu no meio — OPCAO_ENVIAR_IMAGEM segue
# vazia de proposito, e `_abrir_menu_de_anexo` trata lista vazia como "o
# proprio botao e o gatilho").
BOTAO_ANEXO = [
    ("css", "button[aria-label='Carregar imagem']"),
    ("text", "Arraste e solte"),
]

# "Aprimorador de Prompt": reescreve o texto DENTRO do proprio textarea. O id
# e estavel; o fallback pega pelo texto caso o id mude de nome.
BOTAO_APRIMORAR = [
    ("css", "#promptEnhancerRealtime"),
    ("text", "Aprimorador de Prompt"),
]
OPCAO_ENVIAR_IMAGEM: list[tuple[str, str]] = []
MINIATURA_REFERENCIA: list[tuple[str, str]] = []
REMOVER_REFERENCIA: list[tuple[str, str]] = []
ENTRADA_ARQUIVO = 'input[type="file"]'


def entrada_de_arquivo(page, indice: int = 0):
    try:
        loc = page.locator(ENTRADA_ARQUIVO)
        return loc.nth(indice) if loc.count() > indice else None
    except Exception:
        return None


def select_com_opcao(page, valor: str):
    """O <select> que oferece `valor`, ou None.

    Os selects nao tem id nem name, entao o que os identifica e o que eles
    oferecem — e isso e mais estavel que posicao: um controle novo no meio da
    barra nao quebra nada.
    """
    try:
        total = page.locator("select").count()
    except Exception:
        return None
    for i in range(total):
        alvo = page.locator("select").nth(i)
        try:
            opcoes = alvo.evaluate("e => Array.from(e.options).map(o => o.value)")
        except Exception:
            continue
        if valor in opcoes:
            return alvo
    return None


# O que prova que uma imagem ENTROU no editor: o botao "Remover imagem N" que
# o proprio site cria para ela. Medido no DOM em 27/08/2026 — anexar duas em
# sequencia no mesmo input deixa 'Remover imagem 1' e 'Remover imagem 2'.
#
# Contar <img> nao servia nas duas pontas: `blob:`/`data:` NAO aparece (o
# site monta a miniatura de outro jeito) e `img` solto pegava o historico
# carregando tarde. Foi o detector errado que fez o worker concluir que a
# segunda imagem substituia a primeira e que a juncao so podia receber uma.
JS_MINIATURAS = """() => Array.from(document.querySelectorAll('button'))
  .map(b => b.getAttribute('aria-label') || '')
  .filter(l => /^remover imagem/i.test(l))"""


def miniaturas(page) -> list[str]:
    try:
        return [str(s) for s in page.evaluate(JS_MINIATURAS)]
    except Exception:
        return []


def resultados_na_tela(page) -> list[dict]:
    """Imagens que sao saida deste modelo, com tamanho."""
    try:
        imagens = page.evaluate(JS_IMAGENS)
    except Exception:
        return []
    return [i for i in imagens
            if i.get("src") and PADRAO_RESULTADO.match(i["src"])]


LISTAS_ONLINE = (
    ("sessao viva", "SESSAO_VIVA", "erro"),
    ("campo de prompt", "CAMPO_PROMPT", "erro"),
    ("botao de gerar", "BOTAO_GERAR", "erro"),
    ("proporcao", "BOTAO_ASPECTO", "aviso"),
    ("aprimorador de prompt", "BOTAO_APRIMORAR", "aviso"),
    ("quantidade", "BOTAO_QUANTIDADE", "aviso"),
)


# ------------------------------------------------------------- historico
# A aba "Historico" (`?tab=history`, painel `#generations`) lista as geracoes
# DA CONTA — de todo mundo que a compartilha — com o PROMPT inteiro, a data
# ("25 DE AGO. DE 2026, 22:26") e a imagem. E a unica tela do site que liga
# um resultado ao texto que o pediu, e por isso e ela que prova a origem: o
# card com o NOSSO prompt e o nosso, e a imagem DELE e a que se baixa. Vale
# igual para o criador e para o Editor Pro (mesma casca). Levantado do DOM
# real em 25/08/2026.
#
# A imagem do card e LAZY: so ganha `src` quando o card entra na tela. Por
# isso `cards_do_historico` aceita `revelar`, que rola aquele card para o
# centro antes de ler.
PARAMETRO_HISTORICO = "tab=history"

PAINEL_HISTORICO = [
    ("css", "#generations[role='tabpanel']"),
    ("css", "[data-slot='tabs-content']#generations"),
    ("css", "button[aria-label='Copiar prompt']"),
]

JS_CARDS_HISTORICO = """([limite, revelar]) => {
  const painel = document.querySelector('#generations') || document;
  const botoes = Array.from(painel.querySelectorAll('button[aria-label="Copiar prompt"]'));
  const out = [];
  botoes.slice(0, limite).forEach((botao, indice) => {
    // O card e o MAIOR ancestral que ainda contem SO este botao de copiar.
    // A ancora antiga ("subir ate ter <img>") estourava para o painel
    // inteiro quando a imagem do card ainda nao tinha carregado — e ai o
    // texto/data/imagens vinham do card ERRADO (visto em 26/08/2026: todos
    // os cards devolviam o innerText do painel e as imagens do topo).
    let card = botao;
    for (let i = 0; i < 12 && card.parentElement; i++) {
      const pai = card.parentElement;
      if (pai.querySelectorAll('button[aria-label="Copiar prompt"]').length > 1) break;
      card = pai;
    }
    if (revelar === indice) card.scrollIntoView({block: 'center'});
    const bloco = botao.parentElement ? botao.parentElement.parentElement : null;
    const p = bloco ? bloco.querySelector('p') : null;
    // TODOS os paragrafos, e nao so o primeiro: no card RECUSADO (14/09/2026,
    // "CONTEUDO ILEGAL - Este conteudo e ilegal e proibido na nossa
    // plataforma") o primeiro <p> pode ser o aviso, e o prompt nunca casava.
    const paragrafos = Array.from(card.querySelectorAll('p'))
      .map(x => (x.innerText || x.textContent || '').trim()).filter(Boolean);
    const imagens = Array.from(card.querySelectorAll('img'))
      .map(i => i.currentSrc || i.getAttribute('src') || '').filter(Boolean);
    const texto = (card.innerText || '').slice(0, 3000);
    const escudo = Array.from(card.querySelectorAll('svg, [class*="shield"]')).some(el =>
      /shield[-_]?alert|shield[-_]?ban|shield[-_]?x/i.test(
        (el.getAttribute('class') || '') + ' ' + (el.className && el.className.baseVal || '')));
    const aviso = /conte[uú]do\\s+ilegal|n[aã]o\\s+pode\\s+ser\\s+processado|proibido\\s+na\\s+nossa\\s+plataforma/i.test(texto);
    out.push({
      indice: indice,
      prompt: p ? (p.innerText || p.textContent || '') : '',
      paragrafos: paragrafos,
      texto: texto,
      imagens: imagens,
      // Recusa do filtro NO CARD: a frase, ou o escudo num card sem imagem.
      recusado: aviso || (escudo && imagens.length === 0),
    });
  });
  return out;
}"""


def url_historico(url: str | None) -> str:
    """A aba de historico da MESMA pagina (criador ou Editor Pro)."""
    base = (url or URL_CRIACAO).split("?", 1)[0].split("#", 1)[0]
    return f"{base}?{PARAMETRO_HISTORICO}"


def cards_do_historico(page, limite: int = 12, revelar: int | None = None) -> list[dict]:
    """Os `limite` cards do topo (mais novo primeiro), ja filtrados.

    Cada card: {indice, prompt, texto, imagens} — `imagens` so com URLs de
    resultado deste modelo (bucket r2), nunca miniatura de exemplo.
    """
    try:
        bruto = page.evaluate(JS_CARDS_HISTORICO,
                              [int(limite), -1 if revelar is None else int(revelar)])
    except Exception:
        return []
    cards = []
    for item in bruto or []:
        imagens: list[str] = []
        for src in item.get("imagens") or []:
            if src and PADRAO_RESULTADO.match(src) and src not in imagens:
                imagens.append(src)
        cards.append({"indice": item.get("indice"),
                      "prompt": item.get("prompt") or "",
                      "paragrafos": [str(t) for t in item.get("paragrafos") or []
                                     if t],
                      "texto": item.get("texto") or "",
                      "imagens": imagens,
                      "recusado": bool(item.get("recusado"))})
    return cards
