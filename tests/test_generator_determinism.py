"""Regressoes de reprodutibilidade do gerador de roster."""

from __future__ import annotations

import random
import unittest

from neural_fights.data.database import validar_database
from neural_fights.tools.gerador_database import gerar_database_completa


class GeneratorDeterminismTests(unittest.TestCase):
    def test_same_seed_produces_the_same_valid_documents(self) -> None:
        primeiro = gerar_database_completa(16, "representativa", seed=12345)
        segundo = gerar_database_completa(16, "representativa", seed=12345)

        self.assertEqual(primeiro, segundo)
        validar_database(*primeiro)

    def test_seeded_generation_does_not_mutate_global_random_state(self) -> None:
        random.seed(99)
        estado = random.getstate()

        gerar_database_completa(16, seed=7)

        self.assertEqual(estado, random.getstate())


if __name__ == "__main__":
    unittest.main()
