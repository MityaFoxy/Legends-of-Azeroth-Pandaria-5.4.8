#!/usr/bin/env python3
"""Verify random Pandaren finish and recover the native faction transfer."""

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


manager_source = (root / "modules/mod_playerbots/src/Manager/RandomPlayerbotMgr.cpp").read_text()
handler_source = (root / "src/server/game/Handlers/MiscHandler.cpp").read_text()

on_login = method(manager_source, "void RandomPlayerbotMgr::OnBotLoginInternal(")
handler = method(handler_source, "void WorldSession::HandleSelectFactionOpcode(")

# A newly created neutral bot must satisfy the same final-quest gate used by
# CanPlayerLeaveStartingArea before it sends the faction-selection opcode.
neutral = on_login.index("if (bot->GetRace() == RACE_PANDAREN_NEUTRAL)")
complete = on_login.index("CompletePandarenFactionQuest(bot);", neutral)
select = on_login.index("session->HandleSelectFactionOpcode(packet);", neutral)
assert complete < select
assert on_login.index("if (!HasCompletedPandarenFactionQuest(bot))", complete) < select

# Legacy recovery is deliberately narrower than a generic teleport: selected
# race, map 860 and persisted homebind must all agree with playercreateinfo.
recovery = on_login.index("else if (IsSelectedPandaren(bot) && bot->GetMapId() == 860)")
homebind_guard = on_login.index("if (!HasExpectedPandarenHomebind(bot, start))", recovery)
recovery_complete = on_login.index("CompletePandarenFactionQuest(bot);", homebind_guard)
recovery_teleport = on_login.index("bot->TeleportTo(start)", recovery_complete)
recovery_save = on_login.index("bot->SaveToDB();", recovery_teleport)
assert recovery < homebind_guard < recovery_complete < recovery_teleport < recovery_save

# Core must validate the choice, roll race/faction back when the native
# TeleportTo gate rejects it, and persist only after a transfer was accepted.
choice_guard = handler.index("if (choice != JOIN_THE_HORDE && choice != JOIN_THE_ALLIANCE)")
quest_credit = handler.index("if (_player->GetQuestStatus(31450) == QUEST_STATUS_INCOMPLETE)")
set_race = handler.index("_player->SetRace(newRace);")
teleport = handler.index("if (!_player->TeleportTo(location))")
rollback = handler.index("_player->SetRace(RACE_PANDAREN_NEUTRAL);", teleport)
save = handler.index("_player->SaveToDB();", teleport)
assert choice_guard < quest_credit < set_race < teleport < rollback < save
assert handler.count("_player->SaveToDB();") == 1
assert handler.count("_player->TeleportTo(location)") == 1

helpers = "\n".join(
    method(manager_source, signature)
    for signature in (
        "bool IsSelectedPandaren(Player const* bot)",
        "bool HasCompletedPandarenFactionQuest(Player const* bot)",
        "void CompletePandarenFactionQuest(Player* bot)",
        "bool HasExpectedPandarenHomebind(Player const* bot, WorldLocation const& start)",
    )
)

source = r'''
#include <cassert>
#include <cmath>
#include <cstdint>

using uint8 = std::uint8_t;
using uint32 = std::uint32_t;

constexpr uint8 RACE_PANDAREN_NEUTRAL = 24;
constexpr uint8 RACE_PANDAREN_ALLIANCE = 25;
constexpr uint8 RACE_PANDAREN_HORDE = 26;
constexpr uint32 QUEST_STATUS_NONE = 0;
constexpr uint32 QUEST_STATUS_COMPLETE = 1;
constexpr uint32 PandarenFactionQuest = 31450;
constexpr float PandarenHomebindTolerance = 1.0f;

struct WorldLocation
{
    uint32 GetMapId() const { return map; }
    float GetPositionX() const { return x; }
    float GetPositionY() const { return y; }
    float GetPositionZ() const { return z; }

    uint32 map = 0;
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct Player
{
    uint8 GetRace() const { return race; }
    bool IsQuestRewarded(uint32 quest) const { return rewarded && quest == PandarenFactionQuest; }
    uint32 GetQuestStatus(uint32 quest) const
    {
        return complete && quest == PandarenFactionQuest ? QUEST_STATUS_COMPLETE : QUEST_STATUS_NONE;
    }
    void CompleteQuest(uint32 quest, bool completely, bool fromCommand)
    {
        assert(quest == PandarenFactionQuest);
        assert(completely);
        assert(fromCommand);
        complete = true;
        ++completeCalls;
    }

    uint8 race = RACE_PANDAREN_NEUTRAL;
    bool rewarded = false;
    bool complete = false;
    uint32 completeCalls = 0;
    uint32 m_homebindMapId = 860;
    float m_homebindX = 0.0f;
    float m_homebindY = 0.0f;
    float m_homebindZ = 0.0f;
};
'''
source += helpers
source += r'''
int main()
{
    Player bot;
    assert(!IsSelectedPandaren(&bot));
    assert(!HasCompletedPandarenFactionQuest(&bot));
    CompletePandarenFactionQuest(&bot);
    assert(HasCompletedPandarenFactionQuest(&bot));
    assert(bot.completeCalls == 1);
    CompletePandarenFactionQuest(&bot);
    assert(bot.completeCalls == 1);

    WorldLocation horde{1, 1357.62f, -4373.55f, 26.13f};
    bot.race = RACE_PANDAREN_HORDE;
    bot.m_homebindMapId = 1;
    bot.m_homebindX = horde.x;
    bot.m_homebindY = horde.y;
    bot.m_homebindZ = horde.z;
    assert(IsSelectedPandaren(&bot));
    assert(HasExpectedPandarenHomebind(&bot, horde));
    bot.m_homebindZ += 1.01f;
    assert(!HasExpectedPandarenHomebind(&bot, horde));

    WorldLocation alliance{0, -8960.02f, 516.10f, 96.36f};
    bot = Player{};
    bot.race = RACE_PANDAREN_ALLIANCE;
    bot.m_homebindMapId = 0;
    bot.m_homebindX = alliance.x;
    bot.m_homebindY = alliance.y;
    bot.m_homebindZ = alliance.z;
    assert(HasExpectedPandarenHomebind(&bot, alliance));
    alliance.map = 1;
    assert(!HasExpectedPandarenHomebind(&bot, alliance));
}
'''

with tempfile.TemporaryDirectory(prefix="loa-pandaren-faction-") as directory:
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
