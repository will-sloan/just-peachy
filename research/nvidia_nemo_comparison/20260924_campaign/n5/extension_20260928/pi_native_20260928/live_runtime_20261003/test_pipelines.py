"""Synthetic component tests only; README_PIPELINES.md contains registered launch commands."""
import ctypes
from dataclasses import replace
import unittest

from correction import CaptionLedger, SampleInterval, SpeakerSpan, align_speakers
from profiles import (Geometry, ModelLimits, RuntimeSelection, SessionPolicy, catalog,
                      effective_c_abi_geometry, get_profile, validate_geometry)
from telemetry import BoundedRefinementQueue, RollingTelemetry
from nemotron_binding import copy_new_probabilities, expected_frames


def interval(start, end, session="test-session", source="same-audio"):
    return SampleInterval(session, source, start, end, 100)


def span(start, end, speaker, **kwargs):
    return SpeakerSpan(interval(start, end, **kwargs), speaker)


class ProfilesTests(unittest.TestCase):
    def test_independent_backend_source_product(self):
        for source in ("live", "saved"):
            for embedding in ("redimnet", "titanet", "anonymous"):
                for diarizer in ("pyannote", "nemotron"):
                    selection = RuntimeSelection(diarizer, embedding, source,
                        "current_delayed" if diarizer == "nemotron" else None)
                    self.assertEqual(selection.validate()["input_source"], source)

    def test_exact_recipes_and_experimental_gate(self):
        self.assertEqual(get_profile("current_delayed").geometry, Geometry(264, 1, 1, 0, 264, 188, "v3-offline"))
        for name, seconds in (("official_low", 1.04), ("official_very_low", .64), ("official_ultra_low", .32)):
            profile = get_profile(name)
            self.assertAlmostEqual(profile.geometry.nominal_input_seconds, seconds)
            with self.assertRaises(ValueError):
                RuntimeSelection("nemotron", "anonymous", "live", name).validate()
        self.assertTrue(all(not row["native_pass_claimed"] for row in catalog()))
        self.assertTrue(all(row["parameter_validation"]["status"] == "SOURCE_PARAMETER_RULES_VALIDATED"
                            for row in catalog()))
        compact = get_profile("candidate_3_compact")
        self.assertEqual(compact.geometry, Geometry(37, 1, 0, 40, 128, 40))
        self.assertAlmostEqual(compact.geometry.nominal_input_seconds, 3.04)
        self.assertEqual(validate_geometry(compact.geometry)["sequence_frames"], 206)
        with self.assertRaises(ValueError):
            RuntimeSelection("nemotron", "anonymous", "saved", compact.id).validate()

    def test_actual_native_constraints_and_c_abi_zero_trap(self):
        for bad in (Geometry(0, 1), Geometry(9, 4, spkcache_frames=15),
                    Geometry(4800, 1), Geometry(9, 0), Geometry(9, 1, fifo_frames=0)):
            with self.assertRaises(ValueError):
                validate_geometry(bad)
        requested = Geometry(9, 0, fifo_frames=0)
        self.assertEqual(effective_c_abi_geometry(requested).fifo_frames, 80)
        self.assertEqual(effective_c_abi_geometry(requested).right_context_frames, 1)
        self.assertEqual(validate_geometry(Geometry(1, 1, fifo_frames=1, spkcache_frames=16))["minimum_cache_frames"], 16)
        with self.assertRaises(ValueError):
            validate_geometry(Geometry(1, 1, spkcache_frames=16), ModelLimits(silence_frames_per_speaker=3))

    def test_session_policy_not_intrinsic_five_minute_counter(self):
        self.assertEqual(SessionPolicy().maximum_samples(), 4800000)
        policy = SessionPolicy(3600, True, max_drain_seconds=1800)
        self.assertFalse(policy.expired(300))
        self.assertTrue(policy.expired(3600))
        self.assertEqual(policy.total_deadline_seconds, 5580)
        with self.assertRaises(ValueError):
            SessionPolicy(3600).validate()
        with self.assertRaises(ValueError):
            SessionPolicy(300, True).validate()


class CorrectionTests(unittest.TestCase):
    def test_permutation_mapping_does_not_use_slot_names(self):
        reference = [span(0, 100, "A"), span(100, 200, "B")]
        self.assertEqual(align_speakers(reference, [span(0, 100, "B"), span(100, 200, "A")],
                                       minimum_overlap_samples=8), {"A": "B", "B": "A"})
        ambiguous = [span(0, 200, "x"), span(0, 200, "y")]
        self.assertEqual(align_speakers(reference, ambiguous, minimum_overlap_samples=8), {})
        with self.assertRaises(ValueError):
            align_speakers(reference, [span(0, 100, "A", source="different-audio")])

    def test_text_first_revision_same_id_exact_provenance(self):
        ledger = CaptionLedger("test-session", "same-audio", sample_rate=100)
        ledger.advance(200)
        added = ledger.add_caption(1, interval(80, 120), "Text is immediately visible.")
        self.assertEqual(added[0]["speaker"], "unknown")
        self.assertEqual(added[0]["event"], "caption_added")
        ledger.apply_fast([span(0, 100, "raw0"), span(100, 200, "raw1")])
        events = ledger.apply_refinement("independent-pass", [span(0, 80, "raw1"), span(80, 200, "raw0")])
        revised = [event for event in events if event["event"] == "caption_revised"][0]
        self.assertEqual(revised["caption_id"], added[0]["caption_id"])
        self.assertEqual(revised["speaker"], "speaker-2")
        self.assertEqual(revised["provenance"]["sample_evidence"],
                         [{"local_speaker": "raw0", "start_sample": 80, "end_sample": 120}])
        self.assertEqual(events[0]["event"], "speaker_alignment")
        self.assertEqual(events[0]["alignment_id"], revised["provenance"]["alignment_id"])
        self.assertEqual(ledger.add_caption(1, interval(80, 120), "Text is immediately visible."), [])
        self.assertEqual(ledger.apply_refinement("retry", [span(0, 80, "raw1"), span(80, 200, "raw0")]), [])

    def test_late_refinement_retains_fallback_and_bounds(self):
        ledger = CaptionLedger("test-session", "same-audio", sample_rate=100,
                               revision_window_seconds=1, maximum_captions=2, maximum_spans=2)
        ledger.add_caption(1, interval(0, 20), "one")
        finalized = ledger.advance(200)
        self.assertEqual(finalized[0]["status"], "fallback")
        self.assertEqual(ledger.apply_refinement("late", [span(0, 20, "r")]), [])
        self.assertEqual(ledger.dropped_refinements, 1)
        self.assertEqual(ledger.add_caption(1, interval(0, 20), "one"), [])
        for i in range(2, 10):
            ledger.add_caption(i, interval(150 + i, 160 + i), str(i))
        self.assertLessEqual(len(ledger.captions), 2)
        self.assertGreater(ledger.evicted_captions, 0)

    def test_mutating_output_cannot_change_ledger_and_clock_is_exact(self):
        ledger = CaptionLedger("test-session", "same-audio", sample_rate=100)
        event = ledger.add_caption(0, interval(0, 100), "stable")[0]
        event["interval"]["start_sample"] = 999
        self.assertEqual(next(iter(ledger.captions.values()))["interval"]["start_sample"], 0)
        with self.assertRaises(ValueError):
            ledger.apply_fast([span(0, 100, "slot", source="other")])
        with self.assertRaises(ValueError):
            ledger.apply_fast([span(0, 101, "slot")])


class TelemetryTests(unittest.TestCase):
    def test_weighted_rolling_rtf_and_bounded_history(self):
        metrics = RollingTelemetry(window_seconds=10, maximum_events=2, backlog_limit_seconds=3)
        self.assertIsNone(metrics.snapshot(0)["rolling_rtf"])
        metrics.observe(now=1, audio_seconds=1, compute_seconds=2, backlog_seconds=1)
        metrics.observe(now=2, audio_seconds=3, compute_seconds=1, backlog_seconds=4, dropped_samples=5)
        self.assertEqual(metrics.snapshot(2)["rolling_rtf"], .75)
        self.assertFalse(metrics.snapshot(2)["refinement_admissible"])
        metrics.observe(now=3, audio_seconds=1, compute_seconds=1, backlog_seconds=2)
        self.assertEqual(len(metrics.events), 2)
        self.assertEqual(metrics.snapshot(3)["evicted_events"], 1)
        self.assertIsNone(metrics.snapshot(20)["rolling_rtf"])
        self.assertEqual(metrics.snapshot(20)["dropped_samples"], 5)

    def test_nonblocking_refinement_queue_expiry_and_overload(self):
        queue = BoundedRefinementQueue(maximum_jobs=1, maximum_job_bytes=16)
        self.assertTrue(queue.offer(b"job", now=0, deadline=2))
        self.assertFalse(queue.offer(b"overflow", now=1, deadline=2))
        self.assertIsNone(queue.take(3))
        self.assertEqual((queue.dropped_full, queue.dropped_late), (1, 1))
        self.assertFalse(queue.offer(b"work", now=3, deadline=4, refinement_admissible=False))
        self.assertEqual(queue.dropped_backlog, 1)


class NativeCopyTests(unittest.TestCase):
    def test_workspace_reuse_preserves_all_new_rows_and_compaction(self):
        import numpy as np
        class FakeApi:
            def __init__(self):
                self.base = 0
                self.count = 3
                self.rows = np.arange(40, dtype=np.float32).reshape(5, 8) / 40
            def nemo_speech_diar_frame_count(self, stream): return self.count
            def nemo_speech_diar_frame_probs_start(self, stream): return self.base
            def nemo_speech_diar_frame_probs(self, stream, pointer, size):
                target = np.ctypeslib.as_array(pointer, shape=(size,))
                target[:] = self.rows[self.base:self.count].ravel()
                return 0
        api = FakeApi()
        workspace = np.empty((100, 8), dtype=np.float32)
        check = lambda status: self.assertEqual(status, 0)
        _, _, first = copy_new_probabilities(np, api, None, workspace, first=0, maximum_frames=100, check=check)
        original = first.copy()
        api.base, api.count = 2, 5
        _, base, second = copy_new_probabilities(np, api, None, workspace, first=3, maximum_frames=100, check=check)
        np.testing.assert_array_equal(second, api.rows[3:5])
        np.testing.assert_array_equal(first, original)
        self.assertFalse(second.flags.writeable)
        self.assertEqual(base, 2)
        api.base = 4
        with self.assertRaises(RuntimeError):
            copy_new_probabilities(np, api, None, workspace, first=3, maximum_frames=100, check=check)

    def test_endpoint_policy_and_bad_native_probabilities(self):
        self.assertEqual(expected_frames(0, 1000), 0)
        self.assertEqual(expected_frames(160, 1000), 2)
        with self.assertRaises(ValueError):
            expected_frames(1001, 1000)
        import numpy as np
        class InvalidApi:
            def nemo_speech_diar_frame_count(self, stream): return 1
            def nemo_speech_diar_frame_probs_start(self, stream): return 0
            def nemo_speech_diar_frame_probs(self, stream, pointer, size):
                np.ctypeslib.as_array(pointer, shape=(size,))[:] = np.nan
                return 0
        with self.assertRaises(RuntimeError):
            copy_new_probabilities(np, InvalidApi(), None, np.empty((10, 8), np.float32),
                                   first=0, maximum_frames=10, check=lambda value: None)


if __name__ == "__main__":
    unittest.main()
