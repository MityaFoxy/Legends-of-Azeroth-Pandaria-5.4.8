#ifndef _BOTLIFE_QUEST_OBJECT_H
#define _BOTLIFE_QUEST_OBJECT_H

#include "BotLifeQuestPlan.h"

class GameObject;
class Player;
struct GameObjectTemplate;

namespace BotLife
{
struct QuestObjectUseResult
{
    char const* reason;
    bool retryable = false;
};

bool IsSupportedQuestObject(GameObjectTemplate const& info, uint32_t questId);
GameObject* FindQuestObject(Player& bot, QuestSpawn const& target);
char const* QuestObjectApproachRejection(Player& bot, GameObject const* object);
QuestObjectUseResult TryUseQuestObject(Player& bot, GameObject& object, QuestPlanData const& data);
}

#endif
