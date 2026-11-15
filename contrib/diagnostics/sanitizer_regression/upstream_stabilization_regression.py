#!/usr/bin/env python3
"""Guard the verified upstream fixes adopted by the stabilization branch."""

from pathlib import Path
import re
import sys


root = Path(sys.argv[1])


def read(relative: str) -> str:
    return (root / relative).read_text()


def require(text: str, needle: str, label: str) -> None:
    assert needle in text, f"missing {label}: {needle}"


player = read("src/server/game/Entities/Player/Player.cpp")
stats = read("src/server/game/Entities/Unit/StatSystem.cpp")
auras = read("src/server/game/Spells/Auras/SpellAuraEffects.cpp")
spell_info = read("src/server/game/Spells/SpellInfo.cpp")
smart = read("src/server/game/AI/SmartScripts/SmartScript.cpp")
smart_mgr = read("src/server/game/AI/SmartScripts/SmartScriptMgr.cpp")
creature = read("src/server/game/Entities/Creature/Creature.cpp")
unit = read("src/server/game/Entities/Unit/Unit.cpp")
hallow = read("src/server/scripts/Events/hallows_end.cpp")

# Alternate power is owned by its aura/script, not by generic stat recalculation.
require(player, "if (i != POWER_ALTERNATE_POWER)", "alternate-power level initialization guard")
assert stats.count("if (power == POWER_ALTERNATE_POWER)\n        return;") == 3

# Flat health changes must use the pre-clamp health and keep living units above zero.
require(auras, "int64 const health = target->GetHealth();", "pre-clamp health snapshot")
require(auras, "health + (apply ? GetAmount() : -GetAmount())", "symmetric flat-health adjustment")
require(auras, "std::max<int64>(1,", "living flat-health floor")

# Per-level spell scaling starts at BaseLevel and never treats a negative delta as a bonus.
require(spell_info, "level -= int32(_spellInfo->BaseLevel);", "base-level subtraction")
require(spell_info, "if (level < 0)\n                level = 0;", "base-level floor")

# SmartAI accepts SET_COUNTER(0, reset=1), and auto-accepted quests are visible to the client.
require(smart_mgr, "if (e.action.setCounter.value == 0 && !e.action.setCounter.reset)", "resettable zero counter")
require(smart, "if (q->IsAutoAccept())", "auto-accept quest detail gate")
require(smart, "SendQuestGiverQuestDetails(q, (*itr)->GetGUID(), true, true);", "auto-accept quest details")

# Respawning the same GUID retains its rolled level; creature combat/death clears looping work poses.
require(creature, "SelectLevel(cinfo, true);", "respawn level preservation")
require(creature, "if (keepLevel && GetLevel() >= minlevel && GetLevel() <= maxlevel)",
        "bounded respawn level reuse")
assert unit.count("SetEmoteState(EMOTE_ONESHOT_NONE);") >= 2
require(unit, "if (!IsControlledByPlayer())", "uncontrolled creature attack emote reset")

# Hallow's End fire summons run only after the event keeper is in world and tolerate failed summons/AI creation.
constructor_start = hallow.index("npc_hallowend(Creature* creature)")
appeared_start = hallow.index("void JustAppeared() override", constructor_start)
constructor = hallow[constructor_start:appeared_start]
appeared_end = hallow.index("uint32 TimerBegin;", appeared_start)
appeared = hallow[appeared_start:appeared_end]
assert "SummonCreature" not in constructor
require(appeared, "if (FiresInitialized)", "one-time Hallow fire initialization")
require(appeared, "if (Creature* summon = me->SummonCreature", "nullable Hallow summon")
require(appeared, "if (summon->AI())", "nullable Hallow summon AI")
assert "SummonCreature(NPC_HEADLESS_HORSEMAN_FIRE_DND" in appeared
assert "SummonCreature(NPC_HEADLESS_HORSEMAN_FIRE_DND" + ")" not in appeared
assert "->ToCreature()" not in appeared

# Local Playerbots call sites must pass parsed typed packets to the new handlers.
playerbot_sources = "\n".join(
    path.read_text() for path in (root / "modules/mod_playerbots/src").rglob("*.cpp")
)
legacy_handlers = (
    "HandeSetTalentSpecialization", "HandleLearnTalentOpcode", "HandleJoinChannel",
    "HandleSetFactionAtWar", "HandleRepopRequestOpcode", "HandleAreaSpiritHealerQueueOpcode",
    "HandleGroupInviteOpcode", "HandleUseItemOpcode", "HandleBattlemasterJoinOpcode",
    "HandleBattleFieldPortOpcode", "HandleLeaveBattlefieldOpcode", "HandleCancelMountAuraOpcode",
    "HandlePortGraveyardOpcode",
)
for handler in legacy_handlers:
    assert not re.search(rf"->{handler}\(\s*packet\s*\)", playerbot_sources), \
        f"legacy raw WorldPacket call remains for {handler}"
require(playerbot_sources, "WorldPackets::Talent::SetPrimaryTalentTree", "typed talent packet")
require(playerbot_sources, "WorldPackets::Combat::RepopRequest", "typed release packet")
require(playerbot_sources, "WorldPackets::Battleground::BattlemasterJoin", "typed battleground join packet")

# Small semantic tables make the intended boundary behavior explicit.
def level_delta(level: int, base_level: int, max_level: int = 0) -> int:
    if max_level and level > max_level:
        level = max_level
    return max(0, level - base_level)


assert [level_delta(level, 60) for level in (59, 60, 61)] == [0, 0, 1]


def adjusted_health(health: int, amount: int, applying: bool) -> int:
    return max(1, health + (amount if applying else -amount))


assert adjusted_health(521, -20, True) == 501
assert adjusted_health(501, -20, False) == 521
assert adjusted_health(10, -20, True) == 1

print("PASS: upstream packet, SmartAI, stat, spell, creature and Hallow's End fixes")
