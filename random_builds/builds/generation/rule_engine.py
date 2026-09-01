"""RuleEngine: data-driven IF/THEN rules applied before each roulette spins.

Rules live in config/rules.json. A rule matches a roulette (and optionally a
condition over already-rolled values) and mutates the roulette definition for
this spin only: filtering options, biasing weights, clamping ranges, swapping
distributions or attaching modifiers to the entity draft.
"""
from __future__ import annotations

import copy
from typing import Any


def get_path(data: dict, path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def check_condition(cond: dict, context: dict) -> bool:
    path, op, value = cond.get("path"), cond.get("op"), cond.get("value")
    if path is None:
        return True
    actual = get_path(context, path)
    if isinstance(actual, dict) and "value" in actual:
        actual = actual["value"]
    if op == "eq":
        return actual == value
    if op == "neq":
        return actual != value
    if op == "in":
        return actual in value
    if op == "not_in":
        return actual not in value
    if op == "gte":
        return actual is not None and actual >= value
    if op == "lte":
        return actual is not None and actual <= value
    raise ValueError(f"Operador desconhecido: {op}")


class RuleEngine:
    def __init__(self, rules_config: dict):
        self.rules = rules_config.get("rules", [])

    def apply(self, roulette: dict, context: dict, draft_modifiers: list) -> dict:
        """Returns an adjusted copy of the roulette definition for this spin.

        `context` holds every value already rolled for the current entity
        (and, for weapons, the finished character under "character").
        `draft_modifiers` collects modifiers pushed by add_modifier actions.
        """
        adjusted = copy.deepcopy(roulette)
        for rule in self.rules:
            when = rule.get("when", {})
            if when.get("roulette") and when["roulette"] != roulette["id"]:
                continue
            if not check_condition(when, context):
                continue
            for action in rule.get("then", []):
                self._apply_action(action, adjusted, context, draft_modifiers)
        return adjusted

    def _apply_action(self, action: dict, roulette: dict, context: dict, draft_modifiers: list) -> None:
        kind = action["action"]
        options = roulette.get("options", [])
        if kind == "restrict_options_by_tag":
            source = get_path(context, action["source_path"])
            field = action["tag_field"]
            kept = [o for o in options if source in o.get(field, [])]
            if kept:
                roulette["options"] = kept
        elif kind == "deny_options":
            kept = [o for o in options if o["value"] not in action["values"]]
            if kept:
                roulette["options"] = kept
        elif kind == "allow_options":
            kept = [o for o in options if o["value"] in action["values"]]
            if kept:
                roulette["options"] = kept
        elif kind == "boost_option":
            for o in options:
                if o["value"] == action["value"]:
                    o["weight"] = o.get("weight", 1) * action.get("weight_mult", 1)
        elif kind == "set_distribution":
            roulette["distribution"] = action["distribution"]
        elif kind == "clamp_range":
            if "min" in action:
                roulette["min"] = max(roulette.get("min", action["min"]), action["min"])
            if "max" in action:
                roulette["max"] = min(roulette.get("max", action["max"]), action["max"])
        elif kind == "set_value":
            roulette["forced_value"] = action["value"]
        elif kind == "skip_roulette":
            roulette["skip"] = True
        elif kind == "add_modifier":
            mod = action["modifier"]
            if all(m.get("id") != mod.get("id") for m in draft_modifiers):
                draft_modifiers.append(mod)
        else:
            raise ValueError(f"Acao de regra desconhecida: {kind}")
