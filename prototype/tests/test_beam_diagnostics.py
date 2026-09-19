"""Read-only diagnostic and Tk contracts; synthetic getter data, no device IO.

Run from repository root; see docs/BEAM_DIAGNOSTICS.md for exact commands.
"""
import math
import threading
import time
import unittest

from prototype.app.beam_diagnostics import BeamDiagnostics, arrow_tip, native_angle_degrees, parse_values


class BeamDiagnosticsTests(unittest.TestCase):
    def test_official_replies_units_invalid_and_cardinality(self):
        selected = parse_values("AUDIO_MGR_SELECTED_AZIMUTHS",
                                "AUDIO_MGR_SELECTED_AZIMUTHS nan (nan deg) 1.570796 (90.00 deg)\n")
        self.assertIsNone(selected[0])
        self.assertAlmostEqual(native_angle_degrees(selected[1]), 90, places=4)
        self.assertEqual(native_angle_degrees(3.141593), 180)
        for value in (-.1, math.pi + .1, float("nan"), float("inf"), True, None):
            self.assertIsNone(native_angle_degrees(value))
        for bad in ("AEC_AZIMUTH_VALUES 1 2", "AEC_AZIMUTH_VALUES 1 2 3 nope",
                    "AEC_AZIMUTH_VALUES 1 2 3 4\nAEC_AZIMUTH_VALUES 1 2 3 4"):
            with self.assertRaises(ValueError):
                parse_values("AEC_AZIMUTH_VALUES", bad)
        with self.assertRaises(ValueError):
            parse_values("AUDIO_MGR_OP_L", "AUDIO_MGR_OP_L 1 0")

    def test_native_endpoints_do_not_wrap_or_reverse(self):
        self.assertEqual(arrow_tip(0, 100, 100, 50), (150, 100))
        self.assertAlmostEqual(arrow_tip(90, 100, 100, 50)[0], 100)
        self.assertEqual(arrow_tip(90, 100, 100, 50)[1], 50)
        self.assertAlmostEqual(arrow_tip(180, 100, 100, 50)[0], 50)
        for angle in (-1, 181, float("nan"), True):
            with self.assertRaises(ValueError):
                arrow_tip(angle, 100, 100, 50)

    def test_asynchronous_fields_expire_independently_and_snapshot_is_detached(self):
        clock = [10.0]
        samples = {"AEC_AZIMUTH_VALUES": [0, math.pi, None, 9],
                   "AUDIO_MGR_SELECTED_AZIMUTHS": [math.pi / 2, None]}
        diagnostic = BeamDiagnostics(lambda name: samples[name], clock=lambda: clock[0])
        diagnostic._sample("AEC_AZIMUTH_VALUES")
        clock[0] = 12
        diagnostic._sample("AUDIO_MGR_SELECTED_AZIMUTHS")
        view = diagnostic.snapshot()
        self.assertEqual({row["id"] for row in view["arrows"]}, {"focused_1", "focused_2", "processed_output"})
        view["fields"]["AEC_AZIMUTH_VALUES"]["values"][0] = 999
        self.assertEqual(diagnostic.snapshot()["fields"]["AEC_AZIMUTH_VALUES"]["values"][0], 0)
        clock[0] = 12.6
        self.assertEqual([row["id"] for row in diagnostic.snapshot()["arrows"]], ["processed_output"])
        self.assertFalse(diagnostic.snapshot()["affects_identity_or_asr"])
        diagnostic.stop()
        self.assertEqual(diagnostic.snapshot()["arrows"], [])

    def test_constructor_and_snapshot_never_read_hardware(self):
        calls = []
        diagnostic = BeamDiagnostics(lambda command: calls.append(command))
        for _ in range(30):
            self.assertEqual(diagnostic.snapshot()["state"], "IDLE")
        self.assertEqual(calls, [])
        with self.assertRaises(ValueError):
            BeamDiagnostics(lambda _: [], interval_seconds=.1)

    def test_failed_optional_reader_disables_only_diagnostics(self):
        attempted = threading.Event()
        def broken(_):
            attempted.set()
            raise RuntimeError("device read failed")
        diagnostic = BeamDiagnostics(broken).start()
        self.assertTrue(attempted.wait(1))
        self.assertTrue(diagnostic.stop(timeout=2))
        view = diagnostic.snapshot()
        self.assertEqual(view["state"], "UNAVAILABLE")
        self.assertEqual(view["arrows"], [])
        self.assertEqual(view["counters"]["errors"], 1)
        self.assertIn("device read failed", view["error"])

    def test_stop_waits_for_single_inflight_getter_and_blocks_further_calls(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def getter(command):
            calls.append(command)
            entered.set()
            release.wait(2)
            return [0, 1, 2, 3]
        diagnostic = BeamDiagnostics(getter).start()
        self.assertTrue(entered.wait(1))
        self.assertFalse(diagnostic.stop(timeout=.01))
        self.assertEqual(diagnostic.snapshot()["arrows"], [])
        release.set()
        self.assertTrue(diagnostic.stop(timeout=1))
        self.assertEqual(len(calls), 1)
        with self.assertRaises(RuntimeError):
            diagnostic.start()

    def test_poll_rate_cap_has_no_catchup_burst(self):
        calls, complete = [], threading.Event()
        def getter(command):
            calls.append(time.monotonic())
            if len(calls) == 3:
                complete.set()
            return [0, 1] if command == "AUDIO_MGR_SELECTED_AZIMUTHS" else [0, 1, 2, 3]
        diagnostic = BeamDiagnostics(getter).start()
        try:
            self.assertTrue(complete.wait(3))
        finally:
            self.assertTrue(diagnostic.stop(timeout=1))
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(b - a >= .49 for a, b in zip(calls, calls[1:])))
        self.assertEqual(len(diagnostic.snapshot()["fields"]), 3)


if __name__ == "__main__":
    unittest.main()
