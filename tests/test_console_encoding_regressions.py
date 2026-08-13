"""Contratos de saida para consoles Windows com encoding legado."""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from neural_fights.cli import headless, roster
from neural_fights.simulation import manual
from neural_fights.tools import analise_armas, diagnostico_hitbox, migrar_database
from neural_fights.utils.console import safe_print


def _cp1252_stream():
    raw = io.BytesIO()
    text = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    return raw, text


class ConsoleEncodingRegressionTests(unittest.TestCase):
    def test_safe_print_escapes_unrepresentable_user_text(self):
        raw, output = _cp1252_stream()
        safe_print("Lutador \U0001f525", file=output)
        output.flush()

        self.assertEqual(
            raw.getvalue().decode("cp1252").splitlines(),
            ["Lutador \\U0001f525"],
        )

    def test_database_migrator_reports_unicode_errors_without_crashing(self):
        raw, output = _cp1252_stream()
        with (
            patch.object(migrar_database.database, "carregar_database") as load,
            patch("sys.stdout", output),
        ):
            load.side_effect = migrar_database.database.DataValidationError(
                "personagem \U0001f525 invalido"
            )
            code = migrar_database.main([])
        output.flush()

        self.assertEqual(code, 1)
        self.assertIn("\\U0001f525", raw.getvalue().decode("cp1252"))

    def test_manual_entrypoint_reports_unicode_runtime_error_safely(self):
        raw, error = _cp1252_stream()
        with (
            patch.object(manual, "SimuladorManual", side_effect=ValueError("\U0001f525")),
            patch("sys.stderr", error),
            patch("sys.stdout", io.StringIO()),
        ):
            code = manual.main()
        error.flush()

        self.assertEqual(code, 1)
        self.assertIn("\\U0001f525", raw.getvalue().decode("cp1252"))

    def test_argparse_entrypoints_escape_unknown_unicode_arguments(self):
        entrypoints = (
            headless.main,
            roster.main,
            migrar_database.main,
            analise_armas.main,
            diagnostico_hitbox.main,
        )
        for entrypoint in entrypoints:
            with self.subTest(entrypoint=entrypoint.__module__):
                raw, error = _cp1252_stream()
                with (
                    patch("sys.stderr", error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    entrypoint(["--\U0001f525"])
                error.flush()

                self.assertEqual(raised.exception.code, 2)
                self.assertIn(
                    "\\U0001f525",
                    raw.getvalue().decode("cp1252"),
                )


if __name__ == "__main__":
    unittest.main()
