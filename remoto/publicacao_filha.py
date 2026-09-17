# -*- coding: utf-8 -*-
"""Roda UM `main.py publicar` longe do servidor do app e anota como acabou.

    python -m remoto.publicacao_filha --pasta P --cwd C -- <comando...>

POR QUE EXISTE. Com a saida do `main.py` num PIPE do servidor, o servidor
que cai (ou reinicia, ou para de ler) mata o filho no proximo `print` —
inclusive logo depois do clique no TikTok, sem marca e sem ledger. Aqui:

  - o filho escreve num ARQUIVO (`P/saida.log`), nunca num pipe;
  - este processo sobe DESLIGADO do servidor (outro grupo, sem console),
    entao o servidor pode morrer sem levar a publicacao junto;
  - no fim grava `P/fim.json` com o codigo de saida. E so isso que o
    servidor (este ou o proximo, na subida) precisa para concluir.

Nada aqui decide nada: quem le a saida e marca "a conferir" e o
`remoto.acoes`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def criado_em(pid) -> float | None:
    """Quando o processo nasceu (epoch), ou None se nao deu para saber.

    Serve para nao confundir um PID reaproveitado (depois de um reboot) com
    a filha de verdade: PID igual com nascimento diferente e outro processo.
    """
    try:
        numero = int(pid)
    except (TypeError, ValueError):
        return None
    if os.name != "nt" or numero <= 0:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, numero)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            criacao, saida, kernel, usuario = (wintypes.FILETIME() for _ in range(4))
            if not k32.GetProcessTimes(handle, ctypes.byref(criacao), ctypes.byref(saida),
                                       ctypes.byref(kernel), ctypes.byref(usuario)):
                return None
        finally:
            k32.CloseHandle(handle)
        cem_ns = (criacao.dwHighDateTime << 32) | criacao.dwLowDateTime
        return cem_ns / 1e7 - 11644473600.0
    except Exception:                                        # noqa: BLE001
        return None


def _gravar(caminho: Path, dados: dict) -> None:
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, caminho)


def rodar(pasta: Path, cwd: str, comando: list) -> int:
    pasta.mkdir(parents=True, exist_ok=True)
    ambiente = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    codigo = None
    erro = ""
    try:
        with open(pasta / "saida.log", "a", encoding="utf-8") as saida:
            filho = subprocess.Popen(comando, cwd=cwd, stdin=subprocess.DEVNULL,
                                     stdout=saida, stderr=subprocess.STDOUT,
                                     creationflags=NO_WINDOW, env=ambiente)
            _gravar(pasta / "filho.json", {"pid": filho.pid,
                                           "criado": criado_em(filho.pid)})
            codigo = filho.wait()
    except Exception as exc:                                 # noqa: BLE001
        erro = f"{type(exc).__name__}: {exc}"
    _gravar(pasta / "fim.json", {
        "codigo": codigo, "erro": erro,
        "fim": datetime.now().isoformat(timespec="seconds")})
    return 0 if codigo == 0 else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        print("uso: python -m remoto.publicacao_filha --pasta P --cwd C -- cmd...",
              file=sys.stderr)
        return 2
    corte = argv.index("--")
    parser = argparse.ArgumentParser(prog="python -m remoto.publicacao_filha")
    parser.add_argument("--pasta", required=True)
    parser.add_argument("--cwd", required=True)
    args = parser.parse_args(argv[:corte])
    comando = argv[corte + 1:]
    if not comando:
        return 2
    return rodar(Path(args.pasta), args.cwd, comando)


if __name__ == "__main__":
    raise SystemExit(main())
