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
    Reset
};

class ActivityExecutor
{
public:
    virtual ~ActivityExecutor() = default;

    virtual ActivityType GetType() const = 0;
    virtual void Start(PlayerbotAI& botAI) = 0;
    virtual ActivityResult Update(PlayerbotAI& botAI, uint32_t elapsed) = 0;
    virtual void Interrupt(PlayerbotAI& botAI, InterruptReason reason) = 0;
    virtual void Finish(PlayerbotAI& botAI, ActivityResult result) = 0;
};

class ActivityContext final : public PlayerbotAIExtension
{
public:
    ActivityContext();
    ~ActivityContext() override;

    PlayerbotAIExtensionResult Update(PlayerbotAI& botAI, uint32_t elapsed) override;
    void Reset(PlayerbotAI& botAI) override;

    ActivityType GetActivity() const { return _activity; }
    bool IsActive() const { return _active; }

private:
    void Stop(PlayerbotAI& botAI, InterruptReason reason);
    void Start(PlayerbotAI& botAI, ActivityType activity, char const* reason);
    void Transition(PlayerbotAI& botAI, ActivityType activity, ActivityResult result, char const* reason);

    std::unique_ptr<ActivityExecutor> _executor;
    ActivityType _activity;
    uint32_t _elapsed;
    bool _active;
};

void LoadConfig();
}

#endif
