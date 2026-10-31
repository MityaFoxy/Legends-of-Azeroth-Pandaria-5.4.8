#!/usr/bin/env python3
"""Check bounded SQL retry and observable failure cleanup without live servers."""

import importlib.util
import datetime
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

root = pathlib.Path(sys.argv.pop(1))
if len(sys.argv) > 1:
    sys.argv.pop(1)  # CTest passes its C++ compiler; unused by this Python fixture.
path = root / "contrib/diagnostics/sanitizer_soak.py"
spec = importlib.util.spec_from_file_location("soak", path)
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)


class ControllerTests(unittest.TestCase):
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
