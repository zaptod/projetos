"""
NEURAL FIGHTS - Efeitos Visuais (UI)
Texto flutuante e manchas (decals)
"""

import pygame
from utils.config import PRETO


class FloatingText:
    """Texto flutuante para dano e notificações"""
    def __init__(self, x, y, texto, cor, tamanho=20):
        self.x = x
        self.y = y
        self.texto = str(int(texto)) if isinstance(texto, (int, float)) else texto
        self.cor = cor
        self.fonte = pygame.font.SysFont("Impact", tamanho)
        self.vel_y = -1.0
        self.vida = 1.0
        self.alpha = 255

    def update(self, dt):
        self.y += self.vel_y * dt * 60
        self.vel_y += 0.05 
        self.vida -= dt
        if self.vida < 0.5:
            self.alpha = int(255 * (self.vida / 0.5))

    def draw(self, tela, cam):
        if self.vida <= 0:
            return
        sx, sy = cam.converter(self.x, self.y)
        surf = self.fonte.render(self.texto, True, self.cor)
        surf.set_alpha(self.alpha)
        sombra = self.fonte.render(self.texto, True, PRETO)
        sombra.set_alpha(self.alpha)
        tela.blit(sombra, (sx+2, sy+2))
        tela.blit(surf, (sx, sy))


class Decal:
    """Manchas no chão (sangue, queimaduras, etc)"""
    def __init__(self, x, y, raio, cor):
        self.x = x
        self.y = y
        self.raio = raio
        self.cor = cor
        self.alpha = 200

    def draw(self, tela, cam):
        sx, sy = cam.converter(self.x, self.y)
        r = cam.converter_tam(self.raio)
        if r < 1:
            return
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.cor, self.alpha), (r, r), r)
        tela.blit(s, (sx-r, sy-r))
