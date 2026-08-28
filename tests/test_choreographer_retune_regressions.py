# -*- coding: utf-8 -*-
"""Regressões do retune do coreógrafo e do tédio (Onda 10A).

O diretor não fabrica mais o cara-a-cara: FACE_OFF é curto, único e termina
em iniciativa; STANDOFF/BREATHER não alongam o timer de decisão; o tédio
acelera a decisão em vez de travá-la.
"""

from __future__ import annotations

import random
import unittest
from types import SimpleNamespace

from neural_fights.ai.brain import AIBrain
from neural_fights.ai.choreographer import CombatChoreographer
from neural_fights.ai.personalities import HUMORES


class _RngFixo:
    def __init__(self, valor=0.0):
        self.valor = valor

    def random(self):
        return self.valor

    def uniform(self, a, b):
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


class _Brain:
    def __init__(self, agressao):
        self._agressao = agressao
        self.chamadas = []
        self.tempo_combate = 10.0

    def agressividade_efetiva(self):
        return self._agressao

    def forcar_iniciativa(self, distancia, inimigo, *, permitir_dash=True, hold_s=0.6):
        self.chamadas.append(distancia)
        return True

    def on_momento_cinematografico(self, *a, **k):
        pass


def _lutador(x, hp=0.4, agressao=0.5, estamina=100.0):
    return SimpleNamespace(
        pos=[x, 8.0], vida=hp * 100.0, vida_max=100.0, estamina=estamina,
        atacando=False, morto=False, brain=_Brain(agressao),
        rng_runtime=_RngFixo(0.0),
    )


def _coreografo(l1, l2, rng=0.0):
    CombatChoreographer.reset()
    core = CombatChoreographer(rng=_RngFixo(rng))
    core.registrar_lutadores(l1, l2)
    core.rng = _RngFixo(rng)
    return core


class FaceOffTests(unittest.TestCase):
    def test_face_off_e_curto_unico_e_explode_em_iniciativa(self):
        l1, l2 = _lutador(5.0, agressao=0.8), _lutador(9.0, agressao=0.3)
        core = _coreografo(l1, l2)
        core.intensidade = 0.9
        self.assertFalse(core._face_off_usado)
        core._detectar_momento()
        self.assertEqual(core.momento_atual, "FACE_OFF")
        self.assertLessEqual(core.duracao_momento, 0.8 + 1e-9)
        self.assertTrue(core._face_off_usado)

        core._finalizar_momento()
        self.assertEqual(core.momento_atual, "NEUTRO")
        # O mais agressivo toma a iniciativa ao fim do encarar.
        self.assertEqual(len(l1.brain.chamadas), 1)
        self.assertEqual(len(l2.brain.chamadas), 0)

        # Segunda vez na mesma luta: não acontece.
        core.cooldown_momentos.clear()
        core._detectar_momento()
        self.assertNotEqual(core.momento_atual, "FACE_OFF")

    def test_standoff_curto(self):
        l1, l2 = _lutador(5.0, hp=0.9), _lutador(10.5, hp=0.9)
        core = _coreografo(l1, l2, rng=0.99)
        core.intensidade = 0.6
        core.tempo_sem_hit = 4.0
        core._detectar_momento()
        self.assertEqual(core.momento_atual, "STANDOFF")
        self.assertLessEqual(core.duracao_momento, 1.5 + 1e-9)

    def test_breather_exige_folego_baixo_nos_dois(self):
        l1, l2 = _lutador(5.0, hp=0.9), _lutador(10.0, hp=0.9)
        core = _coreografo(l1, l2)
        core.intensidade = 0.0
        core.trocas_seguidas = 6
        core.tempo_sem_hit = 0.0
        core._detectar_momento()
        self.assertNotEqual(core.momento_atual, "BREATHER")
        l1.estamina = 10.0
        l2.estamina = 10.0
        core.momento_atual = "NEUTRO"
        core._detectar_momento()
        self.assertEqual(core.momento_atual, "BREATHER")


class BrainRetuneTests(unittest.TestCase):
    def _brain(self, humor):
        brain = object.__new__(AIBrain)
        brain.rng = random.Random(1)
        brain.tracos = []
        brain.modo_berserk = False
        brain.humor = humor
        brain.tempo_combate = 5.0
        brain._acao_atual = "CIRCULAR"
        brain.timer_decisao = 0.1
        brain.contadores = {}
        brain.adrenalina = 0.0
        brain.modo_burst = False
        return brain

    def test_entediado_decide_mais_rapido_e_mais_agressivo(self):
        brain = self._brain("ENTEDIADO")
        brain._calcular_timer_decisao()
        self.assertLessEqual(brain.timer_decisao, 0.3 * 1.2 + 1e-9)
        self.assertGreater(HUMORES["ENTEDIADO"]["mod_agressividade"], 0.0)

    def test_beats_do_diretor_nao_esticam_o_timer(self):
        brain = self._brain("CALMO")
        brain._executar_acao_sincronizada("CIRCULAR_LENTO", 5.0, None)
        self.assertAlmostEqual(brain.timer_decisao, 0.1)
        self.assertEqual(brain.acao_atual, "CIRCULAR")
        brain._executar_acao_sincronizada("RECUPERAR", 5.0, None)
        self.assertAlmostEqual(brain.timer_decisao, 0.1)


if __name__ == "__main__":
    unittest.main()
