# -*- coding: utf-8 -*-
"""Checagem 1-a-1 (Onda 11B): cada skill castada no MOTOR REAL produz a
``consequencia_esperada`` declarada no contrato (core/skill_contract).

Por padrão roda um representante por tipo + os casos históricos (rápido).
O catálogo inteiro roda com NF_SKILL_GATE=1 — parte do fechamento de onda e
do ``skill_inspector checar --todas``.
"""

from __future__ import annotations

import os
import unittest

from neural_fights.tools.skill_check import checar_skill, checar_todas

REPRESENTANTES = [
    "Bola de Fogo",          # PROJETIL simples
    "Julgamento Celestial",  # AREA com pilares (P1-P7 da Onda 11B)
    "Corrente em Cadeia",    # BEAM com chain
    "Teleporte Relâmpago",   # DASH
    "Golpe do Executor",     # BUFF persistente
    "Ira da Floresta",       # SUMMON
    "Muralha de Gelo",       # TRAP (bloqueia projéteis)
    "Forma Relâmpago",       # TRANSFORM
    "Fotossíntese",          # CHANNEL de cura
    "Shatter",               # gate ALVO_CONGELADO (priming do dummy)
    "Execução",              # FINISHER ALVO_BAIXA_VIDA
    "Buraco Negro",          # vórtice (deslocamento:puxa)
    "Cura Menor",            # cura instantânea (sem buff persistente)
]


class SkillOneByOneTests(unittest.TestCase):
    def test_representantes_produzem_consequencia_declarada(self):
        for nome in REPRESENTANTES:
            with self.subTest(skill=nome):
                resultado = checar_skill(nome)
                self.assertTrue(resultado["ok"], resultado)

    @unittest.skipUnless(
        os.environ.get("NF_SKILL_GATE") == "1",
        "gate pesado; ligue com NF_SKILL_GATE=1",
    )
    def test_catalogo_inteiro_produz_consequencia_declarada(self):
        for resultado in checar_todas():
            with self.subTest(skill=resultado["skill"]):
                self.assertTrue(resultado["ok"], resultado)


if __name__ == "__main__":
    unittest.main()
