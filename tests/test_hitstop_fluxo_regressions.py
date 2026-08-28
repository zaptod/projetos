# -*- coding: utf-8 -*-
"""Regressões do hit-stop de fluxo (Onda 10, ajuste pós-entrega).

Congelar a tela a cada golpe quebrava o ritmo: o hit stop virou pontuação
de PANCADA GRANDE (>= HITSTOP_DANO_MIN_PCT da vida do alvo). Golpes comuns
seguem com shake/partículas; a magia carregada (alvo None) e o slow-motion
de KO não mudam.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.core.game_feel import HitStopManager
from neural_fights.utils.config import HITSTOP_DANO_MIN_PCT


def _lutador(classe="Guerreiro (Força Bruta)", vida_max=500.0):
    return SimpleNamespace(classe_nome=classe, vida_max=vida_max, pos=[0.0, 0.0])


class HitStopFluxoTests(unittest.TestCase):
    def setUp(self):
        HitStopManager.reset()
        self.manager = HitStopManager.get_instance()

    def tearDown(self):
        HitStopManager.reset()

    def test_golpe_comum_nao_congela(self):
        atacante, alvo = _lutador("Berserker (Fúria)"), _lutador()
        dano = alvo.vida_max * HITSTOP_DANO_MIN_PCT * 0.5
        self.manager.registrar_hit(atacante, alvo, dano, (0.0, 0.0), "MEDIO", True)
        self.assertIsNone(self.manager.evento_atual)

    def test_pancada_grande_congela(self):
        atacante, alvo = _lutador(), _lutador()
        dano = alvo.vida_max * HITSTOP_DANO_MIN_PCT * 1.2
        self.manager.registrar_hit(atacante, alvo, dano, (0.0, 0.0), "PESADO", False)
        self.assertIsNotNone(self.manager.evento_atual)
        self.assertGreater(self.manager.evento_atual.duracao, 0.0)

    def test_limiar_e_relativo_a_vida_do_alvo(self):
        atacante = _lutador()
        fragil = _lutador(vida_max=100.0)
        tanque = _lutador(vida_max=1000.0)
        dano = 40.0   # 40% do frágil, 4% do tanque
        self.manager.registrar_hit(atacante, tanque, dano, (0.0, 0.0), "MEDIO", False)
        self.assertIsNone(self.manager.evento_atual)
        self.manager.registrar_hit(atacante, fragil, dano, (0.0, 0.0), "MEDIO", False)
        self.assertIsNotNone(self.manager.evento_atual)

    def test_magia_carregada_sem_alvo_continua_epica(self):
        self.manager.registrar_hit(_lutador(), None, 5.0, (0.0, 0.0), "EPICO", False)
        self.assertIsNotNone(self.manager.evento_atual)


if __name__ == "__main__":
    unittest.main()
