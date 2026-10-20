#include "BotLifeRouteClearance.h"
#include "BotLifeCombatAssessment.h"
#include "BotLifeQuestHunt.h"
#include "Creature.h"
#include "Log.h"
#include "Map.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "Timer.h"
#include <algorithm>
#include <cmath>

namespace BotLife
{
RouteClearance::RouteClearance(PlayerbotAI& ai, QuestHunt& hunt)
    : _bot(*ai.GetBot()), _hunt(hunt), _movement(ai, [&hunt] { return hunt.Safety().RouteSafe(); }), _travel(_movement) { }

bool RouteClearance::Start(uint32_t blocker)
{
    if (Active() || !blocker || _attempted.size() >= 4 || _attempted.count(blocker) || _spentMs >= 180000 || _hunt.IsFighting())
        return false;
    if (_checked && GetMSTimeDiffToNow(_checkedAt) < 5000)
        return false; // Bound repeated rejected assessments, including different blockers.
    _checked = true;
    _checkedAt = getMSTime();
    auto target = _hunt.RouteObstacle(blocker, true);
    if (!target)
    {
        TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=reject spawn={} reason=unavailable-or-unsafe detail={} obstruction={}",
            _bot.GetGUID().GetCounter(), blocker, _hunt.Safety().Reason(), _hunt.Safety().Blocker());
        return false;
    }
    Creature* enemy = _bot.GetMap()->GetCreatureBySpawnId(blocker);
    if (!enemy)
        return false;
    CombatAssessment const assessment = AssessRouteOpponent(_bot, *enemy);
    TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=assess spawn={} level={} elite={} hp={} allowed={} reason={} seconds={} incoming={} model={} mainhand={} offhand={} outgoingDps={} incomingDps={}",
        _bot.GetGUID().GetCounter(), blocker, enemy->GetLevel(), enemy->isElite(), enemy->GetHealth(),
        assessment.allowed, assessment.reason, assessment.seconds, assessment.incomingDamage,
        assessment.model, assessment.mainhandDps, assessment.offhandDps, assessment.outgoingDps, assessment.incomingDps);
    if (!assessment.allowed)
        return false;
    _staging = !_bot.IsWithinDistInMap(enemy, 60);
    QuestSpawn approach = *target;
    if (_staging)
    {
        // Bridge the observation (90m) / pull-planning (60m) gap with a
        // noncombat waypoint 50m from the blocker, never a distant attack.
        float const dx = target->x - _bot.GetPositionX(), dy = target->y - _bot.GetPositionY(),
            dz = target->z - _bot.GetPositionZ();
        float const distance = std::sqrt(dx*dx + dy*dy + dz*dz);
        if (!std::isfinite(distance) || distance <= 50)
            return false;
        float const fraction = (distance - 50) / distance;
        approach = {0, 0, target->mapId, target->phaseMask, _bot.GetPositionX() + dx*fraction,
            _bot.GetPositionY() + dy*fraction, _bot.GetPositionZ() + dz*fraction};
        _hunt.Safety().SetTarget(0); // No aggro exemption, including the blocker.
        if (!_hunt.Safety().CanApproach(approach))
            return false;
        _stagingPoint = approach;
        TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=stage-approach spawn={} distance={} to=({},{},{})",
            _bot.GetGUID().GetCounter(), blocker, distance, approach.x, approach.y, approach.z);
    }
    _target = target;
    _attempted.insert(blocker);
    _startedAt = getMSTime();
    _engaged = false;
    _travel.Start({_bot.GetMapId(), _bot.GetInstanceId(), _bot.GetPhaseMask(), approach.x, approach.y, approach.z, 1.0f});
    return true;
}

ClearanceResult RouteClearance::Update(uint32_t elapsed)
{
    if (!Active())
        return ClearanceResult::Failed;
    if (_hunt.IsFighting())
        return ClearanceResult::Running; // Never retarget or move through another pack during combat.
    Creature* enemy = _bot.GetMap()->GetCreatureBySpawnId(_target->guid);
    if (!enemy || enemy->GetEntry() != _target->entry || !(enemy->GetPhaseMask() & _bot.GetPhaseMask()))
        return Finish(false, "target-unavailable");
    if (!enemy->IsAlive())
        return Finish(_engaged, _engaged ? "cleared" : "target-gone");
    if (GetMSTimeDiffToNow(_startedAt) >= 60000 || _spentMs + GetMSTimeDiffToNow(_startedAt) >= 180000)
        return Finish(false, "clearance-timeout");
    if (_engaged)
        return GetMSTimeDiffToNow(_engagedAt) < 5000 ? ClearanceResult::Running
            : Finish(false, "combat-ended-target-alive"); // Allow native attack acquisition; never repull a survivor.
    auto current = _hunt.RouteObstacle(_target->guid, _staging);
    if (!current || !AssessRouteOpponent(_bot, *enemy).allowed)
        return Finish(false, "risk-changed");
    if (_staging)
    {
        // Reassess at close range before exempting one opponent from geometry.
        // Patrolling targets and newly visible neighbours can invalidate the approach.
        if (_bot.IsWithinDistInMap(enemy, 60))
        {
            _travel.Cancel();
            _staging = false;
            _travel.Start({_bot.GetMapId(), _bot.GetInstanceId(), _bot.GetPhaseMask(),
                current->x, current->y, current->z, 1.0f});
            TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=stage-ready spawn={}",
                _bot.GetGUID().GetCounter(), current->guid);
        }
        else
        {
            _hunt.Safety().SetTarget(0);
            if (!_hunt.Safety().CanApproach(_stagingPoint))
                return Finish(false, "unsafe-staging");
        }
    }
    if (!_staging && _hunt.CanEngage(*current))
    {
        _travel.Cancel();
        if (!_hunt.Engage(*current))
            return Finish(false, "attack-refused");
        _engaged = true;
        _engagedAt = getMSTime();
        TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=engage spawn={} entry={}",
            _bot.GetGUID().GetCounter(), current->guid, current->entry);
        return ClearanceResult::Running;
    }
    if (_travel.GetStatus() == TravelStatus::Paused && !_travel.Resume())
        return Finish(false, "resume-refused");
    if (_travel.ControlsMovement() && !_hunt.Safety().RouteSafe())
        return Finish(false, "unsafe-route");
    auto const status = _travel.Update(elapsed);
    if (status == TravelStatus::Failed || status == TravelStatus::Cancelled || status == TravelStatus::Arrived)
        return Finish(false, "approach-failed");
    return ClearanceResult::Running;
}

void RouteClearance::Pause() { _travel.Pause(); }
void RouteClearance::Cancel()
{
    if (Active())
        _spentMs += std::min(GetMSTimeDiffToNow(_startedAt), 180000u - _spentMs);
    _travel.Cancel();
    _target.reset();
    _engaged = _staging = false;
}
ClearanceResult RouteClearance::Finish(bool success, char const* reason)
{
    TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=finish spawn={} reason={}",
        _bot.GetGUID().GetCounter(), _target->guid, reason);
    Cancel();
    return success ? ClearanceResult::Finished : ClearanceResult::Failed;
}
}
