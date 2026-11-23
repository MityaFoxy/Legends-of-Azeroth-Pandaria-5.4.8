#ifndef _BOTLIFE_QUEST_SELECTION_H
#define _BOTLIFE_QUEST_SELECTION_H

#include "BotLifeQuestPlan.h"

#include <cstdint>
#include <optional>
#include <vector>

namespace BotLife
{
struct ScheduledQuestCandidate
{
    uint32_t questId = 0;
    QuestPlanStage stage = QuestPlanStage::Rejected;
    double distanceSquared = 0.0;
};

// Pure deterministic policy. Active work always wins over acquiring a new
// quest; distance and quest id make selection stable within the same stage.
std::optional<uint32_t> SelectScheduledQuest(std::vector<ScheduledQuestCandidate> const& candidates,
    bool allowAcquire = true);
}

#endif
