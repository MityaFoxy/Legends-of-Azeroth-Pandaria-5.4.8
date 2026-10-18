#!/usr/bin/env python3
"""Execute production quest policy/player/config readers with read-only core doubles."""
import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]
source_dir = root / "modules/mod_botlife/src"
native = (source_dir / "BotLifeQuestData.cpp").read_text()
diagnostic = (source_dir / "BotLifeQuestDiagnostic.cpp").read_text()
quest_def = (root / "src/server/game/Quests/QuestDef.h").read_text()


def definition(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


# Guard boundaries that do not require a fake database or world grid.
for forbidden in ("AddQuest(", "CompleteQuest(", "KilledMonsterCredit(", "RewardQuest(",
                  "MoveTo(", "TeleportTo(", "SetQuestStatus(", "CanAddQuest("):
    assert forbidden not in re.sub(r"//[^\n]*", "", native + diagnostic), forbidden
assert native.count("WorldDatabase.") == 1
reader = definition(native, "QuestPlayerSnapshot ReadQuestPlayer(")
assert "WorldDatabase" not in reader
assert "LIMIT 4097" in native and "GetRowCount() > 4096" in native
assert "entries.size() > 256" in native
assert "spawn->phaseid || spawn->phaseGroup" in native
assert "pool_creature" in native and "game_event_creature" in native
assert "GetCreatureQuestRelationMapHACK" in native
assert "GetCreatureQuestInvolvedRelationReverseBounds" in native
assert "creature.KillCredit" in native
assert "ControlsMovement()" not in diagnostic
config = (root / "modules/mod_botlife/config/botlife.conf.dist").read_text()
assert "AiPlayerbot.BotLife.QuestPlan.Enabled = 0" in config
assert "AiPlayerbot.BotLife.QuestPlan.QuestId = 0" in config

prefix = r'''
#include "BotLifeQuestPlan.h"
#include <cassert>
#include <set>
#include <string>
#include <vector>
using uint32 = uint32_t;
using int32 = int32_t;
using uint8 = uint8_t;
using int8 = int8_t;
using namespace BotLife;
#define QUEST_OBJECTIVES_COUNT 4
'''
enums = "\n".join(definition(quest_def, "enum " + name) + ";" for name in
                  ("QuestFlags :", "QuestStatus :", "QuestObjectiveType"))
objective = definition(quest_def, "struct QuestObjective\n") + ";"
mocks = r'''
struct Quest
{
    bool unavailable = false, turnIn = false, seasonal = false;
    uint32 special = 0, flags = 0, flagsEx = 0, limit = 0, sourceItem = 0, sourceSpell = 0;
    uint32 script = 0, suggested = 0, info = 0;
    std::vector<QuestObjective> objectives;
    static inline bool enabled = true;
    bool IsUnavailable() const { return unavailable; }
    bool IsTurnIn() const { return turnIn; }
    bool IsSeasonal() const { return seasonal; }
    static bool IsTakingQuestEnabled(uint32) { return enabled; }
#define GETTER(name, field) uint32 name() const { return field; }
    GETTER(GetSpecialFlags, special)
    GETTER(GetFlags, flags)
    GETTER(GetFlagsEx, flagsEx)
    GETTER(GetLimitTime, limit)
    GETTER(GetSrcItemId, sourceItem)
    GETTER(GetSrcSpell, sourceSpell)
    GETTER(GetScriptId, script)
    GETTER(GetSuggestedPlayers, suggested)
    GETTER(GetQuestInfoID, info)
#undef GETTER
    auto const& GetObjectives() const { return objectives; }
};
struct Map { bool instance = false; bool Instanceable() const { return instance; } };
struct Player
{
    Map map;
    bool world = true, alive = true, teleport = false, bg = false, flight = false, transport = false, vehicle = false;
    bool level = true, race = true, classOk = true, dependencies = true, canTake = true, log = true;
    QuestStatus status = QUEST_STATUS_NONE;
    uint32 count = 0, takeCalls = 0;
    bool IsInWorld() { return world; }
    bool IsAlive() { return alive; }
    bool IsBeingTeleported() { return teleport; }
    Map* GetMap() { return &map; }
    bool InBattleground() { return bg; }
    bool IsInFlight() { return flight; }
    bool GetTransport() { return transport; }
    bool GetVehicle() { return vehicle; }
    uint32 GetMapId() { return 1; }
    uint32 GetPhaseMask() { return 1; }
    float GetPositionX() { return 0; }
    float GetPositionY() { return 0; }
    float GetPositionZ() { return 0; }
    uint32 GetQuestObjectiveCounter(uint32) { return count; }
    QuestStatus GetQuestStatus(uint32) { return status; }
#define CHECK(name, field) bool name(Quest const*, bool msg) { assert(!msg); return field; }
    CHECK(SatisfyQuestLevel, level)
    CHECK(SatisfyQuestRace, race)
    CHECK(SatisfyQuestClass, classOk)
    CHECK(SatisfyQuestDependentQuests, dependencies)
#undef CHECK
    bool CanTakeQuest(Quest const*, bool msg) { assert(!msg); ++takeCalls; return canTake; }
    bool SatisfyQuestLog(bool msg) { assert(!msg); return log; }
};
struct ObjectMgr { Quest const* quest = nullptr; Quest const* GetQuestTemplate(uint32) { return quest; } } mgr;
ObjectMgr* sObjectMgr = &mgr;
struct Config
{
    bool enable = false;
    int bot = 6, quest = 42;
    bool GetBoolDefault(char const*, bool) { return enable; }
    int GetIntDefault(std::string const& key, int) { return key.ends_with("BotGuid") ? bot : quest; }
} config;
Config* sConfigMgr = &config;
bool allowed = true, travel = false, enabled = false;
uint32 botGuid = 0, questId = 0;
bool IsOnlyEligibleBot(uint32 guid) { return allowed && guid == 6; }
bool IsTravelTestEnabled() { return travel; }
#define TC_LOG_ERROR(...) ((void)0)
'''
tests = r'''
int main()
{
    Quest quest;
    quest.objectives.push_back({10, 42, QUEST_OBJECTIVE_MONSTER, 0, 200, 5, 0, {}, {}});
    assert(Supported(quest));
    for (uint32 Quest::* field : {&Quest::special, &Quest::flagsEx, &Quest::limit,
        &Quest::sourceItem, &Quest::sourceSpell, &Quest::script, &Quest::info})
    {
        quest.*field = 1;
        assert(!Supported(quest));
        quest.*field = 0;
    }
    for (uint32 flag : {QUEST_FLAGS_DAILY, QUEST_FLAGS_WEEKLY, QUEST_FLAGS_AUTO_COMPLETE,
        QUEST_FLAGS_AUTO_ACCEPT, QUEST_FLAGS_AUTO_SUBMIT, QUEST_FLAGS_AUTO_TAKE,
        QUEST_FLAGS_TRACKING_EVENT, QUEST_FLAGS_FLAGS_PVP, QUEST_FLAGS_COMPLETION_AREA_TRIGGER})
    {
        quest.flags = flag;
        assert(!Supported(quest));
    }
    quest.flags = 0;
    quest.suggested = 2;
    assert(!Supported(quest));
    quest.suggested = 0;
    QuestObjective& obj = quest.objectives[0];
    for (uint8 type = QUEST_OBJECTIVE_ITEM; type < MAX_QUEST_OBJECTIVE_TYPE; ++type)
    {
        obj.Type = type;
        assert(!Supported(quest));
    }
    obj.Type = QUEST_OBJECTIVE_MONSTER;
    obj.Amount = -1;
    assert(!Supported(quest));
    obj.Amount = 5;
    obj.StorageIndex = -1;
    assert(!Supported(quest));
    obj.StorageIndex = 0;
    obj.Flags = 1;
    assert(!Supported(quest));
    obj.Flags = 0;
    quest.objectives.push_back(obj);
    assert(!Supported(quest)); // duplicate objective/slot
    quest.objectives.pop_back();

    mgr.quest = &quest;
    QuestPlanData data{42, "Test", QuestPlanReason::None, {}, {}, {{10, 200, 5, {}}}};
    Player player;
    assert(ReadQuestPlayer(data, player).eligibility == QuestPlanReason::None);
    for (auto const& test : std::vector<std::pair<bool Player::*, QuestPlanReason>>{
        {&Player::level, QuestPlanReason::Level}, {&Player::race, QuestPlanReason::RaceOrClass},
        {&Player::classOk, QuestPlanReason::RaceOrClass}, {&Player::dependencies, QuestPlanReason::Prerequisites},
        {&Player::canTake, QuestPlanReason::NativeEligibility}, {&Player::log, QuestPlanReason::QuestLogFull}})
    {
        player.*test.first = false;
        assert(ReadQuestPlayer(data, player).eligibility == test.second);
        player.*test.first = true;
    }
    Quest::enabled = false;
    assert(ReadQuestPlayer(data, player).eligibility == QuestPlanReason::QuestDisabled);
    Quest::enabled = true;
    player.map.instance = true;
    assert(!ReadQuestPlayer(data, player).validContext);
    player.map.instance = false;
    player.world = false;
    assert(!ReadQuestPlayer(data, player).validContext);
    player.world = true;
    for (bool Player::* field : {&Player::teleport, &Player::bg, &Player::flight, &Player::transport, &Player::vehicle})
    {
        player.*field = true;
        assert(!ReadQuestPlayer(data, player).validContext);
        player.*field = false;
    }
    player.status = QUEST_STATUS_INCOMPLETE;
    player.count = 3;
    player.canTake = false; // Existing quests must not be rejected by CanTakeQuest.
    uint32 before = player.takeCalls;
    auto snapshot = ReadQuestPlayer(data, player);
    assert(snapshot.progress == QuestProgress::Active && snapshot.eligibility == QuestPlanReason::None);
    assert(snapshot.counters.at(10) == 3 && before == player.takeCalls);
    player.status = QUEST_STATUS_COMPLETE;
    assert(ReadQuestPlayer(data, player).progress == QuestProgress::Complete);
    player.status = QUEST_STATUS_REWARDED;
    assert(ReadQuestPlayer(data, player).progress == QuestProgress::Rewarded);
    player.status = QUEST_STATUS_FAILED;
    assert(ReadQuestPlayer(data, player).progress == QuestProgress::Failed);
    quest.objectives[0].Amount = 9;
    assert(ReadQuestPlayer(data, player).eligibility == QuestPlanReason::CatalogChanged);
    mgr.quest = nullptr;
    assert(ReadQuestPlayer(data, player).eligibility == QuestPlanReason::CatalogChanged);

    LoadQuestPlanConfig();
    assert(!enabled);
    config.enable = true;
    LoadQuestPlanConfig();
    assert(enabled && botGuid == 6 && questId == 42);
    for (int invalid : {0, -1})
    {
        config.quest = invalid;
        LoadQuestPlanConfig();
        assert(!enabled);
        config.quest = 42;
        config.bot = invalid;
        LoadQuestPlanConfig();
        assert(!enabled);
        config.bot = 6;
    }
    allowed = false;
    LoadQuestPlanConfig();
    assert(!enabled);
    allowed = true;
    travel = true;
    LoadQuestPlanConfig();
    assert(!enabled);
}
'''
with tempfile.TemporaryDirectory(prefix="botlife-quest-native-") as temp:
    cpp = pathlib.Path(temp) / "test.cpp"
    exe = pathlib.Path(temp) / "test"
    cpp.write_text(prefix + enums + objective + mocks + definition(native, "bool Supported(") +
                   reader + definition(diagnostic, "void LoadQuestPlanConfig()") + tests)
    subprocess.run([compiler, "-std=c++20", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-UNDEBUG", "-I", str(source_dir), str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("BotLife native quest reader/config contracts passed")
