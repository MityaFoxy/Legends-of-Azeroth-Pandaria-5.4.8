#include "BotLifeServices.h"
#include "BotLifePreparation.h"
#include "BotLifeReadiness.h"
#include "BotLifeSafety.h"
#include "Log.h"
#include "MotionMaster.h"
#include "MoveSpline.h"
#include "Player.h"
#include "PlayerbotAI.h"

#include <algorithm>
#include <limits>

namespace BotLife
{
ScheduleNeeds ReadScheduleNeeds(PlayerbotAI& ai)
{
    if (!ai.GetBot())
        return {false, false, false};
    Readiness const readiness = ReadCombatReadiness(*ai.GetBot());
    PreparationDecision const decision = EvaluateReadiness(readiness, false);
    bool const recovery = readiness.health < 75 || (readiness.usesMana && readiness.mana < 50) ||
        readiness.resurrectionSickness;
    return {recovery, decision.state == Preparation::Repair,
        decision.state == Preparation::Ready};
}

namespace
{
class ServiceExecutor final : public ActivityExecutor
{
public:
    ServiceExecutor(ActivityType type, uint32_t duration) : _type(type), _duration(duration) { }
    ActivityType GetType() const override { return _type; }

    void Start(PlayerbotAI& ai) override
    {
        _elapsed = _settledMs = 0;
        _result = ActivityResult::Running;
        _safety = std::make_unique<QuestSafety>(*ai.GetBot());
        if (_type == ActivityType::Town)
            _service = std::make_unique<QuestPreparation>(ai, *_safety);
    }

    ActivityResult Update(PlayerbotAI& ai, uint32_t elapsed) override
    {
        if (_result != ActivityResult::Running)
            return _result;
        Player& bot = *ai.GetBot();
        _elapsed += std::min(elapsed, std::numeric_limits<uint32_t>::max() - _elapsed);
        if (_elapsed >= uint64_t(_duration) + (_type == ActivityType::Leisure ? 30000u : 0u))
            return End(ai, ActivityResult::Failed, "activity-budget");
        if (_service)
        {
            PreparationResult const result = _service->Update(elapsed);
            if (result == PreparationResult::Failed)
                return End(ai, ActivityResult::Failed, _service->Reason());
            if (result == PreparationResult::Ready)
                return End(ai, ActivityResult::Completed, "service-ready");
            return ActivityResult::Running;
        }

        bool const usesMana = bot.GetPowerType() == POWER_MANA && bot.GetMaxPower(POWER_MANA) > 0;
        if (!_safety->CanRest() || bot.GetHealthPct() < 75 ||
            (usesMana && bot.GetPowerPct(POWER_MANA) < 50) || bot.HasAura(15007))
            return End(ai, ActivityResult::Failed, "leisure-unsafe-or-recovery");
        // Never sit on a foreign spline, mount or active cast. Waiting is bounded
        // by this activity's budget and does not cancel somebody else's motion.
        if (bot.IsMounted() || bot.IsNonMeleeSpellCasted(false) ||
            bot.GetMotionMaster()->GetCurrentMovementGeneratorType() != IDLE_MOTION_TYPE ||
            !bot.movespline->Finalized())
        {
            Stand(ai);
            return ActivityResult::TemporarilyBlocked;
        }
        if (!bot.IsSitState())
        {
            bot.SetStandState(UNIT_STAND_STATE_SIT);
            _ownsSit = true;
        }
        _settledMs += std::min(elapsed, std::numeric_limits<uint32_t>::max() - _settledMs);
        if (_settledMs >= _duration)
            return End(ai, ActivityResult::Completed, "leisure-completed");
        return ActivityResult::Running;
    }

    void Pause(PlayerbotAI& ai) override
    {
        if (_service)
            _service->Pause();
        Stand(ai);
    }
    bool Resume(PlayerbotAI& ai) override
    {
        return _result == ActivityResult::Running && ai.GetBot() &&
            (_service || _safety->CanRest());
    }
    void Interrupt(PlayerbotAI& ai, InterruptReason) override { End(ai, ActivityResult::Failed, "interrupted"); }
    void Finish(PlayerbotAI& ai, ActivityResult) override { Pause(ai); }
    bool ControlsMovement() const override { return _service && _service->ControlsMovement(); }
    bool HoldsNonCombat() const override
    {
        return _result == ActivityResult::Running && (!_service || _service->HoldsNonCombat());
    }

private:
    void Stand(PlayerbotAI& ai)
    {
        if (_ownsSit && ai.GetBot()->IsSitState())
            ai.GetBot()->SetStandState(UNIT_STAND_STATE_STAND);
        _ownsSit = false;
    }
    ActivityResult End(PlayerbotAI& ai, ActivityResult result, char const* reason)
    {
        Pause(ai);
        _result = result;
        TC_LOG_INFO("playerbots.botlife", "BotLife service guid={} activity={} result={} reason={} duration_ms={}",
            ai.GetBot()->GetGUID().GetCounter(), ToString(_type), ToString(result), reason, _elapsed);
        return result;
    }

    ActivityType _type;
    uint32_t _duration, _elapsed = 0, _settledMs = 0;
    ActivityResult _result = ActivityResult::Failed;
    bool _ownsSit = false;
    std::unique_ptr<QuestSafety> _safety;
    std::unique_ptr<QuestPreparation> _service;
};
}

std::unique_ptr<ActivityExecutor> CreateServiceExecutor(ActivityType activity, uint32_t duration)
{
    return std::make_unique<ServiceExecutor>(activity, duration);
}
}
