#include "BotLife.h"

#include <algorithm>
#include <cstdlib>
#include <limits>
#include <set>
#include <string>
#include <string_view>

#include "Config.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"
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
};

BotLifeConfig config;

char const* ToString(ActivityType activity)
{
    switch (activity)
    {
        case ActivityType::Free:
            return "FREE";
        case ActivityType::Quest:
            return "QUEST";
        case ActivityType::Town:
            return "TOWN";
        case ActivityType::Rest:
            return "REST";
    }

    return "UNKNOWN";
}

char const* ToString(ActivityResult result)
{
    switch (result)
    {
        case ActivityResult::Running:
            return "running";
        case ActivityResult::Completed:
            return "completed";
        case ActivityResult::TemporarilyBlocked:
            return "temporarily-blocked";
        case ActivityResult::Failed:
            return "failed";
    }

    return "unknown";
}

char const* ToString(InterruptReason reason)
{
    switch (reason)
    {
        case InterruptReason::Disabled:
            return "disabled";
        case InterruptReason::NotAllowed:
            return "not-allowed";
        case InterruptReason::PlayerControl:
            return "player-control";
        case InterruptReason::Reset:
            return "reset";
    }

    return "unknown";
}

ActivityType NextActivity(ActivityType activity)
{
    switch (activity)
    {
        case ActivityType::Free:
            return ActivityType::Quest;
        case ActivityType::Quest:
            return ActivityType::Town;
        case ActivityType::Town:
            return ActivityType::Rest;
        case ActivityType::Rest:
            return ActivityType::Free;
    }

    return ActivityType::Free;
}

bool IsEligible(Player* bot)
{
    return config.enabled && bot && config.botGuids.find(bot->GetGUID().GetCounter()) != config.botGuids.end();
}

class TimedStubExecutor final : public ActivityExecutor
{
public:
    explicit TimedStubExecutor(ActivityType type) : _type(type), _elapsed(0) { }

    ActivityType GetType() const override { return _type; }

    void Start(PlayerbotAI&) override
    {
        _elapsed = 0;
    }

    ActivityResult Update(PlayerbotAI&, uint32_t elapsed) override
    {
        uint32_t const available = std::numeric_limits<uint32_t>::max() - _elapsed;
        _elapsed += std::min(elapsed, available);
        if (_elapsed >= config.stubActivityDuration)
            return ActivityResult::Completed;

        return ActivityResult::Running;
    }

    void Interrupt(PlayerbotAI&, InterruptReason) override
    {
        _elapsed = 0;
    }

    void Finish(PlayerbotAI&, ActivityResult) override
    {
        _elapsed = 0;
    }

private:
    ActivityType _type;
    uint32_t _elapsed;
};

std::unique_ptr<ActivityExecutor> CreateExecutor(ActivityType activity)
{
    return std::make_unique<TimedStubExecutor>(activity);
}
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

    if (config.enabled && config.botGuids.empty())
        TC_LOG_WARN("server.loading", "BotLife is enabled but AiPlayerbot.BotLife.BotGuids is empty; no bots are eligible");
}

ActivityContext::ActivityContext() : _activity(ActivityType::Free), _elapsed(0), _active(false) { }

ActivityContext::~ActivityContext() = default;

PlayerbotAIExtensionResult ActivityContext::Update(PlayerbotAI& botAI, uint32_t elapsed)
{
    Player* bot = botAI.GetBot();
    if (!config.enabled)
    {
        Stop(botAI, InterruptReason::Disabled);
        return PlayerbotAIExtensionResult::ContinueBaseAI;
    }

    if (!IsEligible(bot))
    {
        Stop(botAI, InterruptReason::NotAllowed);
        return PlayerbotAIExtensionResult::ContinueBaseAI;
    }

    if (botAI.HasRealPlayerMaster())
    {
        Stop(botAI, InterruptReason::PlayerControl);
        return PlayerbotAIExtensionResult::ContinueBaseAI;
    }

    // The diagnostic slice observes the existing AI but owns no movement or
    // combat. Its timer pauses while the native combat/death engines are active.
    if (!bot->IsAlive() || bot->IsInCombat())
        return PlayerbotAIExtensionResult::ContinueBaseAI;

    if (!_active)
        Start(botAI, _activity, "enabled");

    uint32_t const available = std::numeric_limits<uint32_t>::max() - _elapsed;
    _elapsed += std::min(elapsed, available);

    ActivityResult const result = _executor->Update(botAI, elapsed);
    switch (result)
    {
        case ActivityResult::Running:
        case ActivityResult::TemporarilyBlocked:
            break;
        case ActivityResult::Completed:
            Transition(botAI, NextActivity(_activity), result, "stub-completed");
            break;
        case ActivityResult::Failed:
            Transition(botAI, ActivityType::Free, result, "executor-failed");
            break;
    }

    return PlayerbotAIExtensionResult::ContinueBaseAI;
}

void ActivityContext::Reset(PlayerbotAI& botAI)
{
    Stop(botAI, InterruptReason::Reset);
}

void ActivityContext::Stop(PlayerbotAI& botAI, InterruptReason reason)
{
    if (!_active)
        return;

    Player* bot = botAI.GetBot();
    _executor->Interrupt(botAI, reason);

    TC_LOG_INFO("playerbots.botlife",
        "BotLife bot={} guid={} transition={}->FREE reason={} result=interrupted duration_ms={}",
        bot ? bot->GetName() : "<unknown>", bot ? bot->GetGUID().ToString() : "<none>", ToString(_activity),
        ToString(reason), _elapsed);

    _executor.reset();
    _activity = ActivityType::Free;
    _elapsed = 0;
    _active = false;
}

void ActivityContext::Start(PlayerbotAI& botAI, ActivityType activity, char const* reason)
{
    _activity = activity;
    _elapsed = 0;
    _executor = CreateExecutor(activity);
    _executor->Start(botAI);
    _active = true;

    Player* bot = botAI.GetBot();
    TC_LOG_INFO("playerbots.botlife", "BotLife bot={} guid={} activity={} event=start reason={}",
        bot ? bot->GetName() : "<unknown>", bot ? bot->GetGUID().ToString() : "<none>", ToString(activity), reason);
}

void ActivityContext::Transition(PlayerbotAI& botAI, ActivityType activity, ActivityResult result, char const* reason)
{
    Player* bot = botAI.GetBot();
    ActivityType const previous = _activity;
    uint32_t const duration = _elapsed;

    _executor->Finish(botAI, result);
    _executor.reset();

    TC_LOG_INFO("playerbots.botlife",
        "BotLife bot={} guid={} transition={}->{} reason={} result={} duration_ms={}",
        bot ? bot->GetName() : "<unknown>", bot ? bot->GetGUID().ToString() : "<none>", ToString(previous),
        ToString(activity), reason, ToString(result), duration);

    Start(botAI, activity, reason);
}
}
