/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "DruidTriggers.h"

#include "DruidValues.h"
#include "Playerbots.h"

bool DruidDispelTrigger::IsActive()
{
    return bot->IsAlive() && DruidDispelSpell(bot, dispelType) &&
        DruidNeedsDispel(botAI, GetTarget(), dispelType);
}

// Selectively adapted from NotCronky aace1b02. Preserve local strategy names;
// native spell_druid.cpp and live combo ownership define the cast contracts.
namespace
{
    uint8 DruidCurrentTargetComboPoints(PlayerbotAI* ai, Player* bot)
    {
        Unit* target = ai->GetAiObjectContext()->GetValue<Unit*>("current target")->Get();
        if (!target || !target->IsAlive() || bot->GetComboTarget() != target)
            return 0;
        return bot->GetComboPoints();
    }
}

bool DruidFormTrigger::IsActive()
{
    return bot->IsAlive() && bot->HasSpell(spellId) && !bot->IsMounted() && !bot->IsFlying() &&
        bot->GetShapeshiftForm() != form;
}

bool DruidComboPointsTrigger::IsActive()
{
    Unit* target = AI_VALUE(Unit*, "current target");
    if (bot->GetShapeshiftForm() != FORM_CAT || !target || !target->IsAlive())
        return false;

    uint8 points = DruidCurrentTargetComboPoints(botAI, bot);
    switch (condition)
    {
        case Condition::NotFull:
            return points < 5;
        case Condition::NotFullHighEnergy:
            return points < 5 && bot->GetPower(POWER_ENERGY) >= 60;
        case Condition::Finisher:
            return points >= 5;
        case Condition::DyingTarget:
            return points > 0 && target->GetHealthPct() < 15.0f;
    }
    return false;
}

bool DruidSavageRoarTrigger::IsActive()
{
    return bot->GetShapeshiftForm() == FORM_CAT && (bot->HasSpell(52610) || bot->HasSpell(127538)) &&
        DruidCurrentTargetComboPoints(botAI, bot) > 0 && BuffTrigger::IsActive();
}

bool DruidDebuffTrigger::IsActive()
{
    return bot->HasSpell(spellId) && (!catOnly || bot->GetShapeshiftForm() == FORM_CAT) &&
        DebuffTrigger::IsActive();
}

Value<Unit*>* DruidMarkOfTheWildTrigger::GetTargetValue()
{
    return party ? context->GetValue<Unit*>("mark of the wild target") : BuffTrigger::GetTargetValue();
}

bool DruidMarkOfTheWildTrigger::IsActive()
{
    return bot->HasSpell(1126) && DruidNeedsMarkOfTheWild(botAI, GetTarget()) && BuffTrigger::IsActive();
}

bool DruidBerserkTrigger::IsActive()
{
    ShapeshiftForm form = bot->GetShapeshiftForm();
    return ((form == FORM_CAT && bot->HasSpell(106951)) || (form == FORM_BEAR && bot->HasSpell(50334))) &&
        BuffTrigger::IsActive() && botAI->CanCastSpell("berserk", bot);
}

bool DruidEclipseTrigger::IsActive()
{
    if (bot->GetTalentSpecialization() != SPEC_DRUID_BALANCE || !bot->HasSpell(lunar ? 2912 : 5176))
        return false;

    bool lunarEclipse = bot->HasAura(48518);
    bool solarEclipse = bot->HasAura(48517);
    if (!between)
        return lunar ? lunarEclipse : solarEclipse;
    if (lunarEclipse || solarEclipse)
        return false;

    // Starfire moves toward Solar (67483); Wrath toward Lunar (67484).
    // The native scripts retain this direction through zero until the endpoint.
    return bot->HasAura(lunar ? 67483 : 67484);
}
