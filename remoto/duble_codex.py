# -*- coding: utf-8 -*-
"""Dublê do `codex exec --json` para os testes do despachante (remoto/delegar.py).

NUNCA chama o Codex de verdade. Le o prompt do stdin (como o de verdade, com
`-`), grava o que recebeu em `$NF_DUBLE_SAIDA/chamada_N.json` (argv, stdin,
cwd e as variaveis de ambiente que importam) e se comporta conforme
`$NF_DUBLE_MODO`:

    ok       muda remoto/novo.py e remoto/existente.py (CRLF), responde e sai 0
    lento    manda os primeiros eventos e dorme (o teste o mata)
    falha    turn.failed e sai 2
    fora     cria outro/fora.py (fora da lista permitida)
    binario  cria remoto/foto.png
    nada     responde sem mudar nada
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def emitir(ev: dict) -> None:
    sys.stdout.write(json.dumps(ev, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    args = sys.argv[1:]
    prompt = sys.stdin.read() if args and args[-1] == "-" else ""
    modo = os.environ.get("NF_DUBLE_MODO", "ok")
    saida = Path(os.environ.get("NF_DUBLE_SAIDA") or ".")
    saida.mkdir(parents=True, exist_ok=True)
    n = len(list(saida.glob("chamada_*.json"))) + 1
    (saida / f"chamada_{n}.json").write_text(json.dumps({
        "argv": args, "stdin": prompt, "cwd": os.getcwd(), "pid": os.getpid(),
        "env": {k: os.environ.get(k) for k in ("PYTEST_ADDOPTS", "PYTHONDONTWRITEBYTECODE",
                                                "NF_SEGREDO_TOKEN", "NF_DELEGADO")}},
        ensure_ascii=False), encoding="utf-8")
    cwd = Path(os.getcwd())
    if "-C" in args:
        cwd = Path(args[args.index("-C") + 1])
    resposta = Path(args[args.index("-o") + 1]) if "-o" in args else None

    emitir({"type": "thread.started", "thread_id": "01a0f92a-17e1-7a60-bc18-093e93057408"})
    emitir({"type": "turn.started"})
    cmd = ('"C:\\\\WINDOWS\\\\System32\\\\WindowsPowerShell\\\\v1.0\\\\powershell.exe" '
           "-NoProfile -Command 'Get-Content remoto/existente.py'")
    emitir({"type": "item.started", "item": {"id": "item_0", "type": "command_execution",
                                             "command": cmd, "aggregated_output": "",
                                             "exit_code": None, "status": "in_progress"}})
    emitir({"type": "item.completed", "item": {"id": "item_0", "type": "command_execution",
                                               "command": cmd, "aggregated_output": "linha\r\n",
                                               "exit_code": 0, "status": "completed"}})
    if modo == "lento":
        emitir({"type": "item.completed", "item": {"id": "item_1", "type": "reasoning",
                                                   "text": "pensando devagar"}})
        time.sleep(60)
        return 0
    if modo == "aos_poucos":
        # para a prova de tela: um evento por segundo, como o de verdade
        for i in range(int(os.environ.get("NF_DUBLE_PASSOS", "12"))):
            time.sleep(1.0)
            c = f"Get-Content remoto/arquivo_{i}.py"
            emitir({"type": "item.completed", "item": {
                "id": f"item_p{i}", "type": "command_execution", "command": c,
                "aggregated_output": f"conteudo {i}\n", "exit_code": 0,
                "status": "completed"}})
            emitir({"type": "item.completed", "item": {"id": f"item_r{i}", "type": "reasoning",
                                                       "text": f"passo {i}: lendo"}})
        modo = "ok"
    if modo == "falha":
        emitir({"type": "turn.failed", "error": {"message": "limite de uso atingido"}})
        return 2
    mudancas = []
    if modo == "ok":
        (cwd / "remoto").mkdir(exist_ok=True)
        (cwd / "remoto" / "novo.py").write_text("X = 1\n", encoding="utf-8")
        existente = cwd / "remoto" / "existente.py"
        existente.write_bytes(existente.read_bytes() + b"Y = 2\r\n")
        mudancas = [{"path": "remoto/novo.py", "kind": "add"},
                    {"path": "remoto/existente.py", "kind": "update"}]
    elif modo == "fora":
        (cwd / "outro").mkdir(exist_ok=True)
        (cwd / "outro" / "fora.py").write_text("Z = 3\n", encoding="utf-8")
        mudancas = [{"path": "outro/fora.py", "kind": "add"}]
    elif modo == "binario":
        (cwd / "remoto").mkdir(exist_ok=True)
        (cwd / "remoto" / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00binario")
        mudancas = [{"path": "remoto/foto.png", "kind": "add"}]
    if mudancas:
        emitir({"type": "item.completed", "item": {"id": "item_2", "type": "file_change",
                                                   "changes": mudancas, "status": "completed"}})
    texto = f"Feito ({modo}). Mudei {len(mudancas)} arquivo(s)."
    emitir({"type": "item.completed", "item": {"id": "item_3", "type": "agent_message",
                                               "text": texto}})
    emitir({"type": "turn.completed", "usage": {"input_tokens": 1000, "cached_input_tokens": 800,
                                                "output_tokens": 50,
                                                "reasoning_output_tokens": 10}})
    if resposta:
        resposta.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
