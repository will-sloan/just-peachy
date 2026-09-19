"""S5 text-panel boundary fixtures; run with unittest. README_S5.md."""
import unittest
from unittest.mock import patch
from s5_text_panel import score_job, resolve_native

class TextPanelTests(unittest.TestCase):
    def test_reserve_rejected_before_path_or_binding(self):
        scenes = [{'case_id': 'R', 'split': 'reserve', 'task_scoring_allowed': False}]
        with patch('s5_text_panel.bind', side_effect=AssertionError('must not open')):
            with self.assertRaises(PermissionError):
                score_job({'case_id': 'R', 'stream': 'O0'}, scenes, {}, [])

    def test_failed_native_is_not_empty_success(self):
        job = {'job_key': 'x'}
        with self.assertRaises(AssertionError):
            resolve_native(job, {'job_key': 'x', 'status': 'FAILED'})

    def test_changed_gain_is_not_compatible(self):
        job = {'job_key': 'x', 'gain': 1.0, 'raw_audio': {'sha256': 'a'}}
        r = {'job_key': 'x', 'status': 'COMPLETE', 'exit_code': 0,
             'raw_audio': job['raw_audio'], 'adapter': {'gain_scalar': 2.0}}
        with self.assertRaises(AssertionError):
            resolve_native(job, r)

if __name__ == '__main__':
    unittest.main()
