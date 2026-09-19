"""Synthetic metadata-only fixtures. README_S5_COVERAGE.md."""
import copy
from pathlib import Path
import tempfile
import unittest

from s5_coverage import Evidence, components, population


def scene():
    return {'split': 'development', 'task_scoring_allowed': True, 'all_speaker_reference_complete': True,
            'transcript_valid': True, 'overlap_intervals': [], 'segments': [{'kind': 'utterance', 'transcript': 'Native text.'}]}


class CoverageTests(unittest.TestCase):
    def test_complete_populations(self):
        q = scene()
        self.assertEqual(population(q), 'COMPLETE_REFERENCE_NONOVERLAP')
        q['overlap_intervals'] = [[1, 2]]
        self.assertEqual(population(q), 'COMPLETE_REFERENCE_OVERLAP')

    def test_incomplete_ambient_has_priority(self):
        q = scene(); q['all_speaker_reference_complete'] = False; q['transcript_valid'] = False; q['overlap_intervals'] = [[1, 2]]
        self.assertEqual(population(q), 'INCOMPLETE_AMBIENT_REFERENCE')

    def test_strict_empty_and_unknown_noise(self):
        q = scene(); q['segments'] = []
        self.assertEqual(population(q), 'STRICT_EMPTY_REFERENCE')
        q['segments'] = [{'kind': 'real_noise', 'strict_nonspeech_eligible': False}]
        with self.assertRaises(ValueError): population(q)
        q['segments'][0]['strict_nonspeech_eligible'] = True
        self.assertEqual(population(q), 'STRICT_EMPTY_REFERENCE')

    def test_protected_metadata_is_not_task_population(self):
        q = scene(); q['split'] = 'reserve'; q['task_scoring_allowed'] = False
        self.assertEqual(population(q), 'PROTECTED_RESERVE_METADATA_ONLY')
        q['task_scoring_allowed'] = True
        with self.assertRaises(ValueError): population(q)

    def test_missing_text_not_forced_complete(self):
        q = scene(); q['segments'][0]['transcript'] = ''
        with self.assertRaises(ValueError): population(q)

    def test_transitive_matched_union_is_order_independent(self):
        ids = ['A', 'B', 'C', 'D']
        groups = [['A', 'B'], ['B', 'C']]
        self.assertEqual(components(groups, ids), [['A', 'B', 'C'], ['D']])
        self.assertEqual(components(reversed(groups), reversed(ids)), [['A', 'B', 'C'], ['D']])

    def test_primary_projection_preserves_match_through_control(self):
        full = components([['A', 'CONTROL'], ['CONTROL', 'B']], ['A', 'B', 'CONTROL'])
        projected = [sorted(set(g) & {'A', 'B'}) for g in full]
        self.assertEqual(projected, [['A', 'B']])

    def test_reader_refuses_audio_and_task_results(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ['source.wav', 'output.pcm16', 'metrics.json', 'events.jsonl', 'audio_metrics.json']:
                p = Path(td) / name; p.write_bytes(b'{}')
                with self.assertRaises(ValueError): Evidence().bind(p)

    def test_metadata_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'manifest.json'; p.write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError): Evidence().bind(p, '0' * 64)
            ev = Evidence(); self.assertEqual(ev.read(p), {})
            p.write_text('{"changed":true}', encoding='utf-8')
            with self.assertRaises(ValueError): ev.bind(p)


if __name__ == '__main__':
    unittest.main()
