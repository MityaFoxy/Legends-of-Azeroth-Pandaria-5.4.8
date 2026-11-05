#!/usr/bin/env python3
"""Test recovered DB fixtures with the actual core quest predicates.

--data is JSON exported from the isolated/restored database (see the audit).
The dependency loader and two Player methods are compiled from current source;
world/session/reputation storage are test doubles. This is not a client test.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data', required=True, type=Path)
parser.add_argument('--dbc-dir', required=True, type=Path)
args = parser.parse_args()
fixture = json.loads(args.data.read_text())
assert fixture['objective'] == [270242, -1, 6, 1359, 42000]
assert fixture['objective_count'] == 1
assert fixture['template'] == [90, 90, 83, 6, 228000, 247200, 139524, 1359, 5]
assert fixture['starter'] == fixture['ender'] == 1
assert sorted(fixture['addons']) == [
    [32591, 32590, 32593, -32591, 0, 0],
    [32592, 32590, 32593, -32591, 0, 0]]

def dbc(name):
    data = (args.dbc_dir / name).read_bytes()
    magic, count, fields, size, _ = struct.unpack_from('<4s4I', data)
    assert magic == b'WDBC' and size == fields * 4
    return [struct.unpack_from('<' + 'I' * fields, data, offset)
            for offset in range(20, 20 + count * size, size)]

assert next(r for r in dbc('QuestV2.dbc') if r[0] == 32592)[1] == 14815
assert next(r for r in dbc('QuestXP.dbc') if r[0] == 90)[7] == 294000
assert next(r for r in dbc('QuestFactionReward.dbc') if r[0] == 1)[6] == 250
effect = [r for r in dbc('SpellEffect.dbc') if r[27] == 139524]
assert len(effect) == 1 and (effect[0][2], effect[0][25], effect[0][28]) == (77, 1, 0)

def block(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

player = (ROOT / 'src/server/game/Entities/Player/Player.cpp').read_text()
header = (ROOT / 'src/server/game/Quests/QuestDef.h').read_text()
manager = (ROOT / 'src/server/game/Globals/ObjectMgr.cpp').read_text()
loader = manager[manager.index('        // fill additional data stores'):
                 manager.index('        if (qinfo->_limitTime)',
                               manager.index('        // fill additional data stores'))]
objective_enum = block(header, 'enum QuestObjectiveType') + ';'
methods = '\n'.join(block(player, s) for s in [
    'bool Player::IsQuestObjectiveComplete(',
    'bool Player::SatisfyQuestDependentPreviousQuests('])
prefix = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <set>
#include <vector>
#include <iostream>
using uint32 = uint32_t;
using int32 = int32_t;
using uint64 = uint64_t;
#define ASSERT assert
#define TC_LOG_DEBUG(...) do {} while(0)
#define TC_LOG_ERROR(...) do {} while(0)
constexpr int QUEST_ERR_NONE = 0;
struct QuestObjective { uint32 ID; int32 Type, ObjectID, Amount; };
struct Quest {
    uint32 id = 0;
    int32 _prevQuestID = 0, _nextQuestID = 0, _exclusiveGroup = 0;
    std::vector<uint32> DependentPreviousQuests;
    uint32 GetQuestId() const { return id; }
    int32 GetPrevQuestId() const { return _prevQuestID; }
    int32 GetNextQuestId() const { return _nextQuestID; }
    int32 GetExclusiveGroup() const { return _exclusiveGroup; }
};
struct ObjectMgr {
    std::map<uint32, Quest*> _questTemplates;
    std::multimap<int32, uint32> _exclusiveQuestGroups;
    Quest const* GetQuestTemplate(uint32 id) const { return _questTemplates.at(id); }
    auto GetExclusiveQuestGroupBounds(int32 group) const { return _exclusiveQuestGroups.equal_range(group); }
    void LoadDependencies();
} manager;
ObjectMgr* sObjectMgr = &manager;
struct Reputation {
    std::map<int32, int32> values;
    int32 GetReputation(int32 faction) const { return values.at(faction); }
};
struct Player {
    Reputation rep;
    std::set<uint32> rewarded;
    Reputation const& GetReputationMgr() const { return rep; }
    bool IsQuestRewarded(uint32 id) const { return rewarded.count(id); }
    void SendCanTakeQuestResponse(int) const {}
    bool HasSpell(int32) const { return false; }
    bool HasEnoughMoney(uint64) const { return false; }
    bool HasCurrency(int32, int32) const { return false; }
    uint32 GetQuestObjectiveCounter(uint32) const { return 0; }
    bool IsQuestObjectiveComplete(Quest const*, QuestObjective const&) const;
    bool SatisfyQuestDependentPreviousQuests(Quest const*, bool) const;
};
'''
fixtures = '\n'.join(
    'Quest q%d{%d,%d,%d,%d}; manager._questTemplates[%d] = &q%d;' %
    (q[0], q[0], q[1], q[2], q[3], q[0], q[0]) for q in fixture['addons'])
obj = fixture['objective']
main = r'''
int main() {
    Quest upstairs{32590}, forge{32593};
    manager._questTemplates[32590] = &upstairs;
    manager._questTemplates[32593] = &forge;
''' + fixtures + '\nQuestObjective objective{%d,%d,%d,%d};\n' % (obj[0], obj[2], obj[3], obj[4]) + r'''
    manager.LoadDependencies();
    Player p;
    for (int32 reputation : {0, 9000, 21000, 41999, 42000, 42999}) {
        p.rep.values[1359] = reputation;
        assert(p.IsQuestObjectiveComplete(&q32592, objective) == (reputation >= 42000));
    }
    for (unsigned mask = 0; mask < 4; ++mask) {
        p.rewarded.clear();
        if (mask & 1) p.rewarded.insert(32591);
        if (mask & 2) p.rewarded.insert(32592);
        assert(p.SatisfyQuestDependentPreviousQuests(&forge, false) == (mask == 3));
    }
    p.rewarded.clear();
    assert(!p.SatisfyQuestDependentPreviousQuests(&q32592, false));
    p.rewarded.insert(32590);
    assert(p.SatisfyQuestDependentPreviousQuests(&q32592, false));
    std::cout << "PASS: reputation boundaries, both predecessor orders, prerequisite gate\n";
}
'''
cpp = prefix + objective_enum + methods + '''
void ObjectMgr::LoadDependencies() {
    for (auto const& pair : _questTemplates) {
        Quest* qinfo = pair.second;
''' + loader + '\n    }\n}\n' + main
with tempfile.TemporaryDirectory(prefix='wrathion-32592-test-') as tmp:
    source, binary = Path(tmp) / 'test.cpp', Path(tmp) / 'test'
    source.write_text(cpp)
    subprocess.run(['c++', '-std=c++17', '-O0', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: restored database fixture and local MoP DBC mappings')
