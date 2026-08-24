"""Contratos da gravacao de lutas em video.

O video so pode ser mostrado ao lado do placar se ele for a MESMA luta que o
placar descreve. Estes testes travam essa equivalencia e as regras de
enquadramento que a sustentam.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.data.database import carregar_personagens  # noqa: E402
from neural_fights.recording.fight_recorder import gravar_luta  # noqa: E402
from neural_fights.simulation.headless import run_headless_match  # noqa: E402


def _dois_lutadores() -> tuple[str, str]:
    personagens = carregar_personagens()
    return personagens[0].nome, personagens[1].nome


def _assinatura(resultado: dict) -> tuple:
    """O que precisa bater entre execucoes: quem venceu, quanto durou, HP."""
    return (
        resultado["vencedor"],
        round(float(resultado["duracao_jogo"]), 2),
        round(float(resultado["hp_final"]["p1"]), 1),
        round(float(resultado["hp_final"]["p2"]), 1),
    )


# Gravar exige rodar o motor desenhando cada frame: cada luta custa ~20 s de
# CPU. Os dois contratos que sustentam a feature rodam sempre; os demais ficam
# atras de NF_RECORDING_GATE=1, como o gate de qualidade de luta ja faz.
GATE_PESADO = os.environ.get("NF_RECORDING_GATE") != "1"


class GravacaoDeLutaTests(unittest.TestCase):
    SEED = 20260821
    CENARIO = "Arena Pequena"

    @classmethod
    def setUpClass(cls) -> None:
        cls.p1, cls.p2 = _dois_lutadores()

    def _gravar(self, *, portrait: bool, camera: str | None, nome: str) -> dict:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / f"{nome}.mp4"
            resultado = gravar_luta(
                p1=self.p1, p2=self.p2, saida=destino, seed=self.SEED,
                cenario=self.CENARIO, portrait=portrait, camera_modo=camera,
                preset="ultrafast", crf=30,
            )
            self.assertTrue(resultado["sucesso"], resultado.get("erro"))
            self.assertTrue(destino.is_file(), "o mp4 nao foi criado")
            self.assertGreater(destino.stat().st_size, 0)
        return resultado

    def test_gravacao_reproduz_a_luta_do_motor_headless(self) -> None:
        """A gravacao e a autoridade do resultado: ela PRECISA bater com o
        motor headless, senao o video contradiz o placar mostrado depois."""
        headless = run_headless_match(
            {"p1_nome": self.p1, "p2_nome": self.p2, "cenario": self.CENARIO,
             "best_of": 1, "portrait_mode": False},
            fixed_dt=1 / 60, max_duration=120.0, seed=self.SEED)
        self.assertTrue(headless.success, headless.error)

        gravado = self._gravar(portrait=False, camera=None, nome="ref")

        self.assertEqual(headless.winner, gravado["vencedor"])
        self.assertAlmostEqual(headless.duration, gravado["duracao_jogo"],
                               delta=0.05)
        self.assertAlmostEqual(headless.p1_hp_ratio * 100,
                               gravado["hp_final"]["p1"], delta=0.5)
        self.assertAlmostEqual(headless.p2_hp_ratio * 100,
                               gravado["hp_final"]["p2"], delta=0.5)

    def test_resolucao_e_camera_nao_alteram_a_luta(self) -> None:
        """Os dois formatos de video precisam ser a MESMA luta.

        E o que permite gravar em 9:16 com a camera seguindo os lutadores e em
        16:9 mostrando a arena inteira sem que os videos se contradigam.
        """
        paisagem = self._gravar(portrait=False, camera=None, nome="paisagem")
        retrato = self._gravar(portrait=True, camera="AUTO", nome="retrato")

        self.assertEqual(_assinatura(paisagem), _assinatura(retrato))
        self.assertEqual([1200, 800], paisagem["resolucao"])
        self.assertEqual([540, 960], retrato["resolucao"])

    @unittest.skipIf(GATE_PESADO, "gate pesado; ligue com NF_RECORDING_GATE=1")
    def test_arena_altera_a_luta(self) -> None:
        """Documenta a regra que impede uma 'otimizacao' perigosa.

        Trocar a arena entre formatos pareceria uma boa ideia (cada formato
        com o cenario que enquadra melhor), mas o terreno muda o combate: os
        dois videos contariam historias diferentes. A arena e escolhida UMA
        vez por luta.
        """
        import tempfile
        from pathlib import Path

        resultados = []
        for cenario in ("Arena Pequena", "Coliseu"):
            with tempfile.TemporaryDirectory() as pasta:
                resultados.append(gravar_luta(
                    p1=self.p1, p2=self.p2,
                    saida=Path(pasta) / "x.mp4", seed=self.SEED,
                    cenario=cenario, preset="ultrafast", crf=30))
        self.assertNotEqual(_assinatura(resultados[0]), _assinatura(resultados[1]),
                            "arenas diferentes deveriam produzir lutas diferentes")

    @unittest.skipIf(GATE_PESADO, "gate pesado; ligue com NF_RECORDING_GATE=1")
    def test_gravacao_continua_depois_do_ko(self) -> None:
        """O video precisa conter o slow-motion e o letterbox do nocaute."""
        gravado = self._gravar(portrait=False, camera=None, nome="cauda")
        if gravado["ko_em_video"] is None:
            self.skipTest("a luta terminou por tempo, sem KO")
        self.assertGreaterEqual(
            gravado["duracao_video"] - gravado["ko_em_video"], 3.0,
            "faltou cauda apos o KO")

    @unittest.skipIf(GATE_PESADO, "gate pesado; ligue com NF_RECORDING_GATE=1")
    def test_eventos_de_dano_tem_tempo_de_video(self) -> None:
        """Os timestamps servem para cortar o mp4: precisam caber nele."""
        gravado = self._gravar(portrait=False, camera=None, nome="eventos")
        self.assertTrue(gravado["eventos_dano"], "nenhum golpe registrado")
        for t, slot, dano, _categoria in gravado["eventos_dano"]:
            self.assertGreaterEqual(t, 0.0)
            self.assertLessEqual(t, gravado["duracao_video"] + 0.1)
            self.assertIn(slot, ("p1", "p2"))
            self.assertGreater(dano, 0.0)


if __name__ == "__main__":
    unittest.main()
