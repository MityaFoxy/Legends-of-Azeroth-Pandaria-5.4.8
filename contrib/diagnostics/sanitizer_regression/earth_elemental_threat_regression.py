#!/usr/bin/env python3
"""Execute the real Earth Elemental scheduled task with threat-list doubles."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
text = (root/'src/server/scripts/Spells/spell_shaman.cpp').read_text()
start = text.index('struct npc_sha_earth_elemental ')
start = text.index('    void Reset() override', start)
end = text.index('\n    void UpdateAI(', start)
reset = text[start:end].replace(' override', '')
prefix = r'''
#include <cassert>
#include <chrono>
#include <functional>
using Milliseconds=std::chrono::milliseconds;
constexpr int TYPEID_PLAYER=1, TYPEID_UNIT=2, ROLES_TANK=1, ROLES_DAMAGE=2;
struct Unit;
struct ThreatManager {
    bool allowed=false;
    int calls=0;
    Unit* victim=nullptr;
    bool CanHaveThreatList() { return allowed; }
    Unit* GetCurrentVictim() { assert(allowed); ++calls; return victim; }
};
struct Unit {
    int type=TYPEID_UNIT, role=ROLES_DAMAGE;
    Unit* victim=nullptr;
    ThreatManager threat;
    Unit* GetVictim() {return victim;}
    ThreatManager& GetThreatManager() {return threat;}
    int GetTypeId() {return type;}
    Unit* ToPlayer() {assert(type==TYPEID_PLAYER); return this;}
    int GetRoleForGroup() {return role;}
};
struct TaskContext { void Repeat(Milliseconds d) {assert(d.count()==5000);} };
struct Scheduler {
    std::function<void(TaskContext)> callback;
    void CancelAll() {callback={};}
    void Schedule(Milliseconds d,std::function<void(TaskContext)> f) {assert(d.count()==1);callback=f;}
};
struct AI {
    Unit* me;
    Scheduler scheduler;
    int casts=0;
    enum {SPELL_SHAMAN_ANGEREDEARTH=36213};
    void DoCastVictim(int spell) {assert(spell==36213); if(me->GetVictim()) ++casts;}
'''
suffix = r'''
};
int main() {
    Unit elemental,target,tank;
    AI ai{&elemental}; ai.Reset();
    ai.scheduler.callback({}); assert(ai.casts==0);
    elemental.victim=&target;
    // PvP player and controlled summon targets have no threat list.
    for (int type : {TYPEID_PLAYER,TYPEID_UNIT}) {
        target.type=type;
        ai.scheduler.callback({});
        assert(target.threat.calls==0);
    }
    assert(ai.casts==2);
    target.type=TYPEID_UNIT; target.threat.allowed=true;
    ai.scheduler.callback({}); assert(ai.casts==3 && target.threat.calls==1);
    target.threat.victim=&tank; tank.type=TYPEID_PLAYER; tank.role=ROLES_TANK;
    ai.scheduler.callback({}); assert(ai.casts==3 && target.threat.calls==2);
    tank.role=ROLES_DAMAGE;
    ai.scheduler.callback({}); assert(ai.casts==4 && target.threat.calls==3);
    tank.type=TYPEID_UNIT;
    ai.scheduler.callback({}); assert(ai.casts==5 && target.threat.calls==4);
    ai.Reset(); ai.scheduler.callback({}); assert(ai.casts==6);
}
'''
with tempfile.TemporaryDirectory(prefix='loa-earth-elemental-') as directory:
    cpp=Path(directory)/'test.cpp'; binary=Path(directory)/'test'
    for mutation in (False,True):
        body=reset
        if mutation:
            body=body.replace('target->GetThreatManager().CanHaveThreatList()',
                              'target->GetThreatManager().GetCurrentVictim()')
            assert body != reset
        cpp.write_text(prefix+body+suffix)
        subprocess.run([sys.argv[2],'-std=c++20','-O1','-g','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer',str(cpp),'-o',str(binary)],check=True)
        p=subprocess.run([str(binary)],capture_output=True,text=True,env=dict(os.environ,
            ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1'))
        if mutation:
            assert p.returncode != 0 and 'allowed' in p.stderr,p.stderr
        else:
            assert p.returncode == 0,p.stderr
print('PASS: Earth Elemental player/summon/NPC targets, tank protection, one threat query, old-call mutation rejected')
