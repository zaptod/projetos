# -*- coding: utf-8 -*-
"""SCR-P9 (14/10/2026): `qualidade._alvos_do_jogo` lia um arquivo que nada
escrevia (`relatorio_qualidade.json`) — "nunca avaliado" para sempre.

O campo saiu. A guarda: o panorama nao le esse arquivo enquanto ninguem fora
de `visao/` o escrever.
"""
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


class SemLeitorSemEscritorTests(unittest.TestCase):
    def test_panorama_nao_le_relatorio_sem_escritor(self):
        nome = "relatorio_qualidade" + ".json"
        leitores = [p for p in (RAIZ / "visao" / "panorama").rglob("*.py")
                    if nome in p.read_text(encoding="utf-8", errors="replace")]
        if not leitores:
            return
        escritores = []
        for pasta in ("neural_fights", "random_builds", "ferramentas"):
            for p in (RAIZ / pasta).rglob("*.py"):
                if nome in p.read_text(encoding="utf-8", errors="replace"):
                    escritores.append(p)
        self.assertTrue(escritores, f"{leitores} le {nome} e ninguem escreve")


if __name__ == "__main__":
    unittest.main()
