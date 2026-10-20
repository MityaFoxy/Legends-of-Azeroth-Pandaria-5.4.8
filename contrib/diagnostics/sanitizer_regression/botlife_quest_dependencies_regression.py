#!/usr/bin/env python3
"""Offline prefilter parity for native dependency edges and signed groups."""
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

root = pathlib.Path(sys.argv.pop(1))
compiler = sys.argv.pop(1)
sys.path.insert(0, str(root / "contrib/diagnostics"))
from botlife_quest_dependencies import QuestDependencies


class DependencyTests(unittest.TestCase):
    def test_prefilter_against_actual_native_dependency_functions(self):
        player = (root / "src/server/game/Entities/Player/Player.cpp").read_text()
        native = player[player.index("bool Player::SatisfyQuestDependentQuests("):
                        player.index("bool Player::SatisfyQuestClass(")]
        native += player[player.index("bool Player::SatisfyQuestExclusiveGroup("):
                         player.index("bool Player::SatisfyQuestDay(")]
        source = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <map>
#include <set>
#include <vector>
#include <cstdlib>
using uint32=uint32_t;
#define ASSERT(x) assert(x)
#define TC_LOG_DEBUG(...) ((void)0)
constexpr int QUEST_ERR_NONE=0, QUEST_STATUS_NONE=0, QUEST_STATUS_INCOMPLETE=3;
struct Quest {
    uint32 id; int prev, next, group; std::vector<uint32> DependentPreviousQuests;
    uint32 GetQuestId() const { return id; }
    int GetPrevQuestId() const { return prev; }
    int GetExclusiveGroup() const { return group; }
    bool IsRepeatable() const { return false; }
};
struct Manager {
    std::map<uint32,Quest> quests;
    std::multimap<int,uint32> groups;
    Quest const* GetQuestTemplate(uint32 id) { return &quests.at(id); }
    auto GetExclusiveQuestGroupBounds(int group) { return groups.equal_range(group); }
} manager;
auto* sObjectMgr=&manager;
struct Player {
    std::set<uint32> m_RewardedQuests;
    std::map<uint32,int> active;
    bool IsQuestRewarded(uint32 q) const { return m_RewardedQuests.count(q); }
    int GetQuestStatus(uint32 q) const { auto i=active.find(q); return i==active.end()?0:i->second; }
    void SendCanTakeQuestResponse(int) const {}
    bool SatisfyQuestDay(Quest const*,bool) const { return true; }
    bool SatisfyQuestWeek(Quest const*,bool) const { return true; }
    bool SatisfyQuestSeasonal(Quest const*,bool) const { return true; }
    bool SatisfyQuestDependentQuests(Quest const*,bool) const;
    bool SatisfyQuestPreviousQuest(Quest const*,bool) const;
    bool SatisfyQuestDependentPreviousQuests(Quest const*,bool) const;
    bool SatisfyQuestExclusiveGroup(Quest const*,bool);
};
'''
        source += native
        source += r'''
void check(Player bot,uint32 id,bool expected) {
    auto& quest=manager.quests.at(id);
    bool everyOrder=true;
    std::sort(quest.DependentPreviousQuests.begin(),quest.DependentPreviousQuests.end());
    do {
        bool eligible=!bot.IsQuestRewarded(id) &&
          (bot.GetQuestStatus(id)==3 || (bot.GetQuestStatus(id)==0 &&
           bot.SatisfyQuestDependentQuests(&quest,false) && bot.SatisfyQuestExclusiveGroup(&quest,false)));
        everyOrder &= eligible;
    } while(std::next_permutation(quest.DependentPreviousQuests.begin(),quest.DependentPreviousQuests.end()));
    assert(expected==everyOrder);
}
int main() {
'''
        rows = [(1, 0, 4, -7), (2, 0, 0, -7), (3, 0, 4, 0),
                (4, 0, 0, 0), (5, 1, 0, 9), (6, -1, 0, 9)]
        catalog = QuestDependencies(rows)
        for qid, prev, next_id, group in rows:
            edges = ",".join(map(str, sorted(catalog.previous[qid])))
            source += f"manager.quests.emplace({qid},Quest{{{qid},{prev},{next_id},{group},{{{edges}}}}});\n"
            if group:
                source += f"manager.groups.emplace({group},{qid});\n"
        rng = random.Random(8280)
        source += "struct Case { unsigned rewarded; int active[6]; bool expected[6]; }; Case cases[]={\n"
        for _ in range(150):
            rewarded = {qid for qid, *_ in rows if rng.randrange(2)}
            active = {qid: rng.choice((0, 1, 3, 5)) for qid, *_ in rows}
            reward_mask = sum(1 << (qid-1) for qid in rewarded)
            statuses = ",".join(map(str, active.values()))
            expected = ",".join("true" if catalog.rejection(qid, rewarded, active) is None else "false"
                                for qid, *_ in rows)
            source += "{" + str(reward_mask) + ",{" + statuses + "},{" + expected + "}},\n"
        source += r'''
};
for (auto const& sample : cases) {
    Player bot;
    for (uint32 q=1;q<=6;++q) {
        if (sample.rewarded & (1u << (q-1))) bot.m_RewardedQuests.insert(q);
        bot.active[q]=sample.active[q-1];
    }
    for (uint32 q=1;q<=6;++q) check(bot,q,sample.expected[q-1]);
}
}
'''
        with tempfile.TemporaryDirectory(prefix="loa-quest-dependencies-") as directory:
            cpp = pathlib.Path(directory) / "test.cpp"
            binary = pathlib.Path(directory) / "test"
            cpp.write_text(source)
            subprocess.run([compiler, "-std=c++20", "-O1", "-g", "-UNDEBUG",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_reverse_next_is_required_even_without_prev(self):
        catalog = QuestDependencies([(1, 0, 8280, 0), (8280, 0, 0, 0)])
        self.assertEqual(catalog.rejection(8280, set(), {}), "dependent-previous-not-rewarded")
        self.assertIsNone(catalog.rejection(8280, {1}, {}))
        self.assertIsNotNone(catalog.rejection(8280, set(), {1: 1}))

    def test_positive_and_negative_previous_have_different_status_rules(self):
        catalog = QuestDependencies([(1, 0, 0, 0), (2, 1, 0, 0), (3, -1, 0, 0)])
        self.assertIsNone(catalog.rejection(2, {1}, {}))
        self.assertIsNotNone(catalog.rejection(2, set(), {1: 3}))
        self.assertIsNone(catalog.rejection(3, set(), {1: 3}))
        self.assertIsNotNone(catalog.rejection(3, {1}, {}))
        self.assertIsNotNone(catalog.rejection(3, set(), {1: 1}))

    def test_reverse_dependencies_are_any_not_all(self):
        catalog = QuestDependencies([(1, 0, 3, 0), (2, 0, 3, 0), (3, 0, 0, 0)])
        for reward in ({1}, {2}, {1, 2}):
            self.assertIsNone(catalog.rejection(3, reward, {}))
        # Direct positive prev must ALSO be rewarded, not bypassed by reverse edge.
        catalog = QuestDependencies([(1, 0, 0, 0), (2, 0, 3, 0), (3, 1, 0, 0)])
        self.assertIsNotNone(catalog.rejection(3, {2}, {}))
        self.assertIsNone(catalog.rejection(3, {1}, {}))

    def test_each_from_all_and_ambiguous_loader_order_fail_closed(self):
        rows = [(1, 0, 4, -7), (2, 0, 0, -7), (3, 0, 4, 0), (4, 0, 0, 0)]
        for ordered in (rows, list(reversed(rows))):
            catalog = QuestDependencies(ordered)
            self.assertIsNotNone(catalog.rejection(4, {1}, {}))
            self.assertIsNone(catalog.rejection(4, {1, 2}, {}))
            self.assertIsNone(catalog.rejection(4, {3}, {}))
            self.assertIsNotNone(catalog.rejection(4, {1, 3}, {}))

    def test_positive_exclusive_group_rejects_active_complete_failed_rewarded_peer(self):
        catalog = QuestDependencies([(1, 0, 0, 5), (2, 0, 0, 5)])
        self.assertIsNone(catalog.rejection(1, set(), {}))
        for status in (1, 3, 5):
            self.assertIsNotNone(catalog.rejection(1, set(), {2: status}))
        self.assertIsNotNone(catalog.rejection(1, {2}, {}))

    def test_resume_does_not_reapply_acceptance_or_mutate_inputs(self):
        catalog = QuestDependencies([(1, 99, 0, 0)])
        active, rewarded = {1: 3}, set()
        self.assertIsNone(catalog.rejection(1, rewarded, active))
        self.assertEqual(active, {1: 3})
        self.assertEqual(rewarded, set())
        self.assertIsNotNone(catalog.rejection(1, set(), {}))
        self.assertIsNotNone(catalog.rejection(1, {1}, {1: 3}))
        self.assertIsNotNone(catalog.rejection(999, set(), {}))
        for status in (1, 5):
            self.assertIsNotNone(catalog.rejection(1, set(), {1: status}))

    def test_missing_reverse_target_does_not_create_a_template(self):
        catalog = QuestDependencies([(1, 0, 999, 0)])
        self.assertIsNone(catalog.rejection(1, set(), {}))
        self.assertIsNotNone(catalog.rejection(999, {1}, {}))


if __name__ == "__main__":
    unittest.main()
