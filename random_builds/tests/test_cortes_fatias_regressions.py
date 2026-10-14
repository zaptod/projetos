# -*- coding: utf-8 -*-
"""PUB-4: `cortes.pedacos` nunca devolve fatia curta, negativa ou longa.

Auditoria de 11/10/2026 (`publicar-builds.md` #5), verificada em 14/10. Ao
subir `quantos`, a escolha de um corte podia passar do ponto ideal do corte
seguinte, e o recurso "corta no ideal" caia ANTES do corte anterior. A
verificacao final so olhava o teto. Medido no HEAD d6aedb45:

  - `pedacos(598.7, pontos=[159.7, 384.5, 417.6])` -> 7 fatias, uma de
    11,36 s (159,70 -> 171,06), abaixo de `MINIMO_S` (12 s);
  - 20 000 sorteios com `random.seed(2)` (181-1200 s, 1-12 fronteiras):
    7 fatias abaixo do minimo — a pior com -51,34 s — e 3 acima do teto.
    (Com `random.seed(1)` e 5 000 sorteios, zero: por isso a semente 2.)

Latente hoje (nenhuma parte passa de 182 s). Quando disparar, sobe um Short
de 1-11 s, ou o ffmpeg recebe duracao negativa e o video vai inteiro, fora
do Shorts. Conta a mao do caso fixo com o conserto: 4 fatias, 159,7 /
139,65 / 149,675 / 149,675 s.
"""
from __future__ import annotations

import random
import unittest

from builds.publicar import cortes as C

TETO = C.LIMITE_PADRAO_S - C.MARGEM_S


class FatiasTests(unittest.TestCase):
    def _confere(self, duracao, fatias):
        self.assertAlmostEqual(0.0, fatias[0][0])
        self.assertAlmostEqual(duracao, fatias[-1][1])
        for (a, b), (c, _d) in zip(fatias, fatias[1:]):
            self.assertAlmostEqual(b, c, msg="contiguas")
        for ini, fim in fatias:
            self.assertGreaterEqual(fim - ini, C.MINIMO_S - 1e-9,
                                    f"{duracao}: fatia {ini:.2f}-{fim:.2f}")
            self.assertLessEqual(fim - ini, TETO + C.MARGEM_S + 1e-9,
                                 f"{duracao}: fatia {ini:.2f}-{fim:.2f}")

    def test_caso_medido_598_7(self):
        fatias = C.pedacos(598.7, pontos=[159.7, 384.5, 417.6])
        self._confere(598.7, fatias)
        self.assertEqual([159.7, 139.65, 149.675, 149.675],
                         [round(b - a, 3) for a, b in fatias])

    def test_propriedade_em_20000_sorteios(self):
        random.seed(2)
        for _ in range(20000):
            duracao = random.uniform(181, 1200)
            pontos = [random.uniform(0, duracao)
                      for _ in range(random.randint(1, 12))]
            fatias = C.pedacos(duracao, pontos=pontos)
            self._confere(duracao, fatias)

    def test_sem_fronteira_nenhuma(self):
        for duracao in (181.0, 206.0, 359.9, 600.0, 1199.0):
            with self.subTest(duracao=duracao):
                self._confere(duracao, C.pedacos(duracao, pontos=[]))

    def test_caso_zero_cabe_no_shorts_nao_corta(self):
        self.assertEqual([(0.0, 150.0)], C.pedacos(150.0, pontos=[60.0]))
        self.assertEqual([(0.0, 180.0)], C.pedacos(180.0))

    def test_continua_equilibrado_e_na_cena(self):
        """206 s -> ~100 + ~106 na fronteira mais perto do meio (a regra de
        31/08 que o conserto nao pode perder)."""
        fatias = C.pedacos(206.0, pontos=[50.0, 100.0, 150.0])
        self.assertEqual([(0.0, 100.0), (100.0, 206.0)], fatias)


if __name__ == "__main__":
    unittest.main()
