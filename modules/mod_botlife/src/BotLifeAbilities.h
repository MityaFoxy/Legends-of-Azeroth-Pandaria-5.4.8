#ifndef BOTLIFE_ABILITIES_H
#define BOTLIFE_ABILITIES_H

#include <cstdint>
#include <vector>

class PlayerbotAI;

namespace BotLife
{
// Diagnostic observations, NOT a CanCastSpell result or a damage estimate.
struct AbilityPower
{
    int32_t type = 0;
    uint32_t flat = 0;
    float percent = 0;
    uint32_t requiredAura = 0;
    bool auraPresent = false;
};

struct AbilityEffect
{
    uint32_t spell = 0, index = 0, effect = 0, aura = 0, trigger = 0;
    int32_t base = 0, dieSides = 0;
    float scaling = 0, coefficient = 0;
    bool area = false;
};

struct AbilitySnapshot
{
    char const* action = "";
    char const* condition = "";
    char const* trigger = "";
    uint32_t baseId = 0, resolvedId = 0, school = 0;
    bool baseKnown = false, active = false, disabled = false, passive = false;
    bool meleeStrategy = false, weaponReady = false, cooldownReady = false;
    bool actionRegistered = false, triggerRegistered = false;
    uint32_t cooldownMs = 0, baseCastMs = 0, baseRecoveryMs = 0, baseGcdMs = 0;
    std::vector<AbilityPower> powers;
    std::vector<AbilityEffect> effects;
};

std::vector<AbilitySnapshot> ReadEnhancementAbilities(PlayerbotAI& ai);
void LogEnhancementAbilities(PlayerbotAI& ai);
}
#endif
