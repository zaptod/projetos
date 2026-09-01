# -*- coding: utf-8 -*-
"""A camada de video do random_builds: roleta de build -> video publicado.

O pacote se chamava `src` ate 01/09/2026, e o de historias tambem. Dois
pacotes de topo com o mesmo nome nao convivem: qual deles ganha depende da
ORDEM do `sys.path`, e - pior - este aqui era um namespace PEP 420 (sem
`__init__.py`) enquanto o outro era um pacote regular. Pacote regular ganha
de namespace SEM ERRO NENHUM, entao a troca aconteceria em silencio.

O sintoma que isso causava: o painel nao conseguia importar historias de
jeito nenhum (o nome `src` ja estava tomado) e falava com aquele projeto por
`subprocess` com codigo Python dentro de uma string.

Este arquivo existe, e nao esta vazio de proposito: sem `__init__.py` o
pacote volta a ser namespace e a colisao volta a ser possivel.
"""
