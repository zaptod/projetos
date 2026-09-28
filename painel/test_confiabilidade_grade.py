# -*- coding: utf-8 -*-
"""O cartao CONFERENCIA nao pode dar ✓ para grade furada.

Ate 28/09/2026 a linha era so o veredito do ledger: um canal com 5 de 10
horarios cumpridos aparecia como "builds: ✓ 5/5" — ledger coerente, grade
furada, e um tique verde. Funcao pura: nada aqui abre janela.
"""
import unittest

from painel.paginas.confiabilidade import _linha_da_conferencia


def _conf(**extra):
    base = {"estado": "limpo", "casados": 5, "no_ledger": 5,
            "fantasmas": 0, "rascunhos": 0}
    base.update(extra)
    return base


class ACartaDaGrade(unittest.TestCase):

    def test_ledger_limpo_com_grade_em_falta_nao_ganha_tique(self):
        linha = _linha_da_conferencia("builds", _conf(
            grade="em falta", horarios_cumpridos=5, slots_da_grade=10))
        self.assertTrue(linha.startswith("builds: ✕"))
        self.assertIn("grade 5/10", linha)
        self.assertIn("ledger ✓ 5/5", linha)

    def test_grade_cumprida_continua_verde(self):
        linha = _linha_da_conferencia("builds", _conf(
            grade="cumprida", horarios_cumpridos=10, slots_da_grade=10))
        self.assertEqual("builds: ✓ 5/5 · grade 10/10", linha)

    def test_sujo_mostra_a_grade_junto(self):
        linha = _linha_da_conferencia("historias", _conf(
            estado="sujo", fantasmas=1, grade="em falta",
            horarios_cumpridos=7, slots_da_grade=10))
        self.assertIn("✕ 1 fant.", linha)
        self.assertIn("grade 7/10", linha)

    def test_ficha_de_antes_da_grade_fica_como_era(self):
        # Ficha anterior a 27/09 nao sabe a grade: nao inventa placar.
        self.assertEqual("builds: ✓ 5/5",
                         _linha_da_conferencia("builds", _conf()))
        self.assertEqual("builds: não rodou",
                         _linha_da_conferencia("builds",
                                               {"estado": "falhou"}))


if __name__ == "__main__":
    unittest.main()
