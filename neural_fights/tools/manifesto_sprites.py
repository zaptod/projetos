"""Manifesto das partes estaticas que o palco pode montar.

O desenho dos eixos fica no prototipo aprovado pelo contrato.  Este modulo e
o ponto de entrada de producao: importa os catalogos da engine, normaliza os
campos que o painel consome e grava o resultado de modo atomico.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import sys
import tempfile
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
PROTOCOLO = RAIZ / "docs" / "sprites" / "prototipo_gerar_manifesto.py"
PADRAO = RAIZ / "palco" / "biblioteca" / "manifesto_slots.json"


def gerar() -> dict:
    """Importa a engine e devolve todos os slots, sem depender de banco real."""
    argv, sys.argv = sys.argv, [str(PROTOCOLO)]
    try:
        # O prototipo tambem serve de demonstracao na documentacao e imprime
        # resumo; o gerador nao pode poluir quem o importa.
        with contextlib.redirect_stdout(io.StringIO()):
            dados = runpy.run_path(str(PROTOCOLO))
    finally:
        sys.argv = argv
    slots = dados["slots"]
    for slot in slots:
        slot["rotulo"] = _rotulo(slot)
        slot["reserva"] = _reserva(slot)
        slot["obrigatorio"] = slot["papel"] == "obrigatorio"
        if slot["grupo"] in ("lutador", "camada_estado"):
            slot["tamanho_px"] = [1024, 1024]
            slot["ancora"] = "gabarito"
    resumo = dados["resumo"]
    return {"versao": 1, "resumo": resumo, "slots": slots}


def _rotulo(slot: dict) -> str:
    parte = str(slot["parte"]).replace("_", " ")
    alvo = slot["alvo"]["rotulo"]
    estado = slot["estado"]
    return " · ".join(x for x in (parte.capitalize(), alvo, "base" if estado == "base" else estado.replace("_", " ")) if x)


def _reserva(slot: dict) -> str:
    if slot["grupo"] == "lutador":
        return "desenho atual da bolinha"
    if slot["grupo"] == "camada_estado":
        return "efeito atual do jogo"
    return "desenho atual do palco"


def gravar(caminho: Path = PADRAO) -> dict:
    """Gera e troca o manifesto inteiro de uma vez, nunca um JSON pela metade."""
    manifesto = gerar()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix="manifesto-", suffix=".json", dir=caminho.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as arquivo:
            json.dump(manifesto, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.replace(temporario, caminho)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(temporario)
        raise
    return manifesto


if __name__ == "__main__":
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else PADRAO
    manifesto = gravar(saida)
    print(json.dumps(manifesto["resumo"]["por_grupo"], ensure_ascii=False, sort_keys=True))
