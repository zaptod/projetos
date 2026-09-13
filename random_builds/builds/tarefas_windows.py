# -*- coding: utf-8 -*-
"""Os tres ajustes que o `schtasks /Create` nao faz — e sem os quais a
tarefa some justamente no dia em que ela precisava rodar.

MEDIDO em 09/09/2026, nas dez tarefas do projeto (as 8 de historias, o bot do
Telegram e a de postagem). Todas estavam com os PADROES do Windows, e os tres
padroes sao hostis a uma maquina que publica sozinha:

    DisallowStartIfOnBatteries=True   na bateria, a tarefa RECUSA iniciar. E
                                      o resultado 0x800710E0 ("o operador ou
                                      administrador recusou a solicitacao")
                                      que aparecia em TODAS elas.
    StopIfGoingOnBatteries=True       se a maquina cair para bateria no meio,
                                      a tarefa e MORTA. Uma postagem leva
                                      minutos de navegador; um render leva uma
                                      hora.
    StartWhenAvailable=False          horario perdido (maquina desligada ou
                                      dormindo) NUNCA e recuperado. O pedido
                                      era "pelo menos um video novo por dia" —
                                      e com isto desligado, um cochilo as
                                      17:07 custa o dia inteiro, em silencio.

O `schtasks` da linha de comando nao expoe nenhum dos tres: quem cria a tarefa
por ali herda os padroes sem escolher. Por isso este passo vem DEPOIS do
/Create, e por isso ele mora aqui em vez de repetido nos tres lugares que
criam tarefa (`contos/pipeline/tarefas.py`, `ferramentas/postar.py` e
`remoto/tarefa.py`) — cada um esquecendo de um jeito diferente seria pior do
que nao ter.
"""
from __future__ import annotations

import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _aspas(texto: str) -> str:
    """O nome como literal PowerShell entre aspas simples."""
    return "'" + str(texto).replace("'", "''") + "'"


def _rodar(script: str, nome: str, timeout: float):
    """PowerShell com o nome EMBUTIDO e a saida decodificada na mao.

    Duas armadilhas, as duas silenciosas:

    `-Command` junta todo o resto da linha no proprio comando, entao passar
    `-args <nome>` depois dele NAO preenche `$args` — ele vira texto colado no
    fim do script, `$args[0]` fica vazio e `Get-ScheduledTask` falha. Por isso
    o nome entra no script como literal.

    E `text=True` assume UTF-8 enquanto o PowerShell escreve na pagina de
    codigo do console (cp1252 aqui): um acento em "O sistema nao pode
    encontrar..." virava `UnicodeDecodeError` dentro da thread leitora do
    subprocess — e o erro nao subia, a funcao so devolvia vazio, como se a
    tarefa nao existisse.
    """
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive",
         "-Command", script.replace("@NOME@", _aspas(nome))],
        capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    saida = (proc.stdout or b"").decode("utf-8", "replace")
    erro = (proc.stderr or b"").decode("utf-8", "replace")
    return proc.returncode, saida, erro

# Preserva `ExecutionTimeLimit` e `MultipleInstances` da tarefa que ja existe:
# `New-ScheduledTaskSettingsSet` devolve um conjunto NOVO, e aplicar ele cru
# apagaria o limite de execucao e a regra de instancia unica que o /Create
# tinha deixado. Endurecer a tarefa nao pode afrouxa-la em outro ponto.
_SCRIPT = """
$ErrorActionPreference = 'Stop'
$nome = @NOME@
$t = Get-ScheduledTask -TaskName $nome
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable
$s.ExecutionTimeLimit = $t.Settings.ExecutionTimeLimit
$s.MultipleInstances  = $t.Settings.MultipleInstances
$s.Enabled            = $t.Settings.Enabled
$s.WakeToRun          = $true
Set-ScheduledTask -TaskName $nome -Settings $s | Out-Null
"""


def endurecer(nome: str, *, timeout: float = 60) -> dict:
    """Aplica os tres ajustes numa tarefa que JA existe.

    Nunca levanta: uma tarefa criada e melhor do que nenhuma, e falhar aqui
    nao pode desfazer o `/Create` que acabou de dar certo. O chamador recebe
    `{"ok": bool, "mensagem": str}` e decide se avisa.
    """
    try:
        codigo, saida, erro = _rodar(_SCRIPT, nome, timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "tarefa": nome,
                "mensagem": f"{type(exc).__name__}: {exc}"}
    return {"ok": codigo == 0, "tarefa": nome,
            "mensagem": " ".join((saida + erro).split())[:300]}


def conferir(nome: str, *, timeout: float = 60) -> dict:
    """Como a tarefa esta AGORA. `{}` quando ela nao existe.

    Serve para o painel e para a auditoria responderem "essa tarefa vai mesmo
    disparar?" sem ninguem abrir o Agendador — que e como estes tres ajustes
    passaram despercebidos desde que as tarefas foram criadas.
    """
    script = (
        "$ErrorActionPreference='Stop';"
        "$t = Get-ScheduledTask -TaskName @NOME@;"
        "$s = $t.Settings;"
        "'{0};{1};{2}' -f $s.DisallowStartIfOnBatteries,"
        "$s.StopIfGoingOnBatteries, $s.StartWhenAvailable")
    try:
        codigo, saida, _erro = _rodar(script, nome, timeout)
    except (OSError, subprocess.SubprocessError):
        return {}
    if codigo != 0:
        return {}
    campos = saida.strip().split(";")
    if len(campos) != 3:
        return {}
    def _bool(texto: str) -> bool:
        return str(texto).strip().lower() in ("true", "verdadeiro", "1")
    so_no_ac, para_na_bateria, roda_se_perdeu = (_bool(c) for c in campos)
    return {"tarefa": nome,
            "so_no_ac": so_no_ac,
            "para_na_bateria": para_na_bateria,
            "roda_se_perdeu": roda_se_perdeu,
            # A pergunta que interessa, ja respondida: da para confiar que
            # esta tarefa dispara no horario combinado?
            "confiavel": (not so_no_ac and not para_na_bateria
                          and roda_se_perdeu)}
