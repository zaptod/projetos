# -*- coding: utf-8 -*-
"""LayoutSpec — âncoras de HUD/broadcast nas duas proporções (Passe 3).

Decisão de direção: 16:9 e 9:16 DESDE O INÍCIO. Todo elemento de tela
(barras, placar, ticker, lower-third, VS screen) consome este spec em vez
de números soltos — o modo retrato deixa de ser "os mesmos retângulos
espremidos" e vira um layout de verdade.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutSpec:
    portrait: bool
    largura: int
    altura: int

    # Barras dos lutadores (x, y) e tamanho (w, h)
    barra_p1: tuple[int, int]
    barra_p2: tuple[int, int]
    barra_tamanho: tuple[int, int]

    # Faixa de placar/contexto no topo
    placar_y: int

    # Ticker (faixa rolante) — âncora do TOPO da faixa
    ticker_y: int
    ticker_altura: int

    # Lower-thirds de comando (x, y da primeira linha; empilham para cima)
    lower_third_pos: tuple[int, int]
    lower_third_largura: int

    # Tipografia
    fonte_titulo: int
    fonte_media: int
    fonte_pequena: int

    @property
    def centro_x(self) -> int:
        return self.largura // 2

    @property
    def centro_y(self) -> int:
        return self.altura // 2


def obter_layout(largura: int, altura: int) -> LayoutSpec:
    """Spec pela proporção real da janela (não por flag solta)."""
    portrait = altura > largura
    if portrait:
        # 9:16 — barras EMPILHADAS no topo (lado a lado não cabe), ticker
        # mais alto (a zona inferior é coberta por UI do player no celular).
        w_barra = largura - 40
        return LayoutSpec(
            portrait=True,
            largura=largura,
            altura=altura,
            barra_p1=(20, 14),
            barra_p2=(20, 52),
            barra_tamanho=(w_barra, 22),
            placar_y=96,
            ticker_y=altura - 96,
            ticker_altura=30,
            lower_third_pos=(14, altura - 150),
            lower_third_largura=largura - 28,
            fonte_titulo=30,
            fonte_media=18,
            fonte_pequena=13,
        )
    return LayoutSpec(
        portrait=False,
        largura=largura,
        altura=altura,
        barra_p1=(20, 20),
        barra_p2=(largura - 320, 20),
        barra_tamanho=(300, 30),
        placar_y=20,
        ticker_y=altura - 42,
        ticker_altura=30,
        lower_third_pos=(20, altura - 120),
        lower_third_largura=420,
        fonte_titulo=40,
        fonte_media=22,
        fonte_pequena=14,
    )
