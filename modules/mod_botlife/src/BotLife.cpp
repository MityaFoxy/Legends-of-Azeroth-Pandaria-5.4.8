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
#include "WorldSession.h"

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

bool IsOnlyEligibleBot(uint32_t guid)
{
    return config.enabled && config.botGuids.size() == 1 && config.botGuids.count(guid);
}

ActivityContext::ActivityContext(ExecutorFactory factory, SingleRunFactory singleRun)
    : _factory(factory), _singleRun(singleRun), _activity(ActivityType::Free), _elapsed(0), _active(false) { }

ActivityContext::~ActivityContext() = default;

void ActivityContext::Observe(PlayerbotAI& botAI)
{
    CheckLifecycle(botAI);
}

bool ActivityContext::CheckLifecycle(PlayerbotAI& botAI)
{
    Player* bot = botAI.GetBot();
    if (!config.enabled)
    {
        Stop(botAI, InterruptReason::Disabled);
        return false;
    }

    if (!IsEligible(bot))
    {
        Stop(botAI, InterruptReason::NotAllowed);
        return false;
    }

    if (botAI.HasRealPlayerMaster())
    {
        Stop(botAI, InterruptReason::PlayerControl);
        return false;
    }

    if (!bot->GetSession() || bot->GetSession()->isLogingOut())
    {
        Stop(botAI, InterruptReason::Logout);
        return false;
    }
    if (bot->IsBeingTeleported())
    {
        Stop(botAI, InterruptReason::Teleport);
        return false;
    }
    if (!bot->IsInWorld() || bot->IsDuringRemoveFromWorld())
    {
        Stop(botAI, InterruptReason::OutOfWorld);
        return false;
    }
    if (!bot->IsAlive())
    {
        Stop(botAI, InterruptReason::Death);
        return false;
    }
    if (_active && (_mapId != bot->GetMapId() || _instanceId != bot->GetInstanceId() ||
        _phaseMask != bot->GetPhaseMask()))
    {
        Stop(botAI, InterruptReason::WorldChanged);
        return false;
    }
    if (bot->IsInCombat())
    {
        if (_active && !_paused)
        {
            _executor->Pause(botAI);
            _paused = true;
            TC_LOG_INFO("playerbots.botlife",
                "BotLife bot={} guid={} activity={} event=pause reason=combat duration_ms={}",
                bot->GetName(), bot->GetGUID().ToString(), ToString(_activity), _elapsed);
        }
        return false;
    }
    return true;
}

PlayerbotAIExtensionResult ActivityContext::Update(PlayerbotAI& botAI, uint32_t elapsed)
{
    // Packet handling may have changed lifecycle state after Observe().
    if (!CheckLifecycle(botAI))
        return PlayerbotAIExtensionResult::ContinueBaseAI;

    if (_paused)
    {
        if (!_executor->Resume(botAI))
        {
            Stop(botAI, InterruptReason::InvalidTarget);
            return PlayerbotAIExtensionResult::ContinueBaseAI;
        }
        _paused = false;
        Player* bot = botAI.GetBot();
        TC_LOG_INFO("playerbots.botlife",
            "BotLife bot={} guid={} activity={} event=resume reason=combat-ended duration_ms={}",
            bot->GetName(), bot->GetGUID().ToString(), ToString(_activity), _elapsed);
        // The interval supplied by the caller may include the paused time.
        return PlayerbotAIExtensionResult::ContinueBaseAI;
    }

    if (!_active)
    {
        if (_singleRun && _singleRunConsumed)
            return PlayerbotAIExtensionResult::ContinueBaseAI;
        Start(botAI, _activity, "enabled");
        if (!_active)
            return PlayerbotAIExtensionResult::ContinueBaseAI;
    }

    uint32_t const available = std::numeric_limits<uint32_t>::max() - _elapsed;
    _elapsed += std::min(elapsed, available);

    ActivityResult const result = _executor->Update(botAI, elapsed);
    if (_singleRun && (result == ActivityResult::Completed || result == ActivityResult::Failed))
    {
        _executor->Finish(botAI, result);
        _executor.reset();
        _active = false;
        return PlayerbotAIExtensionResult::ContinueBaseAI;
    }
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

    return _executor && _executor->ControlsMovement()
        ? PlayerbotAIExtensionResult::SuppressBaseNonCombatAction
        : PlayerbotAIExtensionResult::ContinueBaseAI;
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
    _paused = false;
}

void ActivityContext::Start(PlayerbotAI& botAI, ActivityType activity, char const* reason)
{
    _activity = activity;
    _elapsed = 0;
    _executor = _singleRun ? _singleRun(botAI) : _factory(activity, config.stubActivityDuration);
    _singleRunConsumed = true;
    if (!_executor)
        return;
    _activity = _executor->GetType();
    _executor->Start(botAI);
    _active = true;
    _paused = false;

    Player* bot = botAI.GetBot();
    _mapId = bot->GetMapId();
    _instanceId = bot->GetInstanceId();
    _phaseMask = bot->GetPhaseMask();
    TC_LOG_INFO("playerbots.botlife", "BotLife bot={} guid={} activity={} event=start reason={}",
        bot ? bot->GetName() : "<unknown>", bot ? bot->GetGUID().ToString() : "<none>", ToString(_activity), reason);
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
