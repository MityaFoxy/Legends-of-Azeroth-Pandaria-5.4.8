# Protection equipment selection — 2026-11-07

This repair continues the selective class-AI restoration. Invalid equipment
can prevent native tank spells from executing even when their factories and
strategies are correct.

## Confirmed defect and sources

`RandomItemManager::ShouldEquipWeaponForSpec` mixed weapon subclasses with
`ITEM_SUBCLASS_ARMOR_SHIELD` in its Protection offhand sets. In the actual
`ItemPrototype.h` enums, shield and polearm both have numeric subclass 6.
The global `_viable_slots` map includes two-hand weapons in the offhand
candidate set. The old predicate therefore accepted a two-handed polearm
for Protection Warrior and Paladin. The saved reproduction's source SHA
matched the source before this change.

The native selection chain in `RandomItemManager.cpp` separates weapons
(`CanEquipWeapon`) from shields/held armor (`CanEquipSubArmor`). The latter
already permits shields for both Protection specializations. The core's
`Player::FindEquipSlot` and equip validation separately enforce weapon slots,
dual wield and Titan's Grip. Removing two-hand support from the shared slot
map would affect other specializations and is unnecessary for this defect.

## Narrow repair

Only Protection Warrior/Paladin weapon candidates must have weapon ItemClass
and inventory type `INVTYPE_WEAPON` or `INVTYPE_WEAPONMAINHAND`. Their existing
one-hand subclass sets remain unchanged. Armor shield subclasses are removed
from these two weapon sets; real shields continue through the armor path.
The other specializations and global slot map retain their existing policy.
There is no inventory mutation or automatic rerandomization in this repair.
Already-issued invalid equipment needs a separately reviewed recovery plan.

## Verification

`tank_equipment_regression.py` compiles the actual initialization, private
predicate and public weapon/subarmor filters with real repository enums and
bounded player/item data. Before the fix it fails on the polearm assertion.
Afterward GCC 15 and Clang ASan/UBSan pass: accepted one-hand classes, rejected
two-hand/offhand-only/foreign-class candidates, valid shield path, and sample
non-Protection policies including Fury, Rogue, Guardian and all Monk specs.
Three intentional mutations are detected by assertions: removing ItemClass
validation, removing inventory-type validation, and rejecting Warrior shields.
The regression is included in CTest's `class-ai` label and the existing CI jobs.

The opt-in console command `npcbot equipmentcheck <random bot GUID>` requires
`AiPlayerbot.EquipmentDiagnostics=1` and a live Protection Warrior/Paladin.
It calls the actual `FindBestItemForLevelAndEquip` selector for a weapon and
shield, reports item class/subclass/inventory type and verifies equipped GUIDs
are unchanged. Despite the selector's name it returns an item template ID;
it does not create or equip an item. The selector shuffles its existing cache
as it does during normal selection.

Autonomous build/probe unit: `loa-tank-selection-20261107-r1.service`.
Evidence directory: `wow_mop_codex_handoff/tests/commit-tank-20261107/`.
The build uses -j4 and a private test binary/configuration. The native probe
disables the forced BG/level test workload, observes 100 logged-in bots for
at least 65 seconds, checks candidates for both Protection classes, stops
gracefully and checks online flags and complete Action traces.

**Native PASS: November 7, 11:52:07 MSK.** The -j4 worldserver build and the
unit/server exit codes were 0. After 100 bots logged in, 65.78 seconds of
observation covered five selection rounds for Warriors 17/28/50 (spec 73)
and Paladin 51 (spec 66). All 40 candidates were valid one-hand weapons or
shields; all 20 paired observations confirmed unchanged equipped GUIDs.
For example, Warrior 28 selected weapon 21392 and shield 21485; Paladin 51
selected weapon 77580 and shield 21269. The probe uses current specializations,
not the historical Protection GUIDs from older tests.

The complete Behavior audit contains 36391 decisions and zero UNKNOWN.
Its 740 FAILED outcomes require contextual analysis and do not establish
other defects by themselves. After graceful shutdown there were zero online
characters and no remaining worldserver. Evidence is in `native-r1/`:
`result.json`, `native-equipment.json`, `action-audit.json`, `build.log` and
the complete console/Behavior logs. Native sources match the tested snapshot;
binary SHA-256 is
`972a7d47c00f138c00bbc17f1a441f494e4bc5d23ae5576e22c26968b0e538f2`.

This proves native selection against the current database at level 60, not
physical equip/recovery, a full BG cycle or a full-server sanitizer run.
The installed runtime was not replaced and no existing equipment was repaired.

## Checkpoint commits

Before this repair the accumulated work was split into six commits:

- `a9b6ae6c`: Rogue triggers and native finisher checks.
- `d14b7079`: Hunter pet slot persistence and guarded recovery tooling.
- `dbe346b1`: formation, oil and mana-potion Actions.
- `9314dd0b`: class factory registrations and spell contracts.
- `5606ea7a`: SQL queue drain and final offline ordering.
- `12bbc6b5`: autonomous supervision, Action auditing and recorded evidence.

Both GCC and Clang passed all 12 existing `class-ai` tests with mutation checks;
the Python multi-level controller passed 14 tests. The behavior diagnostic and
BG resurrection telemetry regressions also pass with Clang; the shared soak
controller passes all 40 tests. Previous native mana/shutdown PASS remains
recorded in `playerbot_mana_shutdown_audit.md`. The main objective remains
class-AI restoration; zero UNKNOWN does not complete every rotation.
