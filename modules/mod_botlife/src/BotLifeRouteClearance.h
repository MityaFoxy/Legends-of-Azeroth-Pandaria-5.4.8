#ifndef _BOTLIFE_ROUTE_CLEARANCE_H
#define _BOTLIFE_ROUTE_CLEARANCE_H
#include "BotLifeMovement.h"
#include "BotLifeQuestPlan.h"
#include <optional>
#include <unordered_set>
class Player;
class PlayerbotAI;
namespace BotLife
{
class QuestHunt;
enum class ClearanceResult { Running, Finished, Failed };

// One temporary combat target. The caller retains the actual quest destination.
class RouteClearance
{
public:
    RouteClearance(PlayerbotAI& ai, QuestHunt& hunt);
    bool Start(uint32_t blocker);
    ClearanceResult Update(uint32_t elapsed);
    void Pause();
    void Cancel();
    bool Active() const { return _target.has_value(); }
    bool HoldsNonCombat() const { return Active() && !_engaged; }
    bool ControlsMovement() const { return _travel.ControlsMovement(); }
private:
    ClearanceResult Finish(bool success, char const* reason);
    Player& _bot;
    QuestHunt& _hunt;
    NativeTravelMovement _movement;
    TravelExecutor _travel;
    std::optional<QuestSpawn> _target;
    QuestSpawn _stagingPoint{};
    std::unordered_set<uint32_t> _attempted;
    uint32_t _startedAt = 0, _engagedAt = 0, _spentMs = 0, _checkedAt = 0;
    bool _engaged = false, _checked = false, _staging = false;
};
}
#endif
