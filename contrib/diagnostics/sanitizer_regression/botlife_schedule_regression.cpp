#include "BotLifeSchedule.h"
#include <cassert>
#include <limits>
#include <set>
using namespace BotLife;

int main()
{
    ScheduleSettings settings;
    settings.questLimit = 2;
    settings.outingLimitMs = 180000;
    settings.questDurationMs = 120000;
    settings.outingCooldownMs = 300000;
    settings.leisureDurationMs = 120000;
    settings.durationJitterMs = 0;
    LifeSchedule schedule(14, settings);
    auto plan = schedule.InitialPlan();
    assert(plan.activity == ActivityType::Free && plan.durationMs >= 1000);
    plan = schedule.Complete(ActivityType::Free, ActivityResult::Completed, plan.durationMs);
    assert(plan.activity == ActivityType::Quest);
    plan = schedule.Complete(ActivityType::Quest, ActivityResult::Completed, 120000);
    assert(plan.activity == ActivityType::Quest && plan.durationMs == 60000);
    plan = schedule.Complete(ActivityType::Quest, ActivityResult::Completed, 60000);
    assert(plan.activity == ActivityType::Leisure && schedule.CooldownRemainingMs() == 300000);
    assert(schedule.Cycle() == 1 && schedule.CompletedQuests() == 0);
    for (int i = 0; i < 2; ++i)
    {
        plan = schedule.Complete(ActivityType::Leisure, ActivityResult::Completed, plan.durationMs);
        assert(plan.activity == ActivityType::Leisure); // Healthy bots do not skip the break.
    }
    plan = schedule.Complete(ActivityType::Leisure, ActivityResult::Completed, plan.durationMs);
    assert(plan.activity == ActivityType::Quest && !schedule.CooldownRemainingMs());

    LifeSchedule needs(9, settings);
    needs.InitialPlan();
    plan = needs.Complete(ActivityType::Free, ActivityResult::Completed, 1000, {true, true, false});
    assert(plan.activity == ActivityType::Rest); // Recovery before service or questing.
    plan = needs.Complete(ActivityType::Rest, ActivityResult::Completed, 1000, {false, true, false});
    assert(plan.activity == ActivityType::Leisure);
    plan = needs.Complete(ActivityType::Leisure, ActivityResult::Completed, plan.durationMs, {false, true, false});
    assert(plan.activity == ActivityType::Town);
    plan = needs.Complete(ActivityType::Town, ActivityResult::Failed, 1, {false, true, false});
    assert(plan.activity == ActivityType::Leisure);
    plan = needs.Complete(ActivityType::Leisure, ActivityResult::Completed, plan.durationMs, {false, true, false});
    assert(plan.activity == ActivityType::Leisure); // Unavailable repair gets backoff.

    LifeSchedule failed(3, settings);
    failed.InitialPlan();
    failed.Complete(ActivityType::Free, ActivityResult::Completed, 1000);
    plan = failed.Complete(ActivityType::Quest, ActivityResult::Failed, 1);
    assert(plan.activity == ActivityType::Leisure);
    plan = failed.Complete(ActivityType::Leisure, ActivityResult::Failed, 1);
    assert(plan.activity == ActivityType::Free && plan.durationMs >= failed.CooldownRemainingMs());
    plan = failed.Complete(ActivityType::Free, ActivityResult::Completed, 1000);
    assert(plan.activity == ActivityType::Leisure); // Early failure cannot erase cooldown.
    plan = failed.Complete(ActivityType::Leisure, ActivityResult::Completed, std::numeric_limits<uint32_t>::max());
    assert(plan.activity == ActivityType::Quest && !failed.CooldownRemainingMs());

    std::set<uint32_t> starts;
    settings.durationJitterMs = 15000;
    for (uint32_t guid = 1; guid <= 32; ++guid)
    {
        LifeSchedule bot(guid, settings);
        starts.insert(bot.InitialPlan().durationMs);
        auto quest = bot.Complete(ActivityType::Free, ActivityResult::Completed, 1000);
        assert(quest.durationMs >= 105000 && quest.durationMs <= 135000);
        quest = bot.Complete(ActivityType::Quest, ActivityResult::Completed, 179500);
        assert(quest.activity == ActivityType::Quest && quest.durationMs == 500);
    }
    assert(starts.size() > 1);
}
