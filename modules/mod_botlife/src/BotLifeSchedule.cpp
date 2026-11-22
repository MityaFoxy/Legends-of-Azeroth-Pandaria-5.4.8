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
}

ActivityPlan LifeSchedule::InitialPlan()
{
    uint32_t const duration = _settings.initialSpreadMs
        ? Mix(_botGuid ^ 0x9e3779b9u) % (_settings.initialSpreadMs + 1u)
        : 0u;
    ++_decision;
    return { ActivityType::Free, std::max(duration, MinimumActivityDuration), "initial-delay" };
}

ActivityPlan LifeSchedule::Complete(ActivityType activity, ActivityResult result, uint32_t elapsedMs)
{
    if (activity == ActivityType::Quest)
    {
        _outingElapsedMs = SaturatingAdd(_outingElapsedMs, elapsedMs);
        if (result == ActivityResult::Completed)
            ++_completedQuests;

        if (result == ActivityResult::Failed)
            return Plan(ActivityType::Town, "quest-failed");
        if (_completedQuests >= _settings.questLimit)
            return Plan(ActivityType::Town, "quest-limit");
        if (_outingElapsedMs >= _settings.outingLimitMs)
            return Plan(ActivityType::Town, "outing-time-limit");
        return Plan(ActivityType::Quest, "continue-outing");
    }

    switch (activity)
    {
        case ActivityType::Free:
            return Plan(ActivityType::Quest, result == ActivityResult::Failed ? "free-failed" : "outing-start");
        case ActivityType::Town:
            return Plan(ActivityType::Rest, result == ActivityResult::Failed ? "town-failed" : "town-completed");
        case ActivityType::Rest:
            ResetOuting();
            return Plan(result == ActivityResult::Failed ? ActivityType::Free : ActivityType::Quest,
                result == ActivityResult::Failed ? "rest-failed" : "rest-completed");
        case ActivityType::Quest:
            break;
    }

    return Plan(ActivityType::Free, "invalid-activity");
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
            base = std::max(_settings.initialSpreadMs, MinimumActivityDuration);
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
    }

    uint32_t const jitter = std::min(_settings.durationJitterMs, base - MinimumActivityDuration);
    if (!jitter)
        return base;

    uint64_t const width = uint64_t(jitter) * 2u + 1u;
    int64_t const offset = int64_t(Mix(uint32_t(activity) ^ (_cycle * 0x85ebca6bu) ^ _decision) % width) - jitter;
    return uint32_t(int64_t(base) + offset);
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
