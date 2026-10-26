# -*- coding: utf-8 -*-
"""Historias: 3 por dia no YouTube e 1 no TikTok desde 27/10/2026.

Pedido do Adrian (26/10): "quero diminuir a frequencia das historias, esta
comendo muito tempo e eu vejo que nao da tantas views assim por quantidade".
Medido (historias, 01/10 a 26/10, videos com 3+ dias no ar): YouTube 21:37 =
8907 das 10605 views (84%; media 524 por video), 23:37 610, 06:37 601, e os
outros sete horarios 55 a 101 views em TRES SEMANAS (media 3 a 7). Ficam
06:37, 21:37 e 23:37; TikTok 21:37.

Contas de mao: de 27/10 o alvo de estoque cobre 3 horarios por dia, nao 10:
de terca 27/10 00:00 a quarta 28/10 00:00 sao 3 postagens (antes, 10); o teto
de estoque de 2 dias e 6 (antes, 20).
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import date, datetime
from pathlib import Path

from builds import grade
from contos.pipeline import agenda

GRADE_DAS_HISTORIAS_REAL = True        # ver o conftest.py da raiz
POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


class GradeTests(unittest.TestCase):
    def test_de_27_10_tres_e_um(self):
        dia = date(2026, 10, 27)
        self.assertEqual(grade.horas_do_canal("historias", "youtube", dia),
                         (6, 21, 23))
        self.assertEqual(grade.horas_do_canal("historias", "tiktok", dia),
                         (21,))
        self.assertEqual(grade.meta_diaria("historias", "youtube", dia), 3)

    def test_ate_26_10_os_dez_e_os_seis(self):
        dia = date(2026, 10, 26)
        self.assertEqual(len(grade.horas_do_canal("historias", "youtube", dia)),
                         10)
        self.assertEqual(len(grade.horas_do_canal("historias", "tiktok", dia)),
                         6)

    def test_os_duelos_nao_mudaram(self):
        self.assertEqual(grade.horas_do_canal("builds", "youtube",
                                              date(2026, 10, 27)),
                         (6, 9, 12, 15, 17, 21, 22, 23))

    def test_tiktok_e_subconjunto_do_youtube(self):
        dia = date(2026, 10, 27)
        self.assertTrue(set(grade.horas_do_canal("historias", "tiktok", dia))
                        <= set(grade.horas_do_canal("historias", "youtube",
                                                    dia)))


class AlvoDoEstoqueTests(unittest.TestCase):
    def test_postagens_entre_conta_so_os_horarios_das_historias(self):
        self.assertEqual(agenda.postagens_entre(datetime(2026, 10, 27, 0, 0),
                                                datetime(2026, 10, 28, 0, 0)), 3)
        self.assertEqual(agenda.postagens_entre(datetime(2026, 10, 20, 0, 0),
                                                datetime(2026, 10, 21, 0, 0)), 10)

    def test_teto_de_estoque_de_dois_dias(self):
        self.assertEqual(agenda.teto_de_estoque({"teto_por_historia_no_dia": 2}),
                         3 * 2 if date.today() >= date(2026, 10, 27)
                         else 10 * 2)

    def test_o_piso_do_config_e_6(self):
        self.assertEqual(agenda.carregar()["piso_de_reposicao"], 6)


class PortaDaRodadaTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("postar_h3", POSTAR)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.chamadas = []
        self.m.postar_historia = lambda so_ver=False: (
            self.chamadas.append(so_ver) or {"canal": "historias",
                                              "feito": True})

    def test_fora_dos_tres_a_ficha_e_calada_e_nao_le_nada(self):
        for hora, minuto in ((9, 40), (12, 10), (15, 40), (20, 40), (22, 40)):
            with self.subTest(hora=hora):
                ficha = self.m.postar_historia_na_grade(
                    agora=datetime(2026, 10, 27, hora, minuto))
                self.assertTrue(ficha["fora_da_grade"])
                self.assertFalse(ficha["feito"])
        self.assertEqual(self.chamadas, [])

    def test_nos_tres_horarios_publica(self):
        for hora, minuto in ((6, 40), (21, 40), (23, 40)):
            with self.subTest(hora=hora):
                ficha = self.m.postar_historia_na_grade(
                    agora=datetime(2026, 10, 27, hora, minuto))
                self.assertTrue(ficha["feito"])
        self.assertEqual(len(self.chamadas), 3)

    def test_antes_de_27_10_nada_muda(self):
        """O caso ZERO da regra nova: todos os dez horarios publicam."""
        for hora, minuto in ((0, 40), (9, 40), (12, 10), (20, 40)):
            ficha = self.m.postar_historia_na_grade(
                agora=datetime(2026, 10, 26, hora, minuto))
            self.assertTrue(ficha["feito"])
        self.assertEqual(len(self.chamadas), 4)


if __name__ == "__main__":
    unittest.main()
