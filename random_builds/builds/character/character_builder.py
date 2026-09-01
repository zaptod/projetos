"""Converte os inteiros escalados das roletas para o contrato do NF.

O nome, a cor e o vinculo com a arma vem depois, das fabricas oficiais do
neural_fights (exporter) — nunca daqui.
"""
from __future__ import annotations


def _counts(event: dict) -> bool:
    method = event["evaluation"]
    if isinstance(method, dict):
        method = method.get("method", "neutral")
    return method != "neutral"


def finalize_character(entity: dict, events: list[dict]) -> dict:
    entity["tamanho"] = round(entity["tamanho_cm"] / 100, 2)
    entity["forca"] = round(entity["forca_x10"] / 10, 1)
    entity["mana"] = round(entity["mana_x10"] / 10, 1)
    scored = [e["score"] for e in events if not e["contextual_pending"] and _counts(e)]
    entity["character_score"] = round(sum(scored) / len(scored)) if scored else 50
    return entity


def finalize_weapon(entity: dict, events: list[dict]) -> dict:
    entity["peso"] = round(entity["peso_x10"] / 10, 1)
    entity["critico"] = round(entity["critico_x10"] / 10, 1)
    entity["velocidade_ataque"] = round(entity["velocidade_x100"] / 100, 2)
    scored = [e["score"] for e in events if not e["contextual_pending"] and _counts(e)]
    entity["weapon_score"] = round(sum(scored) / len(scored)) if scored else 50
    return entity
