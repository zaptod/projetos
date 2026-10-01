"""Regressões para projéteis sem velocidade na análise defensiva da IA."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.ai.brain import AIBrain
from neural_fights.ai.percepcao import PercepcaoMundo


class AnaliseProjetilSemVelocidadeTests(unittest.TestCase):
    @staticmethod
    def _analisar(*, x: float, y: float, angulo: float, vel: float) -> dict:
        defensor = SimpleNamespace(pos=[0.0, 0.0])
        inimigo = SimpleNamespace(buffer_orbes=[])
        projetil = SimpleNamespace(
            ativo=True,
            dono=inimigo,
            x=x,
            y=y,
            angulo=angulo,
            vel=vel,
        )
        defensor.percepcao = PercepcaoMundo(
            SimpleNamespace(projeteis=[projetil], beams=[])
        )
        brain = object.__new__(AIBrain)
        brain.parent = defensor
        return brain._analisar_projeteis_vindo(inimigo)

    def test_projetil_parado_distante_e_ignorado(self) -> None:
        resultado = self._analisar(x=1.0, y=0.0, angulo=180.0, vel=0.0)

        self.assertEqual(
            resultado,
            {
                "vindo": False,
                "urgencia": 0.0,
                "direcao": 0.0,
                "tempo_impacto": 999.0,
            },
        )

    def test_projetil_parado_na_mesma_posicao_ja_esta_em_cima(self) -> None:
        resultado = self._analisar(x=0.0, y=0.0, angulo=0.0, vel=0.0)

        self.assertEqual(
            resultado,
            {
                "vindo": True,
                "urgencia": 1.0,
                "direcao": 0.0,
                "tempo_impacto": 0.0,
            },
        )

    def test_projetil_em_movimento_preserva_o_calculo_existente(self) -> None:
        resultado = self._analisar(x=5.0, y=0.0, angulo=180.0, vel=10.0)

        self.assertEqual(
            resultado,
            {
                "vindo": True,
                "urgencia": 0.5,
                "direcao": 180.0,
                "tempo_impacto": 0.5,
            },
        )


class Seed21026RegressionTests(unittest.TestCase):
    def test_aurora_contra_jin_completa_sem_zero_division(self) -> None:
        from neural_fights.simulation.headless import HeadlessMatchRunner
        from neural_fights.tools.qualidade_luta import FonteDeDados

        fonte = FonteDeDados("engine")
        resultado = HeadlessMatchRunner(
            {
                "p1_nome": "Aurora o Bravo",
                "p2_nome": "Jin a Protetora",
                "cenario": "Arena",
                "best_of": 1,
            },
            seed=21026,
            max_duration=120.0,
            roster_provider=fonte.provider(),
        ).run()

        self.assertTrue(resultado.success, resultado.error)


if __name__ == "__main__":
    unittest.main()
