#!/usr/bin/env python3
"""Exercise production effect accessors, Aura persistence and sparse DBC lookup.

Subsystem doubles avoid the full game/database dependency. Optional --dbc checks
all slots and difficulties against the previous dense index using a real DBC.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
parser.add_argument("compiler")
parser.add_argument("--dbc", type=Path)
parser.add_argument("--verify-mutations", action="store_true")
args = parser.parse_args()

def method(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]

header = (args.root / "src/server/game/Spells/SpellInfo.h").read_text()
stores = (args.root / "src/server/game/DataStores/DBCStores.cpp").read_text()
auras = (args.root / "src/server/game/Spells/Auras/SpellAuras.cpp").read_text()
declarations = re.findall(r"^        [^{}\n]*SpellEffectInfo[^{}\n]*(?: Effects| _effects)[^;{}\n]*;", header, re.M)
accessors = "\n".join(method(header, signature) for signature in (
    "std::array<SpellEffectInfo, MAX_SPELL_EFFECTS> const& GetEffects()",
    "SpellEffectInfo const& GetEffect(",
    "std::array<SpellEffectInfo, MAX_SPELL_EFFECTS>& _GetEffects()",
    "SpellEffectInfo& _GetEffect("))
index_declaration = re.search(r"typedef std::unordered_map<uint32, .* SpellEffectMap;", stores).group()
insertion = re.search(r"^            sSpellEffectMap\[spellEffect->EffectSpellId\].*;", stores, re.M).group()
source = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <unordered_map>
#include <vector>
extern "C" size_t __sanitizer_get_current_allocated_bytes();
using uint32 = uint32_t;
using SpellEffIndex = uint32;
#define ASSERT assert
constexpr uint32 MAX_SPELL_EFFECTS = 32, MAX_DIFFICULTY = 15, REGULAR_DIFFICULTY = 0;
struct SpellEffectInfo {
    bool active = false, area = false, areaAura = false;
    bool IsEffect() const { return active; }
    bool IsTargetingArea() const { return area; }
    bool IsAreaAuraEffect() const { return areaAura; }
};
struct SpellInfo {
''' + "\n".join(declarations) + accessors + r'''
    bool channel = false, single = false;
    uint32 AttributesCu = 0;
    bool IsChanneled() const { return channel; }
    bool IsSingleTarget() const { return single; }
};
constexpr int SPELL_AURA_CONVERT_RUNE = 1, SPELL_AURA_OPEN_STABLE = 2,
    SPELL_AURA_CONTROL_VEHICLE = 3, SPELL_ATTR0_CU_DONT_SAVE_AURA_TO_DB = 1;
struct Owner { uint32 GetGUID() const { return 1; } };
struct Aura {
    SpellInfo* m_spellInfo;
    uint32 caster = 2;
    bool passive = false, charges = false;
    int effectType = 0, count = 1;
    Owner owner;
    bool IsPassive() const { return passive; }
    SpellInfo* GetSpellInfo() const { return m_spellInfo; }
    uint32 GetCasterGUID() const { return caster; }
    Owner const* GetOwner() const { return &owner; }
    bool HasEffectType(int type) const { return type == effectType; }
    bool IsUsingCharges() const { return charges; }
    int GetCharges() const { return count; }
    bool CanBeSaved() const;
};
''' + method(auras, "bool Aura::CanBeSaved() const") + r'''
struct SpellEffectEntry { uint32 Id, EffectSpellId, EffectDifficulty, EffectIndex; };
''' + index_declaration + "\nSpellEffectMap sSpellEffectMap;\n" + method(stores, "SpellEffectEntry const* GetSpellEffectEntry(") + r'''
void add(SpellEffectEntry const* spellEffect) {
''' + insertion + r'''
}
void verify(std::vector<SpellEffectEntry> const& rows) {
    sSpellEffectMap.clear();
    size_t before = __sanitizer_get_current_allocated_bytes();
    for (auto const& row : rows) add(&row);
    size_t indexBytes = __sanitizer_get_current_allocated_bytes() - before;
    std::unordered_map<uint32, std::vector<SpellEffectEntry const*>> grouped;
    for (auto const& row : rows) grouped[row.EffectSpellId].push_back(&row);
    uint64_t checks = 0;
    for (auto const& [spell, entries] : grouped) {
        SpellEffectEntry const* old[MAX_DIFFICULTY][MAX_SPELL_EFFECTS] = {};
        for (auto entry : entries) old[entry->EffectDifficulty][entry->EffectIndex] = entry;
        for (uint32 difficulty = 0; difficulty < MAX_DIFFICULTY; ++difficulty)
            for (uint32 effect = 0; effect < MAX_SPELL_EFFECTS; ++effect) {
                auto expected = old[difficulty][effect] ? old[difficulty][effect] : old[0][effect];
                assert(GetSpellEffectEntry(spell, effect, difficulty) == expected);
                ++checks;
            }
    }
    std::cout << "verified spells=" << grouped.size() << " lookups=" << checks << " index_allocated_bytes=" << indexBytes << "\n";
}
int main(int argc, char** argv) {
    SpellInfo spell;
    assert(&spell.GetEffects()[0] == &spell.Effects[0]);
    assert(&spell._GetEffects()[31] == &spell.Effects[31]);
    assert(&spell.GetEffect(31) == &spell.Effects[31]);
    assert(&spell._GetEffect(0) == &spell.Effects[0]);
    Aura aura{&spell};
    assert(aura.CanBeSaved());
    spell.Effects[31] = {true, true, false};
    assert(!aura.CanBeSaved());
    aura.caster = 1;
    assert(aura.CanBeSaved());
    aura.caster = 2;
    spell._GetEffect(31) = {true, false, true};
    assert(!aura.CanBeSaved());
    spell._GetEffects()[31] = {false, true, true};
    assert(aura.CanBeSaved());
    spell.single = true;
    assert(!aura.CanBeSaved());
    spell.single = false;
    aura.passive = true;
    assert(!aura.CanBeSaved());
    aura.passive = false;
    spell.channel = true;
    assert(!aura.CanBeSaved());
    spell.channel = false;
    for (int type : {1, 2, 3}) { aura.effectType = type; assert(!aura.CanBeSaved()); }
    aura.effectType = 0;
    spell.AttributesCu = 1;
    assert(!aura.CanBeSaved());
    spell.AttributesCu = 0;
    aura.charges = true; aura.count = 0;
    assert(!aura.CanBeSaved());
    aura.count = 1;
    assert(aura.CanBeSaved());
    verify({{1,42,0,0}, {2,42,14,0}, {3,42,0,31}, {4,42,14,31},
            {5,42,0,0}, {6,42,14,0}, {7,43,2,17}, {8,44,0,31}});
    assert(!GetSpellEffectEntry(99999, 0, 0));
    if (argc == 2) {
        std::ifstream file(argv[1], std::ios::binary);
        uint32 header[5];
        file.read(reinterpret_cast<char*>(header), sizeof(header));
        assert(file && header[0] == 0x43424457 && header[2] == 30 && header[3] == 120);
        std::vector<SpellEffectEntry> rows;
        for (uint32 i = 0; i < header[1]; ++i) {
            uint32 row[30]; file.read(reinterpret_cast<char*>(row), sizeof(row));
            assert(file && row[1] < MAX_DIFFICULTY && row[28] < MAX_SPELL_EFFECTS);
            if (row[0]) rows.push_back({row[0], row[27], row[1], row[28]});
        }
        std::sort(rows.begin(), rows.end(), [](auto const& a, auto const& b) { return a.Id < b.Id; });
        verify(rows);
    }
}
'''
with tempfile.TemporaryDirectory(prefix="loa-spell-storage-") as tmp:
    cpp = Path(tmp) / "test.cpp"
    binary = Path(tmp) / "test"
    cpp.write_text(source)
    subprocess.run([args.compiler, "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)] + ([str(args.dbc)] if args.dbc else []), check=True)

    if args.verify_mutations:
        variants = {
            "separate_uninitialized_effects": source.replace(
                "struct SpellInfo {", "struct SpellInfo { std::array<SpellEffectInfo, 32> _effects;").replace(
                "return Effects;", "return _effects;").replace("return Effects[index];", "return _effects[index];"),
            "missing_regular_fallback": source.replace("return fallback;", "return nullptr;"),
            "first_duplicate_wins": source.replace("itr->second.rbegin()", "itr->second.begin()").replace(
                "itr->second.rend()", "itr->second.end()"),
        }
        for name, mutated in variants.items():
            assert mutated != source
            cpp.write_text(mutated)
            subprocess.run([args.compiler, "-std=c++20", "-O1", "-fsanitize=address,undefined",
                            str(cpp), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            assert result.returncode != 0 and "Assertion" in result.stderr, (name, result.stderr)
            print("rejected mutation:", name)
