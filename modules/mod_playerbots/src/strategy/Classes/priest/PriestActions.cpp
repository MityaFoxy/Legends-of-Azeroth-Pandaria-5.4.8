/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "PriestActions.h"

#include "Event.h"
#include "Playerbots.h"

bool CastRemoveShadowformAction::isUseful() { return botAI->HasAura("shadowform", AI_VALUE(Unit*, "self target")); }

bool CastRemoveShadowformAction::isPossible() { return true; }

bool CastRemoveShadowformAction::Execute(Event event)
{
    botAI->RemoveAura("shadowform");
    return true;
}

Unit* CastPowerWordShieldOnAlmostFullHealthBelowAction::GetTarget()
{
    Group* group = bot->GetGroup();
    if (!group)
        return nullptr;
    for (GroupReference* gref = group->GetFirstMember(); gref; gref = gref->next())
    {
        Player* player = gref->GetSource();
        if (!player || !player->IsInWorld() || !player->IsAlive() ||
            player->GetMap() != bot->GetMap() || !bot->IsValidAssistTarget(player))
        {
            continue;
        }
        if (player->GetHealthPct() > sPlayerbotAIConfig->almostFullHealth)
        {
            continue;
        }
        if (bot->GetDistance(player) > sPlayerbotAIConfig->spellDistance ||
            (player != bot && !bot->IsWithinLOSInMap(player)))
        {
            continue;
        }
        if (botAI->HasAnyAuraOf(player, "weakened soul", "power word: shield", nullptr))
        {
            continue;
        }
        return player;
    }
    return nullptr;
}

bool CastPowerWordShieldOnAlmostFullHealthBelowAction::isUseful()
{
    return GetTarget() && CastSpellAction::isUseful();
}

bool CastPowerWordShieldOnAlmostFullHealthBelowAction::Execute(Event event)
{
    return isUseful() && CastSpellAction::Execute(event);
}

Unit* CastPowerWordShieldOnNotFullAction::GetTarget()
{
    Group* group = bot->GetGroup();
    if (!group)
        return nullptr;
    MinValueCalculator calc(100);
    for (GroupReference* gref = group->GetFirstMember(); gref; gref = gref->next())
    {
        Player* player = gref->GetSource();
        if (!player || !player->IsInWorld() || !player->IsAlive() || player->IsFullHealth() ||
            player->GetMap() != bot->GetMap() || !bot->IsValidAssistTarget(player))
        {
            continue;
        }
        if (bot->GetDistance(player) > sPlayerbotAIConfig->spellDistance ||
            (player != bot && !bot->IsWithinLOSInMap(player)))
        {
            continue;
        }
        if (botAI->HasAnyAuraOf(player, "weakened soul", "power word: shield", nullptr))
        {
            continue;
        }
        calc.probe(player->GetHealthPct(), player);
    }
    return (Unit*)calc.param;
}

bool CastPowerWordShieldOnNotFullAction::isUseful()
{
    return GetTarget() && CastSpellAction::isUseful();
}

bool CastPowerWordShieldOnNotFullAction::Execute(Event event)
{
    // A queued group heal must not fall through to a self-cast after disband.
    return isUseful() && CastSpellAction::Execute(event);
}
