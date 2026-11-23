#include "BotLifeConfig.h"

#include <algorithm>
#include <cstdlib>
#include <set>
#include <string>
#include <string_view>

#include "Config.h"
#include "Log.h"
#include "Player.h"
#include "Util.h"

namespace BotLife
{
namespace
{
struct BotLifeConfig
{
    bool enabled = false;
    std::set<uint32> botGuids;
    uint32 stubActivityDuration = 10000;
    bool scheduleEnabled = false;
    ScheduleSettings schedule;
};

BotLifeConfig config;
}

void LoadConfig()
{
    config.enabled = sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.Enabled", false);
    config.botGuids.clear();

    std::string const guidList = sConfigMgr->GetStringDefault("AiPlayerbot.BotLife.BotGuids", "");
    for (std::string_view value : Trinity::Tokenize(guidList, ',', false))
    {
        std::string const token(value);
        uint32 const guid = uint32(std::strtoul(token.c_str(), nullptr, 10));
        if (guid)
            config.botGuids.insert(guid);
    }

    config.stubActivityDuration = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.StubActivityDuration", 10000), 1000, 3600000);
    config.scheduleEnabled = sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.Scheduler.Enabled", false);
    config.schedule.initialSpreadMs = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.InitialSpread", 30000), 0, 3600000);
    config.schedule.questLimit = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.QuestLimit", 1), 1, 20);
    config.schedule.outingLimitMs = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.OutingDuration", 1800000), 1000, 28800000);
    config.schedule.questDurationMs = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.QuestDuration", 600000), 1000,
        int(config.schedule.outingLimitMs));
    config.schedule.townDurationMs = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.TownDuration", 120000), 1000, 3600000);
    config.schedule.restDurationMs = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.RestDuration", 60000), 1000, 3600000);
    config.schedule.durationJitterMs = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.DurationJitter", 15000), 0, 1800000);
    config.schedule.outingCooldownMs = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.OutingCooldown", 300000), 60000, 3600000);
    config.schedule.leisureDurationMs = std::clamp(
        sConfigMgr->GetIntDefault("AiPlayerbot.BotLife.Scheduler.LeisureDuration", 120000), 30000, 3600000);

    if (config.enabled && config.botGuids.empty())
        TC_LOG_WARN("server.loading", "BotLife is enabled but AiPlayerbot.BotLife.BotGuids is empty; no bots are eligible");
}

bool IsEnabled() { return config.enabled; }

bool IsEligible(Player* bot)
{
    return config.enabled && bot && config.botGuids.find(bot->GetGUID().GetCounter()) != config.botGuids.end();
}

bool IsOnlyEligibleBot(uint32_t guid)
{
    return config.enabled && config.botGuids.size() == 1 && config.botGuids.count(guid);
}

bool IsEligibleBot(uint32_t guid)
{
    return config.enabled && config.botGuids.count(guid);
}

uint32_t EligibleBotCount()
{
    return config.enabled ? uint32_t(config.botGuids.size()) : 0;
}

uint32_t StubActivityDuration() { return config.stubActivityDuration; }
bool IsSchedulerEnabled() { return config.scheduleEnabled; }
ScheduleSettings const& GetScheduleSettings() { return config.schedule; }
}
