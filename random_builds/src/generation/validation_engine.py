"""ValidationEngine: allows BAD combinations, blocks IMPOSSIBLE ones.

Validations in config/rules.json describe forbidden states; when one matches,
the named roulette is rerolled deterministically (bounded attempts).
"""
from __future__ import annotations

from .rule_engine import check_condition


class ValidationEngine:
    MAX_REROLLS = 12

    def __init__(self, rules_config: dict):
        self.validations = rules_config.get("validations", [])

    def find_violation(self, entity_data: dict) -> dict | None:
        for validation in self.validations:
            forbid = validation["forbid"]
            conditions = forbid.get("all", [forbid])
            if all(check_condition(c, entity_data) for c in conditions):
                return validation
        return None
