"""Regressoes dos gates de armas, geometria e roteamento de hitboxes."""

from __future__ import annotations

import copy
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.hitbox import SistemaHitbox
from data import database
from models import Arma, TIPOS_ARMA
from tools import analise_armas, diagnostico_hitbox, gerador_database
from ui.view_armas import GEOMETRY_EDITOR_CONFIG, preencher_geometria_padrao


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WeaponGeometryContractTests(unittest.TestCase):
    def test_canonical_database_has_positive_type_geometry_and_atomic_round_trip(self):
        armas, personagens = database.carregar_database()

        arremessos = [arma for arma in armas if arma["tipo"] == "Arremesso"]
        transformaveis = [arma for arma in armas if arma["tipo"] == "Transformável"]
        self.assertEqual(9, len(arremessos))
        self.assertEqual(9, len(transformaveis))
        self.assertTrue(
            all(arma["largura"] == arma["tamanho_projetil"] for arma in arremessos)
        )
        self.assertTrue(all(arma["largura"] == 5.0 for arma in transformaveis))

        for arma in armas:
            for campo in TIPOS_ARMA[arma["tipo"]]["geometria"]:
                self.assertIsInstance(arma[campo], (int, float))
                self.assertFalse(isinstance(arma[campo], bool))
                self.assertTrue(math.isfinite(float(arma[campo])))
                self.assertGreater(arma[campo], 0)

        with tempfile.TemporaryDirectory() as temporary_directory:
            weapons_path = Path(temporary_directory) / "armas.json"
            characters_path = Path(temporary_directory) / "personagens.json"
            database.salvar_database(
                armas,
                personagens,
                arquivo_armas=str(weapons_path),
                arquivo_personagens=str(characters_path),
            )
            reloaded_weapons, reloaded_characters = database.carregar_database(
                arquivo_armas=str(weapons_path),
                arquivo_personagens=str(characters_path),
            )

        self.assertEqual(armas, reloaded_weapons)
        self.assertEqual(personagens, reloaded_characters)

    def test_database_rejects_zero_or_missing_required_geometry(self):
        armas, _personagens = database.carregar_database()
        cases = (
            next(arma for arma in armas if arma["tipo"] == "Arremesso"),
            next(arma for arma in armas if arma["tipo"] == "Transformável"),
        )

        for original in cases:
            with self.subTest(tipo=original["tipo"]):
                invalid = copy.deepcopy(original)
                invalid["largura"] = 0
                with self.assertRaises(database.DataValidationError) as raised:
                    database.validar_armas([invalid])
                self.assertIn("largura deve ser maior que zero", str(raised.exception))

    def test_generator_and_editor_always_supply_required_geometry(self):
        thrown = gerador_database.gerar_arma("Arremesso", "Comum", variante_idx=0)
        transformed = gerador_database.gerar_arma(
            "Transformável", "Comum", variante_idx=0
        )

        self.assertEqual(thrown["tamanho_projetil"], thrown["largura"])
        self.assertEqual(5.0, transformed["largura"])

        for weapon_type, config in GEOMETRY_EDITOR_CONFIG.items():
            configured_fields = {field for field, _label, _minimum, _maximum in config}
            self.assertEqual(
                set(TIPOS_ARMA[weapon_type]["geometria"]),
                configured_fields,
            )
            geometry = preencher_geometria_padrao(weapon_type, {})
            self.assertTrue(all(value > 0 for value in geometry.values()))

    def test_magic_weapon_reaches_area_branch_and_uses_its_profile(self):
        weapon = Arma(
            nome="Foco de teste",
            tipo="Mágica",
            dano=10,
            peso=1,
            quantidade=3,
            tamanho=12,
            distancia_max=40,
        )
        fighter = SimpleNamespace(
            dados=SimpleNamespace(arma_obj=weapon, tamanho=2.0, nome="Mago"),
            pos=[2.0, 3.0],
            fator_escala=1.0,
            angulo_arma_visual=15.0,
            angulo_olhar=15.0,
            atacando=False,
        )

        hitbox = SistemaHitbox().calcular_hitbox_arma(fighter)

        self.assertIsNotNone(hitbox)
        self.assertEqual("aura", hitbox.forma)
        self.assertEqual("area", hitbox.profile["shape"])
        self.assertTrue(hitbox.ativo)
        self.assertGreater(hitbox.alcance, 0)

    def test_ast_gate_rejects_overlapping_type_routes(self):
        source = diagnostico_hitbox.DEFAULT_HITBOX_SOURCE.read_text(encoding="utf-8")
        ambiguous = source.replace(
            '["Arremesso", "Arco"]',
            '["Arremesso", "Arco", "Mágica"]',
            1,
        )
        self.assertNotEqual(source, ambiguous)

        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "hitbox.py"
            source_path.write_text(ambiguous, encoding="utf-8")
            findings = diagnostico_hitbox.diagnosticar_implementacao_hitbox(source_path)

        self.assertTrue(
            any(
                finding.codigo == "ambiguous-hitbox-routing"
                and finding.tipo == "Mágica"
                for finding in findings
            )
        )


class WeaponGateCLITests(unittest.TestCase):
    @staticmethod
    def _run_module(module: str, *arguments: str, cp1252: bool = False):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        environment["PYTHONIOENCODING"] = "cp1252" if cp1252 else "utf-8"
        return subprocess.run(
            [sys.executable, "-m", module, *arguments],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            check=False,
        )

    def test_default_gates_are_strict_clean_and_json_is_machine_readable(self):
        for module in ("tools.analise_armas", "tools.diagnostico_hitbox"):
            with self.subTest(module=module):
                result = self._run_module(module, "--strict", "--json")
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                report = json.loads(result.stdout.decode("ascii"))
                self.assertEqual(0, report["errors"])
                self.assertEqual(0, report["warnings"])
                self.assertEqual(9, report["accepted_infos"])

    def test_default_paths_do_not_depend_on_current_working_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            try:
                os.chdir(temporary_directory)
                for entrypoint in (analise_armas.main, diagnostico_hitbox.main):
                    with self.subTest(entrypoint=entrypoint.__module__):
                        stdout = io.StringIO()
                        stderr = io.StringIO()
                        exit_code = entrypoint(
                            ["--strict", "--json"],
                            stdout=stdout,
                            stderr=stderr,
                        )
                        self.assertEqual(exit_code, 0, stderr.getvalue())
                        self.assertEqual(78, json.loads(stdout.getvalue())["total"])
            finally:
                os.chdir(previous)

    def test_cp1252_output_is_safe(self):
        for module in ("tools.analise_armas", "tools.diagnostico_hitbox"):
            with self.subTest(module=module):
                result = self._run_module(module, "--strict", cp1252=True)
                output = result.stdout.decode("cp1252")
                self.assertEqual(result.returncode, 0, result.stderr.decode("cp1252"))
                self.assertIn("Result: PASSED", output)
                self.assertNotIn("UnicodeEncodeError", result.stderr.decode("cp1252"))

    def test_strict_mode_rejects_operational_warning_but_normal_mode_accepts_it(self):
        armas, _personagens = database.carregar_database()
        outlier = copy.deepcopy(next(arma for arma in armas if arma["tipo"] == "Reta"))
        outlier["comp_lamina"] = 1_001.0

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "armas.json"
            path.write_text(json.dumps([outlier], ensure_ascii=False), encoding="utf-8")
            for module in ("tools.analise_armas", "tools.diagnostico_hitbox"):
                with self.subTest(module=module):
                    normal = self._run_module(module, "--arquivo", str(path))
                    strict = self._run_module(
                        module,
                        "--arquivo",
                        str(path),
                        "--strict",
                    )
                    self.assertEqual(
                        normal.returncode,
                        0,
                        normal.stderr.decode(errors="replace"),
                    )
                    self.assertEqual(
                        strict.returncode,
                        2,
                        strict.stderr.decode(errors="replace"),
                    )
                    self.assertIn(b"geometry-operational-outlier", strict.stdout)

    def test_structural_geometry_error_fails_both_gates(self):
        armas, _personagens = database.carregar_database()
        invalid = copy.deepcopy(
            next(arma for arma in armas if arma["tipo"] == "Transformável")
        )
        invalid["largura"] = 0

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "invalid_armas.json"
            path.write_text(json.dumps([invalid], ensure_ascii=False), encoding="utf-8")
            for module in ("tools.analise_armas", "tools.diagnostico_hitbox"):
                with self.subTest(module=module):
                    result = self._run_module(
                        module,
                        "--arquivo",
                        str(path),
                        "--strict",
                        "--json",
                    )
                    report = json.loads(result.stdout.decode("ascii"))
                    self.assertEqual(
                        result.returncode,
                        1,
                        result.stderr.decode(errors="replace"),
                    )
                    self.assertGreater(report["errors"], 0)
                    self.assertTrue(
                        any(
                            item["codigo"] == "database-contract"
                            and "largura" in item["problema"]
                            for item in report["diagnosticos"]
                        )
                    )


if __name__ == "__main__":
    unittest.main()
