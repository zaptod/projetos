# -*- coding: utf-8 -*-
"""Publicar no TikTok por automação de navegador (patchright).

Diferente do YouTube, aqui NÃO existe caminho oficial disponível: a Content
Posting API do TikTok exige app aprovado em review. Sobra o navegador — o
mesmo padrão que o projeto já usa no PicassoIA e no Digen: Chrome de verdade,
perfil persistente (login feito UMA vez, na mão) e nenhum truque de stealth
além do que `identity/browser.py` já faz.

Duas consequências que valem estar escritas:

  1. É automação da SUA conta, no site deles, e pode quebrar quando o TikTok
     mudar a tela. Por isso o `sondar()`: ele despeja o DOM da página de
     upload para ajustar os seletores, como o `identity probe` faz.
  2. Por padrão a ferramenta NÃO clica em "Publicar". Ela sobe o arquivo,
     escreve a legenda e PARA com a janela aberta — publicar é irreversível e
     a última palavra é sua. `postar_automatico: true` no config muda isso.
"""
from __future__ import annotations

import time
from pathlib import Path

from .. import atividade
from ..identity.browser import contexto_persistente, pagina

RAIZ = Path(__file__).resolve().parents[2]
PERFIL = RAIZ / ".browser_profile" / "tiktok"

# Quanto esperar a tela de login montar antes de acusar o perfil de
# degradado. A home do TikTok e pesada: com 6 s a checagem acusava
# pagina que so estava lenta (medido em 31/08/2026).
PACIENCIA_LOGIN_S = 40


def perfil_da_conta(canal: str = "builds"):
    """A pasta de Chrome da conta de TikTok ATIVA naquele canal.

    Existe porque os canais deixaram de compartilhar conta: publicar a
    historia no perfil do canal de builds e irreversivel.
    """
    try:
        from ..contas import perfil
        return perfil("tiktok", canal)
    except Exception:
        return PERFIL
URL_UPLOAD = "https://www.tiktok.com/tiktokstudio/upload"

# Espera o input de arquivo aparecer (a página é uma SPA pesada).
ESPERA_PAGINA_S = 60.0
# Depois de entregar o arquivo, o TikTok processa e só então habilita a
# legenda e o botão. Sem confirmação visual não dá para dizer que subiu.
ESPERA_PROCESSAR_S = 300.0

ENTRADA_ARQUIVO = 'input[type="file"]'
# A legenda é um contenteditable (não textarea). Os candidatos vão do mais
# específico ao mais genérico — o primeiro que existir na tela vale.
CAMPO_LEGENDA = (
    'div[contenteditable="true"][role="combobox"]',
    'div[contenteditable="true"]',
    '[data-e2e="caption-input"]',
)
BOTAO_POSTAR = (
    'button[data-e2e="post_video_button"]',
    'button:has-text("Publicar")',
    'button:has-text("Post")',
)
# A SEGUNDA confirmação. O TikTok abre um modal "Publicar agora" quando o
# fluxo vai rápido demais (relatado pelo Adrian em 31/08/2026, com o DOM:
# `<div class="TUXButton-label">Publicar agora</div>`). Sem clicar aqui, o
# vídeo NÃO sobe — e a automação achava que tinha publicado.
#
# O rótulo é um `div` DENTRO do botão (design system TUX), então o seletor
# precisa pegar o botão ancestral; clicar no rótulo também funciona porque o
# clique sobe, e por isso os dois estão na lista.
BOTAO_CONFIRMAR = (
    '[data-e2e="post_video_confirm"]',
    'button:has-text("Publicar agora")',
    'button:has-text("Post now")',
    'div.TUXButton-label:has-text("Publicar agora")',
    'div.TUXButton-label:has-text("Post now")',
)

# O que prova que o vídeo foi mesmo publicado. Nenhum destes é garantido
# sozinho, por isso são vários — e por isso, quando NENHUM aparece, a função
# diz que não conseguiu confirmar em vez de inventar sucesso.
SINAIS_DE_SUCESSO = (
    "seu video esta sendo enviado", "seu video foi publicado",
    "video publicado", "publicado com sucesso",
    "gerenciar publicacoes", "gerenciar posts", "seus videos",
    "your video is being uploaded", "your video has been posted",
    "video published", "posted successfully",
    "manage your posts", "your videos", "view profile", "ver perfil",
)
ESPERA_CONFIRMAR_S = 90.0

# Toda frase de sucesso comeca com isto, e `confirmado()` e como quem chama
# pergunta. Sem um marcador, o chamador teria que adivinhar pelo texto — e
# `serie.py` registrava como publicado QUALQUER coisa que voltasse, inclusive
# um "nao consegui confirmar".
SUCESSO = "publicado no TikTok"


def confirmado(estado: str) -> bool:
    """O TikTok confirmou a publicacao? (a unica pergunta que vale)"""
    return str(estado or "").startswith(SUCESSO)


# A ÚNICA prova de que dá para postar: o botão existe E está habilitado.
#
# Isto já foi uma lista de três, com `div[class*="preview"] video` e `video`
# junto — e `_primeiro` devolve o primeiro que casar. O `<video>` do preview
# nasce assim que o arquivo chega, muito antes de o TikTok terminar de
# processar, então a espera de 300 s saía em poucos segundos e o clique caía
# num botão ainda desabilitado. O Playwright então esperava ele habilitar
# com o timeout PADRÃO (30 s) e estourava.
#
# Medido em 11/09/2026, 12:09: `duelo_00001` subiu no YouTube e ficou fora do
# TikTok exatamente assim, com 300 s de orçamento intactos e um erro que
# dizia "Timeout 30000ms" — o número que não era de ninguém.
PROVA_DE_PRONTO = 'button[data-e2e="post_video_button"]:not([disabled])'
# Estes dizem só que o arquivo CHEGOU. Servem para não desistir calado
# quando o TikTok troca o `data-e2e` do botão, e para nada mais.
SINAIS_DE_PROGRESSO = (
    'div[class*="preview"] video',
    'video',
)
# Quanto esperar o botão habilitar no momento do clique. O padrão do
# Playwright são 30 s, e o processamento do TikTok passa disso com folga.
ESPERA_HABILITAR_S = 120.0


class TikTokFalhou(RuntimeError):
    """Erro legível — o painel mostra a frase, não o traceback."""


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


def _publicou(page, url_antes: str) -> bool:
    """Ha PROVA de que o video foi publicado? (nunca 'provavelmente')"""
    try:
        url = page.url
        if url != url_antes and "/upload" not in url:
            return True
        texto = _sem_acento(page.evaluate(
            "() => document.body ? document.body.innerText : ''"))
    except Exception:
        return False
    return any(sinal in texto for sinal in SINAIS_DE_SUCESSO)


def _confirmar_publicacao(page, passo, espera: float = ESPERA_CONFIRMAR_S) -> str:
    """Clica "Publicar agora" se o modal aparecer, e so entao confere.

    Antes daqui a funcao dormia 15 s e devolvia "publicado no TikTok" sem
    olhar a tela — uma promessa, nao um fato. Com o modal aberto, o video
    ficava parado e o painel dizia que tinha subido.
    """
    url_antes = page.url
    confirmou = False
    fim = time.time() + espera
    while time.time() < fim:
        # A prova vem ANTES da cacada ao modal: `_primeiro` gasta ate 1 s por
        # seletor e, no fluxo normal (sem modal), isso atrasaria em varios
        # segundos o reconhecimento de um sucesso que ja esta na tela.
        if _publicou(page, url_antes):
            return (SUCESSO
                    + (" (com a confirmacao extra)" if confirmou else ""))
        if not confirmou:
            botao = _primeiro(page, BOTAO_CONFIRMAR, timeout=1.0)
            if botao is not None:
                try:
                    botao.click()
                    confirmou = True
                    passo('o TikTok pediu confirmacao: cliquei em "Publicar '
                          'agora".')
                    time.sleep(2.0)
                    continue
                except Exception as exc:
                    passo(f"achei a confirmacao mas nao consegui clicar "
                          f"({type(exc).__name__}).")
        time.sleep(1.5)

    if confirmou:
        return ("cliquei em publicar e na confirmacao, mas o TikTok nao "
                "mostrou o aviso de sucesso. Confira o perfil antes de "
                "publicar de novo.")
    return ("cliquei em publicar, mas o TikTok nao confirmou. A janela ficou "
            "aberta: confira se o video subiu.")


def _abrir(ctx, url: str):
    page = pagina(ctx)
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    return page


def sondar(*, canal: str = "builds", saida: Path | None = None) -> Path:
    """Despeja o DOM da tela de upload (para ajustar seletor quando quebrar).

    Mesmo espírito do `identity probe`: quando o site muda, ninguém adivinha
    o seletor novo — a gente OLHA.
    """
    import json

    saida = saida or (RAIZ / "outputs" / "_identity" /
                      f"probe_tiktok_{time.strftime('%Y%m%d_%H%M%S')}.json")
    saida.parent.mkdir(parents=True, exist_ok=True)
    with contexto_persistente(headless=False, profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, URL_UPLOAD)
        time.sleep(8)
        dados = page.evaluate("""() => ({
            url: location.href,
            titulo: document.title,
            arquivos: Array.from(document.querySelectorAll('input[type=file]'))
                .map(i => ({accept: i.accept, oculto: i.offsetParent === null})),
            editaveis: Array.from(document.querySelectorAll('[contenteditable=true]'))
                .map(e => ({role: e.getAttribute('role'),
                            e2e: e.getAttribute('data-e2e'),
                            texto: (e.innerText || '').slice(0, 40)})),
            botoes: Array.from(document.querySelectorAll('button'))
                .map(b => ({texto: (b.innerText || '').trim().slice(0, 40),
                            e2e: b.getAttribute('data-e2e'),
                            desabilitado: b.disabled}))
                .filter(b => b.texto || b.e2e),
        })""")
        saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        print(f"[tiktok] DOM despejado em {saida}")
        print(f"[tiktok] {len(dados['arquivos'])} input(s) de arquivo, "
              f"{len(dados['editaveis'])} editável(is), "
              f"{len(dados['botoes'])} botão(ões)")
    return saida


def login(*, canal: str = "builds", limpar: bool = False) -> None:
    """Abre a janela para o login manual, e CONSERTA o perfil se preciso.

    Duas coisas que faltavam e custaram uma tarde (31/08/2026):

    1. Se a sessao ja existe, a URL de login redireciona para o feed — a janela
       parecia travada quando na verdade nao havia nada a fazer. Agora isso
       e dito em voz alta.
    2. Um perfil velho de automacao acumula cache e service worker quebrados
       e o TikTok abre BRANCO (so o esqueleto cinza, zero texto). Nao parece
       cache, parece bloqueio. Quando a pagina nao monta, o cache e limpo
       (sem tocar no login) e a janela recarrega sozinha.
    """
    from ..identity.browser import limpar_cache

    perfil = perfil_da_conta(canal)
    if limpar:
        pastas, mb = limpar_cache(perfil)
        print(f"[tiktok] cache do perfil limpo: {len(pastas)} pasta(s), "
              f"{mb} MB. O login foi preservado.")

    if not _janela_de_login(perfil):
        return
    # A pagina nao montou. A limpeza e a segunda janela precisam acontecer
    # FORA do contexto anterior: `sync_playwright` nao pode ser aberto dentro
    # de outro (o erro e "Sync API inside the asyncio loop"), e o cache so
    # pode ser apagado com o Chrome ja fechado.
    if limpar:
        print("[tiktok] a pagina continua sem carregar mesmo com o cache "
              "limpo. Pode ser rede/VPN, ou o site fora do ar.")
        return
    print("[tiktok] a pagina abriu BRANCA (so o esqueleto cinza). Isso e "
          "perfil degradado, nao bloqueio: vou limpar o cache — o login e "
          "preservado — e abrir de novo.")
    time.sleep(1.0)
    login(canal=canal, limpar=True)


def _janela_de_login(perfil: Path) -> bool:
    """A janela do login. Devolve True se a pagina NAO montou (precisa reparo)."""
    from ..identity.browser import montou

    with contexto_persistente(headless=False, profile=perfil) as ctx:
        page = _abrir(ctx, "https://www.tiktok.com/login")

        # Esperar de VERDADE antes de acusar o perfil: a home do TikTok e
        # pesada e leva dezenas de segundos numa maquina ocupada. Seis
        # segundos declaravam "degradado" uma pagina que so estava lenta.
        montada, saiu_do_login = False, False
        fim = time.time() + PACIENCIA_LOGIN_S
        while time.time() < fim:
            time.sleep(2)
            try:
                if "/login" not in page.url:
                    saiu_do_login = True
                    break
                if montou(page, minimo=120):
                    montada = True
                    break
            except Exception:
                break
        if not (montada or saiu_do_login):
            return True

        if saiu_do_login:
            print(f"[tiktok] esta conta JA esta logada (o site foi direto para "
                  f"{page.url}). Nao ha nada a fazer aqui.")
            time.sleep(2)
            return False

        print(f"[tiktok] faça o login nesta janela ({perfil.name}); ela fecha "
              "sozinha em 5 min (ou feche depois de entrar).")
        limite = time.time() + 300
        while time.time() < limite:
            time.sleep(2)
            try:
                if "login" not in pagina(ctx).url:
                    print(f"[tiktok] sessão iniciada; perfil salvo em {perfil}")
                    time.sleep(3)
                    return False
            except Exception:
                return False
        print("[tiktok] tempo esgotado sem login.")
        return False


def publicar(video, *, postar: bool | None = None, config: dict | None = None,
             canal: str = "builds",
             progresso=None) -> str:
    """Sobe o vídeo e escreve a legenda. Só posta se `postar` for True.

    Devolve uma frase de estado — o que aconteceu de fato, não uma promessa.
    """
    from . import catalogo

    config = catalogo.carregar_config() if config is None else config
    ajustes = config.get("tiktok", {})
    if postar is None:
        postar = bool(ajustes.get("postar_automatico", False))
    url_upload = ajustes.get("url_upload") or URL_UPLOAD

    caminho = Path(video.caminho)
    if not caminho.is_file():
        raise TikTokFalhou(f"arquivo sumiu: {caminho}")
    if not video.vertical:
        # Não é impedimento técnico, mas 16:9 no TikTok entra com tarja e
        # some no feed — melhor avisar do que publicar torto.
        print("[tiktok] AVISO: este é o corte 16:9 (normal). O TikTok espera "
              "o 9:16 (celular).")

    def passo(texto: str):
        print(f"[tiktok] {texto}", flush=True)
        if progresso:
            progresso(texto)

    # A Vila mostra o que esta acontecendo lendo o diario, e ate 01/09/2026
    # publicar nao escrevia nada nele. Como o caminho padrao virou o
    # navegador, a fabrica "publicacao" ficava OCIOSA durante quase todo
    # upload de verdade -- so a API, hoje secundaria, reportava. Um painel
    # que mostra "parado" enquanto se publica e pior do que nao ter painel.
    with atividade.fabrica("publicacao", f"TikTok: {caminho.name}",
                           canal=canal), \
            contexto_persistente(headless=False,
                                 profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, url_upload)
        passo("abrindo o estúdio de upload...")

        entrada = None
        limite = time.time() + ESPERA_PAGINA_S
        while time.time() < limite and entrada is None:
            if "login" in page.url:
                raise TikTokFalhou(
                    "o TikTok pediu login. Rode o login uma vez pelo painel "
                    "(botão 'Login no TikTok') e tente de novo.")
            try:
                candidato = page.locator(ENTRADA_ARQUIVO).first
                if candidato.count():
                    entrada = candidato
                    break
            except Exception:
                pass
            time.sleep(1.0)
        if entrada is None:
            raise TikTokFalhou(
                "não achei o campo de arquivo na página de upload. Rode "
                "`python -m builds.publicar.tiktok --sondar` para ver a tela.")

        entrada.set_input_files(str(caminho))
        passo(f"arquivo entregue ({caminho.name}); o TikTok está processando...")

        # O upload real acontece do lado deles; o sinal de pronto é a tela
        # mudar (preview do vídeo / botão de postar habilitado).
        pronto = chegou = None
        limite = time.time() + ESPERA_PROCESSAR_S
        while time.time() < limite and pronto is None:
            pronto = _primeiro(page, (PROVA_DE_PRONTO,), timeout=2.0)
            if pronto is None and chegou is None:
                chegou = _primeiro(page, SINAIS_DE_PROGRESSO, timeout=1.0)
                if chegou is not None:
                    passo("arquivo recebido; esperando o TikTok processar...")
            time.sleep(1.0)
        if pronto is None and chegou is None:
            raise TikTokFalhou(
                "o TikTok não confirmou o processamento do vídeo a tempo. A "
                "janela está aberta: dá para terminar na mão.")
        passo("vídeo processado." if pronto is not None else
              "o botão de publicar não habilitou no tempo, mas o vídeo está "
              "na tela — tentando publicar mesmo assim.")

        legenda = _primeiro(page, CAMPO_LEGENDA, timeout=10.0)
        if legenda is not None:
            try:
                legenda.click()
                # `fill` não funciona em contenteditable: seleciona e digita.
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                legenda.type(video.descricao_completa[:2000], delay=8)
                passo("legenda escrita.")
            except Exception as exc:
                passo(f"não consegui escrever a legenda ({type(exc).__name__}); "
                      "dá para colar na mão.")
        else:
            passo("campo de legenda não encontrado; a janela está aberta.")

        if not postar:
            passo("PARANDO antes de publicar — confira e clique em Publicar. "
                  "A janela fica aberta por 5 minutos.")
            time.sleep(300)
            return ("vídeo carregado e legenda escrita; a publicação final "
                    "ficou com você")

        botao = _primeiro(page, BOTAO_POSTAR, timeout=15.0)
        if botao is None:
            raise TikTokFalhou(
                "não achei o botão de publicar (a janela segue aberta).")
        # O timeout PRECISA ser dito. Sem ele o Playwright usa 30 s para
        # esperar o botão ficar clicável, e o processamento do TikTok passa
        # disso — foi o que deixou `duelo_00001` fora do ar em 11/09/2026.
        try:
            botao.click(timeout=int(ESPERA_HABILITAR_S * 1000))
        except Exception as exc:
            raise TikTokFalhou(
                "o botão de publicar não ficou clicável em "
                f"{ESPERA_HABILITAR_S / 60:.0f} min — o TikTok ainda estava "
                f"processando o vídeo. A janela segue aberta. ({exc})"
            ) from exc
        passo("publicar clicado; confirmando...")
        estado = _confirmar_publicacao(page, passo)
        passo(estado)
        if confirmado(estado):
            # O TikTok nao devolve URL nem id aqui; o registro vale para
            # saber O QUE ja foi publicado e onde (a metrica de retencao
            # segue sendo so do YouTube).
            from . import metricas
            metricas.registrar_publicado(video, estado, "tiktok", canal=canal)
        return estado


def main(argv=None) -> int:
    import argparse

    from . import catalogo

    parser = argparse.ArgumentParser(
        description="Publica um vídeo do catálogo no TikTok (navegador)")
    parser.add_argument("video_id", nargs="?")
    parser.add_argument("--limpar", action="store_true",
                        help="limpa o cache do perfil antes (mantem o login)")
    parser.add_argument("--canal", default="builds",
                        help="de qual canal e a conta (builds|historias)")
    parser.add_argument("--login", action="store_true",
                        help="abre a janela para o login manual (uma vez)")
    parser.add_argument("--sondar", action="store_true",
                        help="despeja o DOM da tela de upload")
    parser.add_argument("--postar", action="store_true",
                        help="clica em publicar (o padrão é PARAR antes)")
    args = parser.parse_args(argv)

    if args.login:
        login(canal=args.canal, limpar=args.limpar)
        return 0
    if args.sondar:
        sondar(canal=args.canal)
        return 0
    if not args.video_id:
        parser.error("informe o video_id, --login ou --sondar")

    video = catalogo.por_id(args.video_id)
    if video is None:
        print(f"vídeo não encontrado: {args.video_id}")
        return 1
    try:
        print(publicar(video, postar=args.postar or None, canal=args.canal))
    except TikTokFalhou as exc:
        print(f"FALHOU: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["PERFIL", "TikTokFalhou", "login", "publicar", "sondar"]
