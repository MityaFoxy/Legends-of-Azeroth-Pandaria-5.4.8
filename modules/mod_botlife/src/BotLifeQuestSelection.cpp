#include "BotLifeQuestSelection.h"

#include <cmath>
#include <limits>
#include <tuple>

namespace BotLife
{
namespace
{
uint8_t Priority(QuestPlanStage stage)
{
    switch (stage)
    {
        case QuestPlanStage::TurnIn: return 0;
        case QuestPlanStage::Hunt: return 1;
        case QuestPlanStage::AwaitCompletion: return 2;
        case QuestPlanStage::Acquire: return 3;
        case QuestPlanStage::Interact:
        case QuestPlanStage::Rejected:
        case QuestPlanStage::Done:
            return std::numeric_limits<uint8_t>::max();
    }
    return std::numeric_limits<uint8_t>::max();
}
}

std::optional<uint32_t> SelectScheduledQuest(std::vector<ScheduledQuestCandidate> const& candidates,
    bool allowAcquire)
{
    std::optional<uint32_t> selected;
    auto best = std::tuple{std::numeric_limits<uint8_t>::max(),
        std::numeric_limits<double>::infinity(), std::numeric_limits<uint32_t>::max()};
    for (ScheduledQuestCandidate const& candidate : candidates)
    {
        uint8_t const priority = Priority(candidate.stage);
        if (!candidate.questId || priority == std::numeric_limits<uint8_t>::max() ||
            (!allowAcquire && candidate.stage == QuestPlanStage::Acquire) ||
            !std::isfinite(candidate.distanceSquared) || candidate.distanceSquared < 0.0)
            continue;
        auto const score = std::tuple{priority, candidate.distanceSquared, candidate.questId};
        if (score < best)
        {
            best = score;
            selected = candidate.questId;
        }
    }
    return selected;
}
}
