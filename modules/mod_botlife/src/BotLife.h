#ifndef _BOTLIFE_H
#define _BOTLIFE_H

#include <cstdint>
#include <memory>

#include "PlayerbotAIExtension.h"

class PlayerbotAI;

namespace BotLife
{
enum class ActivityType : uint8_t
{
    Free,
    Quest,
    Town,
    Rest
};

enum class ActivityResult : uint8_t
{
    Running,
    Completed,
    TemporarilyBlocked,
    Failed
};

enum class InterruptReason : uint8_t
{
    Disabled,
    NotAllowed,
    PlayerControl,
    Reset,
    Combat,
    Death,
    Teleport,
    OutOfWorld,
    Logout,
    WorldChanged,
    InvalidTarget
};

class ActivityExecutor
{
public:
    virtual ~ActivityExecutor() = default;

    virtual ActivityType GetType() const = 0;
    virtual void Start(PlayerbotAI& botAI) = 0;
    virtual ActivityResult Update(PlayerbotAI& botAI, uint32_t elapsed) = 0;
    // Release transient control (including owned movement), retain the plan.
    virtual void Pause(PlayerbotAI& botAI) = 0;
    // Revalidate the plan before resuming. False cancels it safely.
    virtual bool Resume(PlayerbotAI& botAI) = 0;
    virtual void Interrupt(PlayerbotAI& botAI, InterruptReason reason) = 0;
    virtual void Finish(PlayerbotAI& botAI, ActivityResult result) = 0;
    // True only while the executor still owns its non-combat movement.
    virtual bool ControlsMovement() const { return false; }
};

char const* ToString(ActivityType activity);
char const* ToString(ActivityResult result);
char const* ToString(InterruptReason reason);
std::unique_ptr<ActivityExecutor> CreateExecutor(ActivityType activity, uint32_t duration);

class ActivityContext final : public PlayerbotAIExtension
{
public:
    using ExecutorFactory = std::unique_ptr<ActivityExecutor> (*)(ActivityType, uint32_t);
    using SingleRunFactory = std::unique_ptr<ActivityExecutor> (*)(PlayerbotAI&);
    explicit ActivityContext(ExecutorFactory factory = &CreateExecutor, SingleRunFactory singleRun = nullptr);
    ~ActivityContext() override;

    void Observe(PlayerbotAI& botAI) override;
    PlayerbotAIExtensionResult Update(PlayerbotAI& botAI, uint32_t elapsed) override;
    void Reset(PlayerbotAI& botAI) override;

    ActivityType GetActivity() const { return _activity; }
    bool IsActive() const { return _active; }
    bool IsPaused() const { return _paused; }

private:
    bool CheckLifecycle(PlayerbotAI& botAI);
    void Stop(PlayerbotAI& botAI, InterruptReason reason);
    void Start(PlayerbotAI& botAI, ActivityType activity, char const* reason);
    void Transition(PlayerbotAI& botAI, ActivityType activity, ActivityResult result, char const* reason);

    std::unique_ptr<ActivityExecutor> _executor;
    ExecutorFactory _factory;
    SingleRunFactory _singleRun;
    bool _singleRunConsumed = false;
    ActivityType _activity;
    uint32_t _elapsed;
    bool _active;
    bool _paused = false;
    uint32_t _mapId = 0;
    uint32_t _instanceId = 0;
    uint32_t _phaseMask = 0;
};

void LoadConfig();
bool IsOnlyEligibleBot(uint32_t guid);
}

#endif
