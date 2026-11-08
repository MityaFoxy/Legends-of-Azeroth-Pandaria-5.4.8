#!/usr/bin/env python3
"""Verify diagnostic isolation and return values using the real trace implementation."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]
header = (root/'modules/mod_playerbots/src/strategy/ActionExecutionTrace.h').read_text()
body = '\n'.join(line for line in (root/'modules/mod_playerbots/src/strategy/ActionExecutionTrace.cpp').read_text().splitlines()
                 if not line.startswith('#include'))
prefix = r'''
#include <cassert>
#include <cstdint>
#include <string>
#include <tuple>
#include <vector>
using uint32=std::uint32_t;
constexpr int UNIT_STATE_LOST_CONTROL=1,UNIT_STATE_MELEE_ATTACKING=2,LOG_LEVEL_DEBUG=2;
struct Guid { uint32 value; uint32 GetCounter()const{return value;} };
class Unit {
public:
 uint32 id=9;float x=12,y=13,z=14;bool alive=true;
 Guid GetGUID()const{return {id};} uint32 GetTypeId()const{return 4;}
 uint32 GetMapId()const{return 529;}uint32 GetInstanceId()const{return 3;}
 bool IsAlive()const{return alive;}bool isMoving()const{return false;}
 float GetPositionX()const{return x;}float GetPositionY()const{return y;}float GetPositionZ()const{return z;}
};
class Player:public Unit {
public:
 Unit const* GetVictim()const{return nullptr;}
 bool IsInCombat()const{return true;}bool IsNonMeleeSpellCasted(bool)const{return false;}
 bool IsMounted()const{return false;}bool IsStandState()const{return true;}
 bool HasRootAura()const{return false;}bool HasStunAura()const{return false;}
 bool HasConfuseAura()const{return false;}bool IsCharmed()const{return false;}
 bool HasUnitState(int)const{return false;}bool IsBeingTeleported()const{return false;}
 int GetShapeshiftForm()const{return 0;}int GetPowerType()const{return 0;}
 int GetPower(int)const{return 50;}int GetMaxPower(int)const{return 100;}
};
class Action {public: std::string getName()const{return "test action";}};
bool logEnabled=false,configEnabled=false;
struct Log {bool ShouldLog(char const*,int){return logEnabled;}} logObject;
struct Config {bool GetBoolDefault(char const*,bool def){assert(!def);return configEnabled;}} configObject;
auto sLog=&logObject;auto sConfigMgr=&configObject;
struct Row {bool raw,result;std::string reason,detail;uint32 spell;int code;uint32 target;float x;};
std::vector<Row> rows;
template<class... T>void Capture(T... values){
 auto t=std::make_tuple(values...);
 rows.push_back({std::get<4>(t),std::get<5>(t),std::get<6>(t),std::get<7>(t),
   std::get<8>(t),std::get<9>(t),std::get<28>(t),std::get<34>(t)});
}
#define TC_LOG_DEBUG(category,format,...) Capture(__VA_ARGS__)
'''
test = r'''
int main(){
 Player bot;Action action;
 assert(!ActionExecutionTrace::Enabled());logEnabled=true;
 assert(!ActionExecutionTrace::Enabled());configEnabled=true;
 assert(ActionExecutionTrace::Enabled());logEnabled=false;
 assert(!ActionExecutionTrace::Enabled());
 assert(!ActionExecutionTrace::Fail("outside"));
 {
  ActionExecutionTrace off(false);ActionExecutionTrace::Fail("disabled");
  off.Finish(&bot,&action,false,false);assert(rows.empty());
 }
 {
  ActionExecutionTrace parent(true);
  assert(!ActionExecutionTrace::Fail("parent"));
  ActionExecutionTrace::Spell(403,71);ActionExecutionTrace::RawResult(true);
  assert(parent.GetRawResult());
  auto target=new Unit;ActionExecutionTrace::Target(target);delete target;
  {
   ActionExecutionTrace child(true);assert(!child.GetRawResult());
   child.Finish(&bot,&action,false,false);
   assert(rows.back().reason=="unattributed" && rows.back().spell==0);
   ActionExecutionTrace::Fail("child");ActionExecutionTrace::Spell(100,3);
   child.Finish(&bot,&action,false,false);assert(rows.back().reason=="child");
  }
  parent.Finish(&bot,&action,true,false);
  assert(rows.back().reason=="parent"&&rows.back().spell==403&&rows.back().code==71);
  assert(rows.back().target==9&&rows.back().x==12); // Snapshot, not a retained pointer.
  {
   ActionExecutionTrace direct(false);ActionExecutionTrace::Fail("direct");
  }
  parent.Finish(&bot,&action,true,false);assert(rows.back().reason=="parent");
  ActionExecutionTrace::Fail("parent-again");
  parent.Finish(&bot,&action,false,false);
  assert(rows.back().reason=="parent-again"&&rows.back().detail=="parent");
  parent.Finish(&bot,&action,true,true);
  assert(rows.back().reason=="none"&&rows.back().detail=="none");
 }
 {
  ActionExecutionTrace next(true);next.Finish(&bot,&action,false,false);
  assert(rows.back().reason=="unattributed"&&rows.back().spell==0&&rows.back().target==0);
 }
 assert(!ActionExecutionTrace::Fail("after")); // No dangling current frame.
}
'''
source=prefix+header+body+test
env=dict(os.environ,ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1')
with tempfile.TemporaryDirectory(prefix='loa-execution-trace-') as tmp:
    binary=Path(tmp)/'test'
    def run(text):
        subprocess.run([compiler,'-std=c++20','-O1','-g','-no-pie','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer','-x','c++','-','-o',str(binary)],input=text,text=True,check=True)
        return subprocess.run([str(binary)],capture_output=True,text=True,env=env)
    result=run(source)
    assert result.returncode==0,result.stderr
    print('Execution trace isolation, snapshot and observational returns passed',flush=True)
    for name,old,new in (
        ('lost parent restoration','~ActionExecutionTrace() { current = previous; }','~ActionExecutionTrace() { current = nullptr; }'),
        ('disabled nested contamination','current = enabled ? this : nullptr;','current = enabled ? this : previous;'),
        ('changed gameplay return','        return false;','        return true;'),
        ('stale failure on success','finalResult ? "none" : reason','reason'),
    ):
        assert old in source
        result=run(source.replace(old,new,1))
        assert result.returncode!=0,'Surviving mutation: '+name
        print('Mutation rejected:',name,flush=True)
