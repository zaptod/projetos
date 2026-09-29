# -*- coding: utf-8 -*-
"""    python -m ias sondar <ia>|todas [--sem-gastar] [--headless]
    python -m ias fichas [--json]
    python -m ias tabela-png <saida.png>

`sondar` abre o navegador da IA (uma por vez, com a trava da conta) e
regrava `ias/fichas/<ia>.json`. `--sem-gastar` so olha (login, modelos,
campo, anexo) e nao manda mensagem nem pede imagem.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import IAS, ficha as fichas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ias",
                                     description="fichas de capacidades das IAs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sondar", help="refaz a sonda de uma IA (ou todas)")
    s.add_argument("ia", choices=IAS + ("todas",))
    s.add_argument("--sem-gastar", action="store_true",
                   help="nao manda mensagem nem pede imagem (so olha a tela)")
    s.add_argument("--headless", action="store_true")

    f = sub.add_parser("fichas", help="imprime a tabela comparativa")
    f.add_argument("--json", action="store_true")

    t = sub.add_parser("tabela-png", help="a tabela em PNG")
    t.add_argument("saida")

    g = sub.add_parser("guia", help="sessao GUIADA: abre a IA na tela, o Adrian mostra, grava")
    g.add_argument("ia", choices=IAS)
    g.add_argument("--limite-min", type=float, default=240.0)

    e = sub.add_parser("eventos", help="os cliques gravados na sessao guiada, por passo")
    e.add_argument("ia", choices=IAS)

    args = parser.parse_args(argv)

    if args.cmd == "guia":
        from . import guia
        resumo = guia.rodar(args.ia, limite_min=args.limite_min)
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "eventos":
        from . import guia
        for ev in guia.resumir_eventos(args.ia):
            print(json.dumps(ev, ensure_ascii=False))
        return 0

    if args.cmd == "sondar":
        from . import sonda
        alvos = list(IAS) if args.ia == "todas" else [args.ia]
        for ia in alvos:
            sonda.sondar(ia, gastar=not args.sem_gastar, headless=args.headless)
        print(fichas.tabela(fichas.todas(ias=alvos)))
        return 0
    if args.cmd == "fichas":
        todas = fichas.todas()
        if args.json:
            print(json.dumps(todas, ensure_ascii=False, indent=2))
        else:
            print(fichas.tabela(todas))
        return 0
    if args.cmd == "tabela-png":
        destino = fichas.tabela_png(fichas.todas(), args.saida,
                                    titulo=f"Fichas das IAs — {fichas.agora()[:16]}")
        print(destino)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
