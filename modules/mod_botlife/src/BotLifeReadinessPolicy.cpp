#include "BotLifeReadiness.h"
#include <cmath>

namespace BotLife
{
PreparationDecision EvaluateReadiness(Readiness const& s, bool recovering)
{
    if (!s.weapon || !s.offhand)
        return {Preparation::Unprepared, "missing-weapon"};
    if (s.level >= 10 && (!s.coreArmor || s.armorPieces < 5))
        return {Preparation::Unprepared, "missing-armor"};
    if (s.level >= 20 && (!std::isfinite(s.averageItemLevel) || s.averageItemLevel < s.level * 0.7f))
        return {Preparation::Unprepared, "underlevel-equipment"};
    if (!s.combatSpell)
        return {Preparation::Unprepared, "missing-combat-spells"};
    if (s.broken || !std::isfinite(s.durability) || s.durability < 20)
        return {Preparation::Repair, "equipment-durability"};
    if (s.resurrectionSickness)
        return {Preparation::Rest, "resurrection-sickness"};
    // Hysteresis: once recovery starts, don't leave it half recovered.
    if (!std::isfinite(s.health) || s.health < (recovering ? 90 : 75))
        return {Preparation::Rest, "low-health"};
    if (s.usesMana && (!std::isfinite(s.mana) || s.mana < (recovering ? 80 : 50)))
        return {Preparation::Rest, "low-mana"};
    return {Preparation::Ready, "ready"};
}
}
