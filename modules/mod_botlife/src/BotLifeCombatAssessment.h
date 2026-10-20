#ifndef _BOTLIFE_COMBAT_ASSESSMENT_H
#define _BOTLIFE_COMBAT_ASSESSMENT_H
class Player;
class Creature;
namespace BotLife
{
struct CombatAssessment
{
    bool allowed = false;
    char const* reason = "unknown";
    float seconds = 0, incomingDamage = 0;
    float mainhandDps = 0, offhandDps = 0, outgoingDps = 0, incomingDps = 0;
    char const* model = "physical-mainhand";
};
// Native autoattack fields already include offhand penalties. No speculative
// spell/rotation, crit, pet or healing bonus is added to this physical baseline.
CombatAssessment AssessRouteOpponent(Player& bot, Creature& enemy, bool recovering = true);
}
#endif
