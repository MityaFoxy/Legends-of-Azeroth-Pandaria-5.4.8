# Mana potion and shutdown persistence audit — 2026-11-06

Target: original MoP 5.4.8. Repair actual behavior, retain native validation.

## Verified native result — November 7, 11:08:27 MSK

`native-r4/audit-result.json` is PASS. Full -j4 build succeeded, then 100 level-60
bots were observed for 360 seconds after population readiness, with 12 diagnostic
rounds. Unit `loa-mana-shutdown-20261107-r4.service` and worldserver exited 0.
Binary SHA-256: `fdb8cf0d4d364a27a7c243aa653b65d203e9ebe0d37efb6fdde56747f57e0d78`.

The actual registered Action was invoked through the console fixture during
Mage 90's native combat. Item 2455 / spell 437, fixture GUID 428359: mana
4298 -> 4400, stack 2 -> 1, native readiness false, immediate repeat false and
remaining count still 1. The tracked remainder was removed; post-exit SQL
confirmed no item_instance or character_inventory reference. No characters
remained online after graceful shutdown; no worldserver process remains.
This verifies the concrete native potion and shutdown scenario, not every
supported potion or all historical persistence interleavings. No manual SQL
update, power grant or cooldown reset was used.

Complete two-file Behavior audit: 225123 decisions, 0 UNKNOWN. Other outcomes:
13170 FAILED, 144406 USELESS, 46103 IMPOSSIBLE, 17308 PREREQ, 4136 OK.
These are execution outcomes, not a claim that every rotation is correct.
Normal engine mana-potion fallback was not sampled here; its graph has bounded
coverage, while the separate fixture proves native item use. BG: 82 entered,
57 fought, 54 dealt damage, 26 resurrected; eight starting-area-locked Pandaren.
No full match/requeue, multi-level or full-server sanitizer claim. Positive
stay-line arrival remains pending. Installed runtime unchanged, no commit.
Evidence: `tests/mana-shutdown-20261106/native-r4/` in handoff.

## November 7 build artifact recovery

r3 failed at final link on November 6, 18:48:37 MSK, before any native test.
Four Black Temple AddSC definitions were missing from the link. All four exist
in unchanged source files, but their `.o` files were exactly zero bytes with
timestamps around the interrupted r1 build. Structural ELF checks of all 1544
objects found only these four invalid. Their exact paths and scan results are
in `object-integrity-20261107.json`; only these four empty outputs were removed.
Recompilation recreated all four, with definitions verified by `nm` and recorded
in `objects-rebuilt-20261107.json`. No script registration or gameplay source
was changed to work around the link error.

At 10:58:13 MSK, `loa-mana-shutdown-20261107-r4.service` started the existing
-j4 build and probe/audit chain through `resume_after_object_repair.py`.
Source-hash and offline preflight checks remain in place. Current result path
is `tests/mana-shutdown-20261106/native-r4/`; full build/native PASS is recorded above.
The following r1/r2/r3 execution details are historical.

## Historical execution after reboot — November 6

At the restart review, r1's build log ended at 77%, last written at
15:38:09 MSK, alongside the journal's boot transition. Both transient units
were absent; no successful build result or native-r2 directory existed.
The stale r1 `building` status is now `interrupted`, preserving its original.
Container startup commands were checked (build: sleep; database: mysqld),
both containers restarted, and offline preflight still found only the known
stale GUID 90. No SQL update was performed.

Since 18:33:55 MSK, `loa-mana-shutdown-20261106-r3.service` runs `resume_after_reboot.py`:
verify native source hashes match r1, resume incremental -j4 build in the
existing directory, run the same 360-second native probe, then audit it.
Current artifacts: `tests/mana-shutdown-20261106/native-r3/` in handoff.
The old r1-to-r2 continuation below is historical and no longer active.
Native acceptance remains pending. Closing VS Code does not stop the unit;
a computer shutdown/reboot does, and this transient unit does not auto-resume.

## Mana potion: evidence before implementation

The complete hour r3 had 5415 `mana potion / UNKNOWN`. The common Strategy
ActionNode and Mage Evocation, Shadow Priest Dispersion, Druid Innervate and
healer Shaman Mana Tide alternatives referenced it, but no Action existed.
The latest 665-UNKNOWN repair did not exercise this path.

Local `mana-items.tsv` and `mana-dbc.json` in handoff
`tests/mana-shutdown-20261106/` record exact templates, effects and DBC hashes.
Initial scope: ordinary direct mana potions 2455/437,3385/438,3827/2023,
6149/11903,13443/17530,13444/17531,22832/28499,40067/28499,33448/43186,
57192/78990,76098/105709. All have a native self-targeted mana energize effect;
item category 4 and category recovery 60000 ms. Do not hand-grant mana,
bypass native cooldowns or supply inventory during normal AI execution.
Special injectors, channelled/reusable/location-restricted potions are outside
this first slice. These local data/core checks are the mechanics evidence.

Comparative architecture only (not original retail proof):
[UseItemAction.cpp, pinned mod-playerbots source](https://github.com/mod-playerbots/mod-playerbots/blob/405f81196161017eebae3ee7a612d786a3ed2a9d/src/Ai/Base/Actions/UseItemAction.cpp)
uses a combat-only mana potion Action. Existing local callers own the low-mana
trigger threshold; this repair must retain their alternatives and priorities.
Use the strongest available permitted ordinary potion by required level, only
for a bot currently using mana and missing mana during combat. Native item use
owns consumable charges and held/category cooldowns. `Spell::SendSpellCooldown`
holds potion cooldown while in combat; `Player::UpdatePotionCooldown` releases
it after combat. Preserve that path and item/arena/ownership requirements.
Success must be an actual power increase or matching accepted pending cast.

## Shutdown: evidence before implementation

After three normal exit-0 probes, one character retained `online=1` with no
server process (GUID 53,64,90 respectively). `PlayerbotHolder::LogoutPlayerBot`
queues a save, then `WorldSession::LogoutPlayer` queues the logout save and
account-offline update. `Main` clears online flags synchronously before
`StopDB`; pending saves can still run after that clear.

More seriously, before this repair `DatabaseWorkerPool::Close` called `io_context.stop()`
before destroying workers. Waiting operations are abandoned. The real Close
and StartWorkerThread methods, compiled with real Boost.Asio and bounded SQL
storage, fail the new regression when 100 writes are waiting behind a blocked
worker. `db-before.log` records the failing expected-write assertion.
This proves queue loss, not the exact interleaving of every historical flag.

[Boost io_context documentation](https://www.boost.org/latest/doc/html/boost_asio/reference/io_context.html)
explicitly distinguishes aborting `stop()` from releasing the work guard and
allowing pending handlers to finish. Implemented narrow lifecycle repair:
move work ownership to the pool, release it and join **all** workers before
closing any connection, and clear final online flags after all database queues
have drained at StopDB. Producers must already be stopped; shutdown waiting
must not happen on an SQL worker thread. Preserve ordinary asynchronous saves
and do not replace this with a manual SQL sweep over live characters.

Verification: real worker/pool regression with 1 and 4 workers, queued writes
and a future, idempotent/partial shutdown; full -j4 build; detached native
potion effect/count/cooldown check and post-shutdown DB verification. These are
separate proof boundaries. Positive live stay-line arrival remains outstanding.

The worker thread ID is cached before the pool accepts work, remaining stable
while other workers drain and scan the connection vector. Reading the mutable
`std::thread` object while joining/resetting another worker would race.
Bounded GCC/Clang tests now also compile the real StopDB sequence and assert
all drains precede final synchronous cleanup and connection/library close.

Native unit `loa-mana-shutdown-20261106-r1.service` started the full `-j4`
build at 14:37:42 MSK. The continuation below will run a detached 360-second,
100-bot level-60 observation. No live acceptance yet.
The default-off `AiPlayerbot.ManaPotionDiagnostics` console fixture supplies a
uniquely tracked two-item stack to Mage 90 (verified free slot and no existing
potions), invokes the real Action during native
combat, records immediate mana/count/readiness and repeat refusal, then removes
only the remaining supplied item. It never edits mana, combat or cooldown.

## Corrected live-test selection and autonomous continuation

Previous native-r5 BG evidence shows Mage 68 entered but did not fight in the
short window; Mage 90 fought, died and resurrected. Current DB confirms Mage
90 at level 60, one free backpack slot, and no potions. The mana fixture now
targets 90. The r1 build is allowed to finish, with its test launch cancelled;
`Stop requested during build` is the expected handoff after successful build,
not live acceptance. `loa-mana-shutdown-20261106-r2.service` automatically
verifies the completed build, reuses its exact SHA, runs native-r2 and then
audits all logs plus actual mana gain/count/cooldown and post-stop SQL cleanup.
The old standalone r1 audit waiter was stopped. Runtime activation remains
out of scope. Test outcome is pending, not PASS.

Both deliberate shutdown mutations were detected: aborting queued work and
clearing online flags before draining. See `shutdown-mutations.json`.
Native compiler syntax checks passed for ManaPotionAction and Main with its
required worldPCH header; the first isolated Main check omitted that PCH and
was corrected in the harness only (`main-native-syntax.log` supersedes it).
Tracked native sources match the build-launch patch. Untracked native sources
and SHA hashes are preserved in r1/source-untracked and source-reviewed.json.
