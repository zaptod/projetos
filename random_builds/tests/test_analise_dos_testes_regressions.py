# -*- coding: utf-8 -*-
"""A Analise dos videos mostra o resultado dos testes de 19/10/2026.

Teste do TikTok (decisao `tiktok-seis-por-dia`): ANTES x DURANTE, por
perfil — views por dia somadas dos videos postados no dia e mediana por
post. Conta de mao do caso abaixo (teste de 3 dias, de 10 a 12/10; antes =
07 a 09/10):
  antes:   10 posts/dia x 2 views  -> 20 views/dia, 2 por post
  durante:  6 posts/dia x 50 views -> 300 views/dia, 50 por post
  -> "efeito" (300 > 20, dia contra dia p < 0,05).
Com 6 x 3 views (18/dia) -> "sem efeito", e a recomendacao do proximo teste
e um dia inteiro sem postar. ZERO (nenhum video) -> "sem dados", nunca
"efeito". Dia que ainda nao fez 3 dias nao entra (nem como zero).
"""
from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from builds.publicar import analise

TESTE = {"inicio": date(2026, 10, 10), "fim": date(2026, 10, 12)}


def _reg(canal, dia: date, i: int, views: int, agora: datetime, plataforma="tiktok"):
    quando = datetime(dia.year, dia.month, dia.day, 9 + i, 37)
    return {"id": f"{canal}{dia.isoformat()}{i}", "canal": canal,
            "plataforma": plataforma, "quando": quando.isoformat(timespec="seconds"),
            "views": views, "hora": quando.hour,
            "idade_dias": round((agora - quando).total_seconds() / 86400.0, 2)}


def _dias(inicio, n):
    return [inicio + timedelta(days=k) for k in range(n)]


class TesteDoTiktokTests(unittest.TestCase):
    def _regs(self, agora, por_dia_antes, views_antes, por_dia_durante, views_durante):
        regs = []
        for canal in ("builds", "historias"):
            for d in _dias(date(2026, 10, 7), 3):
                regs += [_reg(canal, d, i, views_antes, agora) for i in range(por_dia_antes)]
            for d in _dias(date(2026, 10, 10), 3):
                regs += [_reg(canal, d, i, views_durante, agora)
                         for i in range(por_dia_durante)]
        return regs

    def test_efeito_conta_de_mao(self):
        agora = datetime(2026, 10, 20, 12, 0)
        r = analise.resultado_do_teste_tiktok(self._regs(agora, 10, 2, 6, 50),
                                              agora, TESTE)
        self.assertEqual("terminado", r["estado"])
        self.assertEqual("2026-10-07", r["antes_de"])
        p = r["perfis"]["builds"]
        self.assertEqual(20, p["antes"]["views_por_dia"])
        self.assertEqual(300, p["durante"]["views_por_dia"])
        self.assertEqual(2, p["antes"]["por_post"])
        self.assertEqual(50, p["durante"]["por_post"])
        self.assertEqual(6, p["durante"]["posts_por_dia"])
        self.assertEqual("efeito", p["veredito"])
        self.assertNotIn("proximo_teste", p)

    def test_sem_efeito_recomenda_um_dia_sem_postar(self):
        agora = datetime(2026, 10, 20, 12, 0)
        r = analise.resultado_do_teste_tiktok(self._regs(agora, 10, 2, 6, 3),
                                              agora, TESTE)
        p = r["perfis"]["historias"]
        self.assertEqual("sem_efeito", p["veredito"])
        self.assertIn("dia inteiro sem postar", p["proximo_teste"])

    def test_zero_nao_e_efeito(self):
        agora = datetime(2026, 10, 20, 12, 0)
        r = analise.resultado_do_teste_tiktok([], agora, TESTE)
        for canal in ("builds", "historias"):
            self.assertEqual("sem_dados", r["perfis"][canal]["veredito"])

    def test_em_andamento_nao_conta_dia_que_nao_fez_3_dias(self):
        agora = datetime(2026, 10, 13, 12, 0)
        r = analise.resultado_do_teste_tiktok(self._regs(agora, 10, 2, 6, 50),
                                              agora, TESTE)
        self.assertEqual("em_andamento", r["estado"])
        p = r["perfis"]["builds"]
        self.assertEqual("juntando", p["veredito"])
        self.assertEqual(0, p["durante"]["dias_maduros"],
                         "10/10 as 9:37 ainda nao tem 3 dias inteiros as 12h de 13/10?")

    def test_dia_com_mais_de_seis_e_apontado(self):
        agora = datetime(2026, 10, 20, 12, 0)
        r = analise.resultado_do_teste_tiktok(self._regs(agora, 10, 2, 8, 50),
                                              agora, TESTE)
        self.assertEqual(["2026-10-10", "2026-10-11", "2026-10-12"],
                         r["perfis"]["builds"]["dias_fora_do_regime"])

    def test_views_aos_3_dias_pela_fotografia(self):
        """O video de antes tem mais dias no ar: com fotografia, conta-se o que
        ele tinha aos 3 dias."""
        agora = datetime(2026, 10, 20, 12, 0)
        regs = self._regs(agora, 1, 100, 1, 50)
        fotos = {}
        for r in regs:
            dia = (date.fromisoformat(r["quando"][:10]) + timedelta(days=3)).isoformat()
            parte = analise.nome_da_parte(r["canal"], r["plataforma"])
            fotos.setdefault(dia, {}).setdefault(parte, {})[r["id"]] = [10, 0, None]
        r = analise.resultado_do_teste_tiktok(regs, agora, TESTE, fotos=fotos)
        self.assertEqual(10, r["perfis"]["builds"]["antes"]["views_por_dia"])
        self.assertTrue(r["perfis"]["builds"]["antes"]["dias"][0]["pela_foto"])

    def test_fotografia_so_de_um_lado_usa_o_total_nos_dois(self):
        """Medida misturada (antes pelo total, durante aos 3 dias) daria vies;
        sem fotografia para todos, os dois lados usam o total de hoje."""
        agora = datetime(2026, 10, 20, 12, 0)
        regs = self._regs(agora, 1, 100, 1, 50)
        fotos = {}
        for r in regs:
            if r["quando"] >= "2026-10-10":
                dia = (date.fromisoformat(r["quando"][:10]) + timedelta(days=3)).isoformat()
                parte = analise.nome_da_parte(r["canal"], r["plataforma"])
                fotos.setdefault(dia, {}).setdefault(parte, {})[r["id"]] = [10, 0, None]
        r = analise.resultado_do_teste_tiktok(regs, agora, TESTE, fotos=fotos)
        p = r["perfis"]["builds"]
        self.assertEqual((100, 50), (p["antes"]["views_por_dia"], p["durante"]["views_por_dia"]))
        self.assertIn("hoje", p["medida"])

    def test_sem_teste_no_config(self):
        self.assertEqual("sem_teste", analise.resultado_do_teste_tiktok(
            [], datetime(2026, 10, 20), None)["estado"])

    def test_aparece_na_analise_e_na_pagina(self):
        agora = datetime(2026, 10, 20, 12, 0)
        regs = self._regs(agora, 10, 2, 6, 50)
        a = analise.analisar(regs, {"estado": "ok", "partes": {}}, agora,
                             testes={analise.TESTE_DO_TIKTOK: TESTE})
        self.assertIn(analise.TESTE_DO_TIKTOK, a["testes"])
        html = analise.pagina(a)
        self.assertIn("<h2>Testes</h2>", html)
        self.assertIn("deu efeito", html)


class TesteDaParteSeguinteTests(unittest.TestCase):
    def test_antes_e_durante(self):
        agora = datetime(2026, 10, 20, 12, 0)

        def par(fonte, dia, views_n, views_seguinte):
            q1 = datetime(dia.year, dia.month, dia.day, 21, 37)
            q2 = q1 + timedelta(hours=1)
            base = {"canal": "historias", "plataforma": "youtube", "publico": True,
                    "fonte_id": fonte}
            return [dict(base, id=f"{fonte}1", parte=1, views=views_n,
                         quando=q1.isoformat(), idade_dias=(agora - q1).days),
                    dict(base, id=f"{fonte}2", parte=2, views=views_seguinte,
                         quando=q2.isoformat(), idade_dias=(agora - q2).days)]
        regs = par("a", date(2026, 10, 8), 200, 2) + par("b", date(2026, 10, 11), 200, 20)
        r = analise.resultado_da_parte_seguinte(regs, agora, TESTE)
        self.assertEqual((1, 1), (r["pares_antes"], r["pares_durante"]))
        self.assertEqual(1, r["por_100_antes"])
        self.assertEqual(10, r["por_100_durante"])

    def test_zero(self):
        r = analise.resultado_da_parte_seguinte([], datetime(2026, 10, 20), TESTE)
        self.assertEqual((0, 0), (r["pares_antes"], r["pares_durante"]))
        self.assertIsNone(r["por_100_durante"])


if __name__ == "__main__":
    unittest.main()
