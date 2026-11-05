#!/usr/bin/env python3
"""Compile the real condition predicate, nearby selector and search-mask code.

World/grid access and condition evaluation are small test doubles. This tests
server target selection, not client rendering or a full Simon Game session.
Pass --dbc-dir to additionally verify the fixtures against build-18414 DBC.
Pass --revision to run the same checks against a pre-fix Git revision.
"""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--revision")
parser.add_argument("--dbc-dir", type=Path)
args = parser.parse_args()


def source(path):
    if args.revision:
        return subprocess.check_output(
            ["git", "show", f"{args.revision}:{path}"], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


def block(text, signature):
    start = text.index(signature)
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


if args.dbc_dir:
    data = (args.dbc_dir / "SpellEffect.dbc").read_bytes()
    magic, count, fields, size, _ = struct.unpack_from("<4s4I", data)
    assert magic == b"WDBC" and fields == 30 and size == 120
    effects = {}
    for offset in range(20, 20 + count * size, size):
        row = struct.unpack_from("<30I", data, offset)
        if row[27] in range(40244, 40248) and row[1] == 0:
            effects[row[27], row[28]] = (row[2], row[25], row[26])
    for spell in range(40244, 40248):
        assert effects[spell, 0] == (86, 40, 0), effects
        assert effects[spell, 1] == (3, 46, 0), effects
    print("PASS: all four local DBC spells use GO nearby (40) and destination nearby (46)", flush=True)

condition = source("src/server/game/Conditions/ConditionMgr.cpp")
predicate = block(condition, "auto hasImplicitWorldObjectTarget =") + ";"
info = source("src/server/game/Spells/SpellInfo.cpp")
table = block(info, "SpellImplicitTargetInfo::StaticData  SpellImplicitTargetInfo::_data")
rows = re.findall(r"\{(TARGET_OBJECT_TYPE_[^{}]+)\}", table)
target_header = source("src/server/game/Spells/SpellInfo.h")
names = sorted(set(re.findall(r"\bTARGET_[A-Z_0-9]+\b", " ".join(rows) + target_header)))
spell = source("src/server/game/Spells/Spell.cpp")
selector = block(spell, "void Spell::SelectImplicitNearbyTargets(")
mask = block(spell, "uint32 Spell::GetSearcherTypeMask(")

prefix = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
using uint8 = uint8_t;
using uint32 = uint32_t;
using SpellEffIndex = int;
using SpellTargetObjectTypes = int;
#define ASSERT assert
#define TC_LOG_DEBUG(...) do {} while (0)
constexpr uint32 GRID_MAP_TYPE_MASK_PLAYER=1, GRID_MAP_TYPE_MASK_CORPSE=2;
constexpr uint32 GRID_MAP_TYPE_MASK_CREATURE=4, GRID_MAP_TYPE_MASK_GAMEOBJECT=8;
constexpr uint32 GRID_MAP_TYPE_MASK_ALL=15;
constexpr uint32 SPELL_ATTR3_ONLY_TARGET_PLAYERS=1, SPELL_ATTR3_ONLY_TARGET_GHOSTS=2;
struct TargetData { int object, reference, category, check, direction; };
'''
target_data = ("enum {" + ",".join(names) + "};\nTargetData targets[] = {\n" +
               ",\n".join("{" + row + "}" for row in rows) + "};\n")
stubs = r'''
struct SpellImplicitTargetInfo {
    int id=0;
    int GetObjectType() const { return targets[id].object; }
    int GetSelectionCategory() const { return targets[id].category; }
    int GetReferenceType() const { return targets[id].reference; }
    int GetCheckType() const { return targets[id].check; }
};
struct WorldObject {
    uint32 entry, kind;
    float distance;
    WorldObject* ToUnit() { return kind==GRID_MAP_TYPE_MASK_CREATURE ? this : nullptr; }
    WorldObject* ToGameObject() { return kind==GRID_MAP_TYPE_MASK_GAMEOBJECT ? this : nullptr; }
};
using Unit=WorldObject;
using GameObject=WorldObject;
using ConditionContainer=std::vector<uint32>;
struct Conditions {
    uint32 GetSearcherTypeMaskForConditionList(ConditionContainer const&) {
        return GRID_MAP_TYPE_MASK_GAMEOBJECT;
    }
} conditions;
Conditions* sConditionMgr=&conditions;
struct Effect { ConditionContainer* ImplicitTargetConditions=nullptr; };
struct SpellInfo {
    uint32 Id=40244, RequiresSpellFocus=0, AttributesEx3=0;
    Effect Effects[2];
    float GetMaxRange(bool, Unit*, void*) const { return 15; }
    bool IsPositive() const { return true; }
    bool IsAllowingDeadTarget() const { return false; }
};
struct Destination {
    WorldObject const* object=nullptr;
    void SetDst(WorldObject const& value) { object=&value; }
};
struct Spell {
    SpellInfo* m_spellInfo;
    Unit* m_caster=nullptr;
    GameObject* focusObject=nullptr;
    Destination m_targets;
    std::vector<WorldObject*> objects;
    bool rejectInHook=false;
    int objectHits=0, chainCalls=0;
    uint32 GetSearcherTypeMask(SpellTargetObjectTypes, ConditionContainer*);
    void SelectImplicitNearbyTargets(SpellEffIndex, SpellImplicitTargetInfo const&, uint32);
    WorldObject* SearchNearbyTarget(float range, SpellImplicitTargetInfo const& target, ConditionContainer* list) {
        auto kinds=GetSearcherTypeMask(target.GetObjectType(), list);
        WorldObject* found=nullptr;
        for (auto* object : objects) {
            if (!(object->kind & kinds) || object->distance>range)
                continue;
            bool allowed=!list;
            if (list)
                for (auto entry : *list)
                    allowed |= object->entry==entry;
            if (allowed) { found=object; range=object->distance; }
        }
        return found;
    }
    void CallScriptObjectTargetSelectHandlers(WorldObject*& target, SpellEffIndex) {
        if (rejectInHook) target=nullptr;
    }
    void AddUnitTarget(Unit*, uint32, bool, bool) { ++objectHits; }
    void AddGOTarget(GameObject*, uint32) { ++objectHits; }
    void SelectImplicitChainTargets(SpellEffIndex, SpellImplicitTargetInfo const&, WorldObject*, uint32) { ++chainCalls; }
};
void require(bool value, char const* message) {
    if (!value) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}
'''
tests = r'''
int main() {
    PREDICATE
    require(hasImplicitWorldObjectTarget({40}), "GO nearby target must accept conditions");
    require(hasImplicitWorldObjectTarget({46}), "nearby destination must retain the object's conditions");
    for (int target : {1, 6, 7, 8, 24, 38})
        require(hasImplicitWorldObjectTarget({target}), "direct/area/cone object conditions regressed");
    for (int target : {0, 17, 18, 22, 72})
        require(!hasImplicitWorldObjectTarget({target}), "non-search coordinate target must reject conditions");
    std::cout << "PASS: nearby destinations accepted; direct/area/cone preserved; pure coordinates rejected\n";

    WorldObject caster{22923, GRID_MAP_TYPE_MASK_CREATURE, 0};
    WorldObject wrong{999, GRID_MAP_TYPE_MASK_GAMEOBJECT, 1};
    WorldObject far{0, GRID_MAP_TYPE_MASK_GAMEOBJECT, 12};
    WorldObject near{0, GRID_MAP_TYPE_MASK_GAMEOBJECT, 5};
    for (uint32 color=0; color<4; ++color) {
        ConditionContainer list{185604+color};
        near.entry=far.entry=list[0];
        SpellInfo info;
        info.Id=40244+color;
        // The same loaded mask=3 attaches the conditions to both effects.
        info.Effects[0].ImplicitTargetConditions=&list;
        info.Effects[1].ImplicitTargetConditions=&list;
        Spell cast{&info};
        cast.m_caster=&caster;
        cast.objects={&far, &wrong, &caster, &near};
        require(cast.GetSearcherTypeMask(TARGET_OBJECT_TYPE_DEST, &list)==GRID_MAP_TYPE_MASK_GAMEOBJECT,
                "destination search must be limited to gameobjects by conditions");
        cast.SelectImplicitNearbyTargets(1, {46}, 2);
        require(cast.m_targets.object==&near, "visual must land at nearest matching color, not caster/wrong color");
        require(cast.objectHits==0, "destination selection must not activate a crystal");
        cast.m_targets.object=nullptr;
        cast.objects={&wrong, &caster};
        cast.SelectImplicitNearbyTargets(1, {46}, 2);
        require(!cast.m_targets.object, "missing color must not select another object");
        near.distance=16;
        cast.objects={&near};
        cast.SelectImplicitNearbyTargets(1, {46}, 2);
        require(!cast.m_targets.object, "out-of-range color must not be selected");
        near.distance=5;
        cast.rejectInHook=true;
        int chains=cast.chainCalls;
        cast.SelectImplicitNearbyTargets(1, {46}, 2);
        require(!cast.m_targets.object && cast.chainCalls==chains, "hook-rejected target must end selection safely");
    }
    std::cout << "PASS: all four colors, nearer decoys, missing/out-of-range crystals, no activation, null hook target\n";
}
'''
program = prefix + target_data + stubs + mask + "\n" + selector + "\n" + tests.replace("PREDICATE", predicate)
with tempfile.TemporaryDirectory(prefix="simon-target-regression-") as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(program)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Wno-missing-field-initializers",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
