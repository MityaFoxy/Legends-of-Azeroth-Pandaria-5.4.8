#ifndef _BOTLIFE_TRAVEL_H
#define _BOTLIFE_TRAVEL_H

#include <cstdint>

namespace BotLife
{
// A snapshot, never a retained NPC/gameobject pointer. Activities resolve moving
// targets again and perform native interaction checks after arrival.
struct TravelTarget
{
    uint32_t mapId = 0;
    uint32_t instanceId = 0;
    uint32_t phaseMask = 0;
    float x = 0, y = 0, z = 0;
    float tolerance = 1.0f;
};

enum class TravelStatus { Idle, Running, TemporarilyBlocked, Paused, Arrived, Failed, Cancelled, Recovering };
enum class TravelFailure { None, InvalidTarget, Timeout, AttemptLimit, RecoveryExhausted, MovementLost };
enum class TravelMoveResult { Started, Blocked, NoRoute, RecoveryExhausted };
enum class TravelMotion { Moving, Finished, Lost, RecoveryExhausted, Recovering };

char const* ToString(TravelStatus status);
char const* ToString(TravelFailure failure);

struct TravelLimits
{
    uint32_t timeoutMs = 120000;
    uint32_t retryMs = 1000;
    uint32_t maxAttempts = 8;
};

class TravelMovement
{
public:
    virtual ~TravelMovement() = default;
    virtual bool IsValid(TravelTarget const& target) const = 0;
    virtual bool IsBlocked() = 0;
    virtual bool HasArrived(TravelTarget const& target) const = 0;
    virtual TravelMoveResult Move(TravelTarget const& target) = 0;
    virtual TravelMotion Poll() const = 0;
    virtual bool OwnsMovement() const = 0;
    virtual void Release() = 0; // Must never stop replacement/foreign motion.
};

// Reusable activity phase, not a new top-level activity. The adapter must outlive
// this object. Lifecycle owners call Pause/Cancel before disposing their activity.
class TravelExecutor
{
public:
    explicit TravelExecutor(TravelMovement& movement) : _movement(movement) { }
    TravelExecutor(TravelExecutor const&) = delete;
    TravelExecutor& operator=(TravelExecutor const&) = delete;
    void Start(TravelTarget const& target, TravelLimits limits = {});
    TravelStatus Update(uint32_t elapsed);
    void Pause();
    bool Resume();
    void Cancel();
    TravelStatus GetStatus() const { return _status; }
    TravelFailure GetFailure() const { return _failure; }
    uint32_t GetAttempts() const { return _attempts; }
    bool ControlsMovement() const
    {
        return (_status == TravelStatus::Running || _status == TravelStatus::Recovering) && _movement.OwnsMovement();
    }

private:
    bool IsPending() const;
    TravelStatus Fail(TravelFailure reason);
    TravelMovement& _movement;
    TravelTarget _target;
    TravelLimits _limits;
    TravelStatus _status = TravelStatus::Idle;
    TravelFailure _failure = TravelFailure::None;
    uint32_t _elapsed = 0, _retry = 0, _attempts = 0;
    bool _issued = false;
    bool _skipElapsed = false;
};
}
#endif
