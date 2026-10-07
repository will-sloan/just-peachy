"""No logical metadata quota, bounded I/O, real disk guard. See README_RUNTIME_CAPACITY.md."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime_support import DiskBudget, SegmentedText


class RuntimeCapacityContracts(unittest.TestCase):
    def test_aggregate_estimate_is_accounting_and_does_not_refuse_more_metadata(self):
        budget = DiskBudget(2,reserve_bytes=0)
        budget.claim(1000)
        self.assertEqual(budget.maximum,2)
        self.assertEqual(budget.accepted,1000)
        budget.unclaim(10)
        self.assertEqual(budget.accepted,990)
        with self.assertRaises(ValueError):
            budget.unclaim(1000)

    def test_writer_beyond_duration_estimate_drains_and_closes_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'events.jsonl'
            usage = SimpleNamespace(total=10**9,free=10**9)
            with patch('runtime_support.shutil.disk_usage',return_value=usage):
                writer = SegmentedText(path,maximum_bytes=4,reserve_bytes=0,segment_bytes=64,queue_bytes=2048)
                writer.write('first actual event\n')
                writer.write('second actual event\n')
                writer.close()
            index = json.loads(path.with_name(path.name+'.index.json').read_bytes())
            self.assertTrue(index['complete'])
            self.assertFalse(index['cumulative_quota_enforced'])
            self.assertGreater(index['completed_bytes'],index['planned_writer_bytes'])
            self.assertEqual(b''.join(p.read_bytes() for p in sorted(path.parent.glob('events.jsonl.[0-9]*'))),
                b'first actual event\nsecond actual event\n')

    def test_physical_reserve_still_rejects_real_disk_pressure(self):
        budget = DiskBudget(1,reserve_bytes=100,reserve_fraction=.05)
        with patch('runtime_support.shutil.disk_usage',return_value=SimpleNamespace(total=1000,free=100)):
            with self.assertRaisesRegex(OSError,'Storage floor'):
                budget.check_free('.',1)
        with patch('runtime_support.shutil.disk_usage',return_value=SimpleNamespace(total=1000,free=101)):
            budget.check_free('.',1)

    def test_individual_record_ram_bound_remains_and_reports_correct_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            writer = SegmentedText(Path(temporary)/'events.jsonl',maximum_bytes=1,
                reserve_bytes=0,segment_bytes=64,queue_bytes=2048)
            with self.assertRaises(BufferError):
                writer.write('x'*65)
            self.assertEqual(writer.refusal['boundary'],'logical_record')
            self.assertFalse(writer.refusal['cumulative_quota_enforced'])
            with self.assertRaises(RuntimeError):
                writer.close()
            self.assertFalse(writer.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
