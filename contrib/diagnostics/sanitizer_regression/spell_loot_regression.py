#!/usr/bin/env python3
"""Reproduce the spell-mechanic and world-drop loot UBSan findings."""

import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]


def method(source, signature):
    begin = source.index(signature)
    brace = source.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


spell_source = (root / "src/server/game/Spells/SpellInfo.cpp").read_text()
mechanic_methods = "\n".join(
    method(spell_source, signature)
    for signature in (
        "uint32 SpellInfo::GetAllEffectsMechanicMask() const",
        "uint32 SpellInfo::GetEffectMechanicMask(uint8 effIndex) const",
        "uint32 SpellInfo::GetSpellMechanicMaskByEffectMask(uint32 effectMask) const",
    )
)

loot_header = (root / "src/server/game/Loot/LootMgr.h").read_text()
loot_begin = loot_header.index("struct LootItem\n")
loot_end = loot_header.index("\n};", loot_begin) + len("\n};")
loot_declaration = loot_header[loot_begin:loot_end]
loot_source = (root / "src/server/game/Loot/LootMgr.cpp").read_text()
world_drop_constructor = method(
    loot_source, "LootItem::LootItem(WorldDropLootItem const& item)"
)

source = (
    r"""
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <new>
#include <set>
#include <utility>
#include <vector>

using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using int32 = std::int32_t;
constexpr uint8 MAX_SPELL_EFFECTS = 3;

struct SpellEffectInfo
{
    uint32 Mechanic = 0;
    bool Active = false;
    bool IsEffect() const { return Active; }
};

struct SpellInfo
{
    uint32 Mechanic = 0;
    std::array<SpellEffectInfo, MAX_SPELL_EFFECTS> Effects{};
    uint32 GetAllEffectsMechanicMask() const;
    uint32 GetEffectMechanicMask(uint8 effIndex) const;
    uint32 GetSpellMechanicMaskByEffectMask(uint32 effectMask) const;
};
"""
    + mechanic_methods
    + r"""

using ConditionContainer = std::vector<int>;
using AllowedLooterSet = std::set<std::uint64_t>;
struct LootStoreItem;
struct WorldDropLootItem;
struct Player;
struct Object;
struct ByteBuffer;
"""
    + loot_declaration
    + r"""

struct WorldDropLootItem { uint32 Item; };
struct ItemTemplate {};
struct ObjectMgr
{
    ItemTemplate const* GetItemTemplate(uint32) const { return nullptr; }
};
ObjectMgr objectMgr;
ObjectMgr* sObjectMgr = &objectMgr;
constexpr uint8 LOOT_ITEM_TYPE_ITEM = 0;
uint32 GenerateEnchSuffixFactor(uint32) { return 0; }
struct Item
{
    static int32 GenerateItemRandomPropertyId(uint32) { return 0; }
};
"""
    + world_drop_constructor
    + r"""

int main(int argc, char** argv)
{
    assert(argc == 2);
    if (std::strcmp(argv[1], "spell") == 0)
    {
        SpellInfo spell;
        spell.Effects[0] = { 31, true };
        assert(spell.GetAllEffectsMechanicMask() == 0x80000000U);
        spell.Effects[0].Mechanic = 32;
        assert(spell.GetAllEffectsMechanicMask() == 0);
        assert(spell.GetEffectMechanicMask(0) == 0);
        assert(spell.GetSpellMechanicMaskByEffectMask(1) == 0);
        spell.Effects[0] = { 1, true };
        assert(spell.GetAllEffectsMechanicMask() == 2U);
        return 0;
    }

    alignas(LootItem) unsigned char storage[sizeof(LootItem)];
    std::memset(storage, 0x87, sizeof(storage));
    auto* worldDrop = new (storage) LootItem(WorldDropLootItem{ 123 });
    LootItem moved(std::move(*worldDrop));
    assert(!moved.is_underthreshold && moved.canSave);
    worldDrop->~LootItem();

    std::memset(storage, 0x87, sizeof(storage));
    auto* empty = new (storage) LootItem();
    assert(!empty->is_world_drop && !empty->personal);
    empty->~LootItem();
}
"""
)

with tempfile.TemporaryDirectory(prefix="loa-spell-loot-regression-") as directory:
    binary = pathlib.Path(directory) / "regression"
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
            "-",
            "-o",
            str(binary),
        ],
        input=source,
        text=True,
        check=True,
    )
    failures = []
    for case in ("spell", "loot"):
        result = subprocess.run([str(binary), case], check=False)
        if result.returncode:
            failures.append((case, result.returncode))
    if failures:
        raise RuntimeError(f"sanitizer regression failures: {failures}")
print("Spell mechanic mask and LootItem initialization regressions: PASS")
