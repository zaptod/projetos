# -*- coding: utf-8 -*-
"""A tarefa do Windows que mantem o bot no ar.

O bot so avisa e so aceita comando enquanto o processo dele estiver rodando —
e em 08/09/2026 ele simplesmente NAO estava. O token estava guardado, o
celular pareado, os alertas ligados, e nada chegava: ninguem tinha ligado o
`python -m remoto` depois do ultimo boot. Alerta que depende de alguem lembrar
de ligar nao e alerta.

POR QUE A CADA 10 MINUTOS, E NAO NO LOGON. `/SC ONLOGON` precisa de terminal
de administrador (`Acesso negado` sem ele), e pedir elevacao para uma coisa
que tem que "so funcionar" e comecar errado. A batida de 10 em 10 minutos nao
precisa de nada disso E e mais forte: se o bot cair as 3 da manha, ele volta
sozinho as 3h10 — o ONLOGON so voltaria no proximo logon.

Subir seis bots por hora seria o desastre obvio, e por isso `python -m remoto`
tem trava de instancia unica: o segundo sai na hora dizendo que ja tem um no
ar. Isso tambem conserta um problema que ja existia — dois bots no mesmo token
brigam pelo `getUpdates` e comem as mensagens um do outro.

    python -m remoto --instalar     cria a tarefa
    python -m remoto --desinstalar  remove
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# `remoto/` e uma pasta da RAIZ do monorepo (nao esta instalada no workspace):
# ele so e importavel com a raiz como diretorio de trabalho, e e por isso que
# o lancador faz `cd` para ca antes de chamar `-m remoto`.
RAIZ = Path(__file__).resolve().parents[1]
TAREFA = "NeuralFights_bot_telegram"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def caminho_do_lancador() -> Path:
    return RAIZ / "bot.cmd"


def escrever_lancador(python: str | None = None) -> Path:
    """O .cmd que a tarefa chama.

    Redireciona a saida para arquivo pela mesma licao que custou 13 minutos de
    rodada travada no mesmo dia: escrever num console que ninguem esvazia
    bloqueia o processo para sempre, e um bot bloqueado parece um bot no ar.
    """
    destino = caminho_do_lancador()
    python = python or sys.executable
    saida = RAIZ / "outputs" / "bot.txt"
    saida.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        "@echo off\r\n"
        "rem Bot de Telegram (avisos + comandos do celular).\r\n"
        "rem Gerado por: python -m remoto --instalar\r\n"
        f'cd /d "{RAIZ}"\r\n'
        f'"{python}" -u -X utf8 -m remoto >> "{saida}" 2>&1\r\n',
        encoding="utf-8")
    return destino


def _schtasks(argumentos: list) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks"] + argumentos, capture_output=True,
                          text=True, timeout=60, creationflags=NO_WINDOW)


def instalar(minutos: int = 10) -> dict:
    lancador = escrever_lancador()
    proc = _schtasks(["/Create", "/TN", TAREFA, "/TR", f'"{lancador}"',
                      "/SC", "MINUTE", "/MO", str(int(minutos)),
                      "/RL", "LIMITED", "/F"])
    ficha = {"tarefa": TAREFA, "ok": proc.returncode == 0,
             "lancador": str(lancador),
             "mensagem": (proc.stdout or proc.stderr or "").strip()}
    if ficha["ok"]:
        # O bot e o que AVISA quando algo quebra. Ele nao pode ser a coisa que
        # o Windows recusa por estar na bateria — era exatamente o caso ate
        # 09/09/2026. Ver builds/tarefas_windows.py.
        try:
            from builds import tarefas_windows
            ajuste = tarefas_windows.endurecer(TAREFA)
        except Exception as exc:                               # noqa: BLE001
            ajuste = {"ok": False, "mensagem": f"{type(exc).__name__}: {exc}"}
        ficha["ajustada"] = ajuste["ok"]
        if not ajuste["ok"]:
            ficha["mensagem"] = (
                f"{ficha['mensagem']} (criada, mas os ajustes de bateria e de "
                f"horario perdido falharam: {ajuste['mensagem']})").strip()
    return ficha


def desinstalar() -> dict:
    proc = _schtasks(["/Delete", "/TN", TAREFA, "/F"])
    return {"tarefa": TAREFA, "ok": proc.returncode == 0,
            "mensagem": (proc.stdout or proc.stderr or "").strip()}


def instalada() -> bool:
    return _schtasks(["/Query", "/TN", TAREFA]).returncode == 0
