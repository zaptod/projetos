# -*- coding: utf-8 -*-
"""Despeja o DOM real do ChatGPT/Gemini para consertar seletor que quebrou.

Os dois sites mudam de classe sem avisar. Quando a automacao parar, o
caminho e este: abrir a pagina com o perfil logado, ver o que EXISTE agora e
ajustar `src/llm/seletores.py`. Nenhum outro arquivo precisa mudar.

    python main.py llm probe --provedor chatgpt
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from builds.identity import browser as _rb_identity_browser

from . import cliente as cli
from . import seletores as sel

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "outputs" / "_llm"


def run(provedor: str = "chatgpt", *, esperar: float = 0.0,
        headless: bool = False, log=print) -> Path:
    browser = _rb_identity_browser
    alvo = sel.do_provedor(provedor)

    with browser.contexto_persistente(headless=headless,
                                      profile=cli.perfil_de(provedor)) as ctx:
        page = browser.pagina(ctx)
        page.goto(alvo["url"], wait_until="domcontentloaded", timeout=90_000)
        if esperar:
            log(f"[probe] esperando {esperar:.0f}s (use para logar ou "
                "chegar na tela certa)...")
            page.wait_for_timeout(int(esperar * 1000))
        else:
            page.wait_for_timeout(4000)

        achados = {}
        for nome, candidatos in alvo.items():
            if not isinstance(candidatos, list):
                continue
            achados[nome] = []
            for seletor in candidatos:
                try:
                    total = page.locator(seletor).count()
                    visivel = sel.encontrar(page, [seletor], timeout=0.4) is not None
                except Exception as exc:
                    achados[nome].append({"seletor": seletor,
                                          "erro": str(exc)[:120]})
                    continue
                achados[nome].append({"seletor": seletor, "no_dom": total,
                                      "visivel": visivel})

        dados = {
            "provedor": provedor, "url": page.url,
            "quando": datetime.now().isoformat(timespec="seconds"),
            "titulo_da_pagina": page.title(),
            "seletores": achados,
            # Um retrato do que existe: quando NENHUM candidato casa, e aqui
            # que se descobre com que nome o site chama as coisas agora.
            "contenteditable": page.eval_on_selector_all(
                "[contenteditable='true']",
                "els => els.slice(0,6).map(e => ({id: e.id, cls: e.className, "
                "aria: e.getAttribute('aria-label'), role: e.getAttribute('role')}))"),
            "botoes": page.eval_on_selector_all(
                "button",
                "els => els.slice(0,40).map(e => ({t: (e.innerText||'').slice(0,24), "
                "aria: e.getAttribute('aria-label'), test: "
                "e.getAttribute('data-testid'), cls: (e.className||'').slice(0,60)}))"),
        }

    DESTINO.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo = DESTINO / f"probe_{provedor}_{carimbo}.json"
    with open(arquivo, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)

    log(f"[probe] {provedor}: {dados['titulo_da_pagina']}")
    for nome, linhas in achados.items():
        marcas = ", ".join(
            f"{l['seletor']}={'VISIVEL' if l.get('visivel') else l.get('no_dom', 0)}"
            for l in linhas)
        log(f"[probe]   {nome}: {marcas}")
    log(f"[probe] despejo completo em {arquivo}")
    return arquivo


# A tela de desafio do Cloudflare, nas duas linguas. Ela NAO e "deslogado":
# e "nao deu para perguntar". Tratar uma como a outra foi o erro de 09/09/2026
# — o `chatgpt.com` serve este interstitial para janela headless e a conta boa
# foi declarada morta por causa dele.
BARRADO = ("um momento", "just a moment", "verificando", "checking your browser",
           "attention required")


def sessao_valida(provedor: str = "chatgpt", *, headless: bool = False,
                  log=print) -> bool | None:
    """A sessao vale? True / False / None quando NAO DEU PARA PERGUNTAR.

    Duas armadilhas, uma de cada lado:

    `contas.tem_login` so olha se o arquivo de cookies do Chrome esta no
    disco — e ele nasce na primeira vez que o navegador abre, logado ou nao.
    Perfil recem-criado responde "True" ali. Falso positivo.

    E o `chatgpt.com` responde o desafio do Cloudflare para janela headless:
    o chat nunca monta, e concluir "deslogado" dai declara morta uma sessao
    viva. Falso negativo. Por isso o padrao aqui e headless=False, e por isso
    existe o terceiro estado: `None` e "a pergunta nao chegou ao site".
    """
    browser = _rb_identity_browser
    alvo = sel.do_provedor(provedor)
    try:
        with browser.contexto_persistente(headless=headless,
                                          profile=cli.perfil_de(provedor)) as ctx:
            page = browser.pagina(ctx)
            page.goto(alvo["url"], wait_until="domcontentloaded",
                      timeout=90_000)
            page.wait_for_timeout(4000)
            if sel.encontrar(page, alvo["logado"], timeout=6.0) is not None:
                return True
            titulo = (page.title() or "").strip().lower()
            if any(marca in titulo for marca in BARRADO):
                log(f"[login] o site respondeu {titulo!r} (desafio anti-bot); "
                    "nao da para saber daqui se a sessao vale.")
                return None
            # Sem o chat E sem desafio: se a tela de login esta ai, e deslogado
            # mesmo. Se nao esta nenhuma das duas, a pagina nao e o que se
            # espera — e chutar "deslogado" seria o mesmo erro de novo.
            if sel.encontrar(page, alvo["login"], timeout=3.0) is not None:
                return False
            log(f"[login] nao achei nem o chat nem a tela de login em "
                f"{page.url}; nao concluo nada.")
            return None
    except Exception as exc:                                   # noqa: BLE001
        log(f"[login] nao deu para conferir a sessao ({exc}).")
        return None


def login(provedor: str = "chatgpt", *, espera: float = 300.0, log=print) -> bool:
    """Abre a janela e espera voce entrar na conta. O perfil guarda a sessao.

    FECHAR A JANELA E O FIM NORMAL, nao um acidente: quando o login termina, o
    reflexo e fechar. Antes isso subia um `TargetClosedError` com trinta linhas
    de traceback e ninguem sabia se tinha dado certo — e a checagem de disco
    respondia "logado" para um perfil vazio. Agora o fecho e esperado e a
    resposta vem do SITE.
    """
    browser = _rb_identity_browser
    alvo = sel.do_provedor(provedor)
    perfil = cli.perfil_de(provedor)
    log(f"[login] abrindo o {provedor} no perfil {perfil}.")
    log("[login] entre na conta na janela que abriu; quando o chat aparecer, "
        "pode fechar a janela.")
    visto = False
    try:
        with browser.contexto_persistente(headless=False,
                                          profile=perfil) as ctx:
            page = browser.pagina(ctx)
            page.goto(alvo["url"], wait_until="domcontentloaded", timeout=90_000)
            limite = espera
            passo = 3.0
            while limite > 0:
                if sel.encontrar(page, alvo["logado"], timeout=1.0) is not None:
                    visto = True
                    log(f"[login] o chat do {provedor} montou. Salvando a "
                        "sessao no perfil...")
                    page.wait_for_timeout(3000)
                    break
                page.wait_for_timeout(int(passo * 1000))
                limite -= passo
    except Exception as exc:                                   # noqa: BLE001
        if "closed" not in str(exc).lower():
            raise
        log("[login] janela fechada.")

    # O CHAT TER MONTADO NA JANELA DE VERDADE JA E A PROVA. Reconferir depois
    # so acrescenta uma chance de errar: em 09/09/2026 a reconferencia abria
    # headless, tomava o desafio do Cloudflare e dizia "NAO LOGADO" por cima
    # de um login que tinha acabado de dar certo.
    if visto:
        log(f"[login] SESSAO VALIDA. O {provedor} esta logado no perfil "
            f"{perfil}.")
        return True

    valida = sessao_valida(provedor, log=log)
    if valida:
        log(f"[login] SESSAO VALIDA. O {provedor} esta logado no perfil "
            f"{perfil}.")
        return True
    if valida is None:
        log("[login] a janela fechou antes de o chat montar e o site nao "
            "deixou conferir depois. NAO SEI dizer se logou — abra o "
            f"{provedor} voce mesmo, ou rode de novo e espere o chat aparecer.")
        return False
    log(f"[login] NAO LOGADO. Rode de novo: "
        f"python main.py llm login --provedor {provedor}")
    return False
