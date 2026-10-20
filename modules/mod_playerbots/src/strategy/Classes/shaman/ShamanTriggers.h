/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#ifndef _PLAYERBOT_SHAMANTRIGGERS_H
#define _PLAYERBOT_SHAMANTRIGGERS_H

#include "GenericTriggers.h"
#include "SharedDefines.h"
#include "Unit.h"

class PlayerbotAI;

class ShamanWeaponImbueTrigger : public Trigger
{
public:
    ShamanWeaponImbueTrigger(PlayerbotAI* ai, std::string name, WeaponAttackType hand, uint32 spellId)
        : Trigger(ai, name), hand(hand), spellId(spellId) { }
    bool IsActive() override;
private:
    WeaponAttackType hand;
    uint32 spellId;
};

class MaelstromWeaponTrigger : public Trigger
{
public:
    MaelstromWeaponTrigger(PlayerbotAI* ai) : Trigger(ai, "maelstrom weapon 4") { }
    bool IsActive() override;
};

#endif
