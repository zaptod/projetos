# -*- coding: utf-8 -*-
"""BLD-6 (auditoria profunda de 11/10/2026) com a decisao do Adrian de
14/10/2026 (``builds/empate-persistente``: "Desempatar pelo HP que sobrou").

Antes: tres empates seguidos viravam vitoria INVENTADA do p1
(``vencedor = bruto["vencedor"] or p1``). Agora:

1. vence quem tem a maior fracao de vida no fim da ultima tentativa;
2. HP exatamente igual: quem causou mais dano (vida que tirou do outro);
3. ainda igual: a paridade da seed decide (par = p1, impar = p2) — regra
   deterministica e sem vies de lado.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from builds.tournament import runner


def _resultado(seed, winner=None, p1_ratio=0.5, p2_ratio=0.5, p1_hp=None, p2_hp=None,
               reason="time_limit"):
    return SimpleNamespace(
        success=True, error=None, winner=winner, winner_slot=None, reason=reason,
        duration=120.0, frames=7200, seed=seed, p1_name="A", p2_name="B",
        p1_hp=p1_hp if p1_hp is not None else p1_ratio * 400.0,
        p2_hp=p2_hp if p2_hp is not None else p2_ratio * 400.0,
        p1_hp_ratio=p1_ratio, p2_hp_ratio=p2_ratio,
    )


class DesempateTests(unittest.TestCase):
    def test_tres_empates_vencem_pelo_hp_e_nao_pelo_lado(self):
        respostas = [_resultado(700), _resultado(701), _resultado(702, p1_ratio=0.2, p2_ratio=0.6)]
        with mock.patch("neural_fights.simulation.headless.run_headless_match",
                        side_effect=respostas):
            bruto = runner.simular_luta("A", "B", "Torre", 700)
        self.assertEqual(bruto["vencedor"], "B")  # antes: "A" inventado
        self.assertEqual(bruto["desempate"], "hp")
        evento = runner._evento_base("A", "B", bruto, {}, set(), "Torre")
        self.assertEqual(evento["vencedor"], "B")
        self.assertEqual(evento["perdedor"], "A")

    def test_hp_igual_decide_quem_causou_mais_dano(self):
        # mesma fracao (0,5), mas B tinha mais vida: A tirou 300, B tirou 200
        ultimo = _resultado(702, p1_ratio=0.5, p2_ratio=0.5, p1_hp=200.0, p2_hp=300.0)
        with mock.patch("neural_fights.simulation.headless.run_headless_match",
                        side_effect=[_resultado(700), _resultado(701), ultimo]):
            bruto = runner.simular_luta("A", "B", "Torre", 700)
        self.assertEqual(bruto["vencedor"], "A")
        self.assertEqual(bruto["desempate"], "dano")

    def test_tudo_igual_decide_pela_paridade_da_seed(self):
        self.assertEqual(runner.desempatar("A", "B", 0.5, 0.5, 10.0, 10.0, 702), ("A", "seed"))
        self.assertEqual(runner.desempatar("A", "B", 0.5, 0.5, 10.0, 10.0, 703), ("B", "seed"))

    def test_vencedor_do_motor_nao_e_tocado(self):
        with mock.patch("neural_fights.simulation.headless.run_headless_match",
                        side_effect=[_resultado(700, winner="B", p1_ratio=0.9, p2_ratio=0.1)]):
            bruto = runner.simular_luta("A", "B", "Torre", 700)
        self.assertEqual(bruto["vencedor"], "B")
        self.assertNotIn("desempate", bruto)

    def test_evento_sem_vencedor_falha_em_vez_de_inventar(self):
        with self.assertRaises(runner.EmpatePersistente):
            runner._evento_base("A", "B", {"vencedor": None, "duracao": 1.0, "motivo": "x",
                                           "hp_vencedor": 0.0, "seed": 1}, {}, set(), "Torre")


if __name__ == "__main__":
    unittest.main()
