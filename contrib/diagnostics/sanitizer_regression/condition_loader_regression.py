#!/usr/bin/env python3
"""Exercise signed loot-condition matching and validate the warning cleanup."""
from pathlib import Path
import os
import re
import struct
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
compiler = sys.argv[2]


def method(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


loot = (root / "src/server/game/Loot/LootMgr.cpp").read_text()
add_condition = method(loot, "bool LootTemplate::addConditionItem(")
is_reference = method(loot, "bool LootTemplate::isReference(")

conditions = (root / "src/server/game/Conditions/ConditionMgr.cpp").read_text()
warning_index = conditions.index("Quest condition has useless data in value2")
quest_start = conditions.rindex("        case CONDITION_QUESTSTATE:", 0, warning_index)
quest_block = conditions[
    quest_start:conditions.index("        case CONDITION_DRUNKENSTATE:", warning_index)]
warning_guard = re.search(
    r"if \(([^\n]+)\)\n\s+TC_LOG_ERROR\(\"sql\.sql\", "
    r"\"Quest condition has useless data in value2", quest_block)
assert warning_guard, "Quest value2 warning guard not found"

source = r'''
#include <cassert>
#include <cstdint>
#include <vector>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using int32 = std::int32_t;
using int64 = std::int64_t;
#define TC_LOG_ERROR(...) ((void)0)
enum LootItemType { LOOT_ITEM_TYPE_ITEM, LOOT_ITEM_TYPE_CURRENCY };
struct Condition {
    int32 SourceEntry = 0;
    int ConditionType = 0;
    uint32 ConditionValue2 = 0;
    bool isLoaded() const { return true; }
};
struct LootStoreItem {
    uint32 itemid;
    LootItemType type;
    int32 mincountOrRef;
    std::vector<Condition*> conditions;
};
using LootStoreItemList = std::vector<LootStoreItem*>;
struct LootGroup {
    LootStoreItemList explicitItems, equalItems;
    LootStoreItemList* GetExplicitlyChancedItemList() { return &explicitItems; }
    LootStoreItemList* GetEqualChancedItemList() { return &equalItems; }
};
using LootGroups = std::vector<LootGroup*>;
struct LootTemplate {
    LootStoreItemList Entries;
    LootGroups Groups;
    bool addConditionItem(Condition*);
    bool isReference(int32);
};
'''
source += add_condition + "\n" + is_reference + "\n"
source += "constexpr int CONDITION_QUESTSTATE = 47;\n"
source += "bool warns(Condition* cond) { return " + warning_guard.group(1) + "; }\n"
source += r'''
int main() {
    LootStoreItem coin{777, LOOT_ITEM_TYPE_CURRENCY, 1};
    LootStoreItem groupedCoin{738, LOOT_ITEM_TYPE_CURRENCY, 1};
    LootStoreItem item{100, LOOT_ITEM_TYPE_ITEM, 1};
    LootStoreItem reference{0, LOOT_ITEM_TYPE_ITEM, -42};
    LootGroup group;
    group.equalItems = {&groupedCoin};
    LootTemplate loot;
    loot.Entries = {&coin, &item, &reference};
    loot.Groups = {&group};

    Condition coinCondition{-777};
    assert(loot.isReference(-777));
    assert(loot.addConditionItem(&coinCondition));
    assert(coin.conditions.size() == 1 && item.conditions.empty());

    Condition groupedCoinCondition{-738};
    assert(loot.isReference(-738));
    assert(loot.addConditionItem(&groupedCoinCondition));
    assert(groupedCoin.conditions.size() == 1);

    Condition itemCondition{100};
    assert(loot.addConditionItem(&itemCondition));
    assert(item.conditions.size() == 1);
    Condition wrongKind{-100};
    assert(!loot.addConditionItem(&wrongKind));
    assert(loot.isReference(0));
    assert(!loot.isReference(-999));

    Condition questState{0, CONDITION_QUESTSTATE, 74};
    Condition ordinaryQuest{0, 9, 74};
    assert(!warns(&questState));
    assert(warns(&ordinaryQuest));
}
'''

migration = (root / "sql/updates/world/2026_10_31_00_fix_condition_loader_warnings.sql").read_text()
for required in (
        "conditions_invalid_reference_archive", "SourceEntry` = 60535",
        "ConditionTypeOrReference` = 31", "ConditionValue1` = 5",
        "(74670, 78499, 126022)", "SourceEntry` = 89008",
        "(64558, 68355, 89892, 100342, 100344, 137967)",
        "SourceEntry` = 100345", "(13, 7, 60430", "(13, 1, 75886",
        "(13, 1, 136909"):
    assert required in migration, required

dbc = (root.parent / "loa-runtime/dbc/SpellEffect.dbc")
if dbc.exists():
    data = dbc.read_bytes()
    magic, count, fields, size, _ = struct.unpack_from("<4s4I", data)
    assert magic == b"WDBC" and fields == 30 and size == 120
    effects = {}
    for offset in range(20, 20 + count * size, size):
        row = struct.unpack_from("<30I", data, offset)
        effects.setdefault((row[27], row[28]), set()).add((row[2], row[25], row[26]))
    expected = {
        (60535, 0): {(86, 40, 0)},
        (64558, 0): {(3, 8, 0)},
        (68355, 0): {(3, 38, 0)},
        (74670, 0): {(149, 46, 0)},
        (74670, 1): {(32, 87, 0)},
        (78499, 0): {(2, 8, 0)},
        (89008, 0): {(86, 109, 0)},
        (89008, 1): {(3, 38, 0)},
        (89892, 0): {(3, 38, 0)},
        (100342, 0): {(6, 38, 0)},
        (100344, 0): {(6, 38, 0)},
        (100345, 0): {(6, 38, 0)},
        (100345, 1): {(64, 1, 0)},
        (137967, 0): {(6, 38, 0)},
        (136909, 0): {(61, 0, 0)},
    }
    for key, value in expected.items():
        assert effects.get(key) == value, (key, effects.get(key))

with tempfile.TemporaryDirectory(prefix="loa-condition-loader-") as directory:
    cpp = Path(directory) / "test.cpp"
    binary = Path(directory) / "test"
    cpp.write_text(source)
    subprocess.run([compiler, "-std=c++20", "-O1", "-g",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True, env=dict(
        os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1",
        UBSAN_OPTIONS="halt_on_error=1"))

print("PASS: currency loot conditions, QuestState masks, DBC masks and reversible SQL cleanup")
