# -*- coding: utf-8 -*-
"""A Oficina de sprites sem janela.

    python -m painel.sprites medir FOLHA.png [--receita R.json]
    python -m painel.sprites lote A.png B.png --saida PASTA [--receita R.json]

`medir` imprime as medidas (antes e depois) em JSON; `lote` limpa varias
folhas com a mesma receita. A janela e `python -m painel --janela oficina`.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import limpeza, medidas
from .lote import limpar_lote
from .receita import Receita, processar


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="painel.sprites",
                                     description="a Oficina de sprites")
    sub = parser.add_subparsers(dest="comando", required=True)
    pm = sub.add_parser("medir", help="limpa e mede uma folha")
    pm.add_argument("folha")
    pm.add_argument("--receita")
    pl = sub.add_parser("lote", help="a mesma receita em varias folhas")
    pl.add_argument("folhas", nargs="+")
    pl.add_argument("--saida", required=True)
    pl.add_argument("--receita")
    args = parser.parse_args(argv)
    receita = Receita.ler(args.receita) if args.receita else Receita()

    if args.comando == "medir":
        res = processar(limpeza.abrir(args.folha), receita)
        print(json.dumps(medidas.medir(res, receita), ensure_ascii=False,
                         indent=1))
        return 0
    falhas = 0
    for linha in limpar_lote(args.folhas, receita, args.saida):
        falhas += bool(linha.get("erro"))
        print(f"{linha['arquivo']}: {linha['resumo']}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
