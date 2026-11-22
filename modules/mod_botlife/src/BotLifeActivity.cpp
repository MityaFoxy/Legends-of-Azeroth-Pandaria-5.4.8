#include "BotLife.h"

#include <algorithm>
#include <limits>

#include "Player.h"
#include "PlayerbotAI.h"

namespace BotLife
{
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
        case InterruptReason::Combat:
            return "combat";
        case InterruptReason::Death:
            return "death";
        case InterruptReason::RecoveryTimeout:
            return "death-recovery-timeout";
        case InterruptReason::Teleport:
            return "teleport";
        case InterruptReason::OutOfWorld:
            return "out-of-world";
        case InterruptReason::Logout:
            return "logout";
        case InterruptReason::WorldChanged:
            return "world-changed";
        case InterruptReason::InvalidTarget:
            return "invalid-target";
    }

    return "unknown";
}

class TimedStubExecutor final : public ActivityExecutor
{
public:
    TimedStubExecutor(ActivityType type, uint32_t duration) : _type(type), _duration(duration), _elapsed(0) { }

    ActivityType GetType() const override { return _type; }

    void Start(PlayerbotAI&) override
    {
        _elapsed = 0;
    }

    ActivityResult Update(PlayerbotAI&, uint32_t elapsed) override
    {
        uint32_t const available = std::numeric_limits<uint32_t>::max() - _elapsed;
        _elapsed += std::min(elapsed, available);
        if (_elapsed >= _duration)
            return ActivityResult::Completed;

        return ActivityResult::Running;
    }

    void Pause(PlayerbotAI&) override { }

    bool Resume(PlayerbotAI&) override { return true; } // Timer stubs have no world target.

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
    uint32_t _duration;
    uint32_t _elapsed;
};

class RestExecutor final : public ActivityExecutor
{
public:
    explicit RestExecutor(uint32_t duration) : _duration(duration) { }

    ActivityType GetType() const override { return ActivityType::Rest; }

    void Start(PlayerbotAI& botAI) override
    {
        _elapsed = 0;
        _resting = NeedsRest(*botAI.GetBot());
        if (_resting)
            Sit(*botAI.GetBot());
    }

    ActivityResult Update(PlayerbotAI& botAI, uint32_t elapsed) override
    {
        Player& bot = *botAI.GetBot();
        uint32_t const available = std::numeric_limits<uint32_t>::max() - _elapsed;
        _elapsed += std::min(elapsed, available);

        if (!_resting)
        {
            if (!NeedsRest(bot))
                return ActivityResult::Completed;
            _resting = true;
        }

        if (Recovered(bot) || _elapsed >= _duration)
        {
            Stand(bot);
            _resting = false;
            return ActivityResult::Completed;
        }

        Sit(bot);
        return ActivityResult::Running;
    }

    void Pause(PlayerbotAI& botAI) override { Stand(*botAI.GetBot()); }
    bool Resume(PlayerbotAI&) override { return true; }
    void Interrupt(PlayerbotAI& botAI, InterruptReason) override { Reset(*botAI.GetBot()); }
    void Finish(PlayerbotAI& botAI, ActivityResult) override { Reset(*botAI.GetBot()); }
    bool HoldsNonCombat() const override { return _resting; }

private:
    static bool UsesMana(Player const& bot)
    {
        return bot.GetPowerType() == POWER_MANA && bot.GetMaxPower(POWER_MANA) > 0;
    }

    static bool NeedsRest(Player const& bot)
    {
        return bot.GetHealthPct() < 50.0f || (UsesMana(bot) && bot.GetPowerPct(POWER_MANA) < 30.0f);
    }

    static bool Recovered(Player const& bot)
    {
        return bot.GetHealthPct() >= 95.0f && (!UsesMana(bot) || bot.GetPowerPct(POWER_MANA) >= 90.0f);
    }

    void Sit(Player& bot)
    {
        if (!bot.IsSitState())
        {
            bot.SetStandState(UNIT_STAND_STATE_SIT);
            _ownsSit = true;
        }
    }

    void Stand(Player& bot)
    {
        if (_ownsSit && bot.IsSitState())
            bot.SetStandState(UNIT_STAND_STATE_STAND);
        _ownsSit = false;
    }

    void Reset(Player& bot)
    {
        Stand(bot);
        _elapsed = 0;
        _resting = false;
    }

    uint32_t _duration;
    uint32_t _elapsed = 0;
    bool _resting = false;
    bool _ownsSit = false;
};

std::unique_ptr<ActivityExecutor> CreateExecutor(ActivityType activity, uint32_t duration)
{
    if (activity == ActivityType::Rest)
        return std::make_unique<RestExecutor>(duration);

    return std::make_unique<TimedStubExecutor>(activity, duration);
}
}
