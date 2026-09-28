"""No-future-support checks; README_D1_CAUSAL_SUPPORT_V1.md."""
import unittest
from assess_d1_causal_support_v1 import support_before_deadline, RATE


class CausalSupportTests(unittest.TestCase):
    def test_late_recognition_does_not_rescue_discarded_audio(self):
        self.assertEqual(support_before_deadline([], [(0, 1, 3)], RATE, .22), [])
        self.assertEqual(support_before_deadline([], [(0, 1, 3)], RATE, 4), [[0, RATE]])

    def test_support_deadline_boundary_and_no_unbounded_backfill(self):
        result = support_before_deadline([], [(0, 1, 1.5)], 2*RATE, .22)
        self.assertEqual(result, [[20160, 22400]])

    def test_existing_energy_survives_absent_asr(self):
        self.assertEqual(support_before_deadline([[0, 320]], [], RATE, .22), [[0, 320]])

    def test_invalid_future_source_observation_refused(self):
        with self.assertRaises(ValueError):
            support_before_deadline([], [(0, 2, 1)], 3*RATE, 1)
        with self.assertRaises(ValueError):
            support_before_deadline([], [], RATE, .1)


if __name__ == '__main__':
    unittest.main()
