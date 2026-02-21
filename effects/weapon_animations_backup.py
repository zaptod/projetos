"""
NEURAL FIGHTS - Sistema Avançado de Animações de Armas
Animações de ataque específicas e expressivas para cada tipo de arma.
"""

import math
import pygame
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum


# ============================================================================
# CURVAS DE ANIMAÇÃO (EASING FUNCTIONS)
# ============================================================================

class Easing:
    """Funções de easing para animações suaves e impactantes"""
    
    @staticmethod
    def linear(t: float) -> float:
        return t
    
    @staticmethod
    def ease_in_quad(t: float) -> float:
        return t * t
    
    @staticmethod
    def ease_out_quad(t: float) -> float:
        return 1 - (1 - t) * (1 - t)
    
    @staticmethod
    def ease_in_out_quad(t: float) -> float:
        return 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2
    
    @staticmethod
    def ease_out_back(t: float) -> float:
        """Overshoot no final - bom para swings"""
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)
    
    @staticmethod
    def ease_out_elastic(t: float) -> float:
        """Bounce elástico - bom para impactos"""
        if t == 0 or t == 1:
            return t
        c4 = (2 * math.pi) / 3
        return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1
    
    @staticmethod
    def ease_in_back(t: float) -> float:
        """Wind-up antes do movimento - anticipation"""
        c1 = 1.70158
        c3 = c1 + 1
        return c3 * t * t * t - c1 * t * t
    
    @staticmethod
    def ease_out_bounce(t: float) -> float:
        """Bounce no final"""
        n1 = 7.5625
        d1 = 2.75
        if t < 1 / d1:
            return n1 * t * t
        elif t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        elif t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        else:
            t -= 2.625 / d1
            return n1 * t * t + 0.984375
    
    @staticmethod
    def anticipate_overshoot(t: float) -> float:
        """Combina anticipation (wind-up) com overshoot"""
        if t < 0.2:
            # Wind-up: vai para trás primeiro
            return -0.5 * Easing.ease_out_quad(t / 0.2)
        else:
            # Swing com overshoot
            adjusted = (t - 0.2) / 0.8
            return -0.5 + 1.5 * Easing.ease_out_back(adjusted)


# ============================================================================
# FASES DE ANIMAÇÃO
# ============================================================================

class AttackPhase(Enum):
    """Fases de uma animação de ataque"""
    ANTICIPATION = "anticipation"  # Wind-up / preparação
    ATTACK = "attack"              # Golpe principal
    IMPACT = "impact"              # Momento do impacto
    FOLLOW_THROUGH = "follow"      # Continuação após impacto
    RECOVERY = "recovery"          # Retorno à posição neutra


# ============================================================================
# DEFINIÇÕES DE ANIMAÇÃO POR TIPO DE ARMA
# ============================================================================

@dataclass
class WeaponAnimationProfile:
    """Perfil de animação para um tipo de arma"""
    
    # Tempos de cada fase (em segundos)
    anticipation_time: float = 0.08
    attack_time: float = 0.12
    impact_time: float = 0.03
    follow_through_time: float = 0.1
    recovery_time: float = 0.12
    
    # Ângulos de movimento
    anticipation_angle: float = -45      # Wind-up (negativo = para trás)
    attack_angle: float = 120            # Arco do ataque
    follow_through_angle: float = 30     # Overshoot após impacto
    
    # Escala (squash/stretch)
    anticipation_scale: float = 0.85     # Comprime na preparação
    attack_scale: float = 1.15           # Estica durante ataque
    impact_scale: float = 0.9            # Comprime no impacto
    
    # Efeitos visuais
    trail_enabled: bool = True
    trail_length: int = 8
    trail_fade: float = 0.8
    
    # Shake na arma
    shake_on_impact: bool = True
    shake_intensity: float = 3.0
    
    # Tipo de curva de easing
    anticipation_easing: str = "ease_out_quad"
    attack_easing: str = "ease_out_back"
    recovery_easing: str = "ease_in_out_quad"
    
    @property
    def total_time(self) -> float:
        return (self.anticipation_time + self.attack_time + 
                self.impact_time + self.follow_through_time + 
                self.recovery_time)


# Perfis específicos para cada tipo de arma
WEAPON_PROFILES: Dict[str, WeaponAnimationProfile] = {
    
    "Reta": WeaponAnimationProfile(
        anticipation_time=0.1,
        attack_time=0.12,
        impact_time=0.02,
        follow_through_time=0.08,
        recovery_time=0.15,
        anticipation_angle=-50,
        attack_angle=130,
        follow_through_angle=25,
        anticipation_scale=0.9,
        attack_scale=1.2,
        trail_length=10,
        shake_intensity=4.0,
    ),
    
    "Dupla": WeaponAnimationProfile(
        anticipation_time=0.05,       # Mais rápido
        attack_time=0.08,
        impact_time=0.02,
        follow_through_time=0.05,
        recovery_time=0.08,
        anticipation_angle=-30,        # Wind-up menor
        attack_angle=90,               # Arco menor mas rápido
        follow_through_angle=15,
        anticipation_scale=0.95,
        attack_scale=1.1,
        trail_length=6,
        shake_intensity=2.0,
    ),
    
    "Corrente": WeaponAnimationProfile(
        anticipation_time=0.15,        # Wind-up longo para momentum
        attack_time=0.2,               # Ataque mais lento mas poderoso
        impact_time=0.03,
        follow_through_time=0.15,      # Continua girando
        recovery_time=0.2,
        anticipation_angle=-80,        # Grande wind-up
        attack_angle=200,              # Arco enorme
        follow_through_angle=60,
        anticipation_scale=0.8,
        attack_scale=1.3,
        trail_length=15,
        shake_intensity=6.0,
    ),
    
    "Arremesso": WeaponAnimationProfile(
        anticipation_time=0.12,
        attack_time=0.06,              # Release rápido
        impact_time=0.0,               # Sem impacto (projétil)
        follow_through_time=0.1,
        recovery_time=0.15,
        anticipation_angle=-60,        # Puxa para trás
        attack_angle=80,
        follow_through_angle=40,       # Acompanha o arremesso
        anticipation_scale=0.85,
        attack_scale=1.25,
        trail_enabled=False,           # Trail no projétil, não na mão
        shake_intensity=0.0,
    ),
    
    "Arco": WeaponAnimationProfile(
        anticipation_time=0.25,        # Puxar a corda
        attack_time=0.04,              # Release instantâneo
        impact_time=0.0,
        follow_through_time=0.08,
        recovery_time=0.2,
        anticipation_angle=-10,        # Quase não muda ângulo
        attack_angle=5,                # Pequeno recuo
        follow_through_angle=3,
        anticipation_scale=1.15,       # Estica ao puxar
        attack_scale=0.9,              # Comprime no release
        trail_enabled=False,
        shake_intensity=1.5,
    ),
    
    "Orbital": WeaponAnimationProfile(
        anticipation_time=0.0,         # Sempre girando
        attack_time=0.15,
        impact_time=0.02,
        follow_through_time=0.1,
        recovery_time=0.0,
        anticipation_angle=0,
        attack_angle=360,              # Giro completo
        follow_through_angle=0,
        anticipation_scale=1.0,
        attack_scale=1.0,
        trail_length=20,
        shake_intensity=2.0,
    ),
    
    "Mágica": WeaponAnimationProfile(
        anticipation_time=0.1,
        attack_time=0.15,
        impact_time=0.05,              # Mais tempo de impacto para efeitos
        follow_through_time=0.1,
        recovery_time=0.15,
        anticipation_angle=-20,
        attack_angle=60,
        follow_through_angle=20,
        anticipation_scale=0.7,        # Contrai antes de expandir
        attack_scale=1.4,              # Expansão dramática
        trail_length=12,
        shake_intensity=3.0,
    ),
    
    "Transformável": WeaponAnimationProfile(
        anticipation_time=0.08,
        attack_time=0.15,
        impact_time=0.03,
        follow_through_time=0.12,
        recovery_time=0.15,
        anticipation_angle=-40,
        attack_angle=110,
        follow_through_angle=30,
        anticipation_scale=0.85,
        attack_scale=1.2,
        trail_length=10,
        shake_intensity=4.0,
    ),
}


# ============================================================================
# ANIMADOR DE ARMA
# ============================================================================

@dataclass
class WeaponAnimationState:
    """Estado atual de uma animação de arma"""
    
    # Estado de ataque
    is_attacking: bool = False
    attack_timer: float = 0.0
    current_phase: AttackPhase = AttackPhase.RECOVERY
    
    # Valores calculados
    angle_offset: float = 0.0          # Offset do ângulo base
    scale: float = 1.0                 # Escala atual
    shake_offset: Tuple[float, float] = (0.0, 0.0)
    
    # Trail de movimento
    trail_positions: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, alpha)
    
    # Padrão de ataque atual (para variação)
    attack_pattern: int = 0            # 0, 1, 2... para alternar direções
    
    # Bow-specific
    draw_amount: float = 0.0           # Quanto o arco está puxado (0-1)
    
    # Chain-specific
    chain_momentum: float = 0.0        # Momentum acumulado
    
    # Magic-specific
    pulse_phase: float = 0.0           # Fase de pulsação


class WeaponAnimator:
    """
    Gerenciador de animações de armas.
    Calcula o estado visual da arma baseado no tempo e tipo.
    """
    
    def __init__(self):
        self.states: Dict[int, WeaponAnimationState] = {}
        self.easings = {
            "linear": Easing.linear,
            "ease_in_quad": Easing.ease_in_quad,
            "ease_out_quad": Easing.ease_out_quad,
            "ease_in_out_quad": Easing.ease_in_out_quad,
            "ease_out_back": Easing.ease_out_back,
            "ease_out_elastic": Easing.ease_out_elastic,
            "ease_in_back": Easing.ease_in_back,
            "ease_out_bounce": Easing.ease_out_bounce,
            "anticipate_overshoot": Easing.anticipate_overshoot,
        }
    
    def get_state(self, fighter_id: int) -> WeaponAnimationState:
        """Obtém ou cria estado de animação para um lutador"""
        if fighter_id not in self.states:
            self.states[fighter_id] = WeaponAnimationState()
        return self.states[fighter_id]
    
    def start_attack(self, fighter_id: int, weapon_type: str):
        """Inicia uma animação de ataque"""
        state = self.get_state(fighter_id)
        profile = WEAPON_PROFILES.get(weapon_type, WEAPON_PROFILES["Reta"])
        
        state.is_attacking = True
        state.attack_timer = 0.0
        state.current_phase = AttackPhase.ANTICIPATION
        state.trail_positions = []
        
        # Alterna padrão de ataque (esquerda/direita)
        state.attack_pattern = (state.attack_pattern + 1) % 3
    
    def update(self, dt: float, fighter_id: int, weapon_type: str, 
               base_angle: float, weapon_tip_pos: Tuple[float, float]) -> WeaponAnimationState:
        """
        Atualiza animação e retorna estado atual.
        
        Args:
            dt: Delta time
            fighter_id: ID do lutador
            weapon_type: Tipo da arma
            base_angle: Ângulo base (direção que o lutador olha)
            weapon_tip_pos: Posição da ponta da arma (para trail)
        """
        state = self.get_state(fighter_id)
        profile = WEAPON_PROFILES.get(weapon_type, WEAPON_PROFILES["Reta"])
        
        if state.is_attacking:
            state.attack_timer += dt
            self._update_attack_animation(state, profile, base_angle)
            
            # Atualiza trail
            if profile.trail_enabled:
                state.trail_positions.append((weapon_tip_pos[0], weapon_tip_pos[1], 1.0))
                if len(state.trail_positions) > profile.trail_length:
                    state.trail_positions.pop(0)
                # Fade trail
                for i in range(len(state.trail_positions)):
                    x, y, a = state.trail_positions[i]
                    state.trail_positions[i] = (x, y, a * profile.trail_fade)
        else:
            # Idle animation
            self._update_idle_animation(state, weapon_type, dt)
            
            # Fade out trail
            if state.trail_positions:
                new_trail = []
                for x, y, a in state.trail_positions:
                    a *= 0.85
                    if a > 0.05:
                        new_trail.append((x, y, a))
                state.trail_positions = new_trail
        
        return state
    
    def _update_attack_animation(self, state: WeaponAnimationState, 
                                  profile: WeaponAnimationProfile, base_angle: float):
        """Atualiza animação durante ataque"""
        
        t = state.attack_timer
        
        # Determina fase atual
        phase_times = [
            (AttackPhase.ANTICIPATION, profile.anticipation_time),
            (AttackPhase.ATTACK, profile.attack_time),
            (AttackPhase.IMPACT, profile.impact_time),
            (AttackPhase.FOLLOW_THROUGH, profile.follow_through_time),
            (AttackPhase.RECOVERY, profile.recovery_time),
        ]
        
        elapsed = 0.0
        current_phase = AttackPhase.RECOVERY
        phase_progress = 1.0
        
        for phase, duration in phase_times:
            if t < elapsed + duration:
                current_phase = phase
                phase_progress = (t - elapsed) / max(duration, 0.001)
                break
            elapsed += duration
        
        state.current_phase = current_phase
        
        # Direção do swing baseada no padrão
        direction = 1 if state.attack_pattern % 2 == 0 else -1
        
        # Calcula offset de ângulo baseado na fase
        if current_phase == AttackPhase.ANTICIPATION:
            # Wind-up: vai para trás
            easing = self.easings.get(profile.anticipation_easing, Easing.ease_out_quad)
            prog = easing(phase_progress)
            state.angle_offset = profile.anticipation_angle * prog * direction
            state.scale = 1.0 + (profile.anticipation_scale - 1.0) * prog
            
        elif current_phase == AttackPhase.ATTACK:
            # Swing principal
            easing = self.easings.get(profile.attack_easing, Easing.ease_out_back)
            prog = easing(phase_progress)
            
            start = profile.anticipation_angle * direction
            end = profile.attack_angle * direction
            state.angle_offset = start + (end - start) * prog
            
            # Escala com pico no meio do swing
            scale_prog = math.sin(phase_progress * math.pi)
            state.scale = 1.0 + (profile.attack_scale - 1.0) * scale_prog
            
        elif current_phase == AttackPhase.IMPACT:
            # Momento do impacto - shake e pausa breve
            state.angle_offset = profile.attack_angle * direction
            state.scale = profile.impact_scale
            
            if profile.shake_on_impact:
                shake = profile.shake_intensity * (1 - phase_progress)
                state.shake_offset = (
                    random.uniform(-shake, shake),
                    random.uniform(-shake, shake)
                )
            
        elif current_phase == AttackPhase.FOLLOW_THROUGH:
            # Overshoot após impacto
            prog = Easing.ease_out_quad(phase_progress)
            total_angle = (profile.attack_angle + profile.follow_through_angle) * direction
            state.angle_offset = profile.attack_angle * direction + (profile.follow_through_angle * direction * (1 - prog))
            state.scale = profile.impact_scale + (1.0 - profile.impact_scale) * prog
            state.shake_offset = (0, 0)
            
        elif current_phase == AttackPhase.RECOVERY:
            # Retorno à posição neutra
            easing = self.easings.get(profile.recovery_easing, Easing.ease_in_out_quad)
            prog = easing(phase_progress)
            
            start = (profile.attack_angle + profile.follow_through_angle) * direction
            state.angle_offset = start * (1 - prog)
            state.scale = 1.0
            
            # Termina ataque
            if phase_progress >= 1.0:
                state.is_attacking = False
                state.angle_offset = 0
    
    def _update_idle_animation(self, state: WeaponAnimationState, 
                                weapon_type: str, dt: float):
        """Animação idle/breathing quando não está atacando"""
        
        state.pulse_phase += dt * 2.0
        
        if weapon_type == "Orbital":
            # Orbitais sempre giram
            pass  # Rotação é feita externamente
            
        elif weapon_type == "Mágica":
            # Pulsação suave
            state.scale = 1.0 + 0.05 * math.sin(state.pulse_phase * 1.5)
            state.angle_offset = 3 * math.sin(state.pulse_phase * 0.8)
            
        elif weapon_type == "Corrente":
            # Leve oscilação como se tivesse peso
            state.angle_offset = 5 * math.sin(state.pulse_phase * 0.5)
            
        else:
            # Respiração sutil
            state.scale = 1.0 + 0.02 * math.sin(state.pulse_phase)
            state.angle_offset = 0


# ============================================================================
# RENDERIZADOR DE TRAIL
# ============================================================================

class WeaponTrailRenderer:
    """Renderiza trails de armas durante ataques"""
    
    def __init__(self):
        pass
    
    def draw_trail(self, surface: pygame.Surface, 
                   trail_positions: List[Tuple[float, float, float]],
                   weapon_color: Tuple[int, int, int],
                   weapon_type: str):
        """
        Desenha trail da arma.
        
        Args:
            surface: Superfície pygame
            trail_positions: Lista de (x, y, alpha)
            weapon_color: Cor base da arma
            weapon_type: Tipo da arma
        """
        if len(trail_positions) < 2:
            return
        
        # Diferentes estilos de trail por tipo
        if weapon_type == "Mágica":
            self._draw_magic_trail(surface, trail_positions, weapon_color)
        elif weapon_type == "Corrente":
            self._draw_chain_trail(surface, trail_positions, weapon_color)
        else:
            self._draw_slash_trail(surface, trail_positions, weapon_color)
    
    def _draw_slash_trail(self, surface: pygame.Surface,
                          positions: List[Tuple[float, float, float]],
                          color: Tuple[int, int, int]):
        """Trail padrão de corte"""
        
        for i in range(len(positions) - 1):
            x1, y1, a1 = positions[i]
            x2, y2, a2 = positions[i + 1]
            
            alpha = int(min(a1, a2) * 180)
            if alpha < 10:
                continue
            
            # Largura diminui ao longo do trail
            width = max(1, int(4 * (i / len(positions))))
            
            # Cor com fade
            trail_color = (
                min(255, color[0] + 50),
                min(255, color[1] + 50),
                min(255, color[2] + 50)
            )
            
            # Desenha linha com alpha simulado (mistura com preto)
            blend = alpha / 255
            final_color = tuple(int(c * blend) for c in trail_color)
            
            pygame.draw.line(surface, final_color, 
                           (int(x1), int(y1)), (int(x2), int(y2)), width)
    
    def _draw_magic_trail(self, surface: pygame.Surface,
                          positions: List[Tuple[float, float, float]],
                          color: Tuple[int, int, int]):
        """Trail mágico com partículas"""
        
        for i, (x, y, a) in enumerate(positions):
            if a < 0.1:
                continue
            
            # Partículas brilhantes
            size = max(2, int(6 * a))
            bright_color = (
                min(255, color[0] + 100),
                min(255, color[1] + 100),
                min(255, color[2] + 100)
            )
            
            # Core brilhante
            pygame.draw.circle(surface, bright_color, (int(x), int(y)), size)
            
            # Glow externo
            glow_size = int(size * 2)
            if glow_size > 0:
                s = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
                glow_alpha = int(60 * a)
                pygame.draw.circle(s, (*color, glow_alpha), (glow_size, glow_size), glow_size)
                surface.blit(s, (int(x - glow_size), int(y - glow_size)))
    
    def _draw_chain_trail(self, surface: pygame.Surface,
                          positions: List[Tuple[float, float, float]],
                          color: Tuple[int, int, int]):
        """Trail de corrente com efeito de blur"""
        
        if len(positions) < 2:
            return
        
        # Desenha múltiplas linhas com alpha decrescente
        for layer in range(3):
            alpha_mult = 1.0 - (layer * 0.3)
            width = 3 - layer
            
            for i in range(len(positions) - 1):
                x1, y1, a1 = positions[i]
                x2, y2, a2 = positions[i + 1]
                
                alpha = int(min(a1, a2) * 150 * alpha_mult)
                if alpha < 10:
                    continue
                
                blend = alpha / 255
                final_color = tuple(int(c * blend) for c in color)
                
                pygame.draw.line(surface, final_color,
                               (int(x1), int(y1)), (int(x2), int(y2)), max(1, width))


# ============================================================================
# EFEITOS ESPECIAIS POR TIPO DE ARMA
# ============================================================================

@dataclass
class SlashEffect:
    """Efeito visual de corte"""
    x: float
    y: float
    angle: float
    width: float
    color: Tuple[int, int, int]
    lifetime: float = 0.15
    timer: float = 0.0
    arc_length: float = 90  # Graus
    
    def update(self, dt: float) -> bool:
        self.timer += dt
        return self.timer < self.lifetime
    
    def draw(self, surface: pygame.Surface, camera):
        if self.timer >= self.lifetime:
            return
        
        progress = self.timer / self.lifetime
        alpha = int(200 * (1 - progress))
        
        # Arco de corte que expande
        current_width = self.width * (1 + progress * 2)
        
        # Cria surface com alpha
        size = int(current_width * 3)
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        
        # Desenha arco
        start_angle = math.radians(self.angle - self.arc_length / 2)
        end_angle = math.radians(self.angle + self.arc_length / 2)
        
        points = []
        segments = 12
        for i in range(segments + 1):
            t = i / segments
            a = start_angle + (end_angle - start_angle) * t
            r_inner = current_width * 0.3
            r_outer = current_width
            
            points.append((
                center + math.cos(a) * r_outer,
                center + math.sin(a) * r_outer
            ))
        
        for i in range(segments, -1, -1):
            t = i / segments
            a = start_angle + (end_angle - start_angle) * t
            r_inner = current_width * 0.3
            
            points.append((
                center + math.cos(a) * r_inner,
                center + math.sin(a) * r_inner
            ))
        
        if len(points) > 2:
            color_with_alpha = (*self.color, alpha)
            pygame.draw.polygon(s, color_with_alpha, points)
        
        # Converte posição
        screen_pos = camera.mundo_para_tela(self.x, self.y)
        surface.blit(s, (screen_pos[0] - center, screen_pos[1] - center))


@dataclass 
class ThrustEffect:
    """Efeito visual de estocada"""
    x: float
    y: float
    angle: float
    length: float
    color: Tuple[int, int, int]
    lifetime: float = 0.1
    timer: float = 0.0
    
    def update(self, dt: float) -> bool:
        self.timer += dt
        return self.timer < self.lifetime
    
    def draw(self, surface: pygame.Surface, camera):
        if self.timer >= self.lifetime:
            return
        
        progress = self.timer / self.lifetime
        alpha = int(180 * (1 - progress))
        
        # Linha que se estende
        current_length = self.length * (0.5 + progress * 0.5)
        
        rad = math.radians(self.angle)
        end_x = self.x + math.cos(rad) * current_length
        end_y = self.y + math.sin(rad) * current_length
        
        start = camera.mundo_para_tela(self.x, self.y)
        end = camera.mundo_para_tela(end_x, end_y)
        
        # Trilha de estocada
        width = max(2, int(8 * (1 - progress)))
        
        blend = alpha / 255
        final_color = tuple(min(255, int(c * blend + 100 * blend)) for c in self.color)
        
        pygame.draw.line(surface, final_color, start, end, width)


@dataclass
class BowDrawEffect:
    """Efeito visual de puxar o arco"""
    x: float
    y: float
    draw_amount: float  # 0-1
    color: Tuple[int, int, int]
    
    def draw(self, surface: pygame.Surface, camera, radius: float):
        if self.draw_amount < 0.1:
            return
        
        screen_pos = camera.mundo_para_tela(self.x, self.y)
        
        # Glow de energia acumulada
        glow_radius = int(radius * 0.5 * self.draw_amount)
        if glow_radius > 2:
            s = pygame.Surface((glow_radius * 4, glow_radius * 4), pygame.SRCALPHA)
            center = glow_radius * 2
            
            # Múltiplos círculos para efeito de glow
            for i in range(3):
                r = glow_radius * (1 + i * 0.3)
                alpha = int(60 * self.draw_amount * (1 - i * 0.3))
                pygame.draw.circle(s, (*self.color, alpha), (center, center), int(r))
            
            surface.blit(s, (screen_pos[0] - center, screen_pos[1] - center))


# ============================================================================
# GERENCIADOR PRINCIPAL
# ============================================================================

class WeaponAnimationManager:
    """Gerenciador central de animações de armas"""
    
    def __init__(self):
        self.animator = WeaponAnimator()
        self.trail_renderer = WeaponTrailRenderer()
        self.active_effects: List[Any] = []
    
    def start_attack(self, fighter_id: int, weapon_type: str,
                     position: Tuple[float, float], angle: float):
        """Inicia ataque e cria efeitos visuais"""
        self.animator.start_attack(fighter_id, weapon_type)
        
        # Cria efeitos baseado no tipo
        if weapon_type in ["Reta", "Dupla", "Transformável"]:
            self.active_effects.append(SlashEffect(
                x=position[0], y=position[1],
                angle=angle,
                width=30,
                color=(255, 255, 255)
            ))
    
    def update(self, dt: float):
        """Atualiza todos os efeitos"""
        # Atualiza efeitos ativos
        self.active_effects = [e for e in self.active_effects if e.update(dt)]
    
    def get_weapon_transform(self, fighter_id: int, weapon_type: str,
                             base_angle: float, weapon_tip: Tuple[float, float],
                             dt: float) -> Dict[str, Any]:
        """
        Obtém transformações da arma para renderização.
        
        Returns:
            Dict com: angle_offset, scale, shake, trail_positions
        """
        state = self.animator.update(dt, fighter_id, weapon_type, base_angle, weapon_tip)
        
        return {
            "angle_offset": state.angle_offset,
            "scale": state.scale,
            "shake": state.shake_offset,
            "trail_positions": state.trail_positions,
            "is_attacking": state.is_attacking,
            "phase": state.current_phase,
        }
    
    def draw_trails(self, surface: pygame.Surface, fighter_id: int,
                    weapon_color: Tuple[int, int, int], weapon_type: str):
        """Desenha trails da arma"""
        state = self.animator.get_state(fighter_id)
        if state.trail_positions:
            self.trail_renderer.draw_trail(surface, state.trail_positions, 
                                          weapon_color, weapon_type)
    
    def draw_effects(self, surface: pygame.Surface, camera):
        """Desenha efeitos especiais"""
        for effect in self.active_effects:
            effect.draw(surface, camera)


# ============================================================================
# SINGLETON GLOBAL
# ============================================================================

_weapon_animation_manager: Optional[WeaponAnimationManager] = None

def get_weapon_animation_manager() -> WeaponAnimationManager:
    """Obtém instância global do gerenciador"""
    global _weapon_animation_manager
    if _weapon_animation_manager is None:
        _weapon_animation_manager = WeaponAnimationManager()
    return _weapon_animation_manager
