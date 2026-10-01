# Quest 32592 and legacy escort audit — 2026-10-01

Target: original MoP 5.4.8. Restore verified content; retain existing data.

## Quest 32592: I Need a Champion

### Before the repair

Live `world` has Wrathion 69782 and both quest relations, but no template,
addon, objective, POI, offer-reward or request-items row for 32592. Existing
translations are present and must be preserved. Quest 32591 already has
`PrevQuestID=32590, NextQuestID=32593, ExclusiveGroup=-32591`; its missing
parallel member allows the core's each-from-all dependency check to pass
without the reputation quest. No original deletion cause has been established.

### Evidence and version mapping

- [SkyFire's original 2014-09-04 objective import](https://github.com/ProjectSkyfire/SkyFire_548/blob/d960ac405d1ec708ec918c001140010b0adb21ad/sql/old/5.4.8/world/SFDB_release_7_to_8/2014_09_04_02_world_quest_objective.sql#L15954):
  `(32592,270242,255,6,1359,42000,0,...)`. Index 255 becomes signed -1 in our
  schema. This is actual MoP-era implementation evidence, not a retail-era
  guess about the objective ID.
- [TrinityCore's 2014-12-29 template import](https://github.com/TrinityCore/TrinityCore/blob/976d67be0556e08786660b307f20e6122e6646e0/sql/old/6.x/world/00_2014_10_19/2014_12_29_00_world.sql#L3400):
  the retained build-19034 template supplies text, level 90, legendary category,
  flags 45088768/256, reward spell 139524 and faction reward index 5. It is a
  WoD source, so it is NOT imported wholesale: its bonus money 103800 is
  inappropriate for MoP. Its adjacent 32591/32593 records share the same
  level/reward structure as their existing build-18414 counterparts here.
- Local `QuestV2.dbc`: 32592 exists, unique bit 14815. Local `QuestXP.dbc`:
  level 90/difficulty 6 = 294000 XP. Local `QuestFactionReward.dbc`:
  positive reward index 5 = 250. Local `Spell.dbc`/`SpellEffect.dbc`: 139524
  exists as "Play Event after turning in Reputation Quest", self-targeted
  script effect 77. These verify client compatibility, not the missing RP script.
- [Original 2013 5.4 quest-chain guide](https://www.wowhead.com/news/mists-of-pandaria-legendary-cape-guide-updated-for-5-4-217993)
  corroborates the Exalted objective and its parallel material-gathering quest.
  [Historical quest documentation](https://warcraft.wiki.gg/wiki/I_Need_a_Champion)
  records level 90, 294000 XP, +250 Black Prince reputation, 24g72s and the
  next quest The Thunder Forge. The money mapping is the same as local 32591:
  base 228000, max-level reward 247200. The core takes their maximum at cap.
- [TrinityCore's preserved POI](https://github.com/TrinityCore/TrinityCore/blob/976d67be0556e08786660b307f20e6122e6646e0/sql/old/6.x/world/01_2015_03_21/2015_04_05_03_world.sql):
  map 870, world-map area 873, point (832,-167), matching local 32591.
- [Historical progress and completion dialogue](https://wowpedia.fandom.com/wiki/I_Need_a_Champion)
  agrees with the Russian reward text in alexkulya's 2023-03-04 database.
- [Existing recovery in ingussuveiks-dev's fork](https://github.com/ingussuveiks-dev/Legends-of-Azeroth-Pandaria-5.4.8/blob/160f07e7394bbda64eac8ffb07b617491b585b56/sql/updates/world/2026_07_17_00_world_restore_quest_32592.sql)
  led to the original SkyFire source. This is a reconstruction using the same
  sources, not an independent original sniff. Our migration uses explicit
  fields, preserves existing/custom definitions, and adds the quest dialogue.

`VerifiedBuild=0` intentionally records that this is a documented reconstruction,
not a falsely labelled original-18414 packet capture. Unused fields use neutral
schema defaults. Existing starter/ender links and locale rows are untouched.

### Implementation and test plan

`sql/updates/world/2026_10_01_07_restore_wrathion_quest_32592.sql` adds seven
rows in a transaction. It fails on unexpected partial state or a colliding
objective ID and does nothing if a template already exists. It returns 32592
to the existing negative dependency group, requiring BOTH 32591 and 32592
before 32593. Exalted is a completion condition, not an acceptance gate.

Validate on isolated table copies: first apply, repeated apply, custom-template
preservation, failed preconditions without partial writes, unchanged old rows.
Check the core's actual reputation/dependency methods at 41999/42000 and all
four combinations of the two predecessor quests. Then run the normal updater
and verify the loaded quest and startup diagnostics. Full client playthrough
must be distinguished from these database and core-logic checks.

### Remaining limits

The optional conversation between Wrathion and Anduin is not implemented by
the local NPC script. Correction after the follow-up search: the documented
Thunder King conversation occurs on accepting both 32591 and 32592, not on
rewarding 32592. Do not conflate it with reward spell 139524, whose exact
event remains unidentified. That spell has neither a local spell script nor a
`spell_scripts` payload. No timing/dispatch is invented here. The upstream
prerequisite chain makes 32590 mandatory, whereas historical sources describe
optional breadcrumbs; this pre-existing wider-chain discrepancy is not silently
changed as part of recovering the missing row.

## NPC 4962 and NPC 17238

These are **not verified missing active MoP escort quests**. They have legacy
route data, but quest 1249 (Tapoke) and 9446 (Truuen) both have `Flags=16386`
in local build-15595 data, including `QUEST_FLAGS_DEPRECATED=16384`. Neither
NPC has an active questgiver/ender relation for the retired escort.

- [Tomb of the Lightbringer history](https://warcraft.wiki.gg/wiki/Tomb_of_the_Lightbringer)
  dates removal to 4.0.3a. [Truuen's NPC page](https://warcraft.wiki.gg/wiki/Anchorite_Truuen)
  distinguishes the surviving NPC from his removed quests.
- [The Missing Diplomat in MoP Classic](https://www.wowhead.com/mop-classic/quest=1249/the-missing-diplomat)
  marks the quest obsolete; [Slim's Friend history](https://warcraft.wiki.gg/wiki/Slim%27s_Friend)
  dates the companion's removal to 4.0.3a. Classic-era comments on an MoP
  database page do not prove MoP availability.
- MaNGOS Four ScriptDev3 at server commit
  `27b6bdf2e08784abd0d1614bb1b06fab2f1c3936` contains old quest-driven scripts.
  Mikhail starts Tapoke's route only on accepting 1249. Truuen starts only
  on accepting 9446; that implementation needs waypoint 38 to grant credit
  and continues through 41, while our route contains only 26 points.
  Binding it to our path would not complete even the old escort correctly.

Original decision: preserve all 7/26 route points and both NPC spawns; retain
the loader warnings pending the user's decision. No verified MoP event justified
activating these old escort scripts. Re-enabling pre-Cataclysm quests would be
custom content, not restoration of confirmed 5.4.8 behavior. This is a scoped
negative finding, not a claim that no private/unknown source can ever exist.

Follow-up user approval: retire the old pre-MoP scripts. Migration
`2026_10_01_08_archive_two_retired_escort_routes.sql` removes ONLY these 33
points from the active `script_waypoint` table, retaining their exact existing
copies in `script_waypoint_legacy_archive`. There were no bound C++ scripts
for these two NPCs to remove. NPC templates, spawns and quest rows are unchanged.
The migration fails on custom script/AI/quest bindings, nondeprecated quests or
any differing archive payload. No previous migration was edited.

Tests: isolated first/repeated apply passed; zero unrelated row differences,
zero archive mismatches. An injected archive conflict correctly failed and
retained all 33 active points. Normal updater applied 08 (`RELEASED`); live
active count is zero, archive counts are 7/26, and both NPCs retain one spawn.
Repeat startup captured in full at `/tmp/mop-two-routes-startup-20261001.log`:
world initialized in 16 seconds, zero `TSCR:` lines. This repeat capture avoids
relying on the first tool response, which was truncated. Test server stopped;
original bot-autologin setting restored. Canonical launch paths unchanged.

## Follow-up search: Wrathion / Anduin conversation

The earlier claim that the dialogue itself was unavailable was too broad.
Confirmed local evidence exists in `broadcast_text` IDs 72311–72320,
`VerifiedBuild=18019`, all with sound mappings:

| Speaker | Broadcast IDs | SoundEntries IDs |
| --- | --- | --- |
| Wrathion | 72311, 72312, 72314, 72317, 72319 | 36071, 36072, 36073, 36074, 36075 |
| Anduin | 72313, 72315, 72316, 72318, 72320 | 35311, 35312, 35313, 35314, 35315 |

These rows also exist in the repository's historical
`sql/old/Merged to World DB 30_12_2023/2022_11_29_00_broadcast_text.sql`.
Their emote delays are zero; those fields do not supply conversation timings.
An independent original-2014 import also preserves them:
[TrinityCore 2014_03_30_06_world_broadcast_text.sql](https://github.com/TrinityCore/TrinityCore/blob/976d67be0556e08786660b307f20e6122e6646e0/sql/old/3.3.5a/TDB53_to_TDB54_updates/world/2014_03_30_06_world_broadcast_text.sql#L71422).
Its directory name is not the content version: the actual rows are build 18019.
Both NPCs (69782/69257) have no local `creature_text` rows. The Wrathion script
only handles accepting The Thunder Forge; Anduin has no bound script.

[Quest transcript](https://warcraft.wiki.gg/wiki/I_Need_a_Champion) places the
conversation after accepting BOTH parallel quests. This is documentary evidence,
not an independently observed packet-level dispatch condition. A
[2013-02-09 publication](https://www.wowchakra.com/wow/cinematica-wrathion-anduin-tweets-azules-y-noticias)
embeds [a chapter III introduction recording](https://www.youtube.com/watch?v=k5qyc8rEYJ8).
The video link/title were verified via its embed and YouTube oEmbed; playback
was unavailable to the browsing tool, so no timestamps or trigger observations
are claimed from it. PTR introduction footage must not be assumed to depict
the exact acceptance conversation without viewing it.

Expanded public-fork scan: 2167 distinct SQL/Pandaria/Spells blobs from the
previously enumerated 81 default heads, searching reward spell 139524,
distinctive dialogue and quest enum names. Only the existing broadcast import
and quest-restoration reward reference matched; no scene implementation found.
The earlier numeric-quest scan also found no implementation in the selected
zone scripts. Additional C++ searches in JadeCore548 (`f7b83aa95c113cc180f273f82c79832424714315`),
WoDCore (`7c00f9a8a4f3a26c6dc23f9f0207b6c561983bba`), SkyFire and historical
TrinityCore found no matching implementation. LegionCore
[`9222216e0dda0708ae53e6e6f6b07db7d65ba46f`](https://github.com/dufernst/LegionCore-7.3.5/tree/9222216e0dda0708ae53e6e6f6b07db7d65ba46f)
Pandaria/Spells scripts and world updates also yielded no scene implementation;
its zipped full world database was not scanned. This is not an exhaustive
claim about all private repositories, branches or packet archives.

Remaining evidence gap: verified timing, precise dispatch/replay/visibility
behavior and the identity of the event behind reward spell 139524. Existing
broadcast texts are preserved; no fabricated timer sequence or reward hook
was installed. A readable original-era recording or packet capture could
resolve this gap.

## Search coverage

Read the default branch heads of all 81 public forks returned by GitHub for
the Legends-of-Azeroth upstream: 50 distinct heads, 1073 distinct SQL and
selected zone-script blobs scanned. Found the 32592 recovery above; another
fork only deletes the relations and is rejected as a repair. This does not
claim coverage of every nondefault branch, deleted/private fork or archive.
Temporary reproducibility artifacts: `/tmp/mop-quest-forks-audit.json` and
`/tmp/mop-quest-fork-hits.json`.

Also inspected PandaEMU, MaNGOS Four server/database, SkyFire's current full
DB and original 2014 updates, JadeCore548 SQL, MoPDB 5.4.7, InfinityCoreDB
(actually earlier data adapted for 5.0.5), alexkulya's full 2023 dump and
TrinityCore/WoDCore historical SQL. Current full dumps lacking the row are
not evidence that the real MoP quest was absent. The decisive additional
sources were historical SkyFire objective data and TrinityCore's retained
template, with local-client and original-era cross-checks.

## Validation results

- Backup of all nine affected/reference tables saved and gzip-validated:
  `/home/user/wow-mop-build/db-backups/world-quest32592-before-20261001.sql.gz`.
- Isolated full table copies: first and second application both passed; exactly
  seven new rows, no existing rows changed, no relations changed.
- Invalid surrounding dependency group: intentional duplicate-key guard failure,
  no quest template or objective inserted. An existing custom template survived
  reapplication unchanged, with no addon/objective inserted.
- `contrib/tests/wrathion_quest_32592_regression.py` passed using extracted actual
  core methods and test doubles: reputation boundaries including 41999/42000,
  all predecessor combinations, both completion orders and prerequisite gate.
  Exported database fields and local client DBC mappings passed too. This is
  not a full game-server integration test or client playthrough.
- Normal canonical worldserver startup applied migration 07; live `world.updates`
  reports `RELEASED`. Live data matches the tested copy across all nine tables
  (zero row-count differences and zero differing joined rows). The live fixture
  has objective 270242/type 6/faction 1359/42000 and both negative-group members.
- Runtime stdout reached `World initialized in 0 minutes 18 seconds`.
  The test process was stopped cleanly; bot autologin restored to its original
  value 1. Launch paths and worldserver configuration were not changed.
  Console lookup was unavailable (`Console.Enable=0`); old file logs were not
  used as evidence of this startup. Full in-client acceptance/turn-in remains
  untested, and the optional RP conversation remains unimplemented.
