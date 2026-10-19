#ifndef _BOTLIFE_QUEST_TURN_IN_H
#define _BOTLIFE_QUEST_TURN_IN_H

#include "BotLifeQuestPlan.h"
class Player;

namespace BotLife
{
char const* QuestExecutionRejection(Player& bot, QuestPlanData const& data);
bool TryTurnInQuest(Player& bot, QuestPlanData const& data, QuestSpawn const& ender, char const*& reason);
}
#endif
