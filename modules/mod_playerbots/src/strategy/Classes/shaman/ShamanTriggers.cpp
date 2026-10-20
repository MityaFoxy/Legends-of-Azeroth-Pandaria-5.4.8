/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "ShamanTriggers.h"

#include "Playerbots.h"
#include "ShamanWeaponImbue.h"
#include "SpellAuras.h"

bool ShamanWeaponImbueTrigger::IsActive()
{
    return bot->GetTalentSpecialization() == SPEC_SHAMAN_ENHANCEMENT &&
        bot->HasSpell(spellId) && GetShamanImbueWeapon(*bot, hand);
}

bool MaelstromWeaponTrigger::IsActive()
{
    if (!bot->IsAlive() || bot->GetTalentSpecialization() != SPEC_SHAMAN_ENHANCEMENT ||
        !bot->HasSpell(403))
        return false;
    // Read the actual proc aura, not the passive talent with the same name.
    // Keep the existing strategy's four-stack threshold; native casting owns
    // movement, cast time, cost, consumption and target validation.
    Aura const* aura = bot->GetAura(53817);
    return aura && aura->GetStackAmount() >= 4;
}
