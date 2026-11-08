#!/usr/bin/env python3
"""Host-side, supervised native BG validation using an already built server.

Prepare private stage configs, then run --execute in a lingering user systemd
service. The runner holds a sleep inhibitor until shutdown is complete.
No build flags or installed configs are changed.
"""
import argparse
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

from hunter_pet_recovery import Connection
from playerbot_action_audit import audit_actions
from sanitizer_soak import (check_disk_space, compress_rotated_bot_log,
                            disk_space, full_bot_logging_overlay, memory,
                            optional_overlay, stamp)


SERVER_USER = "0"
SERVER_CONTROL_SCRIPT = """import json,os,signal,sys,time
from pathlib import Path
pidfile,binary,config,mode=sys.argv[1:]
for attempt in range(60):
    if Path(pidfile).exists(): break
    time.sleep(1)
else: raise RuntimeError('Server PID file unavailable; inspect manually')
pid=int(Path(pidfile).read_text())
if pid <= 1: raise RuntimeError('Invalid server PID')
cmd=Path('/proc')/str(pid)/'cmdline'
if cmd.exists():
    argv=cmd.read_bytes().split(bytes([0]))
    if argv[0] != binary.encode() or config.encode() not in argv[1:]:
        raise RuntimeError('PID identity mismatch')
    os.kill(pid, 0 if mode == 'probe' else signal.SIGTERM)
    print(json.dumps(dict(pid=pid, uid=os.geteuid(), operation=mode)))
elif mode == 'probe':
    raise RuntimeError('Server exited before control probe')
"""


def signal_owned_server(container, pidfile, binary, config, probe=False):
    # The same UID must launch the server and send its shutdown signal. The
    # image's default user may differ. Signal 0 probes actual permission.
    try:
        return subprocess.run([
            "podman", "exec", "--user", SERVER_USER, container, "python3", "-c",
            SERVER_CONTROL_SCRIPT, str(pidfile), str(binary), str(config),
            "probe" if probe else "stop"], check=True, timeout=70, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("Server control failed: " + error.stderr.strip()) from error


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def digest(path):
    with path.open("rb") as data:
        return hashlib.file_digest(data, "sha256").hexdigest()


def snapshot_binary(source, destination):
    """Prefer a CoW snapshot; retain a real copy on filesystems without reflinks."""
    try:
        subprocess.run([
            "cp", "--reflink=always", "--preserve=mode,timestamps", "--",
            str(source), str(destination),
        ], check=True, capture_output=True)
        return "reflink"
    except (OSError, subprocess.CalledProcessError):
        shutil.copy2(source, destination)
        return "copy"


class LogTail:
    """Bounded reads; finish the open inode before following a rotation."""

    def __init__(self, path):
        self.path = path
        self.file = None
        self.pending = b""

    def sample(self):
        if self.file is None:
            if not self.path.exists():
                return []
            self.file = self.path.open("rb")
        chunk = self.file.read(4 * 1024**2)
        if not chunk and self.path.exists():
            current, opened = self.path.stat(), os.fstat(self.file.fileno())
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                self.file.close()
                self.file = self.path.open("rb")
                chunk = self.file.read(4 * 1024**2)
        rows = (self.pending + chunk).split(b"\n")
        self.pending = rows.pop()[-65536:]
        return [row.decode(errors="replace") for row in rows]

    def close(self):
        if self.file:
            self.file.close()


class BGObservations:
    def __init__(self, level):
        self.level = level
        self.phases = collections.Counter()
        self.readiness = collections.Counter()
        self.actors = collections.defaultdict(set)
        self.levels = collections.Counter()
        self.instances = set()
        self.teams = set()
        self.last_combat = None
        self.max_scores = [0, 0]

    def consume(self, rows, now):
        for row in rows:
            values = dict(re.findall(r"\b(\w+)=([^\s]+)", row))
            if "queue_action" in values:
                self.readiness[values.get("reason", "unknown")] += 1
            if "GUID" not in values or "phase" not in values:
                continue
            phase, guid = values["phase"], values["GUID"]
            self.phases[phase] += 1
            if values.get("map") != "529" or int(values.get("instance", 0)) == 0:
                continue
            level = int(values["level"])
            self.levels[level] += 1
            if level != self.level:
                continue
            self.instances.add(int(values["instance"]))
            self.teams.add(values.get("bg_team"))
            self.actors[phase].add(guid)
            if int(values.get("damage_done", 0)) > 0:
                self.actors["damage"].add(guid)
            if phase == "combat" and values.get("bg_status") == "3":
                self.last_combat = now
            # Entered may precede preparation. Count the later active match,
            # including its objective/combat event when no new entered is sent.
            if values.get("bg_status") == "3" and int(values.get("matches", 0)) >= 2 and int(values.get("completed", 0)) >= 1:
                self.actors["reentered"].add(guid)
            for index, key in enumerate(("score_a", "score_h")):
                self.max_scores[index] = max(self.max_scores[index], int(values.get(key, 0)))

    def ready(self):
        return bool(self.actors["combat"] & self.actors["damage"]) and len(self.teams) == 2

    def summary(self):
        return {"phases": dict(self.phases), "readiness": dict(self.readiness),
                "observed_bg_levels": dict(self.levels), "instances": sorted(self.instances),
                "teams": sorted(t for t in self.teams if t is not None),
                "bots_by_phase": {k: len(v) for k, v in self.actors.items()},
                "max_scores": self.max_scores,
                "full_cycle_observed": bool(self.actors["combat"] & self.actors["damage"]
                                            & self.actors["dead"] & self.actors["resurrected"]
                                            & self.actors["reentered"])}


def container_path(path, root):
    return str(Path("/work") / path.resolve().relative_to(root.resolve()))


def prepare(args):
    args.run.mkdir(parents=True, exist_ok=False)
    (args.run / "bin").mkdir()
    snapshot_method = snapshot_binary(args.binary, args.run / "bin/worldserver")
    world = (args.runtime / "worldserver.conf").read_text()
    bots = (args.runtime / "playerbots.conf").read_text()
    stages = []
    for level in args.levels:
        stage = args.run / f"level-{level}-bots-{args.bots}"
        (stage / "Logs/gm").mkdir(parents=True)
        if (args.runtime / "lua_scripts").exists():
            (stage / "lua_scripts").symlink_to(container_path(args.runtime / "lua_scripts", args.work_root),
                                               target_is_directory=True)
        stage_world = optional_overlay(world, {
            "DataDir": json.dumps(container_path(args.runtime / "Data", args.work_root)),
            "LogsDir": '"Logs"', "PidFile": '"worldserver.pid"',
            "Console.Enable": "0", "Updates.EnableDatabases": "0",
            "AiPlayerbot.PetPersistenceTestGuid": "0", "Battleground.IgnoreFaction": "0",
            "AiPlayerbot.ExecutionDiagnostics": "0",
            "Appender.Console": "1,3,7,13 11 9 5 3 1",
            "Appender.Server": "2,2,7,Server.log,a,67108864",
            "Appender.MeleeMovement": "2,2,7,MeleeMovement.log,a,67108864",
            "Appender.DBErrors": "2,2,7,DBErrors.log,a,67108864",
            "Appender.PlayerbotBG": "2,3,7,PlayerbotBG.log,a,67108864",
            "Logger.playerbots.bgtest": "3,PlayerbotBG",
            "Logger.bg.resurrection": "3,PlayerbotBG",
        })
        stage_bots = optional_overlay(bots, {
            "AiPlayerbot.Enabled": "1", "AiPlayerbot.RandomBotAutologin": "1",
            "AiPlayerbot.RandomBotLoginAtStartup": "1",
            "AiPlayerbot.MinRandomBots": str(args.bots), "AiPlayerbot.MaxRandomBots": str(args.bots),
            "AiPlayerbot.BattlegroundTest": "1", "AiPlayerbot.DisableRandomLevels": "0",
            "AiPlayerbot.RandomBotMinLevel": str(level), "AiPlayerbot.RandomBotMaxLevel": str(level),
            "AiPlayerbot.RandomBotJoinLfg": "0", "AiPlayerbot.RandomBotAutoJoinBG": "0",
        })
        stage_world, stage_bots = full_bot_logging_overlay(stage_world, stage_bots)
        if getattr(args, "rotation_diagnostics", False):
            stage_world = optional_overlay(stage_world, {
                "Console.Enable": "1", "AiPlayerbot.SpellDiagnostics": "1",
                "AiPlayerbot.EquipmentDiagnostics": "1",
                "AiPlayerbot.ExecutionDiagnostics": "1",
            })
        if getattr(args, "liquid_diagnostics", False):
            stage_world = optional_overlay(stage_world, {
                "Appender.PlayerbotBG": "2,2,7,PlayerbotBG.log,a,67108864",
                "Logger.movement.charge": "2,PlayerbotBG",
            })
        (stage / "worldserver.conf").write_text(stage_world)
        (stage / "playerbots.conf").write_text(stage_bots)
        stages.append({"level": level, "directory": stage.name,
                       "seconds": args.minutes_per_level * 60,
                       "config_sha256": {name: digest(stage / name) for name in
                                         ("worldserver.conf", "playerbots.conf")}})
    write_json(args.run / "manifest.json", {
        "created": stamp(), "binary_sha256": digest(args.run / "bin/worldserver"),
        "binary_snapshot": snapshot_method,
        "source_binary": str(args.binary), "bots": args.bots, "stages": stages,
        "build_container": args.build_container, "mysql_container": args.mysql_container,
        "work_root": str(args.work_root), "runtime": str(args.runtime),
        "startup_timeout_seconds": 1800, "sanitizer_run": False,
    })
    print("Prepared " + str(args.run), flush=True)


def execute(args):
    manifest = json.loads((args.run / "manifest.json").read_text())
    for key in ("runtime", "work_root", "build_container", "mysql_container"):
        if str(getattr(args, key)) != manifest[key]:
            raise RuntimeError("Prepared/run option mismatch: " + key)
    if (args.run / "result.json").exists() or (args.run / "events.jsonl").exists():
        raise RuntimeError("Run already started; prepare a new artifact directory")
    binary = args.run / "bin/worldserver"
    if digest(binary) != manifest["binary_sha256"]:
        raise RuntimeError("Prepared binary changed")
    db = Connection(args.runtime / "worldserver.conf", args.mysql_container)
    stop_requested = False
    inhibitor = None
    process = None
    stage = None
    results = []
    state = {"started": stamp(), "status": "starting", "stages": results}

    def event(kind, **fields):
        entry = {"time": stamp(), "event": kind, **fields}
        with (args.run / "events.jsonl").open("a") as out:
            out.write(json.dumps(entry) + "\n")
        print(json.dumps(entry), flush=True)

    def request_stop(signum, frame):
        nonlocal stop_requested
        stop_requested = True

    def inspect_console(rows):
        for line in rows:
            if any(marker in line for marker in
                   ("runtime error:", "AddressSanitizer", "Assertion failed",
                    "ASSERTION FAILED", "that just lost any reference to the owner")):
                raise RuntimeError("Fatal diagnostic in console.log")

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, request_stop)

    def resources():
        if inhibitor is not None and inhibitor.poll() is not None:
            raise RuntimeError("Sleep inhibitor exited unexpectedly")
        record = disk_space(args.run)
        record["available_bytes"] = memory()["MemAvailable"]
        record["artifact_bytes"] = sum(p.stat().st_size for p in args.run.rglob("*")
                                       if p.is_file() and not p.is_symlink())
        check_disk_space(record)
        if record["available_bytes"] < 768 * 1024**2:
            raise RuntimeError("Available RAM below 768 MiB")
        if record["artifact_bytes"] > 12 * 1024**3:
            raise RuntimeError("Artifacts exceed 12 GiB")
        return record

    def graceful_stop():
        if process is None or process.poll() is not None:
            return
        state["status"] = "stopping"
        write_json(args.run / "status.json", state)
        # Signal the actual server, not podman exec or other worldservers.
        # Verify both binary and private config before using the PID file.
        signal_owned_server(args.build_container,
                            container_path(stage / "worldserver.pid", args.work_root),
                            container_path(binary, args.work_root),
                            container_path(stage / "worldserver.conf", args.work_root))
        event("shutdown_requested", stage=stage.name)
        while process.poll() is None:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                event("shutdown_waiting", stage=stage.name)
        event("server_stopped", stage=stage.name, exit_code=process.returncode)

    try:
        for command in (["pgrep", "-x", "worldserver"],
                        ["podman", "exec", args.build_container, "pgrep", "-x", "worldserver"]):
            if subprocess.run(command, capture_output=True).returncode != 1:
                raise RuntimeError("worldserver already running or status unavailable")
        if int(db.query("SELECT COUNT(*) FROM characters WHERE online<>0;").strip()):
            raise RuntimeError("Characters already marked online; inspect before starting")
        inhibitor = subprocess.Popen([
            "systemd-inhibit", "--what=sleep:idle:handle-lid-switch", "--mode=block",
            "--who=LoA-playerbot-hour", "--why=Autonomous native BG behavior test",
            "sleep", "infinity"], start_new_session=True)
        time.sleep(0.5)
        event("preflight_passed", resources=resources(), binary_sha256=manifest["binary_sha256"])
        for spec in manifest["stages"]:
            if stop_requested:
                raise RuntimeError("Stop requested")
            stage = args.run / spec["directory"]
            for name, wanted in spec["config_sha256"].items():
                if digest(stage / name) != wanted:
                    raise RuntimeError("Prepared config changed: " + name)
            observation = BGObservations(spec["level"])
            bg = LogTail(stage / "Logs/PlayerbotBG.log")
            console = LogTail(stage / "Logs/console.log")
            started = time.monotonic()
            reached = None
            dip = None
            control_verified = False
            last_diagnostic = 0
            result = {"level": spec["level"], "started": stamp(), "status": "starting"}
            results.append(result)
            with (stage / "Logs/console.log").open("xb", buffering=0) as output:
                process = subprocess.Popen([
                    "podman", "exec", "--user", SERVER_USER, "--env", "LD_PRELOAD=",
                    "--workdir", container_path(stage, args.work_root), args.build_container,
                    container_path(binary, args.work_root), "-c",
                    container_path(stage / "worldserver.conf", args.work_root)],
                    stdin=subprocess.PIPE if getattr(args, "rotation_diagnostics", False) else None,
                    stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                event("stage_started", level=spec["level"], pid=process.pid)
                try:
                    while True:
                        if stop_requested:
                            raise RuntimeError("Stop requested")
                        if process.poll() is not None:
                            raise RuntimeError("Unexpected server exit: " + str(process.returncode))
                        if not control_verified and (stage / "worldserver.pid").exists():
                            signal_owned_server(args.build_container,
                                                container_path(stage / "worldserver.pid", args.work_root),
                                                container_path(binary, args.work_root),
                                                container_path(stage / "worldserver.conf", args.work_root), probe=True)
                            control_verified = True
                            event("server_control_verified", level=spec["level"], user=SERVER_USER)
                        now = time.monotonic()
                        observation.consume(bg.sample(), now)
                        inspect_console(console.sample())
                        count = int(db.query(f"SELECT COUNT(*) FROM characters c JOIN `{db.auth}`.account a "
                                             "ON a.id=c.account WHERE c.online=1 AND a.username REGEXP '^RNDBOT[0-9]+$';").strip())
                        if getattr(args, "rotation_diagnostics", False) and count >= manifest["bots"] and now - last_diagnostic >= 60:
                            # Console-only, read-only diagnostics. No casting,
                            # spell grants, equipment changes or AI pauses.
                            rows = db.query(f"SELECT c.guid,c.class FROM characters c JOIN `{db.auth}`.account a "
                                            "ON a.id=c.account WHERE c.online=1 AND a.username REGEXP '^RNDBOT[0-9]+$' "
                                            "AND c.class IN (1,2,3) ORDER BY c.guid;")
                            for row in rows.splitlines():
                                guid, bot_class = map(int, row.split())
                                commands = ([f"npcbot spellcheck {guid} {spell}" for spell in (883,136,982,1130,1978,3674)]
                                            if bot_class == 3 else [f"npcbot equipmentcheck {guid}"])
                                for command in commands:
                                    process.stdin.write((command + "\n").encode())
                            process.stdin.flush()
                            last_diagnostic = now
                            event("read_only_diagnostics", level=spec["level"])
                        usage = resources()
                        compress_rotated_bot_log(args.run)
                        if reached is None:
                            if control_verified and count >= manifest["bots"] and observation.ready():
                                reached = now
                                result.update(status="measuring", measuring_started=stamp())
                                event("measurement_started", level=spec["level"], online=count)
                            elif now - started > manifest["startup_timeout_seconds"]:
                                raise RuntimeError("Population/native BG combat readiness timed out")
                        else:
                            dip = (dip or now) if count < manifest["bots"] else None
                            if dip is not None and now - dip >= 120:
                                raise RuntimeError("Bot population below target for two minutes")
                            if now - observation.last_combat >= 900:
                                raise RuntimeError("No native BG combat observed for fifteen minutes")
                        elapsed = max(0, now - reached) if reached is not None else 0
                        result.update(online=count, measured_seconds=round(elapsed, 1), bg=observation.summary())
                        state.update(status=result["status"], current_level=spec["level"], updated=stamp(), resources=usage)
                        write_json(args.run / "status.json", state)
                        event("sample", level=spec["level"], online=count, measured_seconds=round(elapsed, 1),
                              bg=result["bg"], resources=usage)
                        if elapsed >= spec["seconds"]:
                            break
                        time.sleep(15)
                finally:
                    graceful_stop()
                    try:
                        while rows := bg.sample():
                            observation.consume(rows, time.monotonic())
                        while rows := console.sample():
                            inspect_console(rows)
                        result.update(bg=observation.summary(), exit_code=process.returncode, ended=stamp())
                    finally:
                        bg.close()
                        console.close()
            if process.returncode != 0:
                raise RuntimeError("Server shutdown failed: " + str(process.returncode))
            result["workload_status"] = "passed"
            state.update(status="auditing", current_level=spec["level"], updated=stamp())
            write_json(args.run / "status.json", state)
            result["action_resolution"] = audit_actions(stage / "Logs")
            result["status"] = "passed" if result["action_resolution"]["passed"] else "failed"
            write_json(stage / "result.json", result)
            event("stage_" + result["status"], level=spec["level"], result=result)
            # A structural AI defect must fail acceptance, but collect the other
            # level brackets too. Fatal/resource failures still stop immediately.
        passed = all(result["status"] == "passed" for result in results)
        state.update(status="passed" if passed else "failed", ended=stamp())
        if not passed:
            state["error"] = "Action resolution failed: UNKNOWN actions or missing decision TRACE; inspect stages"
    except Exception as error:
        # No retry, forced victory, load reduction or SIGKILL on failure.
        if results and results[-1]["status"] != "passed":
            results[-1].update(status="failed", error=str(error))
        state.update(status="failed", error=str(error), ended=stamp())
        event("failed", error=str(error))
    finally:
        try:
            graceful_stop()
        except Exception as error:
            state.update(status="failed", shutdown_error=str(error))
        if inhibitor is not None and inhibitor.poll() is None:
            try:
                os.killpg(inhibitor.pid, signal.SIGTERM)
                inhibitor.wait(timeout=10)
            except ProcessLookupError:
                pass  # It can exit between poll() and killpg(). Still save the result.
            except Exception as error:
                state.update(status="failed", inhibitor_cleanup_error=str(error))
        write_json(args.run / "status.json", state)
        write_json(args.run / "result.json", state)
        report = [f"Playerbot multi-level BG run: {state['status']}",
                  "Normal build; no full-server ASan/UBSan claim.",
                  "Each passed stage requires the manifest duration after native combat and population readiness.",
                  "Each passed stage also requires decision TRACE and no UNKNOWN Actions in any retained rotation.",
                  "Action resolution does not establish spell correctness or complete class rotation coverage.",
                  "Match completion/reentry are reported separately; they are not implied by a passed timed stage."]
        for result in results:
            report.append(json.dumps(result, ensure_ascii=False))
        if "error" in state:
            report.append("Failure: " + state["error"])
        (args.run / "report.txt").write_text("\n\n".join(report) + "\n")
        event("finished", status=state["status"])
    return 0 if state["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, default=Path("/home/user/wow-mop-build/loa-runtime"))
    parser.add_argument("--binary", type=Path, default=Path("/home/user/wow-mop-build/build-ubuntu2604-openssl35/src/server/worldserver/worldserver"))
    parser.add_argument("--work-root", type=Path, default=Path("/home/user/wow-mop-build"))
    parser.add_argument("--build-container", default="loa-build")
    parser.add_argument("--mysql-container", default="loa-mysql")
    parser.add_argument("--levels", type=int, nargs="+", default=[60, 80, 90])
    parser.add_argument("--bots", type=int, default=100)
    parser.add_argument("--minutes-per-level", type=int, default=20)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--rotation-diagnostics", action="store_true",
                        help="Sample native Hunter spellbooks and Protection candidates through read-only console probes")
    args = parser.parse_args()
    os.umask(0o077)
    args.run = args.run.resolve()
    if any(level < 55 or level > 90 for level in args.levels) or len(set(args.levels)) != len(args.levels):
        parser.error("Use distinct levels 55..90 (the native Death Knight floor is 55)")
    if args.bots < 16 or args.minutes_per_level < 1:
        parser.error("At least 16 bots and a positive duration are required")
    if not args.execute:
        prepare(args)
        return 0
    with (args.run.parent / ".playerbot-multilevel.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
