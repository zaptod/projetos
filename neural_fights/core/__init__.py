"""Exports publicos lazy do nucleo do Neural Fights.

Importar um submodulo leve, como :mod:`neural_fights.core.skills`, nao deve inicializar
Pygame, audio, arena ou o runtime de combate. Os nomes historicamente
reexportados continuam disponiveis e sao carregados apenas quando acessados.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    # Physics
    "normalizar_angulo": ("neural_fights.core.physics", "normalizar_angulo"),
    "distancia_pontos": ("neural_fights.core.physics", "distancia_pontos"),
    "colisao_linha_circulo": ("neural_fights.core.physics", "colisao_linha_circulo"),
    "intersect_line_circle": ("neural_fights.core.physics", "intersect_line_circle"),
    "colisao_linha_linha": ("neural_fights.core.physics", "colisao_linha_linha"),
    # Skills
    "SKILL_DB": ("neural_fights.core.skills", "SKILL_DB"),
    "get_skill_data": ("neural_fights.core.skills", "get_skill_data"),
    # Entities
    "Lutador": ("neural_fights.core.entities", "Lutador"),
    # Game feel
    "GameFeelManager": ("neural_fights.core.game_feel", "GameFeelManager"),
    "HitStopManager": ("neural_fights.core.game_feel", "HitStopManager"),
    "SuperArmorSystem": ("neural_fights.core.game_feel", "SuperArmorSystem"),
    "ChannelingSystem": ("neural_fights.core.game_feel", "ChannelingSystem"),
    "CameraFeel": ("neural_fights.core.game_feel", "CameraFeel"),
    "ChannelState": ("neural_fights.core.game_feel", "ChannelState"),
    "SuperArmorState": ("neural_fights.core.game_feel", "SuperArmorState"),
    # Combat
    "ArmaProjetil": ("neural_fights.core.combat", "ArmaProjetil"),
    "FlechaProjetil": ("neural_fights.core.combat", "FlechaProjetil"),
    "OrbeMagico": ("neural_fights.core.combat", "OrbeMagico"),
    "Projetil": ("neural_fights.core.combat", "Projetil"),
    "AreaEffect": ("neural_fights.core.combat", "AreaEffect"),
    "Beam": ("neural_fights.core.combat", "Beam"),
    "Buff": ("neural_fights.core.combat", "Buff"),
    "DotEffect": ("neural_fights.core.combat", "DotEffect"),
    # Hitbox
    "DEBUG_HITBOX": ("neural_fights.core.hitbox", "DEBUG_HITBOX"),
    "DEBUG_VISUAL": ("neural_fights.core.hitbox", "DEBUG_VISUAL"),
    "HitboxInfo": ("neural_fights.core.hitbox", "HitboxInfo"),
    "SistemaHitbox": ("neural_fights.core.hitbox", "SistemaHitbox"),
    "sistema_hitbox": ("neural_fights.core.hitbox", "sistema_hitbox"),
    "verificar_hit": ("neural_fights.core.hitbox", "verificar_hit"),
    "get_debug_visual": ("neural_fights.core.hitbox", "get_debug_visual"),
    "atualizar_debug": ("neural_fights.core.hitbox", "atualizar_debug"),
    # Arena
    "Arena": ("neural_fights.core.arena", "Arena"),
}

__all__ = list(_EXPORTS)


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
