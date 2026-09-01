"""Biblioteca de videos de reacao indexada por ID.

Fonte primaria: assets/reactions/catalog.json + arquivos 0001.mp4, 0002.mp4...
(criados pelo comando `import-reactions`). Cada entrada tem categoria por tier
(terrible/bad/neutral/good/great/insane), que substitui a tela de reacao
sintetica. Compatibilidade: entradas legadas de assets/metadata.json e clipes
soltos em subpastas por categoria tambem sao carregados.

A biblioteca funciona VAZIA: sem clipe compativel, o renderer desenha o
cartao sintetico.
"""
from __future__ import annotations

import json
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".gif"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}

# categoria -> (sentimento, intensidade) usada quando um clipe substitui o cartao
CATEGORY_PROFILE = {
    "terrible": ("negative", 0.9),
    "bad": ("negative", 0.6),
    "neutral": ("neutral", 0.3),
    "good": ("positive", 0.5),
    "great": ("positive", 0.75),
    "insane": ("positive", 0.95),
    # Categorias EDITORIAIS (secao 11): nao existe tier para elas, existe
    # situacao. Uma arma absurda que o personagem nao levanta nao e "ruim",
    # e contraditoria - e a reacao certa e outra.
    "funny": ("positive", 0.8),
    "contradictory": ("negative", 0.7),
    "rare": ("positive", 0.85),
}
CATEGORIES = list(CATEGORY_PROFILE)

# As categorias que saem de um TIER. `category_from_sentiment` so pode devolver
# uma destas: as editoriais dependem da situacao, nunca de sentimento sozinho.
TIER_CATEGORIES = ("terrible", "bad", "neutral", "good", "great", "insane")


def category_from_sentiment(sentiment: str, intensity: float) -> str:
    candidates = [(cat, CATEGORY_PROFILE[cat]) for cat in TIER_CATEGORIES
                  if CATEGORY_PROFILE[cat][0] == sentiment]
    if not candidates:
        return "neutral"
    return min(candidates, key=lambda cp: abs(cp[1][1] - intensity))[0]


class AssetCatalog:
    def __init__(self, assets_dir: Path):
        self.assets_dir = Path(assets_dir)
        self.reactions_dir = self.assets_dir / "reactions"
        self.entries: list[dict] = []
        self._load()

    # ------------------------------------------------------------------- carga
    def _load(self) -> None:
        seen: set[str] = set()
        self._load_reaction_catalog(seen)
        self._load_legacy_metadata(seen)
        self._load_category_folders(seen)
        self._load_audio(seen)

    def _load_reaction_catalog(self, seen: set[str]) -> None:
        path = self.reactions_dir / "catalog.json"
        if not path.exists():
            return
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        for entry in data.get("reactions", []):
            file = self.reactions_dir / entry["file"]
            if not file.exists():
                continue
            sentiment, intensity = CATEGORY_PROFILE.get(
                entry.get("category", "neutral"), ("neutral", 0.3))
            self.entries.append({
                "id": entry["id"], "kind": "reaction", "path": str(file),
                "category": entry.get("category", "neutral"),
                "sentiment": entry.get("sentiment", sentiment),
                "intensity": entry.get("intensity", intensity),
                "duration": entry.get("duration"),
                "tags": entry.get("tags", []),
            })
            seen.add(str(file))

    def _load_legacy_metadata(self, seen: set[str]) -> None:
        path = self.assets_dir / "metadata.json"
        if not path.exists():
            return
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        for entry in data.get("assets", []):
            file = self.assets_dir / entry["file"]
            if not file.exists() or str(file) in seen:
                continue
            entry = dict(entry)
            entry["path"] = str(file)
            entry.setdefault("category", category_from_sentiment(
                entry.get("sentiment", "neutral"), entry.get("intensity", 0.5)))
            self.entries.append(entry)
            seen.add(str(file))

    def _load_category_folders(self, seen: set[str]) -> None:
        if not self.reactions_dir.exists():
            return
        for folder in CATEGORIES:
            for file in sorted((self.reactions_dir / folder).glob("*")):
                if file.suffix.lower() in VIDEO_EXT and str(file) not in seen:
                    sentiment, intensity = CATEGORY_PROFILE[folder]
                    self.entries.append({
                        "id": file.stem, "kind": "reaction", "path": str(file),
                        "category": folder, "sentiment": sentiment,
                        "intensity": intensity, "duration": None, "tags": [],
                    })
                    seen.add(str(file))

    def _load_audio(self, seen: set[str]) -> None:
        for kind in ("sfx", "music"):
            folder = self.assets_dir / kind
            if not folder.exists():
                continue
            for file in sorted(folder.glob("*")):
                if file.suffix.lower() in AUDIO_EXT and str(file) not in seen:
                    self.entries.append({
                        "id": file.stem, "kind": kind, "path": str(file),
                        "sentiment": "neutral", "intensity": 0.5, "tags": [],
                    })
                    seen.add(str(file))

    # ----------------------------------------------------------------- queries
    def reactions_by_category(self, category: str) -> list[dict]:
        return [e for e in self.entries
                if e.get("kind") == "reaction" and e.get("category") == category]

    def query(self, kind: str) -> list[dict]:
        return [e for e in self.entries if e.get("kind") == kind]
