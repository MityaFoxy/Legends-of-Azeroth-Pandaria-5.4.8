#!/usr/bin/env python3
"""Check transmitted-object registration and actual Unit cleanup under sanitizers."""

import pathlib
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


effects = (root / "src/server/game/Spells/SpellEffects.cpp").read_text()
units = (root / "src/server/game/Entities/Unit/Unit.cpp").read_text()
transmitted = body(effects, "void Spell::EffectTransmitted(")
tail = transmitted[transmitted.index("    switch (goinfo->type)") :]
source = (
    r"""
#include <cassert>
#include <cstdint>
#include <list>
#include <vector>
using uint32 = std::uint32_t;
using int32 = std::int32_t;
struct ObjectGuid { static constexpr uint32 Empty = 0; };
enum { TYPEID_PLAYER, TYPEID_UNIT, GAMEOBJECT_TYPE_FISHINGNODE,
       GAMEOBJECT_TYPE_SUMMONING_RITUAL, GAMEOBJECT_TYPE_DUEL_ARBITER,
       GAMEOBJECT_TYPE_FISHINGHOLE, GAMEOBJECT_TYPE_CHEST, GAMEOBJECT_TYPE_GENERIC };
constexpr int UNIT_FIELD_CHANNEL_OBJECT = 0, IN_MILLISECONDS = 1000,
              FISHING_BOBBER_READY_TIME = 5, GO_STATE_READY = 0;
enum class HighGuid { GameObject };
int urand(int, int) { return 0; }
#define TC_LOG_DEBUG(...) ((void)0)
int liveObjects = 0, cooldownHolds = 0;
struct SpellInfo {
    uint32 Id = 46905;
    bool IsCooldownStartedOnEvent() const { return true; }
};
struct SpellMgr { SpellInfo info; SpellInfo const* GetSpellInfo(uint32) { return &info; } } spellMgr;
auto sSpellMgr = &spellMgr;
struct SpellHistory { void SetCooldownOnHold(SpellInfo const*, int) { ++cooldownHolds; } };
struct GameObjectTemplate {
    int type = GAMEOBJECT_TYPE_GENERIC;
    uint32 linked = 0;
    uint32 GetLinkedGameObjectEntry() const { return linked; }
};
struct Map;
struct GameObject {
    uint32 owner = 0, spell = 0, guid = 0, respawn = 0;
    bool removed = false;
    Map* map = nullptr;
    GameObjectTemplate info;
    GameObject() { ++liveObjects; }
    ~GameObject() { --liveObjects; }
    bool Create(uint32, uint32, Map*, int, float, float, float, float,
                std::initializer_list<int>, int, int);
    uint32 GetOwnerGUID() const { return owner; }
    void SetOwnerGUID(uint32 value) { owner = value; }
    uint32 GetGUID() const { return guid; }
    uint32 GetSpellId() const { return spell; }
    void SetSpellId(uint32 value) { spell = value; }
    void SetRespawnTime(uint32 value) { respawn = value; }
    void AddToTransportIfNeeded(int) {}
    void SetPhased(int, bool, bool) {}
    template<class T> void AddUniqueUse(T*) {}
    GameObjectTemplate const* GetGOInfo() const { return &info; }
    Map* GetMap() { return map; }
    void Delete() { assert(!owner && !removed); removed = true; }
};
struct Map {
    std::vector<GameObject*> objects;
    bool failLinked = false;
    template<HighGuid> uint32 GenerateLowGuid() { return 2; }
    void AddToMap(GameObject* go) { assert(go->owner == 42); objects.push_back(go); }
    ~Map() { for (auto go : objects) delete go; }
};
bool GameObject::Create(uint32 id, uint32, Map* m, int, float, float, float,
                        float, std::initializer_list<int>, int, int) {
    map = m; guid = id; return !m->failLinked;
}
using GameObjectList = std::list<GameObject*>;
struct Unit {
    GameObjectList m_gameObj;
    int type;
    uint32 channel = 0;
    SpellHistory history;
    uint32 GetGUID() const { return 42; }
    int GetTypeId() const { return type; }
    Unit* ToPlayer() { return this; }
    SpellHistory* GetSpellHistory() { return &history; }
    void SetUInt64Value(int, uint32 value) { channel = value; }
    int GetTransport() { return 0; }
    int GetPhaseMask() { return 1; }
    float GetOrientation() { return 0; }
    std::vector<int> GetPhases() { return {1, 2}; }
    void AddGameObject(GameObject*);
    void RemoveAllGameObjects();
};
"""
    + body(units, "void Unit::AddGameObject(")
    + body(units, "void Unit::RemoveAllGameObjects()")
    + r"""
struct Spell {
    Unit* m_caster;
    SpellInfo* m_spellInfo;
    void ExecuteLogEffectSummonObject(int, GameObject*) {}
    void SpawnTail(GameObject* pGameObj, Map* cMap, GameObjectTemplate const* goinfo, int32 duration) {
        float fx = 0, fy = 0, fz = 0;
        int effIndex = 0;
"""
    + tail
    + r"""
};
int main() {
    for (int cycle = 0; cycle < 100; ++cycle)
    for (int ownerType : {TYPEID_PLAYER, TYPEID_UNIT})
    for (int goType : {GAMEOBJECT_TYPE_FISHINGNODE, GAMEOBJECT_TYPE_SUMMONING_RITUAL,
                       GAMEOBJECT_TYPE_DUEL_ARBITER, GAMEOBJECT_TYPE_FISHINGHOLE,
                       GAMEOBJECT_TYPE_CHEST, GAMEOBJECT_TYPE_GENERIC})
    for (bool linked : {false, true})
    for (bool failLinked : {false, true})
    for (int32 duration : {0, 30000}) {
        assert(liveObjects == 0);
        Map map; map.failLinked = failLinked;
        Unit caster; caster.type = ownerType;
        SpellInfo info;
        Spell spell{&caster, &info};
        auto go = new GameObject;
        go->map = &map; go->guid = 1;
        go->info.type = goType; go->info.linked = linked ? 100 : 0;
        spell.SpawnTail(go, &map, &go->info, duration);
        auto count = linked && !failLinked ? 2u : 1u;
        assert(map.objects.size() == count && caster.m_gameObj.size() == count);
        assert(cooldownHolds == 0); // Preserve registration-before-SpellId behavior.
        int32 expected = goType == GAMEOBJECT_TYPE_FISHINGNODE ? duration + 2000 : duration;
        for (auto object : map.objects) {
            assert(object->owner == 42 && object->spell == 46905);
            assert(object->respawn == uint32(expected / IN_MILLISECONDS));
        }
        assert(caster.channel == (goType == GAMEOBJECT_TYPE_FISHINGNODE ? 1u : 0u));
        caster.RemoveAllGameObjects();
        assert(caster.m_gameObj.empty());
        for (auto object : map.objects)
            assert(!object->owner && !object->respawn && object->removed);
        caster.RemoveAllGameObjects(); // Repeated cleanup must be harmless.
    }
    assert(liveObjects == 0);
}
"""
)
with tempfile.TemporaryDirectory(
    prefix="loa-gameobject-owner-regression-"
) as directory:
    cpp = pathlib.Path(directory) / "regression.cpp"
    executable = pathlib.Path(directory) / "regression"
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
print("Transmitted GameObject owner registration and cleanup regression passed")
