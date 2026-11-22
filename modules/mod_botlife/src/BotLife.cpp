#include "BotLife.h"
#include "BotLifeConfig.h"
#include "BotLifeSchedule.h"

#include <algorithm>
#include <limits>

#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "WorldSession.h"

namespace BotLife
{
namespace
{
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
    if (!IsEnabled())
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
    if (!bot->IsInWorld() || bot->IsDuringRemoveFromWorld())
    {
        Stop(botAI, InterruptReason::OutOfWorld);
        return false;
    }
    if (_active && (_mapId != bot->GetMapId() || _instanceId != bot->GetInstanceId() ||
        _phaseMask != bot->GetPhaseMask()))
    {
        Stop(botAI, InterruptReason::WorldChanged);
        return false;
    }
    if (!CheckDeathRecovery(botAI))
        return false;
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
            "BotLife bot={} guid={} activity={} event=resume reason={} duration_ms={}",
            bot->GetName(), bot->GetGUID().ToString(), ToString(_activity),
            _recoveringFromDeath ? "resurrected" : "combat-ended", _elapsed);
        _recoveringFromDeath = false;
        // The interval supplied by the caller may include the paused time.
        return PlayerbotAIExtensionResult::ContinueBaseAI;
    }

    if (!_active)
    {
        if (_singleRun && _singleRunConsumed)
            return PlayerbotAIExtensionResult::ContinueBaseAI;
        if (!_singleRun && IsSchedulerEnabled() && !_schedule)
        {
            Player* bot = botAI.GetBot();
            _schedule = std::make_unique<LifeSchedule>(bot->GetGUID().GetCounter(), GetScheduleSettings());
            ActivityPlan const plan = _schedule->InitialPlan();
            Start(botAI, plan.activity, plan.reason, plan.durationMs);
        }
        else
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
            if (_schedule)
            {
                ActivityPlan const plan = _schedule->Complete(_activity, result, _elapsed);
                Transition(botAI, plan.activity, result, plan.reason, plan.durationMs);
            }
            else
                Transition(botAI, NextActivity(_activity), result, "stub-completed");
            break;
        case ActivityResult::Failed:
            if (_schedule)
            {
                ActivityPlan const plan = _schedule->Complete(_activity, result, _elapsed);
                Transition(botAI, plan.activity, result, plan.reason, plan.durationMs);
            }
            else
                Transition(botAI, ActivityType::Free, result, "executor-failed");
            break;
    }

    return _executor && (_executor->ControlsMovement() || _executor->HoldsNonCombat())
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
    {
        _schedule.reset();
        return;
    }

    Player* bot = botAI.GetBot();
    _executor->Interrupt(botAI, reason);

    TC_LOG_INFO("playerbots.botlife",
        "BotLife bot={} guid={} transition={}->FREE reason={} result=interrupted duration_ms={}",
        bot ? bot->GetName() : "<unknown>", bot ? bot->GetGUID().ToString() : "<none>", ToString(_activity),
        ToString(reason), _elapsed);

    _executor.reset();
    _schedule.reset();
    _activity = ActivityType::Free;
    _elapsed = 0;
    _active = false;
    _paused = false;
    _recoveringFromDeath = false;
}

void ActivityContext::Start(PlayerbotAI& botAI, ActivityType activity, char const* reason, uint32_t duration)
{
    _activity = activity;
    _elapsed = 0;
    uint32_t const selectedDuration = _singleRun ? 0 : (duration ? duration : StubActivityDuration());
    _executor = _singleRun ? _singleRun(botAI) : _factory(activity, selectedDuration);
    _singleRunConsumed = true;
    if (!_executor)
        return;
    _activity = _executor->GetType();
    _executor->Start(botAI);
    _active = true;
    _paused = false;
    _recoveringFromDeath = false;

    Player* bot = botAI.GetBot();
    _mapId = bot->GetMapId();
    _instanceId = bot->GetInstanceId();
    _phaseMask = bot->GetPhaseMask();
    TC_LOG_INFO("playerbots.botlife", "BotLife bot={} guid={} activity={} event=start reason={} budget_ms={}",
        bot ? bot->GetName() : "<unknown>", bot ? bot->GetGUID().ToString() : "<none>", ToString(_activity), reason,
        selectedDuration);
}

void ActivityContext::Transition(PlayerbotAI& botAI, ActivityType activity, ActivityResult result, char const* reason,
    uint32_t nextDuration)
{
    Player* bot = botAI.GetBot();
    ActivityType const previous = _activity;
    uint32_t const completedDuration = _elapsed;

    _executor->Finish(botAI, result);
    _executor.reset();

    TC_LOG_INFO("playerbots.botlife",
        "BotLife bot={} guid={} transition={}->{} reason={} result={} duration_ms={}",
        bot ? bot->GetName() : "<unknown>", bot ? bot->GetGUID().ToString() : "<none>", ToString(previous),
        ToString(activity), reason, ToString(result), completedDuration);

    Start(botAI, activity, reason, nextDuration);
}
}
