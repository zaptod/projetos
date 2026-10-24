# -*- coding: utf-8 -*-
"""O piso de duelos olha a grade dos PROXIMOS dias, nao so a de hoje (24/10/2026).

Medido em 24/10 08:36: estoque 26 duelos, grade de 3 por dia, piso 4 x 3 = 12
=> a geracao nao fez um duelo em 22, 23 e 24/10 (0 em 3 dias, diarios
`gerar_*.txt`). A decisao `publicacao/semana-2-volume` poe 8 duelos por dia no
YouTube a partir de 27/10: 26 duelos viram 3,25 dias, e como o consumo era o
de HOJE o piso so subia (4 x 8 = 32) no dia da troca, sem tempo de gerar.
Agora o consumo do piso e o maior dos proximos `piso_por_formato_em_dias`
dias, cada um pela grade DO DIA; a troca de grade que entrar em
`grade.HORAS_POR_CANAL_DESDE` acende a geracao 3 dias antes, sem ninguem
lembrar de mexer no config (e sem reverter nada depois).
"""
from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest import mock

from builds import grade
from builds.pipeline import noite

PUB = {"grade": {"mistura": {"duelo": 4, "build": 3, "estreia": 1,
                             "torneio": 0}}}
OITO = (6, 9, 12, 15, 17, 20, 21, 22)
COM_8 = grade.HORAS_POR_CANAL_DESDE + (
    (date(2026, 10, 27), {"builds": {"youtube": OITO, "tiktok": (21,)}}),)


def _as(dia, h, m=0):
    return datetime(dia.year, dia.month, dia.day, h, m)


class PisoOlhaAFrente(unittest.TestCase):

    def setUp(self):
        self.config = noite.carregar()

    def _com_8(self):
        return mock.patch.object(grade, "HORAS_POR_CANAL_DESDE", COM_8)

    def test_consumo_por_dia_pelo_dia(self):
        with self._com_8():
            self.assertEqual(3.0, noite.consumo_por_dia(
                PUB, quando=date(2026, 10, 26))["duelo"])
            self.assertEqual(8.0, noite.consumo_por_dia(
                PUB, quando=date(2026, 10, 27))["duelo"])

    def test_sem_agora_e_o_de_hoje_como_antes(self):
        with self._com_8():
            self.assertEqual(12, noite.piso_do_formato(
                "duelo", self.config, PUB))

    def test_sabado_ja_enxerga_o_dia_27(self):
        # 24, 25, 26 e 27/10: o 27 tem 8 => 4 x 8 = 32
        with self._com_8():
            piso = noite.piso_do_formato("duelo", self.config, PUB,
                                         _as(date(2026, 10, 24), 8, 2))
        self.assertEqual(32, piso)

    def test_sexta_ainda_nao(self):
        # 23..26/10: tudo 3 por dia
        with self._com_8():
            piso = noite.piso_do_formato("duelo", self.config, PUB,
                                         _as(date(2026, 10, 23), 8, 2))
        self.assertEqual(12, piso)

    def test_depois_da_troca_continua_32(self):
        with self._com_8():
            piso = noite.piso_do_formato("duelo", self.config, PUB,
                                         _as(date(2026, 10, 28), 8, 2))
        self.assertEqual(32, piso)

    def test_caso_zero_sem_troca_nada_muda(self):
        # a grade de hoje no repositorio (3 por dia): o piso e o de sempre
        self.assertEqual(12, noite.piso_do_formato(
            "duelo", self.config, PUB, _as(date(2026, 10, 24), 8, 2)))

    def test_o_estoque_de_24_10_passa_a_faltar_na_reposicao(self):
        """26 duelos prontos, sabado 08:02: com a grade de 8 a partir de 27/10
        a meta de reposicao e 32 e faltam 6; sem a grade nova, nenhum."""
        agora = _as(date(2026, 10, 24), 8, 2)
        with self._com_8():
            metas = noite.metas_do_plano(self.config, agora, "reposicao", PUB)
        self.assertEqual(32, metas["duelo"])
        self.assertEqual(6, max(0, metas["duelo"] - 26))
        sem = noite.metas_do_plano(self.config, agora, "reposicao", PUB)
        self.assertEqual(12, sem["duelo"])

    def test_lote_de_segunda_26_10_cobre_a_semana_de_8(self):
        """Segunda 26/10 07:02 -> 02/11 07:00: 26/10 tem 3, 27..31/10 tem 8
        (5 dias), 01/11 tem 3 (grade de 01/11) e 02/11 mais 0 ate as 07h
        => cobertura de postagens do YouTube; o piso entra por cima."""
        agora = _as(date(2026, 10, 26), 7, 2)
        with self._com_8():
            metas = noite.metas_do_plano(self.config, agora, "lote", PUB)
            fim = noite.fim_da_cobertura(self.config, agora)
            cobre = noite.postagens_da_plataforma(agora, fim, "youtube")
        self.assertEqual(32 + cobre, metas["duelo"])
        self.assertGreater(metas["duelo"], 70)


if __name__ == "__main__":
    unittest.main()
