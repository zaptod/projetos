#!/usr/bin/env python3
"""CLI fina para executar o motor real em modo headless.

Este arquivo mantém o nome histórico por compatibilidade. Não contém regras de
combate: cada frame é processado por ``Simulador.update`` através do runner
canônico de ``neural_fights.simulation.headless``.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from typing import Any

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.data import database
from neural_fights.simulation.headless import HeadlessMatchResult, HeadlessMatchRunner


class HeadlessBattle:
    """Adaptador compatível com o antigo ponto de entrada programático."""

    def __init__(
        self,
        char1_data: dict[str, Any] | str,
        char2_data: dict[str, Any] | str,
        arma1_data: dict[str, Any] | None = None,
        arma2_data: dict[str, Any] | None = None,
        max_frames: int = 3000,
        debug: bool = False,
        *,
        fixed_dt: float = 1.0 / 60.0,
        seed: int = 0,
    ) -> None:
        # Armas vêm do banco canônico associado aos nomes; os parâmetros são
        # aceitos somente para compatibilidade de chamada com o script antigo.
        del arma1_data, arma2_data
        self.p1_name = (
            str(char1_data.get("nome")) if isinstance(char1_data, dict)
            else str(char1_data)
        )
        self.p2_name = (
            str(char2_data.get("nome")) if isinstance(char2_data, dict)
            else str(char2_data)
        )
        self.debug = bool(debug)
        self.runner = HeadlessMatchRunner(
            _match_config(self.p1_name, self.p2_name),
            max_frames=max_frames,
            fixed_dt=fixed_dt,
            seed=seed,
        )

    def executar(self) -> dict[str, Any]:
        result = self.runner.run()
        payload = result.to_dict()
        payload["vencedor"] = result.winner or "EMPATE"
        payload["erros"] = [] if result.success else [result.error]
        return payload


def _match_config(p1_name: str, p2_name: str) -> dict[str, Any]:
    return {
        "p1_nome": p1_name,
        "p2_nome": p2_name,
        "cenario": "Arena",
        "best_of": 1,
        "portrait_mode": False,
    }


def _roster_names() -> list[str]:
    names = [character.nome for character in database.carregar_personagens()]
    if len(names) < 2:
        raise RuntimeError("São necessários ao menos dois personagens válidos")
    return names


def executar_luta(
    p1_name: str,
    p2_name: str,
    *,
    seed: int = 0,
    fixed_dt: float = 1.0 / 60.0,
    max_frames: int = 3000,
) -> HeadlessMatchResult:
    return HeadlessMatchRunner(
        _match_config(p1_name, p2_name),
        seed=seed,
        fixed_dt=fixed_dt,
        max_frames=max_frames,
    ).run()


def executar_teste_rapido(
    p1_name: str | None = None,
    p2_name: str | None = None,
    **options: Any,
) -> HeadlessMatchResult:
    roster = _roster_names()
    return executar_luta(p1_name or roster[0], p2_name or roster[1], **options)


def executar_teste_stress(
    quantidade: int = 10,
    *,
    seed: int = 0,
    fixed_dt: float = 1.0 / 60.0,
    max_frames: int = 3000,
) -> list[HeadlessMatchResult]:
    if quantidade <= 0:
        raise ValueError("quantidade precisa ser positiva")
    roster = _roster_names()
    chooser = random.Random(seed)
    results = []
    for index in range(quantidade):
        p1_name, p2_name = chooser.sample(roster, 2)
        results.append(
            executar_luta(
                p1_name,
                p2_name,
                seed=seed + index,
                fixed_dt=fixed_dt,
                max_frames=max_frames,
            )
        )
    return results


def _print_result(result: HeadlessMatchResult) -> None:
    print(
        json.dumps(
            result.to_dict(),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Neural Fights - runner headless do motor real"
    )
    parser.add_argument("--mode", choices=("rapido", "stress", "all"), default="rapido")
    parser.add_argument("--p1")
    parser.add_argument("--p2")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--fixed-dt", type=float, default=1.0 / 60.0)
    parser.add_argument("--max-frames", type=int, default=3000)
    parser.add_argument("--stress-count", type=int, default=10)
    args = parser.parse_args(argv)

    try:
        results: list[HeadlessMatchResult] = []
        if args.mode in {"rapido", "all"}:
            results.append(
                executar_teste_rapido(
                    args.p1,
                    args.p2,
                    seed=args.seed,
                    fixed_dt=args.fixed_dt,
                    max_frames=args.max_frames,
                )
            )
        if args.mode in {"stress", "all"}:
            results.extend(
                executar_teste_stress(
                    args.stress_count,
                    seed=args.seed,
                    fixed_dt=args.fixed_dt,
                    max_frames=args.max_frames,
                )
            )
    except Exception as exc:
        print(
            json.dumps(
                {"success": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=True,
                allow_nan=False,
            )
        )
        return 1

    try:
        for result in results:
            _print_result(result)
    except (TypeError, ValueError) as exc:
        print(
            json.dumps(
                {"success": False, "error": f"serialization error: {exc}"},
                ensure_ascii=True,
                allow_nan=False,
            )
        )
        return 1
    return 0 if results and all(result.success for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
