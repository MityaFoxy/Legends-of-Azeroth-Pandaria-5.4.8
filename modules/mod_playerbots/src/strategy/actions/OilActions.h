#ifndef _PLAYERBOT_OILACTIONS_H
#define _PLAYERBOT_OILACTIONS_H

#include "Action.h"

class Item;

class ApplyOilAction : public Action
{
public:
    ApplyOilAction(PlayerbotAI* botAI) : Action(botAI, "apply oil") {}

    bool isUseful() override;
    bool isPossible() override;
    bool Execute(Event event) override;

private:
    bool CanApply();
    Item* FindOil(Item* weapon, uint32& spellId, uint32& enchantId);
};

#endif
