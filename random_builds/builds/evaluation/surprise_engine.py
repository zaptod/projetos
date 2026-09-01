"""SurpriseScore (section 40): how unexpected a result is, good OR bad."""
from __future__ import annotations


class SurpriseEngine:
    def score_event(self, event: dict) -> int:
        extremity = abs(event["score"] - 50) * 2          # 0..100
        rarity = event.get("rarity", 0.0) * 100           # 0..100
        surprise = 0.45 * rarity + 0.55 * extremity
        return max(0, min(100, round(surprise)))

    def score_build(self, character: dict, weapon: dict, compatibility: dict) -> int:
        """Mismatch surprise: great weapon on a character who can't use it, etc."""
        weapon_quality = weapon.get("weapon_score", 50)
        compat = compatibility["compatibility_score"]
        gap = abs(weapon_quality - compat)
        conflict_bonus = 12 * len(compatibility.get("conflicts", []))
        synergy_bonus = 8 * len(compatibility.get("synergies", []))
        return max(0, min(100, round(gap * 0.9 + conflict_bonus + synergy_bonus)))
