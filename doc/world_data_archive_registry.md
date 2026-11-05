# World data archive registry

## Purpose

This document is the repository-wide inventory of world database rows moved to
`*_archive` tables. Archiving is used when a row is historically useful or may
be needed for future implementation work, but must not be consumed by the
current MoP 5.4.8 server.

An archive is not a trash table. It preserves the original payload and the
reason for taking it out of the active loader. Some archived rows can be
reinserted after their supporting content is restored; others are forensic
snapshots of invalid values and must never be restored verbatim.

The inventory below was reconstructed from the complete Git history containing
world archive tables and checked against the current `world` database on
2026-10-15. The current achievement update was additionally tested on isolated
normal and archive-conflict schemas.

## Archive states

| State | Meaning | Restoration rule |
| --- | --- | --- |
| Dormant content | A complete row was removed from its active table | Reinsert only after the corresponding MoP mechanic, client record or intentional custom content exists |
| Disabled binding | Data points at an absent, retired or unsafe script | Restore only together with a verified and registered implementation |
| Forensic snapshot | The active row remains, but a corrupt field was repaired | Never reinsert the archived row; use it only to audit or reverse a specific field change |
| Repaired payload | The archived copy records the old binding while a safe payload remains active | Do not insert over the active primary key; restore only the verified field |

There is deliberately no universal “restore every archive” update. The rows
belong to different game versions and failure modes. Restoring all of them would
reintroduce startup errors and, in several cases, broken gameplay.

## Git history

| Date | Commit | Archive work |
| --- | --- | --- |
| 2026-10-01 | `a152ad885cb2036bd413ad8a999cc01cfe55a7ab` | Legacy escort routes and the incorrect permanent Winter Veil quest starter |
| 2026-10-01 | `780ed7b7d816384200ce3392ac359f7dc5f998f1` | Post-MoP quest objectives and their locale rows |
| 2026-10-02 | `ffe5e9ee3ef7adb8b4985b587c0960fa5e6ebd6d` | Obsolete starting skills and retired empty quest POI headers |
| 2026-10-03 | `f80a97ea81d651e586fd90da1d898c8d0eb03c53` | Missing/unsafe script bindings and invalid numeric script names |
| 2026-10-09 | `6df5562b0a829f9d68af0481779b828368c92aa1` | Duplicate unspawned quest ender |
| 2026-10-11 | `a9e1d7a60e030aa0aa9d958a7c2cea6e1d2c8663` | Duplicate Gobber creature spawn |

The current addition is
`sql/updates/world/2026_10_15_00_archive_legacy_achievement_data.sql`. It reuses
the criteria archive created on October 3 and adds the reward-locale archive.

## Inventory

### `script_waypoint_legacy_archive`

Source: `script_waypoint`. State: dormant content.

| Creature entry | Archived points | Reason |
| ---: | ---: | --- |
| `349` | 115 | Corporal Keeshan route for obsolete quest 219; NPC has no spawn in this MoP world |
| `1754` | 17 | Lord Gregor Lescovar event for obsolete quest 434; NPC has no spawn |
| `3849` | 14 | Old Shadowfang prisoner route; NPC has no spawn |
| `3850` | 14 | Old Shadowfang prisoner route; NPC has no spawn |
| `4962` | 7 | Tapoke “Slim” Jahn route for deprecated quest 1249 |
| `6575` | 12 | Scarlet Trainee route from the pre-MoP Herod encounter; NPC has no spawn |
| `8856` | 18 | Tyrion's Spybot route for obsolete quests 2745/434; NPC has no spawn |
| `17238` | 26 | Anchorite Truuen route for deprecated quest 9446; incomplete for the old 41-point implementation |
| **Total** | **223** | |

Introduced by
`2026_10_01_02_archive_retired_escort_routes.sql`. That first migration used a
broad entry-based delete after `INSERT IGNORE`; this is weaker than the later
exact-match convention. Update `03` restored all eight routes for audit, update
`05` re-archived the six unspawned entries, and update `08` retired entries
4962/17238 after validating their full point payload and quest/script guards.

Restore by selecting only the intended entry from the archive into
`script_waypoint`, after restoring or deliberately implementing its quest or
encounter script. Do not restore all 223 points as a group.

### `creature_queststarter_legacy_archive`

Source: `creature_queststarter`. State: dormant erroneous relation.

| NPC | Quest | Reason |
| ---: | ---: | --- |
| `1362` | `7062` | Gothor Brumn is not the quest giver; the correct seasonal relation is event 2, NPC 1365 (Goli Krumn) |

Introduced by `2026_10_01_06_fix_winter_veil_questgiver.sql`. Restore only if
intentionally creating custom behavior for NPC 1362; it is not the verified MoP
Winter Veil relation.

### `quest_objective_post_mop_archive`

Source: `quest_objective`. State: dormant foreign-version data.

| Quest | Objective ID | Index | Type | Object | Amount | Flags | Description |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `10794` | `273866` | 0 | 1 | `113135` | 1 | 0 | empty |
| `11997` | `280563` | 0 | 0 | `99418` | 1 | 0 | Mage Portal Taken |
| `11997` | `280564` | 1 | 0 | `100290` | 1 | 34 | Obtain Felo'melorn |

These exact objectives came from later client builds 19865 and 22522, while the
local quests are deprecated/reuse MoP build-15595 records. Introduced by
`2026_10_01_09_archive_post_mop_quest_objectives.sql`.

### `quest_objectives_locale_post_mop_archive`

Source: `quest_objectives_locale`. State: dormant foreign-version data.

| Objective ID | Archived locales |
| ---: | ---: |
| `273866` | 0 |
| `280563` | 10 |
| `280564` | 10 |
| **Total** | **20** |

Restore locale rows only after restoring the matching objective and moving the
server/client content target to the version that owns it.

### `playercreateinfo_skills_legacy_archive`

Source: `playercreateinfo_skills`. State: dormant legacy data.

All 36 SkillLine IDs are absent from the original MoP 5.4.8 client DBCs. They
were rejected by the loader and never populated `PlayerInfo`.

| Class mask | Count | SkillLine IDs |
| ---: | ---: | --- |
| 1 (Warrior) | 4 | `26, 256, 257, 803` |
| 2 (Paladin) | 3 | `184, 267, 594` |
| 4 (Hunter) | 3 | `50, 51, 163` |
| 8 (Rogue) | 4 | `38, 39, 253, 797` |
| 9 (Warrior/Rogue Thrown overlap) | 1 | `176` |
| 16 (Priest) | 3 | `56, 78, 613` |
| 32 (Death Knight) | 3 | `770, 771, 772` |
| 64 (Shaman) | 4 | `373, 374, 375, 801` |
| 128 (Mage) | 4 | `6, 8, 237, 799` |
| 256 (Warlock) | 4 | `354, 355, 593, 802` |
| 1024 (Druid) | 3 | `134, 573, 574` |

Introduced by `2026_10_02_00_archive_legacy_start_skills.sql`. Restore only if
the target client DBC contains those SkillLine records and the core consumer is
verified for them; do not substitute modern class skills into these rows.

### `quest_poi_retired_archive`

Source: `quest_poi`. State: dormant retired data.

| Quest | Idx1 | Objective index | Map | World-map area | Flags | Reason |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `3379` | 1 | -1 | 0 | 28 | 3 | Empty POI header on a deprecated build-15595 quest |
| `10216` | 1 | 1 | 530 | 478 | 7 | Empty POI header on a deprecated build-15595 quest |
| `29178` | 0 | -1 | 568 | 781 | 7 | Empty POI header on a deprecated build-15595 quest |

All three have `QuestObjectiveId=0`, `Floor=0`, `Priority=0` and
`VerifiedBuild=0`, with no matching POI points. Introduced by
`2026_10_02_01_archive_retired_quest_poi.sql`. Restore only with valid point
rows and an intentionally reactivated quest.

### `achievement_criteria_data_disabled_archive`

Source: `achievement_criteria_data`. State: disabled bindings/conditions. This
table is shared by two updates.

The October 3 update archived four `type=11` bindings whose named handler is
absent while the encounter awards the achievement directly:

| Criteria IDs | Value payload | Archived script |
| --- | --- | --- |
| `12777, 13079, 13080, 13081` | `value1=0, value2=0` | `achievement_im_on_a_boat` |

The October 15 update adds 21 rows:

- 17 difficulty rows: criteria
  `6803, 7315, 7318, 7319, 7320, 7361, 7363, 7579, 7583, 7587, 7590,
  7593, 7598, 11789, 12752, 12976, 12993`, all with
  `type=12, value1=1, value2=0, ScriptName=''`. Each criterion already has the
  MoP client ModifierTree `INSTANCE_DIFFICULTY` condition.
- 4 empty script hooks: criteria `7231, 7321, 16081, 16848`, all with
  `type=11, value1=0, value2=0, ScriptName=''`. Keleseth and Volkhan award the
  result directly; Ashbury and Mandokir update the active ModifierTree state.

On the audited base the archive therefore contains 25 rows after the current
update. Restore a group only after restoring its missing core path. The current
achievement subset has a guarded manual restore script described below.

### `areatrigger_scripts_disabled_archive`

Source: `areatrigger_scripts`. State: disabled binding.

| Entry | Script | Reason |
| ---: | --- | --- |
| `7144` | `at_well_of_eternity_skip_illidan_intro` | Disabled source path can close the route before the first trash pack |

Introduced by `2026_10_03_00_repair_script_bindings.sql`. Restore only after the
route logic is implemented and tested.

### `spell_script_names_disabled_archive`

Source: `spell_script_names`. State: disabled bindings.

| Spell | Script | Reason |
| ---: | --- | --- |
| `38528` | `spell_protection_of_elune` | Retired/unregisterable local AuraScript |
| `85084` | `spell_howling_gale_howling_gale` | Handler is a no-op with its effects commented out |

Restore only together with verified implementations.

### `spell_areatrigger_template_disabled_archive`

Source: `spell_areatrigger_template`. State: repaired payload.

| Entry | Geometry | Archived script | Active state |
| ---: | --- | --- | --- |
| `742` | flags 0, collision 0, radius 7, scales 0/0 | `sat_icy_shadows` | Geometry restored by update `2026_10_03_01`; `ScriptName` intentionally empty |

Do not insert the archived row over entry 742. If a working script is later
implemented, update only the active `ScriptName` after registration and tests.

### `conditions_invalid_script_archive`

Source: `conditions`. State: forensic snapshot.

The six active declarative conditions were retained; only the invalid numeric
`ScriptName='0'` was cleared.

| Source type | Source entry | Condition type | Values | Archived script |
| ---: | ---: | ---: | --- | --- |
| 17 | `52410` | 22 | `607,0,0` | `0` |
| 17 | `52418` | 22 | `607,0,0` | `0` |
| 17 | `117866` | 22 | `996,0,0` | `0` |
| 17 | `126845` | 9 | `31496,0,0` | `0` |
| 17 | `126845` | 23 | `6435,0,0` | `0` |
| 17 | `139603` | 29 | `70388,5,0` | `0` |

These archive rows must not be inserted into `conditions`: the active rows
already exist, and `0` is not a script identifier.

### `gameobject_invalid_script_archive`

Source: `gameobject`. State: forensic snapshot.

| GUID | Entry | Map | Position | Archived script |
| ---: | ---: | ---: | --- | --- |
| `20936` | `200004` | `1064` | `6710.24, 6481, 0.00256714` | `1` |

The spawn remains active with an empty `ScriptName`. Do not reinsert this row or
restore numeric `ScriptName='1'`.

### `creature_questender_disabled_archive`

Source: `creature_questender`. State: dormant erroneous relation.

| NPC | Quest | Reason |
| ---: | ---: | --- |
| `58507` | `31713` | Unspawned duplicate; active Ace Longpaw 58506 completes the quest |

Introduced by `2026_10_09_00_fix_questender_npcflags.sql`. Restore only if NPC
58507 is intentionally made the quest ender.

### `creature_duplicate_spawn_archive`

Source: `creature`. State: dormant duplicate spawn.

| GUID | Entry | Map | Position | Reason |
| ---: | ---: | ---: | --- | --- |
| `371766` | `36613` | `648` | `-8179.37, 1321.39, 27.6083` | Banker variant overlapped the intended quest-facing Gobber 34954 |

Introduced by `2026_10_10_00_remove_duplicate_gobber_spawn.sql` in commit dated
October 11. Restore only if the overlapping banker is intentionally required;
the row is otherwise complete and can be selected back by GUID.

### `achievement_reward_locale_retired_archive`

Source: `achievement_reward_locale`. State: dormant retired data. Introduced by
`2026_10_15_00_archive_legacy_achievement_data.sql`.

| Retired achievement ID | Locale rows | Reason / active status |
| ---: | ---: | --- |
| `1681` | 5 | Alliance Loremaster text retained for a future faction-aware reward for active achievement 7520 |
| `1682` | 5 | Horde Loremaster text retained for a future faction-aware reward for active achievement 7520 |
| `2145` | 6 | Retired faction-era ID; archived only when text exactly matches active reward 2144 |
| `3656` | 4 | Retired faction-era ID; archived only when text exactly matches active reward 3478 |
| `4784` | 4 | Retired Alliance emblem-quartermaster achievement absent from client 5.4.8.18414 |
| `4785` | 4 | Retired Horde emblem-quartermaster achievement absent from client 5.4.8.18414 |
| **Total** | **28** | |

The 1681/1682 rows are evidence, not a complete solution. The current reward
schema has one common sender, subject and body for both factions, so restoring a
Horde-only Cairne letter for achievement 7520 would send incorrect mail to
Alliance characters.

## Related active restoration

Achievement 2796 (Brew of the Month) is an active 5.4.8 achievement, not an
archive candidate. The October 15 update restores its verified welcome mail
from sender 27487 only when that sender exists and no reward row is already
configured. Existing/custom data is never overwritten; its existing `deDE` and
`zhCN` locale rows remain active.

## Manual restoration procedure

Before restoring anything:

1. Stop the world server or use an isolated copy of the database.
2. Identify one archive table and the exact keys to restore.
3. Verify that no active row or custom payload conflicts with those keys.
4. Restore the supporting script, quest, DBC/client record or intentional
   custom behavior first.
5. Insert only the selected rows inside a transaction, then run startup and
   gameplay checks. Keep the archive copy as provenance.

The current achievement data has a non-automatic helper:

```text
sql/archive/world/2026_10_15_00_restore_legacy_achievement_data.sql
```

It restores only the 21 October 15 criteria rows and the 28 retired locale rows
with `INSERT IGNORE`; it does not touch the four October 3 criteria rows and does
not remove archive copies. On the current core it intentionally reintroduces the
associated startup diagnostics, so it is for audit/reproduction or use after
the corresponding implementation changes.

Preview that subset before restoration:

```sql
SELECT *
FROM `achievement_criteria_data_disabled_archive`
WHERE `criteria_id` IN
      (6803,7315,7318,7319,7320,7361,7363,7579,7583,7587,7590,7593,7598,
       11789,12752,12976,12993,7231,7321,16081,16848);

SELECT *
FROM `achievement_reward_locale_retired_archive`
WHERE `ID` IN (1681,1682,2145,3656,4784,4785)
ORDER BY `ID`, `Locale`;
```

To undo the newly inserted reward 2796 separately, delete it only if every
field still matches the migration payload. Never delete an operator-customized
row. Its locale rows were not archived and must not be removed.

## Safety of the current achievement update

The October 15 migration is reapplicable and conflict-preserving:

- criteria and locale deletes require a full payload match with the archive;
- duplicate locale IDs 2145/3656 require an active replacement and identical
  subject/body text;
- a different row already occupying an archive primary key prevents deletion
  of the live row;
- reward 2796 is insert-only and preserves any existing configuration;
- no reward for achievement 7520 is created or modified.

Isolated tests covered initial apply, repeated apply, manual restoration,
re-archival after restoration, and deliberately conflicting criteria and locale
archive rows. In the conflict case both live rows remained active.

## Evidence and detailed audits

- `doc/quest_32592_and_legacy_escorts_audit.md` records the route-by-route
  escort investigation and the later user-approved retirement of entries 4962
  and 17238.
- `doc/startup_objectives_respawn_poi_audit.md` records the foreign-version
  objective provenance, DBC checks for starting skills and POI investigation.
- SkyFire commit
  [`0dcd42675454e43c7d8ebc086d0b9cc95da41fd4`](https://github.com/ProjectSkyfire/SkyFire_548/commit/0dcd42675454e43c7d8ebc086d0b9cc95da41fd4)
  removed database achievement difficulty requirements after those conditions
  moved to client data.
- Blizzard's archived
  [Brewfest overview](https://worldofwarcraft.blizzard.com/en-us/news/7237858/brewfest)
  confirms Brew of the Month as active content, while the exact reward payload
  is preserved in the
  [AzerothCore achievement reward base](https://github.com/azerothcore/azerothcore-wotlk/blob/master/data/sql/base/db_world/achievement_reward.sql).
