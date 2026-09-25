"""Model-free factorial integrity tests; see README_COMPOSITIONS.md."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import unittest
from common import load, fingerprint
from compose_release_v3 import expand, inventory


class CompositionTests(unittest.TestCase):
    def source(self):
        worktree = Path(__file__).resolve().parents[4]
        return load(worktree / 'prototype/config/backends.json')

    def rehash(self, row):
        row['manifest_id'] = 'sha256:' + fingerprint(row['composition'])

    def test_complete_unique_factorial_preserves_source_and_baseline(self):
        source = self.source(); before = deepcopy(source)
        expanded = expand(source); rows = inventory(expanded)
        self.assertEqual(source, before)
        self.assertEqual(set(rows), set(product(('A0', 'A1', 'A2', 'A3'), ('D0', 'D1'), ('E0', 'E1'))))
        for row in source['backends']:
            self.assertEqual(next(r for r in expanded['backends'] if r['key'] == row['key']), row)
        self.assertEqual(rows[('A0', 'D0', 'E0')]['manifest_id'], 'sha256:1a6be7490786a81d971c19ad35572b8c13c30993f7b8a7c1903f4b0617b6b1b5')

    def test_each_family_keeps_exact_asr_punctuation_and_bundle(self):
        rows = inventory(expand(self.source()))
        for a in ('A1', 'A2', 'A3'):
            base = rows[(a, 'D0', 'E0')]['composition']
            for d, e in product(('D0', 'D1'), ('E0', 'E1')):
                row = rows[(a, d, e)]['composition']
                for key in ('asr', 'punctuation'):
                    self.assertEqual(row['components'][key], base['components'][key])
                self.assertEqual(row['n3'], base['n3'])
                donor = rows[('A0', d, e)]['composition']
                for key in ('diarization', 'enrollment'):
                    self.assertEqual(row['components'][key], donor['components'][key])

    def test_missing_a1_is_not_silently_a_twelve_cell_matrix(self):
        doc = self.source(); next(r for r in doc['backends'] if r['key'] == 'compact_eou')['implemented'] = False
        with self.assertRaisesRegex(ValueError, 'Missing implemented N3 adapter: A1'): expand(doc)

    def test_unbound_or_dither_a1_rejected(self):
        for name, value in [('bundle_sha256', None), ('frontend_policy', 'training_dither')]:
            doc = self.source(); row = next(r for r in doc['backends'] if r['key'] == 'compact_eou')
            row['composition']['n3'][name] = value; self.rehash(row)
            with self.assertRaisesRegex(ValueError, 'qualified portable bundle'): expand(doc)

    def test_truth_or_duplicate_composition_rejected(self):
        doc = self.source(); row = next(r for r in doc['backends'] if r['key'] == 'compact_eou')
        row['composition']['seat_truth'] = 'not permitted'; self.rehash(row)
        with self.assertRaisesRegex(ValueError, 'truth'): expand(doc)
        doc = self.source(); row = deepcopy(doc['backends'][0]); row['key'] = 'duplicate'
        doc['backends'].append(row)
        with self.assertRaisesRegex(ValueError, 'Duplicate factorial'): expand(doc)


if __name__ == '__main__': unittest.main(verbosity=2)
