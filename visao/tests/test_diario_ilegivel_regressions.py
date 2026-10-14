# -*- coding: utf-8 -*-
"""SCR-P3 (14/10/2026): diario ou ledger ilegivel viravam "zero" e o
veredito ficava verde.

`confiabilidade.hoje` fazia `eventos = lidos or []` e `_ledger` devolvia `[]`
na excecao: "0 falhas, prometido 0", o retrato de um dia calmo. `saude.agora`
e `qualidade.problemas` liam o diario sem distinguir ausente de vazio.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from builds import atividade
from builds.publicar import metricas, sinais
from panorama import confiabilidade, qualidade, saude


class DiarioIlegivelTests(unittest.TestCase):
    def test_diario_ilegivel_nao_e_dia_calmo(self):
        with mock.patch.object(sinais, "ler_diario", return_value=None):
            ficha = confiabilidade.hoje(builds=[], historias=[],
                                        conferencias={}, marca={})
        self.assertNotEqual("ok", ficha["veredito"])
        self.assertTrue(any("diário" in a for a in ficha["alertas"]),
                        ficha["alertas"])

    def test_ledger_ilegivel_acende(self):
        with mock.patch.object(metricas, "publicados",
                               side_effect=OSError("trancado")):
            ficha = confiabilidade.hoje(historias=[], eventos=[],
                                        conferencias={}, marca={})
        self.assertFalse(ficha["ledger_lido"]["builds"])
        self.assertTrue(any("ledger de builds" in a for a in ficha["alertas"]))

    def test_caso_zero_lido_e_vazio_nao_acende_leitura(self):
        ficha = confiabilidade.hoje(builds=[], historias=[], eventos=[],
                                    conferencias={}, marca={})
        self.assertTrue(ficha["diario_lido"])
        self.assertFalse(any("não consegui ler" in a for a in ficha["alertas"]))

    def test_saude_e_qualidade_com_diario_ausente_dizem_erro(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(atividade, "_arquivo",
                                  return_value=Path(tmp) / "nao" / "a.jsonl"):
            self.assertIn("erro", qualidade.problemas())
            self.assertIn("erro", saude.agora())


if __name__ == "__main__":
    unittest.main()
