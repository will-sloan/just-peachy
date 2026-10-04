"""Synthetic schedule contracts, never native quality evidence. See README_SPARSE_EMBEDDING.md."""
from dataclasses import replace
import unittest

from profiles import RuntimeSelection
from sparse_embedding import SparseCleanTurnSchedule, attach_sparse_schedule


class TimelineFixture:
    def __init__(self):
        self.end = 0.
        self.reserve_sec = 120.
        self.candidates = []
        self.cursor_calls = []

    def exclusive_windows(self, cursor, **kwargs):
        self.cursor_calls.append(dict(cursor))
        return [row for row in self.candidates if row[2] > cursor.get(row[0], -1)+1e-6]


class EngineFixture:
    n2_diarization = "D1"
    def __init__(self, selection):
        self.mode_configuration = dict(selection=selection.validate())
        self._n2_timeline = TimelineFixture()
        self._n2_last_query = {}
        self.events = []
    def _anonymous_native_only(self):
        return False
    def _emit(self, kind, elapsed, payload):
        self.events.append((kind, elapsed, payload))
        return "original-result"


def selection():
    return RuntimeSelection("nemotron", "redimnet", "saved", "current_delayed",
                            allow_experimental=True, embedding_schedule="sparse_clean_turn")


def receipt(candidate):
    slot, start, end, _ = candidate
    return dict(model_slot=slot, source_start_sec=start, source_end_sec=end,
                actual_selected_window=True, event_id=f"real-{slot}-{end}")


class SparseScheduleTests(unittest.TestCase):
    def test_first_clean_window_and_refresh_do_not_fabricate_evaluations(self):
        engine, logs = EngineFixture(selection()), []
        schedule = attach_sparse_schedule(engine, logs.append)
        timeline = engine._n2_timeline
        timeline.end = 2.5
        timeline.candidates = [(0, max(0., end-2), end, 0.) for end in (.5, 1., 1.5, 2., 2.5)]
        selected = timeline.exclusive_windows(engine._n2_last_query)
        self.assertEqual([row[2] for row in selected], [.5, 2.5])
        self.assertEqual(schedule.counts, dict(considered=5, scheduled=2, skipped=3, evaluated=0))
        self.assertEqual(schedule.queried, {})
        for row in selected:
            engine._n2_last_query[row[0]] = row[2]
            self.assertEqual(engine._emit("research_embedding", row[2], receipt(row)), "original-result")
        self.assertEqual(schedule.queried, {0: 2.5})
        self.assertEqual(schedule.counts["evaluated"], 2)
        self.assertEqual(len(engine.events), 2)
        self.assertEqual(timeline.exclusive_windows({}), [])
        self.assertEqual(timeline.cursor_calls[-1], {0: 2.5})

    def test_returning_turn_after_overlap_is_immediate_for_each_slot(self):
        timeline, logs = TimelineFixture(), []
        schedule = SparseCleanTurnSchedule(timeline, 2, logs.append)
        timeline.end = .5
        timeline.candidates = [(0, 0., .5, 0.)]
        self.assertEqual(schedule.exclusive_windows({}), timeline.candidates)
        schedule.evaluated(receipt(timeline.candidates[0]))
        timeline.end = .8
        timeline.candidates = []  # Real selector supplies no overlapping waveform.
        self.assertEqual(schedule.exclusive_windows({0: .5}), [])
        timeline.end = 2.
        timeline.candidates = [(0, .8, 1.3, .8), (1, 1.5, 2., 1.5)]
        self.assertEqual(schedule.exclusive_windows({0: .5}), timeline.candidates)
        self.assertEqual([item["reason"] for item in logs if item["event"] == "embedding_schedule_decision"],
                         ["first_eligible_clean_turn"]*3)

    def test_ring_eviction_does_not_requery_same_continuous_turn(self):
        timeline, logs = TimelineFixture(), []
        schedule = SparseCleanTurnSchedule(timeline, 2, logs.append)
        timeline.end = 2.5
        timeline.candidates = [(0, 0., .5, 0.), (0, .5, 2.5, 0.)]
        for row in schedule.exclusive_windows({}):
            schedule.evaluated(receipt(row))
        timeline.reserve_sec = 2.
        timeline.end = 3.
        timeline.candidates = [(0, 1., 3., 1.)]
        self.assertEqual(schedule.exclusive_windows({}), [])
        self.assertEqual(logs[-1]["reason"], "refresh_not_due")
        self.assertEqual(logs[-1]["run_start_sample"], 0)
        self.assertEqual(schedule.exclusive_windows({}), [])
        timeline.end = 4.5
        timeline.candidates = [(0, 2.5, 4.5, 2.5)]
        self.assertEqual(schedule.exclusive_windows({}), timeline.candidates)
        self.assertEqual(logs[-1]["reason"], "refresh_due")
        self.assertEqual(schedule.queried, {0: 2.5})  # Scheduled is not evaluated.

    def test_state_and_log_history_remain_bounded(self):
        timeline, logs = TimelineFixture(), []
        schedule = SparseCleanTurnSchedule(timeline, 2, logs.append, history_limit=8)
        for index in range(1, 401):
            end = index*.5
            timeline.end = end
            timeline.candidates = [(0, max(0., end-2), end, max(0., end-120))]
            for row in schedule.exclusive_windows({}):
                schedule.evaluated(receipt(row))
        self.assertEqual(len(schedule.history), 8)
        self.assertEqual(len(schedule.runs), 1)
        self.assertEqual(schedule.pending, {})
        self.assertEqual(schedule.considered, {0: 200.})
        self.assertEqual(schedule.counts["considered"], 400)
        self.assertTrue(all(v["source_end_sample"] <= 3200000 for v in logs))

    def test_explicit_selection_and_continuous_default(self):
        selected = selection()
        for bad in (replace(selected, allow_experimental=False),
                    replace(selected, diarizer="pyannote", nemotron_profile=None),
                    replace(selected, embedding="anonymous"),
                    replace(selected, embedding_refresh_seconds=float("nan"))):
            with self.assertRaises(ValueError):
                bad.validate()
        engine = EngineFixture(replace(selected, embedding_schedule="continuous"))
        original = engine._n2_timeline.exclusive_windows
        self.assertIsNone(attach_sparse_schedule(engine, lambda event: self.fail("Unexpected event")))
        self.assertEqual(engine._n2_timeline.exclusive_windows, original)
        named_titanet = replace(selected, embedding="titanet", embedding_refresh_seconds=3.)
        self.assertEqual(named_titanet.validate()["embedding_refresh_seconds"], 3.)

    def test_unmatched_or_duplicate_evaluation_is_rejected(self):
        timeline = TimelineFixture()
        schedule = SparseCleanTurnSchedule(timeline, 2, lambda event: None)
        row = (0, 0., .5, 0.)
        with self.assertRaises(ValueError):
            schedule.evaluated(receipt(row))
        timeline.end, timeline.candidates = .5, [row]
        schedule.exclusive_windows({})
        schedule.evaluated(receipt(row))
        with self.assertRaises(ValueError):
            schedule.evaluated(receipt(row))


if __name__ == "__main__":
    unittest.main()
