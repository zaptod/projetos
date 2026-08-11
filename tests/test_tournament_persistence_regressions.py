import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import neural_fights.tournament.tournament_mode as tournament_module

from neural_fights.tournament.tournament_mode import (
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

    def test_default_state_uses_ignored_runtime_path_independent_of_cwd(self):
        tournament = Tournament("Estado local")
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_path = Path(temp_dir) / "runtime" / "neural_fights.tournament.json"
            other_cwd = Path(temp_dir) / "other"
            other_cwd.mkdir()
            with (
                patch.object(
                    tournament_module,
                    "DEFAULT_TOURNAMENT_STATE",
                    str(runtime_path),
                ),
                patch.dict(
                    os.environ,
                    {tournament_module.TOURNAMENT_STATE_ENV: ""},
                ),
                redirect_stdout(io.StringIO()),
            ):
                tournament.save_state()
                previous_cwd = Path.cwd()
                try:
                    os.chdir(other_cwd)
                    restored = Tournament()
                    self.assertTrue(restored.load_state())
                finally:
                    os.chdir(previous_cwd)

        self.assertEqual(restored.name, "Estado local")

    def test_relative_environment_override_stays_in_runtime_directory(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(tournament_module.database, "RUNTIME_DIR", temp_dir),
            patch.dict(
                os.environ,
                {tournament_module.TOURNAMENT_STATE_ENV: "estado-custom.json"},
            ),
        ):
            resolved = tournament_module._resolver_caminho_estado()

        self.assertEqual(
            Path(resolved),
            Path(temp_dir).resolve() / "estado-custom.json",
        )

    def test_relative_explicit_path_is_resolved_from_current_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_cwd = Path.cwd()
            try:
                os.chdir(temp_dir)
                resolved = tournament_module._resolver_caminho_estado("save.json")
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(Path(resolved), Path(temp_dir).resolve() / "save.json")

    def test_console_output_escapes_names_unsupported_by_cp1252(self):
        tournament = Tournament("Torneio 🔥")
        tournament.participants = ["Fogo🔥", "Gelo❄"]
        with redirect_stdout(io.StringIO()):
            self.assertTrue(tournament.generate_bracket())

        raw = io.BytesIO()
        console = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
        try:
            with patch.object(tournament_module.sys, "stdout", console):
                tournament_module._console_print(tournament.get_bracket_display())
                console.flush()
        finally:
            console.detach()

        rendered = raw.getvalue().decode("cp1252")
        self.assertIn("Torneio", rendered)
        self.assertIn("\\U0001f525", rendered)

    def test_corrupt_nested_state_is_rejected_without_partial_mutation(self):
        match = TournamentMatch(
            match_id=0,
            round_num=0,
            fighter1_name="A",
            fighter2_name="B",
            winner_name="A",
            loser_name="B",
            duration=3.0,
            ko_type="KO",
            fight_log=["fim"],
            completed=True,
        )
        source = Tournament("Valido")
        source.participants = ["A", "B"]
        source.bracket = [
            TournamentRound(0, "Final", matches=[match], completed=True)
        ]
        source.fight_history = [match]
        source.state = TournamentState.FINISHED
        source.champion = "A"
        source.current_round = 1
        source.stats["total_fights"] = 1
        source.stats["total_kos"] = 1
        valid = self._save_to_dict(source)

        cases = {}
        invalid_stats = copy.deepcopy(valid)
        invalid_stats["stats"]["total_fights"] = "um"
        cases["stats"] = invalid_stats
        invalid_log = copy.deepcopy(valid)
        invalid_log["bracket"][0]["matches"][0]["fight_log"] = "abc"
        cases["fight_log"] = invalid_log
        invalid_pointer = copy.deepcopy(valid)
        invalid_pointer["current_round"] = 0
        invalid_pointer["current_match"] = 1
        cases["pointer"] = invalid_pointer

        for label, state in cases.items():
            target = Tournament("Intacto")
            target.participants = ["X", "Y"]
            snapshot = (target.name, list(target.participants), target.state)
            with tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "state.json"
                path.write_text(json.dumps(state), encoding="utf-8")
                with self.subTest(case=label), redirect_stdout(io.StringIO()):
                    self.assertFalse(target.load_state(str(path)))

            self.assertEqual(
                snapshot,
                (target.name, target.participants, target.state),
            )


if __name__ == "__main__":
    unittest.main()
