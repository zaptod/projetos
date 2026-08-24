"""
NEURAL FIGHTS - Efeitos Visuais (UI)
Texto flutuante e manchas (decals)
"""

import pygame
from neural_fights.utils.config import PRETO


class FloatingText:
    """Texto flutuante para dano e notificações"""
    # Reforma "luta limpa": 3 degraus (eram 4 — em movimento os degraus
    # intermediários não se distinguiam). Os TIERS mandam no tamanho de
    # todo texto NUMÉRICO: o argumento `tamanho` dos call sites numéricos
    # era silenciosamente ignorado, então a hierarquia agora é oficial.
    TIERS = (
        (40, 18, None),              # leve: cor do chamador
        (110, 28, (255, 205, 90)),   # médio: âmbar
        (10**9, 40, (255, 80, 60)),  # pesado: vermelho
    )

    def __init__(self, x, y, texto, cor, tamanho=20):
        # Passe de arte 1: o NUMERO carrega o peso do golpe — tamanho e
        # cor escalam com o valor (um 13 sussurra, um 140 grita).
        self.x = x
        self.y = y
        numerico = isinstance(texto, (int, float))
        self.texto = str(int(texto)) if numerico else texto
        self.cor = cor
        if numerico:
            valor = abs(float(texto))
            for teto, tam, cor_tier in self.TIERS:
                if valor < teto:
                    tamanho = tam
                    if cor_tier is not None:
                        self.cor = cor_tier
                    break
        self.valor = float(texto) if numerico else None
        self.cor_base = cor
        from neural_fights.utils.fonts import get_fonte_impact
        self.fonte = get_fonte_impact(tamanho)  # cache (Passe 2)
        self.vel_y = -1.0
        self.vida = 1.0
        self.alpha = 255
        self.idade = 0.0

    def acumular(self, valor):
        """Soma no MESMO texto em vez de nascer outro (reforma "luta
        limpa"): ticks de canalização/DoT enchiam a tela a 10 textos/s.
        Reinicia a vida e re-resolve o tier pelo total."""
        if self.valor is None:
            return
        self.valor += float(valor)
        self.texto = str(int(self.valor))
        tamanho = 18
        self.cor = self.cor_base
        for teto, tam, cor_tier in self.TIERS:
            if abs(self.valor) < teto:
                tamanho = tam
                if cor_tier is not None:
                    self.cor = cor_tier
                break
        from neural_fights.utils.fonts import get_fonte_impact
        self.fonte = get_fonte_impact(tamanho)
        self.vida = max(self.vida, 0.75)
        self.idade = 0.0
        self.alpha = 255

    def update(self, dt):
        self.idade += dt
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
        contorno = self.fonte.render(self.texto, True, PRETO)
        # pop de entrada: nasce 35% maior e assenta em ~0,12s
        if self.idade < 0.12:
            fator = 1.35 - (self.idade / 0.12) * 0.35
            w, h = surf.get_size()
            surf = pygame.transform.smoothscale(surf, (int(w * fator), int(h * fator)))
            contorno = pygame.transform.smoothscale(contorno, (int(w * fator), int(h * fator)))
        surf.set_alpha(self.alpha)
        contorno.set_alpha(self.alpha)
        sx -= surf.get_width() // 2  # centrado no impacto
        # contorno em 4 direcoes + sombra: legivel sobre qualquer fundo
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
            tela.blit(contorno, (sx + dx, sy + dy))
        tela.blit(surf, (sx, sy))


class Decal:
    """Manchas no chão (sangue, queimaduras, etc)"""
    def __init__(self, x, y, raio, cor):
        self.x = x
        self.y = y
        self.raio = raio
        self.cor = cor
        self.alpha = 160
        # Reforma "luta limpa": decal FAZ FADE. O alpha era fixo em 200 e
        # a única poda era FIFO — 40 Surfaces desenhadas para sempre.
        self.vida = 6.0
        self.vida_max = 6.0

    def update(self, dt):
        self.vida -= dt
        if self.vida < 2.0:
            self.alpha = max(0, int(160 * (self.vida / 2.0)))
        return self.vida > 0

    def draw(self, tela, cam):
        if self.vida <= 0:
            return
        sx, sy = cam.converter(self.x, self.y)
        r = cam.converter_tam(self.raio)
        if r < 1:
            return
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.cor, self.alpha), (r, r), r)
        tela.blit(s, (sx-r, sy-r))
