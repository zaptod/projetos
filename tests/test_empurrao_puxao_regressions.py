# -*- coding: utf-8 -*-
"""Regressões dos efeitos que eram `pass` (Onda 10D).

EMPURRAO empurra de verdade (e lança: na parede vira wall-splat), EXPLOSAO
tem raio por padrão, PUXADO/VORTEX puxam para a origem.
"""

from __future__ import annotations

import unittest

from neural_fights.core.combat import AreaEffect, Projetil
from neural_fights.utils.config import FORCA_EMPURRAO_PADRAO
from tests import test_remaining_skill_regressions as _helpers


def _par(dist=1.0):
    p1 = _helpers.RemainingSkillRegressionTests._fighter("Um", x=0.0, y=0.0)
    p2 = _helpers.RemainingSkillRegressionTests._fighter("Dois", x=dist, y=0.0)
    return p1, p2


class EmpurraoTests(unittest.TestCase):
    def test_empurrao_soma_velocidade_e_lanca(self):
        p1, p2 = _par()
        p1.tomar_dano(30.0, 1.0, 0.0, "EMPURRAO", atacante=p2,
                      metadata_impacto={"forca_empurrao": 20.0, "eh_skill": True})
        self.assertGreater(p1.vel[0], 20.0)
        self.assertIs(p1.lancado_por, p2)
        self.assertGreater(p1.lancado_timer, 0.0)

    def test_empurrao_sem_forca_usa_o_padrao(self):
        p1, p2 = _par()
        p1.tomar_dano(5.0, 1.0, 0.0, "EMPURRAO", atacante=p2, metadata_impacto={"eh_skill": True})
        self.assertGreaterEqual(p1.vel[0], FORCA_EMPURRAO_PADRAO * 0.9)

    def test_normal_nao_empurra_extra(self):
        p1, p2 = _par()
        p1.tomar_dano(5.0, 1.0, 0.0, "NORMAL", atacante=p2, metadata_impacto={"eh_skill": True})
        # Só o knockback base (15-25); sem o empurrão extra nem o estado lançado.
        self.assertLess(p1.vel[0], 26.0)
        self.assertIsNone(p1.lancado_por)


class ExplosaoTests(unittest.TestCase):
    def test_efeito_explosao_ganha_raio_por_padrao(self):
        p1, _ = _par()
        proj = Projetil("Bola de Fogo", 0.0, 0.0, 0.0, p1)
        self.assertGreater(proj.raio_explosao, 0.0)
        self.assertAlmostEqual(proj.raio_explosao, proj.raio * 2.0, places=6)

    def test_raio_declarado_prevalece(self):
        p1, _ = _par()
        nome = next(n for n, d in __import__("neural_fights.core.skills", fromlist=["SKILL_DB"]).SKILL_DB.items()
                    if d.get("raio_explosao") and d.get("tipo") == "PROJETIL")
        proj = Projetil(nome, 0.0, 0.0, 0.0, p1)
        self.assertGreater(proj.raio_explosao, 0.0)


class PuxaoTests(unittest.TestCase):
    def test_puxado_arrasta_para_a_origem(self):
        p1, p2 = _par(dist=3.0)
        p1.tomar_dano(5.0, 0.0, 0.0, "PUXADO", atacante=p2,
                      metadata_impacto={"origem_puxao": (3.0, 0.0), "eh_skill": True})
        self.assertIsNotNone(p1.puxao)
        p1.stun_timer = 1.0     # sem IA/movimento próprio: só o puxão
        x0 = p1.pos[0]
        for _ in range(30):
            p1.update(1 / 60, p2)
        self.assertGreater(p1.pos[0], x0 + 0.5)
        self.assertIsNone(p1.puxao)

    def test_vortex_puxa_forte(self):
        p1, _ = _par()
        area = AreaEffect("Buraco Negro", 0.0, 0.0, p1)
        self.assertGreaterEqual(area.forca_puxar, 30.0)


if __name__ == "__main__":
    unittest.main()
