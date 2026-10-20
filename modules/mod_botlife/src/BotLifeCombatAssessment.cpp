#include "BotLifeCombatAssessment.h"
#include "BotLifeReadiness.h"
#include "Creature.h"
#include "Player.h"
#include <cmath>
#include <algorithm>
#include <limits>

namespace BotLife
{
namespace
{
template<class Attacker, class Victim>
float PhysicalDps(Attacker& attacker, Victim& victim, WeaponAttackType attack = BASE_ATTACK)
{
    if (!attacker.CanUseAttackType(attack))
        return 0;
    uint32 const minimum = attack == OFF_ATTACK ? UNIT_FIELD_MIN_OFF_HAND_DAMAGE : UNIT_FIELD_MIN_DAMAGE;
    uint32 const maximum = attack == OFF_ATTACK ? UNIT_FIELD_MAX_OFF_HAND_DAMAGE : UNIT_FIELD_MAX_DAMAGE;
    float const damage = (attacker.GetFloatValue(minimum) + attacker.GetFloatValue(maximum)) * 0.5f;
    uint32 const period = attacker.GetAttackTime(attack);
    if (!std::isfinite(damage) || damage <= 0 || double(damage) >= std::numeric_limits<uint32>::max() || !period)
        return 0;
    return attacker.CalcArmorReducedDamage(&victim, uint32(damage), nullptr, attack) * (1000.0f / period);
}
}

CombatAssessment AssessRouteOpponent(Player& bot, Creature& enemy, bool recovering)
{
    Readiness const ready = ReadCombatReadiness(bot);
    if (EvaluateReadiness(ready, recovering).state != Preparation::Ready)
        return {false, "not-ready"}; // Recovery thresholds (90% HP / 80% mana), not minimum quest thresholds.
    // Level/rank are risk factors, not categorical exclusions. Native HP and
    // damage already reflect rank scaling; this adds uncertainty, not that scaling again.
    int const higherLevels = std::max(0, int(enemy.GetLevel()) - int(bot.GetLevel()));
    CombatAssessment result;
    result.mainhandDps = PhysicalDps(bot, enemy);
    // A shield, broken weapon, feral form or disarm must never become free DPS.
    // TOTAL_PCT's native offhand penalty is already in these damage fields.
    if (bot.CanDualWield() && bot.GetWeaponForAttack(OFF_ATTACK, true))
        result.offhandDps = PhysicalDps(bot, enemy, OFF_ATTACK);
    result.model = result.offhandDps > 0 ? "physical-dual-wield" : "physical-mainhand";
    float const outgoing = (result.mainhandDps + result.offhandDps) * 0.65f / (1.0f + 0.15f * higherLevels);
    float const incoming = PhysicalDps(enemy, bot) + (enemy.CanDualWield() ? PhysicalDps(enemy, bot, OFF_ATTACK) : 0);
    result.outgoingDps = outgoing;
    result.incomingDps = incoming;
    if (outgoing <= 0 || incoming <= 0 || !enemy.GetHealth() || !bot.GetMaxHealth())
    {
        result.reason = "unknown-damage";
        return result;
    }
    float const seconds = enemy.GetHealth() / outgoing;
    float const uncertainty = 2.0f * (1.0f + 0.10f * higherLevels) * (enemy.isElite() ? 1.5f : 1.0f);
    float const damage = incoming * (seconds + 3.0f) * uncertainty;
    result.seconds = seconds;
    result.incomingDamage = damage;
    if (!std::isfinite(seconds) || !std::isfinite(damage) || seconds > 45)
        result.reason = "long-fight";
    else if (damage > bot.GetHealth() - bot.GetMaxHealth() * 0.40f)
        result.reason = "insufficient-health-reserve";
    else
    {
        result.allowed = true;
        result.reason = "manageable";
    }
    return result;
}
}
