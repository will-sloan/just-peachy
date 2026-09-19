import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from measurement_app.recovery import RecoveryMonitor, probe_usb_width


def identity(bits=24):
    return {'VERSION': [3, 2, 1], 'USB_BIT_DEPTH': [bits, bits],
            'AUDIO_MGR_MIC_GAIN': [10], 'AUDIO_MGR_REF_GAIN': [1],
            'AUDIO_MGR_SYS_DELAY': [-32]}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.control = Mock()
        self.control.identify.return_value = identity()
        self.control.query.return_value = 'parameters snapshot'
        self.events = []
        self.monitor = RecoveryMonitor(Path(self.temp.name), Mock(), Mock(), self.events.append,
            Mock(return_value=[{'name': 'Fixture output'}]), probe=Mock(return_value=[24, 24]),
            control=Mock(return_value=self.control), seal=Mock())
        self.monitor.stop = Mock()
        self.monitor.stop.is_set.return_value = False
        self.monitor.stop.wait.return_value = False

    def test_busy_owner_prevents_probe_reset_and_refresh(self):
        self.monitor.claim.side_effect = RuntimeError('capture active')
        self.monitor.tick()
        self.monitor.probe.assert_not_called()
        self.control.query.assert_not_called()
        self.monitor.refresh_audio.assert_not_called()
        self.monitor.release.assert_not_called()

    def test_missing_device_waits_without_reset_or_audio_restart(self):
        self.monitor.probe.side_effect = RuntimeError('No device found')
        self.monitor.tick()
        self.assertFalse(self.monitor.ready)
        self.assertEqual(self.events[-1]['state'], 'waiting')
        self.monitor.control.assert_not_called()
        self.monitor.refresh_audio.assert_not_called()
        self.monitor.release.assert_called_once()

    def test_usb16_reconnect_restores_then_verifies_before_ready(self):
        self.monitor.probe.return_value = [16, 16]
        self.control.identify.side_effect = [identity(16), identity()]
        self.monitor.tick()
        self.control.query.assert_any_call('USB_BIT_DEPTH', 24, 24)
        for name, value in [('AUDIO_MGR_MIC_GAIN', [10]), ('AUDIO_MGR_REF_GAIN', [1]), ('AUDIO_MGR_SYS_DELAY', [-32])]:
            self.control.set.assert_any_call(name, value)
        self.monitor.refresh_audio.assert_called_once()
        self.assertTrue(self.monitor.ready)
        self.assertEqual(self.monitor.generation, 1)
        self.assertTrue(list(Path(self.temp.name).glob('AUTO_USB24_*/before_params.txt')))

    def test_healthy_poll_does_not_reboot_or_refresh_again(self):
        self.monitor.tick()
        self.monitor.tick()
        self.control.query.assert_not_called()
        self.monitor.refresh_audio.assert_called_once()
        self.assertEqual(self.monitor.generation, 1)

    def test_usb24_reconnect_refreshes_without_reboot(self):
        self.monitor.tick()
        self.monitor.request_check()
        self.monitor.tick()
        self.assertEqual(self.monitor.refresh_audio.call_count, 2)
        self.control.query.assert_not_called()

    def test_wrong_device_identity_never_writes(self):
        self.control.identify.side_effect = RuntimeError('Wrong firmware or array')
        self.monitor.tick()
        self.control.query.assert_not_called()
        self.assertFalse(self.monitor.ready)

    def test_gain_delay_mismatch_does_not_silently_change_configuration(self):
        wrong = identity(16)
        wrong['AUDIO_MGR_MIC_GAIN'] = [1]
        self.control.identify.return_value = wrong
        self.monitor.tick()
        self.control.set.assert_not_called()
        self.control.query.assert_not_called()
        self.assertFalse(self.monitor.ready)

    def test_failed_readback_prevents_ready_and_audio_restart(self):
        self.monitor.probe.return_value = [16, 16]
        self.control.identify.side_effect = [identity(16), identity(16)]
        self.monitor.tick()
        self.assertFalse(self.monitor.ready)
        self.monitor.refresh_audio.assert_not_called()

    def test_audio_refresh_failure_retries_without_extra_reboot(self):
        self.monitor.refresh_audio.side_effect = [RuntimeError('driver settling'), []]
        self.monitor.tick()
        self.assertFalse(self.monitor.ready)
        self.monitor.tick()
        self.assertTrue(self.monitor.ready)
        self.control.query.assert_not_called()

    def test_shutdown_during_reboot_never_announces_ready(self):
        self.monitor.probe.return_value = [16, 16]
        self.control.identify.return_value = identity(16)
        self.monitor.stop.wait.return_value = True
        self.monitor.tick()
        self.assertFalse(self.monitor.ready)
        self.monitor.refresh_audio.assert_not_called()

    def test_probe_rejects_malformed_and_error_replies(self):
        with patch('measurement_app.recovery.subprocess.run') as run:
            run.return_value = Mock(returncode=0, stdout=b'USB_BIT_DEPTH 24 24\r\n', stderr=b'')
            self.assertEqual(probe_usb_width(), [24, 24])
            run.return_value.stdout = b'USB_BIT_DEPTH 24 24\nUSB_BIT_DEPTH 16 16\n'
            with self.assertRaises(RuntimeError): probe_usb_width()
            run.return_value = Mock(returncode=0, stdout=b'USB_BIT_DEPTH 24 24', stderr=b'control error 87')
            with self.assertRaises(RuntimeError): probe_usb_width()


if __name__ == '__main__':
    unittest.main()
