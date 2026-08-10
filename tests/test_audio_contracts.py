"""Contratos estaticos do catalogo de audio."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from effects.audio import AudioManager


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


if __name__ == "__main__":
    unittest.main()
