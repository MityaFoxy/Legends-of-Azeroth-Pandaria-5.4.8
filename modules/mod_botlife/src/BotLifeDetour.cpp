#include "BotLifeSafety.h"
#include "Player.h"
#include "Timer.h"
#include "Log.h"
#include <algorithm>
#include <cmath>
#include <string_view>

namespace BotLife
{
std::optional<QuestSpawn> QuestSafety::FindDetour(QuestSpawn const& target)
{
    SafetyPoint const from{_bot.GetPositionX(), _bot.GetPositionY(), _bot.GetPositionZ()};
    SafetyPoint const requested{target.x, target.y, target.z};
    // Retain failed variants across update ticks. Replan only for a materially
    // different destination/origin, or after the exhausted-search cooldown.
    if (!_detourSearch || _detourTarget != target.guid ||
        SegmentDistanceSquared(requested, _detourGoal, _detourGoal) > 100 ||
        SegmentDistanceSquared(from, _detourOrigin, _detourOrigin) > 100 ||
        (_detourStage >= 5 && GetMSTimeDiffToNow(_detourAt) >= 60000))
    {
        _detourSearch = true;
        _detourTarget = target.guid;
        _detourGoal = requested;
        _detourOrigin = from;
        _detourStage = 0;
        _detourPending = true;
    }
    if (_detourStage >= 5)
    {
        _detourPending = false;
        return std::nullopt;
    }
    if (_detourChecked && GetMSTimeDiffToNow(_detourAt) < 5000)
        return std::nullopt;
    _detourChecked = true;
    _detourAt = getMSTime();
    uint32_t const intended = _target;
    // Revalidate this exact goal: never turn a target-neighbour, readiness or
    // repeated-defeat rejection into permission by walking around it.
    bool const preflightSafe = CanApproach(target);
    bool const failedActual = _failedSpline && _failedSpline->target == intended &&
        GetMSTimeDiffToNow(_failedSpline->at) < 30000 &&
        SegmentDistanceSquared(from, _failedSpline->origin, _failedSpline->origin) <= 100 &&
        SegmentDistanceSquared(_approachGoal, _failedSpline->goal, _failedSpline->goal) <= 100;
    if ((preflightSafe && !failedActual) || (!preflightSafe &&
        std::string_view(_reason) != "hostile-on-route" && std::string_view(_reason) != "repeated-defeat-area-route"))
    {
        _detourPending = false;
        return std::nullopt;
    }
    uint32_t const blocker = preflightSafe ? _failedSpline->blocker : _blocker;
    LocalThreat threat{blocker, preflightSafe ? _failedSpline->hazard : _hazard,
        preflightSafe ? _failedSpline->radius : _hazardRadius, true};
    if (preflightSafe)
    {
        auto current = std::find_if(_threats.begin(), _threats.end(), [blocker](auto const& t) { return t.spawn == blocker; });
        if (current == _threats.end())
        {
            _failedSpline.reset();
            _detourPending = false;
            return std::nullopt;
        }
        threat = *current;
    }
    SafetyPoint const goal = _approachGoal; // CanApproach resolved any live patrol/NPC.
    float const dx = goal.x - from.x, dy = goal.y - from.y;
    float const length = std::hypot(dx, dy);
    if (!std::isfinite(length) || length < 1 || !std::isfinite(threat.radius))
    {
        _detourPending = false;
        return std::nullopt;
    }
    uint32_t const stage = _detourStage++;
    _detourPending = _detourStage < 5;
    float const base = std::max(20.0f, threat.radius * 2.0f + 8.0f);
    float const offset = base * (stage == 1 ? 1.5f : stage >= 2 ? 2.0f : 1.0f);
    for (float side : {-1.0f, 1.0f})
    {
        SafetyPoint point{threat.position.x - side * dy / length * offset,
            threat.position.y + side * dx / length * offset, threat.position.z};
        if (stage == 3) // Angled alternatives, behind the blocking pack.
        {
            point.x -= dx / length * base;
            point.y -= dy / length * base;
        }
        if (stage == 4) // Bounded exploratory retreat; continuation is replanned there.
        {
            point = {from.x - dx / length * 20 - side * dy / length * 10,
                from.y - dy / length * 20 + side * dx / length * 10, from.z};
            if (SegmentDistanceSquared(threat.position, point, point) <=
                SegmentDistanceSquared(threat.position, from, from) + 100)
                continue;
        }
        _bot.UpdateAllowedPositionZ(point.x, point.y, point.z);
        // Local probes only; terrain projection is not itself proof of access.
        if (!std::isfinite(point.x + point.y + point.z) ||
            SegmentDistanceSquared(point, from, from) > 180 * 180 ||
            std::abs(point.z - from.z) > 20)
            continue;
        _target = 0; // The first leg must not pull even the intended quest mob.
        bool const first = SafeNavigationLeg(from, point);
        _target = intended;
        if (!first || (stage != 4 && !SafeNavigationLeg(point, goal)))
            continue;
        _detourPending = false;
        TC_LOG_INFO("playerbots.botlife", "BotLife detour guid={} event=planned blocker={} stage={} exploratory={} side={} waypoint=({},{},{}) goal=({},{},{})",
            _bot.GetGUID().GetCounter(), blocker, stage, stage == 4, side, point.x, point.y, point.z, goal.x, goal.y, goal.z);
        return QuestSpawn{0, 0, target.mapId, target.phaseMask, point.x, point.y, point.z};
    }
    _target = intended;
    TC_LOG_INFO("playerbots.botlife", "BotLife detour guid={} event=search-blocked blocker={} stage={} pending={} goal=({},{},{})",
        _bot.GetGUID().GetCounter(), blocker, stage, _detourPending, goal.x, goal.y, goal.z);
    return std::nullopt;
}
}
