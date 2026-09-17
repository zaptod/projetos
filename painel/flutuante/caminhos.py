# -*- coding: utf-8 -*-
"""Onde estao os arquivos que a janela le.

A RAIZ DOS DADOS nao e necessariamente a pasta deste codigo: numa worktree
de desenvolvimento o codigo mora em `.claude/worktrees/...`, mas os ledgers,
os logs e o `ferramentas/postar.py` que rodam de verdade estao no checkout
instalado — e e para la que o pacote `builds` aponta. Entao a raiz e
descoberta subindo a partir dele, e so cai na pasta deste arquivo quando o
workspace nao esta instalado. `NF_RAIZ` fura tudo (testes).
"""
from __future__ import annotations

import os
from pathlib import Path


def _tem_cara_de_raiz(pasta: Path) -> bool:
    return ((pasta / "ferramentas").is_dir()
            and (pasta / "random_builds").is_dir())


def _subir(de: Path) -> Path | None:
    for pasta in [de, *de.parents]:
        if _tem_cara_de_raiz(pasta):
            return pasta
    return None


def raiz_dos_dados() -> Path:
    fixa = os.environ.get("NF_RAIZ")
    if fixa:
        return Path(fixa)
    try:
        import builds
        achada = _subir(Path(builds.__file__).resolve().parent)
        if achada:
            return achada
    except Exception:                                        # noqa: BLE001
        pass
    return _subir(Path(__file__).resolve().parent) or Path.cwd()


def runtime() -> Path:
    """`%LOCALAPPDATA%/neural-fights` (ou o `NEURAL_FIGHTS_RUNTIME_DIR`)."""
    try:
        from builds.contas import runtime_dir
        return Path(runtime_dir())
    except Exception:                                        # noqa: BLE001
        fixa = os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR")
        if fixa:
            return Path(fixa)
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "neural-fights"


class Caminhos:
    """Tudo o que a janela le, num lugar so."""

    def __init__(self, raiz: Path | None = None, rt: Path | None = None):
        self.raiz = Path(raiz) if raiz else raiz_dos_dados()
        self.runtime = Path(rt) if rt else runtime()

    @property
    def diario(self) -> Path:
        return self.runtime / "atividade.jsonl"

    @property
    def travas(self) -> Path:
        return self.runtime / "locks"

    @property
    def relatorios(self) -> Path:
        return self.runtime / "relatorios.json"

    @property
    def preferencias(self) -> Path:
        # O UNICO arquivo que a janela escreve: onde ela estava e de que
        # tamanho. E estado dela, nao do sistema.
        return self.runtime / "flutuante.json"

    @property
    def ledgers(self) -> dict:
        return {
            "historias": self.raiz / "historias" / "outputs" / "_publicar"
            / "publicados.jsonl",
            "builds": self.raiz / "random_builds" / "outputs" / "_publicar"
            / "publicados.jsonl",
        }

    @property
    def terminais(self) -> dict:
        """Os consoles que a janela substitui, na ordem das abas."""
        return {
            "bot": self.raiz / "outputs" / "bot.txt",
            "postar": self.raiz / "outputs" / "postar.txt",
            "histórias": self.raiz / "historias" / "outputs" / "_logs"
            / "auto_saida.txt",
        }


__all__ = ["Caminhos", "raiz_dos_dados", "runtime"]
