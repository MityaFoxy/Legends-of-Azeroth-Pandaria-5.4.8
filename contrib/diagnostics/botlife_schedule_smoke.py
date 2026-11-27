#!/usr/bin/env python3
"""Bounded 1..2 bot scheduler observation on explicitly isolated test databases."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

from botlife_quest_group_smoke import stop_server
from botlife_sanitizer_soak import ConsoleEvents, write_json
from botlife_schedule_observer import ScheduleObserver
from sanitizer_soak import SanitizerMonitor, memory, optional_overlay, setting, stamp


def utc_now():
    # Test child logs use TZ=UTC. Compare at their one-second precision.
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)


def parse_quest_ids(value):
    try:
        ids = sorted(set(int(token) for token in value.split(",")))
    except ValueError:
        raise argparse.ArgumentTypeError("Require comma-separated positive uint32 quest IDs") from None
    if not 1 <= len(ids) <= 32 or not 0 < min(ids) <= max(ids) <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("Require 1..32 positive uint32 quest IDs")
    return ids


def profile_settings(name):
    if name not in ("smoke", "quest-life"):
        raise ValueError("Unknown scheduler observation profile")
    quest_life = name == "quest-life"
    quest_ms = 120000 if quest_life else 30000
    cooldown_ms = 300000 if quest_life else 60000
    profile = dict(min_walks=0 if quest_life else 1, min_leisure=1, min_cooldown_gaps=1,
                   min_desync_seconds=1, max_quest_fraction=0.5,
                   max_outing_active_ms=quest_ms + 2000, max_unobserved_seconds=1,
                   min_native_quest_seconds=1 if quest_life else 0,
                   min_objective_progress_events=1 if quest_life else 0)
    return profile, quest_ms, cooldown_ms


def verify_candidate_roster(text, guids, quest_ids):
    lines = text.splitlines()
    if not lines or lines[0].split("\t")[:7] != ["distance", "guid", "name", "class", "level", "map", "quest"]:
        raise RuntimeError("Unexpected candidate prefilter format")
    try:
        candidates = {(int(row[1]), int(row[6])) for line in lines[1:] if (row := line.split("\t"))}
    except (ValueError, IndexError):
        raise RuntimeError("Malformed candidate prefilter row") from None
    matches = sorted((guid, quest) for guid, quest in candidates if guid in guids and quest in quest_ids)
    if {guid for guid, _ in matches} != set(guids) or {quest for _, quest in matches} != set(quest_ids):
        raise RuntimeError("Full prefilter did not confirm the requested bot/quest roster")
    return [dict(guid=guid, quest_id=quest) for guid, quest in matches]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--guids", required=True)
    quests = parser.add_mutually_exclusive_group(required=True)
    quests.add_argument("--quest-id", type=int)
    quests.add_argument("--quest-ids", type=parse_quest_ids)
    parser.add_argument("--profile", choices=("smoke", "quest-life"), default="smoke")
    parser.add_argument("--seconds", type=int, default=240)
    parser.add_argument("--expected-character-db", required=True)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    guids = sorted(set(map(int, args.guids.split(","))))
    quest_ids = args.quest_ids if args.quest_ids is not None else [args.quest_id]
    if not 1 <= len(guids) <= 2 or min(guids) < 1 or max(guids) > 0xFFFFFFFF or not 0 < min(quest_ids) <= max(quest_ids) <= 0xFFFFFFFF:
        parser.error("Require 1..2 positive uint32 GUIDs and a positive quest id")
    if not 180 <= args.seconds <= 3600 or not args.run.is_absolute():
        parser.error("Require fresh absolute run directory and 180..3600 seconds")
    if args.profile == "quest-life" and args.seconds < 600:
        parser.error("quest-life requires at least 600 seconds for work and cooldown")
    os.umask(0o077)
    args.run.mkdir(parents=True, exist_ok=False)
    logs = args.run / "Logs"
    (logs / "gm").mkdir(parents=True)
    source = Path(__file__).resolve().parents[2]
    base = (args.config_dir / "worldserver.conf").read_text()
    connections = {key: setting(base, key).split(";") for key in
                   ("CharacterDatabaseInfo", "LoginDatabaseInfo", "PlayerbotsDatabaseInfo", "WorldDatabaseInfo")}
    if (connections["CharacterDatabaseInfo"][-1] != args.expected_character_db or
            any("_test_" not in value[-1] for value in connections.values())):
        raise RuntimeError("Require explicitly matching isolated test databases")
    host, port, user, password, database = connections["CharacterDatabaseInfo"]

    def sql(query):
        result = subprocess.run(["mysql", "-h", host, "-P", port, "-u", user, "-N", "-B", database, "-e", query],
                                env=dict(os.environ, MYSQL_PWD=password), capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise RuntimeError("Read-only character query failed (credentials omitted)")
        return result.stdout.strip()

    def online():
        return set(map(int, sql("SELECT guid FROM characters WHERE online=1").split()))

    events = (args.run / "events.jsonl").open("a", buffering=1)

    def event(kind, **values):
        row = dict(time=stamp(), event=kind, **values)
        events.write(json.dumps(row) + "\n")
        write_json(args.run / "status.json", row)
        print(json.dumps(row), flush=True)

    profile, quest_ms, cooldown_ms = profile_settings(args.profile)
    observer = ScheduleObserver(guids, cooldown=cooldown_ms / 1000)
    stop = False

    def request_stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    child = None
    error = None
    observation_end = None
    monitor = SanitizerMonitor(logs)
    lock = (args.run.parent / ".botlife-quest-run.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for proc in Path("/proc").iterdir():
            if proc.name.isdecimal():
                try:
                    if (proc / "comm").read_text().strip() == "worldserver":
                        raise RuntimeError("Another worldserver is running")
                except FileNotFoundError:
                    pass
        if online():
            raise RuntimeError("Characters are already online")
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(("127.0.0.1", 8097)) == 0:
                raise RuntimeError("Test port 8097 is occupied")
        ids = ",".join(map(str, guids))
        before = sql(f"SELECT guid,name,level,map,position_x,position_y,position_z FROM characters WHERE guid IN ({ids}) ORDER BY guid")
        if len(before.splitlines()) != len(guids):
            raise RuntimeError("Missing configured test characters")
        candidates = None
        if args.profile == "quest-life":
            result = subprocess.run([sys.executable, str(source / "contrib/diagnostics/botlife_quest_candidates.py"),
                                     "--config", str(args.config_dir / "worldserver.conf")],
                                    capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError("Full read-only candidate prefilter failed (credentials omitted)")
            (args.run / "candidate-prefilter.tsv").write_text(result.stdout)
            candidates = verify_candidate_roster(result.stdout, guids, quest_ids)
        git = ["git", "-c", f"safe.directory={source}", "-C", str(source)]
        (args.run / "source-changes.patch").write_bytes(subprocess.check_output([*git, "diff", "HEAD", "--binary"]))
        shutil.copy2(Path(__file__).resolve(), args.run / "controller.py")
        shutil.copy2(source / "contrib/diagnostics/botlife_schedule_observer.py", args.run / "observer.py")
        write_json(args.run / "manifest.json", dict(time=stamp(), guids=guids, seconds=args.seconds,
                   character_database=database, world_database=connections["WorldDatabaseInfo"][-1],
                   initial=before, quest_id=quest_ids[0] if len(quest_ids) == 1 else None,
                   quest_ids=quest_ids, profile_name=args.profile, cooldown_seconds=cooldown_ms / 1000,
                   candidate_matches=candidates,
                   acceptance_profile=profile, log_timezone="UTC",
                   binary=str(args.binary), binary_sha256=hashlib.file_digest(args.binary.open("rb"), "sha256").hexdigest(),
                   revision=subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip(),
                   limits="Bounded scheduler smoke; a no-eligible probe is not executed quest work. No forced combat, teleport, equipment grant or quest reset. Native saves persist on test DB."))
        world = optional_overlay(base, {
            "LogsDir": '"Logs"', "DataDir": '"/work/loa-runtime/Data"', "WorldServerPort": "8097",
            "BindIP": '"127.0.0.1"', "Console.Enable": "1", "Ra.Enable": "0", "SOAP.Enabled": "0",
            "Updates.EnableDatabases": "0", "Playerbots.Updates.EnableDatabases": "0",
            "Appender.BotLife": "2,1,7,BotLife.log,a,0", "Logger.playerbots.botlife": "2,BotLife",
            "Appender.Navigation": "2,2,7,Navigation.log,a,67108864", "Logger.playerbots.navigation": "2,Navigation",
        })
        bots = optional_overlay((args.config_dir / "playerbots.conf").read_text(), {
            "AiPlayerbot.Enabled": "1", "AiPlayerbot.RandomBotAutologin": "0", "AiPlayerbot.RandomBotLoginAtStartup": "0",
            "AiPlayerbot.MinRandomBots": str(len(guids)), "AiPlayerbot.MaxRandomBots": str(len(guids)),
            "AiPlayerbot.RandomBotJoinBG": "0", "AiPlayerbot.RandomBotAutoJoinBG": "0",
            "AiPlayerbot.RandomBotJoinLfg": "0", "AiPlayerbot.BattlegroundTest": "0",
        })
        life = optional_overlay((source / "modules/mod_botlife/config/botlife.conf.dist").read_text(), {
            "AiPlayerbot.BotLife.Enabled": "1", "AiPlayerbot.BotLife.BotGuids": json.dumps(args.guids),
            "AiPlayerbot.BotLife.Scheduler.Enabled": "1", "AiPlayerbot.BotLife.Scheduler.QuestIds": json.dumps(",".join(map(str, quest_ids))),
            "AiPlayerbot.BotLife.Scheduler.InitialSpread": "15000", "AiPlayerbot.BotLife.Scheduler.QuestDuration": str(quest_ms),
            "AiPlayerbot.BotLife.Scheduler.OutingDuration": str(quest_ms),
            "AiPlayerbot.BotLife.Scheduler.QuestLimit": "1",
            "AiPlayerbot.BotLife.Scheduler.DurationJitter": "5000", "AiPlayerbot.BotLife.Scheduler.OutingCooldown": str(cooldown_ms),
            "AiPlayerbot.BotLife.Scheduler.LeisureDuration": "30000", "AiPlayerbot.BotLife.Scheduler.Walk.Enabled": "1",
            "AiPlayerbot.BotLife.Scheduler.Walk.Duration": "60000",
        })
        for name, text in (("worldserver", world), ("playerbots", bots), ("botlife", life)):
            (args.run / f"{name}.conf").write_text(text)
        output = (logs / "console.log").open("ab", buffering=0)
        child = subprocess.Popen([str(args.binary), "-c", str(args.run / "worldserver.conf")], cwd=args.run,
                                 stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
                                 text=True, start_new_session=True, env=dict(os.environ, TZ="UTC"))
        event("server_started", pid=child.pid)
        reader = ConsoleEvents(logs / "console.log", logs / "BotLife.log")
        ready = False
        requested = set()
        seen = set()
        deadline = time.monotonic() + 1200
        next_login = sample_at = 0
        observing = False
        while time.monotonic() < deadline:
            now = time.monotonic()
            if stop or child.poll() is not None:
                raise RuntimeError("Stop requested or early server exit")
            if memory()["MemAvailable"] < 2 * 1024**3 or shutil.disk_usage(args.run).free < 10 * 1024**3:
                raise RuntimeError("Resource guard: RAM <2 GiB or disk <10 GiB")
            if sum(f.stat().st_size for f in logs.rglob("*") if f.is_file()) > 512 * 1024**2:
                raise RuntimeError("Logs exceeded 512 MiB")
            monitor.check()
            if "World initialized in " in reader.read_lines(logs / "console.log"):
                ready = True
                event("world_ready")
            if ready and len(requested) < len(guids) and now >= next_login:
                guid = guids[len(requested)]
                child.stdin.write("botlife-test-login\n")
                child.stdin.flush()
                requested.add(guid)
                next_login = now + 30
                event("login_requested", guid=guid)
            for line in reader.read_lines(logs / "BotLife.log").splitlines():
                observer.inspect(line)
            if now >= sample_at:
                population = online()
                observer.population(population, requested)
                seen |= population
                if not observing and population == set(guids):
                    observing = True
                    observer.begin(utc_now())
                    deadline = time.monotonic() + args.seconds
                    event("observation_started", seconds=args.seconds)
                event("sample", online=sorted(population), evidence=observer.summary(utc_now()),
                      desync_samples=observer.desync_samples, desync_seconds=observer.desync_seconds(utc_now()))
                sample_at = now + 15
            time.sleep(1)
        if not observing or seen != set(guids):
            raise RuntimeError("Roster did not come online before startup deadline")
        for line in reader.read_lines(logs / "BotLife.log").splitlines():
            observer.inspect(line)
        observer.population(online(), requested)
        observation_end = utc_now()
        observer.validate(observation_end, profile)
    except Exception as exc:
        error = str(exc)
        event("failure", reason=error)
    finally:
        observation_end = observation_end or utc_now()
        evidence = observer.summary(observation_end)
        if child and child.poll() is None:
            if stop_server(child, event):
                error = error or "Forced shutdown"
        if child:
            try:
                monitor.check(drain=True)
                if child.returncode != 0 or online():
                    error = error or "Nonzero exit or online characters after shutdown"
            except Exception as exc:
                error = error or str(exc)
        write_json(args.run / "result.json", dict(error=error, evidence=evidence,
                   combat_observed=any(row["combat_pauses"] for row in evidence.values()),
                   desync_samples=observer.desync_samples, acceptance_profile=profile,
                   desync_seconds=observer.desync_seconds(observation_end),
                   native_quest_execution_observed=all(row["native_quest_seconds"] > 0 for row in evidence.values()),
                   objective_progress_observed=all(sum(row["objective_progress_events"].values()) > 0 for row in evidence.values()),
                   hour_criterion_closed=False))
        event("finished", error=error)
    if error:
        raise SystemExit(error)


if __name__ == "__main__":
    main()
