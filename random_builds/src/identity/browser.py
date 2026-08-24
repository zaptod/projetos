"""Contexto de browser persistente e pouco detectavel (patchright).

Por que patchright e nao selenium/playwright de fabrica: os dois publicam o
vazamento de `Runtime.enable` no CDP, que e o sinal nº1 usado para identificar
automacao. O patchright executa JS em ExecutionContext isolado e nao emite esse
comando.

O que realmente esconde o bot aqui sao QUATRO coisas, nao um pacote de truques:

  1. `channel="chrome"`   -> Chrome de verdade, nao o Chromium empacotado
  2. `user_data_dir=...`  -> perfil persistente: historico, cookies e cookies de
                             anti-bot que so um usuario real acumula
  3. `headless=False`     -> headless e detectavel de dezenas de formas
  4. `no_viewport=True`   -> sem viewport forcado; a janela tem o tamanho real

Deliberadamente NAO fazemos: user-agent forjado, `--no-sandbox`,
`--disable-web-security` ou stealth-plugins. Cada um deles ADICIONA sinal (um
UA que nao bate com o build do Chrome, flags que nenhum usuario liga) em vez de
remover.
"""
from __future__ import annotations

import contextlib
import os
import random
import signal
import subprocess
import time
from pathlib import Path

from . import config

# nao abrir janela de console para o powershell de diagnostico no Windows
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# A unica flag que vale a pena: tira o `navigator.webdriver`.
ARGS_PADRAO = ["--disable-blink-features=AutomationControlled"]


class PatchrightAusente(RuntimeError):
    pass


def _sync_playwright():
    try:
        from patchright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise PatchrightAusente(
            "patchright nao instalado. Rode:\n"
            "    pip install patchright\n"
            "    patchright install chrome") from exc
    return sync_playwright


def _chrome_do_perfil(user_data_dir: str) -> list[int]:
    """PIDs de Chrome que seguram ESTE perfil (nunca o Chrome do usuario).

    O filtro e a linha de comando conter o nosso `--user-data-dir`. Sem isso
    nao da para distinguir: `taskkill` por nome mataria as abas pessoais junto.
    """
    alvo = str(user_data_dir).replace("/", "\\")
    if os.name == "nt":
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{alvo}*' }} | "
            "Select-Object -ExpandProperty ProcessId")
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    else:
        cmd = ["pgrep", "-f", f"user-data-dir={user_data_dir}"]
    try:
        saida = subprocess.run(cmd, capture_output=True, text=True, timeout=25,
                               creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(linha) for linha in saida.split() if linha.strip().isdigit()]


def _liberar_perfil(user_data_dir: str) -> int:
    """Encerra o Chrome orfao que ficou segurando o perfil.

    Acontece toda vez que o worker morre no meio (Ctrl+C, crash, maquina
    suspensa): o Chrome continua vivo, o proximo launch anexa na sessao
    existente e morre com "Target page, context or browser has been closed" —
    mensagem que nao diz nada sobre a causa real.
    """
    pids = _chrome_do_perfil(user_data_dir)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            continue
    if pids:
        print(f"[digen] {len(pids)} processo(s) Chrome orfao(s) do perfil "
              "encerrado(s).")
        time.sleep(2.0)
    return len(pids)


@contextlib.contextmanager
def contexto_persistente(headless: bool = False, profile: Path | None = None):
    """Contexto logado e persistente. Fecha tudo no fim, com ou sem excecao.

    Nao ha `browser` separado: `launch_persistent_context` devolve o contexto
    ja ligado ao perfil. Fechar o contexto fecha o Chrome.
    """
    sync_playwright = _sync_playwright()
    user_data_dir = str(profile or config.profile_dir())

    def abrir(p):
        return p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=headless,
            no_viewport=True,
            args=ARGS_PADRAO,
        )

    with sync_playwright() as p:
        try:
            ctx = abrir(p)
        except Exception as exc:
            # Uma unica retomada, e so se havia mesmo orfao para matar: sem
            # isso um erro de outra natureza viraria loop de tentativa.
            if not _liberar_perfil(user_data_dir):
                raise RuntimeError(
                    f"nao consegui abrir o Chrome no perfil {user_data_dir}. "
                    "Se houver uma janela aberta nesse perfil, feche-a e tente "
                    "de novo.") from exc
            ctx = abrir(p)
        try:
            yield ctx
        finally:
            with contextlib.suppress(Exception):
                ctx.close()


def pagina(ctx):
    """Reusa a aba que o Chrome ja abriu em vez de criar uma segunda."""
    return ctx.pages[0] if ctx.pages else ctx.new_page()


# O que conta como "a pagina montou": qualquer conteudo real do app.
CONTEUDO_HIDRATADO = ('[contenteditable="true"], video, a[href*="/space/"], '
                      'button.submit-btn')


def esperar_hidratacao(page, limite: float = 45.0) -> bool:
    """Espera a SPA montar de verdade, em vez de dormir um tempo fixo.

    Deep-link (`goto` direto num /en/space/<id>) hidrata MUITO mais devagar que
    navegar por dentro do app: medimos 18 s ate aparecer conteudo. Uma pausa
    fixa ou e curta demais (e o seletor "nao existe") ou longa demais em toda
    chamada.

    Pronto = existe conteudo real na tela. NAO exigimos que os spinners sumam:
    a pagina de Spaces mantem pelo menos um `.animate-spin` permanente (carga
    preguicosa dos cards), entao "zero spinners" nunca acontecia — a espera
    queimava o limite inteiro em toda navegacao e ainda reportava False, o que
    fez o worker concluir que a sessao tinha caido.
    """
    fim = time.time() + limite
    while time.time() < fim:
        try:
            if page.locator(CONTEUDO_HIDRATADO).count() > 0:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# --------------------------------------------------------------------- ritmo
def pausa_humana(rng: random.Random | None = None,
                 minimo: float = 0.4, maximo: float = 1.6) -> None:
    """Intervalo irregular entre acoes.

    Nao e so furtividade: e nao martelar um servico gratuito. Um bot que clica
    em 40 ms e obvio; um que espera sempre 1.000 ms tambem.
    """
    rng = rng or random
    time.sleep(rng.uniform(minimo, maximo))


# Acima disto, digitar caractere a caractere deixa de parecer humano e passa a
# parecer paciencia sobre-humana: 650 chars a ~90 ms sao quase um minuto batendo
# tecla. Gente cola prompt longo.
LIMIAR_COLAR = 80


def digitar(locator, texto: str, rng: random.Random | None = None) -> None:
    """Digita caractere a caractere.

    `fill()` injeta o valor de uma vez e nao dispara a sequencia de eventos de
    teclado que um formulario observa; `type()` com delay dispara. Use para
    campo curto (login); para prompt longo use `escrever`.
    """
    rng = rng or random
    locator.click()
    pausa_humana(rng, 0.15, 0.45)
    locator.type(texto, delay=rng.uniform(45, 130))


def escrever(page, locator, texto: str, rng: random.Random | None = None) -> None:
    """Texto longo entra como colagem; texto curto, tecla a tecla.

    `insert_text` emite UM evento de input com o texto inteiro — que e
    exatamente o que o navegador faz num Ctrl+V. Funciona em contenteditable,
    onde `fill()` as vezes nao dispara os eventos que o Vue escuta.
    """
    rng = rng or random
    locator.click()
    pausa_humana(rng, 0.2, 0.6)
    if len(texto) < LIMIAR_COLAR:
        locator.type(texto, delay=rng.uniform(45, 130))
        return
    page.keyboard.insert_text(texto)
    pausa_humana(rng, 0.3, 0.8)
