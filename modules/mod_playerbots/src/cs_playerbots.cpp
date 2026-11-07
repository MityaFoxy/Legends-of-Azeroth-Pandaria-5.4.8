/*
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program. If not, see <http://www.gnu.org/licenses/>.
 */

#include "Chat.h"
#include "BotFactory.h"
#include "CharacterCache.h"
#include "Config.h"
#include "AiObjectContext.h"
#include "Item.h"
#include "OilActions.h"
#include "Pet.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "PerformanceMonitor.h"
#include "PlayerbotAIConfig.h"
#include "RandomPlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SpellMgr.h"
#include "SpellInfo.h"
#include "SpellHistory.h"

#include <sstream>
#include <map>

class playerbots_commandscript : public CommandScript
{
public:
    playerbots_commandscript() : CommandScript("playerbots_commandscript") {}

    std::vector<ChatCommand> GetCommands() const override
    {
        static std::vector<ChatCommand> commandTable =
        {
            { "npcbot", &HandlePlayerbotCommand, rbac::RBAC_PERM_COMMAND_NPCBOT, Trinity::ChatCommands::Console::Yes },
            { "pmon",   &HandlePerfMonCommand,   rbac::RBAC_PERM_COMMAND_PMON,   Trinity::ChatCommands::Console::Yes },
        };
        return commandTable;
    }

    static bool HandlePlayerbotCommand(ChatHandler* handler, char const* args)
    {
        std::string command = args ? args : "";
        if (command == "pettest" || command.starts_with("pettest "))
            return HandlePetPersistenceTest(handler, command.substr(std::min<size_t>(8, command.size())));
        if (command.starts_with("spellcheck "))
            return HandleSpellDiagnostic(handler, command.substr(11));
        if (command.starts_with("potiontest "))
            return HandleManaPotionTest(handler, command.substr(11));
        if (command.starts_with("oiltest "))
            return HandleOilTest(handler, command.substr(8));

        return PlayerbotMgr::HandlePlayerbotMgrCommand(handler, args);
    }

    // Console-only native potion probe. It never changes mana, combat or cooldowns.
    static bool HandleManaPotionTest(ChatHandler* handler, std::string const& arguments)
    {
        if (handler->GetSession() || !sConfigMgr->GetBoolDefault("AiPlayerbot.ManaPotionDiagnostics", false))
            return false;
        uint32 lowGuid = 0;
        std::string operation, extra;
        std::istringstream input(arguments);
        if (!(input >> lowGuid >> operation) || (input >> extra))
            return false;
        ObjectGuid guid = ObjectGuid::Create<HighGuid::Player>(lowGuid);
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(guid);
        PlayerbotAI* ai = bot ? sPlayerbotsMgr->GetPlayerbotAI(bot) : nullptr;
        if (!bot || !ai || ai->IsRealPlayer() || !bot->IsInWorld() ||
            !sPlayerbotAIConfig->IsInRandomAccountList(sCharacterCache->GetCharacterAccountIdByGuid(guid)))
            return false;
        static std::map<uint32, ObjectGuid> probes;
        if (operation == "supply")
        {
            if (probes.contains(lowGuid) || bot->GetPowerType() != POWER_MANA ||
                bot->DoForEachItem([](Item* item) { return item->IsPotion(); }))
            {
                handler->SendSysMessage("Potion fixture requires a mana user without existing potions or an active fixture.");
                return false;
            }
            ItemPosCountVec dest;
            InventoryResult result = bot->CanStoreNewItem(NULL_BAG, NULL_SLOT, dest, 2455, 2);
            if (result != EQUIP_ERR_OK)
            {
                handler->PSendSysMessage("Potion fixture inventory rejected guid=%u error=%u", lowGuid, uint32(result));
                return false;
            }
            Item* potion = bot->StoreNewItem(dest, 2455, true);
            if (!potion)
                return false;
            probes.emplace(lowGuid, potion->GetGUID());
            handler->PSendSysMessage("Potion fixture supplied guid=%u item_guid=%u count=%u",
                lowGuid, potion->GetGUID().GetCounter(), potion->GetCount());
            return true;
        }
        auto found = probes.find(lowGuid);
        if (found == probes.end())
            return false;
        ObjectGuid const itemGuid = found->second;
        if (operation == "run")
        {
            Item* item = bot->GetItemByGuid(itemGuid);
            uint32 const before = bot->GetPower(POWER_MANA);
            uint32 const countBefore = item ? item->GetCount() : 0;
            Action* action = ai->GetAiObjectContext()->GetAction("mana potion");
            bool const useful = action && action->isUseful();
            bool const accepted = useful && action->isPossible() && action->Execute(Event());
            uint32 const after = bot->GetPower(POWER_MANA);
            item = bot->GetItemByGuid(itemGuid);
            uint32 const countAfter = item ? item->GetCount() : 0;
            bool const ready = bot->GetSpellHistory()->IsReady(437, 2455);
            // Same update, still in combat: repeat must respect the held category cooldown.
            bool const repeat = accepted && action->isUseful() && action->isPossible() && action->Execute(Event());
            item = bot->GetItemByGuid(itemGuid);
            handler->PSendSysMessage("Potion fixture run guid=%u item_guid=%u combat=%u useful=%u accepted=%u mana_before=%u mana_after=%u count_before=%u count_after=%u ready=%u repeat=%u count_repeat=%u",
                lowGuid, itemGuid.GetCounter(), uint32(bot->IsInCombat()), uint32(useful), uint32(accepted),
                before, after, countBefore, countAfter, uint32(ready), uint32(repeat), item ? item->GetCount() : 0);
            return true;
        }
        if (operation == "cleanup")
        {
            if (bot->IsNonMeleeSpellCasted(true))
                return false;
            Item* item = bot->GetItemByGuid(itemGuid);
            if (item && item->GetEntry() == 2455 && item->GetOwnerGUID() == guid)
                bot->DestroyItem(item->GetBagSlot(), item->GetSlot(), true);
            bool const remaining = bot->GetItemByGuid(itemGuid) != nullptr;
            if (!remaining)
                probes.erase(found);
            handler->PSendSysMessage("Potion fixture cleaned guid=%u item_guid=%u remaining=%u",
                lowGuid, itemGuid.GetCounter(), uint32(remaining));
            return !remaining;
        }
        return false;
    }

    // Opt-in fixture: supplies one identifiable oil, uses the real Action, then
    // removes only that test item and its enchant. Never changes the weapon.
    static bool HandleOilTest(ChatHandler* handler, std::string const& arguments)
    {
        if (handler->GetSession() || !sConfigMgr->GetBoolDefault("AiPlayerbot.OilDiagnostics", false))
            return false;
        uint32 lowGuid = 0;
        std::string operation, extra;
        std::istringstream input(arguments);
        if (!(input >> lowGuid >> operation) || (input >> extra))
            return false;
        ObjectGuid guid = ObjectGuid::Create<HighGuid::Player>(lowGuid);
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(guid);
        PlayerbotAI* ai = bot ? sPlayerbotsMgr->GetPlayerbotAI(bot) : nullptr;
        if (!bot || !ai || ai->IsRealPlayer() || !bot->IsInWorld() ||
            !sPlayerbotAIConfig->IsInRandomAccountList(sCharacterCache->GetCharacterAccountIdByGuid(guid)))
            return false;

        struct Probe { ObjectGuid oil; ObjectGuid weapon; int32 charges; };
        static std::map<uint32, Probe> probes;
        if (operation == "supply")
        {
            Item* weapon = bot->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_MAINHAND);
            if (probes.contains(lowGuid) || bot->IsInCombat() || !weapon ||
                weapon->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT) || weapon->GetTemplate()->ItemLevel > 200 ||
                bot->HasItemCount(20744, 1, true))
                return false;
            ItemPosCountVec dest;
            if (bot->CanStoreNewItem(NULL_BAG, NULL_SLOT, dest, 20744, 1) != EQUIP_ERR_OK)
                return false;
            Item* oil = bot->StoreNewItem(dest, 20744, true);
            if (!oil)
                return false;
            probes.emplace(lowGuid, Probe{ oil->GetGUID(), weapon->GetGUID(), oil->GetSpellCharges(0) });
            handler->PSendSysMessage("Oil fixture supplied guid=%u oil_guid=%u weapon_guid=%u ilevel=%u charges=%d",
                lowGuid, oil->GetGUID().GetCounter(), weapon->GetGUID().GetCounter(),
                weapon->GetTemplate()->ItemLevel, oil->GetSpellCharges(0));
            return true;
        }
        auto found = probes.find(lowGuid);
        if (found == probes.end())
            return false;
        Probe const probe = found->second;
        Item* oil = bot->GetItemByGuid(probe.oil);
        Item* weapon = bot->GetItemByGuid(probe.weapon);
        if (operation == "run")
        {
            Action* action = ai->GetAiObjectContext()->GetAction("apply oil");
            bool const useful = action && action->isUseful();
            bool const possible = useful && action->isPossible();
            bool const accepted = possible && action->Execute(Event());
            handler->PSendSysMessage("Oil fixture run guid=%u useful=%u possible=%u accepted=%u",
                lowGuid, uint32(useful), uint32(possible), uint32(accepted));
            return true;
        }
        if (operation == "status")
        {
            handler->PSendSysMessage("Oil fixture status guid=%u oil_guid=%u weapon_guid=%u enchant=%u duration=%u charges_before=%d charges_now=%d",
                lowGuid, probe.oil.GetCounter(), probe.weapon.GetCounter(),
                weapon ? weapon->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT) : 0,
                weapon ? weapon->GetEnchantmentDuration(TEMP_ENCHANTMENT_SLOT) : 0,
                probe.charges, oil ? oil->GetSpellCharges(0) : 0);
            return true;
        }
        if (operation == "cleanup")
        {
            // Wait for the native cast to finish before deleting its cast item.
            if (bot->IsNonMeleeSpellCasted(true))
                return false;
            if (weapon && weapon->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT) == 2623)
            {
                bot->ApplyEnchantment(weapon, TEMP_ENCHANTMENT_SLOT, false);
                weapon->ClearEnchantment(TEMP_ENCHANTMENT_SLOT);
            }
            if (oil && oil->GetEntry() == 20744 && oil->GetOwnerGUID() == guid)
                bot->DestroyItem(oil->GetBagSlot(), oil->GetSlot(), true);
            probes.erase(found);
            handler->PSendSysMessage("Oil fixture cleaned guid=%u oil_guid=%u remaining=%u enchant=%u",
                lowGuid, probe.oil.GetCounter(), uint32(bot->GetItemByGuid(probe.oil) != nullptr),
                weapon ? weapon->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT) : 0);
            return true;
        }
        return false;
    }

    // Read-only console inspection: do not cast, teach spells, change targets,
    // run CheckCast (which can apply spell modifiers), or modify equipment.
    static bool HandleSpellDiagnostic(ChatHandler* handler, std::string const& arguments)
    {
        if (handler->GetSession() || !sConfigMgr->GetBoolDefault("AiPlayerbot.SpellDiagnostics", false))
        {
            handler->SendSysMessage("Spell inspection requires console and AiPlayerbot.SpellDiagnostics=1.");
            return false;
        }
        uint32 lowGuid = 0, spellId = 0;
        std::string extra;
        std::istringstream input(arguments);
        if (!(input >> lowGuid >> spellId) || (input >> extra) || !lowGuid || !spellId)
        {
            handler->SendSysMessage("Usage: npcbot spellcheck <random bot GUID> <spell ID>");
            return false;
        }
        ObjectGuid guid = ObjectGuid::Create<HighGuid::Player>(lowGuid);
        uint32 account = sCharacterCache->GetCharacterAccountIdByGuid(guid);
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(guid);
        PlayerbotAI* ai = bot ? sPlayerbotsMgr->GetPlayerbotAI(bot) : nullptr;
        SpellInfo const* spell = sSpellMgr->GetSpellInfo(spellId);
        if (!sPlayerbotAIConfig->IsInRandomAccountList(account) || !bot || !ai || ai->IsRealPlayer() ||
            !bot->IsInWorld() || !spell)
        {
            handler->SendSysMessage("Spell inspection requires a logged-in random bot and a valid spell ID.");
            return false;
        }
        uint32 resolved = ai->GetAiObjectContext()->GetValue<uint32>("spell id", spell->SpellName)->Get();
        Item* weapon = bot->GetWeaponForAttack(RANGED_ATTACK, true);
        handler->PSendSysMessage("Spell inspection guid=%u level=%u spec=%u spell=%u known=%u resolved=%u caster_aura_state=%u state_present=%u guard53592=%u weapon=%u weapon_subclass=%u",
            lowGuid, uint32(bot->GetLevel()), bot->GetTalentSpecialization(), spellId,
            uint32(bot->HasSpell(spellId)), resolved, spell->CasterAuraState,
            uint32(!spell->CasterAuraState || bot->HasAuraState(AuraStateType(spell->CasterAuraState), spell, bot)),
            uint32(bot->HasAura(53592)), weapon ? weapon->GetEntry() : 0,
            weapon ? uint32(weapon->GetTemplate()->SubClass) : 0);
        if (bot->GetClass() == CLASS_PALADIN)
            for (uint32 seal : { 105361u, 31801u, 20165u, 20154u, 20164u })
                handler->PSendSysMessage("Seal inspection guid=%u spell=%u known=%u active=%u",
                    lowGuid, seal, uint32(bot->HasSpell(seal)), uint32(bot->HasAura(seal)));
        return true;
    }

    // Opt-in console probe for one random Hunter. It uses ordinary login,
    // native spell validation/effects and pet persistence; it never edits SQL.
    static bool HandlePetPersistenceTest(ChatHandler* handler, std::string const& operation)
    {
        int32 configuredGuid = sConfigMgr->GetIntDefault("AiPlayerbot.PetPersistenceTestGuid", 0);
        if (handler->GetSession() || configuredGuid <= 0 || !sPlayerbotAIConfig->enabled)
        {
            handler->SendSysMessage("Pet test requires console and a positive AiPlayerbot.PetPersistenceTestGuid.");
            return false;
        }
        ObjectGuid guid = ObjectGuid::Create<HighGuid::Player>(uint32(configuredGuid));
        uint32 account = sCharacterCache->GetCharacterAccountIdByGuid(guid);
        if (!sPlayerbotAIConfig->IsInRandomAccountList(account))
        {
            handler->SendSysMessage("Pet test target must belong to a configured random-bot account.");
            return false;
        }
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(guid);
        if (operation == "login")
        {
            if (!bot)
                sRandomPlayerbotMgr->AddPlayerBot(guid, 0);
            handler->PSendSysMessage("Pet test login requested: %u", uint32(configuredGuid));
            return true;
        }
        PlayerbotAI* ai = bot ? sPlayerbotsMgr->GetPlayerbotAI(bot) : nullptr;
        if (!bot || !ai || ai->IsRealPlayer() || bot->GetClass() != CLASS_HUNTER || !bot->IsInWorld())
        {
            handler->SendSysMessage("Pet test requires the configured Hunter bot to be fully logged in.");
            return false;
        }
        if (operation == "logout")
        {
            sRandomPlayerbotMgr->LogoutPlayerBot(guid);
            handler->PSendSysMessage("Pet test logout requested: %u", uint32(configuredGuid));
            return true;
        }
        if (operation == "status")
        {
            Pet* pet = bot->GetPet();
            handler->PSendSysMessage("Pet test guid=%u current=%u slot0=%u live=%u entry=%u alive=%u call883=%u dismiss2641=%u combat=%u mounted=%u exotic=%u",
                uint32(configuredGuid), bot->GetCurrentPetId(), bot->GetPetIdBySlot(PET_SLOT_ACTIVE_FIRST),
                pet ? pet->GetCharmInfo()->GetPetNumber() : 0, pet ? pet->GetEntry() : 0,
                uint32(pet && pet->IsAlive()), uint32(bot->HasSpell(883)), uint32(bot->HasSpell(2641)),
                uint32(bot->IsInCombat()), uint32(bot->IsMounted()), uint32(bot->CanTameExoticPets()));
            return true;
        }
        if (operation == "resume")
        {
            ai->SetNextCheckDelay(0);
            handler->SendSysMessage("Pet test AI resumed.");
            return true;
        }
        if (operation != "pause" && operation != "call" && operation != "dismiss" && operation != "refresh")
        {
            handler->SendSysMessage("Usage: npcbot pettest login/status/pause/call/dismiss/refresh/resume/logout");
            return false;
        }
        if (bot->IsInCombat() || bot->IsBeingTeleported() || !bot->IsAlive())
        {
            handler->SendSysMessage("Pet test changes require an alive, stationary-world, out-of-combat bot.");
            return false;
        }
        bool result = true;
        if (operation == "pause")
            bot->StopMoving();
        else if (operation == "call")
            result = ai->DoSpecificAction("call pet 1");
        else if (operation == "dismiss")
            result = ai->CastSpell(uint32(2641), bot);
        else if (operation == "refresh")
            BotFactory(bot, bot->GetLevel()).InitPet();

        // Stop autonomous decisions from racing the next observation. Spell
        // events continue normally; resume or logout ends the bounded pause.
        ai->SetNextCheckDelay(10 * MINUTE * IN_MILLISECONDS);
        handler->PSendSysMessage("Pet test %s result=%u (inspect status after spell completion)", operation.c_str(), uint32(result));
        return result;
    }

    static bool HandlePerfMonCommand(ChatHandler* handler, char const* args)
    {
        if (!strcmp(args, "reset"))
        {
            sPerformanceMonitor->Reset();
            return true;
        }

        if (!strcmp(args, "tick"))
        {
            sPerformanceMonitor->PrintStats(true, false);
            return true;
        }

        if (!strcmp(args, "stack"))
        {
            sPerformanceMonitor->PrintStats(false, true);
            return true;
        }

        if (!strcmp(args, "toggle"))
        {
            sPlayerbotAIConfig->perfMonEnabled = !sPlayerbotAIConfig->perfMonEnabled;
            if (sPlayerbotAIConfig->perfMonEnabled)
                TC_LOG_INFO("playerbots", "Performance monitor enabled");
            else
                TC_LOG_INFO("playerbots", "Performance monitor disabled");
            return true;
        }

        sPerformanceMonitor->PrintStats();
        return true;
    }
};

void AddSC_playerbots_commandscript() { new playerbots_commandscript(); }
