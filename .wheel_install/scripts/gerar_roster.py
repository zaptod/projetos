"""CLI para gerar rosters validos do Neural Fights.

O script apenas combina a API canonica do gerador com a persistencia
transacional. Catalogos paralelos de skills e personalidades nao sao mantidos
aqui.
"""

from __future__ import annotations

import argparse

from tools.gerador_database import gerar_database_completa, salvar_database


def _gerar_e_salvar(quantidade: int, estrategia: str, *, seed=None):
    armas, personagens = gerar_database_completa(quantidade, estrategia, seed=seed)
    salvar_database(armas, personagens, substituir=True)
    print(
        f"Roster valido gerado: {len(personagens)} personagens e "
        f"{len(armas)} armas."
    )
    return armas, personagens


def gerar_roster_completo(*, seed=None):
    """Gera o roster padrao de 64 lutadores."""

    return _gerar_e_salvar(64, "diversa", seed=seed)


def gerar_roster_torneio_64(*, seed=None):
    """Gera um roster balanceado para torneio de 64 lutadores."""

    return _gerar_e_salvar(64, "balanceada", seed=seed)


def gerar_roster_torneio_16(*, seed=None):
    """Gera um roster representativo para torneio de 16 lutadores."""

    return _gerar_e_salvar(16, "representativa", seed=seed)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gerador de roster Neural Fights")
    parser.add_argument(
        "--modo",
        choices=("completo", "64", "16"),
        default="completo",
        help="tamanho e estrategia do roster",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="seed opcional para gerar exatamente o mesmo roster",
    )
    args = parser.parse_args(argv)

    geradores = {
        "completo": gerar_roster_completo,
        "64": gerar_roster_torneio_64,
        "16": gerar_roster_torneio_16,
    }
    geradores[args.modo](seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
