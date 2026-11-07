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

Do not use `PetIsDeadValue` as evidence that a missing pet died: its current
implementation treats any persisted pet row as dead when no pet is loaded.
This separate legacy value is not changed by the two-trigger repair.

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

The run also contains 78 accepted `call pet 1` attempts. Their repetition alone
does not establish successful summons or a new defect; correlate current pets,
slots, deaths, dismissals and exotic-pet eligibility before changing that path.

The old `CastShootAction` reads `EQUIPMENT_SLOT_RANGED`, while the core's ranged
weapon lookup reads main hand. That discrepancy alone does not prove a broken
wand path: with no old-slot item the Action retains the correct `shoot` name,
and native checks validate the weapon. Shoot remains an audit item, with no
speculative change included here.
