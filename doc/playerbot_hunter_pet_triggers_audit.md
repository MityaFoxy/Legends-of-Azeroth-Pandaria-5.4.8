# Hunter pet-care triggers — 2026-11-07

This is the next narrow class-AI restoration after the seven checkpoint commits
ending at `770feec6`. It restores two existing strategy links, not a complete
Hunter rotation or the remaining Hunter trigger catalog.

## Confirmed defect

`GenericHunterStrategy::InitTriggers` requests `hunters pet medium health` →
`mend pet`. `HunterPetStrategy::InitTriggers` requests the same healing link
and `hunters pet dead` → `revive pet`. Both Actions already exist and are
registered. However, `HunterTriggerFactoryInternal` was empty and neither
predicate existed in `HunterTriggers.h/.cpp`.

`Engine::ProcessTriggers` skips an unresolved Trigger before queuing any Action.
Consequently an Action trace with zero UNKNOWN cannot detect these unreachable
pet-care handlers. The new regression fails on the old source with the explicit
assertion `pet triggers unreachable`, after successful compilation.

## Sources and adaptation

- Local strategies and `HunterAiObjectContext.cpp` establish the existing names,
  handlers and priorities. `AiFactory.cpp` attaches `pet` in noncombat; the
  generic combat strategy already requests Mend Pet.
- [NotCronky HunterTriggers.cpp at 969150c0](https://github.com/NotCronky/Legends-of-Azeroth-Pandaria-5.4.8/blob/969150c0d398039e993a88913fe71a528b74dc41/modules/mod_playerbots/src/strategy/Classes/hunter/HunterTriggers.cpp)
  provides comparison predicates: current pet present, alive and injured without
  Mend Pet for healing; present and dead for resurrection. The pinned GitHub
  file was checked against the local git object.
- The local enUS DBC has Mend Pet **136**, effect 6 / aura 20 targeting pet 5;
  Revive Pet **982** includes effect **109**. The existing spell script handles
  Mend Pet's periodic effect. `Spell::EffectResurrectPet` requires a present dead
  pet and owns resurrection, health restoration and persistence.
- Keep the local `AiPlayerbot.MediumHealth` setting (default **65**), rather than
  import NotCronky's fixed 50% threshold or different trigger names. Poll every
  two seconds, using the existing Trigger timer conversion.

The predicates use the current `bot->GetPet()` on every check; absent/dismissed
pets do not count as dead. An existing Mend Pet aura suppresses another healing
request. Actions retain their original targets, priorities, spell knowledge,
costs, cooldowns and native casting checks. No pet creation, slot migration,
forced injury, resurrection command or inventory mutation is added.

The two-trigger repair did not use the legacy `PetIsDeadValue`, which treated
any persisted pet row as death when no pet was loaded. The follow-up below
repairs that separate value.

## Follow-up: current pet death value

On November 7, `PetIsDeadValue::Calculate` was changed to read the current
`Player::GetPet()` once and require `!pet->IsAlive()`. Stored ownership,
stable/dismissal records and an unresolved pet GUID do not establish death.
This matches `IsDeadValue`'s absent-target behavior, the Hunter death trigger
and `Spell::EffectResurrectPet`'s requirement for a present dead pet. Loaded
pet death states retain their original behavior, including transitions.
`Pet::LoadPetFromDB` remains responsible for loading persisted health/state.
The value no longer queries the characters database.

A repository-wide call-site search finds the `pet dead` registration in
`ValueContext` but no static consumers in current strategies/Actions. This
is a corrected value contract, not evidence of improved live rotations or
an explanation for repeated Call Pet. Its registration/cache API is retained.

`pet_state_value_regression.py` compiles the actual value, Hunter death
predicate and native Unit state methods/enums with pet/storage doubles.
Old source compiles and fails the saved-but-absent-pet assertion. GCC15 and
Clang ASan/UBSan pass: absent pets with/without saved rows or stale GUIDs,
all native death states, replacement/removal, consistency with the Hunter
predicate and zero SQL calls. Three mutations are detected: absent-as-dead,
inverted alive check and reintroduced storage polling. CTest/CI include it.

Autonomous build `loa-pet-state-build-20261107-r1.service` passed -j4 on
November 7 at **12:27:30 MSK**. Binary SHA-256:
`976eb35b75a734d19404bb57169c930b6cb3b42e64d76ec689b5ace7d23b438a`.
Evidence: `wow_mop_codex_handoff/tests/pet-state-20261107/`. No live server was
started for this value-only check and the installed runtime was not replaced.

## Verification

`hunter_pet_trigger_regression.py` compiles the real two strategies' trigger
methods, full Hunter trigger/action factories, new predicates, native
Trigger/NextAction/NamedObjectContext code and existing Mend/Revive action
wrappers. World state, unrelated actions and base spell execution are bounded
doubles. Tests cover null/live/dead pets, threshold and configuration changes,
existing aura, pet replacement with cached triggers, handler priorities and
targets. GCC 15 and Clang ASan/UBSan pass, including five detected mutations:
missing registration, reversed living-pet guard, fixed threshold, missing aura
guard and reversed resurrection guard. CTest includes the test in `hunter`
and `class-ai`, so the existing GCC/Clang CI jobs run it.

Native build/observation is recorded under
`wow_mop_codex_handoff/tests/hunter-pet-triggers-20261107/`.
`loa-hunter-pet-triggers-20261107-r1.service` runs a detached -j4 build and
180 seconds of observation after 100 bots log in, with the existing level-60
BG workload. The probe records all Action outcomes, pet-care outcomes and BG
observations; it stops gracefully and verifies online flags.

**Native PASS: November 7, 12:19:26 MSK.** The -j4 build succeeded, and the
unit/worldserver exited 0. After 100 bots logged in, observation lasted 180.21
seconds. The complete Behavior file contains **95691 decisions, 0 UNKNOWN**.
There are two `hunters pet dead` events followed by `revive pet OK` (GUIDs
63 and 8) and `hunters pet medium health` followed by `mend pet OK` (GUID 63).
Mend was initially IMPOSSIBLE and accepted two seconds later; native casting
checks remain effective. These events occurred on map 1 / instance 0, not BG.
No pet injury, death or spell execution was forced by the test controller.
Accepted casts alone do not prove the final heal/resurrection effect.

Post-shutdown online count is zero, no worldserver remains, and the logs contain
no fatal assertion/sanitizer/lost-owner markers. The 2237 other FAILED outcomes
require context; they are not automatically defects. BG telemetry saw 87 entries
and 60 objective participants but no combat phase or full match cycle in this
short window. It is not BG acceptance or a full-server sanitizer test.
Artifacts: `native-r1/{result,action-audit,pet-actions,bg-observations}.json`,
build log and complete runtime logs. The native source diff matches the build;
binary SHA-256:
`426528e95708cd5933dd180809c81ffcd42019127662acb58486703cb0fb9900`.
The installed runtime was not replaced.

## Remaining class work

Other Hunter triggers and MoP-incompatible legacy choices still need individual
source checks. Existing Call Pet/slot recovery is a separate completed slice;
this change does not redefine its behavior. Other classes, including Monk,
are unchanged.

The run also contains 78 accepted `call pet 1` attempts. The follow-up below
correlates those attempts with owned pets before changing the request condition.

The old `CastShootAction` reads `EQUIPMENT_SLOT_RANGED`, while the core's ranged
weapon lookup reads main hand. That discrepancy alone does not prove a broken
wand path: with no old-slot item the Action retains the correct `shoot` name,
and native checks validate the weapon. Shoot remains an audit item, with no
speculative change included here.

## Follow-up: Call Pet 1 requires an owned active-slot pet

The complete original native trace attributes **72 of 78** accepted Call Pet
attempts to GUIDs **30 and 74**, 36 each. A read-only database snapshot finds
both Hunters at level 1 with no `character_pet` rows or current pet. This
is separate from exotic-pet eligibility and the previous slot-255 migration;
the saved recovery plan contains no skipped records for these two owners.

Local DBC **883 / Call Pet 1** uses summon-pet effect **56**, MiscValue 0 and
BasePoints **0**. `Spell::EffectSummonPet` treats that BasePoints value as a
slot and calls `LoadPetFromDB(PET_LOAD_BY_SLOT, slot)`. With no row, it deletes
the unspawned Pet object and returns. An accepted cast can therefore produce no
summoned pet; generic absence alone is not sufficient for this Hunter action.
The pinned NotCronky comparison likewise checks spell 883 and active slot 0.

`HunterPetStrategy` now requests a dedicated `hunter no pet` trigger. It
inherits all native `NoPetTrigger` restrictions and its five-second cadence,
then requires knowledge of spell 883 and a pet ID in `PET_SLOT_ACTIVE_FIRST`.
The shared generic trigger remains available to Mage, Warlock and Death Knight.
No spell, pet, level or slot is granted, no failure log is suppressed, and the
existing Call Pet Action/native spell path and priority 60 are preserved.
Loaded dead pets remain the responsibility of the revival handler. Other
active slots, stable slots and overflow pets do not satisfy Call Pet **1**.

The extended Hunter regression compiles the real generic trigger as well as
the Hunter predicates and strategy. It tests unknown spell, empty/other/stable
slots, positive slot-0 recall, loaded live/dead pets, minion, guardian,
controlled unit, mounted state, and the preserved handler/target. Four new
mutations join the existing five: registration, slot, knowledge and base guards.
Native build and before/after observation are recorded separately under
`wow_mop_codex_handoff/tests/hunter-call-pet-20261107/`.

**PASS — November 7, 12:36:53 MSK.** GCC15 and Clang ASan/UBSan pass all nine
mutations; -j4 worldserver build succeeds. Autonomous
`loa-hunter-call-pet-20261107-r1.service` observes 100 bots for 180.31 seconds
after login. GUIDs 30/74 both produce normal decision traces and make **zero**
pet-care requests, versus their previous 72 accepted empty Call Pet attempts.
Preflight and post-shutdown queries confirm neither owner has pet rows.
The positive path is sampled on GUID8: Call Pet1 OK at09:33:47UTC, then native
`has pet` events from09:33:52UTC onward. The test issues no summon commands.

Complete trace: **90990 decisions, 0 UNKNOWN**; other1159FAILED require context.
Unit/server exit0, online0, no remaining worldserver or fatal log markers.
BG89entered/60objective, no combat-phase/full-cycle sample in this short window.
Mend/Revive were not sampled again; their previous native observations and
current predicate regressions remain separate evidence. This is neither a
full-server sanitizer run nor a full rotation/BG acceptance test.

Native sources match the tested build; binary SHA-256:
`ff06ff9e748d10232b1fcc9f47bde7698bc68a5e45c7f4e11a47a8820e570207`.
See `native-r1/result.json`, `action-audit.json`, `pet-actions-by-guid.json`,
`positive-call-observation.json` and complete runtime logs. The installed
runtime was not replaced.
