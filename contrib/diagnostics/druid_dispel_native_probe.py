#!/usr/bin/env python3
"""Build with -j4 and run the bounded native Druid dispel fixture.

Run under a lingering user systemd service; see doc/sanitizer_soak.md.
Uses this workspace's loa-build/loa-mysql containers and private runtime configs.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', type=Path, required=True)
parser.add_argument('--guid', type=int, required=True)
parser.add_argument('--skip-build', action='store_true', help='Use the already-built worldserver; source hash must match build evidence')
args = parser.parse_args()
if args.guid <= 0:
    parser.error('--guid must be positive')
repo = Path(__file__).resolve().parents[2]
run = args.run.resolve()
sys.path.insert(0, str(repo / 'contrib/diagnostics'))
from hunter_pet_recovery import Connection
from playerbot_multilevel_soak import prepare, signal_owned_server, container_path, write_json, digest
from playerbot_action_audit import audit_actions
from sanitizer_soak import stamp, optional_overlay, check_disk_space, disk_space, memory

os.umask(0o077)
run.mkdir(parents=True, exist_ok=False)
runtime = Path('/home/user/wow-mop-build/loa-runtime')
work = runtime.parent
server = inhibitor = None
before = None
stop_requested = False
state = {'status': 'building', 'started': stamp()}


def status(**values):
    state.update(values, updated=stamp())
    write_json(run / 'status.json', state)


def stop(signum, frame):
    global stop_requested
    stop_requested = True


for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, stop)

try:
    status()
    lock = (repo / 'wow_mop_codex_handoff/tests/.playerbot-multilevel.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    db = Connection(runtime / 'worldserver.conf', 'loa-mysql')

    def offline():
        for cmd in (['pgrep', '-x', 'worldserver'], ['podman', 'exec', 'loa-build', 'pgrep', '-x', 'worldserver']):
            if subprocess.run(cmd, capture_output=True).returncode != 1:
                raise RuntimeError('Server exists or process inspection failed')
        if db.query('SELECT guid FROM characters WHERE online<>0;').strip():
            raise RuntimeError('Online characters before probe')

    offline()
    def protected_state():
        return {name: db.query(sql) for name, sql in {
            'character': f'SELECT guid,level,talentTree FROM characters WHERE guid={args.guid};',
            'spells': f'SELECT * FROM character_spell WHERE guid={args.guid} ORDER BY spell;',
            'inventory': f'SELECT * FROM character_inventory WHERE guid={args.guid} ORDER BY item;',
            'pets': f'SELECT id,entry,owner,name,slot FROM character_pet WHERE owner={args.guid} ORDER BY id;',
        }.items()}
    def native_sources():
        return {str(p.relative_to(repo)): digest(p) for pattern in ('src/**/*.cpp', 'src/**/*.h', 'modules/**/*.cpp', 'modules/**/*.h') for p in repo.glob(pattern)}
    frozen = native_sources()
    write_json(run / 'source-sha256.json', frozen)
    for p in (repo / 'modules/mod_playerbots/src').rglob('*'):
        if p.is_file() and p.suffix in ('.cpp', '.h') and (p.name.startswith('Druid') or p.name.startswith('ActionExecutionTrace')):
            dest = run / 'sources' / p.relative_to(repo)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p.read_bytes())
    before = protected_state()
    write_json(run / 'protected-before.json', before)
    check_disk_space(disk_space(run))
    inhibitor = subprocess.Popen(['systemd-inhibit', '--what=sleep:idle:handle-lid-switch', '--mode=block',
                                  '--who=LoA-hunter-attacker-probe', '--why=Native Druid dispel effects check',
                                  'sleep', 'infinity'], start_new_session=True)
    patch = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=repo)
    (run / 'source.patch').write_bytes(patch)
    for name in ('DruidDispelTest.cpp', 'DruidDispelTest.h'):
        (run / name).write_bytes((repo / 'modules/mod_playerbots/src' / name).read_bytes())
    (run / 'source-head.txt').write_bytes(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo))
    if not args.skip_build:
        with (run / 'build.log').open('xb') as output:
            subprocess.run(['podman', 'exec', '--user', '0', 'loa-build', 'cmake', '-S',
                            '/work/Legends-of-Azeroth-Pandaria-5.4.8', '-B', '/work/build-ubuntu2604-openssl35'],
                           check=True, stdout=output, stderr=subprocess.STDOUT)
            subprocess.run(['podman', 'exec', '--user', '0', 'loa-build', 'cmake', '--build',
                            '/work/build-ubuntu2604-openssl35', '--target', 'worldserver', '-j4'],
                           check=True, stdout=output, stderr=subprocess.STDOUT)
    if stop_requested:
        raise RuntimeError('Stop requested during build')
    # Check native changes only; recording test results in docs is harmless.
    (run / 'native.patch').write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'HEAD', '--', 'src', 'modules'], cwd=repo))
    if native_sources() != frozen:
        raise RuntimeError('Native sources changed during build')
    status(build_exit_code=0)
    prepared = run / 'server'
    prepare(SimpleNamespace(run=prepared, runtime=runtime, work_root=work,
                            binary=work / 'build-ubuntu2604-openssl35/src/server/worldserver/worldserver',
                            levels=[60], bots=1, minutes_per_level=8,
                            build_container='loa-build', mysql_container='loa-mysql'))
    stage = prepared / 'level-60-bots-1'
    conf = stage / 'worldserver.conf'
    conf.write_text(optional_overlay(conf.read_text(), {'Console.Enable': '1', 'AiPlayerbot.SpellDiagnostics': '1', 'AiPlayerbot.DruidDispelTestGuid': str(args.guid)}))
    bots = stage / 'playerbots.conf'
    bots.write_text(optional_overlay(bots.read_text(), {'AiPlayerbot.BattlegroundTest': '0', 'AiPlayerbot.DisableRandomLevels': '1', 'AiPlayerbot.RandomBotAutologin': '0', 'AiPlayerbot.RandomBotLoginAtStartup': '0', 'AiPlayerbot.RandomBotJoinBG': '0', 'AiPlayerbot.RandomBotJoinLfg': '0', 'AiPlayerbot.BotAutologin': '0'}))
    manifest = json.loads((prepared / 'manifest.json').read_text())
    subprocess.run(['strip', '--strip-debug', str(prepared / 'bin/worldserver')], check=True)
    manifest['binary_sha256'] = digest(prepared / 'bin/worldserver')
    manifest['build_binary_sha256'] = digest(work / 'build-ubuntu2604-openssl35/src/server/worldserver/worldserver')
    manifest['purpose'] = 'Existing Druid spellbook; hostile temporary aura source; party selector in solo mode (self); native dispel casts, no cooldown/power override'
    manifest['stages'][0]['config_sha256'] = {p.name: digest(p) for p in (conf, bots)}
    write_json(prepared / 'manifest.json', manifest)
    offline()
    binary = container_path(prepared / 'bin/worldserver', work)
    config = container_path(conf, work)
    log = (run / 'console.log').open('xb', buffering=0)
    server = subprocess.Popen(['podman', 'exec', '-i', '--user', '0', '--env', 'LD_PRELOAD=',
                               '--workdir', container_path(stage, work), 'loa-build', binary, '-c', config],
                              stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
    status(status='starting', binary_sha256=manifest['binary_sha256'])
    started = time.monotonic()
    requested = False
    while time.monotonic() - started < 300:
        if stop_requested:
            raise RuntimeError('Stop requested')
        if server.poll() is not None or inhibitor.poll() is not None:
            raise RuntimeError('Server or inhibitor exited early')
        check_disk_space(disk_space(run))
        if memory()['MemAvailable'] < 768 * 1024**2:
            raise RuntimeError('Low available memory')
        console = (run / 'console.log').read_text(errors='replace')
        if not requested and 'World initialized' in console:
            signal_owned_server('loa-build', container_path(stage / 'worldserver.pid', work), binary, config, probe=True)
            server.stdin.write(b'npcbot druiddispel start\n')
            server.stdin.flush()
            requested = True
        full_log = stage / 'Logs/PlayerbotFull.log'
        lines = full_log.read_text(errors='replace').splitlines() if full_log.exists() else []
        rows = [line for line in lines if 'Dispel fixture ' in line]
        (run / 'fixture.log').write_text('\n'.join(rows) + '\n')
        finished = [row for row in rows if 'Dispel fixture finished' in row]
        status(status='observing', fixture=rows)
        if finished:
            if 'passed=true' not in finished[-1] or 'cleanup=done combat=false' not in finished[-1]:
                raise RuntimeError('Native fixture did not pass: ' + finished[-1])
            if any(marker in console for marker in ('AddressSanitizer', 'runtime error:', 'Assertion failed', 'ASSERTION FAILED')):
                raise RuntimeError('Fatal diagnostic')
            status(status='observed', observation_seconds=time.monotonic() - started)
            break
        time.sleep(1)
    else:
        raise RuntimeError('Fixture timeout')
except Exception as error:
    status(status='failed', error=str(error))
finally:
    if server is not None and server.poll() is None:
        try:
            server.stdin.write(b'npcbot druiddispel cleanup\n')
            server.stdin.flush()
            time.sleep(1)
        except BrokenPipeError:
            pass
        signal_owned_server('loa-build', container_path(stage / 'worldserver.pid', work), binary, config)
        server.wait()
        server.stdin.close()
        log.close()
        status(server_exit_code=server.returncode)
        if server.returncode:
            status(status='failed', error='Nonzero server shutdown')
    if inhibitor is not None and inhibitor.poll() is None:
        os.killpg(inhibitor.pid, signal.SIGTERM)
        inhibitor.wait()
    # Preserve the postcondition evidence even when the fixture/coverage fails.
    if before is not None:
        try:
            offline()
            after = protected_state()
            write_json(run / 'protected-after.json', after)
            unchanged = before == after
            status(protected_state_unchanged=unchanged, post_shutdown_online=0)
            if not unchanged:
                raise RuntimeError('Protected character state changed')
        except Exception as error:
            previous = state.get('error')
            status(status='failed', error=f'{previous}; {error}' if previous else str(error))
    if before is not None and native_sources() != frozen:
        status(status='failed', error='Native sources changed during fixture')
    if state['status'] == 'observed':
        try:
            assert not db.query('SELECT guid FROM characters WHERE online<>0;').strip(), 'Stale online characters'
            audit = audit_actions(stage / 'Logs')
            write_json(run / 'action-audit.json', audit)
            status(status='passed', post_shutdown_online=0, unknown_actions=audit['unknown_count'])
        except Exception as error:
            status(status='failed', error=str(error))
    status(ended=stamp())
    write_json(run / 'result.json', state)
raise SystemExit(0 if state['status'] == 'passed' else 1)
