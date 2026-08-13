"""Regressões para o único caminho de combate visual/headless/torneio."""

from __future__ import annotations

import io
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from neural_fights.cli import headless as headless_cli
from neural_fights.data import database
from neural_fights.simulation.headless import HeadlessMatchResult, HeadlessMatchRunner
from neural_fights.simulation.simulacao import DELETE_MATCH_CONFIG_ENV, Simulador
import neural_fights.tournament.tournament_mode as tournament_module
from neural_fights.tournament.tournament_mode import Tournament, TournamentMatch, TournamentRunner


def _fighter(name: str, hp: float = 100.0, hp_max: float = 100.0):
    return SimpleNamespace(
        dados=SimpleNamespace(nome=name),
        vida=hp,
        vida_max=hp_max,
        morto=hp <= 0.0,
    )


class SimulatorConstructionTests(unittest.TestCase):
    def test_in_memory_config_never_reads_the_global_match_file(self) -> None:
        config = {
            "p1_nome": "A",
            "p2_nome": "B",
            "cenario": "Arena",
            "best_of": 1,
        }
        with (
            patch.object(Simulador, "recarregar_tudo"),
            patch.object(
                database,
                "carregar_match_config",
                side_effect=AssertionError("arquivo global não deveria ser lido"),
            ),
        ):
            simulator = Simulador(match_config=config, headless=True, seed=7)

        try:
            self.assertEqual(simulator.match_config, config)
            self.assertTrue(simulator.headless)
            self.assertIsInstance(simulator.tela, pygame.Surface)
        finally:
            simulator.close()

    def test_initialization_failure_is_propagated_and_not_partially_hidden(self) -> None:
        config = {"p1_nome": "A", "p2_nome": "B", "best_of": 1}
        with patch.object(
            Simulador,
            "carregar_luta_dados",
            side_effect=ValueError("lutador inválido"),
        ):
            with self.assertRaisesRegex(ValueError, "lutador inválido"):
                Simulador(match_config=config, headless=True)

    def test_isolated_file_is_removed_even_when_loading_it_fails(self) -> None:
        descriptor, config_path = tempfile.mkstemp(
            prefix="neural-fights-match-",
            suffix=".json",
        )
        os.close(descriptor)
        try:
            with (
                patch.dict(
                    os.environ,
                    {
                        database.MATCH_CONFIG_ENV: config_path,
                        DELETE_MATCH_CONFIG_ENV: "1",
                    },
                ),
                patch.object(
                    database,
                    "carregar_match_config",
                    side_effect=ValueError("config quebrada"),
                ),
                patch("neural_fights.simulation.simulacao.os.remove") as remove_config,
            ):
                with self.assertRaisesRegex(ValueError, "config quebrada"):
                    Simulador()

            remove_config.assert_called_once_with(config_path)
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

    def test_cleanup_flag_never_deletes_an_arbitrary_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "important.json")
            with (
                patch.dict(
                    os.environ,
                    {
                        database.MATCH_CONFIG_ENV: config_path,
                        DELETE_MATCH_CONFIG_ENV: "1",
                    },
                ),
                patch.object(
                    database,
                    "carregar_match_config",
                    side_effect=ValueError("config quebrada"),
                ),
                patch("neural_fights.simulation.simulacao.os.remove") as remove_config,
                self.assertRaisesRegex(ValueError, "config quebrada"),
            ):
                Simulador()

        remove_config.assert_not_called()

    def test_public_run_releases_resources_and_propagates_loop_errors(self) -> None:
        simulator = object.__new__(Simulador)
        simulator.headless = False
        simulator.rodando = True
        simulator.clock = SimpleNamespace(tick=lambda _fps: 16)
        simulator.slow_mo_timer = 0.0
        simulator.time_scale = 1.0
        simulator.processar_inputs = Mock(side_effect=RuntimeError("frame quebrado"))
        simulator.close = Mock()

        with self.assertRaisesRegex(RuntimeError, "frame quebrado"):
            simulator.run()

        simulator.close.assert_called_once_with()

    def test_public_run_preserves_frame_error_when_close_also_fails(self) -> None:
        simulator = object.__new__(Simulador)
        simulator.headless = False
        simulator.rodando = True
        simulator.clock = SimpleNamespace(tick=lambda _fps: 16)
        simulator.slow_mo_timer = 0.0
        simulator.time_scale = 1.0
        simulator.processar_inputs = Mock(side_effect=RuntimeError("frame quebrado"))
        simulator.close = Mock(side_effect=RuntimeError("cleanup quebrado"))

        with self.assertRaisesRegex(RuntimeError, "frame quebrado") as raised:
            simulator.run()

        notes = getattr(raised.exception, "__notes__", [])
        self.assertTrue(any("cleanup quebrado" in note for note in notes))


class HeadlessRunnerContractTests(unittest.TestCase):
    class FakeSimulator:
        instances = []

        def __init__(self, *, match_config, headless, seed):
            self.match_config = match_config
            self.headless = headless
            self.seed = seed
            self.p1 = _fighter("A")
            self.p2 = _fighter("B")
            self.round_finalizado = False
            self.vencedor_round_side = None
            self.update_calls = []
            self.closed = False
            self.__class__.instances.append(self)

        def update(self, dt):
            self.update_calls.append(dt)
            if len(self.update_calls) == 2:
                self.p2.vida = 0.0
                self.p2.morto = True
                self.round_finalizado = True
                self.vencedor_round_side = "p1"

        def close(self):
            self.closed = True

    def setUp(self) -> None:
        self.FakeSimulator.instances.clear()

    def test_runner_uses_only_simulator_update_with_fixed_dt(self) -> None:
        config = {"p1_nome": "A", "p2_nome": "B"}
        with patch("neural_fights.simulation.headless.Simulador", self.FakeSimulator):
            result = HeadlessMatchRunner(
                config,
                fixed_dt=0.125,
                max_frames=10,
                seed=42,
            ).run()

        simulator = self.FakeSimulator.instances[0]
        self.assertEqual(simulator.update_calls, [0.125, 0.125])
        self.assertTrue(simulator.headless)
        self.assertEqual(simulator.match_config["best_of"], 1)
        self.assertTrue(simulator.closed)
        self.assertTrue(result.success)
        self.assertEqual(result.winner, "A")
        self.assertEqual(result.reason, "knockout")
        self.assertEqual(result.duration, 0.25)

    def test_runner_restores_global_random_state(self) -> None:
        random.seed(9123)
        state_before = random.getstate()
        with patch("neural_fights.simulation.headless.Simulador", self.FakeSimulator):
            HeadlessMatchRunner(
                {"p1_nome": "A", "p2_nome": "B"},
                max_frames=3,
                seed=99,
            ).run()
        self.assertEqual(random.getstate(), state_before)

    def test_same_seed_reproduces_the_same_time_limit_decision(self) -> None:
        class RandomSimulator:
            def __init__(self, **kwargs):
                self.p1 = _fighter("A")
                self.p2 = _fighter("B")
                self.round_finalizado = False
                self.vencedor_round_side = None
                self.rng = random.Random(kwargs["seed"])

            def update(self, _dt):
                self.p1.vida -= self.rng.random()
                self.p2.vida -= self.rng.random()

            def close(self):
                pass

        options = {
            "fixed_dt": 0.1,
            "max_frames": 5,
            "seed": 2026,
        }
        with patch("neural_fights.simulation.headless.Simulador", RandomSimulator):
            first = HeadlessMatchRunner(
                {"p1_nome": "A", "p2_nome": "B"},
                **options,
            ).run()
            second = HeadlessMatchRunner(
                {"p1_nome": "A", "p2_nome": "B"},
                **options,
            ).run()

        self.assertEqual(first, second)
        self.assertEqual(first.reason, "time_limit_decision")

    def test_runner_rejects_nonfinite_or_fractional_timing(self) -> None:
        config = {"p1_nome": "A", "p2_nome": "B"}
        for options in (
            {"fixed_dt": float("nan")},
            {"fixed_dt": float("inf")},
            {"max_duration": float("nan")},
            {"max_frames": float("inf")},
            {"max_frames": 1.5},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                HeadlessMatchRunner(config, **options)

    def test_cleanup_error_becomes_explicit_failed_result(self) -> None:
        class CleanupBrokenSimulator(self.FakeSimulator):
            def close(self):
                raise RuntimeError("cleanup failed")

        with patch("neural_fights.simulation.headless.Simulador", CleanupBrokenSimulator):
            result = HeadlessMatchRunner(
                {"p1_nome": "A", "p2_nome": "B"},
                max_frames=3,
            ).run()

        self.assertFalse(result.success)
        self.assertIn("falha ao liberar simulador", result.error)

    def test_headless_preserves_frame_error_when_cleanup_also_fails(self) -> None:
        class BrokenSimulator(self.FakeSimulator):
            def update(self, _dt):
                raise ValueError("frame original")

            def close(self):
                raise RuntimeError("cleanup secundario")

        with patch(
            "neural_fights.simulation.headless.Simulador",
            BrokenSimulator,
        ):
            result = HeadlessMatchRunner(
                {"p1_nome": "A", "p2_nome": "B"},
                max_frames=1,
            ).run()

        self.assertFalse(result.success)
        self.assertIn("ValueError: frame original", result.error)
        self.assertIn("cleanup secundario", result.error)

    def test_initialization_error_becomes_an_explicit_failed_result(self) -> None:
        class BrokenSimulator:
            def __init__(self, **_kwargs):
                raise RuntimeError("falha de bootstrap")

        with patch("neural_fights.simulation.headless.Simulador", BrokenSimulator):
            result = HeadlessMatchRunner(
                {"p1_nome": "A", "p2_nome": "B"},
                max_frames=1,
            ).run()

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "error")
        self.assertIn("falha de bootstrap", result.error)

    def test_real_engine_can_advance_headlessly_without_match_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_dir = Path(temp_dir) / "database"
            with (
                patch.object(
                    database,
                    "ARQUIVO_ARMAS_RUNTIME",
                    str(runtime_dir / "armas.json"),
                ),
                patch.object(
                    database,
                    "ARQUIVO_CHARS_RUNTIME",
                    str(runtime_dir / "personagens.json"),
                ),
            ):
                roster = database.carregar_personagens()
                self.assertGreaterEqual(len(roster), 2)
                config = {
                    "p1_nome": roster[0].nome,
                    "p2_nome": roster[1].nome,
                    "cenario": "Arena",
                }
                with patch.object(
                    database,
                    "carregar_match_config",
                    side_effect=AssertionError("runner tentou ler match_config"),
                ):
                    result = HeadlessMatchRunner(
                        config,
                        fixed_dt=1.0 / 60.0,
                        max_frames=2,
                        seed=123,
                    ).run()

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.frames, 2)
        self.assertEqual({result.p1_name, result.p2_name}, {roster[0].nome, roster[1].nome})


class TournamentEngineIntegrationTests(unittest.TestCase):
    @staticmethod
    def _engine_result(*, success=True, winner="B", error=None, reason=None, seed=5):
        return HeadlessMatchResult(
            success=success,
            winner=winner if success else None,
            winner_slot="p2" if success and winner is not None else None,
            reason=reason or ("knockout" if success else "error"),
            duration=4.0,
            frames=240,
            seed=seed,
            p1_name="A",
            p2_name="B",
            p1_hp=0.0,
            p2_hp=50.0,
            p1_hp_ratio=0.0,
            p2_hp_ratio=0.5,
            error=error,
        )

    def test_tournament_match_delegates_to_real_headless_runner(self) -> None:
        runner = TournamentRunner(Tournament())
        match = TournamentMatch(5, 1, "A", "B")
        engine_result = self._engine_result()

        with patch(
            "neural_fights.simulation.headless.run_headless_match",
            return_value=engine_result,
        ) as run_engine:
            result = runner.run_single_match(match)

        config = run_engine.call_args.args[0]
        self.assertEqual(config["p1_nome"], "A")
        self.assertEqual(config["p2_nome"], "B")
        self.assertEqual(config["best_of"], 1)
        self.assertTrue(result["success"])
        self.assertEqual(result["winner"], "B")
        self.assertEqual(result["stats"]["frames"], 240)

    def test_tournament_does_not_invent_a_winner_when_engine_fails(self) -> None:
        runner = TournamentRunner(Tournament())
        match = TournamentMatch(1, 1, "A", "B")
        with patch(
            "neural_fights.simulation.headless.run_headless_match",
            return_value=self._engine_result(success=False, error="engine failed"),
        ):
            result = runner.run_single_match(match)

        self.assertFalse(result["success"])
        self.assertNotIn("winner", result)
        self.assertIn("engine failed", result["error"])

    def test_tournament_retries_draw_with_deterministically_derived_seed(self) -> None:
        runner = TournamentRunner(Tournament())
        runner.simulation_config.update({"seed": 100, "draw_retry_limit": 2})
        match = TournamentMatch(7, 1, "A", "B")
        draw = self._engine_result(winner=None, reason="double_ko", seed=107)
        victory = self._engine_result(winner="B", seed=108)

        with patch(
            "neural_fights.simulation.headless.run_headless_match",
            side_effect=[draw, victory],
        ) as run_engine:
            result = runner.run_single_match(match)

        seeds = [call.kwargs["seed"] for call in run_engine.call_args_list]
        self.assertEqual(seeds, [107, 108])
        self.assertTrue(result["success"])
        self.assertEqual(result["winner"], "B")
        self.assertEqual(result["stats"]["attempts"], 2)

    def test_tournament_returns_explicit_failure_after_draw_retry_limit(self) -> None:
        runner = TournamentRunner(Tournament())
        runner.simulation_config.update({"seed": 20, "draw_retry_limit": 2})
        match = TournamentMatch(3, 1, "A", "B")
        draw = self._engine_result(winner=None, reason="double_ko")

        with patch(
            "neural_fights.simulation.headless.run_headless_match",
            return_value=draw,
        ) as run_engine:
            result = runner.run_single_match(match)

        seeds = [call.kwargs["seed"] for call in run_engine.call_args_list]
        self.assertEqual(seeds, [23, 24, 25])
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "draw_retry_exhausted")
        self.assertEqual(result["attempts"], 3)
        self.assertNotIn("winner", result)

    def test_tournament_does_not_retry_headless_engine_error(self) -> None:
        runner = TournamentRunner(Tournament())
        runner.simulation_config["draw_retry_limit"] = 3
        match = TournamentMatch(1, 1, "A", "B")
        failure = self._engine_result(success=False, error="engine failed")

        with patch(
            "neural_fights.simulation.headless.run_headless_match",
            return_value=failure,
        ) as run_engine:
            result = runner.run_single_match(match)

        run_engine.assert_called_once()
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "engine_error")

    def test_visual_setup_removes_partial_isolated_file_when_save_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = TournamentRunner(Tournament())
            with (
                patch.object(
                    tournament_module.tempfile,
                    "gettempdir",
                    return_value=temp_dir,
                ),
                patch.object(
                    database,
                    "salvar_match_config",
                    side_effect=OSError("disco indisponível"),
                ) as save_config,
            ):
                with self.assertRaisesRegex(OSError, "disco indisponível"):
                    runner.setup_match_config("A", "B")
                generated_path = save_config.call_args.kwargs["arquivo"]
                self.assertTrue(
                    tournament_module._is_generated_visual_config(generated_path)
                )

            self.assertFalse(Path(generated_path).exists())
            self.assertEqual(set(), runner._generated_visual_configs)

    def test_visual_launch_uses_module_and_has_child_and_parent_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = TournamentRunner(Tournament())
            with patch.object(
                tournament_module.tempfile,
                "gettempdir",
                return_value=temp_dir,
            ):
                config_path = runner.setup_match_config("A", "B")
                process = Mock()
                process.wait.side_effect = OSError("wait indisponível")

                with (
                    patch("subprocess.Popen", return_value=process) as popen,
                    patch("threading.Thread") as thread,
                ):
                    returned_process = runner.launch_simulation()
                    cleanup_target = thread.call_args.kwargs["target"]
                    self.assertTrue(Path(config_path).exists())
                    cleanup_target()

            self.assertIs(returned_process, process)
            self.assertEqual(
                popen.call_args.args[0],
                [sys.executable, "-m", "neural_fights.simulation.simulacao"],
            )
            child_env = popen.call_args.kwargs["env"]
            self.assertEqual(child_env[database.MATCH_CONFIG_ENV], config_path)
            self.assertEqual(child_env[DELETE_MATCH_CONFIG_ENV], "1")
            thread.assert_called_once_with(target=cleanup_target, daemon=True)
            self.assertFalse(Path(config_path).exists())
            self.assertEqual(set(), runner._generated_visual_configs)

    def test_visual_runner_never_cleans_an_unowned_path_or_exports_delete_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            arbitrary_path = Path(temp_dir) / (
                "neural-fights-match-" + "a" * 32 + ".json"
            )
            arbitrary_path.write_text("important", encoding="utf-8")
            runner = TournamentRunner(Tournament())

            with (
                patch.object(
                    tournament_module.tempfile,
                    "gettempdir",
                    return_value=temp_dir,
                ),
                patch.dict(
                    os.environ,
                    {DELETE_MATCH_CONFIG_ENV: "1"},
                ),
                patch("subprocess.Popen", return_value=Mock()) as popen,
                patch("threading.Thread") as thread,
            ):
                runner.launch_simulation(str(arbitrary_path))

            child_env = popen.call_args.kwargs["env"]
            self.assertEqual(
                child_env[database.MATCH_CONFIG_ENV],
                str(arbitrary_path),
            )
            self.assertNotIn(DELETE_MATCH_CONFIG_ENV, child_env)
            thread.assert_not_called()
            self.assertFalse(runner._remove_visual_config(arbitrary_path))
            self.assertEqual("important", arbitrary_path.read_text(encoding="utf-8"))

    def test_visual_launch_failure_cleans_only_the_owned_reserved_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = TournamentRunner(Tournament())
            with patch.object(
                tournament_module.tempfile,
                "gettempdir",
                return_value=temp_dir,
            ):
                config_path = runner.setup_match_config("A", "B")
                with patch(
                    "subprocess.Popen",
                    side_effect=OSError("processo indisponível"),
                ):
                    with self.assertRaisesRegex(OSError, "processo indisponível"):
                        runner.launch_simulation(config_path)

            self.assertFalse(Path(config_path).exists())
            self.assertEqual(set(), runner._generated_visual_configs)

    def test_visual_setup_rejects_a_different_returned_path_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            arbitrary_path = Path(temp_dir) / "important.json"
            arbitrary_path.write_text("keep", encoding="utf-8")
            runner = TournamentRunner(Tournament())
            with (
                patch.object(
                    tournament_module.tempfile,
                    "gettempdir",
                    return_value=temp_dir,
                ),
                patch.object(
                    database,
                    "salvar_match_config",
                    return_value=str(arbitrary_path),
                ) as save_config,
            ):
                with self.assertRaisesRegex(RuntimeError, "caminho diferente"):
                    runner.setup_match_config("A", "B")

            reserved_path = Path(save_config.call_args.kwargs["arquivo"])
            self.assertFalse(reserved_path.exists())
            self.assertEqual("keep", arbitrary_path.read_text(encoding="utf-8"))
            self.assertEqual(set(), runner._generated_visual_configs)

    def test_consecutive_visual_launches_keep_their_own_config_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = TournamentRunner(Tournament())
            process = Mock()
            process.wait.return_value = 0
            with (
                patch.object(
                    tournament_module.tempfile,
                    "gettempdir",
                    return_value=temp_dir,
                ),
                patch.object(
                    database,
                    "salvar_match_config",
                    side_effect=lambda _config, **kwargs: kwargs["arquivo"],
                ),
                patch("subprocess.Popen", return_value=process) as popen,
                patch("threading.Thread"),
            ):
                first_path = runner.setup_match_config("A", "B")
                second_path = runner.setup_match_config("C", "D")
                runner.launch_simulation(first_path)
                runner.launch_simulation(second_path)

            self.assertNotEqual(first_path, second_path)
            first_env = popen.call_args_list[0].kwargs["env"]
            second_env = popen.call_args_list[1].kwargs["env"]
            self.assertEqual(first_env[database.MATCH_CONFIG_ENV], first_path)
            self.assertEqual(second_env[database.MATCH_CONFIG_ENV], second_path)


class HeadlessCliContractTests(unittest.TestCase):
    def test_cli_returns_nonzero_for_engine_error(self) -> None:
        failure = HeadlessMatchResult(
            success=False,
            winner=None,
            winner_slot=None,
            reason="error",
            duration=0.0,
            frames=0,
            seed=0,
            p1_name="A",
            p2_name="B",
            p1_hp=0.0,
            p2_hp=0.0,
            p1_hp_ratio=0.0,
            p2_hp_ratio=0.0,
            error="boom",
        )
        with (
            patch.object(headless_cli, "executar_teste_rapido", return_value=failure),
            patch.object(headless_cli, "_print_result"),
        ):
            exit_code = headless_cli.main(["--mode", "rapido"])

        self.assertEqual(exit_code, 1)

    def test_result_json_is_rfc_compliant_and_cp1252_safe(self) -> None:
        result = HeadlessMatchResult(
            success=True,
            winner="Fogo🔥",
            winner_slot="p1",
            reason="knockout",
            duration=1.0,
            frames=60,
            seed=1,
            p1_name="Fogo🔥",
            p2_name="B",
            p1_hp=10.0,
            p2_hp=0.0,
            p1_hp_ratio=0.1,
            p2_hp_ratio=0.0,
        )
        raw = io.BytesIO()
        console = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
        try:
            with patch("sys.stdout", console):
                headless_cli._print_result(result)
                console.flush()
        finally:
            console.detach()

        payload = json.loads(raw.getvalue().decode("cp1252"))
        self.assertEqual(payload["winner"], "Fogo🔥")
        self.assertNotIn("NaN", raw.getvalue().decode("cp1252"))

    def test_subprocess_stdout_is_one_rfc_json_document_under_cp1252(self) -> None:
        project_dir = Path(__file__).resolve().parents[1]
        roster = database.carregar_personagens(
            arquivo_armas=database.ARQUIVO_ARMAS,
            arquivo_personagens=database.ARQUIVO_CHARS,
        )
        unicode_names = [fighter.nome for fighter in roster if not fighter.nome.isascii()]
        self.assertGreaterEqual(len(unicode_names), 2)

        with tempfile.TemporaryDirectory() as temp_dir:
            environment = os.environ.copy()
            environment.update(
                {
                    database.RUNTIME_DATA_DIR_ENV: str(Path(temp_dir) / "runtime"),
                    "PYGAME_HIDE_SUPPORT_PROMPT": "1",
                    "PYTHONIOENCODING": "cp1252:strict",
                    "SDL_AUDIODRIVER": "dummy",
                    "SDL_VIDEODRIVER": "dummy",
                }
            )
            environment.pop(database.MATCH_CONFIG_ENV, None)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "neural_fights.cli.headless",
                    "--mode",
                    "rapido",
                    "--p1",
                    unicode_names[0],
                    "--p2",
                    unicode_names[1],
                    "--max-frames",
                    "1",
                ],
                cwd=project_dir,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )

        stderr = completed.stderr.decode("cp1252", errors="replace")
        self.assertEqual(completed.returncode, 0, stderr)
        stdout = completed.stdout.decode("ascii")
        self.assertEqual(len(stdout.splitlines()), 1, stdout)

        def reject_nonfinite(token: str):
            raise ValueError(f"constante JSON nao permitida: {token}")

        payload = json.loads(stdout, parse_constant=reject_nonfinite)
        self.assertEqual(payload["p1_name"], unicode_names[0])
        self.assertEqual(payload["p2_name"], unicode_names[1])
        self.assertTrue(payload["success"], payload.get("error"))


if __name__ == "__main__":
    unittest.main()
