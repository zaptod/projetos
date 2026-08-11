"""Exports lazy do sistema de IA.

Catalogos declarativos, como :mod:`ai.personalities`, podem ser importados por
validadores e ferramentas sem inicializar o runtime de combate ou Pygame.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "CombatChoreographer": ("ai.choreographer", "CombatChoreographer"),
    "AIBrain": ("ai.brain", "AIBrain"),
    "TODOS_TRACOS": ("ai.personalities", "TODOS_TRACOS"),
    "TRACOS_AGRESSIVIDADE": ("ai.personalities", "TRACOS_AGRESSIVIDADE"),
    "TRACOS_DEFENSIVO": ("ai.personalities", "TRACOS_DEFENSIVO"),
    "TRACOS_MOBILIDADE": ("ai.personalities", "TRACOS_MOBILIDADE"),
    "TRACOS_SKILLS": ("ai.personalities", "TRACOS_SKILLS"),
    "TRACOS_MENTAL": ("ai.personalities", "TRACOS_MENTAL"),
    "TRACOS_ESPECIAIS": ("ai.personalities", "TRACOS_ESPECIAIS"),
    "ARQUETIPO_DATA": ("ai.personalities", "ARQUETIPO_DATA"),
    "ESTILOS_LUTA": ("ai.personalities", "ESTILOS_LUTA"),
    "QUIRKS": ("ai.personalities", "QUIRKS"),
    "FILOSOFIAS": ("ai.personalities", "FILOSOFIAS"),
    "HUMORES": ("ai.personalities", "HUMORES"),
    "SpatialAwarenessSystem": ("ai.spatial", "SpatialAwarenessSystem"),
    "EmotionSystem": ("ai.emotions", "EmotionSystem"),
    "CombatTacticsSystem": ("ai.combat_tactics", "CombatTacticsSystem"),
    "SkillStrategySystem": ("ai.skill_strategy", "SkillStrategySystem"),
    "CombatSituation": ("ai.skill_strategy", "CombatSituation"),
    "SkillPriority": ("ai.skill_strategy", "SkillPriority"),
    "StrategicRole": ("ai.skill_strategy", "StrategicRole"),
}

SKILL_STRATEGY_AVAILABLE = True
__all__ = [*_EXPORTS, "SKILL_STRATEGY_AVAILABLE"]


def __getattr__(name: str):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
