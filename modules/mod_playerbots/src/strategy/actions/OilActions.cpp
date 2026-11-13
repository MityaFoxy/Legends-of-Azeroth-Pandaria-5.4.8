/*
 * Copyright (C) 2016+ AzerothCore <www.azerothcore.org>, released under GNU GPL v2 license.
 * Oil selection restores the main-hand contract of mod-playerbots ImbueAction;
 * MoP item requirements and native result handling are documented in
 * doc/playerbot_oil_line_audit.md.
 */

#include "OilActions.h"

#include "DatabaseEnv.h"
#include "Battleground.h"
#include "Item.h"
#include "Playerbots.h"
#include "PlayerbotSpec.h"
#include "ScriptMgr.h"
#include "Spell.h"
#include "SpellHistory.h"

namespace
{
    struct WeaponOil
    {
        uint32 item;
        uint32 spell;
        bool mana;
    };

    // Exact item/use-spell pairs verified in the local MoP DB and DBC.
    constexpr WeaponOil WeaponOils[] = {
        {22522, 28017, false}, {20749, 25122, false}, {20750, 25121, false},
        {20746, 25119, false}, {20744, 25117, false},
        {22521, 28013, true}, {20748, 25123, true}, {20747, 25120, true}, {20745, 25118, true}
    };
}

bool ApplyOilAction::CanApply()
{
    if (!bot->IsInWorld() || !bot->IsAlive() || bot->IsInCombat() || bot->isMoving() ||
        bot->IsMounted() || bot->IsInFlight() || bot->IsBeingTeleported() ||
        bot->GetVehicle() || bot->GetTransport() || bot->IsCharmed() ||
        bot->HasUnitState(UNIT_STATE_LOST_CONTROL) || bot->IsNonMeleeSpellCasted(true) ||
        (!PlayerBotSpec::IsCaster(bot, true) && !PlayerBotSpec::IsHeal(bot, true)))
        return false;

    return true;
}

Item* ApplyOilAction::FindOil(Item* weapon, uint32& spellId, uint32& enchantId)
{
    if (!weapon || weapon->GetOwnerGUID() != bot->GetGUID() || weapon->IsInTrade() ||
        weapon->IsBroken() || weapon->GetTemplate()->Class != ITEM_CLASS_WEAPON ||
        weapon->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT))
        return nullptr;

    bool const preferMana = PlayerBotSpec::IsHeal(bot, true);
    Item* best = nullptr;
    bool bestPreferred = false;
    bot->DoForEachItem([&](Item* item)
    {
        if (item->GetOwnerGUID() != bot->GetGUID() || item->IsInTrade() ||
            bot->GetUseableItemByPos(item->GetBagSlot(), item->GetSlot()) != item ||
            bot->CanUseItem(item) != EQUIP_ERR_OK)
            return false;

        ItemTemplate const* proto = item->GetTemplate();
        for (WeaponOil const& oil : WeaponOils)
        {
            if (item->GetEntry() != oil.item || proto->Spells[0].SpellId != int32(oil.spell) ||
                proto->Spells[0].SpellTrigger != ITEM_SPELLTRIGGER_ON_USE ||
                !bot->GetSpellHistory()->IsReady(oil.spell, oil.item))
                continue;

            SpellInfo const* info = sSpellMgr->GetSpellInfo(oil.spell);
            if (!info || !weapon->IsFitToSpellRequirements(info) ||
                (info->MaxLevel && weapon->GetTemplate()->ItemLevel > info->MaxLevel))
                continue;

            if (Battleground const* bg = bot->GetBattlegorund())
                if ((bg->IsArena() || bg->IsRatedBG()) &&
                    (!(proto->Flags & ITEM_PROTO_FLAG_USEABLE_IN_ARENA) ||
                     (proto->Flags & ITEM_PROTO_FLAG_NOT_USEABLE_IN_ARENA)))
                    continue;

            uint32 enchant = 0;
            for (SpellEffectInfo const& effect : info->Effects)
                if (effect.Effect == SPELL_EFFECT_ENCHANT_ITEM_TEMPORARY)
                    enchant = effect.MiscValue;
            if (!enchant)
                continue;

            bool const preferred = oil.mana == preferMana;
            if (!best || (preferred && !bestPreferred) ||
                (preferred == bestPreferred && proto->RequiredLevel > best->GetTemplate()->RequiredLevel))
            {
                best = item;
                bestPreferred = preferred;
                spellId = oil.spell;
                enchantId = enchant;
            }
        }
        return false;
    }, true, true, false, false, false); // Backpack/bags, never equipment or bank.
    return best;
}

bool ApplyOilAction::isUseful()
{
    uint32 spellId = 0, enchantId = 0;
    return CanApply() && FindOil(bot->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_MAINHAND),
        spellId, enchantId);
}

bool ApplyOilAction::isPossible() { return isUseful(); }

bool ApplyOilAction::Execute(Event /*event*/)
{
    if (!CanApply())
        return false;
    Item* weapon = bot->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_MAINHAND);
    uint32 spellId = 0, enchantId = 0;
    Item* oil = FindOil(weapon, spellId, enchantId);
    if (!oil)
        return false;

    ObjectGuid const oilGuid = oil->GetGUID();
    ObjectGuid const weaponGuid = weapon->GetGUID();
    ItemTemplate const* proto = oil->GetTemplate();
    if (!oil->IsSoulBound() && (proto->Bonding == BIND_ON_USE ||
        proto->Bonding == BIND_ON_ACQUIRE || proto->Bonding == BIND_QUEST))
    {
        oil->SetState(ITEM_CHANGED, bot);
        oil->SetBinding(true);
    }

    SpellCastTargets targets;
    targets.SetItemTarget(weapon);
    if (!sScriptMgr->OnItemUse(bot, oil, targets))
        bot->CastItemUseSpell(oil, targets, 1, 0);

    // Native casting owns the cast item and may consume its final charge.
    // Reacquire the target; do not dereference the old oil pointer after use.
    weapon = bot->GetItemByGuid(weaponGuid);
    if (weapon && weapon->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT) == enchantId)
        return true;
    Spell* cast = bot->GetCurrentSpell(CURRENT_GENERIC_SPELL);
    if (cast && cast->GetSpellInfo()->Id == spellId && cast->m_castItemGUID == oilGuid &&
        cast->GetCastResult() == SPELL_CAST_OK)
    {
        botAI->SetNextCheckDelay(std::max<int32>(1, cast->GetCastTime()));
        return true;
    }
    return false;
}
