# -*- coding: utf-8 -*-
"""PUB-5: a falha de leitura do banco nao fica guardada para o resto do processo.

Auditoria de 11/10/2026 (`publicar-builds.md` #6): `_nomes_no_banco` tinha
`@lru_cache(maxsize=1)` com `return None` no `except` — uma leitura que
falhou uma vez fazia toda build sem estreia dizer "estreia nao gravada"
(tarefa) em vez de "estreia impossivel" (lapide) ate o app ou o bot
reiniciar. Medido no HEAD: a 2a chamada devolvia `None` e o dublê era chamado
1 vez. Agora: `frozenset({"Ana"})` e 2 chamadas.
"""
from __future__ import annotations

import unittest

from builds.publicar import catalogo


class _BancoDeMentira:
    def __init__(self):
        self.chamadas = 0

    def carregar_database(self):
        self.chamadas += 1
        if self.chamadas == 1:
            raise OSError("banco trancado")
        return {}, [{"nome": "Ana"}, {"nome": ""}]


class NomesNoBancoTests(unittest.TestCase):
    def setUp(self):
        from builds.nf_bridge import loader
        self.banco = _BancoDeMentira()
        antes = loader.database
        self.addCleanup(setattr, loader, "database", antes)
        loader.database = self.banco
        catalogo._nomes_no_banco.cache_clear()
        self.addCleanup(catalogo._nomes_no_banco.cache_clear)

    def test_a_falha_nao_fica_guardada(self):
        self.assertIsNone(catalogo._nomes_no_banco())
        self.assertEqual(frozenset({"Ana"}), catalogo._nomes_no_banco())
        self.assertEqual(2, self.banco.chamadas)

    def test_o_acerto_fica_guardado(self):
        catalogo._nomes_no_banco()
        catalogo._nomes_no_banco()
        catalogo._nomes_no_banco()
        self.assertEqual(2, self.banco.chamadas, "le de novo so depois da falha")


if __name__ == "__main__":
    unittest.main()
