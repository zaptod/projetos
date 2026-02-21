"""
NEURAL FIGHTS - Módulo Effects
Sistema de efeitos visuais, partículas e câmera.
"""

# Partículas
from .particles import (
    Particula,
    HitSpark,
    Shockwave,
    EncantamentoEffect,
    CORES_ENCANTAMENTOS,
)

# Impacto
from .impact import (
    ImpactFlash,
    MagicClash,
    BlockEffect,
    DashTrail,
)

# Câmera
from .camera import Câmera

# Visual/UI
from .visual import (
    FloatingText,
    Decal,
)

# === NOVO: Sistema de Animação de Movimento v8.0 ===
from .movement import (
    MovementAnimationManager,
    AfterImageTrail,
    DustCloud,
    SpeedLinesEffect,
    MotionBlur,
    SquashStretch,
    RecoveryFlash,
    MovementType,
)

# === NOVO: Sistema de Animação de Ataque v8.0 IMPACT EDITION ===
from .attack import (
    AttackAnimationManager,
    WeaponTrailEnhanced,
    ImpactShockwave,
    ImpactSparks,
    ScreenFlash,
    CraterMark,
    GroundCrack,
    AttackAnticipation,
    get_impact_tier,
    calcular_knockback_com_forca,
)

# === NOVO: Sistema de Animação de Armas v2.0 ===
from .weapon_animations import (
    WeaponAnimationManager,
    WeaponAnimator,
    WeaponTrailRenderer,
    WeaponAnimationProfile,
    WeaponAnimationState,
    AttackPhase,
    Easing,
    WEAPON_PROFILES,
    get_weapon_animation_manager,
)

# v10.0 - Audio movido para effects
from .audio import (
    AudioManager,
    play_sound,
    play_attack_sound,
    play_impact_sound,
    play_skill_sound,
)

# v11.0 - Efeitos de Magia Dramáticos
from .magic_vfx import (
    MagicVFXManager,
    DramaticExplosion,
    DramaticBeam,
    DramaticAura,
    DramaticSummon,
    DramaticProjectileTrail,
    MagicParticle,
    ELEMENT_PALETTES,
    get_element_from_skill,
)

__all__ = [
    # Partículas
    'Particula',
    'HitSpark',
    'Shockwave',
    'EncantamentoEffect',
    'CORES_ENCANTAMENTOS',
    # Impacto
    'ImpactFlash',
    'MagicClash',
    'BlockEffect',
    'DashTrail',
    # Câmera
    'Câmera',
    # Visual
    'FloatingText',
    'Decal',
    # Movimento v8.0
    'MovementAnimationManager',
    'AfterImageTrail',
    'DustCloud',
    'SpeedLinesEffect',
    'MotionBlur',
    'SquashStretch',
    'RecoveryFlash',
    'MovementType',
    # Ataque v8.0 IMPACT
    'AttackAnimationManager',
    'WeaponTrailEnhanced',
    'ImpactShockwave',
    'ImpactSparks',
    'ScreenFlash',
    'CraterMark',
    'GroundCrack',
    'AttackAnticipation',
    'get_impact_tier',
    'calcular_knockback_com_forca',
    # Animações de Armas v2.0
    'WeaponAnimationManager',
    'WeaponAnimator',
    'WeaponTrailRenderer',
    'WeaponAnimationProfile',
    'WeaponAnimationState',
    'AttackPhase',
    'Easing',
    'WEAPON_PROFILES',
    'get_weapon_animation_manager',
    # Audio v10.0
    'AudioManager',
    'play_sound',
    'play_attack_sound',
    'play_impact_sound',
    'play_skill_sound',
    # Magic VFX v11.0
    'MagicVFXManager',
    'DramaticExplosion',
    'DramaticBeam',
    'DramaticAura',
    'DramaticSummon',
    'DramaticProjectileTrail',
    'MagicParticle',
    'ELEMENT_PALETTES',
    'get_element_from_skill',
]
