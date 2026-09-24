"""No-model injected sharing-violation and persistent-failure tests; README_IO.md."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import io_utils


def denial(code):
    error=PermissionError('Injected Windows sharing/access denial')
    error.winerror=code
    return error


class AtomicRetryTest(unittest.TestCase):
    def test_transient_sharing_violation_preserves_then_replaces(self):
        with tempfile.TemporaryDirectory(prefix='n2-io-test-') as directory:
            path=Path(directory)/'progress.json'
            path.write_text('{"old":true}')
            replace=io_utils.os.replace
            calls=[]
            def transient(source,destination):
                calls.append(1)
                if len(calls)<=2:
                    self.assertEqual(json.loads(path.read_text()),{'old':True})
                    raise denial(32)
                replace(source,destination)
            with patch.object(io_utils.os,'replace',side_effect=transient):
                io_utils.atomic(path,{'new':True})
            self.assertEqual(len(calls),3)
            self.assertEqual(json.loads(path.read_text()),{'new':True})
            self.assertFalse(list(Path(directory).glob('*.tmp')))

    def test_persistent_access_denial_is_bounded_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory(prefix='n2-io-test-') as directory:
            path=Path(directory)/'progress.json'
            path.write_text('{"old":true}')
            started=time.monotonic()
            with patch.object(io_utils.os,'replace',side_effect=denial(5)) as mocked:
                with self.assertRaises(PermissionError):io_utils.atomic(path,{'new':True})
            elapsed=time.monotonic()-started
            self.assertGreaterEqual(elapsed,1.9)
            self.assertLess(elapsed,2.5)
            self.assertGreater(mocked.call_count,2)
            self.assertEqual(json.loads(path.read_text()),{'old':True})
            staged=list(Path(directory).glob('*.tmp'))
            self.assertEqual(len(staged),1)
            self.assertEqual(json.loads(staged[0].read_text()),{'new':True})

    def test_unrelated_permission_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory(prefix='n2-io-test-') as directory:
            with patch.object(io_utils.os,'replace',side_effect=denial(123)) as mocked:
                with self.assertRaises(PermissionError):io_utils.atomic(Path(directory)/'x.json',{})
            self.assertEqual(mocked.call_count,1)


if __name__=='__main__':unittest.main(verbosity=2)
