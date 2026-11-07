/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "HunterTriggers.h"

#include "GenericTriggers.h"
#include "HunterActions.h"
#include "Pet.h"
#include "PlayerbotAIConfig.h"
#include "Playerbots.h"
#include "ServerFacade.h"
#include "SharedDefines.h"

Unit* SerpentStingOnAttackerTrigger::GetTarget() { return SelectSerpentStingAttacker(botAI); }

bool HunterNoPetTrigger::IsActive()
{
    // Call Pet 1 loads active slot 0; it cannot create a pet for an empty slot.
    return NoPetTrigger::IsActive() && bot->HasSpell(883) &&
        bot->GetPetIdBySlot(PET_SLOT_ACTIVE_FIRST);
}

bool HuntersPetMediumHealthTrigger::IsActive()
{
    Pet* pet = bot->GetPet();
    return pet && pet->IsAlive() && pet->GetHealthPct() < sPlayerbotAIConfig->mediumHealth &&
        !botAI->HasAura("mend pet", pet);
}

bool HuntersPetDeadTrigger::IsActive()
{
    Pet* pet = bot->GetPet();
    return pet && !pet->IsAlive();
}
