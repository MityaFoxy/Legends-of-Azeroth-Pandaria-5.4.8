#!/usr/bin/env python3
"""Compile actual pet-death value and Hunter predicate with bounded pet/DB state.

An unloaded pet has no observable death state. Saved ownership or a stale GUID
must not turn absence into death. Local Player::GetPet, Unit::IsAlive and
Spell::EffectResurrectPet establish the runtime contract; no SQL fixture is
applied to a live database. The DB double also detects accidental polling.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root, compiler = Path(sys.argv[1]), sys.argv[2]


def block(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


unit = (root / 'src/server/game/Entities/Unit/Unit.h').read_text()
value_source = (root / 'modules/mod_playerbots/src/strategy/value/StatsValues.cpp').read_text()
value = block(value_source, 'bool PetIsDeadValue::Calculate()')
trigger = block((root / 'modules/mod_playerbots/src/strategy/Classes/hunter/HunterTriggers.cpp').read_text(),
                'bool HuntersPetDeadTrigger::IsActive()')
prefix = '''#include <cassert>
#include <cstdint>
#include <iostream>
using uint32=uint32_t;
'''
prefix += block(unit, 'enum DeathState') + ';\n'
prefix += 'struct Pet { DeathState m_deathState = ALIVE;\n'
prefix += block(unit, 'bool IsAlive() const') + '\n'
prefix += block(unit, 'DeathState getDeathState() const') + '\n};\n'
prefix += '''
struct Guid { uint32 GetCounter() const { return 42; } };
struct Player {
    Pet* current = nullptr;
    bool staleGuid = false;
    Pet* GetPet() { return current; }
    Guid GetGUID() { return {}; }
    bool GetPetGUID() { return staleGuid; }
};
using QueryResult = bool;
struct Database {
    bool savedPets = true;
    int queries = 0;
    QueryResult PQuery(char const*, uint32) { ++queries; return savedPets; }
} CharacterDatabase;
struct PetIsDeadValue { Player* bot; bool Calculate(); };
struct HuntersPetDeadTrigger { Player* bot; bool IsActive(); };
'''
tests = r'''
int main() {
    Player bot;
    PetIsDeadValue value{&bot};
    HuntersPetDeadTrigger trigger{&bot};
    // An owner with saved pets may have dismissed/stabled them. No current pet
    // is not death, including after the object disappears before GUID cleanup.
    for (bool saved : {true, false}) for (bool stale : {false, true}) {
        CharacterDatabase.savedPets = saved;
        bot.staleGuid = stale;
        assert(!value.Calculate() && "absent pet must not be classified as dead");
        assert(!trigger.IsActive());
    }
    Pet pet;
    bot.current = &pet;
    for (DeathState state : {ALIVE, JUST_DIED, CORPSE, DEAD, JUST_RESPAWNED, ALIVE}) {
        pet.m_deathState = state;
        assert(value.Calculate() == (state != ALIVE) && "loaded pet state changed");
        assert(value.Calculate() == trigger.IsActive() && "value and native Hunter predicate disagree");
    }
    pet.m_deathState = CORPSE;
    Pet replacement;
    bot.current = &replacement;
    assert(!value.Calculate() && "value retained dead previous pet");
    bot.current = nullptr;
    assert(!value.Calculate() && "removed pet must not remain dead");
    assert(CharacterDatabase.queries == 0 && "pet state lookup must not query storage");
    std::cout << "PASS: absent/saved/stale-GUID pets, native death transitions, replacement and zero SQL\n";
}
'''
env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
with tempfile.TemporaryDirectory(prefix='loa-pet-state-') as directory:
    source, binary = Path(directory) / 'fixture.cpp', Path(directory) / 'fixture'

    def run(body):
        source.write_text(prefix + body + trigger + tests)
        subprocess.run([compiler, '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', str(source), '-o', str(binary)], check=True)
        return subprocess.run([str(binary)], env=env, text=True, capture_output=True)

    result = run(value)
    print(result.stdout + result.stderr, end='')
    if result.returncode:
        raise SystemExit(1)
    if '--verify-mutations' in sys.argv:
        mutations = [
            ('absence', 'return pet && !pet->IsAlive();', 'return !pet || !pet->IsAlive();', 'absent pet must not be classified as dead'),
            ('alive', '!pet->IsAlive()', 'pet->IsAlive()', 'loaded pet state changed'),
            ('sql-polling', 'Pet* pet = bot->GetPet();', 'CharacterDatabase.PQuery("SELECT id FROM character_pet WHERE owner = {}", bot->GetGUID().GetCounter());\n    Pet* pet = bot->GetPet();', 'pet state lookup must not query storage'),
        ]
        for name, before, after, assertion in mutations:
            assert value.count(before) == 1, name
            result = run(value.replace(before, after, 1))
            assert result.returncode and assertion in result.stderr, (name, result.stderr)
            print('Detected mutation:', name)
