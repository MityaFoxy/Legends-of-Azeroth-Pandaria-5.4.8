/*
 * This file is part of the Legends of Azeroth Pandaria Project.
 * Released under GNU GPL version 2 or later; see COPYING.
 */
#include "ManaPotionAction.h"

#include "DatabaseEnv.h"
#include "Battleground.h"
#include "Item.h"
#include "Playerbots.h"
#include "ScriptMgr.h"
#include "Spell.h"
#include "SpellHistory.h"
#include <algorithm>

namespace
{
    struct ManaPotion { uint32 item; uint32 spell; };
    // Ordinary direct mana potions verified in local MoP templates and DBC.
    // Specialized injectors, channels and reusable potions need separate handling.
    constexpr ManaPotion ManaPotions[] = {
        {2455, 437}, {3385, 438}, {3827, 2023}, {6149, 11903},
        {13443, 17530}, {13444, 17531}, {22832, 28499}, {40067, 28499},
        {33448, 43186}, {57192, 78990}, {76098, 105709}
    };
}

bool ManaPotionAction::CanUsePotion()
{
    // The existing strategies own low-mana thresholds; out of combat they can drink.
    return bot->IsInWorld() && bot->IsAlive() && bot->IsInCombat() &&
        bot->GetPowerType() == POWER_MANA && bot->GetPower(POWER_MANA) < bot->GetMaxPower(POWER_MANA) &&
        !bot->IsMounted() && !bot->IsInFlight() && !bot->IsBeingTeleported() &&
        !bot->GetVehicle() && !bot->IsCharmed() && !bot->HasUnitState(UNIT_STATE_LOST_CONTROL) &&
        !bot->IsNonMeleeSpellCasted(true);
}

Item* ManaPotionAction::FindPotion(uint32& spellId)
{
    Item* best = nullptr;
    bot->DoForEachItem([&](Item* item)
    {
        if (item->GetOwnerGUID() != bot->GetGUID() || item->IsInTrade() ||
            bot->GetUseableItemByPos(item->GetBagSlot(), item->GetSlot()) != item ||
            bot->CanUseItem(item) != EQUIP_ERR_OK || !item->IsPotion())
            return false;
        ItemTemplate const* proto = item->GetTemplate();
        for (ManaPotion const& potion : ManaPotions)
        {
            if (item->GetEntry() != potion.item || proto->Spells[0].SpellId != int32(potion.spell) ||
                proto->Spells[0].SpellTrigger != ITEM_SPELLTRIGGER_ON_USE ||
                !bot->GetSpellHistory()->IsReady(potion.spell, potion.item))
                continue;
            SpellInfo const* info = sSpellMgr->GetSpellInfo(potion.spell);
            if (!info || !std::any_of(std::begin(info->Effects), std::end(info->Effects),
                [](SpellEffectInfo const& effect)
                {
                    return effect.Effect == SPELL_EFFECT_ENERGIZE && effect.MiscValue == POWER_MANA;
                }))
                continue;
            if (Battleground const* bg = bot->GetBattlegorund())
                if ((bg->IsArena() || bg->IsRatedBG()) &&
                    (!(proto->Flags & ITEM_PROTO_FLAG_USEABLE_IN_ARENA) ||
                     (proto->Flags & ITEM_PROTO_FLAG_NOT_USEABLE_IN_ARENA)))
                    continue;
            if (!best || proto->RequiredLevel > best->GetTemplate()->RequiredLevel)
            {
                best = item;
                spellId = potion.spell;
            }
        }
        return false;
    }, true, true, false, false, false);
    return best;
}

bool ManaPotionAction::isUseful()
{
    uint32 spellId = 0;
    return CanUsePotion() && FindPotion(spellId);
}

bool ManaPotionAction::isPossible() { return isUseful(); }

bool ManaPotionAction::Execute(Event /*event*/)
{
    if (!CanUsePotion())
        return false;
    uint32 spellId = 0;
    Item* potion = FindPotion(spellId);
    if (!potion)
        return false;

    ObjectGuid const itemGuid = potion->GetGUID();
    uint32 const manaBefore = bot->GetPower(POWER_MANA);
    ItemTemplate const* proto = potion->GetTemplate();
    if (!potion->IsSoulBound() && (proto->Bonding == BIND_ON_USE ||
        proto->Bonding == BIND_ON_ACQUIRE || proto->Bonding == BIND_QUEST))
    {
        potion->SetState(ITEM_CHANGED, bot);
        potion->SetBinding(true);
    }
    SpellCastTargets targets;
    targets.SetUnitTarget(bot);
    if (!sScriptMgr->OnItemUse(bot, potion, targets))
        bot->CastItemUseSpell(potion, targets, 1, 0);

    // Native use may delete the last item. Never dereference potion here.
    if (bot->GetPower(POWER_MANA) > manaBefore)
        return true;
    Spell* cast = bot->GetCurrentSpell(CURRENT_GENERIC_SPELL);
    if (cast && cast->GetSpellInfo()->Id == spellId && cast->m_castItemGUID == itemGuid &&
        cast->GetCastResult() == SPELL_CAST_OK)
    {
        botAI->SetNextCheckDelay(std::max<int32>(1, cast->GetCastTime()));
        return true;
    }
    return false;
}
