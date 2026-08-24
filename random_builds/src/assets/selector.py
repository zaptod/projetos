"""AssetSelector: escolhe o video de reacao pela CATEGORIA (tier) do momento,
com cadeia de fallback e controle de uso para nao repetir o mesmo clipe no
video. Sem clipe compativel -> descritor sintetico (o renderer desenha o
cartao)."""
from __future__ import annotations

import random

from .catalog import AssetCatalog, CATEGORY_PROFILE

TIER_TO_CATEGORY = {
    "TERRIBLE": "terrible", "BAD": "bad", "WEAK": "bad", "AVERAGE": "neutral",
    "GOOD": "good", "GREAT": "great", "INSANE": "insane",
}
FALLBACKS = {
    "terrible": ["terrible", "bad"],
    "bad": ["bad", "terrible"],
    "neutral": ["neutral", "good", "bad"],
    "good": ["good", "great"],
    "great": ["great", "insane", "good"],
    "insane": ["insane", "great"],
    # Categorias editoriais: caem para o tier mais proximo em espirito quando
    # a biblioteca ainda nao tem clipe proprio delas.
    "funny": ["funny", "insane", "neutral"],
    "contradictory": ["contradictory", "funny", "bad", "terrible"],
    "rare": ["rare", "insane", "great"],
}


class AssetSelector:
    def __init__(self, catalog: AssetCatalog):
        self.catalog = catalog
        self.last_id: str | None = None

    def select_reaction(self, rng: random.Random, tier: str,
                        sentiment: str, intensity: float,
                        category: str | None = None) -> dict:
        """Escolha ALEATORIA entre todos os clipes que se encaixam na
        categoria (evitando so repetir o mesmo clipe duas vezes seguidas
        quando ha mais de um disponivel).

        `category` vem da classe editorial da rolagem (secao 11) e manda mais
        que o tier: e ela que sabe a diferenca entre "foi ruim" e "foi
        contraditorio". Sem ela, cai no mapa por tier de sempre.
        """
        category = category or TIER_TO_CATEGORY.get(tier, "neutral")
        for candidate_cat in FALLBACKS.get(category, [category]):
            candidates = self.catalog.reactions_by_category(candidate_cat)
            if not candidates:
                continue
            pool = [c for c in candidates if c["id"] != self.last_id] or candidates
            choice = rng.choice(pool)
            self.last_id = choice["id"]
            return {**choice, "synthetic": False}
        return {
            "id": f"synthetic_{category}",
            "kind": "reaction", "category": category,
            "sentiment": sentiment or CATEGORY_PROFILE[category][0],
            "intensity": intensity, "synthetic": True,
        }

    def select_music(self, rng: random.Random) -> dict | None:
        candidates = self.catalog.query("music")
        return rng.choice(candidates) if candidates else None
