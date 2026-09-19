/*
 * Copyright (C) 2026 Legends of Azeroth Pandaria Project.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 */

#include "MonkStrategies.h"

#include "Playerbots.h"

WindwalkerMonkStrategy::WindwalkerMonkStrategy(PlayerbotAI* botAI) : MeleeCombatStrategy(botAI)
{
}

NextAction** WindwalkerMonkStrategy::getDefaultActions()
{
    return NextAction::array(0,
        new NextAction("rising sun kick", ACTION_DEFAULT + 0.5f),
        new NextAction("fists of fury", ACTION_DEFAULT + 0.4f),
        new NextAction("blackout kick", ACTION_DEFAULT + 0.3f),
        new NextAction("jab", ACTION_DEFAULT + 0.2f),
        new NextAction("melee", ACTION_DEFAULT), nullptr);
}

void WindwalkerMonkStrategy::InitTriggers(std::vector<TriggerNode*>& triggers)
{
    MeleeCombatStrategy::InitTriggers(triggers);

    triggers.push_back(new TriggerNode("tiger power",
        NextAction::array(0, new NextAction("tiger palm", ACTION_HIGH), nullptr)));
    triggers.push_back(new TriggerNode("low health",
        NextAction::array(0, new NextAction("expel harm", ACTION_HIGH + 1), nullptr)));
    triggers.push_back(new TriggerNode("spear hand strike",
        NextAction::array(0, new NextAction("spear hand strike", ACTION_INTERRUPT), nullptr)));
}

void WindwalkerMonkAoeStrategy::InitTriggers(std::vector<TriggerNode*>& triggers)
{
    triggers.push_back(new TriggerNode("medium aoe",
        NextAction::array(0, new NextAction("spinning crane kick", ACTION_NORMAL + 1), nullptr)));
}

BrewmasterMonkStrategy::BrewmasterMonkStrategy(PlayerbotAI* botAI) : MeleeCombatStrategy(botAI)
{
}

NextAction** BrewmasterMonkStrategy::getDefaultActions()
{
    return NextAction::array(0,
        new NextAction("keg smash", ACTION_DEFAULT + 0.4f),
        new NextAction("blackout kick", ACTION_DEFAULT + 0.3f),
        new NextAction("jab", ACTION_DEFAULT + 0.2f),
        new NextAction("melee", ACTION_DEFAULT), nullptr);
}

void BrewmasterMonkStrategy::InitTriggers(std::vector<TriggerNode*>& triggers)
{
    MeleeCombatStrategy::InitTriggers(triggers);

    triggers.push_back(new TriggerNode("heavy stagger",
        NextAction::array(0, new NextAction("purifying brew", ACTION_HIGH + 3), nullptr)));
    triggers.push_back(new TriggerNode("moderate stagger",
        NextAction::array(0, new NextAction("purifying brew", ACTION_HIGH + 2), nullptr)));
    triggers.push_back(new TriggerNode("guard",
        NextAction::array(0, new NextAction("guard", ACTION_HIGH + 1), nullptr)));
    triggers.push_back(new TriggerNode("elusive brew available",
        NextAction::array(0, new NextAction("elusive brew", ACTION_HIGH + 1), nullptr)));
    triggers.push_back(new TriggerNode("low health",
        NextAction::array(0, new NextAction("expel harm", ACTION_HIGH + 2), nullptr)));
    triggers.push_back(new TriggerNode("critical health",
        NextAction::array(0, new NextAction("fortifying brew", ACTION_EMERGENCY + 1), nullptr)));
    triggers.push_back(new TriggerNode("lose aggro",
        NextAction::array(0, new NextAction("provoke", ACTION_INTERRUPT + 1), nullptr)));
    triggers.push_back(new TriggerNode("spear hand strike",
        NextAction::array(0, new NextAction("spear hand strike", ACTION_INTERRUPT), nullptr)));
}

void BrewmasterMonkAoeStrategy::InitTriggers(std::vector<TriggerNode*>& triggers)
{
    triggers.push_back(new TriggerNode("medium aoe",
        NextAction::array(0, new NextAction("breath of fire", ACTION_NORMAL + 1), nullptr)));
}

NextAction** MistweaverMonkStrategy::getDefaultActions()
{
    return NextAction::array(0, new NextAction("soothing mist on party", ACTION_DEFAULT), nullptr);
}

void MistweaverMonkStrategy::InitTriggers(std::vector<TriggerNode*>& triggers)
{
    triggers.push_back(new TriggerNode(
        "medium group heal setting",
        NextAction::array(0, new NextAction("uplift", ACTION_CRITICAL_HEAL + 3),
                          new NextAction("renewing mist on party", ACTION_CRITICAL_HEAL + 2), nullptr)));
    triggers.push_back(new TriggerNode(
        "group heal setting",
        NextAction::array(0, new NextAction("renewing mist on party", ACTION_MEDIUM_HEAL + 3),
                          new NextAction("uplift", ACTION_MEDIUM_HEAL + 2), nullptr)));
    triggers.push_back(new TriggerNode(
        "party member critical health",
        NextAction::array(0, new NextAction("life cocoon on party", ACTION_EMERGENCY + 2),
                          new NextAction("surging mist on party", ACTION_EMERGENCY + 1), nullptr)));
    triggers.push_back(new TriggerNode(
        "party member low health",
        NextAction::array(0, new NextAction("enveloping mist on party", ACTION_MEDIUM_HEAL + 2),
                          new NextAction("surging mist on party", ACTION_MEDIUM_HEAL + 1),
                          new NextAction("soothing mist on party", ACTION_MEDIUM_HEAL), nullptr)));
    triggers.push_back(new TriggerNode(
        "party member medium health",
        NextAction::array(0, new NextAction("renewing mist on party", ACTION_LIGHT_HEAL + 2),
                          new NextAction("soothing mist on party", ACTION_LIGHT_HEAL + 1), nullptr)));
    triggers.push_back(new TriggerNode(
        "party member almost full health",
        NextAction::array(0, new NextAction("renewing mist on party", ACTION_LIGHT_HEAL), nullptr)));
    triggers.push_back(new TriggerNode(
        "mana tea available", NextAction::array(0, new NextAction("mana tea", ACTION_HIGH + 1), nullptr)));
    triggers.push_back(new TriggerNode(
        "party member to heal out of spell range",
        NextAction::array(0, new NextAction("reach party member to heal", ACTION_CRITICAL_HEAL + 1), nullptr)));
}
