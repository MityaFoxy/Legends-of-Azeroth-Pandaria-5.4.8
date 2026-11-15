#include "BotLifeRouteClearance.h"
#include "BotLifeQuestHunt.h"
#include "Creature.h"
#include "Log.h"
#include "Map.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "Timer.h"
#include <cmath>

namespace BotLife
{
RouteClearance::RouteClearance(PlayerbotAI& ai, QuestHunt& hunt)
    : _bot(*ai.GetBot()), _hunt(hunt), _movement(ai, [&hunt] { return hunt.Safety().RouteSafe(); }), _travel(_movement) { }

bool RouteClearance::Start(uint32_t blocker)
{
    if (Active() || !blocker || _hunt.IsFighting())
        return false;
    if (_checked && GetMSTimeDiffToNow(_checkedAt) < 5000)
        return false; // Bound repeated rejected assessments, including different blockers.
    _checked = true;
    _checkedAt = getMSTime();
    if (_attempted.count(blocker))
    {
        TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=reject spawn={} reason=already-attempted attempts={}",
            _bot.GetGUID().GetCounter(), blocker, _attempted.size());
        return false;
    }
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
    CombatAdmission const admission = _hunt.CanAttemptGroup(*enemy, true);
    TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=assess spawn={} level={} elite={} allowed={} reason={} assistants={}",
        _bot.GetGUID().GetCounter(), blocker, enemy->GetLevel(), enemy->isElite(), admission.allowed, admission.reason,
        _hunt.AssistanceCount());
    if (!admission.allowed)
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
    _engaged = _combatStarted = false;
    _travel.Start({_bot.GetMapId(), _bot.GetInstanceId(), _bot.GetPhaseMask(), approach.x, approach.y, approach.z, 1.0f});
    return true;
}

ClearanceResult RouteClearance::Update(uint32_t elapsed)
{
    if (!Active())
        return ClearanceResult::Failed;
    Creature* enemy = _bot.GetMap()->GetCreatureBySpawnId(_target->guid);
    if (!enemy || enemy->GetEntry() != _target->entry || !(enemy->GetPhaseMask() & _bot.GetPhaseMask()))
        return Finish(false, "target-unavailable");
    if (_engaged && (_bot.IsInCombat() || enemy->IsInCombat()))
        _combatStarted = true;
    if (_engaged && !_combatStarted && GetMSTimeDiffToNow(_engagedAt) >= 30000 &&
        _hunt.CancelUnstartedAttack(*_target))
    {
        _attempted.erase(_target->guid);
        return Finish(false, "attack-not-started-retryable");
    }
    if (_hunt.IsFighting())
        return ClearanceResult::Running; // Never retarget or move through another pack during combat.
    if (!enemy->IsAlive())
        return Finish(_engaged, _engaged ? "cleared" : "target-gone");
    if (_engaged)
    {
        if (!_combatStarted)
            return ClearanceResult::Running;
        if (enemy->IsInEvadeMode())
        {
            // The native pull was real, but the creature explicitly reset.
            // Permit a fresh assessment only after Available() observes that it
            // has completed the return home; do not repull an ordinary survivor.
            _attempted.erase(_target->guid);
            return Finish(false, "target-evaded-retryable");
        }
        return Finish(false, "combat-ended-target-alive");
    }
    auto current = _hunt.RouteObstacle(_target->guid, _staging);
    if (!current || !_hunt.CanAttemptGroup(*enemy, true).allowed)
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
    if (!_staging && _hunt.CanEngage(*current, true))
    {
        _travel.Cancel();
        if (!_hunt.Engage(*current, true))
            return Finish(false, "attack-refused");
        _engaged = true;
        _attempted.insert(current->guid); // Only a real native combat handoff consumes this spawn.
        _engagedAt = getMSTime();
        TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=engage spawn={} entry={} assistants={}",
            _bot.GetGUID().GetCounter(), current->guid, current->entry, _hunt.AssistanceCount());
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
    _travel.Cancel();
    _target.reset();
    _engaged = _combatStarted = _staging = false;
}
ClearanceResult RouteClearance::Finish(bool success, char const* reason)
{
    TC_LOG_INFO("playerbots.botlife", "BotLife clearance guid={} event=finish spawn={} reason={}",
        _bot.GetGUID().GetCounter(), _target->guid, reason);
    Cancel();
    return success ? ClearanceResult::Finished : ClearanceResult::Failed;
}
}
