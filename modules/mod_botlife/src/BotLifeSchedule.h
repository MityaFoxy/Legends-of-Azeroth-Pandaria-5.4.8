#ifndef _BOTLIFE_SCHEDULE_H
#define _BOTLIFE_SCHEDULE_H

#include <cstdint>

#include "BotLifeTypes.h"

namespace BotLife
{
struct ScheduleSettings
{
    uint32_t initialSpreadMs = 30000;
    uint32_t questLimit = 1;
    uint32_t outingLimitMs = 30 * 60 * 1000;
    uint32_t questDurationMs = 10 * 60 * 1000;
    uint32_t townDurationMs = 2 * 60 * 1000;
    uint32_t restDurationMs = 60 * 1000;
    uint32_t durationJitterMs = 15000;
};

struct ActivityPlan
{
    ActivityType activity = ActivityType::Free;
    uint32_t durationMs = 1000;
    char const* reason = "initial-delay";
};

// Pure per-bot scheduling policy. It selects work and owns only bounded counters;
// ActivityContext remains responsible for world lifecycle, pause and cancellation.
class LifeSchedule final
{
public:
    LifeSchedule(uint32_t botGuid, ScheduleSettings settings);

    ActivityPlan InitialPlan();
    ActivityPlan Complete(ActivityType activity, ActivityResult result, uint32_t elapsedMs);

    uint32_t CompletedQuests() const { return _completedQuests; }
    uint32_t OutingElapsedMs() const { return _outingElapsedMs; }
    uint32_t Cycle() const { return _cycle; }

private:
    ActivityPlan Plan(ActivityType activity, char const* reason);
    uint32_t DurationFor(ActivityType activity) const;
    uint32_t Mix(uint32_t value) const;
    void ResetOuting();

    uint32_t _botGuid;
    ScheduleSettings _settings;
    uint32_t _completedQuests = 0;
    uint32_t _outingElapsedMs = 0;
    uint32_t _cycle = 0;
    uint32_t _decision = 0;
};
}

#endif
