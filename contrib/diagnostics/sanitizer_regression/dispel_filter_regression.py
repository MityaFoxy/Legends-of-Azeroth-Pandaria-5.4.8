#!/usr/bin/env python3
"""Compile production aura eligibility/filter and string comparison, with bounded world doubles."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
compiler = sys.argv[2]

def block(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

source = (root / 'modules/mod_playerbots/src/AI/PlayerbotAI.cpp').read_text()
helper = (root / 'modules/mod_playerbots/src/Utils/Helper.h').read_text()
methods = block(source, 'bool PlayerbotAI::canDispel(') + '\n' + block(source, 'bool PlayerbotAI::HasAuraToDispel(')
comparison = block(helper, 'inline bool caseInsensitiveEqual(')
prefix = r'''
#include <algorithm>
#include <cassert>
#include <cctype>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <string_view>
#include <vector>
using uint32 = std::uint32_t; using int32 = std::int32_t;
struct SpellInfo { uint32 Dispel; char const* SpellName; bool positive = false; bool IsPositive() const { return positive; } };
struct Aura {
    SpellInfo info; bool passive = false; int32 duration = 30000;
    bool IsPassive() const { return passive; }
    int32 GetDuration() const { return duration; }
    SpellInfo const* GetSpellInfo() const { return &info; }
};
struct AuraApplication { Aura* aura; Aura* GetBase() const { return aura; } };
struct Unit {
    using VisibleAuraMap = std::map<uint32, AuraApplication*>;
    VisibleAuraMap auras; bool world = true, friendly = true;
    bool IsInWorld() const { return world; }
    bool IsFriendlyTo(Unit* target) const { return target->friendly; }
    VisibleAuraMap const* GetVisibleAuras() const { return &auras; }
};
struct Config { uint32 dispelAuraDuration = 2000; } config;
Config* sPlayerbotAIConfig = &config;
struct PlayerbotAI {
    Unit* bot;
    bool canDispel(SpellInfo const*, uint32);
    bool HasAuraToDispel(Unit*, uint32);
};
'''
tests = r'''
int main() {
    Unit bot, ally, enemy; enemy.friendly = false; PlayerbotAI ai{&bot};
    for (auto name : {"Deadly Poison", "Curse of the Elements", "Frost Nova", "", static_cast<char const*>(nullptr)}) {
        SpellInfo info{4, name};
        assert(ai.canDispel(&info, 4) && "ordinary matching aura must be eligible");
        assert(!ai.canDispel(&info, 1) && "dispel type must match");
    }
    for (auto name : {"mutating injection", "FROSTBOLT", "Demon Skin", "mage armor", "frost armor",
                      "wavering will", "chilled", "mana tap", "ice armor"}) {
        SpellInfo info{1, name};
        assert(!ai.canDispel(&info, 1) && "historical exclusions must be preserved");
    }
    Aura harmful{{4, "Deadly Poison"}}, beneficial{{1, "Power Word: Fortitude", true}};
    AuraApplication negative{&harmful}, positive{&beneficial};
    ally.auras[0] = &negative; ally.auras[1] = &positive;
    enemy.auras = ally.auras;
    assert(ai.HasAuraToDispel(&ally, 4));
    assert(!ai.HasAuraToDispel(&ally, 1) && "do not purge an ally buff");
    assert(!ai.HasAuraToDispel(&enemy, 4) && "do not cleanse an enemy debuff");
    assert(ai.HasAuraToDispel(&enemy, 1) && "hostile buff can be purged");
    harmful.passive = true; assert(!ai.HasAuraToDispel(&ally, 4)); harmful.passive = false;
    harmful.duration = 1000; assert(!ai.HasAuraToDispel(&ally, 4));
    harmful.duration = 0; assert(ai.HasAuraToDispel(&ally, 4));
    ally.world = false; assert(!ai.HasAuraToDispel(&ally, 4)); ally.world = true;
    ally.auras.erase(0); assert(!ai.HasAuraToDispel(&ally, 4));
    std::cout << "PASS: shared dispel filter, exclusions, friendly/hostile polarity, lifetime and passive gates\n";
}
'''
with tempfile.TemporaryDirectory(prefix='loa-dispel-filter-') as tmp:
    def run(label, code, expected=None):
        binary = Path(tmp) / label
        subprocess.run([compiler, '-x', 'c++', '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-', '-o', str(binary)],
                       input=prefix + comparison + code + tests, text=True, check=True)
        result = subprocess.run([str(binary)], text=True, capture_output=True,
                                env=dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1'))
        if expected:
            assert result.returncode and expected in result.stderr, result.stderr
            print(f'Mutation {label}: rejected ({expected})', flush=True)
        else:
            print(result.stdout, end='', flush=True)
            if result.returncode:
                print(result.stderr, file=sys.stderr)
                raise subprocess.CalledProcessError(result.returncode, str(binary))
    run('current', methods)
    if '--verify-mutations' in sys.argv:
        for label, old, new, expected in (
            ('bool-as-strcmp', 'if (caseInsensitiveEqual(spellInfo->SpellName, wl))',
             'if (caseInsensitiveEqual(spellInfo->SpellName, wl) == 0)', 'ordinary matching aura must be eligible'),
            ('inverted-exclusion', '!caseInsensitiveEqual(spellInfo->SpellName, "demon skin")',
             'caseInsensitiveEqual(spellInfo->SpellName, "demon skin")', 'ordinary matching aura must be eligible'),
            ('wrong-type', 'if (spellInfo->Dispel != dispelType)', 'if (false)', 'dispel type must match'),
            ('ally-positive', 'if (isPositiveSpell && isFriend)', 'if (false)', 'do not purge an ally buff')):
            assert old in methods, old
            run(label, methods.replace(old, new, 1), expected)
