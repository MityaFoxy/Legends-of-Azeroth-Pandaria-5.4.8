#!/usr/bin/env python3
"""Observer acceptance must reflect native lifecycle, time and roster evidence."""
import datetime
import argparse
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(sys.argv.pop(1)) / "contrib/diagnostics"))
from botlife_schedule_observer import ScheduleObserver
from botlife_schedule_smoke import parse_quest_ids, profile_settings, verify_candidate_roster


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.observer = ScheduleObserver([1138])
        self.observer.begin(self.when(0))

    @staticmethod
    def when(seconds):
        return datetime.datetime(2026, 11, 24) + datetime.timedelta(seconds=seconds)

    def emit(self, seconds, body):
        stamp = self.when(seconds).strftime("%Y-%m-%d_%H:%M:%S")
        self.observer.inspect(f"{stamp} INFO [playerbots.botlife] BotLife {body}")

    def life(self, seconds, suffix, guid=1138):
        self.emit(seconds, f"bot=Test guid=GUID Full: 0x123 Type: Player Low: {guid} {suffix}")

    def start(self, seconds, activity, guid=1138, budget=30000):
        self.life(seconds, f"activity={activity} event=start reason=test budget_ms={budget}", guid)

    def transition(self, seconds, before, after, duration, guid=1138):
        self.life(seconds, f"transition={before}->{after} reason=test result=completed duration_ms={duration}", guid)

    def row(self, seconds):
        return self.observer.summary(self.when(seconds))[1138]

    def test_cooldown_uses_server_time_and_full_guid(self):
        self.start(0, "QUEST")
        self.transition(1, "QUEST", "LEISURE", 1000)
        self.start(1, "LEISURE")
        self.transition(61, "LEISURE", "QUEST", 60000)
        self.start(61, "QUEST")
        self.assertEqual(self.row(61)["cooldown_gaps"], [60])

    def test_early_restart_rejected(self):
        self.start(0, "QUEST")
        self.transition(1, "QUEST", "LEISURE", 1000)
        self.start(1, "LEISURE")
        self.transition(31, "LEISURE", "QUEST", 30000)
        with self.assertRaisesRegex(RuntimeError, "cooldown"):
            self.start(31, "QUEST")

    def test_quest_continuation_is_one_outing(self):
        self.start(0, "QUEST")
        self.transition(10, "QUEST", "QUEST", 10000)
        self.start(10, "QUEST")
        self.transition(20, "QUEST", "LEISURE", 10000)
        self.start(20, "LEISURE")
        row = self.row(20)
        self.assertEqual((row["outings"], row["max_outing_active_ms"]), (1, 20000))
        self.assertEqual(row["cooldown_gaps"], [])

    def test_probe_is_not_executed_quest_work(self):
        self.emit(0, "scheduled-quest guid=1138 event=select result=none reason=no-eligible-candidate")
        self.start(0, "QUEST")
        self.transition(10, "QUEST", "LEISURE", 10000)
        self.start(10, "LEISURE")
        self.transition(70, "LEISURE", "QUEST", 60000)
        self.emit(70, "quest-run guid=1138 quest=216 event=start resumed=false result=running")
        self.emit(70, "scheduled-quest guid=1138 event=select quest=216 budget_ms=30000")
        self.start(70, "QUEST")
        self.transition(80, "QUEST", "LEISURE", 10000)
        self.start(80, "LEISURE")
        row = self.row(80)
        self.assertEqual(row["native_quest_seconds"], 10)
        self.assertEqual(row["quest_selections"], 1)
        self.assertEqual(row["refusals"], {"quest:no-eligible-candidate": 1})
        self.assertEqual(row["quest_fraction"], 0.25)

    def test_selected_quest_with_failed_start_is_not_native_execution(self):
        self.emit(0, "quest-run guid=1138 quest=13943 event=start resumed=false result=failed")
        self.emit(0, "scheduled-quest guid=1138 event=select quest=13943 budget_ms=30000")
        self.start(0, "QUEST")
        self.emit(1, "quest-run guid=1138 quest=13943 event=finish result=failed rewarded=false reason=reward-choice-unsupported")
        self.transition(1, "QUEST", "LEISURE", 211)
        self.start(1, "LEISURE")
        row = self.row(10)
        self.assertEqual((row["quest_selections"], row["quests_started"], row["native_quest_seconds"]), (1, 0, 0))
        self.assertEqual(row["quest_failures"], {"reward-choice-unsupported": 1})

    def test_native_quest_completion_requires_reward_evidence(self):
        for rewarded in (False, True):
            with self.subTest(rewarded=rewarded):
                self.setUp()
                self.emit(0, "quest-run guid=1138 quest=216 event=start resumed=false result=running")
                self.emit(0, "scheduled-quest guid=1138 event=select quest=216 budget_ms=30000")
                self.start(0, "QUEST")
                self.emit(10, f"quest-run guid=1138 quest=216 event=finish result=completed rewarded={str(rewarded).lower()} reason=test")
                self.assertEqual(self.row(10)["quests_completed"], int(rewarded))

    def test_combat_time_separated_from_active_quest_time(self):
        self.emit(0, "quest-run guid=1138 quest=216 event=start resumed=false result=running")
        self.emit(0, "scheduled-quest guid=1138 event=select quest=216 budget_ms=30000")
        self.start(0, "QUEST")
        self.life(10, "activity=QUEST event=pause reason=combat duration_ms=10000")
        self.life(40, "activity=QUEST event=resume reason=combat-ended duration_ms=10000")
        self.transition(50, "QUEST", "LEISURE", 20000)
        self.start(50, "LEISURE")
        row = self.row(50)
        self.assertEqual((row["seconds"]["QUEST"], row["seconds"]["COMBAT"]), (20, 30))
        self.assertEqual(row["native_quest_seconds"], 20)
        self.assertEqual((row["quest_wall_seconds"], row["quest_fraction"]), (50, 1))
        self.assertEqual((row["combat_pauses"], row["combat_resumes"]), (1, 1))
        self.assertEqual(row["max_outing_active_ms"], 20000)
        self.assertEqual(row["max_outing_wall_seconds"], 50)

    def test_death_is_separate_from_combat(self):
        self.start(0, "WALK")
        self.life(10, "activity=WALK event=pause reason=death duration_ms=10000")
        self.life(40, "activity=WALK event=resume reason=resurrected duration_ms=10000")
        self.assertEqual(self.row(40)["seconds"]["DEATH"], 30)
        self.assertEqual(self.row(40)["combat_pauses"], 0)

    def test_death_can_replace_an_existing_combat_pause(self):
        self.start(0, "QUEST")
        self.life(10, "activity=QUEST event=pause reason=combat duration_ms=10000")
        self.life(20, "activity=QUEST event=pause reason=death duration_ms=10000")
        self.life(40, "activity=QUEST event=resume reason=resurrected duration_ms=10000")
        row = self.row(40)
        self.assertEqual((row["seconds"]["QUEST"], row["seconds"]["COMBAT"], row["seconds"]["DEATH"]), (10, 10, 20))

    def test_common_window_clips_early_login_without_inventing_completion(self):
        self.observer = ScheduleObserver([1138])
        self.start(0, "LEISURE")
        self.observer.begin(self.when(20))
        self.emit(40, "service guid=1138 activity=LEISURE result=completed reason=leisure-completed")
        self.assertEqual(self.row(50)["observed_seconds"], 30)
        self.assertEqual(self.row(50)["seconds"]["LEISURE"], 30)
        self.assertEqual(self.row(50)["leisure"], 1)

    def test_failed_walk_does_not_count_as_completed(self):
        self.start(0, "WALK")
        self.emit(1, "walk guid=1138 event=finish result=failed reason=walk-unsafe-route")
        self.assertEqual(self.row(1)["walks"], 0)
        self.assertEqual(self.row(1)["refusals"], {"WALK:walk-unsafe-route": 1})
        self.life(1, "transition=WALK->LEISURE reason=walk-failed result=failed duration_ms=1000")
        self.start(1, "LEISURE")
        self.transition(61, "LEISURE", "WALK", 60000)
        self.start(61, "WALK")
        self.emit(62, "walk guid=1138 event=finish result=completed reason=walk-arrived")
        self.assertEqual(self.row(62)["walks"], 1)

    def test_completed_walk_requires_matching_active_activity(self):
        self.start(0, "LEISURE")
        with self.assertRaisesRegex(RuntimeError, "Completion"):
            self.emit(1, "walk guid=1138 event=finish result=completed reason=walk-arrived")

    def test_roster_disappearance_and_foreign_actor_rejected(self):
        self.observer.population({1138}, {1138})
        with self.assertRaisesRegex(RuntimeError, "disappeared"):
            self.observer.population(set(), {1138})
        with self.assertRaisesRegex(RuntimeError, "Unexpected online"):
            self.observer.population({9, 1138}, {1138})
        with self.assertRaisesRegex(RuntimeError, "Unexpected BotLife"):
            self.start(0, "WALK", guid=9)

    def test_movement_cannot_leak_into_leisure_or_paused_activity(self):
        self.start(0, "WALK")
        self.emit(1, "bot=1138 phase=travel event=issued spline=4")
        self.life(2, "activity=WALK event=pause reason=combat duration_ms=2000")
        with self.assertRaisesRegex(RuntimeError, "Travel command"):
            self.emit(3, "bot=1138 phase=travel event=issued spline=5")
        self.life(4, "activity=WALK event=resume reason=combat-ended duration_ms=2000")
        self.transition(5, "WALK", "LEISURE", 3000)
        self.start(5, "LEISURE")
        with self.assertRaisesRegex(RuntimeError, "Travel command"):
            self.emit(6, "bot=1138 phase=travel event=issued spline=6")
        self.assertEqual(self.row(6)["travel_commands"], 1)

    def test_summary_does_not_double_count_or_advance_log_cursor(self):
        self.start(0, "LEISURE")
        self.assertEqual(self.row(20), self.row(20))
        self.emit(15, "service guid=1138 activity=LEISURE result=completed reason=leisure-completed")
        self.assertEqual(self.row(20)["seconds"]["LEISURE"], 20)

    def test_profile_rejects_ongoing_overlong_outing_and_time_share(self):
        self.start(0, "QUEST")
        profile = dict(min_walks=0, min_leisure=0, min_cooldown_gaps=0, min_desync_seconds=0,
                       max_quest_fraction=1, max_outing_active_ms=32000, max_unobserved_seconds=1)
        with self.assertRaisesRegex(RuntimeError, "outing exceeds"):
            self.observer.validate(self.when(40), profile)
        profile["max_outing_active_ms"] = 60000
        profile["max_quest_fraction"] = 0.5
        with self.assertRaisesRegex(RuntimeError, "time share"):
            self.observer.validate(self.when(40), profile)

    def test_desync_requires_two_observed_activities(self):
        self.observer = ScheduleObserver([584, 1138])
        self.observer.begin(self.when(0))
        self.start(0, "LEISURE", guid=584)
        self.start(0, "LEISURE")
        self.observer.population({584, 1138}, {584, 1138})
        self.assertEqual(self.observer.desync_samples, 0)
        self.transition(10, "LEISURE", "WALK", 10000)
        self.start(10, "WALK")
        self.observer.population({584, 1138}, {584, 1138})
        self.assertEqual(self.observer.desync_samples, 1)

    def test_short_walk_between_population_samples_still_proves_desync(self):
        self.observer = ScheduleObserver([584, 1138])
        self.observer.begin(self.when(0))
        self.start(0, "LEISURE", guid=584)
        self.start(0, "LEISURE")
        self.observer.population({584, 1138}, {584, 1138})
        self.transition(5, "LEISURE", "WALK", 5000)
        self.start(5, "WALK")
        self.transition(10, "WALK", "LEISURE", 5000)
        self.start(10, "LEISURE")
        self.observer.population({584, 1138}, {584, 1138})
        self.assertEqual(self.observer.desync_samples, 0)
        self.assertEqual(self.observer.desync_seconds(self.when(15)), 5)
        self.assertEqual(self.observer.desync_seconds(self.when(15)), 5)

    def test_progress_requires_a_running_quest_and_increasing_count(self):
        self.emit(0, "quest-run guid=1138 quest=216 event=start resumed=false result=running")
        self.emit(0, "scheduled-quest guid=1138 event=select quest=216 budget_ms=30000")
        self.start(0, "QUEST")
        for when, count in ((1, 0), (2, 1), (3, 1), (4, 2)):
            self.emit(when, f"quest-run guid=1138 quest=216 event=progress objective=4 count={count} required=8")
        self.assertEqual(self.row(4)["objective_progress_events"], {"216:4": 2})
        self.assertEqual(self.row(4)["objective_counts"], {"216:4": 2})
        self.transition(5, "QUEST", "LEISURE", 5000)
        self.start(5, "LEISURE")
        with self.assertRaisesRegex(RuntimeError, "outside a running quest"):
            self.emit(6, "quest-run guid=1138 quest=216 event=progress objective=4 count=3 required=8")

    def quest_life_trace(self, progress):
        profile, quest_ms, cooldown_ms = profile_settings("quest-life")
        self.observer = ScheduleObserver([1138], cooldown=cooldown_ms / 1000)
        self.observer.begin(self.when(0))
        self.emit(0, "quest-run guid=1138 quest=216 event=start resumed=false result=running")
        self.emit(0, f"scheduled-quest guid=1138 event=select quest=216 budget_ms={quest_ms}")
        self.start(0, "QUEST", budget=quest_ms)
        if progress:
            self.emit(20, "quest-run guid=1138 quest=216 event=progress objective=4 count=1 required=8")
        self.emit(120, "quest-run guid=1138 quest=216 event=finish result=failed rewarded=false reason=budget-expired")
        self.life(120, "transition=QUEST->LEISURE reason=quest-failed result=failed duration_ms=120000")
        self.start(120, "LEISURE")
        for when in range(150, 421, 30):
            self.emit(when, "service guid=1138 activity=LEISURE result=completed reason=leisure-completed")
            self.transition(when, "LEISURE", "QUEST" if when == 420 else "LEISURE", 30000)
            if when < 420:
                self.start(when, "LEISURE")
        self.emit(420, "quest-run guid=1138 quest=216 event=start resumed=true result=running")
        self.emit(420, f"scheduled-quest guid=1138 event=select quest=216 budget_ms={quest_ms}")
        self.start(420, "QUEST", budget=quest_ms)
        return profile

    def test_quest_life_profile_requires_progress_not_just_running_time(self):
        profile = self.quest_life_trace(progress=False)
        with self.assertRaisesRegex(RuntimeError, "actual objective progress"):
            self.observer.validate(self.when(450), profile)

    def test_real_progress_then_independent_leisure_and_cooldown_pass(self):
        profile = self.quest_life_trace(progress=True)
        self.observer.validate(self.when(450), profile)
        row = self.row(450)
        self.assertEqual(row["cooldown_gaps"], [300])
        self.assertEqual(row["seconds"]["LEISURE"], 300)
        self.assertEqual(row["native_quest_seconds"], 150)


class AllowlistTests(unittest.TestCase):
    def test_shared_allowlist_is_normalized(self):
        self.assertEqual(parse_quest_ids("8320,216,216"), [216, 8320])

    def test_bad_allowlist_fails_before_launch(self):
        for value in ("", "0", "-1", "216,", "a", str(2**32), ",".join(map(str, range(1, 34)))):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                parse_quest_ids(value)

    def test_full_prefilter_must_confirm_each_bot_and_each_quest(self):
        text = "distance\tguid\tname\tclass\tlevel\tmap\tquest\n27\t101\tAranne\t8\t22\t1\t216\n52\t26\tIbrand\t10\t60\t1\t8320\n"
        self.assertEqual(verify_candidate_roster(text, [26, 101], [216, 8320]),
                         [dict(guid=26, quest_id=8320), dict(guid=101, quest_id=216)])
        for guids, quests in (([26, 1138], [216, 8320]), ([26, 101], [216, 13943])):
            with self.assertRaisesRegex(RuntimeError, "did not confirm"):
                verify_candidate_roster(text, guids, quests)

    def test_malformed_prefilter_cannot_authorize_launch(self):
        for text in ("", "unexpected header", "distance\tguid\tname\tclass\tlevel\tmap\tquest\ninvalid"):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                verify_candidate_roster(text, [26], [8320])


if __name__ == "__main__":
    unittest.main()
