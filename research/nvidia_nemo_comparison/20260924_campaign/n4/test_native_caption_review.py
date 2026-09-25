"""Actual pure span-state fixtures, synthetic clocks. README_NATIVE_CAPTION_REVIEW.md."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from common import freeze
from review_native_journal import inspect
import review_native_captions as captions

OUTPUT = None
SOURCE = None


class NativeCaptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load unchanged pure relative modules without executing the package's
        # runtime/model imports. All three files are verified by the probe.
        package = types.ModuleType('jp_n4_caption_fixture')
        package.__path__ = [str(SOURCE/'vendor/edge_speech_pipeline')]
        sys.modules[package.__name__] = package
        module = importlib.import_module(package.__name__+'.research_s6d')
        cls.settings = module.S6DSettings; cls.build = staticmethod(module.build_presentation_state)

    def setUp(self):
        self.folder = OUTPUT/self._testMethodName; self.folder.mkdir()
        self.job = dict(job_id='synthetic_O0', audio_path=str(self.folder/'never_opened.wav'),
            audio_sha256='1'*64, frames=160000, sample_rate_hz=16000, gain=1., reset_between_scenes=True, tap='O0')
        self.state = self.build(self.settings(max_display_rows=512), s7=dict(mode='M2',
            session_id='session', ownership_mode='timestamped_spans_v3'))
        self.events = []; self.tick = 101.; self.raw_serial = 0
        self.emit('session_started', {})
        self.emit('source_started', dict(mode='file', path=self.job['audio_path'], start_sample=0, gain=1.,
            pacing='absolute', source_epoch_monotonic_sec=100.))

    def emit(self, kind, payload, source=None):
        self.tick += .25; payload = deepcopy(payload)
        payload.update(publication_sequence=len(self.events)+1, publication_monotonic_sec=self.tick,
            session_id='session', publication_source_cursor_sec=0. if kind in ('session_started','source_started') else 10.)
        if kind == 's6d_text_ready':
            payload.update(available_at_sec=self.tick-100.-.01, observed_text_ready_at_sec=self.tick-100.-.01)
        event = dict(schema_version='edge-speech-event.v1', event_type=kind,
            source_time_sec=source if source is not None else payload.get('source_end_sec', payload['publication_source_cursor_sec']),
            wall_time_utc='2026-09-25T19:40:00+00:00', payload=payload, journal_write_monotonic_sec=self.tick+.001)
        self.events.append(event)
        shown = self.state.consume(kind, payload, now=self.tick+.01)
        if shown is not None: self.emit('s6d_display', shown, source=event['source_time_sec'])
        return payload

    def raw(self, text, *, final=False, end=1., uid='utterance:000000'):
        self.raw_serial += 1; rid = f'asr:{self.raw_serial:08d}'
        p = dict(kind='asr', event_id=rid, utterance_id=uid, source_start_sec=0., source_end_sec=end,
            available_at_sec=end+.1, text=text, final=final, display_text=text, punctuation=None, asr_decode_ms=1.)
        self.emit('research_asr_observation', p)
        self.emit('s6d_text_ready', dict(**p, text_revision_id=rid,
            token_ids=self.state.token_ids(uid, text, self.raw_serial),
            token_timing='untimed hypothesis revision positions; not phonetic alignment',
            speaker='Pending identity', identity_pending=True, publication_path='independent_asr_before_policy',
            modeled_available_at_sec=end+.1, availability_clock='observed_text_publication_before_policy_admission'))

    def scenario(self):
        self.raw('one old')
        self.raw('one new words', final=True, end=2.)
        self.emit('transcript_label_revision', dict(utterance_id='utterance:000000', event_id='policy:00000001',
            source_start_sec=0., source_end_sec=1., target_source_start_sec=0., target_source_end_sec=2.,
            target_text_revision_id='asr:00000002', latest_label_time=2.2, available_at_sec=2.2,
            target_span_ids=[self.state.rows['utterance:000000']['word_spans'][0]['id']],
            latest_label='Speaker 0', replacement_tracker_id=0, latest_anonymous_label='Speaker 0'))
        self.emit('s6d_punctuation_revision', dict(utterance_id='utterance:000000', text='one new words',
            display_text='One new words.', punctuation=dict(text='One new words.'), changes_raw_words=False,
            compute_started_monotonic_sec=self.tick+.02, compute_finished_monotonic_sec=self.tick+.03), source=2.)

    def display_rows(self):
        return [e['payload'] for e in self.events if e['event_type'] == 's6d_display']

    def write(self):
        self.emit('session_completed', {})
        session = self.folder/'session'; session.mkdir()
        (session/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in self.events), encoding='utf-8')
        n = len(self.events)
        freeze(session/'s6d_consumer_closure.json', dict(state='COMPLETED', full_event_consumer_drained=True,
            monotonic_sec=200., queues=dict(journal=dict(accepted=n, completed=n, depth=0, error=None,
            thread_alive=False, closed=True), event_consumer=dict(consumed=n, coalesced_obsolete_ui_partials=0, depth=0))))
        freeze(session/'session_finalization_v3.json', dict(schema_version='edge-session-finalization.v3', state='COMPLETED',
            live_lanes_at_finalization=[], finalization_error=None, resident_bundle_lease_retained=False,
            resident_bundle_reuse_allowed=True, event_and_transcript_handles_closed=True,
            source_samples=self.job['frames'], identity_samples=self.job['frames'],
            handle_close_results={k:dict(closed=True, error=None, was_opened=True)
                for k in ('_event_handle','_transcript_handle','_readable_transcript_handle')}))
        return session, inspect(session, job=self.job)

    def review(self):
        session, envelope = self.write()
        return captions.review(session, job=self.job, expected_envelope=envelope)

    def test_actual_span_state_rewrite_identity_zero_and_formatting(self):
        self.scenario(); result = self.review()
        self.assertEqual(result['raw_final_text'], 'one new words')
        self.assertEqual(result['raw_revision_count'], 2)
        self.assertEqual(result['native_display_count'], 4)
        self.assertEqual(len(result['stable_word_spans']), 4)
        self.assertTrue(result['raw_revision_caption_coverage_complete'])
        self.assertTrue(any(p['identity']['track_id'] == 0 for p in result['displays'][-1]['segments']))
        self.assertFalse(result['actual_widget_content_joined']); self.assertFalse(result['N4_accepted'])
        freeze(self.folder/'SYNTHETIC_CAPTION_REVIEW.json', result)

    def test_caption_raw_text_or_finality_cannot_diverge(self):
        self.raw('actual words', final=True)
        self.display_rows()[0]['text'] = 'different words'
        with self.assertRaisesRegex(ValueError, 'raw words'): self.review()

    def test_word_identity_and_fragment_text_cannot_diverge(self):
        self.scenario(); p = self.display_rows()[-1]
        p['segments'][0]['raw_text'] += ' fabricated'
        with self.assertRaisesRegex(ValueError, 'fragment changed'): self.review()

    def test_missing_fragment_partition_is_rejected(self):
        self.scenario(); p = self.display_rows()[-1]
        self.assertGreater(len(p['segments']), 1); p['segments'].pop()
        # Keep the remaining single segment's formatting coherent so this
        # fixture reaches the missing-tail check rather than an earlier guard.
        p['segments'][0]['display_text'] = p['display_text']
        with self.assertRaisesRegex(ValueError, 'omitted raw text'): self.review()

    def test_retired_span_cannot_reappear(self):
        self.raw('one old'); old = deepcopy(self.display_rows()[0]['word_spans'][1])
        self.raw('one new', end=1.1); self.raw('one old', final=True, end=1.2)
        p = self.display_rows()[-1]; p['token_ids'][1] = old['id']; p['word_spans'][1] = old
        with self.assertRaisesRegex(ValueError, 'Retired native span'): self.review()

    def test_retained_span_cannot_change_stable_time(self):
        self.scenario(); p = self.display_rows()[-1]
        p['word_spans'][0]['first_seen_monotonic_sec'] += .01
        with self.assertRaisesRegex(ValueError, 'stable word facts'): self.review()

    def test_display_cause_must_precede_state_application(self):
        self.raw('words', final=True)
        self.display_rows()[0]['controller_update_monotonic_sec'] = 1.
        with self.assertRaisesRegex(ValueError, 'cause/state/publication'): self.review()

    def test_display_version_cannot_be_reused(self):
        self.scenario(); self.display_rows()[-1]['display_version'] = self.display_rows()[-2]['display_version']
        with self.assertRaisesRegex(ValueError, 'display version'): self.review()

    def test_formatting_must_be_from_preceding_publication(self):
        self.raw('words', final=True); self.display_rows()[0]['display_text'] = 'new unsupported sentence'
        with self.assertRaisesRegex(ValueError, 'formatting has no'): self.review()

    def test_missing_caption_remains_a_missing_revision_denominator(self):
        self.raw('words', final=True)
        for event in self.events:
            if event['event_type'] == 's6d_display': event['event_type'] = 'diagnostic_omitted_display'
        result = self.review()
        self.assertEqual(result['missing_raw_revision_ids'], ['asr:00000001'])
        self.assertFalse(result['raw_revision_caption_coverage_complete']); self.assertFalse(result['N4_accepted'])

    def test_empty_final_and_zero_duration_are_not_phonetic_alignment(self):
        self.raw('', final=True, end=0.)
        result = self.review()
        self.assertEqual(result['raw_final_text'], ''); self.assertEqual(result['stable_word_spans'], [])
        self.assertEqual(result['native_display_count'], 1); self.assertFalse(result['source_to_widget_latency_qualified'])

    def test_span_budget_is_enforced(self):
        self.scenario()
        with patch.object(captions, 'MAX_SPANS', 2), self.assertRaisesRegex(ValueError, 'span census|exceeds budget'):
            self.review()
