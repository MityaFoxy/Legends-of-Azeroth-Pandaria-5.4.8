#!/usr/bin/env python3
"""Exercise the real BotLife soak observer without a running server."""
import pathlib
import sys
import tempfile
import unittest

root = pathlib.Path(sys.argv.pop(1))
sys.path.insert(0, str(root / "contrib/diagnostics"))
from botlife_sanitizer_soak import ConsoleEvents


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.logs = pathlib.Path(self.directory.name)
        self.console = self.logs / "console.log"
        self.botlife = self.logs / "BotLife.log"
        self.observer = ConsoleEvents(self.console, self.botlife)

    def append(self, path, data):
        with path.open("ab") as stream:
            stream.write(data)

    def test_separate_appender_starts_and_completes_travel(self):
        self.console.write_bytes(b"World initialized in 0 minutes 37 seconds\n")
        self.botlife.write_bytes(b"INFO BotLife travel-test guid=6 event=start map=1\n")
        self.observer.update(6)
        self.assertTrue(self.observer.ready)
        self.assertTrue(self.observer.travel_started)
        self.assertFalse(self.observer.travel_verified)
        self.append(self.botlife, b"INFO BotLife travel-test guid=6 event=finish result=completed failure=None\n")
        self.observer.update(6)
        self.assertEqual(self.observer.travel_result, "completed")
        self.assertTrue(self.observer.travel_verified)

    def test_missing_files_and_wrong_guid_do_not_start(self):
        self.observer.update(6)
        self.assertFalse(self.observer.ready)
        self.botlife.write_bytes(b"BotLife travel-test guid=60 event=start\n"
                                b"BotLife travel-test guid=9 event=finish result=completed\n")
        self.observer.update(6)
        self.assertFalse(self.observer.travel_started)
        self.assertFalse(self.observer.travel_verified)

    def test_split_lines_and_result_are_not_consumed_early(self):
        self.console.write_bytes(b"World initialized ")
        self.botlife.write_bytes(b"BotLife travel-test guid=6 event=sta")
        self.observer.update(6)
        self.assertFalse(self.observer.travel_started)
        self.append(self.console, b"in 0 minutes 37 seconds\n")
        self.append(self.botlife, b"rt map=1\nBotLife travel-test guid=6 event=finish result=comp")
        self.observer.update(6)
        self.assertTrue(self.observer.ready)
        self.assertTrue(self.observer.travel_started)
        self.assertIsNone(self.observer.travel_result)
        self.append(self.botlife, b"leted failure=None\n")
        self.observer.update(6)
        self.assertTrue(self.observer.travel_verified)

    def test_fragments_from_different_files_cannot_form_event(self):
        self.console.write_bytes(b"BotLife travel-test guid=6 event=")
        self.botlife.write_bytes(b"start map=1\n")
        self.observer.update(6)
        self.assertFalse(self.observer.travel_started)

    def test_rotation_and_truncation_reset_partial_lines(self):
        self.botlife.write_bytes(b"BotLife travel-test guid=6 event=")
        self.observer.update(6)
        self.botlife.rename(self.logs / "BotLife.old")
        self.botlife.write_bytes(b"start\n" + b"x" * 100 + b"\n")
        self.observer.update(6)
        self.assertFalse(self.observer.travel_started)
        self.botlife.write_bytes(b"BotLife travel-test guid=6 event=start\n")
        self.observer.update(6)
        self.assertTrue(self.observer.travel_started)

    def test_failed_result_does_not_verify_travel(self):
        self.botlife.write_bytes(b"BotLife travel-test guid=6 event=finish result=failed failure=Timeout\n")
        self.observer.update(6)
        self.assertEqual(self.observer.travel_result, "failed")
        self.assertFalse(self.observer.travel_verified)

    def test_work_per_update_is_bounded(self):
        self.botlife.write_bytes(b"x" * self.observer.SAMPLE_BYTES + b"\n"
                                b"BotLife travel-test guid=6 event=start\n")
        self.observer.update(6)
        self.assertFalse(self.observer.travel_started)
        _, offset, tail = self.observer.cursors[self.botlife]
        self.assertEqual(offset, self.observer.SAMPLE_BYTES)
        self.assertLessEqual(len(tail), 4096)
        self.observer.update(6)
        self.assertTrue(self.observer.travel_started)


if __name__ == "__main__":
    unittest.main()
