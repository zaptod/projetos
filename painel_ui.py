# -*- coding: utf-8 -*-
"""Atalho para o painel, que agora e um PACOTE.

Este arquivo tinha 4583 linhas e uma classe com 191 metodos. Virou
`painel/`: estilo, widgets, processos, casca e uma pagina por arquivo.

Ele continua existindo so para quem tem o costume de rodar
`python painel_ui.py`. O caminho de verdade e:

    python -m painel
    painel.bat
"""
from painel.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
