#ifndef _BOTLIFE_QUEST_EXECUTOR_H
#define _BOTLIFE_QUEST_EXECUTOR_H

#include "BotLife.h"
#include "BotLifeQuestPlan.h"

namespace BotLife
{
// The immutable startup catalog must outlive its executor.
std::unique_ptr<ActivityExecutor> MakeQuestExecutor(PlayerbotAI& ai, QuestPlanData const& data);
}
#endif
