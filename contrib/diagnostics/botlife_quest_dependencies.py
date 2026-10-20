"""Read-only prerequisite prefilter. Native CanTakeQuest is still authoritative.

Mirrors ObjectMgr's positive PrevQuestID/reverse NextQuestID edges and Player's
dependency/exclusive-group checks for the nonrepeatable quests in our shortlist.
Conditions, reputation, scripts, daily/seasonal history and live state are not
reimplemented here. Ambiguous negative-group alternatives fail conservatively.
"""


class QuestDependencies:
    def __init__(self, rows):
        # rows: quest ID, signed PrevQuestID, NextQuestID, signed ExclusiveGroup.
        self.quests = {int(qid): (int(prev), int(next_id), int(group))
                       for qid, prev, next_id, group in rows}
        self.previous = {qid: set() for qid in self.quests}
        self.groups = {}
        for qid, (prev, next_id, group) in self.quests.items():
            if prev > 0 and prev in self.quests:
                self.previous[qid].add(prev)
            if next_id in self.quests:
                self.previous[next_id].add(qid)
            if group:
                self.groups.setdefault(group, set()).add(qid)

    def rejection(self, qid, rewarded, active):
        """active maps native quest IDs to status (INCOMPLETE=3, COMPLETE=1)."""
        if qid not in self.quests:
            return "missing-template"
        if qid in rewarded:
            return "already-rewarded"
        if active.get(qid) == 3:
            return None  # Resume an existing quest, do not re-run acceptance.
        if active.get(qid, 0):
            return "not-incomplete"
        prev, _, group = self.quests[qid]
        if prev > 0 and prev not in rewarded:
            return "previous-not-rewarded"
        if prev < 0 and active.get(-prev) != 3:
            return "previous-not-active"

        dependencies = self.previous[qid]
        if dependencies:
            satisfied = False
            for prerequisite in dependencies & rewarded:
                previous_group = self.quests[prerequisite][2]
                if previous_group < 0 and not self.groups[previous_group].issubset(rewarded):
                    # Native code can return false at the first rewarded member
                    # of an unfinished each-from-all group. Its unordered loader
                    # order is unavailable offline: never claim certain success.
                    return "incomplete-prerequisite-group"
                satisfied = True
            if not satisfied:
                return "dependent-previous-not-rewarded"

        if group > 0:
            for alternative in self.groups[group] - {qid}:
                if alternative in rewarded or active.get(alternative, 0):
                    return "exclusive-alternative-started"
        return None
