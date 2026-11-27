#include "BotLifeQuestObject.h"

#include "DBCStores.h"
#include "GameObject.h"
#include "GameObjectPackets.h"
#include "Map.h"
#include "Player.h"
#include "WorldSession.h"
#include <cmath>

namespace BotLife
{
bool IsSupportedQuestObject(GameObjectTemplate const& info, uint32_t questId)
{
    if (info.type != GAMEOBJECT_TYPE_GOOBER || info.ScriptId || !info.AIName.empty())
        return false;
    auto const& goober = info.goober;
    return (goober.questId <= 0 || uint32(goober.questId) == questId) && !goober.lockId &&
        !goober.eventId && !goober.pageId && !goober.spellId && !goober.linkedTrapId &&
        !goober.gossipID && !goober.WorldStateSetsState && !goober.conditionID1;
}

GameObject* FindQuestObject(Player& bot, QuestSpawn const& target)
{
    if (!bot.IsInWorld() || bot.IsDuringRemoveFromWorld() || target.mapId != bot.GetMapId())
        return nullptr;
    GameObject* object = bot.GetMap()->GetGameObjectBySpawnId(target.guid);
    return object && object->IsInWorld() && object->GetMap() == bot.GetMap() && object->GetEntry() == target.entry &&
        (object->GetPhaseMask() & bot.GetPhaseMask()) && object->isSpawned() ? object : nullptr;
}

char const* QuestObjectApproachRejection(Player& bot, GameObject const* object)
{
    if (!object || !bot.IsInMap(object) || !object->isSpawned())
        return "object-unavailable";
    if (!object->IsAtInteractDistance(&bot))
        return "object-out-of-range";
    if (!bot.CanSeeOrDetect(object, false, true))
        return "object-not-visible";
    if (bot.IsWithinLOSInMap(object))
        return nullptr;

    // A model can occlude a ray to its own base. Check its upper surface
    // with ordinary map LOS, including dynamic collision and the bot's phase.
    auto const* bounds = sGameObjectDisplayInfoStore.LookupEntry(object->GetGOInfo()->displayId);
    float const scale = object->GetObjectScale();
    if (!bounds || !(scale > 0) || !(bounds->maxZ > bounds->minZ))
        return "object-line-of-sight-blocked";
    G3D::Vector3 const upperCentre{
        (bounds->minX + bounds->maxX) * scale * 0.5f,
        (bounds->minY + bounds->maxY) * scale * 0.5f, bounds->maxZ * scale + 0.05f};
    G3D::Vector3 const surface = object->GetWorldRotation().toRotationMatrix() * upperCentre;
    if (!std::isfinite(surface.x) || !std::isfinite(surface.y) || !std::isfinite(surface.z))
        return "object-line-of-sight-blocked";
    bool const visible = bot.GetMap()->isInLineOfSight(bot.GetPositionX(), bot.GetPositionY(),
        bot.GetPositionZ() + bot.GetCollisionHeight(), object->GetPositionX() + surface.x,
        object->GetPositionY() + surface.y, object->GetPositionZ() + surface.z,
        bot.GetPhaseMask(), VMAP::ModelIgnoreFlags::Nothing);
    return visible ? nullptr : "object-line-of-sight-blocked";
}

QuestObjectUseResult TryUseQuestObject(Player& bot, GameObject& object, QuestPlanData const& data)
{
    QuestObjectiveData const& objective = data.objectives.front();
    uint32 const before = bot.GetQuestObjectiveCounter(objective.id);
    if (bot.GetQuestStatus(data.questId) != QUEST_STATUS_INCOMPLETE || before >= objective.amount)
        return {"object-objective-inactive"};
    if (!bot.GetSession() || !bot.IsAlive() || bot.GetGroup() || bot.IsInCombat() || bot.IsMounted() ||
        bot.HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED | UNIT_STATE_LOST_CONTROL) || bot.IsNonMeleeSpellCasted(false))
        return {"object-interaction-blocked", true};
    GameObjectTemplate const* info = object.GetGOInfo();
    if (!info || object.GetEntry() != objective.entry || object.GetOwnerGUID() || object.GetScriptId() || !object.AI() ||
        !IsSupportedQuestObject(*info, data.questId))
        return {"object-unsupported"};
    if (object.HasFlag(GAMEOBJECT_FIELD_FLAGS, GO_FLAG_LOCKED | GO_FLAG_INTERACT_COND | GO_FLAG_NOT_SELECTABLE))
        return {"object-not-ready"};
    if (object.getLootState() != GO_READY || object.GetGoState() != GO_STATE_READY ||
        object.HasFlag(GAMEOBJECT_FIELD_FLAGS, GO_FLAG_IN_USE))
        return {"object-not-ready", true};
    if (char const* reason = QuestObjectApproachRejection(bot, &object))
        return {reason};

    WorldPackets::GameObject::GameObjUse request(WorldPacket(CMSG_GAMEOBJ_USE, 0));
    request.Guid = object.GetGUID();
    bot.GetSession()->HandleGameObjectUseOpcode(request);
    return {bot.GetQuestObjectiveCounter(objective.id) > before ? "used" : "object-no-quest-progress"};
}
}
