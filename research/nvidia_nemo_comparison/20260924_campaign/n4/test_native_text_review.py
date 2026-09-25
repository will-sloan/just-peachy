"""Synthetic text-lineage corruption checks; see README_NATIVE_TEXT_REVIEW.md."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import freeze
from review_native_journal import inspect
import review_native_text as native

OUTPUT = None
CASES = []


class NativeTextTests(unittest.TestCase):
    def setUp(self):
        self.folder = OUTPUT/self._testMethodName; self.folder.mkdir()
        self.job = dict(job_id='synthetic_O0', audio_path=str(self.folder/'never_opened.wav'),
            audio_sha256='1'*64, frames=160000, sample_rate_hz=16000, gain=1., reset_between_scenes=True, tap='O0')

    def transcript(self, serial, raw, *, final=False, uid='utterance:000000', end=1.):
        observation = dict(kind='asr', event_id=f'asr:{serial:08d}', utterance_id=uid,
            source_start_sec=0., source_end_sec=end, available_at_sec=end+.1,
            text=raw, final=final, display_text=raw, punctuation=None, asr_decode_ms=2.)
        ready = dict(**observation, text_revision_id=observation['event_id'],
            token_ids=[f'{uid}:{serial}:{i}' for i, _ in enumerate(raw.split())],
            token_timing='untimed hypothesis revision positions; not phonetic alignment',
            identity_pending=True, publication_path='independent_asr_before_policy', speaker='Pending identity',
            observed_text_ready_at_sec=end+.2, modeled_available_at_sec=end+.1,
            availability_clock='observed_text_publication_before_policy_admission')
        ready['available_at_sec'] = end+.2
        return [('research_asr_observation', observation), ('s6d_text_ready', ready)]

    def standard(self):
        first = self.transcript(1, 'raw alpha', end=1.)
        final = self.transcript(2, 'raw beta', final=True, end=2.)
        punctuation = ('s6d_punctuation_revision', dict(utterance_id='utterance:000000', text='raw beta',
            display_text='DIFFERENT FORMATTED WORDS!', punctuation=dict(text='DIFFERENT FORMATTED WORDS!'),
            compute_started_monotonic_sec=114., compute_finished_monotonic_sec=114.5, changes_raw_words=False))
        # A display record may interleave raw observation and text publication.
        return first[:1]+[('s6d_display', dict(text='not a raw hypothesis'))]+first[1:]+final+[punctuation]

    def fixture(self, events, *, name='session', prefix=0):
        session = self.folder/name; session.mkdir()
        facts = [('session_started', {}), ('source_started', dict(mode='file', path=self.job['audio_path'],
            start_sample=0, gain=1., pacing='absolute', source_epoch_monotonic_sec=100.))]+deepcopy(events)+[('session_completed', {})]
        rows = []
        for i, (kind, p) in enumerate(facts):
            cursor = 0. if i < 2 else 10.
            p.update(publication_sequence=i+1, publication_monotonic_sec=110.+i,
                     session_id=name, publication_source_cursor_sec=cursor)
            if kind == 's6d_text_ready':
                p.update(available_at_sec=9.75+i, observed_text_ready_at_sec=9.75+i)
            # Punctuation compute follows the final's raw publication and ends before its own.
            if kind == 's6d_punctuation_revision':
                p.update(compute_started_monotonic_sec=109.+i, compute_finished_monotonic_sec=109.5+i)
            source = p.get('source_end_sec', 2. if kind == 's6d_punctuation_revision' else cursor)
            rows.append(dict(schema_version='edge-speech-event.v1', event_type=kind,
                source_time_sec=source, wall_time_utc='2026-09-25T19:00:00+00:00', payload=p,
                journal_write_monotonic_sec=110.1+i))
        (session/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows[prefix:]), encoding='utf-8')
        n = len(rows)
        freeze(session/'s6d_consumer_closure.json', dict(state='COMPLETED', full_event_consumer_drained=True,
            monotonic_sec=200., queues=dict(journal=dict(accepted=n, completed=n, depth=0, error=None,
            thread_alive=False, closed=True), event_consumer=dict(consumed=n-1, coalesced_obsolete_ui_partials=1, depth=0))))
        freeze(session/'session_finalization_v3.json', dict(schema_version='edge-session-finalization.v3',
            state='COMPLETED', live_lanes_at_finalization=[], finalization_error=None,
            resident_bundle_lease_retained=False, resident_bundle_reuse_allowed=True,
            event_and_transcript_handles_closed=True, source_samples=self.job['frames'], identity_samples=self.job['frames'],
            handle_close_results={k:dict(closed=True, error=None, was_opened=True)
                for k in ('_event_handle', '_transcript_handle', '_readable_transcript_handle')}))
        return session, inspect(session, job=self.job)

    def review(self, events, **kwargs):
        session, envelope = self.fixture(events, **kwargs)
        return native.review(session, job=self.job, expected_envelope=envelope)

    def test_interleaved_revisions_preserve_raw_words_and_separate_formatting(self):
        result = self.review(self.standard())
        self.assertEqual(result['raw_final_text'], 'raw beta')
        self.assertEqual(result['raw_final_word_count'], 2)
        self.assertEqual(len(result['raw_revisions']), 2)
        self.assertEqual(result['formatting_revisions'][0]['display_text'], 'DIFFERENT FORMATTED WORDS!')
        self.assertFalse(result['accuracy_qualified']); self.assertFalse(result['N4_accepted'])
        self.assertFalse(result['application_owner_reviewed']); self.assertEqual(result['integrated_N4_cells'], 0)
        freeze(self.folder/'SYNTHETIC_TEXT_REVIEW.json', result)

    def test_missing_duplicate_or_foreign_ready_publication_is_rejected(self):
        for name in ('missing', 'duplicate', 'foreign'):
            events = self.transcript(1, 'words', final=True)
            if name == 'missing': events.pop()
            elif name == 'duplicate': events.append(deepcopy(events[-1]))
            else: events[-1][1]['text_revision_id'] = 'asr:00000002'
            with self.subTest(name=name), self.assertRaises(ValueError): self.review(events, name=name)

    def test_changed_raw_fields_are_not_hidden_by_matching_ids(self):
        for key, value in (('text', 'changed'), ('display_text', 'changed'), ('final', False), ('final', 1),
                           ('source_end_sec', 2.), ('asr_decode_ms', 9.)):
            events = self.transcript(1, 'words', final=True); events[-1][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.review(events, name=key+str(value))

    def test_revision_reuse_final_rewrite_and_backward_support_are_rejected(self):
        variants = [self.transcript(1, 'one')+self.transcript(1, 'two'),
            self.transcript(1, 'one', final=True)+self.transcript(2, 'two'),
            self.transcript(1, 'one', end=2.)+self.transcript(2, 'two', end=1.)]
        for i, events in enumerate(variants):
            with self.subTest(i=i), self.assertRaises(ValueError): self.review(events, name=str(i))

    def test_partial_only_and_empty_populations_remain_explicit(self):
        partial = self.review(self.transcript(1, 'still unfinished'), name='partial')
        self.assertEqual(partial['raw_final_text'], '')
        self.assertEqual(partial['partial_only_utterance_ids'], ['utterance:000000'])
        self.assertFalse(partial['raw_hypothesis_completeness_qualified'])
        empty = self.review([], name='empty')
        self.assertEqual(empty['raw_revisions'], []); self.assertEqual(empty['raw_final_word_count'], 0)
        self.assertFalse(empty['accuracy_qualified'])

    def test_multiple_utterances_keep_order_unicode_and_diagnostic_overhang(self):
        events = self.transcript(1, 'café α', final=True, uid='utterance:000003', end=1.)
        events += self.transcript(2, 'next word', final=True, uid='utterance:000007', end=10.08)
        result = self.review(events)
        self.assertEqual(result['raw_final_text'], 'café α next word')
        self.assertEqual(result['source_end_overhang_revisions'], 1)
        self.assertEqual(result['raw_revisions'][-1]['source_end_sec'], 10.08)

    def test_punctuation_wrong_target_false_claim_or_clock_is_rejected(self):
        for name, change in (('target', dict(text='not raw beta')), ('claim', dict(changes_raw_words=True)),
                             ('display', dict(punctuation=dict(text='different')))):
            events = self.standard(); events[-1][1].update(change)
            with self.subTest(name=name), self.assertRaises(ValueError): self.review(events, name=name)
        session, envelope = self.fixture(self.standard(), name='clock')
        path = session/'events.jsonl'; records = [json.loads(x) for x in path.read_text().splitlines()]
        records[-2]['payload']['compute_started_monotonic_sec'] = 1.
        path.write_text(''.join(json.dumps(x)+'\n' for x in records), encoding='utf-8')
        envelope = inspect(session, job=self.job)
        with self.assertRaisesRegex(ValueError, 'Punctuation compute'):
            native.review(session, job=self.job, expected_envelope=envelope)

    def test_observed_clock_and_token_census_are_checked(self):
        changes = [dict(token_ids=[]), dict(token_ids=['duplicate', 'duplicate']),
            dict(modeled_available_at_sec=99.), dict(observed_text_ready_at_sec=0.),
            dict(available_at_sec=2., observed_text_ready_at_sec=2.),
            dict(available_at_sec=1000., observed_text_ready_at_sec=1000.),
            dict(availability_clock='modeled'), dict(token_timing='phonetic')]
        for i, change in enumerate(changes):
            session, envelope = self.fixture(self.transcript(1, 'two words', final=True), name=str(i))
            path = session/'events.jsonl'; records = [json.loads(x) for x in path.read_text().splitlines()]
            records[-2]['payload'].update(change)
            path.write_text(''.join(json.dumps(x)+'\n' for x in records), encoding='utf-8')
            envelope = inspect(session, job=self.job)
            with self.subTest(i=i), self.assertRaises(ValueError):
                native.review(session, job=self.job, expected_envelope=envelope)

    def test_synchronous_formatting_and_empty_final_do_not_rewrite_raw(self):
        events = self.transcript(1, 'raw only', final=True)
        for _, p in events: p.update(display_text='Raw only.', punctuation=dict(text='Raw only.'))
        result = self.review(events, name='sync'); self.assertEqual(result['raw_final_text'], 'raw only')
        empty = self.review(self.transcript(1, '', final=True), name='emptyfinal')
        self.assertEqual(len(empty['final_revision_ids']), 1); self.assertEqual(empty['raw_final_word_count'], 0)

    def test_limits_are_enforced_before_unbounded_accumulation(self):
        for name, limit in (('MAX_REVISIONS', 1), ('MAX_UTTERANCES', 0), ('MAX_TEXT_BYTES', 2), ('MAX_TOTAL_TEXT_BYTES', 4)):
            with self.subTest(name=name), patch.object(native, name, limit), self.assertRaises(ValueError):
                self.review(self.standard(), name=name)

    def test_incomplete_history_and_changed_expected_binding_are_rejected(self):
        session, envelope = self.fixture(self.standard(), name='truncated', prefix=2)
        with self.assertRaisesRegex(ValueError, 'retained tail'):
            native.review(session, job=self.job, expected_envelope=envelope)
        session, envelope = self.fixture(self.standard(), name='changed')
        with (session/'events.jsonl').open('r+', encoding='utf-8') as stream:
            content = stream.read().replace('raw beta', 'raw zeta'); stream.seek(0); stream.write(content); stream.truncate()
        with self.assertRaisesRegex(ValueError, 'envelope changed'):
            native.review(session, job=self.job, expected_envelope=envelope)

    def test_all_nine_historical_prefixes_remain_unavailable(self):
        self.assertEqual(len(CASES), 9)
        results = []
        for case in CASES:
            envelope = inspect(case['session'], job=case['audio'])
            with self.assertRaisesRegex(ValueError, 'retained tail'):
                native.review(case['session'], job=case['audio'], expected_envelope=envelope)
            results.append(dict(cell_id=case['cell_id'], missing_prefix_events=envelope['missing_prefix_events'],
                                text_projection_status='UNAVAILABLE_INCOMPLETE_NATIVE_HISTORY'))
        freeze(self.folder/'HISTORICAL_REFUSALS.json', dict(cases=results, actual_panel_reviewed=False))
