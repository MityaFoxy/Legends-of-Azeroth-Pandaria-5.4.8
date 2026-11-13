/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "HunterActions.h"

#include "AttackersValue.h"
#include "Event.h"
#include "GenericSpellActions.h"
#include "Playerbots.h"

Unit* SelectSerpentStingAttacker(PlayerbotAI* botAI)
{
    Player* bot = botAI->GetBot();
    Unit* current = botAI->GetAiObjectContext()->GetValue<Unit*>("current target")->Get();
    Unit* result = nullptr;
    for (ObjectGuid const guid : botAI->GetAiObjectContext()->GetValue<GuidVector>("attackers")->Get())
    {
        Unit* unit = botAI->GetUnit(guid);
        // The attackers value is cached. Recheck eligibility at every use,
        // including immediately before casting at a secondary target.
        if (!unit || unit == current || !unit->IsAlive() || !bot->IsInMap(unit) || !bot->InSamePhase(unit) ||
            !AttackersValue::IsValidTarget(unit, bot) ||
            unit->HasBreakableByDamageCrowdControlAura() || unit->HasBreakableByDamageAuraType(SPELL_AURA_MOD_ROOT) ||
            !bot->IsWithinCombatRange(unit, botAI->GetRange("spell")) ||
            botAI->HasAura("serpent sting", unit, false, true))
            continue;

        if (!result || unit->GetHealth() >= result->GetHealth())
            result = unit;
    }
    return result;
}

Unit* CastSerpentStingOnAttackerAction::GetTarget() { return SelectSerpentStingAttacker(botAI); }

bool CastSerpentStingOnAttackerAction::Execute([[maybe_unused]] Event event)
{
    if (!CastDebuffSpellOnAttackerAction::isUseful())
        return false;

    Unit* target = GetTarget();
    return target && botAI->CastSpell(spell, target);
}

bool CastHuntersMarkAction::isUseful() { return CastDebuffSpellAction::isUseful(); }

bool CastViperStingAction::isUseful()
{
    return AI_VALUE2(uint8, "mana", "self target") < 50 && AI_VALUE2(uint8, "mana", "current target") >= 30;
}

bool CastAspectOfTheCheetahAction::isUseful()
{
    return !botAI->HasAnyAuraOf(GetTarget(), "aspect of the cheetah", "aspect of the pack", nullptr);
}

Value<Unit*>* CastFreezingTrap::GetTargetValue() { return context->GetValue<Unit*>("cc target", "freezing trap"); }

bool CastAutoShotAction::isUseful()
{
    if (botAI->IsInVehicle() && !botAI->IsInVehicle(false, false, true))
        return false;

    if (AI_VALUE(Unit*, "current target") && bot->GetCurrentSpell(CURRENT_AUTOREPEAT_SPELL) &&
        bot->GetCurrentSpell(CURRENT_AUTOREPEAT_SPELL)->m_targets.GetUnitTargetGUID() ==
            AI_VALUE(Unit*, "current target")->GetGUID())
    {
        return false;
    }
    return AI_VALUE(uint32, "active spell") != AI_VALUE2(uint32, "spell id", getName());
}

Value<Unit*>* CastScareBeastCcAction::GetTargetValue() { return context->GetValue<Unit*>("cc target", "scare beast"); }

bool CastScareBeastCcAction::Execute(Event event) { return botAI->CastSpell("scare beast", GetTarget()); }

bool CastWingClipAction::isUseful() { return CastSpellAction::isUseful() && !botAI->HasAura(spell, GetTarget()); }

NextAction** CastWingClipAction::getPrerequisites() { return nullptr; }
