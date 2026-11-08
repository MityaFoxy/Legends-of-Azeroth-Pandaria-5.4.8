/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#ifndef _PLAYERBOT_DRUIDTRIGGERS_H
#define _PLAYERBOT_DRUIDTRIGGERS_H

#include "GenericTriggers.h"
#include "CureTriggers.h"
#include "SharedDefines.h"

class DruidDispelTrigger : public PartyMemberNeedCureTrigger
{
public:
    DruidDispelTrigger(PlayerbotAI* ai, std::string const name, uint32 dispelType)
        : PartyMemberNeedCureTrigger(ai, name, dispelType) {}
    bool IsActive() override;
};

class DruidFormTrigger : public Trigger
{
public:
    DruidFormTrigger(PlayerbotAI* ai, std::string const name, uint32 spellId, ShapeshiftForm form)
        : Trigger(ai, name), spellId(spellId), form(form) {}
    bool IsActive() override;

private:
    uint32 spellId;
    ShapeshiftForm form;
};

class DruidComboPointsTrigger : public Trigger
{
public:
    enum class Condition { NotFull, NotFullHighEnergy, Finisher, DyingTarget };
    DruidComboPointsTrigger(PlayerbotAI* ai, std::string const name, Condition condition)
        : Trigger(ai, name), condition(condition) {}
    bool IsActive() override;

private:
    Condition condition;
};

class DruidSavageRoarTrigger : public BuffTrigger
{
public:
    DruidSavageRoarTrigger(PlayerbotAI* ai)
        : BuffTrigger(ai, "savage roar", 1, false, false, 3 * IN_MILLISECONDS) {}
    bool IsActive() override;
};

class DruidDebuffTrigger : public DebuffTrigger
{
public:
    DruidDebuffTrigger(PlayerbotAI* ai, std::string const spell, uint32 spellId,
        bool owner = false, float lifetime = 8.0f, bool catOnly = false)
        : DebuffTrigger(ai, spell, 1, owner, lifetime), spellId(spellId), catOnly(catOnly) {}
    bool IsActive() override;

private:
    uint32 spellId;
    bool catOnly;
};

class DruidMarkOfTheWildTrigger : public BuffTrigger
{
public:
    DruidMarkOfTheWildTrigger(PlayerbotAI* ai, bool party = false)
        : BuffTrigger(ai, "mark of the wild", 2), party(party) {}
    bool IsActive() override;
    Value<Unit*>* GetTargetValue() override;

private:
    bool party;
};

class DruidBerserkTrigger : public BuffTrigger
{
public:
    DruidBerserkTrigger(PlayerbotAI* ai) : BuffTrigger(ai, "berserk") {}
    bool IsActive() override;
};

class DruidEclipseTrigger : public Trigger
{
public:
    // The old "cooldown" names select the direction between Eclipse buffs.
    DruidEclipseTrigger(PlayerbotAI* ai, std::string const name, bool lunar, bool between)
        : Trigger(ai, name), lunar(lunar), between(between) {}
    bool IsActive() override;

private:
    bool lunar;
    bool between;
};


#endif
