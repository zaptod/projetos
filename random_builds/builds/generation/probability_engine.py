"""Distribution engine: uniform, weighted, normal, rare_extremes, custom_curve.

Distributions are described by config dicts (inline in a roulette definition)
or by preset name resolved through config/probability.json.
"""
from __future__ import annotations

import random
from typing import Any


class ProbabilityEngine:
    def __init__(self, presets: dict[str, Any]):
        self.presets = presets.get("presets", presets)

    def resolve(self, distribution: Any) -> dict[str, Any]:
        if distribution is None:
            return {"kind": "uniform"}
        if isinstance(distribution, str):
            preset = self.presets.get(distribution)
            if preset is None:
                raise KeyError(f"Distribuicao preset desconhecida: {distribution}")
            return preset
        return distribution

    # ------------------------------------------------------------------ numeric
    def roll_numeric(self, rng: random.Random, lo: int, hi: int, distribution: Any) -> int:
        cfg = self.resolve(distribution)
        kind = cfg.get("kind", "uniform")
        if kind == "uniform":
            return rng.randint(lo, hi)
        if kind == "normal":
            return self._roll_normal(rng, lo, hi, cfg)
        if kind == "rare_extremes":
            return self._roll_rare_extremes(rng, lo, hi, cfg)
        if kind == "custom_curve":
            return self._roll_custom_curve(rng, lo, hi, cfg)
        raise ValueError(f"Distribuicao desconhecida: {kind}")

    def _roll_normal(self, rng: random.Random, lo: int, hi: int, cfg: dict) -> int:
        span = hi - lo
        mean = lo + span * cfg.get("mean_pct", cfg.get("mid_mean_pct", 0.5))
        std = max(1.0, span * cfg.get("std_pct", cfg.get("mid_std_pct", 0.15)))
        return max(lo, min(hi, round(rng.gauss(mean, std))))

    def _roll_rare_extremes(self, rng: random.Random, lo: int, hi: int, cfg: dict) -> int:
        span = hi - lo
        band = max(1, round(span * cfg.get("extreme_band_pct", 0.06)))
        r = rng.random()
        low_c = cfg.get("low_extreme_chance", 0.05)
        high_c = cfg.get("high_extreme_chance", 0.05)
        uni_c = cfg.get("uniform_chance", 0.2)
        if r < low_c:
            return rng.randint(lo, lo + band)
        if r < low_c + high_c:
            return rng.randint(hi - band, hi)
        if r < low_c + high_c + uni_c:
            return rng.randint(lo, hi)
        return self._roll_normal(rng, lo, hi, cfg)

    def _roll_custom_curve(self, rng: random.Random, lo: int, hi: int, cfg: dict) -> int:
        segments = [s for s in cfg["segments"] if s["range"][0] <= hi and s["range"][1] >= lo]
        if not segments:
            return rng.randint(lo, hi)
        weights = [s["weight"] for s in segments]
        seg = rng.choices(segments, weights=weights, k=1)[0]
        a = max(lo, seg["range"][0])
        b = min(hi, seg["range"][1])
        return rng.randint(a, b)

    # -------------------------------------------------------------- categorical
    def roll_categorical(self, rng: random.Random, options: list[dict]) -> tuple[dict, float]:
        """Returns (option, rarity) where rarity is 0..1 (1 = rarest)."""
        weights = [max(0.0, float(o.get("weight", 1))) for o in options]
        total = sum(weights)
        if total <= 0:
            raise ValueError("Nenhuma opcao com peso positivo disponivel")
        choice = rng.choices(options, weights=weights, k=1)[0]
        p = float(choice.get("weight", 1)) / total
        rarity = 1.0 - min(1.0, p * len(options) / 2)
        return choice, max(0.0, rarity)

    def numeric_rarity(self, value: int, lo: int, hi: int, distribution: Any) -> float:
        """Approximate rarity 0..1 of a numeric result: distance from the center."""
        if hi <= lo:
            return 0.0
        pos = (value - lo) / (hi - lo)
        return round(abs(pos - 0.5) * 2, 3)
