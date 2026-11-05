#!/usr/bin/env python3
"""Check remaining r6 leaks with actual method bodies and small doubles."""

import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]


def body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


registrations = {
    "Spells/spell_mage.cpp": ("spell_mage_evocation", "aura_script"),
    "Spells/spell_paladin.cpp": ("spell_pal_avenging_wrath", "aura_script"),
    "Spells/spell_priest.cpp": ("spell_pri_devouring_plague", "spell_script"),
    "Spells/spell_warlock.cpp": ("spell_warl_soul_link", "aura_script"),
    "Pandaria/HeartOfFear/boss_unsok.cpp": (
        "spell_unsok_reshape_of_life",
        "aura_script",
    ),
}
for relative, (name, wrapper) in registrations.items():
    text = (root / "src/server/scripts" / relative).read_text()
    assert not re.search(r"new\s+" + name + r"\s*\(\s*\)\s*;", text), name
    assert text.count(f'new {wrapper}<{name}>("{name}")') == 1, name
paladin = (root / "src/server/scripts/Spells/spell_paladin.cpp").read_text()
archimonde = (
    root
    / "src/server/scripts/Kalimdor/CavernsOfTime/BattleForMountHyjal/boss_archimonde.cpp"
).read_text()
assert not re.search(
    r"new\s+(?:aura_script<)?spell_protection_of_elune\b",
    body(archimonde, "void AddSC_boss_archimonde()"),
), "Do not reactivate an archived legacy script"
name = "spell_pal_glyph_of_double_jeopardy_judgment"
assert not re.search(r"new\s+" + name + r"\s*\(\s*\)\s*;", paladin)
assert paladin.count(f'new spell_script<{name}>("{name}")') == 1

maps = (root / "src/server/game/Maps/Map.cpp").read_text()
destructor = body(maps, "Map::~Map()")
assert destructor.index("UnloadCorpseData();") < destructor.index("UnloadAll();")
cleanup = body(maps, "void Map::UnloadCorpseData()")
assert "Database" not in cleanup and "DeleteFromDB" not in cleanup
target = body(
    (root / "src/server/game/AI/SmartScripts/SmartScript.cpp").read_text(),
    "std::unique_ptr<ObjectList> SmartScript::GetTargetList(",
)

source = (
    r"""
#include <cassert>
#include <cstdint>
#include <list>
#include <map>
#include <memory>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <type_traits>
using uint32 = std::uint32_t;
using ObjectGuid = uint32;
constexpr int CORPSE_BONES = 0;
int liveCorpses = 0;
struct Corpse {
    ObjectGuid owner;
    int type;
    bool inGrid;
    bool detached = false;
    Corpse(ObjectGuid owner, int type, bool inGrid) : owner(owner), type(type), inGrid(inGrid) { ++liveCorpses; }
    ~Corpse() { assert(detached); --liveCorpses; }
    void DestroyForNearbyPlayers() {}
    bool IsInGrid() const { return inGrid; }
    void RemoveFromWorld() { detached = true; }
    void ResetMap() { detached = true; }
    int GetType() const { return type; }
    ObjectGuid GetOwnerGUID() const { return owner; }
    struct Cell { uint32 GetId() const { return 1; } };
    Cell GetCellCoord() const { return {}; }
};
struct Map {
    std::unordered_map<uint32, std::unordered_set<Corpse*>> _corpsesByCell;
    std::unordered_map<ObjectGuid, Corpse*> _corpsesByPlayer;
    std::unordered_set<Corpse*> _corpseBones;
    ~Map() { UnloadCorpseData(); }
    void RemoveFromMap(Corpse* corpse, bool deleting) {
        assert(!deleting); corpse->inGrid = false; corpse->RemoveFromWorld(); corpse->ResetMap();
    }
    void RemoveCorpse(Corpse* corpse);
    void UnloadCorpseData();
};
#define ASSERT(x) assert(x)
"""
    + body(maps, "void Map::RemoveCorpse(")
    + "\n"
    + cleanup
    + r"""
struct WorldObject { uint32 id; };
using GuidList = std::list<ObjectGuid>;
using ObjectList = std::list<WorldObject*>;
std::map<ObjectGuid, WorldObject*> worldObjects;
struct ObjectAccessor {
    static WorldObject* GetWorldObject(WorldObject const&, ObjectGuid guid) {
        auto it = worldObjects.find(guid);
        return it == worldObjects.end() ? nullptr : it->second;
    }
};
constexpr int SMART_SCRIPT_TYPE_AREATRIGGER = 1;
struct SmartScript {
    WorldObject const* base = nullptr;
    int mScriptType = 0;
    std::map<uint32, GuidList> storage;
    std::map<uint32, GuidList>* mTargetStorage = &storage;
    WorldObject const* GetBaseObject() const { return base; }
    std::unique_ptr<ObjectList> GetTargetList(uint32 id, WorldObject const* scriptTrigger = nullptr);
};
"""
    + target
    + r"""
int main() {
    for (int cycle = 0; cycle < 1000; ++cycle) {
        { Map map;
          // Player corpses and bones, in loaded and never-loaded grids.
          for (uint32 id = 1; id <= 4; ++id) {
              auto corpse = new Corpse(id, id <= 2 ? 1 : CORPSE_BONES, id % 2 == 0);
              map._corpsesByCell[1].insert(corpse);
              if (corpse->type == CORPSE_BONES) map._corpseBones.insert(corpse);
              else map._corpsesByPlayer[id] = corpse;
          }
          map.UnloadCorpseData(); map.UnloadCorpseData();
          assert(liveCorpses == 0 && map._corpsesByCell.empty());
          auto corpse = new Corpse(5, 1, false);
          map._corpsesByPlayer[5] = corpse; map._corpsesByCell[1].insert(corpse);
        }
        assert(liveCorpses == 0);
        WorldObject base{10}, first{2}, second{4};
        worldObjects = {{2, &first}, {4, &second}};
        SmartScript script;
        script.storage[1] = {2, 3, 4}; // GUID 3 no longer resolves.
        assert(!script.GetTargetList(1));
        script.base = &base;
        assert(!script.GetTargetList(2));
        script.storage[2] = {};
        auto empty = script.GetTargetList(2); assert(empty && empty->empty());
        { auto targets = script.GetTargetList(1);
          static_assert(std::is_same_v<decltype(targets), std::unique_ptr<ObjectList>>);
          assert(targets->size() == 2 && targets->front() == &first && targets->back() == &second);
        }
        // Early-return caller: the temporary list must be destroyed as well.
        auto hasTarget = [&] { auto targets = script.GetTargetList(1); return targets && !targets->empty(); };
        assert(hasTarget());
        script.base = nullptr; script.mScriptType = SMART_SCRIPT_TYPE_AREATRIGGER;
        assert(script.GetTargetList(1, &base)->size() == 2);
        assert(first.id == 2 && second.id == 4); // Borrowed objects were not deleted.
    }
}
"""
)
with tempfile.TemporaryDirectory(prefix="loa-cleanup-regression-") as directory:
    cpp = pathlib.Path(directory) / "cleanup.cpp"
    executable = pathlib.Path(directory) / "cleanup"
    cpp.write_text(source)
    subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(cpp),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
print("Corpse, SmartAI target and spell registration regression passed")
