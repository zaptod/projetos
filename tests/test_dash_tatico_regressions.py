# -*- coding: utf-8 -*-
"""Regressões do dash tático (Onda 10B).

O dash universal (8B) tinha um único chamador — o desvio urgente. Agora é
verbo tático da IA: gap-close com plano ofensivo, hit-and-run após acertar,
flanco sobre guarda erguida. Só estado observável, sorteio no stream do
brain, cooldown por evento.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.ai.brain import AIBrain
from tests import test_remaining_skill_regressions as _helpers


class _RngFixo:
    def __init__(self, valor=0.0):
        self.valor = valor

    def random(self):
        return self.valor

    def uniform(self, a, b):
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


def _brain(parent, *, plano=None, estilo="BALANCED", mob=0.0, intencao="parado",
           rng=0.0):
    brain = object.__new__(AIBrain)
    brain.parent = parent
    brain.rng = _RngFixo(rng)
    brain.tempo_combate = 6.0
    brain._acao_atual = "CIRCULAR"
    brain.contadores = {"escritas_aceitas": 0, "escritas_seguradas": 0}
    brain.tell_atual = None
    brain.tracos = []
    brain.quirks = []
    brain._perfil_chave = ()
    brain._perfil_cache = {}
    brain.agressividade_base = 0.6
    brain.humor = "NEUTRO"
    brain.ritmo_modificadores = {"agressividade": 0}
    brain.plano = plano
    brain.estilo_luta = estilo
    brain.dir_circular = 1
    brain.cd_dash_tatico = 0.0
    brain._observar = lambda inimigo: SimpleNamespace(
        intencao=intencao, fase_ataque=None
    )
    # `perfil` e property (cache por tupla de tracos): com tracos=[] a chave
    # e () e o cache abaixo e devolvido tal qual.
    brain._perfil_cache = {"mobilidade": mob, "agressao": 0.3}
    return brain


def _par(dist):
    p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=dist)
    p1.estamina = 100.0
    p1.dash_cooldown = 0.0
    p1.rng_runtime = _RngFixo(0.5)
    return p1, p2


class DashTaticoTests(unittest.TestCase):
    def test_gap_close_com_plano_ofensivo_e_recuo_observado(self):
        p1, p2 = _par(3.5)
        brain = _brain(p1, plano={"tipo": "PRESSIONAR"}, intencao="recuando")
        self.assertTrue(brain._considerar_dash_tatico(1 / 60, 3.5, p2))
        self.assertEqual(brain.acao_atual, "PRESSIONAR")
        self.assertGreater(p1.vel[0], 0.0)           # rumo ao alvo (+x)
        self.assertGreater(brain.cd_dash_tatico, 0.0)
        self.assertEqual(p1.contadores_luta["dashes_taticos"], 1)
        self.assertEqual(p1.contadores_luta["dashes_ofensivos"], 1)
        self.assertEqual(brain.tell_atual["modo"], "GAP_CLOSE")

    def test_sem_plano_ofensivo_nao_fecha_distancia(self):
        p1, p2 = _par(3.5)
        brain = _brain(p1, plano={"tipo": "RECUPERAR"}, intencao="recuando")
        self.assertFalse(brain._considerar_dash_tatico(1 / 60, 3.5, p2))
        self.assertEqual(p1.contadores_luta.get("dashes_taticos", 0), 0)

    def test_hit_and_run_apos_acertar(self):
        p1, p2 = _par(1.5)
        brain = _brain(p1, estilo="HIT_RUN")
        brain._t_ultimo_hit_dado = brain.tempo_combate - 0.1
        p1.atacando = True
        self.assertTrue(brain._considerar_dash_tatico(1 / 60, 1.5, p2))
        self.assertEqual(brain.acao_atual, "RECUAR")
        self.assertLess(p1.vel[0], 0.0)              # para longe do alvo
        self.assertFalse(p1.atacando)                 # dash-cancel
        self.assertEqual(p1.contadores_luta["dashes_taticos"], 1)
        self.assertEqual(p1.contadores_luta.get("dashes_ofensivos", 0), 0)

    def test_flanco_sobre_guarda_erguida(self):
        p1, p2 = _par(2.0)
        p2.tempo_bloqueando = 0.5
        brain = _brain(p1)
        self.assertTrue(brain._considerar_dash_tatico(1 / 60, 2.0, p2))
        self.assertEqual(brain.acao_atual, "FLANQUEAR")
        self.assertGreater(abs(p1.vel[1]), abs(p1.vel[0]))   # lateral
        self.assertEqual(brain.tell_atual["modo"], "FLANK")

    def test_respeita_cooldown_e_pode_dash(self):
        p1, p2 = _par(3.5)
        brain = _brain(p1, plano={"tipo": "PRESSIONAR"}, intencao="recuando")
        self.assertTrue(brain._considerar_dash_tatico(1 / 60, 3.5, p2))
        p1.dash_cooldown = 0.0
        self.assertFalse(brain._considerar_dash_tatico(1 / 60, 3.5, p2))  # cd tático
        brain.cd_dash_tatico = 0.0
        p1.estamina = 0.0
        self.assertFalse(brain._considerar_dash_tatico(1 / 60, 3.5, p2))  # sem fôlego

    def test_sorteio_no_stream_do_brain(self):
        p1, p2 = _par(3.5)
        brain = _brain(p1, plano={"tipo": "PRESSIONAR"}, intencao="recuando", rng=0.999)
        self.assertFalse(brain._considerar_dash_tatico(1 / 60, 3.5, p2))


if __name__ == "__main__":
    unittest.main()
