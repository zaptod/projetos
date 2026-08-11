"""Caminhos de assets imutaveis e overrides locais de audio."""

from __future__ import annotations

import os
from pathlib import Path

from neural_fights.data import database


SOUND_RUNTIME_DIR_ENV = "NEURAL_FIGHTS_SOUND_RUNTIME_DIR"
PACKAGE_SOUND_DIR = Path(__file__).resolve().parents[1] / "sounds"
SUPPORTED_SOUND_EXTENSIONS = (".wav", ".ogg", ".mp3")


def get_runtime_sound_dir() -> Path:
    override = os.environ.get(SOUND_RUNTIME_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return Path(database.resolver_runtime_data_dir()) / "sounds"


def get_runtime_config_path() -> Path:
    return get_runtime_sound_dir() / "sound_config.json"


def get_package_config_path() -> Path:
    return PACKAGE_SOUND_DIR / "sound_config.json"


def load_sound_config() -> dict:
    """Prefere o snapshot local completo e usa o empacotado como default."""
    runtime_config = get_runtime_config_path()
    source = runtime_config if runtime_config.is_file() else get_package_config_path()
    config = database.carregar_json(str(source), padrao={})
    if not isinstance(config, dict):
        raise database.DataValidationError(
            f"configuracao de audio deve ser um objeto JSON: {source}"
        )
    return dict(config)


def save_sound_config(config: dict) -> Path:
    if not isinstance(config, dict):
        raise TypeError("configuracao de audio deve ser um dicionario")
    destination = get_runtime_config_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    database.salvar_json(str(destination), config)
    return destination


def resolve_sound_file(filename: str | None) -> Path | None:
    if not isinstance(filename, str) or not filename:
        return None
    if Path(filename).name != filename:
        return None
    for directory in (get_runtime_sound_dir(), PACKAGE_SOUND_DIR):
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def remove_runtime_sound_overrides(event_id: str) -> int:
    """Remove somente arquivos locais do evento, nunca assets do pacote."""

    if not event_id or Path(event_id).name != event_id:
        raise ValueError("event_id de audio invalido")
    runtime_dir = get_runtime_sound_dir()
    removed = 0
    for extension in SUPPORTED_SOUND_EXTENSIONS:
        candidate = runtime_dir / f"{event_id}{extension}"
        if candidate.is_file():
            candidate.unlink()
            removed += 1
    return removed
