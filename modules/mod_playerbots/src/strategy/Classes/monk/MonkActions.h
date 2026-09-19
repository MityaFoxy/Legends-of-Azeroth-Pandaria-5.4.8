/*
 * Copyright (C) 2026 Legends of Azeroth Pandaria Project.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 */

#ifndef _PLAYERBOT_MONKACTIONS_H
#define _PLAYERBOT_MONKACTIONS_H

#include "GenericSpellActions.h"

class PlayerbotAI;

class CastJabAction : public CastMeleeSpellAction
{
public:
    CastJabAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "jab") {}
};

class CastTigerPalmAction : public CastMeleeSpellAction
{
public:
    CastTigerPalmAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "tiger palm") {}
};

class CastBlackoutKickAction : public CastMeleeSpellAction
{
public:
    CastBlackoutKickAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "blackout kick") {}
};

class CastRisingSunKickAction : public CastMeleeSpellAction
{
public:
    CastRisingSunKickAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "rising sun kick") {}
};

class CastFistsOfFuryAction : public CastMeleeSpellAction
{
public:
    CastFistsOfFuryAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "fists of fury") {}
};

class CastSpinningCraneKickAction : public CastMeleeSpellAction
{
public:
    CastSpinningCraneKickAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "spinning crane kick") {}
};

class CastExpelHarmAction : public CastHealingSpellAction
{
public:
    CastExpelHarmAction(PlayerbotAI* botAI) : CastHealingSpellAction(botAI, "expel harm") {}
};

class CastSpearHandStrikeAction : public CastMeleeSpellAction
{
public:
    CastSpearHandStrikeAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "spear hand strike") {}
};

class CastKegSmashAction : public CastMeleeSpellAction
{
public:
    CastKegSmashAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "keg smash") {}
};

class CastBreathOfFireAction : public CastMeleeSpellAction
{
public:
    CastBreathOfFireAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "breath of fire") {}
};

class CastGuardAction : public CastBuffSpellAction
{
public:
    CastGuardAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "guard") {}
};

class CastPurifyingBrewAction : public CastBuffSpellAction
{
public:
    CastPurifyingBrewAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "purifying brew") {}
};

class CastFortifyingBrewAction : public CastBuffSpellAction
{
public:
    CastFortifyingBrewAction(PlayerbotAI* botAI) : CastBuffSpellAction(botAI, "fortifying brew") {}
};

class CastProvokeAction : public CastMeleeSpellAction
{
public:
    CastProvokeAction(PlayerbotAI* botAI) : CastMeleeSpellAction(botAI, "provoke") {}
};

class CastRenewingMistOnPartyAction : public BuffOnPartyAction
{
public:
    CastRenewingMistOnPartyAction(PlayerbotAI* botAI) : BuffOnPartyAction(botAI, "renewing mist") {}
};

class CastSoothingMistOnPartyAction : public HealPartyMemberAction
{
public:
    CastSoothingMistOnPartyAction(PlayerbotAI* botAI)
        : HealPartyMemberAction(botAI, "soothing mist", 15.0f, HealingManaEfficiency::VERY_HIGH)
    {
    }
};

class CastSurgingMistOnPartyAction : public HealPartyMemberAction
{
public:
    CastSurgingMistOnPartyAction(PlayerbotAI* botAI)
        : HealPartyMemberAction(botAI, "surging mist", 35.0f, HealingManaEfficiency::LOW)
    {
    }
};

class CastEnvelopingMistOnPartyAction : public HealPartyMemberAction
{
public:
    CastEnvelopingMistOnPartyAction(PlayerbotAI* botAI)
        : HealPartyMemberAction(botAI, "enveloping mist", 30.0f, HealingManaEfficiency::MEDIUM)
    {
    }
};

class CastLifeCocoonOnPartyAction : public HealPartyMemberAction
{
public:
    CastLifeCocoonOnPartyAction(PlayerbotAI* botAI)
        : HealPartyMemberAction(botAI, "life cocoon", 40.0f, HealingManaEfficiency::MEDIUM)
    {
    }
};

class CastUpliftAction : public CastSpellAction
{
public:
    CastUpliftAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "uplift") {}

    std::string const GetTargetName() override { return "self target"; }
};

class CastManaTeaAction : public CastSpellAction
{
public:
    CastManaTeaAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "mana tea") {}

    std::string const GetTargetName() override { return "self target"; }
};

class CastElusiveBrewAction : public CastSpellAction
{
public:
    CastElusiveBrewAction(PlayerbotAI* botAI) : CastSpellAction(botAI, "elusive brew") {}

    std::string const GetTargetName() override { return "self target"; }
};

#endif
