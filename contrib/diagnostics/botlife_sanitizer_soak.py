#!/usr/bin/env python3
"""Detached, guarded single-bot BotLife travel + native-AI sanitizer observation.

Run inside loa-build under a host service/inhibitor. Does not deploy binaries,
edit source configs, alter SQL manually, enable BGs or claim a full quest cycle.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from sanitizer_soak import SanitizerMonitor, memory, optional_overlay, rss, setting, stamp


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


class ConsoleEvents:
    """Read readiness and travel from their own appenders, never from SQL alone."""

    SAMPLE_BYTES = 4 * 1024**2

    def __init__(self, path, botlife_path):
        self.path, self.botlife_path = path, botlife_path
        self.cursors = {}
        self.ready = self.travel_started = False
        self.travel_result = None

    def read_lines(self, path):
        try:
            stream = path.open("rb")
        except FileNotFoundError:
            return ""
        with stream:
            stat = os.fstat(stream.fileno())
            identity = (stat.st_dev, stat.st_ino)
            previous, offset, tail = self.cursors.get(path, (None, 0, b""))
            if identity != previous or stat.st_size < offset:
                offset, tail = 0, b""
            stream.seek(offset)
            text = tail + stream.read(self.SAMPLE_BYTES)
            end = text.rfind(b"\n") + 1
            # Keep partial lines bounded, and never join fragments across files.
            self.cursors[path] = (identity, stream.tell(), text[end:][-4096:])
        return text[:end].decode(errors="replace")

    def update(self, guid):
        self.ready |= "World initialized in " in self.read_lines(self.path)
        text = self.read_lines(self.botlife_path)
        self.travel_started |= bool(re.search(rf"BotLife travel-test guid={guid} event=start(?:\s|$)", text))
        for match in re.finditer(rf"BotLife travel-test guid={guid} event=finish result=(\w+)(?:\s|$)", text):
            self.travel_result = match.group(1).lower()

    @property
    def travel_verified(self):
        return self.travel_result == "completed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--build", type=Path, default=Path("/work/build-asan-ubsan"))
    parser.add_argument("--runtime", type=Path, default=Path("/work/loa-runtime"))
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--guid", type=int, default=6)
    parser.add_argument("--destination", default="1 -8218.48 -4293.23 13.6594")
    parser.add_argument("--seconds", type=int, default=3600)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not args.run.is_absolute() or args.guid <= 0 or args.seconds < 60 or not 1 <= args.jobs <= 4:
        parser.error("Require an absolute fresh run directory, positive GUID, >=60 seconds and 1..4 jobs")
    os.umask(0o077)
    args.run.mkdir(parents=True, exist_ok=False)
    logs = args.run / "Logs"
    (logs / "gm").mkdir(parents=True)
    source = Path(__file__).resolve().parents[2]
    stopped = False
    child = None
    building = False
    started = None
    travel_result = None
    observed_seconds = 0
    error = None
    monitor = None
    console = None
    events_file = (args.run / "events.jsonl").open("a", buffering=1)

    def event(kind, **values):
        row = dict(time=stamp(), event=kind, **values)
        events_file.write(json.dumps(row) + "\n")
        write_json(args.run / "status.json", row)
        print(json.dumps(row), flush=True)
        return row

    def signal_stop(signum, _frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, signal_stop)
    signal.signal(signal.SIGINT, signal_stop)

    def guard():
        if stopped:
            raise RuntimeError("Supervisor stop requested")
        if memory()["MemAvailable"] < 2 * 1024**3:
            raise RuntimeError("Less than 2 GiB host RAM available")
        if shutil.disk_usage(args.run).free < 10 * 1024**3:
            raise RuntimeError("Less than 10 GiB disk space available")
        if sum(p.stat().st_size for p in logs.iterdir() if p.is_file()) > 1024**3:
            raise RuntimeError("Run logs exceeded 1 GiB")

    def sample(kind, **extra):
        event(kind, pid=child.pid if child else None,
              rss_bytes=rss(child.pid) if child else 0,
              available_bytes=memory()["MemAvailable"],
              disk_free_bytes=shutil.disk_usage(args.run).free, **extra)

    def wait_child():
        # Never SIGKILL a saving server. Keep supervising a slow graceful stop.
        while child and child.poll() is None:
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                sample("shutdown_waiting")

    def no_server():
        for proc in Path("/proc").iterdir():
            if not proc.name.isdecimal():
                continue
            try:
                if (proc / "comm").read_text().strip() == "worldserver":
                    raise RuntimeError("Another worldserver is running")
            except FileNotFoundError:
                pass

    def sql(query):
        host, port, user, password, database = connection.split(";")
        env = dict(os.environ, MYSQL_PWD=password)
        result = subprocess.run(["mysql", "--connect-timeout=5", "-h", host, "-P", port,
                                 "-u", user, "-N", "-B", database, "-e", query],
                                env=env, text=True, capture_output=True, timeout=15)
        if result.returncode:
            raise RuntimeError("Read-only character DB check failed (credentials omitted)")
        return result.stdout.strip()

    def online():
        return [int(x) for x in sql("SELECT guid FROM characters WHERE online=1 ORDER BY guid").split()]

    lock = (args.build / ".botlife-soak.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        no_server()
        guard()
        base_world = (args.config_dir / "worldserver.conf").read_text()
        base_bot = (args.config_dir / "playerbots.conf").read_text()
        connection = setting(base_world, "CharacterDatabaseInfo")
        if online():
            raise RuntimeError("Characters are already online; refusing to interfere")
        character = sql(f"SELECT guid,name,map,position_x,position_y,position_z FROM characters WHERE guid={args.guid}")
        if not character:
            raise RuntimeError("Configured test character does not exist")
        write_json(args.run / "manifest.json", dict(created=stamp(), guid=args.guid,
                   destination=args.destination, duration_seconds=args.seconds, jobs=args.jobs,
                   workload="one BotLife travel attempt then native AI; no full quest/teleport coverage",
                   initial_character=character, backup="No SQL backup requested; native character saves persist"))
        git = ["git", "-c", f"safe.directory={source}", "-C", str(source)]
        (args.run / "source-changes.patch").write_bytes(subprocess.check_output([*git, "diff", "HEAD", "--binary"]))
        (args.run / "revision.txt").write_bytes(subprocess.check_output([*git, "rev-parse", "HEAD"]))
        for name in subprocess.check_output([*git, "ls-files", "--others", "--exclude-standard", "-z"]).decode().split("\0"):
            if name:
                target = args.run / "source-untracked" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / name, target)
        event("preflight_complete", initial_character=character, seconds=args.seconds, jobs=args.jobs)
        building = True
        with (args.run / "build.log").open("wb", buffering=0) as output:
            for step, command in (
                ("configure", ["cmake", "-S", str(source), "-B", str(args.build),
                               "-DBOTLIFE=1", "-DPLAYERBOTS=1", "-DELUNA=0", "-DALLOCATOR=SYSTEM"]),
                ("build", ["cmake", "--build", str(args.build), "--target", "worldserver", f"-j{args.jobs}"])):
                child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                event("build_started", step=step, pid=child.pid)
                sample_at = 0
                while child.poll() is None:
                    guard()
                    if time.monotonic() >= sample_at:
                        sample("build_sample", step=step)
                        sample_at = time.monotonic() + 30
                    time.sleep(5)
                if child.returncode:
                    raise RuntimeError(f"{step} failed; inspect build.log")
        building = False
        binary = args.build / "src/server/worldserver/worldserver"
        linkage = subprocess.check_output(["ldd", str(binary)], text=True)
        (args.run / "ldd.txt").write_text(linkage)
        if any(x in linkage for x in ("not found", "jemalloc", "mimalloc")) or not all(x in linkage for x in ("libasan", "libubsan")):
            raise RuntimeError("ASan/UBSan linkage verification failed")
        shutil.copy2(args.build / "CMakeCache.txt", args.run / "CMakeCache.txt")
        event("build_complete", binary_sha256=hashlib.file_digest(binary.open("rb"), "sha256").hexdigest())
        no_server()
        if online():
            raise RuntimeError("Characters became online during build; aborting launch")
        world = optional_overlay(base_world, {
            "DataDir": f'"{args.runtime / "Data"}"', "LogsDir": '"Logs"',
            "WorldServerPort": "8097", "BindIP": '"127.0.0.1"', "Console.Enable": "1",
            "Ra.Enable": "0", "SOAP.Enabled": "0", "Updates.EnableDatabases": "0",
            "Playerbots.Updates.EnableDatabases": "0", "MaxCoreStuckTime": "120",
            "Appender.Console": "1,3,7,13 11 9 5 3 1",
            "Appender.Server": "2,2,7,Server.log,a,67108864",
            "Appender.DBErrors": "2,2,7,DBErrors.log,a,67108864",
            "Appender.BotLife": "2,2,7,BotLife.log,a,67108864",
            "Appender.Navigation": "2,2,7,Navigation.log,a,67108864",
            "Appender.Behavior": "2,3,7,Behavior.log,a,67108864",
            "Logger.playerbots.botlife": "3,Console BotLife", "Logger.playerbots.navigation": "2,Navigation",
            "Logger.playerbots.behavior": "3,Behavior",
        })
        bots = optional_overlay(base_bot, {
            "AiPlayerbot.Enabled": "1", "AiPlayerbot.RandomBotAutologin": "0",
            "AiPlayerbot.RandomBotLoginAtStartup": "0", "AiPlayerbot.MinRandomBots": "1",
            "AiPlayerbot.MaxRandomBots": "1", "AiPlayerbot.RandomBotJoinLfg": "0",
            "AiPlayerbot.RandomBotJoinBG": "0", "AiPlayerbot.RandomBotAutoJoinBG": "0",
            "AiPlayerbot.BattlegroundTest": "0", "AiPlayerbot.LogBehavior": "1",
            "AiPlayerbot.LogBehaviorInterval": "60",
            "Playerbots.Updates.EnableDatabases": "0",
        })
        botlife = optional_overlay((source / "modules/mod_botlife/config/botlife.conf.dist").read_text(), {
            "AiPlayerbot.BotLife.Enabled": "1", "AiPlayerbot.BotLife.BotGuids": str(args.guid),
            "AiPlayerbot.BotLife.TravelTest.Enabled": "1", "AiPlayerbot.BotLife.TravelTest.BotGuid": str(args.guid),
            "AiPlayerbot.BotLife.TravelTest.Destination": json.dumps(args.destination),
            "AiPlayerbot.BotLife.QuestPlan.Enabled": "0",
        })
        for name, content in (("worldserver", world), ("playerbots", bots), ("botlife", botlife)):
            (args.run / f"{name}.conf").write_text(content)
        env = dict(os.environ)
        env.pop("LD_PRELOAD", None)
        env["ASAN_OPTIONS"] = f"halt_on_error=1:detect_leaks=1:quarantine_size_mb=128:log_path={logs}/asan"
        env["UBSAN_OPTIONS"] = f"halt_on_error=1:print_stacktrace=1:log_path={logs}/ubsan"
        monitor = SanitizerMonitor(logs)
        output = (logs / "console.log").open("ab", buffering=0)
        child = subprocess.Popen([str(binary), "-c", str(args.run / "worldserver.conf")],
                                 cwd=args.run, env=env, stdin=subprocess.PIPE, stdout=output,
                                 stderr=subprocess.STDOUT, text=True, start_new_session=True)
        event("server_started", pid=child.pid)
        console = ConsoleEvents(logs / "console.log", logs / "BotLife.log")
        deadline = time.monotonic() + 900
        login_sent = False
        sample_at = 0
        while started is None or time.monotonic() - started < args.seconds:
            guard()
            monitor.check()
            console.update(args.guid)
            travel_result = console.travel_result
            if child.poll() is not None:
                raise RuntimeError(f"Server exited early with code {child.returncode}")
            if console.ready and not login_sent:
                child.stdin.write("botlife-test-login\n")
                child.stdin.flush()
                login_sent = True
                event("login_requested", guid=args.guid)
            now = time.monotonic()
            if now >= sample_at:
                guids = online()
                if any(guid != args.guid for guid in guids):
                    raise RuntimeError("Unexpected online character; stopping isolated run")
                if started is None and console.ready and console.travel_started and guids == [args.guid]:
                    started = now
                    event("soak_started", guid=args.guid, duration_seconds=args.seconds,
                          expected_end_unix=time.time() + args.seconds)
                    write_json(args.run / "soak-start.json", dict(time=stamp(), expected_end_unix=time.time() + args.seconds))
                if started is not None and guids != [args.guid]:
                    raise RuntimeError("Test bot left the world before the hour completed")
                sample("runtime_sample", online=guids, measured_seconds=now-started if started else 0,
                       travel_result=travel_result)
                sample_at = now + 30
            if started is None and now > deadline:
                raise RuntimeError("World/bot/travel readiness was not reached within 15 minutes")
            time.sleep(5)
        event("hour_elapsed", measured_seconds=time.monotonic()-started)
    except Exception as exc:
        error = str(exc)
        event("failure_detected", reason=error)
    finally:
        if started is not None:
            observed_seconds = time.monotonic() - started
        if child and child.poll() is None:
            event("shutdown_requested", pid=child.pid, building=building)
            if building:
                os.killpg(child.pid, signal.SIGTERM)
            else:
                child.send_signal(signal.SIGTERM)
            wait_child()
        if monitor is not None:
            try:
                monitor.check(drain=True)
                if console is not None:
                    console.update(args.guid)
                    travel_result = console.travel_result
                if child.returncode != 0:
                    raise RuntimeError(f"Nonzero server exit: {child.returncode}")
                if online():
                    raise RuntimeError("Online character flags remain after shutdown")
            except Exception as exc:
                error = error or str(exc)
        row = event("failed" if error else "complete", reason=error,
                    exit_code=child.returncode if child else None,
                    measured_seconds=observed_seconds,
                    travel_result=travel_result,
                    travel_verified=console.travel_verified if console is not None else False,
                    live_stuck_recovery_verified=False)
        write_json(args.run / "result.json", row)
        fcntl.flock(lock, fcntl.LOCK_UN)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
