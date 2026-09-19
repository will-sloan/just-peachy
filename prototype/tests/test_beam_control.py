"""Read-only diagnostic command boundary; no USB/microphone access. See README."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.live_audio import HostControl, LiveAudioError, LiveConfig


class BeamControlTests(unittest.TestCase):
    def test_annotated_radians_missing_value_and_bounded_receipts(self):
        with tempfile.NamedTemporaryFile() as executable:
            control = HostControl(LiveConfig(executable.name, 'unused'))
            reply = b'AEC_AZIMUTH_VALUES 0 (0 deg) 1.5708 (90 deg) nan 3.14159 (180 deg)\r\n'
            with patch('app.live_audio.subprocess.run', return_value=subprocess.CompletedProcess([], 0, reply, b'')) as run:
                for _ in range(20):
                    self.assertEqual(control.diagnostic_values('AEC_AZIMUTH_VALUES'), [0., 1.5708, None, 3.14159])
                self.assertEqual(control.receipts, [])
                self.assertEqual(len(run.call_args.args[0]), 4)
                with self.assertRaises(LiveAudioError):
                    control.query('AEC_AZIMUTH_VALUES', 1)
                with self.assertRaises(LiveAudioError):
                    control.diagnostic_values('AUDIO_MGR_OP_L')
                self.assertEqual(run.call_count, 20)


if __name__ == '__main__':
    unittest.main()
