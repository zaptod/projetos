# -*- coding: utf-8 -*-
"""Regressões do agarrão/arremesso (Onda 10A).

O cara-a-cara sem golpe é resolvido no corpo: 0,25s de lock e um desfecho
rápido (arremesso/joelhada/empurrão/reversão/escape) sorteado no stream do
MOTOR do iniciador. A mecânica é pura (core/agarrao.py); o ciclo vive no
Simulador.
"""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from neural_fights.core import agarrao
from neural_fights.simulation.simulacao import Simulador
from neural_fights.utils.config import (
    AGARRAO_COOLDOWN_S,
    AGARRAO_LOCK_S,
    FORCA_ARREMESSO,
)
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


def _par(dist=0.8):
    p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=dist)
    p1.rng_runtime = _RngFixo(0.3)
    p2.rng_runtime = _RngFixo(0.3)
    return p1, p2


def _sim_fake(p1, p2, rng=0.3):
    sim = object.__new__(Simulador)
    sim.p1, sim.p2 = p1, p2
    p1.rng_runtime = _RngFixo(rng)
    p2.rng_runtime = _RngFixo(rng)
    sim.shockwaves = []
    sim.particulas = []
    sim.cam = SimpleNamespace(
        aplicar_shake=lambda *a, **k: None,
        aplicar_momento=lambda *a, **k: None,
    )
    sim._tempo_clinch = 0.5
    sim._clinch_cooldown = 0.0
    sim._agarrao = None
    sim._agarrao_cooldown = 0.0
    sim._standoff_t = 0.0
    sim._standoff_t_fase = 0.0
    sim._standoff_fase = 0
    sim._standoff_fora = 0.0
    sim._standoff_cooldown = 0.0
    sim._standoff_ids = (0, 0)
    sim._standoff_hp_ant = None
    sim.standoff_estado = {"em_range": False, "ninguem_atacando": False,
                           "fase": 0, "t": 0.0}
    sim.arena = None
    return sim


class MecanicaPuraTests(unittest.TestCase):
    def test_lock_imobiliza_e_bloqueia_acoes(self):
        p1, p2 = _par()
        p1.agarrao_timer = AGARRAO_LOCK_S
        p1.vel = [5.0, 0.0]
        x_antes = p1.pos[0]
        self.assertFalse(p1.pode_iniciar_acao())
        p1.update(1 / 60, p2)
        self.assertEqual(p1.vel, [0.0, 0.0])
        self.assertAlmostEqual(p1.pos[0], x_antes, places=6)
        # O relógio do lutador anda; o do Simulador é o dono.
        self.assertLess(p1.agarrao_timer, AGARRAO_LOCK_S)

    def test_arremesso_lanca_3_a_5_m_e_arma_wall_splat(self):
        ini, alvo = _par()
        vida_antes = alvo.vida
        modo, revertido, ini_f, alvo_f = agarrao.aplicar_desfecho(
            ini, alvo, "ARREMESSO", 1.0, 0.0
        )
        self.assertEqual(modo, "ARREMESSO")
        self.assertFalse(revertido)
        self.assertIs(alvo_f, alvo)
        self.assertGreaterEqual(alvo.stun_timer, 0.45)
        self.assertIs(alvo.lancado_por, ini)
        self.assertGreater(alvo.lancado_timer, 0.0)
        self.assertLess(alvo.vida, vida_antes)
        self.assertAlmostEqual(alvo.vel[0], FORCA_ARREMESSO, places=6)
        x0 = alvo.pos[0]
        for _ in range(90):
            alvo.aplicar_fisica(1 / 60)
        deslocamento = alvo.pos[0] - x0
        self.assertGreater(deslocamento, 2.5)
        self.assertLess(deslocamento, 5.5)
        # O agarrão acabou para os dois.
        self.assertEqual(ini.agarrao_timer, 0.0)
        self.assertEqual(alvo.agarrao_timer, 0.0)

    def test_escape_abre_janela_no_iniciador(self):
        ini, alvo = _par()
        modo, _rev, ini_f, alvo_f = agarrao.aplicar_desfecho(
            ini, alvo, "ESCAPE", 1.0, 0.0
        )
        self.assertEqual(modo, "ESCAPE")
        self.assertGreaterEqual(ini.stun_timer, 0.3)
        # O alvo saiu para trás (dash ou empurrão negativo).
        self.assertLess(alvo.vel[0], 0.0)

    def test_reversao_troca_papeis_uma_vez(self):
        ini, alvo = _par()
        alvo.rng_runtime = _RngFixo(0.0)   # novo iniciador sorteia o 1º da roleta
        modo, revertido, ini_f, alvo_f = agarrao.aplicar_desfecho(
            ini, alvo, "REVERSAO", 1.0, 0.0
        )
        self.assertTrue(revertido)
        self.assertIs(ini_f, alvo)
        self.assertIs(alvo_f, ini)
        self.assertIn(modo, ("ARREMESSO", "JOELHADA", "EMPURRAO"))

    def test_dano_real_interrompe_o_agarrao(self):
        p1, p2 = _par()
        p1.agarrao_timer = AGARRAO_LOCK_S
        p1.tomar_dano(50.0, 1.0, 0.0, "NORMAL", atacante=p2,
                      metadata_impacto={"eh_corpo_a_corpo": True})
        self.assertEqual(p1.agarrao_timer, 0.0)
        self.assertTrue(p1.agarrao_interrompido)

    def test_desfechos_diversos_por_rng(self):
        vistos = set()
        for valor in (0.02, 0.3, 0.55, 0.75, 0.97):
            ini, alvo = _par()
            pesos = agarrao.pesos_desfecho(ini, alvo)
            vistos.add(agarrao.sortear_desfecho(pesos, _RngFixo(valor)))
        self.assertGreaterEqual(len(vistos), 3, vistos)

    def test_pesos_refletem_classe(self):
        pesado, agil = _par()
        pesado.classe_nome = "Cavaleiro (Defesa)"
        agil.classe_nome = "Ninja (Velocidade)"
        pesos = agarrao.pesos_desfecho(pesado, agil)
        self.assertGreater(pesos["ARREMESSO"], pesos["EMPURRAO"])
        self.assertGreater(pesos["ESCAPE"] + pesos["REVERSAO"], 0.4)


class CicloNoSimuladorTests(unittest.TestCase):
    def test_lock_resolve_no_tempo_e_conta(self):
        p1, p2 = _par(dist=2.0)
        sim = _sim_fake(p1, p2)
        sim._iniciar_agarrao(p1, p2, "standoff")
        self.assertIsNotNone(sim._agarrao)
        self.assertGreater(p1.agarrao_timer, 0.0)
        self.assertGreater(p2.agarrao_timer, 0.0)
        self.assertEqual(p1.contadores_luta["agarroes"], 1)
        self.assertAlmostEqual(sim._agarrao_cooldown, AGARRAO_COOLDOWN_S)

        frames = 0
        while sim._agarrao is not None and frames < 60:
            sim._atualizar_agarrao(1 / 60)
            frames += 1
        self.assertIsNone(sim._agarrao)
        self.assertLessEqual(frames / 60.0, AGARRAO_LOCK_S + 0.05)
        # Lunge: os corpos se encostaram durante o lock.
        dist = math.hypot(p2.pos[0] - p1.pos[0], p2.pos[1] - p1.pos[1])
        self.assertLess(dist, 2.0)
        desfechos = sum(
            p.contadores_luta.get(k, 0)
            for p in (p1, p2)
            for k in ("agarrao_arremesso", "agarrao_joelhada",
                      "agarrao_empurrao", "agarrao_escape")
        )
        self.assertEqual(desfechos, 1)
        self.assertEqual(p1.agarrao_timer, 0.0)
        self.assertEqual(p2.agarrao_timer, 0.0)

    def test_contato_dispara_agarrao_antes_do_resolvedor(self):
        p1, p2 = _par(dist=0.5)
        sim = _sim_fake(p1, p2)
        sim.resolver_fisica_corpos(1 / 60)
        self.assertIsNotNone(sim._agarrao)
        self.assertEqual(sim._agarrao["origem"], "contato")
        # Origem contato também conta como clinch (compat com o alvo R1).
        self.assertEqual(p1.contadores_luta["clinches"] + p2.contadores_luta["clinches"], 1)

    def test_agarrao_em_cooldown_cai_no_resolvedor_antigo(self):
        p1, p2 = _par(dist=0.5)
        sim = _sim_fake(p1, p2)
        sim._agarrao_cooldown = AGARRAO_COOLDOWN_S
        sim.resolver_fisica_corpos(1 / 60)
        self.assertIsNone(sim._agarrao)
        self.assertEqual(p1.contadores_luta["clinches"] + p2.contadores_luta["clinches"], 1)

    def test_morte_cancela_o_agarrao(self):
        p1, p2 = _par(dist=1.0)
        sim = _sim_fake(p1, p2)
        sim._iniciar_agarrao(p1, p2, "standoff")
        p2.morto = True
        sim._atualizar_agarrao(1 / 60)
        self.assertIsNone(sim._agarrao)
        self.assertEqual(p1.agarrao_timer, 0.0)


if __name__ == "__main__":
    unittest.main()
