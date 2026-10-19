#!/usr/bin/env python3
"""Isolated one-bot quest/travel smoke. No manual database writes or teleport."""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from botlife_sanitizer_soak import ConsoleEvents, write_json
from sanitizer_soak import SanitizerMonitor, memory, optional_overlay, setting, stamp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--config-dir", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("diagnostic", "acquire", "travel", "quest"))
    parser.add_argument("--destination", help='Travel-only target: "mapId x y z"')
    parser.add_argument("--guid", required=True, type=int)
    parser.add_argument("--quest", required=True, type=int)
    parser.add_argument("--binary", type=Path, default=Path("/work/build/src/server/worldserver/worldserver"))
    args = parser.parse_args()
    if not args.run.is_absolute() or args.guid <= 0 or args.quest <= 0:
        parser.error("Require a fresh absolute run path and positive GUID/QuestId")
    if (args.mode == "travel") != bool(args.destination):
        parser.error("--destination is required only for travel mode")
    os.umask(0o077)
    args.run.mkdir(parents=True, exist_ok=False)
    logs = args.run / "Logs"
    (logs / "gm").mkdir(parents=True)
    events = (args.run / "events.jsonl").open("a", buffering=1)
    child = None
    stop = False
    error = None
    observed = None
    progress_seen = False
    turn_in_seen = False
    monitor = SanitizerMonitor(logs)

    def event(kind, **values):
        row = dict(time=stamp(), event=kind, **values)
        events.write(json.dumps(row) + "\n")
        write_json(args.run / "status.json", row)
        print(json.dumps(row), flush=True)
        return row

    def stop_requested(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, stop_requested)
    signal.signal(signal.SIGINT, stop_requested)
    base = (args.config_dir / "worldserver.conf").read_text()
    h, p, u, password, db = setting(base, "CharacterDatabaseInfo").split(";")

    def sql(query):
        result = subprocess.run(["mysql", "--connect-timeout=5", "-h", h, "-P", p, "-u", u,
                                 "-N", "-B", db, "-e", query], env=dict(os.environ, MYSQL_PWD=password),
                                capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise RuntimeError("Read-only SQL check failed (credentials omitted)")
        return result.stdout.strip()

    def online():
        return sql("SELECT guid FROM characters WHERE online=1 ORDER BY guid")

    def quest_state():
        return sql(f"SELECT quest,status FROM character_queststatus WHERE guid={args.guid} AND quest={args.quest}; "
                   f"SELECT quest,active FROM character_queststatus_rewarded WHERE guid={args.guid} AND quest={args.quest}")

    def objectives():
        return sql(f"SELECT objectiveId,amount FROM character_queststatus_objective WHERE guid={args.guid} ORDER BY objectiveId")

    try:
        for proc in Path("/proc").iterdir():
            if proc.name.isdecimal():
                try:
                    if (proc / "comm").read_text().strip() == "worldserver":
                        raise RuntimeError("Another worldserver is running")
                except FileNotFoundError:
                    pass
        if online():
            raise RuntimeError("Characters already online")
        before = quest_state()
        if before and args.mode not in ("travel", "quest"):
            raise RuntimeError("Selected quest already taken or rewarded; choose a different scenario")
        if args.mode == "quest" and before != f"{args.quest}\t3":
            raise RuntimeError("Full-cycle smoke requires the already accepted INCOMPLETE quest")
        character = sql(f"SELECT guid,name,level,map,position_x,position_y,position_z FROM characters WHERE guid={args.guid}")
        if not character:
            raise RuntimeError("Character not found")
        write_json(args.run / "manifest.json", dict(time=stamp(), mode=args.mode, guid=args.guid,
                   quest=args.quest, character=character, quest_before=before, binary=str(args.binary),
                   destination=args.destination, objectives_before=objectives(),
                   backup="No database dump requested; native character saves persist"))
        source = Path(__file__).resolve().parents[2]
        git = ["git", "-c", f"safe.directory={source}", "-C", str(source)]
        (args.run / "revision.txt").write_bytes(subprocess.check_output([*git, "rev-parse", "HEAD"]))
        (args.run / "source-changes.patch").write_bytes(subprocess.check_output([*git, "diff", "HEAD", "--binary"]))
        for name in subprocess.check_output([*git, "ls-files", "--others", "--exclude-standard", "-z"]).decode().split("\0"):
            if name:
                target = args.run / "source-untracked" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / name, target)
        world = optional_overlay(base, {
            "LogsDir": '"Logs"', "DataDir": '"/work/loa-runtime/Data"',
            "WorldServerPort": "8097", "BindIP": '"127.0.0.1"', "Console.Enable": "1",
            "Ra.Enable": "0", "SOAP.Enabled": "0", "Updates.EnableDatabases": "0",
            "Playerbots.Updates.EnableDatabases": "0", "MaxCoreStuckTime": "120",
            "Appender.BotLife": "2,2,7,BotLife.log,a,67108864",
            "Appender.Navigation": "2,2,7,Navigation.log,a,67108864",
            "Logger.playerbots.botlife": "2,BotLife", "Logger.playerbots.navigation": "2,Navigation",
        })
        bots = optional_overlay((args.config_dir / "playerbots.conf").read_text(), {
            "AiPlayerbot.Enabled": "1", "AiPlayerbot.RandomBotAutologin": "0",
            "AiPlayerbot.RandomBotLoginAtStartup": "0", "AiPlayerbot.MinRandomBots": "1",
            "AiPlayerbot.MaxRandomBots": "1", "AiPlayerbot.RandomBotJoinBG": "0",
            "AiPlayerbot.RandomBotAutoJoinBG": "0", "AiPlayerbot.RandomBotJoinLfg": "0",
            "AiPlayerbot.BattlegroundTest": "0", "Playerbots.Updates.EnableDatabases": "0",
        })
        botlife = optional_overlay((source / "modules/mod_botlife/config/botlife.conf.dist").read_text(), {
            "AiPlayerbot.BotLife.Enabled": "1", "AiPlayerbot.BotLife.BotGuids": str(args.guid),
            "AiPlayerbot.BotLife.TravelTest.Enabled": "1" if args.mode == "travel" else "0",
            "AiPlayerbot.BotLife.TravelTest.BotGuid": str(args.guid),
            "AiPlayerbot.BotLife.TravelTest.Destination": json.dumps(args.destination or ""),
            "AiPlayerbot.BotLife.QuestPlan.Enabled": "1" if args.mode == "diagnostic" else "0",
            "AiPlayerbot.BotLife.QuestPlan.BotGuid": str(args.guid),
            "AiPlayerbot.BotLife.QuestPlan.QuestId": str(args.quest),
            "AiPlayerbot.BotLife.QuestAcquire.Enabled": "1" if args.mode == "acquire" else "0",
            "AiPlayerbot.BotLife.QuestAcquire.BotGuid": str(args.guid),
            "AiPlayerbot.BotLife.QuestAcquire.QuestId": str(args.quest),
            "AiPlayerbot.BotLife.QuestRun.Enabled": "1" if args.mode == "quest" else "0",
            "AiPlayerbot.BotLife.QuestRun.BotGuid": str(args.guid),
            "AiPlayerbot.BotLife.QuestRun.QuestId": str(args.quest),
        })
        for name, text in (("worldserver", world), ("playerbots", bots), ("botlife", botlife)):
            (args.run / f"{name}.conf").write_text(text)
        output = (logs / "console.log").open("ab", buffering=0)
        child = subprocess.Popen([str(args.binary), "-c", str(args.run / "worldserver.conf")],
                                 cwd=args.run, stdin=subprocess.PIPE, stdout=output,
                                 stderr=subprocess.STDOUT, text=True, start_new_session=True)
        event("server_started", pid=child.pid)
        reader = ConsoleEvents(logs / "console.log", logs / "BotLife.log")
        login = False
        deadline = time.monotonic() + (1500 if args.mode == "quest" else 600)
        sample_at = 0
        while time.monotonic() < deadline:
            if stop:
                raise RuntimeError("Stop requested")
            if memory()["MemAvailable"] < 2 * 1024**3 or shutil.disk_usage(args.run).free < 10 * 1024**3:
                raise RuntimeError("Resource guard: RAM <2 GiB or disk <10 GiB")
            if sum(f.stat().st_size for f in logs.iterdir() if f.is_file()) > 1024**3:
                raise RuntimeError("Run logs exceeded 1 GiB")
            monitor.check()
            if child.poll() is not None:
                raise RuntimeError(f"Early server exit {child.returncode}")
            console = reader.read_lines(logs / "console.log")
            if not login and "World initialized in " in console:
                child.stdin.write("botlife-test-login\n")
                child.stdin.flush()
                login = True
                event("login_requested", guid=args.guid)
            text = reader.read_lines(logs / "BotLife.log")
            for line in text.splitlines():
                if args.mode == "diagnostic":
                    match = re.search(rf"QuestPlan read-only guid={args.guid} quest={args.quest} .* stage=(\w+) reason=(\w+)", line)
                    if match:
                        observed = line
                        if match.group(1) != "Acquire":
                            raise RuntimeError("Diagnostic did not produce Acquire: " + line)
                elif args.mode == "quest":
                    prefix = f"quest-run guid={args.guid} quest={args.quest} "
                    if prefix not in line:
                        continue
                    if "event=progress " in line:
                        progress_seen = True
                        event("quest_progress", detail=line)
                    if "event=stage stage=TurnIn" in line:
                        turn_in_seen = True
                        event("quest_turn_in", detail=line)
                    if "event=finish " in line:
                        observed = line
                        if "result=completed rewarded=true reason=rewarded" not in line:
                            raise RuntimeError("Quest run failed: " + line)
                        if not progress_seen or not turn_in_seen:
                            raise RuntimeError("Missing objective progress or TurnIn evidence")
                    if "event=cancel " in line:
                        raise RuntimeError("Quest run cancelled: " + line)
                elif args.mode == "travel":
                    if f"travel-test guid={args.guid} event=finish" in line:
                        observed = line
                        if "result=completed failure=None" not in line:
                            raise RuntimeError("Travel failed: " + line)
                    elif f"travel-test guid={args.guid} event=cancel" in line:
                        raise RuntimeError("Travel cancelled: " + line)
                elif f"quest-acquire guid={args.guid} quest={args.quest} event=finish" in line:
                    observed = line
                    if "result=completed accepted=true" not in line:
                        raise RuntimeError("Acquisition failed: " + line)
                elif f"quest-acquire guid={args.guid} quest={args.quest} event=cancel" in line:
                    raise RuntimeError("Acquisition cancelled: " + line)
            if time.monotonic() >= sample_at or observed:
                population = online()
                if population not in ("", str(args.guid)):
                    raise RuntimeError("Unexpected online character")
                event("sample", online=population, observed=observed)
                sample_at = time.monotonic() + 30
                if observed:
                    if population != str(args.guid):
                        raise RuntimeError("Target not online at terminal event")
                    break
            time.sleep(1)
        if not observed:
            raise RuntimeError("Scenario timeout")
    except Exception as exc:
        error = str(exc)
        event("failure", reason=error)
    finally:
        if child and child.poll() is None:
            event("shutdown_requested", pid=child.pid)
            child.send_signal(signal.SIGTERM)
            while child.poll() is None:
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    event("shutdown_waiting", pid=child.pid)
        if child:
            try:
                monitor.check(drain=True)
                after = quest_state()
                if child.returncode != 0 or online():
                    raise RuntimeError("Nonzero exit or remaining online characters")
                if not error:
                    if args.mode in ("diagnostic", "travel") and after != before:
                        raise RuntimeError("Read-only quest state changed")
                    if args.mode == "acquire" and after != f"{args.quest}\t3":
                        raise RuntimeError("Expected persisted INCOMPLETE quest; got " + after)
                    if args.mode == "quest":
                        active = sql(f"SELECT COUNT(*) FROM character_queststatus WHERE guid={args.guid} AND quest={args.quest}")
                        rewarded = sql(f"SELECT COUNT(*) FROM character_queststatus_rewarded WHERE guid={args.guid} AND quest={args.quest}")
                        if active != "0" or rewarded != "1":
                            raise RuntimeError("Quest removal/reward not persisted")
                event("saved_state", quest_after=after, objectives_after=objectives())
            except Exception as exc:
                error = error or str(exc)
        result = event("failed" if error else "complete", reason=error, observed=observed,
                       exit_code=child.returncode if child else None,
                       progress_seen=progress_seen, turn_in_seen=turn_in_seen)
        write_json(args.run / "result.json", result)
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
