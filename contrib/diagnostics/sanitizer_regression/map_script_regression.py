#!/usr/bin/env python3
"""Exercise actual ScriptMgr map dispatch with polymorphic map/registry doubles."""

import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]
script = (root / "src/server/game/Scripting/ScriptMgr.cpp").read_text()
dispatch = script[script.index("#define SCR_MAP_BGN") : script.index("#undef SCR_MAP_END")]
source = r'''
#include <cassert>
#include <cstdint>
#include <map>
using uint32 = std::uint32_t;
#define ASSERT assert
struct MapEntry {
    uint32 MapID;
    int kind;
    bool IsWorldMap() const { return kind == 0; }
    bool IsDungeon() const { return kind == 1; }
    bool IsBattleground() const { return kind == 2; }
};
struct Map {
    MapEntry entry;
    explicit Map(int kind): entry{uint32(kind), kind} {}
    virtual ~Map() = default;
    MapEntry const* GetEntry() const { return &entry; }
    uint32 GetId() const { return entry.MapID; }
};
struct MapInstanced : Map { explicit MapInstanced(int kind): Map(kind) {} };
struct InstanceMap : Map { InstanceMap(): Map(1) {} };
struct BattlegroundMap : Map { BattlegroundMap(): Map(2) {} };
struct GridMap {};
struct Player {};
template<class T> struct RecordingScript {
    MapEntry entry;
    int calls[7]{};
    T* last = nullptr;
    explicit RecordingScript(int kind): entry{uint32(kind), kind} {}
    MapEntry const* GetEntry() const { return &entry; }
    void OnCreate(T* m) { ++calls[0]; last = m; }
    void OnDestroy(T* m) { ++calls[1]; last = m; }
    void OnLoadGridMap(T* m, GridMap*, uint32, uint32) { ++calls[2]; last = m; }
    void OnUnloadGridMap(T* m, GridMap*, uint32, uint32) { ++calls[3]; last = m; }
    void OnPlayerEnter(T* m, Player*) { ++calls[4]; last = m; }
    void OnPlayerLeave(T* m, Player*) { ++calls[5]; last = m; }
    void OnUpdate(T* m, uint32) { ++calls[6]; last = m; }
};
using WorldMapScript = RecordingScript<Map>;
using InstanceMapScript = RecordingScript<InstanceMap>;
using BattlegroundMapScript = RecordingScript<BattlegroundMap>;
template<class T> std::map<int, T*> registry;
#define FOR_SCRIPTS(M, I, E) for (auto I = registry<M>.begin(), E = registry<M>.end(); I != E; ++I)
struct PlayerScript { void OnMapChanged(Player*) {} };
PlayerScript playerScript;
#define FOREACH_SCRIPT(M) (&playerScript)
struct ScriptMgr {
    void OnCreateMap(Map*);
    void OnDestroyMap(Map*);
    void OnLoadGridMap(Map*, GridMap*, uint32, uint32);
    void OnUnloadGridMap(Map*, GridMap*, uint32, uint32);
    void OnPlayerEnterMap(Map*, Player*);
    void OnPlayerLeaveMap(Map*, Player*);
    void OnMapUpdate(Map*, uint32);
};
'''
source += dispatch + r'''
void exercise(ScriptMgr& mgr, Map* map) {
    Player player; GridMap grid;
    mgr.OnCreateMap(map); mgr.OnDestroyMap(map);
    mgr.OnLoadGridMap(map, &grid, 0, 0); mgr.OnUnloadGridMap(map, &grid, 0, 0);
    mgr.OnPlayerEnterMap(map, &player); mgr.OnPlayerLeaveMap(map, &player);
    mgr.OnMapUpdate(map, 1);
}
int main() {
    ScriptMgr mgr;
    WorldMapScript world(0); InstanceMapScript instance(1); BattlegroundMapScript bg(2);
    registry<WorldMapScript>[0] = &world;
    registry<InstanceMapScript>[1] = &instance;
    registry<BattlegroundMapScript>[2] = &bg;
    // A DBC dungeon flag does not make either base or container an InstanceMap.
    Map baseDungeon(1), baseBg(2);
    MapInstanced dungeonContainer(1), bgContainer(2);
    exercise(mgr, &baseDungeon); exercise(mgr, &baseBg);
    exercise(mgr, &dungeonContainer); exercise(mgr, &bgContainer);
    for (int i = 0; i < 7; ++i) assert(!instance.calls[i] && !bg.calls[i]);
    Map continent(0); InstanceMap copy; BattlegroundMap arena;
    exercise(mgr, &continent); exercise(mgr, &copy); exercise(mgr, &arena);
    for (int i = 0; i < 7; ++i)
        assert(world.calls[i] == 1 && instance.calls[i] == 1 && bg.calls[i] == 1);
    assert(world.last == &continent && instance.last == &copy && bg.last == &arena);
    // Null/unknown script map entries remain ignored.
    registry<InstanceMapScript>.clear(); exercise(mgr, &copy);
    for (int i = 0; i < 7; ++i) assert(instance.calls[i] == 1);
}
'''
with tempfile.TemporaryDirectory(prefix="loa-map-script-regression-") as directory:
    cpp = pathlib.Path(directory) / "regression.cpp"
    executable = pathlib.Path(directory) / "regression"
    cpp.write_text(source)
    subprocess.run(
        [compiler, "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
         "-fno-omit-frame-pointer", str(cpp), "-o", str(executable)], check=True
    )
    subprocess.run([str(executable)], check=True)

# Check the real lifecycle placement as well as isolated dispatcher behavior.
maps = (root / "src/server/game/Maps/Map.cpp").read_text()
for type_name in ("InstanceMap", "BattlegroundMap"):
    start = maps.index(type_name + "::" + type_name + "(")
    end = maps.index(type_name + "::~" + type_name + "()", start)
    assert maps[start:end].count("sScriptMgr->OnCreateMap(this);") == 1
    body = maps[end:maps.index("\n}", end)]
    assert body.count("sScriptMgr->OnDestroyMap(this);") == 1
    if type_name == "InstanceMap":
        assert body.index("OnDestroyMap") < body.index("delete i_data")
base_ctor = maps[maps.index("Map::Map("):maps.index("void Map::InitVisibilityDistance()")]
base_dtor = maps[maps.index("Map::~Map()"):maps.index("void Map::", maps.index("Map::~Map()"))]
for body in (base_ctor, base_dtor):
    assert "if (!Instanceable())\n        sScriptMgr->" in body
print("Map script dispatch and lifecycle placement checks passed")
