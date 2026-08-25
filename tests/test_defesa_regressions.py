# -*- coding: utf-8 -*-
"""Regressões das mecânicas defensivas da Onda 8B.

Bloqueio direcional (arco frontal, pago em estamina), parry (guarda
recém-erguida nega golpe físico e cambaleia o atacante), dash universal
(verbo de primeira classe com custo e cooldown) e a estamina viva.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from neural_fights.utils.config import (
    COOLDOWN_DASH_S,
    CUSTO_ESTAMINA_BLOQUEIO,
    CUSTO_ESTAMINA_DASH,
    FATOR_DANO_BLOQUEIO,
    FATOR_DANO_BLOQUEIO_CAVALEIRO,
)
from tests import test_remaining_skill_regressions as _helpers


def _brain_guarda(acao="BLOQUEAR"):
    return SimpleNamespace(
        acao_atual=acao,
        ultimo_bloqueio=99.0,
        raiva=0.0,
        tracos=[],
        medo=0.0,
        ritmo_combate=1.0,
        momentum=0.0,
        processar=lambda *a, **k: None,
    )


def _par_de_lutadores():
    defensor = _helpers.RemainingSkillRegressionTests._fighter("Defensor", x=0.0)
    atacante = _helpers.RemainingSkillRegressionTests._fighter("Atacante", x=2.0)
    defensor.angulo_olhar = 0.0  # olhando para o atacante (+x)
    return defensor, atacante


MELEE = {"eh_corpo_a_corpo": True}


class BloqueioDirecionalTests(unittest.TestCase):
    def test_bloqueio_frontal_reduz_dano_e_consome_estamina(self):
        defensor, atacante = _par_de_lutadores()
        defensor.brain = _brain_guarda()
        defensor.tempo_bloqueando = 1.0  # guarda estabelecida (fora do parry)
        defensor.resolver_impacto(
            100.0, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
        )
        dano = defensor.vida_max - defensor.vida
        self.assertAlmostEqual(dano, 100.0 * FATOR_DANO_BLOQUEIO, delta=1.0)
        self.assertAlmostEqual(
            defensor.estamina, 100.0 - CUSTO_ESTAMINA_BLOQUEIO, delta=0.01
        )
        self.assertEqual(defensor.brain.ultimo_bloqueio, 0.0)

    def test_ataque_por_tras_ignora_bloqueio(self):
        defensor, atacante = _par_de_lutadores()
        defensor.brain = _brain_guarda()
        defensor.tempo_bloqueando = 1.0
        defensor.angulo_olhar = 180.0  # de costas para o atacante (GRAUS)
        defensor.resolver_impacto(
            100.0, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
        )
        dano = defensor.vida_max - defensor.vida
        self.assertGreater(dano, 90.0)
        self.assertAlmostEqual(defensor.estamina, 100.0, delta=0.01)

    def test_guarda_sem_estamina_quebra(self):
        defensor, atacante = _par_de_lutadores()
        defensor.brain = _brain_guarda()
        defensor.tempo_bloqueando = 1.0
        defensor.estamina = 5.0  # abaixo do mínimo: guarda quebrada
        defensor.resolver_impacto(
            100.0, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
        )
        self.assertGreater(defensor.vida_max - defensor.vida, 90.0)

    def test_cavaleiro_e_o_mestre_da_guarda(self):
        defensor, atacante = _par_de_lutadores()
        defensor.classe_nome = "Cavaleiro (Tanque)"
        defensor.brain = _brain_guarda()
        defensor.tempo_bloqueando = 1.0
        defensor.resolver_impacto(
            100.0, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
        )
        dano = defensor.vida_max - defensor.vida
        self.assertAlmostEqual(
            dano, 100.0 * FATOR_DANO_BLOQUEIO_CAVALEIRO, delta=1.0
        )
        self.assertAlmostEqual(
            defensor.estamina, 100.0 - CUSTO_ESTAMINA_BLOQUEIO * 0.5, delta=0.01
        )

    def test_sem_guarda_dano_integral(self):
        defensor, atacante = _par_de_lutadores()
        defensor.brain = _brain_guarda(acao="COMBATE")
        defensor.resolver_impacto(
            100.0, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
        )
        self.assertGreater(defensor.vida_max - defensor.vida, 90.0)


class ParryTests(unittest.TestCase):
    def test_parry_nega_dano_e_cambaleia_atacante(self):
        defensor, atacante = _par_de_lutadores()
        defensor.brain = _brain_guarda()
        defensor.tempo_bloqueando = 0.1  # guarda recém-erguida
        atacante.atacando = True
        defensor.resolver_impacto(
            100.0, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
        )
        self.assertEqual(defensor.vida, defensor.vida_max)
        self.assertGreaterEqual(atacante.stun_timer, 0.4)
        self.assertFalse(atacante.atacando)
        self.assertGreaterEqual(atacante.cooldown_ataque, 0.9)
        self.assertEqual(
            defensor.ultimo_resultado_impacto.bloqueado_por, "parry"
        )

    def test_parry_e_um_por_guarda_erguida(self):
        defensor, atacante = _par_de_lutadores()
        defensor.brain = _brain_guarda()
        defensor.tempo_bloqueando = 0.1
        defensor.resolver_impacto(
            100.0, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
        )
        self.assertEqual(defensor.vida, defensor.vida_max)  # 1º: parry
        defensor.resolver_impacto(
            100.0, 1.0, 0.0, atacante=atacante, metadata_impacto=dict(MELEE)
        )
        # 2º golpe na mesma guarda: bloqueio normal, não parry de novo.
        self.assertLess(defensor.vida, defensor.vida_max)

    def test_parry_nao_vale_contra_projetil(self):
        defensor, atacante = _par_de_lutadores()
        defensor.brain = _brain_guarda()
        defensor.tempo_bloqueando = 0.1
        defensor.resolver_impacto(100.0, 1.0, 0.0, atacante=atacante)
        # Sem eh_corpo_a_corpo: vira bloqueio normal (reduzido, não zerado).
        dano = defensor.vida_max - defensor.vida
        self.assertGreater(dano, 0.0)
        self.assertLess(dano, 50.0)


class DashUniversalTests(unittest.TestCase):
    def test_dash_paga_estamina_cooldown_e_da_janela(self):
        lutador = _helpers.RemainingSkillRegressionTests._fighter("Corredor")
        ok = lutador.iniciar_dash(0.0)
        self.assertTrue(ok)
        self.assertGreater(lutador.vel[0], 10.0)
        self.assertAlmostEqual(lutador.dash_timer, 0.25, delta=0.01)
        self.assertAlmostEqual(
            lutador.estamina, 100.0 - CUSTO_ESTAMINA_DASH, delta=0.01
        )
        self.assertAlmostEqual(lutador.dash_cooldown, COOLDOWN_DASH_S, delta=0.01)

    def test_dash_em_cooldown_ou_sem_folego_falha(self):
        lutador = _helpers.RemainingSkillRegressionTests._fighter("Corredor")
        self.assertTrue(lutador.iniciar_dash(0.0))
        self.assertFalse(lutador.iniciar_dash(0.0))  # cooldown
        lutador.dash_cooldown = 0.0
        lutador.estamina = 10.0
        self.assertFalse(lutador.iniciar_dash(0.0))  # sem estamina


class EstaminaVivaTests(unittest.TestCase):
    def test_estamina_regenera_e_guarda_regenera_menos(self):
        livre, inimigo = _par_de_lutadores()
        livre.estamina = 40.0
        livre.update(0.5, inimigo)
        regen_livre = livre.estamina - 40.0
        self.assertGreater(regen_livre, 0.0)

        guardando, inimigo2 = _par_de_lutadores()
        guardando.estamina = 40.0
        guardando.brain = _brain_guarda()  # fantoche: guarda erguida, sem IA
        guardando.update(0.5, inimigo2)
        regen_guarda = guardando.estamina - 40.0
        self.assertGreater(regen_guarda, 0.0)
        self.assertLess(regen_guarda, regen_livre)


if __name__ == "__main__":
    unittest.main()
