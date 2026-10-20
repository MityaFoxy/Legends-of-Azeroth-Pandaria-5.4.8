#!/usr/bin/env python3
"""Isolated, staggered 1–10 bot QuestRun; native saves only, no resets or teleport."""
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

from botlife_sanitizer_soak import ConsoleEvents, write_json
from sanitizer_soak import SanitizerMonitor, memory, optional_overlay, rss, setting, stamp


def parse_assignments(text):
    if len(text) > 219 or not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*(,[1-9][0-9]*:[1-9][0-9]*){0,9}", text):
        raise ValueError("Require 1–10 GUID:QuestId pairs without spaces")
    pairs = [tuple(map(int, token.split(":"))) for token in text.split(",")]
    if len({guid for guid, _ in pairs}) != len(pairs) or any(value > 0xFFFFFFFF for pair in pairs for value in pair):
        raise ValueError("Require unique uint32 GUIDs and uint32 quest IDs")
    return dict(sorted(pairs))


def observe(line, roster, evidence):
    match = re.search(r"quest-run guid=(\d+) quest=(\d+) event=([\w-]+)(?: |$)", line)
    if not match:
        return None
    guid, quest = map(int, match.group(1, 2))
    if roster.get(guid) != quest:
        raise RuntimeError("Unexpected QuestRun participant: " + line)
    row = evidence[guid]
    event = match.group(3)
    if event == "start":
        if row["started"]:
            raise RuntimeError("Repeated single-run start: " + line)
        row["started"] = True
    elif event == "progress":
        row["progress"].append(line)
        if row["resurrections"] and not row["recovering"]:
            row["progress_after_resurrection"].append(line)
    elif event == "death-wait":
        row["recovering"] = True
        row["deaths"] += 1
    elif event == "resurrected":
        row["recovering"] = False
        row["resurrections"] += 1
    elif event == "stage" and "stage=TurnIn" in line:
        row["turn_in"] = True
    elif event in ("finish", "cancel"):
        row["recovering"] = False
        row["terminal"] = line
        row["success"] = (event == "finish" and row["started"] and (row["turn_in_only"] or bool(row["progress"])) and row["turn_in"]
                          and "result=completed rewarded=true reason=rewarded" in line)
    return guid, event


def new_evidence(roster, turn_in_only=False):
    return {guid: dict(quest=quest, started=False, progress=[], turn_in=False, terminal=None, success=False,
                       turn_in_only=turn_in_only,
                       recovering=False, deaths=0, resurrections=0, progress_after_resurrection=[])
            for guid, quest in roster.items()}


def quest_preflight_error(snapshot, turn_in_only=False):
    statuses = ("1",) if turn_in_only else ("", "3")
    if not snapshot["character"] or snapshot["rewarded"] != "0" or snapshot["active"] not in statuses:
        return "require COMPLETE, non-rewarded quest" if turn_in_only else "require untaken or INCOMPLETE, non-rewarded quest"
    return None


def observation_error(roster, evidence, seen_online):
    if seen_online != set(roster):
        return "Not all configured bots observed online"
    if not all(row["started"] for row in evidence.values()):
        return "One or more configured bots did not start QuestRun"
    if any(row["terminal"] and not row["success"] for row in evidence.values()):
        return "One or more quest runs failed; see bots.json"
    return None


def preparation_error(snapshot):
    """Persistent-data preflight only; runtime readiness remains authoritative."""
    slots = set(map(int, snapshot["equipment_slots"].split()))
    if not slots.intersection((15, 17)):
        return "missing equipped weapon; prepare the character before QuestRun"
    if int(snapshot["level"]) >= 10 and not {4, 6}.issubset(slots):
        return "missing chest/leg armor; prepare the character before QuestRun"
    return None


def stop_server(child, event, grace_seconds=180):
    """Bound shutdown of this owned child only; a forced stop is never a pass."""
    if child.poll() is not None:
        return False
    event("shutdown_requested", pid=child.pid)
    child.send_signal(signal.SIGTERM)
    try:
        child.wait(timeout=grace_seconds)
        return False
    except subprocess.TimeoutExpired:
        event("shutdown_forced", pid=child.pid, reason="Graceful shutdown exceeded deadline; saves may be incomplete")
        child.kill()
        child.wait(timeout=30)
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--assignments", required=True)
    parser.add_argument("--duration-seconds", type=int, default=1500)
    parser.add_argument("--post-terminal-seconds", type=int, default=0,
                        help="Observe native AI after all one-shot quests terminate; never restart them")
    parser.add_argument("--full-logging", action="store_true")
    parser.add_argument("--turn-in-only", action="store_true",
                        help="One-bot return test: require a persisted COMPLETE quest; do not require new kill credit")
    parser.add_argument("--observe-only", action="store_true",
                        help="A clean bounded observation may end with unfinished quests")
    parser.add_argument("--prepare-character", action="store_true",
                        help="Explicit one-bot bootstrap: grant missing equipment, preserve existing items and quest")
    parser.add_argument("--expected-character-db", help="Required database-name assertion for explicit preparation")
    parser.add_argument("--binary", type=Path, default=Path("/work/build/src/server/worldserver/worldserver"))
    args = parser.parse_args()
    try:
        roster = parse_assignments(args.assignments)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.run.is_absolute():
        parser.error("Require a fresh absolute run directory")
    if args.prepare_character and (len(roster) != 1 or not args.expected_character_db):
        parser.error("Preparation requires exactly one bot and --expected-character-db")
    if args.turn_in_only and (len(roster) != 1 or args.prepare_character or args.observe_only):
        parser.error("Turn-in-only requires exactly one bot, no preparation and strict reward verification")
    if not 180 <= args.duration_seconds <= 7200 or not 0 <= args.post_terminal_seconds <= 600:
        parser.error("Duration must be 180..7200 seconds, post-terminal observation 0..600 seconds")
    if not args.expected_character_db:
        parser.error("Require --expected-character-db to assert the isolated character database")
    os.umask(0o077)
    args.run.mkdir(parents=True, exist_ok=False)
    logs = args.run / "Logs"
    (logs / "gm").mkdir(parents=True)
    events = (args.run / "events.jsonl").open("a", buffering=1)
    evidence = new_evidence(roster, args.turn_in_only)
    child = None
    error = None
    stop = False
    lock = None
    monitor = SanitizerMonitor(logs)
    base = (args.config_dir / "worldserver.conf").read_text()
    h, port, user, password, db = setting(base, "CharacterDatabaseInfo").split(";")

    def sql(query):
        result = subprocess.run(["mysql", "--connect-timeout=5", "-h", h, "-P", port, "-u", user,
                                 "-N", "-B", db, "-e", query], env=dict(os.environ, MYSQL_PWD=password),
                                capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise RuntimeError("Read-only SQL check failed (credentials omitted)")
        return result.stdout.strip()

    def online():
        return set(map(int, sql("SELECT guid FROM characters WHERE online=1").split()))

    def snapshot(guid, quest):
        return dict(character=sql(f"SELECT guid,name,level,map,position_x,position_y,position_z FROM characters WHERE guid={guid}"),
                    level=sql(f"SELECT level FROM characters WHERE guid={guid}"),
                    progression=sql(f"SELECT level,xp,money,talentTree,activespec FROM characters WHERE guid={guid}"),
                    inventory=sql(f"SELECT bag,slot,item FROM character_inventory WHERE guid={guid} ORDER BY bag,slot"),
                    equipment_slots=sql(f"SELECT slot FROM character_inventory WHERE guid={guid} AND bag=0 AND slot<19 ORDER BY slot"),
                    equipment=sql(f"SELECT ci.slot,ii.itemEntry,ii.durability FROM character_inventory ci JOIN item_instance ii ON ii.guid=ci.item WHERE ci.guid={guid} AND ci.bag=0 AND ci.slot<19 ORDER BY ci.slot"),
                    saved_spells=sql(f"SELECT COUNT(*) FROM character_spell WHERE guid={guid}"),
                    active=sql(f"SELECT status FROM character_queststatus WHERE guid={guid} AND quest={quest}"),
                    rewarded=sql(f"SELECT COUNT(*) FROM character_queststatus_rewarded WHERE guid={guid} AND quest={quest}"),
                    objectives=sql(f"SELECT objectiveId,amount FROM character_queststatus_objective WHERE guid={guid} ORDER BY objectiveId"))

    def event(event_name, **values):
        row = dict(time=stamp(), event=event_name, **values)
        events.write(json.dumps(row) + "\n")
        write_json(args.run / "status.json", row)
        write_json(args.run / "bots.json", evidence)
        print(json.dumps(row), flush=True)
        return row

    def request_stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        lock = (args.run.parent / ".botlife-quest-run.lock").open("a")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for proc in Path("/proc").iterdir():
            if proc.name.isdecimal():
                try:
                    if (proc / "comm").read_text().strip() == "worldserver":
                        raise RuntimeError("Another worldserver is running")
                except FileNotFoundError:
                    pass
        if online():
            raise RuntimeError("Characters already online")
        if args.expected_character_db and db != args.expected_character_db:
            raise RuntimeError("Character database does not match the explicitly expected database")
        before = {guid: snapshot(guid, quest) for guid, quest in roster.items()}
        write_json(args.run / "preflight.json", before)
        for guid, row in before.items():
            if reason := quest_preflight_error(row, args.turn_in_only):
                raise RuntimeError(f"Bot {guid}: {reason}")
            if not args.prepare_character and (reason := preparation_error(row)):
                raise RuntimeError(f"Bot {guid}: {reason}")
        source = Path(__file__).resolve().parents[2]
        git = ["git", "-c", f"safe.directory={source}", "-C", str(source)]
        (args.run / "revision.txt").write_bytes(subprocess.check_output([*git, "rev-parse", "HEAD"]))
        (args.run / "source-changes.patch").write_bytes(subprocess.check_output([*git, "diff", "HEAD", "--binary"]))
        for name in subprocess.check_output([*git, "ls-files", "--others", "--exclude-standard", "-z"]).decode().split("\0"):
            if name and "__pycache__" not in Path(name).parts:
                target = args.run / "source-untracked" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / name, target)
        write_json(args.run / "manifest.json", dict(time=stamp(), assignments=roster, before=before,
                   binary=str(args.binary), login_interval_seconds=30, deadline_seconds=args.duration_seconds,
                   deadline_origin="world-ready", startup_timeout_seconds=1200,
                   post_terminal_seconds=args.post_terminal_seconds, full_logging=args.full_logging,
                   turn_in_only=args.turn_in_only,
                   binary_sha256=hashlib.file_digest(args.binary.open("rb"), "sha256").hexdigest(),
                   observe_only=args.observe_only,
                   prepare_character=args.prepare_character, character_database=db,
                   backup="No database dump requested; native character saves persist"))
        world = optional_overlay(base, {
            "LogsDir": '"Logs"', "DataDir": '"/work/loa-runtime/Data"', "WorldServerPort": "8097",
            "BindIP": '"127.0.0.1"', "Console.Enable": "1", "Ra.Enable": "0", "SOAP.Enabled": "0",
            "Updates.EnableDatabases": "0", "Playerbots.Updates.EnableDatabases": "0", "MaxCoreStuckTime": "120",
            "Appender.BotLife": "2,2,7,BotLife.log,a,67108864", "Appender.Navigation": "2,2,7,Navigation.log,a,67108864",
            "Logger.playerbots.botlife": "2,BotLife", "Logger.playerbots.navigation": "2,Navigation",
        })
        if args.full_logging:
            # Dedicated files retain all emitted task diagnostics. No rotation
            # of the two event-reader files: preserve exact one-shot evidence.
            full = {"Appender.BotLife": "2,1,7,BotLife.log,a,0", "Logger.playerbots.botlife": "1,BotLife",
                    "Appender.Navigation": "2,1,7,Navigation.log,a,67108864", "Logger.playerbots.navigation": "1,Navigation"}
            for name, category in (("Playerbots", "playerbots"), ("Behavior", "playerbots.behavior"),
                                   ("MeleeMovement", "movement.melee"), ("Combat", "entities.unit"),
                                   ("Spells", "spells"), ("Quest", "entities.player.quest"), ("Network", "network")):
                full[f"Appender.{name}"] = f"2,1,7,{name}.log,a,67108864"
                full[f"Logger.{category}"] = f"1,{name}"
            world = optional_overlay(world, full)
        bots = optional_overlay((args.config_dir / "playerbots.conf").read_text(), {
            "AiPlayerbot.Enabled": "1", "AiPlayerbot.RandomBotAutologin": "0", "AiPlayerbot.RandomBotLoginAtStartup": "0",
            "AiPlayerbot.MinRandomBots": str(len(roster)), "AiPlayerbot.MaxRandomBots": str(len(roster)),
            "AiPlayerbot.RandomBotJoinBG": "0", "AiPlayerbot.RandomBotAutoJoinBG": "0",
            "AiPlayerbot.RandomBotJoinLfg": "0", "AiPlayerbot.BattlegroundTest": "0",
            "Playerbots.Updates.EnableDatabases": "0",
        })
        life = optional_overlay((source / "modules/mod_botlife/config/botlife.conf.dist").read_text(), {
            "AiPlayerbot.BotLife.Enabled": "1", "AiPlayerbot.BotLife.BotGuids": '"' + ",".join(map(str, roster)) + '"',
            "AiPlayerbot.BotLife.TravelTest.Enabled": "0", "AiPlayerbot.BotLife.QuestPlan.Enabled": "0",
            "AiPlayerbot.BotLife.QuestAcquire.Enabled": "0", "AiPlayerbot.BotLife.QuestRun.Enabled": "1",
            "AiPlayerbot.BotLife.QuestRun.BotGuid": "0", "AiPlayerbot.BotLife.QuestRun.QuestId": "0",
            "AiPlayerbot.BotLife.QuestRun.Assignments": json.dumps(args.assignments),
            "AiPlayerbot.BotLife.QuestRun.PrepareCharacter": "1" if args.prepare_character else "0",
        })
        for name, text in (("worldserver", world), ("playerbots", bots), ("botlife", life)):
            (args.run / f"{name}.conf").write_text(text)
        output = (logs / "console.log").open("ab", buffering=0)
        child = subprocess.Popen([str(args.binary), "-c", str(args.run / "worldserver.conf")], cwd=args.run,
                                 stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
                                 text=True, start_new_session=True)
        event("server_started", pid=child.pid)
        reader = ConsoleEvents(logs / "console.log", logs / "BotLife.log")
        ready = False
        requested = []
        seen_online = set()
        next_login = sample_at = 0
        all_terminal_at = None
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            if stop:
                raise RuntimeError("Stop requested")
            if memory()["MemAvailable"] < 2 * 1024**3 or shutil.disk_usage(args.run).free < 10 * 1024**3:
                raise RuntimeError("Resource guard: RAM <2 GiB or disk <10 GiB")
            log_bytes = sum(f.stat().st_size for f in logs.rglob("*") if f.is_file())
            if log_bytes > (4 if args.full_logging else 1) * 1024**3:
                raise RuntimeError("Run logs exceeded safety budget")
            monitor.check()
            if child.poll() is not None:
                raise RuntimeError(f"Early server exit {child.returncode}")
            now = time.monotonic()
            console_text = reader.read_lines(logs / "console.log")
            if not ready and "World initialized in " in console_text:
                ready = True
                deadline = now + args.duration_seconds
                event("world_ready", observation_seconds=args.duration_seconds,
                      deadline_epoch=time.time() + args.duration_seconds)
            if ready and len(requested) < len(roster) and now >= next_login:
                guid = list(roster)[len(requested)]
                child.stdin.write("botlife-test-login\n")
                child.stdin.flush()
                requested.append(guid)
                next_login = now + 30
                event("login_requested", guid=guid)
            for line in reader.read_lines(logs / "BotLife.log").splitlines():
                observed = observe(line, roster, evidence)
                if observed:
                    event("quest_event", guid=observed[0], kind=observed[1], detail=line)
            if now >= sample_at:
                population = online()
                if population - set(requested):
                    raise RuntimeError("Unexpected online character")
                seen_online |= population
                event("sample", online=sorted(population), seen_online=sorted(seen_online),
                      rss_bytes=rss(child.pid), available_bytes=memory()["MemAvailable"],
                      disk_free_bytes=shutil.disk_usage(args.run).free, log_bytes=log_bytes)
                sample_at = now + 15
            if len(requested) == len(roster) and all(row["terminal"] for row in evidence.values()):
                if all_terminal_at is None:
                    all_terminal_at = now
                    event("all_quests_terminal", post_terminal_seconds=args.post_terminal_seconds,
                          all_quests_completed=all(row["success"] for row in evidence.values()))
                if now < all_terminal_at + args.post_terminal_seconds:
                    time.sleep(1)
                    continue
                failure = observation_error(roster, evidence, seen_online)
                if failure:
                    raise RuntimeError(failure)
                break
            if (not args.observe_only and ready and len(requested) == len(roster)
                    and now >= next_login + 90 and not all(row["started"] for row in evidence.values())):
                raise RuntimeError("One or more configured bots did not start QuestRun")
            time.sleep(1)
        else:
            if not ready:
                raise RuntimeError("World startup exceeded 1200 seconds")
            if not args.observe_only:
                raise RuntimeError("Quest group scenario timeout")
            failure = observation_error(roster, evidence, seen_online)
            if failure:
                raise RuntimeError(failure)
            event("observation_deadline", all_quests_completed=all(row["success"] for row in evidence.values()))
    except Exception as exc:
        error = str(exc)
        event("failure", reason=error)
    finally:
        if child and child.poll() is None:
            try:
                if stop_server(child, event):
                    error = error or "Forced shutdown; native saves may be incomplete"
            except Exception as exc:
                error = error or "Shutdown failed: " + str(exc)
        if child:
            try:
                monitor.check(drain=True)
                if child.returncode != 0 or online():
                    raise RuntimeError("Nonzero exit or remaining online characters")
                after = {guid: snapshot(guid, quest) for guid, quest in roster.items()}
                for guid, row in after.items():
                    evidence[guid]["saved"] = row
                    if evidence[guid]["success"] and (row["active"] or row["rewarded"] != "1"):
                        error = error or f"Bot {guid}: native reward not persisted"
                event("saved_state", after=after)
            except Exception as exc:
                error = error or str(exc)
        result = event("failed" if error else ("observation_complete" if args.observe_only else "complete"), reason=error,
                       all_quests_completed=all(row["success"] for row in evidence.values()),
                       exit_code=child.returncode if child else None, bots=evidence)
        write_json(args.run / "result.json", result)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
