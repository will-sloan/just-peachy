"""Model-free S5 timing and emitted-snapshot fixtures."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from s5_timing_metrics import analyze_timing, transcript_revisions


def event(kind, seconds, payload=None, cursor=None):
    return {'event_type': kind, 'wall_time_utc': f'2026-09-09T13:00:{seconds:02d}+00:00',
            'source_time_sec': seconds if cursor is None else cursor, 'payload': payload or {}}


def transcript(kind, seconds, index, text, label):
    return event(kind, seconds, {'utterance_index': index, 'text': text, 'speaker': label,
                                'display_text': 'Unrelated polished text'}, cursor=4)


def data():
    ref = {'case_id': 'DEV', 'split': 'development', 'task_scoring_allowed': True}
    receipt = {'schema': 'jp_s5_native_attempt_v1', 'case_id': 'DEV', 'stream': 'O0',
               'status': 'COMPLETE', 'exit_code': 0, 'model_wall_s': 18.2,
               'created_utc': '2026-09-09T13:00:00+00:00',
               'owned_process_creation_time': 1788958801., 'owned_process_pid': 999,
               'model_exited_utc': '2026-09-09T13:00:19+00:00',
               'completed_utc': '2026-09-09T13:00:20+00:00',
               'adapter': {'duration_s': 44.2}, 'queue_wait_since_s5_start_s': 300,
               'queue_wait_scope': 'Includes preparation and prior serial jobs'}
    # Derive fixture epoch once to avoid a manually guessed date constant.
    from datetime import datetime
    receipt['owned_process_creation_time'] = datetime.fromisoformat('2026-09-09T13:00:01+00:00').timestamp()
    events = [event('session_created', 5), event('session_started', 7), event('source_started', 8),
              transcript('transcript_partial', 9, 1, 'HELLO', 'Speaker_1'),
              transcript('transcript_partial', 10, 1, 'HELLO THERE', 'Speaker_1'),
              transcript('transcript_final', 11, 1, 'HELLO WORLD', 'Speaker_2'),
              event('session_completed', 15, {'telemetry': {'source_duration_sec': 44.2, 'elapsed_wall_sec': 10,
                    'speaker_analyzed_through_sec': 44, 'speaker_unanalyzed_short_tail_sec': .2}}, cursor=44.2)]
    return ref, receipt, events


def score(ref=None, receipt=None, events=None, origin='fresh_s5'):
    base = data()
    return analyze_timing(receipt or base[1], events or base[2], scene=ref or base[0], development_ids={'DEV'}, origin=origin)


class TimingTests(unittest.TestCase):
    def test_recorded_intervals_and_distinct_wall_definitions(self):
        r = score()
        self.assertEqual(r['intervals_s']['process_created_to_session_created'], 4)
        self.assertEqual(r['intervals_s']['source_started_to_session_completed'], 7)
        self.assertEqual(r['intervals_s']['session_completed_to_child_exit'], 4)
        self.assertEqual(r['intervals_s']['child_exit_to_receipt_complete'], 1)
        self.assertEqual(r['model_child_wall_s'], 18.2)
        self.assertEqual(r['intervals_s']['process_created_to_child_exit'], 18)
        self.assertEqual(r['native_source_tail']['speaker_unanalyzed_short_tail_sec'], .2)
        self.assertIsNone(r['unsupported']['live_word_latency'])

    def test_historical_missing_process_creation_not_inferred(self):
        _, receipt, _ = data(); receipt['schema'] = 'jp_s45_h2_job_v1'
        receipt.pop('owned_process_creation_time')
        r = score(receipt=receipt, origin='reused_s45')
        self.assertIsNone(r['intervals_s']['process_created_to_session_created'])
        self.assertEqual(r['intervals_s']['receipt_created_to_session_created'], 5)
        self.assertIsNone(r['queue_wait_since_s5_start_s'])

    def test_origin_must_match_original_native_schema(self):
        with self.assertRaises(ValueError): score(origin='reused_s45')
        with self.assertRaises(ValueError): score(origin='pooled')

    def test_prefix_append_vs_rewrite_and_label_snapshot(self):
        r = score()['transcript_revisions']; c = r['counts']
        self.assertEqual(c['prefix_append_transitions'], 1)
        self.assertEqual(c['lexical_rewrite_transitions'], 1)
        self.assertEqual(c['removed_suffix_tokens'], 1)
        self.assertEqual(c['added_suffix_tokens'], 2)
        self.assertEqual(c['emitted_label_changed_transitions'], 1)
        self.assertTrue(r['utterances'][0]['final_label_differs_from_first_partial'])
        self.assertIsNone(r['post_merge_reconciliation'])

    def test_duplicate_final_refused(self):
        _, _, e = data(); e.insert(-1, transcript('transcript_final', 12, 1, 'HELLO', 'Speaker_2'))
        with self.assertRaises(ValueError): score(events=e)

    def test_partial_after_final_refused(self):
        _, _, e = data(); e.insert(-1, transcript('transcript_partial', 12, 1, 'HELLO', 'Speaker_2'))
        with self.assertRaises(ValueError): score(events=e)

    def test_native_empty_decode_and_missing_final_are_explicit(self):
        _, _, events = data(); events = [e for e in events if not e['event_type'].startswith('transcript')]
        r = score(events=events)['transcript_revisions']
        self.assertEqual(r['utterance_count'], 0)
        events.insert(-1, transcript('transcript_partial', 12, 2, 'fragment', None))
        r = score(events=events)['transcript_revisions']
        self.assertEqual(r['utterances_without_final'], 1)
        self.assertIsNone(r['utterances'][0]['final_label_differs_from_first_partial'])

    def test_partial_word_revision_not_accuracy(self):
        events = [transcript('transcript_partial', 1, 1, 'NO', 'A'), transcript('transcript_final', 2, 1, 'NORTH', 'A')]
        r = transcript_revisions(events)
        self.assertEqual(r['counts']['lexical_rewrite_transitions'], 1)
        self.assertNotIn('word_errors', r)

    def test_display_and_raw_case_do_not_create_lexical_rewrite(self):
        events = [transcript('transcript_partial', 1, 1, 'HELLO', 'A'), transcript('transcript_final', 2, 1, 'Hello!', 'A')]
        r = transcript_revisions(events)['counts']
        self.assertEqual(r['raw_text_changed_transitions'], 1)
        self.assertEqual(r['normalized_text_changed_transitions'], 0)
        self.assertEqual(r['lexical_rewrite_transitions'], 0)

    def test_clock_reversal_is_limited_not_absolute_value(self):
        _, receipt, _ = data(); receipt['model_exited_utc'] = '2026-09-09T13:00:14+00:00'
        r = score(receipt=receipt)
        self.assertEqual(r['status'], 'LIMITED_HOST_CLOCK_ANOMALY')
        self.assertIsNone(r['intervals_s']['session_completed_to_child_exit'])
        self.assertTrue(r['host_clock_anomalies'])

    def test_reserve_refused_before_inspecting_native_events(self):
        ref, _, _ = data(); ref['split'] = 'reserve'
        with self.assertRaises(PermissionError):
            analyze_timing({}, None, scene=ref, development_ids={'DEV'}, origin='fresh_s5')

    def test_failed_nonterminal_and_duration_mismatch_refused(self):
        _, receipt, events = data(); receipt['exit_code'] = 1
        with self.assertRaises(ValueError): score(receipt=receipt)
        _, _, events = data(); events.append(transcript('transcript_final', 18, 2, 'late', 'A'))
        with self.assertRaises(ValueError): score(events=events)
        _, receipt, _ = data(); receipt['adapter']['duration_s'] = 1
        with self.assertRaises(ValueError): score(receipt=receipt)

    def test_missing_label_is_not_counted_as_correction(self):
        events = [transcript('transcript_partial', 1, 1, 'hi', None), transcript('transcript_final', 2, 1, 'hi', 'A')]
        r = transcript_revisions(events)
        self.assertEqual(r['counts']['missing_label_transitions'], 1)
        self.assertEqual(r['counts']['emitted_label_changed_transitions'], 0)
        self.assertIsNone(r['utterances'][0]['final_label_differs_from_first_partial'])


if __name__ == '__main__':
    unittest.main()
