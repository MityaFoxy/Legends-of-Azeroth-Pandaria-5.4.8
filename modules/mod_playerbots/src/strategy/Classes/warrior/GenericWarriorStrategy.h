#ifndef _PLAYERBOT_GENERICWARRIORSTRATEGY_H
#define _PLAYERBOT_GENERICWARRIORSTRATEGY_H

#include "MeleeCombatStrategy.h"

class PlayerbotAI;

class GenericWarriorStrategy : public MeleeCombatStrategy
{
public:
    GenericWarriorStrategy(PlayerbotAI* botAI);

    void InitTriggers(std::vector<TriggerNode*>& triggers) override;
    std::string const getName() override { return "warrior"; }
};

class WarriorAoeStrategy : public CombatStrategy
{
public:
    WarriorAoeStrategy(PlayerbotAI* botAI);

    void InitTriggers(std::vector<TriggerNode*>& triggers) override;
    std::string const getName() override { return "aoe"; }
};

#endif
