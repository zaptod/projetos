"""CaptionGenerator: legendas direto dos dados (sem speech-to-text).

Cada rolagem vira uma legenda shitposter montada combinatoriamente:
  prefixo(tier) + nucleo(roleta + banda de qualidade) + sufixo(tier)
Os nucleos vivem em config/frases.json, escritos POR ROLETA — velocidade ruim
zoa a lentidao, forca insana zoa a forca — e a combinacao com prefixos e
sufixos garante 500+ legendas possiveis distintas para cada (roleta x tier).
"""
from __future__ import annotations

import random

BAND_BY_TIER = {
    "TERRIBLE": "negativo", "BAD": "negativo", "WEAK": "negativo",
    "AVERAGE": "mediano", "GOOD": "positivo", "GREAT": "positivo",
    "INSANE": "insano",
}
POOL_BY_TIER = {
    "TERRIBLE": "negativo_forte", "BAD": "negativo", "WEAK": "negativo",
    "AVERAGE": "neutro", "GOOD": "positivo", "GREAT": "positivo",
    "INSANE": "hype",
}


class CaptionGenerator:
    def __init__(self, captions_config: dict, frases_config: dict):
        self.config = captions_config
        self.frases = frases_config

    def _pick(self, rng: random.Random, pool: list[str]) -> str:
        return rng.choice(pool)

    # ------------------------------------------------------------ montagem
    def _compor(self, rng: random.Random, nucleo: str, tier: str) -> str:
        prefixo = self._pick(rng, self.frases["prefixos"][POOL_BY_TIER[tier]])
        sufixo = self._pick(rng, self.frases["sufixos"][POOL_BY_TIER[tier]])
        if sufixo.strip(",.!? ").lower() == prefixo.strip(",.!? ").lower():
            sufixo = ""
        return " ".join(parte for parte in (prefixo, nucleo, sufixo) if parte)

    def _nucleos(self, roulette_id: str, band: str) -> list[str]:
        banco = self.frases["por_roleta"].get(roulette_id, {})
        return banco.get(band) or self.frases["_default"][band]

    def pool_size(self, roulette_id: str, tier: str) -> int:
        """Quantas legendas distintas existem para (roleta, tier)."""
        nucleos = self._nucleos(roulette_id, BAND_BY_TIER[tier])
        pool = POOL_BY_TIER[tier]
        return (len(nucleos) * len(self.frases["prefixos"][pool])
                * len(self.frases["sufixos"][pool]))

    # -------------------------------------------------------------- eventos
    def for_event(self, rng: random.Random, event: dict) -> str:
        # descompasso contextual (peso x forca) tem banco proprio
        method = event["evaluation"]
        if isinstance(method, dict):
            method = method.get("method")
        if method == "contextual" and event["roulette_id"] == "peso":
            if event["score"] <= 20:
                nucleo = self._pick(rng, self.frases["contextual"]["cant_lift"])
                nucleo = nucleo.replace("{VALUE}", event["display_value"])
                return self._compor(rng, nucleo, "TERRIBLE")
            if event["score"] >= 80:
                nucleo = self._pick(rng, self.frases["contextual"]["perfect_fit"])
                return self._compor(rng, nucleo, "INSANE")

        nucleo = self._pick(rng, self._nucleos(event["roulette_id"],
                                               BAND_BY_TIER[event["tier"]]))
        nucleo = (nucleo
                  .replace("{CATEGORY}", event["category"])
                  .replace("{VALUE}", event["display_value"]))
        return self._compor(rng, nucleo, event["tier"])

    # ----------------------------------------------------------- torneio
    def torneio_hook(self, rng: random.Random, quantidade: int) -> str:
        return self._pick(rng, self.frases["torneio"]["hook"]).replace(
            "{N}", str(quantidade))

    def torneio_card(self, rng: random.Random, luta: dict) -> str:
        banco = self.frases["torneio"]
        if luta.get("favorito") and rng.random() < 0.4:
            texto = self._pick(rng, banco["card_favorito"]).replace(
                "{FAV}", luta["favorito"])
        else:
            texto = self._pick(rng, banco["card"])
        return texto.replace("{P1}", luta["p1"]).replace("{P2}", luta["p2"])

    def torneio_resultado(self, rng: random.Random, luta: dict) -> str:
        banco = self.frases["torneio"]
        marcas = [m for m in luta.get("marcas", []) if m in banco["marcas"]]
        # uma marca especial (zebra, virada, duplo KO...) rouba a cena
        if marcas and rng.random() < 0.75:
            nucleo = self._pick(rng, banco["marcas"][rng.choice(marcas)])
        else:
            nucleo = self._pick(rng, banco["resultado"][BAND_BY_TIER[luta["tier"]]])
        nucleo = (nucleo
                  .replace("{VENCEDOR}", luta["vencedor"])
                  .replace("{PERDEDOR}", luta["perdedor"])
                  .replace("{DURACAO}", str(luta["duracao"]))
                  .replace("{HP}", str(luta["hp_vencedor"])))
        return self._compor(rng, nucleo, luta["tier"])

    def torneio_campeao(self, rng: random.Random, torneio: dict) -> str:
        banco = self.frases["torneio"]["campeao"]
        hp_medio = torneio.get("estatisticas", {}).get("hp_medio_campeao", 0)
        if hp_medio >= 60:
            pool = banco["dominante"]
        elif hp_medio and hp_medio <= 25:
            pool = banco["sofrido"]
        else:
            pool = banco["gerado"] if torneio.get("campeao_gerado") else banco["banco"]
        return (self._pick(rng, pool)
                .replace("{CAMPEAO}", str(torneio.get("campeao", "???")))
                .replace("{HP}", str(hp_medio)))

    # ------------------------------------------------------- demais telas
    def hook(self, rng: random.Random) -> str:
        return self._pick(rng, self.config["hook"])

    def stinger(self, rng: random.Random, entity: str) -> str:
        """Batida curta de virada entre as roletas do personagem e as da arma.

        Existe para o corte nao ficar seco: sem ela o video passa do clipe do
        personagem direto para uma roleta laranja, e o espectador leva meio
        segundo para entender que comecou outra metade.
        """
        banco = self.config.get("stinger", {})
        pool = banco.get(entity) or ["AGORA A ARMA"]
        return self._pick(rng, pool)

    def outro(self, rng: random.Random) -> str:
        return self._pick(rng, self.config["outro"])

    def for_reveal(self, rng: random.Random, kind: str, name: str) -> str:
        key = "reveal_character" if kind == "character" else "reveal_weapon"
        return self._pick(rng, self.config[key]).replace("{NAME}", name.upper())

    def for_identity(self, rng: random.Random, personagem: dict) -> str:
        """Legenda do clipe de identidade visual (Digen)."""
        return (self._pick(rng, self.config["identity"])
                .replace("{NAME}", str(personagem.get("nome", "")).upper())
                .replace("{CLASSE}", str(personagem.get("classe", "")).upper()))

    def for_synergy(self, rng: random.Random, compatibility: dict) -> str:
        score = compatibility["compatibility_score"]
        if score >= 70:
            pool = self.config["synergy"]["positive"]
        elif score <= 40:
            pool = self.config["synergy"]["negative"]
        else:
            pool = self.config["synergy"]["neutral"]
        return self._pick(rng, pool)

    def for_final(self, rng: random.Random, build: dict) -> str:
        pool = self.config["final_by_verdict"][build["verdict"]]
        return self._pick(rng, pool).replace("{SCORE}", str(build["final_score"]))
