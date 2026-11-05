#!/usr/bin/env python3
"""Exercise the real CalcPowerCost body with special health resource values."""

import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
compiler = sys.argv[2]


def method(source, signature):
    begin = source.index(signature)
    end = source.index("{", begin) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]


spell_source = (root / "src/server/game/Spells/SpellInfo.cpp").read_text()
shared = (root / "src/server/game/Miscellaneous/SharedDefines.h").read_text()
powers = shared[shared.index("enum Powers\n"):]
powers = powers[:powers.index("\n};") + 3]
source = r'''
#include <cassert>
#include <cstdint>
#include <vector>
using uint32 = std::uint32_t;
using int32 = std::int32_t;
'''+ powers + r'''
using SpellSchoolMask = uint32;
constexpr uint32 SPELL_ATTR1_DRAIN_ALL_POWER = 2;
constexpr uint32 SPELL_ATTR4_SPELL_VS_EXTEND_COST = 0x400;
constexpr uint32 SPELL_ATTR3_REQ_OFFHAND = 0x1000000;
constexpr uint32 SPELL_ATTR0_LEVEL_DAMAGE_CALCULATION = 0x80000;
constexpr int SPELLMOD_COST2 = 34;
enum WeaponAttackType { BASE_ATTACK, OFF_ATTACK };
enum { SPELL_AURA_MOD_POWER_COST_SCHOOL, SPELL_AURA_MOD_POWER_COST_SCHOOL_PCT };
#define TC_LOG_ERROR(...) ((void)0)
#define TC_LOG_DEBUG(...) ((void)0)
template<class T, class U> auto CalculatePct(T base, U percent)
{ return base * percent / 100.0f; }
struct AuraEffect
{
    int32 school, mask, amount;
    int32 GetMiscValue() const { return school; }
    int32 GetMiscValueB() const { return mask; }
    int32 GetAmount() const { return amount; }
};
struct Player
{
    int32 adjustment = 0;
    void ApplyCostSpellMod(uint32, int32& cost) { cost += adjustment; }
    void ApplySpellMod(uint32, int, int32& cost) { cost += adjustment; }
};
struct Unit
{
    using AuraEffectList = std::vector<AuraEffect const*>;
    AuraEffectList flat, pct;
    Player* owner = nullptr;
    uint32 requiredAura = 0;
    bool HasAura(uint32 id) const { return id == requiredAura; }
    uint32 GetHealth() const { return 800; }
    uint32 GetCreateHealth() const { return 1000; }
    uint32 GetCreateMana() const { return 2000; }
    uint32 GetPower(Powers) const { return 50; }
    uint32 GetMaxPower(Powers) const { return 100; }
    AuraEffectList const& GetAuraEffectsByType(int type) const
    { return type == SPELL_AURA_MOD_POWER_COST_SCHOOL ? flat : pct; }
    uint32 GetAttackTime(WeaponAttackType) const { return 2000; }
    Player* GetSpellModOwner() const { return owner; }
    bool IsControlledByPlayer() const { return true; }
    uint32 GetLevel() const { return 90; }
};
struct GtNPCManaCostScalerEntry { float ratio; };
struct ScalerStore
{
    GtNPCManaCostScalerEntry const* LookupEntry(uint32) const { return nullptr; }
} sGtNPCManaCostScalerStore;
struct SpellPowerEntry
{
    uint32 PowerType, Cost;
    float CostPercentage;
    uint32 RequiredAura = 0;
};
struct SpellInfo
{
    uint32 Id = 1, Attributes = 0, AttributesEx = 0, AttributesEx3 = 0;
    uint32 AttributesEx4 = 0, SpellLevel = 1;
    std::vector<SpellPowerEntry const*> SpellPowers;
    int32 CalcPowerCost(Unit const*, SpellSchoolMask, int32 = -1) const;
};
''' + method(spell_source, "int32 SpellInfo::CalcPowerCost(") + r'''
int main()
{
    Unit caster;
    SpellInfo spell;
    SpellPowerEntry entry{POWER_HEALTH, 20, 10};
    spell.SpellPowers = {&entry};
    // Both aura branches must reject health as a bit index, without losing
    // the flat health cost, percent-of-create-health cost or spell modifiers.
    AuraEffect flat{1, -1, 10}, pct{1, -1, -50};
    caster.flat = {&flat};
    assert(spell.CalcPowerCost(&caster, 1) == 120);
    caster.pct = {&pct};
    assert(spell.CalcPowerCost(&caster, 1) == 120);
    caster.flat.clear();
    assert(spell.CalcPowerCost(&caster, 1) == 120);
    Player owner{7};
    caster.owner = &owner;
    assert(spell.CalcPowerCost(&caster, 1) == 127);
    caster.owner = nullptr;
    caster.flat = {&flat};
    // Ordinary resource masks preserve both the flat and percentage filters.
    for (uint32 power = 0; power < MAX_POWERS; ++power)
    {
        entry = {power, 100, 0};
        flat.mask = pct.mask = int32(uint32(1) << power);
        assert(spell.CalcPowerCost(&caster, 1) == 55);
        flat.mask = pct.mask = int32(uint32(1) << ((power + 1) % MAX_POWERS));
        assert(spell.CalcPowerCost(&caster, 1) == 100);
    }
    // Guard the mask's full 32-bit width, including its unsigned high bit.
    entry = {31, 100, 0};
    flat.mask = pct.mask = int32(0x80000000u);
    assert(spell.CalcPowerCost(&caster, 1) == 55);
    for (uint32 special : {32u, uint32(POWER_ALL), uint32(POWER_HEALTH), 0xffffffffu})
    {
        entry = {special, 100, 0};
        flat.mask = pct.mask = -1;
        assert(spell.CalcPowerCost(&caster, 1) == 100);
    }
    entry = {POWER_MANA, 100, 10};
    assert(spell.CalcPowerCost(&caster, 2) == 300); // School does not match.
    entry = {POWER_ENERGY, 100, 10};
    assert(spell.CalcPowerCost(&caster, 2) == 110);
    flat.amount = -1000;
    assert(spell.CalcPowerCost(&caster, 1) == 0); // Preserve zero-cost clamp.
    spell.AttributesEx = SPELL_ATTR1_DRAIN_ALL_POWER;
    entry.PowerType = POWER_HEALTH;
    assert(spell.CalcPowerCost(&caster, 1) == 800);
    entry.PowerType = POWER_MANA;
    assert(spell.CalcPowerCost(&caster, 1) == 50);
    spell.AttributesEx = 0;
    // Required-aura selection still reaches health costs and the right entry.
    SpellPowerEntry health{POWER_HEALTH, 30, 5, 42};
    spell.SpellPowers = {&entry, &health};
    caster.requiredAura = 42;
    assert(spell.CalcPowerCost(&caster, 1) == 80);
    caster.flat.clear(); caster.pct.clear();
    spell.SpellPowers.clear();
    assert(spell.CalcPowerCost(&caster, 1) == 0);
}
'''

with tempfile.TemporaryDirectory(prefix="loa-power-cost-regression-") as directory:
    binary = pathlib.Path(directory) / "regression"
    subprocess.run([compiler, "-x", "c++", "-std=c++20", "-g", "-O1",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-", "-o", str(binary)], input=source, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print("Spell health and ordinary resource cost regressions: PASS")
