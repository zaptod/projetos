"""RollEvaluator: turns each roll into score 0-100 + tier.

Evaluation methods (section 19 of the spec):
  higher_is_better / lower_is_better / neutral / categorical / contextual /
  composite_mean. Contextual rolls are scored against the rest of the build
  (e.g. weapon weight vs character strength) the moment that context exists.
"""
from __future__ import annotations

from typing import Any


class RollEvaluator:
    def __init__(self, scoring: dict, synergies: dict):
        self.tiers = scoring["tiers"]
        self.compat = synergies.get("compatibility", {})

    # ------------------------------------------------------------------- tiers
    def tier_for(self, score: int) -> dict:
        for tier in self.tiers:
            if tier["min"] <= score <= tier["max"]:
                return tier
        return self.tiers[-1] if score > 50 else self.tiers[0]

    # ------------------------------------------------------------------ scores
    def evaluate(self, roulette: dict, value: Any, option: dict | None,
                 lo: int | None, hi: int | None, context: dict) -> tuple[int, bool]:
        """Returns (score, is_contextual_pending)."""
        ev = roulette.get("evaluation", {})
        method = ev.get("method", "neutral") if isinstance(ev, dict) else ev

        # eval_min/eval_max fixam a regua global mesmo quando regras
        # estreitam o range rolavel (ex.: dano por raridade)
        eval_lo = roulette.get("eval_min", lo)
        eval_hi = roulette.get("eval_max", hi)
        if method == "higher_is_better":
            return self._scale(value, eval_lo, eval_hi), False
        if method == "lower_is_better":
            return 100 - self._scale(value, eval_lo, eval_hi), False
        if method == "neutral":
            return 50, False
        if method == "categorical":
            return int(option.get("score", 50)) if option else 50, False
        if method == "contextual":
            fn = ev.get("context_fn")
            score = self.contextual_score(fn, value, context)
            if score is None:
                return 50, True
            return score, False
        if method == "composite_mean":
            return 50, False  # composite score computed by PowerGenerator
        raise ValueError(f"Metodo de avaliacao desconhecido: {method}")

    @staticmethod
    def _scale(value: float, lo: float, hi: float) -> int:
        if hi <= lo:
            return 50
        return max(0, min(100, round((value - lo) / (hi - lo) * 100)))

    # -------------------------------------------------------------- contextual
    def contextual_score(self, fn: str, value: float, context: dict) -> int | None:
        character = context.get("character")
        if character is None:
            return None
        if fn == "peso_vs_forca":
            return self.peso_vs_forca(value / 10, character)
        raise ValueError(f"Funcao contextual desconhecida: {fn}")

    def peso_vs_forca(self, peso_kg: float, character: dict) -> int:
        """Escala do NF: peso 0.5-9.0kg contra forca ~3-9."""
        forca = character.get("forca", character.get("forca_x10", 50) / 10)
        base = self.compat.get("forca_base_necessaria", 1.2)
        por_kg = self.compat.get("forca_por_kg", 0.75)
        necessaria = base + peso_kg * por_kg
        ratio = forca / max(0.1, necessaria)
        if ratio >= 1.0:
            # arma pesada que ELE consegue usar bate mais forte
            bonus_peso = min(16, peso_kg * 2.2)
            score = 60 + bonus_peso + min(20, (ratio - 1.0) * 30)
        else:
            score = ratio * 55
        return max(0, min(100, round(score)))

    def alcance_vs_tamanho(self, alcance: float, tamanho_m: float) -> int:
        """Alcance da arma (comp_cabo+comp_lamina, unidades do NF) versus o
        tamanho do personagem — ponto ideal proximo de tamanho*55."""
        ideal = tamanho_m * 55
        score = 100 - abs(alcance - ideal) * 0.85
        return max(5, min(97, round(score)))

    def decorate(self, event: dict) -> dict:
        tier = self.tier_for(event["score"])
        event["tier"] = tier["name"]
        event["tier_label"] = tier["label"]
        event["sentiment"] = tier["sentiment"]
        event["intensity"] = tier["intensity"]
        event["tier_color"] = tier["color"]
        return event
