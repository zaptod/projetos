# -*- coding: utf-8 -*-
"""O que o vigia e o gravador dividem: onde mora o espelho, onde fica o
estado e QUANDO e permitido fazer coisa pesada (npm ci, npm test, gravacao).

Coisa pesada tem duas proibicoes (pedido do orquestrador, 19/10/2026):

  - o League of Legends aberto: o Adrian joga, e build ou gravacao com o
    jogo aberto derruba o FPS dele (e o nosso tempo de render dobra);
  - de :19 a :55 das horas de postagem (`post-18` a `post+18`, pela grade de
    `random_builds/builds/grade.py`): a publicacao abre navegador e sobe
    video nessa janela, e ja perdemos horario por maquina disputada.

`git fetch` e o avanco fast-forward NAO sao pesados: o vigia faz sempre.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

# Espelho de LEITURA da main do Adrian. Nunca commitar, empurrar nem editar.
ESPELHO = Path(os.environ.get("NF_BLUELOCK_ESPELHO") or r"E:\BLUE-Lock-project")
REMOTO = "origin"
RAMO = "main"
URL = "https://github.com/zaptod/BLUE-Lock-project"

# As margens da regra "nada pesado de :19 a :55" para postagens em :37.
ANTES_MIN = 18
DEPOIS_MIN = 18

# O executavel do jogo (a partida em si). O cliente parado nao pesa; a
# partida, sim — e e ela que o Adrian nao quer disputada.
JOGO = "League of Legends.exe"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def runtime_dir() -> Path:
    """O runtime do projeto (fora do git). Os testes o trocam pela variavel."""
    isolado = os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR")
    if isolado:
        return Path(isolado)
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "neural-fights"


def pasta() -> Path:
    destino = runtime_dir() / "bluelock"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def league_aberto(rodar=subprocess.run) -> bool:
    """O jogo esta rodando? Na duvida (tasklist falhou), responde True:
    adiar um teste custa 30 min; atrapalhar a partida dele, nao."""
    try:
        saida = rodar(["tasklist", "/FI", f"IMAGENAME eq {JOGO}", "/NH", "/FO", "CSV"],
                      capture_output=True, timeout=20, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return True
    texto = (getattr(saida, "stdout", b"") or b"")
    if isinstance(texto, bytes):
        texto = texto.decode("oem", "replace") if os.name == "nt" else texto.decode("utf-8", "replace")
    if getattr(saida, "returncode", 1) != 0:
        return True
    return JOGO.lower() in texto.lower()


def janela_das_postagens(agora: datetime) -> tuple[bool, str]:
    """(dentro, texto) para a janela larga, de `post-18` a `post+18` min."""
    from builds import janela
    dentro, texto, _ate = janela.em_janela(agora, antes=ANTES_MIN, depois=DEPOIS_MIN,
                                           olhar_voo=False)
    return dentro, texto


def pode_pesado(agora: datetime | None = None, *, league=league_aberto,
                janela=janela_das_postagens) -> tuple[bool, str]:
    """(pode, motivo). Motivo vazio quando pode."""
    agora = agora or datetime.now()
    try:
        dentro, texto = janela(agora)
    except Exception as exc:                                   # noqa: BLE001
        return False, f"não consegui ler a grade ({type(exc).__name__}: {exc})"
    if dentro:
        return False, texto
    try:                                  # publicacao em voo tambem barra
        from builds import janela as central
        if central.publicacao_em_voo():
            return False, "publicação em andamento (postar.py vivo)"
    except Exception:                                          # noqa: BLE001
        pass
    if league():
        return False, "League of Legends aberto"
    return True, ""
