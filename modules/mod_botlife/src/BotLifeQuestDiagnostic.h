#ifndef _BOTLIFE_QUEST_DIAGNOSTIC_H
#define _BOTLIFE_QUEST_DIAGNOSTIC_H

#include "BotLife.h"

namespace BotLife
{
void LoadQuestPlanConfig();
void InitializeQuestPlanData();
bool IsQuestPlanEnabled();
uint32_t GetQuestPlanBotGuid();
std::unique_ptr<ActivityExecutor> CreateQuestPlanExecutor(PlayerbotAI& ai);
}
#endif
