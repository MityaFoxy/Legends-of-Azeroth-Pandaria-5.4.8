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
#include <string_view>
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
       UNIT_STAND_STATE_STAND=0, UNIT_STAND_STATE_SIT=1, REACT_PASSIVE=0 };
enum { CONFIG_CREATURE_FAMILY_ASSISTANCE_RADIUS };
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
    bool Instanceable() const { return false; }
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
    uint32 guid=1,entry=10,phase=1,level=56,type=1,faction=1; float x=0,y=0,z=0;
    bool alive=true,combat=false,evade=false,elite=false,hostile=false,attackable=false,repair=true,aggressive=false,los=true,civilian=false,passive=false;
    bool IsAlive() const { return alive; } bool IsInCombat() const { return combat; }
    bool IsInEvadeMode() const { return evade; } bool isElite() const { return elite; }
    bool IsCivilian() const { return civilian; }
    bool HasReactState(uint32) const { return passive; }
    bool HasFlag(uint32,uint32) const { return repair; }
    template<class T> bool IsHostileTo(T*) const { return hostile; }
    float attackDistance=15,m_CombatDistance=0,size=0;
    template<class T> float GetAggroRange(T*) const { return 0; } // Native non-pet behaviour.
    template<class T> float GetAttackDistance(T*) const { return attackDistance; }
    float GetObjectSize() const { return size; }
    template<class Friendly, class Enemy> bool CanAssistTo(Friendly const* friendly, Enemy const*) const {
        return aggressive && hostile && faction==friendly->faction;
    }
    bool IsWithinDistInMap(Creature const* other,float radius) const {
        float dx=x-other->x,dy=y-other->y,dz=z-other->z;
        return dx*dx+dy*dy+dz*dz < radius*radius;
    }
    bool IsWithinLOSInMap(Creature const*) const { return los; }
    uint32 GetSpawnId() const { return guid; } uint32 GetEntry() const { return entry; }
    uint32 GetCreatureType() const { return type; }
    uint32 GetPhaseMask() const { return phase; } uint32 GetLevel() const { return level; }
    Guid GetGUID() const { return {guid}; }
    float GetPositionX() const { return x; } float GetPositionY() const { return y; } float GetPositionZ() const { return z; }
};
struct World { float assistanceRadius=10; float getFloatConfig(uint32) const { return assistanceRadius; } } world;
auto* sWorld=&world;
class Player {
public:
    void UpdateAllowedPositionZ(float,float,float&) const {}
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
    bool IsFriendlyTo(Creature* npc) const { return !npc->hostile && !npc->attackable; }
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
enum { PATHFIND_NORMAL=1, PATHFIND_INCOMPLETE=4 };
namespace G3D { struct Vector3 { float x,y,z; Vector3(float a,float b,float c):x(a),y(b),z(c){} }; }
struct PathGenerator {
    static inline bool available=false;
    static inline int type=PATHFIND_NORMAL,calls=0;
    static inline std::vector<BotLife::SafetyPoint> points;
    static inline bool straight=false;
    static inline bool rejectContinuation=false;
    PathGenerator(Player*,uint32 nodes) { assert(nodes==4096); }
    void SetUseWaterShortcut(bool enabled) { assert(!enabled); }
    bool CalculatePath(float x,float y,float z,bool a,bool b,bool c,G3D::Vector3 const* origin) {
      assert(!a && !b && !c && origin); ++calls;
      if(straight) points={{origin->x,origin->y,origin->z},{x,y,z}};
      return available && !(rejectContinuation && x==100 && (origin->x!=0 || origin->y!=0)); }
    bool HasNavigationData() const { return available; }
    int GetPathType() const { return type; }
    auto const& GetPath() const { return points; }
};
namespace BotLife {
bool avoidDefeated=false;
std::vector<DefeatArea> defeatAreas;
std::vector<DefeatArea> GetDefeatAreas(Player const&) { return defeatAreas; }
bool AvoidDefeatedOpponent(Player const&,Creature const&) { return avoidDefeated; }
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
    Scene() { clockMs=1; NativeTravelMovement::owns=false; NativeTravelMovement::valid=true; bot.map.creatures[1]=&vendor;
      defeatAreas.clear(); avoidDefeated=false; PathGenerator::rejectContinuation=false; PathGenerator::straight=false; PathGenerator::available=false; PathGenerator::type=PATHFIND_NORMAL; PathGenerator::calls=0; PathGenerator::points.clear(); }
};
int main() {
    { Scene s; s.vendor.x=40; auto walk=CreateWalkExecutor(60000); walk->Start(s.ai);
      assert(walk->HoldsNonCombat()); assert(walk->Update(s.ai,1)==ActivityResult::Running);
      assert(walk->ControlsMovement()); walk->Pause(s.ai); assert(!walk->ControlsMovement());
      assert(walk->Resume(s.ai)); s.bot.x=40;
      assert(walk->Update(s.ai,1)==ActivityResult::Completed && !walk->ControlsMovement()); }
    { Scene s; auto walk=CreateWalkExecutor(60000); walk->Start(s.ai);
      assert(walk->Update(s.ai,1)==ActivityResult::Failed && !walk->HoldsNonCombat()); } // Too close.
    for(int mode=0;mode<5;++mode) {
      Scene s; s.vendor.x=40; auto walk=CreateWalkExecutor(60000); walk->Start(s.ai); walk->Update(s.ai,1);
      if(mode==0) s.vendor.alive=false;
      if(mode==1) s.vendor.x=50;
      if(mode==2) s.bot.map.creatures.clear();
      if(mode==3) s.vendor.hostile=true;
      if(mode==4) s.vendor.phase=2;
      assert(walk->Update(s.ai,1)==ActivityResult::Failed && !walk->ControlsMovement());
    }
    { Scene s; s.vendor.x=40; auto walk=CreateWalkExecutor(60000); walk->Start(s.ai); walk->Update(s.ai,1);
      assert(walk->Update(s.ai,60000)==ActivityResult::Failed && !walk->ControlsMovement()); }
    { Scene s; s.vendor.x=40; auto walk=CreateWalkExecutor(60000); walk->Start(s.ai); walk->Update(s.ai,1);
      walk->Pause(s.ai); s.vendor.alive=false;
      assert(walk->Resume(s.ai)); // Terminal result returns to policy without dropping cooldown.
      assert(walk->Update(s.ai,1)==ActivityResult::Failed && !walk->ControlsMovement()); }
    { Scene s; s.vendor.x=40; auto walk=CreateWalkExecutor(60000); walk->Start(s.ai); walk->Update(s.ai,1);
      Creature patrol; patrol.guid=2; patrol.x=20; patrol.hostile=patrol.attackable=true;
      s.bot.map.creatures[2]=&patrol; clockMs+=500;
      assert(walk->Update(s.ai,1)==ActivityResult::Failed && !walk->ControlsMovement()); }
    { Scene s; auto leisure=CreateServiceExecutor(ActivityType::Leisure,60000); leisure->Start(s.ai);
      assert(leisure->Update(s.ai,1000)==ActivityResult::Running && s.bot.sitting);
      assert(leisure->HoldsNonCombat() && s.bot.health==100 && s.bot.mana==100);
      leisure->Pause(s.ai); assert(!s.bot.sitting); assert(leisure->Resume(s.ai));
      assert(leisure->Update(s.ai,59000)==ActivityResult::Completed && !s.bot.sitting); }
    { Scene s; s.bot.sitting=true; auto leisure=CreateServiceExecutor(ActivityType::Leisure,60000);
      leisure->Start(s.ai); leisure->Update(s.ai,1000); leisure->Interrupt(s.ai,InterruptReason::Reset);
      assert(s.bot.sitting); }
    { Scene s; s.bot.mounted=true; auto leisure=CreateServiceExecutor(ActivityType::Leisure,60000);
      leisure->Start(s.ai); assert(leisure->Update(s.ai,60000)==ActivityResult::TemporarilyBlocked);
      assert(!s.bot.sitting); assert(leisure->Update(s.ai,30000)==ActivityResult::Failed); }
    { Scene s; auto leisure=CreateServiceExecutor(ActivityType::Leisure,60000); leisure->Start(s.ai);
      leisure->Update(s.ai,1); Creature patrol; patrol.guid=2; patrol.x=5; patrol.hostile=patrol.attackable=true;
      s.bot.map.creatures[2]=&patrol; clockMs+=500;
      assert(leisure->Update(s.ai,500)==ActivityResult::Failed && !s.bot.sitting); }
    { Scene s; s.bot.items[15].durability=10; auto town=CreateServiceExecutor(ActivityType::Town,60000);
      assert(ReadScheduleNeeds(s.ai).service); town->Start(s.ai);
      assert(town->Update(s.ai,1)==ActivityResult::Running && s.bot.repairs==1);
      assert(town->Update(s.ai,1)==ActivityResult::Completed && !ReadScheduleNeeds(s.ai).service); }
    { Scene s; s.bot.items[15].durability=10; s.bot.map.creatures.clear();
      auto town=CreateServiceExecutor(ActivityType::Town,60000); town->Start(s.ai);
      assert(town->Update(s.ai,1)==ActivityResult::Failed && !town->ControlsMovement()); }
    for(int mode=0;mode<4;++mode) {
      Scene s; Creature mob; mob.guid=2; mob.x=50; mob.y=50; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; QuestSpawn goal{3,10,1,1,100,0,0};
      PathGenerator::available=PathGenerator::straight=true;
      assert(s.safety.CanApproach(goal)); // Safe preflight chord.
      s.bot.spline.finalized=false; s.bot.spline.path={{0,0,0},{0,50,0},{100,50,0},{100,0,0}};
      assert(!s.safety.RouteSafe()); // Native route took a different, unsafe corridor.
      s.bot.spline.finalized=true;
      assert(s.safety.CanApproach(goal)); // Must not erase the actual failure.
      if(mode==1) clockMs+=30000; // Snapshot expires.
      if(mode==2) goal.x=150; // Different destination must not inherit it.
      if(mode==3) { mob.x=90; mob.y=0; clockMs+=500; } // Goal danger still takes priority.
      assert(bool(s.safety.FindDetour(goal))==(mode==0));
    }
    { Scene s; defeatAreas.push_back({1,2,1,{50,0,0}});
      assert(!s.safety.CanApproach({3,10,1,1,100,0,0}));
      assert(!strcmp(s.safety.Reason(),"repeated-defeat-area-route"));
      PathGenerator::available=PathGenerator::straight=true;
      assert(s.safety.FindDetour({3,10,1,1,100,0,0})); }
    { Scene s; defeatAreas.push_back({1,2,1,{0,0,0}});
      s.bot.x=2; assert(s.safety.CanApproach({0,0,1,1,8,0,0})); // Escape inside the region.
      s.safety.SetTarget(3);
      assert(!s.safety.CanApproach({3,10,1,1,8,0,0})); // Not permission to attack there.
      assert(s.safety.CanApproach({3,10,1,1,11,0,0})); }
    { Scene s; defeatAreas.push_back({1,2,1,{50,0,0}}); s.bot.z=5;
      assert(s.safety.CanApproach({3,10,1,1,100,0,5})); } // Separate floor.
    { Scene s; Creature mob; mob.guid=2; mob.x=50; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; PathGenerator::available=PathGenerator::straight=true;
      PathGenerator::rejectContinuation=true; QuestSpawn goal{3,10,1,1,100,0,0};
      for(int stage=0;stage<4;++stage) { assert(!s.safety.FindDetour(goal)); clockMs+=5000; }
      auto retreat=s.safety.FindDetour(goal);
      assert(retreat && retreat->x<0 && !s.safety.DetourPending()); }
    { Scene s; Creature mob; mob.guid=2; mob.x=50; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; QuestSpawn goal{3,10,1,1,100,0,0};
      PathGenerator::available=PathGenerator::straight=true;
      auto point=s.safety.FindDetour(goal);
      assert(point && point->guid==0 && std::abs(point->y)>20);
      assert(!s.safety.FindDetour(goal)); // Five-second planning throttle.
      clockMs+=5000; PathGenerator::type=PATHFIND_INCOMPLETE;
      assert(!s.safety.FindDetour(goal)); }
    { Scene s; Creature mob; mob.guid=2; mob.x=40; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; s.safety.SetTarget(2); avoidDefeated=true;
      assert(!s.safety.CanApproach({2,10,1,1,40,0,0}));
      assert(!strcmp(s.safety.Reason(),"repeated-defeat"));
      assert(!s.safety.FindDetour({2,10,1,1,40,0,0})); }
    { Scene s; Creature mob; mob.guid=2; mob.x=50; mob.hostile=mob.attackable=true;
      Creature left=mob; left.guid=4; left.y=-44;
      s.bot.map.creatures[2]=&mob; s.bot.map.creatures[4]=&left;
      PathGenerator::available=PathGenerator::straight=true;
      auto point=s.safety.FindDetour({3,10,1,1,100,0,0});
      assert(point && point->y>0); // Unsafe left leg, safe right alternative.
      Creature right=left; right.guid=5; right.y=44; s.bot.map.creatures[5]=&right;
      clockMs+=5000;
      assert(!s.safety.FindDetour({3,10,1,1,100,0,0})); }
    { Scene s; Creature mob; mob.guid=2; mob.x=50; mob.hostile=mob.attackable=true;
      Creature left=mob; left.guid=4; left.y=-44;
      Creature right=mob; right.guid=5; right.y=44;
      s.bot.map.creatures[2]=&mob; s.bot.map.creatures[4]=&left; s.bot.map.creatures[5]=&right;
      PathGenerator::available=PathGenerator::straight=true;
      QuestSpawn goal{3,10,1,1,100,0,0};
      assert(!s.safety.FindDetour(goal) && s.safety.DetourPending());
      int calls=PathGenerator::calls;
      assert(!s.safety.FindDetour(goal) && PathGenerator::calls==calls);
      clockMs+=5000;
      assert(!s.safety.FindDetour(goal) && s.safety.DetourPending());
      clockMs+=5000;
      auto wide=s.safety.FindDetour(goal);
      assert(wide && std::abs(wide->y)>=80 && !s.safety.DetourPending()); }
    { Scene s; Creature mob; mob.guid=2; mob.x=50; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; PathGenerator::available=PathGenerator::straight=true;
      PathGenerator::type=PATHFIND_INCOMPLETE;
      QuestSpawn goal{3,10,1,1,100,0,0};
      for(int stage=0;stage<5;++stage) {
        assert(!s.safety.FindDetour(goal)); assert(s.safety.DetourPending()==(stage<4)); clockMs+=5000; }
      int calls=PathGenerator::calls;
      assert(!s.safety.FindDetour(goal) && PathGenerator::calls==calls); }
    { Scene s; Creature mob; mob.guid=2; mob.x=50; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; QuestSpawn goal{3,10,1,1,100,0,0};
      PathGenerator::available=true;
      PathGenerator::points={{0,0,0},{0,50,0},{100,50,0},{100,0,0}};
      assert(s.safety.CanApproach(goal)); // Blocked chord, safe complete corridor.
      assert(!s.safety.Blocker() && !strcmp(s.safety.Reason(),"none"));
      PathGenerator::points={{0,0,0},{100,0,0}};
      assert(!s.safety.CanApproach(goal)); // A valid navmesh route may still cross aggro.
      assert(!s.safety.CanApproach(goal) && PathGenerator::calls==2); // Query budget.
      clockMs+=500; PathGenerator::points={{0,0,0},{0,50,0},{100,50,0},{100,0,0}};
      PathGenerator::type=PATHFIND_INCOMPLETE;
      assert(!s.safety.CanApproach(goal));
      PathGenerator::type=PATHFIND_NORMAL; PathGenerator::points.back()={90,0,0};
      assert(!s.safety.CanApproach(goal)); // No unverified endpoint bridge.
      clockMs+=500; PathGenerator::points.back()={100,0,0};
      mob.y=50; clockMs+=500;
      // Safe chord is allowed; actual spline through this patrol is still rejected.
      assert(s.safety.CanApproach(goal));
      s.bot.spline.finalized=false; s.bot.spline.path={{0,0,0},{0,50,0},{100,50,0},{100,0,0}};
      assert(!s.safety.RouteSafe()); }
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
      assert(s.safety.CanApproach(target)); } // Combat admission is owned by QuestHunt, not route geometry.
    { Scene s; Creature add; add.guid=2; add.x=30; add.y=40; add.hostile=add.attackable=true;
      s.bot.map.creatures[2]=&add; s.bot.spline.finalized=false;
      s.bot.spline.path={{0,0,0},{30,40,0},{60,0,0}};
      assert(!s.safety.RouteSafe());
      assert(!strcmp(s.safety.Reason(),"hostile-on-route") && s.safety.Blocker()==2); }
    { Scene s; Creature civilian; civilian.guid=2; civilian.x=30; civilian.y=5;
      civilian.hostile=civilian.attackable=civilian.civilian=true;
      s.bot.map.creatures[2]=&civilian;
      assert(s.safety.CanApproach({3,10,1,1,60,0,0}));
      civilian.civilian=false; civilian.passive=true; clockMs+=500;
      assert(s.safety.CanApproach({3,10,1,1,60,0,0}));
      civilian.passive=false; clockMs+=500;
      assert(!s.safety.CanApproach({3,10,1,1,60,0,0})); }
    { Scene s; s.safety.RememberDeath(); s.bot.spline.finalized=false;
      s.bot.spline.path={{0,0,0},{0,0,0},{60,0,0}};
      assert(s.safety.RouteSafe()); } // Duplicate start points don't prevent escaping death area.
    { Scene s; s.safety.RememberDeath(); s.safety.SetTarget(2); QuestSpawn near{2,10,1,1,5,0,0},far{3,10,1,1,60,0,0};
      assert(!s.safety.CanApproach(near) && s.safety.CanApproach(far)); clockMs+=300000;
      assert(s.safety.CanApproach(near)); }
    { Scene s; s.safety.RememberDeath(); s.bot.x=10;
      assert(!s.safety.CanApproach({3,10,1,1,-60,0,0})); } // Cannot cross centre while "escaping".
    { Scene s; Creature mob; mob.guid=2; mob.x=5; mob.hostile=mob.attackable=true;
      s.bot.map.creatures[2]=&mob; s.bot.health=20;
      assert(s.prep.Update(1)==PreparationResult::Waiting && !s.bot.sitting); }
    { Scene s; Creature target; target.guid=3; target.x=40; target.attackable=target.hostile=true;
      Creature neutral=target; neutral.guid=2; neutral.y=20; neutral.hostile=neutral.aggressive=false;
      s.bot.map.creatures[2]=&neutral; s.bot.map.creatures[3]=&target; s.safety.SetTarget(3);
      assert(s.safety.CanApproach({3,10,1,1,40,0,0})); // Attackable neutral does not answer assistance.
      neutral.y=9; neutral.hostile=neutral.aggressive=true; clockMs+=500;
      assert(!s.safety.CanApproach({3,10,1,1,40,0,0}));
      assert(!strcmp(s.safety.Reason(),"target-assistance") && s.safety.Blocker()==2); }
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
    "BotLifeReadiness.cpp", "BotLifeSafety.cpp", "BotLifeDetour.cpp", "BotLifePreparation.h", "BotLifePreparation.cpp", "BotLifeServices.cpp", "BotLifeWalk.cpp"))
for forbidden in ("TeleportTo(", "SetHealth(", "SetPower(", "Randomize(", "RewardQuest(", "CharacterDatabase"):
    assert forbidden not in production, forbidden

with tempfile.TemporaryDirectory(prefix="loa-preparation-") as directory:
    cpp = pathlib.Path(directory) / "test.cpp"
    binary = pathlib.Path(directory) / "test"
    cpp.write_text('#include "BotLifeServices.h"\n#include "BotLifeWalk.h"\n' + mocks + production + tests)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-UNDEBUG", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-I", str(module),
                    "-I", str(root / "modules/mod_playerbots/src/AI"), str(cpp),
                    str(module / "BotLifeReadinessPolicy.cpp"), str(module / "BotLifeSafetyPolicy.cpp"),
                    str(module / "BotLifeTravel.cpp"), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("BotLife readiness, native paid repair, rest hysteresis and local route safety passed")
