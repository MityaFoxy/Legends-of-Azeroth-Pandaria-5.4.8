# Startup content audit — 2026-10-01

## Authorized email outreach — sent (2026-10-02)

At the user's explicit request, sent separate English evidence requests to
both relevant public contacts found:

- DigiD702, `poserbiker@live.com`: published author address in the
  [NightElf import patch](https://github.com/ProjectSkyfire/SkyFire_548_Cluster/commit/922fe37967ebfadbc27c1e9e20944af46060499e.patch).
- AlterEgo / SkyFire administration, `admin@projectskyfire.org`: published
  author address in an [official SkyFire patch](https://github.com/ProjectSkyfire/SkyFire_548/commit/d960ac405d1ec708ec918c001140010b0adb21ad.patch).

Subject: `MoP 5.4.8 POI data request: NightElf exports and 12 empty blobs`.
Both Gmail calls succeeded and returned the `SENT` label; delivery and replies
are not yet verified. No CC/BCC or attachments were used. The messages request
sanitized original-version POI evidence, explicitly distinguish downstream
indexes from SkyFire blob IDs, and include all twelve unresolved keys and the
27316/13892 NightElf provenance questions. No configs, dumps, account or player
data were sent. Mailbox identifiers are kept only in the local ignored handoff.
No automatic reply monitoring was configured. All twelve cases remain open;
no SQL/core/runtime changes were made. The failed GitHub attempt below remains
historical context, not a published issue.

## Authorized upstream request — publication blocked (2026-10-02)

User-requested retry (2026-10-02, after email outreach): searched repository
issues for `27316` again (no results), then retried `create_issue` with the
prepared title/body below. GitHub again returned HTTP 403
`Resource not accessible by integration`. No issue was created; email outreach
remains the only successfully sent request. No permissions were changed.

User explicitly approved publication to `ProjectSkyfire/SkyFire_548`.
Checked available issue templates and searched existing issues for POI and
27316; no matching source request was found in those searches. The connected
GitHub integration rejected `create_issue` with HTTP 403:
`Resource not accessible by integration`. No issue number or URL was returned;
the request is **not published**. This is distinct from the unauthenticated
read API's rate limit encountered while checking templates. Templates were
subsequently read from the existing SkyFire research clone.

Manual destination: https://github.com/ProjectSkyfire/SkyFire_548/issues/new

Title: `[Data request] Original MoP POI evidence for 12 empty blobs (NightElf export: 27316 / 13892)`

Ready-to-post body (contains only public source references and quest metadata;
no local configuration, DB dump or player/account data):

```markdown
## Problem / scope

Could you help locate original MoP quest-POI evidence for the cases below, especially the NightElf consolidated exports referenced by the Cluster import?

This is a **data-provenance request for original 5.x / 5.4.8 (18414) content**, not a claim that all twelve cases reproduce on current stock SkyFire. The list comes from auditing inherited POI data in a downstream LOA-based 5.4.8 database. Headers exist but their associated point groups are absent. We have not established whether each case is lost geometry, an intentionally empty blob, or a mixed-version/import problem.

Cluster issues are disabled, so I am asking here; please redirect this request if another venue is preferred.

## Requested solution

If available, please share **sanitized POI-only packet excerpts or a provenance-labelled export** containing:

- Client build and capture provenance (original retail vs. Classic/private-server data).
- Quest ID, original blob/index identifiers, objective association, map/area metadata.
- Point counts, including explicit zero-point blobs, and any coordinates.
- WorldEffectID and condition metadata where present.

No full captures or account/player information are needed. A pointer to the original export or confirmation of how it was generated would also help.

## Twelve unresolved pairs

These are **downstream LOA `(QuestID, Idx1)` keys**, not assumed to be the same numeric IDs in SkyFire's schema. There are twelve blobs across eleven quests.

| Quest | Name | Downstream missing Idx1 |
| --- | --- | --- |
| 6922 | Baron Aquanis | 0, 1 |
| 11078 | To Rule the Skies | 6 |
| 13892 | Leave No Tracks | 0 |
| 24591 | Changing of the Gar'dul | 2 |
| 27228 | Man Against Abomination | 2 |
| 27316 | The Rattle of Bones | 0 |
| 28170 | Night Terrors | 1 |
| 29151 | Bad Supplies | 0 |
| 29763 | Stealing Their Thunder | 1 |
| 29861 | Whatever It Takes! | 0 |
| 32944 | Work Order: Kirin Tor Offensive I | 1 |

## Specific NightElf-export lead

[Cluster commit 922fe379](https://github.com/ProjectSkyfire/SkyFire_548_Cluster/commit/922fe37967ebfadbc27c1e9e20944af46060499e) says the SQL was compared against consolidated NightElf sniff exports. Its promoted version is [2026_08_26_world_05.sql](https://github.com/ProjectSkyfire/SkyFire_548_Cluster/blob/11e457459095d8a7e8fc837fdfc1b82129c3268d/sql/updates/world/2026_08_26_world_05.sql).

In that SQL:

- `quest_poi` includes `(27316,0,-1,1,61,0,0,7)`, but there is no corresponding point insert for `(27316,0)`; the point `(-5239,-2340)` belongs to `(27316,1)`.
- The `(13892,2)` point `(4567,406)` matches an already-present downstream group after index remapping; it does not by itself recover downstream `(13892,0)`.

Do the underlying exports explicitly record an empty blob for 27316/0, or could the SQL export/merge have omitted its points or metadata? Which client build produced those exports?

## Alternatives already investigated

We compared historical MoP-labelled dumps (including 5.0.5, DiamondDB 5.1.0 and WoWSource), Cataclysm imports, MaNGOS data and later TrinityCore/Legion sources. Many repeat the same holes, so their agreement may be shared ancestry rather than independent capture evidence.

[Cluster commit 022de23d](https://github.com/ProjectSkyfire/SkyFire_548_Cluster/commit/022de23d9a69c36d062950ba1e47275f27922e49) explicitly imports POIs from LOA. The [LOA merge script](https://github.com/Legends-of-Azeroth/Legends-of-Azeroth-Pandaria-5.4.8/blob/d4b6eb0c6ffc672de7f8680eff6291086eac5e42/sql/updates/master/world/wip/0000_00_00_00_quest-poi-rework-merge.sql) combines several versions, making original index/metadata provenance particularly important.

We have deliberately avoided copying another floor's marker, inventing polygons, deleting active-quest headers, or suppressing warnings as a substitute for restoring content. For 28170, sources also disagree on objective-index associations, so an index match alone is insufficient.

Any original-version evidence for even one of these cases would be appreciated. Thank you!
```

## Provenance follow-up — 2026-10-02

All twelve remain unresolved; no DB/core/runtime changes. An important
dependency was confirmed: SkyFire Cluster commit
[022de23d](https://github.com/ProjectSkyfire/SkyFire_548_Cluster/commit/022de23d9a69c36d062950ba1e47275f27922e49)
explicitly imports POIs from LOA for about 5,500 quests. Thus the Cluster
baseline is not an independent confirmation of our data. This does not
disprove the separate NightElf sniff claim, but that claim still needs its
underlying source. The NightElf commit has no published commit comments or
capture attachment in its changed files. Searching commit metadata found two
NightElf hits and eighteen quest_poi hits in that repository; neither the
NightElf import nor the inspected LOA-import commit supplies a capture link.
LOA PR #243 also has no issue comments supplying its source databases.

An earlier additional database,
[Kresh96/SkyFireDB](https://github.com/Kresh96/SkyFireDB/tree/1b59481b09c4dd5ac02b3865d7df459f6d659b07/MainDB/dev),
has the same empty groups for 11078, 13892, 24591, 27316 and 28170 after
header-index matching. It supplies only the obsolete outdoor 6922 marker and
the two already-known 27228 groups. The later target quest IDs have no POI
rows there. Both complete quest_poi SQL files were inspected, not imported.
Additional repository-tree searches found OpenWoW540's world.sql is only 31
bytes and OpenTools provides a sniffer program archive, not recorded packets;
neither is a recovered capture source. Public repository searches for the
NightElf consolidated export found no matching repository. No claim of an
exhaustive private/archived-data search is made.

Next concrete evidence request, **not sent**: ask SkyFire maintainers whether
the NightElf export behind 922fe379 contains the original 5.x POI responses
for 27316 and 13892, and whether other captures cover our twelve pairs.
Ask specifically for client build, original blob IDs/indexes, point counts,
WorldEffectID and condition fields. Request only sanitized POI excerpts or
SQL with provenance, not whole captures containing account/player data.
Cluster has GitHub issues disabled; ProjectSkyfire/SkyFire_548 has them enabled.
Publishing a request from the user's account requires separate authorization.

## Wider/deeper POI search — 2026-10-02

Result: no additional verified restoration; all twelve pairs remain open.
No live database, migration, core or runtime changes in this pass. Searches
included GitHub commit/issue metadata, archived SQL payloads, another full MoP
dump and a recent Classic database. Search hits and repository labels are not
treated as original-capture provenance.

### Newly inspected data sources

- [WoWSource full DB V3](https://github.com/dufernst/WS548-v4/blob/20d5940889daecf46de322d9e0988db2620da569/sql/WoWSourceDB%20V3%2003_07_2015.rar):
  SQL filename says 2015, archive entry timestamp says 2016-10-17. The ten
  pre-MoP target quest IDs reproduce the same missing groups after matching
  header semantics, not numeric indexes. Quest 32944 has no POI data here.
  In particular, 6922's indoor point is index 0 in this dump, versus our
  index 2; its two outdoor headers still lack points. Header lines 4207–4208,
  points 4231–4235. SQL SHA-256:
  `5a4200edef892cbea0b3a134d77546becaf138df6d269985877212e2f36e63b3`.
- [ArkCORE-NG](https://github.com/Arkania/ArkCORE-NG/tree/a7304c3075bf8ee7eb5bdf45f31cda01c8626b52/sql):
  scanned 1,053 SQL entries inside ZIP archives. Only
  `sql/old/Old 2016/_world_2016_04.zip:2016_04_14_00_world.sql` contains
  target POI tuples; these are headers, not restored point groups. Also
  checked smaller archived SQL for shrine credit IDs and quest 13892;
  text/flag/source-item adjustments are not POI restoration.
- [MaNGOSThree headers](https://github.com/mangosthree/database/blob/2e72872298e59a7ec8763ad2cdf897218b761b20/World/Setup/FullDB/quest_poi.sql)
  and companion points: same old outdoor 6922 marker and inherited missing
  groups; some 29763/29861 known points occur twice. No new coordinates.
- [TDB 442.26081](https://github.com/TrinityCore/TrinityCore/releases/tag/TDB442.26081):
  full world SQL retains the eleven missing pre-MoP blobs, matched through
  `Idx1` and header roles despite different `BlobIndex` and modern UiMapIDs.
  It has no 32944 POI. Rows carry VerifiedBuild 60192, but that does not make
  them MoP evidence or explain whether empty blobs were deliberate. SQL
  SHA-256 `51419b7dcb49c0550aef8c37c8a74c66b8d1ec497bbdb0fb718d9bbb6d3b7692`.
- [LegionCore-Reforged POI import](https://github.com/Titans-Project/LegionCore-Reforged/commit/b8d81610b93dfcf20db01593f4346d0002701b87):
  inspected both `2026_09_24_02_quest_poi_tdb735.sql` and
  `2026_09_24_03_quest_poi_tdb1210.sql`; neither supplies target quest tuples.
  The accompanying merge repairs collisions between versions in that core,
  not a verified repair for our twelve empty groups.

### Two specific leads examined, neither accepted as a fix

1. [SkyFire Cluster NightElf sniff import](https://github.com/ProjectSkyfire/SkyFire_548_Cluster/commit/922fe37967ebfadbc27c1e9e20944af46060499e),
   authored by DigiD702 on 2026-08-26. It was promoted by
   `36b742f0631dee60450b47d22cda9e27b3e39134`; current pinned path is
   [2026_08_26_world_05.sql](https://github.com/ProjectSkyfire/SkyFire_548_Cluster/blob/11e457459095d8a7e8fc837fdfc1b82129c3268d/sql/updates/world/2026_08_26_world_05.sql).
   The comment claims consolidated NightElf sniff exports. It inserts the
   empty **27316/0 header**, but the actual point at line 3840 is
   **27316/1 (-5239,-2340)**, already present locally. The 13892/2 point
   `(4567,406)` is our existing 13892/1 after index remapping, not our missing
   13892/0. Merely seeing 27316/0 in the DELETE key list is not a point insert.
   All ten world updates dated August 26–27 were inspected; only this one
   contains quest_poi SQL. No raw capture was found in the inspected repository
   tree or a sniff-labelled repository among the author's returned public
   repositories. **Useful next lead:** obtain the underlying consolidated
   export / original POI response, with client build and zero-point metadata.
   No external message/request was sent to the author.
2. [DivineProject quest 28170 patch](https://github.com/jorge990125/DivineProject/commit/fa9f4cc9f5a1e6d811380f302b8afd86f202e88d):
   adds shrine-credit spawns, including 47839 at
   `(-3457.65,-4202.22,212.586)`, and grants credit with SmartAI event 10 /
   action 33 on proximity. It supplies no POI points and no capture evidence
   for these positions; its linked Discord report was not inspected. This
   proximity workaround is not proof of the original cleansing mechanic or
   marker location. Do not import its wholesale template/spawn replacements.

Additional caution for 28170: WoWSource and TDB442 attach both objective
headers to the first shrine (the latter explicitly names credit 47838), while
our merged headers use objective indexes 1 and 2. Thus "missing second-shrine
marker" describes our current header, not an independently established retail
identity of the original blob. The historical WoW-Pro route distinguishes
three shrines but repeats its second/third waypoint coordinates; it cannot
resolve the blob identity. Existing points must not be re-labelled blindly.

### History/capture search limits

- The completed `git rev-list --all` pass examined 629 unique historical SQL
  objects reachable from local refs in the shallow fork mirror and found four
  target-containing blobs, all already-known imports. This does **not** cover
  every fork head: many previously fetched heads are stored only in the audit
  JSON. Traversal from all 50 unique recorded heads attempted lazy fetching
  and was stopped; retry with `GIT_NO_LAZY_FETCH=1` failed on missing object
  `ddfff4d4d7d15d26ff5446f960a8945fd4b88422`. Do not report a complete historical
  fork scan. The previous 81-fork / 1,101-current-SQL-blob audit remains separate.
- MaNGOSFour's seven POI-test file commits were read via the GitHub API. They
  describe retail packet measurements and later retract earlier floor-field
  assumptions, but no target-quest raw response was recovered. In particular,
  [672dea3](https://github.com/mangosfour/server/commit/672dea39853738bd9ca9bd50e78f6baf02faa875)
  describes WorldEffectID as the scalar before the points, supporting the
  previously recorded serializer discrepancy. It does not prove these twelve
  blobs should be empty. Our point-count slot is already correct; do not port
  the unrelated MaNGOS point-count fix.
- GitHub search briefly returned rate-limit errors; subsequent narrower
  searches succeeded. Neither web search nor absent results proves that no
  public/private source exists.

Temporary reproduction: `/tmp/poi_deep_scan.py` (read-only SQL/ZIP inspection),
`/tmp/mop-poi-arkcore`, `/tmp/mop-wowsource-v3`, `/tmp/mop-poi-tdb442`.

## Additional twelve-POI source search — 2026-10-02

No verified coordinate restoration resulted from this pass. No migration,
live DB write, server restart or core change was made in this pass.

- [DiamondDB 5.1.0 archive](https://github.com/Yamatoo/DiamondDB/blob/fb9ff7d4a50df2917d65bccc0c3b7780045351bb/base/world/DDB%205.1.0.01.rar):
  extracted `DDB 5.1.0.01.sql`; archive entry date 2013-01-27 is not proof of
  packet provenance. Headers 11078/6, 29763/1 and 29861/0 already lack points.
  6922 has the old outdoor turn-in (3355,1033), rejected for the reasons below.
  The other seven target quest IDs have no POI rows in this dump.
- [Published MoP 5.0.5 database](https://github.com/imortalbr/Mists_of_pandaria_5.0.5_16135b/blob/ce6c860afa0ba8b6e4bea7c30ff85c86663d6352/sql/base/world_database.sql):
  same three missing groups, same obsolete 6922 marker, no POI rows for the
  other seven target quest IDs. Extracted 13 headers and 54 points for the
  target quest IDs (header line 3943, point lines 3971–3972). Repository name
  is not verification that each imported row was captured in that client.
  Agreement between these dumps may reflect shared ancestry, not independent
  retail captures.
- InfinityCoreDB `Full_DB/world.sql` contains empty POI tables; it supplies
  no evidence about the individual missing groups.
- WoDCore revision `7c00f9a8a4f3a26c6dc23f9f0207b6c561983bba`: none of the
  target quest IDs occur in the three named quest_poi update files under
  `sql/updates/archive/old/world` (2014-11-25, 2015-05-09, 2016-05-30).
- MOP_V2_Repack revision `0739d072f8f1f42523f04cca4b2607d88a01def4`:
  inspected local patches `0005_fix_world_validation_errors.sql` and
  `0011_fix_orphaned_world_references.sql`; neither contains a POI repair.
  This is a scoped check, not a claim that all repository history was searched.

Downloaded SQL SHA-256 for reproducibility:

```
DiamondDB: 7fb7f8abbb768865c5e70d827576686fa1d7d3b83f93a9fbdb9e9f8d54483232
imortalbr: 0b07e3ce10a902a42e2d716f587e63c2c78c22003255fc07e220dad3fc3463c6
```

All twelve pairs listed below remain unresolved. The next useful evidence is
a version-matched quest POI response (including zero-point blobs, WorldEffect
and condition metadata), or a source with documented original provenance.
For 28170/1, independently verifying the second shrine's position and phase
could support a separately identified reconstructed marker, but does not
recover its original polygon. Do not silently treat reconstruction as a sniff
restoration. In-client checks remain necessary for phased/follower turn-ins,
dungeon floor display and 32944's seed-dependent effect. Neither missing
points nor repeated absence in inherited dumps proves that a header is junk.

## POI follow-up 2026-10-02: three retired headers archived; twelve unresolved

Migration `2026_10_02_01_archive_retired_quest_poi.sql` is applied (RELEASED).
It archives only `(3379,1)`, `(10216,1)`, `(29178,0)`, not all empty POIs.
These are retirement of obsolete references, **not three restored quests**.

Unlike the unresolved active quests, these three quest templates already have
the deprecated bit 0x4000 in the original Cataclysm build-15595 data, before
MoP. This is independently recorded in
[TrinityCore's 4.3.4 quest import](https://github.com/TrinityCore/TrinityCore/blob/976d67be0556e08786660b307f20e6122e6646e0/sql/old/4.3.4/TDB0_to_TDB1_updates/world/005_quest_template.sql):

- 3379: UPDATE Flags=16392, WDBVerified=15595. The
  [Shadoweaver history](https://warcraft.wiki.gg/wiki/Shadoweaver) also dates
  removal to 4.0.3a.
- 10216: UPDATE Flags=278664, WDBVerified=15595. The
  [quest page](https://www.wowhead.com/quest=10216/safety-is-job-one) marks the
  old version obsolete; it is not the newer similarly named dungeon quest.
- 29178: INSERT Flags=16520, WDBVerified=15595 (line 5123). The
  [quest page](https://www.wowhead.com/quest=29178/oooh-shinies) also marks this
  specific ID obsolete. Do not confuse it with earlier quests of the same name.

Local templates retain those exact flags/build. `Quest::IsUnavailable()`
tests the deprecated bit. The migration requires exact expected POI payloads,
exact quest flags/build, absence of point rows and an exact archival copy
before removing a header from the active table. Custom changes, newly supplied
points, reactivated quests and conflicting archives protect the active row.
All three original headers survive in `quest_poi_retired_archive`. Templates,
quest relations/objectives, player progress, every coordinate row and every
other header are untouched. Archive restoration is possible; do not blindly
overwrite a newly supplied active header with its old archival copy.

Additional research on the active quests:

- Original 4.3.4 imports already include empty `(29763,1)` and `(29861,0)`:
  `013_quest_poi.sql` (TDB0_to_TDB1, header lines 2502–2504, points
  13551–13552) and `078_quest_poi.sql` (TDB1_to_TDB2, header lines 42–44,
  points 179–180), under the same TrinityCore revision above. Their known
  points belong to other indexes/floors; no new point set recovered.
- [Firelands base POIs](https://github.com/FirelandsProject/firelands-cata/blob/b250899d4fdf68603e4d8a4d05b4b522d8319eb0/data/sql/base/db_world/quest_poi.sql)
  and its companion `quest_poi_points.sql` reproduce the same holes for the
  ten relevant pre-MoP active quest IDs. These tuples use build 19831, so the
  repository's Cataclysm label does not make them independent MoP evidence.
  11078 also uses indexes 0..5 where our corresponding headers use 1..6;
  matching numeric indexes alone remains unsafe.
- [Historical Thousand Needles guide](https://www.wow-pro.com/source-code-thousand-needles-alliance/)
  describes the Feralas Sentinel appearing alongside the player after
  crossing the bridge. This supports investigating dynamic turn-in behavior
  for 27316, not inventing a fixed missing point from the NPC's absence in
  the static spawn table. Guide percentages are not original POI packet data.

Remaining twelve pairs, unchanged:

```
(6922,0) (6922,1) (11078,6) (13892,0) (24591,2) (27228,2)
(27316,0) (28170,1) (29151,0) (29763,1) (29861,0) (32944,1)
```

No new coordinates or WorldEffect metadata were guessed, and neither the
loader nor packet serializer was changed. This does not establish that no
solution exists: matching original captures or independently sourced data
are still needed to distinguish omitted points from intentional empty blobs.

Validation and runtime caveat:

- Backup: workspace-parent `db-backups/world-before-retired-poi-20261002.sql.gz`
  (complete POI headers, points and quest templates); gzip integrity passed.
- Isolated `world_poi_retired_audit_20261002`: first/repeated application,
  lossless header partition and unchanged point data passed. Custom header,
  newly supplied point, reactivated quest and conflicting archive tests all
  preserved the active header. Fixture was restored afterwards.
  Reproduction SQL: `/tmp/mop-poi-retired-tests.sql`.
- Live vs tested copy: all columns compared, zero differences; equal counts
  33669 headers, 106462 points, 3 archive rows, 18029 quest templates.
- Operational mistake: an existing user worldserver PID 2147 was running,
  but a second test process PID 2180 was launched before handling the check
  result. The updater applied the migration. The second process loaded data
  and logged exactly 12 remaining POI warnings, then failed to bind occupied
  network/SOAP ports and terminated with signal 6. **This is not a successful
  full startup smoke test.** Log: `/tmp/mop-retired-poi-startup-20261002.log`.
  The pre-existing process was not stopped and remained running; no controlled
  restart or client verification was performed. Bot autologin restored to 1,
  launch paths unchanged. Do not assume the running process reloaded its
  cached POIs merely because SQL changed. Confirm the 12-warning baseline on
  the next user-approved normal restart; do not launch another server alongside it.
- Read-only SQL checks: `contrib/tests/quest_poi_checks.sql`.

**Runtime caveat resolved by a subsequent controlled test (2026-10-02).**
After the user reported stopping their server, a separate process check
confirmed no live worldserver (only the old PID 908 zombie). One instance was
started with the canonical command and bot autologin temporarily disabled.
It initialized in 18 seconds; game port 8085 and SOAP port 7878 were verified
LISTEN in `/proc/net/tcp`. No network-bind failures, signal/crash messages or
`Wrong skill id` warnings occurred. Exactly the twelve remaining POI warnings
listed above were emitted. All three read-only POI checks passed. Log:
`/tmp/mop-poi-clean-startup-20261002.log`.
The test instance then stopped cleanly (exit 0); absence of a live process
was verified again. Bot autologin restored to 1; launch paths unchanged.
This closes the startup-test gap, not the twelve unresolved POIs or the
separate in-client gameplay/character-creation testing debt.

## Follow-up 2026-10-02: 36 obsolete starting skill references

Migration `2026_10_02_00_archive_legacy_start_skills.sql` addresses the 36
`Wrong skill id` warnings from `playercreateinfo_skills`. The check in
`ObjectMgr::LoadPlayerInfo` rejects these rows before adding any skills, because
none of their IDs exists in the runtime original-MoP `SkillLine.dbc`.
They also have zero references in `SkillRaceClassInfo.dbc` and
`SkillLineAbility.dbc`. These are old specialization skill lines, obsolete
general-class lines and Thrown (176), not missing MoP spells to recreate.

DBC evidence is reproducible offline:

```
python3 contrib/tests/start_skills_dbc_check.py /path/to/Data/dbc
```

Original WDBC layouts checked: SkillLine 9 fields/36 bytes, SkillRaceClassInfo
8/32, SkillLineAbility 13/52. The script verifies all 36 IDs are absent and
all 11 classes have current class-skill records with Availability 1 and
ReqLevel <= 1. Current class skills by class ID 1..11 are
840, 800, 795, 921, 804, 796, 924, 904, 849, 829, 798.
`ObjectMgr` already adds the corresponding SkillRaceClassInfo record IDs in
its automatic DBC pass; `Player::LearnDefaultSkills` consumes those records.
Do not blindly replace old SQL IDs with new class skill IDs or restore old
talent-branch skills. Specialization spells have a separate learning path.

Safety: all exact old rows (including rank and comment) are retained in
`playercreateinfo_skills_legacy_archive`. A row leaves the active table only
if it matches the expected payload and the archival copy byte-for-byte.
Custom rows and conflicting archive entries are left untouched. No character
table, spell, talent, profession, valid starting skill or core code is changed.
The old rejected rows did not contribute to PlayerInfo before this migration.

Backup: workspace-parent `db-backups/world-before-start-skills-20261002.sql.gz`,
full source table, gzip integrity checked. Isolated database
`world_skills_audit_20261002`: repeated application, lossless partition of the
original table, all 36 archived records, custom rank and archive-conflict tests
passed. Test fixture restored afterwards. SQL test:
`/tmp/mop-skills-tests.sql`. DBC test passed for all eleven classes.

Live validation: migration is RELEASED in world.updates; active table has
61 rows, archive 36. Both match the isolated tested result. Startup completed
in 16 seconds with zero `Wrong skill id` messages. Loaded counts remain
exactly 2195 player-create skills / 2456 player-create spells, identical to
the pre-change log. Log: `/tmp/mop-start-skills-startup-20261002.log`.
Test worldserver stopped, bot autologin restored to 1, canonical launch paths
unchanged. No in-client character-creation test was performed.

Separate issue found, NOT repaired here: the SQL path currently appends
`skill` (SkillLine ID) to `PlayerInfo::skills`, while its consumer interprets
values as SkillRaceClassInfo record IDs. The automatic DBC path appends the
correct record ID. This mismatch affects other, valid SQL rows and deserves
a separately scoped creation/login/level-up regression test; do not claim
the present archival migration repairs all starting-skill behavior.

## Original October 1 scope

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

## Quest POI: initial investigation (superseded by follow-up below)

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
Idx1=0 turn-in. Correction to the initial audit: old `(6922,id=0)` point
`(3355,1033)` is on map **1**, not 48. It is nevertheless unsuitable for our
Cataclysm/MoP version: Je'neu moved inside Blackfathom Deeps (see below).
The 2015 source has the same missing sets; its 32944/Idx1=1 header additionally
has WorldEffectID=1116 and shares BlobIndex=0, but no point rows. The import is
WoD-era, but the WorldEffect itself already exists in MoP; its applicability
to this quest is a separate, unproven claim. No headers were deleted.

Search limitation: these are the inspected public dumps/history, not an
exhaustive search of every private sniff, branch or fork. Next useful evidence
is an original MoP quest-POI packet capture matching the map/objective/floor,
or another independently populated historical database. Do not infer a polygon
from present-day NPC coordinates alone.

## POI follow-up: verified 8306 restoration, 15 entries still open

The warning means a header has no `(QuestID,Idx1)` point group and is skipped
by `ObjectMgr::LoadQuestPOI`. It does **not** by itself establish that a quest
objective cannot be completed. POIs are client guidance, not quest credit.

The SQL snapshot introduced in `d4b6eb0c6ffc672de7f8680eff6291086eac5e42`
(2024-06-17) already has these holes. Its WIP merge script combines Cataclysm,
Wrath and Pandaria data and then imports objective IDs from TDB. The same
commit replaces the previous vector loader (which could retain empty vectors)
with the current missing-group warning/skip. This establishes data ancestry
and a loader change, not that every missing group is an accidental deletion.

An additional scan of the available 81 public-fork snapshots examined 1,101
unique SQL blobs; seven contained relevant tuples/statements. One fork,
[ingussuveiks-dev at 160f07e7](https://github.com/ingussuveiks-dev/Legends-of-Azeroth-Pandaria-5.4.8/tree/160f07e7394bbda64eac8ffb07b617491b585b56/sql/updates/world),
has two July 22 migrations adding five markers and an August 21 migration
deleting the other eleven. These are leads, **not independent verification**.
The modern TDB-based copies for 13892/27316/29861 do not establish an original
MoP marker; the floor difference for 29861 especially needs confirmation.
The blanket eleven-header deletion is not adopted. This scan covers the
fetched heads, not every historical commit or private fork.

### 8306 / Idx1 1: add one source-backed return point

[MaNGOS Four header](https://github.com/mangosfour/database/blob/8b798ac6a6a51c0c00c7e20c0a864793eb53904c/World/Setup/FullDB/quest_poi.sql#L6704)
is `(8306,1,-1,1,261,0,0,1)` and its
[point](https://github.com/mangosfour/database/blob/8b798ac6a6a51c0c00c7e20c0a864793eb53904c/World/Setup/FullDB/quest_poi_points.sql#L22623)
is `(8306,1,-6752,824)`. This matches our missing header's index, objective,
map, area, floor, priority and flags. MoPDB 5.4.7 and SFDB 5.4.8 also preserve
this return position under their older index 0. This is not inferred solely
from the surviving local index 2 duplicate.

[Wowhead's MoP quest page](https://www.wowhead.com/mop-classic/quest=8306/into-the-maw-of-madness)
corroborates the Natalia investigation and Commander Mar'alith/Cenarion Hold
context. Our return relation is NPC 15181, at map 1 position
`(-6752.38,823.836,57.4468)`, consistent with the historical integer POI.
The objective itself is creature 15215, not the return NPC. Only the missing
return point is restored; the objective, other markers and quest availability
are unchanged.

Migration `2026_10_01_11_restore_quest_8306_poi.sql` inserts
`(8306,1,1,0,-6752,824,0)` only when every expected header field matches and
the entire target point group is absent. BlobIndex 1 agrees with the historical
2015 header group; the current loader keys by Idx1. No UPDATE/DELETE or schema
change. VerifiedBuild 0 explicitly denotes reconstruction, not a new sniff.

### 6922: rejected restoration after objective/version cross-check

The draft initially included the fork's exterior point `(3355,1033)`.
It was removed **before any live application**. MoP-labelled dumps can retain
pre-Cataclysm quest data: their map-1 return marker is insufficient evidence.
[Wowhead's retained quest text](https://www.wowhead.com/quest=6922/baron-aquanis)
requires returning the Strange Water Globe to Je'neu **inside Blackfathom
Deeps**. Our build-15595 text says the same, the return relation is NPC 12736,
and the only local spawn is map 48 at `(-157.078,74.129,-45.5308)`.
The valid index-2 marker already contains `(-157,74)`. Adding an outdoor
turn-in would misdirect the player. The two map-1 headers are retained for
now; neither their original intended use nor a safe replacement is proven.

### All other reported headers: objective-level review

Wowhead/Classic pages corroborate intent, but Classic's newer client is not
an original 5.4.8 packet source. World coordinates, POI indexes and polygons
still need version-matched data; comments alone are insufficient.

| Quest / missing index | Verified intent / local objective | Remaining issue |
| --- | --- | --- |
| 3379 / 1 | Five Shadowsilk Poachers (8442), return to Nilith; local deprecated flag | Do not reactivate old quest; no distinct return point recovered. |
| 10216 / 1 | Five Nexus Stalkers (18314), one of four kill objectives | [Old quest obsolete](https://www.wowhead.com/quest=10216/safety-is-job-one); do not substitute its newer replacement or guess a dungeon/entrance marker. |
| 11078 / 6 | [Dragon Teeth](https://www.wowhead.com/mop-classic/quest=11078/to-rule-the-skies), item 32732, four summonable dragons | Four existing polygons already cover summon areas; purpose of fifth objective blob unproven. |
| 13892 / 0 | [Spy on Twilight's Hammer](https://www.wowhead.com/quest=13892/leave-no-tracks), credit 34410 near Foreman Balsoth | Existing index 1 point does not prove index 0 should duplicate it. |
| 24591 / 2 | [Tower event and Gar'dul relieved](https://www.wowhead.com/mop-classic/quest=24591/changing-of-the-gardul), credits 37843/37811 | Missing return marker; event completion/phase is relevant, not simply a kill position. |
| 27228 / 2 | [Kill Ramstein](https://www.wowhead.com/mop-classic/quest=27228/man-against-abomination), 10439 | Missing floor-1 return marker, not the existing floor-2 boss point; multiple quest-giver locations/phases. |
| 27316 / 0 | [Return the Rattle to Feralas Sentinel](https://www.wowhead.com/de/quest=27316/die-rassel-der-knochen), item 60959 | Alliance quest, not Horde 27317; NPC 45277 has no static local spawn. Modern duplicate point does not verify the missing MoP blob. |
| 28170 / 1 | [Cleanse three shrines](https://www.wowhead.com/mop-classic/quest=28170/night-terrors), credits 47838/47839/47840 | Missing second-shrine marker in phased cave; do not copy the third shrine's point. |
| 29151 / 0 | [Search supplies](https://www.wowhead.com/mop-classic/quest=29151/bad-supplies), credit 52882 | Missing return marker, not the grain-sack objective point; static Bwemba spawn alone cannot verify follower/phase return location. |
| 29178 / 0 | Local text: speak to Budd in Ghostlands; local deprecated flag | Header is in Zul'Aman; no trustworthy replacement point. [Quest reference](https://www.wowhead.com/quest=29178/oooh-shinies). |
| 29763 / 1 | [Ingvar's Head](https://www.wowhead.com/mop-classic/quest=29763/stealing-their-thunder), item 33330 | Missing floor-1 objective blob; known floor-3 boss point is not proof of floor-1 coordinates. |
| 29861 / 0 | [Loken's Tongue](https://www.wowhead.com/mop-classic/quest=29861/whatever-it-takes), item 43151, return to Eljrrin | Missing floor-1 return blob; do not copy floor-2 marker blindly. Local NPC has two spawn positions. |
| 32944 / 1 | Plant eight Juicycrunch Carrot Seeds, credit 65480 | Empty world-effect candidate has conflicting seed condition; see below. |

### Empty POIs / WorldEffect: important, but not a blanket fix

[WPP's 5.4.8 parser](https://github.com/TrinityCore/WowPacketParser/blob/28fc3d194b22063ce8e94d2ed7235ca98ca51ef2/WowPacketParserModule.V5_4_8_18291/Parsers/QuestHandler.cs#L279)
can decode zero-point blobs and retain their headers. It reads the first
scalar as WorldEffectID, whereas our serializer writes `blob.Floor` there.
This is a separate protocol discrepancy needing packet/client validation.
The parser accepting zero points does **not** prove these 16 are intentionally
empty or justify disabling the warning. No core behavior changed in this fix.

Local 5.4.8 `Data/dbc/WorldEffect.dbc` has row
`(1116,1,58718,11,18987,0,1)`: Merchant Greenfield (58718), feedback 11,
PlayerCondition 18987. Using the original-5.4.8 layouts in
[WoWDBDefs](https://github.com/wowdev/WoWDBDefs/tree/master/definitions),
the latter has ItemLogic 196609 and ItemID 89326/89847: Witchberry Seeds / Bag
of Witchberry Seeds. Quest 32944 instead requires Juicycrunch Carrot Seeds
(80590), corroborated by the historical
[WoW-Pro guide](https://www.wow-pro.com/tillers-reputation/).
Thus the 2015 TDB effect reference cannot be imported as a proven MoP fix.
Neither a guessed carrot effect nor invented coordinates were substituted.

### Follow-up validation

- Backup of both complete POI tables: `db-backups/world-before-poi-20261001.sql.gz`
  under the workspace parent; dump completion footer and `gzip -t` verified.
- Isolated `world_poi_audit_20261001`: first and second application passed;
  exactly one point added, all existing point values and every header retained.
  Custom point payload and custom header guards passed; fixture restored.
- Read-only check: `contrib/tests/quest_poi_checks.sql`.
- Normal updater applied migration 11 (`world.updates`: RELEASED). Live tables
  match the tested copy across every column, with equal row counts and zero
  differing headers/points. Startup initialized in 17 seconds; 8306's warning
  is gone and exactly 15 remain. Log: `/tmp/mop-poi-startup-20261001.log`.
  Worldserver was stopped; bot autologin restored to 1. Canonical startup paths
  unchanged. No in-client map/quest playthrough has been performed.
- Research artifacts: `/tmp/mop-poi-fork-scan.py`, its JSONL output,
  `/tmp/mop-poi-guard-tests.sql`. Original source files remain in the research
  clones noted above. No claim of exhaustive search of private data.

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
