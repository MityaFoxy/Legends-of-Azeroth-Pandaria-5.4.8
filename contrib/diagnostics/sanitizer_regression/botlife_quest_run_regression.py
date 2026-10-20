#!/usr/bin/env python3
"""Production quest controller, hunt and reward gates against controlled native APIs."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
module = root / "modules/mod_botlife/src"


def body(name):
    return "\n".join(line for line in (module / name).read_text().splitlines() if not line.startswith("#"))


production = "\n".join(body(name) for name in ("BotLifeQuestExecutor.cpp", "BotLifeQuestHunt.cpp", "BotLifeQuestTurnIn.cpp", "BotLifeRouteClearance.cpp", "BotLifeCombatAssessment.cpp"))
for forbidden in ("CompleteQuest(", "KilledMonster", "SetQuestStatus(", "TeleportTo(", "WorldDatabase", "CharacterDatabase", "RemoveActiveQuest(", "ResurrectPlayer(", "BuildPlayerRepop(", "RepopAtGraveyard("):
    assert forbidden not in production, forbidden
assert production.count("bot.RewardQuest(") == 1
assert "AiPlayerbot.BotLife.QuestRun.Enabled = 0" in (module.parent / "config/botlife.conf.dist").read_text()

mocks = r'''
#include "BotLife.h"
#include "BotLifeQuestPlan.h"
#include "BotLifeTravel.h"
#include "BotLifeQuestRoster.h"
#include "BotLifeReadiness.h"
#include <cassert>
#include <cmath>
#include <limits>
#include <set>
#include <unordered_set>
#include <functional>
#include <cstring>
#include <algorithm>
using uint32=uint32_t; using int32=int32_t;
uint32 clockMs=1;
uint32 getMSTime() { return clockMs; }
uint32 GetMSTimeDiffToNow(uint32 start) { return clockMs-start; }
#define TC_LOG_INFO(...) ((void)0)
#define TC_LOG_ERROR(...) ((void)0)
#define TC_LOG_WARN(...) ((void)0)
constexpr uint32 UNIT_STATE_ROOT=1, UNIT_STATE_STUNNED=2, UNIT_STATE_LOST_CONTROL=4;
constexpr uint32 QUEST_FLAGS_PARTY_ACCEPT=8, MAX_QUEST_LOG_SIZE=25;
constexpr uint32 BOT_STATE_COMBAT=1;
constexpr uint32 IDLE_MOTION_TYPE=0;
constexpr uint32 UNIT_FIELD_MIN_DAMAGE=0, UNIT_FIELD_MAX_DAMAGE=1;
constexpr uint32 UNIT_FIELD_MIN_OFF_HAND_DAMAGE=2, UNIT_FIELD_MAX_OFF_HAND_DAMAGE=3;
enum WeaponAttackType { BASE_ATTACK, OFF_ATTACK };
struct DamageStats {
    float damage=10,armorFactor=1; uint32 period=2000;
    float offDamage=0; uint32 offPeriod=2000;
    bool dual=false, mainAllowed=true, offAllowed=true;
    bool CanDualWield() const { return dual; }
    bool CanUseAttackType(uint32 attack) const { return attack==OFF_ATTACK?offAllowed:mainAllowed; }
    float GetFloatValue(uint32 field) const { return field>=2?offDamage:damage; }
    uint32 GetAttackTime(uint32 attack) const { return attack==OFF_ATTACK?offPeriod:period; }
    template<class Victim> uint32 CalcArmorReducedDamage(Victim* victim,uint32 amount,void*,uint32) const {
        return uint32(amount*victim->armorFactor);
    }
};
struct Motion { uint32 type=0; uint32 GetCurrentMovementGeneratorType() const { return type; } };
struct Spline { bool done=true; bool Finalized() const { return done; } };
enum QuestStatus { QUEST_STATUS_NONE, QUEST_STATUS_INCOMPLETE, QUEST_STATUS_COMPLETE, QUEST_STATUS_FAILED, QUEST_STATUS_REWARDED };
struct Quest {
    bool party=false; uint32 choices=0,package=0;
    bool HasFlag(uint32) const { return party; }
    uint32 GetRewChoiceItemsCount() const { return choices; }
    uint32 GetQuestPackageID() const { return package; }
};
struct Manager {
    Quest quest; bool missing=false,broken=false;
    Quest const* GetQuestTemplate(uint32) { return missing ? nullptr : &quest; }
    bool IsBrokenQuest(uint32) { return broken; }
} manager;
auto* sObjectMgr=&manager;
struct Config {
    bool enabled=false; int32 guid=6,quest=42; std::set<std::string> conflicts;
    std::string assignments;
    std::string GetStringDefault(std::string const&,std::string const&) { return assignments; }
    bool GetBoolDefault(std::string const& key,bool) { return key.find("QuestRun")!=key.npos?enabled:conflicts.count(key); }
    int32 GetIntDefault(std::string const& key,int32) { return key.ends_with("BotGuid")?guid:quest; }
} config;
auto* sConfigMgr=&config;
struct Creature;
struct Map {
    std::unordered_map<uint32,Creature*> creatures;
    Creature* GetCreatureBySpawnId(uint32 id) { auto i=creatures.find(id); return i==creatures.end()?nullptr:i->second; }
};
struct Creature : DamageStats {
    Map* map=nullptr;
    bool alive=true,world=true,combat=false,evade=false,elite=false,involved=true,offers=true;
    uint32 entry=20,phase=1,level=10,owner=0;
    uint32 health=100;
    bool hostile=true;
    uint32 GetHealth() const { return health; }
    template<class T> bool IsHostileTo(T*) const { return hostile; }
    float x=0,y=0,z=0;
    std::set<uint32> taps;
    bool IsAlive() const { return alive; } bool IsInWorld() const { return world; }
    bool IsInCombat() const { return combat; } bool IsInEvadeMode() const { return evade; }
    bool isElite() const { return elite; } uint32 GetOwnerGUID() const { return owner; }
    uint32 GetEntry() const { return entry; } uint32 GetPhaseMask() const { return phase; }
    uint32 GetLevel() const { return level; } auto const& GetLootRecipients() const { return taps; }
    Map* GetMap() const { return map; }
    bool hasInvolvedQuest(uint32) const { return involved; } bool hasQuest(uint32) const { return offers; }
    float GetPositionX() const { return x; } float GetPositionY() const { return y; } float GetPositionZ() const { return z; }
};
struct Guid { uint32 value=6; uint32 GetCounter() const { return value; } };
struct Player : DamageStats {
    uint32 guid=6;
    Map map;
    Motion motion; Spline spline; Spline* movespline=&spline;
    Motion* GetMotionMaster() { return &motion; }
    bool world=true,removing=false,group=false,combat=false,casting=false,mounted=false;
    bool visible=true,los=true,validAttack=true,interact=true,eligibleReward=true,inventory=true,rewardEffect=true;
    uint32 state=0,rewards=0,accepts=0,checks=0,inventoryChecks=0;
    float health=100,mana=100;
    bool usesMana=false;
    bool usableOffhand=false;
    void* GetWeaponForAttack(WeaponAttackType attack,bool usable) {
      assert(attack==OFF_ATTACK && usable); return usableOffhand?this:nullptr;
    }
    Creature* victim=nullptr;
    BotLife::QuestPlayerSnapshot snapshot;
    Player() { damage=100; snapshot.validContext=true; snapshot.mapId=1; snapshot.phaseMask=1; snapshot.progress=BotLife::QuestProgress::Active; }
    uint32 GetHealth() const { return uint32(health*10); }
    uint32 GetMaxHealth() const { return 1000; }
    bool IsInWorld() const { return world; } bool IsDuringRemoveFromWorld() const { return removing; }
    bool GetGroup() const { return group; } bool IsInCombat() const { return combat; }
    bool HasUnitState(uint32 flags) const { return state&flags; }
    bool IsNonMeleeSpellCasted(bool) const { return casting; }
    bool IsMounted() const { return mounted; } float GetHealthPct() const { return health; }
    Creature* GetVictim() const { return victim; }
    uint32 GetMapId() const { return snapshot.mapId; } uint32 GetPhaseMask() const { return snapshot.phaseMask; }
    uint32 GetInstanceId() const { return 0; } uint32 GetLevel() const { return 10; }
    float GetPositionX() const { return snapshot.x; } float GetPositionY() const { return snapshot.y; } float GetPositionZ() const { return snapshot.z; }
    Map* GetMap() { return &map; } Guid GetGUID() const { return {guid}; }
    bool CanSeeOrDetect(Creature*) const { return visible; }
    bool IsValidAttackTarget(Creature*) const { return validAttack; }
    bool IsWithinLOSInMap(Creature*) const { return los; }
    bool IsWithinDistInMap(Creature* npc,float r) const {
      float dx=npc->x-snapshot.x,dy=npc->y-snapshot.y,dz=npc->z-snapshot.z;
      return dx*dx+dy*dy+dz*dz <= r*r;
    }
    bool CanInteractWithQuestGiver(Creature* npc) const { return interact && IsWithinDistInMap(npc,5); }
    QuestStatus GetQuestStatus(uint32) const {
      using P=BotLife::QuestProgress;
      switch(snapshot.progress) {
        case P::NotTaken:return QUEST_STATUS_NONE; case P::Active:return QUEST_STATUS_INCOMPLETE;
        case P::Complete:return QUEST_STATUS_COMPLETE; case P::Failed:return QUEST_STATUS_FAILED;
        case P::Rewarded:return QUEST_STATUS_REWARDED;
      } return QUEST_STATUS_NONE;
    }
    bool GetQuestRewardStatus(uint32) const { return snapshot.progress==BotLife::QuestProgress::Rewarded; }
    uint32 FindQuestSlot(uint32) const { return GetQuestRewardStatus(1)?MAX_QUEST_LOG_SIZE:0; }
    bool CanRewardQuest(Quest const*,bool) { ++checks; return eligibleReward; }
    bool CanRewardQuest(Quest const*,uint32,bool) { ++inventoryChecks; return inventory; }
    void RewardQuest(Quest const*,uint32,Creature*) { ++rewards; if(rewardEffect) snapshot.progress=BotLife::QuestProgress::Rewarded; }
};
struct PlayerbotAI {
    Player* bot; uint32 state=0,attacks=0;
    Player* GetBot() { return bot; } uint32 GetState() const { return state; }
};
class AttackAction {
protected:
    PlayerbotAI* botAI; Player* bot;
    AttackAction(PlayerbotAI* ai,char const*) : botAI(ai),bot(ai->bot) { }
    bool Attack(Creature* target) { assert(target); ++botAI->attacks; bot->victim=target; botAI->state=BOT_STATE_COMBAT; return true; }
};
namespace BotLife {
void LogEnhancementAbilities(PlayerbotAI&) {}
bool ProvisionMissingEquipment(PlayerbotAI&, char const*&) { return true; }
bool allowed=true;
std::set<uint32> eligible{6};
bool IsOnlyEligibleBot(uint32 guid) { return allowed && guid==6; }
bool IsEligibleBot(uint32 guid) { return allowed && eligible.count(guid); }
uint32 EligibleBotCount() { return allowed ? eligible.size() : 0; }
char const* ToString(InterruptReason) { return "cancelled"; }
QuestPlayerSnapshot ReadQuestPlayer(QuestPlanData const&,Player& bot) { return bot.snapshot; }
QuestPlanData LoadQuestPlanData(uint32) { return {}; }
bool TryAcceptQuest(Player& bot,QuestPlanData const&,QuestSpawn const&,char const*& reason) {
    ++bot.accepts; bot.snapshot.progress=QuestProgress::Active; reason="accepted"; return true;
}
class NativeTravelMovement final : public TravelMovement {
    Player& bot; bool owned=false; TravelTarget target;
public:
    static inline uint32 moves=0;
    static inline TravelTarget lastTarget{};
    static inline bool route=true,valid=true,lost=false,unsafe=false;
    explicit NativeTravelMovement(PlayerbotAI& ai, std::function<bool()> = {}) : bot(*ai.GetBot()) { }
    bool IsValid(TravelTarget const& t) const override { return valid && bot.snapshot.validContext && t.mapId==bot.GetMapId() && t.phaseMask==bot.GetPhaseMask(); }
    bool IsBlocked() override { return bot.combat; }
    bool HasArrived(TravelTarget const& t) const override { return std::abs(t.x-bot.snapshot.x)<1 && std::abs(t.y-bot.snapshot.y)<1; }
    TravelMoveResult Move(TravelTarget const& t) override { ++moves; lastTarget=target=t; owned=route && !unsafe;
        return unsafe?TravelMoveResult::UnsafeRoute:route?TravelMoveResult::Started:TravelMoveResult::NoRoute; }
    TravelMotion Poll() const override { return lost?TravelMotion::Lost:TravelMotion::Moving; }
    bool HasProgressed() const override { return true; }
    bool OwnsMovement() const override { return owned; }
    void Release() override { owned=false; }
};
Readiness ReadCombatReadiness(Player& bot) {
    Readiness s; s.level=10; s.health=bot.health; s.weapon=s.offhand=s.coreArmor=s.combatSpell=true;
    s.mana=bot.mana; s.usesMana=bot.usesMana;
    s.armorPieces=5; return s;
}
class QuestSafety {
public:
    static inline bool safe=true, stagingSafe=true;
    static inline uint32 blockedTarget=0,blocker=0;
    uint32 target=0;
    explicit QuestSafety(Player&) { }
    bool CanApproach(QuestSpawn const& spawn) { return safe && (!blockedTarget || spawn.guid!=blockedTarget) && (spawn.guid || stagingSafe); }
    bool RouteSafe() { return safe; }
    void SetTarget(uint32 id) { target=id; }
    uint32 Blocker() const { return blocker; }
    char const* Reason() const { return blocker?"hostile-on-route":"none"; }
    void RememberDeath() { }
};
enum class PreparationResult { Ready, Waiting, Failed };
class QuestPreparation {
    Player& bot;
    bool recovering=false;
public:
    explicit QuestPreparation(PlayerbotAI& ai, QuestSafety&) : bot(*ai.GetBot()) { }
    void RequireRecovery() { recovering=true; }
    bool NeedsService() const { return bot.health<(recovering?90:75); }
    PreparationResult Update(uint32) { if(NeedsService()) return PreparationResult::Waiting; recovering=false; return PreparationResult::Ready; }
    void Pause() { }
    bool ControlsMovement() const { return false; }
    bool HoldsNonCombat() const { return NeedsService(); }
    char const* Reason() const { return "preparation"; }
};
}
'''

tests = r'''
using namespace BotLife;
struct Scene {
    Player bot; PlayerbotAI ai{&bot}; Creature giver,enemy;
    QuestPlanData data; QuestSpawn ender{10,20,1,1,100,0,0};
    std::unique_ptr<ActivityExecutor> run;
    Scene() {
      QuestSafety::safe=QuestSafety::stagingSafe=true;
      QuestSafety::blockedTarget=QuestSafety::blocker=0;
      manager={}; allowed=true; eligible={6}; clockMs=1;
      NativeTravelMovement::moves=0; NativeTravelMovement::route=NativeTravelMovement::valid=true; NativeTravelMovement::lost=NativeTravelMovement::unsafe=false;
      giver.map=enemy.map=&bot.map; giver.x=100; enemy.x=10; enemy.entry=30;
      bot.map.creatures={{10,&giver},{11,&enemy}};
      data.questId=42; data.error=QuestPlanReason::None; data.starters={ender}; data.enders={ender};
      data.objectives={{1,30,1,{{11,30,1,1,10,0,0}}}};
    }
    void start() { run=MakeQuestExecutor(ai,data); run->Start(ai); }
    ActivityResult tick(uint32 elapsed=1) { clockMs+=elapsed; return run->Update(ai,elapsed); }
};
int main() {
    // Native offhand stats already carry the penalty. Use its own speed and
    // attack type, never turn a shield/unequippable item into a second weapon.
    { Scene s; auto main=AssessRouteOpponent(s.bot,s.enemy);
      s.bot.dual=true; s.bot.usableOffhand=true; s.bot.offDamage=50; s.bot.offPeriod=1000;
      auto dual=AssessRouteOpponent(s.bot,s.enemy);
      assert(dual.allowed && dual.mainhandDps==50 && dual.offhandDps==50);
      assert(dual.outgoingDps==65 && dual.seconds==main.seconds/2);
      assert(!strcmp(dual.model,"physical-dual-wield"));
      s.bot.offAllowed=false; assert(AssessRouteOpponent(s.bot,s.enemy).offhandDps==0);
      s.bot.offAllowed=true; s.bot.usableOffhand=false;
      assert(AssessRouteOpponent(s.bot,s.enemy).offhandDps==0);
      s.bot.usableOffhand=true; s.bot.dual=false;
      assert(AssessRouteOpponent(s.bot,s.enemy).offhandDps==0);
      s.bot.dual=true; s.bot.offPeriod=0;
      assert(AssessRouteOpponent(s.bot,s.enemy).offhandDps==0); }
    { Scene s; s.enemy.health=1600; assert(!AssessRouteOpponent(s.bot,s.enemy).allowed);
      s.bot.dual=s.bot.usableOffhand=true; s.bot.offDamage=50;
      assert(AssessRouteOpponent(s.bot,s.enemy).allowed); // Physical underestimate, no class multiplier.
      s.enemy.dual=true; s.enemy.offDamage=100;
      assert(!AssessRouteOpponent(s.bot,s.enemy).allowed); // Enemy offhand increases incoming risk too.
      s.bot.mainAllowed=false; s.bot.offAllowed=false;
      assert(!AssessRouteOpponent(s.bot,s.enemy).allowed); }
    // HP is the current work remaining, level and elite rank add uncertainty,
    // never a hard veto. Actual armor modifies both sides of the estimate.
    { Scene s; auto ordinary=AssessRouteOpponent(s.bot,s.enemy); assert(ordinary.allowed);
      s.enemy.level=12; auto higher=AssessRouteOpponent(s.bot,s.enemy);
      assert(higher.allowed && higher.seconds>ordinary.seconds && higher.incomingDamage>ordinary.incomingDamage);
      s.enemy.elite=true; auto elite=AssessRouteOpponent(s.bot,s.enemy);
      assert(elite.allowed && elite.incomingDamage>higher.incomingDamage);
      QuestHunt hunt(s.ai); assert(hunt.Choose(s.data,s.bot.snapshot,{}));
      assert(hunt.Engage(s.data.objectives[0].candidates[0]));
      s.enemy.health=100000; assert(!AssessRouteOpponent(s.bot,s.enemy).allowed);
      s.enemy.health=100; s.enemy.damage=1000; assert(!AssessRouteOpponent(s.bot,s.enemy).allowed); }
    { Scene s; auto before=AssessRouteOpponent(s.bot,s.enemy);
      s.enemy.armorFactor=0.5; auto armored=AssessRouteOpponent(s.bot,s.enemy);
      assert(armored.seconds>before.seconds && armored.incomingDamage>before.incomingDamage);
      s.bot.armorFactor=0.5; assert(AssessRouteOpponent(s.bot,s.enemy).incomingDamage<armored.incomingDamage);
      s.bot.health=89; assert(!AssessRouteOpponent(s.bot,s.enemy).allowed);
      assert(AssessRouteOpponent(s.bot,s.enemy,false).allowed);
      s.bot.health=100; s.bot.damage=0; assert(!AssessRouteOpponent(s.bot,s.enemy).allowed);
      s.bot.damage=std::numeric_limits<float>::quiet_NaN(); assert(!AssessRouteOpponent(s.bot,s.enemy).allowed);
      s.bot.damage=100; s.enemy.period=0; assert(!AssessRouteOpponent(s.bot,s.enemy).allowed); }
    { Scene s; s.bot.usesMana=true; s.bot.mana=79;
      assert(!AssessRouteOpponent(s.bot,s.enemy).allowed && AssessRouteOpponent(s.bot,s.enemy,false).allowed);
      s.bot.mana=80; assert(AssessRouteOpponent(s.bot,s.enemy).allowed);
      s.bot.usesMana=false; s.bot.mana=0; assert(AssessRouteOpponent(s.bot,s.enemy).allowed); }
    // Isolated obstacle: native combat owns the single target until death;
    // finishing/cancelling does not re-pull that spawn or fabricate quest credit.
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      assert(clear.Start(11) && clear.HoldsNonCombat()); assert(!clear.Start(10));
      assert(clear.Update(1)==ClearanceResult::Running && s.ai.attacks==1 && !clear.HoldsNonCombat());
      clear.Pause(); assert(clear.Update(1)==ClearanceResult::Running && s.ai.attacks==1);
      s.enemy.alive=false; s.bot.victim=nullptr; s.ai.state=0;
      assert(clear.Update(1)==ClearanceResult::Finished && !clear.Active());
      s.enemy.alive=true; clockMs+=5000; assert(!clear.Start(11));
      assert(s.bot.snapshot.counters.empty() && !s.bot.accepts && !s.bot.rewards); }
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      s.enemy.x=40; assert(clear.Start(11)); assert(clear.Update(1)==ClearanceResult::Running);
      assert(clear.ControlsMovement()); clear.Pause(); assert(!clear.ControlsMovement());
      QuestSafety::safe=false; assert(clear.Update(1)==ClearanceResult::Failed && !s.ai.attacks); }
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      s.enemy.damage=1000; assert(!clear.Start(11)); s.enemy.damage=10;
      assert(!clear.Start(11)); clockMs+=5000; assert(clear.Start(11));
      clockMs+=60000; assert(clear.Update(1)==ClearanceResult::Failed && !clear.Active()); }
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      assert(clear.Start(11)); clear.Update(1); s.bot.victim=nullptr; s.ai.state=0;
      clockMs+=5000; assert(clear.Update(1)==ClearanceResult::Failed && s.ai.attacks==1); }
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      assert(clear.Start(11)); s.bot.map.creatures.erase(11);
      assert(clear.Update(1)==ClearanceResult::Failed); }
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      assert(clear.Start(11)); s.enemy.health=100000;
      assert(clear.Update(1)==ClearanceResult::Failed && !s.ai.attacks); }
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      s.enemy.x=40; assert(clear.Start(11)); NativeTravelMovement::unsafe=true;
      assert(clear.Update(1)==ClearanceResult::Failed && !clear.ControlsMovement() && !s.ai.attacks); }
    for(int mode=0;mode<6;++mode) {
      Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      switch(mode) { case 0:s.enemy.combat=true;break; case 1:s.enemy.taps.insert(9);break;
        case 2:s.enemy.phase=2;break; case 3:QuestSafety::safe=false;break;
        case 4:s.enemy.hostile=false;break; case 5:s.enemy.x=91;break; }
      assert(!clear.Start(11) && !s.ai.attacks);
    }
    // The 60..90m gap: bounded noncombat staging without target exemption,
    // then fresh close-range assessment and native combat, never a remote pull.
    { Scene s; s.enemy.x=70; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      assert(!hunt.RouteObstacle(11)); assert(clear.Start(11));
      assert(hunt.Safety().target==0 && !s.ai.attacks);
      assert(clear.Update(1)==ClearanceResult::Running);
      assert(hunt.Safety().target==0 && NativeTravelMovement::lastTarget.x==20);
      s.bot.snapshot.x=20;
      assert(clear.Update(1)==ClearanceResult::Running && !s.ai.attacks);
      assert(hunt.Safety().target==11 && NativeTravelMovement::lastTarget.x==70);
      s.bot.snapshot.x=51;
      assert(clear.Update(1)==ClearanceResult::Running && s.ai.attacks==1);
      assert(!clear.ControlsMovement() && s.bot.snapshot.counters.empty()); }
    { Scene s; s.enemy.x=70; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      QuestSafety::stagingSafe=false;
      assert(!clear.Start(11) && !NativeTravelMovement::moves && !s.ai.attacks); }
    { Scene s; s.enemy.x=70; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      assert(clear.Start(11)); clear.Update(1); QuestSafety::stagingSafe=false;
      assert(clear.Update(1)==ClearanceResult::Failed && !clear.ControlsMovement() && !s.ai.attacks); }
    { Scene s; s.enemy.x=70; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      assert(clear.Start(11)); clear.Update(1); s.bot.snapshot.x=20;
      QuestSafety::blockedTarget=11; // Newly visible neighbour vetoes close-range approach.
      assert(clear.Update(1)==ClearanceResult::Failed && !s.ai.attacks); }
    { Scene s; s.enemy.x=70; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      assert(clear.Start(11)); clear.Update(1); s.enemy.x=100;
      assert(clear.Update(1)==ClearanceResult::Failed && !clear.ControlsMovement()); }
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      for(uint32 id=20;id<24;++id) { s.bot.map.creatures[id]=&s.enemy;
        assert(clear.Start(id)); clear.Cancel(); clockMs+=5000; }
      s.bot.map.creatures[24]=&s.enemy; assert(!clear.Start(24)); }
    { Scene s; QuestHunt hunt(s.ai); RouteClearance clear(s.ai,hunt);
      for(uint32 id=20;id<23;++id) { s.bot.map.creatures[id]=&s.enemy;
        assert(clear.Start(id)); clockMs+=60000; clear.Cancel(); }
      s.bot.map.creatures[23]=&s.enemy; assert(!clear.Start(23)); }
    // Controller preserves quest target/counters across the obstacle and rests
    // before engaging the original target. Here safety itself is an API mock;
    // real neighbour/spline policy is covered in preparation/travel regressions.
    { Scene s; Creature obstacle=s.enemy; obstacle.entry=31;
      s.bot.map.creatures[12]=&obstacle; QuestSafety::blockedTarget=11; QuestSafety::blocker=12;
      s.start(); s.tick(); assert(!s.ai.attacks); s.tick(); assert(s.bot.victim==&obstacle && s.ai.attacks==1);
      s.run->Pause(s.ai); obstacle.alive=false; s.bot.victim=nullptr; s.ai.state=0; s.bot.health=80;
      assert(s.run->Resume(s.ai)); s.tick(); QuestSafety::blockedTarget=QuestSafety::blocker=0;
      s.tick(); assert(s.ai.attacks==1); s.bot.health=90; s.tick();
      assert(s.bot.victim==&s.enemy && s.ai.attacks==2 && s.bot.snapshot.counters.empty()); }
    { Scene s; Creature obstacle=s.enemy; s.bot.map.creatures[12]=&obstacle;
      QuestSafety::blockedTarget=11; QuestSafety::blocker=12; s.start(); s.tick();
      assert(s.run->SuspendForDeath(s.ai)); assert(!s.run->ControlsMovement());
      assert(s.bot.snapshot.progress==QuestProgress::Active && s.bot.snapshot.counters.empty());
      s.tick(5000); assert(!s.ai.attacks); }
    { Scene s; Creature obstacle=s.enemy; s.bot.map.creatures[12]=&obstacle;
      QuestSafety::blockedTarget=11; QuestSafety::blocker=12; s.start(); s.tick();
      assert(s.tick(180000)==ActivityResult::Failed && !s.ai.attacks); }
    { Scene s; s.bot.health=40; s.start();
      assert(s.tick()==ActivityResult::Running && !s.ai.attacks && s.run->HoldsNonCombat());
      assert(s.bot.snapshot.progress==QuestProgress::Active && s.bot.snapshot.counters.empty());
      s.bot.health=100; s.tick(); assert(s.ai.attacks==1); }
    { Scene s; QuestSafety::safe=false; s.start();
      assert(s.tick()==ActivityResult::Running && !s.ai.attacks && !NativeTravelMovement::moves && s.run->HoldsNonCombat());
      assert(s.tick(180000)==ActivityResult::Failed && !s.bot.accepts && !s.bot.rewards); }
    // Unsafe spline is not an eight-attempt navigation failure. Hold base
    // noncombat, then reconsider the target after (not before) its cooldown.
    { Scene s; s.enemy.x=100; NativeTravelMovement::unsafe=true; s.start();
      assert(s.tick()==ActivityResult::Running && NativeTravelMovement::moves==1);
      assert(s.run->HoldsNonCombat() && !s.run->ControlsMovement() && !s.ai.attacks);
      NativeTravelMovement::unsafe=false; s.enemy.x=10;
      assert(s.tick(44999)==ActivityResult::Running && !s.ai.attacks && NativeTravelMovement::moves==1);
      assert(s.tick(1)==ActivityResult::Running && s.ai.attacks==1);
      assert(s.bot.snapshot.counters.empty() && !s.bot.accepts && !s.bot.rewards); }
    // A threat discovered on an already owned route also defers, rather
    // than permanently retiring, the quest target.
    { Scene s; s.enemy.x=100; s.start(); s.tick(); assert(s.run->ControlsMovement());
      QuestSafety::safe=false; s.tick(); assert(s.run->HoldsNonCombat() && !s.run->ControlsMovement());
      QuestSafety::safe=true; s.enemy.x=10; s.tick(44999); assert(!s.ai.attacks);
      s.tick(1); assert(s.ai.attacks==1); }
    { Scene s; clockMs=UINT32_MAX-20000; s.enemy.x=100; NativeTravelMovement::unsafe=true; s.start(); s.tick();
      NativeTravelMovement::unsafe=false; s.enemy.x=10;
      s.tick(44999); assert(!s.ai.attacks); s.tick(1); assert(s.ai.attacks==1); }
    // TurnIn safety waits are bounded, throttle checks and preserve COMPLETE.
    { Scene s; s.bot.snapshot.progress=QuestProgress::Complete; s.enemy.x=70;
      QuestSafety::blockedTarget=10; QuestSafety::blocker=11; s.start(); s.tick(); s.tick();
      assert(!s.ai.attacks && NativeTravelMovement::lastTarget.x==20);
      s.bot.snapshot.x=20; s.tick(); s.bot.snapshot.x=51; s.tick();
      assert(s.ai.attacks==1 && s.bot.snapshot.progress==QuestProgress::Complete);
      s.enemy.alive=false; s.bot.victim=nullptr; s.ai.state=0; s.tick();
      QuestSafety::blockedTarget=QuestSafety::blocker=0; s.tick();
      assert(s.run->ControlsMovement() && NativeTravelMovement::lastTarget.x==100);
      s.bot.snapshot.x=100; assert(s.tick()==ActivityResult::Completed && s.bot.rewards==1 && !s.bot.accepts);
      assert(s.bot.snapshot.counters.empty()); }
    { Scene s; s.bot.snapshot.progress=QuestProgress::Complete; NativeTravelMovement::unsafe=true; s.start();
      assert(s.tick()==ActivityResult::Running && NativeTravelMovement::moves==1 && s.run->HoldsNonCombat());
      for(int i=0;i<100;++i) assert(s.tick()==ActivityResult::Running);
      assert(NativeTravelMovement::moves==1 && s.bot.snapshot.progress==QuestProgress::Complete);
      NativeTravelMovement::unsafe=false; s.tick(5000);
      assert(s.run->ControlsMovement() && NativeTravelMovement::moves==2);
      s.bot.snapshot.x=100; assert(s.tick()==ActivityResult::Completed && s.bot.rewards==1); }
    // Rejected splines must not consume the visit budget. Simulated native
    // progress keeps this stress test within the unchanged no-progress timeout.
    { Scene s; s.enemy.x=100; s.data.objectives[0].amount=1000;
      s.data.objectives[0].candidates.clear();
      for(uint32 id=200;id<340;++id)
        s.data.objectives[0].candidates.push_back({id,30,1,1,100,0,0});
      NativeTravelMovement::unsafe=true; s.start();
      for(int i=0;i<130;++i) {
        s.bot.snapshot.counters[1]=i;
        assert(s.tick(5000)==ActivityResult::Running);
      }
      assert(NativeTravelMovement::moves==130 && !s.ai.attacks);
    }
    // Real controller continues an accepted quest; the test simulates native kill
    // credit externally. Without that external update, it cannot advance to reward.
    { Scene s; s.start(); assert(s.tick()==ActivityResult::Running && s.ai.attacks==1 && !s.bot.accepts);
      assert(s.bot.snapshot.counters.empty() && !s.bot.rewards && !s.run->ControlsMovement());
      s.bot.combat=true; s.run->Pause(s.ai); s.enemy.alive=false;
      s.bot.snapshot.counters[1]=1; s.bot.snapshot.progress=QuestProgress::Complete;
      s.bot.combat=false; s.bot.victim=nullptr; s.ai.state=0; assert(s.run->Resume(s.ai));
      assert(s.tick()==ActivityResult::Running && s.run->ControlsMovement());
      s.bot.snapshot.x=100; assert(s.tick()==ActivityResult::Completed && s.bot.rewards==1);
      assert(s.bot.checks==1 && s.bot.inventoryChecks==1);
      for(int i=0;i<5;++i) assert(s.tick()==ActivityResult::Completed);
      assert(s.bot.rewards==1 && s.bot.accepts==0); }
    // New quest acquisition is one stage, never the terminal result.
    { Scene s; s.bot.snapshot.progress=QuestProgress::NotTaken; s.bot.snapshot.x=100; s.start();
      assert(s.tick()==ActivityResult::Running && s.bot.accepts==1 && !s.bot.rewards);
      s.tick(); assert(s.bot.accepts==1 && s.run->ControlsMovement()); }
    // A completed quest at startup can be turned in; rewarded quests cannot be repeated.
    { Scene s; s.bot.snapshot.progress=QuestProgress::Complete; s.bot.snapshot.x=100; s.start();
      assert(s.tick()==ActivityResult::Completed && s.bot.rewards==1); }
    { Scene s; s.bot.snapshot.progress=QuestProgress::Rewarded; s.start();
      assert(s.tick()==ActivityResult::Failed && !s.bot.rewards && !s.bot.accepts); }
    { Scene s; s.start(); s.bot.snapshot.progress=QuestProgress::NotTaken;
      assert(s.tick()==ActivityResult::Failed && !s.bot.accepts); }
    { Scene s; s.start(); s.bot.snapshot.progress=QuestProgress::Failed; assert(s.tick()==ActivityResult::Failed); }
    // Native complete, not just a filled counter, is required.
    { Scene s; s.bot.snapshot.counters[1]=1; s.start(); s.tick();
      assert(!s.bot.rewards && !s.ai.attacks); assert(s.tick(180000)==ActivityResult::Failed); }
    { Scene s; s.enemy.alive=false; s.start(); assert(s.tick()==ActivityResult::Running);
      assert(s.tick(180000)==ActivityResult::Failed && !s.bot.rewards); }
    { Scene s; s.start(); s.tick(); s.run->Pause(s.ai); s.enemy.alive=false;
      s.bot.victim=nullptr; s.ai.state=0; assert(s.run->Resume(s.ai));
      assert(s.tick(180000)==ActivityResult::Failed && !s.bot.rewards && s.bot.snapshot.counters.empty()); }
    { Scene s; s.start(); assert(s.tick(1200000)==ActivityResult::Failed); }
    { Scene s; s.bot.map.creatures.clear(); s.data.objectives[0].candidates.clear();
      for(uint32 i=1;i<=130;++i) s.data.objectives[0].candidates.push_back({i,30,1,1,0,0,0});
      s.start(); for(int i=0;i<128;++i) assert(s.tick()==ActivityResult::Running);
      assert(s.tick()==ActivityResult::Failed && !s.ai.attacks && !s.bot.rewards); }
    // Travel interruption/revalidation never steals combat or ignores changed context.
    { Scene s; s.enemy.x=100; s.start(); s.tick(); assert(s.run->ControlsMovement());
      s.run->Pause(s.ai); assert(!s.run->ControlsMovement()); s.bot.snapshot.phaseMask=2;
      assert(!s.run->Resume(s.ai) && !s.bot.rewards); }
    { Scene s; s.enemy.x=100; s.start(); s.tick(); NativeTravelMovement::lost=true;
      assert(s.tick()==ActivityResult::Failed); }
    { Scene s; s.start(); s.run->Interrupt(s.ai,InterruptReason::Death);
      assert(s.tick()==ActivityResult::Failed && s.ai.attacks==0 && !s.bot.rewards); }
    // Both native reward checks and every live interaction gate are necessary.
    for(int mode=0;mode<22;++mode) {
      Scene s; s.bot.snapshot.progress=QuestProgress::Complete; s.bot.snapshot.x=100;
      switch(mode) {
        case 0:s.bot.snapshot.progress=QuestProgress::Active;break;
        case 1:s.bot.snapshot.progress=QuestProgress::Rewarded;break;
        case 2:s.bot.combat=true;break; case 3:s.bot.state=UNIT_STATE_ROOT;break;
        case 4:s.bot.casting=true;break; case 5:s.giver.alive=false;break;
        case 6:s.giver.world=false;break; case 7:s.giver.combat=true;break;
        case 8:s.giver.entry=99;break; case 9:s.giver.phase=2;break;
        case 10:s.bot.visible=false;break; case 11:s.giver.involved=false;break;
        case 12:s.bot.los=false;break; case 13:s.bot.snapshot.x=0;break;
        case 14:s.bot.eligibleReward=false;break; case 15:s.bot.inventory=false;break;
        case 16:manager.broken=true;break; case 17:manager.quest.choices=1;break;
        case 18:manager.quest.package=1;break; case 19:s.bot.group=true;break;
        case 20:s.bot.map.creatures.erase(10);break; case 21:manager.missing=true;break;
      }
      char const* reason=nullptr; assert(!TryTurnInQuest(s.bot,s.data,s.ender,reason)); assert(!s.bot.rewards);
    }
    { Scene s; s.bot.snapshot.progress=QuestProgress::Complete; s.bot.snapshot.x=100; s.bot.rewardEffect=false;
      s.start(); assert(s.tick()==ActivityResult::Failed && s.bot.rewards==1);
      s.tick(); assert(s.bot.rewards==1); }
    // Live hunt cannot target dead/tapped/friendly/hidden/overpowering/owned creatures,
    // or attack remotely through a wall. Credit aliases come only from catalog.
    for(int mode=0;mode<18;++mode) {
      Scene s; QuestHunt hunt(s.ai);
      switch(mode) {
        case 0:s.enemy.alive=false;break; case 1:s.enemy.combat=true;break;
        case 2:s.enemy.evade=true;break; case 3:s.enemy.elite=true;s.enemy.health=100000;break;
        case 4:s.enemy.owner=5;break; case 5:s.enemy.level=14;s.enemy.damage=1000;break;
        case 6:s.enemy.taps.insert(9);break; case 7:s.bot.validAttack=false;break;
        case 8:s.bot.visible=false;break; case 9:s.bot.los=false;break;
        case 10:s.enemy.x=21;break; case 11:s.bot.health=49;break;
        case 12:s.bot.mounted=true;break; case 13:s.enemy.phase=2;break;
        case 14:s.enemy.entry=31;break; case 15:s.bot.state=UNIT_STATE_STUNNED;break;
        case 16:s.bot.motion.type=1;break; case 17:s.bot.spline.done=false;break;
      }
      assert(!hunt.Engage(s.data.objectives[0].candidates[0]) && !s.ai.attacks);
    }
    { Scene s; QuestHunt hunt(s.ai); auto chosen=hunt.Choose(s.data,s.bot.snapshot,{}); assert(chosen && chosen->guid==11);
      assert(!hunt.Choose(s.data,s.bot.snapshot,{11})); s.bot.snapshot.counters[1]=1;
      assert(!hunt.Choose(s.data,s.bot.snapshot,{})); }
    { Scene s; s.data.objectives[0].entry=999; QuestHunt hunt(s.ai);
      assert(hunt.Choose(s.data,s.bot.snapshot,{})->entry==30); } // Native KillCredit alias represented in catalog.
    // Death retains native progress, invalidates the lethal target, and does not
    // issue movement/attacks/rewards during recovery. A new target is chosen after resuming.
    { Scene s; s.data.objectives[0].amount=2; s.bot.snapshot.counters[1]=1;
      s.data.objectives[0].candidates.push_back({12,30,1,1,60,0,0});
      s.start(); s.tick(); assert(s.ai.attacks==1);
      s.run->Pause(s.ai); clockMs+=240000; // Long combat before death is not instant failure on revival.
      assert(s.run->SuspendForDeath(s.ai));
      assert(!s.run->ControlsMovement());
      auto moves=NativeTravelMovement::moves;
      clockMs+=240000; assert(s.run->SuspendForDeath(s.ai)); // Duplicate observation must not restart clock.
      assert(s.tick()==ActivityResult::Running && NativeTravelMovement::moves==moves && s.ai.attacks==1);
      assert(s.bot.snapshot.counters[1]==1 && s.bot.accepts==0 && s.bot.rewards==0);
      s.bot.victim=nullptr; s.ai.state=0;
      assert(s.run->Resume(s.ai)); assert(s.tick()==ActivityResult::Running && s.run->ControlsMovement());
      assert(s.ai.attacks==1); // Original target is alive but retired; travel to the other spawn.
      s.bot.snapshot.counters[1]=2; s.bot.snapshot.progress=QuestProgress::Complete;
      s.bot.snapshot.x=100; assert(s.tick()==ActivityResult::Completed && s.bot.rewards==1);
      assert(!s.run->SuspendForDeath(s.ai)); }
    // Recovery time does not consume the 20-minute quest budget. New progress window stays finite.
    { Scene s; s.enemy.alive=false; s.start(); clockMs+=1100000;
      assert(s.run->SuspendForDeath(s.ai)); clockMs+=200000; assert(s.run->Resume(s.ai));
      assert(s.tick()==ActivityResult::Running);
      assert(s.tick(100000)==ActivityResult::Failed); } // Existing work budget retained, not reset.
    { Scene s; s.enemy.alive=false; s.start(); assert(s.run->SuspendForDeath(s.ai));
      clockMs+=400000; assert(s.run->Resume(s.ai)); assert(s.tick(180000)==ActivityResult::Failed); }
    { Scene s; s.start(); assert(s.run->SuspendForDeath(s.ai)); clockMs+=599999;
      assert(!s.run->IsDeathRecoveryExpired()); assert(s.run->SuspendForDeath(s.ai)); ++clockMs;
      assert(s.run->IsDeathRecoveryExpired() && !s.run->Resume(s.ai)); }
    // Repeat deaths cannot defeat the separate absolute 30-minute guard.
    { Scene s; s.start();
      for(int i=0;i<3;++i) { assert(s.run->SuspendForDeath(s.ai)); clockMs+=500000; assert(s.run->Resume(s.ai)); }
      assert(s.run->SuspendForDeath(s.ai)); clockMs+=300000;
      assert(s.run->IsDeathRecoveryExpired() && !s.run->Resume(s.ai)); }
    // Clock wrap, death before acceptance and death on the way to turn-in.
    { Scene s; clockMs=std::numeric_limits<uint32>::max()-100000; s.start();
      assert(s.run->SuspendForDeath(s.ai)); clockMs+=300000;
      assert(!s.run->IsDeathRecoveryExpired() && s.run->Resume(s.ai)); }
    { Scene s; s.bot.snapshot.progress=QuestProgress::NotTaken; s.start(); s.tick();
      assert(s.run->SuspendForDeath(s.ai)); clockMs+=200000; assert(s.run->Resume(s.ai));
      s.bot.snapshot.x=100; assert(s.tick()==ActivityResult::Running && s.bot.accepts==1); }
    { Scene s; s.bot.snapshot.progress=QuestProgress::Complete; s.start(); s.tick();
      assert(s.run->SuspendForDeath(s.ai)); clockMs+=200000; assert(s.run->Resume(s.ai));
      s.bot.snapshot.x=100; assert(s.tick()==ActivityResult::Completed && s.bot.rewards==1); }
    for(int mode=0;mode<5;++mode) {
      Scene s; s.start(); assert(s.run->SuspendForDeath(s.ai));
      switch(mode) {
        case 0:s.bot.snapshot.progress=QuestProgress::NotTaken;break;
        case 1:s.bot.snapshot.progress=QuestProgress::Rewarded;break;
        case 2:s.bot.snapshot.progress=QuestProgress::Failed;break;
        case 3:++s.bot.snapshot.phaseMask;break;
        case 4:allowed=false;break;
      }
      assert(!s.run->Resume(s.ai) && !s.bot.accepts && !s.bot.rewards);
    }
    // Five independent executors: credit, cancellation and reward never leak between bots.
    { Scene bots[5]; eligible={6,7,8,9,10};
      for(uint32 i=0;i<5;++i) { bots[i].bot.guid=6+i; bots[i].start(); bots[i].tick(); }
      for(auto& s : bots) assert(s.ai.attacks==1 && !s.bot.rewards && s.bot.snapshot.counters.empty());
      auto& done=bots[0]; done.bot.victim=nullptr; done.ai.state=0;
      done.bot.snapshot.counters[1]=1; done.bot.snapshot.progress=QuestProgress::Complete;
      done.bot.snapshot.x=100; assert(done.tick()==ActivityResult::Completed && done.bot.rewards==1);
      eligible.erase(7); assert(bots[1].tick()==ActivityResult::Failed);
      for(int i=2;i<5;++i) assert(bots[i].tick()==ActivityResult::Running && !bots[i].bot.rewards);
      assert(done.bot.rewards==1 && !bots[1].bot.rewards);
    }
    // Opt-in must fail closed for every competing mode, invalid ID or allowlist.
    { Scene s; LoadQuestRunConfig(); assert(!IsQuestRunEnabled() && !GetQuestRunBotGuid());
      config.enabled=true; LoadQuestRunConfig(); assert(IsQuestRunEnabled() && GetQuestRunBotGuid()==6);
      for(auto name : {"TravelTest", "QuestPlan", "QuestAcquire"}) {
        config.conflicts={std::string("AiPlayerbot.BotLife.")+name+".Enabled"};
        LoadQuestRunConfig(); assert(!IsQuestRunEnabled());
      }
      config.conflicts.clear(); config.guid=-1; LoadQuestRunConfig(); assert(!IsQuestRunEnabled());
      config.guid=9; LoadQuestRunConfig(); assert(!IsQuestRunEnabled());
      config.guid=6; config.quest=0; LoadQuestRunConfig(); assert(!IsQuestRunEnabled());
      config.quest=42; allowed=false; LoadQuestRunConfig(); assert(!IsQuestRunEnabled()); }
    { Scene s; config={}; config.enabled=true; config.guid=config.quest=0;
      eligible={6,7,8,9,10}; config.assignments="6:42,7:43,8:42,9:44,10:45";
      LoadQuestRunConfig(); assert(IsQuestRunEnabled() && !GetQuestRunBotGuid());
      assert((GetQuestRunBotGuids()==std::vector<uint32>{6,7,8,9,10}));
      InitializeQuestRunData(); assert(catalogs.size()==4); // shared immutable catalog, independent executors
      assert(CreateQuestRunExecutor(s.ai));
      auto first=CreateQuestRunExecutor(s.ai),second=CreateQuestRunExecutor(s.ai);
      assert(first && second && first.get()!=second.get());
      eligible.erase(7); assert(GetQuestRunBotGuids().empty() && !CreateQuestRunExecutor(s.ai));
      LoadQuestRunConfig(); assert(!IsQuestRunEnabled());
      eligible={6,7,8,9,10}; config.guid=6; LoadQuestRunConfig(); assert(!IsQuestRunEnabled());
      config.guid=0;
      for(auto bad : {"6:42,6:43", "6:0", "0:42", "-6:42", "6:42,", "6:42x", "6:42:43",
                       " 6:42", "6:42,7:43,8:42,9:44,10:45,11:46", "4294967296:42"}) {
        config.assignments=bad; LoadQuestRunConfig(); assert(!IsQuestRunEnabled());
      }
      assert(ParseQuestRoster("6:42").size()==1);
      eligible={1,2,3,4,5,6,7,8,9,10};
      config.assignments="1:42,2:42,3:42,4:42,5:42,6:42,7:42,8:42,9:42,10:42";
      LoadQuestRunConfig(); assert(IsQuestRunEnabled() && GetQuestRunBotGuids().size()==10);
      config.assignments+=",11:42"; eligible.insert(11);
      LoadQuestRunConfig(); assert(!IsQuestRunEnabled());
      std::string maxIds;
      for(uint32 i=0;i<10;++i) maxIds+=(i?",":"")+std::to_string(UINT32_MAX-i)+":4294967295";
      assert(maxIds.size()==219 && ParseQuestRoster(maxIds).size()==10);
    }
}
'''

source = mocks + body("BotLifeCombatAssessment.h") + body("BotLifeCombatAssessment.cpp") + body("BotLifeQuestHunt.h") + body("BotLifeQuestHunt.cpp") + body("BotLifeRouteClearance.h") + body("BotLifeRouteClearance.cpp") + body("BotLifeQuestTurnIn.cpp") + body("BotLifeQuestExecutor.cpp") + body("BotLifeQuestRun.cpp") + tests
with tempfile.TemporaryDirectory(prefix="loa-quest-run-") as directory:
    cpp = pathlib.Path(directory) / "test.cpp"
    binary = pathlib.Path(directory) / "test"
    cpp.write_text(source)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-UNDEBUG", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", "-I", str(module), "-I", str(root / "modules/mod_playerbots/src/AI"),
                    str(cpp), str(module / "BotLifeTravel.cpp"), str(module / "BotLifeQuestPlan.cpp"),
                    str(module / "BotLifeReadinessPolicy.cpp"), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("BotLife full quest lifecycle, native hunt and turn-in gates passed")
