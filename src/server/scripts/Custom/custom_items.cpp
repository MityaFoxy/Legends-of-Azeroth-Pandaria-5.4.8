#include "ScriptMgr.h"
#include "Chat.h"
#include "DBCStores.h"
#include "ServiceMgr.h"
#include "World.h"

#include <limits>

namespace BattlePay
{
    enum Money : int64
    {
        GOLD_1K   = 10000000,
        GOLD_5K   = 50000000,
        GOLD_10K  = 100000000,
        GOLD_30K  = 300000000,
        GOLD_80K  = 800000000,
        GOLD_150K = 1500000000
    };
}

#define GetText(player, ru, en) ((player)->GetSession()->GetSessionDbLocaleIndex() == LOCALE_ruRU ? (ru) : (en))

namespace
{
    bool CanReceiveFullCurrency(Player* player, uint32 currencyId, uint32 amount, bool ignoreWeekCap)
    {
        CurrencyTypesEntry const* currency = sCurrencyTypesStore.LookupEntry(currencyId);
        if (!currency)
            return false;

        uint32 totalCap = currency->TotalCap;
        if (currencyId == CURRENCY_TYPE_HONOR_POINTS)
        {
            if (uint32 configuredCap = sWorld->getIntConfig(CONFIG_CURRENCY_MAX_HONOR_POINTS))
                totalCap = configuredCap;
        }
        else if (currencyId == CURRENCY_TYPE_JUSTICE_POINTS)
        {
            if (uint32 configuredCap = sWorld->getIntConfig(CONFIG_CURRENCY_MAX_JUSTICE_POINTS))
                totalCap = configuredCap;
        }

        uint64 newTotal = uint64(player->GetCurrency(currencyId, false)) + amount;
        // ModifyCurrency accumulates the stored total in int32.
        if (newTotal > std::numeric_limits<int32>::max() || (totalCap && newTotal > totalCap))
            return false;

        if (!ignoreWeekCap)
        {
            uint32 weekCap = player->GetCurrencyWeekCap(currencyId, false);
            if (weekCap && uint64(player->GetCurrencyOnWeek(currencyId, false)) + amount > weekCap)
                return false;
        }

        return true;
    }
}

class honor_1000 : public ItemScript
{
public:
    honor_1000() : ItemScript("battle_pay_currency_honor_1000") {}

    bool OnUse(Player* player, Item* item, SpellCastTargets const&) override
    {
        if (player->IsInCombat() || player->InArena() || player->InBattleground()) //Item is not usable in combat, arenas and battlegrounds. This can be modified to your taste.
        {
            player->GetSession()->SendNotification("You may not use this token whilst you are in combat or present in an arena or battleground.");
        }
        else if (!player->HasItemCount(item->GetEntry(), 1, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage("You do not have the necessary token.");
        }
        else if (!CanReceiveFullCurrency(player, CURRENCY_TYPE_HONOR_POINTS, 1000 * CURRENCY_PRECISION, false))
        {
            ChatHandler(player->GetSession()).SendSysMessage("The currency limit prevents receiving the full 1000 points. Your token was not used.");
        }
        else
        {
            player->ModifyCurrency(CURRENCY_TYPE_HONOR_POINTS, 1000 * CURRENCY_PRECISION, true, true); // add exactly 1000 honor points
            ChatHandler(player->GetSession()).SendSysMessage("Thanks for helping the WoW project, you just received 1000 honor points.");

            //Item is destroyed on useage.
            player->DestroyItemCount(item->GetEntry(), 1, true);

            //save pj
            player->SaveToDB();
        }
        return true;
    }
};

class justice_1000 : public ItemScript
{
public:
    justice_1000() : ItemScript("battle_pay_currency_justice_1000") {}

    bool OnUse(Player* player, Item* item, SpellCastTargets const&) override
    {
        if (player->IsInCombat() || player->InArena() || player->InBattleground()) //Item is not usable in combat, arenas and battlegrounds. This can be modified to your taste.
        {
            player->GetSession()->SendNotification("You may not use this token whilst you are in combat or present in an arena or battleground.");
        }
        else if (!player->HasItemCount(item->GetEntry(), 1, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage("You do not have the necessary token.");
        }
        else if (!CanReceiveFullCurrency(player, CURRENCY_TYPE_JUSTICE_POINTS, 1000 * CURRENCY_PRECISION, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage("The currency limit prevents receiving the full 1000 points. Your token was not used.");
        }
        else
        {
            player->ModifyCurrency(CURRENCY_TYPE_JUSTICE_POINTS, 1000 * CURRENCY_PRECISION, true, true, true); // add 1000 justice points
            ChatHandler(player->GetSession()).SendSysMessage("Thanks for helping the WoW project, you just received 1000 justice points.");

            //Item is destroyed on useage.
            player->DestroyItemCount(item->GetEntry(), 1, true);

            //save pj
            player->SaveToDB();
        }
        return true;
    }
};

class valor_1000 : public ItemScript
{
public:
    valor_1000() : ItemScript("battle_pay_currency_valor_1000") {}

    bool OnUse(Player* player, Item* item, SpellCastTargets const&) override
    {
        if (player->IsInCombat() || player->InArena() || player->InBattleground()) //Item is not usable in combat, arenas and battlegrounds. This can be modified to your taste.
        {
            player->GetSession()->SendNotification("You may not use this token whilst you are in combat or present in an arena or battleground.");
        }
        else if (!player->HasItemCount(item->GetEntry(), 1, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage("You do not have the necessary token.");
        }
        else if (!CanReceiveFullCurrency(player, CURRENCY_TYPE_VALOR_POINTS, 1000 * CURRENCY_PRECISION, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage("The currency limit prevents receiving the full 1000 points. Your token was not used.");
        }
        else
        {
            player->ModifyCurrency(CURRENCY_TYPE_VALOR_POINTS, 1000 * CURRENCY_PRECISION, true, true, true); // add 1000 valor points
            ChatHandler(player->GetSession()).SendSysMessage("Thanks for helping the WoW project, you just received 1000 valor points.");

            //Item is destroyed on useage.
            player->DestroyItemCount(item->GetEntry(), 1, true);

            //save pj
            player->SaveToDB();
        }
        return true;
    }
};

class conquest_1000 : public ItemScript
{
public:
    conquest_1000() : ItemScript("battle_pay_currency_conquest_1000") {}

    bool OnUse(Player* player, Item* item, SpellCastTargets const&) override
    {
        if (player->IsInCombat() || player->InArena() || player->InBattleground()) //Item is not usable in combat, arenas and battlegrounds. This can be modified to your taste.
        {
            player->GetSession()->SendNotification("You may not use this token whilst you are in combat or present in an arena or battleground.");
        }
        else if (!player->HasItemCount(item->GetEntry(), 1, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage("You do not have the necessary token.");
        }
        else if (!CanReceiveFullCurrency(player, CURRENCY_TYPE_CONQUEST_POINTS, 1000 * CURRENCY_PRECISION, false))
        {
            ChatHandler(player->GetSession()).SendSysMessage("The currency limit prevents receiving the full 1000 points. Your token was not used.");
        }
        else
        {
            player->ModifyCurrency(CURRENCY_TYPE_CONQUEST_POINTS, 1000 * CURRENCY_PRECISION, true, true); // add exactly 1000 conquest points
            ChatHandler(player->GetSession()).SendSysMessage("Thanks for helping the WoW project, you just received 1000 conquest points.");

            //Item is destroyed on useage.
            player->DestroyItemCount(item->GetEntry(), 1, true);

            //save pj
            player->SaveToDB();
        }
        return true;
    }
};

template<int64 Gold>
class battle_pay_gold : public ItemScript
{
public:
    explicit battle_pay_gold(char const* scriptName) : ItemScript(scriptName) { }

    bool OnUse(Player* player, Item* item, SpellCastTargets const&) override
    {
        if (player->IsInCombat() || player->InArena() || player->InBattleground())
        {
            player->GetSession()->SendNotification(GetText(player,
                "Вы не можете использовать этот жетон, пока находитесь в бою, на арене или поле боя.",
                "You may not use this token whilst you are in combat or present in an arena or battleground."));
        }
        else if (!player->HasItemCount(item->GetEntry(), 1, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage(GetText(player,
                "У вас нет необходимого жетона.", "You do not have the necessary token."));
        }
        else if (player->GetMoney() > uint64(MAX_MONEY_AMOUNT)
            || uint64(Gold) > uint64(MAX_MONEY_AMOUNT) - player->GetMoney())
        {
            ChatHandler(player->GetSession()).SendSysMessage(GetText(player,
                "Превышен максимально допустимый лимит золота.", "Maximum allowed gold limit exceeded."));
        }
        else
        {
            player->ModifyMoney(Gold);
            player->DestroyItemCount(item->GetEntry(), 1, true);

            std::ostringstream message;
            message << GetText(player, "Вы получили ", "You received ") << Gold / GOLD << GetText(player, " золотых.", " gold.");
            ChatHandler(player->GetSession()).SendSysMessage(message.str().c_str());
            player->SaveToDB();
        }

        return true;
    }
};

template<uint32 Level>
class battle_pay_level : public ItemScript
{
public:
    explicit battle_pay_level(char const* scriptName) : ItemScript(scriptName) { }

    bool OnUse(Player* player, Item* item, SpellCastTargets const&) override
    {
        if (player->IsInCombat() || player->InArena() || player->InBattleground())
        {
            player->GetSession()->SendNotification(GetText(player,
                "Вы не можете использовать этот жетон, пока находитесь в бою, на арене или поле боя.",
                "You may not use this token whilst you are in combat or present in an arena or battleground."));
        }
        else if (!player->HasItemCount(item->GetEntry(), 1, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage(GetText(player,
                "У вас нет необходимого жетона.", "You do not have the necessary token."));
        }
        else if (player->GetLevel() >= Level)
        {
            ChatHandler(player->GetSession()).SendSysMessage(GetText(player,
                "Текущий уровень персонажа уже достаточно высок.", "Your current character level is already high enough."));
        }
        else
        {
            player->GiveLevel(Level);
            player->DestroyItemCount(item->GetEntry(), 1, true);
            ChatHandler(player->GetSession()).SendSysMessage(GetText(player,
                "Уровень персонажа повышен до 90.", "Your character has been leveled up to level 90."));
            player->SaveToDB();
        }

        return true;
    }
};

template<AtLoginFlags FlagAtLogin>
class battle_pay_service : public ItemScript
{
public:
    explicit battle_pay_service(char const* scriptName) : ItemScript(scriptName) { }

    bool OnUse(Player* player, Item* item, SpellCastTargets const&) override
    {
        AtLoginFlags const characterServiceFlags = static_cast<AtLoginFlags>(
            AT_LOGIN_RENAME | AT_LOGIN_CUSTOMIZE | AT_LOGIN_CHANGE_FACTION | AT_LOGIN_CHANGE_RACE);

        if (player->IsInCombat() || player->InArena() || player->InBattleground())
        {
            player->GetSession()->SendNotification(GetText(player,
                "Вы не можете использовать этот жетон, пока находитесь в бою, на арене или поле боя.",
                "You may not use this token whilst you are in combat or present in an arena or battleground."));
        }
        else if (!player->HasItemCount(item->GetEntry(), 1, true))
        {
            ChatHandler(player->GetSession()).SendSysMessage(GetText(player,
                "У вас нет необходимого жетона.", "You do not have the necessary token."));
        }
        else if (player->HasAtLoginFlag(characterServiceFlags))
        {
            ChatHandler(player->GetSession()).SendSysMessage(GetText(player,
                "У персонажа уже есть ожидающая услуга изменения.", "This character already has a pending character service."));
        }
        else
        {
            player->SetAtLoginFlag(FlagAtLogin);
            player->DestroyItemCount(item->GetEntry(), 1, true);
            ChatHandler(player->GetSession()).SendSysMessage(GetText(player,
                "Услуга активирована. Перезайдите в учётную запись.",
                "The service has been activated. Please re-login to your account."));
            player->SaveToDB();
        }

        return true;
    }
};

void AddSC_Custom_Items() // Add to scriptloader normally
{
    new honor_1000();
    new justice_1000();
    new valor_1000();
    new conquest_1000();
    new battle_pay_gold<BattlePay::GOLD_1K>("battle_pay_gold_1k");
    new battle_pay_gold<BattlePay::GOLD_5K>("battle_pay_gold_5k");
    new battle_pay_gold<BattlePay::GOLD_10K>("battle_pay_gold_10k");
    new battle_pay_gold<BattlePay::GOLD_30K>("battle_pay_gold_30k");
    new battle_pay_gold<BattlePay::GOLD_80K>("battle_pay_gold_80k");
    new battle_pay_gold<BattlePay::GOLD_150K>("battle_pay_gold_150k");
    new battle_pay_level<90>("battle_pay_service_level_90");
    new battle_pay_service<AT_LOGIN_RENAME>("battle_pay_service_rename");
    new battle_pay_service<AT_LOGIN_CHANGE_FACTION>("battle_pay_service_change_faction");
    new battle_pay_service<AT_LOGIN_CHANGE_RACE>("battle_pay_service_change_race");
    new battle_pay_service<AT_LOGIN_CUSTOMIZE>("battle_pay_service_customize");
}

#undef GetText
