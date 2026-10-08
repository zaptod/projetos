"""Previa curta de uma folha do Atelie no render real do palco."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .cli import render_da_seed


def renderizar_previa(peca: str, estado: str, animacao: str, pasta_saida: Path) -> Path:
    """Renderiza cinco segundos deterministas e devolve o MP4 do Godot.

    A arte ja deve estar em ``biblioteca/animacoes``; o Godot faz a mesma
    resolucao de peca/heranca usada na luta, sem copiar nem importar a folha.
    """
    if not all(isinstance(valor, str) and valor.strip() for valor in (peca, estado, animacao)):
        raise ValueError("peca, estado e animacao sao obrigatorios")
    pasta = Path(pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)
    seed = int.from_bytes(hashlib.sha256(f"{peca}|{estado}|{animacao}".encode()).digest()[:8], "big")
    resumo = render_da_seed(p1=None, p2=None, seed=seed, arena=None, pasta=pasta, quadros=150)
    return Path(resumo["saida"])
