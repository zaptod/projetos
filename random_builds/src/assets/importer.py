"""Importador da biblioteca de reacoes.

`python main.py import-reactions <pasta-ou-arquivo> --categoria insane`
- atribui o proximo ID sequencial (0001, 0002, ...)
- copia (ou move) o clipe para assets/reactions/<id>.<ext>
- mede a duracao com ffprobe
- registra categoria/duracao no assets/reactions/catalog.json
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .catalog import CATEGORIES, CATEGORY_PROFILE, VIDEO_EXT

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _probe_duration(path: Path) -> float | None:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        return round(float(result.stdout.strip()), 2)
    except (ValueError, subprocess.SubprocessError, OSError):
        return None


def probe_info(path: Path) -> dict:
    """Duracao + resolucao de um video (para o assistente mostrar antes de importar)."""
    info = {"duration": _probe_duration(path), "width": None, "height": None}
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        parts = result.stdout.strip().split(",")
        if len(parts) >= 2:
            info["width"], info["height"] = int(parts[0]), int(parts[1])
    except (ValueError, subprocess.SubprocessError, OSError):
        pass
    return info


def _load_catalog(reactions_dir: Path) -> dict:
    path = reactions_dir / "catalog.json"
    if path.exists():
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    return {"next_id": 1, "reactions": []}


def _save_catalog(reactions_dir: Path, data: dict) -> None:
    with open(reactions_dir / "catalog.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def import_reactions(source: Path, category: str, assets_dir: Path,
                     move: bool = False) -> list[dict]:
    if category not in CATEGORIES:
        raise ValueError(
            f"Categoria invalida: {category!r}. Use uma de: {', '.join(CATEGORIES)}")
    source = Path(source)
    files = [source] if source.is_file() else sorted(
        f for f in source.iterdir() if f.suffix.lower() in VIDEO_EXT)
    if not files:
        raise FileNotFoundError(f"Nenhum video encontrado em {source}")

    reactions_dir = Path(assets_dir) / "reactions"
    reactions_dir.mkdir(parents=True, exist_ok=True)
    catalog = _load_catalog(reactions_dir)
    known_ids = {e["id"] for e in catalog["reactions"]}
    next_id = max([catalog.get("next_id", 1)]
                  + [int(i) + 1 for i in known_ids if str(i).isdigit()])

    imported = []
    sentiment, intensity = CATEGORY_PROFILE[category]
    for file in files:
        asset_id = f"{next_id:04d}"
        next_id += 1
        dest = reactions_dir / f"{asset_id}{file.suffix.lower()}"
        (shutil.move if move else shutil.copy2)(str(file), str(dest))
        entry = {
            "id": asset_id,
            "file": dest.name,
            "category": category,
            "sentiment": sentiment,
            "intensity": intensity,
            "duration": _probe_duration(dest),
            "source": file.name,
            "tags": [],
        }
        catalog["reactions"].append(entry)
        imported.append(entry)

    catalog["next_id"] = next_id
    _save_catalog(reactions_dir, catalog)
    return imported


def list_reactions(assets_dir: Path) -> list[dict]:
    return _load_catalog(Path(assets_dir) / "reactions")["reactions"]


def recategorize_reaction(asset_id: str, category: str, assets_dir: Path) -> dict | None:
    if category not in CATEGORIES:
        raise ValueError(
            f"Categoria invalida: {category!r}. Use uma de: {', '.join(CATEGORIES)}")
    reactions_dir = Path(assets_dir) / "reactions"
    catalog = _load_catalog(reactions_dir)
    for entry in catalog["reactions"]:
        if entry["id"] == asset_id:
            sentiment, intensity = CATEGORY_PROFILE[category]
            entry.update({"category": category, "sentiment": sentiment,
                          "intensity": intensity})
            _save_catalog(reactions_dir, catalog)
            return entry
    return None


def remove_reaction(asset_id: str, assets_dir: Path) -> dict | None:
    reactions_dir = Path(assets_dir) / "reactions"
    catalog = _load_catalog(reactions_dir)
    for entry in list(catalog["reactions"]):
        if entry["id"] == asset_id:
            catalog["reactions"].remove(entry)
            _save_catalog(reactions_dir, catalog)
            file = reactions_dir / entry["file"]
            if file.exists():
                file.unlink()
            return entry
    return None
