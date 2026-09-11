"""A arena precisa se separar do vazio em volta (Onda 15C).

`_desenhar_chao` montava a vinheta multiplicando `cor_chao` por 0,72 para o
tom mais escuro. Medido em 11/09/2026, por luminancia, contra o
`COR_FUNDO = (25, 25, 30)` que o simulador pinta fora da arena:

    Duto    (22, 26, 38) -> escuro 18,0  contra 25,4 do fundo
    Torre   (38, 32, 30) -> escuro 23,7  contra 25,4 do fundo

Nas duas, a BORDA DO PALCO era mais escura que o nada em volta, e a arena
sumia na moldura. Duas das tres arenas que vao ao ar. Treze das vinte do
catalogo inteiro.

O grid tinha o mesmo tipo de problema por outro caminho: +5 de luminancia
por canal nao sobrevive a compressao do h264, entao o chao lia como um
borrao liso e a luta parecia acontecer no vazio, sem referencia de escala.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.core.arena import ARENAS, Arena  # noqa: E402
from neural_fights.utils.config import COR_FUNDO  # noqa: E402

LUM_FUNDO = Arena._luminancia(COR_FUNDO)


class ContrasteDoChaoTests(unittest.TestCase):
    def test_o_tom_mais_escuro_do_chao_e_mais_claro_que_o_fundo(self):
        """Vale para TODAS as arenas, nao so as que vao ao ar hoje.

        Cobrar so as verticais deixaria a armadilha armada para a proxima
        arena: e a formula que estava errada, nao a cor de uma delas.
        """
        for nome, cfg in ARENAS.items():
            with self.subTest(arena=nome):
                escuro, _, _ = Arena._tons_do_chao(cfg.cor_chao)
                self.assertGreater(
                    Arena._luminancia(escuro), LUM_FUNDO,
                    f"{nome}: a borda do palco some contra o fundo")

    def test_o_piso_de_contraste_vale_para_qualquer_cor(self):
        """Inclusive preto puro, que e o pior caso possivel."""
        for cor in ((0, 0, 0), (1, 1, 1), (10, 5, 20), (255, 255, 255)):
            with self.subTest(cor=cor):
                escuro, _, _ = Arena._tons_do_chao(cor)
                self.assertGreaterEqual(
                    Arena._luminancia(escuro),
                    LUM_FUNDO + Arena.PISO_DE_CONTRASTE - 1.0)

    def test_a_vinheta_continua_subindo_do_escuro_para_o_claro(self):
        """O piso nao pode inverter a escada: centro mais claro que a borda.

        Levantar so o tom escuro, sem reordenar, faria uma arena de chao
        muito escuro desenhar o miolo mais apagado que a moldura.
        """
        for nome, cfg in ARENAS.items():
            with self.subTest(arena=nome):
                escuro, meio, claro = Arena._tons_do_chao(cfg.cor_chao)
                self.assertLessEqual(Arena._luminancia(escuro),
                                     Arena._luminancia(meio))
                self.assertLessEqual(Arena._luminancia(meio),
                                     Arena._luminancia(claro))

    def test_o_matiz_do_chao_sobrevive_ao_piso(self):
        """Clarear nao pode transformar a arena de gelo em arena de fogo."""
        for nome, cfg in ARENAS.items():
            cor = cfg.cor_chao
            if max(cor) - min(cor) < 8:
                continue  # cinza: nao ha matiz para preservar
            with self.subTest(arena=nome):
                escuro, _, _ = Arena._tons_do_chao(cor)
                self.assertEqual(cor.index(max(cor)),
                                 list(escuro).index(max(escuro)),
                                 "o canal dominante mudou")


class GridTests(unittest.TestCase):
    def test_o_grid_e_visivel_contra_o_chao(self):
        """+5 por canal era subliminar ate para o h264. O grid e a unica
        referencia de escala que o espectador tem do tamanho do lutador."""
        import inspect

        from neural_fights.core.arena import Arena as A
        fonte = inspect.getsource(A._desenhar_grid)
        self.assertIn("c + 14", fonte)
        for cfg in ARENAS.values():
            cor_grid = tuple(min(255, c + 14) for c in cfg.cor_chao)
            with self.subTest(arena=cfg.nome):
                self.assertGreaterEqual(
                    Arena._luminancia(cor_grid) - Arena._luminancia(cfg.cor_chao),
                    8.0, "grid indistinguivel do chao")


if __name__ == "__main__":
    unittest.main()
