"""
NEURAL FIGHTS - Sistema de Física
Funções de colisão e cálculos geométricos.
"""

import math


def normalizar_angulo(ang):
    """Normaliza ângulo para -180 a 180"""
    return (ang + 180) % 360 - 180


def distancia_pontos(p1, p2):
    """Calcula distância entre dois pontos"""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def colisao_linha_circulo(pt1, pt2, centro_circulo, raio_circulo):
    """
    Verifica se uma linha (pt1→pt2) colide com um círculo.
    
    Returns:
        bool: True se houver colisão
    """
    x1, y1 = pt1
    x2, y2 = pt2
    cx, cy = centro_circulo
    dx, dy = x2 - x1, y2 - y1
    
    if dx == 0 and dy == 0:
        return False
    
    t = ((cx - x1) * dx + (cy - y1) * dy) / (dx*dx + dy*dy)
    t = max(0, min(1, t))
    
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    dist_sq = (cx - closest_x)**2 + (cy - closest_y)**2
    return dist_sq <= raio_circulo**2


def intersect_line_circle(pt1, pt2, circle_center, radius):
    """
    Encontra pontos de interseção entre uma linha e um círculo.
    
    Returns:
        list: Lista de pontos de interseção (0, 1 ou 2 pontos)
    """
    x1, y1 = pt1
    x2, y2 = pt2
    cx, cy = circle_center
    dx, dy = x2 - x1, y2 - y1
    fx, fy = x1 - cx, y1 - cy
    
    a = dx*dx + dy*dy
    b = 2*(fx*dx + fy*dy)
    c = (fx*fx + fy*fy) - radius*radius
    
    delta = b*b - 4*a*c
    
    if delta < 0 or a == 0:
        return []
    
    delta_sqrt = math.sqrt(delta)
    t1 = (-b - delta_sqrt) / (2*a)
    t2 = (-b + delta_sqrt) / (2*a)
    
    points = []
    if 0 <= t1 <= 1:
        points.append((x1 + t1*dx, y1 + t1*dy))
    if 0 <= t2 <= 1:
        points.append((x1 + t2*dx, y1 + t2*dy))
    
    return points


def colisao_linha_linha(p1, p2, p3, p4):
    """
    Verifica se duas linhas (p1→p2) e (p3→p4) se cruzam.
    
    Returns:
        bool: True se houver interseção
    """
    def ccw(A, B, C):
        return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
    
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def angulo_entre_pontos(p1, p2):
    """
    Calcula o ângulo em graus de p1 para p2.
    
    Returns:
        float: Ângulo em graus (-180 a 180)
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx))


def ponto_no_circulo(ponto, centro, raio):
    """
    Verifica se um ponto está dentro de um círculo.
    
    Returns:
        bool: True se o ponto está dentro do círculo
    """
    dx = ponto[0] - centro[0]
    dy = ponto[1] - centro[1]
    return dx*dx + dy*dy <= raio*raio


def mover_ponto_direcao(ponto, angulo_graus, distancia):
    """
    Move um ponto em uma direção.
    
    Args:
        ponto: Posição inicial (x, y)
        angulo_graus: Direção em graus
        distancia: Distância a mover
    
    Returns:
        tuple: Nova posição (x, y)
    """
    rad = math.radians(angulo_graus)
    return (
        ponto[0] + math.cos(rad) * distancia,
        ponto[1] + math.sin(rad) * distancia
    )
