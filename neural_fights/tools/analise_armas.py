"""Gate estrutural e resumo do banco canonico de armas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence, TextIO

from neural_fights.tools.diagnostico_hitbox import (
    DEFAULT_WEAPONS,
    HitboxGateReport,
    _write_output,
    carregar_armas,
    criar_relatorio,
    render_text,
)


def analisar_armas(armas: list[dict[str, Any]]) -> list[str]:
    """API legada: devolve somente erros e avisos acionaveis."""

    report = criar_relatorio(
        armas,
        arquivo="memoria",
        hitbox_source=None,
    )
    return [
        f"{item.nome}: {item.problema}"
        for item in report.diagnosticos
        if item.nivel in {"error", "warning"}
    ]


def analisar_relatorio(
    armas: list[dict[str, Any]],
    *,
    arquivo: str,
) -> HitboxGateReport:
    """Valida pelo contrato de :mod:`neural_fights.data.database` e classifica achados."""

    return criar_relatorio(armas, arquivo=arquivo, hitbox_source=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivo", type=Path, default=DEFAULT_WEAPONS)
    parser.add_argument("--json", action="store_true", help="emite JSON ASCII")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="retorna codigo 2 quando houver avisos de limite operacional",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = build_parser().parse_args(argv)
    weapons_path = args.arquivo.resolve()
    try:
        armas = carregar_armas(weapons_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _write_output(f"input error: {exc}\n", stderr)
        return 1

    report = analisar_relatorio(armas, arquivo=str(weapons_path))
    if args.json:
        _write_output(json.dumps(report.to_dict(), ensure_ascii=True, sort_keys=True) + "\n", stdout)
    else:
        _write_output(render_text(report, title="WEAPON DATABASE GATE"), stdout)

    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
