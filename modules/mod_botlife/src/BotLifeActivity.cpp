#include "BotLife.h"

#include <algorithm>
#include <limits>

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

std::unique_ptr<ActivityExecutor> CreateExecutor(ActivityType activity, uint32_t duration)
{
    return std::make_unique<TimedStubExecutor>(activity, duration);
}
}
