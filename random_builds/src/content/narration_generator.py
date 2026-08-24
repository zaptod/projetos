"""NarrationGenerator (section 46): template narration script.

Produces narration.json — a timed script that can later feed a TTS engine
(hook point: each line carries start/duration). An LLM may rewrite lines for
variety, but it never decides numbers.
"""
from __future__ import annotations

import random

INTROS = {
    "classe": ["Primeiro: qual vai ser a classe dele?"],
    "personalidade": ["E a personalidade?"],
    "tamanho": ["Qual o tamanho desse lutador?"],
    "forca": ["Agora vamos descobrir a forca dele."],
    "mana": ["E a mana?"],
    "tipo": ["Agora a arma. Qual tipo?"],
    "estilo": ["E o estilo da arma?"],
    "raridade": ["Hora da raridade..."],
    "encantamento": ["Qual encantamento ela carrega?"],
    "habilidade": ["E a habilidade especial?"],
    "dano": ["Quanto de dano essa arma tem?"],
    "peso": ["Quanto essa arma pesa?"],
    "critico": ["E o critico?"],
    "velocidade_ataque": ["Qual a velocidade de ataque?"],
    "_default": ["Proxima roleta: {CATEGORY}."],
}

COMMENTS = {
    "TERRIBLE": ["{VALUE}?! Ja comecou horrivel.", "Isso foi pessimo.", "Nao tem como aproveitar isso."],
    "BAD": ["{VALUE}... bem ruim.", "Abaixo do esperado."],
    "WEAK": ["{VALUE}. Fraquinho.", "Podia ser pior."],
    "AVERAGE": ["{VALUE}. Na media.", "Ok, aceitavel."],
    "GOOD": ["{VALUE}! Bom resultado.", "Gostei desse."],
    "GREAT": ["{VALUE}! Excelente!", "Agora sim!"],
    "INSANE": ["{VALUE}?! Isso e absurdo!", "Nao acredito nisso. {VALUE}!", "Rolagem historica!"],
}


class NarrationGenerator:
    def build_script(self, rng: random.Random, edit_plan: dict, generation: dict) -> dict:
        lines = []
        for event in edit_plan["events"]:
            if event["type"] == "hook":
                lines.append(self._line(event, "Vamos criar um personagem completamente aleatorio."))
            elif event["type"] == "roulette":
                roll = event["roll"]
                intro_pool = INTROS.get(roll["roulette_id"], INTROS["_default"])
                intro = rng.choice(intro_pool).replace("{CATEGORY}", roll["category"].lower())
                comment = rng.choice(COMMENTS[roll["tier"]]).replace("{VALUE}", roll["display_value"])
                lines.append(self._line(event, f"{intro} ... {comment}"))
            elif event["type"] == "stinger":
                lines.append(self._line(event, "Agora a arma."))
            elif event["type"] in ("identity", "nameplate"):
                lines.append(self._line(event, self._revelacao(event, generation)))
            elif event["type"] in ("reveal_character", "reveal_weapon"):
                # Formato anterior: plano gravado antes da divisao em tres.
                entidade = ("character" if event["type"] == "reveal_character"
                            else "weapon")
                lines.append(self._line(
                    event, f"{generation[entidade]['nome']}."))
            elif event["type"] == "synergy":
                score = generation["compatibility"]["compatibility_score"]
                lines.append(self._line(event, f"Compatibilidade: {score} de 100."))
            elif event["type"] == "final":
                lines.append(self._line(event, f"Nota final da build: {generation['final_score']} de 100."))
        return {"tts": None, "lines": lines}

    @staticmethod
    def _revelacao(event: dict, generation: dict) -> str:
        """A fala de cada uma das tres recompensas."""
        personagem = generation["character"]["nome"]
        arma = generation["weapon"]["nome"]
        return {
            "character": f"Personagem criado: {personagem}.",
            "weapon": f"E a arma: {arma}.",
            "character_weapon": f"{personagem} com {arma}.",
        }.get(event.get("slot", "character"), f"{personagem}.")

    @staticmethod
    def _line(event: dict, text: str) -> dict:
        return {"start": event["start"], "duration": event["duration"], "text": text}
