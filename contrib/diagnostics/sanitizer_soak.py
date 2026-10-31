#!/usr/bin/env python3
"""Build and run an explicitly requested sanitizer soak inside loa-build.

Run as container UID 0. Configurations and database dumps are private runtime
artifacts. With --normal-build, normal binaries are backed up before deployment;
existing configurations are never overwritten.
"""

import argparse
import datetime
import errno
import fcntl
import gzip
import hashlib
import json
import os
import re
import shutil
import signal
import struct
import subprocess
import time
import uuid
from pathlib import Path


BG_CYCLE_TIMEOUT_SECONDS = 60 * 60


class NavigationCaptured(Exception):
    def __init__(self, finding):
        super().__init__("Captured BG path-start-mismatch")
        self.finding = finding


class NavigationStopMonitor:
    """Follow this stage's console; ignore unrelated warnings and other maps."""

    CHUNK_BYTES = 64 * 1024
    SAMPLE_BYTES = 4 * 1024**2
    MAX_LINE_BYTES = 64 * 1024
    ANSI = re.compile(rb"\x1b\[[0-9;]*m")

    def __init__(self, logs, required=1, on_finding=None):
        if not 1 <= required <= 100:
            raise ValueError("navigation error count must be between 1 and 100")
        self.required = required
        self.on_finding = on_finding
        self.findings = []
        self.seen = set()
        self.pending_states = {}
        self.path = logs / "console.log"
        self.identity = None
        self.offset = 0
        self.pending = b""
        self.discarding = False

    def check(self):
        try:
            console = self.path.open("rb")
        except FileNotFoundError:
            return
        with console:
            stat = os.fstat(console.fileno())
            identity = (stat.st_dev, stat.st_ino)
            if identity != self.identity or stat.st_size < self.offset:
                self.identity, self.offset = identity, 0
                self.pending, self.discarding = b"", False
            end = min(stat.st_size, self.offset + self.SAMPLE_BYTES)
            console.seek(self.offset)
            while self.offset < end:
                chunk = console.read(min(self.CHUNK_BYTES, end - self.offset))
                if not chunk:
                    break
                self.offset = console.tell()
                for piece in chunk.splitlines(keepends=True):
                    if len(self.pending) + len(piece) > self.MAX_LINE_BYTES:
                        self.discarding = True
                        self.pending = b""
                    if not self.discarding:
                        self.pending += piece
                    if piece.endswith(b"\n"):
                        if not self.discarding:
                            self.inspect(self.pending)
                        self.pending, self.discarding = b"", False

    def inspect(self, raw):
        line = self.ANSI.sub(b"", raw).decode(errors="replace").strip()
        if "[playerbots.navigation]" not in line:
            return
        fields = dict(re.findall(r"\b(\w+)=([^\s]+)", line))
        if fields.get("map") != "529" or not fields.get("bot", "").isdigit():
            return
        if (fields.get("outcome") == "start-mismatch-state"
                or (fields.get("outcome") == "rejected" and fields.get("reason") == "path-start-mismatch")):
            # State and rejection are one throttled event with the same bot,
            # instance and second. Also ignore replayed lines after rotation.
            stamp = line.split("[playerbots.navigation]", 1)[0].strip()
            key = (stamp, fields["bot"], fields.get("instance"))
            actor = (fields["bot"], fields.get("instance"))
            if fields.get("outcome") == "start-mismatch-state":
                self.pending_states[actor] = stamp
            else:
                previous = self.pending_states.pop(actor, None)
                paired = previous == stamp
                if previous and not paired:
                    try:
                        # These two adjacent log calls can straddle a second.
                        before = datetime.datetime.fromisoformat(previous.split()[0].replace("_", "T"))
                        after = datetime.datetime.fromisoformat(stamp.split()[0].replace("_", "T"))
                        paired = 0 <= (after - before).total_seconds() <= 1
                    except ValueError:
                        pass
                if paired:
                    self.seen.add(key)
                    return
            if key in self.seen:
                return
            self.seen.add(key)
            finding = dict(reason="path-start-mismatch", source=str(self.path),
                           bot=int(fields["bot"]), map=529,
                           instance=fields.get("instance"), line=line)
            self.findings.append(finding)
            if self.on_finding:
                self.on_finding(finding, self.findings)
            if len(self.findings) >= self.required:
                raise NavigationCaptured(dict(finding, captured_count=len(self.findings),
                                              required_count=self.required, findings=list(self.findings)))


def navigation_capture_overlay(text):
    # Navigation DEBUG can have a separate file appender. Retain it, but make
    # sure the stop monitor also receives the warning/state pair on console.
    try:
        value = setting(text, "Logger.playerbots.navigation")
    except RuntimeError:
        # This logger can inherit its parent in an existing runtime config.
        value = "3,Console Server"
    level, appenders = value.split(",", 1)
    names = appenders.split()
    if "Console" not in names:
        names.append("Console")
    if int(level) > 3 or int(level) == 0:
        level = "3"
    return optional_overlay(text, {"Logger.playerbots.navigation": level + "," + " ".join(names)})


class SanitizerMonitor:
    """Follow console diagnostics in bounded chunks, including partial writes."""

    CHUNK_BYTES = 64 * 1024
    SAMPLE_BYTES = 4 * 1024**2
    MARKERS = (b"runtime error:", b"ERROR: AddressSanitizer",
               b"ERROR: LeakSanitizer", b"AddressSanitizer:DEADLYSIGNAL",
               b"SUMMARY: AddressSanitizer", b"SUMMARY: UndefinedBehaviorSanitizer",
               b"that just lost any reference to the owner")

    def __init__(self, logs):
        self.logs = logs
        self.identity = None
        self.offset = 0
        self.tail = b""

    def check(self, drain=False):
        for path in self.logs.iterdir():
            if path.is_file() and path.name.startswith(("asan.", "ubsan.")) and path.stat().st_size:
                raise RuntimeError("Sanitizer report appeared: " + path.name)
        try:
            console = (self.logs / "console.log").open("rb")
        except FileNotFoundError:
            return
        with console:
            stat = os.fstat(console.fileno())
            identity = (stat.st_dev, stat.st_ino)
            if identity != self.identity or stat.st_size < self.offset:
                self.identity = identity
                self.offset = 0
                self.tail = b""
            # Bound live work as well as memory. Final shutdown drains the
            # snapshot in the same small chunks, never read_text() of a huge log.
            end = stat.st_size if drain else min(stat.st_size, self.offset + self.SAMPLE_BYTES)
            console.seek(self.offset)
            overlap = max(map(len, self.MARKERS)) - 1
            while self.offset < end:
                chunk = console.read(min(self.CHUNK_BYTES, end - self.offset))
                if not chunk:
                    break
                self.offset = console.tell()
                text = self.tail + chunk
                if any(marker in text for marker in self.MARKERS):
                    raise RuntimeError("Sanitizer or lost-owner finding in console.log")
                self.tail = text[-overlap:]


def check_bg_cycle_deadline(now, population_reached, verified):
    if (not verified and population_reached is not None
            and now - population_reached > BG_CYCLE_TIMEOUT_SECONDS):
        raise RuntimeError("Native BG fight/death/resurrection/completion/reentry cycle was not verified within 60 minutes")


def requires_bg_cycle(battleground_test, skip_gate):
    return battleground_test and not skip_gate


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def memory():
    fields = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        fields[key] = int(value.split()[0]) * 1024
    return fields


def disk_space(path, sysfs=Path("/sys/fs/btrfs")):
    """Read the backing filesystem, including Btrfs metadata reservations.

    Linux BTRFS_IOC_FS_INFO / BTRFS_IOC_DEV_INFO use the fixed UAPI layouts
    from linux/btrfs.h. These read-only ioctls also work in rootless containers.
    Do not count the global reserve twice: it is included in bytes_may_use.
    """
    record = {"disk_free_bytes": shutil.disk_usage(path).free}
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        info = bytearray(1024)
        try:
            fcntl.ioctl(fd, 0x8400941f, info, True)  # BTRFS_IOC_FS_INFO
        except OSError as error:
            if error.errno == errno.ENOTTY:
                return record  # Other filesystems retain the statfs guard.
            raise
        fsid = str(uuid.UUID(bytes=bytes(info[16:32])))
        root = sysfs / fsid
        metadata = root / "allocation/metadata"
        counters = {name: int((metadata / name).read_text()) for name in (
            "total_bytes", "bytes_used", "bytes_reserved", "bytes_pinned",
            "bytes_may_use", "bytes_readonly")}
        zone = metadata / "bytes_zone_unusable"
        counters["bytes_zone_unusable"] = int(zone.read_text()) if zone.exists() else 0
        headroom = max(0, counters["total_bytes"] - sum(
            value for name, value in counters.items() if name != "total_bytes"))
        devices = []
        for device in (root / "devinfo").iterdir():
            dev = bytearray(4096)
            struct.pack_into("=Q", dev, 0, int(device.name))
            fcntl.ioctl(fd, 0xd000941e, dev, True)  # BTRFS_IOC_DEV_INFO
            used, total = struct.unpack_from("=QQ", dev, 24)
            devices.append(max(0, total - used))
        if not devices:
            raise RuntimeError("Btrfs device allocation counters are unavailable")
        record.update(btrfs_fsid=fsid, btrfs_metadata=counters,
                      btrfs_metadata_headroom_bytes=headroom,
                      btrfs_min_device_unallocated_bytes=min(devices))
        return record
    finally:
        os.close(fd)


def check_disk_space(record):
    if record["disk_free_bytes"] < 10 * 1024**3:
        raise RuntimeError("Less than 10 GiB of disk space available")
    # Conservative diagnostic policy, not a guarantee against every ENOSPC:
    # leave metadata headroom OR room on every device for new metadata chunks.
    if ("btrfs_fsid" in record
            and record["btrfs_metadata_headroom_bytes"] < 256 * 1024**2
            and record["btrfs_min_device_unallocated_bytes"] < 2 * 1024**3):
        raise RuntimeError("Btrfs metadata headroom below 256 MiB and device "
                           "unallocated space below 2 GiB; refusing disk pressure")


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


def navigation_diagnostics_overlay(text, enabled):
    if not enabled:
        return text
    # Isolated stage only; keep verbose path/spline traces out of Server.log.
    return optional_overlay(text, {
        "Appender.PlayerbotNavigation": "2,2,7,PlayerbotNavigation.log,a,67108864",
        "Logger.playerbots.navigation": "2,PlayerbotNavigation",
    })


def full_bot_logging_overlay(world, bots):
    world = optional_overlay(world, {
        "Appender.PlayerbotFull": "2,1,7,PlayerbotFull.log,a,67108864",
        # Console remains INFO-filtered and feeds the live lost-owner guard.
        "Logger.playerbots": "1,PlayerbotFull Console",
        "Appender.PlayerbotBehavior": "2,1,7,PlayerbotBehavior.log,a,67108864",
        "Logger.playerbots.behavior": "1,PlayerbotBehavior",
    })
    bots = optional_overlay(bots, {
        "AiPlayerbot.LogBehavior": "1",
        "AiPlayerbot.LogBehaviorInterval": "5",
        "AiPlayerbot.LogInGroupOnly": "0",
    })
    return navigation_diagnostics_overlay(world, True), bots


def compress_rotated_bot_log(directory, now=None):
    """Compress at most one closed rotation, preserving all logged decisions."""
    now = time.time() if now is None else now
    for path in sorted(directory.glob("*-bots-*/Logs/Playerbot*.log.*")):
        if (path.is_symlink() or not path.is_file()
                or not re.fullmatch(r"Playerbot\w*\.log\.\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", path.name)):
            continue
        before = path.stat()
        if now - before.st_mtime < 60:
            continue
        archive = path.with_name(path.name + ".gz")
        temporary = path.with_name(path.name + ".gz.tmp")
        if archive.exists() or temporary.exists():
            continue
        digest = hashlib.sha256()
        try:
            with path.open("rb") as source, temporary.open("xb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1) as target:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        target.write(chunk)
                raw.flush()
                os.fsync(raw.fileno())
            with gzip.open(temporary, "rb") as check:
                actual = hashlib.file_digest(check, "sha256").digest()
            after = path.stat()
            if (actual != digest.digest() or (before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_ino, after.st_size, after.st_mtime_ns)):
                raise RuntimeError("Rotated bot log changed during compression: " + str(path))
            size = temporary.stat().st_size
            temporary.rename(archive)
            path.unlink()
            return dict(file=str(archive), original_bytes=before.st_size, compressed_bytes=size)
        finally:
            temporary.unlink(missing_ok=True)
    return None


def alive(pid):
    try:
        status = Path("/proc/%d/status" % pid).read_text()
        return not re.search(r"^State:\s+Z", status, re.M)
    except FileNotFoundError:
        return False


def initial_population_ready(count, target, console):
    # A crash leaves characters.online set until the next server clears it.
    # Only trust initial SQL population after THIS stage initialized its world.
    if count < target or not console.exists():
        return False
    with console.open(errors="replace") as log:
        return any("World initialized in " in line for line in log)


def log_size(directory):
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def stop(process, event=None):
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            # A sanitizer build can spend more than two minutes saving and
            # logging out a large bot population. Keep supervising the same
            # graceful stop: a second SIGTERM terminates worldserver instead
            # of telling us whether its first shutdown would have completed.
            while process.poll() is None:
                if event:
                    event("shutdown_waiting", pid=process.pid, still_alive=True,
                          rss_bytes=rss(process.pid),
                          available_bytes=memory()["MemAvailable"])
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    continue


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
        stop(process, event)
    except (RuntimeError, OSError) as error:
        event("shutdown_failed", error=str(error), pid=process.pid)
    # A startup or slow save can outlive the graceful-stop deadline. Never
    # abandon this child (and release the host inhibitor) while it is alive.
    # Do not escalate to SIGKILL: preserve normal database cleanup semantics.
    while process.poll() is None:
        event("shutdown_waiting", pid=process.pid, still_alive=True,
              rss_bytes=rss(process.pid), available_bytes=memory()["MemAvailable"])
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            continue
    result = dict(
        pid=process.pid, exit_code=process.poll(), still_alive=process.poll() is None
    )
    event(
        "shutdown_finished" if not result["still_alive"] else "shutdown_incomplete",
        **result,
    )
    return result


def guarded_pause(seconds, check_resources):
    """Keep resource guards responsive between the slower SQL/BG samples."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(min(5, max(0, deadline - time.monotonic())))
        check_resources()


def finish_navigation_capture(run, finding, process, sanitizer_monitor, event):
    (run / "navigation-finding.json").write_text(json.dumps(finding, indent=2) + "\n")
    event("navigation_error_captured", **finding)
    shutdown = stop_after_failure(process, event)
    try:
        if shutdown["exit_code"]:
            raise RuntimeError("Failure on captured-error shutdown: inspect logs")
        sanitizer_monitor.check(drain=True)
    except BaseException as error:
        event("failed", error=str(error), shutdown=shutdown, navigation_finding=finding)
        raise
    event("complete", message="Navigation error captured; worldserver stopped gracefully",
          stop_reason="navigation_error_captured", error_reproduced=True,
          navigation_finding=finding, shutdown=shutdown)


def population_stages(only_bots, soak_duration):
    if only_bots is not None:
        return ((only_bots, soak_duration),)
    return ((25, 300), (50, 300), (100, soak_duration))


def backup_databases(run, mysql_args, env, databases, event, skip=False):
    if skip:
        event("backup_skipped", reason="Explicit --skip-db-backup waiver; Git does not back up databases")
        return
    event("backup_started", databases=databases)
    dump_help = subprocess.check_output(["mysqldump", "--help"], text=True)
    options = ["--single-transaction", "--routines", "--events", "--triggers", "--hex-blob"]
    if "--set-gtid-purged" in dump_help:
        options.append("--set-gtid-purged=OFF")
    if "--column-statistics" in dump_help:
        options.append("--column-statistics=0")
    path = run / "databases-before-soak.sql"
    with path.open("wb") as dump, (run / "backup.stderr.log").open("wb") as errors:
        subprocess.run(["mysqldump", *mysql_args, *options, "--databases", *databases],
                       env=env, stdout=dump, stderr=errors, check=True)
    if path.stat().st_size < 1024**2:
        raise RuntimeError("Database dump is unexpectedly small")
    with path.open("rb") as dump:
        digest = hashlib.file_digest(dump, "sha256").hexdigest()
    event("backup_complete", bytes=path.stat().st_size, sha256=digest)


class BattlegroundTelemetry:
    """Read the rotating BG log incrementally; never scan an unbounded log in RAM."""

    def __init__(self):
        self.identity = None
        self.offset = 0
        self.pending = ""
        self.phases = {}
        self.fought = set()
        self.died = set()
        self.resurrected = set()
        self.reentered = set()
        self.damaged = set()
        self.latest = {}

    def sample(self, path):
        if not path.exists():
            return self.summary()
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity != self.identity or stat.st_size < self.offset:
            self.offset = 0
            self.pending = ""
            self.identity = identity
        with path.open("rb") as log:
            log.seek(self.offset)
            chunk = log.read(4 * 1024**2)
            self.offset = log.tell()
        text = self.pending + chunk.decode(errors="replace")
        rows = text.split("\n")
        self.pending = rows.pop()[-8192:]
        for row in rows:
            match = re.search(r"\bGUID=(\d+) phase=([\w-]+)\b", row)
            if not match:
                continue
            guid, phase = match.groups()
            self.latest[guid] = phase
            self.phases[phase] = self.phases.get(phase, 0) + 1
            if phase == "combat":
                self.fought.add(guid)
            if phase == "dead":
                self.died.add(guid)
            if phase == "resurrected":
                self.resurrected.add(guid)
            damage = re.search(r"\bdamage_done=(\d+)\b", row)
            if damage and int(damage[1]) > 0:
                self.damaged.add(guid)
            matches = re.search(r"\bmatches=(\d+) completed=(\d+)\b", row)
            if phase == "entered" and matches and int(matches[1]) >= 2 and int(matches[2]) >= 1:
                self.reentered.add(guid)
        return self.summary()

    def summary(self):
        return dict(phases=dict(self.phases), combat_bots=len(self.fought),
                    dead_bots=len(self.died), resurrected_bots=len(self.resurrected),
                    reentered_bots=len(self.reentered),
                    damage_bots=len(self.damaged),
                    current_phases={phase: list(self.latest.values()).count(phase)
                                    for phase in set(self.latest.values())},
                    cycle_verified=bool(self.fought & self.died & self.resurrected & self.reentered & self.damaged))


class WorkloadGuard:
    """Fail a degraded workload; do not silently count an idle/underfilled server."""

    def __init__(self, target):
        self.target = target
        self.dip = None
        self.last_combat = None
        self.last_completion = None
        self.combat_records = 0
        self.completed_records = 0

    def check(self, now, count, bg_state=None):
        if count < self.target:
            if self.dip is None:
                self.dip = now
            if now - self.dip >= 120:
                raise RuntimeError("Bot population stayed below target for two minutes")
        else:
            self.dip = None
        if bg_state is None:
            return
        combat = bg_state["phases"].get("combat", 0)
        completed = bg_state["phases"].get("completed", 0)
        if self.last_combat is None or combat > self.combat_records:
            self.last_combat = now
        if self.last_completion is None or completed > self.completed_records:
            self.last_completion = now
        self.combat_records = combat
        self.completed_records = completed
        if now - self.last_combat >= 900:
            raise RuntimeError("BG workload has had no observed combat for fifteen minutes")
        if now - self.last_completion >= 5400:
            raise RuntimeError("BG workload has had no observed completed match for ninety minutes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path("/work/loa-runtime"))
    parser.add_argument("--build", type=Path, default=Path("/work/build-asan-ubsan"))
    parser.add_argument("--normal-build", type=Path)
    parser.add_argument("--auth-pid", type=int)
    startup = parser.add_mutually_exclusive_group(required=True)
    startup.add_argument("--old-pid", type=int)
    startup.add_argument("--already-stopped", action="store_true")
    ending = parser.add_mutually_exclusive_group()
    ending.add_argument("--hours", type=float)
    ending.add_argument("--until-navigation-error", choices=("path-start-mismatch",),
                        help="Observe native AB until the requested matching error count, then stop gracefully; no timed soak")
    parser.add_argument("--navigation-error-count", type=int, default=1,
                        help="Distinct path-start-mismatch events required before stopping (1..100, default 1)")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--bot-behavior-log", action="store_true")
    parser.add_argument("--full-bot-log", action="store_true",
                        help="All emitted bot TRACE messages, every AI decision, 5-second state snapshots and navigation DEBUG; losslessly compress closed rotations")
    parser.add_argument("--navigation-debug-log", action="store_true",
                        help="Isolated rotating DEBUG path/query/spline log; counts against the normal log budget")
    parser.add_argument("--skip-db-backup", action="store_true",
                        help="Explicitly waive the normally required new SQL backup")
    parser.add_argument("--battleground-test", action="store_true",
                        help="Native AB workload; require fight/death/completion/reentry within 60 minutes before timed soak")
    parser.add_argument("--skip-bg-cycle-gate", action="store_true",
                        help="Observation run only: collect native BG telemetry without waiting for a full match/reentry cycle")
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
    if args.full_bot_log:
        args.bot_behavior_log = True
        args.navigation_debug_log = True
    if not 1 <= args.navigation_error_count <= 100 or (args.navigation_error_count != 1 and not args.until_navigation_error):
        parser.error("--navigation-error-count requires event mode and a count between 1 and 100")
    if args.hours is None and not args.until_navigation_error:
        args.hours = 12
    if (args.hours is not None and args.hours <= 0) or args.jobs < 1:
        parser.error("hours and jobs must be positive")
    if args.only_bots is not None and args.only_bots < 1:
        parser.error("bot population must be positive")
    if args.min_available_ram_mib < 256:
        parser.error("available RAM guard must be at least 256 MiB")
    if args.normal_build and not args.auth_pid:
        parser.error("--normal-build requires --auth-pid")
    if args.skip_bg_cycle_gate and not args.battleground_test:
        parser.error("--skip-bg-cycle-gate requires --battleground-test")
    if args.until_navigation_error and (not args.battleground_test or args.only_bots is None or args.normal_build):
        parser.error("--until-navigation-error requires --battleground-test --only-bots and a sanitizer-only run")
    # Fail before creating artifacts, dumping databases or starting a server.
    check_disk_space(disk_space(args.runtime))
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
        if args.full_bot_log:
            compressed = compress_rotated_bot_log(directory)
            if compressed:
                event("bot_log_compressed", **compressed)
        mem = memory()
        record = dict(
            pid=pid,
            rss_bytes=rss(pid),
            available_bytes=mem["MemAvailable"],
            swap_free_bytes=mem["SwapFree"],
            log_bytes=log_size(directory),
            **disk_space(args.run),
        )
        if bots is not None:
            record["bots_online"] = bots
        event(kind, **record)
        if mem["MemAvailable"] < args.min_available_ram_mib * 1024**2:
            raise RuntimeError(
                "Less than %d MiB of host RAM available" % args.min_available_ram_mib
            )
        check_disk_space(record)
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
        backup_databases(args.run, mysql_args, env, databases, event, args.skip_db_backup)
        phases = []
        if args.normal_build:
            phases.append(("mimalloc", args.normal_build, 1800))
        phases.append(("sanitizer", args.build, args.hours * 3600 if args.hours is not None else None))
        for phase, build_directory, soak_duration in phases:
            binary = build_directory / "src/server/worldserver/worldserver"
            with (args.run / ("build-%s.log" % phase)).open("wb") as output:
                # Module sources are globbed at configure time. Reconfigure so new
                # controller files cannot be silently omitted from a cached build.
                for step, command in (
                    ("configure", ["cmake", "-S", str(source), "-B", str(build_directory)]),
                    ("build", ["cmake", "--build", str(build_directory), "--parallel", str(args.jobs)]),
                ):
                    sample("build_preflight", os.getpid(), args.run)
                    build_process = subprocess.Popen(command, stdout=output,
                                                     stderr=subprocess.STDOUT,
                                                     start_new_session=True)
                    event("build_started", phase=phase, step=step, pid=build_process.pid, jobs=args.jobs)
                    while build_process.poll() is None:
                        sample("build_sample", build_process.pid, args.run)
                        time.sleep(30)
                    if build_process.returncode:
                        raise RuntimeError("%s %s failed: inspect its build log" % (phase, step))
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
                if args.battleground_test:
                    stage_world = optional_overlay(stage_world, {
                        "Appender.PlayerbotBG": "2,3,7,PlayerbotBG.log,a,67108864",
                        "Logger.playerbots.bgtest": "3,PlayerbotBG",
                        "Logger.bg.resurrection": "3,PlayerbotBG",
                    })
                    stage_bot = optional_overlay(stage_bot, {
                        "AiPlayerbot.BattlegroundTest": "1",
                        "AiPlayerbot.RandomBotMinLevel": "90",
                        "AiPlayerbot.RandomBotMaxLevel": "90",
                    })
                stage_world = navigation_diagnostics_overlay(stage_world, args.navigation_debug_log)
                if args.full_bot_log:
                    stage_world, stage_bot = full_bot_logging_overlay(stage_world, stage_bot)
                if args.until_navigation_error:
                    stage_world = navigation_capture_overlay(stage_world)
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
                        hours=duration / 3600 if duration is not None else None,
                        until_navigation_error=args.until_navigation_error,
                        navigation_error_count=args.navigation_error_count,
                    )
                    started = time.monotonic()
                    reached = None
                    population_reached = None
                    bg_telemetry = BattlegroundTelemetry()
                    skip_cycle_gate = args.skip_bg_cycle_gate or bool(args.until_navigation_error)
                    bg_verified = not requires_bg_cycle(args.battleground_test, skip_cycle_gate)
                    if args.battleground_test and skip_cycle_gate:
                        event("bg_cycle_gate_skipped", reason="Focused observation run; full native cycle not claimed")
                    workload_guard = WorkloadGuard(target)
                    behavior_verified = False
                    sanitizer_monitor = SanitizerMonitor(stage / "Logs") if phase == "sanitizer" else None
                    def save_navigation_finding(finding, findings):
                        pending = args.run / "navigation-findings.json.tmp"
                        pending.write_text(json.dumps(findings, indent=2) + "\n")
                        pending.replace(args.run / "navigation-findings.json")
                        event("navigation_error_observed", captured_count=len(findings),
                              required_count=args.navigation_error_count, finding=finding)

                    navigation_monitor = NavigationStopMonitor(stage / "Logs", args.navigation_error_count,
                                                               save_navigation_finding) if args.until_navigation_error else None
                    while args.until_navigation_error or reached is None or time.monotonic() - reached < duration:
                        if sanitizer_monitor:
                            sanitizer_monitor.check()
                        if process.poll() is not None:
                            raise RuntimeError(
                                "Worldserver exited unexpectedly with code %s in stage %s"
                                % (process.returncode, target)
                            )
                        if navigation_monitor:
                            navigation_monitor.check()
                        sql = (
                            "SELECT COUNT(*) FROM `%s`.characters c JOIN `%s`.account a ON a.id=c.account "
                            "WHERE c.online=1 AND a.username LIKE 'RNDBOT%%'"
                            % (character_db, auth_db)
                        )

                        def check_query_resources():
                            if sanitizer_monitor:
                                sanitizer_monitor.check()
                            if process.poll() is not None:
                                raise RuntimeError(
                                    "Worldserver exited during SQL check"
                                )
                            sample("resource_sample", process.pid, args.run)
                            if navigation_monitor:
                                navigation_monitor.check()

                        count = query_bot_count(
                            mysql_args, env, sql, event, check_query_resources
                        )
                        sample("stage_sample", process.pid, args.run, count)
                        bg_state = None
                        if population_reached is None and initial_population_ready(
                            count, target, stage / "Logs/console.log"
                        ):
                            population_reached = time.monotonic()
                            event("population_ready", bots=target, pid=process.pid)
                        if args.battleground_test:
                            bg_state = bg_telemetry.sample(stage / "Logs/PlayerbotBG.log")
                            event("bg_sample", **bg_state)
                            if bg_state["cycle_verified"] and not bg_verified:
                                bg_verified = True
                                event("bg_cycle_verified", **bg_state)
                            if requires_bg_cycle(args.battleground_test, skip_cycle_gate):
                                check_bg_cycle_deadline(time.monotonic(), population_reached, bg_verified)
                        if reached is not None:
                            workload_guard.check(time.monotonic(), count, bg_state)
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
                        if count >= target and population_reached is not None and bg_verified and reached is None:
                            reached = time.monotonic()
                            event(
                                "target_reached",
                                phase=phase,
                                bots=target,
                                pid=process.pid,
                            )
                        if population_reached is None and time.monotonic() - started > 1200:
                            raise RuntimeError(
                                "Target bot population was not reached within twenty minutes"
                            )
                        guarded_pause(30, check_query_resources)
                    stop(process, event)
                event(
                    "stage_finished",
                    phase=phase,
                    bots=target,
                    exit_code=process.returncode,
                )
                if process.returncode:
                    raise RuntimeError("Failure on stage shutdown: inspect logs")
                if phase == "sanitizer":
                    sanitizer_monitor.check(drain=True)
        event(
            "complete",
            message=(
                "%d-bot gate completed; worldserver stopped gracefully" % args.only_bots
                if args.only_bots is not None
                else "100-bot overnight interval completed; worldserver stopped gracefully"
            ),
        )
    except NavigationCaptured as captured:
        finish_navigation_capture(args.run, captured.finding, process, sanitizer_monitor, event)
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
