"""Hardware-free protocol parsing and subprocess lifecycle tests."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from measurement_app.telemetry import TelemetryLogger, parse_reply, DEFAULT_FIELDS


class TelemetryTests(unittest.TestCase):
    def test_radians_and_no_speech_are_not_converted_to_zero(self):
        row = parse_reply("AUDIO_MGR_SELECTED_AZIMUTHS nan (nan deg) 1.5 (85.94 deg)")
        self.assertEqual(row["values"], [None, 1.5])
        self.assertEqual(row["finite"], [False, True])
        self.assertTrue(row["parse_ok"])
        json.dumps(row, allow_nan=False)

    def test_bad_counts_and_values_are_retained_as_errors(self):
        self.assertFalse(parse_reply("AEC_SPENERGY_VALUES 1 2 nope 4")["parse_ok"])
        self.assertFalse(parse_reply("AEC_AZIMUTH_VALUES 1 2")["parse_ok"])

    def run_fake(self, text, wait_s=3):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        real_popen = subprocess.Popen
        def fake(*args, **kwargs):
            return real_popen([sys.executable, "-u", "-c", text],
                              stdout=kwargs["stdout"], stderr=kwargs["stderr"],
                              stdin=kwargs["stdin"], creationflags=kwargs["creationflags"])
        with patch("measurement_app.telemetry.subprocess.Popen", side_effect=fake):
            logger = TelemetryLogger(sys.executable, Path(tmp.name)/"log", duration_s=wait_s).start()
        self.assertIsNotNone(logger.wait(timeout=5))
        return logger

    def test_duration_stop_preserves_reply_prefix(self):
        program = "import time\nwhile True:\n print('AEC_AZIMUTH_VALUES 1 2 3 4',flush=True)\n print('AEC_SPENERGY_VALUES 5 6 7 8',flush=True)\n time.sleep(.02)\n"
        # Allow the real Python fixture process to start on a loaded Windows
        # host; the finite reply/error tests must not race a 300 ms stop timer.
        logger = self.run_fake(program,wait_s=1)
        self.assertEqual(logger.result["status"], "PASS")
        self.assertTrue(logger.result["intended_stop"])
        self.assertTrue(logger.result["received_prefix_in_order"])
        logger.stop()
        logger.stop()
        self.assertIs(logger.wait(timeout=0), logger.result)
        lines = (logger.output_dir/"received_telemetry.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), logger.result["reply_count"])

    def test_missing_reply_changes_sequence_and_fails(self):
        logger = self.run_fake("print('AEC_AZIMUTH_VALUES 1 2 3 4');print('AEC_AZIMUTH_VALUES 1 2 3 4')")
        self.assertEqual(logger.result["status"], "FAIL")
        self.assertGreater(logger.result["command_order_errors"], 0)

    def test_stderr_and_nonzero_exit_fail(self):
        logger = self.run_fake("import sys;print('transport error',file=sys.stderr);sys.exit(4)")
        self.assertEqual(logger.result["status"], "FAIL")
        self.assertEqual(logger.result["exit_code"], 4)

    def test_launch_failure_still_produces_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = TelemetryLogger(Path(tmp)/"missing.exe", Path(tmp)/"log").start()
            self.assertEqual(logger.wait(0)["status"], "FAIL")
            self.assertEqual(logger.result["reply_count"], 0)


if __name__ == "__main__":
    unittest.main()
