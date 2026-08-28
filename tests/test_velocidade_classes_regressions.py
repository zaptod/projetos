# -*- coding: utf-8 -*-
"""Regressões da velocidade por classe (Onda 10B).

A velocidade é identidade de classe: base em m/s por classe, peso da arma e
força só modulam ±30%. Garantia: o Ninja mais pesado e fraco anda mais que o
Cavaleiro mais leve e forte — antes, um Ninja de kunai (6,3 m/s) andava
como um Cavaleiro.
"""

from __future__ import annotations

import unittest

from neural_fights.models import characters
from neural_fights.models.characters import Personagem
from neural_fights.models.constants import CLASSES_DATA, cadencia_base_s


def _velocidade(classe, forca=5.0, peso=2.0, tamanho=1.7):
    return Personagem("T", tamanho, forca, 4, peso_arma_cache=peso,
                      classe=classe).get_velocidade_movimento()


class VelocidadePorClasseTests(unittest.TestCase):
    def test_toda_classe_declara_identidade_de_movimento(self):
        for nome, dados in CLASSES_DATA.items():
            self.assertIn("velocidade_base_ms", dados, nome)
            self.assertIn("mod_cadencia", dados, nome)
            self.assertIn("vel_giro", dados, nome)
            self.assertGreater(dados["velocidade_base_ms"], 3.0, nome)
            self.assertLess(dados["velocidade_base_ms"], 14.0, nome)

    def test_formula_usa_base_por_classe(self):
        ninja = _velocidade("Ninja (Velocidade)")
        cavaleiro = _velocidade("Cavaleiro (Defesa)")
        guerreiro = _velocidade("Guerreiro (Força Bruta)")
        self.assertGreater(ninja, guerreiro)
        self.assertGreater(guerreiro, cavaleiro)
        # Base do Ninja com peso 2 e forca 5: 11,0 x 1,0 x 1,0.
        self.assertAlmostEqual(ninja, 11.0 * min(1.05, 1.10 - 0.1) * 1.0, places=6)

    def test_min_ninja_supera_max_cavaleiro_em_qualquer_build(self):
        pior_ninja = min(
            _velocidade("Ninja (Velocidade)", forca=f, peso=p)
            for f in range(2, 11) for p in range(0, 9)
        )
        melhor_cavaleiro = max(
            _velocidade("Cavaleiro (Defesa)", forca=f, peso=p)
            for f in range(2, 11) for p in range(0, 9)
        )
        self.assertGreater(pior_ninja, melhor_cavaleiro)
        self.assertGreater(pior_ninja / melhor_cavaleiro, 1.15)

    def test_peso_reduz_no_maximo_30pct(self):
        leve = _velocidade("Guerreiro (Força Bruta)", peso=0.0)
        pesado = _velocidade("Guerreiro (Força Bruta)", peso=10.0)
        self.assertGreater(leve, pesado)
        self.assertGreaterEqual(pesado / leve, 0.70 / 1.05 - 1e-9)

    def test_mod_forca_nao_entra_mais_na_velocidade(self):
        # Mago tem mod_forca 0,5; a velocidade e a base da classe.
        mago = _velocidade("Mago (Arcano)", forca=5.0, peso=2.0)
        self.assertAlmostEqual(mago, 6.0 * 1.0 * 1.0, places=6)

    def test_escala_global_continua_knob(self):
        original = characters.ESCALA_VELOCIDADE_MOVIMENTO
        try:
            characters.ESCALA_VELOCIDADE_MOVIMENTO = 2.0
            self.assertAlmostEqual(
                _velocidade("Guerreiro (Força Bruta)"), 2.0 * 7.0, places=6
            )
        finally:
            characters.ESCALA_VELOCIDADE_MOVIMENTO = original


class CadenciaPorClasseTests(unittest.TestCase):
    def test_dupla_ataca_mais_rapido_que_reta(self):
        self.assertLess(cadencia_base_s("Dupla"), cadencia_base_s("Reta"))
        self.assertAlmostEqual(cadencia_base_s("Dupla"), 0.85)

    def test_mod_cadencia_segue_a_identidade(self):
        self.assertLess(CLASSES_DATA["Ninja (Velocidade)"]["mod_cadencia"], 1.0)
        self.assertLess(CLASSES_DATA["Assassino (Crítico)"]["mod_cadencia"], 1.0)
        self.assertGreater(CLASSES_DATA["Cavaleiro (Defesa)"]["mod_cadencia"], 1.0)
        self.assertGreater(
            CLASSES_DATA["Ninja (Velocidade)"]["vel_giro"],
            CLASSES_DATA["Cavaleiro (Defesa)"]["vel_giro"],
        )


if __name__ == "__main__":
    unittest.main()
