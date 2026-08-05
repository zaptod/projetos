import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pygame

from core.match_series import BestOfSeries
from simulation.simulacao import Simulador
from tournament.tournament_mode import Tournament, TournamentRunner


class BestOfSeriesTests(unittest.TestCase):
    def test_accepts_only_positive_odd_integers(self):
        for valid in (1, 3, 5, 7):
            with self.subTest(valid=valid):
                self.assertEqual(valid, BestOfSeries(valid).best_of)

        for invalid in (True, False, "3", 3.0, 0, -1, 2, 4):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    BestOfSeries(invalid)

    def test_required_wins_and_latch_are_deterministic(self):
        series = BestOfSeries(3)

        self.assertEqual(2, series.required_wins)
        self.assertTrue(series.record_win("p1"))
        self.assertFalse(series.record_win("p1"))
        self.assertFalse(series.record_win("p2"))
        self.assertEqual({"p1": 1, "p2": 0}, series.wins)

        self.assertTrue(series.reset_round())
        self.assertEqual(2, series.round_number)
        self.assertTrue(series.record_win("p2"))
        self.assertTrue(series.reset_round())
        self.assertEqual(3, series.round_number)
        self.assertTrue(series.record_win("p1"))

        self.assertEqual("p1", series.winner)
        self.assertTrue(series.finished)
        self.assertEqual({"p1": 2, "p2": 1}, series.wins)
        self.assertFalse(series.reset_round())

    def test_draw_closes_round_without_score_and_repeats_number(self):
        series = BestOfSeries(5)

        self.assertTrue(series.record_draw())
        self.assertTrue(series.round_closed)
        self.assertTrue(series.round_draw)
        self.assertFalse(series.record_draw())
        self.assertFalse(series.record_win("p1"))
        self.assertEqual({"p1": 0, "p2": 0}, series.wins)

        self.assertTrue(series.reset_round())
        self.assertEqual(1, series.round_number)
        self.assertFalse(series.round_closed)

    def test_reset_series_clears_champion_score_and_round(self):
        series = BestOfSeries(1)
        series.record_win("p2")

        series.reset_series()

        self.assertEqual({"p1": 0, "p2": 0}, series.wins)
        self.assertEqual(1, series.round_number)
        self.assertIsNone(series.winner)
        self.assertFalse(series.round_closed)


class SimulatorBestOfIntegrationTests(unittest.TestCase):
    def _simulator(self, best_of=3, p1_dead=False, p2_dead=False, same_name=False):
        simulator = Simulador.__new__(Simulador)
        p1_name = "Mesmo" if same_name else "P1"
        p2_name = "Mesmo" if same_name else "P2"
        simulator.p1 = SimpleNamespace(
            morto=p1_dead,
            dados=SimpleNamespace(nome=p1_name, arma_obj=None),
        )
        simulator.p2 = SimpleNamespace(
            morto=p2_dead,
            dados=SimpleNamespace(nome=p2_name, arma_obj=None),
        )
        simulator.best_of_series = BestOfSeries(best_of)
        simulator.round_finalizado = False
        simulator.vencedor = None
        simulator.vencedor_round_side = None
        simulator.vencedor_serie_side = None
        simulator.empate_round = False
        simulator.audio = None
        simulator.time_scale = 1.0
        simulator.slow_mo_timer = 0.0
        return simulator

    def test_detects_winner_by_slot_and_counts_only_once(self):
        simulator = self._simulator(p2_dead=True, same_name=True)

        self.assertTrue(simulator._detectar_resultado_round())
        self.assertEqual("p1", simulator.vencedor_round_side)
        self.assertEqual("Mesmo", simulator.vencedor)
        self.assertEqual({"p1": 1, "p2": 0}, simulator.best_of_series.wins)

        self.assertFalse(simulator._detectar_resultado_round())
        self.assertEqual({"p1": 1, "p2": 0}, simulator.best_of_series.wins)

    def test_double_ko_is_draw_and_round_reset_preserves_number(self):
        simulator = self._simulator(p1_dead=True, p2_dead=True)

        self.assertTrue(simulator._detectar_resultado_round())
        self.assertTrue(simulator.empate_round)
        self.assertEqual("EMPATE", simulator.vencedor)
        self.assertEqual({"p1": 0, "p2": 0}, simulator.best_of_series.wins)

        simulator.recarregar_tudo = Mock()
        simulator._reiniciar_round_ou_serie()

        self.assertEqual(1, simulator.best_of_series.round_number)
        simulator.recarregar_tudo.assert_called_once_with()

    def test_simultaneous_lethal_dots_update_both_slots_before_deciding(self):
        simulator = self._simulator()
        simulator.p1.update = Mock(
            side_effect=lambda _dt, _enemy: setattr(simulator.p1, "morto", True)
        )
        simulator.p2.update = Mock(
            side_effect=lambda _dt, _enemy: setattr(simulator.p2, "morto", True)
        )

        simulator._atualizar_lutadores(0.5)
        self.assertTrue(simulator._detectar_resultado_round())

        simulator.p1.update.assert_called_once_with(0.5, simulator.p2)
        simulator.p2.update.assert_called_once_with(0.5, simulator.p1)
        self.assertTrue(simulator.empate_round)
        self.assertEqual({"p1": 0, "p2": 0}, simulator.best_of_series.wins)

    def test_simultaneous_melee_hits_are_both_resolved_before_deciding(self):
        simulator = self._simulator()

        def lethal_hit(_attacker, defender):
            defender.morto = True
            return True

        simulator.checar_ataque = Mock(side_effect=lethal_hit)
        simulator.checar_clash_geral = Mock(return_value=False)

        simulator.verificar_colisoes_combate()
        self.assertTrue(simulator._detectar_resultado_round())

        self.assertEqual(2, simulator.checar_ataque.call_count)
        self.assertTrue(simulator.empate_round)
        self.assertEqual({"p1": 0, "p2": 0}, simulator.best_of_series.wins)

    def test_finished_round_keeps_visual_effects_alive_without_gameplay(self):
        simulator = self._simulator()
        simulator.round_finalizado = True
        simulator.cam = Mock()
        simulator.paused = False
        visual = SimpleNamespace(vida=1.0, update=Mock())
        simulator.textos = [visual]
        simulator.shockwaves = []
        simulator.particulas = []
        simulator.decals = []

        simulator.update(0.1)

        simulator.cam.atualizar.assert_called_once_with(0.1, simulator.p1, simulator.p2)
        visual.update.assert_called_once_with(0.1)

    def test_portrait_score_is_below_bars_and_fits_the_screen(self):
        pygame.font.init()
        simulator = self._simulator(best_of=5)
        simulator.screen_width = 540
        simulator.portrait_mode = True
        simulator.tela = Mock()

        simulator.desenhar_placar_serie()

        surface, position = simulator.tela.blit.call_args.args
        self.assertLessEqual(surface.get_width(), 500)
        self.assertEqual(70, position[1])

    def test_r_advances_round_then_resets_series_after_champion(self):
        simulator = self._simulator(best_of=3, p2_dead=True)
        simulator._detectar_resultado_round()
        simulator.recarregar_tudo = Mock()

        simulator._reiniciar_round_ou_serie()

        self.assertEqual(2, simulator.best_of_series.round_number)
        self.assertEqual({"p1": 1, "p2": 0}, simulator.best_of_series.wins)

        simulator.p2.morto = True
        simulator.round_finalizado = False
        simulator._detectar_resultado_round()
        self.assertEqual("p1", simulator.best_of_series.winner)

        simulator._reiniciar_round_ou_serie()

        self.assertEqual(1, simulator.best_of_series.round_number)
        self.assertEqual({"p1": 0, "p2": 0}, simulator.best_of_series.wins)
        self.assertIsNone(simulator.best_of_series.winner)

    def test_tournament_visual_match_forces_single_round(self):
        runner = TournamentRunner(Tournament())

        with patch(
            "tournament.tournament_mode.database.salvar_match_config"
        ) as save_config:
            runner.setup_match_config("A", "B")

        config = save_config.call_args.args[0]
        self.assertEqual(1, config["best_of"])


if __name__ == "__main__":
    unittest.main()
