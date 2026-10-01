# Startup content audit — 2026-10-01

Scope: linked respawn GUID 10011, three invalid objectives on quests
10794/11997, and 16 POI headers lacking point rows. Original MoP 5.4.8 only.
Earlier work was committed separately as `a152ad88`.

## Foreign-version quest objectives: verified repair

The invalid rows are NOT missing MoP content. Exact source tuples exist in
TrinityCore's later-expansion imports:

- [2015_04_10_00_world.sql, line 636](https://github.com/TrinityCore/TrinityCore/blob/976d67be0556e08786660b307f20e6122e6646e0/sql/old/6.x/world/01_2015_03_21/2015_04_10_00_world.sql#L636):
  objective 273866, quest 10794, item 113135, build 19865 (WoD).
- [2016_09_02_00_world.sql, lines 4688–4689](https://github.com/TrinityCore/TrinityCore/blob/976d67be0556e08786660b307f20e6122e6646e0/sql/old/6.x/world/04_2016_10_17/2016_09_02_00_world.sql#L4688):
  objectives 280564/280563, quest 11997, creatures 100290/99418 and the
  Felo'melorn / mage-portal descriptions, build 22522 (Legion).

Our templates are still build 15595: retired rogue breadcrumb 10794 and
unused `REUSE` breadcrumb 11997, with text about speaking to Gryan Stoutmantle.
SkyFire's full MoP DB has those old templates without these three objectives;
its original 2014 objective import also does not contain these objectives.
alexkulya's 2023 full dump already contains the contaminated objective rows;
the exact historical import into this repository has not been established.

Migration 09 archives the three exact foreign tuples and their 20 locale rows,
then removes only matching archived payloads from the active tables. Quest
templates, relations, scripts and character progress are untouched. This does
not reactivate removed quests or claim they become playable in MoP. Custom
payloads and conflicting archival copies are preserved rather than overwritten.

## GUID 10011: restore the NPC, retain the linked respawn

Existing link: `(10011,136105,0)`; master 136105 is Lady Deathwhisper (36855),
map 631. Slave was absent, not merely rejected by the loader.

Sources:

- [MaNGOS Four creature.sql](https://github.com/mangosfour/database/blob/8b798ac6a6a51c0c00c7e20c0a864793eb53904c/World/Setup/FullDB/creature.sql#L302)
  retains exact GUID 10011, Deathspeaker Zealot 36808, position
  `(-587.632,2189.23,49.5599)`, orientation 2.70526, model 30357,
  respawn 7200, health 404430 and stationary movement.
- [MoPDB 5.4.7 creature.sql](https://github.com/gegge6265/MoPDB/blob/374358b13b9669e252c3b1035ea7a61c3670442f/World/creature.sql#L133012)
  independently preserves the same entry/position/orientation under GUID 201033.
- [AzerothCore creature.sql](https://github.com/azerothcore/azerothcore-wotlk/blob/master/data/sql/base/db_world/creature.sql)
  preserves the same entry/position/orientation under GUID 247133. Its GUID,
  respawn interval and difficulty representation are not imported.

The current world has no 36808 at that position under any GUID. Three surviving
36808 spawns (94092, 94093, 114722) match MaNGOS Four's positions/GUIDs; 114722
also retains the same 7200 respawn and 404430 health and links to the same boss.
Both historical models 30326/30357 exist in the current template-model table.

Migration 10 inserts only the missing spawn. Raid difficulties in this core are
bits 3–6, so the four-mode mask is 120, NOT the old 15. This matches the local
boss and other ICC mobs. Existing GUIDs or same-position spawns prevent insertion;
the expected master/link/model must exist. `VerifiedBuild=0`: a documented
reconstruction, not a newly captured packet. No linked-respawn row is deleted.

## Quest POI: still unresolved; data retained

Unresolved `(QuestID, Idx1)` pairs:

```
(3379,1) (6922,0) (6922,1) (8306,1) (10216,1) (11078,6)
(13892,0) (24591,2) (27228,2) (27316,0) (28170,1) (29151,0)
(29178,0) (29763,1) (29861,0) (32944,1)
```

Compared local headers/points with alexkulya's full 2023 dump, SkyFire full
26.002, MoPDB 5.4.7, MaNGOS Four, AzerothCore (applicable old quests), and
[TrinityCore's historical 2015 POI import](https://github.com/TrinityCore/TrinityCore/blob/976d67be0556e08786660b307f20e6122e6646e0/sql/old/6.x/world/01_2015_03_21/2015_04_05_03_world.sql).
No verified missing point set was recovered for the current header semantics.

Important index trap: old `(3379,id=1)` points are already represented by our
Idx1=0 turn-in; the seemingly matching `(6922,id=0)` point is inside map 48
and belongs to our Idx1=2, NOT the missing map-1 marker. Reusing them would put
coordinates under the wrong header. The 2015 source has the same missing sets;
its 32944/Idx1=1 header additionally has WoD WorldEffectID=1116 and shares
BlobIndex=0, but no point rows. This does not establish safe MoP duplication
or justify removing every empty header. No points were fabricated, no headers
deleted, and no loader warning was suppressed.

Search limitation: these are the inspected public dumps/history, not an
exhaustive search of every private sniff, branch or fork. Next useful evidence
is an original MoP quest-POI packet capture matching the map/objective/floor,
or another independently populated historical database. Do not infer a polygon
from present-day NPC coordinates alone.

## Validation

- Backup: `/home/user/wow-mop-build/db-backups/world-before-quest-objectives-icc-20261001.sql.gz`;
  seven complete tables, `gzip -t` passed.
- Isolated DB `world_startup_content_audit_20261001`: first and repeated
  application of migrations 09/10 passed. Only three objectives and 20 locales
  were removed from active data (archived exactly); only one creature added.
  Full-column binary comparisons found no other changed existing rows in all
  seven tables. Quest templates, NPC templates/models and respawn links unchanged.
- Archive-conflict test retained the objective. Custom objective flags=99 and
  existing spawn npcflag=123 survived reapplication; the agent-owned test fixture
  was restored afterwards. All 20 archived translations match byte-for-byte.
- Normal updater applied 09 and 10; both are `RELEASED` in live `world.updates`.
  Runtime initialized in 17 seconds. Full stdout:
  `/tmp/mop-objectives-icc-startup-20261001.log`. Zero missing-GUID-10011 or
  invalid-objective-10794/11997 warnings; all 16 unresolved POI warnings remain.
  The test process was stopped; bot autologin restored to 1. Canonical paths
  and worldserver configuration unchanged. No in-client encounter playthrough.
- Read-only verification SQL: `contrib/tests/startup_objectives_icc_checks.sql`.
  All six repair checks passed in live world; unresolved POI count is 16.
  Live post-updater data matches the tested copy across all seven tables:
  zero differing rows and zero count differences.

Temporary reproducibility artifacts: `/tmp/mop-startup-source-extract.py`,
`/tmp/mop-startup-fixture.sql`, `/tmp/mop-startup-compare.sql`,
`/tmp/mop-startup-guard-tests.sql`.
