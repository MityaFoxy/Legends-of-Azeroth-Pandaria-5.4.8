#include "BotLifeTravel.h"

#include <algorithm>
#include <cmath>

namespace BotLife
{
bool TravelExecutor::IsPending() const
{
    return _status == TravelStatus::Running || _status == TravelStatus::TemporarilyBlocked ||
        _status == TravelStatus::Recovering;
}

void TravelExecutor::Start(TravelTarget const& target, TravelLimits limits)
{
    _movement.Release();
    _target = target;
    _limits.timeoutMs = std::clamp<uint32_t>(limits.timeoutMs, 1000, 1800000);
    _limits.retryMs = std::clamp<uint32_t>(limits.retryMs, 250, 30000);
    _limits.maxAttempts = std::clamp<uint32_t>(limits.maxAttempts, 1, 64);
    _elapsed = _retry = _attempts = 0;
    _issued = false;
    _skipElapsed = true;
    _failure = TravelFailure::None;
    _status = TravelStatus::Running;
    if (!std::isfinite(target.x) || !std::isfinite(target.y) || !std::isfinite(target.z) ||
        !std::isfinite(target.tolerance) || target.tolerance < 0.1f || target.tolerance > 5.0f ||
        !_movement.IsValid(target))
        Fail(TravelFailure::InvalidTarget);
}

TravelStatus TravelExecutor::Fail(TravelFailure reason)
{
    _movement.Release();
    _issued = false;
    _failure = reason;
    return _status = TravelStatus::Failed;
}

TravelStatus TravelExecutor::Update(uint32_t elapsed)
{
    if (!IsPending())
        return _status;
    if (!_movement.IsValid(_target))
        return Fail(TravelFailure::InvalidTarget);
    if (_skipElapsed)
    {
        elapsed = 0; // Exclude time before Start or spent paused.
        _skipElapsed = false;
    }
    _elapsed += std::min(elapsed, _limits.timeoutMs - _elapsed);
    if (_elapsed >= _limits.timeoutMs)
        return Fail(TravelFailure::Timeout);
    if (_movement.IsBlocked())
    {
        _movement.Release();
        _issued = false;
        return _status = TravelStatus::TemporarilyBlocked;
    }
    if (_movement.HasArrived(_target))
    {
        _movement.Release();
        _issued = false;
        return _status = TravelStatus::Arrived;
    }
    if (_issued)
    {
        switch (_movement.Poll())
        {
            case TravelMotion::Moving:
                return _status = TravelStatus::Running;
            case TravelMotion::Recovering:
                // The native watchdog owns bounded replanning. Do not issue a
                // competing MoveTo or reset its attempt budget here.
                return _status = TravelStatus::Recovering;
            case TravelMotion::Lost:
                return Fail(TravelFailure::MovementLost);
            case TravelMotion::RecoveryExhausted:
                return Fail(TravelFailure::RecoveryExhausted);
            case TravelMotion::Finished:
                _movement.Release();
                _issued = false;
                _retry = _limits.retryMs;
                return _status = TravelStatus::TemporarilyBlocked;
        }
    }
    _retry -= std::min(elapsed, _retry);
    if (_retry)
        return _status = TravelStatus::TemporarilyBlocked;
    if (_attempts >= _limits.maxAttempts)
        return Fail(TravelFailure::AttemptLimit);
    TravelMoveResult const result = _movement.Move(_target);
    if (result != TravelMoveResult::Blocked)
        ++_attempts;
    if (result == TravelMoveResult::RecoveryExhausted)
        return Fail(TravelFailure::RecoveryExhausted);
    if (result == TravelMoveResult::Started)
    {
        _issued = true;
        return _status = TravelStatus::Running;
    }
    _retry = _limits.retryMs;
    return _status = TravelStatus::TemporarilyBlocked;
}

void TravelExecutor::Pause()
{
    if (!IsPending())
        return;
    _movement.Release();
    _issued = false;
    _status = TravelStatus::Paused;
}

bool TravelExecutor::Resume()
{
    if (_status != TravelStatus::Paused)
        return false;
    if (!_movement.IsValid(_target))
    {
        Fail(TravelFailure::InvalidTarget);
        return false;
    }
    _skipElapsed = true;
    _status = TravelStatus::Running;
    return true;
}

void TravelExecutor::Cancel()
{
    _movement.Release();
    _issued = false;
    _status = TravelStatus::Cancelled;
}

char const* ToString(TravelStatus status)
{
    switch (status)
    {
        case TravelStatus::Idle: return "Idle";
        case TravelStatus::Running: return "Running";
        case TravelStatus::TemporarilyBlocked: return "TemporarilyBlocked";
        case TravelStatus::Paused: return "Paused";
        case TravelStatus::Arrived: return "Arrived";
        case TravelStatus::Failed: return "Failed";
        case TravelStatus::Cancelled: return "Cancelled";
        case TravelStatus::Recovering: return "Recovering";
    }
    return "Unknown";
}

char const* ToString(TravelFailure failure)
{
    switch (failure)
    {
        case TravelFailure::None: return "None";
        case TravelFailure::InvalidTarget: return "InvalidTarget";
        case TravelFailure::Timeout: return "Timeout";
        case TravelFailure::AttemptLimit: return "AttemptLimit";
        case TravelFailure::RecoveryExhausted: return "RecoveryExhausted";
        case TravelFailure::MovementLost: return "MovementLost";
    }
    return "Unknown";
}
}
