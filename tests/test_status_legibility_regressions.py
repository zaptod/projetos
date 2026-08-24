# -*- coding: utf-8 -*-
"""Contratos do Passe 6 do programa de arte (a luta é legível).

O que se trava aqui: TODO status do runtime tem metadata visual completa
(o vocabulário único — status novo sem visual quebra aqui, não some em
silêncio); o renderer único não explode para nenhum status; e os
eventos de defesa (bloqueio/escudo quebrado/esquiva) disparam por
transição de estado exatamente uma vez.
"""

import unittest
from types import SimpleNamespace

import pygame

from neural_fights.core.status_runtime import (
    STATUS_RUNTIME,
    STATUS_VISUAL,
    StatusTimers,
)
from neural_fights.simulation.simulacao import Simulador

ESTILOS_VALIDOS = {"anel", "tint", "particula"}


class VocabularioVisualTests(unittest.TestCase):
    def test_todo_status_tem_visual_completa(self) -> None:
        """Status novo sem metadata visual é erro de contrato, não um
        efeito invisível."""
        for status_id, dados in STATUS_RUNTIME.items():
            vis = dados.get("visual")
            self.assertIsNotNone(vis, f"{status_id} sem visual")
            self.assertIn("cor", vis)
            self.assertIn("glifo", vis)
            self.assertIn("prioridade", vis)
            self.assertIn(vis.get("estilo"), ESTILOS_VALIDOS, status_id)
            self.assertEqual(len(vis["cor"]), 3)

    def test_visual_nao_tem_orfaos(self) -> None:
        """STATUS_VISUAL não acumula entradas de status que morreram."""
        orfaos = set(STATUS_VISUAL) - set(STATUS_RUNTIME)
        self.assertEqual(orfaos, set())

    def test_prioridade_de_cc_domina_dot(self) -> None:
        """O anel dominante é o que muda a luta AGORA: CC duro acima de
        qualquer dot."""
        for cc in ("ATORDOADO", "CONGELADO", "PARALISIA", "TEMPO_PARADO"):
            for dot in ("ENVENENADO", "QUEIMANDO", "SANGRANDO"):
                self.assertGreater(
                    STATUS_VISUAL[cc]["prioridade"],
                    STATUS_VISUAL[dot]["prioridade"],
                )


def _lutador_fake(status_ativos=(), tell=None):
    timers = StatusTimers()
    for s in status_ativos:
        timers.set(s, 1.5)
    brain = SimpleNamespace(
        tell_atual=tell, tempo_combate=1.0, ultimo_bloqueio=99.0
    )
    return SimpleNamespace(
        status_timers=timers,
        _buffs_validos=lambda: [],
        invencivel_timer=0.0,
        brain=brain,
        dados=SimpleNamespace(cor_r=200, cor_g=60, cor_b=60),
    )


def _sim_fake():
    return SimpleNamespace(tela=pygame.Surface((300, 300)), game_feel=None)


class RendererUnicoTests(unittest.TestCase):
    def test_nenhum_status_explode_o_renderer(self) -> None:
        fake = _sim_fake()
        for status_id in STATUS_RUNTIME:
            lut = _lutador_fake([status_id])
            Simulador._desenhar_status_e_defesa(fake, lut, (150, 150), 20)

    def test_tells_desenham_sem_explodir(self) -> None:
        fake = _sim_fake()
        for tipo in ("instinto", "hesitacao"):
            lut = _lutador_fake(tell={"tipo": tipo, "ate": 2.0})
            Simulador._desenhar_status_e_defesa(fake, lut, (150, 150), 20)

    def test_escudo_com_hp_desenha(self) -> None:
        fake = _sim_fake()
        lut = _lutador_fake()
        lut._buffs_validos = lambda: [
            SimpleNamespace(escudo=40.0, escudo_atual=10.0)
        ]
        Simulador._desenhar_status_e_defesa(fake, lut, (150, 150), 20)


class FeedbackDeDefesaTests(unittest.TestCase):
    def _sim(self, p1, p2):
        return SimpleNamespace(
            p1=p1, p2=p2, textos=[], particulas=[],
            block_effects=[], dash_trails=[], _fx_defesa={},
        )

    def _lut(self):
        lut = _lutador_fake()
        lut.pos = [3.0, 3.0]
        lut.angulo_olhar = 0.0
        return lut

    def test_bloqueio_dispara_uma_vez_na_transicao(self) -> None:
        p1, p2 = self._lut(), self._lut()
        sim = self._sim(p1, p2)
        Simulador._atualizar_feedback_defesa(sim)  # estabelece baseline
        self.assertEqual(sim.textos, [])
        p1.brain.ultimo_bloqueio = 0.0  # absorveu em guarda AGORA
        Simulador._atualizar_feedback_defesa(sim)
        # Re-pino (reforma "luta limpa"): o texto "BLOCK!" saiu — o
        # contrato agora é o ARCO do BlockEffect, que já era a leitura.
        self.assertEqual(len(sim.block_effects), 1)
        p1.brain.ultimo_bloqueio = 0.016  # mesmo bloqueio envelhecendo
        Simulador._atualizar_feedback_defesa(sim)
        self.assertEqual(len(sim.block_effects), 1)  # não re-dispara

    def test_escudo_quebrado_estilhaca_uma_vez(self) -> None:
        p1, p2 = self._lut(), self._lut()
        escudo = SimpleNamespace(escudo=40.0, escudo_atual=15.0)
        p1._buffs_validos = lambda: [escudo]
        sim = self._sim(p1, p2)
        Simulador._atualizar_feedback_defesa(sim)
        escudo.escudo_atual = 0.0
        Simulador._atualizar_feedback_defesa(sim)
        # Re-pino (reforma): o texto saiu; o contrato são os ESTILHAÇOS.
        estilhacos = len(sim.particulas)
        self.assertGreater(estilhacos, 0)
        Simulador._atualizar_feedback_defesa(sim)
        self.assertEqual(len(sim.particulas), estilhacos)  # não re-dispara

    def test_esquiva_dispara_por_incremento(self) -> None:
        p1, p2 = self._lut(), self._lut()
        sim = self._sim(p1, p2)
        Simulador._atualizar_feedback_defesa(sim)
        p1.esquivas_visuais = 1
        Simulador._atualizar_feedback_defesa(sim)
        # Re-pino (reforma): o texto saiu; o contrato é o BURST de
        # afterimages (DashTrail), que já contava a esquiva sozinho.
        self.assertEqual(len(sim.dash_trails), 1)


if __name__ == "__main__":
    unittest.main()
