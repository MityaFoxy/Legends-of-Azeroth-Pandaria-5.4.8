#include "BotLifeQuestDiagnostic.h"
#include "BotLifeQuestData.h"
#include "BotLifeTravelTest.h"

#include "Config.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"

namespace BotLife
{
namespace
{
bool enabled = false;
uint32 botGuid = 0, questId = 0;
// Written once during world startup, before map updates; never refreshed from AI threads.
QuestPlanData catalog;

void LogCandidate(uint32 guid, uint32 quest, char const* role, QuestSpawn const& spawn)
{
    TC_LOG_INFO("playerbots.botlife", "BotLife QuestPlan guid={} quest={} role={} candidate={} entry={} map={} phase={} position=({},{},{}) liveChecks=pending",
        guid, quest, role, spawn.guid, spawn.entry, spawn.mapId, spawn.phaseMask, spawn.x, spawn.y, spawn.z);
}

class QuestPlanExecutor final : public ActivityExecutor
{
public:
    ActivityType GetType() const override { return ActivityType::Quest; }
    void Start(PlayerbotAI& ai) override
    {
        Player* bot = ai.GetBot();
        if (!bot)
            return;
        QuestPlan const plan = BuildQuestPlan(catalog, ReadQuestPlayer(catalog, *bot));
        _result = plan.stage == QuestPlanStage::Rejected ? ActivityResult::Failed : ActivityResult::Completed;
        uint32 const guid = bot->GetGUID().GetCounter();
        TC_LOG_INFO("playerbots.botlife", "BotLife QuestPlan read-only guid={} quest={} title={} stage={} reason={}",
            guid, plan.questId, catalog.title, ToString(plan.stage), ToString(plan.reason));
        if (plan.starter)
            LogCandidate(guid, plan.questId, "starter", *plan.starter);
        for (QuestObjectivePlan const& objective : plan.objectives)
        {
            TC_LOG_INFO("playerbots.botlife", "BotLife QuestPlan guid={} quest={} objective={} credit={} remaining={}/{}",
                guid, plan.questId, objective.id, objective.entry, objective.remaining, objective.required);
            if (objective.candidate)
                LogCandidate(guid, plan.questId, "kill", *objective.candidate);
        }
        if (plan.ender)
            LogCandidate(guid, plan.questId, "ender", *plan.ender);
    }
    ActivityResult Update(PlayerbotAI&, uint32_t) override { return _result; }
    void Pause(PlayerbotAI&) override { }
    bool Resume(PlayerbotAI&) override { return false; } // A snapshot must not be resumed as an executable plan.
    void Interrupt(PlayerbotAI&, InterruptReason) override { }
    void Finish(PlayerbotAI&, ActivityResult) override { }
private:
    ActivityResult _result = ActivityResult::Failed;
};
}

void LoadQuestPlanConfig()
{
    enabled = false;
    if (!sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestPlan.Enabled", false))
        return;
    int32 const configuredBot = sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.QuestPlan.BotGuid", 0);
    int32 const configuredQuest = sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.QuestPlan.QuestId", 0);
    if (configuredBot <= 0 || configuredQuest <= 0 || !IsOnlyEligibleBot(uint32(configuredBot)) || IsTravelTestEnabled())
    {
        TC_LOG_ERROR("server.loading", "BotLife QuestPlan rejected: require one matching allowlisted bot, positive QuestId and TravelTest disabled");
        return;
    }
    botGuid = uint32(configuredBot);
    questId = uint32(configuredQuest);
    enabled = true;
}

void InitializeQuestPlanData()
{
    if (!enabled)
        return;
    catalog = LoadQuestPlanData(questId);
    TC_LOG_INFO("server.loading", "BotLife QuestPlan read-only cache quest={} reason={} objectives={} starters={} enders={}; restart after world-data reload",
        questId, ToString(catalog.error), catalog.objectives.size(), catalog.starters.size(), catalog.enders.size());
}

bool IsQuestPlanEnabled() { return enabled; }

std::unique_ptr<ActivityExecutor> CreateQuestPlanExecutor(PlayerbotAI& ai)
{
    if (!enabled || !IsOnlyEligibleBot(botGuid) || !ai.GetBot() || ai.GetBot()->GetGUID().GetCounter() != botGuid)
        return nullptr;
    return std::make_unique<QuestPlanExecutor>();
}
}
