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

from . import cliente as cli
from . import seletores as sel

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "outputs" / "_llm"


def run(provedor: str = "chatgpt", *, esperar: float = 0.0,
        headless: bool = False, log=print) -> Path:
    from .. import compartilhado
    browser = compartilhado.modulo("identity.browser")
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


def login(provedor: str = "chatgpt", *, espera: float = 300.0, log=print) -> None:
    """Abre a janela e espera voce entrar na conta. O perfil guarda a sessao."""
    from .. import compartilhado
    browser = compartilhado.modulo("identity.browser")
    alvo = sel.do_provedor(provedor)
    log(f"[login] abrindo o {provedor}. Entre na sua conta na janela que abriu.")
    log(f"[login] a janela fica aberta por ate {espera / 60:.0f} min; "
        "quando o chat aparecer, pode fechar ou esperar.")
    with browser.contexto_persistente(headless=False,
                                      profile=cli.perfil_de(provedor)) as ctx:
        page = browser.pagina(ctx)
        page.goto(alvo["url"], wait_until="domcontentloaded", timeout=90_000)
        limite = espera
        passo = 3.0
        while limite > 0:
            if sel.encontrar(page, alvo["logado"], timeout=1.0) is not None:
                log(f"[login] sessao do {provedor} valida e salva no perfil "
                    f"{cli.perfil_de(provedor)}")
                page.wait_for_timeout(2000)
                return
            page.wait_for_timeout(int(passo * 1000))
            limite -= passo
    log(f"[login] nao vi o chat montar em {espera / 60:.0f} min. "
        "Rode de novo se o login nao tiver concluido.")
