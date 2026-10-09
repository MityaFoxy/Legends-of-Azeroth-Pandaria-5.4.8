#!/usr/bin/env python3
"""Host-side pre-finish temperature capture, timed from actual bot target entry."""

import argparse
import datetime
import json
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--bots", type=int, default=100)
    args = parser.parse_args()
    if args.bots < 1:
        parser.error("bot population must be positive")
    deadline = time.monotonic() + 18 * 3600
    while time.monotonic() < deadline:
        if (args.run / "result.json").exists():
            print(
                "Run ended before pre-finish capture; no under-load reading claimed",
                flush=True,
            )
            return
        events = args.run / "events.jsonl"
        if events.exists():
            rows = []
            for line in events.read_text().splitlines():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Concurrent append; retry on the next poll.
            if any(row.get("event") == "failure_detected" for row in rows):
                print(
                    "Run is stopping after a failure; pre-finish capture cancelled",
                    flush=True,
                )
                return
            started = next(
                (
                    row
                    for row in rows
                    if row.get("event") == "stage_started"
                    and row.get("phase") == "sanitizer"
                    and row.get("bots") == args.bots
                ),
                None,
            )
            reached = next(
                (
                    row
                    for row in rows
                    if row.get("event") == "target_reached"
                    and row.get("phase") == "sanitizer"
                    and row.get("bots") == args.bots
                ),
                None,
            )
            if started and reached:
                finish = datetime.datetime.fromisoformat(
                    reached["time"]
                ) + datetime.timedelta(hours=started["hours"])
                now = datetime.datetime.now(datetime.timezone.utc)
                if now >= finish - datetime.timedelta(minutes=2):
                    if now >= finish:
                        raise RuntimeError(
                            "Missed pre-finish window; no under-load reading claimed"
                        )
                    result = subprocess.run(
                        ["sensors"],
                        text=True,
                        capture_output=True,
                        timeout=10,
                        check=True,
                    )
                    status = (args.run / "status.json").read_text()
                    output = (
                        now.isoformat() + "\n" + result.stdout + "\n" + status + "\n"
                    )
                    # Never overwrite an existing diagnostic artifact.
                    with (args.run / "temperature-before-finish.log").open("x") as file:
                        file.write(output)
                    print(output, flush=True)
                    return
        time.sleep(15)
    raise RuntimeError("Timed out waiting for sanitizer stage")


if __name__ == "__main__":
    main()
