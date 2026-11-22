#include "BotLifeSchedule.h"

#include <cassert>
#include <iostream>
#include <set>
#include <string>

using namespace BotLife;

namespace
{
ScheduleSettings FixedSettings()
{
    ScheduleSettings settings;
    settings.initialSpreadMs = 30000;
    settings.questLimit = 2;
    settings.outingLimitMs = 600000;
    settings.questDurationMs = 120000;
    settings.townDurationMs = 30000;
    settings.restDurationMs = 20000;
    settings.durationJitterMs = 0;
    return settings;
}
}

int main()
{
    ScheduleSettings const settings = FixedSettings();
    LifeSchedule schedule(14, settings);

    ActivityPlan plan = schedule.InitialPlan();
    assert(plan.activity == ActivityType::Free);
    assert(plan.durationMs >= 1000 && plan.durationMs <= settings.initialSpreadMs);

    plan = schedule.Complete(ActivityType::Free, ActivityResult::Completed, plan.durationMs);
    assert(plan.activity == ActivityType::Quest && plan.durationMs == settings.questDurationMs);

    plan = schedule.Complete(ActivityType::Quest, ActivityResult::Completed, 120000);
    assert(plan.activity == ActivityType::Quest);
    assert(schedule.CompletedQuests() == 1 && schedule.OutingElapsedMs() == 120000);

    plan = schedule.Complete(ActivityType::Quest, ActivityResult::Completed, 130000);
    assert(plan.activity == ActivityType::Town);
    assert(std::string(plan.reason) == "quest-limit");
    assert(schedule.CompletedQuests() == 2 && schedule.OutingElapsedMs() == 250000);

    plan = schedule.Complete(ActivityType::Town, ActivityResult::Completed, plan.durationMs);
    assert(plan.activity == ActivityType::Rest && plan.durationMs == settings.restDurationMs);
    plan = schedule.Complete(ActivityType::Rest, ActivityResult::Completed, plan.durationMs);
    assert(plan.activity == ActivityType::Quest);
    assert(schedule.CompletedQuests() == 0 && schedule.OutingElapsedMs() == 0 && schedule.Cycle() == 1);

    ScheduleSettings timeLimited = settings;
    timeLimited.questLimit = 20;
    timeLimited.outingLimitMs = 100000;
    timeLimited.questDurationMs = 100000;
    LifeSchedule timeSchedule(9, timeLimited);
    timeSchedule.InitialPlan();
    plan = timeSchedule.Complete(ActivityType::Free, ActivityResult::Completed, 1000);
    plan = timeSchedule.Complete(ActivityType::Quest, ActivityResult::Completed, 100000);
    assert(plan.activity == ActivityType::Town);
    assert(std::string(plan.reason) == "outing-time-limit");

    LifeSchedule failed(9, settings);
    failed.InitialPlan();
    failed.Complete(ActivityType::Free, ActivityResult::Completed, 1000);
    plan = failed.Complete(ActivityType::Quest, ActivityResult::Failed, 5000);
    assert(plan.activity == ActivityType::Town && std::string(plan.reason) == "quest-failed");
    plan = failed.Complete(ActivityType::Town, ActivityResult::Failed, 1000);
    assert(plan.activity == ActivityType::Rest && std::string(plan.reason) == "town-failed");
    plan = failed.Complete(ActivityType::Rest, ActivityResult::Failed, 1000);
    assert(plan.activity == ActivityType::Free && std::string(plan.reason) == "rest-failed");

    std::set<uint32_t> starts;
    for (uint32_t guid = 1; guid <= 16; ++guid)
    {
        LifeSchedule spread(guid, settings);
        starts.insert(spread.InitialPlan().durationMs);
    }
    assert(starts.size() > 1); // Per-bot offsets prevent lockstep startup.

    ScheduleSettings jittered = settings;
    jittered.durationJitterMs = 15000;
    for (uint32_t guid = 1; guid <= 32; ++guid)
    {
        LifeSchedule jitter(guid, jittered);
        jitter.InitialPlan();
        ActivityPlan const quest = jitter.Complete(ActivityType::Free, ActivityResult::Completed, 1000);
        assert(quest.durationMs >= jittered.questDurationMs - jittered.durationJitterMs);
        assert(quest.durationMs <= jittered.questDurationMs + jittered.durationJitterMs);
    }

    std::cout << "BotLife schedule regression passed\n";
}
