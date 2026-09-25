"""Real S7 scheduler/worker/span tests, no model. README_COMPONENT_S7_REPLAY.md."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import threading
import unittest

from component_s7_replay import (CLOCK_KIND, ReplayClock, causal_commands,
    modeled_publication, replay_d0_anonymous)


def advance(lane, bound, ready):
    return dict(lane=lane, operation='advance', modeled_available_at_sec=ready,
        lower_bound_sec=bound, closed=bound is None)


def push(lane, event):
    return dict(lane=lane, operation='push', modeled_available_at_sec=event['available_at_sec'], event=event)


def asr(serial=1, *, ready=1.1, end=1., text='one two', final=True, uid='utterance:000000'):
    return dict(kind='asr', event_id=f'asr:{serial:08d}', utterance_id=uid,
        source_start_sec=0., source_end_sec=end, available_at_sec=ready,
        text=text, final=final, display_text=text, punctuation=None, asr_decode_ms=1.)


def embedding():
    return dict(kind='embedding', event_id='embedding:00000001', observation_id='embedding:00000001',
        source_start_sec=0., source_end_sec=1., available_at_sec=1.,
        receptive_start_sec=0., receptive_end_sec=1., evidence_kind='mature',
        clean_intervals=[[0., 1.]], vector=[1.]+[0.]*191,
        speech=True, overlap=False, rms=.1, clipping_fraction=0., clean_fraction=1.)


class TestS7Replay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('JP_N4_SOURCE',
            r'G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v3\prototype'))
        sys.path[:0] = [str(source), str(source/'vendor')]
        from app.pipeline import effective_profile
        cls.profile = effective_profile('balanced', 'anonymous_conversation', 'O0')

    def run_replay(self, a, s, *, duration=2., formatting=()):
        return replay_d0_anonymous(a, s, duration=duration, formatting=formatting,
            profile=self.profile, session_id='protocol-only')

    def lanes(self, close_at=1.25):
        a = [push('asr', asr()), advance('asr', None, close_at)]
        s = [push('speaker', embedding()), advance('speaker', None, close_at)]
        return a, s

    def test_merge_preserves_same_lane_order_and_deterministic_ties(self):
        a = [push('asr', asr(ready=1.)), advance('asr', 1., 1.), advance('asr', None, 2.)]
        s = [push('speaker', embedding()), advance('speaker', 1., 1.), advance('speaker', None, 2.)]
        original = deepcopy((a, s))
        merged = causal_commands(a, s, duration=2.)
        self.assertEqual([(r['command']['lane'], r['lane_sequence']) for r in merged[:4]],
            [('speaker', 0), ('speaker', 1), ('asr', 0), ('asr', 1)])
        self.assertEqual((a, s), original)

    def test_short_tail_close_waits_for_input_without_changing_ready(self):
        a = [advance('asr', None, 1.2)]
        s = [advance('speaker', 1., 1.01), advance('speaker', None, 1.01)]
        merged = causal_commands(a, s, duration=1.2)
        close = next(r for r in merged if r['command']['lane']=='speaker' and r['command']['closed'])
        self.assertEqual(close['execute_at_sec'], 1.2)
        self.assertEqual(close['command']['modeled_available_at_sec'], 1.01)
        self.assertEqual(close['source_delivery_constraint_sec'], 1.2)

    def test_actual_scheduler_does_not_release_at_equal_watermark(self):
        a = [push('asr', asr(ready=1.)), advance('asr', 1., 1.), advance('asr', None, 1.1)]
        s = [advance('speaker', 1., 1.), advance('speaker', None, 1.1)]
        result = self.run_replay(a, s, duration=1.)
        equality = next(r for r in result['execution'] if r['lane']=='asr' and r['source_watermark_sec']==1.)
        self.assertEqual(equality['pending_events'], 1)
        self.assertEqual(equality['emitted_total'], 0)
        self.assertEqual(result['policy'][0]['native_record']['observed_policy_decision_ready_at_sec'], 1.1)

    def test_actual_eligibility_rejects_evidence_aged_while_waiting_for_other_lane(self):
        a, s = self.lanes()
        fresh = self.run_replay(a, s, duration=1.25)
        a, s = self.lanes(2.)
        stale = self.run_replay(a, s, duration=2.)
        fresh_caption = next(r['native_record'] for r in fresh['policy'] if r['native_record']['event_type']=='transcript_final')
        stale_caption = next(r['native_record'] for r in stale['policy'] if r['native_record']['event_type']=='transcript_final')
        self.assertTrue(fresh_caption['current_source_permission'])
        self.assertFalse(stale_caption['current_source_permission'])
        self.assertNotEqual(fresh_caption['first_final_label'], stale_caption['first_final_label'])
        self.assertEqual(stale_caption['observed_policy_decision_ready_at_sec'], 2.)

    def test_actual_publication_rechecks_fixed_source_expiry(self):
        a, s = self.lanes()
        result = self.run_replay(a, s, duration=1.25)
        speaker = next(r['native_record'] for r in result['policy'] if r['native_record']['event_type']=='speaker_decision')
        self.assertTrue(speaker['current_source_permission'])
        delayed = modeled_publication(speaker, at_sec=1.8)
        self.assertFalse(delayed['current_source_permission'])
        self.assertEqual(delayed['application_scope'], 'HISTORICAL_ONLY')
        self.assertEqual(speaker['source_evidence_expiry_at_sec'], delayed['source_evidence_expiry_at_sec'])
        self.assertTrue(speaker['current_source_permission'])

    def test_raw_revisions_and_exact_final_formatting_preserve_all_words(self):
        a = [push('asr', asr(final=False, text='one old')),
             push('asr', asr(2, end=1.5, ready=1.6, text='one new words')),
             advance('asr', None, 2.)]
        s = [push('speaker', embedding()), advance('speaker', None, 2.)]
        formatting = [dict(utterance_id='utterance:000000', input_event_id='asr:00000002',
            raw_text='one new words', punctuation={'text':'One new words.'}, modeled_available_at_sec=2.1)]
        result = self.run_replay(a, s, formatting=formatting)
        row = result['presentation']['rows'][0]
        self.assertEqual(row['text'], 'one new words')
        self.assertEqual(''.join(s['raw_text'] for s in row['segments']), row['text'])
        self.assertEqual(row['display_text'], 'One new words.')
        raw = [r for r in result['presentation_events'] if r['kind']=='s6d_text_ready']
        self.assertEqual([r['input']['text_revision_id'] for r in raw], ['asr:00000001','asr:00000002'])
        self.assertEqual(result['presentation']['rejected'].get('older_or_unversioned_words'), 1)
        self.assertEqual(result['presentation']['rejected'].get('identity_wrong_target_span'), 1)

    def test_same_boundary_finals_stay_separate_and_clock_fields_stay_modeled(self):
        a = [push('asr', asr()), push('asr', asr(2, text='second', uid='utterance:000001')),
             advance('asr', None, 2.)]
        result = self.run_replay(a, [advance('speaker', None, 2.)])
        self.assertEqual(len(result['presentation']['rows']), 2)
        self.assertEqual(result['clock_kind'], CLOCK_KIND)
        self.assertEqual(result['integrated_N4_cells'], 0)
        self.assertFalse(result['physical_widget_observed'])
        self.assertFalse(result['observed_Controller_parity'])
        self.assertNotIn('s6d_dispatch', result['policy_snapshot'])
        self.assertFalse(result['worker_counts']['thread_alive'])
        self.assertEqual(result['worker_counts']['accepted'], result['worker_counts']['completed'])

    def test_reference_fields_wrong_lane_future_and_duplicate_inputs_fail(self):
        for mutate in (lambda a,s:a[0]['event'].update(reference='forbidden'),
                       lambda a,s:a[0]['event'].update(source_end_sec=3.),
                       lambda a,s:a[0]['event'].update(event_id=s[0]['event']['event_id']),
                       lambda a,s:s[0].update(lane='asr')):
            a, s = self.lanes()
            mutate(a,s)
            with self.assertRaises(ValueError): causal_commands(a,s,duration=2.)

    def test_missing_close_late_push_and_regressing_source_bound_fail(self):
        a, s = self.lanes()
        for bad in (s[:-1], s+[s[0]], [advance('speaker',1.,1.), advance('speaker',.5,1.1), s[-1]],
                    [advance('speaker',1.5,1.),s[-1]]):
            with self.assertRaises(ValueError): causal_commands(a,bad,duration=2.)
        with self.assertRaisesRegex(ValueError,'budget'): causal_commands(a,s,duration=2.,max_commands=1)

    def test_formatting_cannot_borrow_another_final_or_appear_twice(self):
        a,s = self.lanes()
        good = dict(utterance_id='utterance:000000', input_event_id='asr:00000001',
            raw_text='one two', punctuation={'text':'One two.'}, modeled_available_at_sec=2.1)
        for key, value in [('input_event_id','asr:00000009'),('raw_text','different'),('modeled_available_at_sec',.5)]:
            bad = dict(good); bad[key] = value
            with self.assertRaises(ValueError): causal_commands(a,s,duration=2.,formatting=[bad])
        with self.assertRaises(ValueError): causal_commands(a,s,duration=2.,formatting=[good,good])

    def test_worker_failure_is_explicit_and_real_thread_is_closed(self):
        before = {t.ident for t in threading.enumerate() if t.name=='edge-s7-observed-policy'}
        a,s = self.lanes()
        s[0]['event']['vector'] = [1.]
        with self.assertRaisesRegex(RuntimeError, '192-D'):
            self.run_replay(a,s)
        after = {t.ident for t in threading.enumerate() if t.name=='edge-s7-observed-policy'}
        self.assertEqual(after, before)

    def test_clock_and_publication_reject_regression_and_foreign_epoch(self):
        clock = ReplayClock(); clock.set(2.)
        for value in (True, float('inf'), 1.):
            with self.assertRaises(ValueError): clock.set(value)
        a,s = self.lanes()
        record = self.run_replay(a,s,duration=1.25)['policy'][0]['native_record']
        with self.assertRaises(ValueError): modeled_publication(record,at_sec=1.)
        record['source_epoch_monotonic_sec'] = 10.
        with self.assertRaises(ValueError): modeled_publication(record,at_sec=2.)


if __name__ == '__main__': unittest.main()
