"""Released native and two-history widget fixtures. README_RESTART_NATIVE_CONTENT.md."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from common import bind, fingerprint, freeze
from viewport_ledger_v2 import ViewportLedger
import test_native_caption_review as original
import test_native_widget_review as widget_fixture
import review_restart_native_content as subject

OUTPUT = None
SOURCE_RECEIPT = None


def relocate(value, name, shift):
    if type(value) is list: return [relocate(v, name, shift) for v in value]
    if type(value) is dict:
        return {k: v+shift if k.endswith('monotonic_sec') and type(v) in (int, float)
                else relocate(v, name, shift) for k, v in value.items()}
    if type(value) is str:
        if value == 'session': return name
        if value.startswith('session/'): return name+value[len('session'):]
    return value


def write_session(test, *, name='session', origin=100., delivered=160000, job=None):
    """Synthetic clocks only; never changes the supplied full planned job."""
    job = job or test.job; events = deepcopy(test.events)
    end = deepcopy(events[-1]); end['event_type'] = 'session_completed'
    end['payload'] = dict(publication_sequence=len(events)+1, publication_monotonic_sec=test.tick+.25,
                         session_id='session', publication_source_cursor_sec=delivered/16000)
    end.update(source_time_sec=delivered/16000, journal_write_monotonic_sec=test.tick+.251); events.append(end)
    events = relocate(events, name, origin-100.)
    for e in events:
        p = e['payload']
        if p['publication_source_cursor_sec'] > 0: p['publication_source_cursor_sec'] = delivered/16000
        if e['event_type'] == 'source_started': p['path'] = job['audio_path']
    session = test.folder/name; session.mkdir()
    (session/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events), encoding='utf-8')
    n = len(events)
    freeze(session/'s6d_consumer_closure.json', dict(state='COMPLETED', full_event_consumer_drained=True,
        monotonic_sec=origin+100., queues=dict(journal=dict(accepted=n, completed=n, depth=0, error=None,
        thread_alive=False, closed=True), event_consumer=dict(consumed=n, coalesced_obsolete_ui_partials=0, depth=0))))
    freeze(session/'session_finalization_v3.json', dict(schema_version='edge-session-finalization.v3', state='COMPLETED',
        live_lanes_at_finalization=[], finalization_error=None, resident_bundle_lease_retained=False,
        resident_bundle_reuse_allowed=True, event_and_transcript_handles_closed=True, source_samples=delivered,
        identity_samples=delivered, handle_close_results={k: dict(closed=True, error=None, was_opened=True)
            for k in ('_event_handle', '_transcript_handle', '_readable_transcript_handle')}))
    intent = 'completed_release' if delivered == job['frames'] else 'mid_file_stop'
    envelope = subject.inspect(session, job=job, delivered_frames=delivered, intent=intent)
    return dict(session=session, delivered_frames=delivered, intent=intent, envelope=envelope)


class ReleasedNativeContentTests(original.NativeCaptionTests):
    def setUp(self):
        original.OUTPUT = OUTPUT/'native'; super().setUp()
        self.job['frames'] = 320000  # Full fixture is twenty seconds; release after ten.

    def review(self):
        source = write_session(self)
        value = subject.review_native(source['session'], job=self.job, delivered_frames=source['delivered_frames'],
            intent=source['intent'], expected_envelope=source['envelope'])
        self.assertEqual(value['planned_frames'], 320000); self.assertEqual(value['delivered_frames'], 160000)
        self.assertFalse(value['full_planned_audio_coverage']); self.assertFalse(value['actual_restart_qualified'])
        return value['captions']

    def test_partial_only_and_source_overhang_remain_explicit(self):
        self.tick = 112.  # Synthetic publication must follow its 11-second support.
        self.raw('unfinished words', end=11.)
        source = write_session(self); before = deepcopy(self.job)
        value = subject.review_native(source['session'], job=self.job, delivered_frames=160000,
            intent='mid_file_stop', expected_envelope=source['envelope'])
        self.assertEqual(self.job, before); self.assertEqual(value['full_job_sha256'], fingerprint(before))
        self.assertEqual(value['raw']['partial_only_utterance_ids'], ['utterance:000000'])
        self.assertEqual(value['raw']['raw_final_text'], '')
        self.assertEqual(value['raw']['source_end_overhang_revisions'], 1)
        freeze(self.folder/'SYNTHETIC_RELEASED_CONTENT.json', value)

    def test_released_envelope_cannot_be_swapped(self):
        self.scenario(); source = write_session(self)
        altered = dict(source['envelope'], delivered_audio_frames=320000)
        with self.assertRaisesRegex(ValueError, 'envelope changed'):
            subject.review_native(source['session'], job=self.job, delivered_frames=160000,
                intent='mid_file_stop', expected_envelope=altered)

    def test_partial_release_cannot_be_claimed_complete(self):
        self.scenario(); source = write_session(self)
        with self.assertRaises(ValueError):
            subject.review_native(source['session'], job=self.job, delivered_frames=160000,
                intent='completed_release', expected_envelope=source['envelope'])


class RestartNativeWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): original.NativeCaptionTests.setUpClass()

    def setUp(self):
        self.folder = OUTPUT/'widget'/self._testMethodName; self.folder.mkdir()
        original.OUTPUT = self.folder
        self.native = original.NativeCaptionTests('test_actual_span_state_rewrite_identity_zero_and_formatting')
        self.native.setUp(); self.native.job['frames'] = 320000; self.native.scenario()
        self.job = deepcopy(self.native.job)
        self.sources = [write_session(self.native, name='first', delivered=160000),
                        write_session(self.native, name='second', origin=300., delivered=320000)]
        self.first = relocate(widget_fixture.NativeWidgetTests.observations(self), 'first', 0.)
        self.second = relocate(widget_fixture.NativeWidgetTests.observations(self), 'second', 200.)
        for observation in self.second:
            observation['source_elapsed_sec'] = observation['observed_monotonic_sec']-300.

    def review(self, observations=None, index=1, **kwargs):
        observations = observations if observations is not None else self.mixed()
        ledger = ViewportLedger(self.folder/'viewport')
        for value in observations: ledger.add(value)
        ledger.close()
        arguments = dict(job=self.job, index=index, viewport_summary=bind(ledger.directory/'SUMMARY.json'),
                         source_receipt=SOURCE_RECEIPT, people=[], mode='open_with_names')
        arguments.update(kwargs)
        return subject.review_widget(self.sources, **arguments)

    def mixed(self):
        result = deepcopy(self.second)
        for value in result: value['rows'] = deepcopy(self.first[-1]['rows'])+value['rows']
        return result

    def test_retained_caption_matches_first_native_history_with_original_clock(self):
        value = self.review(); states = list(value['states'].values())
        self.assertEqual(value['native_span_population'], 8)
        self.assertEqual({s['native_session'] for s in states}, {'first', 'second'})
        for state in states:
            expected = 100. if state['native_session'] == 'first' else 300.
            self.assertEqual(state['original_source_elapsed_sec'], state['observed_monotonic_sec']-expected)
        self.assertTrue(value['retained_caption_native_content_joined']); self.assertFalse(value['actual_restart_qualified'])
        self.assertFalse(value['exact_consumed_event_attribution'])
        freeze(self.folder/'SYNTHETIC_RETAINED_NATIVE_WIDGET.json', value)

    def test_first_viewport_cannot_borrow_future_session_caption(self):
        seen = deepcopy(self.first); seen[-1]['rows'] += deepcopy(self.second[-1]['rows'])
        with self.assertRaisesRegex(ValueError, 'no matching native'): self.review(seen, index=0)

    def test_retained_caption_text_corruption_refused(self):
        seen = self.mixed(); seen[-1]['rows'][0]['panes']['active']['applied_caption_text'] = 'Fabricated retained words'
        with self.assertRaisesRegex(ValueError, 'compatible preceding'): self.review(seen)

    def test_current_caption_with_first_session_key_refused(self):
        seen = self.mixed(); seen[0]['rows'][-1]['caption_key'] = 'first/utterance:000000'
        with self.assertRaisesRegex(ValueError, 'no matching native'): self.review(seen)

    def test_wrong_current_clock_refused(self):
        seen = self.mixed()
        for value in seen:
            value['source_origin_monotonic_sec'] = 100.; value['source_elapsed_sec'] = value['observed_monotonic_sec']-100.
        with self.assertRaisesRegex(ValueError, 'source origins differ'): self.review(seen)

    def test_missing_native_spans_stay_in_both_history_denominators(self):
        value = self.review(self.second[:1])
        self.assertEqual(value['native_span_population'], 8); self.assertEqual(value['observed_span_population'], 2)
        self.assertEqual(len(value['native_spans_not_observed']), 6)

    def test_reused_native_identity_refused(self):
        self.sources[1]['session'] = self.sources[0]['session']
        with self.assertRaisesRegex(ValueError, 'identities differ'): self.review()

    def test_roster_and_nonprimary_modes_refused(self):
        with self.assertRaisesRegex(ValueError, 'primary open'): self.review(mode='selected_closed')
