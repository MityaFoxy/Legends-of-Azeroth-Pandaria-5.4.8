#!/usr/bin/env python3
"""Run the real Heroic Leap action with controlled height/liquid/cast results."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(sys.argv[1]); compiler=sys.argv[2]
text=(root/'modules/mod_playerbots/src/strategy/Classes/warrior/WarriorActions.cpp').read_text()
a=text.index('bool CastHeroicLeapAction::Execute('); b=text.index('\n}\n',a)+2
method=text[a:b]
# Confirm the pre-fix generic dispatch still copies a unit destination. It must
# remain unchanged for other spells; only Heroic Leap uses the grounded action.
generic=(root/'modules/mod_playerbots/src/strategy/actions/GenericSpellActions.cpp').read_text()
assert 'return botAI->CastSpell(spell, GetTarget());' in generic
ai=(root/'modules/mod_playerbots/src/AI/PlayerbotAI.cpp').read_text()
assert 'targets.SetDst(*target);' in ai
prefix=r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
using uint32=uint32_t;
struct Event {};
struct LiquidData {};
constexpr float INVALID_HEIGHT=-100000.f;
constexpr int MAP_ALL_LIQUIDS=15, LIQUID_MAP_NO_WATER=0;
namespace Trinity { bool IsValidMapCoord(float x,float y,float z) {
 return std::isfinite(x)&&std::isfinite(y)&&std::isfinite(z)&&std::abs(x)<17066&&std::abs(y)<17066&&std::abs(z)<10000;
}}
struct Map {
 int water=0;
 int GetLiquidStatus(uint32 phase,float,float,float,int,LiquidData*,float) { assert(phase==1); return water; }
};
struct Unit {
 bool alive=true,world=true,samePhase=true; void* transport=nullptr; void* vehicle=nullptr;
 Map* map=nullptr; float x=1133.6237f,y=842.14545f,z=-107.554474f,ground=-110.36574f;
 bool IsAlive(){return alive;} bool IsInWorld(){return world;}
 Map* GetMap(){return map;} bool InSamePhase(Unit*){return samePhase;}
 void* GetTransport(){return transport;} void* GetVehicle(){return vehicle;}
 float GetPositionX(){return x;} float GetPositionY(){return y;} float GetPositionZ(){return z;}
 float GetMapHeight(float,float,float z,bool vmap,float range){assert(vmap&&range==6.f);return ground;}
 uint32 GetPhaseMask(){return 1;} float GetCollisionHeight(){return 2;}
};
struct AI {
 int calls=0; bool result=true; float x=0,y=0,z=0;
 bool CastSpell(uint32 id,float px,float py,float pz){assert(id==6544);++calls;x=px;y=py;z=pz;return result;}
 bool CastSpell(std::string const&,Unit* t){return CastSpell(6544,t->x,t->y,t->z);}
};
#define AI_VALUE2(type,key,value) uint32(6544)
struct CastHeroicLeapAction {
 Unit* bot; Unit* target; AI* botAI; std::string spell="heroic leap";
 Unit* GetTarget(){return target;}
 bool Execute(Event);
};
'''
suffix=r'''
int main(int argc,char**) {
 Map map,other; Unit bot,target; bot.map=target.map=&map; AI ai;
 CastHeroicLeapAction action{&bot,&target,&ai};
 if(argc>1) { // Reproduce the old generic route using the recorded Celaneia heights.
  assert(ai.CastSpell(action.spell,&target));
  assert(ai.z==target.z && ai.z-bot.ground>2.f); return 0;
 }
 assert(action.Execute({})); assert(ai.calls==1 && ai.x==target.x && ai.y==target.y && ai.z==bot.ground);
 // All recorded vertical offsets, including the largest observed one.
 for(float offset:{0.f,2.0997543f,2.811264f,3.9911594f,4.f}) {
  target.z=bot.ground+offset; assert(action.Execute({})); assert(ai.z==bot.ground);
 }
 auto rejected=[&] { int calls=ai.calls; assert(!action.Execute({})); assert(ai.calls==calls); };
 target.z=bot.ground+4.1f; rejected(); // No arbitrary downward search over cliffs.
 target.z=bot.ground-0.6f; rejected(); // No roof/upper-floor selection.
 target.z=bot.ground; float ground=bot.ground;
 bot.ground=INVALID_HEIGHT; rejected();
 bot.ground=std::numeric_limits<float>::quiet_NaN(); rejected(); bot.ground=ground;
 target.x=std::numeric_limits<float>::infinity(); rejected(); target.x=1133.6237f;
 map.water=1; rejected(); map.water=0;
 action.target=nullptr; rejected(); action.target=&target;
 target.alive=false; rejected(); target.alive=true;
 target.world=false; rejected(); target.world=true;
 bot.world=false; rejected(); bot.world=true;
 target.map=&other; rejected(); target.map=&map;
 bot.samePhase=false; rejected(); bot.samePhase=true;
 for(Unit* unit:{&bot,&target}) {
  unit->transport=unit; rejected(); unit->transport=nullptr;
  unit->vehicle=unit; rejected(); unit->vehicle=nullptr;
 }
 // Propagate native rejection (range/LOS/cooldown etc.) without manual events.
 ai.result=false; int before=ai.calls; assert(!action.Execute({})); assert(ai.calls==before+1);
}
'''
with tempfile.TemporaryDirectory(prefix='loa-heroic-leap-') as tmp:
 cpp=Path(tmp)/'test.cpp'; exe=Path(tmp)/'test'
 for mutation in (False,True):
  body=method.replace('botAI->CastSpell(spellId, x, y, ground)','botAI->CastSpell(spellId, x, y, targetZ)') if mutation else method
  assert not mutation or body!=method
  cpp.write_text(prefix+body+suffix)
  subprocess.run([compiler,'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(exe)],check=True)
  env=dict(os.environ,ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1')
  if not mutation: subprocess.run([str(exe),'baseline'],env=env,check=True)
  result=subprocess.run([str(exe)],env=env,capture_output=True,text=True)
  if mutation: assert result.returncode!=0, 'Ungrounded landing mutation escaped'
  elif result.returncode: raise RuntimeError(result.stderr)
print('Baseline airborne destination reproduced; grounded landing checks pass; mutation rejected')
