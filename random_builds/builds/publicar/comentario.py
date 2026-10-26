# -*- coding: utf-8 -*-
"""O comentario com a pergunta do episodio, FIXADO (26/10/2026).

Por que existe: a ficha de cada episodio da serie do Blue Lock tem uma
`pergunta` ("Qual personagem voce colocaria no seu time?") que o Adrian quer
como primeiro comentario do video, fixado no topo, para o publico responder.
So escreve no que a SERIE publicou; nao toca em duelos nem historias.

Como: pelo navegador logado da conta do canal (o mesmo perfil que publica),
nao pela API — o token da API do canal e de leitura. A pagina do video (nao o
Studio) e onde o dono comenta e fixa.

Regras:
  * IDEMPOTENTE: se a pagina ja tem o comentario (mesmo texto), nao escreve de
    novo; so fixa o que falta. Rodar duas vezes nao duplica.
  * NUNCA derruba a publicacao: quem chama embrulha; aqui o laudo diz o que
    aconteceu (`comentou`, `fixou`, `tela`).
  * O estado fica em `outputs/_serie_bluelock/comentarios.json` (o que ja foi
    feito por episodio e destino), para a rodada nao abrir o navegador atoa.
  * Texto passa pelo MESMO filtro da serie (`serie_bluelock.texto_proibido`).

Uso manual: `python -m builds.publicar.comentario 1 youtube [--video-id ID]`.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from . import escrita

RAIZ = Path(__file__).resolve().parents[2]
ESTADO = RAIZ / "outputs" / "_serie_bluelock" / "comentarios.json"
MAXIMO = 500

# CHAVE DESLIGADA (26/10/2026, ordem do Adrian): o primeiro teste comentou com
# a conta PESSOAL dele, nao com o canal. Nada comenta nem fixa sozinho ate ele
# mandar religar (e o perfil trocar para o canal certo).
LIGADO = False

# ---------------------------------------------------------------- seletores
# Candidatos em ordem de especificidade. A pagina de video do YouTube e a do
# TikTok mudam de layout: quando quebrar, olhe a captura que o laudo guarda.
YT_CAIXA = ("ytd-comment-simplebox-renderer #placeholder-area",
            "#simple-box #placeholder-area", "#placeholder-area")
YT_EDITOR = ("ytd-commentbox #contenteditable-root",
             "#contenteditable-root", "[contenteditable='true']")
YT_ENVIAR = ("ytd-commentbox #submit-button button",
             "ytd-commentbox #submit-button", "#submit-button button",
             "#submit-button")
YT_THREAD = "ytd-comment-thread-renderer"
YT_MENU = ("#action-menu button", "ytd-menu-renderer button#button",
           "ytd-menu-renderer button")
YT_ITEM_FIXAR = ("ytd-menu-service-item-renderer:has-text('Fixar')",
                 "ytd-menu-service-item-renderer:has-text('Pin')",
                 "tp-yt-paper-item:has-text('Fixar')",
                 "tp-yt-paper-item:has-text('Pin')",
                 "[role='menuitem']:has-text('Fixar')",
                 "[role='menuitem']:has-text('Pin')")
YT_CONFIRMAR = ("yt-confirm-dialog-renderer #confirm-button button",
                "yt-confirm-dialog-renderer #confirm-button",
                "tp-yt-paper-dialog #confirm-button button",
                "tp-yt-paper-dialog #confirm-button",
                "#confirm-button button", "#confirm-button")
YT_FIXADO = ("ytd-pinned-comment-badge-renderer",
             "#pinned-comment-badge")

TT_EDITOR = ("[data-e2e='comment-input'] [contenteditable='true']",
             "[data-e2e='comment-input'] [contenteditable]",
             "[data-e2e='comment-input']", "[contenteditable='true']")
TT_ENVIAR = ("[data-e2e='comment-post']",)
TT_COMENTARIO = "[data-e2e='comment-level-1']"
TT_MENU = ("[data-e2e='comment-more']", "[data-e2e='more-menu-icon']",
           "[data-e2e='comment-item-more']")
TT_ITEM_FIXAR = ("text=/^(Fixar|Pin)/i",
                 "[role='menuitem']:has-text('Fixar')",
                 "[role='menuitem']:has-text('Pin')")
TT_FIXADO = ("[data-e2e='comment-pinned']", "text=/Fixado|Pinned/i")


class ComentarioFalhou(RuntimeError):
    pass


def _primeiro(page, seletores, timeout: float = 5.0, raiz=None):
    """O primeiro candidato VISIVEL, esperando ate `timeout`; ou None."""
    fim = time.time() + timeout
    base = raiz if raiz is not None else page
    while True:
        for sel in seletores:
            try:
                loc = base.locator(sel).first
                if loc.count() and loc.is_visible():
                    return loc
            except Exception:                                  # noqa: BLE001
                continue
        if time.time() >= fim:
            return None
        time.sleep(0.4)


def _rolar_ate(page, seletores, passos: int = 14) -> object:
    """Rola a pagina ate algum candidato aparecer (comentarios carregam sob demanda)."""
    for _ in range(passos):
        achado = _primeiro(page, seletores, timeout=0.8)
        if achado is not None:
            return achado
        try:
            page.mouse.wheel(0, 700)
        except Exception:                                      # noqa: BLE001
            pass
        time.sleep(0.7)
    return _primeiro(page, seletores, timeout=1.0)


def _normal(texto: str) -> str:
    """Sem emoji nem pontuacao (a pagina devolve o emoji como imagem e some
    do `inner_text`): so letras e numeros, em minusculas."""
    miolo = "".join(c if c.isalnum() else " " for c in str(texto or ""))
    return re.sub(r"\s+", " ", miolo).strip().lower()


def _thread_com(page, thread_sel: str, texto: str):
    """O comentario (thread) cujo texto contem `texto`, ou None."""
    alvo = _normal(texto)
    try:
        total = page.locator(thread_sel).count()
    except Exception:                                          # noqa: BLE001
        return None
    for i in range(min(total, 30)):
        loc = page.locator(thread_sel).nth(i)
        try:
            if alvo in _normal(loc.inner_text(timeout=2000)):
                return loc
        except Exception:                                      # noqa: BLE001
            continue
    return None


def _validar(texto: str) -> str:
    texto = str(texto or "").strip()
    if not texto:
        raise ComentarioFalhou("a pergunta esta vazia")
    if len(texto) > MAXIMO:
        raise ComentarioFalhou(f"a pergunta tem {len(texto)} caracteres (maximo {MAXIMO})")
    from . import serie_bluelock
    proibida = serie_bluelock.texto_proibido(texto)
    if proibida:
        raise ComentarioFalhou(f"a pergunta fala de '{proibida}' (regra do Adrian)")
    return texto


# ------------------------------------------------------------------ YouTube
def comentar_e_fixar_youtube(page, texto: str, passo=print) -> dict:
    """Na PAGINA DO VIDEO ja aberta: escreve o comentario (se ainda nao
    existe) e o fixa. Devolve o laudo; levanta `ComentarioFalhou` se nao deu."""
    texto = _validar(texto)
    laudo = {"comentou": False, "fixou": False, "ja_existia": False}
    _rolar_ate(page, YT_CAIXA + (YT_THREAD,))
    thread = _thread_com(page, YT_THREAD, texto)
    if thread is not None:
        laudo["ja_existia"] = True
        passo("o comentario ja esta na pagina; so falta fixar (se nao estiver).")
    else:
        caixa = _rolar_ate(page, YT_CAIXA)
        if caixa is None:
            raise ComentarioFalhou("nao achei a caixa de comentario (comentarios "
                                   "desligados ou a pagina nao montou)")
        caixa.click(timeout=8000)
        editor = _primeiro(page, YT_EDITOR, timeout=8.0)
        if editor is None:
            raise ComentarioFalhou("a caixa nao abriu o editor")
        editor.click(timeout=5000)
        page.keyboard.insert_text(texto)
        time.sleep(0.6)
        lido = _normal(editor.inner_text(timeout=3000))
        if _normal(texto) not in lido:
            raise ComentarioFalhou(f"o editor nao ficou igual ao texto: {lido[:80]!r}")
        enviar = _primeiro(page, YT_ENVIAR, timeout=6.0)
        if enviar is None:
            raise ComentarioFalhou("nao achei o botao de comentar")
        enviar.click(timeout=8000)
        passo("comentario enviado; esperando aparecer...")
        fim = time.time() + 25
        while thread is None and time.time() < fim:
            time.sleep(1.0)
            thread = _thread_com(page, YT_THREAD, texto)
        if thread is None:
            raise ComentarioFalhou("enviei, mas o comentario nao apareceu na pagina")
        laudo["comentou"] = True
    # Ja fixado?
    if _primeiro(page, YT_FIXADO, timeout=1.0, raiz=thread) is not None:
        laudo["fixou"] = True
        return laudo
    thread.hover(timeout=5000)
    menu = _primeiro(page, YT_MENU, timeout=5.0, raiz=thread)
    if menu is None:
        raise ComentarioFalhou("nao achei o menu (...) do comentario")
    menu.click(timeout=5000)
    item = _primeiro(page, YT_ITEM_FIXAR, timeout=5.0)
    if item is None:
        raise ComentarioFalhou("o menu nao tem 'Fixar' (video sem permissao de dono?)")
    item.click(timeout=5000)
    confirmar = _primeiro(page, YT_CONFIRMAR, timeout=6.0)
    if confirmar is not None:
        confirmar.click(timeout=5000)
    fim = time.time() + 15
    while time.time() < fim:
        thread = _thread_com(page, YT_THREAD, texto)
        if thread is not None and _primeiro(page, YT_FIXADO, timeout=0.5,
                                            raiz=thread) is not None:
            laudo["fixou"] = True
            break
        time.sleep(1.0)
    if not laudo["fixou"]:
        raise ComentarioFalhou("cliquei em Fixar, mas o selo de fixado nao apareceu")
    return laudo


# ------------------------------------------------------------------- TikTok
def comentar_e_fixar_tiktok(page, texto: str, passo=print) -> dict:
    """Na pagina do POST ja aberta. Fixar e melhor esforco: se a interface nao
    oferecer, o laudo diz `fixou: False` e o comentario fica."""
    texto = _validar(texto)
    laudo = {"comentou": False, "fixou": False, "ja_existia": False}
    thread = _thread_com(page, TT_COMENTARIO, texto)
    if thread is not None:
        laudo["ja_existia"] = True
    else:
        editor = _rolar_ate(page, TT_EDITOR, passos=4)
        if editor is None:
            raise ComentarioFalhou("nao achei a caixa de comentario do TikTok")
        editor.click(timeout=8000)
        page.keyboard.insert_text(texto)
        time.sleep(0.8)
        enviar = _primeiro(page, TT_ENVIAR, timeout=6.0)
        if enviar is None:
            raise ComentarioFalhou("nao achei o botao Publicar do comentario")
        enviar.click(timeout=8000)
        passo("comentario enviado ao TikTok; esperando aparecer...")
        fim = time.time() + 25
        while thread is None and time.time() < fim:
            time.sleep(1.0)
            thread = _thread_com(page, TT_COMENTARIO, texto)
        if thread is None:
            raise ComentarioFalhou("enviei, mas o comentario nao apareceu")
        laudo["comentou"] = True
    if _primeiro(page, TT_FIXADO, timeout=1.0, raiz=thread) is not None:
        laudo["fixou"] = True
        return laudo
    try:
        thread.hover(timeout=5000)
        menu = _primeiro(page, TT_MENU, timeout=4.0, raiz=thread)
        if menu is not None:
            menu.click(timeout=4000)
            item = _primeiro(page, TT_ITEM_FIXAR, timeout=4.0)
            if item is not None:
                item.click(timeout=4000)
                time.sleep(2.0)
                laudo["fixou"] = _primeiro(page, TT_FIXADO, timeout=4.0,
                                           raiz=thread) is not None
    except Exception as exc:                                   # noqa: BLE001
        laudo["fixar_erro"] = f"{type(exc).__name__}: {str(exc)[:100]}"
    return laudo


# ------------------------------------------------------------------- estado
def _ler_estado() -> dict:
    try:
        dados = json.loads(ESTADO.read_text(encoding="utf-8-sig"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def ja_feito(numero: int, destino: str) -> bool:
    return bool((_ler_estado().get(f"ep{int(numero):02d}") or {}).get(destino, {})
                .get("comentou"))


def _gravar(numero: int, destino: str, laudo: dict) -> None:
    estado = _ler_estado()
    estado.setdefault(f"ep{int(numero):02d}", {})[destino] = {
        **laudo, "em": datetime.now().isoformat(timespec="seconds")}
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, ESTADO)


# ----------------------------------------------------------- com navegador
def aplicar(numero: int, destino: str, texto: str, *, video_id: str = "",
            canal: str = "bluelock", passo=print) -> dict:
    """Abre o navegador LOGADO da conta e comenta+fixa. Grava o estado. Nao
    use dentro de post-12..post+18 (abre o perfil da conta)."""
    from ..identity.browser import abrir_pagina, contexto_persistente
    if not LIGADO and os.environ.get("NF_COMENTARIO_LIBERADO") != "1":
        raise ComentarioFalhou("comentario desligado (ordem do Adrian, 26/10)")
    texto = _validar(texto)
    laudo: dict = {}
    if destino == "youtube":
        from . import youtube_web as web
        if not video_id:
            raise ComentarioFalhou("falta o id do video do YouTube")
        perfil, url = web.perfil_da_conta(canal), f"https://www.youtube.com/watch?v={video_id}"
        funcao = comentar_e_fixar_youtube
    elif destino == "tiktok":
        from . import tiktok as web
        perfil = web.perfil_da_conta(canal)
        url = (f"https://www.tiktok.com/@{web._conta_ativa(canal)}"
               + (f"/video/{video_id}" if video_id else ""))
        funcao = comentar_e_fixar_tiktok
    else:
        raise ComentarioFalhou(f"destino desconhecido: {destino!r}")
    with contexto_persistente(headless=False, profile=perfil) as ctx:
        page = abrir_pagina(ctx, url, log=lambda t: passo(f"[comentario] {t}"))
        page.wait_for_timeout(5000)
        if destino == "tiktok" and not video_id:
            link = _primeiro(page, ("a[href*='/video/']",), timeout=15.0)
            if link is None:
                raise ComentarioFalhou("nao achei o post no perfil do TikTok")
            link.click(timeout=8000)
            page.wait_for_timeout(6000)
        try:
            laudo = funcao(page, texto, passo)
        except ComentarioFalhou as exc:
            laudo = {"comentou": False, "fixou": False, "erro": str(exc)}
            laudo["tela"] = escrita.fotografar(page, f"comentario_{destino}_falha")
            _gravar(numero, destino, laudo)
            raise
        page.wait_for_timeout(1500)
        laudo["tela"] = escrita.fotografar(page, f"comentario_{destino}")
        laudo["url"] = page.url
    _gravar(numero, destino, laudo)
    return laudo


def aplicar_se_tiver(numero: int, destino: str, *, video_id: str = "",
                     passo=print) -> dict:
    """Para a rodada: so age se a ficha do episodio tem `pergunta` e ainda nao
    foi feito. NUNCA levanta."""
    if not LIGADO:
        return {"pulou": "comentario automatico desligado"}
    try:
        if ja_feito(numero, destino):
            return {"pulou": "ja feito"}
        from . import serie_bluelock as serie
        texto = serie.pergunta_de(numero)
        if not texto:
            return {"pulou": "sem pergunta na ficha"}
        return aplicar(numero, destino, texto, video_id=video_id, passo=passo)
    except Exception as exc:                                   # noqa: BLE001
        passo(f"[comentario] {destino}: nao deu ({type(exc).__name__}: {exc})"[:200])
        return {"erro": f"{type(exc).__name__}: {exc}"[:200]}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="comentario")
    ap.add_argument("numero", type=int)
    ap.add_argument("destino", choices=("youtube", "tiktok"))
    ap.add_argument("--video-id", default="")
    ns = ap.parse_args(argv)
    from . import serie_bluelock as serie
    texto = serie.pergunta_de(ns.numero)
    if not texto:
        print("a ficha nao tem `pergunta`.")
        return 1
    try:
        print(aplicar(ns.numero, ns.destino, texto, video_id=ns.video_id))
        return 0
    except ComentarioFalhou as exc:
        print("nao deu:", exc)
        return 1


if __name__ == "__main__":                               # pragma: no cover
    raise SystemExit(main())
