# -*- coding: utf-8 -*-
"""    python -m painel            abre
    python -m painel --smoke    monta todas as paginas e sai (usado por testar.py)
"""
from __future__ import annotations

import sys

from .app import Casca
from .paginas import contas, fluxo, historias, jogo, publicar, vila


# A ordem aqui e a ordem do menu.
PAGINAS = [vila.Pagina, fluxo.Pagina, publicar.Pagina,
           historias.Pagina, contas.Pagina,
           jogo.Simulacao, jogo.Database, jogo.Live]


def main(argv=None) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    app = Casca.criar(PAGINAS, tema="oficina")
    if "--smoke" in argumentos:
        for chave in list(app.paginas):
            app.mostrar(chave)
            app.update()
        print("smoke ok: " + ", ".join(app.paginas))
        app.encerrar()
        app.destroy()
        return 0
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
