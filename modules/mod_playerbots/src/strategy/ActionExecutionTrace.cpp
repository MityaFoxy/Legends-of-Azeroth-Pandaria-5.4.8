#include "ActionExecutionTrace.h"

#include "Action.h"
#include "Config.h"
#include "Log.h"
#include "Player.h"
#include "Unit.h"

bool ActionExecutionTrace::Enabled()
{
    return sLog->ShouldLog("playerbots.execution", LOG_LEVEL_DEBUG)
        && sConfigMgr->GetBoolDefault("AiPlayerbot.ExecutionDiagnostics", false);
}

void ActionExecutionTrace::Target(Unit const* target)
{
    if (!current || !target)
        return;
    // Snapshot immediately: do not retain a Unit pointer across execution or
    // resolve any AI Value merely to produce diagnostics.
    current->targetGuid = target->GetGUID().GetCounter();
    current->targetType = target->GetTypeId();
    current->targetMap = target->GetMapId();
    current->targetInstance = target->GetInstanceId();
    current->targetAlive = target->IsAlive();
    current->targetMoving = target->isMoving();
    current->targetX = target->GetPositionX();
    current->targetY = target->GetPositionY();
    current->targetZ = target->GetPositionZ();
}

void ActionExecutionTrace::Finish(Player const* bot, Action* action, bool rawResult, bool finalResult) const
{
    if (!enabled)
        return;
    Unit const* victim = bot->GetVictim();
    TC_LOG_DEBUG("playerbots.execution", "event=action-execution bot={} map={} instance={} action='{}' raw={} result={} reason={} detail={} spell={} cast_result={} alive={} combat={} moving={} casting={} mounted={} stand={} root={} stun={} confuse={} charmed={} lost_control={} teleport={} form={} power_type={} power={} max_power={} victim={} melee_attacking={} target={} target_type={} target_map={} target_instance={} target_alive={} target_moving={} target_pos=({},{},{}) from=({},{},{})",
        bot->GetGUID().GetCounter(), bot->GetMapId(), bot->GetInstanceId(), action->getName(), rawResult, finalResult,
        finalResult ? "none" : reason, finalResult ? "none" : detail, spellId, castResult,
        bot->IsAlive(), bot->IsInCombat(), bot->isMoving(), bot->IsNonMeleeSpellCasted(false), bot->IsMounted(), bot->IsStandState(),
        bot->HasRootAura(), bot->HasStunAura(), bot->HasConfuseAura(), bot->IsCharmed(),
        bot->HasUnitState(UNIT_STATE_LOST_CONTROL), bot->IsBeingTeleported(), uint32(bot->GetShapeshiftForm()),
        uint32(bot->GetPowerType()), bot->GetPower(bot->GetPowerType()), bot->GetMaxPower(bot->GetPowerType()),
        victim ? victim->GetGUID().GetCounter() : 0, bot->HasUnitState(UNIT_STATE_MELEE_ATTACKING),
        targetGuid, targetType, targetMap, targetInstance, targetAlive, targetMoving, targetX, targetY, targetZ,
        bot->GetPositionX(), bot->GetPositionY(), bot->GetPositionZ());
}
