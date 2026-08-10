import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tournament.tournament_mode import (
    Tournament,
    TournamentMatch,
    TournamentRound,
    TournamentState,
)


class TournamentPersistenceRegressionTests(unittest.TestCase):
    def _save_to_dict(self, tournament):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            with redirect_stdout(io.StringIO()):
                tournament.save_state(str(path))
            return json.loads(path.read_text(encoding="utf-8"))

    def _load_from_dict(self, state):
        tournament = Tournament()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text(json.dumps(state), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                loaded = tournament.load_state(str(path))

        self.assertTrue(loaded)
        return tournament

    def test_round_trip_restores_history_and_fight_logs(self):
        completed_match = TournamentMatch(
            match_id=0,
            round_num=0,
            fighter1_name="Ada",
            fighter2_name="Grace",
            winner_name="Ada",
            loser_name="Grace",
            duration=42.5,
            ko_type="KO Técnico",
            fight_log=["Ada atacou", "Grace caiu"],
            completed=True,
        )
        tournament = Tournament("Persistência")
        tournament.participants = ["Ada", "Grace"]
        tournament.bracket = [
            TournamentRound(
                round_num=0,
                name="Final",
                matches=[completed_match],
                completed=True,
            )
        ]
        tournament.fight_history = [completed_match]
        tournament.state = TournamentState.FINISHED
        tournament.champion = "Ada"
        tournament.current_round = 1
        tournament.stats["total_fights"] = 1

        saved_state = self._save_to_dict(tournament)
        restored = self._load_from_dict(saved_state)

        restored_match = restored.bracket[0].matches[0]
        self.assertEqual(["Ada atacou", "Grace caiu"], restored_match.fight_log)
        self.assertEqual(1, len(restored.fight_history))
        self.assertIs(restored_match, restored.fight_history[0])
        self.assertEqual(42.5, restored.fight_history[0].duration)
        self.assertEqual("Ada", restored.champion)
        self.assertEqual(TournamentState.FINISHED, restored.state)

    def test_legacy_save_without_history_or_logs_still_loads(self):
        legacy_state = {
            "name": "Save legado",
            "participants": ["Lin", "Ken"],
            "state": TournamentState.FINISHED.value,
            "champion": "Lin",
            "current_round": 1,
            "current_match": 0,
            "stats": {"total_fights": 1, "total_kos": 1},
            "bracket": [
                {
                    "round_num": 0,
                    "name": "Final",
                    "completed": True,
                    "matches": [
                        {
                            "match_id": 0,
                            "round_num": 0,
                            "fighter1_name": "Lin",
                            "fighter2_name": "Ken",
                            "winner_name": "Lin",
                            "loser_name": "Ken",
                            "duration": 18.0,
                            "ko_type": "KO",
                            "completed": True,
                        }
                    ],
                }
            ],
        }

        restored = self._load_from_dict(legacy_state)

        restored_match = restored.bracket[0].matches[0]
        self.assertEqual([], restored_match.fight_log)
        self.assertEqual([restored_match], restored.fight_history)
        self.assertEqual(1, restored.get_progress()["completed_matches"])

    def test_explicit_empty_history_is_not_inferred(self):
        state = {
            "name": "Histórico vazio",
            "participants": ["A", "B"],
            "state": TournamentState.FINISHED.value,
            "champion": "A",
            "current_round": 1,
            "current_match": 0,
            "stats": {},
            "fight_history": [],
            "bracket": [
                {
                    "round_num": 0,
                    "name": "Final",
                    "completed": True,
                    "matches": [
                        {
                            "match_id": 0,
                            "round_num": 0,
                            "fighter1_name": "A",
                            "fighter2_name": "B",
                            "winner_name": "A",
                            "loser_name": "B",
                            "duration": 1.0,
                            "ko_type": "KO",
                            "fight_log": [],
                            "completed": True,
                        }
                    ],
                }
            ],
        }

        restored = self._load_from_dict(state)

        self.assertEqual([], restored.fight_history)


if __name__ == "__main__":
    unittest.main()
