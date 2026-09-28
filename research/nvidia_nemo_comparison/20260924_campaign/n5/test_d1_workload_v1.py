"""Analytical checks for diagnostic arithmetic; README_D1_WORKLOAD_V1.md."""
import unittest
import numpy as np
from assess_d1_workload_v1 import energy_intervals, intersection, length, overlap_intervals, queue_bound, RATE


class WorkloadTests(unittest.TestCase):
    def test_overlapping_support_is_not_double_counted(self):
        self.assertEqual(length([(0, 10), (5, 15)]), 15)
        self.assertEqual(intersection([(0, 10), (5, 15)], [(4, 8), (7, 12)]), 8)

    def test_energy_keeps_onset_tail_and_partial_frame(self):
        audio = np.zeros(10001, dtype=np.float32)
        audio[-1] = .5
        support = energy_intervals(audio, -35)
        self.assertEqual(support, [[6720, 10001]])
        self.assertEqual(energy_intervals(np.zeros(10001), -55), [])

    def test_continuous_two_rtf_accumulates_backlog(self):
        result = queue_bound([(0, 10*RATE)], 10*RATE, 2, release_delay=0)
        self.assertAlmostEqual(result['after_eof_drain_seconds'], 10.02)

    def test_same_duty_cycle_can_have_very_different_backlog(self):
        burst = queue_bound([(0, 4*RATE)], 10*RATE, 2, release_delay=0)
        spaced = queue_bound([(i*RATE, i*RATE+int(.4*RATE)) for i in range(10)], 10*RATE, 2, release_delay=0)
        self.assertGreater(burst['peak_work_backlog_seconds'], 3.9)
        self.assertLess(spaced['peak_work_backlog_seconds'], .5)
        self.assertEqual(burst['after_eof_drain_seconds'], 0)
        self.assertEqual(spaced['after_eof_drain_seconds'], 0)

    def test_overlap_requires_distinct_identities(self):
        turns = [dict(identity='a', activity_ranges_samples_estimated=[[0, 10]]),
                 dict(identity='a', activity_ranges_samples_estimated=[[5, 15]]),
                 dict(identity='b', activity_ranges_samples_estimated=[[7, 12]])]
        self.assertEqual(overlap_intervals(turns), [[7, 12]])


if __name__ == '__main__':
    unittest.main()
