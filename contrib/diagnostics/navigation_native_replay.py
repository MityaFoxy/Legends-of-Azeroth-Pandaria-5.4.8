#!/usr/bin/env python3
"""Detached -j4 build and read-only native path queries on ordinary BG bots."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

from hunter_pet_recovery import Connection
from playerbot_multilevel_soak import prepare, signal_owned_server, container_path, write_json, digest
from sanitizer_soak import stamp, optional_overlay, check_disk_space, disk_space, memory

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', required=True, type=Path)
parser.add_argument('--planner', action='store_true', help='Also require three validated native planner routes')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
root = args.run.resolve()
runtime = Path('/home/user/wow-mop-build/loa-runtime')
work = runtime.parent
os.umask(0o077)
root.mkdir(parents=True, exist_ok=False)
state = dict(status='preflight', started=stamp())
server = inhibitor = None
before = db = None
stopped = False


def update(**fields):
    state.update(fields, updated=stamp())
    write_json(root/'status.json', state)


def stop(signum, frame):
    global stopped
    stopped = True


def offline():
    for cmd in (['pgrep', '-x', 'worldserver'], ['podman', 'exec', 'loa-build', 'pgrep', '-x', 'worldserver']):
        if subprocess.run(cmd, capture_output=True).returncode != 1:
            raise RuntimeError('Worldserver exists or process inspection failed')
    if int(db.query('SELECT COUNT(*) FROM characters WHERE online<>0;')):
        raise RuntimeError('Characters still online')


def pets():
    sql = '''SELECT JSON_OBJECT('id',id,'owner',owner,'entry',entry,'name',name,
        'slot',slot,'type',PetType,'created_by_spell',CreatedBySpell) FROM character_pet ORDER BY id;'''
    return {str(row['id']): row for row in map(json.loads, db.query(sql).splitlines())}


def sources():
    paths = [*repo.glob('src/**/*.cpp'), *repo.glob('src/**/*.h'),
             *repo.glob('modules/**/*.cpp'), *repo.glob('modules/**/*.h')]
    return {str(p.relative_to(repo)): digest(p) for p in paths}


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    update()
    lock = (repo/'wow_mop_codex_handoff/tests/.playerbot-multilevel.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    db = Connection(runtime/'worldserver.conf', 'loa-mysql')
    offline()
    before = pets()
    write_json(root/'pets-before.json', before)
    check_disk_space(disk_space(root))
    inhibitor = subprocess.Popen(['systemd-inhibit', '--what=sleep:idle:handle-lid-switch', '--mode=block',
        '--who=LoA-native-navigation-replay', '--why=Native BG path replay and graceful cleanup',
        'sleep', 'infinity'], start_new_session=True)
    backup = root/'backup'
    backup.mkdir()
    db.backup(backup)
    frozen = sources()
    write_json(root/'source-sha256.json', frozen)
    (root/'source.patch').write_bytes(subprocess.check_output(['git','diff','--binary','HEAD'], cwd=repo))
    for path in ('modules/mod_playerbots/src/NavigationReplayTest.cpp', 'modules/mod_playerbots/src/NavigationReplayTest.h'):
        (root/Path(path).name).write_bytes((repo/path).read_bytes())
    update(status='building')
    with (root/'build.log').open('xb') as output:
        for command in (
            ['cmake','-S','/work/Legends-of-Azeroth-Pandaria-5.4.8','-B','/work/build-ubuntu2604-openssl35'],
            ['cmake','--build','/work/build-ubuntu2604-openssl35','--target','worldserver','-j4']):
            subprocess.run(['podman','exec','--user','0','loa-build',*command],
                           stdout=output, stderr=subprocess.STDOUT, check=True)
    if stopped or frozen != sources():
        raise RuntimeError('Stop requested or native source changed during build')
    offline()
    prepared = root/'server'
    prepare(SimpleNamespace(run=prepared, runtime=runtime, work_root=work,
        binary=work/'build-ubuntu2604-openssl35/src/server/worldserver/worldserver',
        levels=[80], bots=100, minutes_per_level=10, build_container='loa-build', mysql_container='loa-mysql'))
    stage = prepared/'level-80-bots-100'
    conf = stage/'worldserver.conf'
    conf.write_text(optional_overlay(conf.read_text(), {
        'Console.Enable':'1', 'AiPlayerbot.NavigationReplayTest':'1',
        'AiPlayerbot.NavigationReplayPlanner':'1' if args.planner else '0',
        'Appender.NavigationReplay':'2,2,7,NavigationReplay.log,a,16777216',
        'Logger.movement.path':'2,NavigationReplay',
        'AuctionHouseBot.Seller.Enabled':'0', 'AuctionHouseBot.Buyer.Enabled':'0',
    }))
    manifest = json.loads((prepared/'manifest.json').read_text())
    manifest['purpose'] = 'Ordinary BG entry; native queries with recorded start overrides, no relocation or movement dispatch by fixture'
    manifest['stages'][0]['config_sha256'] = {p.name:digest(p) for p in (conf, stage/'playerbots.conf')}
    write_json(prepared/'manifest.json',manifest)
    binary, config = container_path(prepared/'bin/worldserver',work), container_path(conf,work)
    console_file = (root/'console.log').open('xb', buffering=0)
    server = subprocess.Popen(['podman','exec','-i','--user','0','--env','LD_PRELOAD=',
        '--workdir',container_path(stage,work),'loa-build',binary,'-c',config],
        stdin=subprocess.PIPE, stdout=console_file, stderr=subprocess.STDOUT)
    update(status='waiting-native-bg', build_exit_code=0, binary_sha256=digest(prepared/'bin/worldserver'))
    started, last_query, identified = time.monotonic(), 0, False
    while time.monotonic()-started < 900:
        if stopped or server.poll() is not None or inhibitor.poll() is not None:
            raise RuntimeError('Stopped or native server/inhibitor exited')
        check_disk_space(disk_space(root))
        if memory()['MemAvailable'] < 768*1024**2:
            raise RuntimeError('Low available memory')
        console = (root/'console.log').read_text(errors='replace')
        if any(s in console for s in ('AddressSanitizer','runtime error:','Assertion failed','ASSERTION FAILED')):
            raise RuntimeError('Fatal diagnostic')
        if 'World initialized' in console:
            if not identified:
                signal_owned_server('loa-build',container_path(stage/'worldserver.pid',work),binary,config,probe=True)
                identified = True
            if time.monotonic()-last_query >= 5:
                server.stdin.write(b'npcbot navreplay\n')
                server.stdin.flush()
                last_query = time.monotonic()
        path = stage/'Logs/PlayerbotFull.log'
        text = path.read_text(errors='replace') if path.exists() else ''
        rows = [line for line in text.splitlines() if 'Navigation replay ' in line]
        (root/'replay.log').write_text('\n'.join(rows)+'\n')
        if 'Navigation replay completed cases=3 queries=9 relocated=0 dispatched=0' in text:
            queries = [r for r in rows if 'Navigation replay case=' in r]
            if len(queries) != 9:
                raise RuntimeError('Incomplete or repeated replay')
            if any(' pathType=8 ' not in r or ' reason=invalid-ground-height ' not in r for r in queries):
                raise RuntimeError('Recorded unsupported paths were not rejected as expected')
            if args.planner:
                plans = [r for r in rows if 'Navigation replay planner case=' in r]
                if len(plans) != 3 or any(' valid=true navigation=true ' not in r for r in plans):
                    raise RuntimeError('Native planner routes failed validation; see replay.log')
            update(status='replayed', observed_seconds=time.monotonic()-started)
            break
        time.sleep(1)
    else:
        raise RuntimeError('Native BG replay timeout')
except Exception as error:
    update(status='failed', error=str(error))
finally:
    if server is not None:
        try:
            if server.poll() is None:
                signal_owned_server('loa-build',container_path(stage/'worldserver.pid',work),binary,config)
            code = server.wait(timeout=120)
            update(server_exit_code=code)
            if code:
                raise RuntimeError('Nonzero shutdown')
        except Exception as error:
            update(status='failed', shutdown_error=str(error))
    if inhibitor is not None and inhibitor.poll() is None:
        os.killpg(inhibitor.pid,signal.SIGTERM)
        inhibitor.wait()
    if before is not None:
        try:
            offline()
            after = pets()
            write_json(root/'pets-after.json',after)
            removed = sorted(before.keys()-after.keys())
            changed = [k for k in before.keys() & after.keys() if before[k] != after[k]]
            added = sorted(after.keys()-before.keys())
            write_json(root/'pet-preservation.json',dict(removed=removed,changed=changed,added=added))
            update(online=0,worldserver_absent=True,protected_pets_unchanged=not removed and not changed)
            if removed or changed:
                raise RuntimeError('Protected pets changed')
        except Exception as error:
            update(status='failed',postcondition_error=str(error))
    if state['status']=='replayed':
        unchanged = frozen == sources()
        update(status='passed' if unchanged else 'failed',native_source_unchanged=unchanged,
               scope='Native query reproduction only; not acceptance of repaired movement')
    write_json(root/'result.json',state)
raise SystemExit(0 if state['status']=='passed' else 1)
