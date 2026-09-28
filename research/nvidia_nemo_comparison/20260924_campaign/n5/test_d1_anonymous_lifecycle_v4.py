"""Model-free V2 refusal tests; README_D1_ANONYMOUS_LIFECYCLE_V4.md."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
import test_d1_anonymous_lifecycle_v1 as original
from test_nemotron_windows_lifecycle_v1 import ReceiptRefusals
from d1_anonymous_lifecycle_v4 import bypass_acceptance, output_bytes


class BypassRefusals(original.BypassRefusals):
    def setUp(self):
        super().setUp()
        self.binding=patch.object(original,'bypass_acceptance',bypass_acceptance)
        self.binding.start();self.addCleanup(self.binding.stop)


class OutputAccounting(unittest.TestCase):
    def test_concurrent_delete_is_not_failure(self):
        kept=Mock();kept.is_file.return_value=True;kept.stat.return_value=SimpleNamespace(st_size=123)
        deleted=Mock();deleted.is_file.return_value=True;deleted.stat.side_effect=FileNotFoundError()
        root=Mock();root.rglob.return_value=[kept,deleted]
        self.assertEqual(output_bytes(root),123)

    def test_other_errors_are_not_suppressed(self):
        denied=Mock();denied.is_file.return_value=True;denied.stat.side_effect=PermissionError()
        root=Mock();root.rglob.return_value=[denied]
        with self.assertRaises(PermissionError):output_bytes(root)


if __name__=='__main__':unittest.main()
