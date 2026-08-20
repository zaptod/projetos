# -*- coding: utf-8 -*-
"""Cache de fontes (Passe 2 do programa de arte).

O render criava ``pygame.font.SysFont`` POR FRAME em barras, placar,
painéis, summons e em cada FloatingText — inclusive dentro de um laço de
ajuste de largura. Fonte é recurso caro de construir e barato de guardar:
este módulo memoiza por (família, tamanho, negrito).
"""

from __future__ import annotations

import pygame

_CACHE: dict[tuple[str, int, bool], pygame.font.Font] = {}


def get_fonte(tamanho: int, negrito: bool = False, familia: str = "Arial") -> pygame.font.Font:
    if not pygame.font.get_init():
        # Testes fazem pygame.font.quit() no teardown: fontes criadas na
        # geração anterior ficam inválidas — renasce o módulo E o cache.
        pygame.font.init()
        _CACHE.clear()
    elif _CACHE:
        # O módulo pode ter sido quit+init por FORA deste helper (setup de
        # teste): get_init() é True mas as fontes do cache morreram. Uma
        # sonda barata numa fonte qualquer detecta a geração antiga.
        try:
            next(iter(_CACHE.values())).get_height()
        except pygame.error:
            _CACHE.clear()
    chave = (familia, int(tamanho), bool(negrito))
    fonte = _CACHE.get(chave)
    if fonte is None:
        fonte = pygame.font.SysFont(familia, int(tamanho), bold=bool(negrito))
        _CACHE[chave] = fonte
    return fonte


def get_fonte_impact(tamanho: int) -> pygame.font.Font:
    return get_fonte(tamanho, familia="Impact")


def get_fonte_mono(tamanho: int) -> pygame.font.Font:
    return get_fonte(tamanho, familia="Consolas")


def limpar_cache() -> None:
    """Para testes que reinicializam o pygame.font."""
    _CACHE.clear()
