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

class BrewmasterMonkStrategy : public MeleeCombatStrategy
{
public:
    BrewmasterMonkStrategy(PlayerbotAI* botAI);

    void InitTriggers(std::vector<TriggerNode*>& triggers) override;
    NextAction** getDefaultActions() override;
    std::string const getName() override { return "tank"; }
    uint32 GetType() const override { return MeleeCombatStrategy::GetType() | STRATEGY_TYPE_TANK; }
};

class BrewmasterMonkAoeStrategy : public CombatStrategy
{
public:
    BrewmasterMonkAoeStrategy(PlayerbotAI* botAI) : CombatStrategy(botAI) {}

    void InitTriggers(std::vector<TriggerNode*>& triggers) override;
    std::string const getName() override { return "aoe"; }
};

class MistweaverMonkStrategy : public Strategy
{
public:
    MistweaverMonkStrategy(PlayerbotAI* botAI) : Strategy(botAI) {}

    void InitTriggers(std::vector<TriggerNode*>& triggers) override;
    NextAction** getDefaultActions() override;
    std::string const getName() override { return "heal"; }
    uint32 GetType() const override { return STRATEGY_TYPE_RANGED | STRATEGY_TYPE_HEAL; }
};

#endif
