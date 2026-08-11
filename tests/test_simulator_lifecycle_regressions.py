"""Regressões do ownership dos singletons usados pelo Simulador."""

from __future__ import annotations

import random
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

from neural_fights.ai import CombatChoreographer
from neural_fights.core.game_feel import GameFeelManager, HitStopManager
from neural_fights.data import database
from neural_fights.effects import AttackAnimationManager, MagicVFXManager, MovementAnimationManager
from neural_fights.effects.audio import AudioManager
from neural_fights.simulation.simulacao import Simulador, _SilentAudioManager
from neural_fights.simulation.manual import SimuladorManual


MANAGERS = (
    AudioManager,
    MagicVFXManager,
    AttackAnimationManager,
    MovementAnimationManager,
    GameFeelManager,
    HitStopManager,
    CombatChoreographer,
)


class SimulatorLifecycleRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._random_state = random.getstate()
        self._runtime_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._runtime_dir.cleanup)
        runtime_dir = Path(self._runtime_dir.name) / "database"
        self._database_patchers = (
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
        )
        for patcher in self._database_patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        # Isolamento defensivo caso uma asserção interrompa um teste no meio.
        with Simulador._lifecycle_lock:
            Simulador._active_owner_token = None
        for manager in MANAGERS:
            try:
                manager.reset()
            except Exception:
                manager._instance = None
        pygame.quit()
        random.setstate(self._random_state)

    def test_partial_initialization_failure_releases_owner_and_all_managers(self) -> None:
        def fail_after_singletons(simulator, *_args, **_kwargs):
            simulator.choreographer = CombatChoreographer.get_instance()
            simulator.game_feel = GameFeelManager.get_instance()
            simulator.movement_anims = MovementAnimationManager.get_instance()
            simulator.attack_anims = AttackAnimationManager()
            simulator.magic_vfx = MagicVFXManager.get_instance()
            simulator.audio = _SilentAudioManager()
            AudioManager._instance = simulator.audio
            raise ValueError("bootstrap interrompido")

        with patch.object(Simulador, "_inicializar", fail_after_singletons):
            with self.assertRaisesRegex(ValueError, "bootstrap interrompido"):
                Simulador(match_config={})

        self.assertIsNone(Simulador._active_owner_token)
        for manager in MANAGERS:
            self.assertIsNone(manager._instance, manager.__name__)

        # A falha anterior não envenena o processo para a próxima execução.
        with patch.object(Simulador, "_inicializar"):
            subsequent = Simulador(match_config={})
        subsequent.close()

    def test_close_is_idempotent(self) -> None:
        with patch.object(Simulador, "_inicializar"):
            simulator = Simulador(match_config={})

        with patch("neural_fights.simulation.simulacao.pygame.quit") as quit_pygame:
            simulator.close()
            simulator.close()

        quit_pygame.assert_called_once_with()
        self.assertTrue(simulator._closed)
        self.assertIsNone(simulator._lifecycle_token)
        self.assertIsNone(Simulador._active_owner_token)

    def test_manual_post_init_failure_releases_base_ownership(self) -> None:
        with (
            patch.object(Simulador, "_inicializar"),
            patch.object(
                SimuladorManual,
                "_inicializar_modo_manual",
                side_effect=RuntimeError("menu quebrado"),
            ),
            self.assertRaisesRegex(RuntimeError, "menu quebrado"),
        ):
            SimuladorManual(match_config={})

        self.assertIsNone(Simulador._active_owner_token)

    def test_manual_loop_closes_on_return_and_exception(self) -> None:
        for side_effect in (None, RuntimeError("frame manual quebrado")):
            manual = object.__new__(SimuladorManual)
            manual._executar_loop_manual = Mock(side_effect=side_effect)
            manual.close = Mock()

            if side_effect is None:
                manual.executar()
            else:
                with self.assertRaisesRegex(RuntimeError, "frame manual quebrado"):
                    manual.executar()
            manual.close.assert_called_once_with()

    def test_seeded_instance_restores_random_state_on_close_and_init_failure(self) -> None:
        random.seed(918273)
        state_before = random.getstate()

        with patch.object(Simulador, "recarregar_tudo"):
            simulator = Simulador(
                match_config={"p1_nome": "A", "p2_nome": "B", "best_of": 1},
                headless=True,
                seed=77,
            )
        self.assertNotEqual(random.getstate(), state_before)
        simulator.close()
        self.assertEqual(random.getstate(), state_before)

        with patch.object(
            Simulador,
            "recarregar_tudo",
            side_effect=RuntimeError("falha depois do seed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "falha depois do seed"):
                Simulador(
                    match_config={"p1_nome": "A", "p2_nome": "B", "best_of": 1},
                    headless=True,
                    seed=99,
                )

        self.assertEqual(random.getstate(), state_before)
        self.assertIsNone(Simulador._active_owner_token)

    def test_concurrent_constructor_is_rejected_while_first_owns_lifecycle(self) -> None:
        initialization_entered = threading.Event()
        release_initialization = threading.Event()
        created = []
        failures = []

        def slow_initialization(_simulator, *_args, **_kwargs):
            initialization_entered.set()
            if not release_initialization.wait(timeout=2.0):
                raise TimeoutError("teste não liberou inicialização")

        def construct_first():
            try:
                created.append(Simulador(match_config={}))
            except BaseException as exc:
                failures.append(exc)

        with patch.object(Simulador, "_inicializar", slow_initialization):
            thread = threading.Thread(target=construct_first)
            thread.start()
            self.assertTrue(initialization_entered.wait(timeout=2.0))
            try:
                with self.assertRaisesRegex(RuntimeError, "instância ativa"):
                    Simulador(match_config={})
            finally:
                release_initialization.set()
                thread.join(timeout=2.0)

        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(created), 1)
        created[0].close()

    def test_two_sequential_headless_instances_have_isolated_managers(self) -> None:
        roster = database.carregar_personagens()
        self.assertGreaterEqual(len(roster), 2)
        config = {
            "p1_nome": roster[0].nome,
            "p2_nome": roster[1].nome,
            "cenario": "Arena",
            "best_of": 1,
            "portrait_mode": False,
        }

        first = Simulador(match_config=config, headless=True, seed=10)
        first_managers = {
            "audio": first.audio,
            "magic": first.magic_vfx,
            "attack": first.attack_anims,
            "movement": first.movement_anims,
            "game_feel": first.game_feel,
            "choreographer": first.choreographer,
        }
        first.close()

        for manager in MANAGERS:
            self.assertIsNone(manager._instance, manager.__name__)

        second = Simulador(match_config=config, headless=True, seed=11)
        try:
            self.assertIsNot(second.audio, first_managers["audio"])
            self.assertIsNot(second.magic_vfx, first_managers["magic"])
            self.assertIsNot(second.attack_anims, first_managers["attack"])
            self.assertIsNot(second.movement_anims, first_managers["movement"])
            self.assertIsNot(second.game_feel, first_managers["game_feel"])
            self.assertIsNot(second.choreographer, first_managers["choreographer"])

            # Um close atrasado da instância antiga não toca nos novos globais.
            first.close()
            self.assertIs(AudioManager._instance, second.audio)
            self.assertIs(MagicVFXManager._instance, second.magic_vfx)
            self.assertIs(AttackAnimationManager._instance, second.attack_anims)
            self.assertIs(MovementAnimationManager._instance, second.movement_anims)
            self.assertIs(GameFeelManager._instance, second.game_feel)
            self.assertIs(CombatChoreographer._instance, second.choreographer)
        finally:
            second.close()

        for manager in MANAGERS:
            self.assertIsNone(manager._instance, manager.__name__)


if __name__ == "__main__":
    unittest.main()
