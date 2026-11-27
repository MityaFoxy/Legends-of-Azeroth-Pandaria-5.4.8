#include "BotLifeQuestLoot.h"

#include "Creature.h"
#include "LootMgr.h"
#include "LootPackets.h"
#include "Map.h"
#include "Player.h"
#include "WorldSession.h"
#include <algorithm>
#include <limits>

namespace BotLife
{
Creature* FindQuestCorpse(Player& bot, ObjectGuid guid, QuestSpawn const& target)
{
    if (!guid || !bot.IsInWorld() || bot.IsDuringRemoveFromWorld() || target.mapId != bot.GetMapId())
        return nullptr;
    Creature* corpse = bot.GetMap()->GetCreature(guid);
    if (!corpse || !corpse->IsInWorld() || corpse->IsAlive() || corpse->GetSpawnId() != target.guid ||
        corpse->GetEntry() != target.entry || !(corpse->GetPhaseMask() & bot.GetPhaseMask()))
        return nullptr;
    return corpse;
}

char const* TryLootQuestItem(Player& bot, Creature& corpse, QuestPlanData const& data)
{
    QuestObjectiveData const& objective = data.objectives.front();
    if (bot.GetQuestStatus(data.questId) != QUEST_STATUS_INCOMPLETE ||
        bot.GetQuestObjectiveCounter(objective.id) >= objective.amount)
        return "loot-objective-inactive";
    if (!bot.GetSession() || !bot.IsAlive() || bot.GetGroup() || bot.IsInCombat() || bot.IsMounted() ||
        bot.HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED | UNIT_STATE_LOST_CONTROL) ||
        bot.IsNonMeleeSpellCasted(false) || !bot.GetLootView().empty())
        return "loot-interaction-blocked";
    if (!corpse.HasNormalLootMode() || corpse.GetLootRecipient() != &bot || !bot.IsAllowedToLoot(&corpse))
        return "loot-not-owned";
    if (!bot.IsWithinDistInMap(&corpse, INTERACTION_DISTANCE) || !bot.IsWithinLOSInMap(&corpse))
        return "loot-out-of-range";

    uint32 const before = bot.GetQuestObjectiveCounter(objective.id);
    ObjectGuid const corpseGuid = corpse.GetGUID();
    bot.SendLoot(corpseGuid, LOOT_CORPSE);
    auto const& view = bot.GetLootView();
    auto const opened = std::find_if(view.begin(), view.end(), [corpseGuid](auto const& entry)
    {
        return entry.second == corpseGuid;
    });
    if (opened == view.end())
        return "loot-view-refused";

    char const* reason = "loot-item-not-available";
    if (view.size() == 1)
    {
        Loot& loot = corpse.loot;
        uint32 const slots = std::min<uint32>(loot.GetMaxSlotInLootFor(&bot), std::numeric_limits<uint8>::max() + 1u);
        for (uint32 slot = 0; slot < slots; ++slot)
        {
            QuestItem* questItem = nullptr;
            LootItem const* item = loot.LootItemInSlot(slot, &bot, &questItem);
            if (!item || !questItem || item->itemid != objective.entry)
                continue;
            ItemPosCountVec dest;
            if (bot.CanStoreNewItem(NULL_BAG, NULL_SLOT, dest, item->itemid, item->count) != EQUIP_ERR_OK)
            {
                reason = "loot-storage-refused";
                break;
            }
            WorldPackets::Loot::LootItem request(WorldPacket(CMSG_AUTOSTORE_LOOT_ITEM, 0));
            request.guids.push_back(opened->first);
            request.lootSlots.push_back(uint8(slot));
            bot.GetSession()->HandleAutostoreLootItemOpcode(request);
            reason = bot.GetQuestObjectiveCounter(objective.id) > before ? "looted" : "loot-no-quest-progress";
            break;
        }
    }

    // Native storage can run hooks. Only the GUID survives across the call.
    WorldPackets::Loot::LootRelease release(WorldPacket(CMSG_LOOT_RELEASE, 0));
    release.Unit = corpseGuid;
    bot.GetSession()->HandleLootReleaseOpcode(release);
    return reason;
}
}
