#!/usr/bin/env python3
"""Exercise the real migration on connection-local copies, never live rows.

Requires MySQL and the project's configured container connection. Temporary
tables are discarded by MySQL at connection close, including on test failure.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'contrib/diagnostics'))
from hunter_pet_recovery import Connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--container', default='loa-mysql')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--baseline', type=Path,
                        help='Pre-migration entry/ench/chance/type TSV; allows replay after the live repair')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    db = Connection(args.config, args.container)
    migration = (ROOT / 'sql/updates/world/2026_11_08_00_restore_random_enchantment_types.sql').read_text()
    plan = [tuple(map(float, r)) for r in re.findall(
        r'^    \((\d+), (\d+), ([\d.]+), ([01]), ([01])\)[,;]$', migration, re.M)]
    assert len(plan) == 84
    select = 'SELECT JSON_ARRAY(entry,ench,chance,type) FROM item_enchantment_template ORDER BY type,entry,ench;'
    live_setup = (f'CREATE TEMPORARY TABLE item_enchantment_template LIKE `{db.world}`.item_enchantment_template;'
                  f'INSERT INTO item_enchantment_template SELECT * FROM `{db.world}`.item_enchantment_template;')
    setup = live_setup
    if args.baseline:
        values = []
        for line in args.baseline.read_text().splitlines():
            entry, ench, chance, kind = line.split('\t')
            entry, ench, chance, kind = int(entry), int(ench), float(chance), int(kind)
            assert 0 <= entry <= 16777215 and 0 <= ench <= 16777215
            assert math.isfinite(chance) and chance >= 0 and kind in (0, 1)
            values.append(f'({entry},{ench},{chance!r},{kind})')
        assert values, 'Empty baseline'
        setup = (f'CREATE TEMPORARY TABLE item_enchantment_template LIKE `{db.world}`.item_enchantment_template;'
                 'INSERT INTO item_enchantment_template (entry,ench,chance,type) VALUES '
                 + ','.join(values) + ';')

    def query(sql):
        return [json.loads(s) for s in db.query(sql).splitlines() if s.startswith('[')]

    def keyed(rows):
        return {(e,n,t): c for e,n,c,t in rows}

    live_before = keyed(query(live_setup + select))
    baseline_rows = query(setup + select)
    baseline = keyed(baseline_rows)
    for e,n,chance,old,new in plan:
        assert (e,n,old) in baseline and abs(baseline[e,n,old]-chance) < .00001
        assert (e,n,new) not in baseline

    scenarios = [
        ('restore', '', 1, set()),
        ('repeat', '', 2, set()),
        ('custom-chance', 'UPDATE item_enchantment_template SET chance=26.61 WHERE entry=460 AND ench=281 AND type=0;', 1, {460}),
        ('destination-collision', 'INSERT INTO item_enchantment_template VALUES (460,281,26.6,1);', 1, {460}),
        ('missing-row', 'DELETE FROM item_enchantment_template WHERE entry=461 AND ench=284 AND type=0;', 1, {461}),
        ('unrelated-custom-row', 'INSERT INTO item_enchantment_template VALUES (460,999999,1,0),(60000,1,1,0);', 1, set()),
        ('partially-correct', 'UPDATE item_enchantment_template SET type=0 WHERE entry=460 AND ench=176 AND type=1;', 1, set()),
    ]
    results = []
    for name, change, repetitions, skipped in scenarios:
        original = keyed(query(setup + change + select))
        expected = dict(original)
        moved = 0
        for e,n,chance,old,new in plan:
            if e in skipped or (e,n,old) not in expected:
                continue
            expected[e,n,new] = expected.pop((e,n,old))
            moved += 1
        actual_rows = query(setup + change + migration * repetitions + select)
        actual = keyed(actual_rows)
        assert actual == expected, f'{name}: unexpected row/value change'
        assert len(actual) == len(original), f'{name}: lost or added rows'
        results.append(dict(scenario=name, passed=True, moved=moved, rows=len(actual), skipped_pools=sorted(skipped)))
        if name == 'restore':
            for filename, rows in [('before.tsv',baseline_rows),('after.tsv',actual_rows)]:
                (args.output/filename).write_text(''.join('\t'.join(map(str,row))+'\n' for row in rows))
    assert keyed(query(live_setup + select)) == live_before, 'Working source table changed during isolated tests'
    (args.output/'migration-regression.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
    print('PASS: exact restoration, reapplication, pool conflict guards and custom-row preservation; live rows unchanged')


if __name__ == '__main__':
    main()
