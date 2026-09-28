"""Safety properties for shadow instrumentation; see README_SHADOW.md."""
import types
import unittest

import numpy as np

from shadow_gate_v1 import ShadowGate, install


class ShadowTests(unittest.TestCase):
    def test_complete_zero_input_has_guard_and_no_actual_skip(self):
        g = ShadowGate()
        for _ in range(16):
            g.observe(np.zeros(320, dtype=np.float32))
        report = g.report()
        self.assertEqual(report['samples'], 5120)
        self.assertEqual(report['actually_skipped_samples'], 0)
        for row in report['proposed_methods'].values():
            self.assertEqual(row['proposed_skip_samples'], 320)

    def test_one_nonzero_sample_is_not_exact_zero(self):
        g = ShadowGate(guard_samples=0)
        block = np.zeros(320, dtype=np.float32)
        block[-1] = 1 / 32768
        g.observe(block)
        self.assertFalse(g.rows[-1]['proposed_skip']['G01'])
        self.assertTrue(g.rows[-1]['proposed_skip']['G02'])

    def test_causal_history_not_changed_by_later_loud_audio(self):
        g = ShadowGate(guard_samples=0)
        g.observe(np.zeros(320, dtype=np.float32))
        prior = dict(g.rows[0])
        g.observe(np.full(320, 0.5, dtype=np.float32))
        self.assertEqual(prior, g.rows[0])

    def test_trailing_guard_and_remainder_accounting(self):
        g = ShadowGate()
        g.observe(np.full(320, 0.5, dtype=np.float32))
        for _ in range(15):
            g.observe(np.zeros(320, dtype=np.float32))
        self.assertFalse(any(r['proposed_skip']['G02'] for r in g.rows))
        g.observe(np.zeros(7, dtype=np.float32))
        self.assertTrue(g.rows[-1]['proposed_skip']['G02'])
        self.assertEqual((g.rows[-1]['start_sample'], g.rows[-1]['end_sample']), (5120, 5127))

    def test_unknown_invalid_input_refuses_instead_of_proposing_skip(self):
        for values in ([], [float('nan')], [float('inf')], [1.0], [0.1234567], [[0.0]], [0.0] * 321):
            with self.subTest(values=str(values)[:20]):
                with self.assertRaises(ValueError):
                    ShadowGate().observe(np.array(values))

    def test_forwarding_preserves_object_order_and_result(self):
        received = []
        class Journal:
            def append(self, block):
                received.append(block)
                return 42
            def finish(self):
                return 'finished'
        class Source:
            def start(self):
                return 'started'
        module = types.SimpleNamespace(FileSource=Source)
        observers = install(module)
        source = module.FileSource()
        source.journal = Journal()
        self.assertEqual(source.start(), 'started')
        block = np.zeros(7, dtype=np.float32)
        self.assertEqual(source.journal.append(block), 42)
        self.assertIs(received[0], block)
        self.assertEqual(source.journal.finish(), 'finished')
        self.assertEqual(observers[0].samples, 7)


if __name__ == '__main__':
    import psutil
    psutil.Process().cpu_affinity([14])
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    unittest.main()
