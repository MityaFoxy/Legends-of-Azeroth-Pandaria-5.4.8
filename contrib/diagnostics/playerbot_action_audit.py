#!/usr/bin/env python3
"""Audit observed Action resolution in a stopped server's complete log set.

This checks factory reachability, not spell effects or rotation quality. Ordinary
FAILED/IMPOSSIBLE/USELESS outcomes are reported, not treated as missing Actions.
"""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path


def audit_actions(logs):
    outcomes, unknown = Counter(), Counter()
    examples = {}
    files = sorted(logs.glob("PlayerbotBehavior.log*"))
    for path in files:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rb") as stream:
            for number, line in enumerate(stream, 1):
                if b" TRACE [playerbots.behavior] " not in line:
                    continue
                _, marker, decision = line.partition(b" decision=A:")
                if not marker:
                    continue
                action, separator, outcome = decision.rstrip().rpartition(b" - ")
                if not separator:
                    continue
                outcome = outcome.decode("utf-8", "replace")
                outcomes[outcome] += 1
                if outcome == "UNKNOWN":
                    action = action.decode("utf-8", "replace")
                    unknown[action] += 1
                    examples.setdefault(action, {"file": path.name, "line": number,
                                                 "text": line.decode("utf-8", "replace").rstrip()})
    return {"passed": bool(outcomes) and not unknown, "files": len(files),
            "action_decisions": sum(outcomes.values()), "outcomes": dict(outcomes),
            "unknown_count": sum(unknown.values()), "unknown_actions": dict(unknown.most_common()),
            "examples": examples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", type=Path)
    args = parser.parse_args()
    result = audit_actions(args.logs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
