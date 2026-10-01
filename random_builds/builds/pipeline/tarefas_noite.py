# -*- coding: utf-8 -*-
"""As tarefas do Agendador que chamam `main.py noite` (`NeuralFights_gerar_HH`).

O mesmo modelo das `Historias_auto_HH` (`contos/pipeline/tarefas.py`), com os
mesmos tres cuidados, cada um pago antes por outra tarefa do projeto:

  O ARQUIVO DE SAIDA E ABERTO PELO PYTHON (`--saida`), nunca pelo `>>` do
  cmd. O `>>` nega escrita a outros processos: em 14/09/2026 as tarefas das
  00h, 01h e 02h das historias morreram com codigo 1, sem uma linha de log,
  porque a rodada das 23h segurava o mesmo arquivo.

  O CONSOLE VAI PARA NUL. Escrever no console que o Agendador da e ninguem
  esvazia trava o `print` (08/09/2026, 13 minutos parado num `print`).

  SEM JANELA PRETA E SEM /RU SYSTEM. A acao e o `wscript` rodando o .cmd
  escondido (pedido do Adrian, 17/09/2026), e a tarefa roda com o usuario
  conectado: o worker de identidade abre Chrome de verdade, e na sessao 0
  nao ha area de trabalho.

Depois do `/Create` vem `tarefas_windows.endurecer`: sem ele a tarefa recusa
iniciar na bateria e nunca recupera horario perdido (09/09/2026).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .. import tarefas_windows

RAIZ = Path(__file__).resolve().parents[2]
PREFIXO = "NeuralFights_gerar"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def hora_e_minuto(horario, minuto: int = 2) -> tuple[int, int]:
    """`5` -> (5, minuto); `"12:32"` -> (12, 32).

    Desde o lote de dia (30/09/2026) as `horas` do `geracao.json` misturam as
    duas formas: 12:02 e 18:02 caem na folga das postagens de 12:07 e 17:57 e
    viram 12:32 e 18:22, como na agenda das historias.
    """
    if isinstance(horario, str) and ":" in horario:
        hora, _, mm = horario.partition(":")
        return int(hora) % 24, int(mm) % 60
    return int(horario) % 24, int(minuto) % 60


def nome_da_tarefa(hora) -> str:
    return f"{PREFIXO}_{hora_e_minuto(hora)[0]:02d}"


def caminho_do_lancador() -> Path:
    return RAIZ / "gerar.cmd"


def caminho_da_saida() -> Path:
    return RAIZ / "outputs" / "_logs" / "gerar_saida.txt"


def conteudo_do_lancador(python: str, raiz: Path, saida: Path) -> str:
    """O texto do .cmd, separado para o teste ler sem escrever no disco.

    `%*` antes do `--saida`: a tarefa chama sem argumento nenhum, e o ensaio
    de ponta a ponta chama `gerar.cmd --ensaio` pelo MESMO lancador.
    """
    return (
        "@echo off\r\n"
        "rem Geracao noturna do canal de builds (duelos + worker). Chamado\r\n"
        "rem pelas tarefas NeuralFights_gerar_HH do Agendador do Windows.\r\n"
        "rem Gerado por: python main.py noite --instalar\r\n"
        f'cd /d "{raiz}"\r\n'
        # `-X utf8`: a saida vai para ARQUIVO, e sem ele o Python assume
        # cp1252 e o primeiro nome com acento ("Aldric o Implacavel" tem um)
        # vira UnicodeEncodeError. `-u`: o log nao fica preso no buffer.
        f'"{python}" -u -X utf8 main.py noite %* --saida "{saida}" > NUL 2>&1\r\n')


def escrever_lancador(python: str | None = None) -> Path:
    destino = caminho_do_lancador()
    saida = caminho_da_saida()
    saida.parent.mkdir(parents=True, exist_ok=True)
    # `newline=""`: o texto ja vem com CRLF, e `write_text` no Windows
    # traduziria cada LF de novo e o arquivo sairia com CR CR LF (o
    # `auto.cmd` das historias esta assim; o cmd tolera, mas e sorte).
    with open(destino, "w", encoding="utf-8", newline="") as fh:
        fh.write(conteudo_do_lancador(python or sys.executable, RAIZ, saida))
    return destino


class _Saida:
    def __init__(self, proc):
        self.returncode = proc.returncode
        # Sem `text=True`: o schtasks escreve na pagina de codigo do console
        # e o "Ê" de "ÊXITO" virava UnicodeDecodeError (09/09/2026).
        self.stdout = (proc.stdout or b"").decode("utf-8", "replace")
        self.stderr = (proc.stderr or b"").decode("utf-8", "replace")


def _schtasks(argumentos: list) -> _Saida:
    return _Saida(subprocess.run(["schtasks"] + argumentos,
                                 capture_output=True, timeout=60,
                                 creationflags=NO_WINDOW))


def instalar(horas: list, minuto: int = 2) -> list[dict]:
    """Cria (ou substitui) uma tarefa diaria por hora. Devolve o que deu."""
    lancador = escrever_lancador()
    saida = []
    for horario in horas:
        hora, mm = hora_e_minuto(horario, minuto)
        nome = nome_da_tarefa(hora)
        proc = _schtasks(["/Create", "/TN", nome,
                          "/TR", tarefas_windows.acao_oculta(lancador),
                          "/SC", "DAILY",
                          "/ST", f"{hora:02d}:{mm:02d}",
                          "/RL", "LIMITED", "/F"])
        ficha = {"hora": hora, "minuto": mm, "tarefa": nome,
                 "ok": proc.returncode == 0,
                 "mensagem": (proc.stdout or proc.stderr or "").strip()}
        if ficha["ok"]:
            ajuste = tarefas_windows.endurecer(nome)
            ficha["ajustada"] = ajuste["ok"]
            if not ajuste["ok"]:
                ficha["mensagem"] = (
                    f"{ficha['mensagem']} (criada, mas os ajustes de bateria "
                    f"e de horario perdido falharam: {ajuste['mensagem']})"
                ).strip()
        saida.append(ficha)
    return saida


def remover(horas: list | None = None) -> list[dict]:
    """Remove as tarefas desta familia. Sem `horas`, procura as 24."""
    alvos = horas if horas is not None else list(range(24))
    saida = []
    for hora in alvos:
        nome = nome_da_tarefa(hora)
        proc = _schtasks(["/Delete", "/TN", nome, "/F"])
        if proc.returncode == 0:
            saida.append({"hora": hora_e_minuto(hora)[0], "tarefa": nome,
                          "removida": True})
    return saida


def listar() -> list[dict]:
    """As tarefas desta familia que existem hoje, com o proximo disparo."""
    proc = _schtasks(["/Query", "/FO", "CSV", "/NH"])
    if proc.returncode != 0:
        return []
    achadas = []
    for linha in (proc.stdout or "").splitlines():
        campos = [c.strip('"') for c in linha.split('","')]
        if not campos:
            continue
        nome = campos[0].strip('"').lstrip("\\")
        if not nome.startswith(PREFIXO):
            continue
        achadas.append({"tarefa": nome,
                        "proximo": campos[1] if len(campos) > 1 else "",
                        "situacao": campos[2] if len(campos) > 2 else ""})
    return sorted(achadas, key=lambda t: t["tarefa"])


__all__ = ["PREFIXO", "caminho_do_lancador", "caminho_da_saida", "hora_e_minuto",
           "conteudo_do_lancador", "escrever_lancador", "instalar", "listar",
           "nome_da_tarefa", "remover"]
