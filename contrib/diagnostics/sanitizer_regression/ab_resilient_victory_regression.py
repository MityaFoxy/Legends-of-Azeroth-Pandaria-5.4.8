#!/usr/bin/env python3
"""Execute real AB scoring/reset/criteria bodies with deterministic world doubles.

The two criterion/worldstate bindings are fixtures from the runtime MoP DBC:
achievement 161, tree 4405 (ANY), criteria 3804/14966, states 5809/5810.
This is not a live DBC loader, database or player-persistence integration test.
"""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
ab = (root / 'src/server/game/Battlegrounds/Zones/BattlegroundAB.cpp').read_text()
header = (root / 'src/server/game/Battlegrounds/Zones/BattlegroundAB.h').read_text()
base = (root / 'src/server/game/Battlegrounds/Battleground.cpp').read_text()
base_header = (root / 'src/server/game/Battlegrounds/Battleground.h').read_text()


def body(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


finish = body(base, 'void Battleground::EndBattleground(')
assert finish.index('SetWinner(') < finish.index('FinalizeAchievementWorldStates(winner);')
assert finish.index('FinalizeAchievementWorldStates(winner);') < finish.index('ACHIEVEMENT_CRITERIA_TYPE_WIN_BG')
assert 'virtual void FinalizeAchievementWorldStates(uint32 /*winner*/) { }' in base_header
assert 'void FinalizeAchievementWorldStates(uint32 winner) override;' in header
assert re.search(r'bool CheckAchievementCriteriaMeet\([^;]+\) override;', header)
assert 'EndBattleground(GetPrematureWinner());' in body(base, 'void Battleground::CheckPrematureEnd(')
assert 'FinalizeAchievementWorldStates' not in body(ab, 'void BattlegroundAB::EndBattleground(')

source = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <functional>
#include <map>
using uint8=std::uint8_t;
using uint32=std::uint32_t;
using int32=std::int32_t;
enum TeamId { TEAM_ALLIANCE, TEAM_HORDE };
enum Team { ALLIANCE=469, HORDE=67 };
enum BattlegroundStatus { STATUS_WAIT_JOIN=2, STATUS_IN_PROGRESS=3, STATUS_WAIT_LEAVE=4 };
constexpr int BG_TEAMS_COUNT=2, WINNER_ALLIANCE=0, WINNER_HORDE=1, WINNER_NONE=2;
constexpr int LANG_BG_A_WINS=1, LANG_ARENA_GOLD_WINS=2, LANG_BG_H_WINS=3, LANG_ARENA_GREEN_WINS=4,
    SOUND_ALLIANCE_WINS=5, SOUND_HORDE_WINS=6, TIME_AUTOCLOSE_BATTLEGROUND=120000,
    LANG_BG_AB_NODE_TAKEN=7, CHAT_MSG_BG_SYSTEM_ALLIANCE=8, CHAT_MSG_BG_SYSTEM_HORDE=9,
    LANG_BG_AB_A_NEAR_VICTORY=10, LANG_BG_AB_H_NEAR_VICTORY=11, CHAT_MSG_BG_SYSTEM_NEUTRAL=12,
    LANG_BG_AB_ALLY=13, LANG_BG_AB_HORDE=14;
struct Unit {};
struct Battleground;
struct Player {
    Battleground* bg;
    TeamId bgTeam;
    TeamId raceTeam;
    Battleground* GetBattleground() const { return bg; }
    TeamId GetBGTeamId() const { return bgTeam; }
    TeamId GetTeam() const { return raceTeam; }
};
struct BattlegroundMap {
    std::map<uint32,uint32> states;
    void SetWorldState(uint32 id,uint32 value) { states[id]=value; }
    uint32 GetWorldState(uint32 id) { return states[id]; }
};
struct Manager { bool IsBGWeekend(int) { return false; } } manager;
Manager* sBattlegroundMgr=&manager;
int baseCriteriaCalls=0;
struct Battleground {
    BattlegroundMap world;
    bool hasMap=true;
    BattlegroundStatus status=STATUS_WAIT_JOIN;
    uint8 winner=WINNER_NONE;
    int32 m_TeamScores[2]={};
    std::function<void()> award;
    virtual ~Battleground()=default;
    virtual void FinalizeAchievementWorldStates(uint32) {}
    virtual bool CheckAchievementCriteriaMeet(uint32,Player const*,Unit const*,uint32=0) {
        ++baseCriteriaCalls; return false;
    }
    void Reset() { status=STATUS_WAIT_JOIN; winner=WINNER_NONE; }
    BattlegroundStatus GetStatus() const { return status; }
    uint8 GetWinner() const { return winner; }
    void SetStatus(BattlegroundStatus value) { status=value; }
    void SetWinner(uint8 value) { winner=value; }
    bool IsBattleground() { return true; }
    void PlaySoundToAll(int) {}
    void SetRemainingTime(int) {}
    BattlegroundMap* FindBgMap() { return hasMap ? &world : nullptr; }
    BattlegroundMap* GetBgMap() { assert(hasMap); return &world; }
    void EndBattleground(uint32 winner);
    int GetTypeID() { return 3; }
    void RewardHonorToTeam(int,uint32) {}
    void RewardReputationToTeam(int,int,int,uint32) {}
    int GetBonusHonorFromKill(int count) { return count; }
    void UpdateWorldState(int,int) {}
    void SendMessageToAll(int,int,void* = nullptr) {}
    void SendMessage2ToAll(int,int,void*,int,int) {}
};
'''
source += body(base_header, 'enum BattlegroundCriteriaId') + ';\n'
source += header[header.index('enum BG_AB_WorldStates'):header.index('struct BattlegroundABScore')]
source += body(ab, 'enum\n{') + ';\n'
source += r'''
struct BattlegroundAB : Battleground {
    uint8 m_Nodes[BG_AB_DYNAMIC_NODES_COUNT]={},m_prevNodes[BG_AB_DYNAMIC_NODES_COUNT]={};
    BG_AB_BannerTimer m_BannerTimers[BG_AB_DYNAMIC_NODES_COUNT]={};
    uint32 m_NodeTimers[BG_AB_DYNAMIC_NODES_COUNT]={};
    uint32 m_lastTick[2]={},m_HonorScoreTics[2]={},m_ReputationScoreTics[2]={};
    bool m_IsInformedNearVictory=false;
    uint32 m_HonorTics=260,m_ReputationTics=160;
    uint32 BgCreatures[BG_AB_ALL_NODES_COUNT+5]={};
'''
source += re.search(r'bool\s+m_TeamHadDisadvantage[^;]+;', header).group(0)
source += r'''
    void PostUpdateImpl(uint32);
    void Reset();
    void EndBattleground(uint32);
    void FinalizeAchievementWorldStates(uint32) override;
    bool CheckAchievementCriteriaMeet(uint32,Player const*,Unit const*,uint32=0) override;
    void _CreateBanner(uint8,uint8,uint8,bool) {}
    void _DelBanner(uint8,uint8,uint8) {}
    void _SendNodeUpdate(uint8) {}
    void _NodeOccupied(uint8,Team) {}
    int _GetNodeNameId(uint8) { return 0; }
    void DelCreature(uint8) {}
};
void Battleground::EndBattleground(uint32 winner) {
    int winmsg=0;
'''
# Execute the actual common finalization sequence, before a deterministic award callback.
source += finish[finish.index('    if (winner == ALLIANCE)'):finish.index('    // arena rating calculation')]
source += '    if (award) award();\n}\n'
for signature in ('void BattlegroundAB::PostUpdateImpl(', 'void BattlegroundAB::Reset(',
                  'void BattlegroundAB::FinalizeAchievementWorldStates(',
                  'bool BattlegroundAB::CheckAchievementCriteriaMeet(',
                  'void BattlegroundAB::EndBattleground('):
    source += body(ab, signature) + '\n'

source += r'''
// Mirrors the audited DB: only 3804 has the extra script; 14966 relies on DBC.
bool credit(BattlegroundAB& bg, Player& player, uint32 criterion) {
    if (bg.GetStatus()!=STATUS_WAIT_LEAVE || player.GetBGTeamId()!=bg.GetWinner()) return false;
    uint32 state=criterion==3804 ? 5809 : 5810;
    if (!bg.world.GetWorldState(state)) return false;
    return criterion!=3804 || bg.CheckAchievementCriteriaMeet(BG_CRITERIA_CHECK_RESILIENT_VICTORY,&player,nullptr);
}
void scores(BattlegroundAB& bg,int alliance,int horde) {
    bg.m_TeamScores[0]=alliance; bg.m_TeamScores[1]=horde;
    bg.PostUpdateImpl(0);
}
void expectAward(BattlegroundAB& bg,TeamId winner,bool eligible) {
    Player a{&bg,TEAM_ALLIANCE,TEAM_HORDE},h{&bg,TEAM_HORDE,TEAM_ALLIANCE}; // Cross-faction.
    bg.award=[&,winner,eligible] {
        assert(bg.GetWinner()==winner);
        assert(bg.world.GetWorldState(5809)==(eligible && winner==TEAM_HORDE));
        assert(bg.world.GetWorldState(5810)==(eligible && winner==TEAM_ALLIANCE));
        for (Player* p : {&a,&h}) {
            bool expected=eligible && p->bgTeam==winner;
            assert((credit(bg,*p,3804)||credit(bg,*p,14966))==expected);
            assert(bg.CheckAchievementCriteriaMeet(0,p,nullptr)==expected);
        }
    };
    // Must execute while the local players/captures are alive.
    bg.Battleground::EndBattleground(winner==TEAM_ALLIANCE ? ALLIANCE : HORDE);
    bg.award={};
}
int main() {
    for (TeamId team : {TEAM_ALLIANCE,TEAM_HORDE}) {
        for (int deficit : {499,500,501}) {
            BattlegroundAB bg;
            assert(!bg.m_TeamHadDisadvantage[0] && !bg.m_TeamHadDisadvantage[1]);
            bg.Reset(); bg.status=STATUS_IN_PROGRESS;
            scores(bg,team==TEAM_ALLIANCE ? 100 : 100+deficit,team==TEAM_HORDE ? 100 : 100+deficit);
            assert(bg.m_TeamHadDisadvantage[team]==(deficit>=500));
            assert(!bg.m_TeamHadDisadvantage[1-team]);
            Player player{&bg,team,team};
            assert(!bg.CheckAchievementCriteriaMeet(0,&player,nullptr)); // Not yet a win.
            scores(bg,1000,1000); // Catching up must not erase history.
            expectAward(bg,team,deficit>=500); // Base path: includes premature finishes.
            bg.Reset();
            assert(!bg.m_TeamHadDisadvantage[0] && !bg.m_TeamHadDisadvantage[1]);
            assert(!bg.world.GetWorldState(5809) && !bg.world.GetWorldState(5810));
            bg.status=STATUS_IN_PROGRESS;
            expectAward(bg,team,false); // Same instance, next match.
        }
        BattlegroundAB bg;
        bg.Reset(); bg.status=STATUS_IN_PROGRESS;
        // Dominant victory is not a comeback. Only the loser trailed.
        scores(bg,team==TEAM_ALLIANCE ? 900 : 100,team==TEAM_HORDE ? 900 : 100);
        expectAward(bg,team,false);

        bg.Reset(); bg.status=STATUS_IN_PROGRESS;
        scores(bg,100,700); scores(bg,1300,700); // Both sides have trailed.
        expectAward(bg,team,true); // Only winner's DBC branch may be active.

        // Real scoring loop reaches 1600 and invokes AB then common finalization.
        bg.Reset(); bg.status=STATUS_IN_PROGRESS;
        scores(bg,team==TEAM_ALLIANCE ? 0 : 500,team==TEAM_HORDE ? 0 : 500);
        bg.m_TeamScores[team]=1590; bg.m_TeamScores[1-team]=1580;
        bg.m_Nodes[0]=uint8(team)+BG_AB_NODE_TYPE_OCCUPIED;
        Player winner{&bg,team,team};
        bool awarded=false;
        bg.award=[&] { awarded=credit(bg,winner,3804)||credit(bg,winner,14966); };
        bg.PostUpdateImpl(BG_AB_TickIntervals[1]+1);
        assert(bg.m_TeamScores[team]==1600 && awarded);
        assert(bg.GetStatus()==STATUS_WAIT_LEAVE);
        bg.award={};
    }
    BattlegroundAB bg,other;
    bg.Reset(); bg.status=STATUS_IN_PROGRESS;
    // Both resource ticks occur together: transient 500 gap is not a true deficit.
    bg.m_Nodes[0]=BG_AB_NODE_STATUS_ALLY_OCCUPIED;
    bg.m_Nodes[1]=BG_AB_NODE_STATUS_HORDE_OCCUPIED;
    bg.m_TeamScores[0]=590; bg.m_TeamScores[1]=100;
    bg.PostUpdateImpl(BG_AB_TickIntervals[1]+1);
    assert(bg.m_TeamScores[0]==600 && bg.m_TeamScores[1]==110);
    assert(!bg.m_TeamHadDisadvantage[0] && !bg.m_TeamHadDisadvantage[1]);
    bg.Reset(); bg.status=STATUS_WAIT_JOIN;
    scores(bg,0,900); assert(!bg.m_TeamHadDisadvantage[0]); // Pregame excluded.
    bg.status=STATUS_IN_PROGRESS;
    scores(bg,0,600); scores(bg,1200,600);
    bg.Battleground::EndBattleground(WINNER_NONE);
    assert(!bg.world.GetWorldState(5809) && !bg.world.GetWorldState(5810));
    Player a{&bg,TEAM_ALLIANCE,TEAM_ALLIANCE},outsider{&other,TEAM_ALLIANCE,TEAM_ALLIANCE};
    assert(!bg.CheckAchievementCriteriaMeet(0,&a,nullptr));
    assert(!bg.CheckAchievementCriteriaMeet(0,nullptr,nullptr));
    bg.Battleground::EndBattleground(ALLIANCE);
    assert(!bg.CheckAchievementCriteriaMeet(0,&outsider,nullptr));
    assert(baseCriteriaCalls==0); // Known criterion never reaches missing-implementation log.
    assert(!bg.CheckAchievementCriteriaMeet(999,&a,nullptr));
    assert(baseCriteriaCalls==1); // Unrelated criteria still delegate normally.
    bg.hasMap=false; bg.Reset(); // Mapless template reset must be safe.
    assert(!bg.m_TeamHadDisadvantage[0] && !bg.m_TeamHadDisadvantage[1]);
    Battleground unrelated;
    unrelated.EndBattleground(ALLIANCE);
    assert(unrelated.world.states.empty()); // Default hook doesn't touch other BGs.
    std::puts("AB Resilient Victory: thresholds, both teams, DBC gates, reset, normal/premature wins OK");
}
'''

with tempfile.TemporaryDirectory(prefix='loa-ab-resilient-') as directory:
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
            ('strict-threshold', '>= 500)', '> 500)'),
            ('forget-history', 'm_TeamHadDisadvantage[team] = true;', 'm_TeamHadDisadvantage[team] = false;'),
            ('loser-credit', 'winner == ALLIANCE && m_TeamHadDisadvantage[TEAM_ALLIANCE]', 'm_TeamHadDisadvantage[TEAM_ALLIANCE]'),
            ('missing-alliance-branch', 'winner == ALLIANCE && m_TeamHadDisadvantage[TEAM_ALLIANCE]', 'false'),
            ('missing-finalization', 'FinalizeAchievementWorldStates(winner);', ''),
            ('stale-match-history', 'm_TeamHadDisadvantage[TEAM_HORDE] = false;', ''),
            ('racial-team', 'TeamId team = source->GetBGTeamId();', 'TeamId team = source->GetTeam();'),
        ):
            assert old in source, name
            result = run(name, source.replace(old, new))
            assert result.returncode != 0 and 'Assertion' in result.stderr, name + ': ' + result.stderr
            print('Rejected mutation: ' + name)
