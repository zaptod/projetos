"""Diagnostico: "esta tudo certo com o gerador de video?".

As falhas aqui sao silenciosas por natureza. O Digen faz um deploy, um seletor
para de casar, e nada avisa - a fila so para de andar. O login expira e os jobs
comecam a falhar um por um. Por isso o diagnostico e dividido em dois:

  local   - sem abrir browser: dependencias, perfil, config, fila, orfaos.
  online  - abre o Chrome e confere o que so o site pode responder: a sessao
            ainda vale, quantos creditos existem e, principalmente, se cada
            lista de seletores AINDA CASA com a pagina de verdade.

O `online` e o que pega deploy do Digen antes de a fila travar.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import config, history, queue, selectors

OK, AVISO, ERRO = "ok", "aviso", "erro"

# Listas de seletores conferidas contra a pagina real. As de login ficam de
# fora: elas so existem quando NAO estamos logados, e nesse caso a checagem de
# sessao ja acusa.
LISTAS_ONLINE = (
    ("sessao viva", "SESSAO_VIVA", ERRO),
    ("New Space", "BOTAO_NOVO_ESPACO", ERRO),
    ("campo de prompt", "CAMPO_PROMPT", ERRO),
    ("botao de enviar", "BOTAO_GERAR", ERRO),
    # ERRO, nao aviso: sem trocar o modelo o video sai do modelo errado, o que
    # gasta uma geracao e entrega outra coisa.
    ("botao de modelo", "BOTAO_MODELO", ERRO),
    ("proporcao", "BOTAO_ASPECTO", AVISO),
    ("duracao", "BOTAO_DURACAO", AVISO),
    ("resolucao", "BOTAO_RESOLUCAO", AVISO),
    ("creditos", "CREDITOS", AVISO),
)

# Job parado mais que isto provavelmente nao vai andar sozinho.
HORAS_PARADO = 3.0


def _check(nome: str, estado: str, detalhe: str) -> dict:
    return {"nome": nome, "estado": estado, "detalhe": detalhe}


def _idade_horas(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        quando = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - quando).total_seconds() / 3600


# ------------------------------------------------------------------- local
def _chrome_instalado() -> Path | None:
    """`channel="chrome"` usa o Chrome do sistema - sem ele nada abre."""
    candidatos = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Google/Chrome/Application/chrome.exe",
    ]
    for caminho in candidatos:
        if caminho.is_file():
            return caminho
    achado = shutil.which("chrome") or shutil.which("google-chrome")
    return Path(achado) if achado else None


def checar_local() -> list[dict]:
    checks: list[dict] = []

    try:
        import patchright  # noqa: F401
        checks.append(_check("patchright", OK, "instalado"))
    except ImportError:
        checks.append(_check("patchright", ERRO,
                             "faltando - `pip install -r requirements.txt`"))

    chrome = _chrome_instalado()
    checks.append(_check("Chrome do sistema", OK if chrome else ERRO,
                         str(chrome) if chrome else
                         "nao encontrado - `patchright install chrome`"))

    faltando = [b for b in ("ffmpeg", "ffprobe") if not shutil.which(b)]
    checks.append(_check("ffmpeg/ffprobe", ERRO if faltando else OK,
                         f"faltando: {', '.join(faltando)}" if faltando
                         else "no PATH"))

    perfil = config.profile_dir()
    cookies = perfil / "Default" / "Network" / "Cookies"
    tem_cookies = cookies.is_file()
    if tem_cookies:
        idade = (datetime.now().timestamp() - cookies.stat().st_mtime) / 86400
        checks.append(_check("perfil do browser", OK,
                             f"cookies de {idade:.1f} dia(s) atras"))
    else:
        checks.append(_check("perfil do browser", AVISO,
                             "sem cookies gravados - rode `identity login`"))

    # Credencial ausente COM perfil logado e o estado normal, nao um alerta.
    # Um check que fica amarelo para sempre so ensina a ignorar amarelo.
    credenciais = config.credentials_path()
    if credenciais.is_file():
        checks.append(_check("credenciais", OK, str(credenciais)))
    elif tem_cookies:
        checks.append(_check("credenciais", OK,
                             "sem arquivo - o perfil logado basta"))
    else:
        checks.append(_check("credenciais", AVISO,
                             "sem arquivo e sem perfil logado"))

    try:
        ajustes = config.settings()
        alvo = int(ajustes.get("render_timeout", 0))
        mediana = history.resumo().get("espera_mediana_s")
        detalhe = f"render_timeout={alvo}s"
        estado = OK
        if mediana and alvo and alvo < mediana * 1.5:
            # A fila do Digen varia muito; timeout perto da mediana faz o job
            # estourar com o video ainda vindo e cair na retomada toda vez.
            estado = AVISO
            detalhe += f" - apertado para a espera mediana de {mediana:.0f}s"
        checks.append(_check("config/identity.json", estado, detalhe))

        # Modelo com nome errado so apareceria na hora de gerar, e ai o job
        # falha. Como o nome tem que bater EXATO com o item do menu, um typo
        # ("Real motion 3.5") quebraria tudo em silencio ate rodar.
        modelo = ajustes.get("modelo", "")
        if not modelo:
            checks.append(_check("modelo", AVISO,
                                 "nao definido - usa o padrao da conta"))
        elif modelo in selectors.MODELOS_CONHECIDOS:
            checks.append(_check(
                "modelo", OK,
                f"{modelo} (botao mostra {selectors.abreviar_modelo(modelo)})"))
        else:
            checks.append(_check(
                "modelo", ERRO,
                f"{modelo!r} nao esta na lista conhecida do Digen - confira o "
                "nome EXATO com `identity probe`"))
    except Exception as exc:
        checks.append(_check("config/identity.json", ERRO, str(exc)[:120]))

    from .browser import _chrome_do_perfil
    orfaos = _chrome_do_perfil(str(perfil))
    checks.append(_check(
        "Chrome orfao", AVISO if orfaos else OK,
        f"{len(orfaos)} processo(s) segurando o perfil - o proximo worker "
        "encerra sozinho" if orfaos else "nenhum"))

    checks.extend(_checar_presets())
    checks.extend(_checar_prompts())
    checks.extend(_checar_fila())
    return checks


def _checar_presets() -> list[dict]:
    """A duracao pedida por slot bate com a janela da montagem?

    Pedir 15 s para um slot que a edicao corta em 4 gera material para o lixo,
    e pedir menos que o minimo entrega uma cena curta demais. Nenhum dos dois
    aparece como erro em lugar nenhum: o video so sai estranho.
    """
    from ..generation.session_generator import load_config
    from . import slots
    from .worker import preset_do_slot
    try:
        ajustes = config.settings()
        janelas = load_config("editing.json").get("identity_slots", {})
    except Exception as exc:
        return [_check("presets", ERRO, str(exc)[:110])]

    linhas, problemas = [], []
    for slot in slots.SLOTS:
        if slots.midia(slot) != slots.VIDEO:
            # Imagem nao tem duracao. Reportar "character=5s" para um slot que
            # virou PNG e ruido que ensina a ignorar o diagnostico.
            linhas.append(f"{slot}=imagem")
            continue
        preferencia = preset_do_slot(ajustes, "duracao", slot)
        primeiro = (preferencia[0] if isinstance(preferencia, list)
                    else preferencia)
        if not primeiro:
            problemas.append(f"{slot}: sem duracao declarada")
            continue
        linhas.append(f"{slot}={primeiro}")
        janela = janelas.get(slot)
        segundos = selectors.valor_numerico(str(primeiro))
        if not janela or segundos is None:
            continue          # "max": quem decide e o menu do modelo
        if segundos < janela["min"]:
            problemas.append(f"{slot}: pede {primeiro} e a montagem precisa de "
                             f"pelo menos {janela['min']}s")
        elif segundos > janela["max"] + 3:
            problemas.append(f"{slot}: pede {primeiro} e a montagem corta em "
                             f"{janela['max']}s")

    checks = [_check("midia e duracao por slot", AVISO if problemas else OK,
                     ("; ".join(problemas) if problemas
                      else " ".join(linhas))[:120])]
    from . import provedores
    checks.append(_check(
        "provedores", OK,
        " ".join(f"{p}:{'+'.join(provedores.slots_de(p)) or 'nenhum'}"
                 for p in provedores.TODOS)))
    junto = bool(config.settings().get("espaco_por_geracao", True))
    checks.append(_check(
        "space por build", OK,
        "os tres clipes no mesmo space" if junto
        else "um space por clipe (espaco_por_geracao=false)"))
    return checks


def _checar_prompts() -> list[dict]:
    """Os tres templates montam de verdade?

    Placeholder com nome errado em `prompts.weapon` so apareceria na hora em
    que aquele job rodasse - depois de esperar o browser, o login e a fila do
    Digen. Aqui custa um sorteio em memoria.
    """
    from . import slots
    try:
        from ..generation.session_generator import SessionGenerator
        from .prompt import build_prompt
        generation = SessionGenerator().generate(
            seed=1, generation_id="generation_diagnostico")
    except Exception as exc:
        return [_check("prompts", ERRO, f"nao deu para montar: {str(exc)[:90]}")]

    checks, tamanhos = [], []
    for slot in slots.SLOTS:
        try:
            texto = build_prompt(generation, slot=slot)
        except Exception as exc:
            checks.append(_check(f"prompt {slot}", ERRO, str(exc)[:110]))
            continue
        if not texto.strip():
            checks.append(_check(f"prompt {slot}", ERRO, "vazio"))
            continue
        tamanhos.append(f"{slot}={len(texto)}")
    if not checks:
        checks.append(_check("prompts", OK, " ".join(tamanhos)))
    return checks


def _checar_fila() -> list[dict]:
    try:
        jobs = queue.listar()
    except Exception as exc:
        return [_check("fila", ERRO, f"ilegivel: {exc}")]

    por_estado: dict[str, int] = {}
    for job in jobs:
        por_estado[job["status"]] = por_estado.get(job["status"], 0) + 1

    falhados = [j for j in jobs if j["status"] == queue.FALHOU]
    checks = [_check("fila", AVISO if falhados else OK,
                     ", ".join(f"{v} {k}" for k, v in sorted(por_estado.items()))
                     or "vazia")]
    if falhados:
        ultimo = falhados[-1]
        checks.append(_check(
            "jobs desistidos", AVISO,
            f"{len(falhados)} - ultimo: {ultimo['generation_id']} "
            f"({str(ultimo.get('error') or '')[:70]})"))

    parados = [j for j in jobs
               if j["status"] in (queue.PENDENTE, queue.RODANDO)
               and (_idade_horas(j.get("updated_at")) or 0) > HORAS_PARADO]
    if parados:
        checks.append(_check(
            "jobs parados", AVISO,
            f"{len(parados)} sem avancar ha mais de {HORAS_PARADO:.0f}h: "
            + ", ".join(j["generation_id"] for j in parados[:4])))
    return checks


# ------------------------------------------------------------------ online
def checar_online(headless: bool = False) -> list[dict]:
    """Abre o browser e confere sessao, creditos e os seletores na pagina real."""
    from .browser import contexto_persistente, esperar_hidratacao, pagina
    from .client import DigenClient
    from .session import sessao_viva

    ajustes = config.settings()
    checks: list[dict] = []
    try:
        with contexto_persistente(headless=headless) as ctx:
            page = pagina(ctx)
            page.goto(selectors.URL_SPACES, wait_until="domcontentloaded",
                      timeout=int(float(ajustes.get("navigation_timeout", 60)) * 1000))
            esperar_hidratacao(page, float(ajustes.get("hydration_timeout", 45)))

            viva = sessao_viva(page, timeout=8.0)
            checks.append(_check("sessao no Digen", OK if viva else ERRO,
                                 "logada" if viva else
                                 "expirada - rode `identity login`"))

            desafio = selectors.encontrar(page, selectors.DESAFIO, timeout=2.0)
            if desafio is not None:
                checks.append(_check("desafio anti-bot", ERRO,
                                     "captcha/2FA na tela - resolva com "
                                     "`identity login`"))

            cliente = DigenClient(ctx, page, ajustes)

            # O que o composer mostra AGORA, para conferir contra a config.
            atual = cliente._modelo_atual()
            desejado = selectors.abreviar_modelo(ajustes.get("modelo", ""))
            if atual is None:
                checks.append(_check("modelo no composer", AVISO, "ilegivel"))
            else:
                checks.append(_check(
                    "modelo no composer",
                    OK if not desejado or atual == desejado else AVISO,
                    atual if not desejado or atual == desejado
                    else f"{atual}, mas a config pede {desejado} "
                         "(o worker troca antes de enviar)"))

            saldo = cliente.creditos(espera=25)
            if saldo is None:
                checks.append(_check("creditos", AVISO, "contador ilegivel"))
            else:
                checks.append(_check("creditos", ERRO if saldo <= 0 else OK,
                                     f"{saldo} disponivel(is)"))

            for rotulo, atributo, gravidade in LISTAS_ONLINE:
                candidatos = getattr(selectors, atributo)
                achou = selectors.encontrar(page, candidatos, timeout=2.0) is not None
                checks.append(_check(
                    f"seletor: {rotulo}", OK if achou else gravidade,
                    atributo if achou else
                    f"{atributo} nao casa mais - rode `identity probe`"))
    except Exception as exc:
        checks.append(_check("browser", ERRO, f"{type(exc).__name__}: {exc}"[:160]))
    return checks


# ---------------------------------------------------------------- relatorio
SIMBOLO = {OK: "OK  ", AVISO: "AVISO", ERRO: "ERRO"}


def imprimir(checks: list[dict], titulo: str) -> None:
    print(f"\n{titulo}")
    print("-" * len(titulo))
    for check in checks:
        print(f"  [{SIMBOLO[check['estado']]}] {check['nome']:<26} {check['detalhe']}")


def pior_estado(checks: list[dict]) -> str:
    estados = {c["estado"] for c in checks}
    if ERRO in estados:
        return ERRO
    return AVISO if AVISO in estados else OK
