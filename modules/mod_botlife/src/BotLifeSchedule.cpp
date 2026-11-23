#include "BotLifeSchedule.h"

#include <algorithm>
#include <limits>

namespace BotLife
{
namespace
{
constexpr uint32_t MinimumActivityDuration = 1000;

uint32_t SaturatingAdd(uint32_t left, uint32_t right)
{
    uint32_t const available = std::numeric_limits<uint32_t>::max() - left;
    return left + std::min(right, available);
}
}

LifeSchedule::LifeSchedule(uint32_t botGuid, ScheduleSettings settings)
    : _botGuid(botGuid), _settings(settings)
{
    _settings.initialSpreadMs = std::min(_settings.initialSpreadMs, 60u * 60u * 1000u);
    _settings.questLimit = std::clamp(_settings.questLimit, 1u, 20u);
    _settings.outingLimitMs = std::clamp(_settings.outingLimitMs, MinimumActivityDuration, 8u * 60u * 60u * 1000u);
    _settings.questDurationMs = std::clamp(_settings.questDurationMs, MinimumActivityDuration, _settings.outingLimitMs);
    _settings.townDurationMs = std::clamp(_settings.townDurationMs, MinimumActivityDuration, 60u * 60u * 1000u);
    _settings.restDurationMs = std::clamp(_settings.restDurationMs, MinimumActivityDuration, 60u * 60u * 1000u);
    _settings.durationJitterMs = std::min(_settings.durationJitterMs, 30u * 60u * 1000u);
    _settings.outingCooldownMs = std::clamp(_settings.outingCooldownMs, 60000u, 3600000u);
    _settings.leisureDurationMs = std::clamp(_settings.leisureDurationMs, 30000u, 3600000u);
    _settings.walkDurationMs = std::clamp(_settings.walkDurationMs, 30000u, 300000u);
    _lastBreakWalk = (_botGuid % 2) != 0;
}

ActivityPlan LifeSchedule::InitialPlan()
{
    uint32_t const duration = _settings.initialSpreadMs
        ? Mix(_botGuid ^ 0x9e3779b9u) % (_settings.initialSpreadMs + 1u)
        : 0u;
    ++_decision;
    return { ActivityType::Free, std::max(duration, MinimumActivityDuration), "initial-delay" };
}

ActivityPlan LifeSchedule::Complete(ActivityType activity, ActivityResult result, uint32_t elapsedMs,
    ScheduleNeeds needs)
{
    if (activity != ActivityType::Quest)
    {
        _cooldownMs -= std::min(_cooldownMs, elapsedMs);
        _serviceBackoffMs -= std::min(_serviceBackoffMs, elapsedMs);
        _walkBackoffMs -= std::min(_walkBackoffMs, elapsedMs);
    }
    if (activity == ActivityType::Quest)
    {
        _outingElapsedMs = SaturatingAdd(_outingElapsedMs, elapsedMs);
        if (result == ActivityResult::Completed)
            ++_completedQuests;

        if (result == ActivityResult::Failed || _completedQuests >= _settings.questLimit ||
            _outingElapsedMs >= _settings.outingLimitMs || needs.recovery || needs.service || !needs.canQuest)
        {
            char const* reason = result == ActivityResult::Failed ? "quest-failed" :
                _completedQuests >= _settings.questLimit ? "quest-limit" :
                _outingElapsedMs >= _settings.outingLimitMs ? "outing-time-limit" : "needs-changed";
            _cooldownMs = _settings.outingCooldownMs;
            ResetOuting();
            ActivityPlan plan = Choose(needs, false);
            plan.reason = reason;
            return plan;
        }
        return Plan(ActivityType::Quest, "continue-outing");
    }

    switch (activity)
    {
        case ActivityType::Free:
            return Choose(needs, true);
        case ActivityType::Town:
            if (result == ActivityResult::Failed)
                _serviceBackoffMs = _settings.outingCooldownMs;
            return needs.recovery ? Plan(ActivityType::Rest, "recovery-needed") :
                Break(needs, "service-break");
        case ActivityType::Rest:
            return Break(needs, "recovery-break");
        case ActivityType::Walk:
            _walkBackoffMs = _settings.outingCooldownMs;
            if (needs.recovery)
                return Plan(ActivityType::Rest, "recovery-needed");
            _lastBreakWalk = true;
            return Plan(ActivityType::Leisure,
                result == ActivityResult::Failed ? "walk-failed" : "walk-completed");
        case ActivityType::Leisure:
            if (result == ActivityResult::Failed)
                return Plan(ActivityType::Free, "leisure-unavailable");
            return Choose(needs, true);
        case ActivityType::Quest:
            break;
    }

    return Plan(ActivityType::Free, "invalid-activity");
}

ActivityPlan LifeSchedule::Choose(ScheduleNeeds needs, bool allowQuest)
{
    if (needs.recovery)
        return Plan(ActivityType::Rest, "recovery-needed");
    if (needs.service && !_serviceBackoffMs)
        return Plan(ActivityType::Town, "service-needed");
    if (!allowQuest || _cooldownMs || !needs.canQuest)
        return Break(needs, _cooldownMs ? "outing-cooldown" : "quest-unavailable");
    return Plan(ActivityType::Quest, "outing-start");
}

ActivityPlan LifeSchedule::Break(ScheduleNeeds needs, char const* reason)
{
    bool const walk = _settings.walkEnabled && needs.canQuest && !needs.recovery &&
        !needs.service && !_walkBackoffMs && !_lastBreakWalk;
    _lastBreakWalk = walk;
    return Plan(walk ? ActivityType::Walk : ActivityType::Leisure, reason);
}

ActivityPlan LifeSchedule::Plan(ActivityType activity, char const* reason)
{
    ActivityPlan const plan{ activity, DurationFor(activity), reason };
    ++_decision;
    return plan;
}

uint32_t LifeSchedule::DurationFor(ActivityType activity) const
{
    uint32_t base = MinimumActivityDuration;
    switch (activity)
    {
        case ActivityType::Free:
            base = std::max({_settings.leisureDurationMs, _cooldownMs, _serviceBackoffMs});
            break;
        case ActivityType::Quest:
            base = _settings.questDurationMs;
            break;
        case ActivityType::Town:
            base = _settings.townDurationMs;
            break;
        case ActivityType::Rest:
            base = _settings.restDurationMs;
            break;
        case ActivityType::Leisure:
            base = _settings.leisureDurationMs;
            break;
        case ActivityType::Walk:
            base = _settings.walkDurationMs;
            break;
    }

    uint32_t const jitter = std::min(_settings.durationJitterMs, base - MinimumActivityDuration);
    uint64_t const width = uint64_t(jitter) * 2u + 1u;
    int64_t const offset = int64_t(Mix(uint32_t(activity) ^ (_cycle * 0x85ebca6bu) ^ _decision) % width) - jitter;
    uint32_t duration = uint32_t(int64_t(base) + offset);
    if (activity == ActivityType::Quest)
        duration = std::min(duration, _settings.outingLimitMs - std::min(_outingElapsedMs, _settings.outingLimitMs));
    if (activity == ActivityType::Free)
        duration = std::max(duration, _cooldownMs); // Jitter cannot shorten a hard cooldown.
    return duration;
}

uint32_t LifeSchedule::Mix(uint32_t value) const
{
    value ^= _botGuid + 0x9e3779b9u + (value << 6) + (value >> 2);
    value ^= value >> 16;
    value *= 0x7feb352du;
    value ^= value >> 15;
    value *= 0x846ca68bu;
    value ^= value >> 16;
    return value;
}

void LifeSchedule::ResetOuting()
{
    _completedQuests = 0;
    _outingElapsedMs = 0;
    ++_cycle;
}
}
