# -*- coding: utf-8 -*-
"""`--saida ARQUIVO`: o log que a TAREFA do Agendador manda o Python abrir.

UM lugar so para os cinco programas que as tarefas chamam (o `main.py` das
historias e dos builds, o `postar.py`, o bot `python -m remoto` e o app
`remoto.api_http`). A regra de cada um ja estava escrita nos cinco:

- o arquivo e aberto PELO PYTHON, e nao pelo `>>` do cmd, que nega escrita a
  outro processo (14/09/2026: o disparo seguinte morria com codigo 1 antes de
  o Python nascer);
- em modo "a" com `buffering=1`, que deixa varios processos escreverem.

O que faltava (SCR-12, 14/10/2026): com `--saida` no fim, sem valor, a saida
ia ao console do Agendador (onde o `print` trava); com a pasta do log
apagada, o `open` levantava ANTES do `main()` e a rodada morria sem uma linha
em lugar nenhum. Agora a pasta e criada, e `--saida` sem arquivo sai com 2 e
deixa o motivo no diario (`atividade.jsonl`).
"""
from __future__ import annotations

import sys
from pathlib import Path


def _registrar(rotulo: str, texto: str) -> None:
    try:
        from . import atividade
        atividade.registrar(rotulo, "erro", texto, etapa="saida")
    except Exception:                                          # noqa: BLE001
        pass
    try:
        sys.__stderr__.write(f"[{rotulo}] {texto}\n")
    except Exception:                                          # noqa: BLE001
        pass


def abrir(argv: list, rotulo: str = "tarefa") -> tuple:
    """`(argv sem --saida ARQUIVO, arquivo aberto)`; sem a opcao, `(argv, None)`.

    `--saida` sem arquivo (no fim, ou seguido de outra opcao) levanta
    `SystemExit(2)` depois de registrar o motivo.
    """
    argv = list(argv)
    if "--saida" not in argv:
        return argv, None
    i = argv.index("--saida")
    if i + 1 >= len(argv) or str(argv[i + 1]).startswith("--"):
        _registrar(rotulo, "--saida sem arquivo: a tarefa saiu sem rodar "
                           "(confira o .cmd do Agendador)")
        raise SystemExit(2)
    caminho = Path(argv[i + 1])
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        arquivo = open(caminho, "a", encoding="utf-8", buffering=1)
    except OSError as exc:
        _registrar(rotulo, f"nao consegui abrir o log {caminho}: "
                           f"{type(exc).__name__}: {exc}")
        raise SystemExit(2) from exc
    return argv[:i] + argv[i + 2:], arquivo
