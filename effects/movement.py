"""
NEURAL FIGHTS - Sistema de Animação de Movimento v8.0
=====================================================

Sistema completo de efeitos visuais para movimentação, incluindo:
- Dash com afterimages e distorção
- Knockback com motion blur e impacto
- Landing com squash/stretch e poeira
- Movimento com dust trails e aura de velocidade
- Recuperação de stagger com efeito de tensão

Filosofia de Design:
- Movimento ATIVO (dash, pulos): Efeitos de PODER e CONTROLE
- Movimento REATIVO (knockback, stagger): Efeitos de IMPACTO e PESO
- Antecipação e Follow-through para cada ação
"""

import pygame
import random
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable
from enum import Enum, auto


# =============================================================================
# CONSTANTES DE ANIMAÇÃO
# =============================================================================

# Cores padrão para efeitos
DUST_COLORS = [(180, 160, 140), (160, 140, 120), (200, 180, 160)]
SPEED_COLORS = [(200, 220, 255), (180, 200, 255), (220, 235, 255)]
IMPACT_COLORS = [(255, 200, 150), (255, 180, 130), (255, 220, 180)]

# Configuração de afterimages por classe
AFTERIMAGE_CONFIG = {
    "fast": {  # Ninjas, Assassinos
        "quantidade": 6,
        "intervalo": 0.02,
        "fade_rate": 0.15,
        "escala_final": 0.8,
        "cor_tint": (100, 150, 255),  # Azulado
    },
    "heavy": {  # Berserkers, Guerreiros
        "quantidade": 3,
        "intervalo": 0.04,
        "fade_rate": 0.2,
        "escala_final": 1.1,  # Ligeiramente maior (impacto)
        "cor_tint": (255, 150, 100),  # Alaranjado
    },
    "magic": {  # Magos
        "quantidade": 4,
        "intervalo": 0.03,
        "fade_rate": 0.12,
        "escala_final": 1.2,
        "cor_tint": (150, 100, 255),  # Roxo
    },
    "default": {
        "quantidade": 4,
        "intervalo": 0.03,
        "fade_rate": 0.18,
        "escala_final": 0.9,
        "cor_tint": (200, 200, 200),
    }
}


# =============================================================================
# ENUMS
# =============================================================================

class MovementType(Enum):
    """Tipos de movimento para seleção de efeito apropriado"""
    DASH_FORWARD = auto()    # Dash ofensivo
    DASH_BACKWARD = auto()   # Dash evasivo
    DASH_LATERAL = auto()    # Dash lateral (strafe)
    KNOCKBACK = auto()       # Empurrado por golpe
    LAUNCH = auto()          # Lançado para o ar
    LANDING = auto()         # Aterrissagem
    STAGGER = auto()         # Cambaleando
    RECOVERY = auto()        # Se recuperando
    SPRINT = auto()          # Corrida rápida
    JUMP = auto()            # Pulo


# =============================================================================
# AFTERIMAGE - Imagem Fantasma (Ghost Trail)
# =============================================================================

@dataclass
class AfterImage:
    """Uma única afterimage do personagem"""
    x: float
    y: float
    z: float  # Altura (para pulos)
    angulo: float
    escala: float
    cor: Tuple[int, int, int]
    cor_tint: Tuple[int, int, int]
    alpha: float = 255.0
    vida: float = 0.3
    max_vida: float = 0.3
    tamanho_base: float = 1.0
    
    def update(self, dt: float, fade_rate: float = 0.18):
        """Atualiza a afterimage"""
        self.vida -= dt
        # Fade não-linear para efeito mais interessante
        # Clamp prog para evitar números complexos com potência fracionária
        prog = max(0.0, min(1.0, 1.0 - (self.vida / self.max_vida)))
        self.alpha = 255 * (1.0 - prog ** 1.5)  # Curva de fade
        self.escala *= (1.0 - fade_rate * dt * 3)
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0 and self.alpha > 5


class AfterImageTrail:
    """
    Sistema de trail de afterimages para dash/movimento rápido.
    
    Cria múltiplas "cópias fantasma" do personagem que fade out,
    dando sensação de velocidade e fluidez.
    """
    
    def __init__(self, lutador, movimento_tipo: MovementType, cor_personagem: tuple):
        self.lutador = lutador
        self.movimento_tipo = movimento_tipo
        self.cor_base = cor_personagem
        
        # Determina configuração baseado na classe
        self.config = self._get_config_por_classe()
        
        self.images: List[AfterImage] = []
        self.timer_spawn = 0.0
        self.ativo = True
        self.vida = 0.5  # Duração total do trail
        
        # Spawn inicial
        self._spawn_image()
    
    def _get_config_por_classe(self) -> dict:
        """Retorna configuração de afterimage baseado na classe"""
        classe = getattr(self.lutador, 'classe_nome', "")
        
        if any(c in classe for c in ["Ninja", "Assassino", "Ladino"]):
            return AFTERIMAGE_CONFIG["fast"]
        elif any(c in classe for c in ["Berserker", "Guerreiro", "Cavaleiro", "Gladiador"]):
            return AFTERIMAGE_CONFIG["heavy"]
        elif any(c in classe for c in ["Mago", "Piromante", "Criomante", "Necromante", "Feiticeiro"]):
            return AFTERIMAGE_CONFIG["magic"]
        else:
            return AFTERIMAGE_CONFIG["default"]
    
    def _spawn_image(self):
        """Cria uma nova afterimage na posição atual"""
        if not self.ativo:
            return
        
        # Variação de cor baseada no tint da classe
        tint = self.config["cor_tint"]
        cor_misturada = (
            int(self.cor_base[0] * 0.6 + tint[0] * 0.4),
            int(self.cor_base[1] * 0.6 + tint[1] * 0.4),
            int(self.cor_base[2] * 0.6 + tint[2] * 0.4),
        )
        
        img = AfterImage(
            x=self.lutador.pos[0],
            y=self.lutador.pos[1],
            z=getattr(self.lutador, 'z', 0),
            angulo=self.lutador.angulo_olhar,
            escala=1.0,
            cor=self.cor_base,
            cor_tint=cor_misturada,
            tamanho_base=self.lutador.dados.tamanho,
            max_vida=0.2 + len(self.images) * 0.02  # Images mais antigas duram mais
        )
        self.images.append(img)
    
    def update(self, dt: float):
        """Atualiza o trail"""
        self.vida -= dt
        
        # Spawn novas images enquanto ativo
        if self.ativo and self.vida > 0.1:
            self.timer_spawn += dt
            if self.timer_spawn >= self.config["intervalo"]:
                self.timer_spawn = 0
                if len(self.images) < self.config["quantidade"]:
                    self._spawn_image()
        
        # Atualiza images existentes
        for img in self.images:
            img.update(dt, self.config["fade_rate"])
        
        # Remove images mortas
        self.images = [img for img in self.images if img.ativo]
        
        # Desativa quando não há mais images
        if self.vida <= 0 and not self.images:
            self.ativo = False
    
    def draw(self, tela, cam, ppm: float):
        """Desenha todas as afterimages"""
        for img in self.images:
            if not img.ativo:
                continue
            
            # Converte para coordenadas de tela
            sx, sy = cam.converter(img.x * ppm, img.y * ppm)
            
            # Aplica offset de altura (Z)
            sy -= int(img.z * ppm * 0.5)
            
            # Tamanho com escala
            tam = int(cam.converter_tam(img.tamanho_base * ppm * 0.5 * img.escala))
            if tam < 2:
                continue
            
            # Garante valores de cor válidos
            r = max(0, min(255, int(img.cor_tint[0])))
            g = max(0, min(255, int(img.cor_tint[1])))
            b = max(0, min(255, int(img.cor_tint[2])))
            
            r2 = max(0, min(255, int(img.cor[0])))
            g2 = max(0, min(255, int(img.cor[1])))
            b2 = max(0, min(255, int(img.cor[2])))
            
            # Desenha círculo com alpha
            s = pygame.Surface((tam * 2 + 4, tam * 2 + 4), pygame.SRCALPHA)
            
            # Glow externo
            glow_alpha = max(0, min(255, int(img.alpha * 0.3)))
            pygame.draw.circle(s, (r, g, b, glow_alpha), (tam + 2, tam + 2), tam + 2)
            
            # Corpo principal
            main_alpha = max(0, min(255, int(img.alpha * 0.7)))
            pygame.draw.circle(s, (r, g, b, main_alpha), (tam + 2, tam + 2), tam)
            
            # Centro mais brilhante
            if tam > 4:
                center_alpha = max(0, min(255, int(img.alpha * 0.5)))
                pygame.draw.circle(s, (r2, g2, b2, center_alpha), (tam + 2, tam + 2), tam // 2)
            
            tela.blit(s, (sx - tam - 2, sy - tam - 2))


# =============================================================================
# DUST PARTICLES - Partículas de Poeira
# =============================================================================

@dataclass
class DustParticle:
    """Partícula individual de poeira"""
    x: float
    y: float
    vx: float
    vy: float
    size: float
    cor: Tuple[int, int, int]
    alpha: float = 255.0
    vida: float = 0.5
    rotation: float = 0.0
    rotation_speed: float = 0.0
    
    def update(self, dt: float):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 50 * dt  # Gravidade leve
        self.vx *= 0.95  # Atrito
        self.vida -= dt
        self.alpha = max(0, 255 * (self.vida / 0.5))
        self.size *= 0.98
        self.rotation += self.rotation_speed * dt
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0 and self.size > 0.5


class DustCloud:
    """
    Nuvem de poeira para aterrissagens, dash no chão, etc.
    
    Adiciona "peso" visual às ações mostrando interação com o ambiente.
    """
    
    def __init__(self, x: float, y: float, intensidade: float = 1.0, 
                 direcao: float = 0.0, tipo: str = "landing"):
        self.x = x
        self.y = y
        self.particles: List[DustParticle] = []
        self.vida = 0.6
        
        # Gera partículas baseado no tipo
        if tipo == "landing":
            self._spawn_landing_dust(intensidade)
        elif tipo == "dash":
            self._spawn_dash_dust(intensidade, direcao)
        elif tipo == "skid":
            self._spawn_skid_dust(intensidade, direcao)
        elif tipo == "impact":
            self._spawn_impact_dust(intensidade)
    
    def _spawn_landing_dust(self, intensidade: float):
        """Poeira de aterrissagem - expande radialmente"""
        intensidade = min(2.0, intensidade)  # Limita intensidade
        qtd = min(20, int(10 * intensidade))  # Max 20 partículas
        for _ in range(qtd):
            ang = random.uniform(0, math.pi * 2)
            vel = random.uniform(30, 80) * intensidade
            self.particles.append(DustParticle(
                x=self.x + random.uniform(-5, 5),
                y=self.y + random.uniform(-2, 2),
                vx=math.cos(ang) * vel,
                vy=math.sin(ang) * vel * 0.3 - random.uniform(20, 50),  # Mais pra cima
                size=random.uniform(4, 10) * intensidade,
                cor=random.choice(DUST_COLORS),
                vida=random.uniform(0.3, 0.6),
                rotation_speed=random.uniform(-180, 180)
            ))
    
    def _spawn_dash_dust(self, intensidade: float, direcao: float):
        """Poeira de dash - deixada para trás"""
        intensidade = min(2.0, intensidade)  # Limita intensidade
        qtd = min(15, int(8 * intensidade))  # Max 15 partículas
        for _ in range(qtd):
            # Partículas vão na direção oposta ao dash
            ang = direcao + math.pi + random.uniform(-0.5, 0.5)
            vel = random.uniform(20, 60) * intensidade
            self.particles.append(DustParticle(
                x=self.x + random.uniform(-10, 10),
                y=self.y + random.uniform(-3, 3),
                vx=math.cos(ang) * vel,
                vy=-random.uniform(10, 30),  # Sobe um pouco
                size=random.uniform(3, 7) * intensidade,
                cor=random.choice(DUST_COLORS),
                vida=random.uniform(0.2, 0.4),
            ))
    
    def _spawn_skid_dust(self, intensidade: float, direcao: float):
        """Poeira de derrapagem - linhas na direção do movimento"""
        intensidade = min(2.0, intensidade)  # Limita intensidade
        qtd = min(12, int(6 * intensidade))  # Max 12 partículas
        for i in range(qtd):
            # Cria linha de poeira
            offset = i * 5
            self.particles.append(DustParticle(
                x=self.x - math.cos(direcao) * offset,
                y=self.y - math.sin(direcao) * offset * 0.3,
                vx=random.uniform(-10, 10),
                vy=-random.uniform(5, 15),
                size=random.uniform(2, 5) * intensidade,
                cor=random.choice(DUST_COLORS),
                vida=random.uniform(0.15, 0.3),
            ))
    
    def _spawn_impact_dust(self, intensidade: float):
        """Poeira de impacto - explosão concentrada"""
        intensidade = min(2.0, intensidade)  # Limita intensidade
        qtd = min(25, int(12 * intensidade))  # Max 25 partículas
        for _ in range(qtd):
            ang = random.uniform(0, math.pi * 2)
            vel = random.uniform(50, 150) * intensidade
            self.particles.append(DustParticle(
                x=self.x,
                y=self.y,
                vx=math.cos(ang) * vel,
                vy=math.sin(ang) * vel - random.uniform(30, 80),
                size=random.uniform(5, 12) * intensidade,
                cor=random.choice(IMPACT_COLORS),
                vida=random.uniform(0.2, 0.5),
                rotation_speed=random.uniform(-360, 360)
            ))
    
    def update(self, dt: float):
        self.vida -= dt
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.ativo]
    
    @property
    def ativo(self) -> bool:
        return len(self.particles) > 0 or self.vida > 0
    
    def draw(self, tela, cam, ppm: float):
        for p in self.particles:
            sx, sy = cam.converter(p.x, p.y)
            tam = int(cam.converter_tam(p.size))
            if tam < 1:
                continue
            
            # Garante valores de cor válidos
            r = max(0, min(255, int(p.cor[0])))
            g = max(0, min(255, int(p.cor[1])))
            b = max(0, min(255, int(p.cor[2])))
            a = max(0, min(255, int(p.alpha * 0.7)))
            
            s = pygame.Surface((tam * 2 + 2, tam * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (r, g, b, a), (tam + 1, tam + 1), tam)
            tela.blit(s, (sx - tam - 1, sy - tam - 1))


# =============================================================================
# SPEED LINES - Linhas de Velocidade
# =============================================================================

@dataclass
class SpeedLine:
    """Uma linha de velocidade individual"""
    x: float
    y: float
    angulo: float
    comprimento: float
    largura: float
    cor: Tuple[int, int, int]
    alpha: float = 255.0
    vida: float = 0.2
    offset: float = 0.0  # Offset do centro
    
    def update(self, dt: float):
        self.vida -= dt
        self.alpha = 255 * (self.vida / 0.2)
        self.comprimento *= 1.05  # Estica um pouco
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0


class SpeedLinesEffect:
    """
    Linhas de velocidade estilo anime/mangá.
    
    Aparecem ao redor do personagem durante movimentos rápidos,
    indicando direção e intensidade do movimento.
    """
    
    def __init__(self, x: float, y: float, direcao: float, intensidade: float = 1.0,
                 cor: tuple = None, tipo: str = "dash"):
        self.x = x
        self.y = y
        self.direcao = direcao
        self.lines: List[SpeedLine] = []
        self.vida = 0.3
        
        cor = cor or random.choice(SPEED_COLORS)
        
        if tipo == "dash":
            self._spawn_dash_lines(intensidade, cor)
        elif tipo == "knockback":
            self._spawn_knockback_lines(intensidade, cor)
        elif tipo == "sprint":
            self._spawn_sprint_lines(intensidade, cor)
    
    def _spawn_dash_lines(self, intensidade: float, cor: tuple):
        """Linhas paralelas na direção oposta ao dash"""
        qtd = int(8 * intensidade)
        for i in range(qtd):
            # Linhas atrás do personagem
            offset_lateral = random.uniform(-30, 30)
            offset_dist = random.uniform(20, 60)
            
            # Posição relativa
            perp = self.direcao + math.pi / 2
            lx = self.x - math.cos(self.direcao) * offset_dist + math.cos(perp) * offset_lateral
            ly = self.y - math.sin(self.direcao) * offset_dist * 0.3 + math.sin(perp) * offset_lateral * 0.3
            
            self.lines.append(SpeedLine(
                x=lx, y=ly,
                angulo=self.direcao + random.uniform(-0.1, 0.1),
                comprimento=random.uniform(20, 50) * intensidade,
                largura=random.uniform(2, 4),
                cor=cor,
                vida=random.uniform(0.1, 0.25),
                offset=offset_dist
            ))
    
    def _spawn_knockback_lines(self, intensidade: float, cor: tuple):
        """Linhas radiando do ponto de impacto"""
        qtd = int(12 * intensidade)
        for i in range(qtd):
            ang = self.direcao + random.uniform(-0.8, 0.8)
            self.lines.append(SpeedLine(
                x=self.x + random.uniform(-10, 10),
                y=self.y + random.uniform(-5, 5),
                angulo=ang,
                comprimento=random.uniform(30, 70) * intensidade,
                largura=random.uniform(2, 5),
                cor=cor,
                vida=random.uniform(0.15, 0.3)
            ))
    
    def _spawn_sprint_lines(self, intensidade: float, cor: tuple):
        """Linhas mais sutis para corrida"""
        qtd = int(5 * intensidade)
        for i in range(qtd):
            offset_lateral = random.uniform(-20, 20)
            self.lines.append(SpeedLine(
                x=self.x + random.uniform(-30, -10),
                y=self.y + offset_lateral,
                angulo=self.direcao,
                comprimento=random.uniform(15, 30) * intensidade,
                largura=random.uniform(1, 2),
                cor=cor,
                vida=random.uniform(0.1, 0.15)
            ))
    
    def update(self, dt: float):
        self.vida -= dt
        for line in self.lines:
            line.update(dt)
        self.lines = [l for l in self.lines if l.ativo]
    
    @property
    def ativo(self) -> bool:
        return len(self.lines) > 0 or self.vida > 0
    
    def draw(self, tela, cam, ppm: float):
        for line in self.lines:
            sx, sy = cam.converter(line.x, line.y)
            comp = cam.converter_tam(line.comprimento)
            
            # Calcula ponto final
            ex = sx + math.cos(line.angulo) * comp
            ey = sy + math.sin(line.angulo) * comp * 0.3  # Achatado em Y
            
            # Desenha linha com fade
            r = max(0, min(255, int(line.cor[0])))
            g = max(0, min(255, int(line.cor[1])))
            b = max(0, min(255, int(line.cor[2])))
            a = max(0, min(255, int(line.alpha)))
            cor_alpha = (r, g, b, a)
            
            # Linha principal
            width = max(int(abs(ex - sx)) + 20, 1)
            height = max(int(abs(ey - sy)) + 20, 1)
            s = pygame.Surface((width, height), pygame.SRCALPHA)
            offset = (min(sx, ex) - 10, min(sy, ey) - 10)
            pygame.draw.line(s, cor_alpha, 
                           (int(sx - offset[0]), int(sy - offset[1])),
                           (int(ex) - int(offset[0]), int(ey) - int(offset[1])),
                           max(1, int(line.largura)))
            tela.blit(s, offset)


# =============================================================================
# MOTION BLUR - Borrão de Movimento
# =============================================================================

class MotionBlur:
    """
    Efeito de motion blur para knockback e movimentos violentos.
    
    Diferente do afterimage trail, este é um efeito mais "borrado"
    que indica perda de controle.
    """
    
    def __init__(self, lutador, direcao: float, intensidade: float = 1.0):
        self.lutador = lutador
        self.direcao = direcao
        self.intensidade = intensidade
        self.vida = 0.4
        self.max_vida = 0.4
        
        # Armazena posições para blur
        self.posicoes: List[Tuple[float, float, float]] = []  # (x, y, alpha)
        self.timer_sample = 0.0
        
        # Cor do personagem (garante inteiros)
        self.cor = (
            int(lutador.dados.cor_r),
            int(lutador.dados.cor_g),
            int(lutador.dados.cor_b)
        )
    
    def update(self, dt: float):
        self.vida -= dt
        
        # Amostra posições durante o knockback
        self.timer_sample += dt
        if self.timer_sample >= 0.015:  # ~60 amostras/segundo
            self.timer_sample = 0
            alpha = 150 * (self.vida / self.max_vida) * self.intensidade
            self.posicoes.append((
                self.lutador.pos[0],
                self.lutador.pos[1],
                alpha
            ))
            
            # Limita quantidade de amostras
            if len(self.posicoes) > 15:
                self.posicoes.pop(0)
        
        # Fade das posições antigas
        for i, (x, y, a) in enumerate(self.posicoes):
            self.posicoes[i] = (x, y, a * 0.9)
        
        # Remove posições muito fracas
        self.posicoes = [(x, y, a) for x, y, a in self.posicoes if a > 5]
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0 or len(self.posicoes) > 0
    
    def draw(self, tela, cam, ppm: float):
        tam_base = self.lutador.dados.tamanho * ppm * 0.5
        
        # Desenha blur "esticado" na direção do movimento
        for x, y, alpha in self.posicoes:
            sx, sy = cam.converter(x * ppm, y * ppm)
            tam = cam.converter_tam(tam_base)
            
            if tam < 2:
                continue
            
            # Garante inteiros para Surface e Rect
            tam = int(tam)
            
            # Elipse esticada na direção do movimento
            s = pygame.Surface((tam * 4, tam * 2), pygame.SRCALPHA)
            
            # Cor com alpha (garante inteiros e limites válidos 0-255)
            r = max(0, min(255, int(self.cor[0])))
            g = max(0, min(255, int(self.cor[1])))
            b = max(0, min(255, int(self.cor[2])))
            a = max(0, min(255, int(alpha * 0.5)))
            cor = (r, g, b, a)
            
            # Desenha elipse
            rect = pygame.Rect(0, 0, tam * 4, tam * 2)
            pygame.draw.ellipse(s, cor, rect)
            
            # Rotaciona para direção do movimento
            s_rot = pygame.transform.rotate(s, -math.degrees(self.direcao))
            
            # Centraliza
            rect_rot = s_rot.get_rect(center=(sx, sy))
            tela.blit(s_rot, rect_rot)


# =============================================================================
# SQUASH & STRETCH - Deformação Elástica
# =============================================================================

class SquashStretch:
    """
    Sistema de squash & stretch para adicionar elasticidade
    aos movimentos de aterrissagem, pulo e impacto.
    
    Princípio clássico de animação que dá "vida" ao movimento.
    """
    
    def __init__(self, lutador, tipo: str = "landing"):
        self.lutador = lutador
        self.tipo = tipo
        self.vida = 0.3
        self.max_vida = 0.3
        
        # Escalas X e Y (1.0 = normal)
        self.escala_x = 1.0
        self.escala_y = 1.0
        
        # Define deformação inicial baseada no tipo
        if tipo == "landing":
            # Achata ao pousar
            self.escala_x = 1.4
            self.escala_y = 0.6
        elif tipo == "jump":
            # Estica ao pular
            self.escala_x = 0.7
            self.escala_y = 1.4
        elif tipo == "impact":
            # Achata muito no impacto
            self.escala_x = 1.6
            self.escala_y = 0.4
        elif tipo == "anticipation":
            # Encolhe antes de agir
            self.escala_x = 1.2
            self.escala_y = 0.8
    
    def update(self, dt: float):
        self.vida -= dt
        
        # Interpola de volta para escala normal
        # Usa easing elástico para efeito de "bounce"
        prog = 1.0 - (self.vida / self.max_vida)
        
        # Easing elástico simplificado
        if prog < 1.0:
            elastic = math.sin(prog * math.pi * 2.5) * (1.0 - prog) * 0.3
            target_x = 1.0 + elastic
            target_y = 1.0 - elastic
        else:
            target_x = 1.0
            target_y = 1.0
        
        # Interpola
        self.escala_x += (target_x - self.escala_x) * 10 * dt
        self.escala_y += (target_y - self.escala_y) * 10 * dt
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0
    
    def get_escalas(self) -> Tuple[float, float]:
        """Retorna escalas para aplicar ao desenho do personagem"""
        return (self.escala_x, self.escala_y)


# =============================================================================
# RECOVERY FLASH - Flash de Recuperação
# =============================================================================

class RecoveryFlash:
    """
    Efeito de flash quando personagem se recupera de stagger/knockback.
    
    Indica ao jogador que o personagem está pronto para agir novamente.
    """
    
    def __init__(self, x: float, y: float, cor: tuple, intensidade: float = 1.0):
        self.x = x
        self.y = y
        self.cor = cor
        self.vida = 0.25
        self.max_vida = 0.25
        self.raio = 20 * intensidade
        self.raio_max = 60 * intensidade
        
        # Linhas de "energia"
        self.linhas = []
        for i in range(6):
            ang = i * (math.pi * 2 / 6)
            self.linhas.append({
                'angulo': ang,
                'comprimento': random.uniform(30, 50) * intensidade,
                'largura': random.uniform(2, 4)
            })
    
    def update(self, dt: float):
        self.vida -= dt
        prog = 1.0 - (self.vida / self.max_vida)
        
        # Raio expande
        self.raio = 20 + (self.raio_max - 20) * prog
    
    @property
    def ativo(self) -> bool:
        return self.vida > 0
    
    def draw(self, tela, cam, ppm: float):
        sx, sy = cam.converter(self.x, self.y)
        alpha = max(0, min(255, int(255 * (self.vida / self.max_vida))))
        raio = int(cam.converter_tam(self.raio))
        
        if raio < 2:
            return
        
        # Garante valores de cor válidos
        r = max(0, min(255, int(self.cor[0])))
        g = max(0, min(255, int(self.cor[1])))
        b = max(0, min(255, int(self.cor[2])))
        
        # Círculo principal
        s = pygame.Surface((raio * 2 + 10, raio * 2 + 10), pygame.SRCALPHA)
        centro = (raio + 5, raio + 5)
        
        # Glow externo
        glow_alpha = max(0, min(255, alpha // 3))
        pygame.draw.circle(s, (r, g, b, glow_alpha), centro, raio + 3)
        
        # Anel
        pygame.draw.circle(s, (r, g, b, alpha), centro, raio, max(2, raio // 8))
        
        # Centro brilhante
        pygame.draw.circle(s, (255, 255, 255, alpha), centro, raio // 3)
        
        # Linhas de energia
        for linha in self.linhas:
            comp = cam.converter_tam(linha['comprimento'] * (self.vida / self.max_vida))
            ex = centro[0] + math.cos(linha['angulo']) * comp
            ey = centro[1] + math.sin(linha['angulo']) * comp
            pygame.draw.line(s, (r, g, b, alpha), centro, (int(ex), int(ey)), 
                           max(1, int(linha['largura'])))
        
        tela.blit(s, (int(sx - raio - 5), int(sy - raio - 5)))


# =============================================================================
# MOVEMENT ANIMATION MANAGER
# =============================================================================

class MovementAnimationManager:
    """
    Gerenciador central de todas as animações de movimento.
    
    Coordena a criação e atualização de todos os efeitos de movimento
    para garantir consistência visual.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def __init__(self):
        self.afterimage_trails: List[AfterImageTrail] = []
        self.dust_clouds: List[DustCloud] = []
        self.speed_lines: List[SpeedLinesEffect] = []
        self.motion_blurs: List[MotionBlur] = []
        self.squash_effects: dict = {}  # lutador -> SquashStretch
        self.recovery_flashes: List[RecoveryFlash] = []
        
        # Limites máximos para performance
        self.MAX_AFTERIMAGES = 10
        self.MAX_DUST = 15
        self.MAX_SPEED_LINES = 12
        self.MAX_BLURS = 6
        self.MAX_FLASHES = 8
        
        # PPM para conversões
        self.ppm = 50  # Será atualizado pelo simulador
    
    def set_ppm(self, ppm: float):
        """Define pixels por metro"""
        self.ppm = ppm
    
    def criar_dash_effect(self, lutador, direcao: float, tipo: MovementType = MovementType.DASH_FORWARD):
        """
        Cria efeitos de dash completos.
        
        Inclui: afterimages, speed lines, dust (se no chão)
        """
        # Limita quantidade de efeitos simultâneos
        if len(self.afterimage_trails) >= self.MAX_AFTERIMAGES:
            return
        
        cor = (int(lutador.dados.cor_r), int(lutador.dados.cor_g), int(lutador.dados.cor_b))
        x, y = lutador.pos[0] * self.ppm, lutador.pos[1] * self.ppm
        
        # Afterimage trail
        trail = AfterImageTrail(lutador, tipo, cor)
        self.afterimage_trails.append(trail)
        
        # Speed lines
        if len(self.speed_lines) < self.MAX_SPEED_LINES:
            intensidade = 1.2 if tipo == MovementType.DASH_FORWARD else 1.0
            lines = SpeedLinesEffect(x, y, direcao, intensidade, cor, "dash")
            self.speed_lines.append(lines)
        
        # Dust se no chão
        if getattr(lutador, 'z', 0) <= 0.1 and len(self.dust_clouds) < self.MAX_DUST:
            dust = DustCloud(x, y, 0.8, direcao, "dash")
            self.dust_clouds.append(dust)
    
    def criar_knockback_effect(self, lutador, direcao: float, intensidade: float = 1.0):
        """
        Cria efeitos de knockback.
        
        Inclui: motion blur, speed lines, impact dust, squash
        """
        # Normaliza intensidade (dano pode ser 5-50+, queremos 0.5-2.0)
        intensidade_norm = min(2.0, max(0.5, intensidade / 15.0))
        
        cor = (int(lutador.dados.cor_r), int(lutador.dados.cor_g), int(lutador.dados.cor_b))
        x, y = lutador.pos[0] * self.ppm, lutador.pos[1] * self.ppm
        
        # Motion blur (com limite)
        if len(self.motion_blurs) < self.MAX_BLURS:
            blur = MotionBlur(lutador, direcao, intensidade_norm)
            self.motion_blurs.append(blur)
        
        # Speed lines de impacto (com limite)
        if len(self.speed_lines) < self.MAX_SPEED_LINES:
            lines = SpeedLinesEffect(x, y, direcao, intensidade_norm, (255, 200, 150), "knockback")
            self.speed_lines.append(lines)
        
        # Dust de impacto (com limite)
        if len(self.dust_clouds) < self.MAX_DUST:
            dust = DustCloud(x, y, intensidade_norm * 0.7, 0, "impact")
            self.dust_clouds.append(dust)
        
        # Squash no impacto
        squash = SquashStretch(lutador, "impact")
        self.squash_effects[lutador] = squash
    
    def criar_landing_effect(self, lutador, velocidade_queda: float):
        """
        Cria efeitos de aterrissagem.
        
        Inclui: dust, squash/stretch, possível screen shake
        """
        x, y = lutador.pos[0] * self.ppm, lutador.pos[1] * self.ppm
        intensidade = min(2.0, abs(velocidade_queda) / 15.0)
        
        # Dust radial (com limite)
        if len(self.dust_clouds) < self.MAX_DUST:
            dust = DustCloud(x, y, intensidade, 0, "landing")
            self.dust_clouds.append(dust)
        
        # Squash
        if intensidade > 0.3:
            squash = SquashStretch(lutador, "landing")
            self.squash_effects[lutador] = squash
    
    def criar_jump_effect(self, lutador):
        """
        Cria efeitos de pulo.
        
        Inclui: stretch, pequena dust
        """
        x, y = lutador.pos[0] * self.ppm, lutador.pos[1] * self.ppm
        
        # Stretch
        stretch = SquashStretch(lutador, "jump")
        self.squash_effects[lutador] = stretch
        
        # Pequena dust (com limite)
        if len(self.dust_clouds) < self.MAX_DUST:
            dust = DustCloud(x, y, 0.5, 0, "dash")
            self.dust_clouds.append(dust)
    
    def criar_recovery_effect(self, lutador):
        """
        Cria efeito de recuperação de stagger.
        """
        # Limite de flashes
        if len(self.recovery_flashes) >= self.MAX_FLASHES:
            return
            
        cor = (int(lutador.dados.cor_r), int(lutador.dados.cor_g), int(lutador.dados.cor_b))
        x, y = lutador.pos[0] * self.ppm, lutador.pos[1] * self.ppm
        
        flash = RecoveryFlash(x, y, cor, 1.0)
        self.recovery_flashes.append(flash)
    
    def criar_sprint_effect(self, lutador, direcao: float):
        """
        Cria efeitos sutis de corrida rápida.
        """
        # Limites
        if len(self.speed_lines) >= self.MAX_SPEED_LINES:
            return
            
        cor = (int(lutador.dados.cor_r), int(lutador.dados.cor_g), int(lutador.dados.cor_b))
        x, y = lutador.pos[0] * self.ppm, lutador.pos[1] * self.ppm
        
        # Speed lines sutis
        lines = SpeedLinesEffect(x, y, direcao, 0.5, cor, "sprint")
        self.speed_lines.append(lines)
        
        # Dust leve se no chão (com limite)
        if getattr(lutador, 'z', 0) <= 0.1 and len(self.dust_clouds) < self.MAX_DUST:
            dust = DustCloud(x, y, 0.3, direcao, "skid")
            self.dust_clouds.append(dust)
    
    def update(self, dt: float):
        """Atualiza todos os efeitos"""
        # Afterimages
        for trail in self.afterimage_trails:
            trail.update(dt)
        self.afterimage_trails = [t for t in self.afterimage_trails if t.ativo]
        
        # Dust
        for dust in self.dust_clouds:
            dust.update(dt)
        self.dust_clouds = [d for d in self.dust_clouds if d.ativo]
        
        # Speed lines
        for lines in self.speed_lines:
            lines.update(dt)
        self.speed_lines = [l for l in self.speed_lines if l.ativo]
        
        # Motion blur
        for blur in self.motion_blurs:
            blur.update(dt)
        self.motion_blurs = [b for b in self.motion_blurs if b.ativo]
        
        # Squash effects
        for lutador, squash in list(self.squash_effects.items()):
            squash.update(dt)
            if not squash.ativo:
                del self.squash_effects[lutador]
        
        # Recovery flashes
        for flash in self.recovery_flashes:
            flash.update(dt)
        self.recovery_flashes = [f for f in self.recovery_flashes if f.ativo]
    
    def draw(self, tela, cam):
        """Desenha todos os efeitos"""
        # Ordem de desenho (de trás para frente):
        # 1. Motion blur (mais atrás)
        for blur in self.motion_blurs:
            blur.draw(tela, cam, self.ppm)
        
        # 2. Afterimages
        for trail in self.afterimage_trails:
            trail.draw(tela, cam, self.ppm)
        
        # 3. Dust
        for dust in self.dust_clouds:
            dust.draw(tela, cam, self.ppm)
        
        # 4. Speed lines
        for lines in self.speed_lines:
            lines.draw(tela, cam, self.ppm)
        
        # 5. Recovery flashes (na frente)
        for flash in self.recovery_flashes:
            flash.draw(tela, cam, self.ppm)
    
    def get_squash_stretch(self, lutador) -> Optional[Tuple[float, float]]:
        """Retorna escalas de squash/stretch para um lutador"""
        if lutador in self.squash_effects:
            return self.squash_effects[lutador].get_escalas()
        return None
    
    def clear(self):
        """Limpa todos os efeitos"""
        self.afterimage_trails.clear()
        self.dust_clouds.clear()
        self.speed_lines.clear()
        self.motion_blurs.clear()
        self.squash_effects.clear()
        self.recovery_flashes.clear()
