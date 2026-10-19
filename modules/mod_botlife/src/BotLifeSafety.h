#ifndef _BOTLIFE_SAFETY_H
#define _BOTLIFE_SAFETY_H

#include "BotLifeQuestPlan.h"
#include <deque>
#include <vector>

class Player;

namespace BotLife
{
struct SafetyPoint { float x, y, z; };
struct LocalThreat
{
    uint32_t spawn;
    SafetyPoint position;
    float radius;
    bool aggressive, strong;
};
float SegmentDistanceSquared(SafetyPoint p, SafetyPoint from, SafetyPoint to);
bool SafeThreatSegment(std::vector<LocalThreat> const& threats, SafetyPoint from, SafetyPoint to,
    uint32_t intendedTarget, LocalThreat const** blocker = nullptr);

// Map-thread, loaded-grid observations only; never force-loads distant grids.
class QuestSafety
{
public:
    explicit QuestSafety(Player& bot) : _bot(bot) { }
    bool CanApproach(QuestSpawn const& target);
    bool RouteSafe();
    bool CanRest();
    void RememberDeath();
    void SetTarget(uint32_t spawn) { _target = spawn; }
    char const* Reason() const { return _reason; }
    uint32_t Blocker() const { return _blocker; }
private:
    void Refresh();
    bool SafeSegment(SafetyPoint from, SafetyPoint to);
    bool Reject(char const* reason, uint32_t spawn, SafetyPoint hazard, float radius, SafetyPoint from, SafetyPoint to);
    Player& _bot;
    std::vector<LocalThreat> _threats;
    struct DeathArea { SafetyPoint position; uint32_t at; };
    std::deque<DeathArea> _deaths;
    uint32_t _observedAt = 0, _target = 0;
    bool _observed = false;
    char const* _reason = "none";
    char const* _check = "none";
    uint32_t _blocker = 0, _reportedAt = 0;
    bool _reported = false;
};
}
#endif
