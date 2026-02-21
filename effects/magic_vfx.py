"""
NEURAL FIGHTS - Efeitos Visuais de Magia v2.0 DRAMATIC EDITION
Sistema avançado de efeitos visuais para skills e magias.
Inclui:
- Partículas complexas com física
- Trilhas de energia
- Explosões dramáticas
- Auras pulsantes
- Efeitos de elemento (fogo, gelo, raio, etc)
"""

import pygame
import random
import math
from typing import List, Tuple, Optional
from utils.config import PPM


# =============================================================================
# CORES E PALETAS DE ELEMENTOS
# =============================================================================

ELEMENT_PALETTES = {
    "FOGO": {
        "core": (255, 255, 200),
        "mid": [(255, 180, 50), (255, 120, 0), (255, 80, 0)],
        "outer": [(255, 50, 0), (200, 30, 0), (150, 20, 0)],
        "spark": (255, 255, 100),
        "glow": (255, 100, 0, 100),
    },
    "GELO": {
        "core": (255, 255, 255),
        "mid": [(200, 240, 255), (150, 220, 255), (100, 200, 255)],
        "outer": [(80, 180, 255), (50, 150, 220), (30, 120, 200)],
        "spark": (220, 250, 255),
        "glow": (100, 200, 255, 100),
    },
    "RAIO": {
        "core": (255, 255, 255),
        "mid": [(255, 255, 150), (255, 255, 100), (200, 200, 255)],
        "outer": [(150, 150, 255), (100, 100, 255), (80, 80, 200)],
        "spark": (255, 255, 255),
        "glow": (150, 150, 255, 120),
    },
    "TREVAS": {
        "core": (150, 100, 200),
        "mid": [(100, 0, 150), (80, 0, 120), (60, 0, 100)],
        "outer": [(40, 0, 80), (30, 0, 60), (20, 0, 40)],
        "spark": (200, 150, 255),
        "glow": (100, 0, 150, 80),
    },
    "LUZ": {
        "core": (255, 255, 255),
        "mid": [(255, 255, 220), (255, 255, 180), (255, 240, 150)],
        "outer": [(255, 220, 100), (255, 200, 50), (255, 180, 0)],
        "spark": (255, 255, 255),
        "glow": (255, 255, 200, 150),
    },
    "NATUREZA": {
        "core": (200, 255, 200),
        "mid": [(100, 255, 100), (80, 220, 80), (60, 200, 60)],
        "outer": [(50, 180, 50), (40, 150, 40), (30, 120, 30)],
        "spark": (180, 255, 180),
        "glow": (100, 255, 100, 100),
    },
    "ARCANO": {
        "core": (255, 200, 255),
        "mid": [(220, 150, 255), (200, 100, 255), (180, 80, 255)],
        "outer": [(150, 50, 200), (120, 30, 180), (100, 20, 150)],
        "spark": (255, 200, 255),
        "glow": (200, 100, 255, 100),
    },
    "CAOS": {
        "core": (255, 255, 255),
        "mid": [(255, 100, 100), (100, 255, 100), (100, 100, 255)],
        "outer": [(255, 50, 200), (200, 50, 255), (50, 200, 255)],
        "spark": (255, 255, 255),
        "glow": (255, 100, 255, 100),
    },
    "SANGUE": {
        "core": (255, 200, 200),
        "mid": [(220, 50, 50), (200, 30, 30), (180, 20, 20)],
        "outer": [(150, 0, 0), (120, 0, 0), (100, 0, 0)],
        "spark": (255, 150, 150),
        "glow": (200, 0, 0, 100),
    },
    "VOID": {
        "core": (100, 50, 150),
        "mid": [(50, 0, 100), (30, 0, 80), (20, 0, 60)],
        "outer": [(10, 0, 40), (5, 0, 30), (0, 0, 20)],
        "spark": (150, 100, 200),
        "glow": (50, 0, 100, 80),
    },
    "DEFAULT": {
        "core": (255, 255, 255),
        "mid": [(200, 200, 200), (180, 180, 180), (150, 150, 150)],
        "outer": [(120, 120, 120), (100, 100, 100), (80, 80, 80)],
        "spark": (255, 255, 255),
        "glow": (200, 200, 200, 100),
    },
}


def get_element_from_skill(skill_nome: str, skill_data: dict) -> str:
    """Determina o elemento de uma skill pelo nome ou dados"""
    # Primeiro verifica se tem elemento definido
    if "elemento" in skill_data:
        return skill_data["elemento"]
    
    # Tenta detectar pelo nome
    nome_lower = skill_nome.lower()
    if any(w in nome_lower for w in ["fogo", "fire", "chama", "meteoro", "inferno", "brasas"]):
        return "FOGO"
    if any(w in nome_lower for w in ["gelo", "ice", "glacial", "nevasca", "congelar"]):
        return "GELO"
    if any(w in nome_lower for w in ["raio", "lightning", "thunder", "relâmpago", "elétric"]):
        return "RAIO"
    if any(w in nome_lower for w in ["trevas", "shadow", "dark", "sombr", "necro"]):
        return "TREVAS"
    if any(w in nome_lower for w in ["luz", "light", "holy", "sagrado", "divino", "celestial"]):
        return "LUZ"
    if any(w in nome_lower for w in ["natureza", "nature", "veneno", "poison", "planta", "espin"]):
        return "NATUREZA"
    if any(w in nome_lower for w in ["arcano", "arcane", "mana", "magia"]):
        return "ARCANO"
    if any(w in nome_lower for w in ["caos", "chaos", "random"]):
        return "CAOS"
    if any(w in nome_lower for w in ["sangue", "blood", "vampir"]):
        return "SANGUE"
    if any(w in nome_lower for w in ["void", "vazio", "tentáculo"]):
        return "VOID"
    
    return "DEFAULT"


# =============================================================================
# PARTÍCULAS AVANÇADAS
# =============================================================================

class MagicParticle:
    """Partícula mágica avançada com física e visual dramático"""
    def __init__(self, x: float, y: float, cor: Tuple[int, int, int],
                 vel_x: float = 0, vel_y: float = 0, 
                 tamanho: float = 5.0, vida: float = 1.0,
                 gravidade: float = 0, arrasto: float = 0.98,
                 pulsar: bool = False, trail: bool = False):
        self.x = x
        self.y = y
        self.cor = cor
        self.vel_x = vel_x
        self.vel_y = vel_y
        self.tamanho = tamanho
        self.tamanho_inicial = tamanho
        self.vida = vida
        self.vida_max = vida
        self.gravidade = gravidade
        self.arrasto = arrasto
        self.pulsar = pulsar
        self.pulse_timer = random.uniform(0, math.pi * 2)
        self.trail = trail
        self.trail_points = [] if trail else None
        self.rotacao = random.uniform(0, math.pi * 2)
        self.rot_vel = random.uniform(-5, 5)
    
    def update(self, dt: float) -> bool:
        """Atualiza partícula. Retorna False se morta."""
        self.vida -= dt
        if self.vida <= 0:
            return False
        
        # Física
        self.vel_y += self.gravidade * dt
        self.vel_x *= self.arrasto
        self.vel_y *= self.arrasto
        
        self.x += self.vel_x * dt
        self.y += self.vel_y * dt
        
        # Tamanho decai com vida
        vida_ratio = self.vida / self.vida_max
        self.tamanho = self.tamanho_inicial * vida_ratio
        
        # Pulso
        if self.pulsar:
            self.pulse_timer += dt * 10
            self.tamanho *= 0.8 + 0.4 * abs(math.sin(self.pulse_timer))
        
        # Rotação
        self.rotacao += self.rot_vel * dt
        
        # Trail
        if self.trail and self.trail_points is not None:
            self.trail_points.append((self.x, self.y))
            if len(self.trail_points) > 10:
                self.trail_points.pop(0)
        
        return True
    
    def draw(self, tela: pygame.Surface, cam):
        """Desenha a partícula"""
        sx, sy = cam.converter(self.x, self.y)
        tam = cam.converter_tam(self.tamanho)
        
        if tam < 1:
            return
        
        alpha = int(255 * (self.vida / self.vida_max))
        
        # Trail
        if self.trail and self.trail_points and len(self.trail_points) > 1:
            for i in range(1, len(self.trail_points)):
                t_alpha = int(alpha * (i / len(self.trail_points)) * 0.5)
                p1 = cam.converter(self.trail_points[i-1][0], self.trail_points[i-1][1])
                p2 = cam.converter(self.trail_points[i][0], self.trail_points[i][1])
                cor_trail = (*self.cor, t_alpha)
                # Desenha linha com alpha
                s = pygame.Surface((abs(p2[0]-p1[0])+4, abs(p2[1]-p1[1])+4), pygame.SRCALPHA)
                pygame.draw.line(s, cor_trail, (2, 2), (abs(p2[0]-p1[0])+2, abs(p2[1]-p1[1])+2), max(1, int(tam * 0.5)))
                tela.blit(s, (min(p1[0], p2[0])-2, min(p1[1], p2[1])-2))
        
        # Glow externo
        glow_size = int(tam * 2)
        if glow_size > 2:
            s = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.cor, alpha // 3), (glow_size, glow_size), glow_size)
            tela.blit(s, (sx - glow_size, sy - glow_size))
        
        # Partícula principal
        s = pygame.Surface((int(tam * 2) + 2, int(tam * 2) + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.cor, alpha), (int(tam) + 1, int(tam) + 1), int(tam))
        tela.blit(s, (sx - int(tam) - 1, sy - int(tam) - 1))


# =============================================================================
# EFEITOS DE MAGIA DRAMÁTICOS
# =============================================================================

class DramaticProjectileTrail:
    """Trail dramático para projéteis mágicos"""
    def __init__(self, elemento: str = "DEFAULT"):
        self.particulas: List[MagicParticle] = []
        self.palette = ELEMENT_PALETTES.get(elemento, ELEMENT_PALETTES["DEFAULT"])
        self.spawn_timer = 0
        self.elemento = elemento
    
    def update(self, dt: float, x: float, y: float, velocidade: float = 1.0):
        """Atualiza trail, spawna novas partículas"""
        self.spawn_timer += dt
        
        # Spawna partículas mais frequentemente para projéteis rápidos
        spawn_rate = 0.02 / max(0.5, velocidade)
        
        while self.spawn_timer > spawn_rate:
            self.spawn_timer -= spawn_rate
            
            # Partícula principal (core)
            cor = self.palette["core"]
            self.particulas.append(MagicParticle(
                x + random.uniform(-3, 3), y + random.uniform(-3, 3),
                cor, random.uniform(-20, 20), random.uniform(-20, 20),
                tamanho=8, vida=0.3, arrasto=0.95, pulsar=True
            ))
            
            # Partículas de cor média
            cor = random.choice(self.palette["mid"])
            self.particulas.append(MagicParticle(
                x + random.uniform(-8, 8), y + random.uniform(-8, 8),
                cor, random.uniform(-40, 40), random.uniform(-40, 40),
                tamanho=5, vida=0.4, arrasto=0.92
            ))
            
            # Partículas externas (mais dispersas)
            if random.random() < 0.5:
                cor = random.choice(self.palette["outer"])
                self.particulas.append(MagicParticle(
                    x + random.uniform(-12, 12), y + random.uniform(-12, 12),
                    cor, random.uniform(-60, 60), random.uniform(-60, 60),
                    tamanho=3, vida=0.5, arrasto=0.9
                ))
            
            # Faíscas (sparks)
            if random.random() < 0.3:
                cor = self.palette["spark"]
                ang = random.uniform(0, math.pi * 2)
                vel = random.uniform(50, 100)
                self.particulas.append(MagicParticle(
                    x, y, cor, math.cos(ang) * vel, math.sin(ang) * vel,
                    tamanho=2, vida=0.15, arrasto=0.85, trail=True
                ))
        
        # Atualiza partículas
        self.particulas = [p for p in self.particulas if p.update(dt)]
    
    def draw(self, tela: pygame.Surface, cam):
        """Desenha todas as partículas"""
        for p in self.particulas:
            p.draw(tela, cam)


class DramaticExplosion:
    """Explosão dramática com múltiplas camadas e física"""
    def __init__(self, x: float, y: float, elemento: str = "DEFAULT", 
                 tamanho: float = 1.0, dano: float = 0):
        self.x = x
        self.y = y
        self.tamanho = tamanho
        self.palette = ELEMENT_PALETTES.get(elemento, ELEMENT_PALETTES["DEFAULT"])
        self.elemento = elemento
        
        self.vida = 0.8
        self.vida_max = 0.8
        
        # Ondas de choque
        self.ondas = []
        for i in range(3):
            self.ondas.append({
                "raio": 0,
                "raio_max": (50 + i * 30) * tamanho,
                "delay": i * 0.05,
                "cor": random.choice(self.palette["mid"]),
                "largura": 5 - i
            })
        
        # Partículas
        self.particulas: List[MagicParticle] = []
        
        # Spawn inicial de partículas
        num_particulas = int(30 * tamanho + dano * 0.5)
        for _ in range(num_particulas):
            ang = random.uniform(0, math.pi * 2)
            vel = random.uniform(100, 300) * tamanho
            
            cor = random.choice(self.palette["mid"] + self.palette["outer"])
            grav = 50 if elemento != "RAIO" else 0
            
            self.particulas.append(MagicParticle(
                x, y, cor,
                math.cos(ang) * vel, math.sin(ang) * vel,
                tamanho=random.uniform(4, 10) * tamanho,
                vida=random.uniform(0.3, 0.6),
                gravidade=grav,
                arrasto=0.95,
                pulsar=random.random() < 0.3
            ))
        
        # Faíscas
        for _ in range(int(15 * tamanho)):
            ang = random.uniform(0, math.pi * 2)
            vel = random.uniform(150, 400) * tamanho
            self.particulas.append(MagicParticle(
                x, y, self.palette["spark"],
                math.cos(ang) * vel, math.sin(ang) * vel,
                tamanho=random.uniform(2, 4),
                vida=random.uniform(0.2, 0.4),
                arrasto=0.9,
                trail=True
            ))
        
        # Flash central
        self.flash_alpha = 255
        self.flash_raio = 30 * tamanho
    
    def update(self, dt: float) -> bool:
        """Atualiza explosão. Retorna False se terminada."""
        self.vida -= dt
        if self.vida <= 0:
            return False
        
        # Atualiza ondas
        for onda in self.ondas:
            if onda["delay"] > 0:
                onda["delay"] -= dt
            else:
                onda["raio"] += 600 * dt
        
        # Atualiza partículas
        self.particulas = [p for p in self.particulas if p.update(dt)]
        
        # Flash decai
        self.flash_alpha = max(0, self.flash_alpha - 800 * dt)
        self.flash_raio += 200 * dt
        
        return True
    
    def draw(self, tela: pygame.Surface, cam):
        """Desenha explosão"""
        sx, sy = cam.converter(self.x, self.y)
        
        # Flash central
        if self.flash_alpha > 0:
            flash_r = cam.converter_tam(self.flash_raio)
            if flash_r > 2:
                s = pygame.Surface((flash_r * 2, flash_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 255, 255, int(self.flash_alpha)), 
                                 (flash_r, flash_r), flash_r)
                tela.blit(s, (sx - flash_r, sy - flash_r))
        
        # Ondas de choque
        for onda in self.ondas:
            if onda["delay"] <= 0 and onda["raio"] > 0 and onda["raio"] < onda["raio_max"]:
                r = cam.converter_tam(onda["raio"])
                if r > 2:
                    prog = onda["raio"] / onda["raio_max"]
                    alpha = int(200 * (1 - prog))
                    largura = max(1, int(onda["largura"] * (1 - prog)))
                    
                    s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*onda["cor"], alpha), (r + 2, r + 2), r, largura)
                    tela.blit(s, (sx - r - 2, sy - r - 2))
        
        # Partículas
        for p in self.particulas:
            p.draw(tela, cam)


class DramaticBeam:
    """Beam dramático com efeitos elétricos e partículas"""
    def __init__(self, x1: float, y1: float, x2: float, y2: float,
                 elemento: str = "DEFAULT", largura: float = 8):
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2
        self.elemento = elemento
        self.palette = ELEMENT_PALETTES.get(elemento, ELEMENT_PALETTES["DEFAULT"])
        self.largura = largura
        
        self.vida = 0.5
        self.vida_max = 0.5
        
        # Segmentos zigzag
        self.segments = self._gerar_segments()
        
        # Partículas ao longo do beam
        self.particulas: List[MagicParticle] = []
        self._spawn_particles()
        
        # Pulso
        self.pulse_timer = 0
    
    def _gerar_segments(self) -> List[Tuple[float, float]]:
        """Gera segmentos zigzag para o beam"""
        segments = [(self.x1, self.y1)]
        
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        dist = math.hypot(dx, dy)
        
        if dist < 10:
            segments.append((self.x2, self.y2))
            return segments
        
        num_segments = max(3, int(dist / 20))
        perp_x = -dy / dist
        perp_y = dx / dist
        
        for i in range(1, num_segments):
            t = i / num_segments
            bx = self.x1 + dx * t
            by = self.y1 + dy * t
            
            # Offset perpendicular aleatório
            offset = random.uniform(-15, 15)
            bx += perp_x * offset
            by += perp_y * offset
            
            segments.append((bx, by))
        
        segments.append((self.x2, self.y2))
        return segments
    
    def _spawn_particles(self):
        """Spawna partículas ao longo do beam"""
        for i in range(len(self.segments) - 1):
            x1, y1 = self.segments[i]
            x2, y2 = self.segments[i + 1]
            
            # Partículas em cada segmento
            num = random.randint(2, 5)
            for j in range(num):
                t = random.random()
                px = x1 + (x2 - x1) * t
                py = y1 + (y2 - y1) * t
                
                cor = random.choice(self.palette["mid"])
                self.particulas.append(MagicParticle(
                    px + random.uniform(-5, 5),
                    py + random.uniform(-5, 5),
                    cor,
                    random.uniform(-30, 30),
                    random.uniform(-30, 30),
                    tamanho=random.uniform(3, 6),
                    vida=random.uniform(0.2, 0.4),
                    arrasto=0.9
                ))
    
    def update(self, dt: float) -> bool:
        """Atualiza beam"""
        self.vida -= dt
        if self.vida <= 0:
            return False
        
        self.pulse_timer += dt * 15
        
        # Regenera segments periodicamente para efeito elétrico
        if random.random() < dt * 10:
            self.segments = self._gerar_segments()
        
        # Atualiza partículas
        self.particulas = [p for p in self.particulas if p.update(dt)]
        
        # Spawna novas partículas
        if random.random() < dt * 20:
            idx = random.randint(0, len(self.segments) - 2)
            x1, y1 = self.segments[idx]
            x2, y2 = self.segments[idx + 1]
            t = random.random()
            px = x1 + (x2 - x1) * t
            py = y1 + (y2 - y1) * t
            
            cor = random.choice(self.palette["mid"])
            self.particulas.append(MagicParticle(
                px, py, cor,
                random.uniform(-50, 50), random.uniform(-50, 50),
                tamanho=random.uniform(3, 5),
                vida=0.3,
                arrasto=0.9
            ))
        
        return True
    
    def draw(self, tela: pygame.Surface, cam):
        """Desenha beam"""
        if len(self.segments) < 2:
            return
        
        # Converte segments para coordenadas de tela
        pts = [cam.converter(x, y) for x, y in self.segments]
        
        vida_ratio = self.vida / self.vida_max
        pulse = 0.7 + 0.3 * abs(math.sin(self.pulse_timer))
        
        # Glow externo (mais largo)
        glow_width = int((self.largura + 10) * pulse)
        glow_alpha = int(100 * vida_ratio)
        
        # Cria surface para glow
        min_x = min(p[0] for p in pts) - glow_width
        min_y = min(p[1] for p in pts) - glow_width
        max_x = max(p[0] for p in pts) + glow_width
        max_y = max(p[1] for p in pts) + glow_width
        
        w = int(max_x - min_x + 1)
        h = int(max_y - min_y + 1)
        
        if w > 0 and h > 0:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            
            # Ajusta pontos para surface local
            local_pts = [(p[0] - min_x, p[1] - min_y) for p in pts]
            
            # Glow externo
            cor_glow = (*self.palette["outer"][0], glow_alpha)
            pygame.draw.lines(s, cor_glow, False, local_pts, glow_width)
            
            # Beam colorido
            cor_mid = (*random.choice(self.palette["mid"]), int(200 * vida_ratio))
            pygame.draw.lines(s, cor_mid, False, local_pts, int(self.largura * pulse))
            
            # Core branco
            pygame.draw.lines(s, (255, 255, 255, int(255 * vida_ratio)), 
                            False, local_pts, max(1, int(self.largura * 0.3)))
            
            tela.blit(s, (min_x, min_y))
        
        # Partículas
        for p in self.particulas:
            p.draw(tela, cam)


class DramaticAura:
    """Aura dramática pulsante para buffs e transformações"""
    def __init__(self, x: float, y: float, raio: float, 
                 elemento: str = "DEFAULT", intensidade: float = 1.0):
        self.x = x
        self.y = y
        self.raio = raio
        self.elemento = elemento
        self.palette = ELEMENT_PALETTES.get(elemento, ELEMENT_PALETTES["DEFAULT"])
        self.intensidade = intensidade
        
        self.vida = 2.0
        self.vida_max = 2.0
        
        # Anéis
        self.aneis = []
        for i in range(3):
            self.aneis.append({
                "raio": raio * (0.5 + i * 0.3),
                "fase": random.uniform(0, math.pi * 2),
                "velocidade": random.uniform(2, 4),
                "cor": random.choice(self.palette["mid"])
            })
        
        # Partículas orbitantes
        self.particulas: List[MagicParticle] = []
        for _ in range(int(10 * intensidade)):
            ang = random.uniform(0, math.pi * 2)
            dist = random.uniform(raio * 0.5, raio * 1.2)
            self.particulas.append({
                "angulo": ang,
                "dist": dist,
                "vel_ang": random.uniform(1, 3) * random.choice([-1, 1]),
                "cor": random.choice(self.palette["mid"]),
                "tamanho": random.uniform(3, 6) * intensidade
            })
    
    def update(self, dt: float, x: float = None, y: float = None) -> bool:
        """Atualiza aura. Pode receber nova posição."""
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        
        self.vida -= dt
        if self.vida <= 0:
            return False
        
        # Atualiza anéis
        for anel in self.aneis:
            anel["fase"] += anel["velocidade"] * dt
        
        # Atualiza partículas orbitantes
        for p in self.particulas:
            p["angulo"] += p["vel_ang"] * dt
        
        return True
    
    def draw(self, tela: pygame.Surface, cam):
        """Desenha aura"""
        sx, sy = cam.converter(self.x, self.y)
        vida_ratio = self.vida / self.vida_max
        
        # Anéis pulsantes
        for anel in self.aneis:
            pulse = 0.8 + 0.2 * math.sin(anel["fase"])
            r = cam.converter_tam(anel["raio"] * pulse)
            
            if r > 2:
                alpha = int(150 * vida_ratio * pulse)
                s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(s, (*anel["cor"], alpha), (r + 2, r + 2), r, 2)
                tela.blit(s, (sx - r - 2, sy - r - 2))
        
        # Partículas orbitantes
        for p in self.particulas:
            px = self.x + math.cos(p["angulo"]) * p["dist"]
            py = self.y + math.sin(p["angulo"]) * p["dist"]
            
            spx, spy = cam.converter(px, py)
            tam = cam.converter_tam(p["tamanho"])
            
            if tam > 1:
                alpha = int(200 * vida_ratio)
                s = pygame.Surface((int(tam * 2) + 2, int(tam * 2) + 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*p["cor"], alpha), (int(tam) + 1, int(tam) + 1), int(tam))
                tela.blit(s, (spx - int(tam) - 1, spy - int(tam) - 1))


class DramaticSummon:
    """Efeito de invocação dramático"""
    def __init__(self, x: float, y: float, elemento: str = "DEFAULT"):
        self.x = x
        self.y = y
        self.elemento = elemento
        self.palette = ELEMENT_PALETTES.get(elemento, ELEMENT_PALETTES["DEFAULT"])
        
        self.vida = 1.5
        self.vida_max = 1.5
        
        # Círculo mágico
        self.circulo_raio = 0
        self.circulo_raio_max = 40
        self.circulo_rotacao = 0
        
        # Pilares de luz
        self.pilares = []
        for i in range(6):
            ang = i * (math.pi / 3)
            self.pilares.append({
                "angulo": ang,
                "altura": 0,
                "altura_max": random.uniform(60, 100),
                "delay": i * 0.1,
                "cor": random.choice(self.palette["mid"])
            })
        
        # Partículas ascendentes
        self.particulas: List[MagicParticle] = []
    
    def update(self, dt: float) -> bool:
        """Atualiza efeito de summon"""
        self.vida -= dt
        if self.vida <= 0:
            return False
        
        prog = 1 - (self.vida / self.vida_max)
        
        # Círculo expande
        if prog < 0.3:
            self.circulo_raio = self.circulo_raio_max * (prog / 0.3)
        
        self.circulo_rotacao += dt * 2
        
        # Pilares crescem
        for pilar in self.pilares:
            if pilar["delay"] > 0:
                pilar["delay"] -= dt
            else:
                if prog < 0.7:
                    pilar["altura"] = min(pilar["altura_max"], pilar["altura"] + 200 * dt)
        
        # Spawna partículas
        if random.random() < dt * 30:
            ang = random.uniform(0, math.pi * 2)
            dist = random.uniform(20, self.circulo_raio_max)
            px = self.x + math.cos(ang) * dist
            py = self.y + math.sin(ang) * dist
            
            cor = random.choice(self.palette["mid"])
            self.particulas.append(MagicParticle(
                px, py, cor,
                random.uniform(-10, 10), random.uniform(-100, -50),
                tamanho=random.uniform(3, 6),
                vida=0.5,
                arrasto=0.98
            ))
        
        # Atualiza partículas
        self.particulas = [p for p in self.particulas if p.update(dt)]
        
        return True
    
    def draw(self, tela: pygame.Surface, cam):
        """Desenha efeito de summon"""
        sx, sy = cam.converter(self.x, self.y)
        vida_ratio = self.vida / self.vida_max
        
        # Círculo mágico no chão
        r = cam.converter_tam(self.circulo_raio)
        if r > 2:
            # Círculo principal
            alpha = int(200 * vida_ratio)
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.palette["mid"][0], alpha), (r + 2, r + 2), r, 3)
            
            # Runas (linhas radiais)
            for i in range(12):
                ang = self.circulo_rotacao + i * (math.pi / 6)
                inner_r = r * 0.6
                outer_r = r
                x1 = r + 2 + math.cos(ang) * inner_r
                y1 = r + 2 + math.sin(ang) * inner_r
                x2 = r + 2 + math.cos(ang) * outer_r
                y2 = r + 2 + math.sin(ang) * outer_r
                pygame.draw.line(s, (*self.palette["spark"], alpha), 
                               (int(x1), int(y1)), (int(x2), int(y2)), 2)
            
            tela.blit(s, (sx - r - 2, sy - r - 2))
        
        # Pilares de luz
        for pilar in self.pilares:
            if pilar["delay"] <= 0 and pilar["altura"] > 0:
                px = self.x + math.cos(pilar["angulo"]) * self.circulo_raio * 0.8
                py = self.y + math.sin(pilar["angulo"]) * self.circulo_raio * 0.8
                
                spx, spy = cam.converter(px, py)
                h = cam.converter_tam(pilar["altura"])
                w = cam.converter_tam(5)
                
                if w > 1 and h > 1:
                    alpha = int(180 * vida_ratio)
                    s = pygame.Surface((int(w * 2), int(h)), pygame.SRCALPHA)
                    pygame.draw.rect(s, (*pilar["cor"], alpha), (0, 0, int(w * 2), int(h)))
                    # Gradiente (mais brilhante em cima)
                    pygame.draw.rect(s, (255, 255, 255, alpha // 2), (int(w * 0.5), 0, int(w), int(h)))
                    tela.blit(s, (spx - int(w), spy - int(h)))
        
        # Partículas
        for p in self.particulas:
            p.draw(tela, cam)


# =============================================================================
# GERENCIADOR DE EFEITOS
# =============================================================================

class MagicVFXManager:
    """Gerenciador central de todos os efeitos visuais de magia"""
    
    _instance = None
    
    def __init__(self):
        self.explosions: List[DramaticExplosion] = []
        self.beams: List[DramaticBeam] = []
        self.auras: List[DramaticAura] = []
        self.summons: List[DramaticSummon] = []
        self.trails: dict = {}  # {proj_id: DramaticProjectileTrail}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MagicVFXManager()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def spawn_explosion(self, x: float, y: float, elemento: str = "DEFAULT",
                       tamanho: float = 1.0, dano: float = 0):
        """Cria uma explosão dramática"""
        self.explosions.append(DramaticExplosion(x, y, elemento, tamanho, dano))
    
    def spawn_beam(self, x1: float, y1: float, x2: float, y2: float,
                  elemento: str = "DEFAULT", largura: float = 8):
        """Cria um beam dramático"""
        self.beams.append(DramaticBeam(x1, y1, x2, y2, elemento, largura))
    
    def spawn_aura(self, x: float, y: float, raio: float,
                  elemento: str = "DEFAULT", intensidade: float = 1.0):
        """Cria uma aura dramática"""
        self.auras.append(DramaticAura(x, y, raio, elemento, intensidade))
    
    def spawn_summon(self, x: float, y: float, elemento: str = "DEFAULT"):
        """Cria efeito de invocação"""
        self.summons.append(DramaticSummon(x, y, elemento))
    
    def get_or_create_trail(self, proj_id: int, elemento: str = "DEFAULT") -> DramaticProjectileTrail:
        """Obtém ou cria trail para um projétil"""
        if proj_id not in self.trails:
            self.trails[proj_id] = DramaticProjectileTrail(elemento)
        return self.trails[proj_id]
    
    def remove_trail(self, proj_id: int):
        """Remove trail de um projétil"""
        if proj_id in self.trails:
            del self.trails[proj_id]
    
    def update(self, dt: float):
        """Atualiza todos os efeitos"""
        self.explosions = [e for e in self.explosions if e.update(dt)]
        self.beams = [b for b in self.beams if b.update(dt)]
        self.auras = [a for a in self.auras if a.update(dt)]
        self.summons = [s for s in self.summons if s.update(dt)]
    
    def draw(self, tela: pygame.Surface, cam):
        """Desenha todos os efeitos"""
        # Trails primeiro (atrás)
        for trail in self.trails.values():
            trail.draw(tela, cam)
        
        # Efeitos de área
        for aura in self.auras:
            aura.draw(tela, cam)
        
        for summon in self.summons:
            summon.draw(tela, cam)
        
        # Beams
        for beam in self.beams:
            beam.draw(tela, cam)
        
        # Explosões por último (na frente)
        for explosion in self.explosions:
            explosion.draw(tela, cam)
