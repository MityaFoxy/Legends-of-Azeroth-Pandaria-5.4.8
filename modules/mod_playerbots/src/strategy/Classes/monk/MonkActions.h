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

#endif
