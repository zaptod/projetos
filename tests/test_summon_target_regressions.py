"""Regressoes de alvo com formato de posicao diferente.

``Lutador`` guarda posicao em ``pos[0]/pos[1]``; ``Summon`` guarda em ``x``/``y``.
Projeteis e beams miram os dois -- a montagem de alvos passa
``incluir_summons=True`` --, entao qualquer caminho que leia ``alvo.pos``
diretamente derruba a partida inteira quando o alvo e uma invocacao.

Numa transmissao ao vivo isso nao e um erro de log: e a luta morrendo na tela.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from neural_fights.data import database
from neural_fights.simulation.headless import HeadlessMatchRunner
from neural_fights.simulation.simulacao import Simulador


class PosicaoDeAlvoTests(unittest.TestCase):
    def test_helper_aceita_os_dois_formatos(self) -> None:
        lutador = SimpleNamespace(pos=[3.0, 4.0])
        summon = SimpleNamespace(x=7.0, y=8.0)

        self.assertEqual(Simulador._posicao_alvo_combate(lutador), (3.0, 4.0))
        self.assertEqual(Simulador._posicao_alvo_combate(summon), (7.0, 8.0))

    def test_pos_incompleta_cai_no_formato_xy(self) -> None:
        hibrido = SimpleNamespace(pos=[1.0], x=5.0, y=6.0)
        self.assertEqual(Simulador._posicao_alvo_combate(hibrido), (5.0, 6.0))

    def test_nenhum_caminho_de_impacto_le_pos_diretamente(self) -> None:
        """Trava a inconsistencia que causou o crash.

        Os laços que miram summons precisam usar ``_posicao_alvo_combate``. Ler
        ``alvo.pos`` ali volta a quebrar a partida na primeira invocação atingida.
        """
        import inspect

        from neural_fights.simulation import simulacao

        for nome in ("_atualizar_projeteis", "_atualizar_beams"):
            with self.subTest(metodo=nome):
                fonte = inspect.getsource(getattr(simulacao.Simulador, nome))
                self.assertNotIn(
                    "alvo.pos[",
                    fonte,
                    f"{nome} lê alvo.pos direto; Summon não tem esse atributo",
                )


class PartidaComInvocacaoTests(unittest.TestCase):
    def test_luta_que_invoca_e_acerta_summon_nao_quebra(self) -> None:
        """Cenário que reproduzia o crash antes da correção."""
        nomes = [p.nome for p in database.carregar_personagens()]
        if "Freya a Implacável" not in nomes or "Brutus" not in nomes:
            self.skipTest("roster não contém o par que reproduz o caso")

        resultado = HeadlessMatchRunner(
            {
                "p1_nome": "Freya a Implacável",
                "p2_nome": "Brutus",
                "cenario": "Arena",
                "best_of": 1,
            },
            seed=1039,
            max_duration=120.0,
        ).run()

        self.assertTrue(resultado.success, resultado.error)
        self.assertIsNone(resultado.error)


if __name__ == "__main__":
    unittest.main()
