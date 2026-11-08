#!/usr/bin/env python3
"""Exercise actual Action bodies with bounded world APIs; diagnostics must preserve effects."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]
strategy = root / 'modules/mod_playerbots/src/strategy'


def method(path, name):
    source = (strategy / path).read_text()
    start = source.index('bool ' + name + '::Execute(Event event)')
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def function(path, signature):
    source = (strategy / path).read_text()
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


corpse_source = (strategy / 'Dead/ReviveFromCorpseAction.cpp').read_text()
revive = method('Dead/ReviveFromCorpseAction.cpp', 'ReviveFromCorpseAction')
support_gate = revive.index('if (!IsSupportedCorpseReclaimPosition(bot))')
stop = revive.index('bot->StopMoving();')
packet = revive.index('WorldPacket packet(CMSG_RECLAIM_CORPSE);')
assert support_gate < stop < packet
assert 'false, false, true);' in method('Dead/ReviveFromCorpseAction.cpp', 'FindCorpseAction')

playerbot_config = (root / 'modules/mod_playerbots/config/playerbots.conf.dist').read_text()
soak_runner = (root / 'contrib/diagnostics/playerbot_multilevel_soak.py').read_text()
assert 'AiPlayerbot.ExecutionDiagnostics = 0' in playerbot_config
assert '"AiPlayerbot.ExecutionDiagnostics": "0"' in soak_runner
assert '"AiPlayerbot.ExecutionDiagnostics": "1"' in soak_runner


prefix = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <string>
#include <type_traits>
#include <vector>
using uint32=std::uint32_t;using int64=std::int64_t;using GuidVector=std::vector<int>;
constexpr int MINUTE=60,MOVE_RUN=0,ALL_ACTIVITY=0,REACT_PASSIVE=0,UNIT_STATE_FOLLOW=0;
constexpr float CORPSE_RECLAIM_RADIUS=39;
constexpr int MAP_ALL_LIQUIDS=0,LIQUID_MAP_NO_WATER=0;
constexpr float INVALID_HEIGHT=-100000.0f;
struct Event{};
std::vector<std::string> effects;
struct LiquidData {float level=0,depth_level=0;};
struct Guid {uint32 GetCounter()const{return 67;}};
struct Unit {
 float x=0,y=0,z=0;
 Guid GetGUID()const{return {};}
 float GetPositionX()const{return x;}float GetPositionY()const{return y;}float GetPositionZ()const{return z;}
};
struct Charm {
 void SetIsCommandAttack(bool b){assert(b);effects.push_back("command");}
 void SetIsAtStay(bool b){assert(!b);effects.push_back("stay");}
 void SetIsFollowing(bool b){assert(!b);effects.push_back("following");}
 void SetIsCommandFollow(bool b){assert(!b);effects.push_back("follow");}
 void SetIsReturning(bool b){assert(!b);effects.push_back("returning");}
};
struct PetAI {void AttackStart(Unit* u){assert(u);effects.push_back("start");}};
struct Guardian:Unit {
 Charm charm;PetAI ai;
 void SetReactState(int){effects.push_back("passive");}
 void ClearUnitState(int){effects.push_back("clear");}
 void AttackStop(){effects.push_back("stop");}void SetTarget(Guid){effects.push_back("target");}
 Charm* GetCharmInfo(){return &charm;}Guardian* ToCreature(){return this;}PetAI* AI(){return &ai;}
};
struct Corpse:Unit {int age=0;time_t GetGhostTime(){return time(nullptr)-age;}};
struct Map {
 std::vector<int> candidates{0,0,0,0};int index=0,waterCalls=0;
 float ground=0;bool liquid=false;LiquidData liquidData{};
 bool CheckCollisionAndGetValidCoords(Unit*,float,float,float,float&,float&,float&){return candidates.at(index++)!=0;}
 bool IsInWater(uint32,float,float,float){++waterCalls;return candidates.at(index-1)==1;}
 int GetLiquidStatus(uint32,float,float,float,int,LiquidData* data,float){if(data)*data=liquidData;return liquid?1:LIQUID_MAP_NO_WATER;}
};
struct Motion {void Clear(){effects.push_back("motion-clear");}};
struct Player:Unit {
 Guardian* pet=nullptr;Corpse* corpse=nullptr;bool valid=true,bg=false,moving=false;
 Map map;Motion motion;
 Guardian* GetGuardianPet(){effects.push_back("guardian-read");return pet;}
 bool IsValidAttackTarget(Unit*){effects.push_back("target-check");return valid;}
 bool InBattleground(){return bg;}Corpse* GetCorpse(){return corpse;}
 bool isMoving(){return moving;}uint32 GetMapId(){return 0;}uint32 GetInstanceId(){return 0;}
 uint32 GetPhaseMask(){return 1;}float GetCollisionHeight(){return 1;}
 bool IsInWater(){return false;}bool IsUnderWater(){return false;}Map* GetMap(){return &map;}
 bool IsInWorld(){return true;}float GetMapHeight(float,float,float,bool,float){return map.ground;}
 float GetSpeed(int){return 7;}Motion* GetMotionMaster(){return &motion;}
 void TeleportTo(uint32,float,float,float,float){effects.push_back("teleport");}
};
struct Config {float tooCloseDistance=5,spellDistance=30,reactDistance=50;} config;
auto sPlayerbotAIConfig=&config;
struct WorldPosition {
 Unit* u;
 explicit WorldPosition(Unit* unit):u(unit){}
 float distance(WorldPosition other){return std::abs(getX()-other.getX());}
 float fDist(WorldPosition other){return distance(other);}
 uint32 getMapId(){return 0;}float getX(){return u?u->x:0;}float getY(){return 0;}float getZ(){return 0;}
 int getUnitsAggro(GuidVector const&,Player*);
};
int aggro=0;int WorldPosition::getUnitsAggro(GuidVector const&,Player*){return aggro;}
struct Facade {float GetDistance2d(Unit* a,Unit* b){return std::abs(a->x-b->x);}} facade;
auto sServerFacade=&facade;
struct Manager {void Revive(Player*){effects.push_back("revive");}} manager;
auto sRandomPlayerbotMgr=&manager;
Unit* selected=nullptr;uint32 deaths=0;
template<class T>T Value(char const*){
 if constexpr(std::is_same_v<T,Unit*>){effects.push_back("target-read");return selected;}
 else if constexpr(std::is_same_v<T,uint32>)return deaths;
 else return {};
}
#define AI_VALUE(type,name) Value<type>(name)
template<class T>struct Cell {void Set(T value){deaths=value;effects.push_back("death-reset");}};
struct Context {template<class T>Cell<T>* GetValue(char const*){static Cell<T> cell;return &cell;}} contextObject;
struct BotAI {
 Player* master=nullptr;bool real=false,activity=true,spirit=false;
 Player* GetGroupMaster(){return master;}bool HasRealPlayerMaster(){return real;}
 bool AllowActivity(int){return activity;}
 bool DoSpecificAction(char const*,Event,bool){effects.push_back("spirit-healer");return spirit;}
};
struct ActionExecutionTrace {
 inline static bool enabled=false;inline static std::string reason="unattributed";
 inline static Unit* target=nullptr;
 static bool Enabled(){return enabled;}
 static bool Fail(char const* why){if(enabled)reason=why;return false;}
 static void Target(Unit* unit){if(enabled)target=unit;}
};
int logs=0,angles=0,distances=0;
#define TC_LOG_DEBUG(...) (++logs)
int urand(int,int){++distances;return 20;}float rand_norm(){++angles;return .25f;}
namespace G3D {struct Vector3 {float x,y,z;Vector3(float a,float b,float c):x(a),y(b),z(c){}};}
struct BaseAction {
 Player* bot;BotAI* botAI;Context* context=&contextObject;int moves=0;bool moveResult=false,lastNormalOnly=false;
 bool MoveTo(uint32,float,float,float,bool,bool,bool normalOnly=false,bool=false){
  ++moves;lastNormalOnly=normalOnly;effects.push_back("move");return moveResult?true:ActionExecutionTrace::Fail("move/no-path");
 }
};
struct MoveRandomAction:BaseAction {bool Execute(Event);};
struct PetAttackAction:BaseAction {bool Execute(Event);};
struct FindCorpseAction:BaseAction {bool Execute(Event);};
void reset(bool enabled){
 effects.clear();logs=angles=distances=aggro=0;deaths=0;selected=nullptr;
 ActionExecutionTrace::enabled=enabled;ActionExecutionTrace::reason="unattributed";ActionExecutionTrace::target=nullptr;
}
void reason(bool enabled,char const* expected){assert(ActionExecutionTrace::reason==(enabled?expected:"unattributed"));}
'''
tests = r'''
int main(){for(bool enabled:{false,true}){
 for(int scenario=0;scenario<4;++scenario){
  reset(enabled);Player bot;BotAI ai;MoveRandomAction action{&bot,&ai};
  if(scenario==1)bot.map.candidates={1,1,1,1}; // Four water candidates.
  if(scenario==2)bot.map.candidates={0,1,2,0}; // Preserve actual MoveTo failure.
  if(scenario==3){bot.map.candidates={0,2,0,0};action.moveResult=true;}
  bool result=action.Execute({});assert(result==(scenario==3));
  assert(bot.map.index==(scenario==3?2:4));assert(angles==bot.map.index&&distances==1);
  assert(action.moves==(scenario>=2?1:0));assert(logs==(enabled?bot.map.index:0));
  if(!result)reason(enabled,scenario==2?"move/no-path":"move-random/no-candidate");
 }
 for(int scenario=0;scenario<4;++scenario){
  reset(enabled);Player bot;BotAI ai;Guardian pet;Unit target;PetAttackAction action{&bot,&ai};
  if(scenario)bot.pet=&pet;
  if(scenario>=2)selected=&target;
  bot.valid=scenario==3;
  assert(action.Execute({})==(scenario==3));
  if(scenario==0){reason(enabled,"pet-attack/no-guardian");assert(effects==std::vector<std::string>{"guardian-read"});}
  if(scenario==1){reason(enabled,"pet-attack/no-target");assert(effects.size()==2);}
  if(scenario==2){reason(enabled,"pet-attack/invalid-target");assert(effects.size()==3);}
  assert(ActionExecutionTrace::target==(enabled&&scenario>=2?&target:nullptr));
  if(scenario==3)assert((effects==std::vector<std::string>{"guardian-read","target-read","target-check","passive","clear","stop","target","command","stay","following","follow","returning","start"}));
 }
 for(int scenario=0;scenario<11;++scenario){
  reset(enabled);Player bot,master;BotAI ai;Corpse corpse;FindCorpseAction action{&bot,&ai};
  bot.corpse=&corpse;
  if(scenario==0)bot.bg=true;
  if(scenario==1)bot.corpse=nullptr;
  if(scenario==2)ai.master=&master;
  if(scenario==3)corpse.age=600;
  if(scenario>=5){corpse.x=100;}
  if(scenario==6)action.moveResult=true;
  if(scenario==7)bot.moving=true;
  if(scenario==8){deaths=5;}
  if(scenario==9){ai.activity=false;corpse.age=600;}
  if(scenario==10){corpse.x=10;bot.map.ground=INVALID_HEIGHT;action.moveResult=true;}
  assert(action.Execute({})==(scenario>=6));
  char const* causes[]={"corpse/in-battleground","corpse/no-corpse","corpse/reclaim-near-master","corpse/reclaim-timeout","corpse/reclaim-no-aggro","corpse/spirit-healer-failed"};
  if(scenario<6)reason(enabled,causes[scenario]);
  if(scenario<5)assert(effects.empty()&&action.moves==0);
  if(scenario==5)assert((effects==std::vector<std::string>{"move","spirit-healer"}));
  if(scenario==6)assert((effects==std::vector<std::string>{"move"}));
  if(scenario==5||scenario==6||scenario==10)assert(action.lastNormalOnly);
  if(scenario==7)assert(effects.empty());
  if(scenario==8){assert(deaths==0);assert((effects==std::vector<std::string>{"death-reset","revive"}));}
  if(scenario==9)assert((effects==std::vector<std::string>{"motion-clear","teleport"}));
  if(scenario==10)assert((effects==std::vector<std::string>{"move"}));
 }
}}
'''
source = prefix + function('Dead/ReviveFromCorpseAction.cpp', 'bool IsSupportedCorpseReclaimPosition(Player* bot)') + '\n' + '\n'.join(method(path, name) for path, name in (
    ('actions/MovementActions.cpp', 'MoveRandomAction'),
    ('actions/GenericActions.cpp', 'PetAttackAction'),
    ('Dead/ReviveFromCorpseAction.cpp', 'FindCorpseAction'))) + tests
env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
with tempfile.TemporaryDirectory(prefix='loa-refusal-diagnostics-') as tmp:
    binary = Path(tmp) / 'test'
    subprocess.run([compiler, '-std=c++20', '-O1', '-g', '-no-pie', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-x', 'c++', '-', '-o', str(binary)],
                   input=source, text=True, check=True)
    subprocess.run([str(binary)], env=env, check=True)
print('MoveRandom, PetAttack and FindCorpse: results, API effects and opt-in diagnostics passed')
