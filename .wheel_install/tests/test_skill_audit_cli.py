"""Testes do contrato de linha de comando da auditoria de skills."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import auditoria_skills


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = PROJECT_ROOT / "tools" / "auditoria_skills.py"


class SkillAuditCLITests(unittest.TestCase):
    @staticmethod
    def _empty_evidence_mapping():
        return {
            field_name: ()
            for field_name in auditoria_skills.RUNTIME_EVIDENCE_FIELDS
        }

    @staticmethod
    def _write_evidence_manifest(path: Path, mapping) -> None:
        path.write_text(
            "SKILL_RUNTIME_EVIDENCE = " + repr(mapping) + "\n",
            encoding="utf-8",
        )

    def _run_cli(self, *arguments: str, cwd: str | None = None, cp1252: bool = False):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONIOENCODING"] = "cp1252" if cp1252 else "utf-8"
        return subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT), *arguments],
            cwd=cwd,
            env=environment,
            capture_output=True,
            check=False,
        )

    def test_import_has_no_output_and_does_not_import_game_runtime(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = str(PROJECT_ROOT)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; import tools.auditoria_skills; "
                    "print('runtime-loaded=' + str('core.entities' in sys.modules))"
                ),
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "runtime-loaded=False\n")
        self.assertEqual(result.stderr, "")

    def test_default_paths_work_outside_project_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = self._run_cli("--json", cwd=temporary_directory)

        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        report = json.loads(result.stdout.decode("ascii"))
        self.assertGreater(report["total"], 1)
        self.assertEqual(report["errors"], 0)
        self.assertIn("structurally_valid", report)
        self.assertEqual(
            set(report["verified_runtime_evidence"]),
            set(auditoria_skills.RUNTIME_EVIDENCE_FIELDS),
        )

        runtime_warning_skills = {
            finding["skill"]
            for finding in report["findings"]
            if finding["code"] == "runtime-evidence-required"
        }
        self.assertNotIn("Cone de Gelo", runtime_warning_skills)
        self.assertNotIn("Corrente em Cadeia", runtime_warning_skills)
        self.assertNotIn("Escudo Arcano", runtime_warning_skills)
        self.assertEqual(runtime_warning_skills, set())

    def test_strict_mode_is_cp1252_safe_and_passes_clean_catalog(self):
        result = self._run_cli("--strict", cp1252=True)

        output = result.stdout.decode("cp1252")
        self.assertEqual(result.returncode, 0, result.stderr.decode("cp1252"))
        self.assertIn("Warnings: 0", output)
        self.assertNotIn("UnicodeEncodeError", result.stderr.decode("cp1252"))

    def test_strict_mode_still_fails_when_runtime_evidence_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "empty_evidence.py"
            self._write_evidence_manifest(
                manifest_path,
                self._empty_evidence_mapping(),
            )
            result = self._run_cli(
                "--strict",
                "--evidence-manifest",
                str(manifest_path),
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn(b"Warnings:", result.stdout)

    def test_structural_errors_always_return_nonzero(self):
        invalid_catalog = '''SKILL_DB = {
    "Nenhuma": {"tipo": "NADA", "custo": 0, "cooldown": 0},
    "Broken": {"tipo": "PROJETIL", "custo": 2, "cooldown": 1},
}
'''
        with tempfile.TemporaryDirectory() as temporary_directory:
            catalog_path = Path(temporary_directory) / "skills.py"
            catalog_path.write_text(invalid_catalog, encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = auditoria_skills.main(
                ["--catalog", str(catalog_path), "--json"],
                stdout=stdout,
                stderr=stderr,
            )

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertGreater(report["errors"], 0)
        self.assertEqual(stderr.getvalue(), "")

    def test_text_report_does_not_claim_runtime_functionality(self):
        result = self._run_cli()

        output = result.stdout.decode("utf-8")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn("structural contracts only", output)
        self.assertNotIn("SKILLS FUNCIONANDO", output)

    def test_missing_evidence_manifest_is_an_input_error_even_in_strict_mode(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing_evidence.py"
            result = self._run_cli(
                "--strict",
                "--evidence-manifest",
                str(missing_path),
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"audit input error", result.stderr)

    def test_evidence_target_requires_existing_module_class_and_method(self):
        valid_module = "tests.test_advanced_skill_regressions"
        valid_class = "AdvancedSkillRegressionTests"
        valid_method = "test_ice_cone_uses_angular_geometry_and_stays_anchored"
        cases = (
            ("tests.module_that_does_not_exist", valid_class, valid_method),
            (valid_module, "ClassThatDoesNotExist", valid_method),
            (valid_module, valid_class, "test_method_that_does_not_exist"),
        )

        for module, class_name, method_name in cases:
            with self.subTest(module=module, class_name=class_name, method_name=method_name):
                mapping = self._empty_evidence_mapping()
                mapping["cone"] = ((module, class_name, method_name),)
                with tempfile.TemporaryDirectory() as temporary_directory:
                    manifest_path = Path(temporary_directory) / "evidence.py"
                    self._write_evidence_manifest(manifest_path, mapping)
                    result = self._run_cli(
                        "--json",
                        "--strict",
                        "--evidence-manifest",
                        str(manifest_path),
                    )

                report = json.loads(result.stdout.decode("ascii"))
                self.assertEqual(result.returncode, 1, result.stderr.decode(errors="replace"))
                self.assertNotIn("cone", report["verified_runtime_evidence"])
                self.assertTrue(
                    any(
                        finding["code"] == "invalid-evidence-target"
                        for finding in report["findings"]
                    )
                )
                self.assertTrue(
                    any(
                        finding["code"] == "runtime-evidence-required"
                        and finding["skill"] == "Cone de Gelo"
                        for finding in report["findings"]
                    )
                )

    def test_manifest_must_explicitly_map_every_advanced_field(self):
        mapping = self._empty_evidence_mapping()
        del mapping["stats_aleatorios"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "incomplete_evidence.py"
            self._write_evidence_manifest(manifest_path, mapping)
            result = self._run_cli(
                "--json",
                "--strict",
                "--evidence-manifest",
                str(manifest_path),
            )

        report = json.loads(result.stdout.decode("ascii"))
        self.assertEqual(result.returncode, 1, result.stderr.decode(errors="replace"))
        self.assertTrue(
            any(
                finding["code"] == "evidence-field-missing"
                and "stats_aleatorios" in finding["message"]
                for finding in report["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
