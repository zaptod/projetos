"""Contratos estaticos do catalogo de audio."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neural_fights.effects.audio import AudioManager
from neural_fights.effects.audio_paths import (
    PACKAGE_SOUND_DIR,
    SOUND_RUNTIME_DIR_ENV,
    load_sound_config,
    remove_runtime_sound_overrides,
    resolve_sound_file,
    save_sound_config,
)
from neural_fights.ui.view_sons import TelaSons


class AudioContractTests(unittest.TestCase):
    def test_every_configured_event_has_an_asset_or_a_valid_fallback(self) -> None:
        sound_dir = PACKAGE_SOUND_DIR
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
        package_config = PACKAGE_SOUND_DIR / "sound_config.json"
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

    def test_clearing_event_removes_only_its_runtime_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_dir = Path(temp_dir)
            own_files = [
                runtime_dir / "slash_light.wav",
                runtime_dir / "slash_light.ogg",
            ]
            unrelated = runtime_dir / "hit_flesh.wav"
            for path in [*own_files, unrelated]:
                path.write_bytes(b"audio")

            with patch.dict(os.environ, {SOUND_RUNTIME_DIR_ENV: temp_dir}):
                self.assertEqual(remove_runtime_sound_overrides("slash_light"), 2)

            self.assertTrue(unrelated.is_file())
            self.assertTrue(all(not path.exists() for path in own_files))

    def test_configured_filename_cannot_escape_sound_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outside = Path(temp_dir) / "secret.wav"
            outside.write_bytes(b"not a sound override")
            runtime = Path(temp_dir) / "sounds"
            runtime.mkdir()
            with patch.dict(os.environ, {SOUND_RUNTIME_DIR_ENV: str(runtime)}):
                self.assertIsNone(resolve_sound_file("../secret.wav"))

    def test_ui_save_keeps_slider_values_when_audio_singleton_reloads(self) -> None:
        screen = object.__new__(TelaSons)
        screen.sound_config = {"slash_light": "slash_light.mp3"}
        screen.sound_widgets = {}
        screen.volume_sliders = {
            "master": {"var": SimpleNamespace(get=lambda: 25)},
            "golpes": {"var": SimpleNamespace(get=lambda: 40)},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            observed_volumes = {}
            audio = Mock()

            def reload_from_saved_snapshot() -> None:
                observed_volumes.update(load_sound_config()["_volumes"])

            audio.reload_sounds.side_effect = reload_from_saved_snapshot
            audio.save_volume_config.side_effect = AssertionError(
                "singleton obsoleto nao deve regravar os sliders"
            )
            with (
                patch.dict(os.environ, {SOUND_RUNTIME_DIR_ENV: temp_dir}),
                patch("neural_fights.effects.audio.AudioManager.get_instance", return_value=audio),
                patch("neural_fights.ui.view_sons.messagebox.showinfo"),
            ):
                screen._salvar_tudo()
                persisted = load_sound_config()["_volumes"]

        self.assertEqual(persisted, {"master": 0.25, "golpes": 0.4})
        self.assertEqual(observed_volumes, persisted)
        audio.reload_sounds.assert_called_once_with()
        audio.save_volume_config.assert_not_called()

    def test_ui_clear_removes_override_and_restores_packaged_fallback(self) -> None:
        screen = object.__new__(TelaSons)
        screen.sound_config = {"slash_light": "slash_light.mp3"}
        file_var = Mock()
        status_label = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            override = Path(temp_dir) / "slash_light.mp3"
            override.write_bytes(b"custom override")
            with (
                patch.dict(os.environ, {SOUND_RUNTIME_DIR_ENV: temp_dir}),
                patch.object(screen, "_atualizar_status") as update_status,
            ):
                self.assertEqual(resolve_sound_file("slash_light.mp3"), override)
                screen._limpar_som("slash_light", file_var, status_label)
                resolved = resolve_sound_file("slash_light.mp3")

            self.assertFalse(override.exists())

        self.assertEqual(resolved, PACKAGE_SOUND_DIR / "slash_light.mp3")
        self.assertNotIn("slash_light", screen.sound_config)
        file_var.set.assert_called_once_with("")
        update_status.assert_called_once_with("slash_light", "", status_label)


if __name__ == "__main__":
    unittest.main()
