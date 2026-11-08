#!/usr/bin/env python3
"""Do not turn missing aura/path evidence, teleports, or flags into movement proof."""
import gzip
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diagnostics'))
from playerbot_liquid_audit import audit_directory, audit_liquid, audit_water_fix


def row(**changes):
    values = dict(GUID=24, sample_ms=1000, level=80, map=529, instance=1, x=10, y=20, z=-60,
                  liquid_status=2, cached_liquid_status=2, liquid_level=-60, liquid_depth=-70,
                  surface_delta=0, ground_valid='true', ground_z=-70, ground_delta=10,
                  min_swim_depth=1.2, water_walk_aura='false', water_walk_effects=0, water_walk_omitted=0,
                  water_walk_auras="''", water_walk_flag='false', in_water='false', under_water='false',
                  swimming='false', can_swim='true', can_fly='false', falling='false', flying='false',
                  charging='false', on_transport='false', on_vehicle='false', controlled='false', moving='true',
                  motion_type=5, controlled_motion_type=0, spline_id=12, spline_initialized='true',
                  spline_finalized='false', spline_falling='false', spline_mode=0, spline_cyclic='false',
                  spline_transport='false', spline_first=0, spline_last=2, spline_current=0,
                  spline_point_count=3, spline_points_omitted=0, spline_points="'0:10,20,-60;1:15,20,-60;2:20,20,-60'")
    values.update(changes)
    return 'event=liquid-surface ' + ' '.join(f'{k}={v}' for k,v in values.items())


class LiquidEvidence(unittest.TestCase):
    def pair(self, **changes):
        second = dict(sample_ms=3000, x=14)
        second.update(changes)
        return audit_liquid([('BG:1', row()), ('BG:2', row(**second))])

    def test_geometric_waterwalk_is_not_spell_permission(self):
        result = self.pair()
        self.assertEqual(result['status'], 'evidence-captured')
        self.assertEqual(len(result['no_aura_motion_pairs']), 1)
        self.assertEqual(result['no_aura_motion_pairs'][0]['distance'], 4)

    def test_real_applied_effect_and_flag_are_separate(self):
        result = self.pair(water_walk_aura='true', water_walk_effects=1,
                           water_walk_auras="'546:0:5000:123'", water_walk_flag='true')
        self.assertEqual(result['categories']['water-walk-aura-present'], 1)
        self.assertFalse(result['no_aura_motion_pairs'])
        result = self.pair(water_walk_flag='true')
        self.assertEqual(result['categories']['water-walk-flag-without-aura'], 1)
        self.assertFalse(result['no_aura_motion_pairs'])

    def test_other_movement_and_incomplete_paths_cannot_prove_episode(self):
        for key, value in [('falling','true'), ('flying','true'), ('charging','true'),
                           ('on_transport','true'), ('on_vehicle','true'), ('controlled','true'),
                           ('spline_finalized','true'), ('spline_initialized','false'),
                           ('spline_transport','true'), ('in_water','true'), ('swimming','true'),
                           ('instance',2), ('spline_id',13), ('sample_ms',20000), ('x',10),
                           ('spline_points_omitted',1), ('spline_current',99)]:
            with self.subTest(key=key):
                self.assertFalse(self.pair(**{key:value})['no_aura_motion_pairs'])

    def test_missing_and_corrupt_evidence_fails_closed(self):
        for line in [row().replace('water_walk_aura=false ', ''), row(x='nan'), row(z=-50),
                     row(water_walk_aura='true'), row(spline_points="'0:10,20,-60'")]:
            result = audit_liquid([('BG:1', line)])
            self.assertEqual(result['status'], 'incomplete-diagnostics')

    def test_no_observation_is_not_pass(self):
        self.assertEqual(audit_liquid([('BG:1','GUID=24 phase=combat')])['status'], 'no-surface-episode')

    def test_plain_and_gzip_rotations_are_combined(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            with gzip.open(path/'PlayerbotBG.log.1.gz', 'wt') as out:
                out.write(row()+'\n')
            (path/'PlayerbotBG.log').write_text(row(sample_ms=3000,x=14)+'\n')
            self.assertEqual(len(audit_directory(path)['no_aura_motion_pairs']), 1)

    def test_underwater_path_is_positive_evidence_without_hiding_surface_samples(self):
        underwater = row(z=-61.2, surface_delta=-1.2, ground_delta=8.8, in_water='true', swimming='true').replace(
            'event=liquid-surface', 'event=liquid-motion')
        result = audit_liquid([('BG:1', row()), ('BG:2', underwater)])
        self.assertEqual(result['status'], 'evidence-captured')
        self.assertEqual(result['events'], {'liquid-surface':1, 'liquid-motion':1})
        self.assertEqual(result['underwater_paths'], ['BG:2'])
        self.assertEqual(result['deep_surface_without_aura'], ['BG:1'])
        self.assertFalse(result['no_aura_motion_pairs'])

    def test_nearby_vmap_support_is_not_deep_water(self):
        result = audit_liquid([('BG:1', row(ground_z=-60.04,ground_delta=.04))])
        self.assertFalse(result['deep_surface_without_aura'])

    def test_near_surface_swimmer_is_not_water_walking(self):
        # Live GUID6 / spline112500: the endpoint is 0.12931824m below
        # water, with queried/cached IN_WATER and the swimming flag. The
        # diagnostic +/-0.15m capture band is not a gameplay boundary:
        # Map/GridMap::GetLiquidStatus uses delta > 0 for IN_WATER.
        for delta in (-.12931824, -.001):
            with self.subTest(delta=delta):
                near = row(z=-60+delta, surface_delta=delta, ground_delta=10+delta,
                           liquid_status=4, cached_liquid_status=4,
                           in_water='true', swimming='true')
                result = audit_liquid([('BG:near',near), ('BG:old-defect',row())])
                self.assertEqual(result['events'], {'liquid-surface':2})
                self.assertEqual(result['deep_surface_without_aura'], ['BG:old-defect'])
                self.assertEqual(result['near_surface_swimming'], ['BG:near'])
                # A stale cached status or false in-water/swimming state is
                # not sufficient positive evidence to dismiss the sample.
                for old, new in [('cached_liquid_status=4','cached_liquid_status=2'),
                                 ('in_water=true','in_water=false'),
                                 ('swimming=true','swimming=false')]:
                    self.assertEqual(audit_liquid([('BG:bad',near.replace(old,new))])[
                        'deep_surface_without_aura'], ['BG:bad'])

    def test_native_near_surface_charge_uses_liquid_state(self):
        charge = ('event=charge-path GUID=6 sample_ms=744576 map=529 instance=1 spline_id=112500 '
                  'duration_ms=1027 points=8 query_nodes=1024 end_x=1020.2359 end_y=917.8377 '
                  'end_z=-67.01931 liquid_status=4 liquid_level=-66.88999 liquid_depth=-71.31101 '
                  'ground_valid=true ground_z=-71.31101 water_walk_aura=false water_walk_flag=false')
        result = audit_liquid([('BG:charge',charge)])
        self.assertEqual(len(result['native_underwater_charges']),1)
        self.assertFalse(result['native_charge_surface_without_aura'])
        old_defect = charge.replace('end_z=-67.01931','end_z=-66.88999').replace(
            'liquid_status=4','liquid_status=2')
        self.assertEqual(len(audit_liquid([('BG:old-defect',old_defect)])[
            'native_charge_surface_without_aura']),1)

    def test_post_resurrection_permission_and_missing_coverage(self):
        result = audit_liquid([('BG:1','GUID=39 phase=resurrected water_walk_aura=false water_walk_flag=false'),
                               ('BG:2','GUID=40 phase=resurrected water_walk_aura=true water_walk_flag=true'),
                               ('BG:3','GUID=41 phase=resurrected water_walk_aura=false water_walk_flag=true'),
                               ('BG:4','GUID=42 phase=resurrected alive=true')])
        self.assertEqual(len(result['resurrection_samples']),4)
        self.assertEqual([r['guid'] for r in result['resurrection_flag_mismatches']],['41'])
        self.assertFalse(result['resurrection_samples'][-1]['complete'])
        self.assertEqual(result['status'],'no-surface-episode')

    def test_fix_requires_native_charge_and_actual_underwater_path(self):
        swimming = row(z=-61.2,surface_delta=-1.2,ground_delta=8.8,in_water='true',swimming='true').replace(
            'event=liquid-surface','event=liquid-motion')
        revived = 'GUID=39 phase=resurrected water_walk_aura=false water_walk_flag=false'
        charge = ('event=charge-path GUID=39 sample_ms=2000 map=529 instance=1 spline_id=12 '
                  'duration_ms=800 points=5 query_nodes=1024 end_x=15 end_y=20 end_z=-61.2 '
                  'liquid_status=4 liquid_level=-60 liquid_depth=-70 ground_valid=true ground_z=-70 '
                  'water_walk_aura=false water_walk_flag=false')
        rows = [('BG:1',swimming),('BG:2',revived),('BG:3',charge)]
        result = audit_liquid(rows)
        self.assertEqual(audit_water_fix(result)['status'],'passed')
        for omitted in range(3):
            self.assertEqual(audit_water_fix(audit_liquid(rows[:omitted]+rows[omitted+1:]))['status'],'coverage-gap')
        surface_charge = charge.replace('end_z=-61.2','end_z=-60').replace('liquid_status=4','liquid_status=2')
        self.assertEqual(audit_water_fix(audit_liquid(rows[:2]+[('BG:3',surface_charge)]))['status'],'failed')
        stale = revived.replace('water_walk_flag=false','water_walk_flag=true')
        self.assertEqual(audit_water_fix(audit_liquid([rows[0],('BG:2',stale),rows[2]]))['status'],'failed')
        corrupt = charge.replace('points=5','points=0')
        self.assertEqual(audit_water_fix(audit_liquid(rows[:2]+[('BG:3',corrupt)]))['status'],'failed')


if __name__ == '__main__':
    unittest.main()
