"""NarrationGenerator: o roteiro FALADO do video, uma fala por batida.

`narration.json` e o que `src/content/voz.py` transforma em voz. Cada linha
carrega `start`/`duration` — o espaco em que ela precisa caber — e o texto
ja no tom do canal: curto, com opiniao, sem ler a ficha.

Uma roleta cheia rende DUAS falas: a pergunta durante o giro ("Classe?") e
o comentario no instante em que a roda para ("Duelista. Na media."). A
roleta-relampago (atributo numerico sem noticia) fica MUDA. A tensao antes
do giro e a pergunta; o comentario carrega o julgamento do tier.

A CENA ESPERA A FALA: o controller mede cada linha sintetizada
(`voz.medir`) e `timeline_builder.ajustar_ao_roteiro` estica o evento ate
ela terminar — por isso as frases aqui sao curtas: cada palavra a mais e
tempo de tela.

O texto nunca decide numero: {VALUE} vem da rolagem, o julgamento vem do
tier que a avaliacao ja deu.
"""
from __future__ import annotations

import random

PERGUNTAS = {
    "classe": ["Classe?", "Qual a classe?", "Primeiro: a classe."],
    "personalidade": ["Personalidade?", "Como ele luta?"],
    "tamanho": ["Tamanho?", "Altura?"],
    "forca": ["Força?", "E a força?"],
    "mana": ["Mana?", "Quanta mana?"],
    "tipo": ["Agora a arma. Tipo?", "Que arma?"],
    "estilo": ["Estilo?", "Qual modelo?"],
    "raridade": ["Raridade...", "Vai ser rara?"],
    "encantamento": ["Encantamento?", "Qual elemento?"],
    "habilidade": ["Habilidade?", "Skill?"],
    "dano": ["Dano?", "Quanto de dano?"],
    "peso": ["Peso?", "Ele levanta?"],
    "critico": ["Crítico?"],
    "velocidade_ataque": ["Velocidade?"],
    "_default": ["{CATEGORY}?"],
}

# Curto de proposito: a cena espera a fala terminar (ver
# timeline_builder.ajustar_ao_roteiro), entao cada palavra a mais e tempo
# de tela. O valor ja esta escrito grande; a voz da o veredito.
COMENTARIOS = {
    "TERRIBLE": ["{VALUE}. Horrível.", "{VALUE}. Desastre.", "{VALUE}. Doeu."],
    "BAD": ["{VALUE}. Ruim.", "{VALUE}. Fraco.", "{VALUE}. Não ajuda."],
    "WEAK": ["{VALUE}. Fraquinho.", "{VALUE}. Meh."],
    # Mediano: so o valor. A opiniao ja esta escrita na legenda, e cada
    # pausa aqui e ~1 s de cena esperando (a cena espera a fala).
    "AVERAGE": ["{VALUE}."],
    "GOOD": ["{VALUE}. Bom.", "{VALUE}. Gostei.", "{VALUE}. Ajuda."],
    "GREAT": ["{VALUE}! Muito bom!", "{VALUE}! Agora sim!", "{VALUE}! Olha isso!"],
    "INSANE": ["{VALUE}?! Absurdo!", "{VALUE}! Não acredito!", "{VALUE}! Histórico!"],
}

EXTREMOS = {
    "CONTRADICTORY": ["{VALUE}. Briga com a build."],
    "RARE": ["{VALUE}. Raro!", "{VALUE}. Isso quase não sai."],
    "FUNNY": ["{VALUE}. Piada."],
}


class NarrationGenerator:
    def build_script(self, rng: random.Random, edit_plan: dict, generation: dict) -> dict:
        lines: list[dict] = []
        personagem = generation.get("character", {}).get("nome", "")
        arma = generation.get("weapon", {}).get("nome", "")
        for event in edit_plan["events"]:
            tipo = event["type"]
            if tipo == "hook":
                lines.append(self._line(event, event.get("caption") or
                                        "Vamos criar um personagem completamente aleatório."))
            elif tipo == "roulette":
                lines.extend(self._roleta(rng, event))
            elif tipo == "stinger":
                lines.append(self._line(event, event.get("caption") or "Agora a arma."))
            elif tipo in ("identity", "nameplate"):
                lines.append(self._line(event, self._revelacao(event, personagem, arma)))
            elif tipo in ("reveal_character", "reveal_weapon"):
                entidade = "character" if tipo == "reveal_character" else "weapon"
                lines.append(self._line(event, f"{generation[entidade]['nome']}."))
            elif tipo == "synergy":
                score = generation["compatibility"]["compatibility_score"]
                lines.append(self._line(event, f"Compatibilidade: {score} de 100."))
            elif tipo == "gameplay":
                lines.append(self._line(event, event.get("narracao")
                                        or f"Agora {personagem} luta de verdade."))
            elif tipo == "final":
                score = generation.get("final_score")
                if score is None:
                    score = (event.get("build") or {}).get("final_score", "")
                lines.append(self._line(event, f"Nota final: {score}."))
            elif tipo == "outro":
                lines.append(self._line(event, event.get("caption") or ""))
        return {"tts": "voz.py", "lines": [l for l in lines if l["text"]]}

    # ---------------------------------------------------------------- roleta
    def _roleta(self, rng: random.Random, event: dict) -> list[dict]:
        roll = event["roll"]
        spin = float(event.get("spin_duration") or 0.0)
        total = float(event["duration"])
        start = float(event["start"])
        valor = self._valor_falado(roll)
        classe = event.get("classification")
        pool = EXTREMOS.get(classe) or COMENTARIOS.get(roll.get("tier", "AVERAGE"),
                                                       COMENTARIOS["AVERAGE"])
        comentario = rng.choice(pool).replace("{VALUE}", valor)
        # Roleta-relampago fica MUDA: e um numero que passa em 1 s, e ler
        # "seis virgula tres" leva mais que a cena inteira. Os estalos e o
        # som do resultado carregam o ritmo; a voz volta na proxima roleta
        # cheia. (O sorteio da frase acima acontece mesmo assim, para a
        # sequencia do rng nao mudar com a duracao.)
        if event.get("rapida"):
            return []
        saida = []
        pergunta = rng.choice(PERGUNTAS.get(roll.get("roulette_id"),
                                            PERGUNTAS["_default"]))
        pergunta = pergunta.replace("{CATEGORY}", str(roll.get("category", "")).lower())
        saida.append({"start": start, "duration": spin, "text": pergunta,
                      "evento": "roulette:pergunta"})
        saida.append({"start": round(start + spin, 3),
                      "duration": round(max(0.3, total - spin), 3),
                      "text": comentario, "evento": "roulette:resultado"})
        return saida

    @staticmethod
    def _valor_falado(roll: dict) -> str:
        """O valor como se fala: sem o rotulo entre parenteses da tela."""
        import re
        valor = str(roll.get("display_value", ""))
        return re.sub(r"\s*\([^)]*\)", "", valor).strip()

    @staticmethod
    def _revelacao(event: dict, personagem: str, arma: str) -> str:
        return {
            "character": f"Esse é {personagem}.",
            "weapon": f"E a arma: {arma}.",
            "character_weapon": f"{personagem}, com {arma}.",
        }.get(event.get("slot", "character"), f"{personagem}.")

    @staticmethod
    def _line(event: dict, text: str) -> dict:
        return {"start": event["start"], "duration": event["duration"],
                "text": text, "evento": event["type"]}
