# -*- coding: utf-8 -*-
"""Publicar no YouTube pelo NAVEGADOR, quando a API recusa.

Por que existe (medido em 01/09/2026): a API do YouTube passou a responder
`uploadLimitExceeded` para um canal de UM DIA de vida com 11 uploads — e
continuou recusando depois de o dia virar no horario do Pacifico. No mesmo
momento, subir video pelo YouTube Studio **funcionava normalmente**. Sao dois
baldes diferentes, e o do navegador e muito mais folgado.

Este modulo e o irmao do `tiktok.py`: mesmo Chrome de verdade, mesmo perfil
persistente, mesmo login manual feito UMA vez. As diferencas com o TikTok,
que valem estar escritas:

  1. O upload do Studio e um ASSISTENTE de varios passos (detalhes ->
     elementos -> verificacoes -> visibilidade), nao uma tela so. Cada
     "Proximo" precisa ser esperado, nao clicado no relogio.
  2. Ha um campo OBRIGATORIO que nao existe no TikTok: "feito para
     criancas". Sem responder, o botao de publicar nunca habilita — e o
     video fica preso num rascunho invisivel.
  3. O resultado tem que ser CONFERIDO. A licao do TikTok vale aqui: dormir
     15 segundos e dizer "publicado" e promessa, nao fato.

O login e MANUAL e continua sendo: a conta Google tem 2FA e captcha, e
automatizar credencial ali seria frágil e errado.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

from .. import atividade
from ..identity.browser import (AberturaFalhou, abrir_pagina,
                                contexto_persistente, ir_para, montou)
from . import escrita

RAIZ = Path(__file__).resolve().parents[2]
PERFIL = RAIZ / ".browser_profile" / "youtube_web"

URL_STUDIO = "https://studio.youtube.com"
URL_UPLOAD = "https://www.youtube.com/upload"


def url_de_upload(canal: str = "builds") -> str:
    """A URL que MIRA o canal certo.

    Este e o ponto do exercicio. Quando todos os canais moram na MESMA conta
    Google — que e o caso aqui —, o login nao distingue nada: o que separa um
    canal do outro e qual deles esta selecionado no Studio. Depender do
    "selecionado" e depender de memoria de navegador, e um dia o video vai
    para o canal errado, de forma irreversivel.

    Com o id do canal (`UC...`) gravado no registro de contas, a URL aponta
    para o canal direto e nao ha o que dar errado:

        studio.youtube.com/channel/UCxxxx/videos/upload

    Sem id gravado, cai na URL generica — que usa o canal atual do Studio.
    Rode `main.py publicar --canais` para gravar os ids.
    """
    try:
        from ..contas import ativa, identidade
        quem = identidade("youtube_web", ativa("youtube_web", canal))
        if quem.get("id"):
            return (f"{URL_STUDIO}/channel/{quem['id']}/videos/upload"
                    f"?{PARAMETRO_DIALOGO}")
    except Exception:
        pass
    return URL_UPLOAD

# CRIAR -> ENVIAR VIDEOS. Sem estes dois passos a pagina do canal nao tem
# campo de arquivo nenhum: `/videos/upload` so FILTRA a lista de videos, ele
# nao abre o envio. Medido em 01/09/2026 — o campo de arquivo era 0 antes de
# clicar e 1 depois.
#
# `?d=ud` abre o dialogo direto, sem clique (testado nos dois canais). Como
# e um parametro nao documentado, os cliques ficam de reserva para o dia em
# que o YouTube o tirar.
PARAMETRO_DIALOGO = "d=ud"
# Quanto esperar o dialogo aparecer, antes e depois dos cliques.
ESPERA_DIALOGO_S = 20.0
# O DIALOGO DE ENVIO DO PROPRIO STUDIO, e o que o backdrop dele faz com o
# Criar (06/10/2026). Medido na sessao de verdade, tres aberturas do canal de
# historias: com o dialogo aberto, o elemento por cima do centro do Criar e
# `tp-yt-iron-overlay-backdrop` — o Criar continua habilitado
# (`aria-disabled="false"`), mas nenhum clique chega nele. Na rodada das
# 00:37 de 06/10 a pagina levou ~126 s para abrir e montar (o normal medido
# e 8-30 s), o campo de arquivo nao veio em 20 s, e o reserva "Criar ->
# Enviar videos" ficou 30 s esperando um clique que o backdrop engolia:
# `Locator.click: Timeout 30000ms ... resolved to <button aria-label="Criar"
# aria-disabled="false"...>`. O reserva era IMPOSSIVEL justamente quando o
# dialogo ja estava la. Agora: dialogo do Studio na tela sem o campo = ele
# esta CARREGANDO, espera-se mais; e o que cobrir o Criar e lido, fotografado
# e fechado com ESC antes do clique (o molde da parede do PicassoIA).
DIALOGO_DE_ENVIO = "ytcp-uploads-dialog tp-yt-paper-dialog"
ESPERA_DIALOGO_CARREGANDO_S = 60.0
# O clique no Criar tem prazo proprio e curto: o padrao do Playwright (30 s)
# era tempo morto com a parede na frente.
CLIQUE_CRIAR_S = 10.0
# Acima disto, abrir + montar a pagina foi LENTO, e a falha do envio que vier
# depois e da rede, nao da tela. Normal medido em 06/10: 8-30 s; a rodada que
# falhou, ~126 s.
PAGINA_LENTA_S = 60.0
BOTAO_CRIAR = (
    'button[aria-label*="Criar" i]',
    'button[aria-label*="Create" i]',
    "ytcp-button#create-icon",
    "#create-icon",
)
# ATENCAO A ORDEM. O item por TEXTO vem primeiro de proposito: `#text-item-0`
# e posicional, e o `#text-item-1` do mesmo menu e "Transmitir ao vivo".
# Se o YouTube trocar a ordem, o seletor posicional abriria uma LIVE em vez
# de um upload — errar assim e muito pior do que nao achar o botao.
MENU_ENVIAR_VIDEOS = (
    'tp-yt-paper-item:has-text("Enviar vídeos")',
    'tp-yt-paper-item:has-text("Upload videos")',
    "tp-yt-paper-item#text-item-0",
)

# A pagina do Studio e pesada; com pouco tempo a checagem acusa "em branco"
# uma pagina que so esta carregando (foi o que aconteceu no DreamFace).
PACIENCIA_S = 45.0
ESPERA_PAGINA_S = 90.0
# O YouTube processa o arquivo enquanto voce preenche; o botao so libera
# quando ele termina de subir.
ESPERA_UPLOAD_S = 900.0
ESPERA_CONFIRMAR_S = 120.0
# A ESPERA DO UPLOAD FALA (06/10/2026). Ate 15 min calada, e o postar mede
# "pendurado" pelo PULSO (toda linha da saida): 15 min de silencio deixavam
# so ~4 min de folga para os 20 min de pulso parado. Uma linha por minuto,
# sem mudar a espera.
FALA_DO_UPLOAD_S = 60.0


class _AvisoDoUpload:
    """Uma linha de progresso a cada `FALA_DO_UPLOAD_S` enquanto o arquivo sobe."""

    def __init__(self, passo, comeco: float):
        self._passo = passo
        self._comeco = comeco
        self._proximo = comeco + FALA_DO_UPLOAD_S

    def talvez(self, agora: float) -> bool:
        if agora < self._proximo:
            return False
        self._proximo = agora + FALA_DO_UPLOAD_S
        self._passo(f"o arquivo ainda sobe ({agora - self._comeco:.0f} s de "
                    f"{ESPERA_UPLOAD_S:.0f} s)...")
        return True


class YouTubeWebFalhou(RuntimeError):
    """Erro legivel — o painel mostra a frase, nao o traceback."""


class LimiteDiarioDoYouTube(YouTubeWebFalhou):
    """A conta bateu a cota de envios do dia. Nao ha o que tentar.

    E DIFERENTE de toda outra falha daqui, e por isso tem classe propria:
    esperar nao resolve, tentar de novo nao resolve, e o proximo video da fila
    vai bater na mesma parede. So passa quando o YouTube libera (vira o dia)
    ou quando alguem eleva o limite na conta.

    Como ela se apresentava antes de ser reconhecida, em 10/09/2026: o Studio
    mostra o aviso e o formulario simplesmente nao completa — o
    `VIDEO_MADE_FOR_KIDS_NOT_MFK` nunca fica clicavel e a falha chega como
    `TimeoutError: Locator.click: 30000ms`, no botao errado. Foram dois
    videos e um minuto de espera cada para descobrir uma coisa que estava
    escrita na tela.
    """


# O aviso, nas duas linguas em que a conta dele pode estar. O YouTube o mostra
# num `.error-short`, e foi assim que o Adrian o achou (10/09/2026).
LIMITE_DIARIO = (
    "limite diário de envios",
    "limite diario de envios",
    "daily upload limit",
    "you have reached the daily",
)


def _bateu_o_limite(page) -> str:
    """A frase do aviso de cota, se ela estiver na tela. `""` se nao."""
    for seletor in (".error-short", "ytcp-uploads-dialog .error-short",
                    "[class*='error-short']"):
        try:
            alvo = page.locator(seletor)
            for i in range(min(alvo.count(), 4)):
                texto = " ".join((alvo.nth(i).inner_text(timeout=1500)
                                  or "").split())
                if any(m in texto.lower() for m in LIMITE_DIARIO):
                    return texto[:160]
        except Exception:                                      # noqa: BLE001
            continue
    return ""


URL_CANAIS = ("https://www.youtube.com/channel_switcher"
              "?next=%2Faccount&feature=settings")

# O id de canal tem tamanho fixo: "UC" + 22. Sem ancorar o tamanho, a varredura
# do HTML devolve pedaco de base64 achando que e canal (ja devolveu 11).
_ID_CANAL = re.compile(r"\bUC[\w-]{22}\b")


def id_do_canal(url: str) -> str:
    r"""O id dentro de uma URL do Studio/YouTube, ou string vazia.

    O `(?![\w-])` no fim nao e enfeite: sem ele, um id de 26 caracteres
    (pedaco de base64 que parece canal) era CORTADO nos 24 primeiros e
    voltava como se fosse valido. Um id errado mas plausivel monta uma URL
    que abre em algum lugar — e ai o video sobe no canal errado. Melhor
    devolver vazio, que o chamador trata.
    """
    achado = re.search(r"/channel/(UC[\w-]{22})(?![\w-])", str(url or ""))
    return achado.group(1) if achado else ""


def canais_da_sessao(canal: str = "builds", *, log=print) -> list:
    """Os canais que ESTE login enxerga: [{nome, arroba, id}].

    Le a lista de canais da conta e resolve cada arroba no id de verdade
    abrindo a pagina do canal — o id vem do `canonical` da propria pagina,
    nao de adivinhacao no HTML.
    """
    achados = []
    with contexto_persistente(headless=False,
                              profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, URL_CANAIS)
        _esperar_montar(page)
        time.sleep(4)
        texto = ""
        try:
            texto = page.evaluate("() => document.body.innerText || ''") or ""
        except Exception:
            pass
        if "accounts.google" in page.url or "signin" in page.url:
            raise YouTubeWebFalhou(
                "esta sessao nao esta logada. Rode uma vez: "
                "`python -m builds.publicar.youtube_web --login`")

        # A lista vem como NOME / @arroba / inscritos, uma coisa por linha.
        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        for i, linha in enumerate(linhas):
            if not linha.startswith("@") or i == 0:
                continue
            arroba = linha[1:]
            nome = linhas[i - 1]
            if nome.startswith("@") or not arroba:
                continue
            achados.append({"nome": nome, "arroba": arroba, "id": ""})

        for item in achados:
            try:
                ir_para(page, f"https://www.youtube.com/@{item['arroba']}")
                time.sleep(3)
                canon = page.evaluate(
                    "() => {const l = document.querySelector"
                    "('link[rel=canonical]'); return l ? l.href : '';}") or ""
                item["id"] = id_do_canal(canon) or (
                    _ID_CANAL.search(canon).group(0)
                    if _ID_CANAL.search(canon) else "")
            except Exception as exc:
                log(f"[youtube-web] nao consegui o id de @{item['arroba']}: "
                    f"{str(exc)[:80]}")
    return [a for a in achados if a["id"]]


def usar_canal(canal: str, escolha: dict) -> dict:
    """Amarra o canal do projeto ('builds'/'historias') a um canal do YouTube.

    `escolha` e um item de `canais_da_sessao`. Cria uma conta com o nome do
    canal e grava o id — e o id que decide o destino do upload, entao a
    partir daqui `builds` e `historias` param de cair no mesmo lugar.
    """
    from .. import contas

    nome = contas.adicionar("youtube_web", escolha["nome"])
    contas.escolher("youtube_web", canal, nome)
    return contas.identificar(
        "youtube_web", nome, rotulo=escolha["nome"],
        identificador=escolha["id"], extra={"arroba": escolha.get("arroba", "")})


def perfil_da_conta(canal: str = "builds") -> Path:
    """A pasta de Chrome da conta de YouTube-web ATIVA naquele canal."""
    try:
        from ..contas import perfil
        return perfil("youtube_web", canal)
    except Exception:
        return PERFIL


# ---------------------------------------------------------------- seletores
# Candidatos em ordem de especificidade; `_primeiro` usa o que existir. O
# Studio muda de layout com frequencia: quando quebrar, rode
#     python -m builds.publicar.youtube_web --sondar
# e ajuste ESTAS listas com o que a pagina realmente tem.
ENTRADA_ARQUIVO = 'input[type="file"]'
# Onda 15D: a miniatura. O Studio tem DOIS inputs de arquivo na tela de
# detalhes — o do video (que ja foi usado) e o da capa —, entao este
# precisa ser especifico. Falhar aqui nunca derruba a publicacao: a API
# ja tentou subir a capa, e o `exportar` a entrega junto com o mp4.
ENTRADA_MINIATURA = (
    'ytcp-thumbnails-compact-editor-uploader input[type="file"]',
    '#file-loader input[type="file"]',
    'input[type="file"][accept*="image"]',
)
CAMPO_TITULO = (
    '#title-textarea #textbox',
    'ytcp-social-suggestions-textbox[id="title-textarea"] #textbox',
    'div[aria-label*="título" i][contenteditable="true"]',
    'div[aria-label*="title" i][contenteditable="true"]',
)
CAMPO_DESCRICAO = (
    '#description-textarea #textbox',
    'ytcp-social-suggestions-textbox[id="description-textarea"] #textbox',
    'div[aria-label*="descrição" i][contenteditable="true"]',
    'div[aria-label*="description" i][contenteditable="true"]',
)
# O campo obrigatorio: sem responder, "Publicar" nunca habilita.
NAO_E_PARA_CRIANCAS = (
    'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]',
    '#audience [name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]',
    'tp-yt-paper-radio-button:has-text("Não, não é conteúdo para crianças")',
    "tp-yt-paper-radio-button:has-text(\"No, it's not made for kids\")",
)
BOTAO_PROXIMO = (
    '#next-button',
    'ytcp-button#next-button',
    'button:has-text("Próximo")',
    'button:has-text("Next")',
)
VISIBILIDADE = {
    "public": ('tp-yt-paper-radio-button[name="PUBLIC"]',
               '[name="PUBLIC"]'),
    "unlisted": ('tp-yt-paper-radio-button[name="UNLISTED"]',
                 '[name="UNLISTED"]'),
    "private": ('tp-yt-paper-radio-button[name="PRIVATE"]',
                '[name="PRIVATE"]'),
}
# Agendar, na etapa de visibilidade. Sem isto o modo navegador perderia o
# agendamento da serie (24 h entre partes) — e perder isso EM SILENCIO seria
# pior do que nao ter: oito partes no mesmo minuto matam a sequencia.
BOTAO_AGENDAR = (
    'tp-yt-paper-radio-button[name="SCHEDULE"]',
    '#schedule-radio-button',
    'tp-yt-paper-radio-button:has-text("Agendar")',
    'tp-yt-paper-radio-button:has-text("Schedule")',
)
CAMPO_DATA = (
    '#datepicker-trigger input',
    'ytcp-date-picker input',
    'input[aria-label*="Data" i]',
)
CAMPO_HORA = (
    '#time-of-day-container input',
    'ytcp-form-input-container:has-text("Hora") input',
    'input[aria-label*="Hora" i]',
)

BOTAO_PUBLICAR = (
    '#done-button',
    'ytcp-button#done-button',
    'button:has-text("Publicar")',
    'button:has-text("Publish")',
    'button:has-text("Salvar")',
)
# Prova de que terminou: o Studio abre um dialogo com o link do video.
SINAIS_PUBLICADO = (
    "vídeo publicado", "video publicado", "video published",
    "processamento concluído", "link do vídeo", "share a link",
    "seu vídeo foi publicado", "your video is now live",
)
# A SEGUNDA CONFIRMACAO DO STUDIO, e a causa de 30 rascunhos no canal.
#
# Quando se clica em Publicar com o video ainda processando (ou sem
# descricao), o Studio abre um aviso com o botao "Publicar mesmo assim". O
# `_confirmar` daqui NUNCA clicou em nada — ele so procurava texto de sucesso
# —, entao o aviso ficava aberto, a espera estourava, o Chrome fechava e o
# video ficava como RASCUNHO. Dos 30 rascunhos do Neural fights em 15/09/2026,
# 29 tinham um gemeo publicado: um por postagem, todo dia, desde 10/09.
#
# O ROTULO E UM `div` DENTRO DO BOTAO (design system do Studio), igual ao
# "Publicar agora" do TikTok:
#   <div class="ytcpButtonShapeImpl__button-text-content">Publicar mesmo assim</div>
# Por isso os seletores pegam tanto o botao quanto o rotulo: clicar no rotulo
# funciona porque o clique sobe.
BOTAO_PUBLICAR_ASSIM = (
    'button:has-text("Publicar mesmo assim")',
    'button:has-text("Publish anyway")',
    'div.ytcpButtonShapeImpl__button-text-content:has-text("Publicar mesmo assim")',
    'div.ytcpButtonShapeImpl__button-text-content:has-text("Publish anyway")',
    '[class*="button-text-content"]:has-text("Publicar mesmo assim")',
    '[class*="button-text-content"]:has-text("Publish anyway")',
)
# O que a barra de estado mostra enquanto o arquivo AINDA NAO ESTA PRONTO.
# Medido em 15/09/2026, no instante em que o codigo clicava em publicar:
# "Envio concluido ... O processamento vai comecar em breve" e, logo depois,
# "Processando ate SD ... 3 minutos restantes". Ou seja: o video ia ao ar
# antes de existir nem em SD, justamente na primeira hora, que e quando o
# algoritmo mede o Short e decide se entrega.
# As fases, da mais crua para a mais adiantada. A ORDEM E O CONTEUDO:
# "processando ate SD" quer dizer que nao ha nada pronto ainda; "processando
# ate HD" quer dizer que o SD ja existe e o HD esta a caminho. Tratar as duas
# como a mesma coisa era o que escondia o problema.
FASES = (
    # "salvando" ENTRA AQUI desde 17/09/2026. Medido na prova gravada da
    # `historia_00016:celular:p02`: no instante do clique a barra dizia
    # "salvando..." com "10 minutos restantes" pela frente, nenhuma frase de
    # FASES casava, e o estagio saiu como `desconhecida`. Sem esta palavra a
    # medicao fica cega justamente no momento que ela existe para medir.
    ("subindo", ("fazendo upload", "enviando", "uploading", "salvando",
                 "saving", "processamento vai comecar", "processing will begin")),
    ("processando", ("processando ate sd", "processando video",
                     "processing sd")),
    ("sd", ("processando ate hd", "processing hd")),
)

# Quanto esperar o video ficar pronto ANTES de clicar em publicar. O teto sai
# da grade (ver `_teto_da_espera`): esperar nao pode empurrar a rodada para
# dentro do horario seguinte.
ESPERA_QUALIDADE_S = 300.0
# Mesmo comecando atrasado, vale esperar um pouco: publicar "em subindo" e o
# pior desfecho possivel.
PISO_DA_ESPERA_S = 30.0
PROCESSANDO = tuple(frase for _, frases in FASES for frase in frases)
# "3 minutos restantes" — quanto o Studio ainda pede.
FALTA = re.compile(
    r"\d+\s*(?:minutos?|segundos?|minutes?|seconds?)\s*"
    r"(?:restantes?|remaining)")
LINK_DO_VIDEO = (
    'a[href*="youtu.be/"]',
    'a[href*="/watch?v="]',
    'span.video-url-fadeable a',
)
# Enquanto o arquivo sobe, o Studio mostra o progresso; quando termina,
# aparece "Verificações concluídas" ou o botao habilita.
SINAIS_PRONTO = (
    '#done-button:not([disabled])',
    'ytcp-button#done-button:not([disabled])',
)


def _primeiro(page, seletores, timeout: float = 5.0):
    """O primeiro seletor que casa, ou None. Nunca levanta."""
    for seletor in seletores:
        try:
            alvo = page.locator(seletor).first
            alvo.wait_for(state="visible", timeout=int(timeout * 1000))
            return alvo
        except Exception:
            continue
    return None


def _sem_acento(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn").lower()


def _teto_da_espera() -> float:
    """Quanto da para esperar sem invadir o proximo horario da grade.

    Derivado da grade, e nao um numero fixo: o buraco mais apertado hoje e
    20:37 -> 21:37, e um teto fixo que caiba ali serve — mas deixa de servir
    no dia em que alguem mexer nos horarios, em silencio. Piso de 30 s para a
    rodada que comeca atrasada: mesmo sem folga, esperar meio minuto e melhor
    que publicar um arquivo que ainda esta subindo.
    """
    try:
        from datetime import datetime, timedelta
        from .. import grade
        agora = datetime.now()
        faltas = []
        for h in grade.HORAS:
            alvo = agora.replace(hour=h, minute=grade.minuto(h), second=0,
                                 microsecond=0)
            if alvo <= agora:
                alvo += timedelta(days=1)
            faltas.append((alvo - agora).total_seconds())
        folga = min(faltas) - 120          # 2 min para a rodada terminar
    except Exception:                                          # noqa: BLE001
        folga = ESPERA_QUALIDADE_S
    return max(PISO_DA_ESPERA_S, min(ESPERA_QUALIDADE_S, folga))


def _nao_publicar_ainda(estagio: dict) -> bool:
    """O estagio em que publicar produz video quebrado.

    `subindo`: o arquivo nao chegou inteiro.
    `processando`: chegou, mas NADA e assistivel ainda ("processando ate SD"
        quer dizer que nem o SD existe).
    `sd`: ja existe video de verdade, que melhora sozinho — um Short em SD na
        primeira hora rende mais que um Short perfeito que nao saiu.
    `hd` e `desconhecida`: publica.
    """
    return estagio.get("qualidade") in ("subindo", "processando")


def _esperar_qualidade(page, passo, laudo: dict, *, canal: str = "builds",
                       limite_s: float | None = None) -> dict:
    """Espera o YouTube terminar de processar antes do clique.

    O botao `#done-button` habilita quando o ARQUIVO TERMINA DE SUBIR, e nao
    quando o YouTube termina de processar. Medido em 16/09/2026: nove
    publicacoes sairam com a barra dizendo "processando" ou "subindo" — o
    video ia ao ar antes de existir nem em SD, justamente na primeira hora,
    que e quando o algoritmo mede o Short. E metade dos "Publicar mesmo
    assim" coincidia com isso.

    `desconhecida` ESPERA como `processando`, e nao publica na hora: "nao
    consegui ler" nao e "pronto". E o mesmo erro do botao habilitado, e o do
    `None` que virava `False`. No estouro do teto ela publica — uma troca de
    layout do Studio nao pode derrubar todas as postagens — mas grava ERRO,
    para a apuracao pegar na primeira vez.
    """
    def ler():
        # LER NUNCA PODE DERRUBAR A POSTAGEM. `_qualidade_agora` ja se protege
        # por dentro, mas esta funcao e o unico caminho de saida da espera:
        # se ela levantar, o video fica no navegador e a rodada perde o
        # horario — trocando um problema de qualidade por um de existencia.
        try:
            return _qualidade_agora(page)
        except Exception:                                      # noqa: BLE001
            return {"qualidade": "desconhecida", "falta": "", "texto": "",
                    "reconhecido": False, "escopo": "nenhum"}

    # O ULTIMO ESTAGIO LEGIVEL VAI PARA A ESPERA E PARA O LAUDO, MAS NAO
    # DECIDE O CLIQUE (05/10/2026). Uma leitura ilegivel no meio da espera (a
    # frase do rodape mudou) nao apaga o que se sabia: o passo e o diario
    # dizem "a ultima legivel foi 'processando'". Mas no ESTOURO do teto quem
    # decide e a leitura de AGORA, e `desconhecida` publica — a regra de
    # 16/09: uma troca de layout do Studio nao pode derrubar todas as
    # postagens. Medido nos ledgers em 05/10: 8 publicacoes estouraram a
    # espera com `desconhecida` no clique depois de comecar num estagio
    # legivel (historias 2 processando + 1 subindo, builds 5 subindo). Se a
    # leitura herdada decidisse, as 8 teriam perdido o YouTube — e a frase
    # que falta em FASES e justamente a que o Studio mostra no fim.
    ultimo_legivel = ""

    def ler_lembrando():
        nonlocal ultimo_legivel
        lido = ler()
        if lido.get("reconhecido") and lido["qualidade"] != "desconhecida":
            ultimo_legivel = lido["qualidade"]
        return lido

    def lembrado(estagio: dict) -> str:
        """O ultimo estagio legivel, so quando a leitura de agora e ilegivel."""
        return ultimo_legivel if estagio["qualidade"] == "desconhecida" else ""

    limite = _teto_da_espera() if limite_s is None else limite_s
    comeco = time.monotonic()
    estagio = ler_lembrando()
    laudo["qualidade_ao_habilitar"] = estagio["qualidade"]
    esperou = 0.0
    # `sd` ENTRA NA ESPERA, mas NAO na guarda: sao perguntas diferentes.
    # "Vale a pena esperar o HD?" — vale, o teto e barato e sai da grade.
    # "Da para publicar assim?" — da, ja existe video de verdade no ar.
    while (estagio["qualidade"] in ("subindo", "processando", "sd",
                                    "desconhecida")
           and esperou < limite):
        passo(f"esperando o processamento ({estagio['qualidade']}"
              + (f"; a ultima legivel foi '{lembrado(estagio)}'"
                 if lembrado(estagio) else "")
              + (f", {estagio['falta']}" if estagio["falta"] else "") + ")...")
        time.sleep(5)
        esperou = time.monotonic() - comeco
        estagio = ler_lembrando()
    laudo["esperou_s"] = round(esperou, 1)
    laudo["qualidade_no_clique"] = estagio["qualidade"]
    laudo["falta_texto"] = estagio["falta"]
    laudo["texto_da_barra"] = estagio["texto"]
    laudo["reconhecido"] = estagio["reconhecido"]
    laudo["escopo"] = estagio["escopo"]
    if lembrado(estagio):
        laudo["ultimo_estagio_legivel"] = lembrado(estagio)
    if esperou >= limite:
        laudo["estourou_a_espera"] = True
        passo(f"o processamento nao terminou em {limite:.0f}s "
              f"(ficou em {estagio['qualidade']}"
              + (f"; a ultima legivel foi '{lembrado(estagio)}'"
                 if lembrado(estagio) else "") + ")")
        if estagio["qualidade"] == "desconhecida":
            # O RODAPE vai no texto (e nao o comeco do dialogo): e a frase que
            # falta em FASES, e so assim alguem a ve.
            try:
                atividade.registrar(
                    "publicacao", atividade.ERRO,
                    f"estagio ILEGIVEL no clique depois de {limite:.0f}s; "
                    "publiquei assim mesmo"
                    + (f" (a ultima leitura legivel foi "
                       f"'{lembrado(estagio)}')"
                       if lembrado(estagio) else "")
                    + f". Rodape: {estagio.get('texto', '')[:200]}",
                    canal, etapa="publicar.youtube.estagio")
            except Exception:                                  # noqa: BLE001
                pass
    return estagio


def _qualidade_agora(page) -> dict:
    """Em que pe o arquivo esta NO INSTANTE do clique em publicar.

    Le a barra de estado contra FASES. Nao decide nada e nao espera: esta
    etapa e so a medida. O `reconhecido` existe porque a ausencia de frase
    de processamento tem DUAS leituras — o Studio terminou, ou o Studio
    mudou o texto e a gente parou de entender a tela. Sem esse campo, o dia
    em que o YouTube trocar as palavras a medicao viraria "hd" para tudo e
    ninguem perceberia.
    """
    vazio = {"qualidade": "desconhecida", "falta": "", "texto": "",
             "reconhecido": False, "escopo": "nenhum"}
    # O ESCOPO E O DIALOGO, nao a pagina. Medido em 16/09/2026: lendo
    # `document.body.innerText` o laudo trazia o menu inteiro do Studio e,
    # pior, a LISTA DE VIDEOS atras do dialogo — que e justamente a dos
    # ultimos enviados. O "10 minutos restantes" gravado podia ser o
    # processamento do video de ONTEM, com um numero plausivel que ninguem
    # questionaria. O rodape com "Envio concluido / processamento vai
    # comecar" fica dentro do dialogo, entao nada do que interessa se perde.
    #
    # E DENTRO DO DIALOGO, SO O RODAPE (05/10/2026). O texto inteiro do
    # dialogo comeca pelo TITULO que nos mesmos escrevemos e pelo estado do
    # rascunho ("salvo como privado", "salvando..."): uma frase de FASES no
    # titulo, ou o "salvando..." do rascunho, classificavam o upload. O
    # rodape vem pelo seletor quando o Studio o expoe; senao, e o trecho em
    # volta da contagem regressiva, que so existe la.
    try:
        lido = page.evaluate(
            "() => {"
            " const d = document.querySelector('ytcp-uploads-dialog');"
            " if (!d) return {dialogo: '', rodape: ''};"
            " const sels = ['ytcp-video-upload-progress',"
            "               '.ytcp-video-upload-progress',"
            "               '[class*=\"upload-progress\"]',"
            "               '.left-button-area', '#dialog-footer'];"
            " let rodape = '';"
            " for (const s of sels) {"
            "   const e = d.querySelector(s);"
            "   if (e && (e.innerText || '').trim()) {"
            "     rodape = e.innerText; break; }"
            " }"
            " return {dialogo: d.innerText || '', rodape: rodape};"
            "}")
    except Exception:
        return vazio
    if isinstance(lido, str):
        # Pagina antiga (ou duble) que devolve so o texto do dialogo.
        lido = {"dialogo": lido, "rodape": ""}
    lido = lido if isinstance(lido, dict) else {}
    texto = _sem_acento(lido.get("dialogo") or "")
    if not texto.strip():
        # Sem dialogo nao ha o que atribuir a ESTE video. Ler a pagina toda
        # aqui seria trocar "nao sei" por um palpite com cara de medida.
        return vazio
    return _classificar_rodape(texto, _sem_acento(lido.get("rodape") or ""))


# Quanto texto guardar em volta da contagem regressiva quando o rodape nao
# vem pelo seletor. O laudo gravava `texto[:200]`, que e so o CABECALHO do
# dialogo (titulo + "salvo como privado" + as abas): nas 13 publicacoes com
# estagio "desconhecida" desde 16/09/2026 (todas com "6 minutos restantes"
# ou "10 minutos restantes") a frase do rodape nunca foi vista.
ANTES_DA_CONTAGEM = 160
DEPOIS_DA_CONTAGEM = 60


def _rodape_pela_contagem(texto: str) -> str:
    """O trecho do dialogo em volta da contagem regressiva, ou `""`."""
    achados = list(FALTA.finditer(texto))
    if not achados:
        return ""
    ultimo = achados[-1]                # o rodape e o fim do dialogo
    comeco = max(0, ultimo.start() - ANTES_DA_CONTAGEM)
    return " ".join(texto[comeco:ultimo.end() + DEPOIS_DA_CONTAGEM].split())


def _classificar_rodape(texto: str, rodape: str = "") -> dict:
    """O estagio, lido SO no rodape do dialogo. Puro, para o teste.

    `texto` e o dialogo inteiro (sem acento); `rodape`, o que o seletor do
    rodape devolveu (pode vir vazio). O laudo grava o rodape, e nao o
    comeco do dialogo: e nele que esta a frase que precisa entrar em FASES.
    """
    rodape = " ".join(str(rodape or "").split())
    janela = _rodape_pela_contagem(texto)
    # O rodape do seletor primeiro; depois o trecho da contagem — que tambem
    # cobre o seletor que pegou o elemento errado (so os botoes, digamos).
    candidatos = [(alvo, escopo) for alvo, escopo in
                  ((rodape, "rodape"), (janela, "contagem")) if alvo]
    achado = FALTA.search(rodape) or FALTA.search(texto)
    falta = achado.group(0) if achado else ""
    for alvo, escopo in candidatos:
        for rotulo, frases in FASES:
            if any(frase in alvo for frase in frases):
                return {"qualidade": rotulo, "falta": falta,
                        "texto": alvo[:240], "reconhecido": True,
                        "escopo": escopo}
    if falta:
        # CONTAGEM REGRESSIVA SEM FRASE CONHECIDA. Medido em 16/09/2026, na
        # primeira noite com esta medicao ligada: a barra dizia "10 minutos
        # restantes" e nenhuma frase de FASES casava, entao o classificador
        # caia em "hd" por omissao e gravava o oposto da verdade. Se o Studio
        # ainda conta o tempo, alguma coisa esta pendente — e a resposta
        # honesta e dizer que nao se sabe o que. O laudo leva o trecho COM a
        # contagem: e nele que esta a frase que falta em FASES.
        alvo, escopo = ((rodape, "rodape") if FALTA.search(rodape)
                        else (janela, "contagem"))
        return {"qualidade": "desconhecida", "falta": falta,
                "texto": alvo[:240], "reconhecido": False, "escopo": escopo}
    if not rodape:
        # Sem rodape pelo seletor e sem contagem: o dialogo inteiro, como era
        # antes — o unico jeito de ver "Envio concluido" nesse caso.
        for rotulo, frases in FASES:
            if any(frase in texto for frase in frases):
                return {"qualidade": rotulo, "falta": "",
                        "texto": " ".join(texto.split())[:240],
                        "reconhecido": True, "escopo": "dialogo"}
    visto = any(_sem_acento(s) in texto for s in SINAIS_PUBLICADO)
    return {"qualidade": "hd", "falta": "",
            "texto": (rodape or " ".join(texto.split()))[:240],
            "reconhecido": visto, "escopo": "rodape" if rodape else "dialogo"}


def _id_do_video(url: str) -> str:
    """O id que o Studio devolveu — a prova que da para conferir depois.

    E o unico campo do laudo que uma API externa consegue desmentir: com ele,
    a conferencia pergunta ao YouTube se aquele video esta mesmo publico. Sem
    ele, "publiquei" continua sendo palavra do proprio publicador contra si
    mesma, que foi como 29 rascunhos passaram por publicados entre 10 e 15 de
    setembro de 2026.
    """
    achado = re.search(
        r"(?:youtu\.be/|[?&]v=|/shorts/|/video/)([\w-]{11})(?![\w-])",
        str(url or ""))
    return achado.group(1) if achado else ""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _conta_ativa(canal: str) -> str:
    """Qual conta de youtube-web esta publicando — nunca levanta."""
    try:
        from ..contas import ativa
        return str(ativa("youtube_web", canal))
    except Exception:
        return ""


LIMITE_DO_SHORT_S = 180.0


def _e_short(video) -> bool:
    """O YouTube vai tratar este video como Short?

    Vertical e com ate 3 min (`LIMITE_DO_SHORT_S`). Sem duracao conhecida, o
    vertical conta como Short: toda parte longa ja e cortada em pedacos de
    ate 180 s (`cortes.py`) antes de subir.
    """
    if not getattr(video, "vertical", False):
        return False
    for nome in ("duracao", "duracao_s"):
        valor = getattr(video, nome, None)
        try:
            if valor is not None and float(valor) > 0:
                return float(valor) <= LIMITE_DO_SHORT_S
        except (TypeError, ValueError):
            continue
    return True


def _abrir(ctx, url: str):
    """A pagina, com novas tentativas (`browser.abrir_pagina`).

    Desde 05/10/2026: um `goto` de 90 s sem segunda chance perdeu o YouTube
    do 23:37 de 04/10 (historias e builds). Na falha final o erro diz que e
    infraestrutura, e a rodada (`postar.main`) tenta o canal de novo dentro
    do mesmo horario.
    """
    try:
        return abrir_pagina(
            ctx, url, log=lambda t: print(f"[youtube-web] {t}", flush=True))
    except AberturaFalhou as exc:
        raise YouTubeWebFalhou(
            f"infraestrutura: a pagina do YouTube nao abriu ({exc})") from exc


def _esperar_montar(page, segundos: float = PACIENCIA_S) -> bool:
    fim = time.time() + segundos
    while time.time() < fim:
        time.sleep(3)
        if montou(page, minimo=120):
            return True
    return False


# -------------------------------------------------------------------- login
def login(*, canal: str = "builds") -> None:
    """Abre a janela para o login manual da conta Google. Uma vez por perfil."""
    perfil = perfil_da_conta(canal)
    with contexto_persistente(headless=False, profile=perfil) as ctx:
        page = _abrir(ctx, URL_STUDIO)
        _esperar_montar(page)
        print(f"[youtube-web] a janela e SUA: entre na conta do canal "
              f"'{canal}' com calma (senha, 2FA, o que aparecer). Ela fica "
              "aberta 15 minutos e nada aqui vai encostar nela.")
        limite = time.time() + 900
        while time.time() < limite:
            time.sleep(5)
            try:
                if page.is_closed():
                    print("[youtube-web] janela fechada por voce.")
                    break
                if "studio.youtube.com/channel" in page.url:
                    print(f"[youtube-web] sessao iniciada ({page.url}).")
                    # Grava QUAL canal ficou selecionado neste perfil: e isso
                    # que faz o perfil significar um canal, e nao so um login.
                    try:
                        import re as _re
                        from .. import contas as _contas
                        achado = _re.search(r"/channel/(UC[\w-]+)", page.url)
                        if achado:
                            nome = _contas.ativa("youtube_web", canal)
                            titulo = ""
                            try:
                                titulo = page.evaluate(
                                    "() => document.title") or ""
                            except Exception:
                                pass
                            _contas.identificar(
                                "youtube_web", nome,
                                rotulo=titulo.replace(" - YouTube Studio", "")
                                             .strip()[:60],
                                identificador=achado.group(1))
                            print(f"[youtube-web] canal deste perfil: "
                                  f"{achado.group(1)}")
                    except Exception as exc:
                        print(f"[youtube-web] nao gravei o id do canal ({exc})")
                    time.sleep(4)
                    break
            except Exception:
                break
    print(f"[youtube-web] perfil de {canal} salvo em {perfil}")


# ------------------------------------------------------------------ sondar
def sondar(*, canal: str = "builds", saida: Path | None = None) -> Path:
    """Despeja o DOM da tela de upload (para ajustar seletor quando quebrar).

    Mesmo espirito do `identity probe`: quando o Studio muda de layout,
    ninguem adivinha o seletor novo — a gente OLHA.
    """
    import json

    saida = saida or (RAIZ / "outputs" / "_identity" /
                      f"probe_youtube_{time.strftime('%Y%m%d_%H%M%S')}.json")
    saida.parent.mkdir(parents=True, exist_ok=True)
    with contexto_persistente(headless=False,
                              profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, url_de_upload(canal))
        _esperar_montar(page)
        time.sleep(6)
        dados = page.evaluate("""() => ({
            url: location.href,
            titulo: document.title,
            arquivos: Array.from(document.querySelectorAll('input[type=file]'))
                .map(i => ({accept: i.accept, oculto: i.offsetParent === null})),
            editaveis: Array.from(
                document.querySelectorAll('[contenteditable=true]'))
                .map(e => ({id: e.id, rotulo: e.getAttribute('aria-label'),
                            texto: (e.innerText || '').slice(0, 40)})),
            botoes: Array.from(document.querySelectorAll('button, ytcp-button'))
                .map(b => ({texto: (b.innerText || '').trim().slice(0, 40),
                            id: b.id, desabilitado: b.hasAttribute('disabled')}))
                .filter(b => b.texto || b.id),
            radios: Array.from(
                document.querySelectorAll('tp-yt-paper-radio-button, [role=radio]'))
                .map(r => ({nome: r.getAttribute('name'),
                            texto: (r.innerText || '').trim().slice(0, 60)})),
        })""")
        saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        print(f"[youtube-web] DOM despejado em {saida}")
        print(f"[youtube-web] {len(dados['arquivos'])} input(s) de arquivo, "
              f"{len(dados['editaveis'])} editavel(is), "
              f"{len(dados['botoes'])} botao(oes), "
              f"{len(dados['radios'])} radio(s)")
    return saida


# ---------------------------------------------------------------- publicar
def _escrever(page, alvo, texto: str, *, rotulo: str = "campo") -> dict:
    """Escreve no campo do Studio e CONFERE. Levanta se o texto nao entrou.

    Era `alvo.type(texto, delay=6)`: uma ida e volta a pagina por letra, e 30 s
    para o texto inteiro. 12 falhas desde 20/09, quase todas durante uma
    partida de LoL — o defeito esta medido em `escrita`. Agora o texto e
    colado (Enter e hashtag continuam tecla), LIDO DE VOLTA, e so se a
    colagem nao pegar cai no tecla a tecla, com o prazo de `escrita` e nao o
    do Playwright.

    Antes nao havia conferencia nenhuma aqui: "o `type` voltou" era tomado
    por "o titulo esta la". A tela da falha fica em `outputs/_publicar/telas/`.
    """
    falha, excecao = "", None
    for colar in (True, False):
        try:
            laudo = escrita.escrever(page, alvo, texto, colar=colar)
        except Exception as erro:                              # noqa: BLE001
            falha, excecao = f"{type(erro).__name__}: {erro}", erro
            continue
        estado = escrita.estado(alvo, texto)
        if estado == "escrita":
            laudo["estado"] = estado
            return laudo
        falha, excecao = estado, None
    tela = escrita.fotografar(page, f"youtube_{rotulo}")
    raise YouTubeWebFalhou(
        f"o {rotulo} nao entrou no campo ({falha[:160]}), colando e tecla a "
        f"tecla." + (f" Tela: {tela}" if tela else "")) from excecao


def _confirmar(page, passo) -> str:
    """Clica o que falta e CONFERE. Nunca devolve promessa.

    O "o que falta" e novo em 15/09/2026 e e o conserto dos rascunhos: o
    Studio abre "Publicar mesmo assim" no instante em que se acha que
    publicou, e ninguem clicava nele. O video ficava parado no aviso ate a
    janela fechar, virava RASCUNHO, e esta funcao devolvia texto de sucesso
    porque a pagina por tras ja dizia "video publicado".
    """
    fim = time.time() + ESPERA_CONFIRMAR_S
    insistiu = False
    while time.time() < fim:
        try:
            texto = _sem_acento(page.evaluate(
                "() => document.body ? document.body.innerText : ''"))
        except Exception:
            texto = ""
        # O AVISO VEM ANTES DA PROVA. Com ele aberto a pagina de tras ja
        # mostra frases de sucesso, e conferir primeiro devolveria "publicado"
        # para um video que vai ficar como rascunho.
        assim = _primeiro(page, BOTAO_PUBLICAR_ASSIM, timeout=1.0)
        if assim is not None:
            try:
                assim.click()
                insistiu = True
                passo('o Studio pediu confirmacao: cliquei em "Publicar '
                      'mesmo assim".')
                time.sleep(2.0)
                continue
            except Exception as exc:
                passo(f"achei 'Publicar mesmo assim' mas nao consegui clicar "
                      f"({type(exc).__name__}).")
                # Os sinais do dialogo atras deste aviso (inclusive o link)
                # nao confirmam nada enquanto ele continua na frente.
                time.sleep(1.0)
                continue
        if any(sinal in texto for sinal in
               (_sem_acento(s) for s in SINAIS_PUBLICADO)):
            link = _primeiro(page, LINK_DO_VIDEO, timeout=3.0)
            if link is not None:
                try:
                    url = link.get_attribute("href")
                    if url:
                        return url
                except Exception:
                    pass
            return SUCESSO + (" (com a confirmacao extra)" if insistiu else "")
        time.sleep(1.5)
    return ("cliquei em publicar, mas o Studio nao mostrou a confirmacao. "
            "A janela ficou aberta: confira em studio.youtube.com se o video "
            "subiu antes de tentar de novo — ele pode ter ficado como "
            "RASCUNHO.")


SUCESSO = "publicado no YouTube"


def confirmado(estado: str) -> bool:
    """O upload foi confirmado? (mesma porta do TikTok)"""
    estado = str(estado or "")
    return estado.startswith(SUCESSO) or estado.startswith("http")


def _agendar(page, quando: str, passo) -> bool:
    """Marca data e hora na etapa de visibilidade. False se nao deu.

    `quando` chega no formato ISO/UTC que a API usava; o Studio pensa no
    fuso do navegador, entao a hora e convertida antes de ser digitada.
    """
    from datetime import datetime

    try:
        alvo = datetime.fromisoformat(str(quando).replace("Z", "+00:00"))
        local = alvo.astimezone()
    except ValueError:
        passo(f"data invalida para agendar: {quando!r}")
        return False

    botao = _primeiro(page, BOTAO_AGENDAR, timeout=15.0)
    if botao is None:
        return False
    botao.click()
    time.sleep(1.5)

    data = _primeiro(page, CAMPO_DATA, timeout=10.0)
    if data is None:
        return False
    data.click()
    page.keyboard.press("Control+A")
    data.type(local.strftime("%d/%m/%Y"), delay=40)
    page.keyboard.press("Enter")
    time.sleep(1.0)

    hora = _primeiro(page, CAMPO_HORA, timeout=8.0)
    if hora is not None:
        hora.click()
        page.keyboard.press("Control+A")
        hora.type(local.strftime("%H:%M"), delay=40)
        page.keyboard.press("Enter")
    passo(f"agendado para {local:%d/%m %H:%M} (horario deste computador).")
    return True


# Quem esta por cima do centro do Criar, e o texto dos dialogos visiveis.
# `elementFromPoint` e a mesma pergunta que o Playwright faz antes de clicar
# ("<x> intercepts pointer events"), feita ANTES, para dar nome a parede.
JS_PAREDE_NO_CRIAR = r"""(seletores) => {
  const vis = e => { const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden'
           && s.display !== 'none'; };
  let criar = null;
  for (const s of seletores) {
    try { criar = document.querySelector(s); } catch (e) { criar = null; }
    if (criar) break;
  }
  let por = '';
  if (criar) {
    const r = criar.getBoundingClientRect();
    const t = document.elementFromPoint(r.left + r.width / 2,
                                        r.top + r.height / 2);
    por = !t ? 'nada' : (criar.contains(t) || t.contains(criar) ? ''
          : t.tagName.toLowerCase() + (t.id ? '#' + t.id : ''));
  }
  const envio = document.querySelector('%s');
  const textos = Array.from(document.querySelectorAll(
      '[role=dialog], [aria-modal=true], tp-yt-paper-dialog'))
    .filter(vis).map(e => (e.innerText || '').trim().replace(/\s+/g, ' '))
    .filter(t => t).map(t => t.slice(0, 160));
  return {criar: !!criar, coberto: !!por && por !== 'nada', por: por,
          envio: !!(envio && vis(envio)), texto: textos.join(' | ').slice(0, 300)};
}""" % DIALOGO_DE_ENVIO


def _parede_no_criar(page) -> dict:
    """O que a tela mostra em volta do Criar. `{}` se nao deu para ler.

    Nunca levanta: e diagnostico, e diagnostico nao derruba o envio.
    """
    try:
        lido = page.evaluate(JS_PAREDE_NO_CRIAR, list(BOTAO_CRIAR))
    except Exception:                                          # noqa: BLE001
        return {}
    return lido if isinstance(lido, dict) else {}


def _abrir_dialogo_de_upload(page, passo, laudo: dict | None = None) -> bool:
    """Garante que a tela tem campo de arquivo. True se conseguiu.

    Caminho curto: a URL ja vem com `?d=ud` e o dialogo abre sozinho.
    Caminho longo: clicar em Criar e depois em "Enviar videos", que e o que
    um humano faz.

    `laudo` (opcional) recebe o que a tela mostrou quando nao deu:
    `dialogo_sem_campo`, `parede` (texto/elemento que cobria o Criar), `tela`
    (foto) e `motivo`. Ver `DIALOGO_DE_ENVIO` para o defeito de 06/10/2026.
    """
    laudo = {} if laudo is None else laudo

    def tem_campo() -> bool:
        try:
            return page.locator(ENTRADA_ARQUIVO).count() > 0
        except Exception:
            return False

    def esperar_campo(segundos: float) -> bool:
        limite = time.time() + segundos
        while time.time() < limite:
            if tem_campo():
                return True
            # Dormir so ate o prazo: sem isto a ultima volta gasta 1 s a toa.
            time.sleep(min(1.0, max(0.0, limite - time.time())))
        return tem_campo()

    if esperar_campo(ESPERA_DIALOGO_S):
        return True

    # O dialogo do Studio veio, mas sem o campo: ele esta carregando. Clicar
    # no Criar agora e impossivel (o backdrop dele cobre o botao).
    if _parede_no_criar(page).get("envio"):
        laudo["dialogo_sem_campo"] = True
        passo("o dialogo de envio abriu sem o campo de arquivo; espero ele "
              "carregar.")
        if esperar_campo(ESPERA_DIALOGO_CARREGANDO_S):
            passo("dialogo de upload aberto.")
            return True

    passo("o dialogo nao abriu sozinho; clicando em Criar -> Enviar videos.")
    criar = _primeiro(page, BOTAO_CRIAR, timeout=20.0)
    if criar is None:
        laudo["motivo"] = "o botao Criar nao esta na tela"
        return False

    # A PAREDE SAI ANTES DO CLIQUE: o texto dela vai ao laudo (sem ele toda
    # parede vira a mesma linha de log), a foto tambem, e o ESC fecha — o
    # dialogo meio carregado do proprio Studio inclusive, que o Criar abre de
    # novo. ESC nunca aceita nada: so dispensa.
    for _ in range(2):
        tela = _parede_no_criar(page)
        if not tela.get("coberto"):
            break
        parede = tela.get("texto") or tela.get("por") or "?"
        laudo["parede"] = parede[:300]
        if not laudo.get("tela"):
            laudo["tela"] = escrita.fotografar(page, "youtube_parede_no_criar")
        passo(f"tem algo por cima do Criar ({tela.get('por')}: "
              f"{parede[:120]}); fechando com ESC.")
        try:
            page.keyboard.press("Escape")
        except Exception:                                      # noqa: BLE001
            break
        time.sleep(1.0)

    try:
        criar.click(timeout=CLIQUE_CRIAR_S * 1000)
    except Exception as exc:                                   # noqa: BLE001
        laudo["motivo"] = (f"o clique no Criar nao passou "
                           f"({type(exc).__name__})")
        if not laudo.get("tela"):
            laudo["tela"] = escrita.fotografar(page, "youtube_criar_sem_clique")
        return False
    time.sleep(2.0)

    enviar = _primeiro(page, MENU_ENVIAR_VIDEOS, timeout=15.0)
    if enviar is None:
        laudo["motivo"] = "o menu do Criar nao mostrou 'Enviar videos'"
        return False
    enviar.click()

    limite = time.time() + ESPERA_DIALOGO_S
    while time.time() < limite:
        if tem_campo():
            passo("dialogo de upload aberto.")
            return True
        time.sleep(min(1.0, max(0.0, limite - time.time())))
    laudo["motivo"] = "cliquei em Criar -> Enviar videos e o campo nao veio"
    return False


def falha_da_montagem(abertura_s: float, tela: str = "") -> str:
    """A frase de "a pagina abriu e ficou em branco". Pura.

    E sempre `infraestrutura:` — a rodada (`postar._e_de_rede`) tenta o canal
    de novo no mesmo horario, e nenhum arquivo foi entregue, entao repetir
    nao duplica nada. Medido em 06/10/2026: as 6 vezes em que esta falha
    aparece no `outputs/postar.txt` cairam em rodadas com erro de rede no
    mesmo minuto (SSLError, `Page.goto: Timeout 90000ms`, 10053). 5 das 6
    foram em historias so porque historias e o PRIMEIRO canal da rodada.

    A frase antiga mandava para "pagina Publicar -> Reparar perfil", um botao
    que nao existe mais em tela nenhuma; e o perfil e o MESMO dos dois canais
    (`.browser_profile/youtube_web`), que publicou builds minutos depois.
    """
    return (f"infraestrutura: a pagina de upload abriu e ficou em branco "
            f"(sem texto depois de {abertura_s:.0f} s). Quase sempre e a rede; "
            f"se acontecer com a rede boa, o cache do perfil pode estar podre "
            f"(`browser.limpar_cache` apaga so o cache e mantem o login)."
            + (f" Tela: {tela}" if tela else ""))


def falha_do_envio(laudo: dict, abertura_s: float) -> str:
    """A frase de "o envio nao abriu", com o que a tela mostrou. Pura.

    `infraestrutura:` so quando ha MEDIDA de que foi a rede: a pagina demorou
    `PAGINA_LENTA_S` ou mais para abrir e montar. Pagina rapida sem o botao,
    com uma parede que o ESC nao tirou, ou com o dialogo do Studio sem o
    campo, e tela mudada — tentar de novo em 60 s nao muda nada, e a frase
    pede o `--sondar`.

    O "dialogo sem campo" ja contou como rede sozinho (c431c6e), e o
    conferente derrubou: na sonda da sessao de verdade (amostra a cada
    0,25 s) o campo nasce JUNTO com o dialogo — nenhuma amostra viu um sem o
    outro. Sem a pagina lenta, nao ha medida de rede atras dele; e se o
    Studio mudar o campo, todo horario viraria "rede", com reposicoes a toa
    e sem a dica do `--sondar`. Ele continua na frase e no laudo.

    Caso medido (06/10/2026, 00:37, historias): ~126 s para abrir e montar,
    campo ausente em 20 s, clique no Criar engolido pelo backdrop do dialogo.
    """
    lento = abertura_s >= PAGINA_LENTA_S
    de_rede = lento
    partes = ["nao consegui abrir o envio de video"]
    if laudo.get("motivo"):
        partes.append(f"({laudo['motivo']})")
    frase = " ".join(partes) + "."
    if lento:
        frase += (f" A pagina levou {abertura_s:.0f} s para abrir (o normal "
                  f"e 8-30 s).")
    if laudo.get("dialogo_sem_campo"):
        frase += " O dialogo de envio do Studio abriu sem o campo de arquivo."
    if laudo.get("parede"):
        frase += f" Na frente do Criar: {laudo['parede'][:160]}."
    if not de_rede:
        frase += (" Rode `python -m builds.publicar.youtube_web --sondar` "
                  "para ver a tela e ajustar BOTAO_CRIAR / MENU_ENVIAR_VIDEOS.")
    if laudo.get("tela"):
        frase += f" Tela: {laudo['tela']}"
    return ("infraestrutura: " + frase) if de_rede else frase


def publicar(video, *, visibilidade: str | None = None,
             postar: bool | None = None, config: dict | None = None,
             canal: str = "builds", agendar_para: str | None = None,
             progresso=None, prova: dict | None = None) -> str:
    """Sobe o video pelo Studio. Devolve a URL, ou o que de fato aconteceu.

    `prova` e um dicionario OPCIONAL preenchido no lugar: quem passa recebe o
    laudo do que aconteceu (id do video, em que resolucao estava no clique,
    se houve confirmacao extra). O retorno e o comportamento nao mudam — os
    chamadores antigos continuam valendo palavra por palavra.
    """
    from . import catalogo

    config = catalogo.carregar_config() if config is None else config
    ajustes = (config.get("youtube") or {})
    visibilidade = (visibilidade or ajustes.get("visibilidade")
                    or "private").lower()
    if visibilidade not in VISIBILIDADE:
        raise YouTubeWebFalhou(
            f"visibilidade desconhecida: {visibilidade!r} "
            f"(use {', '.join(VISIBILIDADE)})")
    if postar is None:
        postar = bool(ajustes.get("postar_automatico", True))

    caminho = Path(video.caminho)
    if not caminho.is_file():
        raise YouTubeWebFalhou(f"arquivo sumiu: {caminho}")

    def passo(texto: str):
        print(f"[youtube-web] {texto}", flush=True)
        if progresso:
            progresso(texto)

    # O laudo nasce PESSIMISTA e e preenchido pelo caminho. Se a funcao
    # estourar no meio, quem passou o dicionario fica com o que deu tempo de
    # medir em vez de ficar sem nada — que era o estado anterior do mundo.
    laudo = prova if prova is not None else {}
    laudo.update({
        "plataforma": "youtube", "canal": canal,
        "conta": _conta_ativa(canal), "estado": "nao_subiu",
        "url": "", "youtube_id": "",
        "qualidade_no_clique": "", "falta_texto": "", "texto_da_barra": "",
        "reconhecido": False, "upload_s": None, "confirmacao_extra": False,
        "quando": _agora(),
    })

    # A Vila mostra o que esta acontecendo lendo o diario, e ate 01/09/2026
    # publicar nao escrevia nada nele. Como o caminho padrao virou o
    # navegador, a fabrica "publicacao" ficava OCIOSA durante quase todo
    # upload de verdade -- so a API, hoje secundaria, reportava. Um painel
    # que mostra "parado" enquanto se publica e pior do que nao ter painel.
    # Ver o mesmo comentario em `tiktok.publicar`: sem `etapa`, o
    # /confiabilidade conta os dois destinos como uma coisa so, e uma excecao
    # crua chega la sem dizer de que passo veio.
    with atividade.fabrica("publicacao", f"YouTube: {caminho.name}",
                           canal=canal, etapa="publicar.youtube",
                           ref=getattr(video, "id", "")), \
            contexto_persistente(headless=False,
                                 profile=perfil_da_conta(canal)) as ctx:
        comeco_da_abertura = time.monotonic()
        page = _abrir(ctx, url_de_upload(canal))
        montada = _esperar_montar(page)
        abertura_s = time.monotonic() - comeco_da_abertura
        laudo["abertura_s"] = round(abertura_s, 1)
        if not montada:
            raise YouTubeWebFalhou(falha_da_montagem(
                abertura_s, escrita.fotografar(page, "youtube_em_branco")))
        if "accounts.google" in page.url or "signin" in page.url:
            raise YouTubeWebFalhou(
                "o Google pediu login. Rode uma vez: "
                "`python -m builds.publicar.youtube_web --login`")

        # ONDE ISTO VAI PARAR. Com varios canais na mesma conta Google, o
        # Studio abre no ultimo usado quando a URL nao manda — e um video de
        # historias no canal de builds e IRREVERSIVEL. Entao confere-se o id
        # que a pagina realmente carregou contra o que foi pedido.
        from .. import contas as _contas
        esperado = (_contas.identidade(
            "youtube_web", _contas.ativa("youtube_web", canal)).get("id") or "")
        atual = id_do_canal(page.url)
        if esperado and atual and atual != esperado:
            raise YouTubeWebFalhou(
                f"PAREI: pedi o canal {esperado} e o Studio abriu {atual}. "
                f"Subir aqui mandaria o video de '{canal}' para o canal "
                "errado, e isso nao tem desfazer. Escolha o canal na pagina "
                "Publicar (botao 'Canais do YouTube') e tente de novo.")
        if not esperado:
            passo(f"ATENCAO: o canal '{canal}' nao tem id gravado; vai para "
                  f"onde o Studio abrir ({atual or 'desconhecido'}).")

        # A pagina do canal so mostra a LISTA de videos: o campo de arquivo
        # vem do `?d=ud` ou de Criar -> Enviar videos.
        envio = {}
        if not _abrir_dialogo_de_upload(page, passo, envio):
            laudo["envio_nao_abriu"] = {
                k: envio[k] for k in ("motivo", "parede", "tela",
                                      "dialogo_sem_campo") if envio.get(k)}
            raise YouTubeWebFalhou(falha_do_envio(envio, abertura_s))

        entrada = None
        limite = time.time() + ESPERA_PAGINA_S
        while time.time() < limite and entrada is None:
            try:
                candidato = page.locator(ENTRADA_ARQUIVO).first
                if candidato.count():
                    entrada = candidato
                    break
            except Exception:
                pass
            time.sleep(1.0)
        if entrada is None:
            raise YouTubeWebFalhou(
                "nao achei o campo de arquivo. Rode "
                "`python -m builds.publicar.youtube_web --sondar` para ver a tela.")

        entrada.set_input_files(str(caminho))
        comeco_do_upload = time.monotonic()
        passo(f"arquivo entregue ({caminho.name}); o YouTube esta subindo...")

        # A COTA SE PERGUNTA AQUI, logo depois do envio. Medido em 10/09/2026:
        # detectando so no fim, a rodada escrevia titulo, escrevia descricao,
        # falhava no botao de "feito para criancas", nao achava o "Proximo",
        # nao achava o "public" — cinco sintomas confusos para uma causa que
        # ja estava escrita na tela desde o primeiro segundo. E pior: deixava
        # um rascunho meio preenchido no canal.
        aviso = _bateu_o_limite(page)
        if aviso:
            raise LimiteDiarioDoYouTube(aviso)

        titulo = _primeiro(page, CAMPO_TITULO, timeout=60.0)
        if titulo is None:
            raise YouTubeWebFalhou(
                "a tela de detalhes nao apareceu (o upload nao comecou?).")
        # O MODO VAI PARA O LAUDO (e dele para o ledger): "digitado" quer
        # dizer que a colagem nao pegou no Studio e o tecla a tecla assumiu.
        # E a unica forma de saber, depois, se o Studio mudou o campo.
        laudo["escrita"] = {}
        laudo["escrita"]["titulo"] = _escrever(
            page, titulo, video.titulo[:100], rotulo="titulo")["modo"]
        passo(f"titulo escrito ({laudo['escrita']['titulo']}).")

        descricao = _primeiro(page, CAMPO_DESCRICAO, timeout=15.0)
        if descricao is not None:
            laudo["escrita"]["descricao"] = _escrever(
                page, descricao, video.descricao_completa[:4900],
                rotulo="descricao")["modo"]
            passo(f"descricao escrita ({laudo['escrita']['descricao']}).")

        capa = getattr(video, "capa", None)
        if capa and Path(capa).is_file() and _e_short(video):
            # SHORT NAO TEM CAMPO DE MINIATURA no envio do Studio: a procura
            # gastava 8 s por video e terminava sempre em "campo de miniatura
            # nao apareceu" (05/10/2026). A capa de Short, quando o canal
            # permite, vai pela API depois (`youtube.definir_capa`).
            passo("Short: o Studio nao tem campo de miniatura no envio; a "
                  "capa vai pela API depois, se o canal permitir.")
        elif capa and Path(capa).is_file():
            try:
                entrada_capa = _primeiro(page, ENTRADA_MINIATURA, timeout=8.0)
                if entrada_capa is None:
                    passo("campo de miniatura nao apareceu; capa fica de fora.")
                else:
                    entrada_capa.set_input_files(str(capa))
                    passo(f"capa entregue ({Path(capa).name}).")
            except Exception as erro:
                # Enfeite: o video ja esta subindo e nao pode cair por isto.
                passo(f"capa falhou ({type(erro).__name__}); seguindo sem ela.")

        # O campo obrigatorio. Sem ele, "Publicar" nunca habilita.
        criancas = _primeiro(page, NAO_E_PARA_CRIANCAS, timeout=15.0)
        if criancas is None:
            passo("AVISO: nao achei a pergunta 'feito para criancas'. Se o "
                  "botao de publicar nao habilitar, e por isso.")
        else:
            try:
                # Se o elemento nao fica clicavel em 10 s (overlay, outro
                # dialogo, ou elemento desabilitado), falha rapido em vez de
                # esperar os 30 s do timeout padrao do Playwright. Melhor
                # falhar rapido e deixar a janela aberta (usuario ve e
                # conserta) do que travar por 30 s esperando algo que nunca
                # vira clicavel.
                criancas.click(timeout=10000)
                passo("marcado: nao e conteudo para criancas.")
            except Exception as exc:
                passo(f"AVISO: nao consegui clicar em 'feito para criancas' "
                      f"({type(exc).__name__}: {str(exc)[:60]}). A janela "
                      f"esta aberta — confira se ha um dialogo cobrindo e "
                      f"feche-o se for o caso.")

        # O assistente: detalhes -> elementos -> verificacoes -> visibilidade
        for etapa in range(3):
            proximo = _primeiro(page, BOTAO_PROXIMO, timeout=20.0)
            if proximo is None:
                passo(f"nao achei o botao Proximo na etapa {etapa + 1}.")
                break
            proximo.click()
            time.sleep(2.5)
        passo("cheguei na visibilidade.")

        if agendar_para:
            if not _agendar(page, agendar_para, passo):
                raise YouTubeWebFalhou(
                    f"nao consegui AGENDAR para {agendar_para} no Studio. "
                    "Publicar agora no lugar disso soltaria as partes todas "
                    "no mesmo minuto, entao parei aqui — a janela esta "
                    "aberta para voce terminar na mao. Rode "
                    "`python -m builds.publicar.youtube_web --sondar` para eu "
                    "ajustar os seletores da tela de agendamento.")
        else:
            escolha = _primeiro(page, VISIBILIDADE[visibilidade], timeout=20.0)
            if escolha is None:
                passo(f"nao achei a opcao '{visibilidade}'; o video fica como "
                      "o Studio deixou.")
            else:
                escolha.click()
                passo(f"visibilidade: {visibilidade}.")

        if not postar:
            passo("PARANDO antes de publicar — confira e clique em Publicar. "
                  "A janela fica aberta por 5 minutos.")
            time.sleep(300)
            return ("video carregado e preenchido; a publicacao final ficou "
                    "com voce")

        # O botao so habilita quando o arquivo termina de subir.
        pronto = None
        limite = time.time() + ESPERA_UPLOAD_S
        aviso_do_upload = _AvisoDoUpload(passo, time.time())
        while time.time() < limite and pronto is None:
            pronto = _primeiro(page, SINAIS_PRONTO, timeout=3.0)
            if pronto is not None:
                break
            aviso_do_upload.talvez(time.time())
            # A COTA SE DESCOBRE AQUI, e nao depois de 15 min de espera: o
            # aviso ja esta na tela e nenhum botao vai habilitar. Perguntar
            # antes de dormir e a diferenca entre saber em 3 s e saber em 900.
            aviso = _bateu_o_limite(page)
            if aviso:
                raise LimiteDiarioDoYouTube(aviso)
            time.sleep(5)
        if pronto is None:
            aviso = _bateu_o_limite(page)
            if aviso:
                raise LimiteDiarioDoYouTube(aviso)
            raise YouTubeWebFalhou(
                "o YouTube nao terminou de processar o video a tempo. A "
                "janela esta aberta: da para terminar na mao.")

        # A ESPERA VAI AQUI, no ultimo instante antes do clique. O botao acima
        # habilita quando o ARQUIVO TERMINA DE SUBIR, e nao quando o YouTube
        # termina de processar — medido em 15/09/2026, a barra ainda dizia
        # "Processando ate SD ... 3 minutos restantes" neste ponto. Desde
        # 16/09 isso era so MEDIDO, e a medida mostrou nove publicacoes assim.
        # Agora segura o clique.
        laudo["upload_s"] = round(time.monotonic() - comeco_do_upload, 1)
        try:
            estagio = _esperar_qualidade(page, passo, laudo, canal=canal)
        except Exception as erro:                              # noqa: BLE001
            # FALHA DA ESPERA NAO PODE VIRAR FALHA DA POSTAGEM. A espera e um
            # ganho de qualidade; ficar sem video e o pior desfecho. Se ela
            # quebrar, publica-se como antes de existir — com ERRO no diario,
            # porque quebrar aqui e defeito e nao rotina.
            laudo["espera_quebrou"] = str(erro)[:200]
            passo(f"a espera pelo processamento falhou ({erro}); publicando")
            try:
                atividade.registrar(
                    "publicacao", atividade.ERRO,
                    f"a espera pelo processamento quebrou: {str(erro)[:160]}",
                    canal, etapa="publicar.youtube.estagio")
            except Exception:                                  # noqa: BLE001
                pass
            estagio = {"qualidade": "desconhecida", "falta": "", "texto": "",
                       "reconhecido": False, "escopo": "nenhum"}
        if _nao_publicar_ainda(estagio):
            # NAO PUBLICA PELA METADE. Em `subindo` o arquivo nao chegou
            # inteiro; em `processando` nada e assistivel ainda. Publicar
            # nestes dois da o rascunho quebrado — e o video volta a fila
            # inteiro, sai depois certo, e nada se perde alem de um horario.
            raise YouTubeWebFalhou(
                f"o video ainda estava em '{estagio['qualidade']}' depois de "
                f"esperar {laudo.get('esperou_s')}s"
                + (f" ({estagio['falta']})" if estagio["falta"] else "")
                + ". Nao publiquei: sairia quebrado. A janela segue aberta.")

        # A PROVA DO CLIQUE, como no TikTok (`tiktok.publicar`): gravada no
        # `laudo` — que e o `prova` de quem chamou — ANTES de o clique sair,
        # para sobreviver a qualquer excecao daqui para baixo. Ate 11/10/2026
        # o YouTube nao gravava: uma excecao depois do clique (a marca "a
        # conferir" sem trava, `progresso` levantando) apagava a frase, a
        # ficha virava "falha comum" e o video era reescolhido no horario
        # seguinte — rascunho gemeo ou duplicata. Antes do clique, e nao
        # depois: um `click()` que estoura o prazo pode ter despachado o
        # clique, e repetir e pior que nao postar (17/09).
        laudo["clicou"] = True
        pronto.click()
        return _depois_do_clique(page, passo, laudo, canal, video)


def _depois_do_clique(page, passo, laudo: dict, canal: str, video) -> str:
    """Tudo o que vem depois de `pronto.click()`: confirmar, preencher o
    laudo e resolver o desfecho.

    Se algo levantar AQUI, o clique ja saiu e o video pode estar no ar: ele
    vai para a lista "a conferir" do YouTube (pelo `laudo["clicou"]`,
    `desfecho.classificar` diz `sem_confirmacao`) antes de a excecao subir.
    Em 05/10/2026 foi o `progresso` levantando depois do clique; sem isto a
    fila reescolhia o video no horario seguinte.
    """
    from . import desfecho as _desf
    try:
        passo("publicar clicado; confirmando...")
        estado = _confirmar(page, passo)
        passo(estado)

        laudo["confirmacao_extra"] = "confirmacao extra" in estado
        if estado.startswith("http"):
            laudo["estado"] = "publicado"
            laudo["url"] = estado
            laudo["youtube_id"] = _id_do_video(estado)
        elif estado.startswith(SUCESSO):
            laudo["estado"] = "publicado"
        else:
            laudo["estado"] = "sem_confirmacao"
        if not laudo.get("youtube_id"):
            # SEGUNDA FONTE PARA O ID. Medido em 16/09/2026: em 3 das 4
            # publicacoes da noite o Studio confirmou o sucesso mas nao
            # renderizou o elemento de link, e a publicacao ficava sem a
            # unica prova que uma API externa consegue desmentir. A propria
            # URL da pagina costuma carregar o id.
            try:
                laudo["youtube_id"] = _id_do_video(page.url)
            except Exception:
                pass
    except Exception as exc:                                   # noqa: BLE001
        laudo["estado"] = "sem_confirmacao"
        try:
            _desf.resolver(
                canal, video,
                f"cliquei em publicar no YouTube e algo falhou depois "
                f"({type(exc).__name__}): o video pode estar no ar como "
                f"publicado ou RASCUNHO — confira em studio.youtube.com.",
                laudo, plataforma="youtube")
        except Exception:                                      # noqa: BLE001
            # `marcar_para_conferir` ja avisou no diario; a excecao que sobe
            # e a original, que diz o que quebrou.
            pass
        raise
    # A MESMA GUARDA DO TIKTOK, e ela faltava aqui — onde o estrago era
    # MAIOR. Sem confirmacao, o video nao ganha linha no ledger; como a
    # fila escolhe pelo que ainda nao foi registrado, ele voltava no
    # horario seguinte e subia DE NOVO. Cada tentativa deixava um
    # rascunho: e a fabrica de rascunhos gemeos que explica os 22 do
    # canal. No TikTok o video so saia da fila; aqui ele reenviava.
    laudo["desfecho"] = _desf.resolver(canal, video, estado, laudo,
                                       plataforma="youtube")
    return estado


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="youtube_web",
        description="publicar no YouTube pelo navegador (quando a API recusa)")
    parser.add_argument("--login", action="store_true",
                        help="abre a janela para o login manual do Google")
    parser.add_argument("--sondar", action="store_true",
                        help="despeja o DOM da tela de upload")
    parser.add_argument("--canais", action="store_true",
                        help="lista os canais que este login enxerga")
    parser.add_argument("--usar-canal", dest="usar_canal", default="",
                        help="amarra um canal do YouTube (id, @arroba ou "
                             "nome) ao canal do projeto passado em --canal")
    parser.add_argument("--canal", default="builds",
                        help="qual canal (builds, historias, geral)")
    args = parser.parse_args(argv)

    if args.login:
        login(canal=args.canal)
        return 0
    if args.sondar:
        sondar(canal=args.canal)
        return 0
    if args.canais or args.usar_canal:
        from .. import contas

        achados = canais_da_sessao(args.canal)
        if not achados:
            print("[youtube-web] nenhum canal encontrado. Sem login? Rode "
                  "`python -m builds.publicar.youtube_web --login`")
            return 1

        # Cadastrar (sem escolher) deixa os canais aparecerem no combo do
        # painel. Escolher e outra coisa, e continua sendo decisao do dono.
        for item in achados:
            nome = contas.adicionar("youtube_web", item["nome"])
            contas.identificar("youtube_web", nome, rotulo=item["nome"],
                               identificador=item["id"],
                               extra={"arroba": item.get("arroba", "")})

        # Cadastrar (sem escolher) deixa os canais aparecerem no combo do
        # painel. Escolher e outra coisa, e continua sendo decisao do dono.
        for item in achados:
            nome = contas.adicionar("youtube_web", item["nome"])
            contas.identificar("youtube_web", nome, rotulo=item["nome"],
                               identificador=item["id"],
                               extra={"arroba": item.get("arroba", "")})

        if not args.usar_canal:
            print(f"Canais que este login enxerga ({len(achados)}):")
            for item in achados:
                marca = ""
                for projeto in ("builds", "historias"):
                    quem = contas.identidade(
                        "youtube_web", contas.ativa("youtube_web", projeto))
                    if quem.get("id") == item["id"]:
                        marca += f"  <- {projeto}"
                print(f"  {item['id']}  @{item['arroba']:24} "
                      f"{item['nome']}{marca}")
            print()
            print("Para escolher:  python -m builds.publicar.youtube_web "
                  "--usar-canal @arroba --canal historias")
            return 0

        alvo = args.usar_canal.strip().lstrip("@").lower()
        escolha = next(
            (i for i in achados
             if alvo in (i["id"].lower(), i["arroba"].lower(),
                         i["nome"].lower())), None)
        if escolha is None:
            print(f"[youtube-web] nao achei {args.usar_canal!r} entre: "
                  + ", ".join(f"@{i['arroba']}" for i in achados))
            return 1
        registro = usar_canal(args.canal, escolha)
        print(f"[youtube-web] '{args.canal}' agora publica em "
              f"{escolha['nome']} (@{escolha['arroba']}, {registro['id']}).")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
