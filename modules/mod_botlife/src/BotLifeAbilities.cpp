#include "BotLifeAbilities.h"
#include "AiObjectContext.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "SpellInfo.h"
#include "SpellMgr.h"

namespace BotLife
{
namespace
{
struct AbilityDefinition
{
    char const* action;
    uint32_t id;
    char const* condition;
    bool mainhand = false, offhand = false;
    char const* trigger = "";
    char const* nativeAction = nullptr;
};

// Audit list from MeleeShamanStrategy, not a second combat rotation.
// Conditional damage, pets, imbues and area effects must not become free DPS.
AbilityDefinition const definitions[] = {
    {"stormstrike", 17364, "default-triggered-weapons", true},
    {"earth shock", 8042, "default-shared-shock-cooldown"},
    {"feral spirit", 51533, "default-pet"},
    {"fire nova", 1535, "default-flame-shock-area"},
    {"lava lash", 60103, "default-offhand-flame-shock-spread", false, true},
    {"flame shock", 8050, "debuff-trigger-shared-shock-cooldown", false, false, "flame shock"},
    {"lightning bolt", 403, "maelstrom-weapon-4-trigger", false, false, "maelstrom weapon 4"},
    {"windfury weapon", 8232, "mainhand-no-imbue-trigger", true, false, "main hand weapon no imbue"},
    {"flametongue weapon", 8024, "offhand-no-imbue-trigger", false, true, "off hand weapon no imbue"},
    {"magma totem", 8190, "no-fire-totem-trigger-area", false, false, "no fire totem"},
    {"searing totem", 3599, "magma-totem-fallback", false, false, "no fire totem"},
    {"fire elemental totem", 2894, "fire-elemental-trigger-pet", false, false,
        "fire elemental totem", "fire elemental totem melee"}
};

void ReadEffects(SpellInfo const& spell, std::vector<AbilityEffect>& output)
{
    uint32_t index = 0;
    // This fork's constructor populates Effects, not the newer _effects
    // storage exposed by GetEffects(). Read the same array as native casting.
    for (auto const& effect : spell.Effects)
    {
        if (effect.IsEffect())
            output.push_back({spell.Id, index, effect.Effect, effect.ApplyAuraName, effect.TriggerSpell,
                effect.BasePoints, effect.DieSides, effect.ScalingMultiplier, effect.BonusMultiplier,
                effect.IsTargetingArea()});
        ++index;
    }
}
}

std::vector<AbilitySnapshot> ReadEnhancementAbilities(PlayerbotAI& ai)
{
    std::vector<AbilitySnapshot> result;
    Player* bot = ai.GetBot();
    AiObjectContext* context = ai.GetAiObjectContext();
    if (!bot || !context || bot->GetClass() != CLASS_SHAMAN ||
        bot->GetTalentSpecialization() != SPEC_SHAMAN_ENHANCEMENT)
        return result;
    bool const melee = ai.HasStrategy("melee", BOT_STATE_COMBAT);
    auto const& spells = bot->GetSpellMap();
    for (AbilityDefinition const& definition : definitions)
    {
        AbilitySnapshot snapshot;
        snapshot.action = definition.action;
        snapshot.condition = definition.condition;
        snapshot.trigger = definition.trigger;
        snapshot.baseId = definition.id;
        auto const base = spells.find(definition.id);
        snapshot.baseKnown = base != spells.end() && base->second->state != PLAYERSPELL_REMOVED;
        // Same resolver as native CastSpellAction, including its rank/name behavior.
        // This may populate AI's value cache but never executes an action.
        auto* value = context->GetValue<uint32>("spell id", definition.action);
        snapshot.resolvedId = value ? value->Get() : 0;
        snapshot.meleeStrategy = melee;
        snapshot.actionRegistered = context->GetAction(definition.nativeAction ? definition.nativeAction : definition.action) != nullptr;
        // Registration only. Never call isPossible/isUseful/IsActive: those
        // checks can depend on a current target or have native side effects.
        snapshot.triggerRegistered = *definition.trigger && context->GetTrigger(definition.trigger) != nullptr;
        snapshot.weaponReady =
            (!definition.mainhand || (bot->CanUseAttackType(BASE_ATTACK) && bot->GetWeaponForAttack(BASE_ATTACK, true))) &&
            (!definition.offhand || (bot->CanDualWield() && bot->CanUseAttackType(OFF_ATTACK) &&
                bot->GetWeaponForAttack(OFF_ATTACK, true)));
        auto const known = spells.find(snapshot.resolvedId);
        if (known != spells.end())
        {
            snapshot.active = known->second->state != PLAYERSPELL_REMOVED && known->second->active;
            snapshot.disabled = known->second->disabled;
        }
        if (SpellInfo const* spell = sSpellMgr->GetSpellInfo(snapshot.resolvedId))
        {
            snapshot.passive = spell->IsPassive();
            snapshot.school = spell->GetSchoolMask();
            snapshot.cooldownReady = !bot->HasSpellCooldown(spell->Id);
            snapshot.cooldownMs = bot->GetSpellCooldownDelay(spell->Id);
            // No Spell instance: base timing only, not haste/proc-adjusted.
            snapshot.baseCastMs = spell->CalcCastTime(bot->GetLevel());
            snapshot.baseRecoveryMs = spell->GetRecoveryTime();
            snapshot.baseGcdMs = spell->StartRecoveryTime;
            for (auto const* power : spell->SpellPowers)
                if (power)
                    snapshot.powers.push_back({int32_t(power->PowerType), power->Cost, power->CostPercentage,
                        power->RequiredAura, power->RequiredAura && bot->HasAura(power->RequiredAura)});
            ReadEffects(*spell, snapshot.effects);
            // One level only: expose Stormstrike's weapon children, never walk
            // an unbounded/cyclic trigger graph or execute script effects.
            for (auto const& effect : spell->Effects)
                if (effect.IsEffect() && effect.TriggerSpell && effect.TriggerSpell != spell->Id)
                    if (SpellInfo const* child = sSpellMgr->GetSpellInfo(effect.TriggerSpell))
                        ReadEffects(*child, snapshot.effects);
        }
        result.push_back(snapshot);
    }
    return result;
}

void LogEnhancementAbilities(PlayerbotAI& ai)
{
    auto const snapshots = ReadEnhancementAbilities(ai);
    if (snapshots.empty())
        return;
    Player const& bot = *ai.GetBot();
    TC_LOG_INFO("playerbots.botlife", "BotLife abilities guid={} event=snapshot diagnosticOnly=true mana={} maxMana={} createMana={}",
        bot.GetGUID().GetCounter(), bot.GetPower(POWER_MANA), bot.GetMaxPower(POWER_MANA), bot.GetCreateMana());
    for (AbilitySnapshot const& s : snapshots)
    {
        TC_LOG_INFO("playerbots.botlife", "BotLife ability guid={} action={} base={} baseKnown={} resolved={} active={} disabled={} passive={} meleeStrategy={} weaponReady={} cooldownReady={} cooldownMs={} baseCastMs={} baseRecoveryMs={} baseGcdMs={} school={} condition={} actionRegistered={} trigger={} triggerRegistered={}",
            bot.GetGUID().GetCounter(), s.action, s.baseId, s.baseKnown, s.resolvedId, s.active, s.disabled, s.passive,
            s.meleeStrategy, s.weaponReady, s.cooldownReady, s.cooldownMs, s.baseCastMs, s.baseRecoveryMs, s.baseGcdMs, s.school, s.condition,
            s.actionRegistered, s.trigger, s.triggerRegistered);
        for (AbilityPower const& p : s.powers)
            TC_LOG_INFO("playerbots.botlife", "BotLife ability-power guid={} spell={} type={} baseFlat={} basePercent={} requiredAura={} auraPresent={}",
                bot.GetGUID().GetCounter(), s.resolvedId, p.type, p.flat, p.percent, p.requiredAura, p.auraPresent);
        for (AbilityEffect const& e : s.effects)
            TC_LOG_INFO("playerbots.botlife", "BotLife ability-effect guid={} actionSpell={} spell={} index={} effect={} aura={} trigger={} rawBase={} dieSides={} scaling={} coefficient={} area={}",
                bot.GetGUID().GetCounter(), s.resolvedId, e.spell, e.index, e.effect, e.aura, e.trigger, e.base, e.dieSides, e.scaling, e.coefficient, e.area);
    }
}
}
