/*
 * Copyright (C) 2026 Legends of Azeroth Pandaria Project.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 */

#ifndef _PLAYERBOT_MONKSTRATEGIES_H
#define _PLAYERBOT_MONKSTRATEGIES_H

#include "MeleeCombatStrategy.h"

class PlayerbotAI;

class WindwalkerMonkStrategy : public MeleeCombatStrategy
{
public:
    WindwalkerMonkStrategy(PlayerbotAI* botAI);

    void InitTriggers(std::vector<TriggerNode*>& triggers) override;
    NextAction** getDefaultActions() override;
    std::string const getName() override { return "melee"; }
    uint32 GetType() const override { return MeleeCombatStrategy::GetType() | STRATEGY_TYPE_DPS; }
};

class WindwalkerMonkAoeStrategy : public CombatStrategy
{
public:
    WindwalkerMonkAoeStrategy(PlayerbotAI* botAI) : CombatStrategy(botAI) {}

    void InitTriggers(std::vector<TriggerNode*>& triggers) override;
    std::string const getName() override { return "melee aoe"; }
};

#endif
