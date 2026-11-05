#!/usr/bin/env python3
"""Compile actual project method/template bodies with small subsystem doubles.

This checks the repaired lifecycle and value logic without linking the complete
world server. Full-server startup/shutdown remains a separate acceptance gate.
"""

import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]
baseline = "--baseline" in sys.argv[3:]


def read(relative):
    if baseline:
        return subprocess.check_output(
            [
                "git",
                "-c",
                "safe.directory=" + str(root),
                "-C",
                str(root),
                "show",
                "HEAD:" + relative,
            ],
            text=True,
        )
    return (root / relative).read_text()


def method(source, signature):
    begin = source.index(signature)
    brace = source.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


values = read("modules/mod_playerbots/src/strategy/Value.h")
calculated = values[
    values.index("class UntypedValue") : values.index(
        "template <class T>\nclass SingleCalculatedValue"
    )
]
memory_begin = values.index("class MemoryCalculatedValue")
memory_begin = values.rfind("template <class T>", 0, memory_begin)
memory_end = values.index("class LogCalculatedValue")
memory_end = values.rfind("template <class T>", 0, memory_end)
memory = values[memory_begin:memory_end]
queue = read("src/server/game/Battlegrounds/BattlegroundQueue.h")
declaration = re.search(r"(?:virtual\s+)?~BattlegroundQueue\(\);", queue).group()
factory = read("modules/mod_playerbots/src/Factory/RandomPlayerbotFactory.cpp")
cache = re.search(r"std::unordered_map<[^\n;]+> nameCache;", factory).group()
destructor = method(
    read("src/server/game/Entities/Object/Object.cpp"), "WorldObject::~WorldObject()"
)
holiday = method(
    read("src/server/game/Battlegrounds/BattlegroundMgr.cpp"),
    "void BattlegroundMgr::SetHolidayWeekends(uint32 mask)",
)

source = (
    r"""
#include <cassert>
#include <cstdint>
#include <ctime>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>
#include <type_traits>
#include "BitMask.h"
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using int32 = std::int32_t;
enum Gender { GENDER_MALE = 0, GENDER_FEMALE = 1, GENDER_NONE = 2, GENDER_BOTH = 3 };
uint32 getMSTime() { return 1000; }
class PlayerbotAI {};
struct AiNamedObject {
    AiNamedObject(PlayerbotAI*, std::string const&) {}
    virtual ~AiNamedObject() = default;
};
"""
    + calculated
    + memory
    + r"""
struct CombatValue : MemoryCalculatedValue<bool> {
    CombatValue() : MemoryCalculatedValue(nullptr) {}
    bool current = false;
    bool Calculate() override { return current; }
    bool EqualToLast(bool v) override { return v == lastValue; }
    bool Last() const { return lastValue; }
};
struct BattlegroundQueue {
"""
    + declaration
    + r"""
};
BattlegroundQueue::~BattlegroundQueue() = default;
bool soloDestroyed = false;
struct SoloQueue : BattlegroundQueue {
    std::vector<int> state = std::vector<int>(20, 1);
    ~SoloQueue() { soloDestroyed = true; }
};
static_assert(std::has_virtual_destructor_v<BattlegroundQueue>);
struct WorldObject;
struct Map {
    WorldObject* registered = nullptr;
    void RemoveWorldObject(WorldObject* p) {
        if (registered == p) registered = nullptr;
    }
};
constexpr int TYPEID_CORPSE = 7;
constexpr int TYPEID_UNIT = 3;
struct Creature;
struct Guid { std::uint64_t GetRawValue() const { return 1; } };
struct WorldObject {
    bool m_isWorldObject = false;
    Map* m_currMap = nullptr;
    int type = TYPEID_UNIT;
    virtual ~WorldObject();
    Creature const* ToCreature() const;
    bool IsWorldObject() const;
    int GetTypeId() const { return type; }
    Guid GetGUID() const { return {}; }
    int GetEntry() const { return 1; }
    void ResetMap() { if (IsWorldObject()) m_currMap->RemoveWorldObject(this); m_currMap = nullptr; }
};
struct Creature : WorldObject { bool m_isTempWorldObject = false; };
Creature const* WorldObject::ToCreature() const {
    return type == TYPEID_UNIT ? reinterpret_cast<Creature const*>(this) : nullptr;
}
bool WorldObject::IsWorldObject() const {
    return m_isWorldObject || (ToCreature() && ToCreature()->m_isTempWorldObject);
}
#define ASSERT(x) assert(x)
#define TC_LOG_FATAL(...) ((void)0)
"""
    + destructor
    + r"""
using BattlegroundTypeId = uint32;
constexpr uint32 MAX_BATTLEGROUND_TYPE_ID = 35;
struct Battleground { bool holiday = true; void SetHoliday(bool v) { holiday = v; } };
struct BattlegroundMgr {
    Battleground bgs[MAX_BATTLEGROUND_TYPE_ID];
    Battleground* GetBattlegroundTemplate(BattlegroundTypeId id) { return &bgs[id]; }
    void SetHolidayWeekends(uint32 mask);
};
"""
    + holiday
    + r"""
int main() {
    { std::unique_ptr<BattlegroundQueue> q = std::make_unique<SoloQueue>(); }
    assert(soloDestroyed);
    CombatValue combat;
    assert(!combat.LazyGet() && !combat.Last());
    assert(!combat.Get());
    combat.current = true;
    assert(combat.Get() && combat.Last());
    combat.Set(false);
    assert(!combat.LazyGet() && !combat.Last());
    Map map;
    { auto c = std::make_unique<Creature>(); c->m_currMap = &map; }
    { auto c = std::make_unique<Creature>(); c->m_currMap = &map;
      c->m_isTempWorldObject = true; map.registered = c.get(); }
    assert(!map.registered);
    { auto c = std::make_unique<Creature>(); c->m_currMap = &map;
      c->m_isWorldObject = true; map.registered = c.get(); }
    assert(!map.registered);
    BattlegroundMgr mgr;
    mgr.SetHolidayWeekends((uint32(1) << 31) | (uint32(1) << 1));
    for (uint32 i = 1; i < MAX_BATTLEGROUND_TYPE_ID; ++i)
        assert(mgr.bgs[i].holiday == (i == 1 || i == 31));
    mgr.SetHolidayWeekends(0);
    for (uint32 i = 1; i < MAX_BATTLEGROUND_TYPE_ID; ++i) assert(!mgr.bgs[i].holiday);
"""
    + cache
    + r"""
    using NameCategory = decltype(nameCache)::key_type;
    nameCache[NameCategory(0)].push_back("male"); nameCache[NameCategory(1)].push_back("female");
    nameCache[NameCategory(14)].push_back("category14");
    assert(nameCache.size() == 3 && nameCache[NameCategory(14)][0] == "category14");
}
"""
)

with tempfile.TemporaryDirectory(prefix="loa-lifecycle-regression-") as temporary:
    binary = pathlib.Path(temporary) / "regression"
    subprocess.run(
        [
            compiler,
            "-x",
            "c++",
            "-std=c++20",
            "-g",
            "-O1",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-I",
            str(root / "src/common/Utilities"),
            "-",
            "-o",
            str(binary),
        ],
        input=source,
        text=True,
        check=True,
    )
    subprocess.run([str(binary)], check=True)
print("Actual lifecycle/value/holiday/cache regression bodies: PASS")
