"""Native CPU command refusal cases; README_NATIVE_STREAM_CPU_V2.md."""
import unittest
from native_stream_cpu_config_v2 import cpu_argv


class NativeCpuTests(unittest.TestCase):
    def test_only_cpu_changes(self):
        original=['qemu','-L','sysroot','-E','LD_LIBRARY_PATH=lib','binary','model','audio']
        actual=cpu_argv(original,'cortex-a76')
        self.assertEqual(actual[1:3],['-cpu','cortex-a76'])
        self.assertEqual(actual[:1]+actual[3:],original)

    def test_wrong_contract_rejected(self):
        original=['qemu','-L','sysroot','-E','LD_LIBRARY_PATH=lib','binary','model','audio']
        for argv,cpu in [(original,'max'),(original[:-1],'cortex-a76'),
                         (original+['extra'],'cortex-a76'),
                         (original[:1]+['-cpu','max']+original[1:],'cortex-a76')]:
            with self.assertRaises(ValueError):cpu_argv(argv,cpu)


if __name__=='__main__':unittest.main()
