#!/usr/bin/env python3
"""Actual readiness, local safety and service adapters with controlled native APIs."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
module = root / "modules/mod_botlife/src"


def body(name):
    return "\n".join(line for line in (module / name).read_text().splitlines() if not line.startswith("#"))


mocks = r'''
#include "BotLifeReadiness.h"
#include "BotLifeSafety.h"
#include "BotLifeCombatAssessment.h"
#include "BotLifeTravel.h"
#include <cassert>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <functional>
#include <list>
#include <map>
#include <memory>
#include <optional>
#include <limits>
using uint8=uint8_t; using uint32=uint32_t; using uint64=uint64_t;
enum { EQUIPMENT_SLOT_START=0, EQUIPMENT_SLOT_HEAD=0, EQUIPMENT_SLOT_NECK=1,
       EQUIPMENT_SLOT_BODY=3, EQUIPMENT_SLOT_CHEST=4, EQUIPMENT_SLOT_LEGS=6,
       EQUIPMENT_SLOT_HANDS=9, EQUIPMENT_SLOT_MAINHAND=15, EQUIPMENT_SLOT_OFFHAND=16,
       EQUIPMENT_SLOT_RANGED=17, EQUIPMENT_SLOT_TABARD=18, EQUIPMENT_SLOT_END=19,
       INVENTORY_SLOT_BAG_0=255 };
enum { ITEM_CLASS_ARMOR=4, ITEM_CLASS_WEAPON=2, ITEM_SUBCLASS_ARMOR_SHIELD=6 };
enum { ITEM_SUBCLASS_WEAPON_BOW=2, ITEM_SUBCLASS_WEAPON_GUN=3, ITEM_SUBCLASS_WEAPON_CROSSBOW=18,
       SPEC_SHAMAN_ENHANCEMENT=263, SPEC_PALADIN_PROTECTION=66, SPEC_WARRIOR_PROTECTION=73 };
enum { ITEM_FIELD_DURABILITY, ITEM_FIELD_MAX_DURABILITY };
enum { POWER_MANA, POWER_RAGE, CLASS_HUNTER=3, CLASS_ROGUE=4 };
enum { CREATURE_TYPE_CRITTER=8 };
enum { EQUIP_ERR_OK, PLAYERSPELL_REMOVED, SPELL_EFFECT_SCHOOL_DAMAGE,
       SPELL_EFFECT_WEAPON_DAMAGE, SPELL_EFFECT_NORMALIZED_WEAPON_DMG,
       SPELL_EFFECT_WEAPON_PERCENT_DAMAGE, SPELL_AURA_PERIODIC_DAMAGE };
enum { IDLE_MOTION_TYPE, UNIT_NPC_FLAG_REPAIR=1, UNIT_FIELD_NPC_FLAGS=2,
       UNIT_STAND_STATE_STAND=0, UNIT_STAND_STATE_SIT=1 };
uint32 clockMs=1;
uint32 getMSTime() { return clockMs; }
uint32 GetMSTimeDiffToNow(uint32 start) { return clockMs-start; }
#define TC_LOG_INFO(...) ((void)0)
struct ItemTemplate { uint32 Class=ITEM_CLASS_ARMOR,SubClass=0,ItemLevel=56; };
struct Item {
    ItemTemplate proto; uint32 durability=100,maximum=100; bool usable=true;
    ItemTemplate const* GetTemplate() const { return &proto; }
    uint32 GetUInt32Value(uint32 field) const { return field==ITEM_FIELD_DURABILITY?durability:maximum; }
    bool IsBroken() const { return maximum && !durability; }
};
struct PlayerSpell { uint32 state=0; bool disabled=false,active=true; };
struct Effect { uint32 Effect=SPELL_EFFECT_SCHOOL_DAMAGE, ApplyAuraName=0; };
struct SpellInfo { std::vector<Effect> Effects{{}}; bool passive=false; bool IsPassive() const { return passive; } };
struct SpellMgr { SpellInfo spell; SpellInfo const* GetSpellInfo(uint32) { return &spell; } } spellMgr;
auto* sSpellMgr=&spellMgr;
struct Creature;
struct Map {
    std::map<uint32,Creature*> creatures;
    Creature* GetCreatureBySpawnId(uint32 guid) { auto i=creatures.find(guid); return i==creatures.end()?nullptr:i->second; }
};
struct Guid { uint32 id; uint32 GetCounter() const { return id; } };
struct Spline {
    struct Point { float x,y,z; };
    bool finalized=true; std::vector<Point> path;
    int current=0;
    bool Finalized() const { return finalized; }
    auto const& getPoints() const { return path; }
    Spline const& _Spline() const { return *this; }
    int _currentSplineIdx() const { return current; }
    int last() const { return int(path.size())-1; }
};
struct Motion { uint32 type=0; uint32 GetCurrentMovementGeneratorType() const { return type; } };
struct Creature {
    uint32 guid=1,entry=10,phase=1,level=56,type=1; float x=0,y=0,z=0;
    bool alive=true,combat=false,evade=false,elite=false,hostile=false,attackable=false,repair=true;
    bool IsAlive() const { return alive; } bool IsInCombat() const { return combat; }
    bool IsInEvadeMode() const { return evade; } bool isElite() const { return elite; }
    bool HasFlag(uint32,uint32) const { return repair; }
    template<class T> bool IsHostileTo(T*) const { return hostile; }
    float attackDistance=15,m_CombatDistance=0,size=0;
    template<class T> float GetAggroRange(T*) const { return 0; } // Native non-pet behaviour.
    template<class T> float GetAttackDistance(T*) const { return attackDistance; }
    float GetObjectSize() const { return size; }
    uint32 GetSpawnId() const { return guid; } uint32 GetEntry() const { return entry; }
    uint32 GetCreatureType() const { return type; }
    uint32 GetPhaseMask() const { return phase; } uint32 GetLevel() const { return level; }
    Guid GetGUID() const { return {guid}; }
    float GetPositionX() const { return x; } float GetPositionY() const { return y; } float GetPositionZ() const { return z; }
};
class Player {
public:
    uint32 level=56,cls=7,spec=263,power=POWER_MANA,phase=1;
    float health=100,mana=100,x=0,y=0,z=0;
    bool sickness=false,sitting=false,combat=false,casting=false,mounted=false,interact=true;
    uint64 money=100; uint32 repairs=0;
    Map map; Motion motion; Spline spline; Spline* movespline=&spline;
    std::map<uint8,Item> items;
    PlayerSpell known; std::map<uint32,PlayerSpell*> spells{{1,&known}};
    Player() {
        for(uint8 slot : {0,2,4,5,6,7,8,9,15,16}) items[slot]={};
        items[15].proto.Class=items[16].proto.Class=ITEM_CLASS_WEAPON;
    }
    uint32 GetLevel() const { return level; } uint32 GetClass() const { return cls; }
    uint32 GetTalentSpecialization() const { return spec; } uint32 GetPowerType() const { return power; }
    uint32 GetMaxPower(uint32) const { return 100; } float GetPowerPct(uint32) const { return mana; }
    float GetHealthPct() const { return health; } bool HasAura(uint32) const { return sickness; }
    Item* GetItemByPos(uint8,uint8 slot) { auto i=items.find(slot); return i==items.end()?nullptr:&i->second; }
    uint32 CanUseItem(Item* item) const { return item->usable?EQUIP_ERR_OK:99; }
    auto const& GetSpellMap() const { return spells; }
    bool IsInCombat() const { return combat; } bool IsNonMeleeSpellCasted(bool) const { return casting; }
    bool IsMounted() const { return mounted; } bool IsSitState() const { return sitting; }
    void SetStandState(uint32 state) { sitting=state==UNIT_STAND_STATE_SIT; }
    Motion* GetMotionMaster() { return &motion; } Map* GetMap() { return &map; }
    float size=0; float GetObjectSize() const { return size; }
    Guid GetGUID() const { return {584}; } uint32 GetMapId() const { return 1; }
    uint32 GetInstanceId() const { return 0; } uint32 GetPhaseMask() const { return phase; }
    float GetPositionX() const { return x; } float GetPositionY() const { return y; } float GetPositionZ() const { return z; }
    float GetDistance(Creature* npc) const { return std::sqrt((npc->x-x)*(npc->x-x)+(npc->y-y)*(npc->y-y)+(npc->z-z)*(npc->z-z)); }
    bool IsWithinDistInMap(Creature* npc,float r) const { return GetDistance(npc)<=r; }
    bool CanSeeOrDetect(Creature* npc) const { return (phase&npc->phase)!=0; }
    bool IsValidAttackTarget(Creature* npc) const { return npc->attackable; }
    bool IsHostileTo(Creature* npc) const { return npc->hostile; }
    Creature* GetNPCIfCanInteractWith(Guid guid,uint32) {
        auto* npc=map.GetCreatureBySpawnId(guid.id);
        return interact && npc && npc->alive && npc->repair && !npc->hostile && CanSeeOrDetect(npc) && GetDistance(npc)<5?npc:nullptr;
    }
    uint64 GetMoney() const { return money; }
    float GetReputationPriceDiscount(Creature*) const { return 0.8f; }
    uint32 DurabilityRepairAll(bool cost,float discount,bool guild) {
        assert(cost && discount==0.8f && !guild); ++repairs;
        if(money>=25) { money-=25; for(auto& [slot,item]:items) item.durability=item.maximum; }
        return 0; // Real native return value excludes personal-money repairs.
    }
};
struct PlayerbotAI { Player* bot; Player* GetBot() const { return bot; } };
namespace Trinity {
template<class Check> struct CreatureListSearcher {
    std::list<Creature*>& output; Check& check;
    CreatureListSearcher(Player*,std::list<Creature*>& out,Check& c):output(out),check(c){}
};
}
namespace Cell {
template<class Search> void VisitAllObjects(Player* bot,Search& search,float) {
    for(auto const& [id,npc]:bot->map.creatures) if(search.check(npc)) search.output.push_back(npc);
}
}
namespace BotLife {
bool opponentAllowed=true;
CombatAssessment AssessRouteOpponent(Player&, Creature&, bool) {
    return {opponentAllowed, opponentAllowed?"manageable":"insufficient-health-reserve"};
}
class NativeTravelMovement final : public TravelMovement {
    Player& bot;
public:
    static inline bool owns=false,valid=true;
    explicit NativeTravelMovement(PlayerbotAI& ai,std::function<bool()> = {}):bot(*ai.GetBot()){}
    bool IsValid(TravelTarget const&) const override { return valid; }
    bool IsBlocked() override { return bot.combat; }
    bool HasArrived(TravelTarget const& t) const override { return std::abs(t.x-bot.x)<3; }
    TravelMoveResult Move(TravelTarget const&) override { owns=true; return TravelMoveResult::Started; }
    TravelMotion Poll() const override { return TravelMotion::Moving; }
    bool HasProgressed() const override { return true; }
    bool OwnsMovement() const override { return owns; }
    void Release() override { owns=false; }
};
}
'''

tests = r'''
using namespace BotLife;
struct Scene {
    Player bot; PlayerbotAI ai{&bot}; QuestSafety safety{bot}; QuestPreparation prep{ai,safety}; Creature vendor;
    Scene() { opponentAllowed=true; clockMs=1; NativeTravelMovement::owns=false; NativeTravelMovement::valid=true; bot.map.creatures[1]=&vendor; }
};
int main() {
    { Scene s; s.bot.health=80; assert(s.prep.Update(1)==PreparationResult::Ready);
      s.prep.RequireRecovery(); assert(s.prep.Update(1)==PreparationResult::Waiting);
      s.bot.health=90; assert(s.prep.Update(1)==PreparationResult::Ready); }
    { Scene s; auto r=ReadCombatReadiness(s.bot); assert(EvaluateReadiness(r,false).state==Preparation::Ready);
      s.bot.items.clear(); assert(s.prep.Update(1)==PreparationResult::Failed && !s.bot.repairs); }
    { Scene s; s.bot.items.erase(16); assert(EvaluateReadiness(ReadCombatReadiness(s.bot),false).state==Preparation::Unprepared); }
    { Scene s; s.bot.cls=CLASS_HUNTER; s.bot.spec=0; assert(!ReadCombatReadiness(s.bot).weapon);
      s.bot.items[15].proto.SubClass=ITEM_SUBCLASS_WEAPON_BOW; assert(ReadCombatReadiness(s.bot).weapon); }
    { Scene s; s.bot.spec=SPEC_WARRIOR_PROTECTION; assert(!ReadCombatReadiness(s.bot).offhand);
      s.bot.items[16].proto.Class=ITEM_CLASS_ARMOR; s.bot.items[16].proto.SubClass=ITEM_SUBCLASS_ARMOR_SHIELD;
      assert(ReadCombatReadiness(s.bot).offhand); }
    { Scene s; s.bot.items[15].usable=false; assert(s.prep.Update(1)==PreparationResult::Failed); }
    { Scene s; s.bot.spells.clear(); assert(s.prep.Update(1)==PreparationResult::Failed); }
    { Scene s; s.bot.known.disabled=true; assert(!ReadCombatReadiness(s.bot).combatSpell); }
    { Scene s; s.bot.items[4].durability=0; auto r=ReadCombatReadiness(s.bot);
      assert(r.broken && EvaluateReadiness(r,false).state==Preparation::Repair); }
    { Scene s; s.bot.items[4].durability=s.bot.items[4].maximum=0;
      assert(EvaluateReadiness(ReadCombatReadiness(s.bot),false).state==Preparation::Ready); }
    { Scene s; for(auto& [slot,item]:s.bot.items) item.proto.ItemLevel=1;
      assert(s.prep.Update(1)==PreparationResult::Failed); }
    { Scene s; s.bot.health=50; assert(s.prep.Update(1)==PreparationResult::Waiting && s.bot.sitting);
      assert(s.bot.health==50 && s.bot.money==100 && !s.bot.repairs && s.prep.HoldsNonCombat());
      s.bot.health=80; assert(s.prep.Update(1)==PreparationResult::Waiting);
      s.bot.health=90; assert(s.prep.Update(1)==PreparationResult::Ready && !s.bot.sitting && !s.prep.HoldsNonCombat()); }
    { Scene s; s.bot.mana=20; assert(s.prep.Update(1)==PreparationResult::Waiting);
      s.bot.mana=60; assert(s.prep.Update(1)==PreparationResult::Waiting);
      s.bot.mana=80; assert(s.prep.Update(1)==PreparationResult::Ready); }
    { Scene s; s.bot.power=POWER_RAGE; s.bot.mana=0; assert(s.prep.Update(1)==PreparationResult::Ready); }
    { Scene s; s.bot.sickness=true; assert(s.prep.Update(1)==PreparationResult::Waiting);
      assert(s.prep.Update(600000)==PreparationResult::Failed && s.bot.sickness); }
    { Scene s; s.bot.health=50; s.bot.motion.type=9; assert(s.prep.Update(1)==PreparationResult::Waiting && !s.bot.sitting);
      assert(s.bot.motion.type==9); s.prep.Pause(); assert(s.bot.motion.type==9); }
    { Scene s; s.bot.items[4].durability=0; assert(s.prep.Update(1)==PreparationResult::Waiting);
      assert(s.bot.repairs==1 && s.bot.money==75 && !s.bot.items[4].IsBroken());
      assert(s.prep.Update(1)==PreparationResult::Ready && s.bot.repairs==1); }
    { Scene s; s.bot.items[4].durability=0; s.bot.money=0;
      assert(s.prep.Update(1)==PreparationResult::Failed && s.bot.repairs==1 && s.bot.items[4].IsBroken()); }
    for(int mode=0;mode<6;++mode) { Scene s; s.bot.items[4].durability=0;
      switch(mode) { case 0:s.bot.map.creatures.clear();break; case 1:s.vendor.hostile=true;break;
        case 2:s.vendor.alive=false;break; case 3:s.vendor.phase=2;break;
        case 4:s.bot.interact=false;break; case 5:s.vendor.repair=false;break; }
      assert(s.prep.Update(1)==PreparationResult::Failed && !s.bot.repairs && s.bot.money==100); }
    { Scene s; s.bot.items[4].durability=0; s.vendor.x=50;
      assert(s.prep.Update(1)==PreparationResult::Waiting && s.prep.ControlsMovement());
      s.prep.Pause(); assert(!s.prep.ControlsMovement()); }
    // Local adds, elites, changing patrols, real curved route, death-area expiry.
    { std::vector<LocalThreat> threats{{8,{80,0,0},15,true},{4,{40,0,0},10,true}};
      LocalThreat const* blocker=nullptr;
      assert(!SafeThreatSegment(threats,{0,0,0},{100,0,0},0,&blocker) && blocker->spawn==4);
      std::reverse(threats.begin(),threats.end());
      assert(!SafeThreatSegment(threats,{0,0,0},{100,0,0},0,&blocker) && blocker->spawn==4);
      assert(!SafeThreatSegment(threats,{0,0,0},{100,0,0},4,&blocker) && blocker->spawn==8);
      threats={{4,{40,0,0},10,true},{8,{60,0,0},35,true}};
      assert(!SafeThreatSegment(threats,{0,0,0},{100,0,0},0,&blocker) && blocker->spawn==8); // Boundary, not centre.
      threats[1].aggressive=false;
      assert(!SafeThreatSegment(threats,{0,0,0},{100,0,0},0,&blocker) && blocker->spawn==4);
      assert(SafeThreatSegment(threats,{0,0,0},{10,0,0},0,&blocker) && !blocker);
      threats={{8,{0,0,0},10,true},{4,{0,0,0},10,true}};
      assert(!SafeThreatSegment(threats,{0,0,0},{0,0,0},0,&blocker) && blocker->spawn==4); }
    { Scene s; Creature mob; mob.guid=2; mob.x=70; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; s.safety.SetTarget(0);
      assert(s.safety.CanApproach({0,0,1,1,20,0,0})); // 50m standoff, no exemption.
      assert(!s.safety.CanApproach({0,0,1,1,70,0,0}));
      s.bot.spline.finalized=false; s.bot.spline.path={{0,0,0},{70,0,0},{20,0,0}};
      assert(!s.safety.RouteSafe()); // Safe endpoint cannot excuse unsafe native detour.
      s.bot.spline.finalized=true; mob.x=40; clockMs+=500;
      assert(!s.safety.CanApproach({0,0,1,1,20,0,0})); } // Patrol invalidates staging.
    { Scene s; Creature mob; mob.guid=2; mob.x=25; mob.hostile=mob.attackable=true; mob.attackDistance=20;
      s.bot.map.creatures[2]=&mob;
      assert(mob.GetAggroRange(&s.bot)==0 && !s.safety.CanRest()); // Must not use pet-only radius.
      mob.x=35; mob.m_CombatDistance=5; mob.size=2; s.bot.size=2; clockMs+=500;
      assert(!s.safety.CanRest()); // 20 + 5 + 2 + 2 + 8, including native object radii.
      mob.x=38; clockMs+=500; assert(s.safety.CanRest()); }
    { Scene s; Creature mob; mob.guid=2; mob.x=40; mob.hostile=mob.attackable=true; mob.repair=false;
      s.bot.map.creatures[2]=&mob; s.safety.SetTarget(2);
      QuestSpawn target{2,10,1,1,40,0,0}; assert(s.safety.CanApproach(target));
      Creature add=mob; add.guid=3; add.y=10; s.bot.map.creatures[3]=&add; clockMs+=500;
      assert(!s.safety.CanApproach(target)); add.y=100; clockMs+=500;
      assert(s.safety.CanApproach(target) && !s.safety.Blocker()); mob.elite=true; mob.level=60; clockMs+=500;
      assert(s.safety.CanApproach(target)); // Rank/level alone never veto an assessed target.
      opponentAllowed=false; assert(!s.safety.CanApproach(target));
      assert(!strcmp(s.safety.Reason(),"insufficient-health-reserve"));
      assert(s.safety.Blocker()==2); }
    { Scene s; Creature add; add.guid=2; add.x=30; add.y=40; add.hostile=add.attackable=true;
      s.bot.map.creatures[2]=&add; s.bot.spline.finalized=false;
      s.bot.spline.path={{0,0,0},{30,40,0},{60,0,0}};
      assert(!s.safety.RouteSafe());
      assert(!strcmp(s.safety.Reason(),"hostile-on-route") && s.safety.Blocker()==2); }
    { Scene s; s.safety.RememberDeath(); s.bot.spline.finalized=false;
      s.bot.spline.path={{0,0,0},{0,0,0},{60,0,0}};
      assert(s.safety.RouteSafe()); } // Duplicate start points don't prevent escaping death area.
    { Scene s; s.safety.RememberDeath(); QuestSpawn near{2,10,1,1,10,0,0},far{3,10,1,1,60,0,0};
      assert(!s.safety.CanApproach(near) && s.safety.CanApproach(far)); clockMs+=300000;
      assert(s.safety.CanApproach(near)); }
    { Scene s; s.safety.RememberDeath(); s.bot.x=10;
      assert(!s.safety.CanApproach({3,10,1,1,-60,0,0})); } // Cannot cross centre while "escaping".
    { Scene s; Creature mob; mob.guid=2; mob.x=5; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; s.bot.health=20;
      assert(s.prep.Update(1)==PreparationResult::Waiting && !s.bot.sitting); }
    { Scene s; Creature neutral; neutral.guid=2; neutral.x=40; neutral.y=20; neutral.attackable=true;
      s.bot.map.creatures[2]=&neutral; s.safety.SetTarget(3);
      assert(!s.safety.CanApproach({3,10,1,1,40,0,0}));
      assert(!strcmp(s.safety.Reason(),"target-neighbour") && s.safety.Blocker()==2); }
    { Scene s; s.bot.health=20; assert(s.prep.Update(1)==PreparationResult::Waiting && s.bot.sitting);
      Creature patrol; patrol.guid=2; patrol.x=5; patrol.hostile=patrol.attackable=true;
      s.bot.map.creatures[2]=&patrol; clockMs+=500;
      assert(s.prep.Update(500)==PreparationResult::Waiting && !s.bot.sitting); }
    { Scene s; Creature rabbit; rabbit.guid=2; rabbit.x=5; rabbit.type=CREATURE_TYPE_CRITTER; rabbit.attackable=true;
      s.bot.map.creatures[2]=&rabbit;
      assert(s.safety.CanApproach({3,10,1,1,10,0,0})); }
    assert(SegmentDistanceSquared({5,3,0},{0,0,0},{10,0,0})==9);
    assert(!SafeThreatSegment({}, {0,0,0}, {std::numeric_limits<float>::quiet_NaN(),0,0}, 0));
}
'''

production = "\n".join(body(name) for name in (
    "BotLifeReadiness.cpp", "BotLifeSafety.cpp", "BotLifePreparation.h", "BotLifePreparation.cpp"))
for forbidden in ("TeleportTo(", "SetHealth(", "SetPower(", "Randomize(", "RewardQuest(", "CharacterDatabase"):
    assert forbidden not in production, forbidden

with tempfile.TemporaryDirectory(prefix="loa-preparation-") as directory:
    cpp = pathlib.Path(directory) / "test.cpp"
    binary = pathlib.Path(directory) / "test"
    cpp.write_text(mocks + production + tests)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-UNDEBUG", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-I", str(module), str(cpp),
                    str(module / "BotLifeReadinessPolicy.cpp"), str(module / "BotLifeSafetyPolicy.cpp"),
                    str(module / "BotLifeTravel.cpp"), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("BotLife readiness, native paid repair, rest hysteresis and local route safety passed")
