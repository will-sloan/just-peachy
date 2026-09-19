"""Hash read-open retry tests; no hardware or actual sleeping."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from measurement_app import core


class HashOpenTests(unittest.TestCase):
    def test_exact_hash_across_chunk_boundaries_and_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.bin'
            for payload in [b'', bytes(range(256)) * 10000 + b'\x00\xffend']:
                with self.subTest(length=len(payload)):
                    path.write_bytes(payload)
                    with patch.object(core.time, 'sleep') as sleep:
                        self.assertEqual(core.sha(path), hashlib.sha256(payload).hexdigest())
                    sleep.assert_not_called()

    def test_transient_open_permission_denial_retries_then_hashes_once(self):
        payload = b'preserved original bytes\x00\xff'
        handle = io.BytesIO(payload)
        with patch.object(core.Path, 'open', side_effect=[PermissionError('sync lock'), PermissionError('indexer lock'), handle]) as opening, \
                patch.object(core.time, 'sleep') as sleep:
            self.assertEqual(core.sha('evidence.bin'), hashlib.sha256(payload).hexdigest())
        self.assertEqual(opening.call_args_list, [call('rb')] * 3)
        self.assertEqual(sleep.call_args_list, [call(.025), call(.05)])
        self.assertTrue(handle.closed)

    def test_persistent_permission_denial_has_seven_attempts_and_finite_backoff(self):
        error = PermissionError('persistent permission failure')
        with patch.object(core.Path, 'open', side_effect=error) as opening, \
                patch.object(core.time, 'sleep') as sleep:
            with self.assertRaises(PermissionError) as raised:
                core.sha('evidence.bin')
        self.assertIs(raised.exception, error)
        self.assertEqual(opening.call_count, 7)
        self.assertEqual(sleep.call_args_list, [call(.025), call(.05), call(.1), call(.2), call(.4), call(.4)])
        self.assertAlmostEqual(sum(args.args[0] for args in sleep.call_args_list), 1.175)

    def test_read_failure_after_partial_hash_is_never_reopened_or_retried(self):
        for error in [PermissionError('read lock'), OSError('read failure')]:
            with self.subTest(error=type(error).__name__):
                handle = Mock()
                handle.__enter__ = Mock(return_value=handle)
                handle.__exit__ = Mock(return_value=False)
                handle.read.side_effect = [b'partially read original evidence', error]
                with patch.object(core.Path, 'open', return_value=handle) as opening, \
                        patch.object(core.time, 'sleep') as sleep:
                    with self.assertRaises(type(error)) as raised:
                        core.sha('evidence.bin')
                self.assertIs(raised.exception, error)
                opening.assert_called_once_with('rb')
                self.assertEqual(handle.read.call_count, 2)
                handle.__exit__.assert_called_once()
                sleep.assert_not_called()

    def test_nonpermission_open_errors_are_immediate(self):
        for error in [FileNotFoundError('missing'), OSError('device I/O error')]:
            with self.subTest(error=type(error).__name__):
                with patch.object(core.Path, 'open', side_effect=error) as opening, \
                        patch.object(core.time, 'sleep') as sleep:
                    with self.assertRaises(type(error)) as raised:
                        core.sha('evidence.bin')
                self.assertIs(raised.exception, error)
                opening.assert_called_once_with('rb')
                sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
