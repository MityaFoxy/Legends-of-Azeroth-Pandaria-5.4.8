#!/usr/bin/env python3
"""Actual death/logout script and runtime adapter against controlled core APIs."""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
module = root / "modules/mod_botlife/src"
source = (module / "BotLifeDefeats.cpp").read_text()
source = "\n".join(line for line in source.splitlines() if not line.startswith("#include"))
mocks = r'''
#include "BotLifeDefeats.h"
#include <cassert>
#include <algorithm>
#include <mutex>
#include <unordered_map>
using uint32=uint32_t;
uint32_t clockMs=1;
uint32_t getMSTime() { return clockMs; }
#define TC_LOG_INFO(...) ((void)0)
struct Guid { uint64_t value; uint32_t GetCounter() const { return value; }
    uint64_t GetRawValue() const { return value; } };
struct PlayerbotAI {
    bool real=false,master=false;
    bool IsRealPlayer() const { return real; }
    bool HasRealPlayerMaster() const { return master; }
};
class Unit {
public:
    virtual ~Unit()=default;
    virtual Player* ToPlayer() { return nullptr; }
    virtual Creature* ToCreature() { return nullptr; }
    float x=0,y=0,z=0; uint32_t map=1,instance=2,phase=1;
    float GetPositionX() const { return x; }
    float GetPositionY() const { return y; }
    float GetPositionZ() const { return z; }
    uint32_t GetMapId() const { return map; }
    uint32_t GetInstanceId() const { return instance; }
    uint32_t GetPhaseMask() const { return phase; }
};
class UnitScript {
public:
    explicit UnitScript(char const*) {}
    virtual ~UnitScript()=default;
    virtual void OnDamage(Unit*,Unit*,uint32&) {}
};
class Player : public Unit {
public:
    Player* ToPlayer() override { return this; }
    bool combat=true,alive=true;
    bool IsInCombat() const { return combat; }
    bool IsAlive() const { return alive; }
    uint32_t id=1; bool bg=false,arena=false; PlayerbotAI ai;
    Guid GetGUID() const { return {id}; }
    bool InBattleground() const { return bg; }
    bool InArena() const { return arena; }
};
class Creature : public Unit {
public:
    Creature* ToCreature() override { return this; }
    uint32_t entry=3,spawn=4; uint64_t runtime=5;
    uint32_t GetEntry() const { return entry; }
    uint32_t GetSpawnId() const { return spawn; }
    Guid GetGUID() const { return {runtime}; }
};
#define GET_PLAYERBOT_AI(p) (&(p)->ai)
class PlayerScript {
public:
    explicit PlayerScript(char const*) {}
    virtual ~PlayerScript()=default;
    virtual void OnPlayerKilledByCreature(Creature*,Player*) {}
    virtual void OnLogout(Player*) {}
    virtual void OnUpdate(Player*,uint32) {}
};
namespace BotLife { bool enabled=true; bool IsEligibleBot(uint32_t) { return enabled; } }
'''
tests = r'''
int main() {
    using namespace BotLife;
    DefeatMemoryScript hook;
    Player bot,other; other.id=2;
    Creature killer,unrelated; unrelated.spawn=44;
    hook.OnPlayerKilledByCreature(&killer,&bot);
    assert(!AvoidDefeatedOpponent(bot,killer));
    hook.OnPlayerKilledByCreature(&unrelated,&bot);
    assert(!AvoidDefeatedOpponent(bot,killer));
    hook.OnPlayerKilledByCreature(&killer,&bot);
    assert(AvoidDefeatedOpponent(bot,killer) && !AvoidDefeatedOpponent(bot,unrelated));
    assert(!AvoidDefeatedOpponent(other,killer));
    ++killer.runtime; // Same spawn after respawn remains known.
    assert(AvoidDefeatedOpponent(bot,killer));
    ++killer.instance; assert(!AvoidDefeatedOpponent(bot,killer)); --killer.instance;
    clockMs+=DefeatHistory::LifetimeMs;
    assert(!AvoidDefeatedOpponent(bot,killer));
    hook.OnPlayerKilledByCreature(&killer,&bot); hook.OnPlayerKilledByCreature(&killer,&bot);
    hook.OnLogout(&bot); assert(!AvoidDefeatedOpponent(bot,killer));
    for(int gate=0;gate<5;++gate) {
      enabled=gate!=0; bot.ai.real=gate==1; bot.ai.master=gate==2;
      bot.bg=gate==3; bot.arena=gate==4;
      hook.OnPlayerKilledByCreature(&killer,&bot); hook.OnPlayerKilledByCreature(&killer,&bot);
      assert(memories.empty());
    }
    enabled=true; bot.ai={}; bot.bg=bot.arena=false;
    killer.spawn=0;
    hook.OnPlayerKilledByCreature(&killer,&bot); hook.OnPlayerKilledByCreature(&killer,&bot);
    assert(AvoidDefeatedOpponent(bot,killer));
    ++killer.runtime; assert(!AvoidDefeatedOpponent(bot,killer));
    for(uint32_t i=10;i<1040;++i) { other.id=i; ++clockMs; hook.OnPlayerKilledByCreature(&killer,&other); }
    assert(memories.size()==1024);
    hook.OnPlayerKilledByCreature(nullptr,&bot); hook.OnLogout(nullptr);
    memories.clear(); killer.spawn=4; unrelated.spawn=44;
    EncounterScript observer; uint32 damage=12;
    killer.x=50; unrelated.x=54;
    observer.OnDamage(&bot,&killer,damage); // Outgoing damage observes the first opponent.
    observer.OnDamage(&unrelated,&bot,damage);
    bot.x=200; // Fleeing death must not move the camp anchor to the corpse.
    hook.OnPlayerKilledByCreature(&unrelated,&bot);
    assert(GetDefeatAreas(bot).empty());
    observer.OnDamage(&killer,&bot,damage);
    hook.OnPlayerKilledByCreature(&killer,&bot);
    auto areas=GetDefeatAreas(bot);
    assert(areas.size()==1 && areas[0].origin.x==50 && areas[0].death.x==200);
    assert(!AvoidDefeatedOpponent(bot,killer) && !AvoidDefeatedOpponent(bot,unrelated));
    assert(GetDefeatAreas(other).empty());
    ++bot.phase; assert(GetDefeatAreas(bot).empty()); --bot.phase;
    // A new QuestRun is irrelevant to adapter-owned memory; only logout clears it.
    assert(GetDefeatAreas(bot).size()==1);
    hook.OnLogout(&bot); assert(GetDefeatAreas(bot).empty());
    for(int gate=0;gate<6;++gate) {
      enabled=gate!=0; bot.ai.real=gate==1; bot.ai.master=gate==2;
      bot.bg=gate==3; bot.arena=gate==4; damage=gate==5?0:12;
      observer.OnDamage(&killer,&bot,damage); assert(memories.empty());
    }
    enabled=true; bot.ai={}; bot.bg=bot.arena=false; damage=12;
    observer.OnDamage(&killer,&bot,damage);
    assert(damage==12 && !memories[bot.id].encounter.participants.empty());
    bot.combat=false; hook.OnUpdate(&bot,1); bot.combat=true;
    assert(memories[bot.id].encounter.participants.empty());
    observer.OnDamage(&killer,&bot,damage); clockMs+=30000;
    hook.OnPlayerKilledByCreature(&killer,&bot);
    assert(GetDefeatAreas(bot).empty());
}
'''
with tempfile.TemporaryDirectory(prefix="loa-defeat-") as directory:
    cpp = pathlib.Path(directory) / "test.cpp"
    binary = pathlib.Path(directory) / "test"
    cpp.write_text(mocks + source + tests)
    subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-UNDEBUG",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-pthread",
                    "-I", str(module), str(cpp), str(module / "BotLifeDefeatPolicy.cpp"),
                    "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
