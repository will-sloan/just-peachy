"""CPU contrast command boundaries; README_BASELINE_ASR_CPU_V4.md."""
import unittest
from run_baseline_asr_cpu_v4 import cpu_argv


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


if __name__ == '__main__':
    unittest.main()
