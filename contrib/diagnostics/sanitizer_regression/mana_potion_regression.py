#!/usr/bin/env python3
"""Real mana-potion Action with bounded item/native-cast doubles; native effects require live test."""
from pathlib import Path
import subprocess
import sys
import tempfile
root,compiler=Path(sys.argv[1]),sys.argv[2]
base=root/'modules/mod_playerbots/src/strategy/actions'
def without_includes(text):
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#include'))
prefix = r'''
#include <cassert>
#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>
#include <map>
constexpr int POWER_MANA=0,SPELL_EFFECT_ENERGIZE=30;
using uint32=uint32_t; using int32=int32_t; using uint8=uint8_t; using ObjectGuid=uint32;
constexpr int ITEM_CLASS_WEAPON=2, TEMP_ENCHANTMENT_SLOT=1, ITEM_SPELLTRIGGER_ON_USE=0,
 ITEM_PROTO_FLAG_USEABLE_IN_ARENA=1, ITEM_PROTO_FLAG_NOT_USEABLE_IN_ARENA=2,
 EQUIP_ERR_OK=0, INVENTORY_SLOT_BAG_0=255, EQUIPMENT_SLOT_MAINHAND=15,
 SPELL_EFFECT_ENCHANT_ITEM_TEMPORARY=54, BIND_ON_USE=2, BIND_ON_ACQUIRE=1, BIND_QUEST=4,
 ITEM_CHANGED=1, CURRENT_GENERIC_SPELL=1, SPELL_CAST_OK=0, UNIT_STATE_LOST_CONTROL=1;
struct Event {};
struct SpellEffectInfo { int Effect=0; int MiscValue=0; };
struct SpellInfo { uint32 Id=0, MaxLevel=200; SpellEffectInfo Effects[3]; bool HasEffect(int effect)const{return Effects[0].Effect==effect;} };
struct SpellMgr { std::map<uint32,SpellInfo> info; SpellInfo const* GetSpellInfo(uint32 id) {
 auto i=info.find(id);return i==info.end()?nullptr:&i->second; } } mgr;
SpellMgr* sSpellMgr=&mgr;
struct ItemTemplate {
 uint32 Class=ITEM_CLASS_WEAPON, ItemLevel=100, RequiredLevel=5, Flags=0, Bonding=0;
 struct Use { int32 SpellId=0; int SpellTrigger=0; } Spells[5];
};
struct Item {
 uint32 id=0,guid=0,owner=1,enchant=0; int bag=255,slot=23;
 bool trade=false,broken=false,fit=true,bound=false,usable=true; ItemTemplate proto;
 uint32 GetEntry(){return id;} ObjectGuid GetGUID(){return guid;} ObjectGuid GetOwnerGUID(){return owner;}
 bool IsPotion(){return proto.Class==0;} bool IsInTrade(){return trade;} bool IsBroken(){return broken;} ItemTemplate const* GetTemplate(){return &proto;}
 uint32 GetEnchantmentId(int){return enchant;} bool IsFitToSpellRequirements(SpellInfo const*){return fit;}
 int GetBagSlot(){return bag;} int GetSlot(){return slot;} bool IsSoulBound(){return bound;}
 void SetState(int,struct Player*){} void SetBinding(bool v){bound=v;}
};
struct Battleground { bool arena=false,rated=false; bool IsArena()const{return arena;} bool IsRatedBG()const{return rated;} } bg;
struct SpellHistory { bool ready=true; bool IsReady(uint32,uint32){return ready;} } history;
struct Spell { SpellInfo const* info=nullptr; uint32 m_castItemGUID=0; int result=0;
 SpellInfo const* GetSpellInfo(){return info;} int GetCastResult(){return result;} int GetCastTime(){return 3000;} } cast;
struct Player; struct SpellCastTargets { Player* unit=nullptr; void SetUnitTarget(Player* p){unit=p;} };
struct Player {
 bool world=true,alive=true,combat=true,moving=false,mounted=false,flight=false,teleport=false,
 vehicle=false,transport=false,charmed=false,lost=false,casting=false,healer=false,caster=true;
 std::vector<Item*> inventory,bank; Item* weapon=nullptr; Spell* current=nullptr;
 uint32 mana=10,maxMana=1000; int powerType=0;
 uint32 GetPower(int){return mana;} uint32 GetMaxPower(int){return maxMana;} int GetPowerType(){return powerType;}
 int dispatch=0,calls=0; uint32 calledItem=0,calledWeapon=0;
 bool IsInWorld(){return world;} bool IsAlive(){return alive;} bool IsInCombat(){return combat;}
 bool isMoving(){return moving;} bool IsMounted(){return mounted;} bool IsInFlight(){return flight;}
 bool IsBeingTeleported(){return teleport;} bool GetVehicle(){return vehicle;} bool GetTransport(){return transport;}
 bool IsCharmed(){return charmed;} bool HasUnitState(int){return lost;} bool IsNonMeleeSpellCasted(bool){return casting;}
 ObjectGuid GetGUID(){return 1;} SpellHistory* GetSpellHistory(){return &history;}
 Battleground const* GetBattlegorund(){return &bg;} int CanUseItem(Item* i){return i->usable?0:1;}
 Item* GetItemByPos(int,int){return weapon;}
 Item* GetUseableItemByPos(int b,int s){for(auto* i:inventory)if(i->bag==b&&i->slot==s)return i;return nullptr;}
 Item* GetItemByGuid(uint32 guid){return weapon && weapon->guid==guid?weapon:nullptr;}
 Spell* GetCurrentSpell(int){return current;}
 template<class F> bool DoForEachItem(F f,bool inv,bool bags,bool eq,bool bn,bool bb){
  assert(inv&&bags&&!eq&&!bn&&!bb);for(auto* i:inventory)if(f(i))return true;return false;}
 void CastItemUseSpell(Item* potion,SpellCastTargets const& t,int count,int glyph){
  ++calls;calledItem=potion->id;assert(t.unit==this&&count==1&&glyph==0);
  if(dispatch==1)mana+=100;
  if(dispatch==2){cast.info=&mgr.info[potion->proto.Spells[0].SpellId];cast.m_castItemGUID=potion->guid;current=&cast;}
  if(dispatch==3){mana+=100;inventory.clear();delete potion;}
 }

};
struct PlayerBotSpec {static bool IsHeal(Player* p,bool){return p->healer;} static bool IsCaster(Player* p,bool){return p->caster;}};
struct PlayerbotAI { Player* bot; int delay=0; void SetNextCheckDelay(int d){delay=d;} };
struct Action { PlayerbotAI* botAI; Player* bot; std::string name;
 Action(PlayerbotAI* ai,std::string n):botAI(ai),bot(ai->bot),name(n){} virtual ~Action()=default;
 virtual bool isUseful(){return true;} virtual bool isPossible(){return true;} virtual bool Execute(Event){return false;}};
struct ScriptMgr {bool handled=false; bool OnItemUse(Player*,Item*,SpellCastTargets const&){return handled;}} scripts;
ScriptMgr* sScriptMgr=&scripts;
'''
checks = r'''
int main(){
 Player p;PlayerbotAI ai{&p};ManaPotionAction action(&ai);
 Item oil;oil.id=2455;oil.guid=20;oil.proto.Class=0;oil.proto.Spells[0].SpellId=437;
 mgr.info[437]={437,0,{{30,0}}};
 assert(!action.isUseful()&&!action.Execute({}));p.bank={&oil};assert(!action.isUseful());
 p.inventory={&oil};assert(action.isUseful()&&action.isPossible());
 assert(!action.Execute({})&&p.calls==1); // dispatch alone is not success
 for(bool* flag:{&p.mounted,&p.flight,&p.teleport,&p.vehicle,&p.charmed,&p.lost,&p.casting}){
  *flag=true;int n=p.calls;assert(!action.isUseful()&&!action.Execute({})&&p.calls==n);*flag=false;}
 for(bool* flag:{&p.world,&p.alive,&p.combat}){*flag=false;assert(!action.isUseful());*flag=true;}
 p.mana=p.maxMana;assert(!action.isUseful());p.mana=10;
 p.powerType=1;assert(!action.isUseful());p.powerType=0;
 oil.owner=2;assert(!action.isUseful());oil.owner=1;
 oil.trade=true;assert(!action.isUseful());oil.trade=false;
 oil.usable=false;assert(!action.isUseful());oil.usable=true;
 oil.proto.Class=2;assert(!action.isUseful());oil.proto.Class=0;
 oil.proto.Spells[0].SpellId=438;assert(!action.isUseful());oil.proto.Spells[0].SpellId=437;
 oil.id=43570;assert(!action.isUseful());oil.id=2455;
 mgr.info[437].Effects[0].MiscValue=1;assert(!action.isUseful());mgr.info[437].Effects[0].MiscValue=0;
 history.ready=false;assert(!action.isUseful()&&!action.Execute({}));history.ready=true;
 for(bool* flag:{&bg.arena,&bg.rated}){*flag=true;assert(!action.isUseful());oil.proto.Flags=1;assert(action.isUseful());oil.proto.Flags=3;assert(!action.isUseful());*flag=false;oil.proto.Flags=0;}
 Item strong=oil;strong.id=76098;strong.guid=21;strong.slot=24;strong.proto.RequiredLevel=85;strong.proto.Spells[0].SpellId=105709;
 mgr.info[105709]={105709,0,{{30,0}}};p.inventory.push_back(&strong);
 p.dispatch=1;assert(action.Execute({})&&p.calledItem==76098);strong.usable=false;
 assert(action.Execute({})&&p.calledItem==2455);p.inventory={&oil};
 p.dispatch=2;assert(action.Execute({})&&ai.delay==3000);p.current=nullptr;
 cast.result=1;assert(!action.Execute({}));cast.result=0;p.current=nullptr;
 scripts.handled=true;p.dispatch=0;assert(!action.Execute({}));scripts.handled=false;
 oil.proto.Bonding=BIND_ON_USE;p.dispatch=1;assert(action.Execute({})&&oil.bound);
 // Last-item consumption cannot leave an Action dereferencing freed Item memory.
 p.inventory={new Item(oil)};p.dispatch=3;assert(action.Execute({}));
}
'''
with tempfile.TemporaryDirectory(prefix='loa-mana-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test'
    cpp.write_text(prefix+without_includes((base/'ManaPotionAction.h').read_text())+without_includes((base/'ManaPotionAction.cpp').read_text())+checks)
    subprocess.run([compiler,'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('Mana potion selection, native result, ownership, cooldown and consumed-item lifetime passed')
