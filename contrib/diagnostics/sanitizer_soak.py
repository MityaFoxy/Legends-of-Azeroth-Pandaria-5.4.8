#!/usr/bin/env python3
"""Build and run an explicitly requested sanitizer soak inside loa-build.

Run as container UID 0. Configurations and database dumps are private runtime
artifacts. With --normal-build, normal binaries are backed up before deployment;
existing configurations are never overwritten.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def memory():
    fields = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        fields[key] = int(value.split()[0]) * 1024
    return fields


def setting(text, key):
    match = re.search(r"^\s*" + re.escape(key) + r"\s*=\s*(.*?)\s*$", text, re.M)
    if not match:
        raise RuntimeError("Missing configuration key: " + key)
    return match.group(1).strip('"')


def overlay(text, changes):
    for key, value in changes.items():
        pattern = r"^\s*" + re.escape(key) + r"\s*=.*$"
        replacement = key + " = " + value
        text, count = re.subn(
            pattern, lambda _, line=replacement: line, text, flags=re.M
        )
        if count != 1:
            raise RuntimeError("Expected exactly one configuration key: " + key)
    return text


def optional_overlay(text, changes):
    for key, value in changes.items():
        if re.search(r"^\s*" + re.escape(key) + r"\s*=", text, re.M):
            text = overlay(text, {key: value})
        else:
            text += "\n" + key + " = " + value + "\n"
    return text


def rss(pid):
    try:
        for line in Path("/proc/%d/status" % pid).read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except FileNotFoundError:
        pass
    return 0


def alive(pid):
    try:
        status = Path("/proc/%d/status" % pid).read_text()
        return not re.search(r"^State:\s+Z", status, re.M)
    except FileNotFoundError:
        return False


def log_size(directory):
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def stop(process):
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Server did not finish graceful shutdown within 120 seconds"
            )


def query_bot_count(mysql_args, env, sql, event, check_resources):
    """Retry only transient connection errors, without hiding resource failures."""
    for attempt in range(1, 4):
        check_resources()
        try:
            result = subprocess.run(
                ["mysql", "--connect-timeout=5", *mysql_args, "-N", "-e", sql],
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                value = result.stdout.strip()
                if not value.isascii() or not value.isdecimal():
                    raise RuntimeError("Invalid bot-count response from MySQL")
                return int(value)
            detail = result.stderr[:8192]
            password = env.get("MYSQL_PWD")
            if password:
                detail = detail.replace(password, "<redacted>")
            transient = bool(
                re.search(r"ERROR\s+(2002|2003|2005|2006|2013|2055)\b", detail)
            )
            event(
                "sql_query_error",
                attempt=attempt,
                exit_code=result.returncode,
                transient=transient,
                stderr=detail,
            )
            if not transient:
                raise RuntimeError("Non-transient MySQL diagnostic query failure")
        except subprocess.TimeoutExpired:
            event("sql_query_timeout", attempt=attempt, timeout_seconds=10)
        check_resources()
        if attempt < 3:
            time.sleep(3)
    raise RuntimeError("MySQL diagnostic query failed after three bounded attempts")


def stop_after_failure(process, event):
    if process is None:
        return None
    event("shutdown_requested", pid=process.pid)
    try:
        stop(process)
    except (RuntimeError, OSError) as error:
        event("shutdown_failed", error=str(error), pid=process.pid)
    result = dict(
        pid=process.pid, exit_code=process.poll(), still_alive=process.poll() is None
    )
    event(
        "shutdown_finished" if not result["still_alive"] else "shutdown_incomplete",
        **result,
    )
    return result


def population_stages(only_bots, soak_duration):
    if only_bots is not None:
        return ((only_bots, soak_duration),)
    return ((25, 300), (50, 300), (100, soak_duration))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path("/work/loa-runtime"))
    parser.add_argument("--build", type=Path, default=Path("/work/build-asan-ubsan"))
    parser.add_argument("--normal-build", type=Path)
    parser.add_argument("--auth-pid", type=int)
    startup = parser.add_mutually_exclusive_group(required=True)
    startup.add_argument("--old-pid", type=int)
    startup.add_argument("--already-stopped", action="store_true")
    parser.add_argument("--hours", type=float, default=12)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--bot-behavior-log", action="store_true")
    parser.add_argument(
        "--min-available-ram-mib",
        type=int,
        default=768,
        help="Stop below this available host RAM (MiB); default: 768",
    )
    parser.add_argument(
        "--only-bots",
        type=int,
        help="Run only this positive bot population (default: 25/50/100 gates)",
    )
    parser.add_argument("--revision", required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    if args.hours <= 0 or args.jobs < 1:
        parser.error("hours and jobs must be positive")
    if args.only_bots is not None and args.only_bots < 1:
        parser.error("bot population must be positive")
    if args.min_available_ram_mib < 256:
        parser.error("available RAM guard must be at least 256 MiB")
    if args.normal_build and not args.auth_pid:
        parser.error("--normal-build requires --auth-pid")
    os.umask(0o077)
    args.run.mkdir(parents=True, exist_ok=False)
    events = (args.run / "events.jsonl").open("a", buffering=1)
    source = Path(__file__).resolve().parents[2]
    git = ["git", "-c", "safe.directory=" + str(source), "-C", str(source)]
    patch = subprocess.check_output([*git, "diff", "HEAD", "--binary"])
    (args.run / "source-changes.patch").write_bytes(patch)
    untracked = (
        subprocess.check_output(
            [*git, "ls-files", "--others", "--exclude-standard", "-z"]
        )
        .decode()
        .split("\0")
    )
    for name in filter(None, untracked):
        destination = args.run / "source-untracked" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, destination)
    for label, build_directory in (
        ("sanitizer", args.build),
        ("mimalloc", args.normal_build),
    ):
        if build_directory:
            shutil.copy2(
                build_directory / "CMakeCache.txt",
                args.run / ("CMakeCache-%s.txt" % label),
            )

    def event(kind, **values):
        record = dict(time=stamp(), event=kind, **values)
        events.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)
        (args.run / "status.json").write_text(json.dumps(record, indent=2) + "\n")
        if kind in ("failed", "complete"):
            (args.run / "result.json").write_text(json.dumps(record, indent=2) + "\n")

    def sample(kind, pid, directory, bots=None):
        mem = memory()
        record = dict(
            pid=pid,
            rss_bytes=rss(pid),
            available_bytes=mem["MemAvailable"],
            swap_free_bytes=mem["SwapFree"],
            disk_free_bytes=shutil.disk_usage(args.run).free,
            log_bytes=log_size(directory),
        )
        if bots is not None:
            record["bots_online"] = bots
        event(kind, **record)
        if mem["MemAvailable"] < args.min_available_ram_mib * 1024**2:
            raise RuntimeError(
                "Less than %d MiB of host RAM available" % args.min_available_ram_mib
            )
        if record["disk_free_bytes"] < 10 * 1024**3:
            raise RuntimeError("Less than 10 GiB of disk space available")
        if record["log_bytes"] > 12 * 1024**3:
            raise RuntimeError("Run logs exceeded the 12 GiB budget")

    world_text = (args.runtime / "worldserver.conf").read_text()
    bot_text = (args.runtime / "playerbots.conf").read_text()
    auth_text = (args.runtime / "authserver.conf").read_text()
    (args.run / "worldserver.original.conf").write_text(world_text)
    (args.run / "playerbots.original.conf").write_text(bot_text)
    (args.run / "authserver.original.conf").write_text(auth_text)
    host, port, user, password, character_db = setting(
        world_text, "CharacterDatabaseInfo"
    ).split(";")
    auth_db = setting(world_text, "LoginDatabaseInfo").split(";")[-1]
    databases = [
        setting(world_text, key).split(";")[-1]
        for key in (
            "LoginDatabaseInfo",
            "CharacterDatabaseInfo",
            "WorldDatabaseInfo",
            "PlayerbotsDatabaseInfo",
        )
    ]
    env = os.environ.copy()
    env["MYSQL_PWD"] = password
    mysql_args = ["-h", host, "-P", port, "-u", user]
    binary = args.build / "src/server/worldserver/worldserver"
    process = None
    build_process = None
    stopped_original = False
    sanitizer_started = False
    try:
        if (
            args.auth_pid
            and Path("/proc/%d/exe" % args.auth_pid).resolve()
            != (args.runtime / "bin/authserver").resolve()
        ):
            raise RuntimeError(
                "Auth PID does not match the expected runtime authserver"
            )
        if args.already_stopped:
            for entry in Path("/proc").iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    name = (entry / "comm").read_text().strip()
                    if name == "worldserver" and alive(int(entry.name)):
                        raise RuntimeError(
                            "worldserver is still running: " + entry.name
                        )
                except FileNotFoundError:
                    pass
            event("original_already_stopped", revision=args.revision)
        else:
            exe = Path("/proc/%d/exe" % args.old_pid).resolve()
            expected = (args.runtime / "bin/worldserver").resolve()
            if exe != expected:
                raise RuntimeError(
                    "Original PID does not match the expected runtime worldserver"
                )
            event("stopping_original", pid=args.old_pid, revision=args.revision)
            os.kill(args.old_pid, signal.SIGTERM)
            deadline = time.monotonic() + 120
            while alive(args.old_pid):
                if time.monotonic() > deadline:
                    raise RuntimeError("Original worldserver did not stop gracefully")
                time.sleep(1)
            stopped_original = True
        shutil.copytree(args.runtime / "Logs", args.run / "logs-before-soak")
        event("backup_started", databases=databases)
        dump_help = subprocess.check_output(["mysqldump", "--help"], text=True)
        dump_options = [
            "--single-transaction",
            "--routines",
            "--events",
            "--triggers",
            "--hex-blob",
        ]
        if "--set-gtid-purged" in dump_help:
            dump_options.append("--set-gtid-purged=OFF")
        if "--column-statistics" in dump_help:
            dump_options.append("--column-statistics=0")
        with (
            (args.run / "databases-before-soak.sql").open("wb") as dump,
            (args.run / "backup.stderr.log").open("wb") as errors,
        ):
            subprocess.run(
                ["mysqldump", *mysql_args, *dump_options, "--databases", *databases],
                env=env,
                stdout=dump,
                stderr=errors,
                check=True,
            )
        dump = args.run / "databases-before-soak.sql"
        if dump.stat().st_size < 1024**2:
            raise RuntimeError("Database dump is unexpectedly small")
        event(
            "backup_complete",
            bytes=dump.stat().st_size,
            sha256=hashlib.file_digest(dump.open("rb"), "sha256").hexdigest(),
        )
        phases = []
        if args.normal_build:
            phases.append(("mimalloc", args.normal_build, 1800))
        phases.append(("sanitizer", args.build, args.hours * 3600))
        for phase, build_directory, soak_duration in phases:
            binary = build_directory / "src/server/worldserver/worldserver"
            with (args.run / ("build-%s.log" % phase)).open("wb") as output:
                build_process = subprocess.Popen(
                    [
                        "cmake",
                        "--build",
                        str(build_directory),
                        "--parallel",
                        str(args.jobs),
                    ],
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                event(
                    "build_started", phase=phase, pid=build_process.pid, jobs=args.jobs
                )
                while build_process.poll() is None:
                    sample("build_sample", build_process.pid, args.run)
                    time.sleep(30)
                if build_process.returncode:
                    raise RuntimeError("%s build failed: inspect its build log" % phase)
            linkage = subprocess.check_output(["ldd", str(binary)], text=True)
            (args.run / ("ldd-%s.txt" % phase)).write_text(linkage)
            if "not found" in linkage or "jemalloc" in linkage:
                raise RuntimeError("Allocator linkage verification failed")
            if phase == "sanitizer" and (
                "libasan" not in linkage or "libubsan" not in linkage
            ):
                raise RuntimeError("Sanitizer linkage verification failed")
            if phase == "mimalloc":
                for name in ("authserver", "worldserver"):
                    built = build_directory / ("src/server/%s/%s" % (name, name))
                    symbols = subprocess.check_output(
                        ["nm", "-g", "--defined-only", str(built)], text=True
                    )
                    if not re.search(r"\bmi_malloc$", symbols, re.M) or not re.search(
                        r"\bmalloc$", symbols, re.M
                    ):
                        raise RuntimeError("mimalloc override missing from " + name)
                    if re.search(r"\bje_(malloc|free)$", symbols, re.M):
                        raise RuntimeError("Legacy jemalloc symbols remain in " + name)
                backup_bin = args.run / "bin-before-mimalloc"
                backup_bin.mkdir()
                for name in ("authserver", "worldserver"):
                    shutil.copy2(args.runtime / "bin" / name, backup_bin / name)
                    shutil.copy2(
                        build_directory / ("src/server/%s/%s" % (name, name)),
                        args.runtime / "bin" / (name + ".mimalloc-new"),
                    )
                os.kill(args.auth_pid, signal.SIGTERM)
                deadline = time.monotonic() + 120
                while alive(args.auth_pid):
                    if time.monotonic() > deadline:
                        raise RuntimeError("Authserver did not stop gracefully")
                    time.sleep(1)
                for name in ("authserver", "worldserver"):
                    os.replace(
                        args.runtime / "bin" / (name + ".mimalloc-new"),
                        args.runtime / "bin" / name,
                    )
                with (args.run / "authserver-mimalloc.log").open("ab") as output:
                    auth_process = subprocess.Popen(
                        [
                            str(args.runtime / "bin/authserver"),
                            "-c",
                            str(args.runtime / "authserver.conf"),
                        ],
                        cwd=args.runtime,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                time.sleep(3)
                if auth_process.poll() is not None:
                    for name in ("authserver", "worldserver"):
                        restored = args.runtime / "bin" / (name + ".restore-old")
                        shutil.copy2(backup_bin / name, restored)
                        os.replace(restored, args.runtime / "bin" / name)
                    with (args.run / "authserver-restored.log").open("ab") as output:
                        restored_auth = subprocess.Popen(
                            [
                                str(args.runtime / "bin/authserver"),
                                "-c",
                                str(args.runtime / "authserver.conf"),
                            ],
                            cwd=args.runtime,
                            stdout=output,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                    event("binaries_restored", auth_pid=restored_auth.pid)
                    raise RuntimeError(
                        "New authserver failed startup; backups retained"
                    )
                event(
                    "mimalloc_deployed",
                    auth_pid=auth_process.pid,
                    backup=str(backup_bin),
                )
            event(
                "build_complete",
                phase=phase,
                binary=str(binary),
                sha256=hashlib.file_digest(binary.open("rb"), "sha256").hexdigest(),
            )
            for target, duration in population_stages(args.only_bots, soak_duration):
                stage = args.run / ("%s-bots-%d" % (phase, target))
                stage.mkdir()
                (stage / "Logs/gm").mkdir(parents=True)
                (stage / "Data").symlink_to(
                    args.runtime / "Data", target_is_directory=True
                )
                if (args.runtime / "lua_scripts").exists():
                    (stage / "lua_scripts").symlink_to(
                        args.runtime / "lua_scripts", target_is_directory=True
                    )
                world_changes = {
                    "DataDir": '"%s"' % (args.runtime / "Data"),
                    "LogsDir": '"Logs"',
                    "Updates.EnableDatabases": "0",
                    "Appender.Console": "1,3,7,13 11 9 5 3 1",
                    "Appender.Server": "2,2,7,Server.log,a,67108864",
                    "Appender.MeleeMovement": "2,2,7,MeleeMovement.log,a,67108864",
                    "Appender.DBErrors": "2,2,7,DBErrors.log,a,67108864",
                }
                stage_world = overlay(world_text, world_changes)
                stage_bot = overlay(
                    bot_text,
                    {
                        "AiPlayerbot.MinRandomBots": str(target),
                        "AiPlayerbot.MaxRandomBots": str(target),
                    },
                )
                if args.bot_behavior_log:
                    stage_world = optional_overlay(
                        stage_world,
                        {
                            "Appender.PlayerbotBehavior": "2,2,7,PlayerbotBehavior.log,a,67108864",
                            "Logger.playerbots.behavior": "2,PlayerbotBehavior",
                        },
                    )
                    stage_bot = optional_overlay(
                        stage_bot,
                        {
                            "AiPlayerbot.LogBehavior": "1",
                            "AiPlayerbot.LogBehaviorInterval": "60",
                        },
                    )
                (stage / "worldserver.conf").write_text(stage_world)
                (stage / "playerbots.conf").write_text(stage_bot)
                server_env = os.environ.copy()
                # Inherited preloads can defeat ASan or accidentally reintroduce an allocator.
                server_env.pop("LD_PRELOAD", None)
                if phase == "mimalloc":
                    server_env["MIMALLOC_VERBOSE"] = "1"
                    server_env["MIMALLOC_SHOW_STATS"] = "1"
                server_env["ASAN_OPTIONS"] = (
                    "halt_on_error=1:detect_leaks=1:quarantine_size_mb=128:"
                    "log_path=%s/Logs/asan" % stage
                )
                server_env["UBSAN_OPTIONS"] = (
                    "print_stacktrace=1:log_path=%s/Logs/ubsan" % stage
                )
                with (stage / "Logs/console.log").open("ab", buffering=0) as output:
                    process = subprocess.Popen(
                        [str(binary), "-c", str(stage / "worldserver.conf")],
                        cwd=stage,
                        env=server_env,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                    sanitizer_started = True
                    event(
                        "stage_started",
                        phase=phase,
                        bots=target,
                        pid=process.pid,
                        hours=duration / 3600,
                    )
                    started = time.monotonic()
                    reached = None
                    behavior_verified = False
                    while reached is None or time.monotonic() - reached < duration:
                        if process.poll() is not None:
                            raise RuntimeError(
                                "Worldserver exited unexpectedly with code %s in stage %s"
                                % (process.returncode, target)
                            )
                        sql = (
                            "SELECT COUNT(*) FROM `%s`.characters c JOIN `%s`.account a ON a.id=c.account "
                            "WHERE c.online=1 AND a.username LIKE 'RNDBOT%%'"
                            % (character_db, auth_db)
                        )

                        def check_query_resources():
                            if process.poll() is not None:
                                raise RuntimeError(
                                    "Worldserver exited during SQL check"
                                )
                            sample("resource_sample", process.pid, args.run)

                        count = query_bot_count(
                            mysql_args, env, sql, event, check_query_resources
                        )
                        sample("stage_sample", process.pid, args.run, count)
                        if (
                            args.bot_behavior_log
                            and reached is not None
                            and not behavior_verified
                            and time.monotonic() - reached >= 120
                        ):
                            behavior_log = stage / "Logs/PlayerbotBehavior.log"
                            if not behavior_log.exists():
                                raise RuntimeError(
                                    "Requested bot behavior log was not created"
                                )
                            with behavior_log.open(errors="replace") as behavior_file:
                                if "Bot=" not in behavior_file.read(65536):
                                    raise RuntimeError(
                                        "Requested bot behavior log has no bot snapshots"
                                    )
                            behavior_verified = True
                            event("behavior_logging_verified", file=str(behavior_log))
                        if count >= target and reached is None:
                            reached = time.monotonic()
                            event(
                                "target_reached",
                                phase=phase,
                                bots=target,
                                pid=process.pid,
                            )
                        if reached is None and time.monotonic() - started > 1200:
                            raise RuntimeError(
                                "Target bot population was not reached within twenty minutes"
                            )
                        time.sleep(30)
                    stop(process)
                event(
                    "stage_finished",
                    phase=phase,
                    bots=target,
                    exit_code=process.returncode,
                )
                if process.returncode:
                    raise RuntimeError("Failure on stage shutdown: inspect logs")
                if phase == "sanitizer":
                    findings = [
                        p
                        for p in (stage / "Logs").iterdir()
                        if p.is_file()
                        and p.name.startswith(("asan.", "ubsan."))
                        and p.stat().st_size
                    ]
                    console = (stage / "Logs/console.log").read_text(errors="replace")
                    if (
                        findings
                        or "runtime error:" in console
                        or "ERROR: AddressSanitizer" in console
                        or "that just lost any reference to the owner" in console
                    ):
                        raise RuntimeError(
                            "Sanitizer or lost-owner findings in stage logs even though exit code was zero"
                        )
        event(
            "complete",
            message=(
                "%d-bot gate completed; worldserver stopped gracefully" % args.only_bots
                if args.only_bots is not None
                else "100-bot overnight interval completed; worldserver stopped gracefully"
            ),
        )
    except BaseException as error:
        event("failure_detected", error=str(error))
        if build_process is not None and build_process.poll() is None:
            os.killpg(build_process.pid, signal.SIGTERM)
            try:
                build_process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                event("build_stop_timeout")
        shutdown = stop_after_failure(process, event)
        # Restore service only when the diagnostic server was never started.
        if stopped_original and not sanitizer_started:
            with (args.run / "fallback-worldserver.log").open("ab") as output:
                fallback = subprocess.Popen(
                    [
                        str(args.runtime / "bin/worldserver"),
                        "-c",
                        str(args.runtime / "worldserver.conf"),
                    ],
                    cwd=args.runtime,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            event(
                "fallback_started",
                pid=fallback.pid,
                reason="Diagnostic preparation failed",
            )
        event("failed", error=str(error), shutdown=shutdown)
        raise


if __name__ == "__main__":
    main()
