# -*- coding: utf-8 -*-
"""SCR-P8 (14/10/2026): catalogo quebrado virava "0 prontos".

`inventario.estoque` copiava so `.get("prontos", 0)`, e `_videos_de_historia`
nem marcava erro: estoque zero e "nao consegui contar" eram o mesmo numero na
Vila e na Auditoria. Agora o lado que falhou vem `None`, o total fica `None`
e os erros aparecem.
"""
import unittest
from unittest import mock

from panorama import inventario


class EstoqueQueNaoContouTests(unittest.TestCase):
    def test_catalogo_quebrado_nao_e_zero(self):
        from builds.publicar import catalogo
        with mock.patch.object(catalogo, "listar",
                               side_effect=OSError("disco")), \
                mock.patch.object(inventario, "_videos_de_historia",
                                  return_value={"prontos": 7}):
            prontos = inventario.estoque()["videos_prontos"]
        self.assertIsNone(prontos["builds"])
        self.assertEqual(7, prontos["historias"])
        self.assertIsNone(prontos["total"])
        self.assertTrue(any("disco" in e for e in prontos["erros"]))

    def test_historias_quebradas_tambem(self):
        from contos.publicar import catalogo
        with mock.patch.object(catalogo, "resumo",
                               side_effect=ValueError("json")), \
                mock.patch.object(inventario, "_videos_de_build",
                                  return_value={"prontos": 3}):
            prontos = inventario.estoque()["videos_prontos"]
        self.assertIsNone(prontos["historias"])
        self.assertIsNone(prontos["total"])

    def test_caso_zero_estoque_vazio_de_verdade_e_zero(self):
        with mock.patch.object(inventario, "_videos_de_build",
                               return_value={"prontos": 0}), \
                mock.patch.object(inventario, "_videos_de_historia",
                                  return_value={"prontos": 0}):
            prontos = inventario.estoque()["videos_prontos"]
        self.assertEqual(0, prontos["total"])
        self.assertNotIn("erros", prontos)


if __name__ == "__main__":
    unittest.main()
