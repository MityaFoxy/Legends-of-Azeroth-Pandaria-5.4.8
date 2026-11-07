#ifndef _PLAYERBOT_MANAPOTIONACTION_H
#define _PLAYERBOT_MANAPOTIONACTION_H

#include "Action.h"

class Item;
class ManaPotionAction : public Action
{
public:
    ManaPotionAction(PlayerbotAI* botAI) : Action(botAI, "mana potion") { }
    bool isUseful() override;
    bool isPossible() override;
    bool Execute(Event event) override;

private:
    bool CanUsePotion();
    Item* FindPotion(uint32& spellId);
};

#endif
