"""Protected capture-analysis branch fixtures; README_S45_ANALYSIS.md."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import s45_capture_analysis as analysis


class QuietProgress:
    """Never starts the project progress writer/thread or touches real REPORT."""
    def __init__(self, *args, **kwargs):
        self.done = 0
        self.case = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@contextlib.contextmanager
def fixture(reference=False, split='reserve'):
    with tempfile.TemporaryDirectory(prefix='jp_s45_protected_analysis_test_') as directory:
        root = Path(directory)
        bank, report, folder = root / 'bank', root / 'report', root / 'capture'
        bank.mkdir(); report.mkdir(); folder.mkdir()
        cid = 'FIXTURE_ONLY_REFERENCE' if reference else 'FIXTURE_ONLY_RESERVE'
        # No transcript, identity, activity intervals or RIR geometry is supplied:
        # protected branches must succeed without any task-reference material.
        scene = {'case_id': cid, 'split': split}
        manifest_path = bank / ('REFERENCE_SCENE_MANIFEST.json' if reference else 'SCENE_MANIFEST.json')
        analysis.save(manifest_path, {'scenes': [scene]})
        analysis.save(report / 'SPATIAL_SCORING_POLICY.json', analysis.S4_SPATIAL_POLICY)
        case_path = folder / 'case_result.json'
        analysis.save(case_path, {'case_id': cid, 'status': 'PASS'})
        selection = {'accepted_count': 1, 'accepted': [{'case_id': cid, 'folder': str(folder), 'case_result': analysis.bind(case_path)}]}
        selection_path = report / ('REFERENCE_CAPTURES.json' if reference else 'ACCEPTED_CAPTURES.json')
        analysis.save(selection_path, selection)
        counts = np.zeros((2000, 6), dtype=np.int32)
        counts[0, 4] = 2 ** 23 - 2  # One residual positive rail on O0.
        counts[100:1800, 5] = -(2 ** 23)  # A gross 1700-sample run on O1.
        left_aligned_pcm24 = counts << 8
        converter_result = {'conversion_status': 'EXACT_NATIVE_COUNTS', 'outputs': {
            output: {'mismatched_saved_vs_native_counts': 0} for output in ('O0', 'O1')}}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(analysis, 'BANK', bank))
            stack.enter_context(patch.object(analysis, 'REPORT', report))
            stack.enter_context(patch.object(analysis, 'Progress', QuietProgress))
            audio_read = stack.enter_context(patch.object(analysis.sf, 'read', return_value=(left_aligned_pcm24, 16000)))
            converter = stack.enter_context(patch.object(analysis, 'audit_converter', return_value=converter_result))
            dev_audio = stack.enter_context(patch.object(analysis, 'development_audio', side_effect=AssertionError('Forbidden development audio scorer called')))
            dev_spatial = stack.enter_context(patch.object(analysis, 'development_spatial', side_effect=AssertionError('Forbidden development spatial scorer called')))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            yield {'root': root, 'bank': bank, 'report': report, 'folder': folder, 'case_path': case_path,
                   'selection': selection, 'selection_path': selection_path, 'audio_read': audio_read,
                   'converter': converter, 'dev_audio': dev_audio, 'dev_spatial': dev_spatial}


class ProtectedAnalysisTests(unittest.TestCase):
    def check_protected(self, reference, split):
        with fixture(reference, split) as f:
            analysis.run(reference=reference)
            f['dev_audio'].assert_not_called()
            f['dev_spatial'].assert_not_called()
            f['audio_read'].assert_called_once_with(f['folder'] / 'decoded_six.wav', dtype='int32', always_2d=True)
            f['converter'].assert_called_once_with(f['folder'])
            metrics = analysis.read(f['folder'] / 'audio_metrics.json')
            self.assertEqual(metrics['task_scoring'], 'PROHIBITED_REFERENCE' if reference else 'PROHIBITED_RESERVE')
            self.assertIsNone(metrics['output_alignment'])
            self.assertEqual(metrics['streams']['O0']['rail_samples'], 1)
            self.assertEqual(metrics['streams']['O1']['maximum_contiguous_rail_run_samples'], 1700)
            self.assertIsNone(metrics['streams']['O0']['support_samples'])
            for key in ('text', 'transcript', 'speaker', 'identity', 'direction', 'reference_turn_evidence'):
                self.assertNotIn(key, metrics)
            receipt = analysis.read(f['folder'] / 's45_analysis_receipt.json')
            self.assertIsNone(receipt['spatial_metrics'])
            self.assertFalse(receipt['task_scoring_allowed'])
            self.assertFalse(receipt['reserve_task_scored'])
            self.assertEqual(receipt['excluded_from_240'], reference)
            self.assertEqual(receipt['task_use_by_output'], {'O0': 'LIMITED_RESIDUAL_RAILS', 'O1': 'QUARANTINED_GROSS_SATURATION'})
            self.assertFalse((f['folder'] / 'spatial_metrics.json').exists())
            index = analysis.read(f['report'] / ('REFERENCE_CAPTURE_ANALYSIS.json' if reference else 'CAPTURE_ANALYSIS.json'))
            self.assertEqual(index['count'], 1)
            self.assertEqual(index['excluded_from_240'], reference)

    def test_reserve_branch_levels_conversion_only(self):
        self.check_protected(False, 'reserve')

    def test_development_optional_reference_still_levels_conversion_only(self):
        self.check_protected(True, 'development')

    def test_compatible_cache_reuses_without_reopening_audio(self):
        for reference, split in [(False, 'reserve'), (True, 'development')]:
            with self.subTest(reference=reference), fixture(reference, split) as f:
                analysis.run(reference=reference)
                receipt_path = f['folder'] / 's45_analysis_receipt.json'
                prior = receipt_path.read_bytes()
                f['audio_read'].reset_mock(); f['converter'].reset_mock()
                analysis.run(reference=reference)
                f['audio_read'].assert_not_called()
                f['converter'].assert_not_called()
                f['dev_audio'].assert_not_called()
                f['dev_spatial'].assert_not_called()
                self.assertEqual(receipt_path.read_bytes(), prior)

    def test_stale_cached_analysis_code_sha_rejected_and_preserved(self):
        for reference, split in [(False, 'reserve'), (True, 'development')]:
            with self.subTest(reference=reference), fixture(reference, split) as f:
                analysis.run(reference=reference)
                cache = f['folder'] / 's45_analysis_receipt.json'
                receipt = analysis.read(cache)
                receipt['analysis_code']['sha256'] = '0' * 64
                analysis.save(cache, receipt)
                prior = cache.read_bytes()
                f['audio_read'].reset_mock(); f['converter'].reset_mock()
                with self.assertRaisesRegex(AssertionError, 'Analysis cache code/input mismatch'):
                    analysis.run(reference=reference)
                self.assertEqual(cache.read_bytes(), prior)
                f['audio_read'].assert_not_called()
                f['converter'].assert_not_called()
                f['dev_audio'].assert_not_called()
                f['dev_spatial'].assert_not_called()

    def test_stale_cached_case_sha_rejected_and_preserved(self):
        for reference, split in [(False, 'reserve'), (True, 'development')]:
            with self.subTest(reference=reference), fixture(reference, split) as f:
                analysis.run(reference=reference)
                cache = f['folder'] / 's45_analysis_receipt.json'
                prior = cache.read_bytes()
                # The authoritative accepted case changes, with a valid new SHA;
                # the old cache must not silently follow the new evidence.
                case = analysis.read(f['case_path']); case['fixture_revision'] = 2
                analysis.save(f['case_path'], case)
                selection = f['selection']
                selection['accepted'][0]['case_result'] = analysis.bind(f['case_path'])
                analysis.save(f['selection_path'], selection)
                f['audio_read'].reset_mock(); f['converter'].reset_mock()
                with self.assertRaisesRegex(AssertionError, 'Analysis cache code/input mismatch'):
                    analysis.run(reference=reference)
                self.assertEqual(cache.read_bytes(), prior)
                f['audio_read'].assert_not_called()
                f['converter'].assert_not_called()
                f['dev_audio'].assert_not_called()
                f['dev_spatial'].assert_not_called()

    def test_unbound_case_modification_rejected_before_raw_read(self):
        with fixture() as f:
            analysis.save(f['case_path'], {'case_id': 'FIXTURE_ONLY_RESERVE', 'status': 'PASS', 'tampered': True})
            with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
                analysis.run()
            f['audio_read'].assert_not_called()
            f['converter'].assert_not_called()
            self.assertFalse((f['folder'] / 'audio_metrics.json').exists())


if __name__ == '__main__':
    unittest.main()
