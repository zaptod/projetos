"""Contratos dos overlays visiveis em transmissao.

A partida e material de live: um overlay de diagnostico ligado por engano vai ao
ar junto com ela. Estes testes fixam os padroes e o bloco ``overlays`` do match
config para que a decisao seja explicita, nunca acidental.
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.core import hitbox
from neural_fights.simulation.simulacao import Simulador


@contextmanager
def simulador_headless(**config_extra):
    """Cria um Simulador headless sem carregar roster nem tocar no disco.

    ``recarregar_tudo`` e o unico passo que precisa de personagens reais; os
    overlays sao resolvidos antes dele, durante ``_inicializar``.
    """
    config = {"p1_nome": "A", "p2_nome": "B", "cenario": "Arena", "best_of": 1}
    config.update(config_extra)
    with patch.object(Simulador, "recarregar_tudo"):
        simulador = Simulador(match_config=config, headless=True, seed=1)
    try:
        yield simulador
    finally:
        simulador.close()


class BroadcastOverlayDefaultTests(unittest.TestCase):
    def test_flags_de_debug_ficam_desligadas_no_modulo(self) -> None:
        """Fonte unica do padrao; ligada aqui, aparece em toda partida."""
        self.assertFalse(hitbox.DEBUG_VISUAL)
        self.assertFalse(hitbox.DEBUG_HITBOX)

    def test_partida_padrao_nao_liga_overlay_de_diagnostico(self) -> None:
        with simulador_headless() as simulador:
            self.assertTrue(simulador.show_hud)
            self.assertFalse(simulador.show_analysis)
            self.assertFalse(simulador.show_hitbox_debug)


class BroadcastOverlayConfigTests(unittest.TestCase):
    def test_bloco_overlays_controla_cada_camada(self) -> None:
        overlays = {"hud": False, "analise": True, "hitbox_debug": True}
        with simulador_headless(overlays=overlays) as simulador:
            self.assertFalse(simulador.show_hud)
            self.assertTrue(simulador.show_analysis)
            self.assertTrue(simulador.show_hitbox_debug)

    def test_bloco_ausente_ou_invalido_cai_nos_padroes(self) -> None:
        for overlays in (None, "ligado", 42, []):
            with self.subTest(overlays=overlays):
                with simulador_headless(overlays=overlays) as simulador:
                    self.assertTrue(simulador.show_hud)
                    self.assertFalse(simulador.show_analysis)
                    self.assertFalse(simulador.show_hitbox_debug)

    def test_chave_desconhecida_no_bloco_e_ignorada(self) -> None:
        with simulador_headless(overlays={"inexistente": True}) as simulador:
            self.assertTrue(simulador.show_hud)
            self.assertFalse(simulador.show_analysis)
            self.assertFalse(simulador.show_hitbox_debug)


class BroadcastOverlayRuntimeTests(unittest.TestCase):
    def test_teclas_continuam_alternando_em_runtime(self) -> None:
        """A config decide o estado inicial; o operador ainda alterna ao vivo."""
        with simulador_headless() as simulador:
            simulador.show_hitbox_debug = not simulador.show_hitbox_debug
            self.assertTrue(simulador.show_hitbox_debug)

    def test_config_padrao_nao_declara_overlays(self) -> None:
        """O padrao vem do codigo, nao de um bloco espalhado na fixture."""
        config = Simulador.criar_match_config_padrao()
        self.assertNotIn("overlays", config)


if __name__ == "__main__":
    unittest.main()
