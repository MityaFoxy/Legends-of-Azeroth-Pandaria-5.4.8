#include "BotLifeSafety.h"
#include "BotLifeCombatAssessment.h"
#include "CellImpl.h"
#include "Creature.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "MoveSpline.h"
#include "Map.h"
#include "Log.h"
#include "Player.h"
#include "Timer.h"
#include <algorithm>
#include <list>

namespace BotLife
{
namespace
{
SafetyPoint Position(Player const& bot) { return {bot.GetPositionX(), bot.GetPositionY(), bot.GetPositionZ()}; }
}

void QuestSafety::Refresh()
{
    if (_observed && GetMSTimeDiffToNow(_observedAt) < 500)
        return;
    _observed = true;
    _observedAt = getMSTime();
    _threats.clear();
    auto check = [this](Creature* npc)
    {
        return npc->IsAlive() && !npc->IsInEvadeMode() && _bot.IsWithinDistInMap(npc, 90) &&
            npc->GetCreatureType() != CREATURE_TYPE_CRITTER &&
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
    for (DeathArea const& area : _deaths)
    {
        float const start = SegmentDistanceSquared(area.position, from, from);
        float const closest = SegmentDistanceSquared(area.position, from, to);
        // Resurrection can start inside a danger area. Permit moving out, not
        // deeper in or crossing it again. Remember at most four recent deaths.
        if ((start >= 35*35 && closest < 35*35) || (start < 35*35 && closest < start - 0.01f))
            return Reject("recent-death-route", 0, area.position, 35, from, to);
    }
    LocalThreat const* blocker = nullptr;
    if (!SafeThreatSegment(_threats, from, to, _target, &blocker))
        return blocker ? Reject("hostile-on-route", blocker->spawn, blocker->position, blocker->radius, from, to)
            : Reject("invalid-segment", 0, from, 0, from, to);
    return true;
}

bool QuestSafety::Reject(char const* reason, uint32_t spawn, SafetyPoint hazard, float radius, SafetyPoint from, SafetyPoint to)
{
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

bool QuestSafety::CanApproach(QuestSpawn const& target)
{
    _check = "approach";
    _reason = "none"; _blocker = 0;
    Refresh();
    SafetyPoint goal{target.x, target.y, target.z};
    if (Creature* npc = _bot.GetMap()->GetCreatureBySpawnId(target.guid))
        if (npc->GetEntry() == target.entry && (npc->GetPhaseMask() & _bot.GetPhaseMask()))
        {
            goal = {npc->GetPositionX(), npc->GetPositionY(), npc->GetPositionZ()};
            if (_target == target.guid && _bot.IsValidAttackTarget(npc))
            {
                CombatAssessment const assessment = AssessRouteOpponent(_bot, *npc, false);
                if (!assessment.allowed)
                {
                    if (!_reported || GetMSTimeDiffToNow(_reportedAt) >= 5000)
                        TC_LOG_INFO("playerbots.botlife", "BotLife assessment guid={} spawn={} allowed=false reason={} model={} mainhand={} offhand={} outgoingDps={} incomingDps={} seconds={} incoming={}",
                            _bot.GetGUID().GetCounter(), target.guid, assessment.reason, assessment.model,
                            assessment.mainhandDps, assessment.offhandDps, assessment.outgoingDps, assessment.incomingDps,
                            assessment.seconds, assessment.incomingDamage);
                    return Reject(assessment.reason, target.guid, goal, 0, Position(_bot), goal);
                }
            }
        }
    // Local visibility is not proof that the rest of a long route is safe.
    // Recheck while moving and after each issued native spline.
    if (!SafeSegment(Position(_bot), goal))
        return false;
    for (DeathArea const& area : _deaths)
        if (SegmentDistanceSquared(area.position, goal, goal) < 35*35)
            return Reject("recent-death-target", 0, area.position, 35, Position(_bot), goal);
    for (LocalThreat const& threat : _threats)
    {
        if (_target && threat.spawn == _target)
            continue;
        // Include neutral attackable neighbours: assistance can pull them in.
        if (SegmentDistanceSquared(threat.position, goal, goal) <= 30*30)
            return Reject("target-neighbour", threat.spawn, threat.position, 30, Position(_bot), goal);
    }
    return true;
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
