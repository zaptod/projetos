"""
=============================================================================
NEURAL FIGHTS - Sistema de IA v9.0 SPATIAL AWARENESS EDITION
=============================================================================
Módulo de Inteligência Artificial modularizado.
Sistema de comportamento humano realista com:
- Antecipação e leitura do oponente
- Desvios inteligentes com timing humano
- Baiting e fintas
- Janelas de oportunidade
- Momentum e pressão psicológica
- Combos e follow-ups
- Consciência espacial (paredes, obstáculos)
=============================================================================
"""

from ai.choreographer import CombatChoreographer
from ai.brain import AIBrain
from ai.personalities import (
    TODOS_TRACOS, TRACOS_AGRESSIVIDADE, TRACOS_DEFENSIVO, TRACOS_MOBILIDADE,
    TRACOS_SKILLS, TRACOS_MENTAL, TRACOS_ESPECIAIS,
    ARQUETIPO_DATA, ESTILOS_LUTA, QUIRKS, FILOSOFIAS, HUMORES
)

# Novos módulos v9.0
from ai.spatial import SpatialAwarenessSystem
from ai.emotions import EmotionSystem
from ai.combat_tactics import CombatTacticsSystem

# Novo módulo v10.0 - Estratégia de Skills
try:
    from ai.skill_strategy import SkillStrategySystem, CombatSituation, SkillPriority, StrategicRole
    SKILL_STRATEGY_AVAILABLE = True
except ImportError:
    SKILL_STRATEGY_AVAILABLE = False

__all__ = [
    'CombatChoreographer',
    'AIBrain',
    'TODOS_TRACOS',
    'TRACOS_AGRESSIVIDADE',
    'TRACOS_DEFENSIVO',
    'TRACOS_MOBILIDADE',
    'TRACOS_SKILLS',
    'TRACOS_MENTAL',
    'TRACOS_ESPECIAIS',
    'ARQUETIPO_DATA',
    'ESTILOS_LUTA',
    'QUIRKS',
    'FILOSOFIAS',
    'HUMORES',
    # Novos sistemas
    'SpatialAwarenessSystem',
    'EmotionSystem',
    'CombatTacticsSystem',
    # Sistema de Estratégia de Skills
    'SkillStrategySystem',
    'CombatSituation',
    'SkillPriority',
    'StrategicRole',
]
