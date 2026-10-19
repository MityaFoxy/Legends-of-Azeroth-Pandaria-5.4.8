#include "BotLifeReadiness.h"
#include "Item.h"
#include "Player.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include <algorithm>

namespace BotLife
{
Readiness ReadCombatReadiness(Player& bot)
{
    Readiness s;
    s.level = bot.GetLevel();
    s.health = bot.GetHealthPct();
    // Don't demand rage/runic power before combat, or mana from a feral druid.
    s.usesMana = bot.GetPowerType() == POWER_MANA && bot.GetMaxPower(POWER_MANA) > 0;
    s.mana = bot.GetPowerPct(POWER_MANA);
    s.resurrectionSickness = bot.HasAura(15007);
    float itemLevels = 0;
    uint32 relevantItems = 0;
    for (uint8 slot = EQUIPMENT_SLOT_START; slot < EQUIPMENT_SLOT_END; ++slot)
    {
        Item* item = bot.GetItemByPos(INVENTORY_SLOT_BAG_0, slot);
        if (!item)
            continue;
        ++s.equipped;
        ItemTemplate const* proto = item->GetTemplate();
        if (slot != EQUIPMENT_SLOT_BODY && slot != EQUIPMENT_SLOT_TABARD)
        {
            itemLevels += proto->ItemLevel;
            ++relevantItems;
        }
        if (proto->Class == ITEM_CLASS_ARMOR && slot <= EQUIPMENT_SLOT_HANDS &&
            slot != EQUIPMENT_SLOT_NECK && slot != EQUIPMENT_SLOT_BODY)
            ++s.armorPieces;
        uint32 const maximum = item->GetUInt32Value(ITEM_FIELD_MAX_DURABILITY);
        if (maximum)
        {
            s.durability = std::min(s.durability, 100.0f * item->GetUInt32Value(ITEM_FIELD_DURABILITY) / maximum);
            s.broken |= item->IsBroken();
        }
    }
    s.averageItemLevel = relevantItems ? itemLevels / relevantItems : 0;
    auto usable = [&bot](uint8 slot, uint32 itemClass)
    {
        Item* item = bot.GetItemByPos(INVENTORY_SLOT_BAG_0, slot);
        return item && item->GetTemplate()->Class == itemClass && bot.CanUseItem(item) == EQUIP_ERR_OK;
    };
    s.weapon = usable(EQUIPMENT_SLOT_MAINHAND, ITEM_CLASS_WEAPON);
    if (bot.GetClass() == CLASS_HUNTER)
    {
        auto ranged = [&bot, &usable](uint8 slot)
        {
            if (!usable(slot, ITEM_CLASS_WEAPON))
                return false;
            uint32 const type = bot.GetItemByPos(INVENTORY_SLOT_BAG_0, slot)->GetTemplate()->SubClass;
            return type == ITEM_SUBCLASS_WEAPON_BOW || type == ITEM_SUBCLASS_WEAPON_GUN || type == ITEM_SUBCLASS_WEAPON_CROSSBOW;
        };
        s.weapon = ranged(EQUIPMENT_SLOT_MAINHAND) || ranged(EQUIPMENT_SLOT_RANGED);
    }
    uint32 const spec = bot.GetTalentSpecialization();
    if ((bot.GetClass() == CLASS_ROGUE && s.level >= 10) || (spec == SPEC_SHAMAN_ENHANCEMENT && s.level >= 40))
        s.offhand = usable(EQUIPMENT_SLOT_OFFHAND, ITEM_CLASS_WEAPON);
    if (spec == SPEC_PALADIN_PROTECTION || spec == SPEC_WARRIOR_PROTECTION)
    {
        Item* shield = bot.GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND);
        s.offhand = usable(EQUIPMENT_SLOT_OFFHAND, ITEM_CLASS_ARMOR) &&
            shield->GetTemplate()->SubClass == ITEM_SUBCLASS_ARMOR_SHIELD;
    }
    s.coreArmor = usable(EQUIPMENT_SLOT_CHEST, ITEM_CLASS_ARMOR) && usable(EQUIPMENT_SLOT_LEGS, ITEM_CLASS_ARMOR);
    for (auto const& [id, known] : bot.GetSpellMap())
    {
        if (known->state == PLAYERSPELL_REMOVED || known->disabled || !known->active)
            continue;
        SpellInfo const* spell = sSpellMgr->GetSpellInfo(id);
        if (!spell || spell->IsPassive())
            continue;
        for (auto const& effect : spell->Effects)
            if (effect.Effect == SPELL_EFFECT_SCHOOL_DAMAGE || effect.Effect == SPELL_EFFECT_WEAPON_DAMAGE ||
                effect.Effect == SPELL_EFFECT_NORMALIZED_WEAPON_DMG || effect.Effect == SPELL_EFFECT_WEAPON_PERCENT_DAMAGE ||
                effect.ApplyAuraName == SPELL_AURA_PERIODIC_DAMAGE)
                s.combatSpell = true;
    }
    return s;
}
}
