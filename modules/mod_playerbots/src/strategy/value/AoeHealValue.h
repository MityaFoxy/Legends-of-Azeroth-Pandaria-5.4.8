/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */
#ifndef _PLAYERBOT_AOEHEALVALUE_H
#define _PLAYERBOT_AOEHEALVALUE_H

#include "NamedObjectContext.h"
#include "Value.h"

// Qualifier: critical, low, medium or almost full (configured health thresholds).
class AoeHealValue : public Uint8CalculatedValue, public Qualified
{
public:
    AoeHealValue(PlayerbotAI* botAI) : Uint8CalculatedValue(botAI, "aoe heal") {}
    uint8 Calculate() override;
};

#endif
