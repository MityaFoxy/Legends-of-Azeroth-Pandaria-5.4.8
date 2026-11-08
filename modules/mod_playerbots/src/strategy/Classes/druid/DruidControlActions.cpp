#include "DruidControlActions.h"

#include "HealthTriggers.h"
#include "Playerbots.h"
#include "RtiTargetValue.h"

namespace
{
    bool CanDruidControl(Player* bot, uint32 id)
    {
        return bot->IsAlive() && bot->HasSpell(id) && !bot->IsFlying() && !bot->IsInFlight();
    }

    bool DruidControlTarget(Player* bot, Unit* target, SpellInfo const* info)
    {
        return target && info && target->IsInWorld() && target->IsAlive() && bot->IsInMap(target) &&
            bot->InSamePhase(target) && bot->IsValidAttackTarget(target) && bot->IsWithinLOSInMap(target) &&
            !target->IsImmunedToSpellEffect(info, EFFECT_0) &&
            info->CheckTarget(bot, target) == SPELL_CAST_OK;
    }
}

Unit* SelectDruidCcTarget(PlayerbotAI* ai, uint32 spellId)
{
    Player* bot = ai->GetBot();
    if (!CanDruidControl(bot, spellId))
        return nullptr;

    // Calculate the existing icon selector afresh: a queued Action must not
    // use a cached assignment after the leader removes or moves the icon.
    RtiCcTargetValue assignment(ai);
    Unit* target = assignment.Calculate();
    SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId);
    if (!DruidControlTarget(bot, target, info) ||
        target == ai->GetAiObjectContext()->GetValue<Unit*>("current target")->Get() ||
        target == bot->GetVictim() ||
        bot->GetDistance(target) > bot->GetSpellMaxRangeForTarget(target, info) ||
        target->HasBreakableByDamageCrowdControlAura() || target->HasAuraType(SPELL_AURA_MOD_ROOT) ||
        target->HasAuraType(SPELL_AURA_PERIODIC_DAMAGE) ||
        target->HasAuraType(SPELL_AURA_PERIODIC_DAMAGE_PERCENT) || target->HasAuraType(SPELL_AURA_PERIODIC_LEECH))
        return nullptr;
    // Native CheckTarget supplies Hibernate's Beast/Dragonkin restriction.
    return target;
}

Unit* DruidCcAction::GetTarget() { return SelectDruidCcTarget(botAI, id); }

bool DruidCcAction::isUseful() { return GetTarget() && CastSpellAction::isUseful(); }

bool DruidCcAction::isPossible() { return GetTarget() && CastSpellAction::isPossible(); }

NextAction** DruidCcAction::getPrerequisites()
{
    SpellInfo const* info = sSpellMgr->GetSpellInfo(id);
    if (GetTarget() && info && info->CheckShapeshift(bot->GetShapeshiftForm()) == SPELL_FAILED_NOT_SHAPESHIFT)
        return NextAction::array(0, new NextAction("caster form"), nullptr);
    return CastSpellAction::getPrerequisites();
}

bool DruidCcAction::Execute(Event event)
{
    return isUseful() && isPossible() && CastSpellAction::Execute(event);
}

Unit* SelectDruidBashTarget(PlayerbotAI* ai, bool healer)
{
    Player* bot = ai->GetBot();
    if (!CanDruidControl(bot, 5211))
        return nullptr;
    SpellInfo const* info = sSpellMgr->GetSpellInfo(5211);
    auto eligible = [&](Unit* target) {
        return DruidControlTarget(bot, target, info) && bot->IsWithinMeleeRange(target) &&
            !target->HasAuraType(SPELL_AURA_MOD_STUN) && target->IsNonMeleeSpellCasted(true);
    };
    Unit* current = ai->GetAiObjectContext()->GetValue<Unit*>("current target")->Get();
    if (!healer)
        return eligible(current) ? current : nullptr;

    // The shared enemy-healer predicate recognizes interrupt/silence effects,
    // not the Mighty Bash stun. Preserve its secondary-positive-caster policy
    // and validate this talent's native target contract instead.
    for (ObjectGuid guid : ai->GetAiObjectContext()->GetValue<GuidVector>("attackers")->Get())
    {
        Unit* target = ai->GetUnit(guid);
        if (target == current || !eligible(target))
            continue;
        for (CurrentSpellTypes type : {CURRENT_GENERIC_SPELL, CURRENT_CHANNELED_SPELL})
            if (Spell* cast = target->GetCurrentSpell(type))
                if (cast->GetSpellInfo()->IsPositive())
                    return target;
    }
    return nullptr;
}

Unit* DruidBashAction::GetTarget() { return SelectDruidBashTarget(botAI, healer); }

bool DruidBashAction::isUseful() { return GetTarget() && CastSpellAction::isUseful(); }

bool DruidBashAction::isPossible() { return GetTarget() && CastSpellAction::isPossible(); }

bool DruidBashAction::Execute(Event event)
{
    return isUseful() && isPossible() && CastSpellAction::Execute(event);
}

bool DruidControlTrigger::IsActive()
{
    Action* cast = context->GetAction(action);
    return cast && cast->isUseful() && cast->isPossible();
}

bool DruidNaturesSwiftnessTrigger::IsActive()
{
    // The existing heal strategy supplies the follow-up emergency heals.
    // Balance's caster strategy has those nodes commented out, so spell
    // knowledge alone must not spend this next-spell buff for a wounded ally.
    // This is a strategy gate, not a restriction of 132158 to one spec.
    PartyMemberCriticalHealthTrigger critical(botAI);
    return botAI->HasStrategy("heal", BOT_STATE_COMBAT) &&
        CanDruidControl(bot, 132158) && !bot->HasAura(132158) && critical.IsActive() &&
        botAI->CanCastSpell("nature's swiftness", bot);
}
