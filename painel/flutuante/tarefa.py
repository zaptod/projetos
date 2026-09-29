# -*- coding: utf-8 -*-
"""A tarefa do Windows que mantem a Vila flutuante no ar — instalada daqui.

    python -m painel.flutuante.tarefa                 mostra o que faria (a seco)
    python -m painel.flutuante.tarefa --instalar      escreve o .cmd e cria a tarefa
    python -m painel.flutuante.tarefa --lancador      so reescreve o .cmd
    python -m painel.flutuante.tarefa --ajustar       reaplica os ajustes na
                                                      tarefa que ja existe
    python -m painel.flutuante.tarefa --desinstalar   remove a tarefa

POR QUE EXISTE. Ate 28/09/2026 a tarefa `NeuralFights_vila_flutuante` e o
`vila_flutuante.cmd` eram feitos A MAO, com o Python e a pasta desta maquina
escritos dentro: maquina refeita a partir do clone nao subia a Vila. Agora os
caminhos vem do ambiente de quem instala — o `pythonw.exe` ao lado do Python
que roda isto, e a raiz dos dados (a mesma que a janela le, ver
`caminhos.raiz_dos_dados`). Como o `bot.cmd` e o `postar.cmd`, o .cmd e
GERADO e fica fora do git. (Nao confundir com `tarefas.py`, que so CONFERE
as tarefas do projeto para a janela — e tem teste proibindo-o de criar.)

O QUE A TAREFA E, e cada pedaco tem motivo:

  - a cada 10 minutos, sem fim: se a Vila cair, volta em ate 10 min. No
    logon precisaria de terminal de administrador;
  - a acao e o `wscript` rodando o `oculto.vbs` com o .cmd — e o que impede
    a janela preta. NUNCA a tarefa direto no .cmd (volta o console): sem o
    `oculto.vbs`, este instalador RECUSA em vez de cair nisso;
  - os ajustes de bateria e de horario perdido de `builds.tarefas_windows`,
    os mesmos de todas as tarefas do projeto — MENOS o de acordar o PC.
    O `endurecer` liga o `WakeToRun` em todas; para uma janela, acordar a
    maquina de 10 em 10 minutos nao serve para nada (a tarefa do bot ja
    acorda do mesmo jeito). Decisao do Adrian (28/09/2026,
    `painel-e-vila/tarefa-da-vila-acorda-o-pc` = "tirar"). Por isso o
    `sem_acordar` roda SEMPRE DEPOIS do `endurecer`: na ordem inversa o
    `endurecer` religaria;
  - a GUARDA mora no .cmd: so lanca se nao houver Vila viva. A janela tem
    instancia unica, mas o segundo lancamento TRAZ A JANELA PARA A FRENTE de
    proposito (e o que faz o atalho funcionar); de 10 em 10 minutos isso
    roubaria o foco do dono o dia inteiro;
  - NA DUVIDA, NAO ABRE: se a consulta de processos falhar ou passar de 2
    min, o .cmd sai sem lancar e a proxima batida tenta de novo. Ate 28/09
    ele lancava — e lancar sem precisar e justamente o que rouba o foco.
"""
from __future__ import annotations

import argparse
import difflib
import os
import subprocess
import sys
from pathlib import Path

TAREFA = "NeuralFights_vila_flutuante"
NOME_DO_LANCADOR = "vila_flutuante.cmd"
MINUTOS = 10
# Quanto a consulta de processos pode levar antes de o .cmd desistir. O WMI
# desta maquina ja levou mais de um minuto para responder (medido em 28/09).
PRAZO_DA_CONSULTA_S = 120
# Decisao do Adrian (28/09/2026): a tarefa da Vila NAO acorda o PC.
ACORDA_O_PC = False
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def raiz() -> Path:
    """A pasta de onde a Vila roda: a mesma raiz que ela le."""
    from .caminhos import raiz_dos_dados
    return raiz_dos_dados()


def pythonw(executavel=None) -> Path:
    """O `pythonw.exe` ao lado do Python que roda isto (sem console)."""
    executavel = Path(executavel or sys.executable)
    if executavel.name.lower() == "pythonw.exe":
        return executavel
    irmao = executavel.with_name("pythonw.exe")
    if irmao.is_file():
        return irmao
    raise FileNotFoundError(
        f"nao achei o pythonw.exe ao lado de {executavel}: com o python.exe "
        "a Vila abriria com uma janela de console junto")


def caminho_do_lancador(pasta=None) -> Path:
    return Path(pasta or raiz()) / NOME_DO_LANCADOR


def _literal_ps(texto) -> str:
    """Literal PowerShell entre aspas simples (aspas dobradas por dentro)."""
    return "'" + str(texto).replace("'", "''") + "'"


def _para_cmd(texto: str) -> str:
    """`%` e especial num .cmd mesmo entre aspas: vira `%%`."""
    return texto.replace("%", "%%")


def comando_da_guarda(executavel: Path, pasta: Path) -> str:
    """O PowerShell que o .cmd roda: so lanca se nao houver Vila viva.

    As `\\"` em volta do filtro sao para o cmd: e o que mantem o `|` da
    linha DENTRO de aspas (fora delas o cmd o trataria como pipe).
    """
    return (
        "try { $viva = Get-CimInstance Win32_Process "
        "-Filter \\\"Name='pythonw.exe'\\\" "
        f"-OperationTimeoutSec {PRAZO_DA_CONSULTA_S} -ErrorAction Stop | "
        "Where-Object { $_.CommandLine -match "
        "'painel.flutuante|vila_flutuante' } } catch { exit 0 }; "
        "if (-not $viva) { Start-Process -FilePath "
        f"{_literal_ps(executavel)} -ArgumentList "
        "'-X','utf8','-m','painel.flutuante','--medio' -WorkingDirectory "
        f"{_literal_ps(pasta)} }}")


def texto_do_lancador(executavel: Path, pasta: Path) -> str:
    """O `vila_flutuante.cmd` inteiro, com CRLF."""
    linhas = [
        "@echo off",
        "rem Mantem a Vila flutuante no ar (janela do painel, sempre por cima).",
        f"rem Chamado pela tarefa {TAREFA} a cada {MINUTOS} min.",
        "rem GERADO por `python -m painel.flutuante.tarefa --instalar`: os",
        "rem caminhos vem do Python e da pasta de quem instalou. Nao edite a",
        "rem mao; rode o instalador de novo.",
        "rem",
        "rem SO ABRE SE NAO ESTIVER ABERTA. A janela ja tem instancia unica, mas o",
        "rem segundo lancamento TRAZ A JANELA PARA A FRENTE de proposito (e o que",
        "rem faz o atalho funcionar). Repetir isso de 10 em 10 minutos roubaria o",
        "rem foco da tela do Adrian o dia inteiro, entao a guarda mora aqui.",
        "rem NA DUVIDA, NAO ABRE: consulta que falha ou demora sai sem lancar.",
        "powershell -NoProfile -ExecutionPolicy Bypass -Command \""
        + _para_cmd(comando_da_guarda(executavel, pasta)) + "\"",
    ]
    return "\r\n".join(linhas) + "\r\n"


def _codificar(texto: str) -> bytes:
    """O cmd le o .cmd na pagina de codigo do console (OEM), nao em UTF-8."""
    try:
        return texto.encode("oem")
    except LookupError:                      # fora do Windows
        return texto.encode("utf-8")


def _decodificar(dados: bytes) -> str:
    try:
        return dados.decode("oem", "replace")
    except LookupError:
        return dados.decode("utf-8", "replace")


def escrever_lancador(executavel=None, pasta=None, destino=None) -> Path:
    """Escreve o .cmd (inteiro ou nada: a tarefa pode le-lo a qualquer hora)."""
    pasta = Path(pasta or raiz())
    destino = Path(destino or caminho_do_lancador(pasta))
    dados = _codificar(texto_do_lancador(pythonw(executavel), pasta))
    temporario = destino.with_name(destino.name + ".tmp")
    temporario.write_bytes(dados)
    os.replace(temporario, destino)
    return destino


def acao(lancador: Path, vbs=None) -> str:
    """O `/TR`: o .cmd pelo `wscript` + `oculto.vbs`, SEM janela preta.

    Sem o pacote `builds` (que sabe onde mora o `oculto.vbs`) levanta
    ImportError — e quem instala recusa, em vez de apontar a tarefa direto
    para o .cmd.
    """
    from builds import tarefas_windows
    return tarefas_windows.acao_oculta(lancador, vbs=vbs)


def _vbs_sem_escrever() -> Path:
    """Onde o `oculto.vbs` mora, sem cria-lo (para o modo a seco)."""
    from builds import tarefas_windows
    from builds.contas import runtime_dir
    return Path(runtime_dir()) / tarefas_windows.NOME_DO_VBS


def _schtasks(argumentos: list) -> subprocess.CompletedProcess:
    """`schtasks` com a saida decodificada na mao: ele escreve na pagina de
    codigo do console ("ÊXITO"), e o `text=True` (UTF-8) derrubava a thread
    leitora e perdia a mensagem."""
    feito = subprocess.run(["schtasks", *argumentos], capture_output=True,
                           timeout=60, creationflags=NO_WINDOW)
    return subprocess.CompletedProcess(
        feito.args, feito.returncode, _decodificar(feito.stdout or b""),
        _decodificar(feito.stderr or b""))


# So o `WakeToRun`: parte do conjunto que a tarefa JA tem (o `endurecer` ja
# passou), entao nada mais muda. `-Settings` com o proprio conjunto, como o
# `endurecer` faz, e nao `-InputObject` (que regrava o principal).
_SCRIPT_ACORDAR = """
$ErrorActionPreference = 'Stop'
$t = Get-ScheduledTask -TaskName @NOME@
$s = $t.Settings
$s.WakeToRun = @VALOR@
Set-ScheduledTask -TaskName @NOME@ -Settings $s | Out-Null
"""
_SCRIPT_CONSULTA = """
$ErrorActionPreference = 'Stop'
(Get-ScheduledTask -TaskName @NOME@).Settings.WakeToRun
"""


def _powershell(script: str) -> subprocess.CompletedProcess:
    """PowerShell sem janela, com o nome da tarefa embutido como literal
    (`-Command` engole o resto da linha: `$args` nao funciona) e a saida
    decodificada na mao (pagina de codigo do console)."""
    feito = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         script.replace("@NOME@", _literal_ps(TAREFA))],
        capture_output=True, timeout=60, creationflags=NO_WINDOW)
    return subprocess.CompletedProcess(
        feito.args, feito.returncode, _decodificar(feito.stdout or b""),
        _decodificar(feito.stderr or b""))


def sem_acordar() -> dict:
    """Desliga o `WakeToRun` da tarefa que ja existe (sem recria-la)."""
    valor = "$true" if ACORDA_O_PC else "$false"
    try:
        proc = _powershell(_SCRIPT_ACORDAR.replace("@VALOR@", valor))
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "mensagem": f"{type(exc).__name__}: {exc}"}
    return {"ok": proc.returncode == 0,
            "mensagem": " ".join((proc.stdout + proc.stderr).split())[:300]}


def acorda_o_pc():
    """Como a tarefa esta AGORA: True/False, ou None se nao deu para ler
    (tarefa ausente, PowerShell caido) — None nunca vira False."""
    try:
        proc = _powershell(_SCRIPT_CONSULTA)
    except (OSError, subprocess.SubprocessError):
        return None
    resposta = proc.stdout.strip().lower()
    if proc.returncode != 0 or resposta not in ("true", "false"):
        return None
    return resposta == "true"


def ajustar() -> dict:
    """Os ajustes de depois do /Create, NA ORDEM: o `endurecer` (bateria e
    horario perdido, e ele liga o acordar) e depois o `sem_acordar`.

    Serve a tarefa recem-criada e a que ja esta no ar: nao recria nada, entao
    a Vila viva nao e tocada."""
    try:
        from builds import tarefas_windows
        dura = tarefas_windows.endurecer(TAREFA)
    except Exception as exc:                                   # noqa: BLE001
        dura = {"ok": False, "mensagem": f"{type(exc).__name__}: {exc}"}
    acordar = sem_acordar()
    falhas = []
    if not dura.get("ok"):
        falhas.append(f"bateria e horario perdido: {dura.get('mensagem')}")
    if not acordar.get("ok"):
        falhas.append(f"tirar o acordar: {acordar.get('mensagem')}")
    return {"ok": not falhas, "mensagem": "; ".join(falhas)}


def instalada() -> bool:
    return _schtasks(["/Query", "/TN", TAREFA]).returncode == 0


def instalar(minutos: int = MINUTOS) -> dict:
    try:
        lancador = escrever_lancador()
        tr = acao(lancador)
    except (ImportError, OSError, UnicodeError) as erro:
        return {"tarefa": TAREFA, "ok": False,
                "mensagem": f"nao instalei: {type(erro).__name__}: {erro}"}
    proc = _schtasks(["/Create", "/TN", TAREFA, "/TR", tr, "/SC", "MINUTE",
                      "/MO", str(int(minutos)), "/RL", "LIMITED", "/F"])
    ficha = {"tarefa": TAREFA, "ok": proc.returncode == 0,
             "lancador": str(lancador), "acao": tr,
             "mensagem": (proc.stdout or proc.stderr or "").strip()}
    if ficha["ok"]:
        ajuste = ajustar()
        ficha["ajustada"] = bool(ajuste.get("ok"))
        if not ficha["ajustada"]:
            ficha["mensagem"] = (
                f"{ficha['mensagem']} (criada, mas os ajustes falharam: "
                f"{ajuste.get('mensagem')})").strip()
    return ficha


def desinstalar() -> dict:
    proc = _schtasks(["/Delete", "/TN", TAREFA, "/F"])
    return {"tarefa": TAREFA, "ok": proc.returncode == 0,
            "mensagem": (proc.stdout or proc.stderr or "").strip()}


def plano() -> dict:
    """O que `--instalar` faria, sem escrever nem criar nada."""
    pasta = raiz()
    destino = caminho_do_lancador(pasta)
    ficha = {"raiz": str(pasta), "lancador": str(destino)}
    try:
        novo = texto_do_lancador(pythonw(), pasta)
        ficha["pythonw"] = str(pythonw())
    except FileNotFoundError as erro:
        ficha["erro"] = str(erro)
        return ficha
    try:
        atual = _decodificar(destino.read_bytes())
    except OSError:
        atual = None
    ficha["lancador_igual"] = atual == novo
    ficha["diferenca"] = "".join(difflib.unified_diff(
        (atual or "").replace("\r\n", "\n").splitlines(keepends=True),
        novo.replace("\r\n", "\n").splitlines(keepends=True),
        "atual", "gerado")) if atual != novo else ""
    try:
        ficha["acao"] = acao(destino, vbs=_vbs_sem_escrever())
    except ImportError as erro:
        ficha["erro"] = (f"sem o pacote builds ({erro}): a tarefa abriria "
                         "janela preta, entao eu nao instalaria")
    ficha["tarefa_existe"] = instalada()
    if ficha["tarefa_existe"]:
        ficha["acorda_o_pc"] = acorda_o_pc()
        if ficha["acorda_o_pc"] is not None:
            ficha["acordar_igual"] = ficha["acorda_o_pc"] == ACORDA_O_PC
    return ficha


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="painel.flutuante.tarefa",
        description="a tarefa do Windows que mantem a Vila flutuante no ar")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--instalar", action="store_true",
                       help="escreve o .cmd e cria (ou recria) a tarefa")
    grupo.add_argument("--lancador", action="store_true",
                       help="so reescreve o .cmd; a tarefa fica como esta")
    grupo.add_argument("--ajustar", action="store_true",
                       help="reaplica os ajustes (bateria, horario perdido, "
                            "sem acordar o PC) na tarefa que ja existe, sem "
                            "recria-la")
    grupo.add_argument("--desinstalar", action="store_true",
                       help="remove a tarefa (o .cmd fica)")
    args = parser.parse_args(argv)

    if args.instalar:
        ficha = instalar()
        print(("ok: " if ficha["ok"] else "FALHOU: ") + ficha["mensagem"])
        return 0 if ficha["ok"] else 1
    if args.ajustar:
        ficha = ajustar()
        print("ok: ajustada" if ficha["ok"] else "FALHOU: " + ficha["mensagem"])
        return 0 if ficha["ok"] else 1
    if args.desinstalar:
        ficha = desinstalar()
        print(("ok: " if ficha["ok"] else "FALHOU: ") + ficha["mensagem"])
        return 0 if ficha["ok"] else 1
    if args.lancador:
        try:
            print(f"ok: {escrever_lancador()}")
        except (OSError, UnicodeError) as erro:
            print(f"FALHOU: {erro}")
            return 1
        return 0

    ficha = plano()
    print("A SECO — nada foi escrito nem criado.")
    for chave in ("raiz", "pythonw", "lancador", "acao", "tarefa_existe",
                  "lancador_igual", "acorda_o_pc", "acordar_igual"):
        if chave in ficha:
            print(f"  {chave}: {ficha[chave]}")
    if ficha.get("diferenca"):
        print("  o .cmd atual difere do que eu escreveria:")
        print(ficha["diferenca"].rstrip())
    if ficha.get("erro"):
        print(f"  ERRO: {ficha['erro']}")
        return 1
    print("  para aplicar: --instalar (tarefa e .cmd), --lancador (so o .cmd)"
          " ou --ajustar (so os ajustes da tarefa que ja existe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
