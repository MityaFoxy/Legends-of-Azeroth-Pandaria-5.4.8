/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */
#include "EnemyHealerTargetValue.h"

#include "Playerbots.h"

Unit* EnemyHealerTargetValue::Calculate()
{
    GuidVector attackers = botAI->GetAiObjectContext()->GetValue<GuidVector>("attackers")->Get();
    Unit* target = botAI->GetAiObjectContext()->GetValue<Unit*>("current target")->Get();
    float const range = botAI->GetRange("spell");

    for (ObjectGuid const guid : attackers)
    {
        Unit* unit = botAI->GetUnit(guid);
        if (!unit || unit == target || !unit->IsInWorld() || !unit->IsAlive() ||
            unit->GetMap() != bot->GetMap() || !bot->IsValidAttackTarget(unit) ||
            bot->GetDistance(unit) > range || !bot->IsWithinLOSInMap(unit))
            continue;

        if (!botAI->IsInterruptableSpellCasting(unit, qualifier))
            continue;

        for (CurrentSpellTypes type : {CURRENT_GENERIC_SPELL, CURRENT_CHANNELED_SPELL})
            if (Spell* spell = unit->GetCurrentSpell(type))
                if (spell->GetSpellInfo()->IsPositive())
                    return unit;
    }
    return nullptr;
}
