/*
 * Copyright (C) 2026 Legends of Azeroth Pandaria Project.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 */

#include "MonkAiObjectContext.h"

#include "GenericTriggers.h"
#include "MonkActions.h"
#include "MonkStrategies.h"
#include "NamedObjectContext.h"
#include "Playerbots.h"

class MonkStrategyFactoryInternal : public NamedObjectContext<Strategy>
{
public:
    MonkStrategyFactoryInternal()
    {
        creators["melee aoe"] = &MonkStrategyFactoryInternal::melee_aoe;
        creators["aoe"] = &MonkStrategyFactoryInternal::aoe;
    }

private:
    static Strategy* melee_aoe(PlayerbotAI* botAI) { return new WindwalkerMonkAoeStrategy(botAI); }
    static Strategy* aoe(PlayerbotAI* botAI) { return new BrewmasterMonkAoeStrategy(botAI); }
};

class MonkCombatStrategyFactoryInternal : public NamedObjectContext<Strategy>
{
public:
    MonkCombatStrategyFactoryInternal() : NamedObjectContext<Strategy>(false, true)
    {
        creators["melee"] = &MonkCombatStrategyFactoryInternal::melee;
        creators["tank"] = &MonkCombatStrategyFactoryInternal::tank;
    }

private:
    static Strategy* melee(PlayerbotAI* botAI) { return new WindwalkerMonkStrategy(botAI); }
    static Strategy* tank(PlayerbotAI* botAI) { return new BrewmasterMonkStrategy(botAI); }
};

class MonkTriggerFactoryInternal : public NamedObjectContext<Trigger>
{
public:
    MonkTriggerFactoryInternal()
    {
        creators["tiger power"] = &MonkTriggerFactoryInternal::tiger_power;
        creators["spear hand strike"] = &MonkTriggerFactoryInternal::spear_hand_strike;
        creators["guard"] = &MonkTriggerFactoryInternal::guard;
        creators["moderate stagger"] = &MonkTriggerFactoryInternal::moderate_stagger;
        creators["heavy stagger"] = &MonkTriggerFactoryInternal::heavy_stagger;
    }

private:
    static Trigger* tiger_power(PlayerbotAI* botAI) { return new BuffTrigger(botAI, "tiger power"); }
    static Trigger* spear_hand_strike(PlayerbotAI* botAI)
    {
        return new InterruptSpellTrigger(botAI, "spear hand strike");
    }
    static Trigger* guard(PlayerbotAI* botAI) { return new BuffTrigger(botAI, "guard"); }
    static Trigger* moderate_stagger(PlayerbotAI* botAI) { return new HasAuraTrigger(botAI, "moderate stagger"); }
    static Trigger* heavy_stagger(PlayerbotAI* botAI) { return new HasAuraTrigger(botAI, "heavy stagger"); }
};

class MonkAiObjectContextInternal : public NamedObjectContext<Action>
{
public:
    MonkAiObjectContextInternal()
    {
        creators["jab"] = &MonkAiObjectContextInternal::jab;
        creators["tiger palm"] = &MonkAiObjectContextInternal::tiger_palm;
        creators["blackout kick"] = &MonkAiObjectContextInternal::blackout_kick;
        creators["rising sun kick"] = &MonkAiObjectContextInternal::rising_sun_kick;
        creators["fists of fury"] = &MonkAiObjectContextInternal::fists_of_fury;
        creators["spinning crane kick"] = &MonkAiObjectContextInternal::spinning_crane_kick;
        creators["expel harm"] = &MonkAiObjectContextInternal::expel_harm;
        creators["spear hand strike"] = &MonkAiObjectContextInternal::spear_hand_strike;
        creators["keg smash"] = &MonkAiObjectContextInternal::keg_smash;
        creators["breath of fire"] = &MonkAiObjectContextInternal::breath_of_fire;
        creators["guard"] = &MonkAiObjectContextInternal::guard;
        creators["purifying brew"] = &MonkAiObjectContextInternal::purifying_brew;
        creators["fortifying brew"] = &MonkAiObjectContextInternal::fortifying_brew;
        creators["provoke"] = &MonkAiObjectContextInternal::provoke;
        creators["taunt spell"] = &MonkAiObjectContextInternal::provoke;
    }

private:
    static Action* jab(PlayerbotAI* botAI) { return new CastJabAction(botAI); }
    static Action* tiger_palm(PlayerbotAI* botAI) { return new CastTigerPalmAction(botAI); }
    static Action* blackout_kick(PlayerbotAI* botAI) { return new CastBlackoutKickAction(botAI); }
    static Action* rising_sun_kick(PlayerbotAI* botAI) { return new CastRisingSunKickAction(botAI); }
    static Action* fists_of_fury(PlayerbotAI* botAI) { return new CastFistsOfFuryAction(botAI); }
    static Action* spinning_crane_kick(PlayerbotAI* botAI) { return new CastSpinningCraneKickAction(botAI); }
    static Action* expel_harm(PlayerbotAI* botAI) { return new CastExpelHarmAction(botAI); }
    static Action* spear_hand_strike(PlayerbotAI* botAI) { return new CastSpearHandStrikeAction(botAI); }
    static Action* keg_smash(PlayerbotAI* botAI) { return new CastKegSmashAction(botAI); }
    static Action* breath_of_fire(PlayerbotAI* botAI) { return new CastBreathOfFireAction(botAI); }
    static Action* guard(PlayerbotAI* botAI) { return new CastGuardAction(botAI); }
    static Action* purifying_brew(PlayerbotAI* botAI) { return new CastPurifyingBrewAction(botAI); }
    static Action* fortifying_brew(PlayerbotAI* botAI) { return new CastFortifyingBrewAction(botAI); }
    static Action* provoke(PlayerbotAI* botAI) { return new CastProvokeAction(botAI); }
};

MonkAiObjectContext::MonkAiObjectContext(PlayerbotAI* botAI) : AiObjectContext(botAI)
{
    strategyContexts.Add(new MonkStrategyFactoryInternal());
    strategyContexts.Add(new MonkCombatStrategyFactoryInternal());
    actionContexts.Add(new MonkAiObjectContextInternal());
    triggerContexts.Add(new MonkTriggerFactoryInternal());
}
