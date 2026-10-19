#!/usr/bin/env python3
"""Five-bot smoke observer: separate evidence, strict roster, no false group success."""
import ast
import inspect
import pathlib
import sys
import unittest

root = pathlib.Path(sys.argv.pop(1))
sys.path.insert(0, str(root / "contrib/diagnostics"))
from botlife_quest_group_smoke import new_evidence, observe, observation_error, parse_assignments, preparation_error


class GroupObserverTests(unittest.TestCase):
    def test_preflight_rejects_naked_character_without_mutating_it(self):
        self.assertIsNotNone(preparation_error(dict(level="56", equipment_slots="")))
        self.assertIsNotNone(preparation_error(dict(level="56", equipment_slots="15")))
        self.assertIsNotNone(preparation_error(dict(level="56", equipment_slots="4\n6")))
        self.assertIsNone(preparation_error(dict(level="56", equipment_slots="4\n6\n15")))
        self.assertIsNone(preparation_error(dict(level="5", equipment_slots="15")))

    def test_runner_event_calls_match_callback_signature(self):
        tree = ast.parse((root / "contrib/diagnostics/botlife_quest_group_smoke.py").read_text())
        callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "event")
        parameters = [inspect.Parameter(arg.arg, inspect.Parameter.POSITIONAL_OR_KEYWORD) for arg in callback.args.args]
        parameters.append(inspect.Parameter(callback.args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
        signature = inspect.Signature(parameters)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "event":
                signature.bind(*node.args, **{kw.arg: kw.value for kw in node.keywords})

    def setUp(self):
        self.roster = parse_assignments("11:8280,22:8280,185:8280,207:8280,584:8280")
        self.rows = new_evidence(self.roster)

    def emit(self, guid, suffix):
        return observe(f"INFO BotLife quest-run guid={guid} quest=8280 {suffix}", self.roster, self.rows)

    def test_five_independent_successes(self):
        for guid in self.roster:
            self.emit(guid, "event=start resumed=false result=running")
            self.emit(guid, "event=progress objective=257615 count=15 required=15")
            self.emit(guid, "event=stage stage=TurnIn")
            self.emit(guid, "event=finish result=completed rewarded=true reason=rewarded visits=15")
        self.assertTrue(all(row["success"] for row in self.rows.values()))

    def test_one_success_is_not_group_success(self):
        self.emit(11, "event=start")
        self.emit(11, "event=progress count=1")
        self.emit(11, "event=stage stage=TurnIn")
        self.emit(11, "event=finish result=completed rewarded=true reason=rewarded visits=15")
        self.assertTrue(self.rows[11]["success"])
        self.assertFalse(any(self.rows[guid]["success"] for guid in self.roster if guid != 11))

    def test_each_success_requires_own_progress_and_turn_in(self):
        for missing in ("start", "progress", "turn_in"):
            self.rows = new_evidence(self.roster)
            if missing != "start":
                self.emit(11, "event=start")
            if missing != "progress":
                self.emit(11, "event=progress count=1")
            if missing != "turn_in":
                self.emit(11, "event=stage stage=TurnIn")
            self.emit(11, "event=finish result=completed rewarded=true reason=rewarded visits=15")
            self.assertFalse(self.rows[11]["success"])

    def test_failure_does_not_end_other_observation(self):
        self.emit(11, "event=finish result=failed rewarded=false reason=quest-no-progress")
        self.emit(22, "event=start")
        self.emit(22, "event=progress count=1")
        self.assertIsNotNone(self.rows[11]["terminal"])
        self.assertFalse(self.rows[11]["success"])
        self.assertEqual(len(self.rows[22]["progress"]), 1)

    def test_reject_wrong_bot_wrong_quest_duplicate_start(self):
        with self.assertRaises(RuntimeError):
            self.emit(12, "event=start")
        with self.assertRaises(RuntimeError):
            observe("quest-run guid=11 quest=999 event=start", self.roster, self.rows)
        self.emit(11, "event=start")
        with self.assertRaises(RuntimeError):
            self.emit(11, "event=start")

    def test_roster_validation(self):
        self.assertEqual(parse_assignments("11:8320"), {11: 8320})
        self.assertEqual(len(parse_assignments("11:8320,185:8320,584:8320")), 3)
        for value in ("", "11:1,11:2", "11:1,11:2,22:3,33:4,44:5", "0:1,2:1,3:1,4:1,5:1",
                      "1:1,2:1,3:1,4:1,5:1,6:1", "1:1,2:1,3:1,4:1,5:1,",
                      "1:1,2:1,3:1,4:1,4294967296:1", "1:1, 2:1,3:1,4:1,5:1"):
            with self.assertRaises(ValueError):
                parse_assignments(value)

    def test_death_is_nonterminal_and_does_not_count_as_progress(self):
        self.emit(11, "event=start")
        self.emit(11, "event=progress count=6")
        self.emit(11, "event=death-wait deaths=1")
        self.assertTrue(self.rows[11]["recovering"])
        self.assertIsNone(self.rows[11]["terminal"])
        self.assertEqual(len(self.rows[11]["progress"]), 1)
        self.emit(11, "event=resurrected deaths=1")
        self.assertFalse(self.rows[11]["recovering"])
        self.assertEqual(self.rows[11]["deaths"], 1)
        self.assertEqual(self.rows[11]["resurrections"], 1)
        self.assertEqual(self.rows[22]["deaths"], 0)
        self.assertEqual(self.rows[11]["progress_after_resurrection"], [])
        self.emit(11, "event=progress count=10")
        self.assertEqual(len(self.rows[11]["progress_after_resurrection"]), 1)
        self.emit(11, "event=stage stage=TurnIn")
        self.emit(11, "event=finish result=completed rewarded=true reason=rewarded visits=15")
        self.assertTrue(self.rows[11]["success"])

    def test_short_observation_is_not_quest_completion(self):
        for guid in self.roster:
            self.emit(guid, "event=start")
        self.emit(11, "event=death-wait deaths=1")
        self.assertIsNone(observation_error(self.roster, self.rows, set(self.roster)))
        self.assertFalse(any(row["success"] for row in self.rows.values()))
        self.assertIsNotNone(observation_error(self.roster, self.rows, {11}))
        self.rows[22]["started"] = False
        self.assertIsNotNone(observation_error(self.roster, self.rows, set(self.roster)))
        self.rows[22]["started"] = True
        self.emit(22, "event=finish result=failed reason=quest-no-progress")
        self.assertIsNotNone(observation_error(self.roster, self.rows, set(self.roster)))


if __name__ == "__main__":
    unittest.main()
