"""Valida e resume as armas persistidas no banco canonico."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from data.database import ARQUIVO_ARMAS
from tools.diagnostico_hitbox import diagnosticar_arma


def carregar_armas(caminho: str | Path = ARQUIVO_ARMAS) -> list[dict[str, Any]]:
    path = Path(caminho)
    with path.open("r", encoding="utf-8") as stream:
        dados = json.load(stream)
    if not isinstance(dados, list):
        raise ValueError(f"Banco de armas precisa ser uma lista: {path}")
    return dados


def analisar_armas(armas: list[dict[str, Any]]) -> list[str]:
    problemas: list[str] = []
    nomes: set[str] = set()

    for indice, arma in enumerate(armas):
        if not isinstance(arma, dict):
            problemas.append(f"item {indice}: esperado objeto JSON")
            continue

        nome = str(arma.get("nome", "")).strip()
        if not nome:
            problemas.append(f"item {indice}: nome ausente")
        elif nome in nomes:
            problemas.append(f"nome duplicado: {nome}")
        nomes.add(nome)

        for diagnostico in diagnosticar_arma(arma):
            problemas.append(f"{diagnostico.nome}: {diagnostico.problema}")

    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivo", type=Path, default=Path(ARQUIVO_ARMAS))
    args = parser.parse_args(argv)

    try:
        armas = carregar_armas(args.arquivo)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}")
        return 2

    contagem = Counter(str(arma.get("tipo", "Desconhecido")) for arma in armas)
    print(f"Armas: {len(armas)}")
    for tipo, quantidade in sorted(contagem.items()):
        print(f"  {tipo}: {quantidade}")

    problemas = analisar_armas(armas)
    if problemas:
        print(f"Problemas: {len(problemas)}")
        for problema in problemas:
            print(f"  - {problema}")
        return 1

    print("Validacao concluida sem problemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
