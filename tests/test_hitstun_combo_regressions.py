# -*- coding: utf-8 -*-
"""Regressões do hitstun e da mecânica de combos (Onda 8H).

Quem apanha perde a resposta por um instante (hitstun); hits emendados
na janela viram combo; o stun decresce por hit e o pushback cresce
(anti-stunlock); guarda bloqueada não atordoa; o burst de escape é o
contra-jogo pago em estamina com chance vinda da personalidade.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.utils.config import (
    CUSTO_ESTAMINA_BURST,
    HITSTUN_MAX_S,
    HITSTUN_MIN_S,
)
from tests import test_remaining_skill_regressions as _helpers

MELEE = {"eh_corpo_a_corpo": True, "tipo_fonte": "ataque_corpo_a_corpo"}


class _RngFixo:
    def __init__(self, valor=0.0):
        self.valor = valor

    def random(self):
        return self.valor

    def uniform(self, a, b):
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


def _par():
    alvo = _helpers.RemainingSkillRegressionTests._fighter("Alvo", x=0.0)
    atacante = _helpers.RemainingSkillRegressionTests._fighter("Autor", x=1.5)
    return alvo, atacante


def _golpe(alvo, atacante, dano=40.0):
    alvo.invencivel_timer = 0.0
    atacante.ataque_id += 1  # cada golpe é um swing novo
    alvo.resolver_impacto(
        dano, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
    )


class HitstunTests(unittest.TestCase):
    def test_golpe_real_gera_hitstun(self):
        alvo, atacante = _par()
        _golpe(alvo, atacante)
        self.assertGreater(alvo.stun_timer, HITSTUN_MIN_S)
        self.assertLessEqual(alvo.stun_timer, HITSTUN_MAX_S + 0.01)
        self.assertEqual(alvo.combo_contra, 1)
        self.assertIs(alvo.combo_contra_autor, atacante)

    def test_dot_nao_gera_hitstun(self):
        alvo, atacante = _par()
        alvo.resolver_impacto(
            40.0, 0.0, 0.0, atacante=atacante,
            metadata_impacto={"tipo_fonte": "dot_encanto"},
        )
        self.assertEqual(alvo.stun_timer, 0.0)
        self.assertEqual(alvo.combo_contra, 0)

    def test_golpe_bloqueado_nao_gera_hitstun(self):
        """A guarda é o quebra-combo universal."""
        alvo, atacante = _par()
        alvo.brain = SimpleNamespace(
            acao_atual="BLOQUEAR", ultimo_bloqueio=99.0, raiva=0.0,
            tracos=[], medo=0.0, ritmo_combate=1.0, momentum=0.0,
        )
        alvo.tempo_bloqueando = 1.0
        alvo.angulo_olhar = 0.0
        _golpe(alvo, atacante)
        self.assertEqual(alvo.stun_timer, 0.0)
        self.assertEqual(alvo.combo_contra, 0)

    def test_hitstun_decresce_a_cada_hit_do_combo(self):
        alvo, atacante = _par()
        stuns = []
        for _ in range(3):
            alvo.stun_timer = 0.0
            _golpe(alvo, atacante)
            stuns.append(alvo.stun_timer)
        self.assertGreater(stuns[0], stuns[1])
        self.assertGreater(stuns[1], stuns[2])
        self.assertEqual(alvo.combo_contra, 3)

    def test_tanque_resiste_mais(self):
        alvo, atacante = _par()
        alvo.classe_nome = "Cavaleiro (Tanque)"
        # Sem guarda erguida: o Cavaleiro apanha, mas o corpo aguenta.
        _golpe(alvo, atacante)
        stun_tanque = alvo.stun_timer

        alvo2, atacante2 = _par()
        _golpe(alvo2, atacante2)
        self.assertLess(stun_tanque, alvo2.stun_timer)

    def test_oitavo_hit_acorda(self):
        """Teto anti-stunlock: do 8º hit em diante, stun zero."""
        alvo, atacante = _par()
        alvo.brain = None
        for _ in range(8):
            alvo.stun_timer = 0.0
            alvo.rng_runtime = _RngFixo(1.0)  # nunca dá burst
            _golpe(alvo, atacante)
        self.assertEqual(alvo.combo_contra, 8)
        self.assertEqual(alvo.stun_timer, 0.0)

    def test_janela_expira_e_combo_morre(self):
        alvo, atacante = _par()
        _golpe(alvo, atacante)
        self.assertEqual(alvo.combo_contra, 1)
        alvo.combo_contra_timer = 0.001
        inimigo_fake = SimpleNamespace(
            pos=[9.0, 5.0], morto=True, vel=[0, 0], z=0.0,
        )
        alvo.update(0.1, inimigo_fake)
        self.assertEqual(alvo.combo_contra, 0)
        self.assertIsNone(alvo.combo_contra_autor)


class BurstDeEscapeTests(unittest.TestCase):
    def test_burst_no_terceiro_hit_com_sorteio_favoravel(self):
        alvo, atacante = _par()
        alvo.rng_runtime = _RngFixo(0.0)  # sempre passa no sorteio
        alvo.brain = SimpleNamespace(
            chance_burst_combo=0.9, tempo_combate=1.0, raiva=0.0,
        )
        for _ in range(3):
            alvo.stun_timer = 0.0
            _golpe(alvo, atacante)
        # Burst: estamina paga, invulnerabilidade curta, combo zerado,
        # agressor empurrado.
        self.assertAlmostEqual(
            alvo.estamina, 100.0 - CUSTO_ESTAMINA_BURST, delta=1.0
        )
        self.assertGreater(alvo.invulnerabilidade_skill_timer, 0.0)
        self.assertEqual(alvo.combo_contra, 0)
        self.assertGreater(atacante.vel[0], 5.0)
        self.assertEqual(alvo.contadores_luta.get("bursts"), 1)

    def test_sem_estamina_nao_ha_burst(self):
        alvo, atacante = _par()
        alvo.rng_runtime = _RngFixo(0.0)
        alvo.estamina = 10.0
        alvo.brain = SimpleNamespace(chance_burst_combo=0.9, raiva=0.0)
        for _ in range(3):
            alvo.stun_timer = 0.0
            _golpe(alvo, atacante)
        self.assertEqual(alvo.contadores_luta.get("bursts", 0), 0)
        self.assertEqual(alvo.combo_contra, 3)


class ComboFlowTests(unittest.TestCase):
    def test_contador_do_atacante_registra_combo(self):
        alvo, atacante = _par()
        alvo.rng_runtime = _RngFixo(1.0)  # sem burst
        for _ in range(3):
            alvo.stun_timer = 0.0
            _golpe(alvo, atacante)
        self.assertEqual(atacante.contadores_luta.get("combos_2mais"), 1)
        self.assertEqual(atacante.contadores_luta.get("maior_combo"), 3)


if __name__ == "__main__":
    unittest.main()
