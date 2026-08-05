"""Regression tests for the public command-line entrypoint."""

from __future__ import annotations

import io
import sys
import types
import unittest
from unittest.mock import patch

import run as entrypoint


class EntrypointRegressionTests(unittest.TestCase):
    def test_sim_mode_runs_the_simulator_public_loop(self) -> None:
        """``--sim`` must call the public loop exposed by ``Simulador``."""

        class FakeSimulador:
            instances: list["FakeSimulador"] = []

            def __init__(self) -> None:
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
            entrypoint.main()

        self.assertEqual(len(FakeSimulador.instances), 1)
        self.assertTrue(FakeSimulador.instances[0].run_called)

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


if __name__ == "__main__":
    unittest.main()
