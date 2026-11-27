#ifndef _BOTLIFE_QUEST_LOOT_H
#define _BOTLIFE_QUEST_LOOT_H

#include "BotLifeQuestPlan.h"
#include "ObjectGuid.h"

class Creature;
class Player;

namespace BotLife
{
Creature* FindQuestCorpse(Player& bot, ObjectGuid guid, QuestSpawn const& target);
char const* TryLootQuestItem(Player& bot, Creature& corpse, QuestPlanData const& data);
}

#endif
