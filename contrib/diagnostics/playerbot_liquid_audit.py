#!/usr/bin/env python3
"""Review simultaneous liquid/aura/executing-spline observations, not fix movement."""
import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path
import re


def audit_liquid(rows):
    records, errors, resurrections, charges = [], [], [], []
    fields = ('GUID sample_ms level map instance x y z liquid_status cached_liquid_status liquid_level '
              'liquid_depth surface_delta ground_valid ground_z ground_delta water_walk_aura water_walk_effects water_walk_omitted water_walk_auras '
              'water_walk_flag in_water under_water swimming can_swim can_fly falling flying charging '
              'on_transport on_vehicle controlled moving motion_type controlled_motion_type spline_id '
              'spline_initialized spline_finalized spline_falling spline_mode spline_cyclic spline_transport '
              'spline_first spline_last spline_current spline_point_count spline_points_omitted spline_points').split()
    for origin, line in rows:
        liquid_event = re.search(r'\bevent=liquid-(surface|motion)\b', line)
        resurrection = 'phase=resurrected ' in line
        charge = 'event=charge-path ' in line
        if not liquid_event and not resurrection and not charge:
            continue
        values = {m[0]: m[1] if m[1] else m[2]
                  for m in re.findall(r"\b(\w+)=(?:'([^']*)'|([^\s]+))", line)}
        if resurrection:
            complete = all(values.get(k) in ('true','false') for k in ('water_walk_aura','water_walk_flag'))
            resurrections.append(dict(origin=origin, guid=values.get('GUID'), complete=complete,
                                      aura=values.get('water_walk_aura'), flag=values.get('water_walk_flag')))
            continue
        if charge:
            try:
                for key in ('GUID','sample_ms','map','instance','spline_id','duration_ms','points','query_nodes','liquid_status'):
                    int(values[key])
                assert int(values['duration_ms'])>0 and int(values['points'])>=2
                for key in ('end_x','end_y','end_z','liquid_level','liquid_depth','ground_z'):
                    assert math.isfinite(float(values[key])),key
                for key in ('ground_valid','water_walk_aura','water_walk_flag'):
                    assert values[key] in ('true','false'),key
                charges.append(dict(origin=origin,values=values))
            except (KeyError, ValueError, AssertionError) as error:
                errors.append(dict(origin=origin,error=str(error) or 'invalid charge record'))
            continue
        missing = sorted(set(fields) - values.keys())
        if missing:
            errors.append(dict(origin=origin, missing=missing))
            continue
        try:
            for key in ('x', 'y', 'z', 'liquid_level', 'liquid_depth', 'surface_delta', 'ground_z', 'ground_delta'):
                assert math.isfinite(float(values[key])), key
            for key in ('water_walk_aura water_walk_flag in_water under_water swimming can_swim can_fly '
                        'falling flying charging on_transport on_vehicle controlled moving '
                        'spline_initialized spline_finalized spline_falling spline_cyclic spline_transport ground_valid').split():
                assert values[key] in ('true', 'false'), key
            count, omitted = int(values['spline_point_count']), int(values['spline_points_omitted'])
            points = []
            for piece in filter(None, values['spline_points'].split(';')):
                index, xyz = piece.split(':')
                point = tuple(map(float, xyz.split(',')))
                assert int(index) == len(points) and len(point) == 3 and all(map(math.isfinite, point))
                points.append(point)
            assert 0 <= omitted <= count and len(points) + omitted == count, 'point counts'
            aura_count = int(values['water_walk_effects'])
            aura_omitted = int(values['water_walk_omitted'])
            aura_rows = list(filter(None, values['water_walk_auras'].split(';')))
            assert 0 <= aura_omitted <= aura_count and len(aura_rows) + aura_omitted == aura_count
            for aura in aura_rows:
                assert len(aura.split(':')) == 4
                list(map(int, aura.split(':')))
            assert (values['water_walk_aura'] == 'true') == (aura_count > 0), 'aura state'
            assert abs(float(values['surface_delta']) - (float(values['z']) - float(values['liquid_level']))) < 0.0001
            surface = values['event'] == 'liquid-surface'
            assert int(values['liquid_status']) != 0
            if surface:
                assert abs(float(values['surface_delta'])) <= 0.151
            else:
                depth = float(values['min_swim_depth'])
                assert math.isfinite(depth) and depth >= 0.1
                assert -(depth+.751) <= float(values['surface_delta']) < -.15
            assert float(values['liquid_level']) - float(values['liquid_depth']) > 2
            current, first, last = (int(values[k]) for k in ('spline_current', 'spline_first', 'spline_last'))
            active = (values['spline_initialized'] == 'true' and values['spline_finalized'] == 'false'
                      and omitted == 0 and 0 <= first <= current < last < count)
            # The capture band overlaps valid swimming. Map/GridMap liquid
            # status uses level-z > 0 for IN_WATER, not this logger's +/-0.15m.
            # Require agreement of queried/cached liquid and actual movement
            # state; keep every surface record, including inconsistent states.
            observed_swimming = (float(values['surface_delta']) < 0
                                 and bool(int(values['liquid_status']) & (4|8))
                                 and bool(int(values['cached_liquid_status']) & (4|8))
                                 and values['in_water']=='true' and values['swimming']=='true')
            category = ('water-walk-aura-present' if aura_count else
                        'water-walk-flag-without-aura' if values['water_walk_flag'] == 'true' else
                        'surface-without-water-walk-permission' if surface and not observed_swimming
                        else 'swimming-without-water-walk-permission')
            native_ground = (active and values['moving'] == 'true' and values['can_swim'] == 'true'
                             and all(values[k] == 'false' for k in
                                     ('can_fly', 'falling', 'flying', 'charging', 'on_transport', 'on_vehicle',
                                      'controlled', 'spline_falling', 'spline_transport', 'in_water', 'under_water', 'swimming')))
            records.append(dict(origin=origin, values=values, points=points, category=category,
                                complete_active_path=active, ordinary_surface_motion=surface and native_ground,
                                observed_swimming=observed_swimming))
        except (KeyError, ValueError, AssertionError) as error:
            errors.append(dict(origin=origin, error=str(error) or 'invalid record'))
    # Positions must be actual samples of the same active spline, never queried
    # detour coordinates or samples on the other side of a map transfer.
    pairs, previous = [], {}
    for record in sorted(records, key=lambda r: int(r['values']['sample_ms'])):
        v = record['values']
        key = (v['GUID'], v['map'], v['instance'], v['spline_id'])
        old = previous.get(key)
        if old and all(r['ordinary_surface_motion'] and r['category'] == 'surface-without-water-walk-permission'
                       for r in (old, record)):
            dt = int(v['sample_ms']) - int(old['values']['sample_ms'])
            distance = math.dist([float(v[k]) for k in ('x', 'y', 'z')],
                                 [float(old['values'][k]) for k in ('x', 'y', 'z')])
            if 0 < dt <= 5000 and distance > 0.5:
                pairs.append(dict(guid=v['GUID'], instance=v['instance'], spline=v['spline_id'],
                                  milliseconds=dt, distance=distance, before=old['origin'], after=record['origin']))
        previous[key] = record
    deep_surface = [r['origin'] for r in records if r['values']['event']=='liquid-surface'
                    and r['values']['ground_valid']=='true' and float(r['values']['ground_delta'])>2
                    and r['values']['water_walk_aura']=='false'
                    and not r['observed_swimming']
                    and all(r['values'][k]=='false' for k in ('flying','falling','charging','on_transport','on_vehicle'))]
    underwater_paths = [r['origin'] for r in records if r['values']['event']=='liquid-motion'
                        and r['values']['spline_initialized']=='true' and int(r['values']['spline_points_omitted'])==0
                        and r['values']['water_walk_aura']=='false' and r['values']['water_walk_flag']=='false'
                        and r['values']['in_water']=='true' and len(r['points'])>=2]
    underwater_charges = [r for r in charges if int(r['values']['liquid_status']) & (4|8)
                          and float(r['values']['end_z']) < float(r['values']['liquid_level'])-.1
                          and r['values']['water_walk_aura']=='false' and r['values']['water_walk_flag']=='false']
    bad_charge_ends = [r for r in charges if int(r['values']['liquid_status'])!=0
                      and abs(float(r['values']['end_z'])-float(r['values']['liquid_level']))<=.15
                      and not (int(r['values']['liquid_status']) & (4|8)
                               and float(r['values']['end_z']) < float(r['values']['liquid_level']))
                      and r['values']['ground_valid']=='true'
                      and float(r['values']['end_z'])-float(r['values']['ground_z'])>2
                      and r['values']['water_walk_aura']=='false']
    return dict(status='incomplete-diagnostics' if errors else 'evidence-captured' if records else 'no-surface-episode',
                samples=len(records), bots=len({r['values']['GUID'] for r in records}),
                events=dict(Counter(r['values']['event'] for r in records)),
                categories=dict(Counter(r['category'] for r in records)),
                complete_active_paths=sum(r['complete_active_path'] for r in records),
                ordinary_surface_motion_samples=sum(r['ordinary_surface_motion'] for r in records),
                unexpected_water_walk_flags=[r['origin'] for r in records if r['category']=='water-walk-flag-without-aura'],
                deep_surface_without_aura=deep_surface, underwater_paths=underwater_paths,
                near_surface_swimming=[r['origin'] for r in records if r['values']['event']=='liquid-surface'
                                       and r['observed_swimming']],
                resurrection_samples=resurrections,
                resurrection_flag_mismatches=[r for r in resurrections if r['complete'] and r['flag']!=r['aura']],
                native_charge_paths=charges, native_underwater_charges=underwater_charges,
                native_charge_surface_without_aura=bad_charge_ends,
                no_aura_motion_pairs=pairs, errors=errors, records=records,
                limitation='Observation only. No samples is missing coverage, not success. Geometric WATER_WALK is not an aura. Inspect actual ground support before treating surface counts as defects. Path origin/Charge success require separate native action evidence.')


def audit_water_fix(review):
    errors = []
    if review['errors']:
        errors.append('Malformed diagnostic records')
    if review['unexpected_water_walk_flags'] or review['resurrection_flag_mismatches']:
        errors.append('Water-walk flag does not match a living player aura')
    if review['deep_surface_without_aura'] or review['native_charge_surface_without_aura']:
        errors.append('Surface position/path without aura or nearby ground support')
    coverage = dict(resurrection=bool(review['resurrection_samples']) and
                    all(r['complete'] for r in review['resurrection_samples']),
                    underwater_path=bool(review['underwater_paths']),
                    native_underwater_charge=bool(review['native_underwater_charges']))
    return dict(status='failed' if errors else 'passed' if all(coverage.values()) else 'coverage-gap',
                errors=errors,coverage=coverage,
                scope='Observed resurrection flags, supported water positions and actual native BG Charge paths; not every navigation route.')


def audit_directory(directory):
    def rows():
        for path in sorted(directory.glob('PlayerbotBG.log*')):
            opener = gzip.open if path.suffix == '.gz' else open
            with opener(path, 'rt', errors='replace') as data:
                for number, line in enumerate(data, 1):
                    yield f'{path.name}:{number}', line
    return audit_liquid(rows())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit_directory(args.logs)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'records'}, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'evidence-captured' else 1


if __name__ == '__main__':
    raise SystemExit(main())
