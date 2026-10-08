"""Prova reproduzivel da E3 fora do sandbox."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from . import config


def prova(raiz: Path) -> None:
    saida = raiz / "palco" / "_saida" / "prova_e3"
    saida.mkdir(parents=True, exist_ok=True)
    exe = config.godot()
    cmd = [str(exe), "--headless", "--path", str(raiz / "palco"), "--script", "res://testes/tocador_folha.gd"]
    subprocess.run(cmd, check=True)
    # O render real usa o mesmo entrypoint de producao; os hashes sao dos PNGs
    # extraidos por ffmpeg apos as duas passadas deterministas.
    print("rode: python -m builds.palco.cli render --seed 7174 --quadros 150")
    print("saida esperada:", saida)


def hash_arquivo(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()
