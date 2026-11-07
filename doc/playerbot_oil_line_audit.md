# Playerbot apply oil / stay line — source audit and verification

Target: original MoP 5.4.8. Date: 2026-11-06.
Observed: `action-followup-20261106/after-seals/action-audit.json` contains
591 `apply oil` and 74 `stay line` UNKNOWN. Both references lack an Action.

## Stay line

`Strategy.cpp` uses it as the alternative to `move random`.
The historical Playerbot implementation builds rows of up to five members
around the master, with 2-yard spacing; it is not an alias for stopping.
Reference (architecture, not retail mechanics):
[mangoszero StayActions.cpp, pinned revision](https://github.com/mangoszero/server/blob/b7fface6b1bd3b036211dcde1bff39cc6da503e4/src/modules/Bots/playerbot/strategy/actions/StayActions.cpp).
The same layout is already implemented locally by `LineFormation`,
`MoveFormation::MoveLine` and `MoveSingleLine` in `Formations.cpp`.

Minimal restoration: expose the existing line location without changing the
configured formation, then use the existing `MovementAction::MoveTo` path.
Require a live master in the same group/map instance/phase, a usable roster,
normal noncombat movement, and an actual displacement. Preserve cast/control/
vehicle/transport gates and BG ownership, consistent with local FollowAction.
Do not stop current movement or return success on invalid/no-op destinations.
Filter unloaded roster entries and center using the actual loaded roster size;
the current Group::GetMembersCount insertion can exceed the vector bounds.

Tests: actual layout and Action, 1/2/5/6-member rows, unloaded members,
master absent/self/foreign instance/phase, combat/BG/cast/root, explicit
formation unchanged, already at destination, rejected collision/path.
A positive live movement observation is distinct from factory resolution.

## Apply oil

Existing calls are in Hunter/Druid/Priest strategies. The related older
AzerothCore implementation searches owned consumables, targets the main-hand
weapon and preserves its existing temporary enchant:
[ImbueAction.cpp](https://github.com/mod-playerbots/mod-playerbots/blob/405f81196161017eebae3ee7a612d786a3ed2a9d/src/Ai/Base/Actions/ImbueAction.cpp).
Its unconditional success and old specialization indices must not be copied.

Local DB/DBC evidence is saved under `tests/oil-line-20261106/` in handoff:
`oil-items.tsv`, `oil-dbc.json` (including source paths and SHA-256).
Supported existing oils: 20744–20750, 22521, 22522. Use spells 25117–25123,
28013, 28017; temporary enchants 2623–2629, 2677, 2678. These have negative
five-use charges. SpellLevels.MaxLevel is **200**, matching local descriptions;
SpellEquippedItems supplies the weapon type masks. No special item scripts
are assigned to these nine IDs. There are currently no instances of these
oils in the character database.

Exceptional and Blessed variants are outside this first repair: one local
Exceptional template has no use spell, and Blessed has a distinct undead
purpose and level cap. No guessed substitutes or automatic supplies.

Minimal restoration: choose a usable owned oil in backpack/bags, prefer
spirit oils for healers and intellect oils for casters using current MoP spec
classification; no caster benefit for Hunter/Feral. Require a bare usable
main-hand weapon, correct item/spell match and native item requirements,
including the DBC MaxLevel. Do not overwrite poisons/imbues or use bank items.
Call native `Player::CastItemUseSpell` with the actual item target, preserving
item charges, cooldowns and Spell validation. Check for the expected enchant
or a matching accepted in-progress cast; dispatch alone is not success.
Mirror the native item-use entry checks (ownership, usable location, trade,
CanUseItem, arena restrictions, binding and item-script hook).

Tests: real item selection/action, no oil, bank-only, unsupported/mismatched
item, cap 200/201, wrong weapon mask, existing enchant, wrong owner/trade,
combat/casting/movement/vehicle, item-use failure, accepted cast and enchant,
charges handled only by native code. Controlled live fixture must verify
actual enchant and charge use; any supplied test item is identified and
removed afterwards. Normal BG absence of oils only verifies the negative path.

## Implementation and bounded verification

Both real Actions are registered in the common `ActionContext`. The factory
regression checks the actual `move random -> stay line` alternative as well
as the oil factory. `LineFormation` keeps its existing geometry and is used
without replacing the selected formation. The roster insertion now uses the
filtered live roster, avoiding an out-of-range iterator when persistent group
membership includes unavailable players.

`oil_action_regression.py` compiles the real oil Action against bounded world,
item and native-cast doubles; `stay_line_regression.py` compiles the real line
layout and Action against bounded collision/navigation doubles. Both passed
Clang and GCC with ASan/UBSan. The factory test and existing party/follow
regression passed Clang ASan/UBSan. These tests are included in the CMake
`class-ai` test label. They do not certify a full-server sanitizer run or real
movement through a particular map's navmesh.

For the native oil check, the default-off console option
`AiPlayerbot.OilDiagnostics = 1` enables
`npcbot oiltest <random bot GUID> supply|run|status|cleanup`. It accepts only
logged-in random bots, supplies one identified Minor Wizard Oil (20744),
uses the registered Action, and removes only that item's GUID and the test
enchant on the original weapon. Existing weapon/enchant and bank contents
are not replaced. A positive result requires native enchant 2623, one charge
consumed, a useless repeat with no additional charge use, and verified cleanup.

The first build attempt exposed a missing include dependency:
`DatabaseEnv.h` must precede `Battleground.h`. The corrected full build passed.
Native attempt `level60-native-r2` was stopped after the test controller sent
`supply` before asynchronous level/gear refresh had finished: the bot still
had level-90 gear above the DBC cap. The command correctly refused it; no oil
was created. That attempt's 104414 decisions have zero UNKNOWN, but its oil
fixture did not pass. The controller now waits for actual supply acknowledgement.
Attempt r3 stopped in preflight because of one stale online flag after the
previous server's exit 0. No server was running; r4 explicitly permits only
reviewed GUID 53 for the core's normal startup cleanup. No manual SQL UPDATE.

The level-60 retry r4 exposed another fixture prerequisite: GUID 24's backpack
has all 16 slots occupied and no equipped bags. Native `CanStoreNewItem`
therefore cannot supply the oil. Existing items were preserved. The next
fixture uses Mage GUID 68: 13 occupied backpack slots, a bare item-level-72
weapon, and the same verified binary SHA-256. After r4 exit 0, GUID 64 retained
an online flag with no running server; r5 reviews this exact stale flag too.
This repeated shutdown-state defect is recorded separately from Action repair.

## Final native result (2026-11-06, 13:10:28 MSK)

`level60-native-r5` used the verified `-j4` binary with SHA-256
`0f3c490e4ff77645b347f1e72328ec0ee6ad87f13a71d74868f00117f584ebfd`:
100 level-60 bots, 360 seconds after population readiness, 12 console rounds,
server and detached unit exit 0. This is the normal build, not server ASan.
All 218457 Action decisions in both final Behavior logs contain **0 UNKNOWN**.
Natural strategy outcomes include oil 570 USELESS and line 54 USELESS; native
positive oil proof comes from the separate controlled Action invocation.

Mage 68 received oil GUID 428320 (20744). Actual native use put enchant 2623
on original weapon GUID 426889 (21452), consuming one of five charges.
The second invocation was useless and preserved four charges. Native cleanup
removed the oil and its enchant. Post-stop SQL verified the item and inventory
reference absent, original weapon still equipped by 68, and temporary enchant
fields zero. Evidence: `level60-native-r5/native-oil.json` and `console.log`.
No existing items were deleted and no weapon was substituted.

BG telemetry observed 89 entrants, 86 combatants, 72 damage dealers and
48 resurrected bots, without full-cycle proof. Live group arrival for
`stay line` remains unverified; bounded tests cover geometry and movement
failure contracts. The old `mana potion` defect remains open even though it
was not observed here. The installed runtime binary was not activated.

An independent shutdown defect repeated: online GUID 53 after r2, 64 after
r4, 90 after r5 persisted after exit 0 with no worldserver process. This does
not invalidate the verified oil cleanup, but must not be called clean DB
shutdown. No speculative shutdown fix or manual SQL flag clearing was made.
Duplicate test executables were deduplicated by hard link after SHA verification;
all evidence paths remain available (`binary-storage.json`).
