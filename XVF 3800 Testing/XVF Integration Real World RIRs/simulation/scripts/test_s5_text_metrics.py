"""Model-free S5 scorer fixtures using the actual pinned MeetEval backend."""
import copy
import unittest
from unittest.mock import patch

import s5_text_metrics as s


def scene(utterances=('alpha beta',), speakers=None, overlap=False):
    speakers = speakers or ['A'] * len(utterances)
    return {'case_id': 'DEV', 'split': 'development', 'task_scoring_allowed': True,
            'all_speaker_reference_complete': True, 'transcript_valid': True,
            'overlap_intervals': [{'start_sample': 0, 'stop_sample': 10}] if overlap else [],
            'segments': [{'kind': 'utterance', 'transcript': text, 'speaker_key': who,
                          'source_start_sample': i * 100, 'source_stop_sample': i * 100 + 50}
                         for i, (text, who) in enumerate(zip(utterances, speakers))], 'target_references': []}


def native(texts=('alpha beta',), labels=None):
    labels = labels or ['Speaker_1'] * len(texts)
    return {'state': 'COMPLETED', 'failure_events': [], 'telemetry': {'source_duration_sec': 60},
            'final_transcripts': [{'utterance_index': i, 'text': text, 'speaker': label, 'source_cursor_s': i + 1,
                                   'display_text': 'Intentionally unrelated punctuation output.'}
                                  for i, (text, label) in enumerate(zip(texts, labels))]}


def run(ref=None, hyp=None, **kwargs):
    return s.score_scene(ref or scene(), hyp if hyp is not None else native(), development_ids={'DEV'}, **kwargs)


class TextTests(unittest.TestCase):
    def test_perfect_and_raw_field(self):
        r = run(); self.assertEqual(r['text']['wer'], 0); self.assertEqual(r['text']['cer'], 0)
        self.assertEqual(r['attributed_cpwer']['wer'], 0)

    def test_exact_historical_normalization(self):
        r = run(scene(["DON'T re-enter 21."]), native(['dont reenter 21']))
        self.assertEqual(r['text']['word_counts']['reference_words'], 3)
        self.assertEqual(r['text']['wer'], 0)

    def test_deletion_and_insertion(self):
        r = run(scene(['a b c']), native(['a b extra extra']))
        self.assertEqual(r['text']['word_counts'], {'errors': 2, 'substitutions': 1, 'deletions': 0,
                         'insertions': 1, 'reference_words': 3, 'hypothesis_words': 4})
        self.assertEqual(run(scene(['a b c']), native(['a']))['text']['word_counts']['deletions'], 2)

    def test_empty_output_is_deletions_and_missing_stream(self):
        r = run(hyp=native([])); self.assertEqual(r['text']['wer'], 1)
        self.assertEqual(r['attributed_cpwer']['missed_speaker'], 1)
        self.assertTrue(r['hypothesis_empty'])

    def test_noise_empty_reference(self):
        r = run(scene([]), native(['hallucinated two words']))
        self.assertEqual(r['population'], 'STRICT_EMPTY_REFERENCE')
        self.assertIsNone(r['text']['wer']); self.assertEqual(r['text']['empty_reference_insertions'], 3)
        self.assertEqual(r['text']['empty_reference_words_per_minute'], 3)

    def test_missing_reference_not_noise(self):
        ref = scene(['']); r = run(ref)
        self.assertEqual(r['population'], 'INCOMPLETE_REFERENCE')
        self.assertIsNone(r['text']['wer']); self.assertIsNone(r['attributed_cpwer']['wer'])

    def test_ambient_target_only_separate(self):
        ref = scene(); ref.update(all_speaker_reference_complete=False, transcript_valid=False)
        ref['target_references'] = [{'start_sample': 0, 'transcript': 'alpha beta'}]
        r = run(ref, native(['alpha beta ambient']))
        self.assertIsNone(r['text']['wer'])
        self.assertEqual(r['target_only_text']['status'], 'LIMITED_TARGET_REFERENCE_ONLY')
        self.assertEqual(r['target_only_text']['word_counts']['insertions'], 1)
        self.assertEqual(r['attributed_cpwer']['status'], 'LIMITED')

    def test_either_overlap_talker_first(self):
        for hyp in ('alpha beta gamma delta', 'gamma delta alpha beta'):
            r = run(scene(['alpha beta', 'gamma delta'], ['A', 'B'], True), native([hyp]))
            self.assertIsNone(r['text']['wer']); self.assertEqual(r['overlap_mimo']['wer'], 0)
            self.assertEqual(r['overlap_mimo']['hypothesis_streams'], 1)

    def test_overlap_missing_talker_and_duplicate_content(self):
        ref = scene(['alpha beta', 'gamma delta'], ['A', 'B'], True)
        missing = run(ref, native(['alpha beta']))['overlap_mimo']['word_counts']
        self.assertEqual(missing['deletions'], 2); self.assertEqual(missing['reference_words'], 4)
        duplicate = run(ref, native(['alpha beta gamma delta gamma delta']))['overlap_mimo']['word_counts']
        self.assertEqual(duplicate['insertions'], 2); self.assertEqual(duplicate['hypothesis_words'], 6)

    def test_no_word_shuffle_or_within_speaker_reversal(self):
        ref = scene(['a b', 'c d'], ['A', 'B'], True)
        self.assertGreater(run(ref, native(['a c b d']))['overlap_mimo']['wer'], 0)
        ref = scene(['a b', 'c d', 'e f'], ['A', 'A', 'B'], True)
        self.assertEqual(run(ref, native(['a b e f c d']))['overlap_mimo']['wer'], 0)
        self.assertGreater(run(ref, native(['c d e f a b']))['overlap_mimo']['wer'], 0)

    def test_duplicate_reference_is_not_deduplicated(self):
        ref = scene(['a b', 'a b'], ['A', 'B'], True)
        r = run(ref, native(['a b']))['overlap_mimo']['word_counts']
        self.assertEqual(r['reference_words'], 4); self.assertEqual(r['deletions'], 2)

    def test_cp_global_permutation_and_changed_return_label(self):
        ref = scene(['alpha beta', 'gamma delta'], ['A', 'B'])
        perfect = run(ref, native(['alpha beta', 'gamma delta'], ['clusterB', 'clusterA']))
        self.assertEqual(perfect['attributed_cpwer']['wer'], 0)
        ref = scene(['alpha beta', 'gamma delta'], ['A', 'A'])
        split = run(ref, native(['alpha beta', 'gamma delta'], ['Speaker_1', 'Speaker_2']))
        self.assertEqual(split['text']['wer'], 0); self.assertEqual(split['attributed_cpwer']['wer'], 1)
        self.assertEqual(split['attributed_cpwer']['falarm_speaker'], 1)

    def test_cp_above_100_valid(self):
        r = run(scene(['a b']), native(['x y z', 'q r s'], ['X', 'Y']))
        self.assertGreater(r['attributed_cpwer']['wer'], 1)

    def test_missing_emitted_label_limits_only_cp(self):
        n = native(); n['final_transcripts'][0]['speaker'] = None
        r = run(hyp=n); self.assertEqual(r['text']['wer'], 0)
        self.assertEqual(r['attributed_cpwer']['status'], 'LIMITED')

    def test_duplicate_final_index_refused(self):
        n = native(['a', 'b']); n['final_transcripts'][1]['utterance_index'] = 0
        with self.assertRaises(ValueError): run(hyp=n)

    def test_failed_model_not_empty_transcript(self):
        n = native([]); n['state'] = 'FAILED'
        with self.assertRaises(ValueError): run(hyp=n)

    def test_reserve_guard_before_task_open(self):
        ref = scene(); ref['split'] = 'reserve'
        with patch.object(s, 'load_json', side_effect=AssertionError('Task input opened')) as read:
            with self.assertRaises(PermissionError):
                s.score_scene_files(ref, development_ids={'DEV'}, metrics_path='does-not-exist.json')
            read.assert_not_called()
        ref = scene(); ref['case_id'] = 'RESERVE'
        with self.assertRaises(PermissionError): run(ref)

    def test_metrics_events_mismatch(self):
        n = native()
        events = [{'event_type': 'session_completed', 'source_time_sec': 60, 'payload': {}},
                  {'event_type': 'transcript_final', 'source_time_sec': 1, 'payload': {'utterance_index': 0, 'text': 'WRONG', 'speaker': 'X'}}]
        with self.assertRaises(ValueError): run(hyp=n, events=events)

    def test_absent_backend_keeps_primary_text(self):
        with patch.object(s, '_backend', side_effect=ImportError('test fixture only')):
            r = run(); self.assertEqual(r['text']['wer'], 0)
            self.assertEqual(r['attributed_cpwer']['status'], 'LIMITED')

    def test_decoded_duration_not_nominal_scene_length(self):
        with self.assertRaises(ValueError): run(duration_s=45)
        n = native(); n.pop('telemetry')
        with self.assertRaises(ValueError): run(hyp=n)


if __name__ == '__main__':
    unittest.main()
