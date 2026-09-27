# -*- coding: utf-8 -*-
"""As tarefas do Agendador ainda abrem janela preta? SO LEITURA.

Em 17/09/2026 as 25 tarefas do projeto (`NeuralFights_bot_telegram`,
`NeuralFights_postar_HH`, `Historias_auto_HH`) passaram a abrir o .cmd por

    wscript.exe //B //Nologo "%LOCALAPPDATA%\\neural-fights\\oculto.vbs" "<.cmd>"

que roda o .cmd sem console e espera ele terminar. Este modulo confere se
continua assim — e ha dois jeitos concretos de deixar de estar:

  VOLTOU O CONSOLE  os instaladores (`postar.py --instalar`,
                    `remoto --instalar`, `main.py auto --instalar`) recriam
                    as tarefas apontando para o .cmd direto.
  QUEBROU           o `oculto.vbs` (ou o .cmd) sumiu: a tarefa dispara e
                    falha sem janela nenhuma para mostrar o erro — pior que
                    a janela preta.

Nada aqui muda tarefa: so `Get-ScheduledTask`, e `is_file()` nos caminhos.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

PREFIXOS = ("NeuralFights_", "Historias_auto")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_PS_LER = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    "@(Get-ScheduledTask | Where-Object { "
    + " -or ".join(f"$_.TaskName -like '{p}*'" for p in PREFIXOS)
    + " } | ForEach-Object { [pscustomobject]@{ "
    "Nome=$_.TaskName; Acoes=@($_.Actions).Count; "
    "Executa=$_.Actions[0].Execute; Argumentos=$_.Actions[0].Arguments; "
    "Pasta=$_.Actions[0].WorkingDirectory } }) | ConvertTo-Json -Compress")

_PARTES = re.compile(r'"([^"]*)"|(\S+)')


def ler_tarefas(rodar=subprocess.run, timeout: float = 60) -> list | None:
    """As tarefas do projeto. None quando nao deu para perguntar."""
    if os.name != "nt":
        return None
    try:
        feito = rodar(["powershell", "-NoProfile", "-NonInteractive",
                       "-Command", _PS_LER], capture_output=True,
                      timeout=timeout, creationflags=SEM_JANELA)
    except (OSError, subprocess.SubprocessError):
        return None
    texto = feito.stdout.decode("utf-8", errors="replace").strip()
    if not texto:
        return [] if feito.returncode == 0 else None
    try:
        dados = json.loads(texto)
    except ValueError:
        return None
    return [dados] if isinstance(dados, dict) else list(dados)


def _partes(argumentos: str) -> list[str]:
    return [a or b for a, b in _PARTES.findall(str(argumentos or ""))]


def _existe(caminho: str) -> bool:
    return Path(os.path.expandvars(caminho)).is_file()


def examinar_uma(tarefa: dict, existe=None) -> dict:
    """{nome, estado, motivo, alvo}. estado: oculta|console|quebrada|desconhecida."""
    existe = existe or _existe
    nome = str(tarefa.get("Nome") or "?")
    executa = str(tarefa.get("Executa") or "").strip().strip('"')
    programa = Path(os.path.expandvars(executa)).name.lower()
    partes = _partes(tarefa.get("Argumentos"))
    extra = ("" if int(tarefa.get("Acoes") or 1) == 1
             else f" (e mais {int(tarefa['Acoes']) - 1} acao(oes) nao olhada(s))")

    def ficha(estado, motivo, alvo=""):
        return {"nome": nome, "estado": estado, "motivo": motivo + extra,
                "alvo": alvo}

    if programa in ("wscript.exe", "wscript"):
        opcoes = {p.lower() for p in partes if p.startswith("//")}
        resto = [p for p in partes if not p.startswith("//")]
        script = next((p for p in resto if p.lower().endswith(".vbs")), "")
        alvo = next((p for p in reversed(resto)
                     if p.lower().endswith((".cmd", ".bat"))), "")
        if not script:
            return ficha("desconhecida", "wscript sem .vbs", alvo)
        if not existe(script):
            return ficha("quebrada", f"o lançador {script} não existe", alvo)
        if alvo and not existe(alvo):
            return ficha("quebrada", f"o {alvo} não existe", alvo)
        if "//b" not in opcoes:
            return ficha("oculta", "wscript sem //B (erro de script abriria "
                                   "caixa de diálogo)", alvo)
        return ficha("oculta", "wscript + oculto.vbs", alvo)
    if programa == "pythonw.exe":
        return ficha("oculta", "pythonw (sem console)",
                     partes[-1] if partes else "")
    if programa.endswith((".cmd", ".bat")) or programa in (
            "cmd.exe", "python.exe", "cscript.exe", "powershell.exe"):
        return ficha("console", "abre janela preta", executa)
    return ficha("desconhecida", f"não reconheço {executa or 'a ação'}",
                 executa)


def examinar(tarefas: list | None, existe=None) -> dict:
    """O resumo que a janela mostra no selo."""
    if tarefas is None:
        return {"lido": False, "total": 0, "itens": [], "ok": None,
                "selo": "tarefas: ?", "problemas": []}
    itens = sorted((examinar_uma(t, existe) for t in tarefas),
                   key=lambda i: i["nome"])
    problemas = [i for i in itens if i["estado"] != "oculta"]
    ocultas = len(itens) - len(problemas)
    if not itens:
        selo = "sem tarefas no Agendador"
    elif not problemas:
        selo = f"tarefas ocultas ✓ {ocultas}/{len(itens)}"
    else:
        quebradas = sum(1 for i in problemas if i["estado"] == "quebrada")
        console = sum(1 for i in problemas if i["estado"] == "console")
        partes = []
        if quebradas:
            partes.append(f"{quebradas} quebrada(s)")
        if console:
            partes.append(f"{console} com console")
        resto = len(problemas) - quebradas - console
        if resto:
            partes.append(f"{resto} estranha(s)")
        selo = "tarefas ⚠ " + ", ".join(partes)
    return {"lido": True, "total": len(itens), "itens": itens,
            "ok": not problemas, "selo": selo, "problemas": problemas}


def descrever(resumo: dict) -> str:
    """Texto agrupado: 10 `postar_HH` iguais viram uma linha."""
    if not resumo.get("lido"):
        return "não consegui ler o Agendador (Get-ScheduledTask falhou)."
    grupos: dict = {}
    for item in resumo["itens"]:
        chave = (item["estado"], item["motivo"], item["alvo"])
        grupos.setdefault(chave, []).append(item["nome"])
    marcas = {"oculta": "ok", "console": "CONSOLE", "quebrada": "QUEBRADA",
              "desconhecida": "?"}
    linhas = []
    for (estado, motivo, alvo), nomes in sorted(
            grupos.items(), key=lambda g: (g[0][0] == "oculta", g[0])):
        titulo = nomes[0] if len(nomes) == 1 else \
            f"{len(nomes)} tarefas ({', '.join(nomes)})"
        linhas.append(f"[{marcas[estado]}] {titulo}")
        linhas.append(f"    {motivo}" + (f" -> {alvo}" if alvo else ""))
    linhas.append("")
    linhas.append(resumo["selo"])
    return "\n".join(linhas)


__all__ = ["descrever", "examinar", "examinar_uma", "ler_tarefas"]
