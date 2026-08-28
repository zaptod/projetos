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

from ..identity.browser import contexto_persistente, pagina

RAIZ = Path(__file__).resolve().parents[2]
PERFIL = RAIZ / ".browser_profile" / "tiktok"
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
# Sinais de que o vídeo terminou de subir e a página está pronta para postar.
SINAIS_PRONTO = (
    'button[data-e2e="post_video_button"]:not([disabled])',
    'div[class*="preview"] video',
    'video',
)


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


def _abrir(ctx, url: str):
    page = pagina(ctx)
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    return page


def sondar(saida: Path | None = None) -> Path:
    """Despeja o DOM da tela de upload (para ajustar seletor quando quebrar).

    Mesmo espírito do `identity probe`: quando o site muda, ninguém adivinha
    o seletor novo — a gente OLHA.
    """
    import json

    saida = saida or (RAIZ / "outputs" / "_identity" /
                      f"probe_tiktok_{time.strftime('%Y%m%d_%H%M%S')}.json")
    saida.parent.mkdir(parents=True, exist_ok=True)
    with contexto_persistente(headless=False, profile=PERFIL) as ctx:
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


def login() -> None:
    """Abre a janela para o login manual. Uma vez por perfil."""
    with contexto_persistente(headless=False, profile=PERFIL) as ctx:
        _abrir(ctx, "https://www.tiktok.com/login")
        print("[tiktok] faça o login nesta janela; ela fecha sozinha em 3 min "
              "(ou feche depois de entrar).")
        limite = time.time() + 180
        while time.time() < limite:
            time.sleep(2)
            try:
                if "login" not in pagina(ctx).url:
                    print("[tiktok] sessão iniciada; perfil salvo em "
                          f"{PERFIL}")
                    time.sleep(3)
                    return
            except Exception:
                return


def publicar(video, *, postar: bool | None = None, config: dict | None = None,
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

    with contexto_persistente(headless=False, profile=PERFIL) as ctx:
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
                "`python -m src.publicar.tiktok --sondar` para ver a tela.")

        entrada.set_input_files(str(caminho))
        passo(f"arquivo entregue ({caminho.name}); o TikTok está processando...")

        # O upload real acontece do lado deles; o sinal de pronto é a tela
        # mudar (preview do vídeo / botão de postar habilitado).
        pronto = None
        limite = time.time() + ESPERA_PROCESSAR_S
        while time.time() < limite and pronto is None:
            pronto = _primeiro(page, SINAIS_PRONTO, timeout=2.0)
            time.sleep(1.0)
        if pronto is None:
            raise TikTokFalhou(
                "o TikTok não confirmou o processamento do vídeo a tempo. A "
                "janela está aberta: dá para terminar na mão.")
        passo("vídeo processado.")

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
        botao.click()
        passo("publicar clicado; confirmando...")
        time.sleep(15)
        return "publicado no TikTok"


def main(argv=None) -> int:
    import argparse

    from . import catalogo

    parser = argparse.ArgumentParser(
        description="Publica um vídeo do catálogo no TikTok (navegador)")
    parser.add_argument("video_id", nargs="?")
    parser.add_argument("--login", action="store_true",
                        help="abre a janela para o login manual (uma vez)")
    parser.add_argument("--sondar", action="store_true",
                        help="despeja o DOM da tela de upload")
    parser.add_argument("--postar", action="store_true",
                        help="clica em publicar (o padrão é PARAR antes)")
    args = parser.parse_args(argv)

    if args.login:
        login()
        return 0
    if args.sondar:
        sondar()
        return 0
    if not args.video_id:
        parser.error("informe o video_id, --login ou --sondar")

    video = catalogo.por_id(args.video_id)
    if video is None:
        print(f"vídeo não encontrado: {args.video_id}")
        return 1
    try:
        print(publicar(video, postar=args.postar or None))
    except TikTokFalhou as exc:
        print(f"FALHOU: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["PERFIL", "TikTokFalhou", "login", "publicar", "sondar"]
