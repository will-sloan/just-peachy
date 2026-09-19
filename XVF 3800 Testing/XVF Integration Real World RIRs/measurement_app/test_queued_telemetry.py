"""Hardware-free tests of the queue wrapper's finalized-evidence lifecycle."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from measurement_app.queued_telemetry import QueuedTelemetryLogger

HOST = Path(__file__).resolve().parents[1] / "tools/xvf321/binary/host_v3.0.0/win32/xvf_host.exe"
FIXTURE = Path(__file__).resolve().parents[1] / "XVF_MEASUREMENT_WORK/experiments/CAPABILITIES_20260905T221801_419147Z/QUEUED_15S"


class QueuedWrapperTests(unittest.TestCase):
    def fake_run(self, broken=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        out = Path(temp.name)/"log"
        real_popen = subprocess.Popen
        rows = [json.loads(row) for row in (FIXTURE/"samples.jsonl").read_text().splitlines()]
        rows = [row for row in rows if row["phase"] == "measurement"][:4]
        inspection = json.loads((FIXTURE/"command_map_inspection.json").read_text())
        result = {"status":"PASS", "per_field": {name:{"count":2} for name in ("AEC_AZIMUTH_VALUES","AEC_SPENERGY_VALUES")}}
        def fake(argv, **kwargs):
            native = Path(argv[argv.index("-OutputDirectory")+1])
            native.mkdir()
            (native/"command_map_inspection.json").write_text(json.dumps(inspection))
            (native/"result.json").write_text("{invalid" if broken else json.dumps(result))
            lines = "\n".join(json.dumps(row) for row in rows)+"\n"
            code = "import sys,time;sys.stdout.write("+repr(lines)+");sys.stdout.flush();time.sleep(.15)"
            return real_popen([sys.executable,"-u","-c",code],stdin=kwargs["stdin"],stdout=kwargs["stdout"],stderr=kwargs["stderr"],creationflags=kwargs["creationflags"])
        with patch("measurement_app.queued_telemetry.subprocess.Popen",side_effect=fake):
            logger = QueuedTelemetryLogger(HOST,out,duration_s=3).start()
        self.assertTrue(logger.wait_ready(3))
        logger.stop("test_stop");logger.stop("duplicate_stop")
        self.assertIsNotNone(logger.wait(5))
        return logger

    def test_retains_transaction_timing_and_finalizes_after_exit(self):
        logger=self.fake_run()
        self.assertEqual(logger.result["status"],"PASS")
        self.assertEqual(logger.result["reply_count"],4)
        self.assertEqual(logger.result["stop_reason"],"test_stop")
        self.assertTrue(logger.stop_file.exists())
        self.assertIsNotNone(logger._process.poll())
        self.assertFalse(logger._reader.is_alive())
        self.assertIn("host_response_end_monotonic_ns",logger.rows[0])

    def test_invalid_native_result_is_a_completed_failure(self):
        logger=self.fake_run(broken=True)
        self.assertEqual(logger.result["status"],"FAIL")
        self.assertTrue(logger.result["errors"])


if __name__ == "__main__":
    unittest.main()
