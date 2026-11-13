/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#ifndef _PLAYERBOT_ROGUETRIGGERS_H
#define _PLAYERBOT_ROGUETRIGGERS_H

#include "GenericTriggers.h"

class PlayerbotAI;

class RogueComboPointsTrigger : public Trigger
{
public:
    RogueComboPointsTrigger(PlayerbotAI* botAI, std::string const name, uint8 amount)
        : Trigger(botAI, name), amount(amount) {}

    bool IsActive() override;

private:
    uint8 amount;
};

class RogueTargetDyingTrigger : public RogueComboPointsTrigger
{
public:
    RogueTargetDyingTrigger(PlayerbotAI* botAI)
        : RogueComboPointsTrigger(botAI, "target with combo points almost dead", 1) {}

    bool IsActive() override;
};

class SliceAndDiceTrigger : public BuffTrigger
{
public:
    SliceAndDiceTrigger(PlayerbotAI* botAI)
        : BuffTrigger(botAI, "slice and dice", 1, false, false, 3 * IN_MILLISECONDS) {}

    bool IsActive() override;
};

#endif
