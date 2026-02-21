"""
NEURAL FIGHTS - Módulo Utils
Funções utilitárias gerais e configurações.
"""

import math
import random

# Re-exporta configurações
from utils.config import (
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


def ease_out(t):
    """Easing function para animações suaves"""
    return 1 - (1 - t) ** 2


def ease_in_out(t):
    """Easing function para início e fim suaves"""
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def random_range(min_val, max_val):
    """Número aleatório entre min e max (float)"""
    return random.uniform(min_val, max_val)


def random_color_variation(base_color, variation=30):
    """Gera uma variação de cor próxima à cor base"""
    r = clamp(base_color[0] + random.randint(-variation, variation), 0, 255)
    g = clamp(base_color[1] + random.randint(-variation, variation), 0, 255)
    b = clamp(base_color[2] + random.randint(-variation, variation), 0, 255)
    return (r, g, b)


def angle_between(x1, y1, x2, y2):
    """Ângulo entre dois pontos em graus"""
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def distance(x1, y1, x2, y2):
    """Distância entre dois pontos"""
    return math.hypot(x2 - x1, y2 - y1)


def normalize_vector(x, y):
    """Normaliza um vetor 2D"""
    mag = math.hypot(x, y)
    if mag == 0:
        return 0, 0
    return x / mag, y / mag


def rotate_point(x, y, angle_degrees, cx=0, cy=0):
    """Rotaciona um ponto ao redor de um centro"""
    angle_rad = math.radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    # Translada para origem
    x -= cx
    y -= cy
    
    # Rotaciona
    new_x = x * cos_a - y * sin_a
    new_y = x * sin_a + y * cos_a
    
    # Translada de volta
    return new_x + cx, new_y + cy


__all__ = [
    # Funções utilitárias
    'clamp',
    'lerp',
    'ease_out',
    'ease_in_out',
    'random_range',
    'random_color_variation',
    'angle_between',
    'distance',
    'normalize_vector',
    'rotate_point',
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
