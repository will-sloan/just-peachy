"""Reconstruction against real frozen ASR calls. README_COMPONENT_COMMANDS.md."""
from copy import deepcopy
import json
import unittest

import test_asr_lane_components as fixtures
from component_commands import asr_commands, d0_commands


class TestASRCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TestRealASRLoops.setUpClass()

    def actual(self, variant):
        fixture = fixtures.TestRealASRLoops()
        capture = fixture.capture()
        actual = []
        original_push = capture._scheduler.push
        original_advance = capture._scheduler_advance
        def push(event, lane):
            actual.append(dict(lane=lane, operation='push', modeled_available_at_sec=event['available_at_sec'], event=deepcopy(event)))
            return original_push(event, lane)
        def advance(lane, source, available):
            actual.append(dict(lane=lane, operation='advance', modeled_available_at_sec=available,
                lower_bound_sec=None if source == float('inf') else source, closed=source == float('inf')))
            return original_advance(lane, source, available)
        capture._scheduler.push = push
        capture._scheduler_advance = advance
        if variant == 'A0': fixture.base._asr_loop(capture, fixtures.BaselineStub())
        else: fixture.native._asr_loop(capture, fixtures.NativeStub())
        capture.finish_capture()
        rows = [json.loads(line) for line in fixture.log.getvalue().splitlines()]
        return rows, actual, len(fixture.wave)/16000

    def test_baseline_command_order_and_tail_match_actual_loop(self):
        rows, actual, duration = self.actual('A0')
        reconstructed = asr_commands(rows, variant='A0', duration=duration)
        self.assertEqual(reconstructed, actual)
        self.assertEqual([x['lower_bound_sec'] for x in reconstructed if x['operation']=='advance'], [.1,.2,None])

    def test_all_native_variants_preserve_exact_feed_and_final_watermarks(self):
        for variant in ('A1','A2','A3'):
            rows, actual, duration = self.actual(variant)
            reconstructed = asr_commands(rows, variant=variant, duration=duration)
            self.assertEqual(reconstructed, actual)
            self.assertEqual([x['lower_bound_sec'] for x in reconstructed if x['operation']=='advance'], [.1,.2,duration,None])

    def test_missing_dispatch_completion_and_missing_drain_are_rejected(self):
        rows, _, duration = self.actual('A0')
        for kind in ('research_asr_full_dispatch_cost','research_asr_drain'):
            with self.assertRaises(ValueError):
                asr_commands([r for r in rows if r['event_type'] != kind], variant='A0', duration=duration)

    def test_future_observation_and_wrong_sequence_are_rejected(self):
        rows, _, duration = self.actual('A2')
        for key, value in [('source_end_sec',100.),('event_id','asr:00000099')]:
            changed = deepcopy(rows)
            next(r for r in changed if r['event_type']=='research_asr_observation')['payload'][key] = value
            with self.assertRaises(ValueError): asr_commands(changed, variant='A2', duration=duration)


class TestD0Commands(unittest.TestCase):
    def actual(self, *, silence=False, frames=43200):
        import io
        import test_d0_calibration as d0fixtures
        np = d0fixtures.np
        profile = d0fixtures.effective_profile('balanced','anonymous_conversation','O0')
        stream = io.StringIO()
        capture = d0fixtures.d0.LaneCapture(profile, profile.apply(), np.linspace(.1,.2,frames,dtype=np.float32), stream)
        actual = []
        def push(event, lane):
            actual.append(dict(lane=lane, operation='push', modeled_available_at_sec=event['available_at_sec'], event=deepcopy(event)))
        def advance(lane, source, available):
            actual.append(dict(lane=lane, operation='advance', modeled_available_at_sec=available,
                lower_bound_sec=None if source == float('inf') else source, closed=source == float('inf')))
        capture._scheduler.push = push
        capture._scheduler_advance = advance
        class Models(d0fixtures.FakeModels):
            def segment(self, audio, include_posteriors=False):
                result = super().segment(audio, include_posteriors)
                return {k:np.zeros_like(v) for k,v in result.items()} if silence else result
        d0fixtures.run_speaker_lane_v3(capture, Models(0))
        self.assertIsNone(capture.error)
        # Native interval tuples are serialized as JSON arrays in the sealed log.
        return [json.loads(line) for line in stream.getvalue().splitlines()], json.loads(json.dumps(actual)), frames/16000

    def test_actual_fixed_cadence_pushes_and_watermarks_match(self):
        rows, actual, duration = self.actual()
        self.assertEqual(d0_commands(rows, duration=duration), actual)
        self.assertEqual(len([r for r in actual if r['operation']=='advance']), 11)

    def test_no_speech_and_short_tail_do_not_invent_queries(self):
        rows, actual, duration = self.actual(silence=True)
        result = d0_commands(rows, duration=duration)
        self.assertEqual(result, actual)
        self.assertFalse(any(r.get('event',{}).get('kind')=='embedding' for r in result))
        self.assertEqual(result[-2]['lower_bound_sec'], 2.5)
        self.assertLess(result[-1]['modeled_available_at_sec'], duration)

    def test_missing_admission_or_vector_cannot_be_reconstructed(self):
        rows, _, duration = self.actual()
        for kind in ('research_embedding_admission','research_embedding'):
            changed = deepcopy(rows)
            del changed[next(i for i,r in enumerate(changed) if r['event_type']==kind)]
            with self.assertRaises(ValueError): d0_commands(changed, duration=duration)


if __name__ == '__main__': unittest.main()
