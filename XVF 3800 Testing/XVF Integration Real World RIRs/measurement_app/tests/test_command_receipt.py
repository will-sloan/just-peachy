import io
import json
import unittest
from unittest.mock import patch
from measurement_app import core


class ReceiptTests(unittest.TestCase):
    def test_transient_open_lock_retries_receipt_only(self):
        class Buffer(io.StringIO):
            def close(self): pass
        output=Buffer()
        with patch.object(core.Path,'open',side_effect=[PermissionError(13,'locked'),output]) as op, patch.object(core.time,'sleep'):
            core.append_command_receipt('unused.jsonl',{'sequence':1,'stdout':'already executed'})
        self.assertEqual(op.call_count,2)
        self.assertEqual([json.loads(x) for x in output.getvalue().splitlines()],[{'sequence':1,'stdout':'already executed'}])

    def test_write_failure_is_not_retried(self):
        class Broken(io.StringIO):
            def write(self,text):raise PermissionError(13,'write failed')
        with patch.object(core.Path,'open',return_value=Broken()) as op:
            with self.assertRaises(PermissionError):core.append_command_receipt('unused.jsonl',{'sequence':2})
        self.assertEqual(op.call_count,1)

    def test_persistent_open_lock_has_finite_attempts(self):
        with patch.object(core.Path,'open',side_effect=PermissionError(13,'locked')) as op, patch.object(core.time,'sleep'):
            with self.assertRaises(PermissionError):core.append_command_receipt('unused.jsonl',{'sequence':3})
        self.assertEqual(op.call_count,7)


if __name__=='__main__':unittest.main()
