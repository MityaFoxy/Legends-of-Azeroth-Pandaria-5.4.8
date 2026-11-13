#ifndef _PLAYERBOT_DRUIDVALUES_H
#define _PLAYERBOT_DRUIDVALUES_H

#include "PartyMemberValue.h"

bool DruidNeedsMarkOfTheWild(PlayerbotAI* ai, Unit* target);
uint32 DruidDispelSpell(Player* bot, uint32 dispelType);
bool DruidNeedsDispel(PlayerbotAI* ai, Unit* target, uint32 dispelType);

class DruidMarkOfTheWildTargetValue : public PartyMemberValue
{
public:
    DruidMarkOfTheWildTargetValue(PlayerbotAI* ai) : PartyMemberValue(ai, "mark of the wild target") {}

protected:
    Unit* Calculate() override;
};

#endif
