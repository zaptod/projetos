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

    def _assert_rejected_without_partial_mutation(self, state):
        target = Tournament("Estado intacto")
        target.participants = ["Sentinela A", "Sentinela B"]
        target.current_match = 1
        target.stats["total_fights"] = 7
        snapshot = copy.deepcopy(target.__dict__)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text(json.dumps(state), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                loaded = target.load_state(str(path))

        self.assertFalse(loaded)
        self.assertEqual(snapshot, target.__dict__)

    def _finished_four_fighter_state(self):
        tournament = Tournament("Chave valida")
        tournament.participants = ["A", "B", "C", "D"]
        with (
            patch.object(tournament_module.random, "shuffle"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(tournament.generate_bracket())
            self.assertTrue(tournament.start_tournament())
            self.assertTrue(tournament.record_match_result("A", 1.0, "KO", ["m0"]))
            self.assertTrue(tournament.record_match_result("C", 2.0, "SUB", ["m1"]))
            self.assertTrue(tournament.record_match_result("A", 3.0, "KO", ["m2"]))

        return self._save_to_dict(tournament)

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
        tournament.stats["total_kos"] = 1

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

    def test_explicit_history_cannot_omit_a_completed_real_match(self):
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

        self._assert_rejected_without_partial_mutation(state)

    def test_semantic_bracket_corruptions_are_rejected_transactionally(self):
        valid = self._finished_four_fighter_state()
        cases = {}

        wrong_champion = copy.deepcopy(valid)
        wrong_champion["champion"] = "C"
        cases["champion_not_final_winner"] = wrong_champion

        foreign_participant = copy.deepcopy(valid)
        foreign_participant["participants"][0] = "Intruso"
        cases["participant_not_in_first_round"] = foreign_participant

        forged_bye = copy.deepcopy(valid)
        forged_bye["bracket"][0]["matches"][0]["fighter1_is_bye"] = True
        cases["forged_bye_sentinel"] = forged_bye

        broken_propagation = copy.deepcopy(valid)
        final_match = broken_propagation["bracket"][-1]["matches"][0]
        final_match.update(
            {
                "fighter1_name": "B",
                "winner_name": "B",
                "loser_name": "C",
            }
        )
        final_history = broken_propagation["fight_history"][-1]
        final_history.update(
            {
                "fighter1_name": "B",
                "winner_name": "B",
                "loser_name": "C",
            }
        )
        broken_propagation["champion"] = "B"
        cases["winner_not_propagated"] = broken_propagation

        skipped_match_id = copy.deepcopy(valid)
        skipped_match_id["bracket"][0]["matches"][1]["match_id"] = 9
        cases["non_sequential_match_id"] = skipped_match_id

        stale_pointer = copy.deepcopy(valid)
        stale_pointer["state"] = TournamentState.IN_PROGRESS.value
        stale_pointer["champion"] = None
        stale_pointer["current_round"] = 0
        stale_pointer["current_match"] = 0
        stale_pointer["bracket"][-1]["matches"][0]["completed"] = False
        stale_pointer["bracket"][-1]["matches"][0]["winner_name"] = None
        stale_pointer["bracket"][-1]["matches"][0]["loser_name"] = None
        stale_pointer["bracket"][-1]["matches"][0]["duration"] = 0.0
        stale_pointer["bracket"][-1]["matches"][0]["ko_type"] = ""
        stale_pointer["bracket"][-1]["matches"][0]["fight_log"] = []
        stale_pointer["bracket"][-1]["completed"] = False
        stale_pointer["fight_history"].pop()
        stale_pointer["stats"]["total_fights"] -= 1
        stale_pointer["stats"]["total_kos"] -= 1
        cases["stale_active_pointer"] = stale_pointer

        partial_pending_result = copy.deepcopy(stale_pointer)
        pending_final = partial_pending_result["bracket"][-1]["matches"][0]
        pending_final["duration"] = 1.0
        cases["pending_partial_result"] = partial_pending_result

        wrong_ko_stats = copy.deepcopy(valid)
        wrong_ko_stats["stats"]["total_kos"] -= 1
        cases["ko_stats_mismatch"] = wrong_ko_stats

        for label, state in cases.items():
            with self.subTest(case=label):
                self._assert_rejected_without_partial_mutation(state)

    def test_history_must_match_every_persisted_match_field(self):
        valid = self._finished_four_fighter_state()
        mutations = {
            "duration": lambda match: match.__setitem__("duration", 99.0),
            "ko_type": lambda match: match.__setitem__("ko_type", "DECISAO"),
            "bye_flag": lambda match: match.__setitem__(
                "fighter1_is_bye", True
            ),
            "fight_log": lambda match: match.__setitem__(
                "fight_log", ["registro adulterado"]
            ),
        }

        for label, mutate in mutations.items():
            state = copy.deepcopy(valid)
            mutate(state["fight_history"][0])
            with self.subTest(field=label):
                self._assert_rejected_without_partial_mutation(state)

    def test_history_rejects_ghost_missing_and_reordered_matches(self):
        valid = self._finished_four_fighter_state()

        ghost = copy.deepcopy(valid)
        ghost_match = copy.deepcopy(ghost["fight_history"][-1])
        ghost_match["match_id"] = 99
        ghost["fight_history"].append(ghost_match)

        missing = copy.deepcopy(valid)
        missing["fight_history"].pop(0)
        missing["stats"]["total_fights"] -= 1

        reordered = copy.deepcopy(valid)
        reordered["fight_history"][0], reordered["fight_history"][1] = (
            reordered["fight_history"][1],
            reordered["fight_history"][0],
        )

        for label, state in {
            "ghost": ghost,
            "missing": missing,
            "reordered": reordered,
        }.items():
            with self.subTest(case=label):
                self._assert_rejected_without_partial_mutation(state)

    def test_valid_generated_bye_round_trip_keeps_canonical_history(self):
        tournament = Tournament("Chave com BYE")
        tournament.participants = ["A", "B", "C"]
        with (
            patch.object(tournament_module.random, "shuffle"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(tournament.generate_bracket())
            self.assertTrue(tournament.start_tournament())
            current = tournament.get_current_match()
            self.assertIsNotNone(current)
            self.assertTrue(
                tournament.record_match_result(
                    current.fighter1_name,
                    2.0,
                    "KO",
                    ["semifinal"],
                )
            )
            final = tournament.get_current_match()
            self.assertIsNotNone(final)
            self.assertTrue(
                tournament.record_match_result(
                    final.fighter1_name,
                    4.0,
                    "KO",
                    ["final"],
                )
            )

        saved = self._save_to_dict(tournament)
        restored = self._load_from_dict(saved)

        completed_byes = [
            match
            for match in restored.bracket[0].matches
            if match.ko_type == "BYE"
        ]
        self.assertEqual(1, len(completed_byes))
        self.assertNotIn(completed_byes[0], restored.fight_history)
        self.assertEqual(
            [1, 2],
            [match.match_id for match in restored.fight_history],
        )

        legacy = copy.deepcopy(saved)
        legacy.pop("generated_byes")
        legacy_restored = self._load_from_dict(legacy)
        self.assertEqual({"BYE_1"}, legacy_restored._generated_byes)

    def test_waiting_pre_bracket_save_preserves_generated_byes(self):
        tournament = Tournament("BYEs antes da chave")
        tournament.participants = ["A", "B", "C"]
        tournament._adjust_to_power_of_two()
        self.assertEqual([], tournament.bracket)
        self.assertEqual({"BYE_1"}, tournament._generated_byes)

        saved = self._save_to_dict(tournament)
        self.assertEqual(["BYE_1"], saved["generated_byes"])
        restored = self._load_from_dict(saved)
        self.assertEqual({"BYE_1"}, restored._generated_byes)

        with (
            patch.object(tournament_module.random, "shuffle"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(restored.generate_bracket())

        bye_matches = [
            match
            for match in restored.bracket[0].matches
            if match.fighter1_is_bye or match.fighter2_is_bye
        ]
        self.assertEqual(1, len(bye_matches))
        self.assertIn("BYE_1", restored.participants)

        round_tripped = self._load_from_dict(self._save_to_dict(restored))
        self.assertEqual({"BYE_1"}, round_tripped._generated_byes)

    def test_legacy_waiting_save_does_not_guess_bye_from_a_name(self):
        legacy_state = {
            "name": "Legado pre-bracket",
            "participants": ["A", "B", "C", "BYE_1"],
            "state": TournamentState.WAITING.value,
            "champion": None,
            "current_round": 0,
            "current_match": 0,
            "bracket": [],
            "fight_history": [],
            "stats": {},
        }

        restored = self._load_from_dict(legacy_state)

        self.assertEqual(set(), restored._generated_byes)
        with (
            patch.object(tournament_module.random, "shuffle"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(restored.generate_bracket())
        self.assertFalse(
            any(
                match.fighter1_is_bye or match.fighter2_is_bye
                for match in restored.bracket[0].matches
            )
        )

    def test_generated_byes_metadata_is_validated_transactionally(self):
        tournament = Tournament("BYEs validos")
        tournament.participants = ["A", "B", "C"]
        tournament._adjust_to_power_of_two()
        valid = self._save_to_dict(tournament)

        cases = {}
        wrong_type = copy.deepcopy(valid)
        wrong_type["generated_byes"] = "BYE_1"
        cases["wrong_type"] = wrong_type

        duplicate = copy.deepcopy(valid)
        duplicate["generated_byes"] = ["BYE_1", "BYE_1"]
        cases["duplicate"] = duplicate

        foreign = copy.deepcopy(valid)
        foreign["generated_byes"] = ["BYE_9"]
        cases["foreign"] = foreign

        malformed = copy.deepcopy(valid)
        malformed["participants"][-1] = "BYE_01"
        malformed["generated_byes"] = ["BYE_01"]
        cases["malformed"] = malformed

        too_many = copy.deepcopy(valid)
        too_many["participants"] = ["A", "B", "BYE_1", "BYE_2"]
        too_many["generated_byes"] = ["BYE_1", "BYE_2"]
        cases["invalid_padding"] = too_many

        bracketed = self._load_from_dict(valid)
        with (
            patch.object(tournament_module.random, "shuffle"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(bracketed.generate_bracket())
        mismatch = self._save_to_dict(bracketed)
        mismatch["generated_byes"] = []
        cases["bracket_mismatch"] = mismatch

        for label, state in cases.items():
            with self.subTest(case=label):
                self._assert_rejected_without_partial_mutation(state)

    def test_generate_bracket_resets_all_derived_tournament_state(self):
        tournament = self._load_from_dict(self._finished_four_fighter_state())
        self.assertEqual(TournamentState.FINISHED, tournament.state)
        self.assertIsNotNone(tournament.champion)
        self.assertTrue(tournament.fight_history)

        with (
            patch.object(tournament_module.random, "shuffle"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertTrue(tournament.generate_bracket())

        self.assertEqual(TournamentState.WAITING, tournament.state)
        self.assertIsNone(tournament.champion)
        self.assertEqual(0, tournament.current_round)
        self.assertEqual(0, tournament.current_match)
        self.assertEqual([], tournament.fight_history)
        self.assertEqual(
            {
                "total_fights": 0,
                "total_kos": 0,
                "fastest_ko": None,
                "longest_fight": None,
                "most_aggressive": None,
            },
            tournament.stats,
        )
        self.assertTrue(tournament.bracket)
        for round_obj in tournament.bracket:
            self.assertFalse(round_obj.completed)
            for match in round_obj.matches:
                self.assertFalse(match.completed)
                self.assertIsNone(match.winner_name)
                self.assertIsNone(match.loser_name)
                self.assertEqual(0.0, match.duration)
                self.assertEqual("", match.ko_type)
                self.assertEqual([], match.fight_log)

        restored = self._load_from_dict(self._save_to_dict(tournament))
        self.assertEqual(TournamentState.WAITING, restored.state)
        self.assertIsNone(restored.champion)
        self.assertEqual([], restored.fight_history)
        self.assertEqual(tournament.stats, restored.stats)

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
