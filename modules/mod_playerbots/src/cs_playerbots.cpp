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

        return PlayerbotMgr::HandlePlayerbotMgrCommand(handler, args);
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
