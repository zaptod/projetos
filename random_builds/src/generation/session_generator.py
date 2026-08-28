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
from . import escolhas as mod_escolhas
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

    def generate(self, seed: int | None = None,
                 generation_id: str = "generated_00001",
                 nome_pedido: str | None = None,
                 autor_pedido: str | None = None,
                 escolhas: dict | None = None) -> dict:
        """nome_pedido: nome escolhido no comentario; vence o nome gerado.

        O sorteio inteiro roda igual com ou sem pedido -- o nome de fora so
        substitui o gerado no fim, entao a mesma seed continua reproduzindo a
        mesma build. autor_pedido e so credito de tela, nao entra em sorteio.

        `escolhas` (de `generation.escolhas.interpretar`): atributos FIXADOS
        em vez de sorteados. Mesma doutrina do nome pedido — cada roleta
        continua girando e consumindo o rng dela, e so o valor final e
        trocado, entao fixar a altura nao muda a arma que teria saido.
        """
        seed = seed if seed is not None else RandomEngine.new_seed()
        engine = RandomEngine(seed)

        char_entity, char_events = self.character_gen.generate(
            engine.fork, escolhas=mod_escolhas.por_entidade(escolhas, "character"))
        char_entity = finalize_character(char_entity, char_events)

        weapon_entity, weapon_events = self.weapon_gen.generate(
            engine.fork, extra_context={"character": char_entity},
            escolhas=mod_escolhas.por_entidade(escolhas, "weapon"))
        weapon_entity = finalize_weapon(weapon_entity, weapon_events)

        # registros canonicos do NF: cor, geometria e passiva vem das fabricas
        # oficiais; os campos rolados sao aplicados por cima e o nome vem da
        # camada propria (src.character.nomes), que tambem aceita o nome pedido
        # no comentario
        arma, personagem, naming = exporter.build_records(
            char_entity, weapon_entity, engine.fork("nf:records"),
            nome_pedido=nome_pedido, genero=(escolhas or {}).get("genero"))

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

        saida = {
            "generation_id": generation_id,
            "seed": seed,
            "character": personagem,
            "weapon": arma,
            "naming": naming,
            "character_rolls": char_entity,
            "weapon_rolls": weapon_entity,
            "compatibility": compatibility,
            "build": build,
            "rolls": events,
            "final_score": build["final_score"],
        }
        # Chave separada e no formato que a CTA le (src/content/caption_generator
        # .pedido_de). So existe quando o nome de fora foi ACEITO: creditar um
        # comentarista que nao mandou nada e pior do que so convidar.
        if naming["requested_name_accepted"]:
            saida["nome_pedido"] = {
                "nome": naming["character_name"],
                "autor": (autor_pedido or "").strip(),
                "origem": "comentario",
            }
        # O que foi ESCOLHIDO em vez de sorteado. So existe quando houve
        # escolha: e esta chave que faz o video parar de dizer "tudo sorteado".
        if mod_escolhas.houve(escolhas):
            saida["escolhas"] = {
                "genero": escolhas.get("genero"),
                "roletas": dict(escolhas.get("roletas") or {}),
                "tela": dict(escolhas.get("tela") or {}),
                "sorteado": {e["roulette_id"]: e["sorteado"]
                             for e in events if e.get("escolhido")},
            }
        return saida
