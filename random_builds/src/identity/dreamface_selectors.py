# -*- coding: utf-8 -*-
"""Seletores do DreamFace (dreamfaceapp.com) — o segundo gerador de imagem.

Por que existe: com um gerador só, a fila de imagens de uma história de 140
cenas anda no ritmo de um site. Com dois, ela anda no dobro — e uma conta
sem crédito ou um bloqueio de conteúdo deixa de parar tudo.

CONFERIDO NA TELA LOGADA em 01/09/2026. O que a sondagem mostrou, e que não
era óbvio de fora:

  - **`/login` não existe.** Redireciona para a home. O login é um MODAL
    dentro do app, e o site manda sozinho para a versão localizada (`/pt/`).
  - **`/ai-tools/text-to-image` é página de marketing**, não a ferramenta:
    logado, ela só mostra um botão "Back Home". A ferramenta de verdade é
    `/pt/image`.
  - Há **reCAPTCHA** no login. Por isso ele é manual, sempre.
  - A ferramenta aceita **imagem de referência** (o `+` ao lado do prompt e
    um `input[type=file]`) — é o que permite as duas fábricas partirem da
    mesma âncora de estilo.
  - O aspecto nasce em **4:3**: para vídeo vertical ele PRECISA ser trocado
    para 9:16, ou a imagem entra deitada.

Quando o site mudar: `python main.py identity probe --provedor dreamface`
e ajuste as listas daqui — nunca adivinhe.
"""
from __future__ import annotations

import re

PROVEDOR = "dreamface"

BASE_URL = "https://www.dreamfaceapp.com"
# NAO existe `/login`: essa URL redireciona para a home. O login e um MODAL
# que aparece dentro do aplicativo — e o proprio site manda para a versao
# localizada (`/pt/...`) sozinho. Sondado em 01/09/2026.
URL_APP = f"{BASE_URL}/pt/avatar"
URL_LOGIN = URL_APP
# A ferramenta DE VERDADE (a de `/ai-tools/` e so marketing).
URL_CRIACAO = f"{BASE_URL}/pt/image"
URL_MARKETING = f"{BASE_URL}/ai-tools/text-to-image"
URL_CONTA = f"{BASE_URL}/pt/user"

# ------------------------------------------------------------------ sessao
# O menu mostra "Entrar/Cadastro" enquanto NAO ha sessao; e o sinal mais
# confiavel que a pagina da, porque nao depende de classe com hash.
TELA_LOGIN = [
    ("css", "button:has-text('Entrar')"),
    ("css", "input[type='password']"),
    ("text", "Entrar/Cadastro"),
    ("text", "Bem-vindo ao DreamFace"),
]
SESSAO_VIVA = [
    ("text", "Criações"),
    ("css", "[class*='avatar']"),
    ("css", "[class*='credit']"),
]

# O formulario do modal (visto no DOM: type=email/password + botao "Entrar").
# Ha reCAPTCHA na tela — por isso o login e MANUAL, sempre: automatizar
# credencial aqui seria contornar uma protecao do site, alem de fragil.
CAMPO_EMAIL = [
    ("css", "input[type='email']"),
    ("css", "input[name='email']"),
]
CAMPO_SENHA = [
    ("css", "input[type='password']"),
    ("css", "input[name='password']"),
]
BOTAO_ENTRAR = [
    ("css", "button:has-text('Entrar')"),
    ("css", "button:has-text('Sign in')"),
]
DESAFIO = [
    ("css", "iframe[src*='recaptcha']"),
    ("css", "#g-recaptcha-response"),
]

# ------------------------------------------------------------------ prompt
CAMPO_PROMPT = [
    ("css", "textarea[placeholder*='Escreva as palavras' i]"),
    ("css", "textarea[placeholder*='cole o texto' i]"),
    ("css", "textarea"),
]
BOTAO_GERAR = [
    ("css", "button:has-text('Criar')"),
    ("css", "button:has-text('Create')"),
    ("css", "button:has-text('Generate')"),
]
GERANDO = [
    ("text", "Gerando"),
    ("text", "Generating"),
    ("css", "[class*='loading']"),
]

# Os tres botoes do rodape do compositor. Sao gatilhos de POPOVER: clicar
# abre um menu, e o texto do proprio botao mostra o valor atual — da para
# saber se precisa mexer sem abrir nada (mesma logica do Digen).
BOTAO_MODELO = [
    ("css", "button:has-text('Dream Image')"),
    ("css", "button:has-text('Seedream')"),
    ("css", "button:has-text('GPT Image')"),
]
MODELOS = ("Dream Image 2.0", "GPT Image 2", "Seedream 5.0 Pro",
           "Seedream 4.5", "Seedream 4.0")
BOTAO_ASPECTO = [
    ("css", "button:has-text('9:16')"),
    ("css", "button:has-text('4:3')"),
    ("css", "button:has-text('16:9')"),
    ("css", "button:has-text('1:1')"),
]
ASPECTOS_VERTICAIS = ("9:16", "3:4", "2:3")
BOTAO_RESOLUCAO = [
    ("css", "button:has-text('resolução')"),
    ("css", "button:has-text('resolution')"),
]

# ---------------------------------------------------------- referencia
# O ponto do exercicio: as duas fabricas partindo da MESMA imagem para o
# estilo nao trocar de uma cena para a outra. Na tela e o quadrado com "+"
# a esquerda do prompt; no DOM, um `input[type=file]` (que costuma estar
# escondido — por isso `set_input_files` direto nele, sem clicar no "+").
ENTRADA_ARQUIVO = 'input[type="file"]'
BOTAO_ANEXO = [
    ("css", "input[type='file']"),
    ("css", "[class*='upload']"),
]
# A aba "Minha img" guarda as imagens ja enviadas pela conta.
ABA_MINHAS_IMAGENS = [
    ("text", "Minha img"),
    ("text", "My img"),
]

# ---------------------------------------------------------------- resultado
# O padrão da URL da imagem pronta. Sem ele confirmado, `resultados_na_tela`
# cai na varredura genérica de <img> — que é o que o PicassoIA também faz.
PADRAO_RESULTADO = re.compile(
    r"https://[^\"'\s]+\.(?:png|jpe?g|webp)(?:\?[^\"'\s]*)?", re.I)

JS_IMAGENS = """() => Array.from(document.images).map(i => ({
  src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight}))"""


def resultados_na_tela(page) -> list:
    """Imagens visíveis com tamanho conhecido (mesma porta do PicassoIA)."""
    try:
        return [i for i in (page.evaluate(JS_IMAGENS) or []) if i.get("src")]
    except Exception:
        return []


# O contador do topo direito. Mostrava 0 na primeira sondagem logada —
# antes de gastar uma rodada inteira, o worker pergunta.
CREDITOS = [
    ("css", "[class*='credit']"),
    ("css", "[class*='coin']"),
    ("css", "button:has-text('Pro')"),
]

# Erro explícito: falhar rápido em vez de esperar o timeout inteiro.
ERRO_GERACAO = [
    ("text", "insufficient"),
    ("text", "not enough credits"),
    ("text", "out of credits"),
    ("text", "Generation failed"),
    ("text", "try again"),
]

LISTAS_ONLINE = (
    ("CAMPO_PROMPT", CAMPO_PROMPT),
    ("BOTAO_GERAR", BOTAO_GERAR),
    ("SESSAO_VIVA", SESSAO_VIVA),
    ("BOTAO_ANEXO", BOTAO_ANEXO),
)
