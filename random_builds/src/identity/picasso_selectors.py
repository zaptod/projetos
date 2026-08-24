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

# Nao ha ponto de anexo aqui: PicassoIA gera a imagem, quem recebe referencia
# e o Digen. Vazias de proposito, e o diagnostico conta lista vazia como "nao
# levantado" em vez de fingir cobertura.
BOTAO_ANEXO: list[tuple[str, str]] = []
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


# Miniaturas do que foi ENVIADO (nao do que foi gerado), contadas dentro do
# painel do composer. Ancora no campo de prompt e sobe: contar `img` da pagina
# inteira pegaria a galeria de exemplos.
JS_MINIATURAS = """() => {
  const campo = document.querySelector('textarea#prompt, textarea[name=prompt]');
  if (!campo) return [];
  let caixa = campo;
  for (let i = 0; i < 8 && caixa.parentElement; i++) {
    caixa = caixa.parentElement;
    if (caixa.querySelectorAll('img').length) break;
  }
  return Array.from(caixa.querySelectorAll('img'))
    .filter(i => { const r = i.getBoundingClientRect();
                   return r.width > 20 && r.height > 20; })
    .map(i => i.currentSrc || i.src || '');
}"""


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
    ("quantidade", "BOTAO_QUANTIDADE", "aviso"),
)
