# -*- coding: utf-8 -*-
"""HIS-4: biblia com menos partes passava e a retomada pedia "PARTE 6 de 5".

Auditoria profunda (11/10/2026): a porta de `gerar_serie` so exigia lista de
partes nao vazia. Uma biblia com 5 de 6 partes virava roteiro com
`partes_esperadas: 6`, `incompletas()` o devolvia sempre e a retomada pedia
ao LLM um episodio depois do fim, sem plano.

Decisao `historias/plano-com-menos-partes` (14/10/2026): "sai mais curta"
(nao perde o trabalho ja feito). Com menos de 2 partes nao e serie: falha.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.roteiro import gerar
from contos.roteiro import roteiro as R


def _biblia(n_partes: int, pedidas: int = 6) -> dict:
    return {"titulo": "T", "partes_esperadas": pedidas,
            "partes": [{"n": i, "titulo": f"p{i}"} for i in range(1, n_partes + 1)]}


class BibliaCurtaTests(unittest.TestCase):
    def test_cinco_de_seis_vira_serie_de_cinco(self):
        falas = []
        biblia = gerar._biblia_curta_vira_serie_curta(_biblia(5), Path("x"),
                                                      falas.append)
        self.assertEqual(5, biblia["partes_esperadas"])
        self.assertTrue(any("5 de 6" in f for f in falas), falas)
        roteiro = {"partes_esperadas": biblia["partes_esperadas"],
                   "partes": [{"n": i} for i in range(1, 6)]}
        self.assertEqual([], R.partes_que_faltam(roteiro))

    def test_biblia_inteira_nao_muda(self):
        biblia = _biblia(6)
        self.assertIs(biblia, gerar._biblia_curta_vira_serie_curta(
            biblia, Path("x"), lambda *_: None))

    def test_uma_parte_so_nao_e_serie(self):
        with self.assertRaises(gerar.GeracaoFalhou):
            gerar._biblia_curta_vira_serie_curta(_biblia(1), Path("x"),
                                                 lambda *_: None)


class RetomadaSemPlanoTests(unittest.TestCase):
    def _retomar(self, n_plano: int, prontas: int):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / "historia_00099"
            pasta.mkdir()
            (pasta / "biblia.json").write_text(json.dumps(_biblia(n_plano)),
                                               encoding="utf-8")
            roteiro = {"partes_esperadas": 6,
                       "partes": [{"n": i} for i in range(1, prontas + 1)]}
            (pasta / "roteiro.json").write_text(json.dumps(roteiro),
                                                encoding="utf-8")
            with mock.patch.object(gerar, "OUTPUTS", Path(tmp)), \
                    mock.patch.object(R, "carregar", return_value=roteiro), \
                    mock.patch("contos.llm.cliente.abrir_cliente",
                               side_effect=AssertionError("pediu ao modelo")):
                try:
                    resultado = gerar.retomar_serie("historia_00099",
                                                    log=lambda *_: None)
                finally:
                    gravado = json.loads((pasta / "roteiro.json").read_text(
                        encoding="utf-8"))
        return resultado, gravado

    def test_roteiro_antigo_sai_mais_curto_sem_pedir_ao_modelo(self):
        """Plano com 5, `partes_esperadas` 6, partes 1-5 prontas: nada a
        pedir ("PARTE 6 de 5" era o pedido de antes) e o roteiro passa a 5."""
        resultado, gravado = self._retomar(5, 5)
        self.assertTrue(resultado["encurtada"])
        self.assertEqual(0, resultado["partes"])
        self.assertEqual(5, gravado["partes_esperadas"])

    def test_plano_de_uma_parte_falha(self):
        with self.assertRaises(gerar.GeracaoFalhou):
            self._retomar(1, 1)


if __name__ == "__main__":
    unittest.main()
