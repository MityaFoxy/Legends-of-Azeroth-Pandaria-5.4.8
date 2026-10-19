#ifndef _BOTLIFE_READINESS_H
#define _BOTLIFE_READINESS_H

#include <cstdint>

class Player;

namespace BotLife
{
enum class Preparation { Ready, Rest, Repair, Unprepared };

// Values, not retained game pointers. Thresholds are deliberately conservative
// for the first solo quest runner; they are not a combat simulator.
struct Readiness
{
    uint32_t level = 1, armorPieces = 0, equipped = 0;
    float health = 0, mana = 0, durability = 100, averageItemLevel = 0;
    bool usesMana = false, weapon = false, offhand = true, coreArmor = false;
    bool combatSpell = false, resurrectionSickness = false, broken = false;
};

struct PreparationDecision
{
    Preparation state;
    char const* reason;
};

Readiness ReadCombatReadiness(Player& bot);
PreparationDecision EvaluateReadiness(Readiness const& state, bool recovering);
}
#endif
