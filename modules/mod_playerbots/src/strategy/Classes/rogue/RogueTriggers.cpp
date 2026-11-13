/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "RogueTriggers.h"

#include "GenericTriggers.h"
#include "Playerbots.h"

// Combo-point ownership and refresh policy adapted from NotCronky's Rogue AI:
// https://github.com/NotCronky/Legends-of-Azeroth-Pandaria-5.4.8/commit/d22152554ed1fb2062accbd589569a2d0f4da187
// Keep the existing local strategy names and their three/five-point thresholds.
namespace
{
    uint8 CurrentTargetComboPoints(PlayerbotAI* botAI, Player* bot)
    {
        Unit* target = botAI->GetAiObjectContext()->GetValue<Unit*>("current target")->Get();
        if (!target || !target->IsAlive() || bot->GetComboTarget() != target)
            return 0;

        // Read live state: a finisher or target switch can invalidate cached points.
        return bot->GetComboPoints();
    }
}

bool RogueComboPointsTrigger::IsActive()
{
    return CurrentTargetComboPoints(botAI, bot) >= amount;
}

bool RogueTargetDyingTrigger::IsActive()
{
    Unit* target = AI_VALUE(Unit*, "current target");
    return target && target->GetHealthPct() < 15.0f && RogueComboPointsTrigger::IsActive();
}

bool SliceAndDiceTrigger::IsActive()
{
    return bot->HasSpell(5171) && CurrentTargetComboPoints(botAI, bot) && BuffTrigger::IsActive();
}
