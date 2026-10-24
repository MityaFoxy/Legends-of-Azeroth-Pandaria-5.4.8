#include "FollowActions.h"

#include <cstddef>
#include <cmath>

#include "Event.h"
#include "Formations.h"
#include "GroupFollowFormation.h"
#include "PlayerbotSpec.h"
#include "LastMovementValue.h"
#include "PlayerbotAI.h"
#include "Playerbots.h"
#include "ServerFacade.h"
#include "SharedDefines.h"

bool FollowAction::UseGroupFollowFormation()
{
    Player* master = GetMaster();
    Formation* formation = AI_VALUE(Formation*, "formation");
    // Replace only default wandering follow; explicit player formations retain
    // their own targets and layout. Combat and BG keep their existing movement.
    return formation && formation->getName() == "chaos" && master && master != bot &&
        bot->GetGroup() && master->GetGroup() == bot->GetGroup() &&
        master->IsInWorld() && bot->IsInWorld() && master->GetMap() == bot->GetMap() &&
        master->InSamePhase(bot) && master->IsAlive() && bot->IsAlive() &&
        !bot->InBattleground() && !master->IsInCombat() && !bot->IsInCombat() &&
        botAI->GetState() == BOT_STATE_NON_COMBAT;
}

bool FollowAction::CanMoveInGroupFormation()
{
    Player* master = GetMaster();
    return master && !master->HasUnitState(UNIT_STATE_IN_FLIGHT) &&
        !bot->HasUnitState(UNIT_STATE_IN_FLIGHT) && !bot->GetVehicle() && !master->GetVehicle() &&
        !bot->GetTransport() && !master->GetTransport() &&
        !bot->IsNonMeleeSpellCasted(true, false, true) &&
        !botAI->HasStrategy("move from group", BOT_STATE_COMBAT) &&
        !botAI->HasStrategy("move from group", BOT_STATE_NON_COMBAT);
}

WorldLocation FollowAction::GetGroupFollowLocation()
{
    Player* master = GetMaster();
    bool const tank = PlayerBotSpec::IsTank(bot, true);
    std::size_t slot = 0;
    for (GroupReference* ref = bot->GetGroup()->GetFirstMember(); ref; ref = ref->next())
    {
        Player* member = ref->GetSource();
        if (member && member != master && member->IsInWorld() && member->IsAlive() &&
            member->GetMap() == bot->GetMap() && member->InSamePhase(bot) &&
            PlayerBotSpec::IsTank(member, true) == tank && member->GetGUID() < bot->GetGUID())
            ++slot;
    }

    auto const offset = GroupFollowFormation::GetOffset(tank, slot);
    float const orientation = master->GetOrientation();
    for (float scale : {1.0f, 0.5f, 0.25f})
    {
        float x = master->GetPositionX() + scale *
            (std::cos(orientation) * offset.forward - std::sin(orientation) * offset.sideways);
        float y = master->GetPositionY() + scale *
            (std::sin(orientation) * offset.forward + std::cos(orientation) * offset.sideways);
        float z = master->GetPositionZ();
        if (master->GetMap()->CheckCollisionAndGetValidCoords(master,
            master->GetPositionX(), master->GetPositionY(), master->GetPositionZ(), x, y, z))
            return WorldLocation(master->GetMapId(), x, y, z);
    }
    // No unchecked fallback to the master's exact position (which piles up bots).
    return Formation::NullLocation;
}

bool FollowAction::Execute(Event event)
{
    if (UseGroupFollowFormation())
    {
        if (!CanMoveInGroupFormation())
            return false;
        WorldLocation const loc = GetGroupFollowLocation();
        if (Formation::IsNullLocation(loc) ||
            bot->GetDistance(loc.GetPositionX(), loc.GetPositionY(), loc.GetPositionZ()) <= 1.0f)
            return false;
        return MoveTo(loc.GetMapId(), loc.GetPositionX(), loc.GetPositionY(), loc.GetPositionZ(),
            false, false, true, false, MovementPriority::MOVEMENT_NORMAL, true);
    }

    Formation* formation = AI_VALUE(Formation*, "formation");
    if (!formation)
        return false;
    std::string const target = formation->GetTargetName();

    bool moved = false;
    if (!target.empty())
    {
        moved = Follow(AI_VALUE(Unit*, target));
    }
    else
    {
        WorldLocation loc = formation->GetLocation();
        if (Formation::IsNullLocation(loc) || loc.GetMapId() == -1)
            return false;

        MovementPriority priority = botAI->GetState() == BOT_STATE_COMBAT ? MovementPriority::MOVEMENT_COMBAT : MovementPriority::MOVEMENT_NORMAL;
        moved = MoveTo(loc.GetMapId(), loc.GetPositionX(), loc.GetPositionY(), loc.GetPositionZ(), false, false, false,
            true, priority, true);
    }

    if (Pet* pet = bot->GetPet())
    {
        //botAI->PetFollow();
    }

    return moved;
}

bool FollowAction::isUseful()
{
    if (UseGroupFollowFormation())
    {
        if (!CanMoveInGroupFormation())
            return false;
        WorldLocation const loc = GetGroupFollowLocation();
        return !Formation::IsNullLocation(loc) &&
            bot->GetDistance(loc.GetPositionX(), loc.GetPositionY(), loc.GetPositionZ()) > 1.0f;
    }

    // move from group takes priority over follow as it's added and removed automatically
    // (without removing/adding follow)
    if (botAI->HasStrategy("move from group", BOT_STATE_COMBAT) ||
        botAI->HasStrategy("move from group", BOT_STATE_NON_COMBAT))
        return false;

    if (bot->GetCurrentSpell(CURRENT_CHANNELED_SPELL) != nullptr)
        return false;

    Formation* formation = AI_VALUE(Formation*, "formation");
    if (!formation)
        return false;

    std::string const target = formation->GetTargetName();

    Unit* fTarget = nullptr;
    if (!target.empty())
        fTarget = AI_VALUE(Unit*, target);
    else
        fTarget = AI_VALUE(Unit*, "master target");

    if (fTarget)
    {
        if (fTarget->HasUnitState(UNIT_STATE_IN_FLIGHT))
            return false;

        if (!CanDeadFollow(fTarget))
            return false;

        if (fTarget->GetGUID() == bot->GetGUID())
            return false;
    }

    float distance = 0.f;
    if (!target.empty())
    {
        distance = AI_VALUE2(float, "distance", target);
    }
    else
    {
        WorldLocation loc = formation->GetLocation();
        if (Formation::IsNullLocation(loc) || bot->GetMapId() != loc.GetMapId())
            return false;

        distance = bot->GetDistance(loc.GetPositionX(), loc.GetPositionY(), loc.GetPositionZ());
    }

    return sServerFacade->IsDistanceGreaterThan(distance, formation->GetMaxDistance());
}

bool FollowAction::CanDeadFollow(Unit* target)
{
    // Move to corpse when dead and player is alive or not a ghost.
    if (!bot->IsAlive() && (target->IsAlive() || !target->HasFlag(PLAYER_FIELD_PLAYER_FLAGS, PLAYER_FLAGS_GHOST)))
        return false;

    return true;
}

bool FleeToMasterAction::Execute(Event event)
{
    Unit* fTarget = AI_VALUE(Unit*, "master target");
    bool canFollow = Follow(fTarget);
    if (!canFollow)
    {
        // botAI->SetNextCheckDelay(5000);
        return false;
    }

    WorldPosition targetPos(fTarget);
    WorldPosition bosPos(bot);
    float distance = bosPos.fDist(targetPos);

    if (distance < sPlayerbotAIConfig->reactDistance * 3)
    {
        if (!urand(0, 3))
            botAI->TellMaster("I am close, wait for me!");
    }
    else if (distance < 1000)
    {
        if (!urand(0, 10))
            botAI->TellMaster("I heading to your position.");
    }
    else if (!urand(0, 20))
        botAI->TellMaster("I am traveling to your position.");

    botAI->SetNextCheckDelay(3000);

    return true;
}

bool FleeToMasterAction::isUseful()
{
    if (!botAI->GetGroupMaster())
        return false;

    if (botAI->GetGroupMaster() == bot)
        return false;

    Unit* target = AI_VALUE(Unit*, "current target");
    if (target && botAI->GetGroupMaster()->GetTarget() == target->GetGUID())
        return false;

    if (!botAI->HasStrategy("follow", BOT_STATE_NON_COMBAT))
        return false;

    Unit* fTarget = AI_VALUE(Unit*, "master target");

    if (!CanDeadFollow(fTarget))
        return false;

    return true;
}
