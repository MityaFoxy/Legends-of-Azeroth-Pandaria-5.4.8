#include "BotLifeSafety.h"
#include "BotLifeDefeats.h"
#include "CellImpl.h"
#include "Creature.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "MoveSpline.h"
#include "Map.h"
#include "Log.h"
#include "Player.h"
#include "PathGenerator.h"
#include "Timer.h"
#include "World.h"
#include <algorithm>
#include <list>
#include <string_view>

namespace BotLife
{
namespace
{
SafetyPoint Position(Player const& bot) { return {bot.GetPositionX(), bot.GetPositionY(), bot.GetPositionZ()}; }
SafetyPoint AreaSpace(SafetyPoint point) { point.z *= AreaDefeatHistory::Radius / AreaDefeatHistory::Height; return point; }
}

void QuestSafety::Refresh()
{
    if (_observed && GetMSTimeDiffToNow(_observedAt) < 500)
        return;
    _observed = true;
    _observedAt = getMSTime();
    _pathQueries = 0;
    _defeatAreas = GetDefeatAreas(_bot);
    _threats.clear();
    auto check = [this](Creature* npc)
    {
        return npc->IsAlive() && !npc->IsInEvadeMode() && _bot.IsWithinDistInMap(npc, 90) &&
            npc->GetCreatureType() != CREATURE_TYPE_CRITTER &&
            !npc->IsCivilian() && !npc->HasReactState(REACT_PASSIVE) &&
            _bot.IsValidAttackTarget(npc) && _bot.CanSeeOrDetect(npc);
    };
    std::list<Creature*> creatures;
    Trinity::CreatureListSearcher<decltype(check)> searcher(&_bot, creatures, check);
    Cell::VisitAllObjects(&_bot, searcher, 90);
    for (Creature* npc : creatures)
    {
        // GetAggroRange is pet-only in this core (ordinary creatures return 0).
        // Match CanStartAttack/IsWithinDistInMap's centre-to-centre threshold,
        // then keep our extra patrol/reaction margin.
        float const attackRadius = npc->GetAttackDistance(&_bot) + npc->m_CombatDistance +
            npc->GetObjectSize() + _bot.GetObjectSize();
        _threats.push_back({npc->GetSpawnId(), {npc->GetPositionX(), npc->GetPositionY(), npc->GetPositionZ()},
            std::max(8.0f, attackRadius + 8.0f), npc->IsHostileTo(&_bot)});
    }
    while (!_deaths.empty() && GetMSTimeDiffToNow(_deaths.front().at) >= 300000)
        _deaths.pop_front();
}

bool QuestSafety::SafeSegment(SafetyPoint from, SafetyPoint to)
{
    for (auto const& area : _defeatAreas)
    {
        SafetyPoint const centre{area.origin.x, area.origin.y, area.origin.z};
        float const start = SegmentDistanceSquared(AreaSpace(centre), AreaSpace(from), AreaSpace(from));
        float const closest = SegmentDistanceSquared(AreaSpace(centre), AreaSpace(from), AreaSpace(to));
        if ((start >= 100 && closest < 100) || (start < 100 && closest < start - 0.01f))
            return Reject("repeated-defeat-area-route", 0, centre, 10, from, to);
    }
    for (DeathArea const& area : _deaths)
    {
        float const start = SegmentDistanceSquared(AreaSpace(area.position), AreaSpace(from), AreaSpace(from));
        float const closest = SegmentDistanceSquared(AreaSpace(area.position), AreaSpace(from), AreaSpace(to));
        // Resurrection can start inside a danger area. Permit moving out, not
        // deeper in or crossing it again. Remember at most four recent deaths.
        if ((start >= 100 && closest < 100) || (start < 100 && closest < start - 0.01f))
            return Reject("recent-death-route", 0, area.position, 10, from, to);
    }
    LocalThreat const* blocker = nullptr;
    if (!SafeThreatSegment(_threats, from, to, _target, &blocker,
        _allowAssistance ? &_assistants : nullptr))
        return blocker ? Reject("hostile-on-route", blocker->spawn, blocker->position, blocker->radius, from, to)
            : Reject("invalid-segment", 0, from, 0, from, to);
    return true;
}

bool QuestSafety::Reject(char const* reason, uint32_t spawn, SafetyPoint hazard, float radius, SafetyPoint from, SafetyPoint to)
{
    _hazard = hazard;
    _hazardRadius = radius;
    if (std::string_view(_check) == "spline" && std::string_view(reason) == "hostile-on-route")
        _failedSpline = FailedSpline{Position(_bot), _approachGoal, hazard, radius, _target, spawn, getMSTime()};
    _reason = reason;
    _blocker = spawn;
    // Choose may inspect many spawns on every tick. Keep the most recent
    // rejection available to callers, but bound diagnostic volume per bot.
    if (!_reported || GetMSTimeDiffToNow(_reportedAt) >= 5000)
    {
        _reported = true;
        _reportedAt = getMSTime();
        TC_LOG_INFO("playerbots.botlife", "BotLife safety guid={} check={} target={} reason={} blocker={} radius={} hazard=({},{},{}) from=({},{},{}) to=({},{},{})",
            _bot.GetGUID().GetCounter(), _check, _target, reason, spawn, radius,
            hazard.x, hazard.y, hazard.z, from.x, from.y, from.z, to.x, to.y, to.z);
    }
    return false;
}

bool QuestSafety::SafeNavigationPath(SafetyPoint goal)
{
    // Bound expensive probes even when Choose inspects many candidates. This
    // is only preflight, not a retained path or permission to skip spline checks.
    if (_pathQueries >= 2)
        return false;
    ++_pathQueries;
    return SafeNavigationLeg(Position(_bot), goal);
}

bool QuestSafety::SafeNavigationLeg(SafetyPoint from, SafetyPoint goal)
{
    PathGenerator path(&_bot, 4096);
    path.SetUseWaterShortcut(false);
    G3D::Vector3 const origin(from.x, from.y, from.z);
    if (!path.CalculatePath(goal.x, goal.y, goal.z, false, false, false, &origin) || !path.HasNavigationData() ||
        path.GetPathType() != PATHFIND_NORMAL)
        return false; // No partial corridor, shortcut, missing mesh or far endpoint.
    auto const& points = path.GetPath();
    if (points.size() < 2 || points.size() > 256)
        return false;
    SafetyPoint const first{points.front().x, points.front().y, points.front().z};
    SafetyPoint const last{points.back().x, points.back().y, points.back().z};
    if (!(SegmentDistanceSquared(first, from, from) <= 1.0f) ||
        !(SegmentDistanceSquared(last, goal, goal) <= 1.0f))
        return false;
    for (auto const& point : points)
    {
        SafetyPoint const to{point.x, point.y, point.z};
        if (!SafeSegment(from, to))
            return false;
        from = to;
    }
    if (!SafeSegment(from, goal))
        return false;
    _reason = "none";
    _blocker = 0;
    return true;
}

bool QuestSafety::CanApproach(QuestSpawn const& target, bool allowAssistance)
{
    _check = "approach";
    _reason = "none"; _blocker = 0;
    _allowAssistance = allowAssistance;
    _assistants.clear();
    Refresh();
    SafetyPoint goal{target.x, target.y, target.z};
    Creature* intended = nullptr;
    if (Creature* npc = _bot.GetMap()->GetCreatureBySpawnId(target.guid))
        if (npc->GetEntry() == target.entry && (npc->GetPhaseMask() & _bot.GetPhaseMask()))
        {
            intended = npc;
            goal = {npc->GetPositionX(), npc->GetPositionY(), npc->GetPositionZ()};
            if (_target == target.guid && _bot.IsValidAttackTarget(npc))
            {
                if (AvoidDefeatedOpponent(_bot, *npc))
                    return Reject("repeated-defeat", target.guid, goal, 0, Position(_bot), goal);
            }
        }
    _approachGoal = goal;
    if (_target)
        for (auto const& area : _defeatAreas)
        {
            SafetyPoint const centre{area.origin.x, area.origin.y, area.origin.z};
            if (SegmentDistanceSquared(AreaSpace(centre), AreaSpace(goal), AreaSpace(goal)) < 100)
                return Reject("repeated-defeat-area-target", 0, centre, 10, Position(_bot), goal);
        }
    for (DeathArea const& area : _deaths)
        if (_target && SegmentDistanceSquared(AreaSpace(area.position), AreaSpace(goal), AreaSpace(goal)) < 100)
            return Reject("recent-death-target", 0, area.position, 10, Position(_bot), goal);
    // Native assistance is narrower than a generic proximity veto: only an
    // aggressive same-faction creature within the configured assistance
    // radius and line of sight can join the intended target. Ordinary aggro
    // from every other hostile remains covered by SafeSegment below.
    float const assistanceRadius = sWorld->getFloatConfig(CONFIG_CREATURE_FAMILY_ASSISTANCE_RADIUS);
    if (_target && intended && assistanceRadius > 0)
        for (LocalThreat const& threat : _threats)
        {
            if (threat.spawn == _target)
                continue;
            Creature* assistant = _bot.GetMap()->GetCreatureBySpawnId(threat.spawn);
            if (assistant && assistant->CanAssistTo(intended, &_bot) &&
                intended->IsWithinDistInMap(assistant, assistanceRadius) && intended->IsWithinLOSInMap(assistant))
            {
                if (!allowAssistance)
                    return Reject("target-assistance", threat.spawn, threat.position, assistanceRadius, Position(_bot), goal);
                _assistants.push_back(threat.spawn);
            }
        }
    // A dangerous chord does not prove a dangerous navigable corridor. Keep
    // target checks above independent and recheck the actual dispatched spline.
    return SafeSegment(Position(_bot), goal) || SafeNavigationPath(goal);
}

bool QuestSafety::RouteSafe()
{
    _check = "spline";
    _reason = "none"; _blocker = 0;
    Refresh();
    if (_bot.movespline->Finalized())
        return true;
    // Inspect the remaining native polyline, including detours, not a ray to
    // the quest destination. Exclude already-traversed and spline control points.
    auto const& spline = _bot.movespline->_Spline();
    auto const& path = spline.getPoints();
    int const next = _bot.movespline->_currentSplineIdx() + 1;
    if (next < 0 || spline.last() >= int(path.size()))
        return Reject("invalid-spline", 0, Position(_bot), 0, Position(_bot), Position(_bot));
    SafetyPoint from = Position(_bot);
    for (int i = next; i <= spline.last(); ++i)
    {
        SafetyPoint const to{path[i].x, path[i].y, path[i].z};
        if (!SafeSegment(from, to))
            return false;
        from = to;
    }
    return true;
}

bool QuestSafety::CanRest()
{
    _check = "rest";
    _reason = "none"; _blocker = 0;
    Refresh();
    SafetyPoint const here = Position(_bot);
    LocalThreat const* blocker = nullptr;
    if (!SafeThreatSegment(_threats, here, here, 0, &blocker))
        return blocker ? Reject("unsafe-rest", blocker->spawn, blocker->position, blocker->radius, here, here)
            : Reject("invalid-segment", 0, here, 0, here, here);
    return true;
}

void QuestSafety::RememberDeath()
{
    if (_deaths.size() == 4)
        _deaths.pop_front();
    _deaths.push_back({Position(_bot), getMSTime()});
    _observed = false;
    _target = 0;
}
}
