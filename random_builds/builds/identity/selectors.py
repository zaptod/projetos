"""TODOS os seletores do Digen num lugar so.

Levantados do DOM real em 22/08/2026 (`python main.py identity probe` regrava).
O Digen e uma SPA em Vue com classes utilitarias geradas por build, entao cada
campo aqui e uma LISTA DE CANDIDATOS tentada em ordem, com preferencia por
ancoras estaveis: `aria-placeholder`, `role`, texto visivel e a classe semantica
`submit-btn` (que e nome de componente, nao utilitaria — nao muda a cada build).

Quando um deploy do Digen quebrar algo, o conserto e:
    python main.py identity probe
e ajustar a lista correspondente aqui. Nenhum outro arquivo muda.

Formato do candidato: (estrategia, valor) — ver `resolver()`.
"""
from __future__ import annotations

import re
import time

# Marca do provedor. O `session.ensure_logged_in` usa para o prefixo do log e
# para achar a credencial certa quando recebe so o modulo de seletores.
PROVEDOR = "digen"

BASE_URL = "https://digen.ai"
# O composer vive na PROPRIA pagina de Spaces: nao existe rota separada de
# criacao. `/create` e outra ferramenta.
URL_SPACES = f"{BASE_URL}/en/space"
URL_CRIACAO = URL_SPACES
URL_LOGIN = f"{BASE_URL}/login"

# Presenca de QUALQUER um destes = a sessao esta viva (estamos logados).
SESSAO_VIVA = [
    ("css", '[aria-placeholder^="Describe your video"]'),
    ("css", 'div[contenteditable="true"][role="textbox"]'),
    ("role", "button|New Space"),
]

# Presenca de QUALQUER um destes = caimos na tela de login.
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
    ("placeholder", "E-mail"),
]

CAMPO_SENHA = [
    ("css", "input[type='password']"),
    ("css", "input[name='password']"),
    ("placeholder", "Password"),
    ("placeholder", "Senha"),
]

BOTAO_LOGIN = [
    ("role", "button|Sign in"),
    ("role", "button|Log in"),
    ("role", "button|Login"),
    ("role", "button|Entrar"),
    ("css", "button[type='submit']"),
]

# Desafios que NAO tentamos resolver — so detectamos para pedir ajuda humana.
DESAFIO = [
    ("css", "iframe[src*='recaptcha']"),
    ("css", "iframe[src*='hcaptcha']"),
    ("css", "iframe[title*='challenge']"),
    ("css", "#cf-challenge-running"),
    ("text", "verification code"),
]

# Space novo = pasta vazia. E o que torna a espera possivel: se o espaco tem
# zero videos, o primeiro que aparecer e o NOSSO, sem heuristica nenhuma.
# Clicar aqui nao navega: ele reseta o composer para um espaco limpo.
# 26/08/2026: o nome ACESSIVEL do botao parou de casar com o role-locator
# (o <button> com texto "New Space" segue no DOM — sondado na propria pagina
# de space); os fallbacks por texto/css cobrem o proximo rebatismo do aria.
BOTAO_NOVO_ESPACO = [
    ("role", "button|New Space"),
    ("css", 'button:has-text("New Space")'),
    ("text", "New Space"),
]

# Nao e <textarea>: e um contenteditable com role=textbox. `get_by_placeholder`
# nao casa (ele olha o atributo `placeholder`, que aqui nao existe).
CAMPO_PROMPT = [
    ("css", '[aria-placeholder^="Describe your video"]'),
    ("css", '[data-placeholder^="Describe your video"]'),
    ("css", 'div[contenteditable="true"][role="textbox"]'),
]

# `submit-btn` e classe de componente, nao utilitaria do Tailwind: e a ancora
# mais estavel do composer. Fica `disabled` enquanto o prompt esta vazio — e
# por isso que esperar ele habilitar confirma que o texto entrou de verdade.
BOTAO_GERAR = [
    ("css", "button.submit-btn"),
    ("css", ".submit-btn"),
]

# Geracao em andamento. Textos reais observados na rodada de 22/08/2026 — a
# fila vem ANTES do render, entao os dois estados precisam contar como "ainda
# nao terminou":
#   "Waiting in generation queue..."
#   "You are in the priority generation queue"
#   "Generating video at 10x speed on the Ultra channel"
#   "Estimated completion: 17 seconds"
GERANDO = [
    ("text", "generation queue"),
    ("text", "Generating video"),
    ("text", "Estimated completion"),
    ("text", "Waiting in"),
]

# O botao de download do card nao tem texto, nem aria-label, nem title: o
# rotulo vive num tooltip (`data-slot="tooltip-trigger"`). A unica ancora
# estavel e o `d` do path do icone (bandeja com seta para baixo, Phosphor).
ICONE_DOWNLOAD = "M228,144v64a12,12,0,0,1-12,12H40a12,12,0,0,1-12-12V144"

# NAO use ("role", "button|Download") com exact=False aqui: isso casa com o
# botao "Download Digen App" do topo da pagina, que existe SEMPRE — inclusive
# durante a geracao. Na rodada de 22/08 isso deu "pronto" aos 24 s, com o video
# ainda na fila, e o download travou 120 s esperando um evento que nunca veio.
BOTAO_DOWNLOAD = [
    ("css", f'button:has(svg path[d^="{ICONE_DOWNLOAD}"])'),
    ("css", "a[download]"),
    ("css", "[aria-label='Download']"),
]

# Video pronto. ATENCAO: nao use `video[src]` como sinal — os <video> sao lazy
# e nascem SEM atributo `src` (e com `currentSrc` vazio); so ganham fonte
# quando tocam. O sinal confiavel e o card ganhar o botao de download.
VIDEO_PRONTO = list(BOTAO_DOWNLOAD)

# Snapshot dos cards de video PRONTOS do espaco.
#
# Com os tres clipes no MESMO espaco, "o primeiro botao de download da tela"
# para de significar "o nosso video". A identificacao passa a ser por
# DIFERENCA: fotografa-se o que ja existia antes de enviar, e o card que
# aparecer fora da foto e o nosso.
#
# A impressao digital sai da miniatura (`img[src]`, `video[poster]`), que o
# card tem ANTES de o video tocar. O `src` do <video> nao serve de ancora: os
# players sao lazy e nascem sem ele.
JS_CARDS_PRONTOS = """(icone) => {
  const visivel = e => { const r = e.getBoundingClientRect();
                         return r.width > 0 && r.height > 0; };
  const cards = [];
  document.querySelectorAll('button').forEach(botao => {
    const path = botao.querySelector('svg path');
    if (!path) return;
    if (!(path.getAttribute('d') || '').startsWith(icone)) return;
    if (!visivel(botao)) return;
    let card = botao;
    for (let i = 0; i < 8 && card.parentElement; i++) {
      card = card.parentElement;
      if (card.querySelector('img, video')) break;
    }
    const partes = [];
    card.querySelectorAll('img[src], video[poster]').forEach(midia => {
      const fonte = midia.getAttribute('src') || midia.getAttribute('poster');
      if (fonte) partes.push(fonte);
    });
    cards.push(partes.join('|'));
  });
  return cards;
}"""


def cards_prontos(page) -> list[str]:
    """Impressao digital de cada card de video pronto, em ordem de DOM."""
    try:
        return [str(fp) for fp in page.evaluate(JS_CARDS_PRONTOS, ICONE_DOWNLOAD)]
    except Exception:
        return []


JS_SRC_DO_CARD = """([icone, alvo]) => {
  const visivel = e => { const r = e.getBoundingClientRect();
                         return r.width > 0 && r.height > 0; };
  let n = 0;
  for (const botao of document.querySelectorAll('button')) {
    const path = botao.querySelector('svg path');
    if (!path) continue;
    if (!(path.getAttribute('d') || '').startsWith(icone)) continue;
    if (!visivel(botao)) continue;
    if (n++ !== alvo) continue;
    let card = botao;
    for (let i = 0; i < 8 && card.parentElement; i++) {
      card = card.parentElement;
      if (card.querySelector('video, a[download]')) break;
    }
    const v = card.querySelector('video');
    if (v && (v.currentSrc || v.src)) return v.currentSrc || v.src;
    const midia = card.querySelector('video[src], video source[src], a[download]');
    return midia ? (midia.getAttribute('src') || midia.getAttribute('href')) : null;
  }
  return null;
}"""


# Fazer o <video> revelar a fonte. Ele nasce sem `src` (lazy) e so ganha
# `currentSrc` quando TOCA — entao a leitura pede para tocar antes de olhar.
# Sem isto, o plano B do download nao tem o que baixar e o video gerado fica
# preso no site.
JS_ACORDAR_VIDEO = """([icone, alvo]) => {
  const vis = e => { const r = e.getBoundingClientRect();
                     return r.width > 0 && r.height > 0; };
  let n = 0;
  for (const botao of document.querySelectorAll('button')) {
    const path = botao.querySelector('svg path');
    if (!path) continue;
    if (!(path.getAttribute('d') || '').startsWith(icone)) continue;
    if (!vis(botao)) continue;
    if (n++ !== alvo) continue;
    let card = botao;
    for (let i = 0; i < 8 && card.parentElement; i++) {
      card = card.parentElement;
      if (card.querySelector('video')) break;
    }
    const v = card.querySelector('video');
    if (!v) return false;
    try { v.muted = true; v.load(); const p = v.play(); if (p) p.catch(() => {}); }
    catch (e) {}
    return true;
  }
  return false;
}"""


def acordar_video(page, indice: int = 0) -> bool:
    try:
        return bool(page.evaluate(JS_ACORDAR_VIDEO, [ICONE_DOWNLOAD, indice]))
    except Exception:
        return False


def src_do_card(page, indice: int = 0) -> str | None:
    """URL do video do card `indice`, se ele ja tiver uma.

    Vale so como PLANO B do botao de download: os players sao lazy e o `src`
    costuma aparecer depois que o video toca.
    """
    try:
        return page.evaluate(JS_SRC_DO_CARD, [ICONE_DOWNLOAD, indice])
    except Exception:
        return None


JS_CARD_NA_TELA = """([icone, alvo]) => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width>0 && r.height>0; };
  let n = 0;
  for (const botao of document.querySelectorAll('button')) {
    const path = botao.querySelector('svg path');
    if (!path) continue;
    if (!(path.getAttribute('d') || '').startsWith(icone)) continue;
    if (!vis(botao)) continue;
    if (n++ !== alvo) continue;
    let card = botao;
    for (let i = 0; i < 8 && card.parentElement; i++) {
      card = card.parentElement;
      if (card.querySelector('video')) break;
    }
    card.scrollIntoView({block: 'center'});
    const r = card.getBoundingClientRect();
    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
  }
  return null;
}"""


def hover_no_card(page, indice: int = 0) -> bool:
    """Rola o card para a tela e passa o mouse por cima dele.

    Os controles do card (download, apagar) so aparecem no HOVER. Sem isso o
    botao de download simplesmente NAO EXISTE no DOM na hora de procurar — e o
    sintoma nao e "nao achei", e "achei e o clique estourou", porque o
    elemento nasce e some enquanto o Playwright tenta.
    """
    try:
        centro = page.evaluate(JS_CARD_NA_TELA, [ICONE_DOWNLOAD, indice])
        if not centro:
            # Sem card visivel ainda: passar o mouse no meio da tela costuma
            # revelar o primeiro, que e o caso comum de um espaco com um video.
            page.mouse.move(page.viewport_size["width"] / 2,
                            page.viewport_size["height"] / 2)
            return False
        page.mouse.move(centro["x"], centro["y"])
        return True
    except Exception:
        return False


# Esvaziar o composer: tirar a imagem anexada e o texto. Com eles a caixa fica
# alta e a barra flutuante do rodape (RealDance / Lip Gen, `pointer-events`
# numa div z-30) cobre o botao de download do card — o Playwright recusa
# clicar em elemento coberto, e forcar o clique acerta a barra, nao o botao.
JS_ESVAZIAR_COMPOSER = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width>0 && r.height>0; };
  const campo = document.querySelector(
    'div[contenteditable="true"][role="textbox"], textarea, [aria-placeholder]');
  if (!campo) return {achou: false};
  let caixa = campo;
  for (let i = 0; i < 6 && caixa.parentElement; i++) {
    caixa = caixa.parentElement;
    if (caixa.querySelector('img')) break;
  }
  let removidas = 0;
  caixa.querySelectorAll('img').forEach(img => {
    const r = img.getBoundingClientRect();
    if (r.width < 20) return;
    let alvo = img;
    for (let i = 0; i < 3 && alvo.parentElement; i++) {
      alvo = alvo.parentElement;
      const x = alvo.querySelector('button');
      if (x && vis(x)) { x.click(); removidas++; return; }
    }
  });
  return {achou: true, removidas: removidas};
}"""


def esvaziar_composer(page) -> int:
    """Remove as miniaturas anexadas. Devolve quantas sairam."""
    try:
        resultado = page.evaluate(JS_ESVAZIAR_COMPOSER) or {}
        return int(resultado.get("removidas") or 0)
    except Exception:
        return 0


def botao_download(page, indice: int = 0):
    """O botao de download do card `indice`, contando so os visiveis.

    A contagem tem que casar com a de `cards_prontos`, que tambem so conta
    visivel — o Digen renderiza cada controle duas vezes (variante mobile
    escondida + desktop), e misturar as duas ordens baixaria o clipe errado.
    """
    loc = page.locator(f'button:has(svg path[d^="{ICONE_DOWNLOAD}"])')
    try:
        total = loc.count()
    except Exception:
        return None
    vistos = 0
    for i in range(total):
        item = loc.nth(i)
        try:
            if not item.is_visible():
                continue
        except Exception:
            continue
        if vistos == indice:
            return item
        vistos += 1
    return None


# ------------------------------------------------------------------- anexo
# Ponto de anexo de imagem de referencia no composer.
#
# O "+" e um popover-trigger do Radix com o icone Plus do Phosphor — mesma
# stack do resto do site, e por isso a ancora e o `d` do path, como ja e feito
# com o download e o modelo. Combinar o icone COM `data-slot="popover-trigger"`
# e o que separa este botao de qualquer outro "+" que apareca na pagina.
ICONE_MAIS = "M224,128a8,8,0,0,1-8,8H136v80"

BOTAO_ANEXO = [
    ("css", f'button[data-slot="popover-trigger"]:has(svg path[d^="{ICONE_MAIS}"])'),
    ("css", f'button:has(svg path[d^="{ICONE_MAIS}"])'),
    ("role", "button|Upload"),
    ("role", "button|Add image"),
]

# O item DENTRO do popover que o "+" abre. Texto primeiro porque e o mais
# legivel, mas o texto depende do idioma da conta ("Enviar imagem" em pt,
# "Upload image" em en) — por isso a ultima ancora e o icone, que nao muda de
# lingua.
#
# O icone e o UploadSimple do Phosphor: bandeja com seta para CIMA. A bandeja
# sozinha e igual a do download; o que distingue e o traco da seta, e por isso
# a ancora usa *= (contem) no lugar de ^= (comeca com) — o pedaco que
# identifica esta no MEIO do path.
SETA_PARA_CIMA = "M93.66,77.66,120,51.31V144"

# Rotulo EXATO visto no menu em 24/08/2026: "Upload Image". O menu tem ainda
# "Select from Gallery" e "Character Library" — nenhum dos dois serve, e por
# isso a ancora nao pode ser "o primeiro item do popover".
OPCAO_ENVIAR_IMAGEM = [
    ("role", "button|Upload Image"),
    ("text", "Upload Image"),
    ("role", "button|Enviar imagem"),
    ("text", "Enviar imagem"),
    ("css", f'button:has(svg path[d*="{SETA_PARA_CIMA}"])'),
]

# O input de arquivo em si. NAO passa por `primeiro_visivel`: num composer
# assim ele e quase sempre `display:none`, acionado pelo botao — e
# `set_input_files` funciona nele mesmo escondido, sem precisar clicar em nada.
# Este e o caminho mais curto e o mais estavel; o botao acima e o plano B.
ENTRADA_ARQUIVO = 'input[type="file"]'


def entrada_de_arquivo(page, indice: int = 0):
    """O <input type=file> da pagina, VISIVEL OU NAO, ou None."""
    try:
        loc = page.locator(ENTRADA_ARQUIVO)
        return loc.nth(indice) if loc.count() > indice else None
    except Exception:
        return None


# Miniatura da referencia ja anexada e o "x" que a remove. VAZIAS: nada foi
# observado no DOM ainda. Lista vazia significa "nao levantado", e e isso que
# o `identity doctor` conta e reporta — nunca um seletor inventado.
# A PROVA de que o anexo pegou: o composer passa a mostrar a miniatura, e ela
# e um `blob:` criado pelo proprio navegador. Contar antes e depois e a unica
# checagem honesta — `set_input_files` nao levantar excecao nao prova nada, e
# foi assim que uma rodada inteira reportou "1 referencia anexada" com o
# composer vazio.
# As miniaturas sao contadas DENTRO do composer, ancorando no campo de prompt
# e subindo ate o bloco que o contem. Contar por `blob:` na pagina inteira nao
# serve: a miniatura nem sempre e blob (as vezes ja e a URL do CDN), e ai a
# contagem dava zero com a imagem visivel na tela — foi assim que uma
# substituicao passou por "recusa".
JS_MINIATURAS = """() => {
  const campo = document.querySelector(
    'div[contenteditable="true"][role="textbox"], textarea, [aria-placeholder]');
  if (!campo) return [];
  let caixa = campo;
  for (let i = 0; i < 6 && caixa.parentElement; i++) {
    caixa = caixa.parentElement;
    if (caixa.querySelector('img')) break;
  }
  return Array.from(caixa.querySelectorAll('img'))
    .filter(i => { const r = i.getBoundingClientRect();
                   return r.width > 20 && r.height > 20; })
    .map(i => i.currentSrc || i.src || '');
}"""


def miniaturas(page) -> list[str]:
    """As miniaturas de referencia que o composer esta mostrando agora."""
    try:
        return [str(s) for s in page.evaluate(JS_MINIATURAS)]
    except Exception:
        return []


REMOVER_REFERENCIA = [
    ("role", "button|Remove"),
    ("css", 'button[aria-label*="emove"]'),
]

# As tres listas acima descrevem um fluxo de anexo que e o mesmo nos dois
# sites que este projeto automatiza (mesmos tokens de tema, mesmos icones
# Phosphor). Sao constantes com nome, e nao literais espalhadas, exatamente
# para poderem ser reaproveitadas pelo modulo de seletores do outro provedor
# sem copiar nada.


# Contador de creditos no topo. O aria-label traz o plano e o saldo
# ("UltraMax, Meme 3, Pro Meme 0"); o texto do botao traz so o numero.
CREDITOS = [
    ("css", "button[aria-label*='Meme']"),
    ("css", "button[aria-label*='Credit']"),
]

# Erro explicito: falhar rapido em vez de esperar o timeout inteiro.
ERRO_GERACAO = [
    ("text", "insufficient"),
    ("text", "not enough credits"),
    ("text", "out of credits"),
    ("text", "quota"),
    ("text", "Generation failed"),
]

# Botoes do rodape do composer. Todos sao gatilhos de POPOVER: clicar abre um
# menu, nao alterna o valor. O texto do botao ja mostra o valor atual, entao da
# para saber se precisa mexer sem abrir nada.
BOTAO_ASPECTO = [
    ("css", "button:has-text('9:16')"),
    ("css", "button:has-text('16:9')"),
    ("css", "button:has-text('1:1')"),
    ("css", "button:has-text('Auto')"),
]
BOTAO_DURACAO = [
    ("css", "button:has-text('3s')"),
    ("css", "button:has-text('5s')"),
    ("css", "button:has-text('8s')"),
    ("css", "button:has-text('10s')"),
]

# Resolucao. Cada modelo oferece um conjunto diferente: o RM3.2 chegava a 720P,
# o RM3.5 so tem 480P. Por isso a escolha e por LISTA DE PREFERENCIA, nao por
# valor fixo — pedir "720P" num modelo que nao tem so daria aviso eterno.
BOTAO_RESOLUCAO = [
    ("css", "button:has-text('480P')"),
    ("css", "button:has-text('720P')"),
    ("css", "button:has-text('1080P')"),
    ("css", "button:has-text('540P')"),
]

DURACOES_CONHECIDAS = ("3s", "5s", "8s", "10s", "12s", "15s")
RESOLUCOES_CONHECIDAS = ("360P", "480P", "540P", "720P", "1080P", "1440P", "4K")

# Valor especial de config: "leia o menu e pegue o maior que existir". Melhor
# que lista fixa porque cada modelo oferece um conjunto diferente e modelos
# novos aparecem com valores que ninguem catalogou aqui ainda.
MAXIMO = "max"

# Proporcoes em pe. A ordem e da mais alta para a menos alta: qualquer uma
# serve para video vertical, e nenhuma pode virar paisagem por acidente.
ASPECTOS_VERTICAIS = ("9:16", "2:3", "3:4")

_NUMERO = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([sSpPkK]?)\s*$")

JS_OPCOES_POPOVER = """() => {
  const vis = e => { const r = e.getBoundingClientRect();
                     return r.width > 0 && r.height > 0; };
  const caixas = document.querySelectorAll(
    '[data-radix-popper-content-wrapper],[role=dialog],[role=menu],[role=listbox]');
  const out = [];
  caixas.forEach(c => Array.from(c.querySelectorAll('*')).filter(vis)
    .filter(e => e.children.length === 0)
    .forEach(e => { const t = (e.innerText || '').trim();
                    if (t && t.length < 12) out.push(t); }));
  return out;
}"""


def valor_deitado(aspecto: str) -> bool:
    """"16:9" -> True, "9:16" -> False, "Auto" -> False (nao da para saber).

    So o que e comprovadamente mais largo que alto conta: um rotulo que nao da
    para ler nao pode virar motivo de abortar a geracao.
    """
    largura, _, altura = (aspecto or "").partition(":")
    try:
        return float(largura) > float(altura)
    except ValueError:
        return False


def valor_numerico(texto: str) -> float | None:
    """"8s" -> 8.0, "1080P" -> 1080.0, "4K" -> 2160.0. Nao numerico -> None."""
    casou = _NUMERO.match(texto or "")
    if not casou:
        return None
    numero = float(casou.group(1))
    if casou.group(2).lower() == "k":
        numero *= 540          # 4K -> 2160, na mesma escala das linhas
    return numero


def opcoes_do_popover(page) -> list[str]:
    """Textos das opcoes no popover ABERTO, sem repetir.

    Repetem porque o Digen renderiza cada item duas vezes (mobile escondida +
    desktop visivel) — o filtro de visibilidade ja tira a escondida, mas a
    deduplicacao protege contra qualquer outra copia.
    """
    try:
        textos = page.evaluate(JS_OPCOES_POPOVER)
    except Exception:
        return []
    vistos, saida = set(), []
    for texto in textos:
        limpo = " ".join((texto or "").split())
        if limpo and limpo not in vistos:
            vistos.add(limpo)
            saida.append(limpo)
    return saida


def maior_opcao(page, conhecidos: tuple[str, ...]) -> str | None:
    """A maior opcao numerica visivel no popover aberto."""
    candidatos = [t for t in opcoes_do_popover(page)
                  if valor_numerico(t) is not None]
    if not candidatos:
        return None
    return max(candidatos, key=valor_numerico)

# Botao de modelo. Mostra o valor atual ABREVIADO ("RM3.2") num <span>, mas o
# menu usa o nome completo ("Real Motion 3.2") — ver `abreviar_modelo`.
#
# A ancora e o `d` do icone (o "D" do Digen), nao o texto: com um modelo que
# nao seja Real Motion o botao mostra "Sora 2" ou "Kling 3.0", e qualquer
# seletor por texto pararia de casar.
ICONE_MODELO = "M14.019 10.5c0-3.065-1.417-4.43-2.697-5.15"

# Familias de modelo, para ler o botao SEJA QUAL FOR o modelo escolhido.
#
# O icone acima e o "D" da Digen e so aparece nos Real Motion. Ancorar apenas
# nele (e em "RM"/"Real Motion", que era o resto da lista) fazia o botao ficar
# ILEGIVEL depois de trocar para Kling: a troca acontecia e a conferencia
# devolvia None, derrubando o job com "ficou em None". A conferencia estava
# certa; a lista e que so enxergava a casa.
FAMILIAS_DE_MODELO = ("RM", "Real Motion", "Kling", "Runway", "Sora", "Veo",
                      "Seedance", "MiniMax", "FLUX", "Grok", "Gemini",
                      "HappyHorse")

BOTAO_MODELO = [
    ("css", f'button:has(svg path[d^="{ICONE_MODELO}"])'),
] + [("css", f"button[aria-haspopup='dialog']:has-text('{familia}')")
     for familia in FAMILIAS_DE_MODELO]

ASPECTOS_CONHECIDOS = ("9:16", "16:9", "1:1", "4:3", "3:4", "Auto")

# Nomes exatos do menu, na ordem em que aparecem (levantado em 22/08/2026).
# A ORDEM IMPORTA: "Real Motion 3.5 Turbo" vem ANTES de "Real Motion 3.5", e
# por isso a selecao NAO pode usar busca por substring — `has-text('Real Motion
# 3.5')` casaria com o Turbo, que e o primeiro da lista.
MODELOS_CONHECIDOS = (
    "Real Motion 3.5 Turbo",
    "Real Motion 3.5",
    "Real Motion 3.1 Turbo",
    "Real Motion 3.1",
    "Real Motion 3.2",
    "Real Motion Turbo",
    "Real Motion 2.6",
    "Real Motion 3.2 Remix",
    "Real Motion 2.6 Remix",
    "MiniMax H3 Fast",
    "MiniMax H3",
    "FLUX 3 Video",
    "Gemini Omni Flash",
    "Google Veo 3.1",
    "Seedance 2.0",
    "Seedance 2.0 Mini",
    "Seedance 2.0 Fast",
    "Grok Video 1.5",
    "Grok Video",
    "HappyHorse 1.0",
    "Sora 2 Max",
    "Sora 2",
    "Kling 3.0",
    "Runway Gen-4.5",
)


def abreviar_modelo(nome: str) -> str:
    """Nome do menu -> como o botao do composer mostra.

    "Real Motion 3.5" aparece como "RM3.5". Serve para saber se o modelo ja
    esta certo sem precisar abrir o popover.
    """
    if nome.startswith("Real Motion "):
        return "RM" + nome[len("Real Motion "):]
    return nome


# Container do popover aberto (Radix UI). Escopo obrigatorio: a pagina de
# Spaces tem uma galeria "Need some inspiration?" com um card intitulado
# "Real Motion 3.5" — sem escopo, o seletor casava com o CARD atras do menu e
# o clique nao trocava modelo nenhum.
POPOVER = ("[data-radix-popper-content-wrapper]", "[role='dialog']",
           "[role='menu']", "[role='listbox']")


def opcao_de_modelo(nome: str) -> list[tuple[str, str]]:
    """Item do menu de modelos, por texto EXATO e dentro do popover.

    Exato porque "Real Motion 3.5 Turbo" vem ANTES de "Real Motion 3.5" na
    lista: substring escolheria o Turbo. Escopado porque o mesmo texto existe
    na galeria da pagina.
    """
    return [("css", f"{caixa} :text-is('{nome}')") for caixa in POPOVER] + [
        ("role", f"menuitem|{nome}"),
        ("role", f"option|{nome}"),
    ]

def opcao_de_popover(valor: str) -> list[tuple[str, str]]:
    """Opcao dentro do popover aberto (proporcao, duracao...).

    Escopado ao popover pelo mesmo motivo de `opcao_de_modelo`: texto solto na
    pagina casaria com conteudo de fundo.
    """
    return [("css", f"{caixa} :text-is('{valor}')") for caixa in POPOVER] + [
        ("role", f"menuitem|{valor}"),
        ("role", f"option|{valor}"),
        ("role", f"button|{valor}"),
    ]


ESTRATEGIAS = ("role", "placeholder", "text", "label", "testid", "css")


class SeletorNaoEncontrado(LookupError):
    """Nenhum candidato casou — quase sempre e deploy novo do Digen."""


def _locator(page, estrategia: str, valor: str):
    if estrategia == "role":
        papel, _, nome = valor.partition("|")
        if nome:
            return page.get_by_role(papel, name=nome, exact=False)
        return page.get_by_role(papel)
    if estrategia == "placeholder":
        return page.get_by_placeholder(valor, exact=False)
    if estrategia == "text":
        return page.get_by_text(valor, exact=False)
    if estrategia == "label":
        return page.get_by_label(valor, exact=False)
    if estrategia == "testid":
        return page.get_by_test_id(valor)
    return page.locator(valor)


# Quantas duplicatas do mesmo seletor vale a pena varrer atras de uma visivel.
LIMITE_DUPLICATAS = 10


def primeiro_visivel(loc, timeout: float = 2.0):
    """Primeiro elemento VISIVEL entre os que o locator casa, ou None.

    Nao da para olhar so `.first`: o Digen renderiza o mesmo controle duas
    vezes (variante mobile escondida + desktop visivel), e a escondida costuma
    vir primeiro no DOM. Checar apenas `.first` retornava "nao existe" para
    elementos que estavam na tela — foi assim que o contador de creditos
    sumiu mesmo estando visivel.
    """
    limite = time.monotonic() + timeout
    while True:
        try:
            total = loc.count()
        except Exception:
            total = 0
        for i in range(min(total, LIMITE_DUPLICATAS)):
            item = loc.nth(i)
            try:
                if item.is_visible():
                    return item
            except Exception:
                continue
        if time.monotonic() >= limite:
            return None
        time.sleep(0.2)


def encontrar(page, candidatos: list[tuple[str, str]], timeout: float = 2.0):
    """Primeiro candidato visivel, ou None.

    `timeout` e por candidato e curto de proposito: a lista inteira e varrida
    varias vezes durante o polling de estado, e nao da para pagar 30 s em cada
    tentativa que nao existe nessa tela.
    """
    for estrategia, valor in candidatos:
        try:
            achado = primeiro_visivel(_locator(page, estrategia, valor), timeout)
        except Exception:
            continue
        if achado is not None:
            return achado
    return None


def _site_da_url(url: str) -> str:
    """"picassoia.com" a partir da URL — para o erro acusar QUEM mudou."""
    resto = str(url or "").split("//", 1)[-1]
    dominio = resto.split("/", 1)[0].split("?", 1)[0]
    partes = [p for p in dominio.split(".") if p and p != "www"]
    return ".".join(partes[-2:]) if len(partes) >= 2 else (dominio or "o site")


def resolver(page, candidatos: list[tuple[str, str]], descricao: str,
             timeout: float = 10.0):
    """Como `encontrar`, mas exige o elemento e explica como consertar.

    A mensagem acusava sempre o "Digen" e mandava editar
    `src/identity/selectors.py`. As duas coisas estavam erradas: `resolver` e
    generico (o PicassoIA passa por aqui tanto quanto o Digen) e `src` virou
    `builds` na reorganizacao de 01/09/2026. Em 08/09 as 17:11 o login do
    PICASSOIA falhou e o log mandou consultar o layout do DIGEN num caminho
    que nao existe mais — a mensagem custou mais tempo do que economizou.
    """
    loc = encontrar(page, candidatos, timeout=timeout / max(len(candidatos), 1))
    if loc is None:
        site = _site_da_url(getattr(page, "url", ""))
        raise SeletorNaoEncontrado(
            f"Nao achei {descricao} em {page.url}.\n"
            f"Candidatos tentados: {candidatos}\n"
            f"O {site} provavelmente mudou o layout. Rode:\n"
            "    python main.py identity probe\n"
            "e atualize a lista em builds/identity/selectors.py.")
    return loc


# O card do Digen NAO mostra o prompt (verificado no DOM em 25/08/2026): so o
# titulo do espaco e os presets, "RM3.5 / 3s / 480P". E o que existe para a
# prova de origem conferir contra os presets que o worker aplicou — pouco,
# mas e evidencia positiva quando NAO bate.
JS_TEXTO_DO_CARD = """([icone, alvo]) => {
  const visivel = e => { const r = e.getBoundingClientRect();
                         return r.width > 0 && r.height > 0; };
  let n = 0;
  for (const botao of document.querySelectorAll('button')) {
    const path = botao.querySelector('svg path');
    if (!path) continue;
    if (!(path.getAttribute('d') || '').startsWith(icone)) continue;
    if (!visivel(botao)) continue;
    if (n++ !== alvo) continue;
    let card = botao;
    for (let i = 0; i < 8 && card.parentElement; i++) {
      card = card.parentElement;
      if (card.querySelector('video, img')) break;
    }
    return (card.innerText || '').slice(0, 400);
  }
  return null;
}"""


def texto_do_card(page, indice: int = 0) -> str | None:
    """Texto visivel do card `indice` (presets), ou None se nao der para ler."""
    try:
        texto = page.evaluate(JS_TEXTO_DO_CARD, [ICONE_DOWNLOAD, indice])
    except Exception:
        return None
    return str(texto) if texto else None
