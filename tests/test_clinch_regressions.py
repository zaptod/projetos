# -*- coding: utf-8 -*-
"""Regressões do sistema de clinch (Onda 8G).

Corpos colados por tempo demais quebram o ritmo da luta. O Simulador
mede a DENSIDADE de contato (EMA ~2s) e, acima do limiar, resolve o
clinch de um jeito diverso — com autor, personalidade e leitura visual.
"""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from neural_fights.simulation.simulacao import Simulador
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


def _sim_fake(p1, p2, modo_rng=0.0):
    """Simulador de contrato: só o que _resolver_clinch consome."""
    sim = object.__new__(Simulador)
    sim.p1, sim.p2 = p1, p2
    p1.rng_runtime = _RngFixo(modo_rng)
    sim.shockwaves = []
    sim.particulas = []
    sim.cam = SimpleNamespace(aplicar_shake=lambda *a, **k: None)
    sim._tempo_clinch = 0.5
    sim._clinch_cooldown = 0.0
    return sim


def _par():
    p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=0.8)
    return p1, p2


class ResolvedorDeClinchTests(unittest.TestCase):
    def test_resolucao_separa_os_corpos(self):
        p1, p2 = _par()
        sim = _sim_fake(p1, p2)
        sim._resolver_clinch(0.8, p2.pos[0] - p1.pos[0], p2.pos[1] - p1.pos[1])

        # Alguma separação física aconteceu (velocidades opostas na linha).
        vel_relativa = (p2.vel[0] - p1.vel[0])  # eixo x é a linha entre eles
        self.assertGreater(abs(vel_relativa), 4.0)
        # Densidade resetada parcialmente + cooldown armado.
        self.assertLess(sim._tempo_clinch, 0.5)
        self.assertGreater(sim._clinch_cooldown, 0.0)
        # Telemetria: o iniciador registrou o clinch.
        total = (p1.contadores_luta["clinches"]
                 + p2.contadores_luta["clinches"])
        self.assertEqual(total, 1)

    def test_modos_diversos_sao_alcancaveis(self):
        """Varrendo o sorteio, mais de um modo de resolução acontece —
        a saída do clinch é uma roleta, não um script único."""
        modos_vistos = set()
        for valor in (0.05, 0.35, 0.65, 0.9):
            p1, p2 = _par()
            sim = _sim_fake(p1, p2, modo_rng=valor)
            brain = SimpleNamespace(
                agressividade_efetiva=lambda: 0.5,
                perfil={"agressao": 0.5, "mobilidade": 0.5, "cautela": 0.5},
                tempo_combate=1.0,
            )
            p1.brain = brain
            sim._resolver_clinch(
                0.8, p2.pos[0] - p1.pos[0], p2.pos[1] - p1.pos[1]
            )
            tell = getattr(brain, "tell_atual", None)
            if tell:
                modos_vistos.add(tell.get("modo"))
        self.assertGreaterEqual(len(modos_vistos), 2, modos_vistos)

    def test_funciona_sem_brains(self):
        """Lutadores sem IA (dummies/manuais) também separam sem crash."""
        p1, p2 = _par()
        sim = _sim_fake(p1, p2)
        sim._resolver_clinch(0.8, 0.8, 0.0)
        self.assertEqual(
            p1.contadores_luta["clinches"] + p2.contadores_luta["clinches"], 1
        )


class RitmoDeLutaTests(unittest.TestCase):
    def test_matchup_de_alcance_curto_dispara_resolucoes(self):
        """Espelho Orbital: o pior fabricante de clinch do roster —
        precisa disparar o resolvedor pelo menos uma vez."""
        sim = Simulador(
            {"p1_nome": "Aria das Chamas", "p2_nome": "Maximus a Sombria",
             "best_of": 1},
            headless=True, seed=5,
        )
        try:
            for _ in range(3600):
                sim.update(1 / 60)
                if sim.round_finalizado:
                    break
            clinches = (sim.p1.contadores_luta.get("clinches", 0)
                        + sim.p2.contadores_luta.get("clinches", 0))
            self.assertGreaterEqual(clinches, 1)
        finally:
            sim.close()

    def test_verbo_ofensivo_nao_prensa_a_curta_distancia(self):
        """Onda 8G/10A: MATAR colado no alvo quase não EMPURRA o corpo
        (componente radial), mas o corpo não congela — orbita (lateral)."""
        p1, p2 = _par()
        brain = SimpleNamespace(
            acao_atual="MATAR", tracos=[], medo=0.0,
            ritmo_combate=1.0, momentum=0.0, dir_circular=1,
        )
        p1.brain = brain
        p1.alcance_ideal = 2.0
        p1.angulo_olhar = 0.0   # olha para +x: radial = vel[0], lateral = vel[1]

        p1.executar_movimento(1 / 60, distancia=0.5)   # colado
        radial_colado = p1.vel[0]
        lateral_colado = abs(p1.vel[1])
        p1.vel = [0.0, 0.0]
        p1.executar_movimento(1 / 60, distancia=3.0)   # aproximando
        radial_longe = p1.vel[0]
        self.assertLess(radial_colado, radial_longe * 0.3)
        self.assertGreater(lateral_colado, 0.0)


if __name__ == "__main__":
    unittest.main()
