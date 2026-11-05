#!/usr/bin/env python3
"""Check bounded SQL retry and observable failure cleanup without live servers."""

import importlib.util
import datetime
import errno
import gzip
import json
import os
import pathlib
import subprocess
import struct
import sys
import tempfile
import unittest
import uuid
from unittest.mock import Mock, patch

root = pathlib.Path(sys.argv.pop(1))
if len(sys.argv) > 1:
    sys.argv.pop(1)  # CTest passes its C++ compiler; unused by this Python fixture.
path = root / "contrib/diagnostics/sanitizer_soak.py"
spec = importlib.util.spec_from_file_location("soak", path)
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)


class ControllerTests(unittest.TestCase):
    def test_full_bot_logging_isolated_and_unfiltered(self):
        world = "Logger.playerbots = 3,Console Server\nLogger.playerbots.bgtest = 3,PlayerbotBG\n"
        bots = "AiPlayerbot.LogBehavior = 0\nAiPlayerbot.LogInGroupOnly = 1\n"
        configured, ai = soak.full_bot_logging_overlay(world, bots)
        self.assertEqual(soak.setting(configured, "Logger.playerbots"), "1,PlayerbotFull Console")
        self.assertEqual(soak.setting(configured, "Logger.playerbots.behavior"), "1,PlayerbotBehavior")
        self.assertEqual(soak.setting(configured, "Logger.playerbots.navigation"), "2,PlayerbotNavigation")
        self.assertEqual(soak.setting(configured, "Logger.playerbots.bgtest"), "3,PlayerbotBG")
        self.assertEqual(soak.setting(ai, "AiPlayerbot.LogBehaviorInterval"), "5")
        self.assertEqual(soak.setting(ai, "AiPlayerbot.LogInGroupOnly"), "0")

    def test_log_compression_retains_bytes_and_ignores_live_and_sanitizer_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            logs = root / "sanitizer-bots-100/Logs"
            logs.mkdir(parents=True)
            name = "PlayerbotBehavior.log.2026-10-28_00-30-00"
            rotated = logs / name
            payload = b"Bot=test GUID=123 decision=A:cast - FAILED\n" * 10000
            rotated.write_bytes(payload)
            os.utime(rotated, (10, 10))
            preserved = [logs / "PlayerbotBehavior.log", logs / "asan.123",
                         logs / "PlayerbotBG.log.2026-10-28_00-31-00"]
            for p in preserved:
                p.write_bytes(b"still live")
                os.utime(p, (100, 100))
            result = soak.compress_rotated_bot_log(root, now=110)
            self.assertEqual(result["original_bytes"], len(payload))
            self.assertFalse(rotated.exists())
            with gzip.open(logs / (name + ".gz"), "rb") as f:
                self.assertEqual(f.read(), payload)
            for p in preserved:
                self.assertEqual(p.read_bytes(), b"still live")
            self.assertIsNone(soak.compress_rotated_bot_log(root, now=110))

    def test_failed_log_archive_never_removes_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            logs = root / "sanitizer-bots-100/Logs"
            logs.mkdir(parents=True)
            rotated = logs / "PlayerbotNavigation.log.2026-10-28_00-30-00"
            rotated.write_bytes(b"evidence")
            os.utime(rotated, (10, 10))
            with patch.object(soak.gzip, "GzipFile", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    soak.compress_rotated_bot_log(root, now=100)
            self.assertEqual(rotated.read_bytes(), b"evidence")
            self.assertFalse(list(logs.glob("*.tmp")))

    def test_btrfs_reservations_block_false_statfs_capacity(self):
        # Reproduce the incident: 23 GiB reported free, but metadata is reserved
        # and only 1 MiB remains outside allocated device chunks.
        fsid = uuid.UUID("2fbaf853-75fb-42c6-ae06-79cbb70f0ff4")
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            metadata = base / str(fsid) / "allocation/metadata"
            metadata.mkdir(parents=True)
            (base / str(fsid) / "devinfo/1").mkdir(parents=True)
            counters = dict(total_bytes=6979321856, bytes_used=6432210944,
                            bytes_reserved=98304, bytes_pinned=802816,
                            bytes_may_use=542670848, bytes_readonly=0,
                            bytes_zone_unusable=0)
            for key, value in counters.items():
                (metadata / key).write_text(str(value))
            def ioctl(fd, request, data, mutate):
                if request == 0x8400941f:
                    data[16:32] = fsid.bytes
                elif request == 0xd000941e:
                    self.assertEqual(struct.unpack_from("=Q", data)[0], 1)
                    struct.pack_into("=QQ", data, 24, 511569821696, 511570870272)
                else:
                    self.fail("Unexpected ioctl")
            with patch.object(soak.fcntl, "ioctl", side_effect=ioctl), \
                    patch.object(soak.shutil, "disk_usage", return_value=Mock(free=23 * 1024**3)):
                record = soak.disk_space(base, sysfs=base)
            self.assertEqual(record["btrfs_metadata_headroom_bytes"], 3538944)
            self.assertEqual(record["btrfs_min_device_unallocated_bytes"], 1024**2)
            with self.assertRaisesRegex(RuntimeError, "Btrfs metadata"):
                soak.check_disk_space(record)
            # Growth space can resolve pressure without removing existing data.
            record["btrfs_min_device_unallocated_bytes"] = 2 * 1024**3
            soak.check_disk_space(record)
            record["btrfs_min_device_unallocated_bytes"] = 0
            record["btrfs_metadata_headroom_bytes"] = 256 * 1024**2
            soak.check_disk_space(record)

    def test_non_btrfs_retains_disk_floor(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(soak.fcntl, "ioctl", side_effect=OSError(errno.ENOTTY, "Not Btrfs")), \
                patch.object(soak.shutil, "disk_usage", return_value=Mock(free=9 * 1024**3)):
            record = soak.disk_space(directory)
        self.assertNotIn("btrfs_fsid", record)
        with self.assertRaisesRegex(RuntimeError, "10 GiB"):
            soak.check_disk_space(record)

    def test_unreadable_btrfs_counters_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(soak.fcntl, "ioctl", side_effect=PermissionError(errno.EPERM, "Denied")):
                with self.assertRaises(PermissionError):
                    soak.disk_space(directory)
            # A successful FS_INFO with inaccessible sysfs must not silently
            # downgrade to statfs and repeat the original false-safe result.
            with patch.object(soak.fcntl, "ioctl", return_value=0):
                with self.assertRaises(FileNotFoundError):
                    soak.disk_space(directory, sysfs=pathlib.Path(directory))

    def test_two_distinct_errors_preserve_first_and_deduplicate_state_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = pathlib.Path(directory)
            console = logs / "console.log"
            observed = []
            def saved(finding, findings):
                observed.append(dict(finding))
                (logs / "saved.json").write_text(json.dumps(findings))
            monitor = soak.NavigationStopMonitor(logs, 2, saved)
            prefix = "2026-10-26_01:00:00 WARN [playerbots.navigation] bot=133 map=529 instance=2 "
            state = prefix + "outcome=start-mismatch-state splinePoints='0:1,2,3;1:4,5,6'"
            reject = prefix.replace("01:00:00", "01:00:01") + "outcome=rejected reason=path-start-mismatch"
            console.write_text(state + "\n" + reject + "\n")
            monitor.check()
            self.assertEqual(len(observed), 1)
            self.assertEqual(json.loads((logs / "saved.json").read_text())[0]["line"], state)
            # A replay in a rotated file is still the same error.
            console.rename(logs / "old.log")
            console.write_text(state + "\n" + reject + "\n")
            monitor.check()
            self.assertEqual(len(observed), 1)
            # A later failure from the same bot counts; no need for another bot.
            second = state.replace("01:00:00", "01:00:31")
            with console.open("a") as output:
                output.write(second[:-4])
            monitor.check()
            self.assertEqual(len(observed), 1)
            with console.open("a") as output:
                output.write(second[-4:] + "\n")
            with self.assertRaises(soak.NavigationCaptured) as captured:
                monitor.check()
            self.assertEqual(captured.exception.finding["captured_count"], 2)
            self.assertEqual(len(captured.exception.finding["findings"]), 2)
            self.assertEqual(len(json.loads((logs / "saved.json").read_text())), 2)

    def test_two_summary_only_errors_from_different_bots_in_same_second(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = soak.NavigationStopMonitor(pathlib.Path(directory), 2)
            line = "2026-10-26_01:00:00 WARN [playerbots.navigation] bot=1 map=529 instance=2 outcome=rejected reason=path-start-mismatch"
            monitor.inspect(line.encode())
            with self.assertRaises(soak.NavigationCaptured):
                monitor.inspect(line.replace("bot=1", "bot=2").encode())

    def test_navigation_capture_is_specific_and_keeps_full_state(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = pathlib.Path(directory)
            console = logs / "console.log"
            monitor = soak.NavigationStopMonitor(logs)
            monitor.check()
            console.write_text("[playerbots.navigation] bot=61 map=0 outcome=start-mismatch-state\n"
                               "[other] bot=61 map=529 outcome=start-mismatch-state\n"
                               "[playerbots.navigation] bot=61 map=529 outcome=rejected reason=path-body-obstructed\n"
                               "[playerbots.navigation] bot=61 map=529 outcome=alternative-route reason=path-start-mismatch\n")
            monitor.check()
            state = ("[playerbots.navigation] bot=61 map=529 instance=3 outcome=start-mismatch-state "
                     "groundDelta=4.376 combat=true auras='123:3:2400:155'")
            with console.open("ab") as output:
                output.write(b"\x1b[31m" + state[:70].encode())
            monitor.check()  # Wait for the complete diagnostic, including auras.
            with console.open("ab") as output:
                output.write(state[70:].encode() + b"\x1b[0m\n")
            with self.assertRaises(soak.NavigationCaptured) as caught:
                monitor.check()
            finding = caught.exception.finding
            self.assertEqual(finding["line"], state)
            self.assertEqual(finding["bot"], 61)
            self.assertEqual(finding["reason"], "path-start-mismatch")

    def test_navigation_capture_handles_bounds_rotation_and_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = pathlib.Path(directory)
            console = logs / "console.log"
            marker = b"[playerbots.navigation] bot=61 map=529 outcome=rejected reason=path-start-mismatch\n"
            monitor = soak.NavigationStopMonitor(logs)
            console.write_bytes(b"x" * (monitor.MAX_LINE_BYTES * 2))
            monitor.check()
            self.assertLessEqual(len(monitor.pending), monitor.MAX_LINE_BYTES)
            with console.open("ab") as output:
                output.write(b"\n" + marker)
            with self.assertRaises(soak.NavigationCaptured):
                monitor.check()
            monitor = soak.NavigationStopMonitor(logs)
            console.write_bytes(b"ignored\n" * (monitor.SAMPLE_BYTES // 8 + 20) + marker)
            monitor.check()
            self.assertEqual(monitor.offset, monitor.SAMPLE_BYTES)
            with self.assertRaises(soak.NavigationCaptured):
                monitor.check()
            monitor = soak.NavigationStopMonitor(logs)
            console.write_bytes(marker[:-5])
            monitor.check()
            console.rename(logs / "old.log")
            console.write_bytes(marker[-5:])
            monitor.check()  # Never join partial records from different files.
            console.write_bytes(b"x")
            monitor.check()  # Truncation resets both pending data and offset.
            self.assertEqual(monitor.offset, 1)
            self.assertEqual(monitor.pending, b"x")
            with console.open("ab") as output:
                output.write(b"\n" + marker)
            with self.assertRaises(soak.NavigationCaptured):
                monitor.check()

    def test_navigation_capture_overlay_preserves_debug_and_adds_console(self):
        original = "Logger.playerbots.navigation = 2,PlayerbotNavigation\nOther = unchanged\n"
        result = soak.navigation_capture_overlay(original)
        self.assertEqual(soak.setting(result, "Logger.playerbots.navigation"), "2,PlayerbotNavigation Console")
        self.assertIn("Other = unchanged", result)
        self.assertEqual(soak.navigation_capture_overlay(result), result)
        disabled = "Logger.playerbots.navigation = 0,Server\n"
        self.assertEqual(soak.setting(soak.navigation_capture_overlay(disabled), "Logger.playerbots.navigation"),
                         "3,Server Console")
        inherited = "Logger.playerbots = 3,Console Server\nOther = unchanged\n"
        result = soak.navigation_capture_overlay(inherited)
        self.assertEqual(soak.setting(result, "Logger.playerbots.navigation"), "3,Console Server")
        self.assertIn(inherited, result)

    def test_navigation_capture_stops_gracefully_and_is_not_a_clean_soak(self):
        with tempfile.TemporaryDirectory() as directory:
            run = pathlib.Path(directory)
            process = Mock(pid=123)
            process.poll.side_effect = [None, 0, 0, 0]
            monitor = Mock()
            events = []
            finding = dict(bot=61, reason="path-start-mismatch", line="state with effects")
            soak.finish_navigation_capture(run, finding, process, monitor,
                                           lambda kind, **data: events.append((kind, data)))
            process.send_signal.assert_called_once_with(soak.signal.SIGTERM)
            process.wait.assert_called_once_with(timeout=120)
            process.kill.assert_not_called()
            monitor.check.assert_called_once_with(drain=True)
            self.assertEqual(json.loads((run / "navigation-finding.json").read_text()), finding)
            self.assertEqual(events[-1][0], "complete")
            self.assertTrue(events[-1][1]["error_reproduced"])
            self.assertEqual(events[-1][1]["stop_reason"], "navigation_error_captured")
            self.assertNotIn("gate completed", events[-1][1]["message"])

    def test_navigation_capture_does_not_hide_shutdown_or_sanitizer_failure(self):
        for exit_code in (0, 1):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as directory:
                process = Mock(pid=123)
                process.poll.return_value = exit_code
                monitor = Mock()
                monitor.check.side_effect = RuntimeError("sanitizer finding on shutdown")
                events = []
                with self.assertRaises(RuntimeError):
                    soak.finish_navigation_capture(pathlib.Path(directory), {}, process, monitor,
                                                   lambda kind, **data: events.append((kind, data)))
                self.assertEqual(events[-1][0], "failed")
                self.assertNotIn("complete", [kind for kind, _ in events])

    def test_error_capture_cli_rejects_conflicting_or_incomplete_modes(self):
        for options in (("--hours", "1", "--until-navigation-error", "path-start-mismatch"),
                        ("--until-navigation-error", "path-start-mismatch"),
                        ("--navigation-error-count", "2"),
                        ("--navigation-error-count", "0"),
                        ("--navigation-error-count", "101")):
            result = subprocess.run([sys.executable, str(path), "--already-stopped", "--revision", "test",
                                     "--run", "/unused", *options], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("error:", result.stderr)

    def test_console_monitor_detects_split_reports_without_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = pathlib.Path(directory)
            console = logs / "console.log"
            monitor = soak.SanitizerMonitor(logs)
            monitor.check()  # Console may not exist during early startup.
            console.write_bytes(b"ordinary output\nruntime er")
            monitor.check()
            with console.open("ab") as out:
                out.write(b"ror: shift exponent 4294967294")
            with self.assertRaisesRegex(RuntimeError, "console.log"):
                monitor.check()

    def test_console_monitor_detects_all_supported_findings(self):
        markers = (b"runtime error:", b"ERROR: AddressSanitizer",
                   b"ERROR: LeakSanitizer", b"AddressSanitizer:DEADLYSIGNAL",
                   b"SUMMARY: UndefinedBehaviorSanitizer",
                   b"that just lost any reference to the owner")
        with tempfile.TemporaryDirectory() as directory:
            logs = pathlib.Path(directory)
            for marker in markers:
                with self.subTest(marker=marker):
                    (logs / "console.log").write_bytes(b"\xff\x1b[31m" + marker)
                    with self.assertRaisesRegex(RuntimeError, "console.log"):
                        soak.SanitizerMonitor(logs).check()

    def test_console_monitor_is_bounded_and_drains_on_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = pathlib.Path(directory)
            console = logs / "console.log"
            monitor = soak.SanitizerMonitor(logs)
            # Split a signature at the internal read boundary, not just samples.
            console.write_bytes(b"x" * (monitor.CHUNK_BYTES - 7) + b"runtime error:")
            with self.assertRaisesRegex(RuntimeError, "console.log"):
                monitor.check()
            monitor = soak.SanitizerMonitor(logs)
            console.write_bytes(b"x" * (monitor.SAMPLE_BYTES + 100) + b"runtime error:")
            monitor.check()
            self.assertEqual(monitor.offset, monitor.SAMPLE_BYTES)
            self.assertLess(len(monitor.tail), 128)
            with self.assertRaisesRegex(RuntimeError, "console.log"):
                monitor.check(drain=True)

    def test_console_monitor_handles_rotation_and_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = pathlib.Path(directory)
            console = logs / "console.log"
            monitor = soak.SanitizerMonitor(logs)
            console.write_bytes(b"x" * 200)
            monitor.check()
            console.write_bytes(b"runtime er")
            monitor.check()  # Truncation resets the offset.
            console.rename(logs / "console.old")
            console.write_bytes(b"ror: unrelated fragment")
            monitor.check()  # Do not join fragments from unrelated files.
            with console.open("ab") as out:
                out.write(b"ERROR: AddressSanitizer")
            with self.assertRaisesRegex(RuntimeError, "console.log"):
                monitor.check()

    def test_console_monitor_checks_separate_reports_too(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = pathlib.Path(directory)
            report = logs / "ubsan.42"
            report.write_bytes(b"")
            monitor = soak.SanitizerMonitor(logs)
            monitor.check()
            report.write_bytes(b"diagnostic")
            with self.assertRaisesRegex(RuntimeError, "ubsan.42"):
                monitor.check()

    def test_bg_cycle_deadline_is_sixty_minutes_after_population(self):
        check = soak.check_bg_cycle_deadline
        check(100000, None, False)  # Population timeout has its own guard.
        check(100 + 2701, 100, False)  # Former deadline must not abort.
        check(100 + 3600, 100, False)
        with self.assertRaisesRegex(RuntimeError, "60 minutes"):
            check(100 + 3601, 100, False)
        check(100 + 3601, 100, True)

    def test_focused_bg_observation_does_not_claim_a_full_cycle_gate(self):
        self.assertTrue(soak.requires_bg_cycle(True, False))
        self.assertFalse(soak.requires_bg_cycle(True, True))
        self.assertFalse(soak.requires_bg_cycle(False, False))

    def test_navigation_debug_is_opt_in_and_stage_isolated(self):
        original = "Logger.playerbots.navigation = 3,Server\nOther = unchanged\n"
        self.assertEqual(soak.navigation_diagnostics_overlay(original, False), original)
        verbose = soak.navigation_diagnostics_overlay(original, True)
        self.assertEqual(verbose.count("Logger.playerbots.navigation"), 1)
        self.assertIn("Logger.playerbots.navigation = 2,PlayerbotNavigation", verbose)
        self.assertIn("PlayerbotNavigation.log,a,67108864", verbose)
        self.assertIn("Other = unchanged", verbose)
        repeated = soak.navigation_diagnostics_overlay(verbose, True)
        self.assertEqual(repeated.count("Appender.PlayerbotNavigation"), 1)
        self.assertEqual(repeated.count("Logger.playerbots.navigation"), 1)
        self.assertEqual(soak.setting(repeated, "Logger.playerbots.navigation"), "2,PlayerbotNavigation")
        self.assertIn("3,Server", original)

    def test_initial_population_ignores_stale_online_until_world_initialized(self):
        with tempfile.TemporaryDirectory() as directory:
            console = pathlib.Path(directory) / "console.log"
            self.assertFalse(soak.initial_population_ready(200, 200, console))
            console.write_text("Loading world data...\n")
            self.assertFalse(soak.initial_population_ready(200, 200, console))
            console.write_text("World initialized in 0 minutes 45 seconds\n")
            self.assertFalse(soak.initial_population_ready(199, 200, console))
            self.assertTrue(soak.initial_population_ready(200, 200, console))

    def test_workload_guard_preserves_population_and_bg_progress(self):
        guard = soak.WorkloadGuard(200)
        guard.check(0, 200)
        guard.check(1, 199)
        guard.check(120, 199)
        with self.assertRaisesRegex(RuntimeError, "population"):
            guard.check(121, 199)
        guard.check(122, 200)
        guard.check(123, 199)
        guard.check(124, 200)
        state = {"phases": {"combat": 1, "completed": 1}}
        guard.check(200, 200, state)
        guard.check(1099, 200, state)
        with self.assertRaisesRegex(RuntimeError, "combat"):
            guard.check(1100, 200, state)
        for now in range(1000, 5600, 100):
            guard.check(now, 200, {"phases": {"combat": now, "completed": 1}})
        with self.assertRaisesRegex(RuntimeError, "completed"):
            guard.check(5600, 200, {"phases": {"combat": 5600, "completed": 1}})

    def test_backup_waiver_does_not_call_dump_or_create_files(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(soak.subprocess, "run") as dump:
            events = []
            run = pathlib.Path(directory)
            soak.backup_databases(run, [], {}, [], lambda kind, **data: events.append(kind), skip=True)
            self.assertEqual(events, ["backup_skipped"])
            self.assertEqual(list(run.iterdir()), [])
            dump.assert_not_called()

    def test_bg_gate_requires_same_bot_fight_death_and_native_reentry(self):
        telemetry = soak.BattlegroundTelemetry()
        with tempfile.TemporaryDirectory() as directory:
            log = pathlib.Path(directory) / "BG.log"
            log.write_text("Bot=A GUID=1 phase=combat damage_done=42 matches=1 completed=0\n"
                           "Bot=B GUID=2 phase=dead matches=1 completed=0\n"
                           "Bot=C GUID=3 phase=entered matches=2 completed=1\n")
            self.assertFalse(telemetry.sample(log)["cycle_verified"])
            self.assertEqual(telemetry.sample(log)["combat_bots"], 1)
            with log.open("a") as out:
                out.write("Bot=A GUID=1 phase=dead matches=1 completed=0\n"
                          "Bot=A GUID=1 phase=entered matches=2 completed=0\n")
            self.assertFalse(telemetry.sample(log)["cycle_verified"])
            with log.open("a") as out:
                out.write("Bot=A GUID=1 phase=entered matches=2 completed=1")
            self.assertFalse(telemetry.sample(log)["cycle_verified"])
            with log.open("a") as out:
                out.write("\n")
            self.assertFalse(telemetry.sample(log)["cycle_verified"])
            with log.open("a") as out:
                out.write("Bot=B GUID=2 phase=resurrected matches=1 completed=0\n")
            self.assertFalse(telemetry.sample(log)["cycle_verified"])
            with log.open("a") as out:
                out.write("Bot=A GUID=1 phase=resurrected matches=2 completed=1\n")
            self.assertTrue(telemetry.sample(log)["cycle_verified"])
            self.assertEqual(telemetry.sample(log)["resurrected_bots"], 2)
            log.rename(log.with_suffix(".old"))
            log.write_text("Bot=D GUID=4 phase=combat matches=1 completed=0\n")
            self.assertEqual(telemetry.sample(log)["combat_bots"], 2)
            log.write_text("Bot=E GUID=5 phase=dead\n")
            self.assertEqual(telemetry.sample(log)["dead_bots"], 3)

    def test_temperature_capture_tracks_actual_duration(self):
        capture_spec = importlib.util.spec_from_file_location(
            "capture", root / "contrib/diagnostics/capture_soak_temperature.py"
        )
        capture = importlib.util.module_from_spec(capture_spec)
        capture_spec.loader.exec_module(capture)
        with tempfile.TemporaryDirectory() as directory:
            run = pathlib.Path(directory)
            reached = (
                datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(hours=10)
                + datetime.timedelta(seconds=60)
            )
            rows = [
                dict(event="stage_started", phase="sanitizer", bots=200, hours=10),
                dict(
                    event="target_reached",
                    phase="sanitizer",
                    bots=200,
                    time=reached.isoformat(),
                ),
            ]
            (run / "events.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows)
            )
            (run / "status.json").write_text('{"bots_online":200}')
            with (
                patch.object(
                    sys, "argv", ["capture", "--run", directory, "--bots", "200"]
                ),
                patch.object(
                    capture.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, "CPU: 73C", ""),
                ),
                patch("builtins.print"),
            ):
                capture.main()
            self.assertIn(
                "CPU: 73C", (run / "temperature-before-finish.log").read_text()
            )
            (run / "temperature-before-finish.log").unlink()
            (run / "result.json").write_text('{"event":"failed"}')
            with (
                patch.object(
                    sys, "argv", ["capture", "--run", directory, "--bots", "200"]
                ),
                patch.object(capture.subprocess, "run") as sensors,
                patch("builtins.print"),
            ):
                capture.main()
            sensors.assert_not_called()
            self.assertFalse((run / "temperature-before-finish.log").exists())

    def test_single_population_accepts_200_bots(self):
        self.assertEqual(soak.population_stages(200, 15 * 3600), ((200, 54000),))

    def test_optional_overlay_replaces_or_adds_once(self):
        text = "Existing = 0\n"
        result = soak.optional_overlay(text, {"Existing": "1", "New": "2"})
        self.assertEqual(result.count("Existing ="), 1)
        self.assertEqual(result.count("New ="), 1)
        self.assertEqual(soak.setting(result, "Existing"), "1")
        self.assertEqual(soak.optional_overlay(result, {"New": "3"}).count("New ="), 1)

    def query(self, responses):
        events, resources = [], Mock()
        with (
            patch.object(soak.subprocess, "run", side_effect=responses) as run,
            patch.object(soak.time, "sleep"),
        ):
            value = soak.query_bot_count(
                [],
                {"MYSQL_PWD": "fake-secret"},
                "SELECT 1",
                lambda kind, **data: events.append((kind, data)),
                resources,
            )
        return value, events, resources, run

    def test_transient_then_success(self):
        error = subprocess.CompletedProcess([], 1, "", "ERROR 2003: fake-secret")
        ok = subprocess.CompletedProcess([], 0, "100\n", "")
        value, events, resources, run = self.query([error, ok])
        self.assertEqual(value, 100)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(resources.call_count, 3)
        self.assertNotIn("fake-secret", str(events))
        self.assertEqual(run.call_args.kwargs["timeout"], 10)
        self.assertIn("--connect-timeout=5", run.call_args.args[0])

    def test_timeout_then_success(self):
        value, events, _, _ = self.query(
            [
                subprocess.TimeoutExpired("mysql", 10),
                subprocess.CompletedProcess([], 0, "0\n", ""),
            ]
        )
        self.assertEqual(value, 0)
        self.assertEqual(events[0][0], "sql_query_timeout")

    def test_persistent_failure_is_bounded(self):
        error = subprocess.CompletedProcess([], 1, "", "ERROR 2013: lost connection")
        with (
            patch.object(soak.subprocess, "run", return_value=error) as run,
            patch.object(soak.time, "sleep"),
            self.assertRaises(RuntimeError),
        ):
            soak.query_bot_count([], {}, "SELECT 1", Mock(), Mock())
        self.assertEqual(run.call_count, 3)

    def test_non_transient_and_malformed_do_not_retry(self):
        for response in [
            subprocess.CompletedProcess([], 1, "", "ERROR 1146: table missing"),
            subprocess.CompletedProcess([], 0, "invalid", ""),
        ]:
            with (
                patch.object(soak.subprocess, "run", return_value=response) as run,
                self.assertRaises(RuntimeError),
            ):
                soak.query_bot_count([], {}, "SELECT 1", Mock(), Mock())
            self.assertEqual(run.call_count, 1)

    def test_resource_guard_is_not_bypassed(self):
        with (
            patch.object(soak.subprocess, "run") as run,
            self.assertRaises(RuntimeError),
        ):
            soak.query_bot_count(
                [], {}, "SELECT 1", Mock(), Mock(side_effect=RuntimeError("RAM guard"))
            )
        run.assert_not_called()

    def test_failure_shutdown_observability(self):
        events = []
        process = Mock(pid=123)
        process.poll.return_value = None
        process.wait.side_effect = lambda **kw: setattr(process.poll, "return_value", 0)
        result = soak.stop_after_failure(
            process, lambda kind, **data: events.append((kind, data))
        )
        process.send_signal.assert_called_once_with(soak.signal.SIGTERM)
        self.assertFalse(result["still_alive"])
        self.assertEqual(events[-1][0], "shutdown_finished")

    def test_shutdown_timeout_retains_supervision_until_child_exits(self):
        process = Mock(pid=123)
        process.poll.return_value = None
        calls = 0

        def wait(**kwargs):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise subprocess.TimeoutExpired("worldserver", kwargs["timeout"])
            process.poll.return_value = 0

        process.wait.side_effect = wait
        events = []
        result = soak.stop_after_failure(
            process, lambda kind, **data: events.append((kind, data))
        )
        self.assertFalse(result["still_alive"])
        process.send_signal.assert_called_once_with(soak.signal.SIGTERM)
        self.assertEqual([call.kwargs["timeout"] for call in process.wait.call_args_list], [120, 30, 30])
        self.assertEqual(
            [kind for kind, _ in events],
            ["shutdown_requested", "shutdown_waiting", "shutdown_waiting", "shutdown_finished"],
        )

    def test_normal_shutdown_timeout_never_sends_a_second_signal(self):
        process = Mock(pid=123)
        process.poll.return_value = None
        calls = 0

        def wait(**kwargs):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise subprocess.TimeoutExpired("worldserver", kwargs["timeout"])
            process.poll.return_value = 0

        process.wait.side_effect = wait
        events = []
        soak.stop(process, lambda kind, **data: events.append((kind, data)))
        process.send_signal.assert_called_once_with(soak.signal.SIGTERM)
        self.assertEqual([call.kwargs["timeout"] for call in process.wait.call_args_list], [120, 30, 30])
        self.assertEqual([kind for kind, _ in events], ["shutdown_waiting", "shutdown_waiting"])

    def test_failed_stop_waits_for_a_real_child_without_force_kill(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
        events = []
        try:
            with patch.object(soak, "stop", side_effect=RuntimeError("Graceful timeout")):
                result = soak.stop_after_failure(process, lambda kind, **data: events.append(kind))
            self.assertFalse(result["still_alive"])
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("shutdown_waiting", events)
        finally:
            process.wait(timeout=5)

    def test_resource_checks_continue_during_pause(self):
        clock = [0]

        def sleep(seconds):
            clock[0] += seconds

        check = Mock()
        with patch.object(soak.time, "monotonic", side_effect=lambda: clock[0]), patch.object(soak.time, "sleep", side_effect=sleep):
            soak.guarded_pause(12, check)
        self.assertEqual(clock[0], 12)
        self.assertEqual(check.call_count, 3)

    def test_terminal_failure_is_written_after_cleanup(self):
        source = path.read_text()
        source = source[source.index("def main():"):]
        failure = source[source.index("    except BaseException as error:") :]
        self.assertLess(
            failure.index('event("failure_detected"'),
            failure.index("shutdown = stop_after_failure"),
        )
        self.assertLess(
            failure.index("shutdown = stop_after_failure"),
            failure.index('event("failed"'),
        )


unittest.main()
