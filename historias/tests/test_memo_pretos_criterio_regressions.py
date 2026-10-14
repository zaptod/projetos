# -*- coding: utf-8 -*-
"""PUB-7: o memo dos trechos pretos leva o CRITERIO na chave.

Auditoria de 11/10/2026 (`publicar-historias.md` #10): a chave era
`real|mtime|size|layout`, e mudar `PRETO_AREA`/`PRETO_PIXEL` nao media de novo
nada que ja tinha sido medido, ate o mp4 ser re-renderizado. Medido no HEAD:
o contador da medida ficava em 1 depois de trocar `PRETO_AREA`. Agora vai a 2.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contos.publicar import qualidade as Q


class MemoComCriterioTests(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.mp4 = Path(pasta.name) / "final_celular_p01.mp4"
        self.mp4.write_bytes(b"x" * 10)
        Q._PRETOS_MEDIDOS.clear()
        self.addCleanup(Q._PRETOS_MEDIDOS.clear)

    def test_mudar_o_criterio_mede_de_novo(self):
        with mock.patch.object(Q, "trechos_pretos", return_value=[]) as medir:
            Q.erros_de_preto(self.mp4, "dividido")
            Q.erros_de_preto(self.mp4, "dividido")
            self.assertEqual(1, medir.call_count, "o mesmo criterio: memo")
            with mock.patch.object(Q, "PRETO_AREA", Q.PRETO_AREA - 0.05):
                Q.erros_de_preto(self.mp4, "dividido")
            self.assertEqual(2, medir.call_count)
            with mock.patch.object(Q, "PRETO_PIXEL", Q.PRETO_PIXEL + 0.02):
                Q.erros_de_preto(self.mp4, "dividido")
            self.assertEqual(3, medir.call_count)


if __name__ == "__main__":
    unittest.main()
