"""Model-free S5 boundary/lifecycle/adapter fixtures. README_S5.md."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from s5_common import DevelopmentGuard, GAINS, bind
from s5_runner import permitted_attempt, same_process
from s4_h2_run import fixed_gain_copy
from s45_h2_run import verify_native_completion

class S5RunnerTests(unittest.TestCase):
    def test_reserve_refused_before_callback(self):
        guard = DevelopmentGuard([{'case_id': 'D', 'split': 'development', 'task_scoring_allowed': True},
                                  {'case_id': 'R', 'split': 'reserve', 'task_scoring_allowed': False}], receipt=False)
        for cid in ('R', 'MISSING'):
            with self.assertRaises(PermissionError):
                guard.require(cid, 'audio_open')
        self.assertEqual(guard.counts, {})
        self.assertEqual(guard.flush()['reserve_task_accesses'], 0)
        self.assertEqual(guard.require('D', 'audio_open')['case_id'], 'D')

    def test_retry_once_and_preserve_identity(self):
        job = {'job_key': 'frozen'}
        self.assertEqual(permitted_attempt([], job), 1)
        self.assertEqual(permitted_attempt([{'job_key': 'frozen'}], job), 2)
        self.assertIsNone(permitted_attempt([{'job_key': 'frozen'}] * 2, job))
        with self.assertRaises(AssertionError):
            permitted_attempt([{'job_key': 'different'}], job)

    def test_no_retry_live_prior_child(self):
        with patch('s5_runner.same_process', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'still alive'):
                permitted_attempt([{'job_key': 'frozen', 'owned_process_pid': 123, 'owned_process_creation_time': 1}], {'job_key': 'frozen'})

    def test_exact_gain_once_and_incompatible_second_gain(self):
        with tempfile.TemporaryDirectory() as d:
            raw, dest = Path(d) / 'raw.wav', Path(d) / 'adapter.wav'
            sf.write(raw, np.array([0, .1, -.2, .01], np.float32), 16000, subtype='PCM_24')
            r = fixed_gain_copy(raw, dest, GAINS['O0'])
            source, _ = sf.read(raw, dtype='float32')
            output, _ = sf.read(dest, dtype='float32')
            np.testing.assert_array_equal(output, (source.astype(np.float64) * GAINS['O0']).astype(np.float32))
            self.assertEqual(r['journal_clip_input_samples'], 0)
            with self.assertRaises(RuntimeError):
                fixed_gain_copy(raw, dest, GAINS['O0'] ** 2)

    def test_hash_mismatch_and_changed_stat(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'source'
            p.write_bytes(b'a')
            old = bind(p)
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                bind(p, old['sha256'])

    def test_existing_positive_rail_is_retained_not_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            raw, dest = Path(d) / 'raw.wav', Path(d) / 'adapter.wav'
            sf.write(raw, np.array([-.99999, .999999], np.float32), 16000, subtype='PCM_24')
            r = fixed_gain_copy(raw, dest, GAINS['O1'])
            self.assertGreater(r['journal_clip_input_samples'], 0)
            self.assertEqual(r['gain_scalar'], 1)
            np.testing.assert_array_equal(sf.read(raw, dtype='float32')[0], sf.read(dest, dtype='float32')[0])

    def test_full_journal_not_only_summary(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / 'input.wav'
            sf.write(src, np.array([0, .1, -.1], np.float32), 16000, subtype='FLOAT')
            (root / 'session_summary.json').write_text(json.dumps({'state': 'COMPLETED', 'telemetry': {}}))
            (root / 'events.jsonl').write_text(json.dumps({'event_type': 'session_completed'}) + '\n')
            (root / 'audio.pcm16').write_bytes(b'\0\0')
            with self.assertRaisesRegex(AssertionError, 'complete input'):
                verify_native_completion(root, src)

if __name__ == '__main__':
    unittest.main()
