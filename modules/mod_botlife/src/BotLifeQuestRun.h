#ifndef _BOTLIFE_QUEST_RUN_H
#define _BOTLIFE_QUEST_RUN_H

#include "BotLife.h"
#include <vector>

namespace BotLife
{
void LoadQuestRunConfig();
void InitializeQuestRunData();
bool IsQuestRunEnabled();
uint32_t GetQuestRunBotGuid();
std::vector<uint32_t> GetQuestRunBotGuids();
std::unique_ptr<ActivityExecutor> CreateQuestRunExecutor(PlayerbotAI& ai);
}
#endif
