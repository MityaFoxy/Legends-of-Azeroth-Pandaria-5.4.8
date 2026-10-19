#ifndef _BOTLIFE_QUEST_HUNT_H
#define _BOTLIFE_QUEST_HUNT_H

#include "BotLifeQuestPlan.h"
#include "AttackActions.h"
#include "BotLifeSafety.h"
#include <unordered_set>

namespace BotLife
{
// Native combat adapter. Retains no target pointers and never grants quest credit.
class QuestHunt final : private AttackAction
{
public:
    explicit QuestHunt(PlayerbotAI& ai) : AttackAction(&ai, "botlife quest hunt"), _safety(*bot) { }
    QuestSafety& Safety() { return _safety; }
    std::optional<QuestSpawn> Choose(QuestPlanData const& data, QuestPlayerSnapshot const& player,
        std::unordered_set<uint32_t> const& visited) const;
    bool CanEngage(QuestSpawn const& target) const;
    bool Engage(QuestSpawn const& target);
    bool IsAlive(QuestSpawn const& target) const;
    bool IsFighting() const;
private:
    mutable QuestSafety _safety;
};
}
#endif
