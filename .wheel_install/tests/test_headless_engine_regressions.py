"""Regressões para o único caminho de combate visual/headless/torneio."""

from __future__ import annotations

import os
import random
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pygame

import test_headless_battle as headless_cli
from data import database
from simulation.headless import HeadlessMatchResult, HeadlessMatchRunner
from simulation.simulacao import DELETE_MATCH_CONFIG_ENV, Simulador
from tournament.tournament_mode import Tournament, TournamentMatch, TournamentRunner


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
        config_path = os.path.abspath("isolated-broken-match.json")
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
            patch("simulation.simulacao.os.remove") as remove_config,
        ):
            with self.assertRaisesRegex(ValueError, "config quebrada"):
                Simulador()

        remove_config.assert_called_once_with(config_path)

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
        with patch("simulation.headless.Simulador", self.FakeSimulator):
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
        with patch("simulation.headless.Simulador", self.FakeSimulator):
            HeadlessMatchRunner(
                {"p1_nome": "A", "p2_nome": "B"},
                max_frames=3,
                seed=99,
            ).run()
        self.assertEqual(random.getstate(), state_before)

    def test_same_seed_reproduces_the_same_time_limit_decision(self) -> None:
        class RandomSimulator:
            def __init__(self, **_kwargs):
                self.p1 = _fighter("A")
                self.p2 = _fighter("B")
                self.round_finalizado = False
                self.vencedor_round_side = None

            def update(self, _dt):
                self.p1.vida -= random.random()
                self.p2.vida -= random.random()

            def close(self):
                pass

        options = {
            "fixed_dt": 0.1,
            "max_frames": 5,
            "seed": 2026,
        }
        with patch("simulation.headless.Simulador", RandomSimulator):
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

    def test_initialization_error_becomes_an_explicit_failed_result(self) -> None:
        class BrokenSimulator:
            def __init__(self, **_kwargs):
                raise RuntimeError("falha de bootstrap")

        with patch("simulation.headless.Simulador", BrokenSimulator):
            result = HeadlessMatchRunner(
                {"p1_nome": "A", "p2_nome": "B"},
                max_frames=1,
            ).run()

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "error")
        self.assertIn("falha de bootstrap", result.error)

    def test_real_engine_can_advance_headlessly_without_match_file(self) -> None:
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
            "simulation.headless.run_headless_match",
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
            "simulation.headless.run_headless_match",
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
            "simulation.headless.run_headless_match",
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
            "simulation.headless.run_headless_match",
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
            "simulation.headless.run_headless_match",
            return_value=failure,
        ) as run_engine:
            result = runner.run_single_match(match)

        run_engine.assert_called_once()
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "engine_error")

    def test_visual_setup_removes_partial_isolated_file_when_save_fails(self) -> None:
        runner = TournamentRunner(Tournament())
        with (
            patch.object(
                database,
                "salvar_match_config",
                side_effect=OSError("disco indisponível"),
            ) as save_config,
            patch.object(runner, "_remove_visual_config") as remove_config,
        ):
            with self.assertRaisesRegex(OSError, "disco indisponível"):
                runner.setup_match_config("A", "B")

        generated_path = save_config.call_args.kwargs["arquivo"]
        self.assertIn("neural-fights-match-", generated_path)
        remove_config.assert_called_once_with(generated_path)

    def test_visual_launch_uses_module_and_has_child_and_parent_cleanup(self) -> None:
        runner = TournamentRunner(Tournament())
        runner.match_config_path = os.path.abspath("isolated-visual-match.json")
        process = Mock()
        process.wait.side_effect = OSError("wait indisponível")

        with (
            patch("subprocess.Popen", return_value=process) as popen,
            patch("threading.Thread") as thread,
            patch.object(runner, "_remove_visual_config") as remove_config,
        ):
            returned_process = runner.launch_simulation()
            cleanup_target = thread.call_args.kwargs["target"]
            cleanup_target()

        self.assertIs(returned_process, process)
        self.assertEqual(
            popen.call_args.args[0],
            [sys.executable, "-m", "simulation.simulacao"],
        )
        child_env = popen.call_args.kwargs["env"]
        self.assertEqual(
            child_env[database.MATCH_CONFIG_ENV],
            runner.match_config_path,
        )
        self.assertEqual(child_env[DELETE_MATCH_CONFIG_ENV], "1")
        thread.assert_called_once_with(target=cleanup_target, daemon=True)
        remove_config.assert_called_once_with(runner.match_config_path)


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


if __name__ == "__main__":
    unittest.main()
