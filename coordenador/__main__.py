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


def _sid_do_usuario() -> str:
    """O SID de quem instala: o schtasks recusa LogonTrigger/Principal sem UserId."""
    try:
        saida = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True,
                               text=True, check=True).stdout.strip()
        return saida.split(",")[-1].strip().strip('"')
    except (OSError, subprocess.CalledProcessError, IndexError):
        return ""


def xml_tarefa(comando: str = r"C:\Windows\System32\wscript.exe",
               argumentos: str | None = None, sid: str | None = None) -> str:
    """XML importavel: logon + a cada 5 min (a trava unica impede o segundo),
    recuperacao persistente e bateria permitida. Caminhos sem %VAR%: o
    Agendador nao expande variavel em Arguments (01/10: a 1a versao nao subia)."""
    if argumentos is None:
        vbs = Path(os.environ.get("LOCALAPPDATA", "")) / "neural-fights" / "oculto.vbs"
        argumentos = f'//B //Nologo "{vbs}" "E:\\projetos\\coordenador.cmd"'
    sid = _sid_do_usuario() if sid is None else sid
    usuario = f"<UserId>{sid}</UserId>" if sid else ""
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><Enabled>true</Enabled>{usuario}</LogonTrigger><TimeTrigger><StartBoundary>2026-10-01T00:00:00</StartBoundary><Repetition><Interval>PT5M</Interval></Repetition><Enabled>true</Enabled></TimeTrigger></Triggers>
  <Principals><Principal id="Author">{usuario}<LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><ExecutionTimeLimit>PT0S</ExecutionTimeLimit><RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled></Settings>
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


def montar() -> Supervisor:
    """O supervisor de producao: comandos do app, o cerebro (Codex so leitura)
    e o vigia de trabalho, que usa o mesmo criterio de momento seguro e pede
    o reinicio ao proprio supervisor; e a esteira de sprites (palco e vila),
    um `ciclo` (anda tudo e mantem a producao cheia) a cada 5 min."""
    from remoto.orquestrador import aplicado, aplicar_pelo_servidor, pendentes

    from . import cerebro
    from . import pedidos
    from .vigia_trabalho import VigiaTrabalho
    from .equipe import GerenteEquipe
    from .supervisor import ciclo_das_esteiras
    from ferramentas.obsidian import atualizar_automaticamente
    from ias.assembleia import avancar as avancar_assembleia
    # 04/10/2026: TODO comando do app e aplicado no pulso (capacidade, fila,
    # parar, modelos; a mensagem vira pedido), sem a sessao do VS Code
    s = Supervisor(comandos=pendentes, aplicar=aplicado, aplicar_app=aplicar_pelo_servidor,
                   cerebro=cerebro.atender, pedidos=pedidos.passo,
                   conversa=pedidos.atender_conversa,
                   esteira=ciclo_das_esteiras, assembleia=avancar_assembleia,
                   obsidian=atualizar_automaticamente)
    s.vigia_trabalho = VigiaTrabalho(
        avisar=s.avisar, evento=lambda tipo, texto: s.evento("", tipo, texto),
        seguro=lambda: s.seguro(""), pedir_reinicio=s.pedir_reinicio)
    s.gerente_equipe = GerenteEquipe(avisar=s.avisar,
                                     evento=lambda tipo, texto: s.evento("", tipo, texto))
    # a resposta final de um pedido vai tambem ao Telegram, de onde quer que
    # ele tenha vindo
    pedidos.MESA.avisar = s.avisar
    # as respostas do Grimorio sao lidas pelo SERVIDOR (04/10/2026), e o
    # desfecho das acoes da lista branca vai ao diario (05/10/2026)
    pedidos._ligar_producao()
    return s


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m coordenador")
    sub = parser.add_subparsers(dest="acao", required=True)
    sub.add_parser("rodar")
    sub.add_parser("status")
    pedir = sub.add_parser("pedir", help="registra trabalho para o passo da Mesa despachar")
    pedir.add_argument("texto")
    pedir.add_argument("--permitido", action="append", default=[])
    pedir.add_argument("--ia", choices=("codex", "claude"), default="codex")
    pedir.add_argument("--titulo", default="")
    pedir.add_argument("--tarefa", help="arquivo com o complemento da tarefa")
    reiniciar = sub.add_parser("reiniciar")
    reiniciar.add_argument("servico", choices=("app", "bot", "carteiro", "vila"))
    sub.add_parser("instalar-tarefa")
    sub.add_parser("remover-tarefa")
    sub.add_parser("desligar-tarefas-antigas")
    sub.add_parser("religar-tarefas-antigas")
    reabrir = sub.add_parser("reabrir-pedido",
                             help="devolve um pedido falhou/parado para 'esperando'")
    reabrir.add_argument("id", nargs="+")
    reabrir.add_argument("--motivo", default="reaberto pelo orquestrador")
    reabrir.add_argument("--continuacao", default=None,
                         help="texto que vai ao mesmo trabalhador (o caminho novo)")
    reavaliar = sub.add_parser("reavaliar-pedido",
                               help="passa a regra do DESFECHO num pedido 'entregue' antigo")
    reavaliar.add_argument("id", nargs="+")
    args = parser.parse_args(argv)
    if args.acao == "pedir":
        from . import pedidos
        texto = args.texto
        if args.tarefa:
            try:
                complemento = Path(args.tarefa).read_text(encoding="utf-8")
            except OSError as exc:
                print(f"recusado: não li a tarefa: {exc}", file=sys.stderr)
                return 3
            texto += "\n\n" + complemento
        try:
            pedido = pedidos.contratar(texto, "chat", cargo="orquestrador",
                                       permitidos=args.permitido or None, ia=args.ia,
                                       titulo=args.titulo or None)
        except ValueError as exc:
            print(f"recusado: {exc}", file=sys.stderr)
            return 3
        print(pedido["id"])
        return 0
    if args.acao == "rodar":
        return montar().rodar()
    if args.acao in ("reabrir-pedido", "reavaliar-pedido"):
        from . import pedidos
        codigo = 0
        for ident in args.id:
            try:
                if args.acao == "reabrir-pedido":
                    p = pedidos.reabrir(ident, args.motivo, args.continuacao)
                else:
                    p = pedidos.reavaliar(ident)
                print(f"{ident}: {p['situacao']}" + (f" ({p['motivo']})" if p.get("motivo") else ""))
            except (KeyError, ValueError) as exc:
                print(f"{ident}: {exc}")
                codigo = 1
        return codigo
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
