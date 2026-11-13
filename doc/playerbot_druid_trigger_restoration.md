# Druid trigger restoration — 2026-11-08

## Seven restored names — native PASS; BG healer coverage incomplete (2026-11-08)

Implemented: `group heal setting`, `medium group heal setting`, `entangling
roots`, `hibernate`, `bash`, `bash on enemy healer`, `nature's swiftness`.
Existing strategy priorities and group-health thresholds are preserved.
The shared aliases use the existing AoeInGroupTrigger (`almost full`/`medium`).
The newly reachable Rejuvenation selector guards null groups, instance/phase,
3D range, LOS and assist eligibility, and reselects at execution.

CC Actions use the existing explicit group icon, canonical spell names,
native target/type/immunity/form checks, and exclude the current attacked target,
existing breakable control and damage-over-time auras. They do not register
placeholder shared `cc target` Values or add automatic CC assignments.
Mighty Bash binds the learned talent5211 and selects an actual nearby caster;
the secondary variant requires a positive cast. Skull Bash is unchanged.

Nature's Swiftness requires a known132158, an active `heal` strategy, the
existing party-critical-health condition, absent buff and native cast eligibility.
The strategy gate is necessary because Balance's default caster strategy has
its emergency-heal nodes commented out; knowledge alone could spend the buff
without a follow-up heal. This does not restrict the spell to Restoration:
Balance can select the existing heal strategy, as the native fixture verifies.

A follow-up audit of the newly reachable shared branches found the same
null-group and inaccessible-target path in Priest's two custom Shield selectors.
Their first-eligible/lowest-health policies and Weakened Soul/Shield exclusions
are retained; both now use native assist, instance, 3D-range and LOS eligibility,
report their real Action aliases, and reselect before executing. The initial BG
was stopped normally for this dependency fix (exit0, pets preserved). Final native
rebuild/fixture `-i` PASS and `druid-control-bg-final-20261108` supersede that stopped run.

Validation:

* GCC and Clang ASan/UBSan extracted-production tests pass and each rejects
  **14 behavioral mutations**. Native world/spell APIs are bounded doubles here.
  Existing Druid and shared-party regressions pass with GCC.
* Native `worldserver -j4` build and the full opt-in five-player fixture PASS:
  `tests/druid-control-native-20261108-i/result.json`, finished18:36:27 MSK.
  Observed339 root,2637 sleep,5211 primary/secondary stun and interrupted casts;
  invalid humanoid, missing assignment/current-target/control guards; Cat Form
  prerequisite; unchanged talent cooldown and observed post-Bash GCD;
  three eligible wounded members in five; ally774 Rejuvenation;132158 consumed
  by instant5185 Healing Touch;740 channel with44203 HoT and healing on all five.
* Normal shutdown0, online0, preserved level/spec/spells/inventory/pets and
  group tables. Temporary NPCs/group removed. Cleanup requests restoration of saved
  position/health/phase; the DB comparison covers the listed protected fields. Native sources (2397 files) unchanged during the run.
* Ordinary BG80 completed608.4 measured combat seconds with100 online and78
  distinct combat participants. Workload/shutdown/pet/source invariants PASS.
  Across retained rotations:762716 decisions,16203 OK,68704 FAILED,0 UNKNOWN;
  all84907 execution records match the decision log, parse errors0.
  **BG acceptance remains `needs-review` for coverage**, not a full rotation PASS:
  `group heal setting` fired33 times, only on Shaman23; the medium condition and
  the two Priest Shield selectors were not exercised. Wild Growth had47 accepted
  Druid casts. The controlled fixture above proves both group conditions and
  individual Druid effects. Arathi does not cover flags or a complete BG cycle.
* Additional observation: Restoration27/38/82 log `+heal,-heal,+caster` on solo
  login, without a later heal re-add in the retained trace. `AiFactory.cpp:400`
  contains that existing ungrouped-healer conversion. Audit the intended strategy
  refresh on joining a group/BG before changing it; this slice does not redesign
  healer roles. See `healer-strategy-observations.json` and `acceptance-summary.json`.
* FAILED counts remain explicit. Main profiles:already-attacking30968,
  NO_POWER9895,waiting-for-last-move6588;21 are still unattributed (move random18,
  pet attack2,find corpse1). Also8 move/no-path and2 native charge NOPATH.
  These are observed outcomes, not a declaration of68704 separate bugs or of
  harmlessness. Full attribution is in `failure-audit.json`.

The earlier failed fixtures are retained as evidence. `-c` localized a dead
hostile test NPC; temporary phase isolation fixed the environment. `-f` showed
four peers moved to phase8065 by teleport/area processing, correctly rejected
with `assist=false`; isolation was moved after arrival. `-g` reached both group
conditions but attempted Rejuvenation within the native post-Bash GCD. `-h`
observed that GCD and waited without clearing it. No native validation was relaxed.

Still unresolved: `player has flag`, `enemy flagcarrier near`, `entangling roots
kite`, `thorns on main tank`, `omen of clarity`, `insect swarm`, `mangle (cat)`.
That is **7 remaining of the audited14**, or28 of35 original missing names now
registered, plus the earlier new magic-dispel branch. The four legacy nodes need
MoP-specific rotation decisions; flags need actual flag-BG scenarios and Guardian
form policy; kiting needs a proven threat policy. None were replaced with guessed
rules or placeholders. The pre-implementation audit below remains historical.

## Audit of the 14 remaining names — no gameplay changes

The owner's explicit rule, reaffirmed on 2026-11-08 and saved in Hindsight:
check reliable sources and historical data for the target version before changing
behavior. If the cause, mechanic or replacement remains doubtful, do not change
the corresponding code/data. Record the uncertainty and the evidence needed.
Restore real behavior; do not suppress messages, register placeholders or relax
native validation to obtain a green count.

This pass investigates **all 14** names; it does not activate or remove any of
them. The result is two confirmed registration omissions, eight conditions whose
complete execution chains still need validation, and four legacy/incorrect
spell-maintenance nodes. These are not 14 wholly missing abilities.

| Original trigger name | Confirmed evidence | Disposition / remaining acceptance |
| --- | --- | --- |
| `group heal setting` | Local `AoeInGroupTrigger` exists since module import `dbcb9e52`. AzerothCore registers this exact name with type `almost full`; our common factory does not. Seven active references across four classes. | Registration mapping is established. Exercise existing group-size/health policy and downstream healing before enabling it globally; do not invent a new percentage or register a Druid-only duplicate. |
| `medium group heal setting` | Same existing class, donor type `medium`; six active references across four classes. | Same shared restoration, with existing priorities and thresholds. Verify Tranquility and the other affected classes, not only that a Trigger can be constructed. |
| `bash` | Action resolves `bash`; learned talent 5211 is named **Mighty Bash**, effect is stun aura12. Talent18583, Druid tier4 (level75). Skull Bash106839 is a different Feral/Guardian ability. | Preserve distinction between stun and interrupt. A name change alone is insufficient: the shared interrupt predicate does not recognize a stun. Native positive cast/interruption and immune/noncasting negatives are needed. |
| `bash on enemy healer` | Same wrong spell name; `EnemyHealerTargetValue` invokes that shared predicate before selecting a positive caster. | Restore both target selection and spell binding; verify secondary healer, range, LOS, current cast and immunity. Do not treat Skull Bash as a cosmetic rename. |
| `entangling roots` | Roots339 is normally learned through SkillLineAbility. Handler calls `entangling roots on cc`, whose base Action spell is incorrectly the alias. Both `cc target` and `current cc target` Values are missing. | Restore/reuse a verified CC selector and bind the canonical spell. Require the selected enemy, no duplicate/breakable CC, native form/cast checks and an observed root effect. |
| `entangling roots kite` | Handler uses canonical Roots on the current target. The Wrath donor gates on fewer than three attackers and target current mana equal to zero. | Zero mana is not proof of a melee attacker. That policy has no verified MoP adaptation here; do not copy it as a game rule. Establish the threat/distance/target policy and native effect first. |
| `hibernate` | Hibernate2637 is normally learned; target creature mask3 means Beast or Dragonkin, and damage breaks it. `hibernate on cc` has the same absent Values and alias-name defect as Roots. | Shared CC dependency plus creature type, existing control, damage and native form checks. Test a valid creature and invalid humanoid/player form; do not infer validity from class alone. |
| `nature's swiftness` | Old17116 absent; actual132158 is learned at30 by specs102 and105. Final Blizzard5.4 notes agree: **Balance and Restoration**. Action already uses the correct canonical name. | The missing name is the optional `boost` predicate; Restoration already references the Action under `party member critical health`. Define/check meaningful consumption of the next-spell buff, cooldown and eligible target before activating an unconditional buff trigger. |
| `player has flag` | No common registration. Native WS/EY/TP track real carriers. Dash1850 is bound to `spell_dru_activate_cat_form` and `spell_dru_dash`, so it activates Cat Form and clears movement impairments. | Implement verified shared carrier semantics, preserving Guardian form decisions; test actual pickup/drop/capture and Dash effects in flag BGs. Arathi coverage does not test this condition. |
| `enemy flagcarrier near` | No common registration and no `enemy flag carrier` Value. Also referenced by Rogue. Modern donor includes additional WSG response policy and range/nearby-enemy conditions. | Reconstruct actual carrier selection, faction, live BG instance and approach policy. Do not copy thresholds or the donor's additional BG systems without evidence. |
| `thorns on main tank` | Old player spell467 absent from supplied DBC and checked normal learning sources. Other spells named Thorns remain; name presence does not identify the removed player spell. | Do not register the old cast-buff predicate or select an NPC/Symbiosis spell by name. No justified replacement has been established. |
| `omen of clarity` | Feral16864 and Restoration113043 have passive attribute0x40 and proc-trigger effects135700/16870 respectively. `SpellIdValue` excludes passive spells. | The old active self-buff Action is semantically wrong. Preserve native passive procs; separately audit actual Clearcasting use instead of casting the passive or faking success. |
| `insect swarm` | Spell5570 exists but has no SkillLineAbility, specialization, talent or LEARN_SPELL entry, and no matching trainer/custom-start/SQL-learn rows in the inspected DB. Sunfire93402 is a genuine Balance spell. | Normal player availability of5570 is unsupported. A Sunfire restoration is a distinct MoP rotation change, not an assumed one-to-one rename with inherited priority. Exact historical removal date and any exceptional custom learning are not claimed. |
| `mangle (cat)` |33876 has weapon-damage and combo-point effects, not the old Mangle bleed-vulnerability debuff. Wrath donor predicate checks Mangle/Trauma auras. Local builder Action is already reachable. | Do not reinstate debuff maintenance. Preserve the existing combo/energy builder paths; changing its high-priority slot needs a separately justified rotation decision. |

### Dependencies that prevent a registration-only fix

* **CC can become unsafe when activated.** `HasCcTargetTrigger::IsActive` uses
  `AI_VALUE2(...)->Get()` on unregistered Values. `AiObjectContext::GetValue`
  returns null for an absent factory entry; the macro has no null guard. This is
  a statically identified null-dereference path if that generic predicate is
  enabled, not an observed server crash in this pass. `rti cc target` does exist,
  but it is an icon selector, not an implementation of all missing CC semantics.
  Several other classes refer to the missing Values. `cc` is not added by the
  default Druid specialization branch, so registration alone also would not prove
  ordinary Engine reachability. The two CC Action aliases must not be passed to
  `SpellIdValue` as if they were learned spell names.
* **Interrupt recognition is incomplete.** Mighty Bash5211 is APPLY_AURA/STUN;
  Skull Bash106839 and form variants80964/80965 are DUMMY spells. The actual
  interrupt effect is93985, cast by `spell_dru_skull_bash`. The shared helper
  examines the resolved outer spell's interrupt/silence effects, not this script.
  Current DB binds the script to80964/80965. DBC override auras106829/106840 refer
  to those variants, and `GetActionbarOverride` already handles native overrides.
  Absence of a direct106839 binding therefore does **not** establish a DB bug;
  do not add it without tracing the native override/cast chain. NotCronky uses
  Skull Bash triggers with the same shared helper, so its registration is not
  proof of working interrupts in this branch.
* **Group healing has an existing policy.** `AoeInGroupTrigger` requires at least
  five nearby members and uses its existing half-group thresholds with caps.
  `AoeHealValue` already counts eligible alive, same-instance, friendly,
  in-range/LOS members using configured health thresholds. These are separate
  eligibility sets: `GetNearGroupMemberCount` lacks several of those filters.
  Their interaction needs coverage before enabling the aliases for five classes.
  The newly reachable Druid branch also queues `rejuvenation on not full`;
  its selector directly dereferences the group and lacks the newer shared
  selector's full eligibility checks. That dependency must be examined rather
  than declaring a complete healer restoration after two registrations.
* **Flags represent policy as well as state.** The modern donor's `player has
  flag` predicate can deliberately return false near the WS capture base during
  a flag stalemate or in EY with no owned bases. It is not merely `HasAura`.
  Local native carrier state exists, but those additional donor decisions are
  not automatically the intended local behavior. Dash already executes through
  the existing `enemy out of melee` branch; turning on the Feral base-strategy
  flag handlers also affects Guardian and can change it into Cat Form.

### Sources, history and existing runtime evidence

Local evidence: supplied enUS DBC (raw rows and SHA-256 saved),
`DBCStructure.h`/`DBCfmt.h`, native `spell_druid.cpp`, `SpellMgr.cpp`,
`Player::LearnSpecializationSpells`, Action/Trigger/Value factories and readonly
SELECTs from the working world DB. No SQL writes or server starts were performed;
online count at the DB check was zero.

The same empty Druid factory is already present in first class import
`da94869e` (2025-02-11), and the group predicate implementation is present in
module import `dbcb9e52` (2025-05-01). No recovered history justifies claiming
the author intentionally removed these abilities. The handoff LoA/PandaEMU
sources share the incomplete import; MaNGOS Four has no usable Playerbot donor
at the previously checked revision (see the evidence table below).

The checked NotCronky revision remains
[`aace1b02`](https://github.com/NotCronky/Legends-of-Azeroth-Pandaria-5.4.8/commit/aace1b02d29cc983748af78ae832b5de7fd8200c).
For the original framework's missing mappings and legacy semantics, this pass
also read pinned AzerothCore mod-playerbots
[`405f8119`](https://github.com/mod-playerbots/mod-playerbots/tree/405f81196161017eebae3ee7a612d786a3ed2a9d):
`src/Ai/Base/TriggerContext.h`, `Trigger/HealthTriggers.cpp`,
`Trigger/PvpTriggers.cpp`, `Trigger/RtiTriggers.cpp`, and
`src/Ai/Class/Druid/DruidTriggers.h/.cpp`. This is a **Wrath AI reference**,
not independent proof of MoP mechanics or a mandate to import its modern policy.
Its group-heal function matches the preserved local implementation; its
Mangle/Trauma, Insect Swarm and old Bash definitions cannot be transplanted.

[Final Blizzard5.4 release notes](https://worldofwarcraft.blizzard.com/en-us/news/10788364)
corroborate Nature's Swiftness for Balance and Restoration at30. The indexed
official release-note text was available; direct page fetch returned403.
Local SpecializationSpells and SpellLevels independently provide the same data.
PTR notes, a broad developer commentary mentioning Restoration only, and modern
Classic changes are not substituted for the final5.4 data.

Recount of the **existing** `druid-dispel-bg-20261108` Arathi run, including
compressed rotations, identified these Druid executions:

| Action | OK | FAILED | Native spell |
| --- | ---: | ---: | --- |
| Mangle cat |164|0|33876|
| Dash |11|0|1850|
| Wild Growth on party |31|4 OUT_OF_RANGE|48438|

No Nature's Swiftness execution was recorded in this sample. That absence does
not establish why its already-present critical-health branch did not execute.
Accepted casts here are evidence of reachability, not fresh per-effect
validation. The flag-specific triggers were not exercised on map529.

Artifacts: `wow_mop_codex_handoff/tests/druid-remaining-14-20261108/` contains
`collect.py`, `source-dbc-evidence.json`, `world-db-evidence.json`,
`existing-bg-evidence.json` and pinned external file responses. The collector
distinguishes active source references from commented-out code; raw registration
matches include Actions and require context-class review. It is a static audit,
not a compiler or gameplay test. No gameplay code, runtime, DB, log policy or
registration was changed. No new build/test PASS is claimed.

Next implementation order is shared group-heal mappings with complete downstream
eligibility coverage; then Druid CC target/Action contracts; then distinct
stun/interrupt native probes; then flag scenarios. Nature's Swiftness needs
buff-consumption evidence, while the four legacy nodes stay excluded from
activation until a target-version behavior is established. The old references
are retained in this audit, not removed to lower a missing-name count.

## Evidence before implementation

The native BG80 baseline in
`wow_mop_codex_handoff/tests/action-failures-20261108` recorded 2,115
Tiger's Fury `CUSTOM_ERROR` results, all in form 0. `Engine::ProcessTriggers`
silently skips a missing trigger; therefore zero `UNKNOWN` actions never proved
that class triggers worked. The Druid trigger factory and implementation were empty.

This predates the current work. The first class import,
[`da94869e` (2025-02-11)](https://github.com/Legends-of-Azeroth/Legends-of-Azeroth-Pandaria-5.4.8/commit/da94869ee0d1b6f96dec06cdba61b64382f16b4e),
already contains the empty factory. The module import
[`dbcb9e52` (2025-05-01)](https://github.com/Legends-of-Azeroth/Legends-of-Azeroth-Pandaria-5.4.8/commit/dbcb9e52af263503d0407aca7d942553d61ba879)
carried it forward. History establishes an incomplete import, not the author's
reason for leaving it incomplete, and not a recent deletion.

Handoff repositories checked through GitHub on 2026-11-08:

| Source | Pinned revision | Finding |
| --- | --- | --- |
| [LoA upstream](https://github.com/Legends-of-Azeroth/Legends-of-Azeroth-Pandaria-5.4.8/tree/a8f32ee3bdcf0c743dc7b575e66b19c54f0b4f6f) | `a8f32ee3` | Same empty Druid factory |
| [PandaEMU](https://github.com/XmUdYx/PandaEMU/tree/64d38ef0bc65a642c37cf1c3ed5b9c29cccd21b7) | `64d38ef0` | Same empty Druid factory; not independent corroboration of correct behavior |
| [NotCronky](https://github.com/NotCronky/Legends-of-Azeroth-Pandaria-5.4.8/commit/aace1b02d29cc983748af78ae832b5de7fd8200c) | `aace1b02` | Restores triggers together with replacement strategies; usable policy reference, not a wholesale transplant |
| [MaNGOS Four](https://github.com/mangosfour/Server/tree/27b6bdf2e08784abd0d1614bb1b06fab2f1c3936/src/modules/Bots/playerbot) | `27b6bdf2` | Playerbot directory contains only a config template; no Druid trigger donor |

The local enUS `Spell.dbc` and `src/server/scripts/Spells/spell_druid.cpp`
are the target-version authority: Cat Form 768, Bear Form 5487, Tiger's Fury
5217, Savage Roar 52610/127538, Rake 1822, Mangle 33876/33878, Swipe
62078/779, Faerie Fire 770, Moonfire 8921, Mark of the Wild 1126.
`mangle (cat)`, `mangle (bear)`, `swipe (cat)`, `swipe (bear)` and
`faerie fire (feral)` are strategy aliases, not learned MoP spell names.
`SpellIdValue` resolves exact learned names. Keep aliases but bind actions to
the actual spells.

Raw `SpellEffect.dbc` additionally confirms that Mangle 33876 has weapon
damage and combo-point effects, no aura-maintenance effect. Mark of the Wild
1126, Kings 20217, Shale Spider 90363 and the actual Emperor auras 117666/117667
all carry aura 137, amount 5 and `EffectMiscValueB=11` (Strength/Agility/Intellect).
`AuraEffect::HandleModTotalPercentStat` uses that B mask. Emperor's cast 115921
applies those auras through `spell_monk_legacy_of_the_emperor`. The trigger checks
aura names, including those actual buff auras. See `dbc-effects.json`; partial
SQL spell-group membership alone was not used as proof of equivalence.

## Bounded restoration

Preserve existing strategy priorities and fallbacks. Restore forms, live
target-owned combo-point predicates, Savage Roar, Rake, Faerie Fire, Moonfire,
Mark of the Wild, Berserk and the four existing Eclipse phase predicates.
Read live combo points as in the already-tested local Rogue implementation.
The three-second Savage Roar refresh and five-point finisher policy are adapted
from NotCronky; this is an AI policy, not a claim that the game requires five points.

Savage Roar targets self and needs the same refresh policy in the action as in
the trigger. Tiger's Fury requires Cat Form and no cat Berserk (106951), as
enforced by native scripts. Use NotCronky's below-35-energy eligibility policy.
Eclipse direction comes from native marker auras 67483/67484: the sign of the
power bar alone is insufficient after crossing zero. Existing `cooldown`
trigger names are retained as between-Eclipse phase selectors, not interpreted
as a Wrath-era cooldown mechanic.

Do not register placeholders for legacy abilities. Abolish Poison 2893,
Thorns 467 and Feral Faerie Fire 16857 are absent from the supplied DBC.
Omen of Clarity is passive. Other old cure, CC, flag, Mangle-debuff and group-heal
strategy nodes require their own effect/target audit before activation. This
change is not a complete MoP rotation rewrite or a restoration of every old node.

The first slice found **54 distinct active trigger references**, of which 35 lacked a
registration before this change. Nineteen are restored here. An earlier count
of 40 also included commented-out handlers. The 16 remaining active names are
recorded below as the first-slice audit backlog (the poison/curse row is addressed by the second slice):

| Names | Remaining verification |
| --- | --- |
| `bash`, `bash on enemy healer` | The learned spell is Mighty Bash, not Bash; distinguish the talent stun from Skull Bash and verify target selection |
| `party member cure poison`, `party member remove curse` | Addressed in the second slice below: learned Remove Corruption / Nature's Cure, plus Restoration magic dispel |
| `thorns on main tank`, `omen of clarity`, `insect swarm` | Thorns is absent; Omen is passive; presence of Insect Swarm in DBC alone does not prove player availability |
| `mangle (cat)` | Old debuff-maintenance predicate is not justified by MoP Mangle; the actual builder action is restored through existing combo/energy handlers |
| `entangling roots`, `entangling roots kite`, `hibernate` | Audit CC target selection, creature-type restrictions and shapeshift prerequisites |
| `player has flag`, `enemy flagcarrier near` | Validate WSG/EotS carrier selection and Dash conditions outside this AB test |
| `nature's swiftness`, `group heal setting`, `medium group heal setting` | Verify specialization availability, group targets and healing thresholds before activation |

## Mark of the Wild: live result required a second correction

The first completed BG80 run met its initial bounded checks (610 seconds,
100 bots, 0 UNKNOWN; Cat Form 44 OK, Bear Form 23, Mangle cat/bear 159/98,
Savage Roar 38, Tiger's Fury 24, Ferocious Bite 35, Rake 1, Starfire 34).
Tiger's Fury had zero execution failures. However, manual review found
626 accepted party Mark casts, **612 aimed at pet/guardian units**, including
the same bot/target pair every two seconds during preparation. The initial
automated PASS is not the final acceptance; see `manual-review.json`.

`PartyMemberValue::FindPartyMember` includes pets. Native
`Spell::SelectImplicitRaidTargetsIfNeed` explicitly removes
`IsPetGuardianStuff()` for target type 118. The Mark script additionally
buffs pets of the caster's own subgroup through `Unit::GetPartyMembers`,
but the generic selector also visits other raid subgroups. Such a pet stays
an eligible unbuffed target and causes repeated casts.

The correction is confined to Druid AI: `DruidMarkOfTheWildTargetValue`
reuses the existing party traversal and spatial checks, excludes the same
pet/guardian category as native raid-buff targeting, and skips equivalent
buffs before choosing a candidate. Thus a pet or an already-buffed first
player cannot starve a later eligible player. Trigger and Action share this
value. Other classes and core raid-buff effects are unchanged.

Opt-in `event=druid-mark` diagnostics record the selected target's aura 1126
before/after the actual Action, preserving its return value. The final
acceptance requires positive party casts, player targets only and actual
auras after accepted casts; accepted execution by itself is insufficient.

## Second bounded slice: native MoP dispels

Local `Spell.dbc`, `SpellEffect.dbc`, `SpecializationSpells.dbc` and
`SpellCooldowns.dbc` confirm Remove Corruption 2782 for Balance/Feral/Guardian
(curse and poison) and Nature's Cure 88423 for Restoration (magic, curse and
poison), both with an 8-second recovery. Cure Poison 8946 and Abolish Poison
2893 are absent. NotCronky `aace1b02` independently registers these two MoP
spells by dispel type; its replacement rotations are not needed here.

Restore the existing party poison/curse trigger names and priorities, binding
their actions to the learned spell for the current specialization. Add the
Restoration magic-dispel branch. Preserve old action aliases for callers, but
do not retain a fallback to an absent spell. Recheck the live harmful aura
before execution so a cached party target cannot cause an empty cast. Native
spell validation and shapeshift prerequisites remain authoritative. This slice
does not change shared party target traversal, CC policy or healing thresholds.

A prerequisite audit also found a shared dispel-filter regression. Commit
`39a1d661` (2025-02-11) used `strcmpi`, where zero means equal. Commit
`ddf7042f` (2025-02-13, Debian12 build) replaced it with the boolean
`caseInsensitiveEqual` while retaining both the `== 0` test and the final
conjunction of unnegated comparisons. With two distinct excluded names, every
named aura was rejected. The DBC string-layout change `dc1ec9b6` only carried
this older bug forward; the pinned NotCronky source also retains it.

A regression compiling the production comparison, `canDispel` and
`HasAuraToDispel` reproduced the failure before repair on a matching Deadly
Poison. Correct boolean comparisons restore the original exclusion policy;
no excluded aura, duration, passive, friendly/hostile polarity or dispel-type
rule is removed. This repair affects all users of the common filter, so its
regression independently checks friendly cleansing and hostile buff purging.
`dispel_filter_regression.py` includes mutations for the original inversion,
type mismatch and ally-buff eligibility. Native coverage is still required;
a passing bounded test alone does not establish restored gameplay.

The opt-in `npcbot druiddispel start/cleanup` fixture requires an explicitly
configured random-account Druid and a console caller. It injects only three
identified test auras from a disposable hostile NPC, pauses that bot's AI, and
calls registered Triggers/Actions with the existing learned spellbook. The
solo party selector targets self; this is controlled native effect coverage,
not proof of automatic raid ally selection or a complete healer rotation.
It checks poison+curse removal, Restoration-only magic removal, rejected empty
repeats/cooldown attempts, and a Cat Form cancellation prerequisite. The runner
checks protected level/spec/spells/inventory/pets after graceful shutdown.

Two preliminary attempts were stopped at fixture preconditions, with no test
auras injected and protected state unchanged. The diagnostic repeat proved
Feral GUID 16 knew 2782 and had persisted Cat Form (form 1), while all other
logged preconditions passed. Fixture setup now uses the existing caster-form
Action to normalize that state. The originally selected Restoration GUID 27
was a saved ghost; the final pair uses live Feral 16 and Restoration 38. These
preflight attempts do not count as gameplay passes.

The next attempt passed all Feral checks and Restoration dispel effects but
rejected the fixture's Cat Form cast with native result 70 (`NOT_READY`): it
was scheduled one second after Nature's Cure. Scenario delays now wait 2.5 s,
past the 1.5 s GCD. The cooldown refusal is consequently checked after GCD
and before the dispel's own 8 s recovery, without clearing either cooldown.
This is a test pacing correction, not a change to native casting.

Form evidence also differs by spell: 2782 has `SPELL_ATTR0_NOT_SHAPESHIFT`;
88423 has `StancesNot=0x1400000c` (Travel/Aquatic/flight forms, not Cat/Bear)
and no such attribute. `DruidDispelAction::getPrerequisites` consults native
`SpellInfo::CheckShapeshift` rather than imposing a universal caster-form rule.
The existing strategy choices are preserved: Balance/Restoration enable
`cure` in combat; Feral/Guardian do not gain a new default combat cure strategy.
Their existing noncombat handlers and explicit cure actions are restored.
The fixture's original unconditional caster-form expectation was corrected
for Restoration after the native run reached and rejected that expectation;
the gameplay Action already followed `CheckShapeshift` correctly.

Dispel eligibility also rejects `IsFlying`/`IsInFlight` before queueing any
caster-form prerequisite, matching the existing native `CastSpell` flight
prohibition. A bounded regression and mutation cover both airborne and taxi
states. This prevents form cancellation from preceding a prohibited cast.
The source-freeze guard deliberately rejected the build in progress when this
last gameplay guard was added; that attempt must not count as a runtime pass.



## Second-slice verification

GCC 16.2.1 and Clang 23.1.4 ASan/UBSan both pass the extended Druid
regression (15 rejected mutations each) and shared dispel regression
(4 rejected mutations each). The latter compiled real production methods and
reproduced the pre-fix failure. CTest registers both. `git diff --check` is clean.

The GCC 15 native build with `-j4` passed. A subsequent live preflight hit the
unchanged 10 GiB disk guard. Three older private Hunter test binaries had DWARF
compressed with zstd, recovering about 3.5 GiB; allocated ELF sections were
hashed before/after and are identical. Logs and directories were retained;
compression records are in `tests/druid-dispel-20261108/debug-compression.json`.
The repeat reuses the built binary only after matching its SHA-256 and all
native source hashes. The installed runtime is not replaced.

Both controlled native scenarios **PASS**, completed **2026-11-08 16:30:38
MSK** (`tests/druid-dispel-live-20261108`): Feral GUID 16 uses learned 2782,
removes Poison 2818 and Curse 1490 while leaving Magic 122, rejects magic-only
cleansing, and removes a later curse after cancelling Cat Form. Restoration
GUID 38 uses learned 88423, removes all three types, and also removes a later
curse while retaining Cat Form. Both verify no empty repeat and native
cooldown refusal after GCD. Each shuts down with exit 0 and online 0;
protected level/spec/spells/inventory/pets are unchanged, UNKNOWN Actions 0.
All native sources remained frozen. This is controlled self-target coverage
through the solo party selector, with aura injection only as setup; it is not
an ordinary Engine rotation or proof for every group target.

The ordinary BG80 integration run **PASS**, reviewed **2026-11-08 16:45:51
MSK** (`tests/druid-dispel-bg-20261108/reviewed-result.json`): 608.3 measured
combat seconds, 100 online, 89 distinct bots observed entering/combat/damage,
three BG instances, 769,195 decisions, 17,695 OK, 70,459 FAILED and zero
UNKNOWN. All 88,154 executions match the independent Behavior TRACE; parser
errors are empty. All 14 acceptance checks pass, including previous Tiger's
Fury form and Mark target/aura guards. Shutdown0, online0, server absent;
no added/removed/changed protected pets; all 2,393 native source hashes frozen.
The full match finish/reentry cycle was not observed.

| Restored Action | Ordinary BG OK | Native spell IDs | FAILED executions |
| --- | ---: | --- | ---: |
| `nature's cure on party` (magic branch) | 14 | 88423 | 0 |
| `cure poison on party` | 6 | 2782 ×2, 88423 ×4 | 0 |

Seventeen of these 20 accepted casts target another player in the same BG
instance on map529. This establishes ordinary Engine reachability and correct
spell/target binding; individual aura removal is proved by the controlled
native fixtures, not independently by every BG cast. The curse-specific Action
has positive controlled-native coverage but no positive ordinary-BG execution
in this sample. It is not a whole-rotation, all-class or all-route pass.

The aggregate FAILED count remains diagnostic. Current Druid examples include
Shred41 OK/121 NO_POWER, Savage Roar35 OK/8 NO_POWER, and Ferocious Bite35 OK/18
NO_POWER. These resource prechecks and 14 original missing trigger names remain
open; different stochastic BG workloads do not justify a performance-improvement
percentage. No installed runtime replacement, commit or push was performed.

To repeat the controlled native check, use a fresh artifact directory and an
existing, alive random-account Druid with the appropriate learned spell:

```bash
python3 contrib/diagnostics/druid_dispel_native_probe.py \
  --run wow_mop_codex_handoff/tests/druid-dispel-new-run --guid 16
```

Run it in a lingering user systemd unit for session independence. It requires
an offline server, takes the shared multilevel lock, builds `worldserver -j4`,
uses private configs with `AiPlayerbot.DruidDispelTestGuid`, and verifies
protected character state after shutdown. `--skip-build` is intended for a
wrapper that first verifies the recorded native source and built-binary hashes,
as the final `druid-dispel-live-20261108/run.py` does. It is not permission to
run an unrelated or stale binary.

## First-slice verification

`contrib/diagnostics/sanitizer_regression/druid_ai_regression.py` compiles the
real Druid trigger factory, predicates, selected actions and local strategy
handlers against bounded world doubles. GCC 16.2.1 and Clang 23.1.4 both pass
with ASan/UBSan; all ten deliberate mutations per compiler are rejected.
The tests cover form recovery, live combo ownership/consumption, self-target
and refresh of Savage Roar, Tiger's Fury form/Berserk gates, owned bleeds,
buff equivalence, native castability, Eclipse direction and canonical spell
names behind the old action aliases. Two further mutations restore the
pet-selection loop and remove the Druid value registration; both are rejected.
CTest registers the regression.

The native container build uses the established GCC 15 stack and `-j4`.
First compilation/link completed successfully. Its first live preflight
refused to start below 10 GiB free disk; no worldserver or BG ran, online
remained zero, protected pets unchanged. This is an infrastructure failure,
not a gameplay pass. The repeat retains that guard. Old test DWARF sections
are compressed losslessly to recover space, with unchanged allocated ELF
sections checked; the newly prepared live binary omits debug sections while
the full current build keeps them. Original and new hashes are recorded.
Compression recovered approximately 2.3 GiB. The attempted repeat then hit
the controller's prohibition on reusing a started directory; it also never
started the server. The actual native repeat uses a fresh `live-r2` directory
and the already-built, hash-checked binary. Both preflight attempts are retained.

Final native acceptance **PASS**, finished **2026-11-08 15:37:53 MSK**:
100 bots, BG80, 611.6 measured combat seconds, 785,806 decisions,
72,139 FAILED, 17,347 OK, zero UNKNOWN Actions. All 89,486 execution records
match the independent behavior TRACE by bot/map/instance/action/outcome.
All 2,391 native source hashes remained unchanged through build/run.
Normal shutdown, online zero, server absent, no added/removed/changed
protected pet records. The final service exited 0. Full BG completion/reentry
was not observed in this short run.

| Action | Final native OK | Remaining execution failures |
| --- | ---: | --- |
| Cat Form / Bear Form / Moonkin Form | 32 / 25 / 10 | 0 |
| Mangle cat / bear | 196 / 107 | 0 |
| Tiger's Fury | 29 | 0; no execution outside Cat Form |
| Savage Roar | 45 | 23 NO_POWER; all successes self-targeted in Cat Form |
| Ferocious Bite | 48 | 26 NO_POWER |
| Rake | 2 | 2 OUT_OF_RANGE |
| Starfire / Wrath | 24 / 293 | 0 |
| Mark of the Wild on party | 26 | 18 OUT_OF_RANGE |

All **26** accepted party Mark casts have a recorded `before=false,
after=true` aura 1126 transition on a player. No party Mark execution targeted
a pet/guardian. Its 18 rejected casts remained rejected, with no aura change;
no return value or log was suppressed. Self Mark had 17 OK.

The work restores reachable, tested behavior, not a complete optimal Druid
rotation. Sixteen missing names remained after the first slice, as listed above. The second slice restores the poison/curse pair and adds a Restoration magic trigger; fourteen of those original names remain. Rip, Moonfire and Berserk
have no positive execution coverage in these BG runs; their absence is not
proof of a particular cause. Rake/Rip keep existing 6/12-second estimated
lifetime gates; exact live gate values were not instrumented, so attributing
the low coverage solely to those gates would be inference. Shred had 109 OK
and **551 NO_POWER**; resource prechecks deserve the next focused audit.
Faerie Fire (feral) had 79 OK / 32 OUT_OF_RANGE. These results are preserved,
not reclassified as harmless. Aggregate FAILED counts across stochastic BG
runs are not used as a causal improvement metric.

Final artifacts: `wow_mop_codex_handoff/tests/druid-triggers-final-20261108`
(`reviewed-result.json`, `failure-audit.json`, `druid-native-outcomes.json`,
`mark-aura-effects.json`, regression logs, build log and source hashes).
Initial research, preflights and first BG evidence remain under
`wow_mop_codex_handoff/tests/druid-triggers-20261108`.
The full current build is retained; tests used a private binary. No installed
runtime replacement, commit or push was performed in this task.
