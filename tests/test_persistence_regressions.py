"""Regression tests for JSON and match-configuration persistence."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from data import database
from models import Arma, Personagem


class JsonPersistenceRegressionTests(unittest.TestCase):
    def test_failed_save_does_not_corrupt_the_previous_json(self) -> None:
        """Serialization errors must leave the last valid file untouched."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            previous = {"version": 1, "fighters": ["A", "B"]}
            path.write_text(json.dumps(previous), encoding="utf-8")

            with self.assertRaises(TypeError):
                database.salvar_json(str(path), {"invalid": object()})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), previous)

    def test_match_config_round_trip_is_independent_from_working_directory(self) -> None:
        """All entrypoints must read and write the same absolute config path."""
        config = {
            "p1_nome": "A",
            "p2_nome": "B",
            "cenario": "Arena",
            "portrait_mode": True,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "match_config.json"
            other_cwd = Path(temp_dir) / "other"
            other_cwd.mkdir()

            with patch.object(database, "ARQUIVO_MATCH", str(config_path)):
                database.salvar_match_config(config)
                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    loaded = database.carregar_match_config()
                finally:
                    os.chdir(previous_cwd)

        self.assertEqual(loaded, config)

    def test_match_config_update_preserves_unknown_fields(self) -> None:
        """A new entrypoint must not erase options owned by another entrypoint."""
        previous = {
            "p1_nome": "Anterior A",
            "p2_nome": "Anterior B",
            "best_of": 5,
            "custom_option": "keep-me",
        }
        update = {
            "p1_nome": "Novo A",
            "p2_nome": "Novo B",
            "cenario": "Coliseu",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "match_config.json"
            config_path.write_text(json.dumps(previous), encoding="utf-8")

            with patch.object(database, "ARQUIVO_MATCH", str(config_path)):
                database.salvar_match_config(update)
                loaded = database.carregar_match_config()

        self.assertEqual(loaded["p1_nome"], "Novo A")
        self.assertEqual(loaded["p2_nome"], "Novo B")
        self.assertEqual(loaded["best_of"], 5)
        self.assertEqual(loaded["custom_option"], "keep-me")

    def test_character_reload_uses_effective_weapon_weight(self) -> None:
        """Rarity modifiers must not change character speed after a round-trip."""
        weapon = Arma(
            nome="Peso efetivo",
            tipo="Reta",
            dano=10,
            peso=10,
            raridade="Mítico",
            comp_cabo=20,
            comp_lamina=50,
            largura=5,
        )
        original = Personagem(
            "Persistente",
            tamanho=2.0,
            forca=8.0,
            mana=2.0,
            nome_arma=weapon.nome,
            peso_arma_cache=weapon.peso,
        )

        def load_fixture(path):
            if path == database.ARQUIVO_CHARS:
                return [original.to_dict()]
            if path == database.ARQUIVO_ARMAS:
                return [weapon.to_dict()]
            self.fail(f"caminho inesperado: {path}")

        with (
            patch.object(database, "carregar_json", side_effect=load_fixture),
            patch.object(
                database,
                "resolver_database_paths",
                return_value=(database.ARQUIVO_ARMAS, database.ARQUIVO_CHARS),
            ),
        ):
            reloaded = database.carregar_personagens()[0]

        self.assertAlmostEqual(reloaded.velocidade, original.velocidade)


if __name__ == "__main__":
    unittest.main()
