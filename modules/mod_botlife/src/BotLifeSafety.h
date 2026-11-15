#ifndef _BOTLIFE_SAFETY_H
#define _BOTLIFE_SAFETY_H

#include "BotLifeQuestPlan.h"
#include "BotLifeDefeats.h"
#include <deque>
#include <vector>
#include <optional>

class Player;

namespace BotLife
{
struct SafetyPoint { float x, y, z; };
struct LocalThreat
{
    uint32_t spawn;
    SafetyPoint position;
    float radius;
    bool aggressive;
};
float SegmentDistanceSquared(SafetyPoint p, SafetyPoint from, SafetyPoint to);
bool SafeThreatSegment(std::vector<LocalThreat> const& threats, SafetyPoint from, SafetyPoint to,
    uint32_t intendedTarget, LocalThreat const** blocker = nullptr,
    std::vector<uint32_t> const* intendedAssistants = nullptr);

// Map-thread, loaded-grid observations only; never force-loads distant grids.
class QuestSafety
{
public:
    explicit QuestSafety(Player& bot) : _bot(bot) { }
    bool CanApproach(QuestSpawn const& target, bool allowAssistance = false);
    std::optional<QuestSpawn> FindDetour(QuestSpawn const& target);
    bool DetourPending() const { return _detourPending; }
    bool RouteSafe();
    bool CanRest();
    void RememberDeath();
    void SetTarget(uint32_t spawn) { _target = spawn; }
    std::vector<uint32_t> const& Assistants() const { return _assistants; }
    char const* Reason() const { return _reason; }
    uint32_t Blocker() const { return _blocker; }
private:
    void Refresh();
    bool SafeSegment(SafetyPoint from, SafetyPoint to);
    bool SafeNavigationPath(SafetyPoint goal);
    bool SafeNavigationLeg(SafetyPoint from, SafetyPoint goal);
    bool Reject(char const* reason, uint32_t spawn, SafetyPoint hazard, float radius, SafetyPoint from, SafetyPoint to);
    Player& _bot;
    std::vector<LocalThreat> _threats;
    std::vector<uint32_t> _assistants;
    std::vector<DefeatArea> _defeatAreas;
    SafetyPoint _hazard{};
    float _hazardRadius = 0;
    struct FailedSpline
    {
        SafetyPoint origin, goal, hazard;
        float radius;
        uint32_t target, blocker, at;
    };
    std::optional<FailedSpline> _failedSpline;
    struct DeathArea { SafetyPoint position; uint32_t at; };
    std::deque<DeathArea> _deaths;
    uint32_t _observedAt = 0, _target = 0;
    bool _observed = false, _allowAssistance = false;
    uint32_t _pathQueries = 0;
    uint32_t _detourAt = 0;
    bool _detourChecked = false;
    bool _detourPending = false, _detourSearch = false;
    uint32_t _detourStage = 0, _detourTarget = 0;
    SafetyPoint _detourGoal{}, _detourOrigin{};
    SafetyPoint _approachGoal{};
    char const* _reason = "none";
    char const* _check = "none";
    uint32_t _blocker = 0, _reportedAt = 0;
    bool _reported = false;
};
}
#endif
