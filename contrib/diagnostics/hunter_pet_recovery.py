#!/usr/bin/env python3
"""Plan/apply guarded slot-255 recovery for offline random-bot Hunters.

Preserves every pet ID and related row. Keeps a valid current pet, otherwise
uses the uniquely most recently saved pet for Call Pet 1. Other pets go into
free stable slots 5..54; overflow and ambiguous/invalid owners remain untouched.
Credentials are read from worldserver.conf and never placed in argv or reports.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def plan_recovery(rows):
    owners = collections.defaultdict(list)
    for row in rows:
        owners[row["owner"]].append(row)
    changes, skipped, choices = [], [], []
    for owner, pets in sorted(owners.items()):
        lost = [p for p in pets if p["slot"] == 255]
        if not lost:
            continue
        sample = pets[0]
        registered = [p for p in pets if p["slot"] != 255]
        reason = None
        if sample["class"] != 3 or not re.fullmatch(r"RNDBOT\d+", sample["account_name"] or ""):
            reason = "not-random-hunter"
        elif sample["online"]:
            reason = "owner-online"
        elif len({p["slot"] for p in registered}) != len(registered):
            reason = "duplicate-existing-slots"
        elif any(p["type"] != 1 or not p["family"] or not (p["type_flags"] & 1) for p in lost):
            reason = "invalid-or-untameable-template"
        current = sample["current"]
        if current and not any(p["id"] == current for p in pets):
            reason = "current-pet-not-owned-hunter"
        if reason:
            skipped.extend({"id": p["id"], "owner": owner, "reason": reason} for p in lost)
            continue
        occupied = {p["slot"] for p in registered}
        ordered = sorted(lost, key=lambda p: (-p["savetime"], -p["id"]))
        active = None
        if 0 not in occupied:
            active = next((p for p in lost if p["id"] == current), None)
            selection = "saved-current-id"
            if active is None:
                newest = [p for p in ordered if p["savetime"] == ordered[0]["savetime"]]
                if len(newest) != 1:
                    skipped.extend({"id": p["id"], "owner": owner, "reason": "ambiguous-latest-pet"} for p in lost)
                    continue
                active = newest[0]
                selection = "only-pet" if len(lost) == 1 else "unique-latest-save"
            # Do not assume a historical exotic pet is compatible with today's spec.
            if active["type_flags"] & 0x10000:
                skipped.extend({"id": p["id"], "owner": owner, "reason": "active-exotic-needs-live-check"} for p in lost)
                continue
            changes.append({"id": active["id"], "owner": owner, "from": 255, "to": 0})
            choices.append({"owner": owner, "name": sample["owner_name"], "pet": active["id"], "reason": selection})
        free = iter(slot for slot in range(5, 55) if slot not in occupied)
        for pet in ordered:
            if active is not None and pet["id"] == active["id"]:
                continue
            slot = next(free, None)
            if slot is None:
                skipped.append({"id": pet["id"], "owner": owner, "reason": "stable-capacity-overflow"})
            else:
                changes.append({"id": pet["id"], "owner": owner, "from": 255, "to": slot})
    return {"changes": changes, "choices": choices, "skipped": skipped}


class Connection:
    def __init__(self, config, container):
        text = config.read_text()
        def setting(key):
            match = re.search(r'^\s*' + re.escape(key) + r'\s*=\s*"([^"\n]*)"', text, re.M)
            if not match:
                raise ValueError(f"Missing {key}")
            return match[1].split(";")
        _, _, self.user, self.password, self.characters = setting("CharacterDatabaseInfo")
        self.auth = setting("LoginDatabaseInfo")[-1]
        self.world = setting("WorldDatabaseInfo")[-1]
        self.bots = setting("PlayerbotsDatabaseInfo")[-1]
        self.databases = [self.auth, self.characters, self.world, self.bots]
        if not all(re.fullmatch(r"[A-Za-z0-9_]+", name) for name in self.databases):
            raise ValueError("Unexpected database identifier")
        self.command = ["podman", "exec", "-i", "-e", "MYSQL_PWD", container]
        self.env = dict(os.environ, MYSQL_PWD=self.password)

    def query(self, sql, timeout=120):
        connect_timeout = max(1, min(5, int(timeout)))
        result = subprocess.run([*self.command, "mysql", f"--connect-timeout={connect_timeout}", "-u", self.user,
                                 "--batch", "--raw", "--skip-column-names", self.characters],
                                input=sql, text=True, env=self.env, capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.replace(self.password, "<redacted>"))
        return result.stdout

    def snapshot(self):
        sql = f"""SELECT JSON_OBJECT('id',p.id,'owner',p.owner,'slot',p.slot,'entry',p.entry,
            'name',p.name,'savetime',p.savetime,'current',COALESCE(cur.pet_id,0),
            'owner_name',c.name,'class',c.class,'online',c.online,'account_name',a.username,
            'type',ct.type,'family',ct.family,'type_flags',ct.type_flags)
            FROM character_pet p LEFT JOIN characters c ON c.guid=p.owner
            LEFT JOIN `{self.auth}`.account a ON a.id=c.account
            LEFT JOIN character_pet_current cur ON cur.owner=p.owner
            LEFT JOIN `{self.world}`.creature_template ct ON ct.entry=p.entry
            WHERE p.PetType=1 ORDER BY p.owner,p.id;"""
        return [json.loads(line) for line in self.query(sql).splitlines()]

    def backup(self, directory):
        path = directory / "databases-before.sql.gz"
        if path.exists():
            raise FileExistsError(path)
        command = [*self.command, "mysqldump", "-u", self.user, "--single-transaction", "--routines",
                   "--events", "--triggers", "--hex-blob", "--set-gtid-purged=OFF", "--column-statistics=0",
                   "--databases", *self.databases]
        with (directory / "backup.stderr.log").open("wb") as errors, path.open("xb") as output:
            proc = subprocess.Popen(command, env=self.env, stdout=subprocess.PIPE, stderr=errors)
            with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=3) as compressed:
                while chunk := proc.stdout.read(1024 * 1024):
                    compressed.write(chunk)
            proc.stdout.close()
            if proc.wait() != 0:
                raise RuntimeError("Backup failed; see private backup.stderr.log")
        size = 0
        with gzip.open(path, "rb") as data:
            while chunk := data.read(1024 * 1024):
                size += len(chunk)
        if size < 1024 * 1024:
            raise RuntimeError("Backup unexpectedly small")
        with path.open("rb") as data:
            digest = hashlib.file_digest(data, "sha256").hexdigest()
        metadata = {"file": path.name, "bytes": path.stat().st_size, "uncompressed_bytes": size, "sha256": digest}
        (directory / "backup.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps({"backup": metadata}), flush=True)


def guarded_sql(changes):
    if not changes:
        raise ValueError("Empty recovery plan")
    values = ",\n".join(f"({r['id']},{r['owner']},{r['to']})" for r in changes)
    # All writes are transactional. CHECK deliberately aborts the mysql client
    # on any mismatch; connection close then rolls back the entire transaction.
    return f"""CREATE TEMPORARY TABLE pet_recovery_plan (
        id INT UNSIGNED PRIMARY KEY, owner INT UNSIGNED NOT NULL, slot TINYINT UNSIGNED NOT NULL,
        UNIQUE KEY owner_slot(owner,slot));
    INSERT INTO pet_recovery_plan VALUES {values};
    CREATE TEMPORARY TABLE pet_recovery_assert (ok INT NOT NULL CHECK(ok=1));
    START TRANSACTION;
    SELECT p.id FROM character_pet p JOIN pet_recovery_plan r ON r.id=p.id FOR UPDATE;
    INSERT INTO pet_recovery_assert SELECT IF(COUNT(*)={len(changes)},1,0)
        FROM character_pet p JOIN pet_recovery_plan r ON r.id=p.id AND r.owner=p.owner
        JOIN characters c ON c.guid=p.owner WHERE p.slot=255 AND p.PetType=1 AND c.class=3 AND c.online=0;
    INSERT INTO pet_recovery_assert SELECT IF(COUNT(*)=0,1,0)
        FROM character_pet p JOIN pet_recovery_plan r ON r.owner=p.owner AND r.slot=p.slot;
    UPDATE character_pet p JOIN pet_recovery_plan r ON r.id=p.id AND r.owner=p.owner
        SET p.slot=r.slot WHERE p.slot=255 AND p.PetType=1;
    INSERT INTO pet_recovery_assert SELECT IF(ROW_COUNT()={len(changes)},1,0);
    INSERT INTO pet_recovery_assert SELECT IF(COUNT(*)={len(changes)},1,0)
        FROM character_pet p JOIN pet_recovery_plan r ON r.id=p.id AND r.owner=p.owner AND r.slot=p.slot;
    COMMIT;
    SELECT 'RECOVERY_COMMITTED', COUNT(*) FROM pet_recovery_plan;
    """


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "backup", "apply"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--mysql-container", default="loa-mysql")
    args = parser.parse_args()
    os.umask(0o077)
    args.run.mkdir(parents=True, exist_ok=True)
    db = Connection(args.config, args.mysql_container)
    if args.mode == "backup":
        db.backup(args.run)
        return
    rows = db.snapshot()
    plan = plan_recovery(rows)
    if args.mode == "audit":
        for name, value in (("before.json", rows), ("plan.json", plan)):
            path = args.run / name
            if path.exists():
                raise FileExistsError(path)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        (args.run / "apply.sql").write_text(guarded_sql(plan["changes"]))
        print(json.dumps({"hunter_pets": len(rows), "slot255": sum(p["slot"] == 255 for p in rows),
                          "restore": len(plan["changes"]), "active_choices": len(plan["choices"]),
                          "choice_reasons": dict(collections.Counter(p["reason"] for p in plan["choices"])),
                          "unresolved": dict(collections.Counter(p["reason"] for p in plan["skipped"]))}, indent=2))
        return
    original = json.loads((args.run / "before.json").read_text())
    saved_plan = json.loads((args.run / "plan.json").read_text())
    if rows != original or plan != saved_plan:
        raise RuntimeError("Audit snapshot changed; prepare a new plan")
    metadata = json.loads((args.run / "backup.json").read_text())
    with (args.run / metadata["file"]).open("rb") as data:
        if hashlib.file_digest(data, "sha256").hexdigest() != metadata["sha256"]:
            raise RuntimeError("Backup checksum mismatch")
    # A local live worldserver could hold stale in-memory pet lists. Both the
    # host and the build container must be stopped before changing slot records.
    for command in (["pgrep", "-x", "worldserver"], ["podman", "exec", "loa-build", "pgrep", "-x", "worldserver"]):
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 1:
            raise RuntimeError("worldserver is running or its status could not be checked")
    result = db.query(guarded_sql(plan["changes"]))
    after = db.snapshot()
    expected = {r["id"]: r["to"] for r in plan["changes"]}
    if len(after) != len(rows):
        raise RuntimeError("Pet row count changed")
    for before, now in zip(rows, after):
        want = dict(before, slot=expected.get(before["id"], before["slot"]))
        if want != now:
            raise RuntimeError("Unexpected data change after recovery")
    (args.run / "after.json").write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n")
    (args.run / "apply.log").write_text(result)
    print(json.dumps({"restored": len(expected), "preserved_pets": len(after), "verified": True}))


if __name__ == "__main__":
    main()
