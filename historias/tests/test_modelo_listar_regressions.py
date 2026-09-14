# -*- coding: utf-8 -*-
"""A listagem de modelos ignora comentario (14/09/2026).

`python main.py modelos` quebrava com `'str' object has no attribute 'get'`:
o config de roteiro explica cada molde numa chave `_comment_*` ao lado dele,
e a listagem tratava esse texto como molde.
"""
from __future__ import annotations

import unittest

from contos.roteiro import modelo


class ListarTests(unittest.TestCase):

    def test_comentario_no_meio_dos_modelos_nao_vira_modelo(self):
        config = {"modelos": {
            "reddit": {"rotulo": "Relato", "cenas_alvo": 12},
            "_comment_quebrada": "outra categoria, e nao mais um molde",
            "quebrada": {"rotulo": "Quebrada", "cenas_alvo": 14}}}
        nomes = [m["nome"] for m in modelo.listar(config)
                 if m["origem"] == "config"]
        self.assertEqual(["reddit", "quebrada"], nomes)

    def test_o_config_de_verdade_lista_sem_quebrar(self):
        listados = [m for m in modelo.listar() if m["origem"] == "config"]
        self.assertTrue(listados)
        self.assertFalse(any(str(m["nome"]).startswith("_") for m in listados))


if __name__ == "__main__":
    unittest.main()
