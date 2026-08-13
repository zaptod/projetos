"""Saida de console segura para terminais com codificacoes limitadas."""

from __future__ import annotations

import argparse
import sys


def _texto_compativel(text: str, destination) -> str:
    encoding = getattr(destination, "encoding", None)
    if not encoding:
        return text
    return text.encode(encoding, "backslashreplace").decode(encoding)


def safe_write(text, *, file=None, flush=False) -> None:
    """Escreve texto sem alterar terminadores ou depender de UTF-8."""

    destination = file or sys.stdout
    destination.write(_texto_compativel(str(text), destination))
    if flush:
        destination.flush()


def safe_print(*values, sep=" ", end="\n", file=None, flush=False) -> None:
    """Imprime qualquer Unicode sem propagar ``UnicodeEncodeError``.

    Nomes de personagens, skills e caminhos sao dados livres. Em consoles
    Windows legados, caracteres nao representaveis sao escapados de maneira
    reversivel em vez de transformar uma operacao bem-sucedida em erro.
    """

    destination = file or sys.stdout
    text = sep.join(str(value) for value in values)
    safe_write(text + end, file=destination, flush=flush)


class SafeArgumentParser(argparse.ArgumentParser):
    """ArgumentParser que tambem aceita argumentos livres em consoles legados."""

    def _print_message(self, message, file=None):
        if message:
            safe_write(message, file=file or sys.stderr)


__all__ = ["SafeArgumentParser", "safe_print", "safe_write"]
