# -*- coding: utf-8 -*-
"""As tarefas do Agendador do Windows que chamam `main.py auto`.

Uma tarefa por hora, todas com o mesmo nome de familia (`Historias_auto_HH`),
para dar para listar e remover em bloco sem tocar em nada mais da maquina.

POR QUE "SOMENTE COM O USUARIO CONECTADO": a rodada abre Chrome de verdade —
o LLM, o PicassoIA e o Studio dependem do perfil logado, e nenhum deles roda
sem sessao grafica. Tarefa marcada para "rodar esteja o usuario conectado ou
nao" cai na sessao 0, onde nao existe area de trabalho: o navegador abre e
trava esperando uma tela que nunca aparece. Entao a tarefa e criada SEM /RU
SYSTEM e sem senha, que e como o schtasks cria uma tarefa interativa.

Consequencia pratica, que e melhor saber agora do que descobrir depois: o PC
precisa estar LIGADO e com a sessao do Windows ABERTA na hora. Bloqueado
(Win+L) o navegador ainda funciona; deslogado, nao.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from builds import tarefas_windows

RAIZ = Path(__file__).resolve().parents[2]
PREFIXO = "Historias_auto"
# O minuto da GERACAO. Depois da postagem (:07), nunca antes.
MINUTO = 20
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def nome_da_tarefa(hora: int) -> str:
    return f"{PREFIXO}_{int(hora):02d}"


def caminho_do_lancador() -> Path:
    return RAIZ / "auto.cmd"


def escrever_lancador(python: str | None = None) -> Path:
    """O .cmd que a tarefa chama.

    Existe para o /TR do schtasks nao virar uma linha gigante com aspas
    aninhadas (que e onde esse comando costuma quebrar), e para o interpretador
    e a pasta ficarem escritos num lugar que da para abrir e ler.

    A REDIRECAO NAO E ENFEITE. Sem ela a rodada TRAVA — 08/09/2026, primeira
    manha da agenda ligada: o py-spy achou o processo parado ha 13 minutos em
    `session.py:77`, que e um `print()`. Nao era o PicassoIA, nao era a rede: o
    processo nao conseguia escrever uma linha no console que o Agendador da a
    ele e ninguem esvazia. Escrevendo em ARQUIVO, `print` nunca bloqueia — e de
    quebra a saida do PicassoIA (que so existe como `print`) fica gravada.

    MAS O ARQUIVO E ABERTO PELO PYTHON, e nao pelo `>>` do cmd (14/09/2026).
    O `>>` nega escrita a outros processos, e os disparos sao um processo por
    hora no mesmo arquivo: enquanto uma rodada longa rodava, o disparo
    seguinte morria com codigo 1 antes de o Python comecar, sem uma linha em
    log nenhum. Ver `_redirecionar_saida` no `main.py`.
    """
    destino = caminho_do_lancador()
    python = python or sys.executable
    saida = RAIZ / "outputs" / "_logs" / "auto_saida.txt"
    saida.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        "@echo off\r\n"
        "rem Criacao automatica de historias. Chamado pelas tarefas\r\n"
        "rem Historias_auto_HH do Agendador do Windows.\r\n"
        "rem Gerado por: python main.py auto --instalar\r\n"
        f'cd /d "{RAIZ}"\r\n'
        # `-X utf8` porque a saida vai para ARQUIVO: sem ele o Python assume a
        # pagina de codigo do Windows (cp1252), e a primeira linha com acento
        # ou emoji vira UnicodeEncodeError — a rodada morreria por causa de um
        # "ç". `-u` para o log nao ficar preso no buffer enquanto ela trabalha.
        # O console do cmd vai para NUL, onde escrever nunca trava; a saida de
        # verdade o Python abre sozinho com `--saida`.
        f'"{python}" -u -X utf8 main.py auto --saida "{saida}" > NUL 2>&1\r\n',
        encoding="utf-8")
    return destino


class _Saida:
    """O que o `schtasks` respondeu, ja decodificado."""

    def __init__(self, proc):
        self.returncode = proc.returncode
        self.stdout = (proc.stdout or b"").decode("utf-8", "replace")
        self.stderr = (proc.stderr or b"").decode("utf-8", "replace")


def _schtasks(argumentos: list) -> "_Saida":
    """SEM `text=True`: o schtasks escreve na pagina de codigo do console
    (cp850 aqui) e o Python assume UTF-8 — o "Ê" de "ÊXITO" virava
    `UnicodeDecodeError` dentro da thread leitora do subprocess, no meio de
    uma instalacao que tinha dado certo. Mesma familia do `-X utf8` que o
    resto do projeto ja carrega, e o mesmo defeito que `ferramentas/postar.py`
    teve em 09/09/2026."""
    return _Saida(subprocess.run(["schtasks"] + argumentos,
                                 capture_output=True, timeout=60,
                                 creationflags=NO_WINDOW))


def instalar(horas: list, minutos: dict | None = None) -> list[dict]:
    """Cria (ou substitui) uma tarefa diaria por hora. Devolve o que deu.

    `minutos` ({hora: minuto}) e o minuto de cada disparo; sem ele, `:20`.
    Desde 15/09/2026 a rodada de dia cai 25 min depois de cada publicacao, e
    a grade de publicacao tem minuto proprio por horario.
    """
    lancador = escrever_lancador()
    minutos = minutos or {}
    saida = []
    for hora in horas:
        nome = nome_da_tarefa(hora)
        minuto = int(minutos.get(int(hora), MINUTO))
        proc = _schtasks(["/Create", "/TN", nome,
                          "/TR", f'"{lancador}"',
                          # POSTAR VEM PRIMEIRO, GERAR DEPOIS. Pedido dele
                          # em 10/09/2026, e a ordem importa de verdade: a
                          # postagem leva ~2 min e a geracao ~2 h, entao gerar
                          # primeiro (era :00, com a postagem as :07) fazia a
                          # rodada de imagens estar no meio quando a postagem
                          # chegava — as duas disputando os mesmos navegadores.
                          # Agora a postagem sai as :07 com a maquina livre, e
                          # a geracao comeca as :20, ja sabendo o que saiu.
                          "/SC", "DAILY", "/ST", f"{int(hora):02d}:{minuto:02d}",
                          "/RL", "LIMITED", "/F"])
        ficha = {"hora": int(hora), "minuto": minuto, "tarefa": nome,
                 "ok": proc.returncode == 0,
                 "mensagem": (proc.stdout or proc.stderr or "").strip()}
        if ficha["ok"]:
            # O `/Create` deixa os padroes do Windows, e os tres sao hostis a
            # uma maquina que trabalha sozinha: na bateria a tarefa nem
            # comeca, cair para bateria no meio a mata, e horario perdido
            # nunca volta. Ver `builds/tarefas_windows.py`.
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
    """Remove as tarefas desta familia. Sem `horas`, remove todas as 24."""
    alvos = horas if horas is not None else list(range(24))
    saida = []
    for hora in alvos:
        nome = nome_da_tarefa(hora)
        proc = _schtasks(["/Delete", "/TN", nome, "/F"])
        if proc.returncode == 0:
            saida.append({"hora": int(hora), "tarefa": nome, "removida": True})
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
