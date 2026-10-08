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
                dict(event="stage_started", phase="sanitizer", bots=100, hours=10),
                dict(
                    event="target_reached",
                    phase="sanitizer",
                    bots=100,
                    time=reached.isoformat(),
                ),
            ]
            (run / "events.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows)
            )
            (run / "status.json").write_text('{"bots_online":100}')
            with (
                patch.object(sys, "argv", ["capture", "--run", directory]),
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
                patch.object(sys, "argv", ["capture", "--run", directory]),
                patch.object(capture.subprocess, "run") as sensors,
                patch("builtins.print"),
            ):
                capture.main()
            sensors.assert_not_called()
            self.assertFalse((run / "temperature-before-finish.log").exists())

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

    def test_shutdown_timeout_reports_live_process(self):
        process = Mock(pid=123)
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired("worldserver", 120)
        events = []
        result = soak.stop_after_failure(
            process, lambda kind, **data: events.append((kind, data))
        )
        self.assertTrue(result["still_alive"])
        self.assertEqual(
            [kind for kind, _ in events],
            ["shutdown_requested", "shutdown_failed", "shutdown_incomplete"],
        )

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
