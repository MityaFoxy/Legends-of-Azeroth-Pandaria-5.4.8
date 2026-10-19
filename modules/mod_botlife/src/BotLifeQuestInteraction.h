#ifndef _BOTLIFE_QUEST_INTERACTION_H
#define _BOTLIFE_QUEST_INTERACTION_H

#include "BotLifeQuestPlan.h"

class Player;

namespace BotLife
{
// Native, map-local checks; never retain live pointers between AI updates.
char const* QuestAcquireRejection(Player& bot, QuestPlanData const& data);
bool TryAcceptQuest(Player& bot, QuestPlanData const& data, QuestSpawn const& giver, char const*& reason);
}
#endif
