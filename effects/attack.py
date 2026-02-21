"""
NEURAL FIGHTS - Sistema de Animações de Ataque v8.0 IMPACT EDITION
===================================================================

Sistema de efeitos visuais para ataques baseado na FORÇA do personagem.

Classes pesadas (Berserker, Cavaleiro, Guerreiro) têm ataques que:
- Deixam marcas/crateras na arena
- Tremem a tela proporcionalmente
- Criam ondas de choque visuais
- Têm trails de arma mais intensos

PRINCÍPIOS DE DESIGN:
- Força 5-10: Ataques leves (Magos, Ladinos)
- Força 10-15: Ataques médios (Guerreiros, Assassinos)
- Força 15-20: Ataques pesados (Gladiadores, Paladinos)
- Força 20+: Ataques COLOSSAIS (Berserkers, Cavaleiros grandes)

O impacto visual deve SEMPRE corresponder ao "peso" do ataque.
"""

import pygame
import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from enum import Enum, auto


# =============================================================================
# CONSTANTES DE IMPACTO BASEADAS EM FORÇA
# =============================================================================

# Multiplicadores de efeito por faixa de força
IMPACT_TIERS = {
    "light": {      # Força 0-8
        "shake_mult": 0.4,
        "crater_chance": 0.0,
        "trail_intensity": 0.5,
        "spark_count": 3,
        "shockwave_size": 0.3,
        "screen_flash": False,
        "ground_crack": False,
    },
    "medium": {     # Força 8-14
        "shake_mult": 0.8,
        "crater_chance": 0.1,
        "trail_intensity": 0.8,
        "spark_count": 8,
        "shockwave_size": 0.6,
        "screen_flash": False,
        "ground_crack": False,
    },
    "heavy": {      # Força 14-20
        "shake_mult": 1.2,
        "crater_chance": 0.4,
        "trail_intensity": 1.2,
        "spark_count": 15,
        "shockwave_size": 1.0,
        "screen_flash": True,
        "ground_crack": True,
    },
    "colossal": {   # Força 20+
        "shake_mult": 2.0,
        "crater_chance": 0.8,
        "trail_intensity": 1.8,
        "spark_count": 25,
        "shockwave_size": 1.5,
        "screen_flash": True,
        "ground_crack": True,
    },
}

# Cores de impacto por tipo de dano
IMPACT_COLORS = {
    "physical": [(255, 200, 100), (255, 150, 50), (255, 100, 0)],
    "fire": [(255, 100, 0), (255, 200, 50), (255, 50, 0)],
    "ice": [(150, 220, 255), (200, 240, 255), (100, 180, 255)],
    "lightning": [(255, 255, 150), (200, 200, 255), (255, 255, 255)],
    "dark": [(100, 0, 150), (150, 50, 200), (80, 0, 100)],
    "holy": [(255, 255, 200), (255, 220, 150), (255, 200, 100)],
}

# Configurações de trail de arma por classe
WEAPON_TRAIL_CONFIG = {
    "Berserker": {"cor": (255, 50, 50), "largura": 8, "duracao": 0.25, "brilho": True},
    "Guerreiro": {"cor": (255, 200, 100), "largura": 6, "duracao": 0.2, "brilho": False},
    "Cavaleiro": {"cor": (200, 200, 255), "largura": 7, "duracao": 0.22, "brilho": True},
    "Gladiador": {"cor": (255, 180, 100), "largura": 5, "duracao": 0.18, "brilho": False},
    "Paladino": {"cor": (255, 220, 100), "largura": 6, "duracao": 0.2, "brilho": True},
    "Assassino": {"cor": (150, 0, 150), "largura": 3, "duracao": 0.1, "brilho": False},
    "Ninja": {"cor": (100, 100, 100), "largura": 2, "duracao": 0.08, "brilho": False},
    "Ladino": {"cor": (80, 80, 80), "largura": 2, "duracao": 0.1, "brilho": False},
    "default": {"cor": (200, 200, 200), "largura": 4, "duracao": 0.15, "brilho": False},
}


def get_impact_tier(forca: float) -> dict:
    """Retorna o tier de impacto baseado na força"""
    if forca >= 20:
        return IMPACT_TIERS["colossal"]
    elif forca >= 14:
        return IMPACT_TIERS["heavy"]
    elif forca >= 8:
        return IMPACT_TIERS["medium"]
    else:
        return IMPACT_TIERS["light"]


def get_weapon_trail_config(classe: str) -> dict:
    """Retorna configuração de trail baseado na classe"""
    for key in WEAPON_TRAIL_CONFIG:
        if key in classe:
            return WEAPON_TRAIL_CONFIG[key]
    return WEAPON_TRAIL_CONFIG["default"]


# =============================================================================
# CRATER MARK - Marca de Cratera na Arena
# =============================================================================

@dataclass
class CraterMark:
    """Marca permanente de impacto no chão"""
    x: float
    y: float
    raio: float
    intensidade: float
    cor: Tuple[int, int, int]
    vida: float = 8.0  # Dura bastante
    max_vida: float = 8.0
    cracks: List[dict] = field(default_factory=list)
    
    def __post_init__(self):
        # Gera rachaduras radiais
        num_cracks = int(4 + self.intensidade * 3)
        for i in range(num_cracks):
            ang = (i / num_cracks) * math.pi * 2 + random.uniform(-0.3, 0.3)
            comp = self.raio * random.uniform(0.8, 1.5) * self.intensidade
            largura = random.uniform(1, 3)
            self.cracks.append({
                'angulo': ang,
                'comprimento': comp,
                'largura': largura,
                'deslocamento': random.uniform(0, 0.3)
            })
    
    def update(self, dt: float):
        self.vida -= dt * 0.5  # Fade lento
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0
    
    @property
    def alpha(self) -> int:
        # Fade suave nos últimos 2 segundos
        if self.vida > 2:
            return 180
        return int(180 * (self.vida / 2))


class GroundCrack:
    """
    Rachadura no chão que se propaga do ponto de impacto.
    Efeito dramático para ataques de força extrema.
    """
    
    def __init__(self, x: float, y: float, direcao: float, forca: float):
        self.x = x
        self.y = y
        self.direcao = direcao
        self.forca = forca
        self.vida = 5.0
        self.max_vida = 5.0
        
        # Comprimento máximo baseado na força
        self.comp_max = 50 + forca * 8
        self.comp_atual = 0
        self.velocidade_propagacao = 400 + forca * 30
        
        # Ramificações
        self.segmentos: List[dict] = []
        self._gerar_segmentos()
    
    def _gerar_segmentos(self):
        """Gera segmentos da rachadura"""
        # Segmento principal
        self.segmentos.append({
            'angulo': self.direcao,
            'comp': self.comp_max,
            'largura': 3 + self.forca * 0.2,
            'offset': 0,
            'filhos': []
        })
        
        # Ramificações (mais com mais força)
        num_ramos = int(2 + self.forca / 5)
        for _ in range(num_ramos):
            ang_offset = random.uniform(-0.8, 0.8)
            pos_inicio = random.uniform(0.2, 0.7)
            self.segmentos.append({
                'angulo': self.direcao + ang_offset,
                'comp': self.comp_max * random.uniform(0.3, 0.6),
                'largura': 2 + self.forca * 0.1,
                'offset': pos_inicio,
                'filhos': []
            })
    
    def update(self, dt: float):
        self.vida -= dt * 0.3
        
        # Propaga rachadura
        if self.comp_atual < self.comp_max:
            self.comp_atual += self.velocidade_propagacao * dt
            self.comp_atual = min(self.comp_atual, self.comp_max)
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0
    
    def draw(self, tela, cam, ppm: float):
        sx, sy = cam.converter(self.x, self.y)
        
        # Alpha baseado na vida
        alpha = int(200 * min(1.0, self.vida / 2))
        
        # Progresso da propagação
        prog = self.comp_atual / self.comp_max
        
        for seg in self.segmentos:
            if prog < seg['offset']:
                continue
            
            # Comprimento atual do segmento
            seg_prog = min(1.0, (prog - seg['offset']) / (1.0 - seg['offset']))
            comp = cam.converter_tam(seg['comp'] * seg_prog)
            
            if comp < 2:
                continue
            
            # Ponto final
            ex = sx + math.cos(seg['angulo']) * comp
            ey = sy + math.sin(seg['angulo']) * comp * 0.5  # Perspectiva
            
            # Desenha rachadura
            largura = max(1, int(seg['largura']))
            cor = (40, 30, 20, alpha)
            
            # Borda escura
            pygame.draw.line(tela, (20, 15, 10), (int(sx), int(sy)), (int(ex), int(ey)), largura + 2)
            # Centro
            pygame.draw.line(tela, (60, 50, 40), (int(sx), int(sy)), (int(ex), int(ey)), largura)


# =============================================================================
# WEAPON TRAIL - Rastro de Arma Melhorado
# =============================================================================

@dataclass
class TrailPoint:
    """Ponto do trail de arma"""
    x: float
    y: float
    tempo: float
    largura: float


class WeaponTrailEnhanced:
    """
    Trail de arma melhorado com intensidade baseada na força.
    
    Para classes pesadas: trail mais largo, mais brilhante, mais duradouro
    Para classes leves: trail fino e rápido
    """
    
    def __init__(self, lutador, config: dict):
        self.lutador = lutador
        self.config = config
        self.pontos: List[TrailPoint] = []
        self.max_pontos = 30
        self.ativo = True
        self.timer_sample = 0.0
        
        # Força afeta intensidade
        forca = lutador.dados.forca
        self.mult_forca = min(2.0, forca / 10.0)
    
    def add_point(self, x: float, y: float, largura: float = None):
        """Adiciona ponto ao trail"""
        if largura is None:
            largura = self.config['largura'] * self.mult_forca
        
        self.pontos.append(TrailPoint(x, y, self.config['duracao'], largura))
        
        # Limita quantidade
        if len(self.pontos) > self.max_pontos:
            self.pontos.pop(0)
    
    def update(self, dt: float):
        """Atualiza trail"""
        # Atualiza tempos
        for p in self.pontos:
            p.tempo -= dt
        
        # Remove pontos expirados
        self.pontos = [p for p in self.pontos if p.tempo > 0]
        
        # Desativa quando vazio
        if len(self.pontos) == 0:
            self.ativo = False
    
    def draw(self, tela, cam, ppm: float):
        if len(self.pontos) < 2:
            return
        
        cor = self.config['cor']
        brilho = self.config['brilho']
        
        # Desenha segmentos do trail
        for i in range(1, len(self.pontos)):
            p1 = self.pontos[i - 1]
            p2 = self.pontos[i]
            
            # Alpha baseado no tempo restante
            alpha1 = int(255 * (p1.tempo / self.config['duracao']))
            alpha2 = int(255 * (p2.tempo / self.config['duracao']))
            alpha = (alpha1 + alpha2) // 2
            
            if alpha < 10:
                continue
            
            sx1, sy1 = cam.converter(p1.x * ppm, p1.y * ppm)
            sx2, sy2 = cam.converter(p2.x * ppm, p2.y * ppm)
            
            largura = int((p1.largura + p2.largura) / 2)
            
            # Glow se configurado
            if brilho and largura > 2:
                glow_cor = (min(255, cor[0] + 50), min(255, cor[1] + 50), min(255, cor[2] + 50))
                pygame.draw.line(tela, glow_cor, (sx1, sy1), (sx2, sy2), largura + 4)
            
            # Trail principal
            pygame.draw.line(tela, cor, (sx1, sy1), (sx2, sy2), largura)
            
            # Core brilhante para trails largos
            if largura > 4:
                pygame.draw.line(tela, (255, 255, 255), (sx1, sy1), (sx2, sy2), max(1, largura // 3))


# =============================================================================
# IMPACT SHOCKWAVE - Onda de Choque de Impacto
# =============================================================================

class ImpactShockwave:
    """
    Onda de choque circular que se expande do ponto de impacto.
    Tamanho e intensidade baseados na força do golpe.
    """
    
    def __init__(self, x: float, y: float, forca: float, cor: Tuple[int, int, int] = None):
        self.x = x
        self.y = y
        self.forca = forca
        
        # Tier de impacto
        tier = get_impact_tier(forca)
        
        # Raio máximo baseado na força e tier
        self.raio_max = (30 + forca * 3) * tier['shockwave_size']
        self.raio = 5
        self.velocidade = 200 + forca * 15
        
        self.vida = 0.4
        self.max_vida = 0.4
        
        # Cor
        if cor is None:
            cor = random.choice(IMPACT_COLORS["physical"])
        self.cor = cor
        
        # Múltiplas ondas para impactos fortes
        self.ondas = [{'raio': 5, 'alpha': 255}]
        if forca >= 15:
            self.ondas.append({'raio': 0, 'alpha': 200})
        if forca >= 20:
            self.ondas.append({'raio': -5, 'alpha': 150})
    
    def update(self, dt: float):
        self.vida -= dt
        
        # Expande ondas
        for onda in self.ondas:
            onda['raio'] += self.velocidade * dt
            # Fade
            prog = 1.0 - (self.vida / self.max_vida)
            onda['alpha'] = int(255 * (1.0 - prog ** 0.5))
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0
    
    def draw(self, tela, cam, ppm: float):
        sx, sy = cam.converter(self.x, self.y)
        
        for onda in self.ondas:
            raio = cam.converter_tam(max(1, onda['raio']))
            alpha = max(0, min(255, onda['alpha']))
            
            if raio < 2 or alpha < 10:
                continue
            
            # Surface com alpha
            size = int(raio * 2 + 10)
            s = pygame.Surface((size, size), pygame.SRCALPHA)
            centro = (size // 2, size // 2)
            
            # Anel da onda
            cor_alpha = (self.cor[0], self.cor[1], self.cor[2], alpha)
            espessura = max(2, int(self.forca / 5))
            pygame.draw.circle(s, cor_alpha, centro, int(raio), espessura)
            
            # Glow interno
            if alpha > 50:
                glow_alpha = alpha // 3
                pygame.draw.circle(s, (*self.cor, glow_alpha), centro, int(raio * 0.8), espessura // 2)
            
            tela.blit(s, (int(sx - size // 2), int(sy - size // 2)))


# =============================================================================
# IMPACT SPARKS - Faíscas de Impacto
# =============================================================================

@dataclass
class Spark:
    """Faísca individual"""
    x: float
    y: float
    vx: float
    vy: float
    vida: float
    max_vida: float
    cor: Tuple[int, int, int]
    tamanho: float
    
    def update(self, dt: float):
        self.vida -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        # Gravidade leve
        self.vy += 200 * dt
        # Fricção
        self.vx *= 0.98
        self.vy *= 0.98
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0
    
    @property
    def alpha(self) -> int:
        return int(255 * (self.vida / self.max_vida))


class ImpactSparks:
    """
    Sistema de faíscas de impacto.
    Quantidade e intensidade baseadas na força.
    """
    
    def __init__(self, x: float, y: float, direcao: float, forca: float, 
                 tipo_dano: str = "physical"):
        self.x = x
        self.y = y
        self.sparks: List[Spark] = []
        
        # Tier de impacto
        tier = get_impact_tier(forca)
        cores = IMPACT_COLORS.get(tipo_dano, IMPACT_COLORS["physical"])
        
        # Quantidade de faíscas
        qtd = tier['spark_count']
        
        # Gera faíscas
        for _ in range(qtd):
            # Direção com spread
            ang = direcao + random.uniform(-0.8, 0.8)
            vel = random.uniform(100, 300) * (1.0 + forca / 20)
            
            vida = random.uniform(0.2, 0.5)
            
            self.sparks.append(Spark(
                x=x + random.uniform(-5, 5),
                y=y + random.uniform(-5, 5),
                vx=math.cos(ang) * vel,
                vy=math.sin(ang) * vel - random.uniform(50, 150),
                vida=vida,
                max_vida=vida,
                cor=random.choice(cores),
                tamanho=random.uniform(2, 5) * (1.0 + forca / 30)
            ))
    
    def update(self, dt: float):
        for spark in self.sparks:
            spark.update(dt)
        self.sparks = [s for s in self.sparks if s.ativo]
    
    @property
    def ativo(self) -> bool:
        return len(self.sparks) > 0
    
    def draw(self, tela, cam, ppm: float):
        for spark in self.sparks:
            sx, sy = cam.converter(spark.x, spark.y)
            tam = max(1, int(cam.converter_tam(spark.tamanho)))
            
            # Cor com alpha
            r = max(0, min(255, spark.cor[0]))
            g = max(0, min(255, spark.cor[1]))
            b = max(0, min(255, spark.cor[2]))
            alpha = max(0, min(255, spark.alpha))
            
            # Surface com alpha
            s = pygame.Surface((tam * 2 + 4, tam * 2 + 4), pygame.SRCALPHA)
            
            # Glow
            pygame.draw.circle(s, (r, g, b, alpha // 2), (tam + 2, tam + 2), tam + 1)
            # Core
            pygame.draw.circle(s, (min(255, r + 50), min(255, g + 50), min(255, b + 50), alpha), 
                             (tam + 2, tam + 2), tam)
            
            tela.blit(s, (int(sx - tam - 2), int(sy - tam - 2)))


# =============================================================================
# SCREEN FLASH - Flash de Tela
# =============================================================================

class ScreenFlash:
    """
    Flash de tela para impactos devastadores.
    Só ativa para força alta (tier heavy/colossal).
    """
    
    def __init__(self, forca: float, cor: Tuple[int, int, int] = (255, 255, 255)):
        self.vida = 0.1
        self.max_vida = 0.1
        self.cor = cor
        self.intensidade = min(150, 50 + forca * 3)
    
    def update(self, dt: float):
        self.vida -= dt
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0
    
    @property
    def alpha(self) -> int:
        prog = self.vida / self.max_vida
        return int(self.intensidade * prog)
    
    def draw(self, tela, largura: int, altura: int):
        alpha = self.alpha
        if alpha < 5:
            return
        
        s = pygame.Surface((largura, altura), pygame.SRCALPHA)
        s.fill((*self.cor, alpha))
        tela.blit(s, (0, 0))


# =============================================================================
# ANTICIPATION EFFECT - Efeito de Antecipação
# =============================================================================

class AttackAnticipation:
    """
    Efeito visual de "wind-up" antes de ataques pesados.
    Mostra ao jogador que um golpe forte está vindo.
    """
    
    def __init__(self, lutador, forca: float):
        self.lutador = lutador
        self.forca = forca
        self.vida = 0.15 + forca * 0.01
        self.max_vida = self.vida
        
        # Linhas de concentração de força
        self.linhas = []
        num_linhas = int(4 + forca / 5)
        for _ in range(num_linhas):
            self.linhas.append({
                'angulo': random.uniform(0, math.pi * 2),
                'dist_inicial': random.uniform(40, 80),
                'velocidade': random.uniform(150, 300),
            })
    
    def update(self, dt: float):
        self.vida -= dt
        
        # Linhas convergem para o personagem
        for linha in self.linhas:
            linha['dist_inicial'] -= linha['velocidade'] * dt
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0
    
    def draw(self, tela, cam, ppm: float):
        x, y = self.lutador.pos[0] * ppm, self.lutador.pos[1] * ppm
        sx, sy = cam.converter(x, y)
        
        alpha = int(200 * (self.vida / self.max_vida))
        
        # Cor baseada na força (mais vermelho = mais forte)
        red = min(255, 150 + int(self.forca * 5))
        cor = (red, 150, 100, alpha)
        
        for linha in self.linhas:
            dist = cam.converter_tam(max(5, linha['dist_inicial']))
            
            # Ponto externo
            ex = sx + math.cos(linha['angulo']) * dist
            ey = sy + math.sin(linha['angulo']) * dist
            
            # Desenha linha convergindo
            pygame.draw.line(tela, cor[:3], (int(ex), int(ey)), (int(sx), int(sy)), 2)


# =============================================================================
# ATTACK ANIMATION MANAGER - Gerenciador Principal
# =============================================================================

class AttackAnimationManager:
    """
    Gerenciador central de todas as animações de ataque.
    
    Coordena:
    - Weapon trails
    - Impact effects (shockwaves, sparks, craters)
    - Screen effects (flash, shake multipliers)
    - Ground marks (cracks, craters)
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def __init__(self):
        # Efeitos ativos
        self.weapon_trails: List[WeaponTrailEnhanced] = []
        self.shockwaves: List[ImpactShockwave] = []
        self.sparks: List[ImpactSparks] = []
        self.screen_flashes: List[ScreenFlash] = []
        self.anticipations: List[AttackAnticipation] = []
        self.ground_cracks: List[GroundCrack] = []
        
        # Marcas permanentes (crateras)
        self.crater_marks: List[CraterMark] = []
        
        # Limites
        self.MAX_TRAILS = 10
        self.MAX_SHOCKWAVES = 8
        self.MAX_SPARKS = 15
        self.MAX_CRATERS = 20
        self.MAX_CRACKS = 10
        
        # PPM
        self.ppm = 50
    
    def set_ppm(self, ppm: float):
        self.ppm = ppm
    
    def criar_attack_impact(self, atacante, alvo, dano: float, posicao: Tuple[float, float],
                           direcao: float, tipo_dano: str = "physical", is_critico: bool = False):
        """
        Cria todos os efeitos de impacto de um ataque.
        
        Args:
            atacante: Lutador que atacou
            alvo: Lutador que levou o golpe
            dano: Dano causado
            posicao: (x, y) do impacto em metros
            direcao: Direção do golpe em radianos
            tipo_dano: Tipo do dano para cores
            is_critico: Se foi crítico
        """
        forca = atacante.dados.forca
        tier = get_impact_tier(forca)
        
        # Posição em pixels
        px, py = posicao[0] * self.ppm, posicao[1] * self.ppm
        
        # Multiplicador de crítico
        crit_mult = 1.5 if is_critico else 1.0
        
        # === FAÍSCAS ===
        if len(self.sparks) < self.MAX_SPARKS:
            sparks = ImpactSparks(px, py, direcao, forca * crit_mult, tipo_dano)
            self.sparks.append(sparks)
        
        # === SHOCKWAVE ===
        if len(self.shockwaves) < self.MAX_SHOCKWAVES:
            cores = IMPACT_COLORS.get(tipo_dano, IMPACT_COLORS["physical"])
            wave = ImpactShockwave(px, py, forca * crit_mult, random.choice(cores))
            self.shockwaves.append(wave)
        
        # === SCREEN FLASH (só para ataques fortes) ===
        if tier['screen_flash'] and (is_critico or forca >= 18):
            cores = IMPACT_COLORS.get(tipo_dano, IMPACT_COLORS["physical"])
            flash = ScreenFlash(forca * crit_mult, random.choice(cores))
            self.screen_flashes.append(flash)
        
        # === CRATER / GROUND CRACK ===
        if random.random() < tier['crater_chance'] * crit_mult:
            if len(self.crater_marks) < self.MAX_CRATERS:
                raio = 15 + forca * 0.8
                crater = CraterMark(
                    x=px, y=py, 
                    raio=raio, 
                    intensidade=forca / 15,
                    cor=(80, 60, 40)
                )
                self.crater_marks.append(crater)
        
        if tier['ground_crack'] and forca >= 16:
            if len(self.ground_cracks) < self.MAX_CRACKS:
                crack = GroundCrack(px, py, direcao, forca)
                self.ground_cracks.append(crack)
        
        # Retorna dados para camera shake
        return {
            'shake_intensity': 5 + dano * 0.5 * tier['shake_mult'],
            'shake_duration': 0.1 + forca * 0.005,
            'zoom_punch': 0.05 + forca * 0.005 if forca >= 12 else 0,
        }
    
    def criar_weapon_trail(self, lutador) -> WeaponTrailEnhanced:
        """Cria um novo trail de arma para o lutador"""
        if len(self.weapon_trails) >= self.MAX_TRAILS:
            # Remove o mais antigo
            self.weapon_trails.pop(0)
        
        config = get_weapon_trail_config(lutador.dados.classe)
        trail = WeaponTrailEnhanced(lutador, config)
        self.weapon_trails.append(trail)
        return trail
    
    def criar_anticipation(self, lutador):
        """Cria efeito de antecipação para ataque pesado"""
        forca = lutador.dados.forca
        if forca < 12:  # Só para ataques pesados
            return None
        
        antic = AttackAnticipation(lutador, forca)
        self.anticipations.append(antic)
        return antic
    
    def calcular_knockback_forca(self, atacante, base_knockback: Tuple[float, float]) -> Tuple[float, float]:
        """
        Calcula knockback modificado pela força do atacante.
        
        Força 5: 0.5x knockback
        Força 10: 1.0x knockback
        Força 15: 1.5x knockback
        Força 20+: 2.0x+ knockback
        """
        forca = atacante.dados.forca
        
        # Multiplicador de knockback baseado na força
        # Escala de 0.5 (força 5) até 2.5 (força 25)
        mult = 0.3 + (forca / 10.0) * 0.7
        mult = max(0.5, min(2.5, mult))
        
        return (base_knockback[0] * mult, base_knockback[1] * mult)
    
    def update(self, dt: float):
        """Atualiza todos os efeitos"""
        # Trails
        for trail in self.weapon_trails:
            trail.update(dt)
        self.weapon_trails = [t for t in self.weapon_trails if t.ativo]
        
        # Shockwaves
        for wave in self.shockwaves:
            wave.update(dt)
        self.shockwaves = [w for w in self.shockwaves if w.ativo]
        
        # Sparks
        for spark in self.sparks:
            spark.update(dt)
        self.sparks = [s for s in self.sparks if s.ativo]
        
        # Screen flashes
        for flash in self.screen_flashes:
            flash.update(dt)
        self.screen_flashes = [f for f in self.screen_flashes if f.ativo]
        
        # Anticipations
        for antic in self.anticipations:
            antic.update(dt)
        self.anticipations = [a for a in self.anticipations if a.ativo]
        
        # Ground cracks
        for crack in self.ground_cracks:
            crack.update(dt)
        self.ground_cracks = [c for c in self.ground_cracks if c.ativo]
        
        # Craters (marcas persistentes)
        for crater in self.crater_marks:
            crater.update(dt)
        self.crater_marks = [c for c in self.crater_marks if c.ativo]
    
    def draw_ground(self, tela, cam):
        """Desenha efeitos no chão (antes dos personagens)"""
        # Crateras
        for crater in self.crater_marks:
            self._draw_crater(tela, cam, crater)
        
        # Rachaduras
        for crack in self.ground_cracks:
            crack.draw(tela, cam, self.ppm)
    
    def _draw_crater(self, tela, cam, crater: CraterMark):
        """Desenha uma cratera"""
        sx, sy = cam.converter(crater.x, crater.y)
        raio = int(cam.converter_tam(crater.raio))
        
        if raio < 3:
            return
        
        alpha = crater.alpha
        
        # Surface para a cratera
        size = raio * 2 + 20
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        centro = (size // 2, size // 2)
        
        # Sombra central (mais escura)
        pygame.draw.ellipse(s, (30, 25, 20, alpha), 
                          (centro[0] - raio, centro[1] - raio // 2, raio * 2, raio))
        
        # Borda elevada
        pygame.draw.ellipse(s, (60, 50, 40, alpha // 2), 
                          (centro[0] - raio - 3, centro[1] - raio // 2 - 2, raio * 2 + 6, raio + 4), 3)
        
        # Rachaduras radiais
        for crack in crater.cracks:
            comp = cam.converter_tam(crack['comprimento'])
            ex = centro[0] + math.cos(crack['angulo']) * comp
            ey = centro[1] + math.sin(crack['angulo']) * comp * 0.5
            pygame.draw.line(s, (40, 35, 30, alpha), centro, (int(ex), int(ey)), 
                           max(1, int(crack['largura'])))
        
        tela.blit(s, (int(sx - size // 2), int(sy - size // 2)))
    
    def draw_effects(self, tela, cam):
        """Desenha efeitos (depois dos personagens)"""
        # Shockwaves
        for wave in self.shockwaves:
            wave.draw(tela, cam, self.ppm)
        
        # Sparks
        for spark in self.sparks:
            spark.draw(tela, cam, self.ppm)
        
        # Anticipations
        for antic in self.anticipations:
            antic.draw(tela, cam, self.ppm)
        
        # Weapon trails
        for trail in self.weapon_trails:
            trail.draw(tela, cam, self.ppm)
    
    def draw_screen_effects(self, tela, largura: int, altura: int):
        """Desenha efeitos de tela (flash, etc)"""
        for flash in self.screen_flashes:
            flash.draw(tela, largura, altura)
    
    def clear(self):
        """Limpa todos os efeitos"""
        self.weapon_trails.clear()
        self.shockwaves.clear()
        self.sparks.clear()
        self.screen_flashes.clear()
        self.anticipations.clear()
        self.ground_cracks.clear()
        self.crater_marks.clear()


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================

def calcular_knockback_com_forca(atacante, alvo, direcao: float, dano: float) -> Tuple[float, float]:
    """
    Calcula vetor de knockback considerando força do atacante e massa do alvo.
    
    Fórmula: knockback = (forca_atacante * dano) / (massa_alvo + 5)
    
    Isso faz com que:
    - Atacantes fortes empurrem mais
    - Alvos pesados sejam empurrados menos
    - Dano maior = knockback maior
    """
    forca = atacante.dados.forca
    massa_alvo = alvo.dados.tamanho
    
    # Base do knockback
    base = (forca * 0.8 + dano * 0.3) / (massa_alvo + 5)
    
    # Escala para valores razoáveis (5-25 unidades)
    magnitude = max(5, min(25, base * 3))
    
    # Vetor
    kx = math.cos(direcao) * magnitude
    ky = math.sin(direcao) * magnitude
    
    return (kx, ky)
