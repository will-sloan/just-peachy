"""Frozen-loop regression and clock-corruption checks. README_D1_FRAME_CLOCK_V2.md."""
from copy import deepcopy
from dataclasses import replace
import json
import struct
import unittest

import test_d1_lane_components as fixtures
import test_review_d1_components as original
from review_d1_components import scan_events as old_scan
from review_d1_frame_clock_v2 import scan_events

STEP = struct.unpack('<f', struct.pack('<f', .01))[0]


class OriginalCorruptionTests(original.TestD1EvidenceReview):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows = deepcopy(cls.rows)
        cls.rows[0]['payload']['native_output_sec_per_frame'] = .01

    def scan(self, rows=None, summary=None):
        return scan_events(self.rows if rows is None else rows, self.wave,
                           self.summary if summary is None else summary,
                           self.namespace, self.timeline)


class FrameStepNative(fixtures.NativeStub):
    def manifest(self):
        return dict(super().manifest(), native_output_sec_per_frame=STEP)

    def _update(self, target, final):
        return replace(super()._update(target, final), seconds_per_frame=STEP)


class LongNativeClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TestD1ActualLoop.setUpClass()
        f = fixtures.TestD1ActualLoop()
        capture = f.setup_capture(frames=55 * 16000 + 5)
        f.resident.native = FrameStepNative(f.Update, f.np)
        cls.summary = capture.run_capture(f.encoder)
        cls.rows = [json.loads(line) for line in f.log.getvalue().splitlines()]
        cls.wave, cls.namespace = f.wave, f.encoder.namespace
        from app.n2_pipeline import ActivityTimeline
        cls.timeline = ActivityTimeline

    def scan(self, rows=None):
        return scan_events(self.rows if rows is None else rows, self.wave,
                           self.summary, self.namespace, self.timeline)

    def test_long_native_interval_reproduces_original_failure_and_passes(self):
        with self.assertRaisesRegex(ValueError, 'Numeric clock/source'):
            old_scan(self.rows, self.wave, self.summary, self.namespace, self.timeline)
        result = self.scan()
        self.assertEqual(result['native_frames'], 5501)
        self.assertGreater(result['embeddings'], 90)

    def test_clock_manifest_missing_nan_or_arbitrary_step_rejected(self):
        for step in [None, float('nan'), .0100000001, .02, True]:
            with self.subTest(step=step):
                rows = deepcopy(self.rows)
                rows[0]['payload']['native_output_sec_per_frame'] = step
                with self.assertRaisesRegex(ValueError, 'Unqualified native frame'):
                    self.scan(rows)

    def test_frame_step_cannot_drift_from_manifest(self):
        rows = deepcopy(self.rows)
        next(r for r in rows if r['event_type'] == 'n2_diarization_frames')['payload']['frame_step_sec'] = .01
        with self.assertRaisesRegex(ValueError, 'interval changed'):
            self.scan(rows)

    def test_decimal_endpoint_cannot_replace_late_native_endpoint(self):
        rows = deepcopy(self.rows)
        r = next(r for r in rows if r['event_type'] == 'n2_diarization_frames'
                 and r['payload']['native_frame_end_sec'] > 50)
        r['payload']['native_frame_end_sec'] += 2e-6
        with self.assertRaisesRegex(ValueError, 'Numeric clock/source'):
            self.scan(rows)

    def test_tail_overhang_corruption_rejected(self):
        rows = deepcopy(self.rows)
        r = next(r for r in reversed(rows) if r['event_type'] == 'n2_diarization_frames')
        r['payload']['endpoint_overhang_sec'] += 2e-6
        with self.assertRaisesRegex(ValueError, 'Numeric clock/source'):
            self.scan(rows)

    def test_source_clock_tolerance_unchanged(self):
        rows = deepcopy(self.rows)
        next(r for r in rows if r['event_type'] == 'component_d1_dispatch')['source_time_sec'] += 2e-6
        with self.assertRaisesRegex(ValueError, 'Numeric clock/source'):
            self.scan(rows)


if __name__ == '__main__':
    unittest.main()
