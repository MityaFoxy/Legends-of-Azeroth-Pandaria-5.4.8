/*
 * This file is part of the Legends of Azeroth Pandaria Project. See THANKS file for Copyright information
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
 * details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program. If not, see <http://www.gnu.org/licenses/>.
 */

#include "ChaseMovementGenerator.h"
#include "Creature.h"
#include "CreatureAI.h"
#include "G3DPosition.hpp"
#include "Log.h"
#include "Map.h"
#include "MotionMaster.h"
#include "MoveSpline.h"
#include "MoveSplineInit.h"
#include "PathGenerator.h"
#include "Unit.h"
#include "Util.h"

static bool HasLostTarget(Unit* owner, Unit* target)
{
    return owner->GetVictim() != target;
}

static bool IsMutualChase(Unit* owner, Unit* target)
{
    if (target->GetMotionMaster()->GetCurrentMovementGeneratorType() != CHASE_MOTION_TYPE)
        return false;

    if (ChaseMovementGenerator* movement = dynamic_cast<ChaseMovementGenerator*>(target->GetMotionMaster()->GetCurrentMovementGenerator()))
        return movement->GetTarget() == owner;

    return false;
}

static bool PositionOkay(Unit* owner, Unit* target, Optional<float> minDistance, Optional<float> maxDistance, Optional<ChaseAngle> angle)
{
    float const distSq = owner->GetExactDistSq(target);
    if (minDistance && distSq < (*minDistance) * (*minDistance))
        return false;
    if (maxDistance && distSq > (*maxDistance) * (*maxDistance))
        return false;
    if (angle && !angle->IsAngleOkay(target->GetRelativeAngle(owner)))
        return false;
    if (!owner->IsWithinLOSInMap(target))
        return false;
    return true;
}

static void DoMovementInform(Unit* owner, Unit* target)
{
    if (owner->GetTypeId() != TYPEID_UNIT)
        return;

    if (CreatureAI* AI = owner->ToCreature()->AI())
        AI->MovementInform(CHASE_MOTION_TYPE, target->GetGUID().GetCounter());
}

static bool GetMeleeChaseLanePoint(Unit* owner, Unit* target, Position& point)
{
    // Distinct points on the contact circle still share the same running line
    // at range. Use a short, bounded lateral waypoint until close to melee.
    if (owner->GetExactDist2d(target) <= owner->GetMeleeRange(target) + 3.0f)
        return false;

    Unit const* leader = owner;
    uint32 rank = 0, count = 0;
    float radius = owner->GetCollisionRadius();
    for (Unit const* other : target->getAttackers())
    {
        if (!other || !other->IsAlive() || !other->ToCreature() || other->IsPet() ||
            other->CanFly() || other->IsInWater() || !other->CanFreeMove())
            continue;
        auto const* chase = dynamic_cast<ChaseMovementGenerator const*>(other->GetMotionMaster()->GetCurrentMovementGenerator());
        if (!chase || chase->GetTarget() != target || !chase->IsDefaultMeleeChase())
            continue;

        ++count;
        radius = std::max(radius, other->GetCollisionRadius());
        if (other->GetGUID().GetCounter() < owner->GetGUID().GetCounter())
            ++rank;
        if (other->GetGUID().GetCounter() < leader->GetGUID().GetCounter())
            leader = other;
    }
    if (count < 2)
        return false;

    float const lane = (rank & 1) ? float((rank + 1) / 2) : -float(rank / 2);
    float const lateral = lane * (2.0f * radius + 0.25f);
    if (std::abs(lateral) > 8.0f)
        return false;

    float const heading = leader->GetAbsoluteAngle(target);
    float const dx = std::cos(heading), dy = std::sin(heading);
    float const behind = (target->GetPositionX() - owner->GetPositionX()) * dx + (target->GetPositionY() - owner->GetPositionY()) * dy;
    float const advance = std::min(5.0f, behind - owner->GetMeleeRange(target) - 2.0f);
    if (advance < 0.5f)
        return false;

    float x = target->GetPositionX() - dx * (behind - advance) - dy * lateral;
    float y = target->GetPositionY() - dy * (behind - advance) + dx * lateral;
    float z = owner->GetPositionZ();
    float const requestedX = x, requestedY = y;
    if (!owner->GetMap()->CanReachPositionAndGetValidCoords(owner, x, y, z, true, true))
        return false;
    // The map helper can return a shortened raycast endpoint. Do not mistake
    // a wall-clipped point for a free lane or loop on a zero-length waypoint.
    if (std::hypot(x - requestedX, y - requestedY) > CONTACT_DISTANCE ||
        (x - owner->GetPositionX()) * dx + (y - owner->GetPositionY()) * dy < 0.25f)
        return false;

    point.Relocate(x, y, z);
    return true;
}

ChaseMovementGenerator::ChaseMovementGenerator(Unit *target, Optional<ChaseRange> range, Optional<ChaseAngle> angle) : AbstractFollower(ASSERT_NOTNULL(target)), _range(range),
    _angle(angle), _rangeCheckTimer(RANGE_CHECK_INTERVAL), _meleeRepositionTimer(urand(MELEE_REPOSITION_INTERVAL_MIN, MELEE_REPOSITION_INTERVAL_MAX))
{
    Priority = MOTION_PRIORITY_NORMAL;
    Flags = MOVEMENTGENERATOR_FLAG_INITIALIZATION_PENDING;
    BaseUnitState = UNIT_STATE_CHASE;
}
ChaseMovementGenerator::~ChaseMovementGenerator() = default;

bool ChaseMovementGenerator::Initialize(Unit* /*owner*/)
{
    RemoveFlag(MOVEMENTGENERATOR_FLAG_INITIALIZATION_PENDING | MOVEMENTGENERATOR_FLAG_DEACTIVATED);
    AddFlag(MOVEMENTGENERATOR_FLAG_INITIALIZED | MOVEMENTGENERATOR_FLAG_INFORM_ENABLED);

    _path = nullptr;
    _lastTargetPosition.reset();
    _meleeApproachAngle.reset();
    _meleeRepositionTimer.Reset(urand(MELEE_REPOSITION_INTERVAL_MIN, MELEE_REPOSITION_INTERVAL_MAX));
    _meleeRepositioning = false;
    _meleeChaseLane = false;
    return true;
}

bool ChaseMovementGenerator::Reset(Unit* owner)
{
    RemoveFlag(MOVEMENTGENERATOR_FLAG_DEACTIVATED);

    return Initialize(owner);
}

bool ChaseMovementGenerator::Update(Unit* owner, uint32 diff)
{
    // owner might be dead or gone (can we even get nullptr here?)
    if (!owner || !owner->IsAlive())
        return false;

    // our target might have gone away
    Unit* const target = GetTarget();
    if (!target || !target->IsInWorld())
        return false;

    // the owner might be unable to move (rooted or casting), or we have lost the target, pause movement
    if (owner->HasUnitState(UNIT_STATE_NOT_MOVE) || owner->IsNonMeleeSpellCasted(false) || HasLostTarget(owner, target))
    {
        owner->StopMoving();
        _lastTargetPosition.reset();
        if (Creature* cOwner = owner->ToCreature())
            cOwner->SetCannotReachTarget(false);
        return true;
    }

    bool const mutualChase = IsMutualChase(owner, target);
    float const hitboxSum = owner->GetCombatReach() + target->GetCombatReach();
    float const minRange = _range ? _range->MinRange + hitboxSum : CONTACT_DISTANCE;
    float const minTarget = (_range ? _range->MinTolerance : 0.0f) + hitboxSum;
    float const maxRange = _range ? _range->MaxRange + hitboxSum : owner->GetMeleeRange(target); // melee range already includes hitboxes
    float const maxTarget = _range ? _range->MaxTolerance + hitboxSum : CONTACT_DISTANCE + hitboxSum;
    Optional<ChaseAngle> angle = mutualChase ? Optional<ChaseAngle>() : _angle;

    // periodically check if we're already in the expected range...
    _rangeCheckTimer.Update(diff);
    if (_rangeCheckTimer.Passed())
    {
        _rangeCheckTimer.Reset(RANGE_CHECK_INTERVAL);
        // A default chase can start while already inside melee tolerance. No
        // approach spline is needed then, so do not leave MovementInform pending
        // forever while waiting for the smaller destination radius. An active
        // approach still has to reach maxTarget before it stops.
        float const maxInformRange = !_range && !owner->HasUnitState(UNIT_STATE_CHASE_MOVE) ? maxRange : maxTarget;
        // Reserved approach points must be reached, not cut short on entering
        // the common melee radius (which would stack the attackers again).
        bool const approachingSlot = _meleeApproachAngle && owner->HasUnitState(UNIT_STATE_CHASE_MOVE);
        if (!approachingSlot && HasFlag(MOVEMENTGENERATOR_FLAG_INFORM_ENABLED) && PositionOkay(owner, target, _movingTowards ? Optional<float>() : minTarget, _movingTowards ? maxInformRange : Optional<float>(), angle))
        {
            RemoveFlag(MOVEMENTGENERATOR_FLAG_INFORM_ENABLED);
            _path = nullptr;
            if (Creature* cOwner = owner->ToCreature())
                cOwner->SetCannotReachTarget(false);
            owner->StopMoving();
            owner->SetInFront(target);
            DoMovementInform(owner, target);
            _meleeRepositionTimer.Reset(0);
            return true;
        }
    }

    // if we're done moving, we want to clean up
    if (owner->HasUnitState(UNIT_STATE_CHASE_MOVE) && owner->movespline->Finalized())
    {
        RemoveFlag(MOVEMENTGENERATOR_FLAG_INFORM_ENABLED);
        _path = nullptr;
        if (Creature* cOwner = owner->ToCreature())
            cOwner->SetCannotReachTarget(false);
        owner->ClearUnitState(UNIT_STATE_CHASE_MOVE);
        owner->SetInFront(target);
        if (_meleeChaseLane)
            _lastTargetPosition.reset(); // intermediate waypoint, not melee arrival
        else if (!_meleeRepositioning)
        {
            DoMovementInform(owner, target);
            _meleeRepositionTimer.Reset(0);
        }
        _meleeRepositioning = false;
        _meleeChaseLane = false;
    }

    // Only an explicitly angle-constrained chase depends on target orientation.
    // Default approaches and avoidance steps keep their world-space side of
    // the target when the player turns.
    bool const targetMoved = !_lastTargetPosition || target->GetExactDistSq(_lastTargetPosition.value()) > 0.0f;
    bool const targetStateChanged = mutualChase != _mutualChase;
    if (targetStateChanged || targetMoved || (angle && target->GetPosition() != _lastTargetPosition.value()))
    {
        _lastTargetPosition = target->GetPosition();
        _mutualChase = mutualChase;
        if (owner->HasUnitState(UNIT_STATE_CHASE_MOVE) || !PositionOkay(owner, target, minRange, maxRange, angle))
        {
            _meleeRepositioning = false;
            Creature* const cOwner = owner->ToCreature();
            // can we get to the target?
            if (cOwner && !target->isInAccessiblePlaceFor(cOwner))
            {
                cOwner->SetCannotReachTarget(true);
                cOwner->StopMoving();
                _path = nullptr;
                return true;
            }

            // figure out which way we want to move
            bool const moveToward = !owner->IsInDist(target, maxRange);

            // make a new path if we have to...
            if (!_path || moveToward != _movingTowards)
                _path = std::make_unique<PathGenerator>(owner);

            float x, y, z;
            bool shortenPath;
            bool chaseLane = false;
            bool const spreadApproach = cOwner && !cOwner->IsPet() && !_range && !_angle &&
                (target->GetTypeId() == TYPEID_PLAYER || target->IsPet()) && !owner->CanFly() && !owner->IsInWater() &&
                owner->CanFreeMove() && target->getAttackers().size() > 1;
            if (!spreadApproach)
                _meleeApproachAngle.reset();

            // if we want to move toward the target and there's no fixed angle...
            if (spreadApproach)
            {
                // Reserve a distinct endpoint before starting the approach.
                // Keep its angle while the target moves, rather than letting
                // all pursuers repeatedly pick the same nearest contact point.
                float const approachAngle = _meleeApproachAngle ? *_meleeApproachAngle : target->GetAbsoluteAngle(owner);
                target->GetNearPoint(owner, x, y, z, CONTACT_DISTANCE, approachAngle);
                Position point(x, y, z);
                target->GetMeleeRepositionPoint(owner, point);
                point.GetPosition(x, y, z);
                float const selectedAngle = target->GetAbsoluteAngle(&point);
                if (!_meleeApproachAngle || std::abs(Position::NormalizePitch(selectedAngle - *_meleeApproachAngle)) > 0.05f)
                    TC_LOG_DEBUG("movement.melee", "Melee approach point: creature %u (GUID: %u), target %u, angle %.3f, point (%.3f, %.3f, %.3f)",
                        cOwner->GetEntry(), cOwner->GetGUID().GetCounter(), target->GetGUID().GetCounter(), selectedAngle, x, y, z);
                _meleeApproachAngle = selectedAngle;
                if (GetMeleeChaseLanePoint(owner, target, point))
                {
                    point.GetPosition(x, y, z);
                    chaseLane = true;
                }
                shortenPath = false;
            }
            else if (moveToward && !angle)
            {
                // ...we'll pathfind to the center, then shorten the path
                target->GetPosition(x, y, z);
                shortenPath = true;
            }
            else
            {
                // otherwise, we fall back to nearpoint finding
                target->GetNearPoint(owner, x, y, z, (moveToward ? maxTarget : minTarget) - hitboxSum, angle ? target->ToAbsoluteAngle(angle->RelativeAngle) : target->GetAbsoluteAngle(owner));
                shortenPath = false;
            }

            bool success = _path->CalculatePath(x, y, z, owner->CanFly());
            if (chaseLane && (!success || (_path->GetPathType() & (PATHFIND_NOPATH | PATHFIND_INCOMPLETE))))
            {
                // A lane is optional. If navmesh rejects it, retain normal
                // pursuit to the contact point rather than evading the fight.
                target->GetNearPoint(owner, x, y, z, CONTACT_DISTANCE, *_meleeApproachAngle);
                _path = std::make_unique<PathGenerator>(owner);
                success = _path->CalculatePath(x, y, z, owner->CanFly());
                chaseLane = false;
            }
            if (!success || (_path->GetPathType() & (PATHFIND_NOPATH /* | PATHFIND_INCOMPLETE*/)))
            {
                if (cOwner)
                    cOwner->SetCannotReachTarget(true);
                owner->StopMoving();
                return true;
            }

            if (shortenPath)
                _path->ShortenPathUntilDist(PositionToVector3(target), maxTarget);

            if (cOwner)
                cOwner->SetCannotReachTarget(false);

            bool walk = false;
            if (cOwner && !cOwner->IsPet())
            {
                switch (cOwner->GetMovementTemplate().GetChase())
                {
                    case CreatureChaseMovementType::CanWalk:
                        walk = owner->IsWalking();
                        break;
                    case CreatureChaseMovementType::AlwaysWalk:
                        walk = true;
                        break;
                    default:
                        break;
                }
            }

            owner->AddUnitState(UNIT_STATE_CHASE_MOVE);
            _meleeChaseLane = chaseLane;
            AddFlag(MOVEMENTGENERATOR_FLAG_INFORM_ENABLED);

            Movement::MoveSplineInit init(owner);
            init.MovebyPath(_path->GetPath());
            init.SetWalk(walk);
            init.SetFacing(target);
            init.Launch();
        }
    }

    _meleeRepositionTimer.Update(diff);
    if (_meleeRepositionTimer.Passed())
    {
        _meleeRepositionTimer.Reset(urand(MELEE_REPOSITION_INTERVAL_MIN, MELEE_REPOSITION_INTERVAL_MAX));

        Creature* const creature = owner->ToCreature();
        bool const isDefaultMeleeChase = creature && !creature->IsPet() && !_range && !_angle &&
            (target->GetTypeId() == TYPEID_PLAYER || target->IsPet()) && !owner->CanFly() && !owner->IsInWater() &&
            !owner->HasUnitState(UNIT_STATE_CHASE_MOVE) && !HasFlag(MOVEMENTGENERATOR_FLAG_INFORM_ENABLED) && owner->CanFreeMove();

        Position point = owner->GetPosition();
        if (isDefaultMeleeChase && target->GetMeleeRepositionPoint(owner, point))
        {
            _path = std::make_unique<PathGenerator>(owner);
            bool const success = _path->CalculatePath(point.GetPositionX(), point.GetPositionY(), point.GetPositionZ(), false);
            if (success && !(_path->GetPathType() & (PATHFIND_NOPATH | PATHFIND_INCOMPLETE)))
            {
                owner->AddUnitState(UNIT_STATE_CHASE_MOVE);
                _meleeRepositioning = true;
                _meleeApproachAngle = target->GetAbsoluteAngle(&point);

                Movement::MoveSplineInit init(owner);
                init.MovebyPath(_path->GetPath());
                CreatureChaseMovementType const chaseMovement = creature->GetMovementTemplate().GetChase();
                init.SetWalk(chaseMovement == CreatureChaseMovementType::AlwaysWalk ||
                    (chaseMovement == CreatureChaseMovementType::CanWalk && owner->IsWalking()));
                init.SetFacing(target);
                init.Launch();

                TC_LOG_DEBUG("movement.melee", "Melee reposition: creature %u (GUID: %u), target %u, from (%.3f, %.3f, %.3f) to (%.3f, %.3f, %.3f)",
                    creature->GetEntry(), creature->GetGUID().GetCounter(), target->GetGUID().GetCounter(),
                    owner->GetPositionX(), owner->GetPositionY(), owner->GetPositionZ(),
                    point.GetPositionX(), point.GetPositionY(), point.GetPositionZ());
            }
        }
    }

    // and then, finally, we're done for the tick
    return true;
}

void ChaseMovementGenerator::Deactivate(Unit* owner)
{
    AddFlag(MOVEMENTGENERATOR_FLAG_DEACTIVATED);
    RemoveFlag(MOVEMENTGENERATOR_FLAG_TRANSITORY | MOVEMENTGENERATOR_FLAG_INFORM_ENABLED);
    owner->ClearUnitState(UNIT_STATE_CHASE_MOVE);
    _meleeRepositioning = false;
    _meleeApproachAngle.reset();
    _meleeChaseLane = false;
    if (Creature* cOwner = owner->ToCreature())
        cOwner->SetCannotReachTarget(false);
}

void ChaseMovementGenerator::Finalize(Unit* owner, bool active, bool/* movementInform*/)
{
    AddFlag(MOVEMENTGENERATOR_FLAG_FINALIZED);
    if (active)
    {
        owner->ClearUnitState(UNIT_STATE_CHASE_MOVE);
        _meleeRepositioning = false;
        _meleeApproachAngle.reset();
        _meleeChaseLane = false;
        if (Creature* cOwner = owner->ToCreature())
            cOwner->SetCannotReachTarget(false);
    }
}
