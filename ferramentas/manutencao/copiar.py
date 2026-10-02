"""Copia arquivos de uma worktree para uma arvore principal com guarda da base."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ARQUIVOS_PADRAO = [
    "random_builds/builds/pipeline/noite.py",
    "random_builds/builds/pipeline/tarefas_noite.py",
    "random_builds/builds/pipeline/sonorizar.py",
    "random_builds/main.py",
    "random_builds/config/geracao.json",
    "random_builds/tests/test_geracao_noturna_regressions.py",
    "random_builds/tests/test_som_da_luta_real_regressions.py",
    "random_builds/tests/test_lote_de_dia_builds_regressions.py",
    "docs/sessoes/builds.md",
]


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("base", help="commit ou referencia que representa a base comum")
    p.add_argument("origem", type=Path, help="raiz da worktree de origem")
    p.add_argument("destino", type=Path, help="raiz da arvore principal")
    p.add_argument("arquivos", nargs="*", help="caminhos relativos a copiar")
    p.add_argument("--conferir", action="store_true", help="so verifica; nao escreve arquivos")
    return p.parse_args()


def destino_mudou(destino: Path, base: str, arquivos: list[str]) -> list[str]:
    r = subprocess.run(["git", "-C", str(destino), "diff", "--name-only", base, "--", *arquivos],
                       capture_output=True, text=True, check=False)
    if r.returncode:
        raise RuntimeError((r.stderr or "git diff falhou").strip())
    return [linha for linha in r.stdout.splitlines() if linha]


def copiar(origem: Path, destino: Path, arquivos: list[str]) -> None:
    for rel in arquivos:
        fonte = origem / rel
        alvo = destino / rel
        dados = fonte.read_bytes().replace(b"\r\n", b"\n")
        crlf = alvo.is_file() and b"\r\n" in alvo.read_bytes()
        if crlf or not alvo.is_file():
            dados = dados.replace(b"\n", b"\r\n")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(dados)
        print("copiado", rel, "CRLF" if crlf or not alvo.exists() else "LF")


def principal() -> int:
    a = argumentos()
    arquivos = a.arquivos or ARQUIVOS_PADRAO
    mudou = destino_mudou(a.destino, a.base, arquivos)
    if mudou:
        print("DESTINO MUDOU desde a base:\n" + "\n".join(mudou))
        return 1
    print("destino igual a base", a.base)
    if not a.conferir:
        copiar(a.origem, a.destino, arquivos)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
