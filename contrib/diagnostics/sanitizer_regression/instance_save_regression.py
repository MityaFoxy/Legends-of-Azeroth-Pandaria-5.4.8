#!/usr/bin/env python3
"""Exercise real InstanceSave cleanup and Main.cpp guards with subsystem doubles.

The doubles model session/map/group lifetimes, not dungeon gameplay or SQL.
Mutations prove the missing shutdown owner leaks and repeated cleanup is safe.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
compiler = sys.argv[2]
header = (root / "src/server/game/Instances/InstanceSaveMgr.h").read_text()
implementation = (root / "src/server/game/Instances/InstanceSaveMgr.cpp").read_text()
main = (root / "src/server/worldserver/Main.cpp").read_text()


def extract(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


guard_names = ("sScriptMgrHandle", "instanceSaveMgrHandle", "mapManagementHandle",
               "battlegroundMgrHandle", "sWorldSocketMgrHandle")
guards = []
for name in guard_names:
    match = re.search(r"    auto " + name + r" = .*", main)
    assert match, "Missing shutdown guard: " + name
    guards.append((match.start(), extract(main, match.group()) + ");"))
guards.sort()
guard_source = "\n".join(guard for _, guard in guards)

source = r'''
#include <cassert>
#include <cstdint>
#include <ctime>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#define ASSERT assert
using uint8 = std::uint8_t;
using uint16 = std::uint16_t;
using uint32 = std::uint32_t;
enum Difficulty { NORMAL };
struct InstanceTemplate;
struct MapEntry;
class Player;
class Group;
'''
source += extract(header, "class InstanceSave\n{") + ";\n"
source += r'''
struct Map {
    bool players = false;
    bool HavePlayers() const { return players; }
};
struct MapManager {
    std::map<uint32, Map> maps;
    Map* FindMap(uint32, uint32 id) {
        auto it = maps.find(id);
        return it == maps.end() ? nullptr : &it->second;
    }
    void UnloadAll();
} mapManager;
MapManager* sMapMgr = &mapManager;
std::vector<std::string> events;
class InstanceSaveManager {
public:
    using InstanceSaveHashMap = std::unordered_map<uint32, InstanceSave*>;
    InstanceSaveHashMap m_instanceSaveById;
    bool lock_instLists = false;
    InstanceSave* GetInstanceSave(uint32);
    void RemoveInstanceSave(uint32);
    void Unload();
};
InstanceSaveManager manager;
InstanceSaveManager* sInstanceSaveMgr = &manager;
struct CharacterDatabasePreparedStatement {
    void setUInt32(uint32, uint32) {}
};
constexpr int CHAR_UPD_INSTANCE_RESETTIME = 0;
struct Database {
    int resetUpdates = 0;
    CharacterDatabasePreparedStatement statement;
    CharacterDatabasePreparedStatement* GetPreparedStatement(int) { return &statement; }
    void Execute(CharacterDatabasePreparedStatement*) { ++resetUpdates; }
} CharacterDatabase;
class Player {
public:
    std::map<uint32, InstanceSave*> binds;
    int unbound = 0;
    void Bind(InstanceSave* save) { binds[save->GetMapId()] = save; save->AddPlayer(this); }
    void UnbindInstance(uint32 map, Difficulty, bool unload) {
        assert(unload);
        auto it = binds.find(map);
        assert(it != binds.end());
        it->second->RemovePlayer(this);
        binds.erase(it);
        ++unbound;
    }
};
class Group {
public:
    std::map<uint32, InstanceSave*> binds;
    int unbound = 0;
    void Bind(InstanceSave* save) { binds[save->GetMapId()] = save; save->AddGroup(this); }
    void UnbindInstance(uint32 map, Difficulty, bool unload) {
        assert(unload);
        auto it = binds.find(map);
        assert(it != binds.end());
        it->second->RemoveGroup(this);
        binds.erase(it);
        ++unbound;
    }
};
'''
for signature in ("InstanceSave::InstanceSave(", "InstanceSave::~InstanceSave()",
                  "bool InstanceSave::UnloadIfEmpty()",
                  "InstanceSave* InstanceSaveManager::GetInstanceSave(",
                  "void InstanceSaveManager::RemoveInstanceSave(",
                  "void InstanceSaveManager::Unload()"):
    source += extract(implementation, signature) + "\n"
source += r'''
time_t InstanceSave::GetResetTimeForDB() { return m_resetTime; }
InstanceSave* Add(uint32 id) {
    auto* save = new InstanceSave(33, id, NORMAL, 1234, true);
    assert(manager.m_instanceSaveById.emplace(id, save).second);
    return save;
}
void MapManager::UnloadAll() {
    assert(!maps.empty());
    assert(manager.GetInstanceSave(1)); // Map teardown can still consult the save.
    events.push_back("maps");
    maps.clear();
}
struct ScriptMgr {
    void Unload() {
        assert(manager.m_instanceSaveById.empty());
        events.push_back("scripts");
    }
} scripts;
ScriptMgr* sScriptMgr = &scripts;
struct BattlegroundMgr {
    void DeleteAllBattlegrounds() { events.push_back("battlegrounds"); }
} battlegrounds;
BattlegroundMgr* sBattlegroundMgr = &battlegrounds;
struct World {
    void KickAll() { events.push_back("sessions"); }
    void UpdateSessions(int) {}
} world;
World* sWorld = &world;
struct WorldSocketMgr { void StopNetwork() {} } sWorldSocketMgr;
void ClearOnlineAccounts() {}
namespace Trinity {
template<class T, class D> auto make_unique_ptr_with_deleter(T* ptr, D deleter) {
    return std::unique_ptr<T, D>(ptr, deleter);
}
}
void ShutdownGuards() {
'''
source += guard_source
source += r'''
}
int main(int argc, char**) {
    // A save can outlive the last binding while a player remains in its map.
    Player player;
    auto* save = Add(1);
    sMapMgr->maps[1].players = true;
    player.Bind(save);
    player.UnbindInstance(33, NORMAL, true);
    assert(manager.GetInstanceSave(1) == save);
    assert(CharacterDatabase.resetUpdates == 0);
    sMapMgr->maps[1].players = false;

    // Simulate ordered stack unwinding in Main.cpp, including early returns.
    ShutdownGuards();
    assert(manager.m_instanceSaveById.empty());
    assert((events == std::vector<std::string>{"sessions", "battlegrounds", "maps", "scripts"}));
    manager.Unload(); // Must be safe after cleanup has already run.

    // Forced cleanup must detach all links without deleting during iteration.
    Player p1, p2;
    Group g1, g2;
    save = Add(2);
    p1.Bind(save); p2.Bind(save); g1.Bind(save); g2.Bind(save);
    Add(3); // Empty save without a live map is still owned by the manager.
    manager.Unload();
    assert(p1.binds.empty() && p2.binds.empty() && g1.binds.empty() && g2.binds.empty());
    assert(p1.unbound == 1 && p2.unbound == 1 && g1.unbound == 1 && g2.unbound == 1);
    assert(manager.m_instanceSaveById.empty());
    assert(CharacterDatabase.resetUpdates == 0); // Shutdown must not delete persistent binds.
    manager.Unload();

    // Ordinary final player/group removal still releases exactly once.
    save = Add(4);
    p1.Bind(save); g1.Bind(save);
    p1.UnbindInstance(33, NORMAL, true);
    assert(manager.GetInstanceSave(4) == save);
    g1.UnbindInstance(33, NORMAL, true);
    assert(!manager.GetInstanceSave(4));
    save = Add(5);
    p1.Bind(save);
    p1.UnbindInstance(33, NORMAL, true);
    assert(!manager.GetInstanceSave(5));
    assert(CharacterDatabase.resetUpdates == 2);
    manager.Unload();
}
'''

environment = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1",
                   UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
with tempfile.TemporaryDirectory(prefix="loa-instance-save-") as temporary:
    binary = str(Path(temporary) / "regression")

    def run(code):
        subprocess.run([compiler, "-std=c++20", "-O1", "-g", "-no-pie",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-x", "c++", "-", "-o", binary], input=code, text=True, check=True)
        return subprocess.run([binary], text=True, capture_output=True, env=environment)

    result = run(source)
    assert result.returncode == 0, result.stdout + result.stderr
    print("InstanceSave lifecycle and shutdown guards: passed under ASan/UBSan/LSan")
    if "--verify-mutations" in sys.argv:
        # Reproduce the original missing owner without an earlier assertion hiding LSan.
        no_owner = source.replace(next(g for _, g in guards if "instanceSaveMgrHandle" in g), "")
        no_owner = no_owner.replace("assert(manager.m_instanceSaveById.empty());", "")
        no_owner = no_owner.replace("    manager.Unload(); // Must be safe after cleanup has already run.",
                                    "    manager.m_instanceSaveById.clear(); return 0;")
        result = run(no_owner)
        assert result.returncode != 0 and "LeakSanitizer" in result.stderr, result.stderr
        print("Missing shutdown guard: original leak reproduced by LSan")
        no_clear = source.replace("    m_instanceSaveById.clear();", "")
        no_clear = no_clear.replace("assert(manager.m_instanceSaveById.empty());", "")
        result = run(no_clear)
        assert result.returncode != 0 and "heap-use-after-free" in result.stderr, result.stderr
        print("Missing registry clear: repeated unload rejected by ASan")
