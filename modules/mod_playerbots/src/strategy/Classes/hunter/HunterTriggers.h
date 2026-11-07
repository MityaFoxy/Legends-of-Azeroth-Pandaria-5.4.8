/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#ifndef _PLAYERBOT_HUNTERTRIGGERS_H
#define _PLAYERBOT_HUNTERTRIGGERS_H

#include "GenericTriggers.h"
#include "Trigger.h"

class PlayerbotAI;

class HuntersPetMediumHealthTrigger : public Trigger
{
public:
    HuntersPetMediumHealthTrigger(PlayerbotAI* botAI) : Trigger(botAI, "hunters pet medium health", 2) {}

    bool IsActive() override;
};

class HuntersPetDeadTrigger : public Trigger
{
public:
    HuntersPetDeadTrigger(PlayerbotAI* botAI) : Trigger(botAI, "hunters pet dead", 2) {}

    bool IsActive() override;
};

#endif
