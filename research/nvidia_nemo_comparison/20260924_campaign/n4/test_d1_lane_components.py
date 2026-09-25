"""Frozen application D1-loop tests, no neural models. README_D1_COMPONENTS.md."""
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest

from d1_lane_components import CausalJournal, ModeledClock, capture_type


class NativeStub:
    def __init__(self, update_type, np, *, fail=False, discontinuity=False):
        self.Update = update_type
        self.np = np
        self.fail = fail
        self.discontinuity = discontinuity
        self.reset(session_id='unassigned')

    def reset(self, *, session_id):
        self.session = session_id
        self.frames = self.samples = self.finishes = 0
        self.blocks = []

    def manifest(self):
        return dict(stub=True, session_reset='independent_scene_or_session_only')

    def _update(self, target, final):
        first = self.frames
        values = self.np.zeros((target-first, 8), dtype='float32')
        for i in range(first, target):
            if i < 65: values[i-first, 0] = .9
            elif i < 85: values[i-first, :2] = .9
            elif 100 <= i < 140: values[i-first, 1] = .9
            elif i >= 140: values[i-first, 2] = .9
        self.frames = target
        now = time.perf_counter()
        return self.Update(self.session, first+(1 if self.discontinuity and target > first else 0),
            values, .01, self.samples/16000, now, now, 0., final,
            tuple(f'{self.session}:nemotron-slot-{s}' for s in range(8)))

    def push(self, block):
        if self.fail: raise RuntimeError('deliberate native failure')
        self.blocks.append(block.copy())
        self.samples += len(block)
        return self._update((self.samples//16000)*100, False)

    def finish(self):
        self.finishes += 1
        return self._update((self.samples+159)//160, True)


class ResidentStub:
    def __init__(self, native):
        self.native = native
        self.sessions = []

    def acquire_diarizer(self, session):
        self.sessions.append(session)
        self.native.reset(session_id=session)
        return self.native


class EncoderStub:
    namespace = {'model': 'unit-test-only', 'dimension': 192}
    last_embed_ms = 0.

    def __init__(self, np, *, invalid=False):
        self.np = np
        self.invalid = invalid
        self.inputs = []

    def embed(self, wave):
        self.inputs.append(wave.copy())
        value = self.np.zeros(192, dtype='float32')
        value[0] = 2. if self.invalid else 1.
        return value


class TestD1ActualLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        source = Path(os.environ.get('JP_N4_SOURCE',
            r'G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v3\prototype'))
        sys.path[:0] = [str(source), str(source/'vendor')]
        from app.n2_pipeline import N2Engine, ActivityTimeline
        from app.n2_identity import N2NameMap
        from edge_speech_pipeline.nemotron_diarization import DiarizationUpdate
        cls.Update = DiarizationUpdate
        cls.Capture = capture_type(N2Engine, ActivityTimeline, N2NameMap)

    def setup_capture(self, frames=40005, **native_options):
        self.wave = self.np.arange(frames, dtype='float32')/160000
        self.log = io.StringIO()
        self.native = NativeStub(self.Update, self.np, **native_options)
        self.resident = ResidentStub(self.native)
        self.capture = self.Capture(self.wave, self.log, self.resident, 'test-scene')
        self.encoder = EncoderStub(self.np)
        return self.capture

    def events(self, kind):
        return [x for x in map(json.loads, self.log.getvalue().splitlines()) if x['event_type'] == kind]

    def test_unchanged_loop_delivers_exact_chunks_tail_and_single_drain(self):
        c = self.setup_capture()
        result = c.run_capture(self.encoder)
        self.assertEqual([len(x) for x in self.native.blocks], [1600]*25+[5])
        self.np.testing.assert_array_equal(self.np.concatenate(self.native.blocks), self.wave)
        self.assertEqual(result['input_samples'], 40005)
        self.assertEqual(self.native.finishes, 1)
        self.assertEqual(result['source_reads'], 26)
        self.assertEqual(len(self.events('component_d1_dispatch')), 27)
        self.assertFalse(result['observed_live_latency_qualified'])

    def test_actual_application_queries_keep_contiguous_exclusive_spans(self):
        c = self.setup_capture()
        result = c.run_capture(self.encoder)
        coordinates = [(x['model_slot'], x['start_sample'], x['end_sample']) for x in result['vectors']]
        self.assertEqual(coordinates, [(0, 0, 8000), (2, 22400, 30400), (2, 22400, 38400)])
        for vector, wave in zip(result['vectors'], self.encoder.inputs):
            self.np.testing.assert_array_equal(wave, self.wave[vector['start_sample']:vector['end_sample']])
        self.assertEqual(result['telemetry']['n2_exclusive_runs_below_embedding_minimum'], 1)
        self.assertAlmostEqual(result['telemetry']['n2_exclusive_seconds_below_embedding_minimum'], .4)

    def test_native_overlap_silence_and_endpoint_overhang_are_not_dropped(self):
        c = self.setup_capture()
        result = c.run_capture(self.encoder)
        frames = self.events('n2_diarization_frames')
        probs = self.np.concatenate([x['payload']['probabilities'] for x in frames])
        self.assertEqual(probs.shape, (251, 8))
        self.assertTrue((probs[65:85, :2] >= .5).all())
        self.assertTrue((probs[85:100] == 0).all())
        self.assertAlmostEqual(frames[-1]['payload']['endpoint_overhang_sec'], 2.51-40005/16000)
        self.assertEqual(result['native_frames'], 251)
        self.assertLessEqual(max(v['end_sample'] for v in result['vectors']), 40005)

    def test_no_gallery_no_known_identity_or_asr(self):
        self.setup_capture().run_capture(self.encoder)
        decisions = self.events('speaker_decision')
        self.assertEqual(len(decisions), 3)
        for event in decisions:
            self.assertIsNone(event['payload'].get('known_profile_id'))
        self.assertEqual(self.events('research_asr_observation'), [])
        self.assertIsNone(self.capture.n2_name_map.gallery)

    def test_new_capture_resets_the_resident_once_for_new_scene(self):
        self.setup_capture().run_capture(self.encoder)
        log = io.StringIO()
        other = self.Capture(self.wave, log, self.resident, 'second-scene')
        second = other.run_capture(self.encoder)
        self.assertEqual(self.resident.sessions, ['test-scene', 'second-scene'])
        self.assertEqual(second['embeddings'], 3)
        self.assertTrue(all(x['tracker_id'].startswith('second-scene:') for x in second['vectors']))

    def test_model_failure_is_terminal_and_preserved(self):
        c = self.setup_capture(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'deliberate native failure'):
            c.run_capture(self.encoder)
        self.assertEqual(c._state, 'FAILED')
        self.assertTrue(c.watermarks[-1]['closed'])

    def test_frame_discontinuity_is_not_repaired_silently(self):
        c = self.setup_capture(discontinuity=True)
        with self.assertRaisesRegex(RuntimeError, 'discontinuity'):
            c.run_capture(self.encoder)

    def test_nonunit_encoder_output_is_rejected(self):
        c = self.setup_capture()
        with self.assertRaisesRegex(RuntimeError, 'embedding vector'):
            c.run_capture(EncoderStub(self.np, invalid=True))

    def test_no_future_query_and_no_nonforward_delivery(self):
        journal = CausalJournal(self.np.zeros(3200, dtype='float32'))
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            journal.read(0, 1600, wait_sec=0)
        journal.read(0, 1600)
        with self.assertRaises(ValueError): journal.read(0, 1600)
        with self.assertRaises(ValueError): journal.read(1600, 1)
        self.assertEqual(len(journal.read(0, 1600, wait_sec=0)), 1600)

    def test_modeled_clock_serializes_compute_without_relabeling_native_times(self):
        clock = ModeledClock()
        clock.advance(.1, .2)
        clock.advance(.2, .3)
        self.assertAlmostEqual(clock.relative(), .6)
        with self.assertRaises(ValueError): clock.advance(0, float('nan'))
        self.setup_capture().run_capture(self.encoder)
        frames = self.events('n2_diarization_frames')
        self.assertGreater(frames[0]['payload']['available_at_monotonic'], 100)
        self.assertTrue(all('not_observed_S7' in x['component_clock'] for x in frames))


if __name__ == '__main__':
    unittest.main()
