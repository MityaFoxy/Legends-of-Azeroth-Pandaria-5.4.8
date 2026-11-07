#!/usr/bin/env python3
"""Exercise the real supervisor with bounded clocks, DB and child processes."""
import argparse
import contextlib
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diagnostics"))
import playerbot_multilevel_soak as soak


def record(level=60, guid=1, team=469, phase="combat", damage=5):
    return (f"Bot=Test GUID={guid} phase={phase} level={level} map=529 instance=1 "
            f"bg_status=3 bg_team={team} damage_done={damage} matches=1 completed=0\n")


class SupervisorTests(unittest.TestCase):
    def run_supervisor(self, rows, online=100, console="", inhibitor_failed=False, levels=(60,),
                       behavior="2026-11-06_05:00:00 TRACE [playerbots.behavior] Bot=Test GUID=1 map=529 instance=1 decision=A:melee - OK\n",
                       rotated_unknown=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            runtime.mkdir()
            (runtime / "worldserver.conf").write_text("")
            (runtime / "playerbots.conf").write_text("")
            binary = root / "worldserver"
            binary.write_text("fake executable")
            args = argparse.Namespace(run=root / "test", runtime=runtime, binary=binary,
                                      work_root=root, build_container="build-test", mysql_container="db-test",
                                      levels=list(levels), bots=100, minutes_per_level=1)
            with contextlib.redirect_stdout(io.StringIO()):
                soak.prepare(args)
            manifest_path = args.run / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["startup_timeout_seconds"] = 45
            soak.write_json(manifest_path, manifest)
            clock = [1.0]
            children, commands = [], []

            class Child:
                def __init__(self, inhibitor=False):
                    self.pid = 100000 + len(children)
                    self.returncode = 1 if inhibitor and inhibitor_failed else None
                    children.append(self)

                def poll(self):
                    return self.returncode

                def wait(self, timeout=None):
                    self.returncode = 0
                    return 0

            class Database:
                auth = "auth"

                def query(self, sql):
                    return "0" if "online<>0" in sql else str(online)

            def spawn(command, **kw):
                if command[0] == "systemd-inhibit":
                    return Child(inhibitor=True)
                self.assertEqual(command[command.index("--user") + 1], "0")
                stage = args.run / Path(command[command.index("--workdir") + 1]).name
                level = int(stage.name.split("-")[1])
                (stage / "Logs/PlayerbotBG.log").write_text(rows(level) if callable(rows) else rows)
                (stage / "Logs/PlayerbotBehavior.log").write_text(behavior)
                if rotated_unknown:
                    with gzip.open(stage / "Logs/PlayerbotBehavior.log.old.gz", "wt") as archived:
                        archived.write("2026-11-06_04:59:59 TRACE [playerbots.behavior] "
                                       "Bot=Test GUID=1 map=529 instance=1 decision=A:combat formation move - UNKNOWN\n")
                (stage / "worldserver.pid").write_text("100000")
                kw["stdout"].write(console.encode())
                return Child()

            def command(argv, **kw):
                commands.append(argv)
                return subprocess.CompletedProcess(argv, 1 if "pgrep" in argv else 0)

            with (patch.object(soak, "Connection", return_value=Database()),
                  patch.object(soak.subprocess, "Popen", side_effect=spawn),
                  patch.object(soak.subprocess, "run", side_effect=command),
                  patch.object(soak.time, "monotonic", side_effect=lambda: clock[0]),
                  patch.object(soak.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)),
                  patch.object(soak.signal, "signal"), patch.object(soak.os, "killpg"),
                  patch.object(soak, "memory", return_value={"MemAvailable": 8 * 1024**3}),
                  patch.object(soak, "disk_space", return_value={"disk_free_bytes": 50 * 1024**3}),
                  contextlib.redirect_stdout(io.StringIO())):
                code = soak.execute(args)
            result = json.loads((args.run / "result.json").read_text())
            self.assertEqual(result, json.loads((args.run / "status.json").read_text()))
            self.assertTrue((args.run / "report.txt").is_file())
            if len(children) >= 2:
                for child in children[1:]:
                    self.assertEqual(child.returncode, 0, "server must stop even on a failed gate")
                signal_commands = [c for c in commands if "python3" in c]
                self.assertEqual(sum(c[-1] == "stop" for c in signal_commands), len(children) - 1,
                                 "one graceful signal per server, never a second signal or kill")
                for command in signal_commands:
                    self.assertEqual(command[:4], ["podman", "exec", "--user", "0"])
                    self.assertIn("PID identity mismatch", command[7])
            return code, result

    def test_real_combat_measures_duration_and_reports_cycle_separately(self):
        code, result = self.run_supervisor(record() + record(guid=2, team=67))
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "passed")
        stage = result["stages"][0]
        self.assertGreaterEqual(stage["measured_seconds"], 60)
        self.assertFalse(stage["bg"]["full_cycle_observed"])

    def test_queue_is_not_combat(self):
        code, result = self.run_supervisor(record(phase="queued", damage=0) + record(guid=2, team=67, phase="queued", damage=0))
        self.assertEqual(code, 1)
        self.assertEqual(result["stages"][0]["measured_seconds"], 0)

    def test_unknown_in_compressed_rotation_fails_acceptance_but_collects_all_levels(self):
        code, result = self.run_supervisor(
            lambda level: record(level=level) + record(level=level, guid=2, team=67),
            levels=(60, 80, 90), rotated_unknown=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["stages"]), 3)
        for stage in result["stages"]:
            self.assertEqual(stage["status"], "failed")
            self.assertEqual(stage["workload_status"], "passed")
            self.assertEqual(stage["action_resolution"]["unknown_actions"], {"combat formation move": 1})
            self.assertEqual(stage["exit_code"], 0)

    def test_missing_trace_cannot_report_action_resolution_success(self):
        code, result = self.run_supervisor(record() + record(guid=2, team=67), behavior="")
        self.assertEqual(code, 1)
        self.assertEqual(result["stages"][0]["workload_status"], "passed")
        self.assertEqual(result["stages"][0]["action_resolution"]["action_decisions"], 0)

    def test_ordinary_cast_failure_is_not_an_unknown_action(self):
        behavior = "2026-11-06_05:00:00 TRACE [playerbots.behavior] Bot=Test GUID=1 map=529 instance=1 decision=A:pummel - IMPOSSIBLE\n"
        code, result = self.run_supervisor(record() + record(guid=2, team=67), behavior=behavior)
        self.assertEqual(code, 0)
        self.assertEqual(result["stages"][0]["action_resolution"]["outcomes"], {"IMPOSSIBLE": 1})

    def test_debug_snapshots_do_not_double_count_trace_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory)
            (logs / "PlayerbotBehavior.log").write_text(
                "2026-11-06_05:00:00 TRACE [playerbots.behavior] Bot=Test GUID=1 decision=A:shoot - UNKNOWN\n"
                "2026-11-06_05:00:01 DEBUG [playerbots.behavior] Bot=Test GUID=1 last_attempt=A:shoot - UNKNOWN ok=0 failed=0\n"
                "2026-11-06_05:00:02 DEBUG [playerbots.behavior] Bot=Test GUID=1 last_attempt=A:shoot - UNKNOWN ok=0 failed=0\n")
            result = soak.audit_actions(logs)
            self.assertFalse(result["passed"])
            self.assertEqual(result["unknown_count"], 1)
            self.assertEqual(result["action_decisions"], 1)

    def test_wrong_level_cannot_satisfy_gate(self):
        code, result = self.run_supervisor(record(level=90) + record(level=90, guid=2, team=67))
        self.assertEqual(code, 1)
        self.assertEqual(result["stages"][0]["measured_seconds"], 0)

    def test_underfilled_population_cannot_start_timer(self):
        code, result = self.run_supervisor(record() + record(guid=2, team=67), online=99)
        self.assertEqual(code, 1)
        self.assertEqual(result["stages"][0]["measured_seconds"], 0)

    def test_fatal_diagnostic_stops_and_persists_failure(self):
        code, result = self.run_supervisor(record(), console="ASSERTION FAILED in world\n")
        self.assertEqual(code, 1)
        self.assertIn("Fatal diagnostic", result["error"])

    def test_inhibitor_failure_prevents_server_launch(self):
        code, result = self.run_supervisor("", inhibitor_failed=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["stages"], [])
        self.assertIn("inhibitor", result["error"])

    def test_all_three_stages_stop_and_advance(self):
        code, result = self.run_supervisor(
            lambda level: record(level=level) + record(level=level, guid=2, team=67), levels=(60, 80, 90))
        self.assertEqual(code, 0)
        self.assertEqual([s["level"] for s in result["stages"]], [60, 80, 90])
        self.assertTrue(all(s["status"] == "passed" and s["exit_code"] == 0 for s in result["stages"]))

    def test_control_script_probes_rejects_wrong_identity_and_stops_real_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = str(root / "private.conf")
            marker = root / "graceful-exit"
            program = ("import signal,sys,time; from pathlib import Path; "
                       "signal.signal(signal.SIGTERM, lambda *args: "
                       "(Path(sys.argv[2]).write_text('stopped'),sys.exit(0))); "
                       "print('ready',flush=True); time.sleep(60)")
            child = subprocess.Popen([sys.executable, "-c", program, config, str(marker)],
                                     stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "ready")
                pidfile = root / "server.pid"
                pidfile.write_text(str(child.pid))
                base = [sys.executable, "-c", soak.SERVER_CONTROL_SCRIPT, str(pidfile), sys.executable]
                probe = subprocess.run([*base, config, "probe"], capture_output=True, text=True, timeout=5)
                self.assertEqual(probe.returncode, 0, probe.stderr)
                self.assertIsNone(child.poll(), "probe must not stop the server")
                wrong = subprocess.run([*base, config + ".wrong", "stop"], capture_output=True, text=True, timeout=5)
                self.assertNotEqual(wrong.returncode, 0)
                self.assertIn("PID identity mismatch", wrong.stderr)
                self.assertIsNone(child.poll(), "wrong identity must not receive a signal")
                stop = subprocess.run([*base, config, "stop"], capture_output=True, text=True, timeout=5)
                self.assertEqual(stop.returncode, 0, stop.stderr)
                self.assertEqual(child.wait(timeout=5), 0)
                self.assertEqual(marker.read_text(), "stopped")
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=5)
                child.stdout.close()

    def test_control_errors_keep_the_actual_permission_failure(self):
        with patch.object(soak.subprocess, "run", side_effect=subprocess.CalledProcessError(
                1, "podman", stderr="PermissionError: [Errno 1] Operation not permitted")):
            with self.assertRaisesRegex(RuntimeError, "PermissionError"):
                soak.signal_owned_server("container", "/pid", "/binary", "/config")

    def test_log_tail_preserves_partial_line_across_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bg.log"
            path.write_text("first\npart")
            tail = soak.LogTail(path)
            self.assertEqual(tail.sample(), ["first"])
            with path.open("a") as output:
                output.write("ial\n")
            path.rename(path.with_suffix(".old"))
            path.write_text("new\n")
            self.assertEqual(tail.sample(), ["partial"])
            self.assertEqual(tail.sample(), ["new"])
            tail.close()


if __name__ == "__main__":
    unittest.main()
