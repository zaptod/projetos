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
from pathlib import Path

from .. import atividade
from ..identity.browser import contexto_persistente, montou, pagina

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
                page.goto(f"https://www.youtube.com/@{item['arroba']}",
                          wait_until="domcontentloaded", timeout=60_000)
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


def _abrir(ctx, url: str):
    page = pagina(ctx)
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    return page


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
def _escrever(page, alvo, texto: str) -> None:
    """Campo do Studio e contenteditable: `fill` nao funciona."""
    alvo.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    alvo.type(texto, delay=6)


def _confirmar(page, passo) -> str:
    """Clica o que falta e CONFERE. Nunca devolve promessa."""
    fim = time.time() + ESPERA_CONFIRMAR_S
    while time.time() < fim:
        try:
            texto = _sem_acento(page.evaluate(
                "() => document.body ? document.body.innerText : ''"))
        except Exception:
            texto = ""
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
            return SUCESSO
        time.sleep(3)
    return ("cliquei em publicar, mas o Studio nao mostrou a confirmacao. "
            "A janela ficou aberta: confira em studio.youtube.com se o video "
            "subiu antes de tentar de novo.")


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


def _abrir_dialogo_de_upload(page, passo) -> bool:
    """Garante que a tela tem campo de arquivo. True se conseguiu.

    Caminho curto: a URL ja vem com `?d=ud` e o dialogo abre sozinho.
    Caminho longo: clicar em Criar e depois em "Enviar videos", que e o que
    um humano faz.
    """
    def tem_campo() -> bool:
        try:
            return page.locator(ENTRADA_ARQUIVO).count() > 0
        except Exception:
            return False

    limite = time.time() + ESPERA_DIALOGO_S
    while time.time() < limite:
        if tem_campo():
            return True
        # Dormir so ate o prazo: sem isto a ultima volta gasta 1 s a toa.
        time.sleep(min(1.0, max(0.0, limite - time.time())))

    passo("o dialogo nao abriu sozinho; clicando em Criar -> Enviar videos.")
    criar = _primeiro(page, BOTAO_CRIAR, timeout=20.0)
    if criar is None:
        return False
    criar.click()
    time.sleep(2.0)

    enviar = _primeiro(page, MENU_ENVIAR_VIDEOS, timeout=15.0)
    if enviar is None:
        return False
    enviar.click()

    limite = time.time() + ESPERA_DIALOGO_S
    while time.time() < limite:
        if tem_campo():
            passo("dialogo de upload aberto.")
            return True
        time.sleep(min(1.0, max(0.0, limite - time.time())))
    return False


def publicar(video, *, visibilidade: str | None = None,
             postar: bool | None = None, config: dict | None = None,
             canal: str = "builds", agendar_para: str | None = None,
             progresso=None) -> str:
    """Sobe o video pelo Studio. Devolve a URL, ou o que de fato aconteceu."""
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

    # A Vila mostra o que esta acontecendo lendo o diario, e ate 01/09/2026
    # publicar nao escrevia nada nele. Como o caminho padrao virou o
    # navegador, a fabrica "publicacao" ficava OCIOSA durante quase todo
    # upload de verdade -- so a API, hoje secundaria, reportava. Um painel
    # que mostra "parado" enquanto se publica e pior do que nao ter painel.
    with atividade.fabrica("publicacao", f"YouTube: {caminho.name}",
                           canal=canal), \
            contexto_persistente(headless=False,
                                 profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, url_de_upload(canal))
        if not _esperar_montar(page):
            raise YouTubeWebFalhou(
                "a pagina de upload nao carregou. Se ela abrir em branco "
                "sempre, o perfil pode estar degradado: pagina Publicar -> "
                "Reparar perfil.")
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

        if not _abrir_dialogo_de_upload(page, passo):
            raise YouTubeWebFalhou(
                "nao consegui abrir o envio de video. A pagina do canal so "
                "mostra a LISTA de videos: o campo de arquivo aparece depois "
                "de Criar -> Enviar videos, e nenhum dos dois botoes "
                "respondeu. Rode `python -m builds.publicar.youtube_web "
                "--sondar` para ver a tela e ajustar BOTAO_CRIAR / "
                "MENU_ENVIAR_VIDEOS.")

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
        _escrever(page, titulo, video.titulo[:100])
        passo("titulo escrito.")

        descricao = _primeiro(page, CAMPO_DESCRICAO, timeout=15.0)
        if descricao is not None:
            _escrever(page, descricao, video.descricao_completa[:4900])
            passo("descricao escrita.")

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
        while time.time() < limite and pronto is None:
            pronto = _primeiro(page, SINAIS_PRONTO, timeout=3.0)
            if pronto is not None:
                break
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

        pronto.click()
        passo("publicar clicado; confirmando...")
        estado = _confirmar(page, passo)
        passo(estado)
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
