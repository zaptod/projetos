"""Contratos estaticos do catalogo de audio."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from effects.audio import AudioManager
from effects.audio_paths import (
    SOUND_RUNTIME_DIR_ENV,
    load_sound_config,
    resolve_sound_file,
    save_sound_config,
)


class AudioContractTests(unittest.TestCase):
    def test_every_configured_event_has_an_asset_or_a_valid_fallback(self) -> None:
        sound_dir = Path(__file__).resolve().parents[1] / "sounds"
        config = json.loads((sound_dir / "sound_config.json").read_text(encoding="utf-8"))

        unresolved = []
        for name, filename in config.items():
            if name.startswith("_"):
                continue
            if (sound_dir / filename).is_file():
                continue

            visited = {name}
            fallback = AudioManager.SOUND_FALLBACKS.get(name)
            while fallback and fallback not in visited:
                visited.add(fallback)
                configured = config.get(fallback)
                if configured and (sound_dir / configured).is_file():
                    break
                for extension in (".wav", ".ogg", ".mp3"):
                    if (sound_dir / f"{fallback}{extension}").is_file():
                        configured = f"{fallback}{extension}"
                        break
                if configured and (sound_dir / configured).is_file():
                    break
                fallback = AudioManager.SOUND_FALLBACKS.get(fallback)
            else:
                unresolved.append(name)

        self.assertEqual([], unresolved)

    def test_fallback_graph_contains_no_cycles(self) -> None:
        for start in AudioManager.SOUND_FALLBACKS:
            visited = set()
            current = start
            while current in AudioManager.SOUND_FALLBACKS:
                self.assertNotIn(current, visited, f"ciclo de fallback iniciado em {start}")
                visited.add(current)
                current = AudioManager.SOUND_FALLBACKS[current]

    def test_runtime_overrides_do_not_modify_packaged_sound_assets(self) -> None:
        package_config = Path(__file__).resolve().parents[1] / "sounds" / "sound_config.json"
        original_text = package_config.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {SOUND_RUNTIME_DIR_ENV: temp_dir}):
                config = load_sound_config()
                self.assertIn("slash_light", config)
                config["_volumes"] = {"master": 0.25}
                destination = save_sound_config(config)
                self.assertEqual(destination.parent, Path(temp_dir))
                self.assertEqual(load_sound_config()["_volumes"]["master"], 0.25)
                self.assertEqual(
                    resolve_sound_file(config["slash_light"]).parent,
                    package_config.parent,
                )

        self.assertEqual(package_config.read_text(encoding="utf-8"), original_text)


if __name__ == "__main__":
    unittest.main()
