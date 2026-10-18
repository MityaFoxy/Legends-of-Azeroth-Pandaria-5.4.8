#include "BotLifeMovement.h"

#include "LastMovementValue.h"
#include "Log.h"
#include "MotionMaster.h"
#include "MoveSpline.h"
#include "Player.h"
#include "Playerbots.h"
#include "WorldSession.h"

namespace BotLife
{
NativeTravelMovement::NativeTravelMovement(PlayerbotAI& ai) : MovementAction(&ai, "botlife travel") { }

bool NativeTravelMovement::IsValid(TravelTarget const& target) const
{
    return bot && bot->IsInWorld() && !bot->IsDuringRemoveFromWorld() && bot->IsAlive() &&
        !bot->IsBeingTeleported() && bot->GetSession() && !bot->GetSession()->isLogingOut() &&
        !botAI->IsRealPlayer() && !botAI->HasRealPlayerMaster() &&
        !bot->InBattleground() && !bot->InArena() && !bot->IsInFlight() &&
        !bot->GetTransport() && !bot->GetVehicle() && !bot->IsFlying() &&
        !bot->HasAuraType(SPELL_AURA_MOD_INCREASE_MOUNTED_FLIGHT_SPEED) &&
        bot->GetMapId() == target.mapId && bot->GetInstanceId() == target.instanceId &&
        bot->GetPhaseMask() == target.phaseMask && Trinity::IsValidMapCoord(target.x, target.y, target.z);
}

bool NativeTravelMovement::IsBlocked()
{
    return bot->IsInCombat() || bot->HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED | UNIT_STATE_LOST_CONTROL) ||
        bot->IsNonMeleeSpellCasted(false) || !IsMovingAllowed();
}

bool NativeTravelMovement::HasArrived(TravelTarget const& target) const
{
    return IsValid(target) && bot->GetExactDist(target.x, target.y, target.z) <= target.tolerance &&
        bot->IsWithinLOS(target.x, target.y, target.z);
}

TravelMoveResult NativeTravelMovement::Move(TravelTarget const& target)
{
    if (!IsValid(target) || IsBlocked() || _owner)
        return TravelMoveResult::Blocked;
    // Don't steal chase/follow, scripted points or untracked splines. Base AI
    // keeps running while the activity waits within its own bounded time budget.
    if (bot->GetMotionMaster()->GetCurrentMovementGeneratorType() != IDLE_MOTION_TYPE ||
        !bot->movespline->Finalized())
        return TravelMoveResult::Blocked;
    bool const moved = MoveTo(target.mapId, target.x, target.y, target.z,
        false, false, true, false, MovementPriority::MOVEMENT_NORMAL);
    if (!moved)
    {
        if (lastMoveFailure == MoveFailure::RecoveryExhausted)
            return TravelMoveResult::RecoveryExhausted;
        if (lastMoveFailure == MoveFailure::Route)
        {
            TC_LOG_DEBUG("playerbots.botlife", "BotLife bot={} phase=travel event=no-route target=({},{},{})",
                bot->GetGUID().GetCounter(), target.x, target.y, target.z);
            return TravelMoveResult::NoRoute;
        }
        return TravelMoveResult::Blocked;
    }
    GroundMovementState& state = AI_VALUE(LastMovement&, "last movement").groundMovement;
    _owner = std::make_shared<uint8_t>(0);
    state.owner = _owner;
    _target = target;
    _endX = state.endpoint.x;
    _endY = state.endpoint.y;
    _endZ = state.endpoint.z;
    TC_LOG_DEBUG("playerbots.botlife", "BotLife bot={} phase=travel event=issued distance={} spline={} target=({},{},{})",
        bot->GetGUID().GetCounter(), bot->GetExactDist(target.x, target.y, target.z), state.splineId,
        target.x, target.y, target.z);
    return TravelMoveResult::Started;
}

bool NativeTravelMovement::OwnsMovement() const
{
    if (!_owner || !bot || !bot->IsInWorld() || bot->IsDuringRemoveFromWorld() ||
        bot->GetMapId() != _target.mapId || bot->GetInstanceId() != _target.instanceId ||
        bot->GetPhaseMask() != _target.phaseMask)
        return false;
    GroundMovementState const& state = AI_VALUE(LastMovement&, "last movement").groundMovement;
    return state.owner == _owner && state.tracked && bot->GetMotionMaster()->top() == state.generator &&
        bot->GetMotionMaster()->GetCurrentMovementGeneratorType() == POINT_MOTION_TYPE &&
        bot->movespline->GetId() == state.splineId;
}

TravelMotion NativeTravelMovement::Poll() const
{
    if (!_owner)
        return TravelMotion::Lost;
    GroundMovementState const& state = AI_VALUE(LastMovement&, "last movement").groundMovement;
    if (state.owner == _owner && state.exhausted)
        return TravelMotion::RecoveryExhausted;
    if (OwnsMovement())
    {
        if (bot->movespline->Finalized())
            return TravelMotion::Finished;
        return state.recovering ? TravelMotion::Recovering : TravelMotion::Moving;
    }
    // MotionMaster may remove a completed generator before the next action tick.
    // Recovery can also have changed the endpoint since the initial dispatch.
    float const x = state.owner == _owner ? state.endpoint.x : _endX;
    float const y = state.owner == _owner ? state.endpoint.y : _endY;
    float const z = state.owner == _owner ? state.endpoint.z : _endZ;
    if ((!state.owner || state.owner == _owner) &&
        bot->GetMotionMaster()->GetCurrentMovementGeneratorType() == IDLE_MOTION_TYPE &&
        bot->movespline->Finalized() && bot->GetExactDist(x, y, z) <= 1.0f)
        return TravelMotion::Finished;
    return TravelMotion::Lost;
}

void NativeTravelMovement::Release()
{
    if (!_owner)
        return;
    LastMovement& last = AI_VALUE(LastMovement&, "last movement");
    if (OwnsMovement())
    {
        bot->StopMoving();
        bot->GetMotionMaster()->MovementExpired(); // Only the matched top generator.
        last.clear();
    }
    else if (last.groundMovement.owner == _owner)
    {
        // Drop only our observer, preserving newer motion and LastMovement.
        // Exhausted-route protection remains until normal navigation resets it.
        last.groundMovement.owner.reset();
        last.groundMovement.active = false;
    }
    _owner.reset();
}
}
