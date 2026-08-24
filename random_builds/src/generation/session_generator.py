"""SessionGenerator: pipeline de DADOS moldada pelo neural_fights.

seed -> roletas do personagem (catalogos NF) -> roletas da arma (catalogos NF)
-> registros canonicos via fabricas oficiais -> sinergia -> build score.
Produz generation.json. Totalmente separado da edicao de video.
"""
from __future__ import annotations

import json
from pathlib import Path

from .random_engine import RandomEngine
from .probability_engine import ProbabilityEngine
from .rule_engine import RuleEngine
from .validation_engine import ValidationEngine
from .entity_generator import EntityGenerator
from ..evaluation.roll_evaluator import RollEvaluator
from ..evaluation.synergy_engine import SynergyEngine
from ..evaluation.surprise_engine import SurpriseEngine
from ..evaluation.interest_engine import InterestEngine
from ..evaluation.build_evaluator import BuildEvaluator
from ..character.character_builder import finalize_character, finalize_weapon
from ..nf_bridge import roulette_factory, exporter

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def load_config(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


class SessionGenerator:
    def __init__(self):
        self.probability = ProbabilityEngine(load_config("probability.json"))
        rules_config = load_config("rules.json")
        rules_config = {
            **rules_config,
            "rules": roulette_factory.generated_rules() + rules_config.get("rules", []),
        }
        self.rules = RuleEngine(rules_config)
        self.validation = ValidationEngine(rules_config)
        scoring = load_config("scoring.json")
        synergies = load_config("synergies.json")
        self.evaluator = RollEvaluator(scoring, synergies)
        self.synergy = SynergyEngine(synergies, self.evaluator)
        self.surprise = SurpriseEngine()
        self.interest = InterestEngine()
        self.build_eval = BuildEvaluator(scoring)

        self.character_gen = EntityGenerator(
            roulette_factory.character_roulettes(), self.probability,
            self.rules, self.validation, self.evaluator)
        self.weapon_gen = EntityGenerator(
            roulette_factory.weapon_roulettes(), self.probability,
            self.rules, self.validation, self.evaluator)

    def generate(self, seed: int | None = None, generation_id: str = "generated_00001") -> dict:
        seed = seed if seed is not None else RandomEngine.new_seed()
        engine = RandomEngine(seed)

        char_entity, char_events = self.character_gen.generate(engine.fork)
        char_entity = finalize_character(char_entity, char_events)

        weapon_entity, weapon_events = self.weapon_gen.generate(
            engine.fork, extra_context={"character": char_entity})
        weapon_entity = finalize_weapon(weapon_entity, weapon_events)

        # registros canonicos do NF: nome, cor, geometria e passiva vem das
        # fabricas oficiais; os campos rolados sao aplicados por cima
        arma, personagem = exporter.build_records(
            char_entity, weapon_entity, engine.fork("nf:records"))

        compatibility = self.synergy.evaluate(
            {**personagem, **{k: char_entity[k] for k in
                              ("classe", "personalidade", "tamanho", "forca", "mana")}},
            arma)

        events = char_events + weapon_events
        for event in events:
            event["surprise"] = self.surprise.score_event(event)
            event["interest"] = self.interest.score_event(event, event["surprise"])

        build = self.build_eval.evaluate(char_entity, weapon_entity,
                                         compatibility, events)
        build["build_surprise"] = self.surprise.score_build(
            char_entity, weapon_entity, compatibility)

        return {
            "generation_id": generation_id,
            "seed": seed,
            "character": personagem,
            "weapon": arma,
            "character_rolls": char_entity,
            "weapon_rolls": weapon_entity,
            "compatibility": compatibility,
            "build": build,
            "rolls": events,
            "final_score": build["final_score"],
        }
