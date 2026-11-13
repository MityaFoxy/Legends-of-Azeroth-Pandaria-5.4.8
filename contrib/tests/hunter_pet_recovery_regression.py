#!/usr/bin/env python3
"""Check recovery decisions without touching a database."""
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "diagnostics/hunter_pet_recovery.py"
spec = importlib.util.spec_from_file_location("recovery", source)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def pet(id=1, **kw):
    return dict(dict(id=id, owner=10, owner_name="Hunter", slot=255, current=0, savetime=id,
                     online=0, type=1, family=2, type_flags=1, **{"class": 3}, account_name="RNDBOT0"), **kw)


class RecoveryTests(unittest.TestCase):
    def test_current_beats_more_recent(self):
        result = recovery.plan_recovery([pet(1, current=1), pet(2, current=1)])
        self.assertEqual(result["changes"], [dict(id=1, owner=10, **{"from": 255}, to=0),
                                             dict(id=2, owner=10, **{"from": 255}, to=5)])
        self.assertEqual(result["choices"][0]["reason"], "saved-current-id")

    def test_preserves_existing_slots_and_unique_latest(self):
        result = recovery.plan_recovery([pet(1, slot=5), pet(2), pet(3)])
        self.assertEqual([(p["id"], p["to"]) for p in result["changes"]], [(3, 0), (2, 6)])
        self.assertEqual(result["choices"][0]["reason"], "unique-latest-save")

    def test_ambiguous_latest_is_not_guessed(self):
        result = recovery.plan_recovery([pet(1, savetime=1), pet(2, savetime=1)])
        self.assertFalse(result["changes"])
        self.assertEqual({p["reason"] for p in result["skipped"]}, {"ambiguous-latest-pet"})

    def test_overflow_retains_every_identity(self):
        result = recovery.plan_recovery([pet(i) for i in range(1, 71)])
        self.assertEqual(len(result["changes"]), 51)
        self.assertEqual(len(result["skipped"]), 19)
        ids = [p["id"] for p in result["changes"] + result["skipped"]]
        self.assertEqual(sorted(ids), list(range(1, 71)))
        self.assertEqual({p["to"] for p in result["changes"]}, {0, *range(5, 55)})

    def test_exotic_current_requires_evidence(self):
        result = recovery.plan_recovery([pet(type_flags=0x10001)])
        self.assertFalse(result["changes"])
        self.assertEqual(result["skipped"][0]["reason"], "active-exotic-needs-live-check")

    def test_protected_and_invalid_owners(self):
        for change in ({"account_name": "PLAYER"}, {"online": 1}, {"class": 9},
                       {"current": 99}, {"type": None}, {"family": 0}, {"type_flags": 0}):
            with self.subTest(change=change):
                self.assertFalse(recovery.plan_recovery([pet(**change)])["changes"])

    def test_existing_active_is_preserved(self):
        result = recovery.plan_recovery([pet(1, slot=0), pet(2), pet(3)])
        self.assertFalse(result["choices"])
        self.assertEqual([(p["id"], p["to"]) for p in result["changes"]], [(3, 5), (2, 6)])

    def test_reapplication_has_no_changes(self):
        rows = [pet(1), pet(2)]
        plan = recovery.plan_recovery(rows)
        slots = {p["id"]: p["to"] for p in plan["changes"]}
        self.assertFalse(recovery.plan_recovery([dict(p, slot=slots[p["id"]]) for p in rows])["changes"])


if __name__ == "__main__":
    unittest.main()
