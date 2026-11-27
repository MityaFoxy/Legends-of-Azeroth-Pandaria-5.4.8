#ifndef _BOTLIFE_QUEST_DATA_H
#define _BOTLIFE_QUEST_DATA_H

#include "BotLifeQuestPlan.h"

class Player;

namespace BotLife
{
QuestPlanData LoadQuestPlanData(uint32_t questId, bool allowSoloObjective = false);
QuestPlayerSnapshot ReadQuestPlayer(QuestPlanData const& data, Player& player);
}
#endif
