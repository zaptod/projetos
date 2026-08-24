# -*- coding: utf-8 -*-
"""Contratos do RENDER DE ROSTO (identidade v5).

O rosto é desenhado em todas as distâncias de câmera, ângulos de olhar e
estados de squash do jogo. O contrato que este arquivo trava é medido em
PIXELS, não no olho: nenhuma tinta de rosto pode cair fora do corpo, em
nenhuma combinação — foi assim que 1474 combinações quebradas
apareceram (mínimos absolutos de traço estourando corpos pequenos, e a
lágrima passando da borda em qualquer tamanho).
"""
import unittest

import numpy as np
import pygame

from neural_fights.effects.character_flair import (
    EXPRESSOES,
    HUMOR_EXPRESSAO,
    desenhar_rosto,
    resolver_expressao,
)

BG = (0, 255, 0)
CORPO = (206, 60, 74)
LADO = 180
C = LADO // 2


def _render(expressao, raio, ang, esc_x, esc_y, t):
    """Desenha corpo + rosto e devolve (máscara de tinta, rx, ry)."""
    tela = pygame.Surface((LADO, LADO))
    tela.fill(BG)
    rx = max(1, int(raio * esc_x))
    ry = max(1, int(raio * esc_y))
    pygame.draw.ellipse(tela, CORPO, (C - rx, C - ry, rx * 2, ry * 2))
    desenhar_rosto(tela, (C, C), raio, ang, esc_x, esc_y, expressao,
                   t=t, seed=3, cor_corpo=CORPO)
    arr = pygame.surfarray.array3d(tela)
    fundo = np.all(arr == np.array(BG), axis=2)
    corpo = np.all(arr == np.array(CORPO), axis=2)
    return ~(fundo | corpo), rx, ry


def _fora_do_corpo(tinta, rx, ry):
    """Quantos pixels de tinta caem fora da elipse do corpo."""
    xs, ys = np.nonzero(tinta)
    if len(xs) == 0:
        return 0, 0.0
    d = np.hypot((xs - C) / rx, (ys - C) / ry)
    return int(np.count_nonzero(d > 1.02)), float(d.max())


class ContencaoNoCorpoTests(unittest.TestCase):
    """A varredura completa (24 expressões × ângulos × raios × squash)."""

    # Amostra representativa (a varredura EXAUSTIVA — 16k combinações —
    # vive no auditor do scratchpad e roda sob demanda).
    ANGULOS = (0, 135, 250)
    RAIOS = (8, 20, 56)
    SQUASHES = ((1.0, 1.0), (1.35, 0.72), (0.72, 1.35))
    TEMPOS = (1.234,)

    def test_nenhuma_tinta_de_rosto_sai_do_corpo(self) -> None:
        falhas = []
        for expressao in EXPRESSOES:
            for ang in self.ANGULOS:
                for raio in self.RAIOS:
                    for esc_x, esc_y in self.SQUASHES:
                        for t in self.TEMPOS:
                            tinta, rx, ry = _render(
                                expressao, raio, ang, esc_x, esc_y, t
                            )
                            fora, pior = _fora_do_corpo(tinta, rx, ry)
                            if fora > 2:
                                falhas.append(
                                    f"{expressao} ang={ang} R={raio} "
                                    f"esc=({esc_x},{esc_y}) t={t}: "
                                    f"{fora}px fora (d={pior:.2f})"
                                )
        self.assertEqual(falhas[:5], [], f"{len(falhas)} combinações vazando")

    def test_rosto_existe_em_tamanho_legivel(self) -> None:
        """Acima do piso de LOD o rosto SEMPRE aparece (nada de sumir)."""
        for expressao in EXPRESSOES:
            tinta, _, _ = _render(expressao, 34, 20.0, 1.0, 1.0, 1.234)
            self.assertGreater(
                int(np.count_nonzero(tinta)), 20,
                f"{expressao} praticamente invisível em tamanho de jogo",
            )

    def test_corpo_minusculo_nao_ganha_rosto(self) -> None:
        """Abaixo do piso medido (7px de raio efetivo) o rosto viraria
        ruído de sub-pixel — o corpo fica um ponto limpo."""
        tinta, _, _ = _render("furia", 6, 0.0, 1.0, 1.0, 1.234)
        self.assertEqual(int(np.count_nonzero(tinta)), 0)


class ResolvedorDeExpressaoTests(unittest.TestCase):
    def _fighter(self, **kw):
        from types import SimpleNamespace

        base = dict(
            morto=False, stun_timer=0.0, flash_timer=0.0, canalizando=False,
            atacando=False, modo_adrenalina=False,
            brain=SimpleNamespace(tell_atual=None, tempo_combate=1.0,
                                  humor="CALMO", acao_atual="COMBATE"),
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_prioridade_morte_vence_tudo(self) -> None:
        l = self._fighter(morto=True, stun_timer=5.0, atacando=True)
        self.assertEqual(resolver_expressao(l, 1.0), "morto")

    def test_dano_vence_ataque(self) -> None:
        l = self._fighter(flash_timer=0.2, atacando=True)
        self.assertEqual(resolver_expressao(l, 1.0), "dor")

    def test_todo_humor_tem_expressao_desenhavel(self) -> None:
        """Humor novo sem rosto é erro de contrato, não rosto genérico."""
        for humor, expressao in HUMOR_EXPRESSAO.items():
            self.assertIn(expressao, EXPRESSOES, humor)

    def test_humor_desconhecido_cai_em_neutro(self) -> None:
        l = self._fighter()
        l.brain.humor = "INEXISTENTE"
        self.assertEqual(resolver_expressao(l, 1.0), "neutro")


if __name__ == "__main__":
    unittest.main()
