"""EditingDirector: decide ONDE a edicao reage.

Duas entradas, dois dominios:

  `decide_rolls`  rolagens da roleta. Usa a CLASSE EDITORIAL (secao 11:
                  ABSURD, CONTRADICTORY, RARE, FUNNY, ...), nao o tier, porque
                  o que merece reacao nao e o que foi bom, e o que da assunto:
                  um resultado mediano improvavel rende mais que um GOOD comum.

  `decide`        lutas do torneio. Continua no tier — la nao existe rolagem
                  improvavel nem contradicao, existe luta boa e luta ruim.

Nos dois casos a reacao e RARA de proposito (secao 10): chance por classe, teto
por video e distancia minima entre duas. Reacao depois de toda roleta para de
parecer espontanea e vira formato.
"""
from __future__ import annotations

import random

from ..evaluation.reaction_classifier import classify_all


class EditingDirector:
    def __init__(self, editing_config: dict):
        self.config = editing_config

    # ------------------------------------------------------------- roletas
    def decide_rolls(self, rng: random.Random, rolls: list[dict]) -> list[dict]:
        """Uma decisao por rolagem, ja com a classe editorial embutida."""
        classificacoes = classify_all(rolls, self.config)
        chances = self.config.get("reaction_chance_by_classification", {})
        orcamento = self.config.get("reaction_budget", {})
        maximo = int(orcamento.get("max_total", 5))
        intervalo = int(orcamento.get("min_gap_rolls", 2))
        max_consecutivas = self.config.get("max_consecutive_reactions", 1)
        boost = self.config.get("interest_boost_weight", 0.35)

        decisoes = []
        candidatos: list[int] = []
        ultima = None
        consecutivas = 0

        for i, (roll, classe) in enumerate(zip(rolls, classificacoes)):
            chance = chances.get(classe["classification"], 0.05)
            chance += (roll.get("interest", 50) / 100 - 0.5) * boost
            quer = rng.random() < max(0.0, min(1.0, chance))

            # Espaco entre reacoes: sem isso duas seguidas viram formato.
            if quer and ultima is not None and (i - ultima) <= intervalo:
                quer = False
            if quer and consecutivas >= max_consecutivas:
                quer = False
            if quer:
                candidatos.append(i)
                ultima = i
                consecutivas += 1
            else:
                consecutivas = 0

            decisoes.append({
                "roll_index": i,
                "reaction": quer,
                "classification": classe["classification"],
                "reason": classe["reason"],
                "weight": classe["weight"],
                "reaction_category": classe["reaction_category"],
                "tier": roll["tier"],
                "sentiment": roll["sentiment"],
                "intensity": self._intensity(roll),
                "effects": list(self.config["effects_by_tier"].get(roll["tier"], [])),
                "extreme": (classe["classification"] in ("ABSURD", "CONTRADICTORY")
                            or roll["tier"] in ("TERRIBLE", "INSANE")),
            })

        # Teto por video: passando dele, ficam as reacoes de maior peso
        # editorial. Empate fica com a mais cedo, para o video nao guardar
        # todas as piadas para o fim.
        if len(candidatos) > maximo:
            mantidos = sorted(sorted(candidatos,
                                     key=lambda i: (-decisoes[i]["weight"], i))[:maximo])
            for i in candidatos:
                if i not in mantidos:
                    decisoes[i]["reaction"] = False
                    decisoes[i]["cortada_por_orcamento"] = True
        return decisoes

    # ------------------------------------------------------------- torneio
    def decide(self, rng: random.Random, events: list[dict]) -> list[dict]:
        decisions = []
        consecutive = 0
        max_consecutive = self.config.get("max_consecutive_reactions", 2)
        boost_weight = self.config.get("interest_boost_weight", 0.35)
        surprise_threshold = self.config.get("surprise_reaction_threshold", 80)

        for event in events:
            chance = self.config["reaction_chance_by_tier"][event["tier"]]
            chance += (event.get("interest", 50) / 100 - 0.5) * boost_weight
            forced = event.get("surprise", 0) >= surprise_threshold
            wants = forced or rng.random() < max(0.0, min(1.0, chance))
            if wants and consecutive >= max_consecutive:
                wants = False
            consecutive = consecutive + 1 if wants else 0

            decisions.append({
                "roll_index": events.index(event),
                "reaction": wants,
                "tier": event["tier"],
                "sentiment": event["sentiment"],
                "intensity": self._intensity(event),
                "effects": list(self.config["effects_by_tier"].get(event["tier"], [])),
                "extreme": event["tier"] in ("TERRIBLE", "INSANE"),
            })
        return decisions

    @staticmethod
    def _intensity(event: dict) -> float:
        base = event.get("intensity", 0.5)
        interest = event.get("interest", 50) / 100
        return round(min(1.0, base * 0.7 + interest * 0.4), 2)
