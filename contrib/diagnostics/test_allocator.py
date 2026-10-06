"""Small allocator integration tests; run inside the build container."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]
FIXTURE = SOURCE / "contrib/diagnostics/allocator_smoke"


class AllocatorTests(unittest.TestCase):
    def configure(self, directory, *options, success=True):
        command = [
            "cmake",
            "-S",
            str(FIXTURE),
            "-B",
            directory,
            "-DLOA_SOURCE_DIR=" + str(SOURCE),
            *options,
        ]
        if os.environ.get("LOA_MIMALLOC_SOURCE"):
            command.append(
                "-DFETCHCONTENT_SOURCE_DIR_LOA_MIMALLOC="
                + os.environ["LOA_MIMALLOC_SOURCE"]
            )
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout)
        return result.stdout

    def smoke(self, allocator):
        with tempfile.TemporaryDirectory(prefix="loa-allocator-") as directory:
            self.configure(directory, "-DALLOCATOR=" + allocator)
            subprocess.run(
                ["cmake", "--build", directory, "--parallel", "2"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["ctest", "--test-dir", directory, "--output-on-failure"], check=True
            )

    def test_system_smoke(self):
        self.smoke("SYSTEM")

    def test_mimalloc_smoke(self):
        self.smoke("MIMALLOC")

    def test_auto_sanitizer_uses_system(self):
        with tempfile.TemporaryDirectory(prefix="loa-allocator-") as directory:
            output = self.configure(
                directory, "-DALLOCATOR=AUTO", "-DWITH_SANITIZER=ON"
            )
            self.assertIn("Server allocator: SYSTEM", output)

    def test_explicit_mimalloc_rejects_sanitizers(self):
        with tempfile.TemporaryDirectory(prefix="loa-allocator-") as directory:
            output = self.configure(
                directory, "-DALLOCATOR=MIMALLOC", "-DWITH_SANITIZER=ON", success=False
            )
            self.assertIn("Sanitizer builds require", output)

    def test_legacy_nojem_uses_system(self):
        with tempfile.TemporaryDirectory(prefix="loa-allocator-") as directory:
            output = self.configure(directory, "-DALLOCATOR=AUTO", "-DNOJEM=ON")
            self.assertIn("Server allocator: SYSTEM", output)

    def test_invalid_allocator_rejected(self):
        with tempfile.TemporaryDirectory(prefix="loa-allocator-") as directory:
            output = self.configure(directory, "-DALLOCATOR=JEMALLOC", success=False)
            self.assertIn("ALLOCATOR must be", output)


if __name__ == "__main__":
    unittest.main()
