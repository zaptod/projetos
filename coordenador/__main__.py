# -*- coding: utf-8 -*-
"""CLI do coordenador. Instalar so cria a tarefa quando chamado explicitamente."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .estado import ler_estado
from .supervisor import Supervisor

NOME = "NeuralFights_coordenador"
CMD = Path(r"E:\projetos\coordenador.cmd")
VBS = '''If WScript.Arguments.Count < 1 Then WScript.Quit 2
Set shell = CreateObject("WScript.Shell")
WScript.Quit shell.Run("cmd.exe /c """ & WScript.Arguments(0) & """", 0, True)
'''


def xml_tarefa(comando: str = r"C:\Windows\System32\wscript.exe",
               argumentos: str = r"//B //Nologo %LOCALAPPDATA%\neural-fights\oculto.vbs E:\projetos\coordenador.cmd") -> str:
    """XML importavel: logon, recuperacao persistente e bateria permitida."""
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><ExecutionTimeLimit>PT0S</ExecutionTimeLimit><RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><Enabled>true</Enabled></Settings>
  <Actions Context="Author"><Exec><Command>{comando}</Command><Arguments>{argumentos}</Arguments><WorkingDirectory>E:\\projetos</WorkingDirectory></Exec></Actions>
</Task>'''


def instalar(rodar=subprocess.run):
    """Materializa o lancador e importa a tarefa. Nunca e chamado sozinho."""
    CMD.write_text('@echo off\r\ncd /d E:\\projetos\r\nC:\\Python314\\python.exe -u -X utf8 -m coordenador rodar\r\n', encoding="ascii")
    vbs = Path(os.environ.get("LOCALAPPDATA", "")) / "neural-fights" / "oculto.vbs"
    if not vbs.is_file():
        vbs.parent.mkdir(parents=True, exist_ok=True)
        vbs.write_text(VBS, encoding="ascii", newline="\r\n")
    xml = Path(__file__).with_name("coordenador-tarefa.xml")
    xml.write_text(xml_tarefa(), encoding="utf-16")
    try:
        rodar(["schtasks", "/create", "/tn", NOME, "/xml", str(xml), "/f"], check=True)
    finally:
        try:
            xml.unlink()
        except OSError:
            pass


def remover(rodar=subprocess.run):
    rodar(["schtasks", "/delete", "/tn", NOME, "/f"], check=True)


def tarefas_antigas(ligar, rodar=subprocess.run):
    for nome in ("NeuralFights_app_celular", "NeuralFights_bot_telegram", "NeuralFights_vila_flutuante"):
        rodar(["schtasks", "/change", "/tn", nome, "/enable" if ligar else "/disable"], check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m coordenador")
    sub = parser.add_subparsers(dest="acao", required=True)
    sub.add_parser("rodar")
    sub.add_parser("status")
    reiniciar = sub.add_parser("reiniciar")
    reiniciar.add_argument("servico", choices=("app", "bot", "carteiro", "vila"))
    sub.add_parser("instalar-tarefa")
    sub.add_parser("remover-tarefa")
    sub.add_parser("desligar-tarefas-antigas")
    sub.add_parser("religar-tarefas-antigas")
    args = parser.parse_args(argv)
    if args.acao == "rodar":
        from remoto.orquestrador import aplicado, pendentes
        return Supervisor(comandos=pendentes, aplicar=aplicado).rodar()
    if args.acao == "status":
        import json
        print(json.dumps(ler_estado(), ensure_ascii=False, indent=2))
    elif args.acao == "reiniciar":
        s = Supervisor()
        s.reiniciar_servico(args.servico)
        print("ok")
    elif args.acao == "instalar-tarefa":
        instalar()
    elif args.acao == "remover-tarefa":
        remover()
    else:
        tarefas_antigas(args.acao == "religar-tarefas-antigas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
