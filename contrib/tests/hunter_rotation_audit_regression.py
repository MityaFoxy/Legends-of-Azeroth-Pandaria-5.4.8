#!/usr/bin/env python3
"""Reject missing native effects and unproved paths, including Survival AoE."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diagnostics'))
from hunter_rotation_audit import audit_rotation


class RotationAcceptanceTests(unittest.TestCase):
    def audit(self, actions=None, **observations):
        fields = dict(guid='107', primary='true', secondary='true', mark='true', damage='true',
                      black_arrow='true', requires_black_arrow='true', known_serpent_spread='true')
        fields.update(observations)
        rows = ['Sting rotation summary ' + ' '.join(f'{k}={v}' for k, v in fields.items())]
        if actions is None:
            actions = {"hunter's mark": {'OK': 1}, 'black arrow': {'OK': 1}, 'multi-shot': {'OK': 31}}
        return audit_rotation(actions, rows, 107)

    def test_native_spread_does_not_claim_direct_action_coverage(self):
        result = self.audit()
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['sting_route'], 'serpent-spread')
        self.assertFalse(any(result['direct_actions_observed'].values()))

    def test_direct_route_without_passive_or_black_arrow(self):
        result = self.audit(actions={name: {'OK': 1} for name in
                            ("hunter's mark", 'serpent sting', 'serpent sting on attacker')},
                            known_serpent_spread='false', requires_black_arrow='false', black_arrow='false')
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['sting_route'], 'direct')

    def test_multishot_cannot_replace_sting_without_known_passive(self):
        for value in ('false', 'missing'):
            with self.subTest(value=value):
                self.assertFalse(self.audit(known_serpent_spread=value)['passed'])

    def test_passive_and_effects_without_successful_engine_action_fail(self):
        for outcome in ('FAILED', 'IMPOSSIBLE', 'USELESS', 'UNKNOWN'):
            with self.subTest(outcome=outcome):
                actions = {"hunter's mark": {'OK': 1}, 'black arrow': {'OK': 1}, 'multi-shot': {outcome: 31}}
                self.assertFalse(self.audit(actions=actions)['passed'])

    def test_successful_actions_do_not_replace_native_effects(self):
        for effect in ('primary', 'secondary', 'mark', 'damage', 'black_arrow'):
            with self.subTest(effect=effect):
                self.assertFalse(self.audit(**{effect: 'false'})['passed'])

    def test_other_hunter_summary_cannot_satisfy_gate(self):
        self.assertFalse(self.audit(guid='19')['passed'])

    def test_missing_or_duplicate_summary_fails(self):
        self.assertFalse(audit_rotation({}, [], 107)['passed'])
        row = 'Sting rotation summary guid=107 primary=true'
        self.assertFalse(audit_rotation({}, [row, row], 107)['passed'])

    def test_black_arrow_effect_without_engine_action_fails(self):
        self.assertFalse(self.audit(actions={"hunter's mark": {'OK': 1}, 'multi-shot': {'OK': 31}})['passed'])

    def test_one_direct_action_is_not_both_paths(self):
        actions = {name: {'OK': 1} for name in ("hunter's mark", 'black arrow', 'serpent sting')}
        self.assertFalse(self.audit(actions=actions, known_serpent_spread='false')['passed'])


if __name__ == '__main__':
    unittest.main()
