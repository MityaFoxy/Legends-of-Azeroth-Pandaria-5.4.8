#!/usr/bin/env python3
"""Run the production corpse-loot adapter against controlled game APIs."""
from pathlib import Path
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]
module = root / 'modules/mod_botlife/src'
adapter = (module / 'BotLifeQuestLoot.cpp').read_text().split('namespace BotLife', 1)[1]
assert all(token not in adapter for token in ('SetQuestStatus(', '.StoreNewItem(', 'KilledMonster', 'CompleteQuest('))

mocks = r'''
#include "BotLifeQuestPlan.h"
#include <algorithm>
#include <cassert>
#include <limits>
#include <map>
#include <string_view>
using uint32 = uint32_t;
using uint8 = uint8_t;
using ObjectGuid = uint32;
enum { QUEST_STATUS_INCOMPLETE = 3, UNIT_STATE_ROOT = 1, UNIT_STATE_STUNNED = 2,
       UNIT_STATE_LOST_CONTROL = 4, INTERACTION_DISTANCE = 5, LOOT_CORPSE = 1,
       NULL_BAG = 0, NULL_SLOT = 0, EQUIP_ERR_OK = 0, CMSG_AUTOSTORE_LOOT_ITEM = 1, CMSG_LOOT_RELEASE = 2 };
using ItemPosCountVec = std::vector<int>;
struct WorldPacket { WorldPacket(int, int) {} };
namespace WorldPackets::Loot {
struct LootItem {
    explicit LootItem(WorldPacket) {}
    std::vector<ObjectGuid> guids;
    std::vector<uint8> lootSlots;
};
struct LootRelease { explicit LootRelease(WorldPacket) {} ObjectGuid Unit=0; };
}
struct Player;
struct QuestItem {};
struct LootItem { uint32 itemid=49208, count=1; };
struct Loot {
    LootItem item;
    QuestItem questItem;
    bool present=true, questDrop=true;
    uint32 GetMaxSlotInLootFor(Player*) const { return 1; }
    LootItem* LootItemInSlot(uint32 slot, Player*, QuestItem** visibleQuestItem) {
        assert(slot==0);
        *visibleQuestItem = questDrop ? &questItem : nullptr;
        return present ? &item : nullptr;
    }
};
struct Creature {
    bool world=true, alive=false, normal=true;
    uint32 phase=1, entry=36304, spawn=243966;
    Player* recipient=nullptr;
    Loot loot;
    bool IsInWorld() const { return world; }
    bool IsAlive() const { return alive; }
    uint32 GetSpawnId() const { return spawn; }
    uint32 GetEntry() const { return entry; }
    uint32 GetPhaseMask() const { return phase; }
    bool HasNormalLootMode() const { return normal; }
    Player* GetLootRecipient() const { return recipient; }
    ObjectGuid GetGUID() const { return 15; }
};
struct Map {
    Creature* corpse=nullptr;
    Creature* GetCreature(ObjectGuid guid) { return guid==15 ? corpse : nullptr; }
};
struct Session {
    Player* bot=nullptr;
    void HandleAutostoreLootItemOpcode(WorldPackets::Loot::LootItem& request);
    void HandleLootReleaseOpcode(WorldPackets::Loot::LootRelease& request);
};
struct Player {
    Session session{this};
    Map map;
    std::map<ObjectGuid,ObjectGuid> view;
    uint32 opens=0, stores=0, releases=0, counter=0, status=QUEST_STATUS_INCOMPLETE;
    bool full=false, allowed=true, grant=true, los=true;
    bool IsInWorld() const { return true; }
    bool IsDuringRemoveFromWorld() const { return false; }
    uint32 GetMapId() const { return 1; }
    uint32 GetPhaseMask() const { return 1; }
    Map* GetMap() { return &map; }
    uint32 GetQuestStatus(uint32) const { return status; }
    uint32 GetQuestObjectiveCounter(uint32) const { return counter; }
    Session* GetSession() { return &session; }
    bool IsAlive() const { return true; }
    bool GetGroup() const { return false; }
    bool IsInCombat() const { return false; }
    bool IsMounted() const { return false; }
    bool HasUnitState(uint32) const { return false; }
    bool IsNonMeleeSpellCasted(bool) const { return false; }
    auto const& GetLootView() const { return view; }
    bool IsAllowedToLoot(Creature*) const { return allowed; }
    bool IsWithinDistInMap(Creature*, float) const { return true; }
    bool IsWithinLOSInMap(Creature*) const { return los; }
    void SendLoot(ObjectGuid guid, int type) { assert(guid==15 && type==LOOT_CORPSE); ++opens; view.emplace(71,guid); }
    int CanStoreNewItem(int, int, ItemPosCountVec&, uint32 item, uint32 count) const {
        assert(item==49208 && count==1); return full ? 1 : EQUIP_ERR_OK;
    }
};
void Session::HandleAutostoreLootItemOpcode(WorldPackets::Loot::LootItem& request) {
    assert(request.guids.size()==1 && request.guids[0]==71 && bot->view.at(71)==15);
    assert(request.lootSlots.size()==1 && request.lootSlots[0]==0);
    ++bot->stores;
    if (bot->grant) ++bot->counter;
}
void Session::HandleLootReleaseOpcode(WorldPackets::Loot::LootRelease& release) {
    assert(release.Unit==15 && bot->view.at(71)==15); ++bot->releases; bot->view.erase(71);
}
'''
tests = r'''
int main() {
    using namespace BotLife;
    QuestPlanData data{14371,"A Gigantic Snack",QuestPlanReason::None,{}, {},
        {{253749,49208,8,{},QuestObjectiveKind::Loot}}};
    QuestSpawn target{243966,36304,1,1,0,0,0};
    for (int test=0;test<9;++test) {
        Player bot;
        Creature corpse;
        bot.map.corpse=&corpse;
        corpse.recipient=&bot;
        assert(FindQuestCorpse(bot,15,target)==&corpse);
        assert(!FindQuestCorpse(bot,16,target));
        corpse.phase=2;
        assert(!FindQuestCorpse(bot,15,target));
        corpse.phase=1;
        if (test==1) corpse.recipient=nullptr;
        if (test==2) corpse.loot.present=false;
        if (test==3) bot.full=true;
        if (test==4) bot.grant=false;
        if (test==5) bot.view.emplace(72,16);
        if (test==6) bot.status=0;
        if (test==7) bot.los=false;
        if (test==8) corpse.loot.questDrop=false;
        char const* expected[]={"looted","loot-not-owned","loot-item-not-available","loot-storage-refused",
            "loot-no-quest-progress","loot-interaction-blocked","loot-objective-inactive","loot-out-of-range",
            "loot-item-not-available"};
        assert(TryLootQuestItem(bot,corpse,data)==std::string_view(expected[test]));
        assert(bot.counter==(test==0));
        assert(bot.stores==(test==0 || test==4));
        assert(bot.releases==bot.opens && bot.opens==(test==0 || (test>=2 && test<=4) || test==8));
        assert(bot.view.size()==(test==5));
    }
}
'''
with tempfile.TemporaryDirectory(prefix='botlife-loot-') as directory:
    cpp = Path(directory) / 'loot.cpp'
    binary = Path(directory) / 'loot'
    cpp.write_text(mocks + '\nnamespace BotLife' + adapter + tests)
    subprocess.run([compiler, '-std=c++20', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-UNDEBUG', '-I', str(module), str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
