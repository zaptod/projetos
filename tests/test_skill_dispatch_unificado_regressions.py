# -*- coding: utf-8 -*-
"""Regressões do despachante unificado de skills (Onda 10D).

`usar_skill_arma` e `usar_skill_classe` eram duas cópias divergentes do mesmo
dispatch. Agora ambas pagam/gatilham e delegam a `_executar_skill`; as
diferenças por origem ficam explícitas (recoil só na arma, bônus do
Piromante só na classe) e a sonda de "cast com consequência" vale para as
duas.
"""

from __future__ import annotations

import unittest

from neural_fights.core.skills import get_skill_data
from tests import test_remaining_skill_regressions as _helpers


def _par():
    p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=3.0)
    return p1, p2


def _arma_skill(p, nome):
    data = get_skill_data(nome)
    p.skills_arma = [{"nome": nome, "custo": data.get("custo", 0.0), "data": data}]
    p.skill_atual_idx = 0
    p.cd_skills[nome] = 0.0


class DispatchUnificadoTests(unittest.TestCase):
    def test_arma_e_classe_passam_pelo_mesmo_executor(self):
        p1, p2 = _par()
        chamadas = []
        original = p1._executar_skill

        def espiao(*a, **k):
            chamadas.append(k.get("origem"))
            return original(*a, **k)

        p1._executar_skill = espiao
        _arma_skill(p1, "Bola de Fogo")
        _helpers.RemainingSkillRegressionTests._add_class_skill(p1, "Lâmina de Sangue")
        self.assertTrue(p1.usar_skill_arma(0, alvo=p2))
        self.assertTrue(p1.usar_skill_classe("Lâmina de Sangue", alvo=p2))
        self.assertEqual(chamadas, ["arma", "classe"])
        self.assertEqual(p1.contadores_luta["skills_lancadas"], 2)

    def test_recoil_so_na_arma(self):
        p1, p2 = _par()
        _arma_skill(p1, "Bola de Fogo")            # dano > 20 → recoil
        p1.usar_skill_arma(0, alvo=p2)
        self.assertLess(p1.vel[0], 0.0)
        p3, p4 = _par()
        _helpers.RemainingSkillRegressionTests._add_class_skill(p3, "Bola de Fogo")
        p3.usar_skill_classe("Bola de Fogo", alvo=p4)
        self.assertEqual(p3.vel[0], 0.0)

    def test_bonus_piromante_so_na_classe(self):
        base, alvo = _par()
        _helpers.RemainingSkillRegressionTests._add_class_skill(base, "Bola de Fogo")
        base.usar_skill_classe("Bola de Fogo", alvo=alvo)
        dano_base = base.buffer_projeteis[-1].dano

        piro, alvo2 = _par()
        piro.classe_nome = "Piromante (Fogo)"
        _helpers.RemainingSkillRegressionTests._add_class_skill(piro, "Bola de Fogo")
        piro.usar_skill_classe("Bola de Fogo", alvo=alvo2)
        self.assertGreater(piro.buffer_projeteis[-1].dano, dano_base * 1.1)

        piro_arma, alvo3 = _par()
        piro_arma.classe_nome = "Piromante (Fogo)"
        _arma_skill(piro_arma, "Bola de Fogo")
        piro_arma.usar_skill_arma(0, alvo=alvo3)
        self.assertAlmostEqual(piro_arma.buffer_projeteis[-1].dano, dano_base, places=6)

    def test_cast_com_consequencia_e_contado(self):
        p1, p2 = _par()
        _helpers.RemainingSkillRegressionTests._add_class_skill(p1, "Teleporte Relâmpago")
        self.assertTrue(p1.usar_skill_classe("Teleporte Relâmpago", alvo=p2, proposito="ESCAPE"))
        self.assertTrue(p1._cast_pendente["consequencia"])
        for _ in range(95):
            p1.update(1 / 60, p2)
        self.assertEqual(p1.contadores_luta["casts_com_consequencia"], 1)
        self.assertIsNone(p1._cast_pendente)

    def test_status_aplicado_conta_para_o_autor(self):
        p1, p2 = _par()
        p2.tomar_dano(10.0, 1.0, 0.0, "CONGELADO", atacante=p1,
                      metadata_impacto={"eh_skill": True})
        self.assertEqual(p1.contadores_luta["status_cc_aplicados"], 1)

    def test_buffers_de_summon_e_trap_existem_desde_o_inicio(self):
        p1, _ = _par()
        self.assertEqual(p1.buffer_summons, [])
        self.assertEqual(p1.buffer_traps, [])


if __name__ == "__main__":
    unittest.main()
