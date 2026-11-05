#!/usr/bin/env python3
"""Verify starter-area BG rejection happens before battleground state changes."""

from pathlib import Path
import subprocess
import sys
import tempfile


root = Path(sys.argv[1])
compiler = sys.argv[2]


def method(source, signature):
    begin = source.index(signature)
    brace = source.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


player_source = (root / "src/server/game/Entities/Player/Player.cpp").read_text()
handler_source = (root / "src/server/game/Handlers/BattleGroundHandler.cpp").read_text()
unit_source = (root / "src/server/game/Entities/Unit/Unit.cpp").read_text()

can_leave = method(player_source, "bool CanPlayerLeaveStartingArea(Player const* player)")
teleport = method(player_source, "bool Player::TeleportTo(uint32 mapid")
port = method(handler_source, "void WorldSession::HandleBattleFieldPortOpcode(")
unit_update = method(unit_source, "void Unit::Update(uint32 p_time)")

# A rejected invitation must enter the normal queue-decline path before any
# entry-point, queue, battleground-id, or team mutation takes place.
guard = port.index("if (action && !CanPlayerLeaveStartingArea(_player))")
for mutation in (
    "_player->SetBattlegroundEntryPoint();",
    "bgQueue.RemovePlayer(_player->GetGUID(), false);",
    "_player->SetBattlegroundId(bg->GetInstanceID(), bgTypeId);",
    "_player->SetBGTeam(ginfo.Team);",
):
    assert guard < port.index(mutation)

guard_end = port.index("//some checks if player isn't cheating", guard)
guard_source = port[guard:guard_end]
assert "SendTransferAborted(bg->GetMapId(), TRANSFER_ABORT_UNIQUE_MESSAGE)" in guard_source
assert "action = 0;" in guard_source
assert "RemoveBattlegroundQueueId(bgQueueTypeId)" in port

# Every far teleport uses the same rule and reports the client's native unique
# starter-zone message instead of failing silently.
assert "if (!CanPlayerLeaveStartingArea(this))" in teleport
assert "SendTransferAborted(mapid, TRANSFER_ABORT_UNIQUE_MESSAGE);" in teleport

# Random-bot starter-story completion and neutral-Pandaren faction selection
# use Unit::AddDelayedEvent. Execute those callbacks only after the unit is in
# the world, so they can no longer remain queued forever.
world_guard = unit_update.index("if (!IsInWorld())")
delayed_update = unit_update.index("_functionsDelayed.Update(p_time);")
assert world_guard < delayed_update

source = r'''
#include <cassert>
#include <cstdint>

using uint32 = std::uint32_t;
constexpr uint32 CLASS_DEATH_KNIGHT = 6;
constexpr uint32 RACE_GOBLIN = 9;
constexpr uint32 RACE_WORGEN = 22;
constexpr uint32 RACE_PANDAREN_NEUTRAL = 24;
constexpr uint32 RACE_PANDAREN_ALLIANCE = 25;
constexpr uint32 RACE_PANDAREN_HORDE = 26;
constexpr uint32 QUEST_STATUS_NONE = 0;
constexpr uint32 QUEST_STATUS_COMPLETE = 1;

struct Player
{
    bool IsGameMaster() const { return gm; }
    uint32 GetClass() const { return playerClass; }
    uint32 GetRace() const { return race; }
    uint32 GetMapId() const { return map; }
    uint32 GetLevel() const { return level; }
    bool HasSpell(uint32 spell) const { return spell == 50977 && hasDeathGate; }
    bool IsQuestRewarded(uint32 quest) const { return rewardedQuest == quest; }
    uint32 GetQuestStatus(uint32 quest) const { return completeQuest == quest ? QUEST_STATUS_COMPLETE : QUEST_STATUS_NONE; }

    uint32 playerClass = 1;
    uint32 race = 1;
    uint32 map = 0;
    uint32 level = 1;
    uint32 rewardedQuest = 0;
    uint32 completeQuest = 0;
    bool hasDeathGate = false;
    bool gm = false;
};
'''
source += can_leave
source += r'''
int main()
{
    Player player;

    player.race = RACE_WORGEN;
    player.map = 654;
    player.level = 14;
    assert(!CanPlayerLeaveStartingArea(&player));
    player.rewardedQuest = 26706;
    assert(CanPlayerLeaveStartingArea(&player));
    player.rewardedQuest = 0;
    player.level = 30;
    assert(CanPlayerLeaveStartingArea(&player));
    player.level = 14;
    player.map = 0;
    assert(CanPlayerLeaveStartingArea(&player));

    player = Player{};
    player.race = RACE_GOBLIN;
    player.map = 648;
    player.level = 14;
    assert(!CanPlayerLeaveStartingArea(&player));
    player.completeQuest = 25266;
    assert(CanPlayerLeaveStartingArea(&player));

    player = Player{};
    player.race = RACE_PANDAREN_HORDE;
    player.map = 860;
    player.level = 14;
    assert(!CanPlayerLeaveStartingArea(&player));
    player.completeQuest = 31450;
    assert(CanPlayerLeaveStartingArea(&player));

    player = Player{};
    player.race = RACE_PANDAREN_NEUTRAL;
    player.map = 0;
    player.level = 90;
    assert(!CanPlayerLeaveStartingArea(&player));

    player = Player{};
    player.playerClass = CLASS_DEATH_KNIGHT;
    player.map = 609;
    player.level = 79;
    assert(!CanPlayerLeaveStartingArea(&player));
    player.hasDeathGate = true;
    assert(CanPlayerLeaveStartingArea(&player));

    player = Player{};
    player.race = RACE_WORGEN;
    player.map = 654;
    player.level = 14;
    player.gm = true;
    assert(CanPlayerLeaveStartingArea(&player));
}
'''

with tempfile.TemporaryDirectory(prefix="loa-bg-starting-area-") as directory:
    cpp = Path(directory) / "regression.cpp"
    exe = Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-fno-pie",
            "-no-pie",
            str(cpp),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)
