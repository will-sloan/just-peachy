"""Pure model-manifest and capability tests. See README_N1_FRONTEND.md."""
from copy import deepcopy
import unittest

from prototype.app.backends import (BASELINE_BACKEND_ID, backend_catalog,
    backend_manifest, backend_status, manifest_id, require_backend)
from prototype.app.mode_policy import MODES, SPATIAL_PARENTS


class BackendCatalogTests(unittest.TestCase):
    def test_manifest_ids_bind_only_composition_and_are_unique(self):
        rows = backend_catalog()
        self.assertEqual(len(rows), len({row['manifest_id'] for row in rows}))
        for row in rows:
            self.assertEqual(row['manifest_id'], manifest_id(row['composition']))
            self.assertFalse(set(row['composition']) & {'mode', 'recipe', 'tap', 'roster', 'seat_truth'})
            changed = deepcopy(row['composition']); changed['runtime'] += 'changed'
            self.assertNotEqual(row['manifest_id'], manifest_id(changed))
            self.assertEqual(set(row['compatible_modes']), set(MODES))

    def test_n2_n3_compositions_and_no_unimplemented_seed_fallback(self):
        self.assertEqual({r['key'] for r in backend_catalog() if r['implemented']},
            {'baseline','nemotron_hybrid','titanet','nemotron_titanet','compact_eou','nemotron_600m','nemotron_35_600m'})
        self.assertEqual(BASELINE_BACKEND_ID,'sha256:1a6be7490786a81d971c19ad35572b8c13c30993f7b8a7c1903f4b0617b6b1b5')
        for row in backend_catalog():
            if not row['implemented']:
                for mode in MODES:
                    status = backend_status(row['manifest_id'], mode, 'O0', recorded_spatial=True)
                    self.assertFalse(status['available'])
                    self.assertEqual(status['reason'], row['reason'])
                    with self.assertRaisesRegex(ValueError, 'UNAVAILABLE'):
                        require_backend(row['manifest_id'], mode)

    def test_spatial_requires_matching_telemetry_without_hiding_mode(self):
        for mode in MODES:
            status = backend_status(BASELINE_BACKEND_ID, mode)
            self.assertEqual(status['available'], mode not in SPATIAL_PARENTS)
            self.assertTrue(backend_status(BASELINE_BACKEND_ID, mode, recorded_spatial=True)['available'])
            self.assertEqual(set(status['compatible_modes']), set(MODES))

    def test_returned_manifests_cannot_mutate_registry(self):
        manifest = backend_manifest(BASELINE_BACKEND_ID)
        manifest['composition']['runtime'] = 'changed'
        self.assertNotEqual(backend_manifest(BASELINE_BACKEND_ID)['composition']['runtime'], 'changed')
        with self.assertRaises(ValueError): backend_manifest('unknown')


if __name__ == '__main__': unittest.main()
