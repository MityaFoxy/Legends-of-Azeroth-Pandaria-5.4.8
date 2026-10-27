/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license, you may redistribute it
 * and/or modify it under version 2 of the License, or (at your option), any later version.
 */

#include "MovementActions.h"

#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <string>
#include <algorithm>

#include "Event.h"
#include "PositionValue.h"
#include "G3D/Vector3.h"
#include "GameObject.h"
#include "LastMovementValue.h"
#include "Log.h"
#include "Map.h"
#include "MotionMaster.h"
#include "MoveSpline.h"
#include "MoveSplineInitArgs.h"
#include "MovementGenerator.h"
#include "ObjectDefines.h"
#include "ObjectGuid.h"
#include "PathGenerator.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "Playerbots.h"
#include "PlayerbotSpec.h"
#include "Position.h"

#include "Random.h"
#include "ServerFacade.h"
#include "SharedDefines.h"
#include "SpellAuraEffects.h"
#include "SpellInfo.h"

#include "Timer.h"
#include "Transport.h"
#include "Unit.h"
#include "Vehicle.h"
#include "WaypointMovementGenerator.h"
#include "Corpse.h"

MovementAction::MovementAction(PlayerbotAI* botAI, std::string const name) : Action(botAI, name)
{
    bot = botAI->GetBot();
}

void MovementAction::ClearIdleState()
{
    context->GetValue<time_t>("stay time")->Set(0);
    context->GetValue<PositionMap&>("position")->Get()["random"].Reset();
}

void MovementAction::WaitForReach(float distance)
{
    float delay = 1000.0f * MoveDelay(distance);

    if (delay > sPlayerbotAIConfig->maxWaitForMove)
        delay = sPlayerbotAIConfig->maxWaitForMove;

    Unit* target = *botAI->GetAiObjectContext()->GetValue<Unit*>("current target");
    Unit* player = *botAI->GetAiObjectContext()->GetValue<Unit*>("enemy player target");
    if ((player || target) && delay > sPlayerbotAIConfig->globalCoolDown)
        delay = sPlayerbotAIConfig->globalCoolDown;

    if (delay < 0)
        delay = 0;

    botAI->SetNextCheckDelay((uint32)delay);
}

void MovementAction::UpdateMovementState()
{
    auto botInLiquidState = bot->GetLiquidStatus();

    if ((botInLiquidState & LIQUID_MAP_IN_WATER) || (botInLiquidState & LIQUID_MAP_UNDER_WATER))
    {
        bot->SetSwim(true);
    }
    else
    {
        bot->SetSwim(false);
    }

    bool onGround = bot->GetPositionZ() < bot->GetMapWaterOrGroundLevel(bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ()) + 1.0f;

    // Keep bot->SendMovementFlagUpdate() withing the if statements to not intefere with bot behavior on ground/(shallow) waters
    if (!bot->HasUnitMovementFlag(MOVEMENTFLAG_FLYING) &&
        bot->HasAuraType(SPELL_AURA_MOD_INCREASE_MOUNTED_FLIGHT_SPEED) && !onGround)
    {
        bot->AddUnitMovementFlag(MOVEMENTFLAG_FLYING);
        bot->SendMovementFlagUpdate();
    }

    else if (bot->HasUnitMovementFlag(MOVEMENTFLAG_FLYING) &&
        (!bot->HasAuraType(SPELL_AURA_MOD_INCREASE_MOUNTED_FLIGHT_SPEED) || onGround))
    {
        bot->RemoveUnitMovementFlag(MOVEMENTFLAG_FLYING);
        bot->SendMovementFlagUpdate();
    }
}

bool MovementAction::ChaseTo(WorldObject* obj, float distance, float angle)
{
    if (!IsMovingAllowed())
    {
        return false;
    }

    if (Vehicle* vehicle = bot->GetVehicle())
    {
        VehicleSeatEntry const* seat = vehicle->GetSeatForPassenger(bot);
        if (!seat || !seat->CanControl())
            return false;

        // vehicle->GetMotionMaster()->Clear();
        vehicle->GetBase()->GetMotionMaster()->MoveChase((Unit*)obj, 30.0f);
        return true;
    }

    UpdateMovementState();

    if (!bot->IsStandState())
        bot->SetStandState(UNIT_STAND_STATE_STAND);

    if (bot->IsNonMeleeSpellCasted(true))
    {
        bot->CastStop();
        botAI->InterruptSpell();
    }

    bot->GetMotionMaster()->MoveChase((Unit*)obj, distance);

    // TODO shouldnt this use "last movement" value?
    WaitForReach(bot->GetExactDist2d(obj) - distance);
    return true;
}

bool MovementAction::ReachCombatTo(Unit* target, float distance)
{
    if (!IsMovingAllowed(target))
        return false;

    float const requestedDistance = distance;
    float tx = target->GetPositionX();
    float ty = target->GetPositionY();
    float tz = target->GetPositionZ();
    float combatDistance = bot->GetCombatReach() + target->GetCombatReach();
    distance += combatDistance;

    bool const melee = requestedDistance <= sPlayerbotAIConfig->meleeDistance + 0.1f;
    Position reposition = bot->GetPosition();
    bool const needsReposition = melee && target->GetMeleeRepositionPoint(bot, reposition);
    if (bot->GetExactDist(tx, ty, tz) <= distance && !needsReposition && bot->IsWithinLOSInMap(target))
        return false;

    float const disToGo = bot->GetExactDist(tx, ty, tz) - distance;
    bool contactPoint = false;
    if (needsReposition)
    {
        reposition.GetPosition(tx, ty, tz);
        contactPoint = true;
    }
    else if (melee && disToGo < 10.0f)
    {
        // Reserve stable angles around a shared target so Playerbots do not
        // all shorten their paths to the same contact point.
        uint32 lane = (bot->GetGUID().GetCounter() * 2654435761U
            ^ target->GetGUID().GetCounter() * 2246822519U) % 16U;
        float angle = float(2.0 * M_PI) * float(lane) / 16.0f;
        target->GetNearPoint(bot, tx, ty, tz, CONTACT_DISTANCE, angle);
        Position point(tx, ty, tz);
        target->GetMeleeRepositionPoint(bot, point);
        point.GetPosition(tx, ty, tz);
        contactPoint = true;
    }

    G3D::Vector3 const targetPosition(target->GetPositionX(), target->GetPositionY(), target->GetPositionZ());
    auto canReachTargetFrom = [&](G3D::Vector3 const& point, float range)
    {
        return (point - targetPosition).length() <= range &&
            bot->GetMap()->isInLineOfSight(point.x, point.y, point.z + bot->GetCollisionHeight(),
                targetPosition.x, targetPosition.y, targetPosition.z + target->GetCollisionHeight(),
                bot->GetPhaseMask(), VMAP::ModelIgnoreFlags::Nothing);
    };
    // A reserved angle separates attackers on flat ground, but terrain can
    // put its contact point outside combat range or behind an obstacle. Do
    // not keep approaching that same unusable point on every AI update.
    if (contactPoint && !canReachTargetFrom({tx, ty, tz}, distance))
    {
        target->GetPosition(tx, ty, tz);
        contactPoint = false;
    }

    // Combat must use the same checked ground/water corridors as objective
    // movement. The legacy preliminary path could select a river-bottom point
    // before MoveTo ever reached that planner, leaving the bot unable to chase.
    bool usingNavigation = true;
    Movement::PointsArray path = SearchForBestPath(tx, ty, tz, usingNavigation, true);
    if (contactPoint && (path.size() < 2 || !canReachTargetFrom(path.back(), distance)))
    {
        // Projection can also collapse the preferred point onto our current
        // position, or leave its actual endpoint out of range. Try the target
        // corridor once, then shorten it below; never force a direct segment.
        contactPoint = false;
        path = SearchForBestPath(targetPosition.x, targetPosition.y, targetPosition.z, usingNavigation, true);
    }
    if (path.size() < 2)
        return false;
    float shortenTo = distance;

    // Avoid walking too far when moving towards each other
    if (!contactPoint && disToGo >= 10.0f)
        shortenTo = disToGo / 2 + distance;

    G3D::Vector3 endPos = path.back();
    if (!contactPoint)
    {
        for (size_t i = 1; i < path.size(); ++i)
        {
            G3D::Vector3 const& point = path[i];
            // Stop at a reachable path vertex with sight of the opponent.
            // Range alone can leave a caster firing into a wall indefinitely.
            if (canReachTargetFrom(point, shortenTo))
            {
                endPos = point;
                break;
            }
        }
    }
    return MoveTo(target->GetMapId(), endPos.x, endPos.y, endPos.z, false, false, false, false,
        MovementPriority::MOVEMENT_COMBAT, true);
}

bool MovementAction::IsDuplicateMove(uint32 mapId, float x, float y, float z)
{
    LastMovement& lastMove = *context->GetValue<LastMovement&>("last movement");

    // heuristic 5s
    if (lastMove.msTime + sPlayerbotAIConfig->maxWaitForMove < getMSTime() ||
        lastMove.lastMoveShort.GetExactDist(x, y, z) > 0.01f)
        return false;

    return true;
}

bool MovementAction::IsWaitingForLastMove(MovementPriority priority)
{
    LastMovement& lastMove = *context->GetValue<LastMovement&>("last movement");

    if (priority > lastMove.priority)
        return false;

    // heuristic 5s
    if (lastMove.lastdelayTime + lastMove.msTime > getMSTime())
        return true;

    return false;
}

float MovementAction::MoveDelay(float distance, bool backwards)
{
    float speed;
    if (bot->isSwimming())
    {
        speed = backwards ? bot->GetSpeed(MOVE_SWIM_BACK) : bot->GetSpeed(MOVE_SWIM);
    }
    else if (bot->IsFlying())
    {
        speed = backwards ? bot->GetSpeed(MOVE_FLIGHT_BACK) : bot->GetSpeed(MOVE_FLIGHT);
    }
    else
    {
        speed = backwards ? bot->GetSpeed(MOVE_RUN_BACK) : bot->GetSpeed(MOVE_RUN);
    }
    float delay = distance / speed;
    return delay;
}

bool MovementAction::MoveTo(WorldObject* target, float distance, MovementPriority priority)
{
    if (!IsMovingAllowed(target))
        return false;

    float bx = bot->GetPositionX();
    float by = bot->GetPositionY();
    float bz = bot->GetPositionZ();

    float tx = target->GetPositionX();
    float ty = target->GetPositionY();
    float tz = target->GetPositionZ();

    float distanceToTarget = bot->GetDistance(target);
    float angle = bot->GetAngle(target);
    float needToGo = distanceToTarget - distance;

    float maxDistance = sPlayerbotAIConfig->spellDistance;
    if (needToGo > 0 && needToGo > maxDistance)
        needToGo = maxDistance;
    else if (needToGo < 0 && needToGo < -maxDistance)
        needToGo = -maxDistance;

    float dx = cos(angle) * needToGo + bx;
    float dy = sin(angle) * needToGo + by;
    float dz;  // = std::max(bz, tz); // calc accurate z position to avoid stuck
    if (distanceToTarget > CONTACT_DISTANCE)
    {
        dz = bz + (tz - bz) * (needToGo / distanceToTarget);
    }
    else
    {
        dz = tz;
    }
    return MoveTo(target->GetMapId(), dx, dy, dz, false, false, false, false, priority);
}

bool MovementAction::MoveTo(uint32 mapId, float x, float y, float z, bool idle, bool react, bool normal_only,
    bool exact_waypoint, MovementPriority priority, bool lessDelay, bool backwards)
{
    lastMoveFailure = MoveFailure::None;
    UpdateMovementState();
    // Never turn an invalid destination into an unchecked fallback movement.
    if (mapId != bot->GetMapId() || !Trinity::IsValidMapCoord(x, y, z))
    {
        LogNavigationResult("rejected", "invalid-map-or-coordinates", 0, 0, x, y, z, true);
        return false;
    }
    if (!IsMovingAllowed(mapId, x, y, z))
    {
        return false;
    }
    if (!bot->GetVehicle() && !bot->GetTransport() && !bot->IsFlying() && !CanStartGroundMovement(x, y, z))
    {
        lastMoveFailure = MoveFailure::RecoveryExhausted;
        return false;
    }
    if (IsDuplicateMove(mapId, x, y, z))
    {
        return false;
    }
    if (IsWaitingForLastMove(priority))
    {
        return false;
    }
    bool const battlegroundGroundMovement = bot->InBattleground();
    if (battlegroundGroundMovement)
        normal_only = true;
    bool const sourceInWater = bot->IsUnderWater() || bot->IsInWater();
    bool const destinationInWater = bot->GetMap()->GetLiquidStatus(bot->GetPhaseMask(), x, y, z,
        MAP_ALL_LIQUIDS, nullptr, bot->GetCollisionHeight()) & MAP_LIQUID_STATUS_IN_CONTACT;
    // Underwater movement to another underwater point is genuinely 3D. When
    // the destination is on land, use the mixed ground/water navmesh instead
    // of drawing one long spline through the river bank or terrain.
    bool generatePath = battlegroundGroundMovement
        || (!bot->IsFlying() && (!sourceInWater || !destinationInWater));
    if (Vehicle* vehicle = bot->GetVehicle())
    {
        VehicleSeatEntry const* seat = vehicle->GetSeatForPassenger(bot);
        Unit* vehicleBase = vehicle->GetBase();
        if (!vehicleBase || !seat || !seat->CanControl())  // is passenger and cant move anyway
            return false;
        generatePath = !vehicleBase->CanFly();

        float distance = vehicleBase->GetExactDist(x, y, z);  // use vehicle distance, not bot
        if (distance > 0.01f)
        {
            MotionMaster& mm = *vehicleBase->GetMotionMaster();  // need to move vehicle, not bot
            mm.Clear();
            if (!backwards)
            {
                mm.MovePoint(0, x, y, z, generatePath);
            }
            else
            {
                mm.MovePointBackwards(0, x, y, z, generatePath);
            }
            float speed = backwards ? vehicleBase->GetSpeed(MOVE_RUN_BACK) : vehicleBase->GetSpeed(MOVE_RUN);
            float delay = 1000.0f * (distance / speed);
            if (lessDelay)
            {
                delay -= botAI->GetReactDelay();
            }
            delay = std::max(.0f, delay);
            delay = std::min((float)sPlayerbotAIConfig->maxWaitForMove, delay);
            AI_VALUE(LastMovement&, "last movement").Set(mapId, x, y, z, bot->GetOrientation(), delay, priority);
            return true;
        }
    }
    else if (!generatePath || bot->GetTransport())
    {
        float distance = bot->GetExactDist(x, y, z);
        if (distance > 0.01f)
        {
            if (bot->IsSitState())
                bot->SetStandState(UNIT_STAND_STATE_STAND);

            MotionMaster& mm = *bot->GetMotionMaster();
            mm.Clear();
            if (!backwards)
            {
                mm.MovePoint(0, x, y, z, generatePath);
            }
            else
            {
                mm.MovePointBackwards(0, x, y, z, generatePath);
            }
            float delay = 1000.0f * MoveDelay(distance, backwards);
            if (lessDelay)
            {
                delay -= botAI->GetReactDelay();
            }
            delay = std::max(.0f, delay);
            delay = std::min((float)sPlayerbotAIConfig->maxWaitForMove, delay);
            AI_VALUE(LastMovement&, "last movement").Set(mapId, x, y, z, bot->GetOrientation(), delay, priority);
            return true;
        }
    }
    else
    {
        Movement::PointsArray path = SearchForBestPath(x, y, z, generatePath, normal_only);
        if (path.size() < 2)
        {
            lastMoveFailure = MoveFailure::Route;
            return false;
        }
        // Partial paths may stop before the requested destination. Move to
        // the reachable endpoint and keep the movement bookkeeping in sync.
        G3D::Vector3 const& endP = path.back();
        float distance = bot->GetExactDist(endP.x, endP.y, endP.z);
        if (distance > 0.01f)
        {
            if (bot->IsSitState())
                bot->SetStandState(UNIT_STAND_STATE_STAND);

            MotionMaster& mm = *bot->GetMotionMaster();
            mm.Clear();
            if (generatePath)
            {
                if (!mm.MovePointPath(0, path))
                    return false;
            }
            else if (!backwards)
            {
                mm.MovePoint(0, endP.x, endP.y, endP.z, generatePath);
            }
            else
            {
                mm.MovePointBackwards(0, endP.x, endP.y, endP.z, generatePath);
            }
            float routeDistance = 0.0f;
            for (size_t i = 1; i < path.size(); ++i)
            {
                G3D::Vector3 const delta = path[i] - path[i - 1];
                routeDistance += delta.length();
            }
            float delay = 1000.0f * MoveDelay(routeDistance, backwards);
            if (lessDelay)
            {
                delay -= botAI->GetReactDelay();
            }
            delay = std::max(.0f, delay);
            delay = std::min((float)sPlayerbotAIConfig->maxWaitForMove, delay);
            AI_VALUE(LastMovement&, "last movement").Set(mapId, endP.x, endP.y, endP.z, bot->GetOrientation(), delay, priority);
            TrackGroundMovement(x, y, z, normal_only, backwards);
            return true;
        }
    }
    return false;
}

bool MoveRandomAction::Execute(Event event)
{
    float distance = sPlayerbotAIConfig->tooCloseDistance + urand(10, 30);
    const float x = bot->GetPositionX();
    const float y = bot->GetPositionY();
    const float z = bot->GetPositionZ();
    int attempts = 5;
    Map* map = bot->GetMap();
    while (--attempts)
    {
        float angle = (float)rand_norm() * 2 * static_cast<float>(M_PI);
        float dx = x + distance * cos(angle);
        float dy = y + distance * sin(angle);
        float dz = z;
        if (!map->CheckCollisionAndGetValidCoords(bot, bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ(),
            dx, dy, dz))
            continue;

        if (map->IsInWater(bot->GetPhaseMask(), dx, dy, dz))
            continue;

        bool moved = MoveTo(bot->GetMapId(), dx, dy, dz, false, false, false, true);
        if (moved)
            return true;
    }

    return false;
}

bool MovementAction::MoveNear(uint32 mapId, float x, float y, float z, float distance, MovementPriority priority)
{
    float angle = GetFollowAngle();
    return MoveTo(mapId, x + cos(angle) * distance, y + sin(angle) * distance, z, false, false, false, false, priority);
}

bool MovementAction::MoveNear(WorldObject* target, float distance, MovementPriority priority)
{
    if (!target)
        return false;

    distance += target->GetCombatReach();

    float x = target->GetPositionX();
    float y = target->GetPositionY();
    float z = target->GetPositionZ();
    float followAngle = GetFollowAngle();

    for (float angle = followAngle; angle <= followAngle + static_cast<float>(2 * M_PI);
        angle += static_cast<float>(M_PI / 4.f))
    {
        float x = target->GetPositionX() + cos(angle) * distance;
        float y = target->GetPositionY() + sin(angle) * distance;
        float z = target->GetPositionZ();

        if (!bot->IsWithinLOS(x, y, z))
            continue;

        bool moved = MoveTo(target->GetMapId(), x, y, z, false, false, false, false, priority);
        if (moved)
            return true;
    }

    // botAI->TellError("All paths not in LOS");
    return false;
}

float MovementAction::GetFollowAngle()
{
    Player* master = GetMaster();
    Group* group = master ? master->GetGroup() : bot->GetGroup();
    if (!group)
        return 0.0f;

    uint32 index = 1;
    for (GroupReference* ref = group->GetFirstMember(); ref; ref = ref->next())
    {
        if (ref->GetSource() == master)
            continue;

        if (ref->GetSource() == bot)
            return 2 * M_PI / (group->GetMembersCount() - 1) * index;

        ++index;
    }

    return 0;
}

bool MoveRandomAction::isUseful()
{
    return true;
}

bool MovementAction::IsMovingAllowed(WorldObject* target)
{
    if (!target)
        return false;

    if (bot->GetMapId() != target->GetMapId())
        return false;

    return IsMovingAllowed();
}

bool MovementAction::IsMovingAllowed(uint32 mapId, float x, float y, float z)
{
    return IsMovingAllowed();
}

bool MovementAction::IsMovingAllowed()
{
    // do not allow if not vehicle driver
    if (botAI->IsInVehicle() && !botAI->IsInVehicle(true))
        return false;

    if (bot->isFrozen() || bot->IsPolymorphed() || (bot->isDead() && !bot->HasPlayerFlag(PLAYER_FLAGS_GHOST)) ||
        bot->IsBeingTeleported() || bot->HasRootAura() || bot->HasSpiritOfRedemptionAura() ||
        bot->HasConfuseAura() || bot->IsCharmed() || bot->HasStunAura() ||
        bot->IsInFlight() || bot->HasUnitState(UNIT_STATE_LOST_CONTROL))
        return false;

    if (bot->GetMotionMaster()->GetMotionSlotType(MOTION_SLOT_CONTROLLED) != NULL_MOTION_TYPE)
    {
        return false;
    }

    return bot->GetMotionMaster()->GetCurrentMovementGeneratorType() != FLIGHT_MOTION_TYPE;
}

bool MoveRandomAction::isPossible()
{
    if (bot->IsInCombat() ||
        !AI_VALUE(bool, "can move around") ||
        !bot->CanFreeMove() ||
        !botAI->CanMove()) return false;

    return true;
}

bool MovementAction::Follow(Unit* target, float distance) { return Follow(target, distance, GetFollowAngle()); }
bool MovementAction::Follow(Unit* target, float distance, float angle)
{
    UpdateMovementState();

    if (!target)
        return false;

    if (!bot->InBattleground() && sServerFacade->IsDistanceLessOrEqualThan(sServerFacade->GetDistance2d(bot, target),
        sPlayerbotAIConfig->followDistance))
    {
        // botAI->TellError("No need to follow");
        return false;
    }

    // Move to target corpse if alive.
    if (!target->IsAlive() && bot->IsAlive() && target->GetGUID().IsPlayer())
    {
        Player* pTarget = (Player*)target;

        Corpse* corpse = pTarget->GetCorpse();

        if (corpse)
        {
            WorldPosition botPos(bot);
            WorldPosition cPos(corpse);

            if (botPos.fDist(cPos) > sPlayerbotAIConfig->spellDistance)
                return MoveTo(cPos.getMapId(), cPos.getX(), cPos.getY(), cPos.getZ());
        }
    }

    if (sServerFacade->IsDistanceGreaterOrEqualThan(sServerFacade->GetDistance2d(bot, target),
        sPlayerbotAIConfig->sightDistance))
    {
        if (target->GetGUID().IsPlayer())
        {
            Player* pTarget = (Player*)target;

            PlayerbotAI* targetBotAI = GET_PLAYERBOT_AI(pTarget);
            if (targetBotAI)  // Try to move to where the bot is going if it is closer and in the same direction.
            {
                WorldPosition botPos(bot);
                WorldPosition tarPos(target);
                WorldPosition longMove =
                    targetBotAI->GetAiObjectContext()->GetValue<WorldPosition>("last long move")->Get();

                if (longMove)
                {
                    float lDist = botPos.fDist(longMove);
                    float tDist = botPos.fDist(tarPos);
                    float ang = botPos.getAngleBetween(tarPos, longMove);
                    if ((lDist * 1.5 < tDist && ang < static_cast<float>(M_PI) / 2) ||
                        target->HasUnitState(UNIT_STATE_IN_FLIGHT))
                    {
                        return MoveTo(longMove.getMapId(), longMove.getX(), longMove.getY(), longMove.getZ());
                    }
                }
            }
            else
            {
                if (pTarget->HasUnitState(UNIT_STATE_IN_FLIGHT))  // Move to where the player is flying to.
                {
                    TaxiPathNodeList const& tMap = static_cast<FlightPathMovementGenerator*>(pTarget->GetMotionMaster()->top())->GetPath();
                    if (!tMap.empty())
                    {
                        /*const TaxiPathNodeEntry& tEnd = tMap[tMap.GetTotalLength()];
                        return MoveTo(tEnd.MapId, tEnd.LocX, tEnd.LocY, tEnd.LocZ);*/
                    }
                }
            }
        }

        if (!target->HasUnitState(UNIT_STATE_IN_FLIGHT))
            return MoveTo(target, sPlayerbotAIConfig->followDistance);
    }

    if (sServerFacade->IsDistanceLessOrEqualThan(sServerFacade->GetDistance2d(bot, target),
        sPlayerbotAIConfig->followDistance))
    {
        // botAI->TellError("No need to follow");
        return false;
    }

    if (target->IsFriendlyTo(bot) && bot->IsMounted() && AI_VALUE(GuidVector, "all targets").empty())
        distance += angle;

    if (!bot->InBattleground() && sServerFacade->IsDistanceLessOrEqualThan(sServerFacade->GetDistance2d(bot, target),
        sPlayerbotAIConfig->followDistance))
    {
        // botAI->TellError("No need to follow");
        return false;
    }

    bot->HandleEmoteCommand(0);

    if (bot->IsSitState())
        bot->SetStandState(UNIT_STAND_STATE_STAND);

    if (bot->IsNonMeleeSpellCasted(true))
    {
        bot->CastStop();
        botAI->InterruptSpell();
    }

    // AI_VALUE(LastMovement&, "last movement").Set(target);
    ClearIdleState();

    if (bot->GetMotionMaster()->GetCurrentMovementGeneratorType() == FOLLOW_MOTION_TYPE)
    {
        Unit* currentTarget = sServerFacade->GetChaseTarget(bot);
        if (currentTarget && currentTarget->GetGUID() == target->GetGUID())
            return false;
    }

    if (bot->GetMotionMaster()->GetCurrentMovementGeneratorType() != FOLLOW_MOTION_TYPE)
        bot->GetMotionMaster()->Clear();

    bot->GetMotionMaster()->MoveFollow(target, distance, angle);
    return true;
}

void MovementAction::LogNavigationResult(char const* outcome, char const* reason, uint32 type, uint32 attempts,
    float x, float y, float z, bool warning)
{
    LastMovement& last = AI_VALUE(LastMovement&, "last movement");
    uint32 const now = getMSTime();
    if (last.navigationLogStarted && (!warning || last.navigationLogWarning) &&
        getMSTimeDiff(last.navigationLogTime, now) < sPlayerbotAIConfig->navigationLogInterval)
    {
        ++last.navigationLogSuppressed;
        return;
    }
    uint32 const suppressed = last.navigationLogSuppressed;
    last.navigationLogStarted = true;
    last.navigationLogWarning = warning;
    last.navigationLogTime = now;
    last.navigationLogSuppressed = 0;
    if (warning)
        TC_LOG_WARN("playerbots.navigation", "bot={} map={} instance={} from=({},{},{}) target=({},{},{}) outcome={} reason={} pathType={} attempts={} inWater={} underWater={} swimming={} suppressed={}",
            bot->GetGUID().GetCounter(), bot->GetMapId(), bot->GetInstanceId(), bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ(),
            x, y, z, outcome, reason, type, attempts, bot->IsInWater(), bot->IsUnderWater(),
            bot->HasUnitMovementFlag(MOVEMENTFLAG_SWIMMING), suppressed);
    else
        TC_LOG_INFO("playerbots.navigation", "bot={} map={} instance={} from=({},{},{}) target=({},{},{}) outcome={} reason={} pathType={} attempts={} inWater={} underWater={} swimming={} suppressed={}",
            bot->GetGUID().GetCounter(), bot->GetMapId(), bot->GetInstanceId(), bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ(),
            x, y, z, outcome, reason, type, attempts, bot->IsInWater(), bot->IsUnderWater(),
            bot->HasUnitMovementFlag(MOVEMENTFLAG_SWIMMING), suppressed);
}

bool MovementAction::CanStartGroundMovement(float x, float y, float z)
{
    GroundMovementState& state = AI_VALUE(LastMovement&, "last movement").groundMovement;
    if (!state.exhausted || !state.Matches(bot->GetMapId(), bot->GetInstanceId(), {x, y, z}))
        return true;
    G3D::Vector3 const position(bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ());
    if ((position - state.anchor).length() > 2.0f)
    {
        state = {};
        return true;
    }
    return false;
}

void MovementAction::TrackGroundMovement(float x, float y, float z, bool normalOnly, bool backwards)
{
    GroundMovementState& state = AI_VALUE(LastMovement&, "last movement").groundMovement;
    bool const continuing = state.Matches(bot->GetMapId(), bot->GetInstanceId(), {x, y, z});
    if (!continuing)
        state = {};
    if (!state.active)
    {
        state.anchor = {bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ()};
        state.idleMs = 0;
    }
    state.tracked = state.active = true;
    state.mapId = bot->GetMapId();
    state.instanceId = bot->GetInstanceId();
    state.goal = {x, y, z};
    state.normalOnly = normalOnly;
    state.backwards = backwards;
    state.generator = bot->GetMotionMaster()->top();
    state.splineId = bot->movespline->GetId();
    state.endpoint = bot->movespline->FinalDestination();
    // Correlate issued motion with path-query diagnostics without changing
    // movement or flooding INFO/WARN with every successful primary route.
    TC_LOG_DEBUG("playerbots.navigation", "bot={} map={} instance={} outcome=ground-movement-started spline={} from=({},{},{}) goal=({},{},{}) endpoint=({},{},{}) normalOnly={} backwards={}",
        bot->GetGUID().GetCounter(), state.mapId, state.instanceId, state.splineId,
        bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ(),
        state.goal.x, state.goal.y, state.goal.z, state.endpoint.x, state.endpoint.y, state.endpoint.z,
        normalOnly, backwards);
}

void MovementAction::LogStuckResult(char const* outcome, uint32 attempts, bool warning)
{
    GroundMovementState const& state = AI_VALUE(LastMovement&, "last movement").groundMovement;
    // Events are bounded by timeout/attempt budget, independent of path-log throttling.
    if (warning)
        TC_LOG_WARN("playerbots.navigation", "bot={} map={} instance={} outcome={} recoveryAttempt={}/{} idleMs={} from=({},{},{}) goal=({},{},{}) endpoint=({},{},{}) spline={}",
            bot->GetGUID().GetCounter(), bot->GetMapId(), bot->GetInstanceId(), outcome, attempts, sPlayerbotAIConfig->stuckMaxAttempts, state.idleMs,
            bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ(), state.goal.x, state.goal.y, state.goal.z,
            state.endpoint.x, state.endpoint.y, state.endpoint.z, state.splineId);
    else
        TC_LOG_INFO("playerbots.navigation", "bot={} map={} instance={} outcome={} recoveryAttempt={} from=({},{},{}) goal=({},{},{})",
            bot->GetGUID().GetCounter(), bot->GetMapId(), bot->GetInstanceId(), outcome, attempts,
            bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ(), state.goal.x, state.goal.y, state.goal.z);
}

void MovementAction::CheckStuck(uint32 elapsed)
{
    LastMovement& last = AI_VALUE(LastMovement&, "last movement");
    GroundMovementState& state = last.groundMovement;
    MotionMaster& mm = *bot->GetMotionMaster();
    bool const swimming = bot->IsInWater() || bot->IsUnderWater();
    // Native chase and idle bots need the same water mode refresh as issued
    // point routes. A transition must not wait for another AI MoveTo call.
    if (!bot->GetVehicle() && !bot->GetTransport() && !bot->IsFlying()
        && !bot->IsBeingTeleported() && bot->IsAlive() && bot->SetSwim(swimming))
        mm.PropagateSpeedChange();
    if (!state.active)
        return;
    if (state.mapId != bot->GetMapId() || state.instanceId != bot->GetInstanceId() ||
        bot->GetVehicle() || bot->GetTransport() || bot->IsFlying() ||
        bot->IsBeingTeleported() || !bot->IsAlive() || mm.top() != state.generator ||
        mm.GetCurrentMovementGeneratorType() != POINT_MOTION_TYPE)
    {
        state = {};
        return;
    }
    G3D::Vector3 const position(bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ());
    float const speed = bot->GetSpeed(swimming ? (state.backwards ? MOVE_SWIM_BACK : MOVE_SWIM)
        : (state.backwards ? MOVE_RUN_BACK : MOVE_RUN));
    if (!IsMovingAllowed() || bot->HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED) ||
        bot->IsNonMeleeSpellCasted(false) || bot->IsSitState() || speed <= 0.01f)
    {
        state.anchor = position;
        state.idleMs = 0;
        return;
    }
    if ((position - state.goal).length() <= 1.0f)
    {
        if (state.attempts)
            LogStuckResult("stuck-goal-reached", state.attempts, false);
        state = {};
        return;
    }
    if (state.recovering && (position - state.recoveryStart).length() >= 2.0f)
    {
        LogStuckResult("stuck-progress-restored", state.attempts, false);
        state.recovering = false;
    }
    // Intentional StopMoving and a completed partial route are not a stuck bot.
    if (bot->movespline->Finalized() || bot->IsStopped())
    {
        state.active = false;
        state.idleMs = 0;
        return;
    }
    // Same generator can relaunch its spline after a speed change.
    if (state.splineId != bot->movespline->GetId())
    {
        if ((state.endpoint - bot->movespline->FinalDestination()).length() > 0.1f)
        {
            state = {};
            return;
        }
        state.splineId = bot->movespline->GetId();
    }
    float const threshold = std::clamp(speed * 0.5f, 0.05f, 0.5f);
    if ((position - state.anchor).length() >= threshold)
    {
        state.anchor = position;
        state.idleMs = 0;
        return;
    }
    // Do not interpret a long server stall as seconds of observed immobility.
    state.idleMs += std::min<uint32>(elapsed, 1000);
    if (state.idleMs < sPlayerbotAIConfig->stuckTimeout)
        return;
    LogStuckResult("stuck-detected", state.attempts);
    auto exhaust = [&]()
    {
        LogStuckResult("stuck-recovery-exhausted", state.attempts);
        bot->StopMoving();
        mm.Clear();
        state.active = state.recovering = false;
        state.exhausted = true;
        state.anchor = position;
        last.lastdelayTime = 0;
    };
    if (state.attempts >= sPlayerbotAIConfig->stuckMaxAttempts)
    {
        exhaust();
        return;
    }
    ++state.attempts;
    state.idleMs = 0;
    bool navigation = true;
    // The primary/direct route has already failed at runtime. Require a new
    // navigated waypoint route, never force that same straight line again.
    Movement::PointsArray path = SearchForBestPath(state.goal.x, state.goal.y, state.goal.z, navigation, true, state.attempts);
    if (path.size() < 2 || !navigation)
    {
        LogStuckResult("stuck-recovery-no-route", state.attempts);
        if (state.attempts >= sPlayerbotAIConfig->stuckMaxAttempts)
            exhaust();
        return;
    }
    mm.Clear();
    if (!mm.MovePointPath(0, path))
    {
        exhaust();
        return;
    }
    state.generator = mm.top();
    state.splineId = bot->movespline->GetId();
    state.endpoint = path.back();
    state.anchor = state.recoveryStart = position;
    state.recovering = true;
    last.Set(state.mapId, path.back().x, path.back().y, path.back().z, bot->GetOrientation(), 0, last.priority);
    LogStuckResult("stuck-recovery-started", state.attempts, false);
}

bool MovementAction::ValidateWaterConnection(G3D::Vector3 const& from, G3D::Vector3 const& to)
{
    float distance = (to - from).length();
    if (distance > 16.0f)
        return false;
    uint32 steps = std::max<uint32>(1, uint32(std::ceil(distance / 0.5f)));
    for (uint32 step = 0; step <= steps; ++step)
    {
        G3D::Vector3 point = from + (to - from) * (float(step) / float(steps));
        LiquidData liquid{};
        if (bot->GetMap()->GetLiquidStatus(bot->GetPhaseMask(), point.x, point.y, point.z,
            MAP_ALL_LIQUIDS, &liquid, bot->GetCollisionHeight()) == LIQUID_MAP_NO_WATER ||
            !std::isfinite(liquid.level) || liquid.level <= INVALID_HEIGHT ||
            liquid.level <= liquid.depth_level || point.z < liquid.depth_level - 0.05f ||
            point.z > liquid.level + 0.75f)
            return false;
    }
    // The voxel water surface may lie slightly above the liquid plane. Every
    // intermediate sample must still be over water and above its bottom, and
    // the swim segment must not pass through a bank, wall or underwater roof.
    float eye = bot->GetCollisionHeight() * 0.5f;
    return bot->GetMap()->isInLineOfSight(from.x, from.y, from.z + eye,
        to.x, to.y, to.z + eye, bot->GetPhaseMask(), VMAP::ModelIgnoreFlags::Nothing);
}

bool MovementAction::ValidateGroundConnection(G3D::Vector3 const& from, G3D::Vector3 const& to)
{
    // Detour's voxel surface and the exact terrain surface can differ near
    // polygon edges. Connect only a short, supported, unobstructed segment.
    // This must not accept a shortcut over a cliff, hole, roof or dry bank.
    float distance = (to - from).length();
    if (distance > 3.0f)
        return false;
    float eye = bot->GetCollisionHeight() * 0.5f;
    if (!bot->GetMap()->isInLineOfSight(from.x, from.y, from.z + eye,
        to.x, to.y, to.z + eye, bot->GetPhaseMask(), VMAP::ModelIgnoreFlags::Nothing))
        return false;
    uint32 steps = std::max<uint32>(1, uint32(std::ceil(distance / 0.25f)));
    for (uint32 step = 0; step <= steps; ++step)
    {
        G3D::Vector3 point = from + (to - from) * (float(step) / float(steps));
        LiquidData liquid{};
        if (bot->GetMap()->GetLiquidStatus(bot->GetPhaseMask(), point.x, point.y, point.z,
            MAP_ALL_LIQUIDS, &liquid, bot->GetCollisionHeight()) != LIQUID_MAP_NO_WATER
            && std::isfinite(liquid.level) && liquid.level > liquid.depth_level
            && point.z >= liquid.depth_level - 0.05f && point.z <= liquid.level + 0.75f)
            continue; // A short shore transition may become supported by water.
        // GetMapHeight already raises the ray origin by Z_OFFSET_FIND_HEIGHT.
        // Raising it twice can put a supporting VMAP surface beyond the 4 m
        // search and select the terrain underneath a bridge instead.
        float ground = bot->GetMapHeight(point.x, point.y, point.z, true, 4.0f);
        if (!std::isfinite(ground) || ground <= INVALID_HEIGHT
            || std::fabs(point.z - ground) > 2.0f)
            return false;
    }
    return true;
}

Movement::PointsArray MovementAction::SearchForBestPath(float x, float y, float z, bool& usingNavigation, bool normalOnly, uint32 recoveryAttempt)
{
    usingNavigation = true;
    G3D::Vector3 const start(bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ());
    G3D::Vector3 const destination(x, y, z);
    if (!Trinity::IsValidMapCoord(start.x, start.y, start.z) || !Trinity::IsValidMapCoord(x, y, z))
    {
        LogNavigationResult("rejected", "invalid-coordinates", 0, 0, x, y, z, true);
        return {};
    }
    float const distance = (destination - start).length();
    if (distance <= 0.01f)
        return {};

    auto retainReplanOverlap = [](Movement::PointsArray& points)
    {
        // Restart before, rather than exactly on, a point-buffer boundary.
        // Nearest-poly selection at the last smoothed point can choose an
        // adjacent isolated layer even though the original corridor crossed
        // it. Keeping a short validated overlap lets the next spline carry the
        // bot through that boundary before another independent query starts.
        constexpr float ReplanOverlap = 8.0f;
        if (points.size() <= 2)
            return;
        float overlap = 0.0f;
        size_t end = points.size() - 1;
        while (end > 1 && overlap < ReplanOverlap)
        {
            overlap += (points[end] - points[end - 1]).length();
            --end;
        }
        points.resize(end + 1);
    };

    // Nearby underwater gameplay is three-dimensional. A verified swim inside
    // the liquid volume need not climb to the surface just to reach its target.
    if (!recoveryAttempt && bot->IsUnderWater() && (bot->GetMap()->GetLiquidStatus(bot->GetPhaseMask(), x, y, z,
        MAP_ALL_LIQUIDS, nullptr, bot->GetCollisionHeight()) & LIQUID_MAP_UNDER_WATER)
        && ValidateWaterConnection(start, destination))
        return {start, destination};

    uint32 const limit = std::clamp<uint32>(sPlayerbotAIConfig->navigationMaxAttempts, 1, 10);
    uint32 attempts = 0;
    uint32 lastType = PATHFIND_BLANK;
    char const* reason = "no-path";
    bool unavailable = false;
    bool startBridge = false;
    bool avoidLiquids = false;
    bool hasObstruction = false;
    G3D::Vector3 obstruction;
    NavigationDetourState& detour = AI_VALUE(LastMovement&, "last movement").navigationDetour;
    uint32 const now = getMSTime();
    if (detour.mapId != bot->GetMapId() || detour.instanceId != bot->GetInstanceId()
        || (detour.goal - destination).length() > 10.0f || getMSTimeDiff(detour.updatedAt, now) > 60000)
    {
        detour = {};
        detour.mapId = bot->GetMapId();
        detour.instanceId = bot->GetInstanceId();
        detour.goal = destination;
    }
    auto rememberContinuation = [&](Movement::PointsArray const& points)
    {
        detour.continuation.assign(points.begin(), points.end());
        detour.updatedAt = now;
    };
    auto query = [&](G3D::Vector3 const& from, G3D::Vector3 const& to, bool completeOnly) -> Movement::PointsArray
    {
        if (attempts >= limit)
            return {};
        ++attempts;
        // Private bounded query: never resize/mutate the shared NPC query.
        PathGenerator gen(bot, 4096);
        // A deeply submerged start still needs a corridor to the shore.
        // Connect to its water polygon with a checked swimming segment below,
        // instead of letting the core replace the whole route with a shortcut.
        gen.SetUseWaterShortcut(false);
        gen.SetTravelSpeeds(bot->GetSpeed(MOVE_RUN), avoidLiquids ? 0.01f : bot->GetSpeed(MOVE_SWIM));
        uint32 const queryStart = getMSTime();
        bool const calculated = gen.CalculatePath(to.x, to.y, to.z, false, false, false, &from);
        PathType const type = gen.GetPathType();
        lastType = type;
        reason = gen.GetPathFailureReason();
        if (std::string(reason) == "unsafe-surface-normalization" || std::string(reason) == "smoothing-loop")
            avoidLiquids = true;
        // No amount of waypoint searching can repair a missing map or query.
        unavailable = !gen.HasNavigationData() || (type & PATHFIND_NOT_USING_PATH);
        Movement::PointsArray points = gen.GetPath();
        if (std::string(reason) == "path-body-obstructed" && !points.empty())
        {
            obstruction = points.back();
            hasObstruction = true;
            // A water corridor can approach a bridge/bank from below even
            // though a land corridor is connected. Retry with land preference.
            if (bot->IsInWater() || bot->IsUnderWater())
                avoidLiquids = true;
        }
        startBridge = false;
        if (!points.empty() && ((type & PATHFIND_FARFROMPOLY_START) || (points.front() - from).length() > 1.0f))
            startBridge = ValidateWaterConnection(from, points.front());
        TC_LOG_DEBUG("playerbots.navigation", "bot={} map={} instance={} attempt={}/{} from=({},{},{}) to=({},{},{}) calculated={} pathType={} queryStatus={} queryNodes={} reason={} points={} startOffset={} endOffset={} progress={} queryMs={}",
            bot->GetGUID().GetCounter(), bot->GetMapId(), bot->GetInstanceId(), attempts, limit,
            from.x, from.y, from.z, to.x, to.y, to.z, calculated, uint32(type), gen.GetPathQueryStatus(), gen.GetPathQueryNodeLimit(), reason, points.size(),
            points.empty() ? -1.0f : (points.front() - from).length(),
            points.empty() ? -1.0f : (points.back() - to).length(),
            points.empty() ? -1.0f : (points.back() - from).length(), getMSTimeDiff(queryStart, getMSTime()));
        if (!calculated || !(type & (PATHFIND_NORMAL | PATHFIND_INCOMPLETE | PATHFIND_SHORT)) ||
            (type & (PATHFIND_NOPATH | PATHFIND_SHORTCUT | PATHFIND_NOT_USING_PATH))
            || ((type & PATHFIND_FARFROMPOLY_START) && !startBridge))
            return {};
        if (points.size() < 2 || std::any_of(points.begin(), points.end(), [](G3D::Vector3 const& point)
            { return !Trinity::IsValidMapCoord(point.x, point.y, point.z); }))
        {
            reason = "invalid-or-empty-path";
            return {};
        }
        if ((points.front() - from).length() > 0.1f && !startBridge)
        {
            if (!ValidateGroundConnection(from, points.front()))
            {
                reason = "path-start-mismatch";
                return {};
            }
            points.insert(points.begin(), from);
        }
        if ((points.front() - from).length() > 0.1f && startBridge)
            points.insert(points.begin(), from);
        if ((points.back() - from).length() <= 0.01f)
        {
            reason = "path-no-progress";
            return {};
        }
        bool const bridgedComplete = startBridge && !(type & PATHFIND_FARFROMPOLY_END)
            && (points.back() - to).length() <= 1.0f;
        if (completeOnly && (((type & PATHFIND_INCOMPLETE) && !bridgedComplete)
            || (type & (PATHFIND_SHORT | PATHFIND_FARFROMPOLY_END)) ||
            (points.back() - to).length() > 1.0f))
        {
            if (std::string(reason) == "none")
                reason = "destination-not-reached";
            return {};
        }
        return points;
    };

    Movement::PointsArray partial = query(start, destination, false);
    if (partial.empty() && avoidLiquids && attempts < limit)
        partial = query(start, destination, false);
    uint32 const primaryType = lastType;
    bool const primaryStartBridge = startBridge;
    if (!partial.empty() && (partial.back() - destination).length() > 1.0f && std::string(reason) == "none")
        reason = "destination-not-reached";
    char const* const primaryReason = reason;
    bool const primaryComplete = !partial.empty() && !(primaryType & (PATHFIND_SHORT | PATHFIND_FARFROMPOLY_END))
        && (!(primaryType & PATHFIND_INCOMPLETE) || primaryStartBridge)
        && (partial.back() - destination).length() <= 1.0f;
    if (!recoveryAttempt && primaryComplete)
    {
        detour.continuation.clear();
        return partial;
    }
    if (!recoveryAttempt && !partial.empty() && (primaryType & PATHFIND_SHORT))
    {
        retainReplanOverlap(partial);
        rememberContinuation(partial);
        LogNavigationResult("partial-route", primaryReason, primaryType, attempts, x, y, z, false);
        return partial;
    }

    // A validated partial spline can finish beside an overlapping or isolated
    // navmesh layer. If the next query cannot safely connect its actual start
    // to Detour's projected start, walk backwards over the remembered spline
    // and retry from an earlier point. This is not a direct fallback: every
    // retreat segment came from the preceding validated route and is checked
    // again, while every forward continuation is a normal bounded mmap query.
    if (!recoveryAttempt && partial.empty() && std::string(primaryReason) == "path-start-mismatch"
        && detour.continuation.size() >= 2 && (detour.continuation.back() - start).length() <= 1.5f)
    {
        Movement::PointsArray retreat{start};
        float retreatDistance = 0.0f;
        for (size_t index = detour.continuation.size() - 1; index > 0 && attempts < limit; --index)
        {
            G3D::Vector3 const& candidate = detour.continuation[index - 1];
            float const step = (retreat.back() - candidate).length();
            if (step <= 0.01f)
                continue;
            if (!ValidateGroundConnection(retreat.back(), candidate))
                break;
            retreat.push_back(candidate);
            retreatDistance += step;
            if (retreatDistance < 4.0f)
                continue;

            Movement::PointsArray continuation = query(candidate, destination, false);
            if (continuation.empty())
                continue;
            bool const continuationComplete = !(lastType & (PATHFIND_SHORT | PATHFIND_FARFROMPOLY_END))
                && (!(lastType & PATHFIND_INCOMPLETE) || startBridge)
                && (continuation.back() - destination).length() <= 1.0f;
            if (!continuationComplete && !(lastType & PATHFIND_SHORT))
                continue;
            if ((retreat.back() - continuation.front()).length() > 0.1f)
                continue;

            retreat.insert(retreat.end(), continuation.begin() + 1, continuation.end());
            bool const partialContinuation = !continuationComplete;
            bool const truncated = retreat.size() > MAX_POINT_PATH_LENGTH;
            if (truncated)
                retreat.resize(MAX_POINT_PATH_LENGTH);
            if (truncated || partialContinuation)
                retainReplanOverlap(retreat);
            if (truncated || partialContinuation)
                rememberContinuation(retreat);
            else
                detour.continuation.clear();
            LogNavigationResult(partialContinuation ? "partial-continuation-retreat-route"
                : "continuation-retreat-route", primaryReason, primaryType, attempts, x, y, z, false);
            return retreat;
        }
    }

    // Detour already searches connected polygons. These are distinct two-leg
    // searches, useful for local mesh/smoothing failures or query-node limits,
    // not repeated calls with identical start/end coordinates.
    // A blocked segment can be far ahead of the starting point. Place the
    // alternatives beside that obstruction, not beside the already safe start.
    bool const aroundObstruction = hasObstruction;
    G3D::Vector3 const origin = aroundObstruction ? obstruction : start;
    Movement::PointsArray bypass;
    float bypassRemaining = distance + 16.0f;
    float dx = x - origin.x;
    float dy = y - origin.y;
    float horizontal = std::sqrt(dx * dx + dy * dy);
    if (aroundObstruction && horizontal <= 0.1f)
    {
        // The last blocked segment may end at the destination itself. Keep
        // the detour centred on the obstacle, using the approach direction
        // when obstacle-to-goal cannot define a stable horizontal direction.
        dx = x - start.x;
        dy = y - start.y;
        horizontal = std::sqrt(dx * dx + dy * dy);
    }
    if (!unavailable && horizontal > 0.1f && !bot->GetTransport())
    {
        // Height-invalid candidates do not spend a path query. Inspect at most
        // the finite obstruction ring, while keeping the expensive query budget.
        uint32 const candidateLimit = aroundObstruction && !recoveryAttempt ? 32 : limit;
        for (uint32 candidate = 0; candidate < candidateLimit && attempts < limit; ++candidate)
        {
            // Planning can fail before a movement generator is launched, so
            // the running-spline recovery counter cannot advance this search.
            // Rotate bounded lateral candidates across those failed calls too.
            uint32 const variant = recoveryAttempt ? candidate + recoveryAttempt * limit
                : (candidate + detour.nextVariant) % 32;
            uint32 const lateralVariant = recoveryAttempt ? variant : variant % 16;
            float forward = aroundObstruction ? -2.0f : std::min(horizontal * 0.5f, 16.0f);
            float side = (lateralVariant % 2 ? -1.0f : 1.0f) * (8.0f + 8.0f * (lateralVariant / 2));
            if (aroundObstruction && !recoveryAttempt)
            {
                // A shallow pool or concave bank can require leaving in the
                // opposite direction first. Lateral-only candidates cannot
                // find that exit, regardless of how far sideways they search.
                static constexpr float forwardFactors[] = {0, 0, -0.707107f, -0.707107f, 0.707107f, 0.707107f, -1, 1};
                static constexpr float sideFactors[] = {1, -1, 0.707107f, -0.707107f, 0.707107f, -0.707107f, 0, 0};
                // Try both sides at increasing radii before changing direction.
                // Spending every query on the 8 m ring repeatedly crosses long
                // fences, even when a wider two-leg corridor is unobstructed.
                uint32 const direction = (variant / 8) * 2 + variant % 2;
                float const radius = 8.0f * float(1u << ((variant % 8) / 2));
                forward += forwardFactors[direction] * radius;
                side = sideFactors[direction] * radius;
            }
            float const wx = origin.x + (dx * forward - dy * side) / horizontal;
            float const wy = origin.y + (dy * forward + dx * side) / horizontal;
            float wz = bot->GetMapHeight(wx, wy, origin.z + (aroundObstruction ? 2.0f : 8.0f),
                true, aroundObstruction ? 4.0f : 50.0f);
            if (bot->CanSwim())
            {
                LiquidData liquid{};
                if (bot->GetMap()->GetLiquidStatus(bot->GetPhaseMask(), wx, wy, wz,
                    MAP_ALL_LIQUIDS, &liquid, bot->GetCollisionHeight()) != LIQUID_MAP_NO_WATER
                    && std::isfinite(liquid.level) && liquid.level > liquid.depth_level)
                {
                    // Detour's liquid corridor is at the water plane. Asking
                    // for the river bottom marks a valid bypass FARFROMPOLY_END.
                    // The path normalizer supplies the swimmer's feet height.
                    wz = std::max(wz, liquid.level);
                }
            }
            if (wz == INVALID_HEIGHT || !Trinity::IsValidMapCoord(wx, wy, wz) || std::fabs(wz - origin.z) > 8.0f)
                continue;
            Movement::PointsArray first = query(start, {wx, wy, wz}, false);
            if (first.empty())
                continue;
            if (aroundObstruction && (lastType & PATHFIND_SHORT))
            {
                // A long, collision-free leg toward the bypass may itself
                // fill the point buffer. Replan from its validated endpoint.
                retainReplanOverlap(first);
                rememberContinuation(first);
                LogNavigationResult("partial-alternative-route", reason, lastType, attempts, x, y, z, false);
                return first;
            }
            G3D::Vector3 const waypoint(wx, wy, wz);
            // A waypoint selected from ground height can be below the water
            // surface corridor. Accept that vertical adjustment only inside
            // a continuous, unobstructed liquid volume at the same XY.
            bool const reachedWaypoint = (first.back() - waypoint).length() <= 1.0f
                || (std::hypot(first.back().x - wx, first.back().y - wy) <= 1.0f
                    && ValidateWaterConnection(waypoint, first.back()));
            if ((lastType & (PATHFIND_INCOMPLETE | PATHFIND_SHORT | PATHFIND_FARFROMPOLY_END))
                || !reachedWaypoint)
                continue;
            // Several separate obstacles may lie on the remaining corridor.
            // Retain a fully validated bypass leg while looking for a complete
            // alternative. It must end clear of the original obstruction and
            // away from recent origins. A bounded retreat is necessary when
            // the first part of a real obstacle bypass leads away from the goal.
            float const remaining = (first.back() - destination).length();
            if (aroundObstruction && remaining < bypassRemaining && detour.origins.size() < 16
                && (first.back() - origin).length() >= 4.0f && (first.back() - start).length() >= 4.0f
                && std::none_of(detour.origins.begin(), detour.origins.end(), [&](G3D::Vector3 const& previous)
                    { return (first.back() - previous).length() < 4.0f; }))
            {
                bypass = first;
                bypassRemaining = remaining;
            }
            // A complete alternative needs a second query. If failed first
            // legs used the budget unevenly, do not discard the final allowed
            // first-leg query; a validated obstruction bypass can still move.
            if (attempts >= limit)
                continue;
            // Use the first route's actual endpoint, not a theoretical waypoint.
            Movement::PointsArray second = query(first.back(), destination, false);
            if (second.empty())
                continue;
            bool const secondComplete = !(lastType & (PATHFIND_SHORT | PATHFIND_FARFROMPOLY_END))
                && (!(lastType & PATHFIND_INCOMPLETE) || startBridge)
                && (second.back() - destination).length() <= 1.0f;
            // Only an explicitly bounded, validated prefix is a usable
            // truncated second leg; a mesh-hole corridor is not a detour.
            if (!secondComplete && !(lastType & PATHFIND_SHORT))
                continue;
            if ((first.back() - second.front()).length() > 0.1f)
            {
                reason = "discontinuous-alternative";
                continue;
            }
            first.insert(first.end(), second.begin() + 1, second.end());
            bool const partialSecond = !secondComplete;
            if (first.size() > MAX_POINT_PATH_LENGTH || partialSecond)
            {
                // Both legs are validated. Execute their bounded prefix and
                // replan from its endpoint, as for a normal partial corridor.
                // Never replace the omitted tail with a straight segment.
                if (first.size() > MAX_POINT_PATH_LENGTH)
                    first.resize(MAX_POINT_PATH_LENGTH);
                retainReplanOverlap(first);
                rememberContinuation(first);
                LogNavigationResult("partial-alternative-route", partialSecond ? reason : "path-point-limit", primaryType, attempts, x, y, z, false);
                return first;
            }
            detour.continuation.clear();
            LogNavigationResult("alternative-route", primaryReason, primaryType, attempts, x, y, z, false);
            return first;
        }
    }
    if (!bypass.empty())
    {
        detour.origins.push_back(start);
        detour.updatedAt = now;
        detour.nextVariant = 0;
        rememberContinuation(bypass);
        LogNavigationResult("partial-alternative-route", "validated-obstacle-bypass", primaryType, attempts, x, y, z, false);
        return bypass;
    }
    detour.nextVariant = (detour.nextVariant + 2) % 32;
    detour.updatedAt = now;
    if (!recoveryAttempt && !partial.empty() && (partial.back() - destination).length() + 0.1f < distance)
    {
        rememberContinuation(partial);
        LogNavigationResult("partial-route", primaryReason, primaryType, attempts, x, y, z, true);
        return partial;
    }
    // Preserve callers' existing navigation-only safety contract (e.g. flee).
    if (normalOnly || bot->GetTransport())
    {
        LogNavigationResult("rejected", reason, lastType, attempts, x, y, z, true);
        return {};
    }
    usingNavigation = false;
    // A final no-navigation fallback remains available, but only as a short,
    // collision-checked step. Re-running normal route selection from the new
    // position is safer than a long spline that can cross terrain or geometry.
    G3D::Vector3 fallback = destination;
    constexpr float DirectFallbackStep = 8.0f;
    if (distance > DirectFallbackStep)
        fallback = start + (destination - start) * (DirectFallbackStep / distance);
    float fallbackX = fallback.x;
    float fallbackY = fallback.y;
    float fallbackZ = fallback.z;
    if (!bot->GetMap()->CheckCollisionAndGetValidCoords(bot, start.x, start.y, start.z,
        fallbackX, fallbackY, fallbackZ) || (G3D::Vector3(fallbackX, fallbackY, fallbackZ) - start).length() <= 0.01f)
    {
        usingNavigation = true;
        LogNavigationResult("rejected", "unsafe-direct-fallback", primaryType, attempts, x, y, z, true);
        return {};
    }
    LogNavigationResult("fallback-direct", primaryReason, primaryType, attempts, x, y, z, true);
    return {start, {fallbackX, fallbackY, fallbackZ}};
}

bool MovementAction::MoveAway(Unit* target, float distance, bool backwards)
{
    if (!target)
    {
        return false;
    }
    float init_angle = target->GetAngle(bot);
    for (float delta = 0; delta <= M_PI / 2; delta += M_PI / 8)
    {
        float angle = init_angle + delta;
        float dx = bot->GetPositionX() + cos(angle) * distance;
        float dy = bot->GetPositionY() + sin(angle) * distance;
        float dz = bot->GetPositionZ();
        bool exact = true;
        if (!bot->GetMap()->CheckCollisionAndGetValidCoords(bot, bot->GetPositionX(), bot->GetPositionY(),
            bot->GetPositionZ(), dx, dy, dz))
        {
            // disable prediction if position is invalid
            dx = bot->GetPositionX() + cos(angle) * distance;
            dy = bot->GetPositionY() + sin(angle) * distance;
            dz = bot->GetPositionZ();
            exact = false;
        }
        if (MoveTo(target->GetMapId(), dx, dy, dz, false, false, true, exact, MovementPriority::MOVEMENT_COMBAT, false, backwards))
        {
            return true;
        }
        if (delta == 0)
        {
            continue;
        }
        exact = true;
        angle = init_angle - delta;
        dx = bot->GetPositionX() + cos(angle) * distance;
        dy = bot->GetPositionY() + sin(angle) * distance;
        dz = bot->GetPositionZ();
        if (!bot->GetMap()->CheckCollisionAndGetValidCoords(bot, bot->GetPositionX(), bot->GetPositionY(),
            bot->GetPositionZ(), dx, dy, dz))
        {
            // disable prediction if position is invalid
            dx = bot->GetPositionX() + cos(angle) * distance;
            dy = bot->GetPositionY() + sin(angle) * distance;
            dz = bot->GetPositionZ();
            exact = false;
        }
        if (MoveTo(target->GetMapId(), dx, dy, dz, false, false, true, exact, MovementPriority::MOVEMENT_COMBAT, false, backwards))
        {
            return true;
        }
    }
    return false;
}

bool MovementAction::Move(float angle, float distance)
{
    float x = bot->GetPositionX() + cos(angle) * distance;
    float y = bot->GetPositionY() + sin(angle) * distance;

    //TODO do we need GetMapWaterOrGroundLevel() if we're using CheckCollisionAndGetValidCoords() ?
    float z = bot->GetMapWaterOrGroundLevel(x, y, bot->GetPositionZ());
    if (z == -100000.0f || z == -200000.0f)
        z = bot->GetPositionZ();
    if (!bot->GetMap()->CheckCollisionAndGetValidCoords(bot, bot->GetPositionX(), bot->GetPositionY(),
        bot->GetPositionZ(), x, y, z, false))
        return false;

    return MoveTo(bot->GetMapId(), x, y, z);
}

// just calculates average position of group and runs away from that position
bool MovementAction::MoveFromGroup(float distance)
{
    if (Group* group = bot->GetGroup())
    {
        uint32 mapId = bot->GetMapId();
        float closestDist = FLT_MAX;
        float x = 0.0f;
        float y = 0.0f;
        uint32 count = 0;

        for (GroupReference* gref = group->GetFirstMember(); gref; gref = gref->next())
        {
            Player* player = gref->GetSource();
            if (!player || player == bot || !player->IsAlive() || player->GetMapId() != mapId)
                continue;
            float dist = bot->GetDistance2d(player);
            if (closestDist > dist)
                closestDist = dist;
            x += player->GetPositionX();
            y += player->GetPositionY();
            count++;
        }

        if (count && closestDist < distance)
        {
            x /= count;
            y /= count;
            // x and y are now average position of the group members
            float angle = bot->GetAngle(x, y) + M_PI;
            return Move(angle, distance - closestDist);
        }
    }
    return false;
}

bool MovementAction::Flee(Unit* target)
{
    return true;
    //Player* master = GetMaster();
    //if (!target)
    //    target = master;

    //if (!target)
    //    return false;

    //if (!IsMovingAllowed())
    //{
    //    botAI->TellError("I am stuck while fleeing");
    //    return false;
    //}

    //bool foundFlee = false;
    //time_t lastFlee = AI_VALUE(LastMovement&, "last movement").lastFlee;
    //time_t now = time(0);
    //uint32 fleeDelay = urand(2, sPlayerbotAIConfig->returnDelay / 1000);

    //if (lastFlee)
    //{
    //    if ((now - lastFlee) <= fleeDelay)
    //    {
    //        return false;
    //    }
    //}

    //HostileReference* ref = target->GetThreatManager().getCurrentVictim();
    //if (ref && ref->getTarget() == bot)  // bot is target - try to flee to tank or master
    //{
    //    if (Group* group = bot->GetGroup())
    //    {
    //        Unit* fleeTarget = nullptr;
    //        float fleeDistance = sPlayerbotAIConfig->sightDistance;

    //        for (GroupReference* gref = group->GetFirstMember(); gref; gref = gref->next())
    //        {
    //            Player* player = gref->GetSource();
    //            if (!player || player == bot || !player->IsAlive())
    //                continue;

    //            if (PlayerBotSpec::IsTank(player))
    //            {
    //                float distanceToTank = sServerFacade->GetDistance2d(bot, player);
    //                float distanceToTarget = sServerFacade->GetDistance2d(bot, target);
    //                if (distanceToTank < fleeDistance)
    //                {
    //                    fleeTarget = player;
    //                    fleeDistance = distanceToTank;
    //                }
    //            }
    //        }

    //        if (fleeTarget)
    //            foundFlee = MoveNear(fleeTarget);

    //        if ((!fleeTarget || !foundFlee) && master)
    //        {
    //            foundFlee = MoveNear(master);
    //        }
    //    }
    //}
    //else  // bot is not targeted, try to flee dps/healers
    //{
    //    bool isHealer = PlayerBotSpec::IsHeal(bot);
    //    bool isDps = !isHealer && !PlayerBotSpec::IsTank(bot);
    //    bool isTank = PlayerBotSpec::IsTank(bot);
    //    bool needHealer = !isHealer && AI_VALUE2(uint8, "health", "self target") < 50;
    //    bool isRanged = PlayerBotSpec::IsRanged(bot);

    //    Group* group = bot->GetGroup();
    //    if (group)
    //    {
    //        Unit* fleeTarget = nullptr;
    //        float fleeDistance = botAI->GetRange("shoot") * 1.5f;
    //        Unit* spareTarget = nullptr;
    //        float spareDistance = botAI->GetRange("shoot") * 2.0f;
    //        std::vector<Unit*> possibleTargets;

    //        for (GroupReference* gref = group->GetFirstMember(); gref; gref = gref->next())
    //        {
    //            Player* player = gref->GetSource();
    //            if (!player || player == bot || !player->IsAlive())
    //                continue;

    //            if ((isHealer && PlayerBotSpec::IsHeal(player)) || needHealer)
    //            {
    //                float distanceToHealer = sServerFacade->GetDistance2d(bot, player);
    //                float distanceToTarget = sServerFacade->GetDistance2d(player, target);
    //                if (distanceToHealer < fleeDistance &&
    //                    distanceToTarget >(botAI->GetRange("shoot") / 2 + sPlayerbotAIConfig->followDistance) &&
    //                    (needHealer || player->IsWithinLOSInMap(target)))
    //                {
    //                    fleeTarget = player;
    //                    fleeDistance = distanceToHealer;
    //                    possibleTargets.push_back(fleeTarget);
    //                }
    //            }
    //            else if (isRanged && PlayerBotSpec::IsRanged(player))
    //            {
    //                float distanceToRanged = sServerFacade->GetDistance2d(bot, player);
    //                float distanceToTarget = sServerFacade->GetDistance2d(player, target);
    //                if (distanceToRanged < fleeDistance &&
    //                    distanceToTarget >(botAI->GetRange("shoot") / 2 + sPlayerbotAIConfig->followDistance) &&
    //                    player->IsWithinLOSInMap(target))
    //                {
    //                    fleeTarget = player;
    //                    fleeDistance = distanceToRanged;
    //                    possibleTargets.push_back(fleeTarget);
    //                }
    //            }
    //            // remember any group member in case no one else found
    //            float distanceToFlee = sServerFacade->GetDistance2d(bot, player);
    //            float distanceToTarget = sServerFacade->GetDistance2d(player, target);
    //            if (distanceToFlee < spareDistance &&
    //                distanceToTarget >(botAI->GetRange("shoot") / 2 + sPlayerbotAIConfig->followDistance) &&
    //                player->IsWithinLOSInMap(target))
    //            {
    //                spareTarget = player;
    //                spareDistance = distanceToFlee;
    //                possibleTargets.push_back(fleeTarget);
    //            }
    //        }

    //        if (!possibleTargets.empty())
    //            fleeTarget = possibleTargets[urand(0, possibleTargets.size() - 1)];

    //        if (!fleeTarget)
    //            fleeTarget = spareTarget;

    //        if (fleeTarget)
    //            foundFlee = MoveNear(fleeTarget);

    //        if ((!fleeTarget || !foundFlee) && master && master->IsAlive() && master->IsWithinLOSInMap(target))
    //        {
    //            float distanceToTarget = sServerFacade->GetDistance2d(master, target);
    //            if (distanceToTarget > (botAI->GetRange("shoot") / 2 + sPlayerbotAIConfig->followDistance))
    //                foundFlee = MoveNear(master);
    //        }
    //    }
    //}

    //if ((foundFlee || lastFlee) && bot->GetGroup())
    //{
    //    if (!lastFlee)
    //    {
    //        AI_VALUE(LastMovement&, "last movement").lastFlee = now;
    //    }
    //    else
    //    {
    //        if ((now - lastFlee) > fleeDelay)
    //        {
    //            AI_VALUE(LastMovement&, "last movement").lastFlee = 0;
    //        }
    //        else
    //            return false;
    //    }
    //}

    //FleeManager manager(bot, botAI->GetRange("flee"), bot->GetAngle(target) + M_PI);
    //if (!manager.isUseful())
    //    return false;

    //float rx, ry, rz;
    //if (!manager.CalculateDestination(&rx, &ry, &rz))
    //{
    //    botAI->TellError("Nowhere to flee");
    //    return false;
    //}

    //bool result = MoveTo(target->GetMapId(), rx, ry, rz);

    //if (result)
    //    AI_VALUE(LastMovement&, "last movement").lastFlee = time(nullptr);

    //return result;
}

Position MovementAction::BestPositionForMeleeToFlee(Position pos, float radius)
{
    Unit* currentTarget = AI_VALUE(Unit*, "current target");
    std::vector<CheckAngle> possibleAngles;
    if (currentTarget)
    {
        // Normally, move to left or right is the best position
        bool isTanking = (currentTarget->CanFreeMove()) && (currentTarget->GetVictim() == bot);
        float angle = bot->GetAngle(currentTarget);
        float angleLeft = angle + (float)M_PI / 2;
        float angleRight = angle - (float)M_PI / 2;
        possibleAngles.push_back({ angleLeft, false });
        possibleAngles.push_back({ angleRight, false });
        possibleAngles.push_back({ angle, true });
        if (isTanking)
        {
            possibleAngles.push_back({ angle + (float)M_PI, false });
            possibleAngles.push_back({ bot->GetAngle(&pos) - (float)M_PI, false });
        }
    }
    else
    {
        float angleTo = bot->GetAngle(&pos) - (float)M_PI;
        possibleAngles.push_back({ angleTo, false });
    }
    float farestDis = 0.0f;
    Position bestPos;
    for (CheckAngle& checkAngle : possibleAngles)
    {
        float angle = checkAngle.angle;
        std::list<FleeInfo>& infoList = AI_VALUE(std::list<FleeInfo>&, "recently flee info");
        if (!CheckLastFlee(angle, infoList))
        {
            continue;
        }
        bool strict = checkAngle.strict;
        float fleeDis = std::min(radius + 1.0f, sPlayerbotAIConfig->fleeDistance);
        float dx = bot->GetPositionX() + cos(angle) * fleeDis;
        float dy = bot->GetPositionY() + sin(angle) * fleeDis;
        float dz = bot->GetPositionZ();
        if (!bot->GetMap()->CheckCollisionAndGetValidCoords(bot, bot->GetPositionX(), bot->GetPositionY(),
            bot->GetPositionZ(), dx, dy, dz))
        {
            continue;
        }
        Position fleePos{ dx, dy, dz };
        if (strict && currentTarget &&
            fleePos.GetExactDist(currentTarget) - currentTarget->GetCombatReach() >
            sPlayerbotAIConfig->tooCloseDistance &&
            bot->IsWithinMeleeRange(currentTarget))
        {
            continue;
        }
        if (pos.GetExactDist(fleePos) > farestDis)
        {
            farestDis = pos.GetExactDist(fleePos);
            bestPos = fleePos;
        }
    }
    if (farestDis > 0.0f)
    {
        return bestPos;
    }
    return Position();
}

Position MovementAction::BestPositionForRangedToFlee(Position pos, float radius)
{
    Unit* currentTarget = AI_VALUE(Unit*, "current target");
    std::vector<CheckAngle> possibleAngles;
    float angleToTarget = 0.0f;
    float angleFleeFromCenter = bot->GetAngle(&pos) - (float)M_PI;
    if (currentTarget)
    {
        // Normally, move to left or right is the best position
        angleToTarget = bot->GetAngle(currentTarget);
        float angleLeft = angleToTarget + (float)M_PI / 2;
        float angleRight = angleToTarget - (float)M_PI / 2;
        possibleAngles.push_back({ angleLeft, false });
        possibleAngles.push_back({ angleRight, false });
        possibleAngles.push_back({ angleToTarget + (float)M_PI, true });
        possibleAngles.push_back({ angleToTarget, true });
        possibleAngles.push_back({ angleFleeFromCenter, true });
    }
    else
    {
        possibleAngles.push_back({ angleFleeFromCenter, false });
    }
    float farestDis = 0.0f;
    Position bestPos;
    for (CheckAngle& checkAngle : possibleAngles)
    {
        float angle = checkAngle.angle;
        std::list<FleeInfo>& infoList = AI_VALUE(std::list<FleeInfo>&, "recently flee info");
        if (!CheckLastFlee(angle, infoList))
        {
            continue;
        }
        bool strict = checkAngle.strict;
        float fleeDis = std::min(radius + 1.0f, sPlayerbotAIConfig->fleeDistance);
        float dx = bot->GetPositionX() + cos(angle) * fleeDis;
        float dy = bot->GetPositionY() + sin(angle) * fleeDis;
        float dz = bot->GetPositionZ();
        if (!bot->GetMap()->CheckCollisionAndGetValidCoords(bot, bot->GetPositionX(), bot->GetPositionY(),
            bot->GetPositionZ(), dx, dy, dz))
        {
            continue;
        }
        Position fleePos{ dx, dy, dz };
        if (strict && currentTarget &&
            fleePos.GetExactDist(currentTarget) - currentTarget->GetCombatReach() > sPlayerbotAIConfig->spellDistance)
        {
            continue;
        }
        if (strict && currentTarget &&
            fleePos.GetExactDist(currentTarget) - currentTarget->GetCombatReach() <
            (sPlayerbotAIConfig->tooCloseDistance))
        {
            continue;
        }

        if (pos.GetExactDist(fleePos) > farestDis)
        {
            farestDis = pos.GetExactDist(fleePos);
            bestPos = fleePos;
        }
    }
    if (farestDis > 0.0f)
    {
        return bestPos;
    }
    return Position();
}

bool MovementAction::FleePosition(Position pos, float radius, uint32 minInterval)
{
    std::list<FleeInfo>& infoList = AI_VALUE(std::list<FleeInfo>&, "recently flee info");

    if (!infoList.empty() && infoList.back().timestamp + minInterval > getMSTime())
        return false;

    Position bestPos;
    if (PlayerBotSpec::IsMelee(bot))
    {
        bestPos = BestPositionForMeleeToFlee(pos, radius);
    }
    else
    {
        bestPos = BestPositionForRangedToFlee(pos, radius);
    }
    if (bestPos != Position())
    {
        if (MoveTo(bot->GetMapId(), bestPos.GetPositionX(), bestPos.GetPositionY(), bestPos.GetPositionZ(), false,
            false, true, false, MovementPriority::MOVEMENT_COMBAT))
        {
            uint32 curTS = getMSTime();
            while (!infoList.empty())
            {
                if (infoList.size() > 10 || infoList.front().timestamp + 5000 < curTS)
                {
                    infoList.pop_front();
                }
                else
                {
                    break;
                }
            }
            infoList.push_back({ pos, radius, bot->GetAngle(&bestPos), curTS });
            return true;
        }
    }
    return false;
}

bool MovementAction::CheckLastFlee(float curAngle, std::list<FleeInfo>& infoList)
{
    uint32 curTS = getMSTime();
    curAngle = Position::NormalizeOrientation(curAngle);
    while (!infoList.empty())
    {
        if (infoList.size() > 10 || infoList.front().timestamp + 5000 < curTS)
        {
            infoList.pop_front();
        }
        else
        {
            break;
        }
    }
    for (FleeInfo& info : infoList)
    {
        // more than 5 sec
        if (info.timestamp + 5000 < curTS)
        {
            continue;
        }
        float revAngle = Position::NormalizeOrientation(info.angle + M_PI);
        // angle too close
        if (fabs(revAngle - curAngle) < M_PI / 4)
        {
            return false;
        }
    }
    return true;
}

bool RunAwayAction::Execute(Event event) { return Flee(AI_VALUE(Unit*, "master target")); }

bool SetFacingTargetAction::Execute(Event event)
{
    Unit* target = AI_VALUE(Unit*, "current target");
    if (!target)
        return false;

    if (bot->HasUnitState(UNIT_STATE_IN_FLIGHT))
        return true;

    sServerFacade->SetFacingTo(bot, target);
    botAI->SetNextCheckDelay(sPlayerbotAIConfig->reactDelay);
    return true;
}

bool SetFacingTargetAction::isUseful()
{
    return !AI_VALUE2(bool, "facing", "current target");
}

bool SetFacingTargetAction::isPossible()
{
    if (bot->isFrozen() || bot->IsPolymorphed() || (bot->isDead() && !bot->HasPlayerFlag(PLAYER_FLAGS_GHOST)) ||
        bot->IsBeingTeleported() || bot->HasConfuseAura() || bot->IsCharmed() ||
        bot->HasStunAura() || bot->IsInFlight() ||
        bot->HasUnitState(UNIT_STATE_LOST_CONTROL))
        return false;

    return true;
}

bool MoveFromGroupAction::Execute(Event event)
{
    float distance = atoi(event.getParam().c_str());
    if (!distance)
        distance = 20.0f; // flee distance from config is too small for this
    return MoveFromGroup(distance);
}

bool FleeAction::Execute(Event event)
{
    return MoveAway(AI_VALUE(Unit*, "current target"), sPlayerbotAIConfig->fleeDistance, true);
}

bool FleeAction::isUseful()
{
    if (bot->GetCurrentSpell(CURRENT_CHANNELED_SPELL) != nullptr)
    {
        return false;
    }
    return true;
}

bool CombatFormationMoveAction::isUseful()
{
    if (getMSTime() - moveInterval < lastMoveTimer)
    {
        return false;
    }
    if (bot->GetCurrentSpell(CURRENT_CHANNELED_SPELL) != nullptr)
    {
        return false;
    }
    return true;
}

bool CombatFormationMoveAction::Execute(Event event)
{
    float dis = AI_VALUE(float, "disperse distance");
    if (dis <= 0.0f)
        return false;
    Player* playerToLeave = NearestGroupMember(dis);
    if (playerToLeave && bot->GetExactDist(playerToLeave) < dis)
    {
        //if (FleePosition(playerToLeave->GetPosition(), dis))
        {
            //lastMoveTimer = getMSTime();
        }
    }
    return false;
}

Position CombatFormationMoveAction::AverageGroupPos(float dis, bool ranged, bool self)
{
    float averageX = 0, averageY = 0, averageZ = 0;
    int cnt = 0;
    Group* group = bot->GetGroup();
    if (!group)
    {
        return Position();
    }
    Group::MemberSlotList const& groupSlot = group->GetMemberSlots();
    for (Group::member_citerator itr = groupSlot.begin(); itr != groupSlot.end(); itr++)
    {
        Player* member = ObjectAccessor::FindPlayer(itr->guid);
        if (!member)
            continue;

        if (!self && member == bot)
            continue;

        if (ranged && !PlayerBotSpec::IsRanged(member))
            continue;

        if (!member->IsAlive() || member->GetMapId() != bot->GetMapId() || member->IsCharmed() ||
            sServerFacade->GetDistance2d(bot, member) > dis)
            continue;

        averageX += member->GetPositionX();
        averageY += member->GetPositionY();
        averageZ += member->GetPositionZ();
    }
    averageX /= cnt;
    averageY /= cnt;
    averageZ /= cnt;
    return Position(averageX, averageY, averageZ);
}

float CombatFormationMoveAction::AverageGroupAngle(Unit* from, bool ranged, bool self)
{
    Group* group = bot->GetGroup();
    if (!from || !group)
    {
        return 0.0f;
    }
    // float average = 0.0f;
    float sumX = 0.0f;
    float sumY = 0.0f;
    int cnt = 0;
    Group::MemberSlotList const& groupSlot = group->GetMemberSlots();
    for (Group::member_citerator itr = groupSlot.begin(); itr != groupSlot.end(); itr++)
    {
        Player* member = ObjectAccessor::FindPlayer(itr->guid);
        if (!member)
            continue;

        if (!self && member == bot)
            continue;

        if (ranged && !PlayerBotSpec::IsRanged(member))
            continue;

        if (!member->IsAlive() || member->GetMapId() != bot->GetMapId() || member->IsCharmed() ||
            sServerFacade->GetDistance2d(bot, member) > sPlayerbotAIConfig->sightDistance)
            continue;

        cnt++;
        sumX += member->GetPositionX() - from->GetPositionX();
        sumY += member->GetPositionY() - from->GetPositionY();
    }
    if (cnt == 0)
        return 0.0f;

    // unnecessary division
    // sumX /= cnt;
    // sumY /= cnt;

    return atan2(sumY, sumX);
}

Position CombatFormationMoveAction::GetNearestPosition(const std::vector<Position>& positions)
{
    if (positions.empty())
        return {};

    Position result = positions.front();
    for (const Position& pos : positions)
    {
        if (bot->GetExactDist(pos) < bot->GetExactDist(result))
            result = pos;
    }
    return result;
}

Player* CombatFormationMoveAction::NearestGroupMember(float dis)
{
    float nearestDis = 10000.0f;
    Player* result = nullptr;
    Group* group = bot->GetGroup();
    if (!group)
    {
        return result;
    }
    Group::MemberSlotList const& groupSlot = group->GetMemberSlots();
    for (Group::member_citerator itr = groupSlot.begin(); itr != groupSlot.end(); itr++)
    {
        Player* member = ObjectAccessor::FindPlayer(itr->guid);
        if (!member || !member->IsAlive() || member == bot || member->GetMapId() != bot->GetMapId() ||
            member->IsCharmed() || sServerFacade->GetDistance2d(bot, member) > dis)
            continue;
        if (nearestDis > bot->GetExactDist(member))
        {
            result = member;
            nearestDis = bot->GetExactDist(member);
        }
    }
    return result;
}

bool TankFaceAction::Execute(Event event)
{
    Unit* target = AI_VALUE(Unit*, "current target");
    if (!target)
        return false;

    if (!bot->GetGroup())
        return false;

    if (!bot->IsWithinMeleeRange(target) || target->isMoving())
        return false;

    if (!AI_VALUE2(bool, "has aggro", "current target"))
        return false;

    float averageAngle = AverageGroupAngle(target, true);

    if (averageAngle == 0.0f)
        return false;

    float deltaAngle = Position::NormalizeOrientation(averageAngle - target->GetAngle(bot));
    if (deltaAngle > M_PI)
        deltaAngle -= 2.0f * M_PI; // -PI..PI

    float tolerable = M_PI_2;

    if (fabs(deltaAngle) > tolerable)
        return false;

    float goodAngle1 = Position::NormalizeOrientation(averageAngle + M_PI * 3 / 5);
    float goodAngle2 = Position::NormalizeOrientation(averageAngle - M_PI * 3 / 5);

    // if dist < bot->GetMeleeRange(target) / 2, target will move backward
    float dist = std::max(bot->GetExactDist(target), bot->GetMeleeRange(target) / 2) - bot->GetCombatReach() - target->GetCombatReach();
    std::vector<Position> availablePos;
    for (float goodAngle : {goodAngle1, goodAngle2})
    {
        float x, y, z;
        target->GetNearPoint(bot, x, y, z, dist, goodAngle);
        if (!bot->GetMap()->CheckCollisionAndGetValidCoords(bot, bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ(),
            x, y, z))
            continue;

        // Collision projection can collapse a candidate onto the bot's XY
        // while leaving Z on the water surface. Tank facing needs horizontal
        // repositioning; a height-only change cannot turn the enemy away.
        if (bot->GetExactDist2d(x, y) <= CONTACT_DISTANCE)
            continue;

        std::list<FleeInfo>& infoList = AI_VALUE(std::list<FleeInfo>&, "recently flee info");
        Position pos(x, y, z);
        float angle = bot->GetAngle(&pos);
        if (CheckLastFlee(angle, infoList))
            availablePos.push_back(pos);
    }
    if (availablePos.empty())
        return false;
    Position nearest = GetNearestPosition(availablePos);
    return MoveTo(bot->GetMapId(), nearest.GetPositionX(), nearest.GetPositionY(), nearest.GetPositionZ(), false, false, false, true, MovementPriority::MOVEMENT_COMBAT);
}
