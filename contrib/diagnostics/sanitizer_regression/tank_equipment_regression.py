#!/usr/bin/env python3
"""Compile native equipment filters with real enum values and bounded item/player data.

Source of the contract: local ItemPrototype.h separates weapon and armor subclasses;
RandomItemManager selects shields through CanEquipSubArmor, weapons through
CanEquipWeapon. Preserve existing Protection one-hand subclass sets and all other
specializations. Native inventory equip checks still own actual slot placement.
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


source = (root / 'modules/mod_playerbots/src/Manager/RandomItemManager.cpp').read_text(encoding='utf-8-sig')
cpp = '''#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <unordered_set>
using uint8=uint8_t; using uint32=uint32_t;
'''
for path, names in (
    ('src/server/game/Miscellaneous/SharedDefines.h', ['Classes', 'Specializations']),
    ('src/server/game/Entities/Item/ItemPrototype.h', ['InventoryType', 'ItemClass', 'ItemSubclassWeapon', 'ItemSubclassArmor']),
    ('src/server/game/Entities/Player/Player.h', ['EquipmentSlots']),
):
    text = (root / path).read_text()
    for name in names:
        cpp += block(text, 'enum ' + name + (' ' if name == 'EquipmentSlots' else '\n')) + ';\n'
cpp += '''
struct ItemTemplate { uint32 Class, SubClass, InventoryType; };
struct Player {
    Classes clazz; Specializations spec;
    uint8 GetClass() const { return clazz; }
    Specializations GetSpecialization() const { return spec; }
    uint32 GetLevel() const { return 60; }
};
struct RandomItemManager {
    std::map<EquipmentSlots, std::set<InventoryType>> _viable_slots;
    void Init();
    bool ShouldEquipWeaponForSpec(Classes, Specializations, ItemTemplate const*);
    bool CanEquipWeapon(Player*, ItemTemplate const*);
    bool CanEquipSubArmor(Player*, ItemTemplate const*);
};
'''
init = block(source, 'void RandomItemManager::Init()')
cpp += init[:init.index('    TC_LOG_INFO')] + '}\n'
for name in ('ShouldEquipWeaponForSpec', 'CanEquipWeapon', 'CanEquipSubArmor'):
    cpp += block(source, 'bool RandomItemManager::' + name + '(') + '\n'
cpp += r'''
int main() {
    RandomItemManager manager; manager.Init();
    ItemTemplate polearm{ITEM_CLASS_WEAPON, ITEM_SUBCLASS_WEAPON_POLEARM, INVTYPE_2HWEAPON};
    ItemTemplate shield{ITEM_CLASS_ARMOR, ITEM_SUBCLASS_ARMOR_SHIELD, INVTYPE_SHIELD};
    assert(polearm.SubClass == shield.SubClass); // The original cross-class collision.
    for (Player bot : {Player{CLASS_WARRIOR,SPEC_WARRIOR_PROTECTION}, Player{CLASS_PALADIN,SPEC_PALADIN_PROTECTION}}) {
        assert(!manager.ShouldEquipWeaponForSpec(bot.clazz, bot.spec, &polearm));
        assert(!manager.CanEquipWeapon(&bot, &polearm));
        for (uint32 subclass : {ITEM_SUBCLASS_WEAPON_SWORD2, ITEM_SUBCLASS_WEAPON_MACE2,
                               ITEM_SUBCLASS_WEAPON_AXE2, ITEM_SUBCLASS_WEAPON_STAFF}) {
            ItemTemplate twoHand{ITEM_CLASS_WEAPON, subclass, INVTYPE_2HWEAPON};
            assert(!manager.CanEquipWeapon(&bot, &twoHand));
        }
        for (uint32 subclass : {ITEM_SUBCLASS_WEAPON_SWORD, ITEM_SUBCLASS_WEAPON_MACE, ITEM_SUBCLASS_WEAPON_AXE}) {
            for (uint32 inv : {INVTYPE_WEAPON, INVTYPE_WEAPONMAINHAND}) {
                ItemTemplate oneHand{ITEM_CLASS_WEAPON, subclass, inv};
                assert(manager.ShouldEquipWeaponForSpec(bot.clazz, bot.spec, &oneHand));
                assert(manager.CanEquipWeapon(&bot, &oneHand));
                oneHand.Class = ITEM_CLASS_ARMOR;
                assert(!manager.ShouldEquipWeaponForSpec(bot.clazz, bot.spec, &oneHand));
            }
            for (uint32 inv : {INVTYPE_2HWEAPON, INVTYPE_WEAPONOFFHAND, INVTYPE_HOLDABLE, INVTYPE_SHIELD}) {
                ItemTemplate wrongSlot{ITEM_CLASS_WEAPON, subclass, inv};
                assert(!manager.ShouldEquipWeaponForSpec(bot.clazz, bot.spec, &wrongSlot));
            }
        }
        // A shield is armor and remains available through the actual armor path.
        assert(manager.CanEquipSubArmor(&bot, &shield));
        assert(!manager.ShouldEquipWeaponForSpec(bot.clazz, bot.spec, &shield));
        ItemTemplate held{ITEM_CLASS_ARMOR, ITEM_SUBCLASS_ARMOR_MISCELLANEOUS, INVTYPE_HOLDABLE};
        assert(!manager.CanEquipSubArmor(&bot, &held));
        for (uint32 subclass : {ITEM_SUBCLASS_WEAPON_DAGGER, ITEM_SUBCLASS_WEAPON_FIST_WEAPON}) {
            ItemTemplate weapon{ITEM_CLASS_WEAPON, subclass, INVTYPE_WEAPON};
            assert(manager.CanEquipWeapon(&bot, &weapon) == (bot.clazz == CLASS_WARRIOR));
        }
    }
    // Keep existing non-Protection rules: in particular do not remove the global
    // two-hand/offhand candidate slot used by native Titan's Grip equip checks.
    assert(manager._viable_slots[EQUIPMENT_SLOT_OFFHAND].contains(INVTYPE_2HWEAPON));
    for (Player bot : {Player{CLASS_WARRIOR,SPEC_WARRIOR_ARMS}, Player{CLASS_WARRIOR,SPEC_WARRIOR_FURY},
                       Player{CLASS_PALADIN,SPEC_PALADIN_RETRIBUTION}})
        assert(manager.CanEquipWeapon(&bot, &polearm));
    ItemTemplate dagger{ITEM_CLASS_WEAPON, ITEM_SUBCLASS_WEAPON_DAGGER, INVTYPE_WEAPON};
    Player rogue{CLASS_ROGUE,SPEC_ROGUE_ASSASSINATION};
    assert(manager.CanEquipWeapon(&rogue, &dagger));
    ItemTemplate staff{ITEM_CLASS_WEAPON, ITEM_SUBCLASS_WEAPON_STAFF, INVTYPE_2HWEAPON};
    for (Player bot : {Player{CLASS_MONK,SPEC_MONK_BREWMASTER}, Player{CLASS_MONK,SPEC_MONK_WINDWALKER},
                       Player{CLASS_MONK,SPEC_MONK_MISTWEAVER}, Player{CLASS_DRUID,SPEC_DRUID_GUARDIAN}})
        assert(manager.CanEquipWeapon(&bot, &staff));
    std::cout << "PASS: Protection one-hand weapons, shield path, class/slot separation and other specs\n";
}
'''
env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
with tempfile.TemporaryDirectory(prefix='loa-tank-equipment-') as directory:
    path = Path(directory) / 'fixture.cpp'
    binary = Path(directory) / 'fixture'

    def run(text):
        path.write_text(text)
        subprocess.run([compiler, '-std=c++20', '-O1', '-g', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', str(path), '-o', str(binary)], check=True)
        return subprocess.run([str(binary)], env=env, text=True, capture_output=True)

    result = run(cpp)
    if result.returncode:
        print(result.stdout + result.stderr)
        raise SystemExit(1)
    print(result.stdout.strip())
    if '--verify-mutations' in sys.argv:
        changes = {
            'item-class': ('proto->Class != ITEM_CLASS_WEAPON ||', 'false ||'),
            'inventory-type': ('(proto->InventoryType != INVTYPE_WEAPON && proto->InventoryType != INVTYPE_WEAPONMAINHAND)', 'false'),
            'shield-path': ('if (spec == Specializations::SPEC_WARRIOR_PROTECTION && proto->SubClass == ITEM_SUBCLASS_ARMOR_SHIELD)\n                return true;',
                            'if (spec == Specializations::SPEC_WARRIOR_PROTECTION && proto->SubClass == ITEM_SUBCLASS_ARMOR_SHIELD)\n                return false;'),
        }
        for name, (before, after) in changes.items():
            assert cpp.count(before) == 1, name
            result = run(cpp.replace(before, after, 1))
            assert result.returncode and ('Assertion' in result.stderr or 'assertion' in result.stderr), name
            print('Detected mutation:', name)
