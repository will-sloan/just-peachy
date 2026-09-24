"""Model-free isolation accounting regressions. See README_CHECK_SUITE.md."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('check_suite_under_test', HERE/'check_suite.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


class SuiteAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='N2 suite accounting ')
        self.root = Path(self.temp.name); self.module = 'prototype.tests.test_fixture'
        self.ids = [self.module+'.Case.test_pass', self.module+'.Case.test_skip']
        self.write('CENSUS.json', dict(module=self.module, planned_tests=2, planned_test_ids=self.ids, loader_errors=[]))
        self.write('CHILD_RESULT.json', dict(module=self.module, planned_tests=2, planned_test_ids=self.ids,
            started_test_ids=self.ids, completed_test_ids=self.ids, successful=True, tests=2, failures=0,
            errors=0, skipped=1, expected_failures=0, unexpected_successes=0,
            outcomes=[dict(test_id=self.ids[0], outcome='addSuccess'), dict(test_id=self.ids[1], outcome='addSkip', reason='fixture skip')]))
        self.write('tests.json', dict(successful=True, tests=2, failures=0, errors=0, skipped=1))
        self.write('isolation.json', dict(exit_code=0, timed_out=False, input_desktop_unchanged=True,
            switch_desktop_called=False, input_injection=False, desktop_handle_closed=True))
        self.write('hardware_guard.json', dict(module=self.module, before_test_import=True,
            physical_audio_calls='disabled', external_non_python_processes='disabled', N2_TEST_E1='1'))

    def tearDown(self): self.temp.cleanup()
    def write(self, name, value): (self.root/name).write_text(json.dumps(value), encoding='utf-8')
    def row(self, code=0): return runner.inspect_module(self.root, self.module, code)

    def test_complete_module_retains_exact_skip_reason_and_count(self):
        row = self.row(); self.assertTrue(row['successful']); self.assertEqual(row['tests'], 2)
        self.assertEqual(row['skipped_tests'][0]['reason'], 'fixture skip')

    def test_zero_exit_cannot_hide_unfinished_or_missing_test(self):
        receipt = runner.load(self.root/'CHILD_RESULT.json'); receipt['completed_test_ids'] = self.ids[:1]
        self.write('CHILD_RESULT.json', receipt)
        self.assertFalse(self.row()['successful'])
        (self.root/'CHILD_RESULT.json').unlink()
        self.assertIn('missing CHILD_RESULT.json', self.row()['reasons'])
        self.write('tests.json', dict(successful=False, tests=1, failures=0, errors=1, skipped=0))
        self.assertEqual(self.row()['errors'], 1, 'loader error must remain counted without a target census')

    def test_native_crash_rejects_otherwise_successful_test_receipts(self):
        receipt = runner.load(self.root/'isolation.json'); receipt['exit_code'] = 0x80000003
        self.write('isolation.json', receipt)
        self.assertFalse(self.row(0x80000003)['successful'])

    def test_all_modules_and_original_failure_remain_in_aggregate(self):
        first = self.row(2); second = dict(self.row(), module='prototype.tests.test_second')
        admission = dict(modules=[first['module'], second['module']], source='fixture', source_receipt=None)
        report = runner.aggregate(admission, [first, second])
        self.assertEqual(report['status'], 'FAILED'); self.assertEqual(report['finished_modules'], 2)
        self.assertEqual(report['tests'], 4); self.assertEqual(report['skipped'], 2)
        self.assertEqual(report['failed_modules'], [first['module']])
        with self.assertRaises(ValueError): runner.aggregate(admission, [first, first])
        self.assertEqual(runner.aggregate(admission, [first])['status'], 'RUNNING')

    def test_bad_guard_or_mismatched_counts_never_pass(self):
        receipt = runner.load(self.root/'tests.json'); receipt['tests'] = 1
        self.write('tests.json', receipt); self.assertFalse(self.row()['successful'])
        self.write('tests.json', dict(successful=True, tests=2, failures=0, errors=0, skipped=1))
        guard = runner.load(self.root/'hardware_guard.json'); guard['before_test_import'] = False
        self.write('hardware_guard.json', guard); self.assertFalse(self.row()['successful'])


if __name__ == '__main__': unittest.main(verbosity=2)
