# -*- coding: utf-8 -*-
"""SCR-P2 (14/10/2026), a parte que ficou: `views`/`retencao` eram so de
builds, ao lado de um `total` dos dois canais, e as metricas de historias
nao apareciam em lugar nenhum do panorama. (O "atualizado em" pelo mtime da
marca foi consertado no d76b7ef.)
"""
import unittest
from unittest import mock

from panorama import desempenho


class PorCanalTests(unittest.TestCase):
    def test_historias_aparecem_separadas(self):
        salvas = {"builds": [{"views": 10, "likes": 1, "media_percentual": 40.0}],
                  "historias": [{"views": 7, "likes": 2, "media_percentual": 60.0},
                                {"erro": "sem analytics"}]}
        with mock.patch.object(desempenho, "_salvas",
                               side_effect=lambda canal="builds": salvas[canal]), \
                mock.patch.object(desempenho, "_builds", return_value=[]), \
                mock.patch.object(desempenho, "_historias", return_value=[]), \
                mock.patch.object(desempenho, "_quando_atualizou",
                                  return_value=""):
            ficha = desempenho.publicado()
        self.assertEqual("builds", ficha["metricas_de"])
        self.assertEqual(10, ficha["views"])
        por = ficha["metricas_por_canal"]
        self.assertEqual({"com_metrica": 1, "views": 7, "likes": 2,
                          "retencao_media": 60.0}, por["historias"])
        self.assertEqual(10, por["builds"]["views"])

    def test_caso_zero_sem_metrica(self):
        with mock.patch.object(desempenho, "_salvas", return_value=[]), \
                mock.patch.object(desempenho, "_builds", return_value=[]), \
                mock.patch.object(desempenho, "_historias", return_value=[]), \
                mock.patch.object(desempenho, "_quando_atualizou",
                                  return_value=""):
            ficha = desempenho.publicado()
        self.assertIsNone(ficha["metricas_por_canal"]["historias"]["retencao_media"])
        self.assertEqual(0, ficha["metricas_por_canal"]["historias"]["com_metrica"])


if __name__ == "__main__":
    unittest.main()
