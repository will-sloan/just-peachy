"""Numerical invariants for S5 paired summaries; README_S5.md."""
import copy
import unittest
from s5_statistics import pooled, paired, uncertainty

def row(cid, words, e0, e1, room='ROOM'):
    def metric(e):
        return {'text': {'word_counts': {'reference_words': words, 'hypothesis_words': words,
                  'errors': e, 'substitutions': e, 'insertions': 0, 'deletions': 0}}}
    return {'case_id': cid, 'room': room, 'O0': metric(e0), 'O1': metric(e1)}

def dependency(rows, groups):
    return {'blocks': [{'primary_scene_ids': ids, 'room_table': rows[0]['room']} for ids in groups],
            'dependency_diagnostics': {'speaker': {'primary_components': [[r['case_id']] for r in rows]}},
            'all_dependencies_primary_component_sizes': [len(rows)]}

class S5StatisticsTests(unittest.TestCase):
    def test_pooled_counts_not_macro(self):
        rows = [row('a', 1, 1, 0), row('b', 99, 0, 1)]
        r = paired(rows)
        self.assertEqual(r['O0']['wer'], .01)
        self.assertEqual(r['O0']['macro_scene_wer'], .5)
        self.assertEqual(r['O1_minus_O0_wer_pp'], 0)
        self.assertEqual(r['O0_better_scenes'], 1)
        self.assertEqual(r['O1_better_scenes'], 1)

    def test_mismatched_reference_fails(self):
        r = row('a', 10, 1, 2)
        r['O1']['text']['word_counts']['reference_words'] = 11
        with self.assertRaises(AssertionError):
            paired([r])

    def test_matched_pair_stays_whole_and_deterministic(self):
        rows = [row('a', 10, 1, 0), row('b', 10, 0, 1), row('c', 10, 1, 1)]
        dep = dependency(rows, [['a', 'b'], ['c']])
        a = uncertainty(rows, dep, 200, 4)
        b = uncertainty(rows, dep, 200, 4)
        self.assertEqual(a, b)
        self.assertEqual(a['paired_O1_minus_O0_wer_pp_percentile95'], [0, 0])
        self.assertEqual(a['matched_block_count'], 2)

    def test_duplicate_block_membership_fails(self):
        rows = [row('a', 10, 0, 1), row('b', 10, 0, 1)]
        with self.assertRaises(AssertionError):
            uncertainty(rows, dependency(rows, [['a', 'b'], ['a']]), 10)

    def test_missing_is_not_zero_error(self):
        r = row('a', 10, 1, 2)
        r['O1'] = None
        self.assertEqual(paired([r])['paired_scenes'], 0)
        self.assertIsNone(paired([r])['O1_minus_O0_wer_pp'])

if __name__ == '__main__':
    unittest.main()
