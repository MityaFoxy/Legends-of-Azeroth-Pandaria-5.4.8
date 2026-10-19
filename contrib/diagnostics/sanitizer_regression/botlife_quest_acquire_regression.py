#!/usr/bin/env python3
"""Run production acceptance gates/executor with map-local core doubles and real travel/planning."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]
source = root / "modules/mod_botlife/src"
interaction = (source / "BotLifeQuestInteraction.cpp").read_text()
executor = (source / "BotLifeQuestAcquire.cpp").read_text()


def definition(text, signature):
    start = text.index(signature)
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


for forbidden in ("TeleportTo(", "CompleteQuest(", "RewardQuest(", "KilledMonsterCredit(",
                  "SetQuestStatus(", "WorldDatabase", "CharacterDatabase", "HandleQuestgiverAcceptQuestOpcode"):
    assert forbidden not in interaction + executor, forbidden
assert interaction.count("bot.AddQuestAndCheckCompletion(") == 1
assert "GetCreatureBySpawnId" in interaction and "FindConnectedPlayer" not in interaction
assert "AiPlayerbot.BotLife.QuestAcquire.Enabled = 0" in (source.parent / "config/botlife.conf.dist").read_text()
assert "CreateQuestAcquireExecutor" in (source / "mod_botlife.cpp").read_text()
assert "GetQuestAcquireBotGuid()" in (source / "BotLifeTravelTest.cpp").read_text()
# Keep the diagnostic read-only: enabling acquisition is a separate opt-in.
assert "TryAcceptQuest" not in (source / "BotLifeQuestDiagnostic.cpp").read_text()

mocks = r'''
#include "BotLife.h"
#include "BotLifeTravel.h"
#include "BotLifeQuestPlan.h"
#include <cassert>
#include <cstring>
#include <string>
using uint32 = uint32_t;
using int32 = int32_t;
constexpr uint32 UNIT_STATE_ROOT=1, UNIT_STATE_STUNNED=2, UNIT_STATE_LOST_CONTROL=4;
constexpr uint32 QUEST_FLAGS_PARTY_ACCEPT=8, MAX_QUEST_LOG_SIZE=25;
enum QuestStatus { QUEST_STATUS_NONE, QUEST_STATUS_INCOMPLETE, QUEST_STATUS_COMPLETE, QUEST_STATUS_FAILED };
#define TC_LOG_INFO(...) ((void)0)
#define TC_LOG_ERROR(...) ((void)0)
#define TC_LOG_WARN(...) ((void)0)
struct Quest { bool party=false; bool HasFlag(uint32) const { return party; } };
struct ObjectMgr
{
    Quest quest;
    bool missing=false, broken=false;
    Quest const* GetQuestTemplate(uint32) { return missing ? nullptr : &quest; }
    bool IsBrokenQuest(uint32) { return broken; }
} manager;
auto sObjectMgr = &manager;
struct Creature;
struct Map
{
    Creature* npc=nullptr;
    Creature* GetCreatureBySpawnId(uint32 id) { return id == 10 ? npc : nullptr; }
};
struct Creature
{
    Map* map=nullptr;
    bool world=true, alive=true, combat=false, offers=true;
    uint32 entry=20, phase=1;
    bool IsInWorld() { return world; }
    bool IsAlive() { return alive; }
    bool IsInCombat() { return combat; }
    uint32 GetEntry() { return entry; }
    Map* GetMap() { return map; }
    uint32 GetPhaseMask() { return phase; }
    bool hasQuest(uint32) { return offers; }
};
struct Guid { uint32 GetCounter() { return 6; } };
class Player
{
public:
    Map map;
    Creature npc;
    bool group=false, combat=false, casting=false, visible=true, los=true;
    bool interact=true, take=true, add=true, nativeEffect=true;
    uint32 state=0, accepts=0, slot=MAX_QUEST_LOG_SIZE;
    QuestStatus status=QUEST_STATUS_NONE;
    BotLife::QuestPlayerSnapshot snapshot;
    Player()
    {
        map.npc=&npc; npc.map=&map;
        snapshot.validContext=true; snapshot.mapId=1; snapshot.phaseMask=1;
    }
    bool GetGroup() { return group; }
    bool IsInCombat() { return combat; }
    bool HasUnitState(uint32 flags) { return state & flags; }
    bool IsNonMeleeSpellCasted(bool) { return casting; }
    uint32 GetMapId() { return snapshot.mapId; }
    uint32 GetInstanceId() { return 0; }
    uint32 GetPhaseMask() { return snapshot.phaseMask; }
    Map* GetMap() { return &map; }
    Guid GetGUID() { return {}; }
    bool CanSeeOrDetect(Creature*) { return visible; }
    bool CanInteractWithQuestGiver(Creature*) { return interact; }
    bool IsWithinLOSInMap(Creature*) { return los; }
    bool CanTakeQuest(Quest const*, bool) { return take; }
    bool CanAddQuest(Quest const*, bool) { return add; }
    void AddQuestAndCheckCompletion(Quest const*, Creature*)
    {
        ++accepts;
        if (nativeEffect) { status=QUEST_STATUS_INCOMPLETE; slot=0; }
    }
    uint32 FindQuestSlot(uint32) { return slot; }
    QuestStatus GetQuestStatus(uint32) { return status; }
};
class PlayerbotAI
{
public:
    Player* bot;
    Player* GetBot() { return bot; }
};
struct Config
{
    bool enabled=true, travel=false, diagnostic=false;
    int32 bot=6, quest=100;
    bool GetBoolDefault(char const* key, bool)
    {
        std::string k=key;
        if (k.find("TravelTest") != k.npos) return travel;
        if (k.find("QuestPlan") != k.npos) return diagnostic;
        if (k.find("QuestRun") != k.npos) return false;
        return enabled;
    }
    int32 GetIntDefault(char const* key, int32)
    {
        return std::string(key).find("BotGuid") != std::string::npos ? bot : quest;
    }
} config;
auto sConfigMgr=&config;

namespace BotLife
{
bool allowed=true;
bool IsOnlyEligibleBot(uint32_t guid) { return allowed && guid == 6; }
char const* ToString(InterruptReason) { return "cancelled"; }
QuestPlayerSnapshot ReadQuestPlayer(QuestPlanData const&, Player& bot)
{
    auto snapshot=bot.snapshot;
    if (bot.status != QUEST_STATUS_NONE) snapshot.progress=QuestProgress::Active;
    return snapshot;
}
bool enabled=false;
uint32 botGuid=6, questId=100;
QuestPlanData catalog;
struct Motion
{
    bool valid=true, blocked=false, arrived=false;
    TravelMoveResult move=TravelMoveResult::Started;
    TravelMotion poll=TravelMotion::Moving;
    uint32 moves=0;
} motion;
class NativeTravelMovement final : public TravelMovement
{
    bool owned=false;
public:
    explicit NativeTravelMovement(PlayerbotAI&) { }
    bool IsValid(TravelTarget const&) const override { return motion.valid; }
    bool IsBlocked() override { return motion.blocked; }
    bool HasArrived(TravelTarget const&) const override { return motion.arrived; }
    TravelMoveResult Move(TravelTarget const&) override
    {
        ++motion.moves;
        owned=motion.move == TravelMoveResult::Started;
        return motion.move;
    }
    TravelMotion Poll() const override { return motion.poll; }
    bool HasProgressed() const override { return motion.arrived; }
    bool OwnsMovement() const override { return owned; }
    void Release() override { owned=false; }
};
'''

tests = r'''
}
using namespace BotLife;
void reset()
{
    manager={}; motion={}; config={}; allowed=true;
    catalog={}; catalog.questId=100; catalog.error=QuestPlanReason::None;
    QuestSpawn giver{10,20,1,1,100,0,0};
    catalog.starters={giver}; catalog.enders={giver};
    catalog.objectives={{1,30,3,{{11,30,1,1,110,0,0}}}};
}
int main()
{
    // Actual native gate body: every failure below must avoid native acceptance.
    for (int failure=0; failure<27; ++failure)
    {
        reset(); Player bot; auto giver=catalog.starters[0]; Map other;
        switch (failure)
        {
            case 0: catalog.error=QuestPlanReason::UnsupportedQuest; break;
            case 1: bot.snapshot.validContext=false; break;
            case 2: bot.snapshot.eligibility=QuestPlanReason::QuestLogFull; break;
            case 3: bot.status=QUEST_STATUS_INCOMPLETE; break;
            case 4: manager.missing=true; break;
            case 5: manager.broken=true; break;
            case 6: bot.group=true; break;
            case 7: manager.quest.party=true; break;
            case 8: bot.combat=true; break;
            case 9: bot.state=UNIT_STATE_ROOT; break;
            case 10: bot.casting=true; break;
            case 11: giver.mapId=2; break;
            case 12: giver.phaseMask=2; break;
            case 13: bot.map.npc=nullptr; break;
            case 14: bot.npc.world=false; break;
            case 15: bot.npc.alive=false; break;
            case 16: bot.npc.combat=true; break;
            case 17: bot.npc.entry=21; break;
            case 18: bot.npc.map=&other; break;
            case 19: bot.npc.phase=2; break;
            case 20: bot.visible=false; break;
            case 21: bot.npc.offers=false; break;
            case 22: bot.interact=false; break;
            case 23: bot.los=false; break;
            case 24: bot.take=false; break;
            case 25: bot.add=false; break;
            case 26: giver.guid=11; break;
        }
        char const* reason=nullptr;
        assert(!TryAcceptQuest(bot,catalog,giver,reason));
        assert(reason && bot.accepts==0);
    }
    {
        reset(); Player bot; char const* reason=nullptr;
        assert(TryAcceptQuest(bot,catalog,catalog.starters[0],reason));
        assert(bot.accepts==1 && std::strcmp(reason,"accepted")==0);
        assert(!TryAcceptQuest(bot,catalog,catalog.starters[0],reason));
        assert(bot.accepts==1);
    }
    {
        reset(); Player bot; bot.nativeEffect=false; char const* reason=nullptr;
        assert(!TryAcceptQuest(bot,catalog,catalog.starters[0],reason));
        assert(bot.accepts==1 && std::strcmp(reason,"acceptance-not-confirmed")==0);
    }
    {
        reset(); Player bot; PlayerbotAI ai{&bot}; QuestAcquireExecutor run(ai);
        run.Start(ai);
        assert(run.GetType()==ActivityType::Quest);
        assert(run.Update(ai,0)==ActivityResult::Running && run.ControlsMovement());
        assert(bot.accepts==0);
        run.Pause(ai); assert(!run.ControlsMovement());
        assert(run.Resume(ai));
        assert(run.Update(ai,600000)==ActivityResult::Running); // Combat time excluded.
        assert(motion.moves==2);
        motion.arrived=true;
        assert(run.Update(ai,10)==ActivityResult::Completed);
        assert(bot.accepts==1 && !run.ControlsMovement());
        assert(run.Update(ai,10)==ActivityResult::Completed && bot.accepts==1);
        run.Finish(ai,ActivityResult::Completed);
    }
    // Cancellation, changed eligibility, absent giver, timeout, ownership loss,
    // recovery exhaustion, blocked interaction and native rejection are terminal.
    for (int failure=0; failure<10; ++failure)
    {
        reset(); Player bot; PlayerbotAI ai{&bot}; QuestAcquireExecutor run(ai);
        run.Start(ai); run.Update(ai,0);
        switch (failure)
        {
            case 0: run.Interrupt(ai,InterruptReason::PlayerControl); break;
            case 1: bot.snapshot.eligibility=QuestPlanReason::QuestLogFull; break;
            case 2: bot.map.npc=nullptr; motion.arrived=true; break;
            case 3: break; // elapsed exceeds travel budget
            case 4: motion.poll=TravelMotion::Lost; break;
            case 5: motion.poll=TravelMotion::RecoveryExhausted; break;
            case 6: motion.valid=false; break;
            case 7: bot.npc.combat=true; motion.arrived=true; break;
            case 8: bot.add=false; motion.arrived=true; break;
            case 9: allowed=false; break;
        }
        assert(run.Update(ai,failure==3 ? 120001 : 10)==ActivityResult::Failed);
        assert(!run.ControlsMovement() && bot.accepts==0);
        motion.arrived=true;
        assert(run.Update(ai,10)==ActivityResult::Failed && bot.accepts==0);
    }
    {
        reset(); Player bot; PlayerbotAI ai{&bot}; QuestAcquireExecutor run(ai);
        run.Start(ai); run.Update(ai,0); run.Pause(ai);
        bot.status=QUEST_STATUS_INCOMPLETE;
        assert(!run.Resume(ai) && bot.accepts==0);
    }
    {
        reset(); Player bot; PlayerbotAI ai{&bot}; QuestAcquireExecutor run(ai);
        catalog.starters.clear(); run.Start(ai);
        assert(run.Update(ai,0)==ActivityResult::Failed && motion.moves==0 && bot.accepts==0);
    }
    {
        reset(); Player bot; PlayerbotAI ai{&bot}; QuestAcquireExecutor run(ai);
        run.Start(ai); motion.blocked=true; motion.arrived=true;
        assert(run.Update(ai,0)==ActivityResult::Running && bot.accepts==0);
        assert(run.Update(ai,120001)==ActivityResult::Failed && bot.accepts==0);
    }
    for (int invalid=0; invalid<7; ++invalid)
    {
        reset();
        switch (invalid)
        {
            case 0: config.enabled=false; break;
            case 1: config.bot=0; break;
            case 2: config.quest=-1; break;
            case 3: allowed=false; break;
            case 4: config.travel=true; break;
            case 5: config.diagnostic=true; break;
            case 6: config.bot=9; break;
        }
        LoadQuestAcquireConfig(); assert(!enabled);
    }
    reset(); LoadQuestAcquireConfig(); assert(enabled && botGuid==6 && questId==100);
}
'''
with tempfile.TemporaryDirectory(prefix="botlife-quest-acquire-") as directory:
    cpp = pathlib.Path(directory) / "test.cpp"
    binary = pathlib.Path(directory) / "test"
    cpp.write_text(mocks + definition(interaction, "char const* QuestAcquireRejection(") +
                   definition(interaction, "bool TryAcceptQuest(") +
                   definition(executor, "class QuestAcquireExecutor final") + ";\n" +
                   definition(executor, "void LoadQuestAcquireConfig()") + tests)
    subprocess.run([compiler, "-std=c++20", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-UNDEBUG", "-I", str(source), "-I", str(root / "modules/mod_playerbots/src/AI"),
                    str(cpp), str(source / "BotLifeTravel.cpp"), str(source / "BotLifeQuestPlan.cpp"),
                    "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("BotLife native quest acceptance, travel lifecycle and opt-in gates passed")
