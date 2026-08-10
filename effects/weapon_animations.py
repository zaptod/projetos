"""
NEURAL FIGHTS - Sistema Avançado de Animações de Armas v2.0
============================================================
CHANGELOG v2.0:
- Melhoria visual em TODAS as armas (trails, glow, partículas, squash/stretch)
- Reformulação TOTAL do Mangual: física de corrente realista, spin acumulativo,
  rastro de bolas de impacto com spike de velocidade no contato
- Reformulação TOTAL das Adagas Gêmeas: sistema de combo alternado L/R,
  dash-stab visual, streak de velocidade por daga, efeito de blur direcional
- Novos efeitos: glow pulsante, motion blur, impact burst, spark showers
- Easing aprimorado com curvas específicas por arma
"""

import math
import pygame
import random
from dataclasses import dataclass, field
from typing import List, Tuple
from enum import Enum


# ============================================================================
# CURVAS DE ANIMAÇÃO (EASING FUNCTIONS)
# ============================================================================

class Easing:
    @staticmethod
    def linear(t):
        return t
    @staticmethod
    def ease_in_quad(t):
        return t * t
    @staticmethod
    def ease_out_quad(t):
        return 1 - (1 - t) * (1 - t)
    @staticmethod
    def ease_in_out_quad(t):
        return 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2
    @staticmethod
    def ease_out_back(t):
        c1 = 1.70158; c3 = c1 + 1
        return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)
    @staticmethod
    def ease_out_elastic(t):
        if t == 0 or t == 1: return t
        c4 = (2 * math.pi) / 3
        return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1
    @staticmethod
    def ease_in_back(t):
        c1 = 1.70158; c3 = c1 + 1
        return c3 * t * t * t - c1 * t * t
    @staticmethod
    def ease_out_bounce(t):
        n1 = 7.5625; d1 = 2.75
        if t < 1 / d1: return n1 * t * t
        elif t < 2 / d1: t -= 1.5 / d1; return n1 * t * t + 0.75
        elif t < 2.5 / d1: t -= 2.25 / d1; return n1 * t * t + 0.9375
        else: t -= 2.625 / d1; return n1 * t * t + 0.984375
    @staticmethod
    def anticipate_overshoot(t):
        if t < 0.2: return -0.5 * Easing.ease_out_quad(t / 0.2)
        else: adjusted = (t - 0.2) / 0.8; return -0.5 + 1.5 * Easing.ease_out_back(adjusted)
    @staticmethod
    def ease_out_expo(t):
        return 0 if t == 0 else 1 - pow(2, -10 * t)
    @staticmethod
    def ease_in_expo(t):
        return 0 if t == 0 else pow(2, 10 * t - 10)
    @staticmethod
    def ease_spring(t):
        return 1 - math.exp(-6 * t) * math.cos(12 * t)
    @staticmethod
    def ease_snap(t):
        return t * t * (3 - 2 * t) if t < 0.8 else 1 + (t - 0.8) * 0.5 * math.sin((t - 0.8) * 20)


class AttackPhase(Enum):
    ANTICIPATION = "anticipation"
    ATTACK = "attack"
    IMPACT = "impact"
    FOLLOW_THROUGH = "follow"
    RECOVERY = "recovery"


@dataclass
class WeaponAnimationProfile:
    anticipation_time: float = 0.08
    attack_time: float = 0.12
    impact_time: float = 0.03
    follow_through_time: float = 0.1
    recovery_time: float = 0.12
    anticipation_angle: float = -45
    attack_angle: float = 120
    follow_through_angle: float = 30
    anticipation_scale: float = 0.85
    attack_scale: float = 1.15
    impact_scale: float = 0.9
    trail_enabled: bool = True
    trail_length: int = 8
    trail_fade: float = 0.8
    shake_on_impact: bool = True
    shake_intensity: float = 3.0
    anticipation_easing: str = "ease_out_quad"
    attack_easing: str = "ease_out_back"
    recovery_easing: str = "ease_in_out_quad"
    # v2.0
    glow_enabled: bool = False
    glow_radius: int = 12
    glow_color: Tuple = (255, 255, 200)
    glow_pulse_speed: float = 2.0
    motion_blur_enabled: bool = False
    motion_blur_frames: int = 4
    spark_on_impact: bool = False
    spark_count: int = 8
    spark_color: Tuple = (255, 220, 80)
    trail_width_start: int = 6
    trail_width_end: int = 1
    trail_color_shift: bool = False

    @property
    def total_time(self):
        return (self.anticipation_time + self.attack_time +
                self.impact_time + self.follow_through_time + self.recovery_time)


# Perfis base
WEAPON_PROFILES = {
    "Reta": WeaponAnimationProfile(
        anticipation_time=0.10, attack_time=0.11, impact_time=0.025,
        follow_through_time=0.09, recovery_time=0.14,
        anticipation_angle=-55, attack_angle=135, follow_through_angle=28,
        anticipation_scale=0.86, attack_scale=1.24,
        trail_length=12, shake_intensity=4.5, attack_easing="ease_out_back",
        glow_enabled=True, glow_radius=8, glow_color=(220, 230, 255),
        trail_width_start=5, trail_width_end=1,
        spark_on_impact=True, spark_count=6, spark_color=(200, 210, 255),
    ),
    "Dupla": WeaponAnimationProfile(
        anticipation_time=0.04, attack_time=0.065, impact_time=0.015,
        follow_through_time=0.04, recovery_time=0.065,
        anticipation_angle=-30, attack_angle=90, follow_through_angle=12,
        anticipation_scale=0.95, attack_scale=1.14,
        trail_length=7, shake_intensity=2.2, attack_easing="ease_out_expo",
        glow_enabled=True, glow_radius=6, glow_color=(180, 240, 255),
        motion_blur_enabled=True, motion_blur_frames=4,
        trail_width_start=4, trail_width_end=1,
        spark_on_impact=True, spark_count=5,
    ),
    "Corrente": WeaponAnimationProfile(
        anticipation_time=0.20, attack_time=0.25, impact_time=0.05,
        follow_through_time=0.20, recovery_time=0.25,
        anticipation_angle=-100, attack_angle=240, follow_through_angle=80,
        anticipation_scale=0.75, attack_scale=1.40,
        trail_length=22, shake_intensity=8.0,
        attack_easing="ease_out_back", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=14, glow_color=(100, 255, 100),
        motion_blur_enabled=True, motion_blur_frames=6,
        trail_width_start=8, trail_width_end=2,
        spark_on_impact=True, spark_count=14, spark_color=(100, 255, 100),
        trail_color_shift=True,
    ),
    "Arremesso": WeaponAnimationProfile(
        anticipation_time=0.13, attack_time=0.055, impact_time=0.0,
        follow_through_time=0.11, recovery_time=0.16,
        anticipation_angle=-65, attack_angle=85, follow_through_angle=45,
        anticipation_scale=0.82, attack_scale=1.28,
        trail_enabled=False, shake_intensity=0.0, attack_easing="ease_out_expo",
        glow_enabled=True, glow_radius=10, glow_color=(255, 200, 80),
    ),
    "Arco": WeaponAnimationProfile(
        anticipation_time=0.28, attack_time=0.04, impact_time=0.0,
        follow_through_time=0.09, recovery_time=0.22,
        anticipation_angle=-12, attack_angle=6, follow_through_angle=4,
        anticipation_scale=1.20, attack_scale=0.86,
        trail_enabled=False, shake_intensity=1.8,
        anticipation_easing="ease_in_out_quad", attack_easing="ease_out_elastic",
        glow_enabled=True, glow_radius=16, glow_color=(255, 230, 120),
        glow_pulse_speed=3.0,
    ),
    "Orbital": WeaponAnimationProfile(
        anticipation_time=0.0, attack_time=0.16, impact_time=0.025,
        follow_through_time=0.12, recovery_time=0.0,
        anticipation_angle=0, attack_angle=360, follow_through_angle=0,
        anticipation_scale=1.0, attack_scale=1.10,
        trail_length=26, shake_intensity=2.8, attack_easing="linear",
        glow_enabled=True, glow_radius=20, glow_color=(120, 180, 255),
        glow_pulse_speed=4.0,
        trail_width_start=7, trail_width_end=1,
        spark_on_impact=True, spark_count=10,
    ),
    "Magica": WeaponAnimationProfile(
        anticipation_time=0.12, attack_time=0.17, impact_time=0.06,
        follow_through_time=0.12, recovery_time=0.17,
        anticipation_angle=-22, attack_angle=65, follow_through_angle=22,
        anticipation_scale=0.62, attack_scale=1.50,
        trail_length=16, shake_intensity=3.8,
        attack_easing="ease_out_elastic", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=22, glow_color=(200, 100, 255),
        glow_pulse_speed=5.0,
        trail_width_start=6, trail_width_end=1,
        spark_on_impact=True, spark_count=16, spark_color=(220, 100, 255),
        trail_color_shift=True,
    ),
    "Transformavel": WeaponAnimationProfile(
        anticipation_time=0.09, attack_time=0.16, impact_time=0.035,
        follow_through_time=0.13, recovery_time=0.16,
        anticipation_angle=-42, attack_angle=115, follow_through_angle=32,
        anticipation_scale=0.83, attack_scale=1.26,
        trail_length=13, shake_intensity=4.8,
        attack_easing="anticipate_overshoot",
        glow_enabled=True, glow_radius=10, glow_color=(255, 180, 80),
        spark_on_impact=True, spark_count=8,
    ),
}
WEAPON_PROFILES["Mágica"] = WEAPON_PROFILES["Magica"]
WEAPON_PROFILES["Transformável"] = WEAPON_PROFILES["Transformavel"]


STYLE_PROFILES = {
    # ── RETA ──
    "Katana": WeaponAnimationProfile(
        anticipation_time=0.20, attack_time=0.065, impact_time=0.04,
        follow_through_time=0.05, recovery_time=0.22,
        anticipation_angle=-90, attack_angle=120, follow_through_angle=15,
        anticipation_scale=0.80, attack_scale=1.30, trail_length=16,
        shake_intensity=5.5, attack_easing="ease_out_expo", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=10, glow_color=(200, 220, 255),
        motion_blur_enabled=True, motion_blur_frames=5,
        trail_width_start=6, trail_width_end=1,
        spark_on_impact=True, spark_count=10, spark_color=(220, 230, 255),
    ),
    "Montante": WeaponAnimationProfile(
        anticipation_time=0.24, attack_time=0.19, impact_time=0.055,
        follow_through_time=0.17, recovery_time=0.26,
        anticipation_angle=-78, attack_angle=170, follow_through_angle=42,
        anticipation_scale=0.75, attack_scale=1.42, trail_length=18,
        shake_intensity=9.0, attack_easing="ease_out_back", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=14, glow_color=(220, 200, 160),
        trail_width_start=8, trail_width_end=2,
        spark_on_impact=True, spark_count=14, spark_color=(255, 220, 100),
    ),
    "Claymore": WeaponAnimationProfile(
        anticipation_time=0.28, attack_time=0.22, impact_time=0.065,
        follow_through_time=0.19, recovery_time=0.30,
        anticipation_angle=-85, attack_angle=190, follow_through_angle=52,
        anticipation_scale=0.70, attack_scale=1.46, trail_length=20,
        shake_intensity=12.0, attack_easing="ease_out_back", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=16, glow_color=(200, 180, 140),
        trail_width_start=10, trail_width_end=2,
        spark_on_impact=True, spark_count=18, spark_color=(255, 200, 80),
        trail_color_shift=True,
    ),
    "Lança": WeaponAnimationProfile(
        anticipation_time=0.12, attack_time=0.065, impact_time=0.028,
        follow_through_time=0.055, recovery_time=0.14,
        anticipation_angle=-38, attack_angle=48, follow_through_angle=9,
        anticipation_scale=0.90, attack_scale=1.20, trail_length=9,
        shake_intensity=3.8, attack_easing="ease_out_expo",
        glow_enabled=True, glow_radius=8, glow_color=(220, 240, 200),
        motion_blur_enabled=True, motion_blur_frames=4,
        trail_width_start=5, trail_width_end=1,
        spark_on_impact=True, spark_count=6,
    ),
    "Alabarda": WeaponAnimationProfile(
        anticipation_time=0.17, attack_time=0.16, impact_time=0.042,
        follow_through_time=0.13, recovery_time=0.21,
        anticipation_angle=-68, attack_angle=160, follow_through_angle=37,
        anticipation_scale=0.80, attack_scale=1.33, trail_length=15,
        shake_intensity=6.0, attack_easing="ease_out_back",
        glow_enabled=True, glow_radius=12, glow_color=(200, 220, 180),
        trail_width_start=7, trail_width_end=2,
        spark_on_impact=True, spark_count=10,
    ),
    "Martelo": WeaponAnimationProfile(
        anticipation_time=0.30, attack_time=0.15, impact_time=0.09,
        follow_through_time=0.08, recovery_time=0.32,
        anticipation_angle=-95, attack_angle=115, follow_through_angle=22,
        anticipation_scale=0.68, attack_scale=1.55, trail_length=13,
        shake_intensity=14.0, attack_easing="ease_out_expo", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=18, glow_color=(255, 180, 60),
        trail_width_start=9, trail_width_end=2,
        spark_on_impact=True, spark_count=20, spark_color=(255, 160, 40),
        trail_color_shift=True,
    ),
    "Foice": WeaponAnimationProfile(
        anticipation_time=0.16, attack_time=0.15, impact_time=0.042,
        follow_through_time=0.15, recovery_time=0.19,
        anticipation_angle=-62, attack_angle=165, follow_through_angle=42,
        anticipation_scale=0.80, attack_scale=1.35, trail_length=17,
        shake_intensity=6.5, attack_easing="ease_out_back",
        glow_enabled=True, glow_radius=12, glow_color=(180, 255, 120),
        trail_width_start=7, trail_width_end=1,
        spark_on_impact=True, spark_count=10, spark_color=(160, 255, 100),
    ),
    "Sabre": WeaponAnimationProfile(
        anticipation_time=0.09, attack_time=0.10, impact_time=0.022,
        follow_through_time=0.10, recovery_time=0.13,
        anticipation_angle=-50, attack_angle=148, follow_through_angle=32,
        anticipation_scale=0.87, attack_scale=1.27, trail_length=13,
        shake_intensity=3.8, attack_easing="ease_out_back",
        glow_enabled=True, glow_radius=9, glow_color=(255, 220, 160),
        motion_blur_enabled=True, motion_blur_frames=4,
        trail_width_start=5, trail_width_end=1,
        spark_on_impact=True, spark_count=7,
    ),
    "Maça": WeaponAnimationProfile(
        anticipation_time=0.20, attack_time=0.14, impact_time=0.055,
        follow_through_time=0.11, recovery_time=0.24,
        anticipation_angle=-72, attack_angle=130, follow_through_angle=27,
        anticipation_scale=0.78, attack_scale=1.38, trail_length=11,
        shake_intensity=8.0, attack_easing="ease_out_back", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=13, glow_color=(200, 180, 150),
        trail_width_start=7, trail_width_end=2,
        spark_on_impact=True, spark_count=12, spark_color=(240, 200, 120),
    ),
    "Machado": WeaponAnimationProfile(
        anticipation_time=0.17, attack_time=0.13, impact_time=0.042,
        follow_through_time=0.12, recovery_time=0.21,
        anticipation_angle=-70, attack_angle=140, follow_through_angle=32,
        anticipation_scale=0.78, attack_scale=1.38, trail_length=12,
        shake_intensity=7.0, attack_easing="ease_out_back", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=12, glow_color=(220, 160, 100),
        trail_width_start=7, trail_width_end=2,
        spark_on_impact=True, spark_count=11, spark_color=(255, 180, 80),
    ),

    # ── ADAGAS GÊMEAS v3.0 - KARAMBIT CROSS-SLASH COMBO ──
    "Adagas Gêmeas": WeaponAnimationProfile(
        anticipation_time=0.018, attack_time=0.038, impact_time=0.008,
        follow_through_time=0.018, recovery_time=0.038,
        anticipation_angle=-30, attack_angle=85, follow_through_angle=10,
        anticipation_scale=0.96, attack_scale=1.22,
        trail_length=12, shake_intensity=2.2,
        attack_easing="ease_out_expo",
        glow_enabled=True, glow_radius=10, glow_color=(160, 230, 255),
        glow_pulse_speed=8.0,
        motion_blur_enabled=True, motion_blur_frames=6,
        trail_width_start=6, trail_width_end=1,
        trail_color_shift=True,
        spark_on_impact=True, spark_count=8, spark_color=(180, 240, 255),
    ),
    "Garras": WeaponAnimationProfile(
        anticipation_time=0.04, attack_time=0.055, impact_time=0.012,
        follow_through_time=0.035, recovery_time=0.060,
        anticipation_angle=-25, attack_angle=78, follow_through_angle=16,
        anticipation_scale=0.94, attack_scale=1.18, trail_length=8,
        shake_intensity=2.8, attack_easing="ease_out_elastic",
        glow_enabled=True, glow_radius=8, glow_color=(200, 160, 255),
        motion_blur_enabled=True, motion_blur_frames=4,
        trail_width_start=5, trail_width_end=1,
        spark_on_impact=True, spark_count=6,
    ),
    "Tonfas": WeaponAnimationProfile(
        anticipation_time=0.055, attack_time=0.075, impact_time=0.018,
        follow_through_time=0.05, recovery_time=0.085,
        anticipation_angle=-40, attack_angle=105, follow_through_angle=20,
        anticipation_scale=0.91, attack_scale=1.20, trail_length=7,
        shake_intensity=3.2, attack_easing="ease_out_back",
        glow_enabled=True, glow_radius=8, glow_color=(200, 220, 200),
        trail_width_start=5, trail_width_end=1,
        spark_on_impact=True, spark_count=7,
    ),

    # ── MANGUAL v3.1 - HEAVY SLAM & GROUND POUND ──
    # Golpes pesados que tremem o chão. Sem spin: overheads e sweeps.
    "Mangual": WeaponAnimationProfile(
        anticipation_time=0.32, attack_time=0.18, impact_time=0.12,
        follow_through_time=0.14, recovery_time=0.30,
        anticipation_angle=-100, attack_angle=140, follow_through_angle=25,
        anticipation_scale=0.65, attack_scale=1.55, impact_scale=0.80,
        trail_length=20, shake_intensity=20.0,
        attack_easing="ease_in_expo", anticipation_easing="ease_in_back",
        recovery_easing="ease_out_back",
        glow_enabled=True, glow_radius=22, glow_color=(100, 220, 80),
        glow_pulse_speed=0.8,
        motion_blur_enabled=True, motion_blur_frames=7,
        trail_width_start=14, trail_width_end=3,
        trail_color_shift=True,
        spark_on_impact=True, spark_count=32, spark_color=(140, 255, 100),
    ),
    "Chicote": WeaponAnimationProfile(
        anticipation_time=0.13, attack_time=0.11, impact_time=0.028,
        follow_through_time=0.11, recovery_time=0.16,
        anticipation_angle=-78, attack_angle=192, follow_through_angle=58,
        anticipation_scale=0.83, attack_scale=1.30, trail_length=18,
        shake_intensity=5.0, attack_easing="ease_out_back",
        glow_enabled=True, glow_radius=10, glow_color=(220, 200, 140),
        trail_width_start=6, trail_width_end=1,
        spark_on_impact=True, spark_count=9, spark_color=(255, 220, 100),
    ),
    "Meteor Hammer": WeaponAnimationProfile(
        anticipation_time=0.0, attack_time=0.28, impact_time=0.07,
        follow_through_time=0.22, recovery_time=0.0,
        anticipation_angle=0, attack_angle=360, follow_through_angle=0,
        anticipation_scale=1.0, attack_scale=1.18, trail_length=26,
        shake_intensity=11.0, attack_easing="linear",
        glow_enabled=True, glow_radius=18, glow_color=(255, 100, 60),
        glow_pulse_speed=5.0,
        motion_blur_enabled=True, motion_blur_frames=7,
        trail_width_start=10, trail_width_end=2,
        spark_on_impact=True, spark_count=20, spark_color=(255, 120, 60),
        trail_color_shift=True,
    ),

    # ── ARREMESSO ──
    "Shuriken": WeaponAnimationProfile(
        anticipation_time=0.07, attack_time=0.038, impact_time=0.0,
        follow_through_time=0.065, recovery_time=0.09,
        anticipation_angle=-44, attack_angle=62, follow_through_angle=36,
        anticipation_scale=0.87, attack_scale=1.22,
        trail_enabled=False, shake_intensity=0.0, attack_easing="ease_out_expo",
        glow_enabled=True, glow_radius=9, glow_color=(200, 220, 255),
    ),
    "Chakram": WeaponAnimationProfile(
        anticipation_time=0.14, attack_time=0.058, impact_time=0.0,
        follow_through_time=0.12, recovery_time=0.18,
        anticipation_angle=-72, attack_angle=98, follow_through_angle=52,
        anticipation_scale=0.78, attack_scale=1.32,
        trail_enabled=False, shake_intensity=0.0, attack_easing="ease_out_expo",
        glow_enabled=True, glow_radius=14, glow_color=(255, 180, 80),
        glow_pulse_speed=6.0,
    ),

    # ── ARCO ──
    "Arco Longo": WeaponAnimationProfile(
        anticipation_time=0.38, attack_time=0.035, impact_time=0.0,
        follow_through_time=0.10, recovery_time=0.26,
        anticipation_angle=-14, attack_angle=7, follow_through_angle=5,
        anticipation_scale=1.24, attack_scale=0.84,
        trail_enabled=False, shake_intensity=2.2,
        anticipation_easing="ease_in_out_quad", attack_easing="ease_out_elastic",
        glow_enabled=True, glow_radius=18, glow_color=(255, 240, 140),
        glow_pulse_speed=3.5,
    ),
    "Arco Élfico": WeaponAnimationProfile(
        anticipation_time=0.23, attack_time=0.036, impact_time=0.0,
        follow_through_time=0.08, recovery_time=0.19,
        anticipation_angle=-11, attack_angle=6, follow_through_angle=4,
        anticipation_scale=1.22, attack_scale=0.87,
        trail_enabled=False, shake_intensity=1.6,
        anticipation_easing="ease_in_out_quad", attack_easing="ease_out_elastic",
        glow_enabled=True, glow_radius=14, glow_color=(200, 255, 180),
        glow_pulse_speed=4.0,
    ),
    "Besta Pesada": WeaponAnimationProfile(
        anticipation_time=0.42, attack_time=0.028, impact_time=0.0,
        follow_through_time=0.08, recovery_time=0.32,
        anticipation_angle=-8, attack_angle=4, follow_through_angle=3,
        anticipation_scale=1.15, attack_scale=0.80,
        trail_enabled=False, shake_intensity=3.5,
        anticipation_easing="linear", attack_easing="ease_out_elastic",
        glow_enabled=True, glow_radius=16, glow_color=(220, 200, 160),
    ),

    # ── ORBITAL ──
    "Lâminas Orbitais": WeaponAnimationProfile(
        anticipation_time=0.0, attack_time=0.12, impact_time=0.022,
        follow_through_time=0.10, recovery_time=0.0,
        anticipation_angle=0, attack_angle=360, follow_through_angle=0,
        anticipation_scale=1.0, attack_scale=1.16, trail_length=26,
        shake_intensity=4.0, attack_easing="linear",
        glow_enabled=True, glow_radius=22, glow_color=(140, 200, 255),
        glow_pulse_speed=5.0,
        trail_width_start=8, trail_width_end=1,
        spark_on_impact=True, spark_count=12,
    ),
    "Orbes Místicos": WeaponAnimationProfile(
        anticipation_time=0.0, attack_time=0.19, impact_time=0.045,
        follow_through_time=0.14, recovery_time=0.0,
        anticipation_angle=0, attack_angle=360, follow_through_angle=0,
        anticipation_scale=1.0, attack_scale=1.12, trail_length=20,
        shake_intensity=2.5, attack_easing="ease_out_elastic",
        glow_enabled=True, glow_radius=26, glow_color=(180, 100, 255),
        glow_pulse_speed=6.0,
        trail_width_start=7, trail_width_end=1,
        spark_on_impact=True, spark_count=14, spark_color=(200, 120, 255),
    ),
    "Drones de Combate": WeaponAnimationProfile(
        anticipation_time=0.0, attack_time=0.10, impact_time=0.022,
        follow_through_time=0.08, recovery_time=0.0,
        anticipation_angle=0, attack_angle=360, follow_through_angle=0,
        anticipation_scale=1.0, attack_scale=1.14, trail_length=18,
        shake_intensity=2.2, attack_easing="linear",
        glow_enabled=True, glow_radius=16, glow_color=(100, 255, 200),
        trail_width_start=6, trail_width_end=1,
        spark_on_impact=True, spark_count=10,
    ),

    # ── MÁGICA ──
    "Espadas Espectrais": WeaponAnimationProfile(
        anticipation_time=0.09, attack_time=0.11, impact_time=0.045,
        follow_through_time=0.09, recovery_time=0.13,
        anticipation_angle=-40, attack_angle=135, follow_through_angle=27,
        anticipation_scale=0.68, attack_scale=1.54, trail_length=18,
        shake_intensity=4.5, attack_easing="ease_out_elastic", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=24, glow_color=(160, 120, 255),
        glow_pulse_speed=4.0,
        trail_width_start=7, trail_width_end=1,
        spark_on_impact=True, spark_count=16, spark_color=(180, 140, 255),
        trail_color_shift=True,
    ),
    "Tentáculos Sombrios": WeaponAnimationProfile(
        anticipation_time=0.11, attack_time=0.19, impact_time=0.055,
        follow_through_time=0.15, recovery_time=0.19,
        anticipation_angle=-30, attack_angle=192, follow_through_angle=48,
        anticipation_scale=0.70, attack_scale=1.44, trail_length=17,
        shake_intensity=3.5, attack_easing="ease_out_elastic", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=20, glow_color=(60, 20, 120),
        trail_width_start=7, trail_width_end=1,
        spark_on_impact=True, spark_count=12, spark_color=(120, 60, 200),
        trail_color_shift=True,
    ),
    "Chamas Espirituais": WeaponAnimationProfile(
        anticipation_time=0.15, attack_time=0.16, impact_time=0.075,
        follow_through_time=0.13, recovery_time=0.17,
        anticipation_angle=-26, attack_angle=74, follow_through_angle=27,
        anticipation_scale=0.58, attack_scale=1.58, trail_length=17,
        shake_intensity=5.0, attack_easing="ease_out_elastic", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=28, glow_color=(255, 120, 40),
        glow_pulse_speed=7.0,
        trail_width_start=8, trail_width_end=1,
        spark_on_impact=True, spark_count=20, spark_color=(255, 140, 40),
        trail_color_shift=True,
    ),
    "Runas Flutuantes": WeaponAnimationProfile(
        anticipation_time=0.17, attack_time=0.14, impact_time=0.065,
        follow_through_time=0.11, recovery_time=0.19,
        anticipation_angle=-20, attack_angle=58, follow_through_angle=19,
        anticipation_scale=0.65, attack_scale=1.50, trail_length=15,
        shake_intensity=4.0, attack_easing="ease_out_elastic", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=22, glow_color=(100, 200, 255),
        glow_pulse_speed=5.5,
        trail_width_start=6, trail_width_end=1,
        spark_on_impact=True, spark_count=14,
    ),
    "Lanças de Mana": WeaponAnimationProfile(
        anticipation_time=0.13, attack_time=0.09, impact_time=0.042,
        follow_through_time=0.08, recovery_time=0.15,
        anticipation_angle=-30, attack_angle=47, follow_through_angle=13,
        anticipation_scale=0.70, attack_scale=1.48, trail_length=13,
        shake_intensity=4.5, attack_easing="ease_out_expo", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=18, glow_color=(80, 180, 255),
        motion_blur_enabled=True, motion_blur_frames=5,
        trail_width_start=6, trail_width_end=1,
        spark_on_impact=True, spark_count=12, spark_color=(100, 200, 255),
    ),
    "Cristais Arcanos": WeaponAnimationProfile(
        anticipation_time=0.15, attack_time=0.13, impact_time=0.055,
        follow_through_time=0.11, recovery_time=0.17,
        anticipation_angle=-22, attack_angle=58, follow_through_angle=19,
        anticipation_scale=0.65, attack_scale=1.50, trail_length=15,
        shake_intensity=4.0, attack_easing="ease_out_elastic", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=22, glow_color=(180, 220, 255),
        glow_pulse_speed=5.0,
        trail_width_start=6, trail_width_end=1,
        spark_on_impact=True, spark_count=14, spark_color=(200, 230, 255),
        trail_color_shift=True,
    ),

    # ── TRANSFORMÁVEL ──
    "Chicote-Espada": WeaponAnimationProfile(
        anticipation_time=0.11, attack_time=0.17, impact_time=0.042,
        follow_through_time=0.16, recovery_time=0.19,
        anticipation_angle=-60, attack_angle=170, follow_through_angle=48,
        anticipation_scale=0.78, attack_scale=1.38, trail_length=15,
        shake_intensity=6.0, attack_easing="anticipate_overshoot",
        glow_enabled=True, glow_radius=12, glow_color=(220, 180, 100),
        trail_width_start=7, trail_width_end=1,
        spark_on_impact=True, spark_count=11,
    ),
    "Arco-Lâminas": WeaponAnimationProfile(
        anticipation_time=0.13, attack_time=0.15, impact_time=0.032,
        follow_through_time=0.13, recovery_time=0.17,
        anticipation_angle=-52, attack_angle=128, follow_through_angle=32,
        anticipation_scale=0.83, attack_scale=1.30, trail_length=13,
        shake_intensity=5.0, attack_easing="anticipate_overshoot",
        glow_enabled=True, glow_radius=12, glow_color=(200, 240, 180),
        trail_width_start=6, trail_width_end=1,
        spark_on_impact=True, spark_count=9,
    ),
    "Machado-Martelo": WeaponAnimationProfile(
        anticipation_time=0.24, attack_time=0.19, impact_time=0.075,
        follow_through_time=0.16, recovery_time=0.28,
        anticipation_angle=-78, attack_angle=155, follow_through_angle=42,
        anticipation_scale=0.70, attack_scale=1.48, trail_length=15,
        shake_intensity=12.0, attack_easing="ease_out_back", anticipation_easing="ease_in_back",
        glow_enabled=True, glow_radius=16, glow_color=(255, 160, 60),
        trail_width_start=9, trail_width_end=2,
        spark_on_impact=True, spark_count=18, spark_color=(255, 180, 60),
    ),
    "Bastão Segmentado": WeaponAnimationProfile(
        anticipation_time=0.15, attack_time=0.17, impact_time=0.042,
        follow_through_time=0.15, recovery_time=0.19,
        anticipation_angle=-57, attack_angle=160, follow_through_angle=42,
        anticipation_scale=0.80, attack_scale=1.34, trail_length=14,
        shake_intensity=5.5, attack_easing="ease_out_back",
        glow_enabled=True, glow_radius=11, glow_color=(200, 200, 180),
        trail_width_start=7, trail_width_end=1,
        spark_on_impact=True, spark_count=10,
    ),
}


def get_animation_profile(weapon_type: str, weapon_style: str = "") -> WeaponAnimationProfile:
    if weapon_style and weapon_style in STYLE_PROFILES:
        return STYLE_PROFILES[weapon_style]
    return WEAPON_PROFILES.get(weapon_type, WEAPON_PROFILES["Reta"])


@dataclass
class WeaponAnimationState:
    is_attacking: bool = False
    attack_timer: float = 0.0
    current_phase: AttackPhase = AttackPhase.RECOVERY
    angle_offset: float = 0.0
    scale: float = 1.0
    shake_offset: Tuple = (0.0, 0.0)
    trail_positions: List = field(default_factory=list)
    attack_pattern: int = 0
    draw_amount: float = 0.0
    chain_momentum: float = 0.0
    pulse_phase: float = 0.0
    # v2.0
    glow_intensity: float = 0.0
    motion_blur_positions: List = field(default_factory=list)
    mangual_spin_speed: float = 0.0
    dagger_side: int = 0
    combo_count: int = 0
    impact_burst_timer: float = 0.0
    spark_list: List = field(default_factory=list)


class WeaponAnimator:
    def __init__(self):
        self.states = {}
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
            "ease_out_expo": Easing.ease_out_expo,
            "ease_in_expo": Easing.ease_in_expo,
            "ease_spring": Easing.ease_spring,
            "ease_snap": Easing.ease_snap,
        }

    def get_state(self, fighter_id):
        if fighter_id not in self.states:
            self.states[fighter_id] = WeaponAnimationState()
        return self.states[fighter_id]

    def start_attack(self, fighter_id, weapon_type, weapon_style=""):
        state = self.get_state(fighter_id)
        if weapon_style == "Mangual" or weapon_type == "Corrente":
            if not state.is_attacking and state.mangual_spin_speed > 0:
                state.mangual_spin_speed = min(state.mangual_spin_speed * 1.3, 5.0)
            else:
                state.mangual_spin_speed = 1.0
        if weapon_style == "Adagas Gêmeas":
            state.dagger_side = 1 - state.dagger_side
            state.combo_count = min(state.combo_count + 1, 8)
        state.is_attacking = True
        state.attack_timer = 0.0
        state.current_phase = AttackPhase.ANTICIPATION
        state.trail_positions = []
        state.motion_blur_positions = []
        state.attack_pattern = (state.attack_pattern + 1) % 3
        state.impact_burst_timer = 0.0

    def update(self, dt, fighter_id, weapon_type, base_angle, weapon_tip_pos, weapon_style=""):
        state = self.get_state(fighter_id)
        profile = get_animation_profile(weapon_type, weapon_style)

        if state.is_attacking:
            state.attack_timer += dt
            self._update_attack_animation(state, profile, base_angle, weapon_type, weapon_style)
            if profile.trail_enabled:
                state.trail_positions.append((weapon_tip_pos[0], weapon_tip_pos[1], 1.0))
                if len(state.trail_positions) > profile.trail_length:
                    state.trail_positions.pop(0)
                for i in range(len(state.trail_positions)):
                    x, y, a = state.trail_positions[i]
                    state.trail_positions[i] = (x, y, a * profile.trail_fade)
            if profile.motion_blur_enabled:
                state.motion_blur_positions.append(weapon_tip_pos)
                if len(state.motion_blur_positions) > profile.motion_blur_frames:
                    state.motion_blur_positions.pop(0)
        else:
            self._update_idle_animation(state, weapon_type, weapon_style, dt)
            if weapon_style == "Mangual" or weapon_type == "Corrente":
                state.mangual_spin_speed = max(0.0, state.mangual_spin_speed - dt * 0.8)
            if state.trail_positions:
                new_trail = [(x, y, a * 0.82) for x, y, a in state.trail_positions if a * 0.82 > 0.04]
                state.trail_positions = new_trail
            state.motion_blur_positions = []

        if profile.glow_enabled:
            state.pulse_phase += dt * profile.glow_pulse_speed
            if state.is_attacking:
                state.glow_intensity = min(1.0, state.glow_intensity + dt * 5.0)
            else:
                state.glow_intensity = 0.3 + 0.2 * math.sin(state.pulse_phase)

        self._update_sparks(state, dt)
        return state

    def _get_phase(self, state, profile):
        t = state.attack_timer
        phase_times = [
            (AttackPhase.ANTICIPATION, profile.anticipation_time),
            (AttackPhase.ATTACK, profile.attack_time),
            (AttackPhase.IMPACT, profile.impact_time),
            (AttackPhase.FOLLOW_THROUGH, profile.follow_through_time),
            (AttackPhase.RECOVERY, profile.recovery_time),
        ]
        elapsed = 0.0
        for phase, duration in phase_times:
            if t < elapsed + duration:
                progress = (t - elapsed) / max(duration, 0.001)
                return phase, progress
            elapsed += duration
        return AttackPhase.RECOVERY, 1.0

    def _update_attack_animation(self, state, profile, base_angle, weapon_type="", weapon_style=""):
        current_phase, phase_progress = self._get_phase(state, profile)
        state.current_phase = current_phase

        if weapon_style == "Mangual":
            self._update_mangual(state, profile, current_phase, phase_progress)
            return
        if weapon_style == "Adagas Gêmeas":
            self._update_dagger(state, profile, current_phase, phase_progress)
            return

        direction = 1 if state.attack_pattern % 2 == 0 else -1
        if current_phase == AttackPhase.ANTICIPATION:
            prog = self.easings.get(profile.anticipation_easing, Easing.ease_out_quad)(phase_progress)
            state.angle_offset = profile.anticipation_angle * prog * direction
            state.scale = 1.0 + (profile.anticipation_scale - 1.0) * prog
        elif current_phase == AttackPhase.ATTACK:
            prog = self.easings.get(profile.attack_easing, Easing.ease_out_back)(phase_progress)
            start = profile.anticipation_angle * direction
            end = profile.attack_angle * direction
            state.angle_offset = start + (end - start) * prog
            scale_prog = math.sin(phase_progress * math.pi)
            state.scale = 1.0 + (profile.attack_scale - 1.0) * scale_prog
        elif current_phase == AttackPhase.IMPACT:
            state.angle_offset = profile.attack_angle * direction
            state.scale = profile.impact_scale
            if profile.shake_on_impact:
                shake = profile.shake_intensity * (1 - phase_progress)
                state.shake_offset = (random.uniform(-shake, shake), random.uniform(-shake, shake))
            if profile.spark_on_impact and phase_progress < 0.1:
                self._spawn_sparks(state, profile)
        elif current_phase == AttackPhase.FOLLOW_THROUGH:
            prog = Easing.ease_out_quad(phase_progress)
            state.angle_offset = profile.attack_angle * direction + profile.follow_through_angle * direction * (1 - prog)
            state.scale = profile.impact_scale + (1.0 - profile.impact_scale) * prog
            state.shake_offset = (0, 0)
        elif current_phase == AttackPhase.RECOVERY:
            prog = self.easings.get(profile.recovery_easing, Easing.ease_in_out_quad)(phase_progress)
            start = (profile.attack_angle + profile.follow_through_angle) * direction
            state.angle_offset = start * (1 - prog)
            state.scale = 1.0
            if phase_progress >= 1.0:
                state.is_attacking = False
                state.angle_offset = 0

    def _update_mangual(self, state, profile, current_phase, phase_progress):
        """v3.1 - Heavy Slam & Ground Pound
        
        Mecânica de golpes pesados: overhead → smash down.
        Cada attack_pattern define o tipo de golpe:
          0 = OVERHEAD SLAM (levanta alto, desce vertical)
          1 = SIDE SWEEP    (horizontal, arco largo de um lado ao outro)
          2 = GROUND POUND  (bola cai em diagonal, ricochete no chão)

        Sensação: LENTO, PESADO, SATISFATÓRIO.
        O jogador sente cada impacto porque o shake é grande e o
        follow-through empurra o inimigo para longe.
        """
        pattern = state.attack_pattern % 3  # cicla entre 3 padrões

        # Direcção do swing por padrão
        if pattern == 0:   # OVERHEAD SLAM: de cima para baixo
            wind_up_ang  = -95   # levanta para cima/trás
            crash_ang    =  70   # desce para baixo/frente
            follow_ang   =  15   # ressalto leve
            slam_dir     =  1
        elif pattern == 1:  # SIDE SWEEP: varre horizontal
            wind_up_ang  = -80
            crash_ang    = 140
            follow_ang   =  30
            slam_dir     = 1 if state.attack_pattern % 4 < 2 else -1
        else:               # GROUND POUND: diagonal para baixo
            wind_up_ang  = -60
            crash_ang    =  90
            follow_ang   =  20
            slam_dir     = 1

        if current_phase == AttackPhase.ANTICIPATION:
            # Wind-up: levanta a bola pesada com esforço
            # ease_in_back = pequeno recuo antes de subir (bola balança para baixo primeiro)
            prog = Easing.ease_in_back(phase_progress)
            state.angle_offset = wind_up_ang * prog * slam_dir
            # Squash no corpo do personagem durante o levantamento
            state.scale = 1.0 + (profile.anticipation_scale - 1.0) * Easing.ease_in_quad(phase_progress)
            state.mangual_spin_speed = 0.2  # Quase parado - está se preparando

        elif current_phase == AttackPhase.ATTACK:
            # SLAM DOWN: Descida explosiva, aceleração gravitacional
            # ease_in_expo = começa devagar (inércia da bola), termina MUITO rápido
            prog = Easing.ease_in_expo(phase_progress)
            state.angle_offset = wind_up_ang * slam_dir + crash_ang * prog * slam_dir
            # Stretch da corrente na direção do golpe (whip effect)
            state.scale = 1.0 + (profile.attack_scale - 1.0) * math.sin(phase_progress * math.pi * 0.8)
            state.mangual_spin_speed = 0.5 + 2.5 * prog  # acelera na descida

        elif current_phase == AttackPhase.IMPACT:
            # IMPACTO: bola toca o alvo/chão. Tudo congela por um frame.
            total = wind_up_ang * slam_dir + crash_ang * slam_dir
            state.angle_offset = total
            state.scale = profile.impact_scale  # squash no impacto
            
            # Camera shake PESADO e assimétrico (sente como vibração de chão)
            if profile.shake_on_impact:
                shake_decay = 1.0 - Easing.ease_out_expo(phase_progress)
                shake_h = profile.shake_intensity * shake_decay * 2.2
                shake_v = profile.shake_intensity * shake_decay * 1.4
                state.shake_offset = (
                    random.uniform(-shake_h, shake_h),
                    random.uniform(-shake_v, shake_v) + shake_v * 0.5  # tendência para baixo
                )
            
            # Sparks e poeira no frame do impacto
            if phase_progress < 0.06:
                self._spawn_sparks(state, profile)
                # Segundo burst de sparks um pouco depois (ricochete)
            elif 0.25 < phase_progress < 0.32:
                for _ in range(profile.spark_count // 4):
                    import random as _r
                    angle = _r.uniform(0, math.pi * 2)
                    speed = _r.uniform(30, 80)  # bounce mais lento
                    state.spark_list.append({
                        "vx": math.cos(angle) * speed,
                        "vy": math.sin(angle) * speed,
                        "life": _r.uniform(0.12, 0.22),
                        "timer": 0.0,
                        "size": _r.uniform(1.5, 3.5),
                        "color": profile.spark_color,
                    })

        elif current_phase == AttackPhase.FOLLOW_THROUGH:
            # Bola ricocheia / escorrega após o impacto
            prog = Easing.ease_out_back(phase_progress)  # pequeno overshoot (bounce)
            total = wind_up_ang * slam_dir + crash_ang * slam_dir
            state.angle_offset = total + follow_ang * slam_dir * prog
            # Escala volta ao normal com um leve bounce
            state.scale = profile.impact_scale + (1.0 - profile.impact_scale) * Easing.ease_out_bounce(phase_progress)
            # Shake residual que vai morrendo
            if profile.shake_on_impact and phase_progress < 0.4:
                residual = profile.shake_intensity * 0.25 * (1.0 - phase_progress / 0.4)
                state.shake_offset = (
                    random.uniform(-residual, residual),
                    random.uniform(-residual, residual)
                )
            else:
                state.shake_offset = (0, 0)
            state.mangual_spin_speed = max(0.1, state.mangual_spin_speed * (1.0 - phase_progress * 0.5))

        elif current_phase == AttackPhase.RECOVERY:
            # Volta à posição de guarda com peso (não é rápido - a bola é pesada)
            prog = Easing.ease_out_quad(phase_progress)
            total = wind_up_ang * slam_dir + crash_ang * slam_dir + follow_ang * slam_dir
            # Pequena oscilação pendular durante o retorno
            pendulum = math.sin(phase_progress * math.pi * 2) * (1.0 - phase_progress) * 8
            state.angle_offset = total * (1.0 - prog) + pendulum
            state.scale = 1.0
            state.shake_offset = (0, 0)
            state.mangual_spin_speed = max(0.0, state.mangual_spin_speed * 0.85)
            if phase_progress >= 1.0:
                state.is_attacking = False
                state.angle_offset = 0

    def _update_dagger(self, state, profile, current_phase, phase_progress):
        """v3.0 - Karambit Cross-Slash Combo System
        
        Sistema de combo karambit com lâmina reversa:
        - Alternação L/R em padrão X (cross-slash)  
        - Cada hit acumula COMBO_COUNT que acelera a velocidade
        - A partir de combo 3+: FRENZY MODE (spring recovery ultra-rápida)
        - Combo 6+: CROSS-X simultâneo (duas dagas juntas)
        - Dash-stab disponível como ataque de gap-closer
        """
        side_dir = 1 if state.dagger_side == 0 else -1
        # Combo multiplier: +15% por hit, máximo 8 hits (2.0x no pico)
        combo_mult = 1.0 + min(state.combo_count, 8) * 0.125
        # Frenzy threshold: combo >= 4
        in_frenzy = state.combo_count >= 4
        # Cross-slash mode: combo >= 6 (usa as duas ao mesmo tempo)
        cross_mode = state.combo_count >= 6

        if current_phase == AttackPhase.ANTICIPATION:
            prog = Easing.ease_out_expo(phase_progress)
            # No frenzy, a antecipação é quase imperceptível
            ant_factor = 0.3 if in_frenzy else 0.8
            # Cross-mode: ambas as adagas recuam juntas
            if cross_mode:
                cross_pull = math.radians(-20) * prog
                state.angle_offset = profile.anticipation_angle * prog * ant_factor + cross_pull * 30
            else:
                state.angle_offset = profile.anticipation_angle * prog * side_dir * ant_factor
            state.scale = 1.0 + (profile.anticipation_scale - 1.0) * prog * ant_factor

        elif current_phase == AttackPhase.ATTACK:
            prog = Easing.ease_out_expo(phase_progress)
            # Cross-mode: ataque simultâneo em X
            if cross_mode:
                # Gira nas duas direções ao mesmo tempo (visual de X)
                cross_ang = profile.attack_angle * combo_mult * prog
                state.angle_offset = cross_ang * side_dir
            else:
                start_ang = profile.anticipation_angle * side_dir * 0.4
                end_ang = profile.attack_angle * side_dir * combo_mult
                state.angle_offset = start_ang + (end_ang - start_ang) * prog
            # Scale: stretch na direção do corte
            scale_prog = math.sin(phase_progress * math.pi)
            speed_scale_bonus = min(state.combo_count, 8) * 0.018
            state.scale = 1.0 + (profile.attack_scale + speed_scale_bonus - 1.0) * scale_prog

        elif current_phase == AttackPhase.IMPACT:
            # Impacto instantâneo (lâmina reversa tem snap natural)
            state.angle_offset = profile.attack_angle * side_dir
            state.scale = profile.impact_scale
            impact_decay = 1.0 - Easing.ease_out_quad(phase_progress)
            shake_mult = 1.5 if cross_mode else 1.0
            if profile.shake_on_impact:
                shake = profile.shake_intensity * impact_decay * shake_mult
                state.shake_offset = (random.uniform(-shake, shake),
                                      random.uniform(-shake, shake))
            if phase_progress < 0.12:
                self._spawn_sparks(state, profile)

        elif current_phase == AttackPhase.FOLLOW_THROUGH:
            prog = Easing.ease_out_quad(phase_progress)
            follow_ang = profile.follow_through_angle * side_dir
            # No frenzy: follow-through mínimo (está pronto para o próximo hit)
            follow_factor = 0.4 if in_frenzy else 1.0
            state.angle_offset = (profile.attack_angle * side_dir +
                                  follow_ang * (1.0 - prog) * follow_factor)
            state.scale = profile.impact_scale + (1.0 - profile.impact_scale) * prog
            state.shake_offset = (0, 0)

        elif current_phase == AttackPhase.RECOVERY:
            # Frenzy: spring ultra-rápida para o próximo combo
            if in_frenzy:
                prog = Easing.ease_spring(phase_progress)
                # Vibração característica do karambit (fio giratório)
                vibrate = math.sin(phase_progress * math.pi * 6) * (1 - phase_progress) * 6
                start = (profile.attack_angle + profile.follow_through_angle) * side_dir
                state.angle_offset = start * (1.0 - prog) + vibrate
            else:
                prog = Easing.ease_out_quad(phase_progress)
                start = (profile.attack_angle + profile.follow_through_angle) * side_dir
                state.angle_offset = start * (1.0 - prog)
            state.scale = 1.0
            if phase_progress >= 1.0:
                state.is_attacking = False
                state.angle_offset = 0

    def _spawn_sparks(self, state, profile):
        for _ in range(profile.spark_count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(50, 150)
            state.spark_list.append({
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": random.uniform(0.1, 0.25),
                "timer": 0.0,
                "size": random.uniform(2, 5),
                "color": profile.spark_color,
            })

    def _update_sparks(self, state, dt):
        state.spark_list = [s for s in state.spark_list if (s.update({"timer": s["timer"] + dt}) or True) and s["timer"] + dt < s["life"]]
        for s in state.spark_list:
            s["timer"] += dt
        state.spark_list = [s for s in state.spark_list if s["timer"] < s["life"]]

    def _update_idle_animation(self, state, weapon_type, weapon_style, dt):
        state.pulse_phase += dt * 2.0
        if weapon_type == "Orbital":
            state.scale = 1.0 + 0.04 * math.sin(state.pulse_phase * 2.0)
        elif weapon_type in ["Mágica", "Magica"]:
            state.scale = 1.0 + 0.07 * math.sin(state.pulse_phase * 1.5)
            state.angle_offset = 4 * math.sin(state.pulse_phase * 0.9)
        elif weapon_style == "Mangual":
            # v3.0: Bola pendula em figura-8 com spin contínuo lento
            # Oscilação pendular com dois componentes de frequência
            pendulum1 = math.sin(state.pulse_phase * 0.55) * 12
            pendulum2 = math.sin(state.pulse_phase * 1.1) * 4
            state.angle_offset = pendulum1 + pendulum2
            # Scale pulsa levemente (corrente esticando/contraindo)
            state.scale = 1.0 + 0.04 * math.sin(state.pulse_phase * 0.9)
            # Spin residual decai suavemente
            if state.mangual_spin_speed > 0.05:
                state.mangual_spin_speed *= (1.0 - dt * 0.4)
        elif weapon_style == "Adagas Gêmeas":
            # v3.0: Karambit idle - dagas rodam suavemente em posição de guarda
            # Micro-vibração de prontidão
            state.angle_offset = (3.5 * math.sin(state.pulse_phase * 3.5) +
                                  1.2 * math.sin(state.pulse_phase * 7.0))
            state.scale = 1.0 + 0.025 * abs(math.sin(state.pulse_phase * 2.8))
            # Decai combo no idle (karambit precisa de contato contínuo)
            decay_interval = 2 * math.pi
            if (state.pulse_phase % decay_interval) < dt * 2.2:
                state.combo_count = max(0, state.combo_count - 1)
        elif weapon_type == "Corrente":
            state.angle_offset = 7 * math.sin(state.pulse_phase * 0.5)
            state.scale = 1.0 + 0.02 * math.cos(state.pulse_phase * 0.8)
        else:
            state.scale = 1.0 + 0.025 * math.sin(state.pulse_phase)
            state.angle_offset = 1.5 * math.sin(state.pulse_phase * 0.7)


class WeaponTrailRenderer:
    def draw_trail(self, surface, trail_positions, weapon_color, weapon_type,
                   profile=None, weapon_style=""):
        if len(trail_positions) < 2:
            return
        if weapon_type in ["Mágica", "Magica"]:
            self._draw_magic_trail(surface, trail_positions, weapon_color)
        elif weapon_style == "Mangual":
            self._draw_mangual_trail(surface, trail_positions, weapon_color)
        elif weapon_style == "Adagas Gêmeas":
            self._draw_dagger_trail(surface, trail_positions, weapon_color)
        elif weapon_type == "Corrente":
            self._draw_chain_trail(surface, trail_positions, weapon_color)
        else:
            self._draw_slash_trail(surface, trail_positions, weapon_color, profile)

    def _draw_slash_trail(self, surface, positions, color, profile=None):
        n = len(positions)
        w_start = profile.trail_width_start if profile else 5
        w_end = profile.trail_width_end if profile else 1
        color_shift = profile.trail_color_shift if profile else False
        for i in range(n - 1):
            x1, y1, a1 = positions[i]
            x2, y2, a2 = positions[i + 1]
            alpha = int(min(a1, a2) * 180)
            if alpha < 8: continue
            ratio = i / max(n - 1, 1)
            width = max(1, int(w_end + (w_start - w_end) * ratio))
            if color_shift:
                cr = min(255, int(color[0] * (0.5 + 0.5 * ratio) + 80 * ratio))
                cg = min(255, int(color[1] * (0.5 + 0.5 * ratio) + 60 * ratio))
                cb = min(255, int(color[2] * (0.5 + 0.5 * ratio)))
            else:
                cr = min(255, color[0] + 40); cg = min(255, color[1] + 40); cb = min(255, color[2] + 40)
            blend = alpha / 255
            try:
                pygame.draw.line(surface, (int(cr*blend), int(cg*blend), int(cb*blend)),
                               (int(x1), int(y1)), (int(x2), int(y2)), width)
            except: pass

    def _draw_mangual_trail(self, surface, positions, color):
        """v3.0 - Heavy Flail trail: rastro de bola com corona de impacto"""
        n = len(positions)
        for i in range(n - 1):
            x1, y1, a1 = positions[i]; x2, y2, a2 = positions[i + 1]
            alpha = int(min(a1, a2) * 220)
            if alpha < 8: continue
            ratio = i / max(n - 1, 1)
            # Linha de corrente (mais fina)
            chain_w = max(1, int(5 * ratio))
            blend = alpha / 255
            # Cor que muda: verde escuro → verde brilhante → amarelo no impacto
            cr = int(min(255, color[0]*blend + 60*blend*(1-ratio) + 80*blend*ratio))
            cg = int(min(255, color[1]*blend + 30*blend))
            cb = int(color[2]*blend * 0.5)
            try:
                pygame.draw.line(surface, (cr, cg, cb),
                                 (int(x1), int(y1)), (int(x2), int(y2)), max(1, chain_w))
                # Bola de impacto a cada 4 segmentos (simula elos pesados)
                if i % 4 == 0 and ratio > 0.3:
                    ball_r = max(2, int(9 * ratio * (0.7 + 0.3 * math.sin(i * 0.8))))
                    pygame.draw.circle(surface, (cr, cg, cb), (int(x1), int(y1)), ball_r)
                    # Corona de glow na bola
                    if ratio > 0.7 and ball_r > 3:
                        try:
                            gs = pygame.Surface((ball_r * 4, ball_r * 4), pygame.SRCALPHA)
                            glow_a = int(alpha * 0.4 * ratio)
                            pygame.draw.circle(gs, (*color, min(255, glow_a)),
                                               (ball_r * 2, ball_r * 2), ball_r * 2)
                            surface.blit(gs, (int(x1) - ball_r * 2, int(y1) - ball_r * 2))
                        except: pass
            except: pass

    def _draw_dagger_trail(self, surface, positions, color):
        """v3.0 - Karambit trail: arco curvo + glow de energia + streak de velocidade"""
        n = len(positions)
        for i in range(n - 1):
            x1, y1, a1 = positions[i]; x2, y2, a2 = positions[i + 1]
            alpha = int(min(a1, a2) * 240)
            if alpha < 8: continue
            ratio = i / max(n - 1, 1)
            blend = alpha / 255
            # Streak de velocidade: linha mais larga e mais brilhante
            streak_w = max(1, int(5 * ratio))
            # Cor karambit: frio → quente dependendo do combo
            cr = int(min(255, color[0]*blend + 40*blend*(1-ratio)))
            cg = int(min(255, color[1]*blend + 60*blend))
            cb = int(min(255, color[2]*blend + 80*blend))
            try:
                # Streak principal
                pygame.draw.line(surface, (cr, cg, cb),
                                 (int(x1), int(y1)), (int(x2), int(y2)), max(1, streak_w))
                # Glow de arc energy na ponta do trail
                if ratio > 0.6:
                    gs_size = 14
                    gs = pygame.Surface((gs_size, gs_size), pygame.SRCALPHA)
                    glow_a = int(alpha * 0.55 * ratio)
                    # Glow menor e mais nítido (karambit é preciso, não bruto)
                    pygame.draw.circle(gs, (*color, min(255, glow_a)),
                                       (gs_size//2, gs_size//2), 5)
                    surface.blit(gs, (int(x2) - gs_size//2, int(y2) - gs_size//2))
                # Traço de fio da lâmina (linha central brilhante)
                if ratio > 0.4:
                    bright_a = int(alpha * 0.7)
                    bright_c = (min(255, cr + 60), min(255, cg + 60), min(255, cb + 60))
                    pygame.draw.line(surface, bright_c,
                                     (int(x1), int(y1)), (int(x2), int(y2)), 1)
            except: pass

    def _draw_magic_trail(self, surface, positions, color):
        for i, (x, y, a) in enumerate(positions):
            if a < 0.08: continue
            size = max(2, int(7 * a))
            bright = (min(255, color[0]+120), min(255, color[1]+80), min(255, color[2]+80))
            try:
                pygame.draw.circle(surface, bright, (int(x), int(y)), size)
                gs = int(size * 2.5)
                if gs > 0:
                    s = pygame.Surface((gs*2, gs*2), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*color, int(70*a)), (gs, gs), gs)
                    surface.blit(s, (int(x-gs), int(y-gs)))
            except: pass

    def _draw_chain_trail(self, surface, positions, color):
        if len(positions) < 2: return
        for layer in range(3):
            alpha_mult = 1.0 - layer * 0.28
            width = max(1, 4 - layer)
            for i in range(len(positions) - 1):
                x1, y1, a1 = positions[i]; x2, y2, a2 = positions[i+1]
                alpha = int(min(a1, a2) * 150 * alpha_mult)
                if alpha < 8: continue
                blend = alpha / 255
                try:
                    pygame.draw.line(surface,
                                   (int(min(255, color[0]*blend+30*blend)),
                                    int(min(255, color[1]*blend+20*blend)),
                                    int(color[2]*blend)),
                                   (int(x1), int(y1)), (int(x2), int(y2)), width)
                except: pass


@dataclass
class SlashEffect:
    x: float; y: float; angle: float; width: float; color: Tuple
    lifetime: float = 0.15; timer: float = 0.0; arc_length: float = 90; glow: bool = True

    def update(self, dt):
        self.timer += dt
        return self.timer < self.lifetime

    def draw(self, surface, camera):
        if self.timer >= self.lifetime: return
        progress = self.timer / self.lifetime
        alpha = int(220 * (1 - progress))
        current_width = self.width * (1 + progress * 2.5)
        size = int(current_width * 3.5)
        try:
            s = pygame.Surface((size, size), pygame.SRCALPHA)
            center = size // 2
            sa = math.radians(self.angle - self.arc_length / 2)
            ea = math.radians(self.angle + self.arc_length / 2)
            segs = 16
            pts = []
            for i in range(segs + 1):
                t = i / segs; a = sa + (ea - sa) * t
                pts.append((center + math.cos(a)*current_width, center + math.sin(a)*current_width))
            for i in range(segs, -1, -1):
                t = i / segs; a = sa + (ea - sa) * t
                pts.append((center + math.cos(a)*current_width*0.25, center + math.sin(a)*current_width*0.25))
            if len(pts) > 2:
                pygame.draw.polygon(s, (*self.color, alpha), pts)
            sp = camera.mundo_para_tela(self.x, self.y)
            surface.blit(s, (sp[0]-center, sp[1]-center))
        except: pass


@dataclass
class ThrustEffect:
    x: float; y: float; angle: float; length: float; color: Tuple
    lifetime: float = 0.1; timer: float = 0.0

    def update(self, dt):
        self.timer += dt
        return self.timer < self.lifetime

    def draw(self, surface, camera):
        if self.timer >= self.lifetime: return
        progress = self.timer / self.lifetime
        alpha = int(180 * (1 - progress))
        current_length = self.length * (0.5 + progress * 0.5)
        rad = math.radians(self.angle)
        end_x = self.x + math.cos(rad) * current_length
        end_y = self.y + math.sin(rad) * current_length
        start = camera.mundo_para_tela(self.x, self.y)
        end = camera.mundo_para_tela(end_x, end_y)
        width = max(2, int(9 * (1 - progress)))
        blend = alpha / 255
        final = tuple(min(255, int(c*blend + 100*blend)) for c in self.color)
        try:
            pygame.draw.line(surface, final, start, end, width)
        except: pass


@dataclass
class BowDrawEffect:
    x: float; y: float; draw_amount: float; color: Tuple

    def draw(self, surface, camera, radius):
        if self.draw_amount < 0.1: return
        sp = camera.mundo_para_tela(self.x, self.y)
        gr = int(radius * 0.55 * self.draw_amount)
        if gr > 2:
            try:
                s = pygame.Surface((gr*5, gr*5), pygame.SRCALPHA)
                c = gr * 2
                for i in range(4):
                    r = gr * (1 + i * 0.35)
                    a = int(70 * self.draw_amount * (1 - i * 0.25))
                    pygame.draw.circle(s, (*self.color, a), (c, c), int(r))
                surface.blit(s, (sp[0]-c, sp[1]-c))
            except: pass


class WeaponAnimationManager:
    def __init__(self):
        self.animator = WeaponAnimator()
        self.trail_renderer = WeaponTrailRenderer()
        self.active_effects = []

    def start_attack(self, fighter_id, weapon_type, position, angle, weapon_style="", weapon_color=(255, 255, 255)):
        self.animator.start_attack(fighter_id, weapon_type, weapon_style)
        if weapon_type in ["Reta", "Dupla", "Transformável", "Transformavel"]:
            slash_width = {
                "Claymore": 58, "Montante": 52, "Martelo": 46, "Foice": 50,
                "Machado": 44, "Maça": 42, "Alabarda": 46, "Sabre": 36,
                "Katana": 40, "Espada Longa": 37, "Espada Curta": 29,
                "Adagas Gêmeas": 18, "Garras": 22, "Tonfas": 26,
            }.get(weapon_style, 30)
            if weapon_style == "Adagas Gêmeas":
                self.active_effects.append(ThrustEffect(
                    x=position[0], y=position[1], angle=angle,
                    length=slash_width * 1.2, color=weapon_color, lifetime=0.08,
                ))
            else:
                self.active_effects.append(SlashEffect(
                    x=position[0], y=position[1], angle=angle,
                    width=slash_width, color=weapon_color,
                ))
        elif weapon_type in ["Mágica", "Magica"]:
            self.active_effects.append(SlashEffect(
                x=position[0], y=position[1], angle=angle, width=28,
                color=weapon_color, arc_length=360, lifetime=0.22, glow=True,
            ))
        elif weapon_type == "Corrente":
            arc = 260 if weapon_style == "Mangual" else 180
            w = 42 if weapon_style == "Mangual" else 34
            self.active_effects.append(SlashEffect(
                x=position[0], y=position[1], angle=angle, width=w,
                color=weapon_color, arc_length=arc, lifetime=0.22, glow=True,
            ))

    def update(self, dt):
        self.active_effects = [e for e in self.active_effects if e.update(dt)]

    def get_weapon_transform(self, fighter_id, weapon_type, base_angle, weapon_tip, dt, weapon_style=""):
        state = self.animator.update(dt, fighter_id, weapon_type, base_angle, weapon_tip, weapon_style)
        profile = get_animation_profile(weapon_type, weapon_style)
        return {
            "angle_offset": state.angle_offset,
            "scale": state.scale,
            "shake": state.shake_offset,
            "trail_positions": state.trail_positions,
            "is_attacking": state.is_attacking,
            "phase": state.current_phase,
            "glow_intensity": state.glow_intensity,
            "glow_radius": profile.glow_radius if profile.glow_enabled else 0,
            "glow_color": profile.glow_color,
            "motion_blur_positions": state.motion_blur_positions,
            "spark_list": state.spark_list,
            "mangual_spin_speed": state.mangual_spin_speed,
            "dagger_side": state.dagger_side,
            "combo_count": state.combo_count,
        }

    def draw_trails(self, surface, fighter_id, weapon_color, weapon_type, weapon_style=""):
        state = self.animator.get_state(fighter_id)
        profile = get_animation_profile(weapon_type, weapon_style)
        if state.trail_positions:
            self.trail_renderer.draw_trail(surface, state.trail_positions,
                                           weapon_color, weapon_type, profile, weapon_style)

    def draw_effects(self, surface, camera):
        for effect in self.active_effects:
            effect.draw(surface, camera)

    def draw_sparks(self, surface, fighter_id, weapon_pos):
        state = self.animator.get_state(fighter_id)
        for spark in state.spark_list:
            progress = spark["timer"] / max(spark["life"], 0.001)
            alpha = int(255 * (1 - progress))
            x = weapon_pos[0] + spark["vx"] * spark["timer"]
            y = weapon_pos[1] + spark["vy"] * spark["timer"]
            size = max(1, int(spark["size"] * (1 - progress)))
            blend = alpha / 255
            color = spark.get("color", (255, 220, 80))
            try:
                pygame.draw.circle(surface, (int(color[0]*blend), int(color[1]*blend), int(color[2]*blend)),
                                  (int(x), int(y)), size)
            except: pass


_weapon_animation_manager = None

def get_weapon_animation_manager():
    global _weapon_animation_manager
    if _weapon_animation_manager is None:
        _weapon_animation_manager = WeaponAnimationManager()
    return _weapon_animation_manager
