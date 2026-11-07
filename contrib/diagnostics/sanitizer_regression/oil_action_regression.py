#!/usr/bin/env python3
"""Real oil selector/action with bounded item/world/native-cast doubles.

This validates dispatch and failure propagation, not native enchant/charge effects.
The latter require the separate live fixture described in the source dossier.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
root, compiler = Path(sys.argv[1]), sys.argv[2]
base = root / 'modules/mod_playerbots/src/strategy/actions'

def without_includes(text):
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#include'))

prefix = r'''
#include <cassert>
#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>
#include <map>
using uint32=uint32_t; using int32=int32_t; using uint8=uint8_t; using ObjectGuid=uint32;
constexpr int ITEM_CLASS_WEAPON=2, TEMP_ENCHANTMENT_SLOT=1, ITEM_SPELLTRIGGER_ON_USE=0,
 ITEM_PROTO_FLAG_USEABLE_IN_ARENA=1, ITEM_PROTO_FLAG_NOT_USEABLE_IN_ARENA=2,
 EQUIP_ERR_OK=0, INVENTORY_SLOT_BAG_0=255, EQUIPMENT_SLOT_MAINHAND=15,
 SPELL_EFFECT_ENCHANT_ITEM_TEMPORARY=54, BIND_ON_USE=2, BIND_ON_ACQUIRE=1, BIND_QUEST=4,
 ITEM_CHANGED=1, CURRENT_GENERIC_SPELL=1, SPELL_CAST_OK=0, UNIT_STATE_LOST_CONTROL=1;
struct Event {};
struct SpellEffectInfo { int Effect=0; int MiscValue=0; };
struct SpellInfo { uint32 Id=0, MaxLevel=200; SpellEffectInfo Effects[3]; };
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
 bool IsInTrade(){return trade;} bool IsBroken(){return broken;} ItemTemplate const* GetTemplate(){return &proto;}
 uint32 GetEnchantmentId(int){return enchant;} bool IsFitToSpellRequirements(SpellInfo const*){return fit;}
 int GetBagSlot(){return bag;} int GetSlot(){return slot;} bool IsSoulBound(){return bound;}
 void SetState(int,struct Player*){} void SetBinding(bool v){bound=v;}
};
struct Battleground { bool arena=false,rated=false; bool IsArena()const{return arena;} bool IsRatedBG()const{return rated;} } bg;
struct SpellHistory { bool ready=true; bool IsReady(uint32,uint32){return ready;} } history;
struct Spell { SpellInfo const* info=nullptr; uint32 m_castItemGUID=0; int result=0;
 SpellInfo const* GetSpellInfo(){return info;} int GetCastResult(){return result;} int GetCastTime(){return 3000;} } cast;
struct SpellCastTargets { Item* item=nullptr; void SetItemTarget(Item* p){item=p;} };
struct Player {
 bool world=true,alive=true,combat=false,moving=false,mounted=false,flight=false,teleport=false,
 vehicle=false,transport=false,charmed=false,lost=false,casting=false,healer=false,caster=true;
 std::vector<Item*> inventory,bank; Item* weapon=nullptr; Spell* current=nullptr;
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
 void CastItemUseSpell(Item* oil,SpellCastTargets const& t,int count,int glyph){
  ++calls;calledItem=oil->id;calledWeapon=t.item->guid;assert(count==1&&glyph==0);
  if(dispatch==1)t.item->enchant=mgr.info[oil->proto.Spells[0].SpellId].Effects[0].MiscValue;
  if(dispatch==2){cast.info=&mgr.info[oil->proto.Spells[0].SpellId];cast.m_castItemGUID=oil->guid;current=&cast;}
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
 Player p; PlayerbotAI ai{&p}; ApplyOilAction action(&ai);
 Item weapon;weapon.guid=10;weapon.slot=15;p.weapon=&weapon;
 Item oil;oil.id=20744;oil.guid=20;oil.proto.Spells[0].SpellId=25117;
 mgr.info[25117]={25117,200,{{54,2623}}};
 assert(!action.isUseful());assert(!action.Execute({}));assert(p.calls==0);
 p.bank={&oil};assert(!action.isUseful());
 p.inventory={&oil};assert(action.isUseful());assert(action.isPossible());
 // Native rejection must not become OK just because a request was sent.
 assert(!action.Execute({}));assert(p.calls==1);
 for(bool* flag:{&p.combat,&p.moving,&p.mounted,&p.flight,&p.teleport,&p.vehicle,&p.transport,&p.charmed,&p.lost,&p.casting}){
  *flag=true;int n=p.calls;assert(!action.isUseful());assert(!action.Execute({}));assert(p.calls==n);*flag=false;}
 p.world=false;assert(!action.Execute({}));p.world=true;
 p.alive=false;assert(!action.Execute({}));p.alive=true;
 p.caster=false;assert(!action.isUseful());p.healer=true;assert(action.isUseful());p.healer=false;p.caster=true;
 weapon.proto.ItemLevel=200;assert(action.isUseful());weapon.proto.ItemLevel=201;assert(!action.isUseful());weapon.proto.ItemLevel=100;
 weapon.enchant=123;assert(!action.isUseful());assert(!action.Execute({}));assert(weapon.enchant==123);weapon.enchant=0;
 weapon.owner=2;assert(!action.isUseful());weapon.owner=1;
 weapon.trade=true;assert(!action.isUseful());weapon.trade=false;
 weapon.broken=true;assert(!action.isUseful());weapon.broken=false;
 weapon.fit=false;assert(!action.isUseful());weapon.fit=true;
 weapon.proto.Class=4;assert(!action.isUseful());weapon.proto.Class=2;
 oil.owner=2;assert(!action.isUseful());oil.owner=1;
 oil.trade=true;assert(!action.isUseful());oil.trade=false;
 oil.usable=false;assert(!action.isUseful());oil.usable=true;
 oil.id=36900;assert(!action.isUseful());oil.id=20744;
 oil.proto.Spells[0].SpellId=25118;assert(!action.isUseful());oil.proto.Spells[0].SpellId=25117;
 history.ready=false;assert(!action.isUseful());history.ready=true;
 bg.arena=true;assert(!action.isUseful());oil.proto.Flags=1;assert(action.isUseful());
 oil.proto.Flags=3;assert(!action.isUseful());bg.arena=false;oil.proto.Flags=0;
 // Prefer healer mana oils, but use only available, allowed items.
 Item mana=oil;mana.id=22521;mana.guid=21;mana.slot=24;mana.proto.RequiredLevel=52;mana.proto.Spells[0].SpellId=28013;
 mgr.info[28013]={28013,200,{{54,2677}}};p.inventory.push_back(&mana);
 p.healer=true;p.dispatch=1;assert(action.Execute({}));assert(p.calledItem==22521&&weapon.enchant==2677);
 weapon.enchant=0;p.healer=false;assert(action.Execute({}));assert(p.calledItem==20744&&weapon.enchant==2623);
 assert(!action.Execute({}));weapon.enchant=0;
 // Start of a native cast is accepted only for the matching item/spell/result.
 p.dispatch=2;assert(action.Execute({}));assert(ai.delay==3000);p.current=nullptr;
 cast.result=1;assert(!action.Execute({}));p.current=nullptr;cast.result=0;
 scripts.handled=true;p.dispatch=0;assert(!action.Execute({}));scripts.handled=false;
 p.dispatch=1;oil.proto.Bonding=BIND_ON_USE;assert(action.Execute({}));assert(oil.bound);
}
'''
with tempfile.TemporaryDirectory(prefix='loa-oil-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test'
    cpp.write_text(prefix+without_includes((base/'OilActions.h').read_text())+without_includes((base/'OilActions.cpp').read_text())+checks)
    subprocess.run([compiler,'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('Oil selection, native dispatch and failure contracts passed')
