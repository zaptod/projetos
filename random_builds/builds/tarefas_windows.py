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


def _em_teste() -> bool:
    """Rodando dentro de uma suite (pytest, ou o runtime descartavel)."""
    import os
    return bool(os.environ.get("PYTEST_CURRENT_TEST")
                or os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR"))


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
    if "Set-ScheduledTask" in script and _em_teste():
        # TESTE NAO MUDA O AGENDADOR DE VERDADE (14/10/2026). Os testes dos
        # instaladores dublam o `/Create`, mas o ajuste depois dele usa o
        # NOME real ("Historias_auto_07"): sem esta guarda, um teste que
        # esquecesse de dublar `limitar_execucao` mudaria a tarefa viva.
        return 1, "", "recusado: teste nao muda o Agendador real"
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


# O LIMITE DE EXECUCAO (06/10/2026). O `/Create` deixa PT72H, e com a regra
# IgnoreNew a tarefa que pendurou ficava "Em execucao" por tres dias: o mesmo
# horario do dia seguinte era IGNORADO. MEDIDO no mesmo dia, numa tarefa de
# teste com a acao de sempre (wscript -> oculto.vbs -> .cmd -> python) e
# limite de 1 min: o Agendador encerrou a tarefa (resultado 0x41306) e
# matou SO o wscript; o cmd.exe e o python continuaram vivos. Entao o limite
# devolve a TAREFA (o proximo disparo dela volta a acontecer), mas nao mata
# o trabalho pendurado — quem faz isso e o proprio programa (no postar, a
# dona pendurada da `TRAVA_DA_RODADA`).
_SCRIPT_LIMITE = """
$ErrorActionPreference = 'Stop'
$nome = @NOME@
$t = Get-ScheduledTask -TaskName $nome
$s = $t.Settings
$s.ExecutionTimeLimit = '@LIMITE@'
Set-ScheduledTask -TaskName $nome -Settings $s | Out-Null
"""


def limitar_execucao(nome: str, limite: str = "PT2H", *,
                     timeout: float = 60) -> dict:
    """Troca o `ExecutionTimeLimit` de uma tarefa que JA existe. Nunca levanta."""
    import re
    if not re.fullmatch(r"PT\d+[HMS]", str(limite)):
        return {"ok": False, "tarefa": nome,
                "mensagem": f"limite invalido: {limite!r} (ex.: PT2H)"}
    try:
        codigo, saida, erro = _rodar(
            _SCRIPT_LIMITE.replace("@LIMITE@", limite), nome, timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "tarefa": nome,
                "mensagem": f"{type(exc).__name__}: {exc}"}
    return {"ok": codigo == 0, "tarefa": nome, "limite": limite,
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
        "'{0};{1};{2};{3}' -f $s.DisallowStartIfOnBatteries,"
        "$s.StopIfGoingOnBatteries, $s.StartWhenAvailable, $t.State")
    try:
        codigo, saida, _erro = _rodar(script, nome, timeout)
    except (OSError, subprocess.SubprocessError):
        return {}
    if codigo != 0:
        return {}
    campos = saida.strip().split(";")
    if len(campos) not in (3, 4):
        return {}
    def _bool(texto: str) -> bool:
        return str(texto).strip().lower() in ("true", "verdadeiro", "1")
    so_no_ac, para_na_bateria, roda_se_perdeu = (_bool(c) for c in campos[:3])
    # SCR-P10 (14/10/2026): o ESTADO. Ate aqui uma `NeuralFights_postar_17`
    # desligada passava como "confiavel" (so os ajustes de bateria eram
    # lidos). `State` e um enum (Ready, Running, Disabled...), em ingles em
    # qualquer idioma do Windows.
    estado = campos[3].strip() if len(campos) == 4 else ""
    return {"tarefa": nome,
            "so_no_ac": so_no_ac,
            "para_na_bateria": para_na_bateria,
            "roda_se_perdeu": roda_se_perdeu,
            "estado": estado,
            "ligada": estado.lower() != "disabled",
            # A pergunta que interessa, ja respondida: da para confiar que
            # esta tarefa dispara no horario combinado?
            "confiavel": (not so_no_ac and not para_na_bateria
                          and roda_se_perdeu)}


def julgar(esperadas: dict, ler=None) -> dict:
    """Confere um conjunto `{nome: "ligada"|"desligada"}` (SCR-P10).

    Uma regra so para os dois leitores (o panorama e o relatorio do bot), que
    tinham listas diferentes e nenhum dos dois via tarefa desligada. Devolve
    `{"total", "faltando", "fracas", "sem_leitura", "motivo_sem_leitura"?}`:
    falta a ligada que nao existe; e fraca a ligada que nao e confiavel ou
    esta desligada, e a desligada de proposito que voltou a ficar ligada (o
    `remoto --instalar` a religaria). Desligada de proposito e ausente nao
    falta. Erro de leitura vai para `sem_leitura` — nunca vira "tudo certo".
    """
    ler = ler or conferir
    faltando, fracas, sem_leitura, motivo = [], [], [], ""
    for nome, quer in esperadas.items():
        try:
            ficha = ler(nome)
        except Exception as erro:                              # noqa: BLE001
            sem_leitura.append(nome)
            motivo = motivo or f"{type(erro).__name__}: {erro}"
            continue
        if quer == "desligada":
            if ficha and ficha.get("ligada", True) and ficha.get("estado"):
                fracas.append(nome)
            continue
        if not ficha:
            faltando.append(nome)
        elif not ficha.get("confiavel") or not ficha.get("ligada", True):
            fracas.append(nome)
    saida = {"total": len(esperadas), "faltando": faltando, "fracas": fracas,
             "sem_leitura": sem_leitura}
    if motivo:
        saida["motivo_sem_leitura"] = motivo
    return saida


# ---------------------------------------------------------- sem janela preta
# Pedido do Adrian (17/09/2026): as tarefas abriam uma janela preta do cmd a
# cada disparo. A acao passa a ser o `wscript.exe` rodando um .vbs que chama o
# .cmd ESCONDIDO e ESPERA ele terminar — assim a tarefa continua "Em
# execucao" enquanto o trabalho roda, e o IgnoreNew (nao abrir segunda copia)
# e o codigo de saida continuam valendo, como era com o .cmd direto.
NOME_DO_VBS = "oculto.vbs"
WSCRIPT = r"C:\Windows\System32\wscript.exe"
VBS = (
    "' Roda um .cmd do projeto SEM janela de console (pedido do Adrian, "
    "17/09/2026).\r\n"
    "' Uso (pelo Agendador): wscript.exe //B //Nologo oculto.vbs "
    "\"E:\\projetos\\postar.cmd\"\r\n"
    "' Espera o .cmd terminar (True): assim a tarefa continua \"Em execucao\" "
    "enquanto\r\n"
    "' o trabalho roda, e a regra do Agendador de nao abrir uma segunda copia\r\n"
    "' (IgnoreNew) continua valendo, como era com o .cmd direto.\r\n"
    "If WScript.Arguments.Count < 1 Then WScript.Quit 2\r\n"
    "Set shell = CreateObject(\"WScript.Shell\")\r\n"
    "codigo = shell.Run(\"cmd.exe /c \"\"\" & WScript.Arguments(0) & "
    "\"\"\"\", 0, True)\r\n"
    "WScript.Quit codigo\r\n"
)


def garantir_vbs(pasta=None):
    """O `oculto.vbs` no runtime, escrito se faltar. Devolve o caminho.

    Um arquivo que ja existe NAO e sobrescrito: quem o ajustou a mao (ou a
    versao que esta rodando agora nas 25 tarefas) continua valendo.
    """
    from pathlib import Path
    if pasta is None:
        from .contas import runtime_dir
        pasta = runtime_dir()
    caminho = Path(pasta) / NOME_DO_VBS
    if not caminho.is_file():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # Em BYTES: `write_text` no Windows traduz cada quebra de linha
        # de novo, e o CRLF do VBS sairia com o CR dobrado.
        caminho.write_bytes(VBS.encode("ascii"))
    return caminho


def acao_oculta(lancador, vbs=None) -> str:
    """O `/TR` do schtasks: o `.cmd` chamado pelo wscript, sem janela."""
    vbs = vbs if vbs is not None else garantir_vbs()
    return f'{WSCRIPT} //B //Nologo "{vbs}" "{lancador}"'
