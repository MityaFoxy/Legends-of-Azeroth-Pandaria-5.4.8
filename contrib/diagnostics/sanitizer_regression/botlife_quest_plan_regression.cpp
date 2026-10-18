#include "BotLifeQuestPlan.h"

#include <cassert>
#include <limits>

using namespace BotLife;

int main()
{
    QuestSpawn const giver{1, 100, 1, 1, 10, 0, 0};
    QuestSpawn const mob{2, 200, 1, 1, 20, 0, 0};
    QuestPlanData data{42, "Kill quest", QuestPlanReason::None, {giver}, {giver}, {{10, 200, 5, {mob}}}};
    QuestPlayerSnapshot player;
    player.validContext = true;
    player.mapId = player.phaseMask = 1;
    auto plan = BuildQuestPlan(data, player);
    assert(plan.stage == QuestPlanStage::Acquire && plan.reason == QuestPlanReason::None);
    assert(plan.starter->guid == 1 && plan.ender->guid == 1);
    assert(plan.objectives[0].remaining == 5 && plan.objectives[0].candidate->guid == 2);

    // Stale counters on an untaken quest cannot reduce its planned work.
    player.counters[10] = 4;
    assert(BuildQuestPlan(data, player).objectives[0].remaining == 5);
    player.progress = QuestProgress::Active;
    plan = BuildQuestPlan(data, player);
    assert(plan.stage == QuestPlanStage::Hunt && plan.objectives[0].remaining == 1);
    player.counters[10] = std::numeric_limits<uint32_t>::max();
    plan = BuildQuestPlan(data, player);
    assert(plan.stage == QuestPlanStage::AwaitCompletion && plan.objectives[0].remaining == 0);
    assert(!plan.objectives[0].candidate); // Never synthesize native completion from counts.

    // Already complete quests need neither kill spawns nor a starter.
    data.starters.clear();
    data.objectives[0].candidates.clear();
    player.progress = QuestProgress::Complete;
    player.counters.clear();
    plan = BuildQuestPlan(data, player);
    assert(plan.stage == QuestPlanStage::TurnIn && plan.objectives[0].remaining == 0);
    data.enders.clear();
    assert(BuildQuestPlan(data, player).reason == QuestPlanReason::MissingEnder);
    player.progress = QuestProgress::Rewarded;
    assert(BuildQuestPlan(data, player).stage == QuestPlanStage::Done);
    player.progress = QuestProgress::Failed;
    assert(BuildQuestPlan(data, player).reason == QuestPlanReason::FailedQuest);
    player.progress = QuestProgress::NotTaken;
    assert(BuildQuestPlan(data, player).reason == QuestPlanReason::MissingStarter);
    data.starters = data.enders = {giver};
    data.objectives[0].candidates = {mob};

    for (QuestPlanReason reason : {QuestPlanReason::QuestDisabled, QuestPlanReason::Level,
        QuestPlanReason::RaceOrClass, QuestPlanReason::Prerequisites, QuestPlanReason::NativeEligibility,
        QuestPlanReason::QuestLogFull, QuestPlanReason::CatalogChanged})
    {
        player.eligibility = reason;
        assert(BuildQuestPlan(data, player).reason == reason);
        assert(BuildQuestPlan(data, player).stage == QuestPlanStage::Rejected);
    }
    player.eligibility = QuestPlanReason::None;
    for (QuestPlanReason reason : {QuestPlanReason::MissingQuest, QuestPlanReason::UnsupportedQuest, QuestPlanReason::DataLimit})
    {
        data.error = reason;
        assert(BuildQuestPlan(data, player).reason == reason);
    }
    data.error = QuestPlanReason::None;
    player.validContext = false;
    assert(BuildQuestPlan(data, player).reason == QuestPlanReason::InvalidContext);
    player.validContext = true;
    player.x = std::numeric_limits<float>::quiet_NaN();
    assert(BuildQuestPlan(data, player).reason == QuestPlanReason::InvalidContext);
    player.x = 0;
    player.phaseMask = 0;
    assert(BuildQuestPlan(data, player).reason == QuestPlanReason::InvalidContext);
    player.phaseMask = 1;

    // Map/phase filtering, invalid coordinates, stable distance ties.
    QuestSpawn wrongMap = mob, wrongPhase = mob, invalid = mob, tie = mob;
    wrongMap.mapId = 0;
    wrongPhase.phaseMask = 2;
    invalid.x = std::numeric_limits<float>::infinity();
    data.objectives[0].candidates = {wrongMap, wrongPhase, invalid};
    assert(BuildQuestPlan(data, player).reason == QuestPlanReason::MissingObjective);
    tie.guid = 3;
    data.objectives[0].candidates = {tie, mob};
    assert(BuildQuestPlan(data, player).objectives[0].candidate->guid == 2);
    tie.x = 1;
    data.objectives[0].candidates = {mob, tie};
    assert(BuildQuestPlan(data, player).objectives[0].candidate->guid == 3);

    // Multiple objectives are independent; completed ones do not need spawns.
    data.objectives.push_back({11, 300, 7, {}});
    player.progress = QuestProgress::Active;
    player.counters[11] = 7;
    plan = BuildQuestPlan(data, player);
    assert(plan.stage == QuestPlanStage::Hunt && plan.objectives.size() == 2);
    assert(plan.objectives[0].remaining == 5 && plan.objectives[1].remaining == 0);
    // A second bot does not inherit counters from the first snapshot.
    QuestPlayerSnapshot second = player;
    second.counters.clear();
    assert(BuildQuestPlan(data, second).reason == QuestPlanReason::MissingObjective);
    assert(BuildQuestPlan(data, player).stage == QuestPlanStage::Hunt);
    // Returned candidates are owned values, not pointers into the catalog.
    data.objectives.clear();
    assert(plan.objectives[0].candidate->guid == 3);
}
