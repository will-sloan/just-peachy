"""Small synthetic callback/telemetry contract checks; README_LIVE_SPATIAL.md.

No microphones, model loading, reference corpus or saved personal profiles.
"""
from copy import deepcopy
from dataclasses import replace
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
from app.live_audio import LiveBlock
from app.live_spatial import LiveSpatialProvider, MotionFrameTracker, ENERGY, SELECTED, ANGLE
from app.pipeline import effective_profile
from edge_speech_pipeline.research_scheduler_v3 import build_s6c_policy


class Diagnostic:
    def __init__(self):
        self.state = 'RUNNING'
        self.fast = []

    def snapshot(self):
        return {'state': self.state, 'arrows': []}

    def set_fast(self, value):
        self.fast.append(value)


class LiveSpatialTests(unittest.TestCase):
    def setUp(self):
        self.time = 100.
        self.profile = effective_profile('balanced', 'spatial_assisted', 'O0')
        self.provider = self.make_provider()

    def make_provider(self, *, enabled=True, tap='O0'):
        value = LiveSpatialProvider(tap, self.profile.tracker, enabled=enabled,
                                    clock=lambda: self.time)
        value.attach(SimpleNamespace(beam_diagnostics=Diagnostic()))
        value.bind_origin(100.)
        return value

    def receive(self, field, values, end, duration=.005, provider=None):
        (provider or self.provider).receive(field, values, 100.+end-duration, 100.+end)

    def block(self, end, *, callback=None, consume=None, provider=None):
        callback = end if callback is None else callback
        self.time = 100.+(callback if consume is None else consume)
        stamp = round((100.+callback)*1e9)
        block = LiveBlock(np.zeros(320, np.float32), round(end*16000)-320,
                          round(end*48000)-960, 960, stamp, callback,
                          round(self.time*1e9), .001, max(0., self.time-100.-callback),
                          callback_perf_counter_ns=stamp)
        (provider or self.provider).advance_audio(block)

    def cue(self, end=1., *, angle=30., auto=30., energy=1., provider=None):
        provider = provider or self.provider
        if energy is not None:
            self.receive(ENERGY, [1., 1., 1., energy], end-.03, provider=provider)
        self.receive(SELECTED, [math.radians(angle) if angle is not None else None,
                                math.radians(auto) if auto is not None else None],
                     end-.01, provider=provider)
        self.block(end, provider=provider)

    def query(self, end=1., now=1.05, provider=None):
        return (provider or self.provider).evidence_for_window(end-.5, end, now)

    def test_motion_frame_applies_to_tracker_cue_and_fails_closed(self):
        class Motion:
            valid=True
            def transform(self, angle, at):return (angle+20., .8) if self.valid and angle is not None else (None, 0.)
            def snapshot(self):return dict(valid=self.valid, compensation=True, yaw_deg=20., reason='Reset required')
        motion=Motion(); self.provider.motion=motion
        self.cue(angle=70.,auto=70.)
        cue=self.query()
        self.assertIsNotNone(cue)
        self.assertAlmostEqual(cue.angle_deg,90.)
        motion.valid=False
        self.assertIsNone(self.query())
        self.assertEqual(self.provider.snapshot()['coordinate_frame'],'relative_anchor_front_assumed')
        self.assertEqual(self.provider.snapshot()['associations'],[])

    def test_recovered_motion_cannot_reuse_previous_frame_cues_or_names(self):
        class Motion:
            generation=1
            def transform(self,angle,at):return angle,1.
            def snapshot(self):return dict(valid=True,compensation=True,yaw_deg=0.,frame_generation=self.generation,unsafe_generation=0)
        motion=Motion();self.provider.motion=motion
        self.cue();self.provider.observe_decision(self.decision())
        self.assertIsNotNone(self.query());self.assertEqual(len(self.provider.snapshot()['associations']),1)
        motion.generation=2
        self.assertIsNone(self.query());self.assertEqual(self.provider.snapshot()['associations'],[])

    def test_motion_frame_clears_only_tracker_locations(self):
        from edge_speech_pipeline.research_tracking_v3 import S6CTracker
        target=S6CTracker(self.profile.tracker)
        voice=np.array([1.,0.,0.],np.float32)
        events=[];track=target._create(voice,1.,1.,events)
        track.location=45.;track.location_at=1.
        target.pending_angle=45.;target.sensor_credit=0.
        class Motion:
            generation=1
            def snapshot(self):return dict(frame_generation=self.generation,unsafe_generation=0)
        motion=Motion();wrapper=MotionFrameTracker(target,motion)
        motion.generation=2
        # Test dispatch boundary without constructing unrelated speech evidence.
        calls=[];target.update=lambda *a,**kw:calls.append(kw)
        wrapper.update(voice,1.,2.,2.,spatial=object())
        self.assertIsNone(track.location);self.assertIsNone(target.pending_angle)
        self.assertEqual(target.sensor_credit,1.);self.assertEqual(wrapper.location_resets,1)
        np.testing.assert_array_equal(track.prototypes[0],voice)
        self.assertIsNone(calls[0]['spatial'])

    def decision(self, end=1., *, identity=None, qualified=True):
        return {'source_start_sec': end-.5, 'source_end_sec': end,
                'input_available_at_sec': end+.05,
                'available_at_sec': end+.06,
                'decision': {'tracker_id': 1, 'anonymous_label': 'Speaker_1',
                             'clean_intervals': [[end-.5, end]],
                             'cue': {'qualified_bearing_deg': 30. if qualified else None,
                                     'reliability': .9 if qualified else 0.},
                             'identity': identity or {}}}

    def test_empty_unbound_and_missing_callback_are_unavailable(self):
        self.assertIsNone(self.query())
        unbound = LiveSpatialProvider('O0', self.profile.tracker, clock=lambda: self.time)
        unbound.receive(SELECTED, [0., 0.], 100., 100.01)
        block = SimpleNamespace(callback_perf_counter_ns=None)
        unbound.advance_audio(block)
        self.assertIsNone(unbound.evidence_for_window(0., 1., 1.))

    def test_receipt_becomes_available_only_after_actual_audio_callback(self):
        self.receive(SELECTED, [math.pi/6, math.pi/6], .99)
        self.block(.98)
        self.assertIsNone(self.query())
        self.block(1.)
        cue = self.query()
        self.assertAlmostEqual(cue.angle_deg, 30.)
        self.assertIsNone(cue.source_start_sec)
        self.assertIsNone(cue.source_end_sec)  # No invented DSP receptive span.
        self.assertLessEqual(cue.available_at_sec, 1.05)

    def test_delayed_voice_cannot_borrow_newer_audio_direction(self):
        self.cue(1., angle=30.)
        self.cue(2., angle=150., auto=150.)
        self.assertAlmostEqual(self.query(end=1., now=1.05).angle_deg, 30.)
        self.assertIsNone(self.query(end=1., now=2.05))
        self.assertAlmostEqual(self.query(end=2., now=2.05).angle_deg, 150.)

    def test_late_audio_consumer_cannot_rejuvenate_old_telemetry(self):
        self.receive(SELECTED, [math.pi/6, math.pi/6], .99)
        self.block(1., callback=1., consume=5.)
        self.assertIsNone(self.query(end=1., now=5.05))

    def test_historical_reliability_and_both_taps_share_selected_processed(self):
        for tap in ('O0', 'O1'):
            with self.subTest(tap=tap):
                provider = self.make_provider(tap=tap)
                self.cue(angle=30., auto=75., provider=provider)
                observation = self.query(provider=provider)
                self.assertAlmostEqual(observation.angle_deg, 30.)
                self.assertAlmostEqual(observation.reliability, .5*(1-.01/.25))
                self.assertEqual(observation.energy, 1.)

    def test_selected_nan_never_falls_back_to_other_available_beams(self):
        self.receive(ANGLE, [0., 1., 2., 3.], .96)
        self.cue(angle=None, auto=75.)
        self.assertIsNone(self.query())

    def test_missing_energy_keeps_documented_selected_speech_gate(self):
        self.cue(energy=None)
        observation = self.query()
        self.assertIsNotNone(observation)
        self.assertIsNone(observation.energy)

    def test_fresh_zero_energy_invalidates_cue(self):
        self.cue(energy=0.)
        self.assertIsNone(self.query())

    def test_stale_energy_is_omitted_and_fresh_energy_does_not_refresh_angle(self):
        self.receive(ENERGY, [1., 1., 1., 0.], .1)
        self.receive(SELECTED, [0., 0.], .99)
        self.block(1.)
        self.assertIsNone(self.query().energy)
        self.receive(ENERGY, [1., 1., 1., 1.], 1.4)
        self.block(1.42)
        self.assertIsNone(self.query(end=1.42, now=1.45))

    def test_slow_selected_transaction_and_callback_delay_are_rejected(self):
        for duration, receipt in ((.3, .99), (.005, .6)):
            with self.subTest(duration=duration, receipt=receipt):
                provider = self.make_provider()
                self.receive(SELECTED, [0., 0.], receipt, duration=duration, provider=provider)
                self.block(1., provider=provider)
                self.assertIsNone(self.query(provider=provider))

    def test_future_reordered_and_duplicate_audio_cannot_change_past_cue(self):
        self.cue()
        self.receive(SELECTED, [math.pi, math.pi], .8)  # Reordered host receipt.
        self.receive(SELECTED, [math.pi, math.pi], 3.)  # Future callback support.
        self.block(1.)  # Duplicate callback is not new evidence.
        observation = self.query()
        self.assertAlmostEqual(observation.angle_deg, 30.)
        self.assertEqual(self.provider.snapshot()['counters']['rejected_receipts'], 1)
        self.assertIsNone(self.query(now=.5))

    def test_disconnect_falls_back_to_voice_and_new_session_has_no_memory(self):
        self.cue()
        self.assertIsNotNone(self.query())
        self.provider.live.beam_diagnostics.state = 'UNAVAILABLE'
        self.assertIsNone(self.query())
        with self.assertRaises(ValueError):
            self.provider.bind_origin(101.)
        fresh = self.make_provider()
        self.assertIsNone(self.query(provider=fresh))
        self.assertEqual(fresh.snapshot()['associations'], [])

    def test_named_association_requires_confirmed_voice_and_remains_estimated(self):
        self.cue()
        self.provider.observe_segmentation({'source_end_sec': 1., 'speech': True, 'overlap': False})
        identity = {'known_profile_id': 'test-uuid', 'known_name': 'Test person',
                    'naming_state': 'confirmed', 'query_executed': True}
        self.provider.observe_decision(self.decision(identity=identity))
        self.time = 101.1
        association = self.provider.snapshot()['associations'][0]
        self.assertEqual(association['label'], 'Test person')
        self.assertEqual(association['association_status'], 'estimated_current')
        self.assertTrue(association['estimated'])
        self.assertNotIn('association_confidence', association)
        # Returned GUI state is detached from the live estimator.
        association['label'] = 'Mutated outside provider'
        self.assertEqual(self.provider.snapshot()['associations'][0]['label'], 'Test person')

    def test_tentative_voice_and_angle_cannot_create_confirmed_name(self):
        self.cue()
        identity = {'known_profile_id': 'test-uuid', 'known_name': 'Test person',
                    'naming_state': 'tentative', 'query_executed': True}
        self.provider.observe_decision(self.decision(identity=identity))
        association = self.provider.snapshot()['associations'][0]
        self.assertEqual(association['label'], 'Speaker_1')
        self.assertIsNone(association['profile_id'])

    def test_rejected_voice_or_unqualified_cue_does_not_assign_direction(self):
        self.cue()
        rejected = self.decision()
        rejected['decision']['reason'] = 'audio_gate_reject'
        for decision in (rejected, self.decision(qualified=False)):
            self.provider.observe_decision(decision)
        self.assertEqual(self.provider.snapshot()['associations'], [])

    def test_cached_name_ages_independently_and_location_becomes_last_known(self):
        self.cue()
        identity = {'known_profile_id': 'test-uuid', 'known_name': 'Test person',
                    'naming_state': 'confirmed', 'query_executed': False,
                    'name_evidence_available_at_sec': .5}
        self.provider.observe_decision(self.decision(identity=identity))
        self.provider.observe_segmentation({'source_end_sec': 1., 'speech': True, 'overlap': False})
        self.time = 102.6
        row = self.provider.snapshot()['associations'][0]
        self.assertEqual(row['association_status'], 'last_known')
        self.assertFalse(row['fresh'])
        self.assertFalse(row['speaking'])
        self.assertIsNone(row['profile_id'])
        self.assertLess(row['reliability'], self.query(now=1.05).reliability)
        self.time = 114.
        self.assertEqual(self.provider.snapshot()['associations'], [])

    def test_overlap_never_displays_current_exclusive_speaker(self):
        self.cue()
        self.provider.observe_decision(self.decision())
        self.provider.observe_segmentation({'source_end_sec': 1., 'speech': True, 'overlap': True})
        self.assertFalse(self.provider.snapshot()['speech'])
        self.assertFalse(self.provider.snapshot()['associations'][0]['speaking'])

    def test_optional_window_hook_gets_audio_end_separately_from_admission(self):
        calls = []
        provider = SimpleNamespace(evidence_for_window=lambda *args: calls.append(args))
        # Isolate scheduler plumbing from gallery matching without changing the tracker.
        profile = replace(self.profile, identity=replace(self.profile.identity, mode='none'))
        scheduler = build_s6c_policy(profile, spatial_provider=provider)
        vector = np.zeros(192, np.float32)
        vector[0] = 1.
        event = {'kind': 'embedding', 'event_id': 'embedding:test',
                 'source_start_sec': .5, 'source_end_sec': 1., 'available_at_sec': 2.,
                 'vector': vector.tolist(), 'speech': True, 'overlap': False,
                 'evidence_kind': 'mature', 'clean_intervals': [[.5, 1.]]}
        scheduler.push(deepcopy(event), 'speaker')
        records = scheduler.finish()
        self.assertEqual(calls, [(.5, 1., 2.)])
        self.assertTrue(any(row['event_type'] == 'speaker_decision' for row in records))
        # Existing recorded JSON providers keep their old two-argument API.
        legacy_calls = []
        legacy = SimpleNamespace(evidence=lambda *args: legacy_calls.append(args))
        old_scheduler = build_s6c_policy(profile, spatial_provider=legacy)
        old_scheduler.push(deepcopy(event), 'speaker')
        old_scheduler.finish()
        self.assertEqual(legacy_calls, [(.5, 2.)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
