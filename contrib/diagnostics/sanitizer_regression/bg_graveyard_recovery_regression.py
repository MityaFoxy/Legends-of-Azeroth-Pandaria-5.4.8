#!/usr/bin/env python3
"""Compile real recovery + native return handler against deterministic doubles.

Tests decision/lifecycle safety, not live terrain, DBC or teleport implementation.
Native wave/queue semantics are covered by battleground_resurrection_regression.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
recovery = (root / 'modules/mod_playerbots/src/Manager/BattlegroundGraveyardRecovery.cpp').read_text()
hook = (root / 'modules/mod_playerbots/src/mod_playerbots.cpp').read_text()
assert 'BattlegroundGraveyardRecovery::Update(diff);' in hook
assert 'ResurrectPlayer(' not in recovery and 'TeleportTo(' not in recovery
assert 'AddPlayerToResurrectQueue(' not in recovery and 'RemoveAurasDueToSpell(' not in recovery


def body(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


handler = body((root / 'src/server/game/Handlers/MiscHandler.cpp').read_text(),
               'void WorldSession::HandleReturnToGraveyard(')
timer = body((root / 'src/common/Utilities/Timer.h').read_text(),
             'inline uint32 getMSTimeDiff(uint32 oldMSTime, uint32 newMSTime)')
source = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <map>
#include <set>
using uint32 = std::uint32_t;
using ObjectGuid = unsigned;
#define TC_LOG_INFO(...) ((void)0)
constexpr int PLAYER_FLAGS_GHOST=1, PLAYER_FIELD_PLAYER_FLAGS=1,
    SPELL_WAITING_FOR_RESURRECT=2584, STATUS_IN_PROGRESS=3,
    ALLIANCE=469, HORDE=67, BG_CREATURE_ENTRY_A_SPIRITGUIDE=13116,
    BG_CREATURE_ENTRY_H_SPIRITGUIDE=13117, AREA_FLAG_NEED_FLY=1,
    CMSG_RETURN_TO_GRAVEYARD=42;
uint32 clockTime=1000;
uint32 getMSTime() { return clockTime; }
uint32 getMSTimeDiff(uint32 before, uint32 now);
struct WorldPacket { explicit WorldPacket(int op) { assert(op==CMSG_RETURN_TO_GRAVEYARD); } };
struct Player;
struct WorldSession {
    Player* player=nullptr;
    bool logout=false;
    bool isLogingOut() { return logout; }
    int GetAccountId() { return 1; }
    Player* GetPlayer() { return player; }
    void HandleReturnToGraveyard(WorldPacket&);
};
struct PlayerbotAI {
    bool real=false, master=false;
    bool IsRealPlayer() { return real; }
    bool HasRealPlayerMaster() { return master; }
};
struct Config {
    float sightDistance=75;
    bool random=true;
    bool IsInRandomAccountList(int) { return random; }
} config;
Config* sPlayerbotAIConfig=&config;
struct Creature { bool service=true; bool IsSpiritService() { return service; } };
struct Map {};
struct WorldSafeLocsEntry { uint32 ID=893, map_id=529; float x=500,y=500,z=0; };
struct AreaTableEntry { uint32 Flags=0; float MaxDepth=-500; };
struct AreaStore {
    AreaTableEntry area;
    bool present=true;
    AreaTableEntry const* LookupEntry(uint32) { return present ? &area : nullptr; }
} sAreaTableStore;
struct Battleground {
    Map map;
    bool arena=false,rated=false,attached=true,hasGrave=true;
    uint32 instance=1, status=STATUS_IN_PROGRESS;
    WorldSafeLocsEntry grave;
    bool IsArena() { return arena; }
    bool IsRated() { return rated; }
    uint32 GetStatus() { return status; }
    Map* FindBgMap() { return attached ? &map : nullptr; }
    uint32 GetInstanceID() { return instance; }
    WorldSafeLocsEntry const* GetClosestGraveYard(Player*) { return hasGrave ? &grave : nullptr; }
};
struct Player {
    PlayerbotAI ai;
    bool hasAI=true,hasSession=true,alive=false,ghost=true,world=true,teleporting=false,waiting=false,transport=false;
    bool transferSucceeds=true,guideAlive=true;
    uint32 mapId=529,instance=1,team=ALLIANCE,guid=1;
    int requests=0,searches=0;
    float x=0,y=0,z=0;
    Battleground* bg;
    Map* map;
    Creature* guide=nullptr;
    WorldSession session;
    explicit Player(Battleground& b):bg(&b),map(&b.map) { session.player=this; }
    WorldSession* GetSession() { return hasSession ? &session : nullptr; }
    bool IsAlive() { return alive; }
    bool HasPlayerFlag(int) { return ghost; }
    bool HasFlag(int,int) { return ghost; }
    bool IsInWorld() { return world; }
    bool IsBeingTeleported() { return teleporting; }
    Battleground* GetBattleground() { return bg; }
    Map* GetMap() { return map; }
    uint32 GetMapId() { return mapId; }
    uint32 GetInstanceId() { return instance; }
    uint32 GetBGTeam() { return team; }
    bool HasAura(int) { return waiting; }
    Creature* FindNearestCreature(uint32 entry,float range,bool aliveGuide) {
        assert(entry==uint32(team==ALLIANCE ? BG_CREATURE_ENTRY_A_SPIRITGUIDE : BG_CREATURE_ENTRY_H_SPIRITGUIDE));
        assert(range==75); ++searches;
        return guideAlive==aliveGuide ? guide : nullptr;
    }
    uint32 GetAreaId() { return 3358; }
    bool GetTransport() { return transport; }
    float GetPositionZ() { return z; }
    float GetExactDist(float a,float b,float c) { return std::sqrt((a-x)*(a-x)+(b-y)*(b-y)+(c-z)*(c-z)); }
    ObjectGuid GetGUID() { return guid; }
    void RepopAtGraveyard() {
        assert(!alive && ghost && !waiting); ++requests;
        if (transferSucceeds) { x=bg->grave.x; y=bg->grave.y; z=bg->grave.z; }
    }
};
#define GET_PLAYERBOT_AI(bot) ((bot)->hasAI ? &(bot)->ai : nullptr)
struct Manager {
    std::map<ObjectGuid,Player*> bots;
    auto GetPlayerBotsBegin() { return bots.begin(); }
    auto GetPlayerBotsEnd() { return bots.end(); }
} manager;
Manager* sRandomPlayerbotMgr=&manager;
namespace BattlegroundGraveyardRecovery { void Update(uint32); }
'''
source += timer + '\n' + handler + '\n' + recovery[recovery.index('namespace\n{'):]
source += r'''
int main() {
    Battleground bg;
    Player p(bg);
    State s;
    assert(Recover(&p,s,1000) && p.requests==1 && !p.alive && !p.waiting);
    assert(!Recover(&p,s,12000)); // At the chosen grave, no teleport-in-place.
    // Second node lost before registration: new native destination, another return.
    bg.grave.ID=894; bg.grave.x=1000;
    assert(!Recover(&p,s,2000)); // Destination changes do not bypass cooldown.
    assert(Recover(&p,s,11000) && p.requests==2);
    Creature guide;
    p.guide=&guide;
    assert(!Recover(&p,s,22000)); // Normal approach/registration owns the next step.
    p.waiting=true; p.guide=nullptr;
    bg.grave.ID=895; bg.grave.x=1500;
    int searches=p.searches;
    assert(!Recover(&p,s,33000) && p.searches==searches && p.waiting);

    // A failed transfer is bounded, and a newly selected grave can recover later.
    p.waiting=false; p.transferSucceeds=false; s=State{}; p.requests=0;
    assert(Recover(&p,s,0));
    assert(!Recover(&p,s,9999));
    assert(Recover(&p,s,10000));
    assert(Recover(&p,s,20000));
    assert(!Recover(&p,s,30000) && p.requests==3);
    bg.grave.ID=896;
    assert(Recover(&p,s,30000));
    s.lastRequest=UINT32_MAX-4999;
    assert(!Recover(&p,s,4999));
    assert(!Recover(&p,s,5000));
    assert(Recover(&p,s,5001)); // Native timer's millisecond clock wrap.

    // Each veto is independent and must have no return side effect.
    auto blocked=[&](auto change) {
        Battleground b; Player q(b); State t; change(q,b);
        assert(!Recover(&q,t,1000) && q.requests==0);
    };
    blocked([](auto& q,auto&){q.alive=true;});
    blocked([](auto& q,auto&){q.ghost=false;});
    blocked([](auto& q,auto&){q.ai.real=true;});
    blocked([](auto& q,auto&){q.ai.master=true;});
    blocked([](auto& q,auto&){q.hasAI=false;});
    blocked([](auto& q,auto&){q.hasSession=false;});
    blocked([](auto& q,auto&){q.session.logout=true;});
    blocked([](auto& q,auto&){q.world=false;});
    blocked([](auto& q,auto&){q.teleporting=true;});
    blocked([](auto& q,auto&){q.bg=nullptr;});
    blocked([](auto&,auto& b){b.arena=true;});
    blocked([](auto&,auto& b){b.rated=true;});
    blocked([](auto&,auto& b){b.status=4;});
    blocked([](auto&,auto& b){b.attached=false;});
    blocked([](auto& q,auto&){q.map=nullptr;});
    blocked([](auto& q,auto&){q.instance=2;});
    blocked([](auto& q,auto&){q.waiting=true;});
    blocked([](auto& q,auto&){q.transport=true;});
    blocked([](auto& q,auto&){q.z=-501;});
    blocked([](auto& q,auto&){q.z=NAN;});
    blocked([](auto& q,auto&){q.x=NAN;});
    blocked([](auto&,auto& b){b.hasGrave=false;});
    blocked([](auto&,auto& b){b.grave.map_id=30;});
    blocked([](auto&,auto& b){b.grave.x=NAN;});
    blocked([](auto&,auto& b){b.grave.y=INFINITY;});
    blocked([](auto&,auto& b){b.grave.z=NAN;});
    blocked([&](auto& q,auto&){q.guide=&guide;});
    blocked([&](auto& q,auto&){q.guide=&guide;q.guideAlive=false;});
    sAreaTableStore.present=false;
    blocked([](auto&,auto&){}); sAreaTableStore.present=true;
    sAreaTableStore.area.Flags=AREA_FLAG_NEED_FLY;
    blocked([](auto&,auto&){}); sAreaTableStore.area.Flags=0;
    config.random=false;
    blocked([](auto&,auto&){}); config.random=true;
    assert(!Recover(nullptr,s,1000));

    // World hook works without the test controller and cleans up per-life state.
    states.clear(); p=Player(bg); p.session.player=&p;
    manager.bots[1]=&p;
    BattlegroundGraveyardRecovery::Update(500); assert(p.requests==0);
    BattlegroundGraveyardRecovery::Update(500); assert(p.requests==1 && states.size()==1);
    p.alive=true;
    BattlegroundGraveyardRecovery::Update(1000); assert(states.empty());
    p.alive=false; p.x=0;
    BattlegroundGraveyardRecovery::Update(1000); assert(p.requests==2);
    manager.bots.clear();
    BattlegroundGraveyardRecovery::Update(1000); assert(states.empty());
    // Instance/team transitions discard the old destination budget.
    s=State{}; p.x=0; p.transferSucceeds=false;
    for(uint32 i=1;i<=3;++i) assert(Recover(&p,s,i*10000));
    p.instance=bg.instance=2;
    assert(Recover(&p,s,31000));
    p.team=HORDE;
    assert(Recover(&p,s,32000));
    // Native handler independently rejects living and unreleased players.
    WorldPacket packet(CMSG_RETURN_TO_GRAVEYARD);
    int before=p.requests; p.alive=true;
    p.session.HandleReturnToGraveyard(packet); assert(p.requests==before);
    p.alive=false; p.ghost=false;
    p.session.HandleReturnToGraveyard(packet); assert(p.requests==before);
    std::puts("BG native graveyard return: double loss, guards, retry budget and lifecycle OK");
}
'''

with tempfile.TemporaryDirectory(prefix='loa-bg-graveyard-') as directory:
    def run(name, code):
        cpp = Path(directory) / (name + '.cpp')
        exe = Path(directory) / name
        cpp.write_text(code)
        subprocess.run([sys.argv[2], '-std=c++20', '-g', '-D_GLIBCXX_DEBUG',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-fno-pie', '-no-pie', str(cpp), '-o', str(exe)], check=True)
        return subprocess.run([str(exe)], capture_output=True, text=True, env=dict(os.environ,
            ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1'))

    result = run('regression', source)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout.strip())
    if '--verify-mutations' in sys.argv:
        for name, old, new in (
            ('missing-return', 'bot->GetSession()->HandleReturnToGraveyard(packet);', ''),
            ('waiting-queue-moved', 'if (bot->HasAura(SPELL_WAITING_FOR_RESURRECT))', 'if (false)'),
            ('teleport-in-place', 'distance <= GRAVEYARD_ARRIVAL_DISTANCE', 'false'),
            ('unbounded-retries', 'if (state.attempts >= MAX_RETURN_ATTEMPTS)', 'if (false)'),
        ):
            assert old in source, name
            result = run(name, source.replace(old, new))
            assert result.returncode != 0 and 'Assertion' in result.stderr, name + ': ' + result.stderr
            print('Rejected mutation: ' + name)
