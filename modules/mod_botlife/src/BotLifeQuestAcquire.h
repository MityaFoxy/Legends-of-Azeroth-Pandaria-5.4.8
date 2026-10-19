#ifndef _BOTLIFE_QUEST_ACQUIRE_H
#define _BOTLIFE_QUEST_ACQUIRE_H

#include "BotLife.h"

namespace BotLife
{
void LoadQuestAcquireConfig();
void InitializeQuestAcquireData();
bool IsQuestAcquireEnabled();
uint32_t GetQuestAcquireBotGuid();
std::unique_ptr<ActivityExecutor> CreateQuestAcquireExecutor(PlayerbotAI& ai);
}
#endif
