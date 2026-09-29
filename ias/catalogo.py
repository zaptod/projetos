# -*- coding: utf-8 -*-
"""O catalogo de TEXTOS que cada site poe na tela no lugar da resposta.

E o pedaco mais valioso da ficha, nas palavras do Adrian: "possiveis erros,
mensagem de limite de cota etc.". Duas fontes, e as duas entram na ficha com
a `fonte` escrita:

  CONHECIDOS   o que o codigo e os logs ja sabiam (texto.RECUSA_ENLATADA,
               probe.BARRADO, a parede do PicassoIA, os "Algo deu errado"
               do Gemini nos logs de setembro) — com o SELETOR de onde cada
               um aparece, quando ha um.
  a sonda      o que a pagina mostra AGORA: `varrer()` recebe o texto visivel
               e devolve so as linhas que casam com alguma categoria.

`classificar()` e uma funcao pura (texto -> categoria ou None) e por isso e
testavel com dublê: nenhuma linha daqui abre navegador.
"""
from __future__ import annotations

import re

# Ordem importa: a primeira categoria que casar ganha. "limite" antes de
# "upgrade" porque a frase de cota costuma trazer os dois ("Voce atingiu o
# limite... faca upgrade"), e o que decide a acao e o limite.
PADROES = (
    ("cloudflare", re.compile(
        r"\b(?:just a moment|um momento|checking your browser|verificando"
        r"\s+(?:seu|o)\s+navegador|attention required|cloudflare"
        r"|verify you are human|confirme que (?:voce|você) (?:e|é) humano"
        r"|are you a robot)\b", re.IGNORECASE)),
    ("limite", re.compile(
        r"(?:limite\s+(?:de\s+)?(?:uso|mensagens|diari|di[aá]rio|atingid|alcanc)"
        r"|atingiu\s+(?:o\s+)?(?:seu\s+)?limite|voc[eê]\s+atingiu"
        r"|you(?:'ve| have)\s+(?:reached|hit)\s+(?:your|the)\s+(?:\w+\s+)?limit"
        r"|(?:usage|rate|message|daily)\s+limit|too many (?:requests|messages)"
        r"|limit(?:e)?\s+(?:reached|exceeded)|cota\s+(?:esgotad|excedid|atingid)"
        r"|quota\s+(?:exceeded|reached)|sem\s+cr[eé]ditos?|no\s+credits?"
        r"|insufficient\s+credits?|not\s+enough\s+credits?|out\s+of\s+credits?"
        r"|cr[eé]ditos?\s+insuficiente|acabaram\s+(?:seus|os)\s+cr[eé]ditos"
        r"|(?:tente|volte)\s+(?:novamente\s+)?(?:em|daqui\s+a|após|apos|depois\s+de)\s+"
        r"\d+\s*(?:h|hora|min|minuto)|try again (?:in|after)\s+\d+"
        r"|resets? (?:in|at)\s+\d+|redefin\w+\s+(?:em|às|as)\s+\d+)",
        re.IGNORECASE)),
    ("upgrade", re.compile(
        r"(?:fa[cç]a\s+(?:o\s+)?upgrade|fazer\s+upgrade|upgrade\s+(?:to|para|now|do\s+plano)"
        r"|assine\s+(?:para|o|agora)|assinar\s+(?:o\s+)?(?:plano|pro|plus)"
        r"|subscribe\s+to|get\s+(?:plus|pro|premium|supergrok)"
        r"|(?:experimente|try)\s+(?:o\s+)?(?:gemini\s+advanced|google\s+ai\s+pro"
        r"|chatgpt\s+plus|supergrok|premium\+?)"
        r"|planos\s+e\s+cr[eé]ditos|ver\s+planos|view\s+plans|desbloqueie"
        r"|unlock\s+(?:more|higher)|(?:^|\b)(?:pro\+|plus|premium|supergrok)\b"
        r"\s*(?:\(|—|-|:)?\s*(?:mais|more|unlimited|ilimitad))", re.IGNORECASE)),
    ("recusa_enlatada", re.compile(
        r"(?:modelo\s+de\s+linguagem|ia\s+(?:com\s+)?base(?:ada)?\s+em\s+texto"
        r"|fui\s+(?:programad|criad|treinad|feit)[oa]"
        r"|(?:processar|gerar)\s+(?:e\s+(?:processar|gerar)\s+)?texto"
        r"|al[eé]m\s+das\s+minhas\s+(?:capacidades|habili)"
        r"|n[aã]o\s+consigo\s+criar\s+(?:esse|este)\s+tipo"
        r"|n[aã]o\s+(?:tenho\s+como|consigo|posso)\s+(?:te\s+)?ajudar"
        r"|language\s+model|text[-\s]based\s+ai|not\s+programmed\s+to"
        r"|outside\s+(?:of\s+)?my\s+capabilities|i\s+can'?t\s+help\s+with\s+that)",
        re.IGNORECASE)),
    ("conteudo", re.compile(
        r"(?:content\s+policy|policy\s+violation|violates?\s+our|blocked\s+by\s+our"
        r"|sensitive\s+content|safety\s+system|conte[uú]do\s+(?:ilegal|bloquead|sens[ií]vel"
        r"|impr[oó]prio|n[aã]o\s+permitido)|viola\s+(?:nossas?|as)\s+(?:pol[ií]ticas|diretrizes)"
        r"|this\s+request\s+(?:violates|may\s+violate)|n[aã]o\s+posso\s+gerar\s+(?:essa|esta)\s+imagem)",
        re.IGNORECASE)),
    ("indisponivel", re.compile(
        r"(?:modelo\s+(?:indispon[ií]vel|temporariamente)|model\s+(?:is\s+)?(?:unavailable|overloaded)"
        r"|(?:servi[cç]o|service)\s+(?:indispon[ií]vel|unavailable)|alta\s+demanda|high\s+demand"
        r"|capacity|estamos\s+com\s+muita\s+procura|tente\s+(?:novamente\s+)?mais\s+tarde"
        r"|try\s+again\s+later|temporarily\s+unavailable|servidor\s+ocupado|server\s+is\s+busy)",
        re.IGNORECASE)),
    ("erro_site", re.compile(
        r"(?:algo\s+deu\s+errado(?:\s*\(\d+\))?|something\s+went\s+wrong|ocorreu\s+um\s+erro"
        r"|an\s+error\s+occurred|generation\s+failed|falha\s+(?:na|ao)\s+gera[cç]"
        r"|n[aã]o\s+foi\s+poss[ií]vel\s+(?:gerar|enviar|carregar|concluir)|failed\s+to\s+(?:generate|load|send)"
        r"|erro\s+(?:de\s+)?(?:rede|conex[aã]o)|network\s+error|tente\s+(?:de\s+novo|novamente)\b)",
        re.IGNORECASE)),
    ("consentimento", re.compile(
        r"(?:direitos\s+sobre\s+os\s+conte[uú]dos|confira\s+se\s+voc[eê]\s+tem\s+os\s+direitos"
        r"|you\s+have\s+the\s+rights|i\s+agree|concordo\b|aceitar\s+(?:os\s+)?termos|accept\s+(?:the\s+)?terms)",
        re.IGNORECASE)),
    ("login", re.compile(
        r"(?:fa[cç]a\s+login|fazer\s+login|entre\s+para\s+(?:usar|continuar)|entrar\s+com\s+google"
        r"|sign\s+in\s+(?:to|with)|log\s+in\s+to|sua\s+sess[aã]o\s+expirou|session\s+(?:has\s+)?expired"
        r"|entre\s+na\s+(?:sua\s+)?conta)", re.IGNORECASE)),
)

# Uma linha da tela so vira item do catalogo se for curta: um paragrafo de
# resposta que cita "language model" e resposta, nao aviso (mesma regua de
# `texto.RECUSA_MAXIMA`).
LINHA_MAXIMA = 300
LINHA_MINIMA = 6


def classificar(texto) -> str | None:
    """A categoria daquele texto, ou None quando nao parece aviso nenhum."""
    limpo = " ".join(str(texto or "").split())
    if len(limpo) < LINHA_MINIMA or len(limpo) > LINHA_MAXIMA:
        return None
    for categoria, padrao in PADROES:
        if padrao.search(limpo):
            return categoria
    return None


def item(categoria: str, texto: str, *, seletor: str | None = None,
         fonte: str = "sonda", visto_em: str | None = None,
         nota: str = "") -> dict:
    return {"categoria": categoria, "texto": " ".join(str(texto).split())[:LINHA_MAXIMA],
            "seletor": seletor, "fonte": fonte, "visto_em": visto_em,
            "nota": nota}


def varrer(texto_visivel: str, *, fonte: str = "sonda",
           visto_em: str | None = None, seletor: str | None = None) -> list:
    """As linhas do texto visivel que sao aviso, ja classificadas, sem repetir."""
    vistos = set()
    saida = []
    for linha in str(texto_visivel or "").splitlines():
        limpo = " ".join(linha.split())
        categoria = classificar(limpo)
        if categoria is None:
            continue
        chave = (categoria, limpo.lower())
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(item(categoria, limpo, seletor=seletor, fonte=fonte,
                          visto_em=visto_em))
    return saida


def juntar(existentes: list, novos: list) -> list:
    """Catalogo sem repetidos (categoria + texto, sem caixa). O antigo fica."""
    saida = []
    vistos = set()
    for lista in (existentes or [], novos or []):
        for it in lista:
            if not isinstance(it, dict) or not it.get("texto"):
                continue
            chave = (it.get("categoria"), " ".join(str(it["texto"]).split()).lower())
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append(it)
    return saida


# --------------------------------------------------------- o que ja se sabia
# Cada item tem a `fonte` ("codigo": esta em algum modulo; "logs": apareceu
# em outputs/_logs; "docs": esta nas memorias/docs de sessao) e o seletor de
# onde aparece, quando ha um. Datas sao as das medicoes registradas.
CONHECIDOS = {
    "gemini": [
        item("recusa_enlatada", "Sou uma IA com base em texto, e isso está além das minhas capacidades",
             seletor="model-response message-content .markdown", fonte="logs",
             visto_em="2026-09-13..27", nota="frase sorteada de lista fixa; 18/169 revisões de vídeo; contos/llm/texto.RECUSA_ENLATADA"),
        item("recusa_enlatada", "Não fui programado para fazer isso",
             seletor="model-response message-content .markdown", fonte="logs", visto_em="2026-09-27"),
        item("recusa_enlatada", "Fui criado apenas para processar e gerar texto",
             seletor="model-response message-content .markdown", fonte="logs", visto_em="2026-09-28"),
        item("recusa_enlatada", "Não consigo criar esse tipo de vídeo",
             seletor="model-response message-content .markdown", fonte="logs", visto_em="2026-09-27"),
        item("erro_site", "Algo deu errado (1155)", seletor="(toast; devolve a pergunta à caixa)",
             fonte="logs", visto_em="2026-09-27", nota="devolve o prompt à caixa sem anexo; cliente._envio_devolvido"),
        item("upgrade", "Faça upgrade para o Google AI Pro", seletor="(barra lateral)",
             fonte="docs", visto_em="2026-09-27", nota="conta free; decisão gemini-pago = fica na gratuita"),
        item("consentimento", "Confira se você tem os direitos sobre os conteúdos que enviar",
             seletor="[data-test-id='video-upload-consent-dialog-agree-button'] button",
             fonte="codigo", visto_em="2026-09-11", nota="modal a cada vídeo; enquanto aberto o Enviar não faz nada"),
        item("outro", "Responder agora", seletor="button:has-text('Responder agora')",
             fonte="codigo", visto_em="2026-09-14", nota="raciocínio preso >300 s; não é limite"),
        item("limite", "Verifique se a conta atingiu o limite de uso", seletor="(mensagem do cliente, não do site)",
             fonte="logs", visto_em="2026-09-14", nota="FALSO ALARME medido: era raciocínio preso (gemini-raciocinio-preso)"),
    ],
    "chatgpt": [
        item("cloudflare", "Um momento… / Just a moment…", seletor="document.title",
             fonte="codigo", visto_em="2026-09-09", nota="só em janela headless; não é deslogado (probe.BARRADO)"),
        item("login", "Criar imagem. Entre para usar.", seletor="button[aria-label='Criar imagem. Entre para usar.']",
             fonte="logs", visto_em="2026-08-31", nota="probe de 31/08 deslogado: imagem e anexo pedem login"),
        item("login", "Adicionar arquivos. Entre para usar.", seletor="button[aria-label*='Entre para usar']",
             fonte="logs", visto_em="2026-08-31"),
        item("outro", "vídeo mp4 entra como 'Arquivo' opaco (conta free não assiste)",
             seletor="div[data-testid*='attachment']", fonte="docs", visto_em="2026-09-12"),
    ],
    "deepseek": [
        item("outro", "Pensou por N segundos (raciocínio DeepThink, em inglês, nunca lido)",
             seletor="div.ds-think-content", fonte="codigo", visto_em="2026-09-17"),
        item("login", "Entrar com Google", seletor="div[role='button']:has-text('Entrar com Google')",
             fonte="codigo", visto_em="2026-09-17"),
    ],
    "grok": [],
    "picasso": [
        item("parede", "Planos e Créditos (diálogo de promoção/assinatura cobre a página)",
             seletor="div[role='dialog'] / [data-slot='dialog-content'] (overlay fixed inset-0 z-50)",
             fonte="codigo", visto_em="2026-09-09", nota="engole o clique no #submit-button; fecha no X ou ESC"),
        item("upgrade", "Assine para Gerar", seletor="button:has-text('Assine para Gerar')",
             fonte="codigo", visto_em="2026-09-17", nota="ParedeDePlanos: sessão FREE numa conta com plano; reabrir o perfil resolve"),
        item("upgrade", "FREE -> PRO+", seletor="(cabeçalho)", fonte="docs", visto_em="2026-09-17"),
        item("conteudo", "CONTEÚDO ILEGAL (escudo shield-alert text-destructive no card)",
             seletor="svg.lucide-shield-alert.text-destructive", fonte="codigo", visto_em="2026-09-15",
             nota="recusa de conteúdo: reescrever o prompt resolve"),
        item("erro_site", "card com ícone lucide-image quebrado em text-destructive (geração morreu do lado do site)",
             seletor="[class*='text-destructive'] sem escudo", fonte="codigo", visto_em="2026-09-09",
             nota="reenviar igual resolve; não é conteúdo"),
        item("erro_site", "Aprimorador de Prompt: 'avaliação terminou' (falha passageira, parecia fim do grátis)",
             seletor="#promptEnhancerRealtime", fonte="docs", visto_em="2026-09-14"),
    ],
    "dreamface": [
        item("limite", "insufficient / not enough credits / out of credits",
             seletor="text=…", fonte="codigo", visto_em="2026-09-01", nota="dreamface_selectors.ERRO_GERACAO"),
        item("erro_site", "Generation failed / try again", seletor="text=…", fonte="codigo", visto_em="2026-09-01"),
        item("login", "Entrar/Cadastro (menu; sessão ausente)", seletor="text='Entrar/Cadastro'", fonte="codigo",
             visto_em="2026-09-01", nota="login é MODAL com reCAPTCHA: sempre manual"),
    ],
    "digen": [
        item("parede", "20% OFF Real Motion 3.5 Fast (modal 'Upgrade' cobre a página, 10-15 s após carregar)",
             seletor="[role='dialog'][data-slot='dialog-content'] img[alt='Upgrade']", fonte="codigo",
             visto_em="2026-09-28", nota="client.tirar_parede_da_frente; fecha em button[data-slot='dialog-close']"),
        item("limite", "insufficient / not enough credits / out of credits / quota",
             seletor="text=…", fonte="codigo", visto_em="2026-08-22", nota="selectors.ERRO_GERACAO"),
        item("outro", "Free, Meme 0, Pro Meme 0 (placeholder do chip de créditos nos primeiros ~15 s)",
             seletor="button[aria-label*='Meme']", fonte="codigo", visto_em="2026-08-22",
             nota="ler cedo dá 0 falso; DigenClient.creditos espera"),
        item("erro_site", "Generation failed", seletor="text='Generation failed'", fonte="codigo", visto_em="2026-08-22"),
    ],
}


def conhecidos(ia: str) -> list:
    return [dict(it) for it in CONHECIDOS.get(str(ia).lower(), [])]
