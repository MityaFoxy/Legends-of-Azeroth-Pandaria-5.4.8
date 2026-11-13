/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */
#ifndef _PLAYERBOT_ENEMYHEALERTARGETVALUE_H
#define _PLAYERBOT_ENEMYHEALERTARGETVALUE_H

#include "NamedObjectContext.h"
#include "Value.h"

// An off-target attacker casting a beneficial spell; qualifier names the interrupt.
class EnemyHealerTargetValue : public UnitCalculatedValue, public Qualified
{
public:
    EnemyHealerTargetValue(PlayerbotAI* botAI) : UnitCalculatedValue(botAI, "enemy healer target") {}

protected:
    Unit* Calculate() override;
};

#endif
