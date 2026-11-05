#!/usr/bin/env python3
"""Run real script enqueue bodies and record types with a minimal queue consumer.

The consumer models reentrancy/clock/counting, not world-object script effects.
--verify-mutations proves the original borrowed-stack command fails under ASan.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
maps = (root / "src/server/game/Scripting/MapScripts.cpp").read_text()
header = (root / "src/server/game/Maps/Map.h").read_text()
objects = (root / "src/server/game/Globals/ObjectMgr.h").read_text()


def extract(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


source = r'''
#include <cassert>
#include <cstdint>
#include <ctime>
#include <functional>
#include <map>
#include <memory>
#include <string>
#include <vector>
using uint32 = std::uint32_t;
using int32 = std::int32_t;
'''
for signature in ("enum ScriptCommands", "enum ScriptsType", "struct ScriptInfo"):
    source += extract(objects, signature) + ";\n"
source += r'''
struct ObjectGuid {
    uint32 value = 0;
    static ObjectGuid const Empty;
    bool operator==(ObjectGuid const&) const = default;
};
ObjectGuid const ObjectGuid::Empty{};
constexpr int TYPEID_ITEM = 1;
struct Object {
    ObjectGuid guid{42};
    int type = 0;
    ObjectGuid GetGUID() { return guid; }
    int GetTypeId() { return type; }
};
struct Item : Object { ObjectGuid GetOwnerGUID() { return {99}; } };
'''
source += extract(header, "struct ScriptAction\n{") + ";\n"
source += r'''
using ScriptMap = std::multimap<uint32, ScriptInfo>;
using ScriptMapMap = std::map<uint32, ScriptMap>;
struct World {
    time_t now = 100;
    time_t GetGameTime() { return now; }
} world;
World* sWorld = &world;
struct ScriptMgr {
    unsigned scheduled = 0;
    void IncreaseScheduledScriptsCount() { ++scheduled; }
    void DecreaseScheduledScriptCount(unsigned n = 1) {
        assert(scheduled >= n); scheduled -= n;
    }
} manager;
ScriptMgr* sScriptMgr = &manager;
struct Map {
    using ScriptScheduleMap = std::multimap<time_t, ScriptAction>;
    ScriptScheduleMap m_scriptSchedule;
    bool i_scriptLock = false;
    std::vector<ScriptInfo> executed;
    std::function<void()> onExecute;
    ~Map() { sScriptMgr->DecreaseScheduledScriptCount(m_scriptSchedule.size()); }
    void ScriptCommandStart(ScriptInfo const&, uint32, Object*, Object*);
    void ScriptsStart(ScriptMapMap const&, uint32, Object*, Object*);
    void ScriptsProcess() {
        while (!m_scriptSchedule.empty() && m_scriptSchedule.begin()->first <= world.now) {
            auto i = m_scriptSchedule.begin();
            executed.push_back(*i->second.script);
            if (onExecute) { auto callback = std::move(onExecute); onExecute = {}; callback(); }
            m_scriptSchedule.erase(i);
            sScriptMgr->DecreaseScheduledScriptCount();
        }
    }
    void Tick() { i_scriptLock = true; ScriptsProcess(); i_scriptLock = false; }
};
'''
source += extract(maps, "void Map::ScriptsStart(")
enqueue = extract(maps, "void Map::ScriptCommandStart(")
source += enqueue
source += r'''
__attribute__((noinline)) void enqueueLocal(Map& map, uint32 delay, uint32 id = 17) {
    ScriptInfo command{};
    command.command = SCRIPT_COMMAND_ACTIVATE_OBJECT;
    command.id = id;
    command.Raw.nData[0] = 1234;
    command.Raw.fData[3] = 2.5f;
    map.ScriptCommandStart(command, delay, nullptr, nullptr);
}
void check(ScriptInfo const& s, uint32 id) {
    assert(s.command == SCRIPT_COMMAND_ACTIVATE_OBJECT && s.id == id);
    assert(s.Raw.nData[0] == 1234 && s.Raw.fData[3] == 2.5f);
}
int main() {
    {
        Map map;
        // Reproduce zero-delay enqueue while an outer script owns the lock:
        // consumption happens after the producer's stack frame has returned.
        map.i_scriptLock = true;
        enqueueLocal(map, 0);
        assert(map.executed.empty() && manager.scheduled == 1);
        map.Tick();
        check(map.executed.at(0), 17);
        assert(map.m_scriptSchedule.empty() && manager.scheduled == 0);

        enqueueLocal(map, 10, 18);
        map.Tick(); assert(map.executed.size() == 1);
        world.now += 10; map.Tick(); check(map.executed.at(1), 18);
        enqueueLocal(map, 0, 19); // Ordinary immediate path still executes now.
        check(map.executed.at(2), 19);

        // Actual nested production of an immediate and a delayed command.
        map.onExecute = [&] { enqueueLocal(map, 0, 21); enqueueLocal(map, 5, 22); };
        enqueueLocal(map, 0, 20);
        check(map.executed.at(3), 20); check(map.executed.at(4), 21);
        assert(map.executed.size() == 5 && manager.scheduled == 1);
        world.now += 5; map.Tick(); check(map.executed.at(5), 22);
        assert(manager.scheduled == 0);

        // Snapshot preserves the fields and GUIDs even if the caller mutates.
        ScriptInfo command{}; command.command = SCRIPT_COMMAND_ACTIVATE_OBJECT;
        command.id = 23;
        Item item; item.type = TYPEID_ITEM; Object target; target.guid.value = 55;
        map.ScriptCommandStart(command, 10, &item, &target);
        auto& step = map.m_scriptSchedule.begin()->second;
        assert(step.script != &command && step.script == step.ownedScript.get());
        assert(step.sourceGUID == item.guid && step.targetGUID == target.guid);
        assert(step.ownerGUID.value == 99);
        command.id = 999;
        assert(step.script->id == 23);
        std::weak_ptr<ScriptInfo const> lifetime = step.ownedScript;
        {
            ScriptAction copy = step;
            world.now += 10; map.Tick();
            assert(!lifetime.expired() && copy.script->id == 23);
        }
        assert(lifetime.expired());

        // Database commands retain their existing stable, non-owning records.
        ScriptMapMap db;
        command.id = 24;
        db[1].emplace(0, command); db[1].emplace(7, command);
        map.ScriptsStart(db, 1, nullptr, nullptr);
        assert(map.executed.back().id == 24 && manager.scheduled == 1);
        auto const& dbStep = map.m_scriptSchedule.begin()->second;
        assert(!dbStep.ownedScript && dbStep.script == &db[1].find(7)->second);
        world.now += 7; map.Tick();
        assert(manager.scheduled == 0);
        map.ScriptsStart(db, 999, nullptr, nullptr);
        assert(manager.scheduled == 0);
    }
    // Destruction with pending commands releases snapshots (LSan checks leaks).
    std::weak_ptr<ScriptInfo const> pending;
    {
        Map map; enqueueLocal(map, 100);
        pending = map.m_scriptSchedule.begin()->second.ownedScript;
        assert(!pending.expired() && manager.scheduled == 1);
    }
    assert(pending.expired() && manager.scheduled == 0);
}
'''

effects = (root / "src/server/game/Spells/SpellEffects.cpp").read_text()
assert "ScriptInfo activateCommand{};" in extract(effects, "void Spell::EffectActivateObject(")
env = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1:detect_stack_use_after_return=1",
           UBSAN_OPTIONS="halt_on_error=1")
with tempfile.TemporaryDirectory(prefix="loa-script-command-ownership-") as directory:
    directory = Path(directory)

    def run(name, code):
        cpp, exe = directory / (name + ".cpp"), directory / name
        cpp.write_text(code)
        subprocess.run([sys.argv[2], "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                        "-fno-omit-frame-pointer", str(cpp), "-o", str(exe)], check=True)
        return subprocess.run([str(exe)], env=env, capture_output=True, text=True)

    result = run("fixed", source)
    assert result.returncode == 0, result.stdout + result.stderr
    if "--verify-mutations" in sys.argv:
        owned = "sa.ownedScript = std::make_shared<ScriptInfo const>(script);\n    sa.script = sa.ownedScript.get();"
        assert owned in enqueue
        mutant = source.replace(owned, "sa.script = &script;", 1)
        result = run("borrowed-stack-mutant", mutant)
        assert result.returncode != 0 and "stack-use-after-return" in result.stderr, result.stderr
        print("Original borrowed-stack mutation rejected by ASan: stack-use-after-return")
print("Script command queue ownership regression passed")
