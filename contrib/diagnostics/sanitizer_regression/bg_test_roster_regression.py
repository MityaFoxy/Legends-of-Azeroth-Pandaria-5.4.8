#!/usr/bin/env python3
"""Run real fixed-level test eligibility/readiness with bounded world doubles."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
controller = (root / 'modules/mod_playerbots/src/Manager/BattlegroundTestController.cpp').read_text()
brackets = (root / 'modules/mod_playerbots/src/Manager/RandomPlayerbotBracketMgr.cpp').read_text()


def function(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


level = function(controller, 'uint8 BattlegroundTest::GetTargetLevel(')
eligible = function(controller, 'bool Eligible(')
repair = function(controller, 'bool RepairQueueReadiness(')
# Exercise the real distribution entry gate, before any per-bracket work.
gate = brackets.split('void RandomBotBacketManager::Update(uint32 diff)', 1)[1].split('_timer += diff;', 1)[0]
update = function(controller, 'void BattlegroundTest::Update(')
assert update.index('if (!Eligible(ai))') < update.index('RepairQueueReadiness(bot, state, now, repairBudget)')
assert update.index('if (bot->InBattlegroundQueue())') < update.index('RepairQueueReadiness(bot, state, now, repairBudget)')
assert 'bot->IsAlive() && !bot->IsInCombat() && !bot->GetGroup()' in update
source = r'''
#include <cassert>
#include <cstdint>
#include <set>
using uint8=std::uint8_t;
using uint32=std::uint32_t;
constexpr uint32 DEFAULT_MAX_LEVEL=90, QUEUE_READINESS_RETRY_INTERVAL=60000;
uint32 getMSTimeDiff(uint32 before,uint32 after) { return after-before; }
struct Config {
    bool battlegroundTest=true;
    uint32 randomBotMinLevel=90, randomBotMaxLevel=90;
    bool IsInRandomAccountList(uint32 id) { return id==1; }
} config;
auto sPlayerbotAIConfig=&config;
namespace BattlegroundTest { uint8 GetTargetLevel(); }
struct Session { uint32 account=1; uint32 GetAccountId() { return account; } } session;
struct Player {
    uint32 level=25, target=0, items=0, instance=0, tags=0, randomizations=0, saves=0;
    bool scheduled=false, flight=false, fail=false;
    uint32 GetLevel() { return level; }
    uint32 GetInstanceId() { return instance; }
    bool IsInFlight() { return flight; }
    void SaveToDB(bool) { ++saves; }
    Session* GetSession() { return &session; }
};
struct PlayerbotAI {
    Player* bot;
    bool real=false, owner=false;
    Player* GetBot() { return bot; }
    bool IsRealPlayer() { return real; }
    bool HasRealPlayerMaster() { return owner; }
};
struct Manager {
    uint32 GetValue(Player* p,char const*) { return p->target; }
    bool HasPendingRandomization(Player* p) { return p->scheduled && p->target && p->target!=p->level; }
    void TagForRandomize(Player* p,uint32 target) { p->target=target; p->scheduled=true; ++p->tags; }
    void Randomize(Player* p) { ++p->randomizations; if(!p->fail) {p->level=p->target;p->items=15;p->scheduled=false;} }
} manager;
auto sRandomPlayerbotMgr=&manager;
enum class QueueReadinessIssue { None, PendingRandomization, MissingEquipment, RepairBudget, RepairFailed };
struct State {
    QueueReadinessIssue readinessIssue=QueueReadinessIssue::None;
    bool readinessRepairAttempted=false;
    uint32 lastReadinessRepair=0;
};
uint32 EquippedCombatItems(Player* p) {return p->items;}
void LogQueueReadiness(Player*,State&,QueueReadinessIssue,uint32,uint32,uint32,char const*) {}
struct BotFactory {
    Player* p;
    BotFactory(Player* player,uint32):p(player) {}
    void InitEquipment(bool) {p->items=15;}
};
'''
source += level + eligible + repair
source += 'bool distributionRan=false; void distribute()' + gate + 'distributionRan=true; }\n'
source += r'''
int main() {
    Player p;
    PlayerbotAI ai{&p};
    assert(Eligible(&ai));
    ai.real=true; assert(!Eligible(&ai)); ai.real=false;
    ai.owner=true; assert(!Eligible(&ai)); ai.owner=false;
    session.account=2; assert(!Eligible(&ai)); session.account=1;
    config.battlegroundTest=false;
    assert(!Eligible(&ai) && BattlegroundTest::GetTargetLevel()==0);
    distribute(); assert(distributionRan);
    config.battlegroundTest=true;
    for (uint32 invalid : {0u,1u,9u,91u,100u,0xffffffffu}) {
        config.randomBotMinLevel=config.randomBotMaxLevel=invalid;
        assert(BattlegroundTest::GetTargetLevel()==0);
    }
    config.randomBotMinLevel=1; config.randomBotMaxLevel=90;
    assert(BattlegroundTest::GetTargetLevel()==0);
    for (uint32 valid : {10u,25u,29u,90u}) {
        config.randomBotMinLevel=config.randomBotMaxLevel=valid;
        assert(BattlegroundTest::GetTargetLevel()==valid);
    }
    distributionRan=false; distribute(); assert(!distributionRan);
    State s;
    uint32 budget=0;
    assert(!RepairQueueReadiness(&p,s,100000,budget));
    assert(p.tags==1 && p.level==25 && p.target==90 && !p.randomizations);
    assert(!RepairQueueReadiness(&p,s,101000,budget)); assert(p.tags==1);
    budget=2; p.flight=true;
    assert(!RepairQueueReadiness(&p,s,102000,budget)); assert(budget==2 && !p.randomizations);
    p.flight=false; p.instance=1;
    assert(!RepairQueueReadiness(&p,s,103000,budget)); assert(budget==2);
    p.instance=0;
    assert(!RepairQueueReadiness(&p,s,104000,budget)); // never join in repair tick
    assert(p.level==90 && p.items==15 && p.randomizations==1 && budget==1);
    assert(RepairQueueReadiness(&p,s,105000,budget)); assert(p.randomizations==1);
    // Discard a stale pending redistribution away from the diagnostic level.
    p.target=25; p.scheduled=true;
    assert(RepairQueueReadiness(&p,s,106000,budget)); assert(p.target==90 && p.tags==2 && p.level==90);
    // Failed preparation respects its cooldown and the shared per-tick budget.
    p.level=25; p.target=25; p.scheduled=false; p.fail=true;
    assert(!RepairQueueReadiness(&p,s,107000,budget)); assert(budget==0 && p.level==25);
    budget=2;
    assert(!RepairQueueReadiness(&p,s,108000,budget)); assert(budget==2);
    p.fail=false;
    assert(!RepairQueueReadiness(&p,s,168000,budget)); assert(p.level==90 && budget==1);
    assert(RepairQueueReadiness(&p,s,169000,budget));
    // Ordinary multi-level test mode does not silently raise levels.
    config.randomBotMinLevel=1; p.level=25; p.target=0; p.scheduled=false;
    auto tags=p.tags;
    assert(RepairQueueReadiness(&p,s,170000,budget)); assert(p.level==25 && p.tags==tags);
}
'''
with tempfile.TemporaryDirectory(prefix='loa-bg-roster-') as directory:
    cpp=Path(directory)/'test.cpp'; binary=Path(directory)/'test'
    cpp.write_text(source)
    subprocess.run([sys.argv[2],'-std=c++20','-O1','-g','-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer',str(cpp),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,env=dict(os.environ,
        ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1'))
print('PASS: fixed BG roster, player exclusion, distribution gate, readiness budget/cooldown and ordinary mode')
