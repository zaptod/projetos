"""Exports lazy do sistema de IA.

Catalogos declarativos, como :mod:`neural_fights.ai.personalities`, podem ser importados por
validadores e ferramentas sem inicializar o runtime de combate ou Pygame.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "CombatChoreographer": ("neural_fights.ai.choreographer", "CombatChoreographer"),
    "AIBrain": ("neural_fights.ai.brain", "AIBrain"),
    "TODOS_TRACOS": ("neural_fights.ai.personalities", "TODOS_TRACOS"),
    "TRACOS_AGRESSIVIDADE": ("neural_fights.ai.personalities", "TRACOS_AGRESSIVIDADE"),
    "TRACOS_DEFENSIVO": ("neural_fights.ai.personalities", "TRACOS_DEFENSIVO"),
    "TRACOS_MOBILIDADE": ("neural_fights.ai.personalities", "TRACOS_MOBILIDADE"),
    "TRACOS_SKILLS": ("neural_fights.ai.personalities", "TRACOS_SKILLS"),
    "TRACOS_MENTAL": ("neural_fights.ai.personalities", "TRACOS_MENTAL"),
    "TRACOS_ESPECIAIS": ("neural_fights.ai.personalities", "TRACOS_ESPECIAIS"),
    "ARQUETIPO_DATA": ("neural_fights.ai.personalities", "ARQUETIPO_DATA"),
    "ESTILOS_LUTA": ("neural_fights.ai.personalities", "ESTILOS_LUTA"),
    "QUIRKS": ("neural_fights.ai.personalities", "QUIRKS"),
    "FILOSOFIAS": ("neural_fights.ai.personalities", "FILOSOFIAS"),
    "HUMORES": ("neural_fights.ai.personalities", "HUMORES"),
    "SpatialAwarenessSystem": ("neural_fights.ai.spatial", "SpatialAwarenessSystem"),
    "EmotionSystem": ("neural_fights.ai.emotions", "EmotionSystem"),
    "SkillStrategySystem": ("neural_fights.ai.skill_strategy", "SkillStrategySystem"),
    "CombatSituation": ("neural_fights.ai.skill_strategy", "CombatSituation"),
    "SkillPriority": ("neural_fights.ai.skill_strategy", "SkillPriority"),
    "StrategicRole": ("neural_fights.ai.skill_strategy", "StrategicRole"),
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
