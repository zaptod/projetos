"""Regression tests for the public command-line entrypoint."""

from __future__ import annotations

import io
import sys
import types
import unittest
from unittest.mock import patch

import run as entrypoint
import run_tournament as tournament_entrypoint
from data import database
from simulation.simulacao import Simulador


class EntrypointRegressionTests(unittest.TestCase):
    def test_sim_mode_runs_the_simulator_public_loop(self) -> None:
        """``--sim`` must call the public loop exposed by ``Simulador``."""

        class FakeSimulador:
            instances: list["FakeSimulador"] = []
            default_config = {
                "p1_nome": "Primeiro",
                "p2_nome": "Segundo",
                "cenario": "Arena",
            }

            @classmethod
            def criar_match_config_padrao(cls):
                return dict(cls.default_config)

            def __init__(self, *, match_config) -> None:
                self.match_config = match_config
                self.run_called = False
                self.__class__.instances.append(self)

            def run(self) -> None:
                self.run_called = True

        fake_simulation = types.ModuleType("simulation")
        fake_simulation.Simulador = FakeSimulador

        with (
            patch.dict(sys.modules, {"simulation": fake_simulation}),
            patch.object(sys, "argv", ["run.py", "--sim"]),
        ):
            exit_code = entrypoint.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(FakeSimulador.instances), 1)
        self.assertEqual(FakeSimulador.instances[0].match_config, FakeSimulador.default_config)
        self.assertTrue(FakeSimulador.instances[0].run_called)

    def test_default_sim_match_uses_first_two_characters_without_runtime_state(self) -> None:
        roster = [types.SimpleNamespace(nome="Primeiro"), types.SimpleNamespace(nome="Segundo")]
        with (
            patch.object(database, "carregar_personagens", return_value=roster),
            patch.object(
                database,
                "carregar_match_config",
                side_effect=AssertionError("não deve ler match_config runtime"),
            ),
            patch.object(
                database,
                "salvar_match_config",
                side_effect=AssertionError("não deve gravar match_config runtime"),
            ),
        ):
            config = Simulador.criar_match_config_padrao()

        self.assertEqual(config["p1_nome"], "Primeiro")
        self.assertEqual(config["p2_nome"], "Segundo")
        self.assertEqual(config["best_of"], 1)

    def test_sim_mode_returns_nonzero_when_roster_has_fewer_than_two(self) -> None:
        class InsufficientRosterSimulator:
            @staticmethod
            def criar_match_config_padrao():
                raise RuntimeError("São necessários pelo menos 2 personagens")

        fake_simulation = types.ModuleType("simulation")
        fake_simulation.Simulador = InsufficientRosterSimulator
        stderr = io.StringIO()
        with (
            patch.dict(sys.modules, {"simulation": fake_simulation}),
            patch.object(sys, "argv", ["run.py", "--sim"]),
            patch.object(sys, "stderr", stderr),
        ):
            exit_code = entrypoint.main()

        self.assertEqual(exit_code, 1)
        self.assertIn("pelo menos 2 personagens", stderr.getvalue())

    def test_help_is_printable_on_a_cp1252_windows_console(self) -> None:
        """The documented help command must not require an UTF-8 console."""

        raw_output = io.BytesIO()
        console = io.TextIOWrapper(
            raw_output,
            encoding="cp1252",
            errors="strict",
            newline="",
        )
        encoding_error: UnicodeEncodeError | None = None

        try:
            with (
                patch.object(sys, "argv", ["run.py", "--help"]),
                patch.object(sys, "stdout", console),
            ):
                try:
                    entrypoint.main()
                    console.flush()
                except UnicodeEncodeError as exc:
                    encoding_error = exc
        finally:
            console.detach()

        if encoding_error is not None:
            self.fail(f"--help is not CP1252-safe: {encoding_error}")

        rendered_help = raw_output.getvalue().decode("cp1252")
        self.assertIn("NEURAL FIGHTS", rendered_help)
        self.assertIn("--sim", rendered_help)

    def test_unknown_argument_returns_nonzero(self) -> None:
        """Argumentos invalidos precisam falhar para funcionar em automacao."""

        with (
            patch.object(sys, "argv", ["run.py", "--inexistente"]),
            patch.object(sys, "stdout", io.StringIO()),
            patch.object(sys, "stderr", io.StringIO()),
        ):
            result = entrypoint.main()

        self.assertEqual(result, 2)

    def test_tournament_help_is_cp1252_safe_and_does_not_import_ui(self) -> None:
        """Ajuda do torneio deve funcionar em terminal Windows sem abrir a UI."""

        raw_output = io.BytesIO()
        console = io.TextIOWrapper(
            raw_output,
            encoding="cp1252",
            errors="strict",
            newline="",
        )

        try:
            with (
                patch.object(sys, "stdout", console),
                patch.dict(sys.modules, {"customtkinter": None}),
            ):
                result = tournament_entrypoint.main(["--help"])
                console.flush()
        finally:
            console.detach()

        rendered_help = raw_output.getvalue().decode("cp1252")
        self.assertEqual(result, 0)
        self.assertIn("MODO TORNEIO", rendered_help)
        self.assertIn("--help", rendered_help)


if __name__ == "__main__":
    unittest.main()
