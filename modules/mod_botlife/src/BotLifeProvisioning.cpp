#include "BotLifeProvisioning.h"
#include "BotLife.h"
#include "BotLifeQuestRun.h"
#include "BotLifeReadiness.h"
#include "Config.h"
#include "CharacterCache.h"
#include "Item.h"
#include "Log.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "RandomItemManager.h"
#include <algorithm>
#include <atomic>
#include <vector>

namespace BotLife
{
namespace
{
bool requested = false;
uint32 configuredGuid = 0;
std::atomic<bool> consumed{false};

bool FitsSlot(uint8 slot, uint32 type)
{
    switch (slot)
    {
        case EQUIPMENT_SLOT_HEAD: return type == INVTYPE_HEAD;
        case EQUIPMENT_SLOT_NECK: return type == INVTYPE_NECK;
        case EQUIPMENT_SLOT_SHOULDERS: return type == INVTYPE_SHOULDERS;
        case EQUIPMENT_SLOT_CHEST: return type == INVTYPE_CHEST || type == INVTYPE_ROBE;
        case EQUIPMENT_SLOT_WAIST: return type == INVTYPE_WAIST;
        case EQUIPMENT_SLOT_LEGS: return type == INVTYPE_LEGS;
        case EQUIPMENT_SLOT_FEET: return type == INVTYPE_FEET;
        case EQUIPMENT_SLOT_WRISTS: return type == INVTYPE_WRISTS;
        case EQUIPMENT_SLOT_HANDS: return type == INVTYPE_HANDS;
        case EQUIPMENT_SLOT_BACK: return type == INVTYPE_CLOAK;
        case EQUIPMENT_SLOT_FINGER1: case EQUIPMENT_SLOT_FINGER2: return type == INVTYPE_FINGER;
        case EQUIPMENT_SLOT_TRINKET1: case EQUIPMENT_SLOT_TRINKET2: return type == INVTYPE_TRINKET;
        case EQUIPMENT_SLOT_MAINHAND: return type == INVTYPE_WEAPON || type == INVTYPE_WEAPONMAINHAND ||
            type == INVTYPE_2HWEAPON || type == INVTYPE_RANGED || type == INVTYPE_RANGEDRIGHT;
        case EQUIPMENT_SLOT_OFFHAND: return type == INVTYPE_WEAPON || type == INVTYPE_WEAPONOFFHAND ||
            type == INVTYPE_SHIELD || type == INVTYPE_HOLDABLE;
        default: return false;
    }
}

bool Suitable(Player& bot, ItemTemplate const& p)
{
    if (p.Duration || p.Bonding == BIND_QUEST || p.RequiredLevel > bot.GetLevel() ||
        p.RequiredLevel + 10 < bot.GetLevel() || p.ItemLevel > bot.GetLevel() * 3 / 2 + 10 ||
        p.Quality < ITEM_QUALITY_UNCOMMON || p.Quality > ITEM_QUALITY_RARE ||
        sRandomItemMgr->IsTestItem(p.ItemId) || bot.CanUseItem(&p) != EQUIP_ERR_OK)
        return false;
    // Existing RandomItemManager filters armor/weapon types but its shaman
    // stat filter is class-wide. Don't bootstrap enhancement in caster gear.
    if (bot.GetTalentSpecialization() == SPEC_SHAMAN_ENHANCEMENT)
    {
        int32 agility = 0, intellect = 0, strength = 0;
        for (auto const& stat : p.ItemStat)
        {
            if (stat.ItemStatType == ITEM_MOD_AGILITY) agility += stat.ItemStatValue;
            if (stat.ItemStatType == ITEM_MOD_INTELLECT) intellect += stat.ItemStatValue;
            if (stat.ItemStatType == ITEM_MOD_STRENGTH) strength += stat.ItemStatValue;
        }
        if (intellect > agility || strength > agility)
            return false;
    }
    if (p.Class == ITEM_CLASS_WEAPON)
        return sRandomItemMgr->CanEquipWeapon(&bot, &p);
    if (p.Class != ITEM_CLASS_ARMOR)
        return false;
    if (p.SubClass == ITEM_SUBCLASS_ARMOR_MISCELLANEOUS || p.SubClass == ITEM_SUBCLASS_ARMOR_SHIELD)
        return sRandomItemMgr->CanEquipSubArmor(&bot, &p);
    return sRandomItemMgr->CanEquipArmor(&bot, &p);
}
}

void LoadProvisioningConfig()
{
    requested = sConfigMgr->GetBoolDefault("AiPlayerbot.BotLife.QuestRun.PrepareCharacter", false);
    configuredGuid = requested && IsQuestRunEnabled() ? GetQuestRunBotGuid() : 0;
    consumed = false;
    if (requested)
        TC_LOG_WARN("server.loading", "BotLife explicit one-shot character preparation requested guid={}; missing-slot grants only, no randomization", configuredGuid);
}

bool ProvisionMissingEquipment(PlayerbotAI& ai, char const*& reason)
{
    if (!requested)
        return true;
    Player* bot = ai.GetBot();
    char const* rejection = nullptr;
    if (!configuredGuid || !IsOnlyEligibleBot(configuredGuid) || !bot || bot->GetGUID().GetCounter() != configuredGuid)
        rejection = "preparation-invalid-roster";
    else if (ai.IsRealPlayer() || ai.HasRealPlayerMaster())
        rejection = "preparation-player-controlled";
    // Manual test login intentionally does not join RandomPlayerbotMgr's
    // automatic population. Authorize the account, just as the login command
    // does, rather than requiring automatic population membership.
    else if (!sPlayerbotAIConfig->IsInRandomAccountList(sCharacterCache->GetCharacterAccountIdByGuid(bot->GetGUID())))
        rejection = "preparation-not-random-account";
    else if (sPlayerbotAIConfig->randomBotAutologin)
        rejection = "preparation-autologin-enabled";
    else if (!bot->IsAlive() || bot->HasFlag(PLAYER_FIELD_PLAYER_FLAGS, PLAYER_FLAGS_GHOST))
        rejection = "preparation-not-alive";
    else if (bot->IsInCombat())
        rejection = "preparation-in-combat";
    else if (bot->GetGroup())
        rejection = "preparation-in-group";
    else if (bot->GetTalentSpecialization() == SPEC_NONE)
        rejection = "preparation-no-specialization";
    else if (consumed.exchange(true))
        rejection = "preparation-already-consumed";
    if (rejection)
    {
        reason = rejection;
        TC_LOG_INFO("playerbots.botlife", "BotLife provision guid={} event=rejected reason={}", configuredGuid, reason);
        return false;
    }
    // Relearn only native class/spec entitlements. No spec/talent reset, skill
    // maximization, level change, XP reset, money grant or quest manipulation.
    bot->LearnDefaultSkills();
    bot->LearnSpecializationSpells();
    std::vector<ItemTemplate const*> candidates;
    for (auto const& [id, proto] : *sObjectMgr->GetItemTemplateStore())
        if (Suitable(*bot, proto))
            candidates.push_back(&proto);
    std::sort(candidates.begin(), candidates.end(), [](auto* a, auto* b)
    {
        if (a->ItemLevel != b->ItemLevel)
            return a->ItemLevel > b->ItemLevel;
        return a->ItemId < b->ItemId;
    });
    uint32 added = 0;
    // Main hand before offhand, then armor. Never let a two-hander displace
    // an existing offhand: native validation alone can permit bag relocation.
    static uint8 const slots[] = {15, 16, 0, 2, 4, 5, 6, 7, 8, 9, 14, 1, 10, 11, 12, 13};
    for (uint8 slot : slots)
    {
        if (bot->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
            continue;
        uint32 attempts = 0;
        for (ItemTemplate const* proto : candidates)
        {
            if (!FitsSlot(slot, proto->InventoryType))
                continue;
            if (slot == EQUIPMENT_SLOT_MAINHAND && bot->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND) &&
                (proto->InventoryType == INVTYPE_2HWEAPON || proto->InventoryType == INVTYPE_RANGED || proto->InventoryType == INVTYPE_RANGEDRIGHT))
                continue;
            if (++attempts > 64)
                break;
            Item* item = Item::CreateItem(proto->ItemId, 1, bot, true);
            if (!item)
                continue;
            uint16 dest = 0;
            InventoryResult const allowed = bot->CanEquipItem(slot, dest, item, false, true);
            item->RemoveFromUpdateQueueOf(bot);
            delete item;
            if (allowed != EQUIP_ERR_OK || uint8(dest) != slot || bot->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
                continue;
            if (bot->EquipNewItem(dest, proto->ItemId, true))
            {
                ++added;
                TC_LOG_INFO("playerbots.botlife", "BotLife provision guid={} event=item slot={} item={} ilvl={}",
                    configuredGuid, uint32(slot), proto->ItemId, proto->ItemLevel);
                break;
            }
        }
    }
    Readiness const after = ReadCombatReadiness(*bot);
    PreparationDecision const decision = EvaluateReadiness(after, false);
    bool const prepared = decision.state != Preparation::Unprepared;
    reason = prepared ? "prepared" : decision.reason;
    TC_LOG_INFO("playerbots.botlife", "BotLife provision guid={} event=finish prepared={} added={} equipped={} reason={}",
        configuredGuid, prepared, added, after.equipped, reason);
    // Partial additions are retained and reported; never destroy items to fake
    // rollback. Normal character persistence saves them, including on failure.
    return prepared;
}
}
