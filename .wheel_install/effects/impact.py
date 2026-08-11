"""
NEURAL FIGHTS - Efeitos de Impacto
Flashes, colisões mágicas, bloqueios e trails
"""

import pygame
import random
import math


class ImpactFlash:
    """Flash de impacto quando projéteis/ataques colidem"""
    def __init__(self, x, y, cor, tamanho=1.0, tipo="normal"):
        self.x = x
        self.y = y
        self.cor = cor
        self.tamanho_base = 30 * tamanho
        self.tamanho = self.tamanho_base
        self.vida = 0.15
        self.max_vida = 0.15
        self.tipo = tipo
        self.raios = []
        
        if tipo == "magic":
            for i in range(8):
                ang = random.uniform(0, math.pi * 2)
                comp = random.uniform(20, 50) * tamanho
                self.raios.append((ang, comp))
        elif tipo == "clash":
            for i in range(12):
                ang = i * (math.pi * 2 / 12)
                comp = random.uniform(30, 60) * tamanho
                self.raios.append((ang, comp))
    
    def update(self, dt):
        self.vida -= dt
        prog = 1.0 - (self.vida / self.max_vida)
        if prog < 0.3:
            self.tamanho = self.tamanho_base * (prog / 0.3)
        else:
            self.tamanho = self.tamanho_base * (1.0 - (prog - 0.3) / 0.7)
    
    def draw(self, tela, cam):
        if self.vida <= 0:
            return
        sx, sy = cam.converter(self.x, self.y)
        alpha = int(255 * (self.vida / self.max_vida))
        tam = cam.converter_tam(self.tamanho)
        
        if tam < 2:
            return
        
        s = pygame.Surface((tam * 4, tam * 4), pygame.SRCALPHA)
        centro = (tam * 2, tam * 2)
        
        cor_glow = (*self.cor[:3], alpha // 2)
        pygame.draw.circle(s, cor_glow, centro, tam * 2)
        
        cor_core = (*self.cor[:3], alpha)
        pygame.draw.circle(s, cor_core, centro, tam)
        
        pygame.draw.circle(s, (255, 255, 255, alpha), centro, max(2, tam // 2))
        
        for ang, comp in self.raios:
            comp_atual = comp * (self.vida / self.max_vida) * cam.zoom
            ex = centro[0] + math.cos(ang) * comp_atual
            ey = centro[1] + math.sin(ang) * comp_atual
            pygame.draw.line(s, cor_core, centro, (int(ex), int(ey)), max(1, tam // 5))
        
        self.tela = tela
        tela.blit(s, (sx - tam * 2, sy - tam * 2))


class MagicClash:
    """Efeito de colisão entre magias"""
    def __init__(self, x, y, cor1, cor2, tamanho=1.0):
        self.x = x
        self.y = y
        self.cor1 = cor1
        self.cor2 = cor2
        self.tamanho = tamanho
        self.vida = 0.5
        self.max_vida = 0.5
        self.particulas = []
        self.ondas = []
        
        for _ in range(25):
            ang = random.uniform(0, math.pi * 2)
            vel = random.uniform(100, 300) * tamanho
            cor = random.choice([cor1, cor2])
            self.particulas.append({
                'x': x, 'y': y,
                'vx': math.cos(ang) * vel,
                'vy': math.sin(ang) * vel,
                'cor': cor,
                'tam': random.uniform(3, 8) * tamanho,
                'vida': random.uniform(0.3, 0.5)
            })
        
        for i in range(3):
            self.ondas.append({
                'raio': 0,
                'cor': cor1 if i % 2 == 0 else cor2,
                'delay': i * 0.08
            })
    
    def update(self, dt):
        self.vida -= dt
        
        for p in self.particulas:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vx'] *= 0.95
            p['vy'] *= 0.95
            p['vida'] -= dt
            p['tam'] *= 0.97
        
        self.particulas = [p for p in self.particulas if p['vida'] > 0]
        
        for onda in self.ondas:
            if onda['delay'] > 0:
                onda['delay'] -= dt
            else:
                onda['raio'] += 400 * dt
    
    def draw(self, tela, cam):
        if self.vida <= 0:
            return
        
        sx, sy = cam.converter(self.x, self.y)
        alpha_base = int(255 * (self.vida / self.max_vida))
        
        for onda in self.ondas:
            if onda['delay'] <= 0 and onda['raio'] > 0:
                r = cam.converter_tam(onda['raio'])
                if r > 0:
                    alpha = int(alpha_base * max(0, 1.0 - onda['raio'] / 150))
                    width = max(1, int(5 * (1.0 - onda['raio'] / 150)))
                    s = pygame.Surface((r * 2 + 10, r * 2 + 10), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*onda['cor'][:3], alpha), (r + 5, r + 5), r, width)
                    tela.blit(s, (sx - r - 5, sy - r - 5))
        
        for p in self.particulas:
            px, py = cam.converter(p['x'], p['y'])
            tam = cam.converter_tam(p['tam'])
            if tam > 0:
                alpha = int(255 * (p['vida'] / 0.5))
                s = pygame.Surface((tam * 2 + 2, tam * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*p['cor'][:3], alpha), (tam + 1, tam + 1), max(1, tam))
                tela.blit(s, (px - tam - 1, py - tam - 1))
        
        if self.vida > 0.3:
            core_tam = cam.converter_tam(20 * self.tamanho * (self.vida / self.max_vida))
            if core_tam > 2:
                s = pygame.Surface((core_tam * 2, core_tam * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 255, 255, alpha_base), (core_tam, core_tam), core_tam)
                tela.blit(s, (sx - core_tam, sy - core_tam))


class BlockEffect:
    """Efeito visual de bloqueio"""
    def __init__(self, x, y, cor_bloqueador, angulo):
        self.x = x
        self.y = y
        self.cor = cor_bloqueador
        self.angulo = angulo
        self.vida = 0.25
        self.max_vida = 0.25
        self.faiscas = []
        
        for _ in range(15):
            ang = angulo + random.uniform(-0.5, 0.5)
            vel = random.uniform(50, 150)
            self.faiscas.append({
                'x': x, 'y': y,
                'vx': math.cos(ang) * vel,
                'vy': math.sin(ang) * vel,
                'vida': random.uniform(0.15, 0.3)
            })
    
    def update(self, dt):
        self.vida -= dt
        for f in self.faiscas:
            f['x'] += f['vx'] * dt
            f['y'] += f['vy'] * dt
            f['vy'] += 200 * dt
            f['vida'] -= dt
        self.faiscas = [f for f in self.faiscas if f['vida'] > 0]
    
    def draw(self, tela, cam):
        if self.vida <= 0:
            return
        
        sx, sy = cam.converter(self.x, self.y)
        alpha = int(255 * (self.vida / self.max_vida))
        
        tam = cam.converter_tam(40)
        if tam > 2:
            s = pygame.Surface((tam * 2, tam * 2), pygame.SRCALPHA)
            rect = pygame.Rect(0, 0, tam * 2, tam * 2)
            ang_start = math.degrees(self.angulo) - 45
            ang_end = math.degrees(self.angulo) + 45
            pygame.draw.arc(s, (*self.cor[:3], alpha), rect, 
                           math.radians(ang_start), math.radians(ang_end), max(3, tam // 4))
            tela.blit(s, (sx - tam, sy - tam))
        
        for f in self.faiscas:
            fx, fy = cam.converter(f['x'], f['y'])
            alpha_f = int(255 * (f['vida'] / 0.3))
            pygame.draw.circle(tela, (255, 255, 150, alpha_f), (int(fx), int(fy)), 2)


class DashTrail:
    """Trail visual para dash evasivo"""
    def __init__(self, posicoes, cor):
        self.posicoes = posicoes
        self.cor = cor
        self.vida = 0.3
        self.max_vida = 0.3
    
    def update(self, dt):
        self.vida -= dt
    
    def draw(self, tela, cam):
        if self.vida <= 0 or len(self.posicoes) < 2:
            return
        
        alpha = int(200 * (self.vida / self.max_vida))
        
        for i in range(1, len(self.posicoes)):
            seg_alpha = int(alpha * (i / len(self.posicoes)))
            p1 = cam.converter(self.posicoes[i-1][0], self.posicoes[i-1][1])
            p2 = cam.converter(self.posicoes[i][0], self.posicoes[i][1])
            
            s = pygame.Surface((abs(p2[0] - p1[0]) + 20, abs(p2[1] - p1[1]) + 20), pygame.SRCALPHA)
            offset = (min(p1[0], p2[0]) - 10, min(p1[1], p2[1]) - 10)
            pygame.draw.line(s, (*self.cor[:3], seg_alpha), 
                           (p1[0] - offset[0], p1[1] - offset[1]),
                           (p2[0] - offset[0], p2[1] - offset[1]), 4)
            tela.blit(s, offset)
