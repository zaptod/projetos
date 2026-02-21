"""
NEURAL FIGHTS - Sistema de Partículas
Partículas, faíscas e efeitos de encantamento
"""

import pygame
import random
import math
from utils.config import PPM


# Cores dos encantamentos para partículas
CORES_ENCANTAMENTOS = {
    "Chamas": [(255, 100, 0), (255, 200, 50), (255, 50, 0)],
    "Gelo": [(100, 200, 255), (200, 230, 255), (150, 220, 255)],
    "Relâmpago": [(255, 255, 100), (200, 200, 255), (255, 255, 255)],
    "Veneno": [(100, 255, 100), (50, 200, 50), (150, 255, 100)],
    "Trevas": [(100, 0, 150), (50, 0, 100), (150, 50, 200)],
    "Sagrado": [(255, 255, 200), (255, 215, 0), (255, 255, 255)],
    "Velocidade": [(200, 200, 255), (150, 150, 255), (255, 255, 255)],
    "Vampirismo": [(200, 0, 0), (150, 0, 50), (255, 50, 50)],
    "Crítico": [(255, 50, 50), (255, 100, 100), (255, 0, 0)],
    "Penetração": [(150, 150, 150), (200, 200, 200), (100, 100, 100)],
    "Execução": [(50, 0, 0), (100, 0, 0), (150, 0, 0)],
    "Espelhamento": [(150, 200, 255), (200, 230, 255), (100, 150, 255)],
}


class Particula:
    """Partícula básica para efeitos visuais"""
    def __init__(self, x, y, cor, vel_x, vel_y, tamanho, vida_util=1.0):
        self.x, self.y = x, y
        self.cor = cor
        self.vel_x, self.vel_y = vel_x, vel_y
        self.tamanho = tamanho
        self.vida = vida_util

    def atualizar(self, dt):
        self.x += self.vel_x * dt
        self.y += self.vel_y * dt
        self.vida -= dt
        self.tamanho *= 0.92


class HitSpark:
    """Faíscas estilizadas de impacto"""
    def __init__(self, x, y, cor, direcao, intensidade=1.0):
        self.x = x
        self.y = y
        self.cor = cor
        self.vida = 0.2
        self.max_vida = 0.2
        self.sparks = []
        
        for _ in range(int(12 * intensidade)):
            ang = direcao + random.uniform(-0.8, 0.8)
            vel = random.uniform(80, 200) * intensidade
            self.sparks.append({
                'x': x, 'y': y,
                'vx': math.cos(ang) * vel,
                'vy': math.sin(ang) * vel,
                'comprimento': random.uniform(8, 20) * intensidade,
                'vida': random.uniform(0.1, 0.2)
            })
    
    def update(self, dt):
        self.vida -= dt
        for s in self.sparks:
            s['x'] += s['vx'] * dt
            s['y'] += s['vy'] * dt
            s['vida'] -= dt
            s['comprimento'] *= 0.9
        self.sparks = [s for s in self.sparks if s['vida'] > 0]
    
    def draw(self, tela, cam):
        for s in self.sparks:
            if s['vida'] <= 0:
                continue
            sx, sy = cam.converter(s['x'], s['y'])
            alpha = int(255 * (s['vida'] / 0.2))
            
            ang = math.atan2(s['vy'], s['vx'])
            comp = cam.converter_tam(s['comprimento'])
            ex = sx + math.cos(ang) * comp
            ey = sy + math.sin(ang) * comp
            
            pygame.draw.line(tela, (255, 255, 255), (sx, sy), (int(ex), int(ey)), 2)
            pygame.draw.line(tela, self.cor, (sx, sy), (int(ex), int(ey)), 3)


class Shockwave:
    """Onda de choque"""
    def __init__(self, x, y, cor, tamanho=1.0):
        self.x = x
        self.y = y
        self.raio = 10.0 * tamanho
        self.cor = cor
        self.vida = 0.3
        self.max_vida = 0.3

    def update(self, dt):
        self.vida -= dt
        self.raio += 500 * dt

    def draw(self, tela, cam):
        if self.vida <= 0:
            return
        sx, sy = cam.converter(self.x, self.y)
        r = cam.converter_tam(self.raio)
        width = int(5 * (self.vida / self.max_vida))
        if width < 1:
            width = 1
        pygame.draw.circle(tela, self.cor, (sx, sy), r, width)


class EncantamentoEffect:
    """Efeito visual de encantamento na arma"""
    def __init__(self, encantamento, pos_func):
        self.encantamento = encantamento
        self.pos_func = pos_func
        self.particulas = []
        self.cores = CORES_ENCANTAMENTOS.get(encantamento, [(255, 255, 255)])
        self.timer = 0
        
    def update(self, dt):
        self.timer += dt
        
        if self.timer > 0.05:
            self.timer = 0
            pos = self.pos_func()
            if pos:
                x, y = pos
                cor = random.choice(self.cores)
                vel_x = random.uniform(-30, 30)
                vel_y = random.uniform(-30, 30)
                
                if self.encantamento == "Chamas":
                    vel_y = random.uniform(-80, -30)
                elif self.encantamento == "Gelo":
                    vel_y = random.uniform(10, 40)
                elif self.encantamento == "Relâmpago":
                    vel_x = random.uniform(-100, 100)
                    vel_y = random.uniform(-100, 100)
                elif self.encantamento == "Trevas":
                    vel_x = random.uniform(-10, 10)
                    vel_y = random.uniform(-10, 10)
                    
                self.particulas.append(Particula(x, y, cor, vel_x, vel_y, 3, 0.5))
        
        for p in self.particulas[:]:
            p.atualizar(dt)
            if p.vida <= 0:
                self.particulas.remove(p)
                
    def draw(self, tela, cam):
        for p in self.particulas:
            sx, sy = cam.converter(p.x, p.y)
            tam = cam.converter_tam(p.tamanho)
            if tam > 0:
                pygame.draw.circle(tela, p.cor, (sx, sy), max(1, tam))
