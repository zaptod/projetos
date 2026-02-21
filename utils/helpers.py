"""
NEURAL FIGHTS - Funções Utilitárias
Helpers genéricos usados em todo o projeto.
"""
import math
import random


def clamp(valor, minimo, maximo):
    """Limita um valor entre mínimo e máximo."""
    return max(minimo, min(maximo, valor))


def lerp(a, b, t):
    """Interpolação linear entre a e b com fator t (0-1)."""
    return a + (b - a) * clamp(t, 0, 1)


def ease_out_quad(t):
    """Easing quadrático de saída (desaceleração)."""
    return 1 - (1 - t) ** 2


def ease_in_out_quad(t):
    """Easing quadrático de entrada e saída."""
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def distancia(p1, p2):
    """Distância euclidiana entre dois pontos."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def angulo_entre_pontos(p1, p2):
    """Ângulo em graus de p1 para p2."""
    return math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))


def random_range(minimo, maximo):
    """Valor aleatório entre mínimo e máximo (float)."""
    return random.uniform(minimo, maximo)


def random_choice_weighted(opcoes, pesos):
    """Escolha aleatória ponderada."""
    return random.choices(opcoes, weights=pesos, k=1)[0]


def format_timer(segundos):
    """Formata segundos em MM:SS."""
    mins = int(segundos // 60)
    secs = int(segundos % 60)
    return f"{mins:02d}:{secs:02d}"


def rgb_to_hex(r, g, b):
    """Converte RGB para hexadecimal."""
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_color):
    """Converte hexadecimal para RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def blend_colors(cor1, cor2, fator):
    """Mistura duas cores RGB com fator (0=cor1, 1=cor2)."""
    return tuple(int(lerp(c1, c2, fator)) for c1, c2 in zip(cor1, cor2))


__all__ = [
    'clamp', 'lerp', 'ease_out_quad', 'ease_in_out_quad',
    'distancia', 'angulo_entre_pontos',
    'random_range', 'random_choice_weighted',
    'format_timer', 'rgb_to_hex', 'hex_to_rgb', 'blend_colors',
]
