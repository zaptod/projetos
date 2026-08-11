"""Exports publicos lazy do nucleo do Neural Fights.

Importar um submodulo leve, como :mod:`core.skills`, nao deve inicializar
Pygame, audio, arena ou o runtime de combate. Os nomes historicamente
reexportados continuam disponiveis e sao carregados apenas quando acessados.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    # Physics
    "normalizar_angulo": ("core.physics", "normalizar_angulo"),
    "distancia_pontos": ("core.physics", "distancia_pontos"),
    "colisao_linha_circulo": ("core.physics", "colisao_linha_circulo"),
    "intersect_line_circle": ("core.physics", "intersect_line_circle"),
    "colisao_linha_linha": ("core.physics", "colisao_linha_linha"),
    # Skills
    "SKILL_DB": ("core.skills", "SKILL_DB"),
    "get_skill_data": ("core.skills", "get_skill_data"),
    # Entities
    "Lutador": ("core.entities", "Lutador"),
    # Game feel
    "GameFeelManager": ("core.game_feel", "GameFeelManager"),
    "HitStopManager": ("core.game_feel", "HitStopManager"),
    "SuperArmorSystem": ("core.game_feel", "SuperArmorSystem"),
    "ChannelingSystem": ("core.game_feel", "ChannelingSystem"),
    "CameraFeel": ("core.game_feel", "CameraFeel"),
    "ChannelState": ("core.game_feel", "ChannelState"),
    "SuperArmorState": ("core.game_feel", "SuperArmorState"),
    # Combat
    "ArmaProjetil": ("core.combat", "ArmaProjetil"),
    "FlechaProjetil": ("core.combat", "FlechaProjetil"),
    "OrbeMagico": ("core.combat", "OrbeMagico"),
    "Projetil": ("core.combat", "Projetil"),
    "AreaEffect": ("core.combat", "AreaEffect"),
    "Beam": ("core.combat", "Beam"),
    "Buff": ("core.combat", "Buff"),
    "DotEffect": ("core.combat", "DotEffect"),
    # Hitbox
    "DEBUG_HITBOX": ("core.hitbox", "DEBUG_HITBOX"),
    "DEBUG_VISUAL": ("core.hitbox", "DEBUG_VISUAL"),
    "HitboxInfo": ("core.hitbox", "HitboxInfo"),
    "SistemaHitbox": ("core.hitbox", "SistemaHitbox"),
    "sistema_hitbox": ("core.hitbox", "sistema_hitbox"),
    "verificar_hit": ("core.hitbox", "verificar_hit"),
    "get_debug_visual": ("core.hitbox", "get_debug_visual"),
    "atualizar_debug": ("core.hitbox", "atualizar_debug"),
    # Arena
    "Arena": ("core.arena", "Arena"),
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
