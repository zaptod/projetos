"""BuildEvaluator: final build score from character, weapon, compatibility,
power and weaknesses (section 24)."""
from __future__ import annotations


class BuildEvaluator:
    def __init__(self, scoring: dict):
        self.scoring = scoring

    def evaluate(self, character: dict, weapon: dict, compatibility: dict,
                 events: list[dict]) -> dict:
        weights = self.scoring["build_weights"]
        components = {
            "character_score": character.get("character_score", 50),
            "weapon_score": weapon.get("weapon_score", 50),
            "compatibility_score": compatibility["compatibility_score"],
        }
        final = sum(components[k] * weights[k] for k in weights)
        # weighted means compress toward 50; stretch so great/terrible builds
        # actually reach the extreme verdicts
        spread = self.scoring.get("final_spread", 1.0)
        final = 50 + (final - 50) * spread

        penalty_weight = self.scoring.get("weakness_penalty_weight", 0.06)
        severities = [e.get("severity", 0.0) for e in events if "severity" in e]
        weakness_penalty = round(sum(severities) * penalty_weight * 100)
        final = max(0, min(100, round(final - weakness_penalty)))

        verdict = self._verdict(final)
        return {
            **components,
            "weakness_penalty": weakness_penalty,
            "final_score": final,
            "verdict": verdict["name"],
            "verdict_label": verdict["label"],
            "sentiment": verdict["sentiment"],
            "intensity": verdict["intensity"],
            "synergies": [s["label"] for s in compatibility.get("synergies", [])],
            "conflicts": [c["label"] for c in compatibility.get("conflicts", [])],
        }

    def _verdict(self, score: int) -> dict:
        for verdict in self.scoring["build_verdicts"]:
            if verdict["min"] <= score <= verdict["max"]:
                return verdict
        return self.scoring["build_verdicts"][-1]
