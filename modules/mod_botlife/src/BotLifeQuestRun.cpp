#include "BotLifeQuestRun.h"
#include "BotLifeQuestExecutor.h"
#include "BotLifeQuestData.h"
#include "BotLifeQuestRoster.h"

#include "Config.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"

namespace BotLife
{
namespace
{
bool enabled = false;
std::map<uint32_t, uint32_t> roster;
std::map<uint32_t, QuestPlanData> catalogs; // Startup-only, immutable during AI updates.
}

void LoadQuestRunConfig()
{
    enabled = false;
    roster.clear();
    if (!sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestRun.Enabled", false))
        return;
    int32 const guid = sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.QuestRun.BotGuid", 0);
    int32 const quest = sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.QuestRun.QuestId", 0);
    std::string const pairs = sConfigMgr->GetStringDefault("AiPlayerbot.BotLife.QuestRun.Assignments", "");
    if (pairs.empty() && guid > 0 && quest > 0)
        roster.emplace(uint32(guid), uint32(quest));
    else if (!pairs.empty() && guid == 0 && quest == 0)
        roster = ParseQuestRoster(pairs);
    bool matching = !roster.empty() && roster.size() == EligibleBotCount();
    for (auto const& [id, unused] : roster)
        matching = matching && IsEligibleBot(id);
    if (!matching || sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.TravelTest.Enabled", false) ||
        sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestPlan.Enabled", false) ||
        sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestAcquire.Enabled", false))
    {
        roster.clear();
        TC_LOG_ERROR("server.loading", "BotLife QuestRun rejected: require 1..5 explicit assignments matching the exact allowlist, no mixed legacy IDs and all other single-run modes disabled");
        return;
    }
    enabled = true;
}

void InitializeQuestRunData()
{
    if (!enabled)
        return;
    catalogs.clear();
    for (auto const& [guid, quest] : roster)
    {
        auto const [it, inserted] = catalogs.try_emplace(quest);
        if (inserted)
            it->second = LoadQuestPlanData(quest);
        TC_LOG_WARN("server.loading", "BotLife one-shot QuestRun guid={} quest={} catalog={}; native acceptance, combat and turn-in enabled",
            guid, quest, ToString(it->second.error));
    }
}

bool IsQuestRunEnabled() { return enabled; }
uint32_t GetQuestRunBotGuid() { return enabled && roster.size() == 1 ? roster.begin()->first : 0; }

std::vector<uint32_t> GetQuestRunBotGuids()
{
    std::vector<uint32_t> guids;
    if (enabled && roster.size() == EligibleBotCount())
        for (auto const& [guid, quest] : roster)
        {
            if (!IsEligibleBot(guid))
                return {};
            guids.push_back(guid);
        }
    return guids;
}

std::unique_ptr<ActivityExecutor> CreateQuestRunExecutor(PlayerbotAI& ai)
{
    if (!enabled || !ai.GetBot() || GetQuestRunBotGuids().empty())
        return nullptr;
    auto const it = roster.find(ai.GetBot()->GetGUID().GetCounter());
    if (it == roster.end())
        return nullptr;
    auto const catalog = catalogs.find(it->second);
    return catalog == catalogs.end() ? nullptr : MakeQuestExecutor(ai, catalog->second);
}
}
