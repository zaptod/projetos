"""Regression tests for JSON and match-configuration persistence."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from neural_fights.data import database
from neural_fights.models import Arma, Personagem


class JsonPersistenceRegressionTests(unittest.TestCase):
    def test_duplicate_json_keys_are_rejected_instead_of_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "duplicate.json"
            path.write_text('{"fighter": "A", "fighter": "B"}', encoding="utf-8")

            with self.assertRaisesRegex(
                database.DataValidationError,
                "chave JSON duplicada: 'fighter'",
            ):
                database.carregar_json(str(path))

    def test_public_persistence_waits_for_another_process(self) -> None:
        """The lock must cover separate CLI/UI processes, not only threads."""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "match.json"
            env = os.environ.copy()
            script = (
                "from neural_fights.data import database; "
                "database.salvar_match_config({'child': True}, "
                f"arquivo={str(config_path)!r}); "
                "print('saved', flush=True)"
            )

            with database._bloqueio_persistencia_interprocesso():
                child = subprocess.Popen(
                    [sys.executable, "-c", script],
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                time.sleep(0.2)
                self.assertIsNone(child.poll())

            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(0, child.returncode, stderr)
            self.assertEqual("saved", stdout.strip())
            self.assertEqual(
                {"child": True},
                json.loads(config_path.read_text(encoding="utf-8")),
            )

    def test_failed_save_does_not_corrupt_the_previous_json(self) -> None:
        """Serialization errors must leave the last valid file untouched."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            previous = {"version": 1, "fighters": ["A", "B"]}
            path.write_text(json.dumps(previous), encoding="utf-8")

            with self.assertRaises(TypeError):
                database.salvar_json(str(path), {"invalid": object()})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), previous)

    def test_non_finite_numbers_are_not_written_as_json(self) -> None:
        """NaN and infinities are JavaScript extensions, not RFC JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            previous = {"version": 1}
            path.write_text(json.dumps(previous), encoding="utf-8")

            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    database.salvar_json(str(path), {"invalid": value})

                self.assertEqual(
                    previous,
                    json.loads(path.read_text(encoding="utf-8")),
                )
                self.assertEqual(
                    [],
                    list(path.parent.glob(f".{path.name}.*.tmp")),
                )

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

    def test_concurrent_match_updates_are_serialized_without_lost_fields(self) -> None:
        """The public read-modify-write operation must hold one process lock."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "match_config.json"
            config_path.write_text(json.dumps({"base": True}), encoding="utf-8")

            carregar_real = database.carregar_match_config
            primeiro_leu = threading.Event()
            liberar_primeiro = threading.Event()
            segundo_leu = threading.Event()
            segundo_testou_lock = threading.Event()
            segundo_adquiriu_lock: list[bool] = []
            erros: list[BaseException] = []

            class RLockObservavel:
                def __init__(self):
                    self._lock = threading.RLock()

                def __enter__(self):
                    if (
                        threading.current_thread().name == "writer-b"
                        and not segundo_adquiriu_lock
                    ):
                        adquiriu = self._lock.acquire(blocking=False)
                        segundo_adquiriu_lock.append(adquiriu)
                        segundo_testou_lock.set()
                        if adquiriu:
                            return self
                    self._lock.acquire()
                    return self

                def __exit__(self, _exc_type, _exc_value, _traceback):
                    self._lock.release()

            def carregar_observavel(arquivo=None):
                dados = carregar_real(arquivo)
                nome = threading.current_thread().name
                if nome == "writer-a":
                    primeiro_leu.set()
                    if not liberar_primeiro.wait(5):
                        raise TimeoutError("writer-a nao foi liberado")
                elif nome == "writer-b":
                    segundo_leu.set()
                return dados

            def salvar(nome_campo):
                try:
                    database.salvar_match_config(
                        {nome_campo: True},
                        arquivo=str(config_path),
                    )
                except BaseException as exc:  # pragma: no cover - reportado abaixo
                    erros.append(exc)

            with (
                patch.object(database, "_PERSISTENCE_LOCK", RLockObservavel()),
                patch.object(
                    database,
                    "carregar_match_config",
                    side_effect=carregar_observavel,
                ),
            ):
                writer_a = threading.Thread(
                    target=salvar,
                    args=("writer_a",),
                    name="writer-a",
                )
                writer_b = threading.Thread(
                    target=salvar,
                    args=("writer_b",),
                    name="writer-b",
                )
                writer_a.start()
                self.assertTrue(primeiro_leu.wait(2))
                writer_b.start()
                self.assertTrue(segundo_testou_lock.wait(2))
                self.assertEqual([False], segundo_adquiriu_lock)
                self.assertFalse(segundo_leu.is_set())
                liberar_primeiro.set()
                writer_a.join(5)
                writer_b.join(5)

            self.assertFalse(writer_a.is_alive())
            self.assertFalse(writer_b.is_alive())
            self.assertEqual([], erros)
            self.assertEqual(
                {"base": True, "writer_a": True, "writer_b": True},
                json.loads(config_path.read_text(encoding="utf-8")),
            )

    def test_explicit_missing_match_config_never_falls_back_to_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.json"
            with (
                patch.dict(
                    os.environ,
                    {database.MATCH_CONFIG_ENV: str(missing)},
                ),
                self.assertRaises(FileNotFoundError),
            ):
                database.carregar_match_config()

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
