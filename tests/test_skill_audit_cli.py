"""Testes do contrato de linha de comando da auditoria de skills."""

from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from neural_fights.tools import auditoria_skills


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = PROJECT_ROOT / "neural_fights" / "tools" / "auditoria_skills.py"


class SkillAuditCLITests(unittest.TestCase):
    @staticmethod
    def _empty_evidence_mapping():
        return {
            field_name: ()
            for field_name in auditoria_skills.RUNTIME_EVIDENCE_KEYS
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
                    "import sys; import neural_fights.tools.auditoria_skills; "
                    "print('runtime-loaded=' + str('neural_fights.core.entities' in sys.modules))"
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
        self.assertFalse(report["evidence_sources_verified"])
        self.assertEqual(report["verified_runtime_evidence"], {})

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

    def test_unicode_argument_error_is_cp1252_safe(self):
        result = self._run_cli("--opcao-漢字", cp1252=True)

        self.assertEqual(result.returncode, 2)
        output = result.stderr.decode("cp1252")
        self.assertIn("\\u6f22\\u5b57", output)
        self.assertNotIn("UnicodeEncodeError", output)

    def test_checkout_mode_explicitly_verifies_evidence_sources(self):
        result = self._run_cli(
            "--json",
            "--strict",
            "--verify-evidence-sources",
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        report = json.loads(result.stdout.decode("ascii"))
        self.assertTrue(report["evidence_sources_verified"])
        self.assertEqual(
            set(report["verified_runtime_evidence"]),
            set(auditoria_skills.RUNTIME_EVIDENCE_KEYS),
        )

    def test_strict_mode_still_fails_when_runtime_evidence_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "empty_evidence.py"
            self._write_evidence_manifest(
                manifest_path,
                self._empty_evidence_mapping(),
            )
            result = self._run_cli(
                "--strict",
                "--verify-evidence-sources",
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

    def test_duplicate_literal_keys_are_an_input_error_instead_of_last_write_wins(self):
        duplicate_catalog = '''SKILL_DB = {
    "Nenhuma": {"tipo": "NADA", "custo": 0, "cooldown": 0},
    "Duplicada": {
        "tipo": "BUFF", "custo": 1, "cooldown": 1,
        "descricao": "primeira", "descricao": "segunda", "cor": (1, 2, 3),
    },
}
'''
        with tempfile.TemporaryDirectory() as temporary_directory:
            catalog_path = Path(temporary_directory) / "skills.py"
            catalog_path.write_text(duplicate_catalog, encoding="utf-8")
            result = self._run_cli("--catalog", str(catalog_path), "--json")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"chave literal duplicada", result.stderr)

    def test_text_report_does_not_claim_runtime_functionality(self):
        result = self._run_cli()

        output = result.stdout.decode("utf-8")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn("structural contracts only", output)
        self.assertIn("Runtime evidence source verification: not requested", output)
        self.assertNotIn("Verified runtime evidence:", output)
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
                        "--verify-evidence-sources",
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
                "--verify-evidence-sources",
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

    def test_evidence_is_partitioned_when_a_field_has_distinct_runtime_paths(self):
        self.assertNotIn("dano_contato", auditoria_skills.RUNTIME_EVIDENCE_KEYS)
        self.assertLessEqual(
            {
                "dano_contato@BUFF",
                "dano_contato@TRAP",
                "dano_contato@TRANSFORM",
            },
            auditoria_skills.RUNTIME_EVIDENCE_KEYS,
        )

        mapping = self._empty_evidence_mapping()
        mapping["dano_contato"] = ()
        _, findings = auditoria_skills.validate_runtime_evidence(mapping)
        self.assertTrue(
            any(
                finding.code == "unknown-evidence-field"
                and "dano_contato" in finding.message
                for finding in findings
            )
        )

    def test_trap_contact_branch_requires_its_own_runtime_evidence(self):
        catalog, contracts, evidence = auditoria_skills.load_sources(
            auditoria_skills.DEFAULT_CATALOG,
            auditoria_skills.DEFAULT_STATUS_CONTRACT,
            auditoria_skills.DEFAULT_EVIDENCE_MANIFEST,
        )
        evidence = dict(evidence)
        evidence["dano_contato@TRAP"] = ()
        report = auditoria_skills.audit_catalog(
            catalog,
            contracts,
            evidence,
            verify_evidence_sources=True,
        )

        self.assertTrue(
            any(
                finding.code == "runtime-evidence-required"
                and finding.skill == "Muralha de Gelo"
                and "dano_contato@TRAP" in finding.message
                for finding in report.findings
            )
        )

    def test_recent_runtime_contracts_have_explicit_verified_evidence(self):
        expected_references = {
            "afeta_caster": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_time_stop_consumes_duration_and_caster_targeting_contracts",
            "ativa_ao_morrer": "tests.test_death_skill_regressions:DeathSkillRegressionTests.test_last_breath_has_priority_then_resurrection_spends_real_resources",
            "aviso_visual": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_delayed_area_exposes_visual_warning_before_activation",
            "bloqueia_projeteis": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_ice_wall_intercepts_fast_hostile_projectiles_until_destroyed",
            "bonus_area": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_amplification_is_a_cast_snapshot_for_magic_damage_and_area",
            "bonus_dano_magico": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_amplification_is_a_cast_snapshot_for_magic_damage_and_area",
            "bonus_vs_trevas@BEAM": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_holy_bonuses_apply_only_to_explicit_dark_affinity",
            "bonus_vs_trevas@PROJETIL": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_holy_bonuses_apply_only_to_explicit_dark_affinity",
            "chance_stun": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_area_chance_stun_controls_primary_paralysis",
            "cura_percent": "tests.test_death_skill_regressions:DeathSkillRegressionTests.test_last_breath_has_priority_then_resurrection_spends_real_resources",
            "cura_por_morte": "tests.test_death_skill_regressions:DeathSkillRegressionTests.test_harvest_heals_flat_amount_only_after_a_terminal_owned_kill",
            "dano_contato@BUFF": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_ember_shield_retaliates_once_per_accepted_melee_source",
            "dano_meteoro": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_meteor_shower_emits_every_configured_meteor_with_explicit_payload",
            "delay_saida": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_shadow_portal_has_delayed_untargetable_exit_and_cast_parity",
            "duracao_stop": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_time_stop_consumes_duration_and_caster_targeting_contracts",
            "esquiva_garantida": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_prediction_consumes_only_two_accepted_hostile_impacts",
            "forca_empurrao": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_repulsion_consumes_configured_force_without_changing_damage",
            "invisivel_durante": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_shadow_portal_has_delayed_untargetable_exit_and_cast_parity",
            "meteoros_aleatorios": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_meteor_shower_emits_every_configured_meteor_with_explicit_payload",
            "ondas": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_area_waves_emit_every_configured_wave_with_step_independence",
            "pilares": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_celestial_pillars_are_distinct_blows",
            "raio_pilar": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_celestial_warning_shows_the_real_pillar_volumes",
            "raio_meteoro": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_meteor_shower_emits_every_configured_meteor_with_explicit_payload",
            "revive_hp_percent": "tests.test_death_skill_regressions:DeathSkillRegressionTests.test_last_breath_has_priority_then_resurrection_spends_real_resources",
            "stacks_por_segundo": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_area_status_stacks_ignore_only_hit_recovery_with_coarse_steps",
            "ve_ataques": "tests.test_buff_skill_contracts:BuffSkillContractTests.test_prediction_consumes_only_two_accepted_hostile_impacts",
            "vida_estrutura": "tests.test_area_structure_skill_regressions:AreaStructureSkillRegressionTests.test_ice_wall_intercepts_fast_hostile_projectiles_until_destroyed",
        }
        _, _, evidence = auditoria_skills.load_sources(
            auditoria_skills.DEFAULT_CATALOG,
            auditoria_skills.DEFAULT_STATUS_CONTRACT,
            auditoria_skills.DEFAULT_EVIDENCE_MANIFEST,
        )

        verified, findings = auditoria_skills.validate_runtime_evidence(evidence)

        self.assertFalse(
            [finding for finding in findings if finding.level == "error"],
            findings,
        )
        self.assertLessEqual(
            set(expected_references),
            auditoria_skills.RUNTIME_EVIDENCE_KEYS,
        )
        for field_name, reference in expected_references.items():
            with self.subTest(field=field_name):
                self.assertIn(reference, verified[field_name])

    def test_advanced_field_values_and_coherence_are_structurally_validated(self):
        catalog, contracts, evidence = auditoria_skills.load_sources(
            auditoria_skills.DEFAULT_CATALOG,
            auditoria_skills.DEFAULT_STATUS_CONTRACT,
            auditoria_skills.DEFAULT_EVIDENCE_MANIFEST,
        )
        skill_with = {
            field_name: next(
                name for name, record in catalog.items() if field_name in record
            )
            for field_name in (
                "aviso_visual",
                "chance_stun",
                "dano_meteoro",
                "meteoros_aleatorios",
                "ondas",
                "raio_meteoro",
            )
        }
        cases = (
            ("Último Suspiro", "cura_percent", 1.5, "invalid-fraction"),
            (
                "Último Suspiro",
                "ativa_ao_morrer",
                "yes",
                "invalid-boolean",
            ),
            ("Último Suspiro", "cooldown", 0.0, "unsafe-death-trigger-cooldown"),
            ("Ressurreição", "revive_hp_percent", 0.0, "invalid-fraction"),
            ("Colheita de Almas", "cura_por_morte", 0.0, "non-positive-number"),
            ("Amplificar Magia", "bonus_dano_magico", 1.0, "invalid-multiplier"),
            ("Amplificar Magia", "bonus_area", 0.5, "invalid-multiplier"),
            ("Raio Sagrado", "bonus_vs_trevas", 1.0, "invalid-multiplier"),
            ("Escudo de Brasas", "dano_contato", 0.0, "non-positive-number"),
            ("Muralha de Gelo", "bloqueia_projeteis", 1, "invalid-boolean"),
            ("Muralha de Gelo", "vida_estrutura", 0.0, "non-positive-number"),
            ("Parar o Tempo", "afeta_caster", "no", "invalid-boolean"),
            ("Parar o Tempo", "duracao_stop", 0.0, "non-positive-number"),
            ("Julgamento Celestial", "pilares", 0, "invalid-pillar-count"),
            ("Julgamento Celestial", "raio_pilar", 0.0, "invalid-pillar-radius"),
            ("Repulsão", "forca_empurrao", 0.0, "non-positive-number"),
            ("Nuvem Tóxica", "stacks_por_segundo", 0, "invalid-stack-rate"),
            ("Portal Sombrio", "invisivel_durante", "yes", "invalid-boolean"),
            ("Portal Sombrio", "delay_saida", 0.0, "invalid-invisible-exit-delay"),
            ("Previsão", "esquiva_garantida", 0, "invalid-dodge-charges"),
            ("Previsão", "ve_ataques", "yes", "invalid-boolean"),
            (skill_with["aviso_visual"], "aviso_visual", "yes", "invalid-boolean"),
            (skill_with["chance_stun"], "chance_stun", 0.0, "invalid-fraction"),
            (skill_with["chance_stun"], "chance_stun", 1.1, "invalid-fraction"),
            (skill_with["ondas"], "ondas", True, "invalid-wave-count"),
            (
                skill_with["meteoros_aleatorios"],
                "meteoros_aleatorios",
                1.5,
                "invalid-meteor-count",
            ),
            (
                skill_with["dano_meteoro"],
                "dano_meteoro",
                0.0,
                "non-positive-number",
            ),
            (
                skill_with["raio_meteoro"],
                "raio_meteoro",
                False,
                "invalid-number",
            ),
        )

        for skill, field, value, expected_code in cases:
            with self.subTest(skill=skill, field=field):
                invalid_catalog = copy.deepcopy(catalog)
                invalid_catalog[skill][field] = value
                report = auditoria_skills.audit_catalog(
                    invalid_catalog,
                    contracts,
                    evidence,
                )
                self.assertTrue(
                    any(
                        finding.code == expected_code and finding.skill == skill
                        for finding in report.findings
                    )
                )

    def test_area_runtime_fields_reject_non_area_skill_types(self):
        catalog, contracts, evidence = auditoria_skills.load_sources(
            auditoria_skills.DEFAULT_CATALOG,
            auditoria_skills.DEFAULT_STATUS_CONTRACT,
            auditoria_skills.DEFAULT_EVIDENCE_MANIFEST,
        )
        valid_values = {
            "aviso_visual": False,
            "chance_stun": 0.5,
            "dano_meteoro": 1.0,
            "meteoros_aleatorios": 1,
            "ondas": 2,
            "raio_meteoro": 1.0,
        }

        for field_name, value in valid_values.items():
            with self.subTest(field=field_name):
                invalid_catalog = copy.deepcopy(catalog)
                invalid_catalog["Nenhuma"][field_name] = value
                report = auditoria_skills.audit_catalog(
                    invalid_catalog,
                    contracts,
                    evidence,
                )

                self.assertTrue(
                    any(
                        finding.code == "invalid-advanced-field-type"
                        and finding.skill == "Nenhuma"
                        and field_name in finding.message
                        for finding in report.findings
                    )
                )

    def test_closed_inventory_validates_every_catalog_field_and_rejects_typos(self):
        catalog, contracts, evidence = auditoria_skills.load_sources(
            auditoria_skills.DEFAULT_CATALOG,
            auditoria_skills.DEFAULT_STATUS_CONTRACT,
            auditoria_skills.DEFAULT_EVIDENCE_MANIFEST,
        )
        catalog_fields = {
            field_name
            for record in catalog.values()
            for field_name in record
        }

        self.assertEqual(len(auditoria_skills.BASIC_FIELDS), 16)
        self.assertEqual(len(auditoria_skills.MECHANICAL_FIELDS), 121)  # Onda 11B: +forca_puxar, +tick_interval
        self.assertEqual(catalog_fields, auditoria_skills.KNOWN_FIELDS)
        self.assertEqual(
            set().union(*auditoria_skills.TYPE_ALLOWED_FIELDS.values()),
            auditoria_skills.KNOWN_FIELDS,
        )

        typo_catalog = copy.deepcopy(catalog)
        typo_catalog["Bola de Fogo"]["danp"] = 35.0
        report = auditoria_skills.audit_catalog(typo_catalog, contracts, evidence)
        self.assertTrue(
            any(
                finding.code == "unknown-field"
                and finding.skill == "Bola de Fogo"
                for finding in report.findings
            )
        )

    def test_every_mechanical_field_has_type_and_value_validation(self):
        catalog, contracts, evidence = auditoria_skills.load_sources(
            auditoria_skills.DEFAULT_CATALOG,
            auditoria_skills.DEFAULT_STATUS_CONTRACT,
            auditoria_skills.DEFAULT_EVIDENCE_MANIFEST,
        )
        skill_for_field = {
            field_name: next(
                name for name, record in catalog.items() if field_name in record
            )
            for field_name in auditoria_skills.MECHANICAL_FIELDS
        }

        for field_name, skill_name in skill_for_field.items():
            with self.subTest(field=field_name, contract="allowed-type"):
                invalid_catalog = copy.deepcopy(catalog)
                invalid_catalog[skill_name]["tipo"] = "NADA"
                report = auditoria_skills.audit_catalog(
                    invalid_catalog,
                    contracts,
                    evidence,
                )
                self.assertTrue(
                    any(
                        finding.code == "invalid-advanced-field-type"
                        and finding.skill == skill_name
                        and field_name in finding.message
                        for finding in report.findings
                    )
                )

            if field_name in auditoria_skills.NUMERIC_FIELDS:
                invalid_value = float("nan")
                expected_code = "invalid-number"
            elif field_name in auditoria_skills.BOOLEAN_CONTRACT_FIELDS:
                invalid_value = 1
                expected_code = "invalid-boolean"
            elif field_name in auditoria_skills.NON_EMPTY_TEXT_FIELDS:
                invalid_value = ""
                expected_code = "invalid-text"
            elif field_name == "dano_variavel":
                invalid_value = (2.0, 1.0)
                expected_code = "invalid-damage-range"
            elif field_name == "efeitos_possiveis":
                invalid_value = []
                expected_code = "invalid-effect-list"
            elif field_name == "combo_apos":
                invalid_value = []
                expected_code = "invalid-combo-reference"
            else:
                self.fail(f"campo mecanico sem validador de valor: {field_name}")

            with self.subTest(field=field_name, contract="value"):
                invalid_catalog = copy.deepcopy(catalog)
                invalid_catalog[skill_name][field_name] = invalid_value
                report = auditoria_skills.audit_catalog(
                    invalid_catalog,
                    contracts,
                    evidence,
                )
                self.assertTrue(
                    any(
                        finding.code == expected_code
                        and finding.skill == skill_name
                        for finding in report.findings
                    ),
                    report.findings,
                )

    def test_advanced_cross_field_coherence_is_structurally_validated(self):
        catalog, contracts, evidence = auditoria_skills.load_sources(
            auditoria_skills.DEFAULT_CATALOG,
            auditoria_skills.DEFAULT_STATUS_CONTRACT,
            auditoria_skills.DEFAULT_EVIDENCE_MANIFEST,
        )
        skill_with = {
            field_name: next(
                name for name, record in catalog.items() if field_name in record
            )
            for field_name in (
                "aviso_visual",
                "chance_stun",
                "meteoros_aleatorios",
                "ondas",
            )
        }
        cases = (
            (
                "Último Suspiro",
                lambda record: record.pop("cura_percent"),
                "incomplete-death-trigger",
            ),
            (
                "Ressurreição",
                lambda record: record.update(cooldown=0.0),
                "unsafe-revive-cooldown",
            ),
            (
                "Colheita de Almas",
                lambda record: record.update(dano=0.0),
                "kill-heal-without-damage",
            ),
            (
                "Amplificar Magia",
                lambda record: record.pop("duracao"),
                "missing-persistent-buff-duration",
            ),
            (
                "Raio Sagrado",
                lambda record: record.update(dano=0.0),
                "dark-bonus-without-damage",
            ),
            (
                "Julgamento Celestial",
                lambda record: record.pop("pilares"),
                "orphan-pillar-radius",
            ),
            (
                "Portal Sombrio",
                lambda record: record.update(invisivel_durante=False),
                "orphan-invisible-exit-delay",
            ),
            (
                "Nuvem Tóxica",
                lambda record: record.pop("duracao"),
                "missing-stacking-area-duration",
            ),
            (
                skill_with["ondas"],
                lambda record: record.update(duracao=0.0),
                "invalid-wave-duration",
            ),
            (
                skill_with["meteoros_aleatorios"],
                lambda record: record.update(duracao=0.0),
                "invalid-meteor-duration",
            ),
            (
                skill_with["meteoros_aleatorios"],
                lambda record: record.pop("dano_meteoro"),
                "incomplete-meteor-contract",
            ),
            (
                skill_with["meteoros_aleatorios"],
                lambda record: record.pop("meteoros_aleatorios"),
                "orphan-meteor-payload",
            ),
            (
                skill_with["aviso_visual"],
                lambda record: record.update(delay=0.0),
                "invalid-area-warning-delay",
            ),
            (
                skill_with["chance_stun"],
                lambda record: record.update(efeito="NORMAL"),
                "invalid-stun-chance-effect",
            ),
            (
                "Nenhuma",
                lambda record: record.update(bonus_area=1.5),
                "invalid-advanced-field-type",
            ),
        )

        for skill, mutate, expected_code in cases:
            with self.subTest(skill=skill, code=expected_code):
                invalid_catalog = copy.deepcopy(catalog)
                mutate(invalid_catalog[skill])
                report = auditoria_skills.audit_catalog(
                    invalid_catalog,
                    contracts,
                    evidence,
                )
                self.assertTrue(
                    any(
                        finding.code == expected_code and finding.skill == skill
                        for finding in report.findings
                    )
                )


if __name__ == "__main__":
    unittest.main()
