"""EntityGenerator: roda a sequencia de roletas e monta a entidade.

Personagem e arma usam o MESMO motor — so muda a configuracao de roletas
(gerada a partir dos catalogos do neural_fights). Cada evento carrega tambem
o payload da roda visual: todas as opcoes possiveis (pos-regras) e o indice
vencedor, para o renderer animar a roleta girando.
"""
from __future__ import annotations

import random
from typing import Any

from .probability_engine import ProbabilityEngine
from .rule_engine import RuleEngine
from .validation_engine import ValidationEngine
from ..evaluation.roll_evaluator import RollEvaluator

WHEEL_MAX_SEGMENTS = 24
WHEEL_NUMERIC_SEGMENTS = 12


def set_path(data: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = data
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def format_value(roulette: dict, value: Any, option: dict | None) -> str:
    if option is not None:
        return option["label"]
    fmt = roulette.get("display_format")
    unit = roulette.get("unit", "")
    if fmt == "meters":
        return f"{value / 100:.2f}".replace(".", ",") + "m"
    if fmt == "decimal10":
        text = f"{value / 10:.1f}".replace(".", ",")
        return text + ("kg" if unit == "kg" else "")
    if fmt == "decimal100":
        return f"{value / 100:.2f}".replace(".", ",")
    if unit == "kg":
        return f"{value}kg"
    return str(value)


def _wheel_for_categorical(options: list[dict], winner_value: Any) -> dict:
    labels = [o["label"] for o in options]
    winner = next(i for i, o in enumerate(options) if o["value"] == winner_value)
    if len(labels) > WHEEL_MAX_SEGMENTS:
        # amostragem uniforme mantendo o vencedor na roda
        step = len(labels) / WHEEL_MAX_SEGMENTS
        idxs = sorted({min(len(labels) - 1, round(i * step))
                       for i in range(WHEEL_MAX_SEGMENTS)} | {winner})
        labels = [labels[i] for i in idxs]
        winner = idxs.index(winner)
    return {"labels": labels, "winner": winner}


def _wheel_for_numeric(roulette: dict, lo: int, hi: int, value: int) -> dict:
    n = min(WHEEL_NUMERIC_SEGMENTS, max(2, hi - lo + 1))
    samples = [round(lo + (hi - lo) * i / (n - 1)) for i in range(n)]
    winner = min(range(n), key=lambda i: abs(samples[i] - value))
    samples[winner] = value  # o segmento vencedor mostra o valor exato
    labels = [format_value(roulette, s, None) for s in samples]
    return {"labels": labels, "winner": winner}


class EntityGenerator:
    def __init__(self, roulettes_config: dict, probability: ProbabilityEngine,
                 rules: RuleEngine, validation: ValidationEngine,
                 evaluator: RollEvaluator):
        self.entity_name = roulettes_config["entity"]
        self.roulettes = roulettes_config["roulettes"]
        self.probability = probability
        self.rules = rules
        self.validation = validation
        self.evaluator = evaluator

    def generate(self, fork, extra_context: dict | None = None,
                 escolhas: dict | None = None) -> tuple[dict, list[dict]]:
        """`escolhas`: {roulette_id: valor} que vence o sorteio daquela roleta.

        A roleta escolhida AINDA gira e consome o rng dela — trocar o valor
        depois e o que mantem "mesma seed, mesma build" para todo o resto (e
        guarda no evento o que teria saido).
        """
        entity: dict[str, Any] = {"modifiers": []}
        events: list[dict] = []
        extra = extra_context or {}
        self._escolhas = dict(escolhas or {})

        for index, roulette in enumerate(self.roulettes):
            rng = fork(f"{self.entity_name}:{roulette['id']}")
            event = self._spin(roulette, rng, entity, extra, index)
            if event is None:
                continue
            events.append(event)

        self._validate(entity, events, fork, extra)
        return entity, events

    # -------------------------------------------------------------------- spin
    def _spin(self, roulette: dict, rng: random.Random, entity: dict,
              extra: dict, index: int) -> dict | None:
        context = {**entity, **extra}
        adjusted = self.rules.apply(roulette, context, entity["modifiers"])
        if adjusted.get("skip"):
            return None

        option = None
        lo = adjusted.get("min")
        hi = adjusted.get("max")
        rarity = 0.0

        if "forced_value" in adjusted:
            value = adjusted["forced_value"]
            wheel = None
        elif adjusted["type"] == "numeric_range":
            value = self.probability.roll_numeric(rng, lo, hi, adjusted.get("distribution"))
            rarity = self.probability.numeric_rarity(value, lo, hi, adjusted.get("distribution"))
            wheel = _wheel_for_numeric(adjusted, lo, hi, value)
        elif adjusted["type"] == "categorical":
            option, rarity = self.probability.roll_categorical(rng, adjusted["options"])
            value = option["value"]
            wheel = _wheel_for_categorical(adjusted["options"], value)
        else:
            raise ValueError(f"Tipo de roleta desconhecido: {adjusted['type']}")

        sorteado = None
        escolhido = getattr(self, "_escolhas", {}).get(roulette["id"])
        if escolhido is not None:
            sorteado = format_value(adjusted, value, option)
            value, option, rarity = self._fixar(adjusted, escolhido, lo, hi)
            # A roda continua sendo a roda inteira, so que parando no valor
            # escolhido: uma roda de UM segmento denunciaria a escolha na tela
            # e transformaria a cena de roleta num cartao.
            wheel = (_wheel_for_categorical(adjusted["options"], value)
                     if adjusted["type"] == "categorical"
                     else _wheel_for_numeric(adjusted, lo, hi, value))

        set_path(entity, adjusted["target"], value)
        if option is not None:
            set_path(entity, adjusted["target"] + "_meta", {
                k: v for k, v in option.items() if k != "weight"
            })

        score, pending = self.evaluator.evaluate(
            adjusted, value, option, lo, hi, {**extra, **entity})

        event = {
            "index": index,
            "entity": self.entity_name,
            "roulette_id": roulette["id"],
            "category": roulette["display_name"],
            "value": value,
            "display_value": format_value(adjusted, value, option),
            "score": score,
            "contextual_pending": pending,
            "evaluation": roulette.get("evaluation", {}),
            "rarity": round(rarity, 3),
            "target": adjusted["target"],
            "wheel": wheel,
        }
        if sorteado is not None:
            # Doutrina do nome pedido: o que TERIA saido fica registrado, e a
            # legenda deixa de afirmar que a roleta decidiu.
            event["escolhido"] = True
            event["sorteado"] = sorteado
        if option is not None and "severity" in option:
            event["severity"] = option["severity"]
        return self.evaluator.decorate(event)

    def _fixar(self, adjusted: dict, escolhido: Any, lo, hi):
        """Valor escolhido no lugar do sorteado, validado contra as REGRAS.

        A validacao acontece aqui, e nao so na entrada da CLI, porque a faixa
        e as opcoes mudam com o que ja saiu: raridade alta estreita o dano,
        o tipo da arma restringe o estilo. Escolha impossivel para ALTO — um
        valor silenciosamente ignorado viraria um sorteio que o dono acha que
        escolheu.
        """
        if adjusted["type"] == "categorical":
            option = next((o for o in adjusted["options"]
                           if o["value"] == escolhido), None)
            if option is None:
                disponivel = ", ".join(o["label"] for o in adjusted["options"])
                raise ValueError(
                    f"{adjusted['id']}: '{escolhido}' nao esta disponivel depois "
                    f"do que ja foi sorteado. Agora vale: {disponivel}")
            return option["value"], option, 0.0
        if not (lo <= escolhido <= hi):
            raise ValueError(
                f"{adjusted['id']}: {escolhido} fora da faixa {lo}..{hi} "
                "depois das regras (raridade e estilo estreitam a faixa)")
        rarity = self.probability.numeric_rarity(escolhido, lo, hi,
                                                 adjusted.get("distribution"))
        return escolhido, None, rarity

    # -------------------------------------------------------------- validation
    def _validate(self, entity: dict, events: list[dict], fork, extra: dict) -> None:
        for attempt in range(ValidationEngine.MAX_REROLLS):
            violation = self.validation.find_violation(entity)
            if violation is None:
                return
            target_id = violation["reroll"]
            if target_id in getattr(self, "_escolhas", {}):
                # Re-rolar uma roleta fixada devolveria o mesmo valor 12 vezes
                # e morreria em "nao convergiu", escondendo a causa real.
                raise ValueError(
                    f"a escolha de '{target_id}' cria uma combinacao proibida "
                    "com o resto da build; escolha outro valor ou outra seed")
            roulette = next(r for r in self.roulettes if r["id"] == target_id)
            rng = fork(f"{self.entity_name}:{target_id}:reroll:{attempt}")
            old = next((e for e in events if e["roulette_id"] == target_id), None)
            index = old["index"] if old else len(events)
            new_event = self._spin(roulette, rng, entity, extra, index)
            if old and new_event:
                events[events.index(old)] = new_event
        raise RuntimeError(f"Validacao nao convergiu para {self.entity_name}")
