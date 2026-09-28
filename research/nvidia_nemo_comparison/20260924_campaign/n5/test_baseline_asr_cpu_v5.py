"""CPU contrast command boundaries; README_BASELINE_ASR_CPU_V5.md."""
import unittest
from run_baseline_asr_cpu_v5 import cpu_argv, check_cpu_help


class CpuContrastTests(unittest.TestCase):
    def setUp(self):
        self.original = ['/qemu','-L','/sysroot','-E','LD_LIBRARY_PATH=/lib','/binary','encoder','decoder','joiner','tokens','audio']

    def test_only_cpu_selection_changes(self):
        result = cpu_argv(self.original,'cortex-a76')
        self.assertEqual(result[1:3], ['-cpu','cortex-a76'])
        self.assertEqual(result[:1]+result[3:], self.original)

    def test_wrong_cpu_or_ambiguous_original_is_refused(self):
        for original, cpu in [(self.original,'max'), (self.original[:-1],'cortex-a76'),
                              (self.original[:1]+['-cpu','max']+self.original[1:],'cortex-a76')]:
            with self.assertRaises(ValueError):
                cpu_argv(original,cpu)


    def test_normal_help_exit_one_is_not_an_inference_pass(self):
        check_cpu_help(dict(returncode=1,cancelled=None,remaining_group_members=[]),
                       'Available CPUs:\n  cortex-a76\n  max\n', '')

    def test_help_error_is_refused(self):
        for receipt, error in [(dict(returncode=2,cancelled=None,remaining_group_members=[]), ''),
                               (dict(returncode=1,cancelled='model_timeout',remaining_group_members=[]), ''),
                               (dict(returncode=1,cancelled=None,remaining_group_members=[]), 'error')]:
            with self.assertRaises(ValueError):check_cpu_help(receipt,'Available CPUs:\n  cortex-a76\n',error)

    def test_cpu_token_must_match_exactly(self):
        with self.assertRaises(ValueError):
            check_cpu_help(dict(returncode=1,cancelled=None,remaining_group_members=[]),
                           'Available CPUs:\n  cortex-a760\n', '')


if __name__ == '__main__':
    unittest.main()
