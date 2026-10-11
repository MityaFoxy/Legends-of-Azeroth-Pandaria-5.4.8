#!/usr/bin/env python3
"""Continue an existing successful population gate with an unattended soak.

Runs inside loa-build as UID 0. Never retries failed runs or suppresses findings.
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--watch", type=Path, required=True)
    parser.add_argument("--hours", type=float, default=12)
    args = parser.parse_args()
    if args.hours <= 0:
        parser.error("hours must be positive")
    os.umask(0o077)
    args.watch.mkdir(parents=True, exist_ok=False)
    runner = Path(__file__).with_name("sanitizer_soak.py")
    source = Path(__file__).resolve().parents[2]
    git = ["git", "-c", "safe.directory=" + str(source), "-C", str(source)]
    revision = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()

    def source_fingerprint():
        digest = hashlib.sha256()
        digest.update(subprocess.check_output([*git, "diff", "HEAD", "--binary"]))
        untracked = subprocess.check_output(
            [*git, "ls-files", "--others", "--exclude-standard", "-z"]
        )
        for name in sorted(filter(None, untracked.split(b"\0"))):
            digest.update(name + b"\0")
            with (source / os.fsdecode(name)).open("rb") as file:
                digest.update(hashlib.file_digest(file, "sha256").digest())
        return digest.hexdigest()

    source_hash = source_fingerprint()

    def event(kind, **fields):
        record = dict(
            time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            event=kind,
            **fields,
        )
        with (args.watch / "events.jsonl").open("a") as output:
            output.write(json.dumps(record) + "\n")
        (args.watch / "status.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)

    try:
        event(
            "waiting_for_previous_gate",
            previous=str(args.previous),
            revision=revision,
            source_sha256=source_hash,
        )
        deadline = time.monotonic() + 8 * 3600
        while not (args.previous / "result.json").exists():
            if time.monotonic() > deadline:
                raise RuntimeError("Previous gate did not finish within eight hours")
            time.sleep(15)
        # The runner writes this once after shutdown and sanitizer-log checks.
        # Give a concurrently written JSON a short opportunity to finish.
        for attempt in range(5):
            try:
                previous = json.loads((args.previous / "result.json").read_text())
                break
            except json.JSONDecodeError:
                if attempt == 4:
                    raise
                time.sleep(1)
        if previous.get("event") != "complete":
            raise RuntimeError(
                "Previous gate failed; overnight run will not start: "
                + str(previous.get("error", previous))
            )
        current = subprocess.check_output(
            [*git, "rev-parse", "HEAD"], text=True
        ).strip()
        if current != revision:
            raise RuntimeError(
                "Source revision changed while waiting; review before starting"
            )
        if source_fingerprint() != source_hash:
            raise RuntimeError(
                "Working tree changed while waiting; overnight run will not start"
            )
        if args.run.exists():
            raise RuntimeError("Destination run already exists; refusing to overwrite")
        event("starting_staged_soak", run=str(args.run), hours=args.hours)
        with (args.watch / "runner.log").open("ab", buffering=0) as output:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    str(runner),
                    "--already-stopped",
                    "--build",
                    "/work/build-asan-ubsan",
                    "--jobs",
                    "2",
                    "--hours",
                    str(args.hours),
                    "--revision",
                    revision,
                    "--run",
                    str(args.run),
                ],
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            event("staged_soak_running", pid=process.pid, run=str(args.run))
            code = process.wait()
        result = json.loads((args.run / "result.json").read_text())
        if code or result.get("event") != "complete":
            raise RuntimeError("Staged soak failed; inspect " + str(args.run))
        event(
            "complete",
            run=str(args.run),
            message="Staged soak completed and worldserver stopped",
        )
    except BaseException as error:
        event("failed", error=str(error))
        raise


if __name__ == "__main__":
    main()
