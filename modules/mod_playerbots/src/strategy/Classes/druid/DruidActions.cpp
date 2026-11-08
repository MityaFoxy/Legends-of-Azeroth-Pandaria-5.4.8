/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "DruidActions.h"

#include "ActionExecutionTrace.h"
#include "DruidValues.h"
#include "Event.h"
#include "Playerbots.h"

Value<Unit*>* CastMarkOfTheWildOnPartyAction::GetTargetValue()
{
    return context->GetValue<Unit*>("mark of the wild target");
}

bool CastMarkOfTheWildOnPartyAction::Execute(Event event)
{
    if (!ActionExecutionTrace::Enabled())
        return BuffOnPartyAction::Execute(event);

    Unit* target = GetTarget();
    bool before = target && target->HasAura(1126);
    bool accepted = BuffOnPartyAction::Execute(event);
    if (target)
        TC_LOG_DEBUG("playerbots.execution", "event=druid-mark bot={} target={} target_type={} before={} after={} accepted={}",
            bot->GetGUID().GetCounter(), target->GetGUID().GetCounter(), uint32(target->GetTypeId()),
            before, target->HasAura(1126), accepted);
    return accepted;
}

bool DruidDispelAction::SelectSpell()
{
    uint32 id = DruidDispelSpell(bot, dispelType);
    spell = id == 88423 ? "nature's cure" : "remove corruption";
    return id != 0;
}

Value<Unit*>* DruidDispelAction::GetTargetValue()
{
    return self ? context->GetValue<Unit*>("self target") : CurePartyMemberAction::GetTargetValue();
}

bool DruidDispelAction::isUseful()
{
    return bot->IsAlive() && SelectSpell() && DruidNeedsDispel(botAI, GetTarget(), dispelType) &&
        CastSpellAction::isUseful();
}

bool DruidDispelAction::isPossible()
{
    return SelectSpell() && CastSpellAction::isPossible();
}

NextAction** DruidDispelAction::getPrerequisites()
{
    SpellInfo const* info = sSpellMgr->GetSpellInfo(DruidDispelSpell(bot, dispelType));
    if (info && info->CheckShapeshift(bot->GetShapeshiftForm()) == SPELL_FAILED_NOT_SHAPESHIFT)
        return NextAction::array(0, new NextAction("caster form"), nullptr);
    return CastSpellAction::getPrerequisites();
}

bool DruidDispelAction::Execute(Event event)
{
    // Party Values are cached; another healer may have removed the effect
    // since this action was queued. Do not spend mana/cooldown on that target.
    return isUseful() && isPossible() && CastSpellAction::Execute(event);
}

NextAction** CastReviveAction::getPrerequisites()
{
    return NextAction::merge(NextAction::array(0, new NextAction("caster form"), nullptr),
                             ResurrectPartyMemberAction::getPrerequisites());
}

NextAction** CastRebirthAction::getPrerequisites()
{
    return NextAction::merge(NextAction::array(0, new NextAction("caster form"), nullptr),
                             ResurrectPartyMemberAction::getPrerequisites());
}

bool CastRebirthAction::isUseful()
{
    return CastSpellAction::isUseful() &&
           AI_VALUE2(float, "distance", GetTargetName()) <= sPlayerbotAIConfig->spellDistance;
}

Unit* CastRejuvenationOnNotFullAction::GetTarget()
{
    Group* group = bot->GetGroup();
    if (!group)
        return nullptr;

    MinValueCalculator calc(100);
    for (GroupReference* gref = group->GetFirstMember(); gref; gref = gref->next())
    {
        Player* player = gref->GetSource();
        // Match the existing AoE-heal Value's native target eligibility. In
        // particular, another floor/instance must not starve a reachable ally.
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
        if (botAI->HasAura("rejuvenation", player))
        {
            continue;
        }
        calc.probe(player->GetHealthPct(), player);
    }
    return (Unit*)calc.param;
}

bool CastRejuvenationOnNotFullAction::isUseful()
{
    return GetTarget() && CastSpellAction::isUseful();
}

bool CastRejuvenationOnNotFullAction::Execute(Event event)
{
    // Re-select after a group change or healing by another player; null must
    // not turn into the native CastSpell fallback to a self-targeted cast.
    return isUseful() && CastSpellAction::Execute(event);
}
