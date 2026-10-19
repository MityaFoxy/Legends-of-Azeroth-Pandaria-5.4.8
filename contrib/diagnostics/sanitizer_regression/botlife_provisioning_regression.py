#!/usr/bin/env python3
"""Native provisioning body: opt-in, empty slots only, bounded and non-destructive."""
import ast
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
module = root / "modules/mod_botlife/src"
fixture = ast.parse((pathlib.Path(__file__).with_name("botlife_preparation_regression.py")).read_text())
mocks = next(ast.literal_eval(n.value) for n in fixture.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "mocks" for t in n.targets))
mocks = mocks.replace("using uint8=", "using int32=int32_t; using uint16=uint16_t; using InventoryResult=int;\nusing uint8=")
mocks = mocks.replace("struct ItemTemplate {", "struct ItemTemplate { struct Stat {uint32 ItemStatType=0; int32 ItemStatValue=0;}; Stat ItemStat[10]; uint32 ItemId=0,RequiredLevel=56,Duration=0,Bonding=0,Quality=2,InventoryType=0;")
mocks = mocks.replace("struct Item {", "struct Item { static Item* CreateItem(uint32,int,Player*,bool); void RemoveFromUpdateQueueOf(Player*) {}")
mocks = mocks.replace("bool sickness=false,", "bool alive=true,ghost=false,group=false,equipAllowed=true; uint32 grants=0,learns=0; bool sickness=false,")
mocks = mocks.replace("uint32 GetLevel() const { return level; } uint32 GetClass()", """
    bool IsAlive() const { return alive; } bool HasFlag(uint32,uint32) const { return ghost; }
    bool GetGroup() const { return group; }
    void LearnDefaultSkills() { ++learns; } void LearnSpecializationSpells() { ++learns; }
    uint32 CanUseItem(ItemTemplate const*) const { return EQUIP_ERR_OK; }
    InventoryResult CanEquipItem(uint8 slot,uint16& dest,Item*,bool swap,bool loading) {
        assert(!swap && loading); dest=(255<<8)|slot; return equipAllowed && !items.count(slot)?0:99;
    }
    Item* EquipNewItem(uint16,uint32,bool);
    uint32 GetLevel() const { return level; } uint32 GetClass()""")
mocks = mocks.replace("Guid GetGUID() const { return {584}; }", "uint32 guid=584; Guid GetGUID() const { return {guid}; }")
mocks = mocks.replace("struct PlayerbotAI { Player* bot;", "struct PlayerbotAI { Player* bot; bool real=false,controlled=false; bool IsRealPlayer() const { return real; } bool HasRealPlayerMaster() const { return controlled; }")

extras = r'''
#include <atomic>
enum { SPEC_NONE=0, PLAYER_FIELD_PLAYER_FLAGS=0, PLAYER_FLAGS_GHOST=16,
       BIND_QUEST=4, ITEM_QUALITY_UNCOMMON=2, ITEM_QUALITY_RARE=3, ITEM_SUBCLASS_ARMOR_MISCELLANEOUS=0 };
enum { ITEM_MOD_AGILITY=3, ITEM_MOD_STRENGTH=4, ITEM_MOD_INTELLECT=5 };
enum { EQUIPMENT_SLOT_SHOULDERS=2,EQUIPMENT_SLOT_WAIST=5,EQUIPMENT_SLOT_FEET=7,
       EQUIPMENT_SLOT_WRISTS=8,EQUIPMENT_SLOT_BACK=14,EQUIPMENT_SLOT_FINGER1=10,
       EQUIPMENT_SLOT_FINGER2=11,EQUIPMENT_SLOT_TRINKET1=12,EQUIPMENT_SLOT_TRINKET2=13 };
enum { INVTYPE_HEAD=1,INVTYPE_NECK,INVTYPE_SHOULDERS,INVTYPE_CHEST,INVTYPE_ROBE,
       INVTYPE_WAIST,INVTYPE_LEGS,INVTYPE_FEET,INVTYPE_WRISTS,INVTYPE_HANDS,INVTYPE_CLOAK,
       INVTYPE_FINGER,INVTYPE_TRINKET,INVTYPE_WEAPON,INVTYPE_WEAPONMAINHAND,
       INVTYPE_2HWEAPON,INVTYPE_RANGED,INVTYPE_RANGEDRIGHT,INVTYPE_WEAPONOFFHAND,INVTYPE_SHIELD,INVTYPE_HOLDABLE };
#define TC_LOG_WARN(...) ((void)0)
struct Config { bool enabled=false; bool GetBoolDefault(char const*,bool) { return enabled; } } config;
auto* sConfigMgr=&config;
struct BotConfig { bool randomBotAutologin=false,randomAccount=true;
    bool IsInRandomAccountList(uint32 account) { return account==42 && randomAccount; }
} botConfig;
auto* sPlayerbotAIConfig=&botConfig;
struct CharacterCache { uint32 GetCharacterAccountIdByGuid(Guid) { return 42; } } characterCache;
auto* sCharacterCache=&characterCache;
struct ItemMgr {
    bool suitable=true;
    bool IsTestItem(uint32) { return false; }
    bool CanEquipWeapon(Player*,ItemTemplate const*) { return suitable; }
    bool CanEquipArmor(Player*,ItemTemplate const*) { return suitable; }
    bool CanEquipSubArmor(Player*,ItemTemplate const*) { return suitable; }
} itemMgr;
auto* sRandomItemMgr=&itemMgr;
struct ObjectMgr { std::map<uint32,ItemTemplate> items; auto const* GetItemTemplateStore() { return &items; } } objectMgr;
auto* sObjectMgr=&objectMgr;
uint32 creates=0;
Item* Item::CreateItem(uint32 id,int,Player*,bool) { ++creates; auto* p=new Item; p->proto=objectMgr.items.at(id); return p; }
Item* Player::EquipNewItem(uint16 dest,uint32 id,bool) { auto& p=items[uint8(dest)]; p.proto=objectMgr.items.at(id); ++grants; return &p; }
namespace BotLife {
bool eligible=true,questMode=true;
bool IsQuestRunEnabled() { return questMode; }
uint32 GetQuestRunBotGuid() { return 584; }
bool IsOnlyEligibleBot(uint32) { return eligible; }
}
'''

tests = r'''
using namespace BotLife;
void catalog() {
    config.enabled=true; eligible=questMode=true; botConfig={}; itemMgr={}; creates=0;
    objectMgr.items.clear(); uint32 id=1;
    for(uint32 type : {INVTYPE_HEAD,INVTYPE_SHOULDERS,INVTYPE_CHEST,INVTYPE_WAIST,INVTYPE_LEGS,
                       INVTYPE_FEET,INVTYPE_WRISTS,INVTYPE_HANDS,INVTYPE_CLOAK,INVTYPE_WEAPON}) {
        ItemTemplate p; p.ItemId=id; p.InventoryType=type;
        if(type==INVTYPE_WEAPON) p.Class=ITEM_CLASS_WEAPON;
        objectMgr.items[id++]=p;
    }
    LoadProvisioningConfig();
}
int main() {
    { catalog(); Player bot; PlayerbotAI ai{&bot}; config.enabled=false; LoadProvisioningConfig(); char const* reason="x";
      assert(ProvisionMissingEquipment(ai,reason) && !bot.learns && !bot.grants); }
    { catalog(); Player bot; bot.items.clear(); bot.items[23].proto.ItemId=7327; PlayerbotAI ai{&bot}; char const* reason="x";
      assert(ProvisionMissingEquipment(ai,reason)); assert(bot.grants==11 && bot.items[23].proto.ItemId==7327);
      assert(bot.level==56 && bot.spec==263 && bot.money==100 && bot.health==100);
      auto count=bot.items.size(); assert(!ProvisionMissingEquipment(ai,reason) && bot.items.size()==count);
      assert(!strcmp(reason,"preparation-already-consumed")); }
    { catalog(); Player bot; bot.items[4].proto.ItemId=999; bot.items[4].durability=12;
      PlayerbotAI ai{&bot}; char const* reason="x"; assert(ProvisionMissingEquipment(ai,reason));
      assert(bot.items[4].proto.ItemId==999 && bot.items[4].durability==12); }
    { catalog(); Player bot; bot.items.clear(); objectMgr.items.clear(); PlayerbotAI ai{&bot}; char const* reason="x";
      assert(!ProvisionMissingEquipment(ai,reason) && !bot.grants); }
    { catalog(); Player bot; auto p=objectMgr.items.begin()->second; p.ItemStat[0]={ITEM_MOD_INTELLECT,20};
      assert(!Suitable(bot,p)); p.ItemStat[0]={ITEM_MOD_AGILITY,20}; assert(Suitable(bot,p)); }
    for(int mode=0;mode<12;++mode) { catalog(); Player bot; PlayerbotAI ai{&bot}; char const* reason="x";
      switch(mode) { case 0:eligible=false;break; case 1:botConfig.randomBotAutologin=true;break;
        case 2:bot.alive=false;break; case 3:bot.ghost=true;break;case 4:bot.combat=true;break;
        case 5:bot.group=true;break;case 6:botConfig.randomAccount=false;break;
        case 7:bot.guid=585;break;case 8:ai.real=true;break;case 9:ai.controlled=true;break;
        case 10:bot.spec=SPEC_NONE;break;case 11:questMode=false;LoadProvisioningConfig();break; }
      assert(!ProvisionMissingEquipment(ai,reason) && !bot.grants && !bot.learns);
      const char* expected[]={"preparation-invalid-roster","preparation-autologin-enabled","preparation-not-alive",
          "preparation-not-alive","preparation-in-combat","preparation-in-group","preparation-not-random-account",
          "preparation-invalid-roster","preparation-player-controlled","preparation-player-controlled",
          "preparation-no-specialization","preparation-invalid-roster"};
      assert(!strcmp(reason,expected[mode])); }
    { catalog(); Player bot; bot.items.erase(15); auto& p=objectMgr.items.rbegin()->second; p.InventoryType=INVTYPE_2HWEAPON;
      PlayerbotAI ai{&bot}; char const* reason="x"; assert(!ProvisionMissingEquipment(ai,reason));
      assert(!bot.items.count(15) && bot.items.count(16)); }
    { catalog(); Player bot; bot.items.clear(); bot.equipAllowed=false; PlayerbotAI ai{&bot}; char const* reason="x";
      assert(!ProvisionMissingEquipment(ai,reason) && !bot.grants && creates<=64*16); }
}
'''

def body(name):
    return "\n".join(line for line in (module / name).read_text().splitlines() if not line.startswith("#"))

production = body("BotLifeProvisioning.cpp")
assert "sRandomPlayerbotMgr" not in production  # Manual login is not automatic-population membership.
for forbidden in ("DestroyItem(", "Randomize(", "SetHealth(", "SetPower(", "SetMoney(", "GiveLevel(", "ResetTalents(", "TeleportTo(", "CharacterDatabase", "SaveToDB("):
    assert forbidden not in production, forbidden
assert "PrepareCharacter = 0" in (module.parent / "config/botlife.conf.dist").read_text()
with tempfile.TemporaryDirectory(prefix="loa-provision-") as directory:
    cpp = pathlib.Path(directory) / "test.cpp"
    binary = pathlib.Path(directory) / "test"
    cpp.write_text(mocks + extras + body("BotLifeReadiness.cpp") + production + tests)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-UNDEBUG", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-I", str(module), str(cpp),
                    str(module / "BotLifeReadinessPolicy.cpp"), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("BotLife explicit missing-slot provisioning preserves existing items and fails closed")
