"""InterestScore (section 41): entertainment value, not quality.

A score of 2/100 can have interest 95 — disasters are content too.
"""
from __future__ import annotations


class InterestEngine:
    def score_event(self, event: dict, surprise: int) -> int:
        extremity = abs(event["score"] - 50) * 2
        interest = 0.55 * extremity + 0.45 * surprise
        # contextual mismatches (can't lift the weapon) are premium content
        if event.get("contextual_pending") is False and self._is_contextual(event):
            interest = min(100, interest * 1.15)
        return max(0, min(100, round(interest)))

    @staticmethod
    def _is_contextual(event: dict) -> bool:
        method = event["evaluation"]
        if isinstance(method, dict):
            method = method.get("method")
        return method == "contextual"
