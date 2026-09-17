# -*- coding: utf-8 -*-
"""Dois cliques: abre a Vila flutuante SEM console (o .pyw roda no pythonw).

O mesmo que `python -m painel.flutuante`. Se ja houver uma aberta, esta
sai na hora — nao nascem duas.
"""
from painel.flutuante.__main__ import main

raise SystemExit(main())
