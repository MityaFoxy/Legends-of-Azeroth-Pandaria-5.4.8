"""Observe scheduler contracts from native lifecycle logs, without world access."""
from collections import Counter
import datetime
import re


def log_time(line):
    return datetime.datetime.strptime(line.split()[0], "%Y-%m-%d_%H:%M:%S")


class ScheduleObserver:
    def __init__(self, guids, cooldown=60):
        self.cooldown = cooldown
        self.window_start = None
        self.desync_samples = 0
        self.rows = {guid: dict(walks=0, leisure=0, outings=0, cooldown_gaps=[],
                               last_outing_end=None, combat_pauses=0, combat_resumes=0,
                               quest_selections=0, quests_started=0, quests_completed=0,
                               quest_failures=Counter(), refusals=Counter(), activity_starts=Counter(),
                               max_outing_active_ms=0, max_outing_wall_seconds=0, travel_commands=0) for guid in guids}
        self.states = {guid: dict(activity=None, paused=False, native_quest=False, selected=False, ready_executor=False,
                                 last=None, seconds=Counter(), segments=[], native_seconds=0.0, pause_reason=None,
                                 quest_active_seconds=0.0, quest_wall_seconds=0.0, outing_started=None,
                                 outing_ms=0, continuing=False) for guid in guids}

    def begin(self, when):
        if self.window_start is not None:
            raise RuntimeError("Observation window already started")
        self.window_start = when

    def population(self, population, requested):
        if population - requested:
            raise RuntimeError("Unexpected online character")
        if self.window_start is not None:
            if population != set(self.rows):
                raise RuntimeError("Configured bot disappeared during observation")
            activities = {self._activity(state) for state in self.states.values()}
            if len(activities) > 1 and "UNOBSERVED" not in activities:
                self.desync_samples += 1

    @staticmethod
    def _activity(state):
        if state["paused"]:
            return "DEATH" if state["pause_reason"] == "death" else "COMBAT"
        return state["activity"] or "UNOBSERVED"

    def _span(self, state, when):
        if self.window_start is None:
            return 0.0
        return max(0.0, (when - max(state["last"] or self.window_start, self.window_start)).total_seconds())

    def inspect(self, line):
        match = re.search(r"\b(?:guid|bot)=(\d+)|Low: (\d+)", line)
        if not match:
            return
        guid = int(match[1] or match[2])
        if guid not in self.rows:
            raise RuntimeError("Unexpected BotLife actor")
        when = log_time(line)
        row, state = self.rows[guid], self.states[guid]
        if state["last"] is not None and when < state["last"]:
            raise RuntimeError("BotLife timestamps moved backwards")
        if state["activity"] == "QUEST" and not state["paused"] and state["last"] is not None:
            state["quest_active_seconds"] += (when - state["last"]).total_seconds()
        span = self._span(state, when)
        state["seconds"][self._activity(state)] += span
        if span:
            self._append_segment(state["segments"], when - datetime.timedelta(seconds=span),
                                 when, self._activity(state))
        if state["activity"] == "QUEST":
            state["quest_wall_seconds"] += span
        if state["activity"] == "QUEST" and state["native_quest"] and not state["paused"]:
            state["native_seconds"] += span
        state["last"] = when
        measured = self.window_start is not None and when >= self.window_start
        fields = dict(re.findall(r"\b([a-z_]+)=([^\s]+)", line))

        if "BotLife quest-run " in line:
            if fields.get("event") == "start":
                state["ready_executor"] = fields.get("result") == "running"
                if measured and state["ready_executor"]:
                    row["quests_started"] += 1
            elif fields.get("event") == "finish":
                state["native_quest"] = False
                state["ready_executor"] = False
                if measured and fields.get("result") == "failed":
                    row["quest_failures"][fields.get("reason", "unknown")] += 1
                elif measured and fields.get("result") == "completed" and fields.get("rewarded") == "true":
                    row["quests_completed"] += 1
        elif "BotLife scheduled-quest " in line and fields.get("event") == "select":
            state["selected"] = "quest" in fields
            if not state["selected"]:
                state["ready_executor"] = False
            if measured:
                if state["selected"]:
                    row["quest_selections"] += 1
                else:
                    row["refusals"]["quest:" + fields.get("reason", "unknown")] += 1
        elif "transition" in fields:
            previous, following = fields["transition"].split("->")
            if previous != state["activity"]:
                raise RuntimeError("Transition does not match the active activity")
            if previous == "QUEST":
                state["outing_ms"] += int(fields["duration_ms"])
                state["continuing"] = following == "QUEST"
                if not state["continuing"]:
                    row["last_outing_end"] = when.isoformat()
                    if measured:
                        row["outings"] += 1
                        row["max_outing_active_ms"] = max(row["max_outing_active_ms"], state["outing_ms"])
                        row["max_outing_wall_seconds"] = max(row["max_outing_wall_seconds"],
                            (when - state["outing_started"]).total_seconds())
                    state["outing_ms"] = 0
                    state["outing_started"] = None
                state["quest_active_seconds"] = 0.0
            state["activity"] = None
            state["paused"] = False
        elif "BotLife bot=" in line and fields.get("event") == "start":
            if state["activity"] is not None:
                raise RuntimeError("Activity replaced without a lifecycle transition")
            activity = fields["activity"]
            if activity not in ("FREE", "QUEST", "TOWN", "REST", "WALK", "LEISURE"):
                raise RuntimeError("Unknown activity")
            if activity == "QUEST" and not state["continuing"] and row["last_outing_end"]:
                gap = (when - datetime.datetime.fromisoformat(row["last_outing_end"])).total_seconds()
                if gap + 1 < self.cooldown:  # Native log precision is one second.
                    raise RuntimeError("Outing restarted before cooldown expired")
                if measured:
                    row["cooldown_gaps"].append(gap)
            if activity == "QUEST" and not state["continuing"]:
                state["outing_started"] = when
            state["activity"] = activity
            state["native_quest"] = activity == "QUEST" and state["selected"] and state["ready_executor"]
            state["continuing"] = False
            if measured:
                row["activity_starts"][activity] += 1
        elif "BotLife bot=" in line and fields.get("event") in ("pause", "resume"):
            if fields.get("activity") != state["activity"]:
                raise RuntimeError("Pause/resume does not match the active activity")
            paused = fields["event"] == "pause"
            death_during_combat = paused and fields.get("reason") == "death" and state["pause_reason"] == "combat"
            if state["paused"] == paused and not death_during_combat:
                raise RuntimeError("Unpaired activity pause/resume")
            state["paused"] = paused
            state["pause_reason"] = fields.get("reason") if paused else None
            if measured and fields.get("reason") in ("combat", "combat-ended"):
                row["combat_pauses" if paused else "combat_resumes"] += 1
        elif fields.get("phase") == "travel" and fields.get("event") == "issued":
            if state["activity"] not in ("QUEST", "WALK", "TOWN") or state["paused"]:
                raise RuntimeError("Travel command outside an active movement activity")
            if measured:
                row["travel_commands"] += 1
        elif measured and ("BotLife walk " in line or "BotLife service " in line):
            if fields.get("result") == "failed":
                activity = fields.get("activity", "WALK")
                row["refusals"][activity + ":" + fields.get("reason", "unknown")] += 1
            elif fields.get("result") == "completed":
                completed = "WALK" if "BotLife walk " in line else fields.get("activity")
                if completed != state["activity"] or state["paused"]:
                    raise RuntimeError("Completion outside the matching active activity")
                if "BotLife walk " in line:
                    row["walks"] += 1
                elif fields.get("activity") == "LEISURE":
                    row["leisure"] += 1

    def summary(self, when):
        result = {}
        for guid, row in self.rows.items():
            state = self.states[guid]
            seconds = state["seconds"].copy()
            span = self._span(state, when)
            seconds[self._activity(state)] += span
            native = state["native_seconds"]
            if state["activity"] == "QUEST" and state["native_quest"] and not state["paused"]:
                native += span
            total = sum(seconds.values())
            quest_wall = state["quest_wall_seconds"] + (span if state["activity"] == "QUEST" else 0)
            ongoing = state["quest_active_seconds"]
            if state["activity"] == "QUEST" and not state["paused"] and state["last"] is not None:
                ongoing += max(0.0, (when - state["last"]).total_seconds())
            result[guid] = dict(row, activity=self._activity(state),
                                seconds=dict(seconds), observed_seconds=total,
                                quest_fraction=quest_wall / total if total else 0,
                                quest_wall_seconds=quest_wall,
                                native_quest_seconds=native,
                                max_outing_active_ms=max(row["max_outing_active_ms"],
                                                         state["outing_ms"] + int(ongoing * 1000)),
                                max_outing_wall_seconds=max(row["max_outing_wall_seconds"],
                                    max(0.0, (when - state["outing_started"]).total_seconds())
                                    if state["outing_started"] is not None else 0))
        return result

    @staticmethod
    def _append_segment(segments, start, end, activity):
        if segments and segments[-1][1] == start and segments[-1][2] == activity:
            segments[-1] = (segments[-1][0], end, activity)
        else:
            segments.append((start, end, activity))

    def desync_seconds(self, when):
        """Intersect the two event timelines; short walks can fall between SQL samples."""
        if len(self.states) != 2 or self.window_start is None:
            return 0.0
        timelines = []
        for state in self.states.values():
            segments = state["segments"].copy()
            span = self._span(state, when)
            if span:
                self._append_segment(segments, when - datetime.timedelta(seconds=span),
                                     when, self._activity(state))
            timelines.append(segments)
        left, right = timelines
        i = j = 0
        total = 0.0
        while i < len(left) and j < len(right):
            start, end = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
            if end > start and left[i][2] != right[j][2] and "UNOBSERVED" not in (left[i][2], right[j][2]):
                total += (end - start).total_seconds()
            if left[i][1] <= right[j][1]:
                i += 1
            else:
                j += 1
        return total

    def validate(self, when, profile):
        for row in self.summary(when).values():
            if (row["walks"] < profile["min_walks"] or row["leisure"] < profile["min_leisure"] or
                    len(row["cooldown_gaps"]) < profile["min_cooldown_gaps"]):
                raise RuntimeError("Missing completed walk/leisure or a verified cooldown gap")
            if row["quest_fraction"] > profile["max_quest_fraction"]:
                raise RuntimeError("Quest time share exceeds the declared profile")
            if row["max_outing_active_ms"] > profile["max_outing_active_ms"]:
                raise RuntimeError("Quest outing exceeds the declared profile")
            if row["seconds"].get("UNOBSERVED", 0) > profile["max_unobserved_seconds"]:
                raise RuntimeError("Incomplete activity coverage")
        if len(self.rows) == 2 and self.desync_seconds(when) < profile["min_desync_seconds"]:
            raise RuntimeError("No observed interval with different bot activities")
