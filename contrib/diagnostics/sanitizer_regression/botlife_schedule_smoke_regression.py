#!/usr/bin/env python3
"""Scheduler observer must distinguish actual completions and early restarts."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(sys.argv.pop(1)) / "contrib/diagnostics"))
from botlife_schedule_smoke import inspect_event


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.rows = {1138: dict(walks=0, leisure=0, outings=0, cooldown_gaps=[], last_outing_end=None,
                                combat_pauses=0, combat_resumes=0)}

    def emit(self, seconds, suffix):
        inspect_event(f"2026-11-24_00:{seconds // 60:02}:{seconds % 60:02} INFO BotLife {suffix}", self.rows, 60)

    def test_cooldown_uses_server_time_and_full_guid(self):
        self.emit(0, "guid=GUID Full: 0x123 Type: Player Low: 1138 transition=QUEST->LEISURE")
        self.emit(60, "guid=GUID Full: 0x123 Type: Player Low: 1138 activity=QUEST event=start")
        self.assertEqual(self.rows[1138]["cooldown_gaps"], [60])

    def test_early_restart_rejected(self):
        self.emit(0, "guid=GUID Full: 0x123 Type: Player Low: 1138 transition=QUEST->LEISURE")
        with self.assertRaises(RuntimeError):
            self.emit(30, "guid=GUID Full: 0x123 Type: Player Low: 1138 activity=QUEST event=start")

    def test_start_or_failed_walk_is_not_success(self):
        self.emit(0, "walk guid=1138 event=start landmark=4")
        self.emit(1, "walk guid=1138 event=finish result=failed")
        self.assertEqual(self.rows[1138]["walks"], 0)
        self.emit(2, "walk guid=1138 event=finish result=completed")
        self.emit(3, "service guid=1138 activity=LEISURE result=completed")
        self.assertEqual(self.rows[1138]["walks"], 1)
        self.assertEqual(self.rows[1138]["leisure"], 1)

    def test_foreign_actor_is_failure(self):
        with self.assertRaises(RuntimeError):
            self.emit(0, "walk guid=9 event=start")


if __name__ == "__main__":
    unittest.main()
