#!/usr/bin/env python3
"""Prevent missing/ambiguous evidence from being counted as explained failures."""
import gzip
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'diagnostics'))
from playerbot_failed_audit import audit

def behavior(action,outcome,guid=7,instance=1):
    return f'2026-11-08_10:00:00 TRACE [playerbots.behavior] Bot=Test GUID={guid} map=529 instance={instance} decision=A:{action} - {outcome}\n'
def tick(guid=7,instance=1):
    return f'2026-11-08_10:00:00 TRACE [playerbots.behavior] Bot=Test GUID={guid} map=529 instance={instance} decision=--- AI Tick ---\n'
def execution(action,result='false',reason='unattributed',guid=7,instance=1,code=-1):
    return f"2026-11-08_10:00:00 DEBUG [playerbots.execution] event=action-execution bot={guid} map=529 instance={instance} action='{action}' raw={result} result={result} reason={reason} detail=none spell=5217 cast_result={code}\n"

class FailureAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.logs=self.root/'Logs';self.logs.mkdir()
        definitions=self.root/'src/server/game/Miscellaneous/SharedDefines.h';definitions.parent.mkdir(parents=True)
        definitions.write_text('enum SpellCastResult { SPELL_FAILED_NO_POWER = 88, SPELL_CAST_OK = 255 };')
    def run_audit(self,trace,details=''):
        (self.logs/'PlayerbotBehavior.log').write_text(trace)
        (self.logs/'PlayerbotExecution.log').write_text(details)
        return audit(self.logs,self.root)
    def test_apostrophe_and_native_code(self):
        result=self.run_audit(behavior("tiger's fury",'FAILED'),execution("tiger's fury",reason='cast/prepare-rejected',code=88))
        self.assertTrue(result['diagnostic_matches_behavior'])
        self.assertEqual(result['actions']["tiger's fury"]['native_failure_reasons'],{'cast/prepare-rejected:SPELL_FAILED_NO_POWER':1})
    def test_success_does_not_erase_failure(self):
        result=self.run_audit(tick()+behavior('melee','FAILED')+behavior('reach melee','OK'),execution('melee')+execution('reach melee','true','none'))
        self.assertTrue(result['diagnostic_matches_behavior'])
        self.assertEqual(result['outcomes']['FAILED'],1)
        self.assertEqual(result['actions']['melee']['next_ok_same_tick'],{'reach melee':1})
        self.assertEqual(result['native_failure_reasons'],{'unattributed':1})
    def test_no_cross_tick_or_instance_success(self):
        result=self.run_audit(tick()+behavior('melee','FAILED')+behavior('spell','OK',instance=2)+tick()+behavior('spell','OK'))
        self.assertEqual(result['actions']['melee']['next_ok_same_tick'],{})
        self.assertEqual(result['actions']['melee']['failed_without_later_ok_in_closed_tick'],1)
    def test_missing_and_duplicate_diagnostics(self):
        result=self.run_audit(behavior('melee','FAILED'),execution('another'))
        self.assertFalse(result['diagnostic_matches_behavior'])
        self.assertEqual(len(result['diagnostic_mismatches']),2)
        result=self.run_audit(behavior('melee','FAILED'),execution('melee')*2)
        self.assertFalse(result['diagnostic_matches_behavior'])
    def test_no_diagnostics_is_not_coverage(self):
        result=self.run_audit(behavior('melee','FAILED'))
        self.assertFalse(result['diagnostic_matches_behavior'])
        self.assertEqual(result['native_failure_reasons'],{})
    def test_rotation_continues_tick(self):
        with gzip.open(self.logs/'PlayerbotBehavior.log.2026-11-08_09-59-59.gz','wt') as f:
            f.write(tick()+behavior('melee','FAILED'))
        result=self.run_audit(behavior('reach melee','OK'),execution('melee')+execution('reach melee','true','none'))
        self.assertTrue(result['diagnostic_matches_behavior'])
        self.assertEqual(result['actions']['melee']['next_ok_same_tick'],{'reach melee':1})
    def test_malformed_detail_is_not_explained(self):
        result=self.run_audit(behavior('melee','FAILED'),execution('melee',code='invalid'))
        self.assertFalse(result['diagnostic_matches_behavior'])
        self.assertEqual(len(result['parse_errors']),1)

if __name__=='__main__':unittest.main()
