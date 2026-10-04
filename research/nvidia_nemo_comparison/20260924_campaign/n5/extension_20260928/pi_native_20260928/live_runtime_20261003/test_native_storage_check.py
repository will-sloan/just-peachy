"""Private fixture/action contracts; README_NATIVE_STORAGE_CHECK.md."""
import os
from pathlib import Path
import tempfile
import unittest
from native_storage_check import run_checks
from storage import StoragePolicy
from launch_raw_qualification_action import budget_plan,wrapper_source


class NativeStorageCheckTests(unittest.TestCase):
    def test_private31_session_scenario_and_existing_root_refusal(self):
        parent=Path(os.environ['LIVE_STORAGE_ACTION_TEST_ROOT']);parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as value:
            root=Path(value)/'fresh'
            result=run_checks(root,StoragePolicy(reserve_bytes=0,reserve_fraction=0,segment_samples=32))
            self.assertEqual(result['status'],'STORAGE_CHECK_PASSED')
            self.assertEqual(result['primary_sessions'],31)
            self.assertEqual(result['sessions_created'],35)
            self.assertEqual(result['complete_replay_samples'],64)
            self.assertTrue(result['unrelated_sentinel_preserved'])
            with self.assertRaises(ValueError):run_checks(root,StoragePolicy())

    def test_storage_action_has_explicit_finite_no_model_budget(self):
        budget=budget_plan(Path('unused'),{},dict(maximum_output_bytes=16*1024**2),'storage')
        self.assertEqual(budget['mode'],'synthetic_storage_only')
        self.assertEqual(budget['runtime_seconds'],180)
        self.assertEqual(budget['file_limit_bytes'],16*1024**2)
        compile(wrapper_source(dict(kind='storage',budget=budget)),'<not-executed-storage-wrapper>','exec')
        with self.assertRaises(ValueError):budget_plan(Path('unused'),{},dict(maximum_output_bytes=1),'storage')


if __name__=='__main__':unittest.main()
