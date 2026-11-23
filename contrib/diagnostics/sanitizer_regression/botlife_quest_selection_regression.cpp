#include "BotLifeQuestSelection.h"

#include <cassert>
#include <limits>
#include <vector>

using namespace BotLife;

int main()
{
    std::vector<ScheduledQuestCandidate> candidates{
        {40, QuestPlanStage::Acquire, 1.0},
        {30, QuestPlanStage::Hunt, 100.0},
        {20, QuestPlanStage::TurnIn, 1000.0},
        {10, QuestPlanStage::AwaitCompletion, 0.0},
    };
    assert(SelectScheduledQuest(candidates) == 20); // Finish before hunting or acquiring.

    candidates.erase(candidates.begin() + 2);
    assert(SelectScheduledQuest(candidates) == 30); // Active hunt beats a nearer new quest.
    candidates.erase(candidates.begin() + 1);
    assert(SelectScheduledQuest(candidates) == 10); // Await native completion before acquiring.
    candidates.erase(candidates.begin() + 1);
    assert(SelectScheduledQuest(candidates) == 40);
    assert(!SelectScheduledQuest(candidates, false)); // An unplannable active quest blocks acquisition.

    // Same-stage selection is nearest first, then stable quest-id order.
    candidates = {{9, QuestPlanStage::Acquire, 4.0}, {8, QuestPlanStage::Acquire, 1.0}};
    assert(SelectScheduledQuest(candidates) == 8);
    candidates[0].distanceSquared = 1.0;
    assert(SelectScheduledQuest(candidates) == 8);

    // Invalid, terminal and non-finite candidates are never selected.
    candidates = {
        {1, QuestPlanStage::Rejected, 0.0},
        {2, QuestPlanStage::Done, 0.0},
        {3, QuestPlanStage::Acquire, -1.0},
        {4, QuestPlanStage::Acquire, std::numeric_limits<double>::infinity()},
        {0, QuestPlanStage::TurnIn, 0.0},
    };
    assert(!SelectScheduledQuest(candidates));
}
