"""Login no Digen — que na pratica quase nunca acontece.

O perfil persistente guarda o cookie de sessao, entao o caminho normal e
`ensure_logged_in` navegar, ver o campo de prompt e voltar. O fluxo de senha
existe para o primeiro uso e para quando a sessao expira.

Desafio (captcha / 2FA / Cloudflare) NAO e resolvido programaticamente: a
janela fica aberta esperando voce resolver. Esse e exatamente o motivo de
rodar headful. Resolvido uma vez, o cookie fica no perfil.
"""
from __future__ import annotations

import random
import time

from . import config, selectors
from .browser import digitar, esperar_hidratacao, pausa_humana


class LoginFalhou(RuntimeError):
    pass


def sessao_viva(page, timeout: float = 3.0) -> bool:
    return selectors.encontrar(page, selectors.SESSAO_VIVA, timeout=timeout) is not None


def _esperar_humano(page, ajustes: dict, motivo: str) -> None:
    """Segura o processo enquanto o usuario resolve o desafio na janela."""
    limite = float(ajustes.get("manual_login_timeout", 180))
    print(f"[digen] {motivo}")
    print(f"[digen] resolva na janela do Chrome — esperando ate {limite:.0f}s...",
          flush=True)
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if sessao_viva(page, timeout=2.0):
            print("[digen] resolvido, sessao viva.")
            return
        time.sleep(3.0)

    # Sem sessao E sem tela de login = o app nao montou. Chamar isso de
    # "problema de login" manda o usuario para o lugar errado; o certo e dizer
    # que a pagina nao carregou (Chrome mal encerrado, perfil travado, rede).
    if selectors.encontrar(page, selectors.TELA_LOGIN, timeout=3.0) is None:
        raise LoginFalhou(
            f"a pagina nao montou em {limite:.0f}s ({page.url}): nao apareceu "
            "nem o campo de prompt nem a tela de login. Costuma ser Chrome "
            "encerrado a forca deixando o perfil sujo — feche as janelas do "
            "perfil da automacao e rode `python main.py identity doctor "
            "--online`.")
    raise LoginFalhou(
        f"{motivo} e o desafio nao foi resolvido em {limite:.0f}s. "
        "Rode `python main.py identity login` e resolva com calma: o cookie "
        "fica salvo no perfil e as proximas execucoes nao pedem de novo.")


def ensure_logged_in(page, ajustes: dict | None = None,
                     rng: random.Random | None = None) -> None:
    ajustes = ajustes if ajustes is not None else config.settings()
    rng = rng or random.Random()

    page.goto(selectors.URL_CRIACAO, wait_until="domcontentloaded",
              timeout=int(float(ajustes.get("navigation_timeout", 60)) * 1000))
    esperar_hidratacao(page, float(ajustes.get("hydration_timeout", 45)))
    pausa_humana(rng)

    if sessao_viva(page, timeout=6.0):
        print("[digen] sessao ja valida (perfil persistente).")
        return

    if selectors.encontrar(page, selectors.DESAFIO, timeout=2.0):
        _esperar_humano(page, ajustes, "desafio anti-bot na tela")
        return

    credenciais = config.load_credentials()
    if credenciais is None:
        _esperar_humano(
            page, ajustes,
            f"sem sessao e sem {config.credentials_path().name}; "
            "faca o login manualmente")
        return

    if not selectors.encontrar(page, selectors.TELA_LOGIN, timeout=3.0):
        page.goto(selectors.URL_LOGIN, wait_until="domcontentloaded")
        pausa_humana(rng)

    print("[digen] preenchendo login...")
    digitar(selectors.resolver(page, selectors.CAMPO_EMAIL, "o campo de e-mail"),
            credenciais["email"], rng)
    pausa_humana(rng)
    digitar(selectors.resolver(page, selectors.CAMPO_SENHA, "o campo de senha"),
            credenciais["password"], rng)
    pausa_humana(rng)
    selectors.resolver(page, selectors.BOTAO_LOGIN, "o botao de login").click()

    fim = time.monotonic() + float(ajustes.get("login_timeout", 60))
    while time.monotonic() < fim:
        if sessao_viva(page, timeout=2.0):
            print("[digen] login concluido; cookie salvo no perfil.")
            return
        if selectors.encontrar(page, selectors.DESAFIO, timeout=1.0):
            _esperar_humano(page, ajustes, "desafio anti-bot apos o login")
            return
        time.sleep(2.0)

    raise LoginFalhou(
        "login enviado mas a pagina logada nao apareceu. Verifique e-mail/senha "
        f"em {config.credentials_path()} ou rode `python main.py identity login`.")
