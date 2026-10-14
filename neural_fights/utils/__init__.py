"""
NEURAL FIGHTS - Módulo Utils
Funções utilitárias gerais e configurações.

MOT-129 (auditoria de 11/10/2026): saíram ``ease_out``, ``ease_in_out``,
``random_range``, ``random_color_variation``, ``angle_between``,
``normalize_vector`` e ``rotate_point``, que não tinham nenhum chamador.
"""

import math

# Re-exporta configurações
from neural_fights.utils.config import (
    PPM, GRAVIDADE_Z, ATRITO, ALTURA_PADRAO,
    LARGURA, ALTURA, FPS,
    PRETO, BRANCO, CHAO_COR, COR_FUNDO, COR_GRID,
    VERMELHO_SANGUE, SANGUE_ESCURO, AMARELO_FAISCA,
    VERDE_VIDA, VERMELHO_VIDA, AZUL_MANA, COR_CORPO,
    COR_P1, COR_P2, COR_UI_BG, COR_TEXTO_TITULO, COR_TEXTO_INFO,
)


def clamp(value, min_val, max_val):
    """Limita um valor entre min e max"""
    return max(min_val, min(max_val, value))


def lerp(a, b, t):
    """Interpolação linear entre a e b"""
    return a + (b - a) * t


def distance(x1, y1, x2, y2):
    """Distância entre dois pontos"""
    return math.hypot(x2 - x1, y2 - y1)


__all__ = [
    # Funções utilitárias
    'clamp',
    'lerp',
    'distance',
    # Configurações - Física
    'PPM', 'GRAVIDADE_Z', 'ATRITO', 'ALTURA_PADRAO',
    # Configurações - Visual
    'LARGURA', 'ALTURA', 'FPS',
    # Configurações - Cores
    'PRETO', 'BRANCO', 'CHAO_COR', 'COR_FUNDO', 'COR_GRID',
    'VERMELHO_SANGUE', 'SANGUE_ESCURO', 'AMARELO_FAISCA',
    'VERDE_VIDA', 'VERMELHO_VIDA', 'AZUL_MANA', 'COR_CORPO',
    'COR_P1', 'COR_P2', 'COR_UI_BG', 'COR_TEXTO_TITULO', 'COR_TEXTO_INFO',
]
