"""Dedicated continuity payload guard regressions. README_CONTINUITY_SEQUENCE_V2.md."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import continuity_sequence_v2 as sequence


class GuardTests(unittest.TestCase):
    def output(self,size):
        output=Mock();output.exists.return_value=True
        item=Mock();item.is_file.return_value=True;item.stat.return_value=SimpleNamespace(st_size=size)
        output.rglob.return_value=[item];return output

    def test_report_sized_limit_does_not_reject_valid_pcm(self):
        with patch.object(sequence,'load',return_value={'target_utc':'2026-09-28T14:48:19+00:00'}),patch.object(sequence.shutil,'disk_usage',return_value=SimpleNamespace(free=100*sequence.GIB)):
            for size in (9*1024**2,38616902,sequence.MAX_OUTPUT-1):sequence.guard(self.output(size),Path('fixture'),sequence.time.monotonic())
            with self.assertRaisesRegex(ValueError,'output bound'):sequence.guard(self.output(sequence.MAX_OUTPUT),Path('fixture'),sequence.time.monotonic())

    def test_floor_reservation_is_retained(self):
        with patch.object(sequence,'load',return_value={'target_utc':'2026-09-28T14:48:19+00:00'}),patch.object(sequence.shutil,'disk_usage',return_value=SimpleNamespace(free=50*sequence.GIB)):
            with self.assertRaisesRegex(ValueError,'floor'):sequence.guard(self.output(0),Path('fixture'),sequence.time.monotonic())

    def test_deadline_and_time_budget_still_refuse(self):
        with patch.object(sequence,'load',return_value={'target_utc':'2000-01-01T00:00:00+00:00'}):
            with self.assertRaisesRegex(ValueError,'Packaging'):sequence.guard(self.output(0),Path('fixture'),sequence.time.monotonic())
        with self.assertRaisesRegex(ValueError,'time budget'):sequence.guard(self.output(0),Path('fixture'),sequence.time.monotonic()-721)

    def test_global_allowance_reserves_full_assembly_and_existing_workers(self):
        policy={'resource_policy':{'new_payload_allowance_gib':50}}
        maximum=50*sequence.GIB-6*sequence.GIB-sequence.MAX_OUTPUT
        with patch.object(sequence,'load',return_value=policy),patch.object(sequence,'payload_inventory',return_value={'errors':[],'total_logical_bytes':maximum}):
            self.assertEqual(sequence.allowance(Path('fixture'))['total_logical_bytes'],maximum)
        with patch.object(sequence,'load',return_value=policy),patch.object(sequence,'payload_inventory',return_value={'errors':[],'total_logical_bytes':maximum+1}):
            with self.assertRaisesRegex(ValueError,'allowance'):sequence.allowance(Path('fixture'))
