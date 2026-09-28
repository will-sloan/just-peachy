"""Check time authority and unchanged resource boundaries; see README.md."""
import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import psutil
process = psutil.Process()
process.cpu_affinity([14])
process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from window_guard import budget, GIB, window


class AuthorizationTests(unittest.TestCase):
    def test_time_bounds_and_hardware_scope(self):
        now = datetime.now(timezone.utc)
        base = dict(started_utc=(now-timedelta(hours=1)).isoformat(),
                    checkpoint_utc=(now+timedelta(hours=1)).isoformat(),
                    logical_cpus_total=2, GPU="OFF", Pi_access=False)
        with patch("window_guard.load", return_value=base):
            self.assertEqual(window(), base)
        for changed in (dict(started_utc=(now+timedelta(minutes=1)).isoformat()),
                        dict(checkpoint_utc=(now-timedelta(minutes=1)).isoformat())):
            with patch("window_guard.load", return_value=base | changed):
                with self.assertRaises(TimeoutError): window()
        for changed in (dict(Pi_access=True), dict(logical_cpus_total=4), dict(GPU="ON")):
            with patch("window_guard.load", return_value=base | changed):
                with self.assertRaises(ValueError): window()

    def test_retained_output_and_reservations(self):
        result = budget(35*GIB, 500*1024**2, 128*1024**2,
                        {"C:": 100*GIB, "G:": 90*GIB}, 50)
        self.assertEqual(result["window_used_bytes"], 500*1024**2)
        self.assertEqual(result["projected_bytes"], 35*GIB+128*1024**2+int(2.5*GIB))
        self.assertEqual(result["physical_bytes_credited"], 0)

    def test_cap_floors_and_total_ceiling_refuse(self):
        cases = [(35*GIB, GIB, 1, {"C:": 100*GIB, "G:": 90*GIB}),
                 (35*GIB, 0, 1, {"C:": 50*GIB, "G:": 90*GIB}),
                 (35*GIB, 0, 1, {"C:": 100*GIB, "G:": 75*GIB}),
                 (48*GIB, 0, 1, {"C:": 100*GIB, "G:": 90*GIB})]
        for values in cases:
            with self.assertRaises(ValueError): budget(*values, 50)

    def test_invalid_counts_refuse(self):
        for count in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                budget(count, 0, 1, {"C:": 100*GIB, "G:": 100*GIB}, 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
