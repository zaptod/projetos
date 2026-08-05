import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tournament.tournament_mode import Tournament, TournamentState


class TournamentByeRegressionTests(unittest.TestCase):
    PARTICIPANTS = [f"Lutador {number}" for number in range(1, 8)]

    def _build_tournament(self, *, bye_first=False):
        tournament = Tournament("Torneio de regressao")
        tournament.participants = self.PARTICIPANTS.copy()

        def deterministic_shuffle():
            if bye_first:
                bye_index = next(
                    index
                    for index, name in enumerate(tournament.participants)
                    if name.startswith("BYE")
                )
                tournament.participants.insert(
                    0, tournament.participants.pop(bye_index)
                )

        with patch.object(
            tournament,
            "shuffle_participants",
            side_effect=deterministic_shuffle,
        ):
            with redirect_stdout(io.StringIO()):
                generated = tournament.generate_bracket()

        self.assertTrue(generated)
        self.assertEqual(8, len(tournament.participants))
        self.assertEqual(
            1,
            sum(name.startswith("BYE") for name in tournament.participants),
        )
        return tournament

    def test_current_match_never_points_to_an_already_completed_bye(self):
        tournament = self._build_tournament(bye_first=True)

        self.assertTrue(tournament.start_tournament())

        transitions = 0
        while tournament.state != TournamentState.FINISHED:
            current_match = tournament.get_current_match()
            self.assertIsNotNone(current_match)
            self.assertFalse(
                current_match.completed,
                "current_match apontou para uma luta de BYE ja concluida",
            )

            self.assertTrue(
                tournament.record_match_result(current_match.fighter1_name)
            )
            transitions += 1
            self.assertLess(transitions, 8, "a maquina de estados nao convergiu")

    def test_bye_winner_is_propagated_to_the_next_round(self):
        tournament = self._build_tournament()
        first_round = tournament.bracket[0]
        bye_match_index, bye_match = next(
            (index, match)
            for index, match in enumerate(first_round.matches)
            if match.fighter1_name.startswith("BYE")
            or match.fighter2_name.startswith("BYE")
        )
        expected_winner = (
            bye_match.fighter2_name
            if bye_match.fighter1_name.startswith("BYE")
            else bye_match.fighter1_name
        )

        self.assertTrue(tournament.start_tournament())

        destination = tournament.bracket[1].matches[bye_match_index // 2]
        propagated_name = (
            destination.fighter1_name
            if bye_match_index % 2 == 0
            else destination.fighter2_name
        )
        self.assertTrue(bye_match.completed)
        self.assertEqual(expected_winner, bye_match.winner_name)
        self.assertEqual(
            expected_winner,
            propagated_name,
            "o vencedor automatico do BYE nao chegou a rodada seguinte",
        )

    def test_next_round_has_no_tbd_after_first_round_finishes(self):
        tournament = self._build_tournament()
        self.assertTrue(tournament.start_tournament())

        while tournament.current_round == 0:
            current_match = tournament.get_current_match()
            self.assertIsNotNone(current_match)
            self.assertFalse(current_match.completed)
            self.assertTrue(
                tournament.record_match_result(current_match.fighter1_name)
            )

        self.assertTrue(tournament.bracket[0].completed)
        self.assertEqual(1, tournament.current_round)

        next_round_names = [
            name
            for match in tournament.bracket[1].matches
            for name in (match.fighter1_name, match.fighter2_name)
        ]
        self.assertNotIn(
            "TBD",
            next_round_names,
            "a rodada seguinte ainda tem vaga TBD apos as quartas",
        )


if __name__ == "__main__":
    unittest.main()
