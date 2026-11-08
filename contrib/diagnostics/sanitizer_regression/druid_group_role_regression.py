#!/usr/bin/env python3
"""Exercise real default factory, Engine strategy edits and Druid role transitions.

World/player APIs and strategy payloads are bounded doubles. This verifies
lifecycle/ownership, not native healing effects or an entire BG match.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]
base = root / 'modules/mod_playerbots/src'


def block(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


ai = (base / 'AI/PlayerbotAI.cpp').read_text()
header = (base / 'AI/PlayerbotAI.h').read_text()
engine = (base / 'strategy/Engine.cpp').read_text()
factory = (base / 'Factory/AiFactory.cpp').read_text()
# Wiring matters: objective handling can return before the ordinary Engine.
tick = block(ai, 'void PlayerbotAI::DoNextAction(')
assert tick.index('IsBeingTeleported()') < tick.index('UpdateDefaultDruidGroupRole();') < tick.index('ArathiBasinPlayerbot::DoNextAction(this)')
assert 'RememberDefaultDruidGroupRole();' in ai[ai.index('PlayerbotAI::PlayerbotAI(Player* bot)'):ai.index('PlayerbotAI::~PlayerbotAI()')]
assert 'RememberDefaultDruidGroupRole();' in block(ai, 'void PlayerbotAI::ResetStrategies()')
fields = header[header.index('    bool _automaticDruidRole'):header.index('\nprotected:', header.index('    bool _automaticDruidRole'))]
shared = (root / 'src/server/game/Miscellaneous/SharedDefines.h').read_text()
specs = block(shared, 'enum Specializations\n') + ';\n'
classes = block(shared, 'enum Classes\n') + ';\n'
context = (base / 'strategy/Classes/druid/DruidAiObjectContext.cpp').read_text()
roles = re.findall(r'creators\["([^"]+)"\]', block(context, 'class DruidDruidStrategyFactoryInternal :'))
prefix = r'''
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>
using uint8 = std::uint8_t;
#define TC_LOG_DEBUG(...) ((void)0)
''' + specs + classes + r'''
enum BotState { BOT_STATE_COMBAT, BOT_STATE_NON_COMBAT, BOT_STATE_DEAD, BOT_STATE_MAX };
std::vector<std::string> split(std::string const& s, char delimiter) {
    std::vector<std::string> out; std::stringstream stream(s); std::string item;
    while (std::getline(stream, item, delimiter)) out.push_back(item);
    return out;
}
struct Group {};
struct Guid { unsigned GetCounter() const { return 38; } };
struct Player {
    Group* group = nullptr; bool bg = false, random = true; Specializations spec = SPEC_DRUID_RESTORATION;
    Group* GetGroup() { return group; }
    Specializations const& GetSpecialization() { return spec; }
    bool InBattleground() { return bg; }
    unsigned GetClass() { return CLASS_DRUID; }
    unsigned GetLevel() { return 80; }
    bool HasAura(unsigned) { return false; }
    Guid GetGUID() { return {}; }
};
struct RandomMgr { bool IsRandomBot(Player* p) { return p->random; } } mgr;
auto* sRandomPlayerbotMgr = &mgr;
struct Config { bool autoAvoidAoe = false; std::string combatStrategies; } config;
auto* sPlayerbotAIConfig = &config;
struct PlayerBotSpec {
    static bool IsHeal(Player* p, bool) { return p->spec == SPEC_DRUID_RESTORATION; }
    static bool IsTank(Player*, bool) { return false; }
    static bool IsMelee(Player*, bool) { return false; }
    static bool IsDps(Player*, bool) { return false; }
};
struct Strategy { std::string name; std::string getName() { return name; } };
struct Context {
    std::map<std::string,Strategy> objects;
    Strategy* GetStrategy(std::string name) {
        if (name == "tank") name = "bear";
        if (name == "dps") name = "cat";
        auto& s = objects[name]; s.name = name; return &s;
    }
    std::set<std::string> GetSiblingStrategy(std::string const& name) {
        std::set<std::string> roles = {ROLE_NAMES};
        return roles.count(name) ? roles : std::set<std::string>{};
    }
};
struct PlayerbotAI;
struct Engine {
    Context* aiObjectContext; PlayerbotAI* botAI;
    std::map<std::string,Strategy*> strategies; unsigned initCount = 0;
    void Init() { ++initCount; }
    template<class... T> void LogAction(T...) {}
    void addStrategy(std::string const, bool init = true);
    bool removeStrategy(std::string const, bool init = true);
    void addStrategiesNoInit(std::string, ...);
    void removeAllStrategies();
    void toggleStrategy(std::string const);
    void ChangeStrategy(std::string const);
    std::vector<std::string> GetStrategies();
    bool HasStrategy(std::string const);
    std::string const ListStrategies();
};
struct PlayerbotAI {
    Player* bot; Engine* _engines[BOT_STATE_MAX]; bool real = false, master = false;
    bool IsRealPlayer() { return real; }
    bool HasRealPlayerMaster() { return master; }
    void TellMaster(std::string const&) {}
    void RememberDefaultDruidGroupRole();
    void UpdateDefaultDruidGroupRole();
    void ChangeStrategy(std::string const, BotState);
    void ClearStrategies(BotState);
FIELDS
};
struct AiFactory { static void AddDefaultCombatStrategies(Player*, PlayerbotAI* const, Engine*); };
'''.replace('ROLE_NAMES', ','.join('"'+r+'"' for r in roles)).replace('FIELDS', fields)
methods = '\n'.join(block(ai, s) for s in (
    'void PlayerbotAI::RememberDefaultDruidGroupRole()',
    'void PlayerbotAI::UpdateDefaultDruidGroupRole()',
    'void PlayerbotAI::ChangeStrategy(', 'void PlayerbotAI::ClearStrategies('))
methods += '\n'.join(block(engine, s) for s in (
    'void Engine::addStrategy(', 'bool Engine::removeStrategy(',
    'void Engine::addStrategiesNoInit(', 'void Engine::removeAllStrategies()',
    'void Engine::toggleStrategy(', 'void Engine::ChangeStrategy(',
    'std::vector<std::string> Engine::GetStrategies()', 'bool Engine::HasStrategy(',
    'std::string const Engine::ListStrategies()'))
methods += block(factory, 'void AiFactory::AddDefaultCombatStrategies(')
tests = r'''
struct Fixture {
    Player bot; Context context; Group group;
    PlayerbotAI ai{&bot, {}};
    Engine combat{&context, &ai}, nc{&context, &ai}, dead{&context, &ai};
    Fixture() {
        ai._engines[0]=&combat; ai._engines[1]=&nc; ai._engines[2]=&dead;
        nc.addStrategy("follow"); dead.addStrategy("dead"); reset();
    }
    void reset() {
        combat.removeAllStrategies(); AiFactory::AddDefaultCombatStrategies(&bot,&ai,&combat);
        ai.RememberDefaultDruidGroupRole();
    }
    void join() { bot.group=&group; bot.bg=true; ai.UpdateDefaultDruidGroupRole(); }
    void leave() { bot.group=nullptr; bot.bg=false; ai.UpdateDefaultDruidGroupRole(); }
};
std::set<std::string> unrelated(Engine& engine) {
    auto names=engine.GetStrategies(); std::set<std::string> result(names.begin(),names.end());
    for (auto name : {"caster","heal","caster aoe","caster debuff"}) result.erase(name);
    return result;
}
void expectSolo(Fixture& f) {
    assert(f.combat.HasStrategy("caster") && !f.combat.HasStrategy("heal"));
    assert(f.combat.HasStrategy("caster aoe") && f.combat.HasStrategy("caster debuff"));
}
void expectHealer(Fixture& f) {
    assert(f.combat.HasStrategy("heal") && !f.combat.HasStrategy("caster"));
    assert(!f.combat.HasStrategy("caster aoe") && !f.combat.HasStrategy("caster debuff"));
}
int main() {
    Fixture f; expectSolo(f); auto saved=unrelated(f.combat);
    unsigned n=f.combat.initCount, nc=f.nc.initCount, dead=f.dead.initCount;
    f.join(); expectHealer(f); assert(f.combat.initCount==n+1);
    assert(unrelated(f.combat)==saved && f.nc.initCount==nc && f.dead.initCount==dead);
    f.ai.UpdateDefaultDruidGroupRole(); assert(f.combat.initCount==n+1);
    Group other; f.bot.group=&other; f.ai.UpdateDefaultDruidGroupRole();
    expectHealer(f); assert(f.combat.initCount==n+1); // BG -> original group is still grouped
    f.leave(); expectSolo(f); assert(f.combat.initCount==n+2); assert(unrelated(f.combat)==saved);
    f.join(); expectHealer(f); // a subsequent match also restores healing
    {
        Fixture g; g.bot.group=&g.group; g.reset(); expectHealer(g); g.leave(); expectSolo(g);
    }
    for (auto command : {"+caster", "+cc", "-heal", "~heal"}) {
        Fixture g; g.ai.ChangeStrategy(command, BOT_STATE_COMBAT); auto selected=g.combat.GetStrategies();
        g.join(); assert(g.combat.GetStrategies()==selected); // explicit commands own even identical role
        g.leave(); assert(g.combat.GetStrategies()==selected);
        g.reset(); g.join(); expectHealer(g); // explicit reset re-enables defaults
    }
    {
        Fixture g; g.ai.ChangeStrategy("?", BOT_STATE_COMBAT); g.join(); expectHealer(g);
    }
    {
        Fixture g; g.ai.ChangeStrategy("+stay", BOT_STATE_NON_COMBAT); g.join(); expectHealer(g);
        assert(g.nc.HasStrategy("stay"));
    }
    {
        Fixture g; g.ai.ClearStrategies(BOT_STATE_COMBAT); g.join(); assert(g.combat.GetStrategies().empty());
    }
    {
        Fixture g; g.combat.addStrategy("cc"); auto custom=g.combat.GetStrategies();
        g.join(); assert(g.combat.GetStrategies()==custom);
    }
    for (int mode=0; mode<4; ++mode) {
        Fixture g;
        if (mode==0) g.ai.master=true;
        if (mode==1) g.ai.real=true;
        if (mode==2) g.bot.random=false;
        if (mode==3) g.bot.spec=SPEC_DRUID_BALANCE;
        g.join(); expectSolo(g); assert(!g.ai._automaticDruidRole);
    }
    for (int mode=0; mode<4; ++mode) {
        Fixture g;
        if (mode==0) g.ai.master=true;
        if (mode==1) g.ai.real=true;
        if (mode==2) g.bot.random=false;
        if (mode==3) g.bot.spec=SPEC_DRUID_BALANCE;
        g.reset(); auto before=g.combat.GetStrategies();
        g.join(); assert(g.combat.GetStrategies()==before && !g.ai._automaticDruidRole);
    }
    std::cout << "PASS: solo/group/reentry roles, defaults, manual ownership, master/spec guards\n";
}
'''
with tempfile.TemporaryDirectory(prefix='loa-druid-role-') as temp:
    folder = Path(temp)
    env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1', DEBUGINFOD_URLS='')

    def run(name, body, mutation=False):
        cpp, binary = folder / (name+'.cpp'), folder / name
        cpp.write_text(prefix+body+tests)
        subprocess.run([compiler,'-std=c++20','-g','-O1','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer','-fno-pie','-no-pie',str(cpp),'-o',str(binary)], check=True)
        result = subprocess.run([str(binary)], text=True, capture_output=True, env=env)
        if mutation:
            assert result.returncode != 0 and 'Assertion' in result.stderr, (name, result.stdout, result.stderr)
            print('REJECTED:',name,flush=True)
        else:
            assert result.returncode == 0, result.stderr
            print(result.stdout,end='',flush=True)
    run('baseline',methods)
    if '--verify-mutations' in sys.argv:
        changes = {
            'missing-transition': ('if (!_automaticDruidRole)', 'if (true)'),
            'stale-aoe': ('engine->removeStrategy("caster aoe", false);', ''),
            'stale-debuff': ('engine->removeStrategy("caster debuff", false);', ''),
            'no-healing-role': ('engine->addStrategy("heal", false);', 'engine->addStrategy("caster", false);'),
            'no-solo-return': ('engine->addStrategiesNoInit("caster", "caster aoe", "caster debuff", nullptr);', ';'),
            'no-queue-rebuild': ('    engine->Init();\n', ''),
            'overwrite-direct-edit': ('engine->GetStrategies() != _druidRoleStrategies', 'false'),
            'overwrite-command': ('if (type == BOT_STATE_COMBAT)\n        for', 'if (false)\n        for'),
            'ignore-master': ('if (IsRealPlayer() || HasRealPlayerMaster() ||', 'if (IsRealPlayer() ||'),
            'ignore-respec': ('bot->GetSpecialization() != SPEC_DRUID_RESTORATION)', 'false)'),
        }
        for name,(old,new) in changes.items():
            assert old in methods,name
            run(name,methods.replace(old,new,1),True)
