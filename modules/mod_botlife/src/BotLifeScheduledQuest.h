#ifndef _BOTLIFE_SCHEDULED_QUEST_H
#define _BOTLIFE_SCHEDULED_QUEST_H

#include "BotLife.h"

namespace BotLife
{
void LoadScheduledQuestConfig();
void InitializeScheduledQuestData();
bool IsScheduledQuestEnabled();
std::unique_ptr<ActivityExecutor> CreateScheduledExecutor(ActivityType activity, uint32_t duration);
}

#endif
