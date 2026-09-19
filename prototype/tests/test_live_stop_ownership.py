"""Injected close-failure ownership checks; no device, stream or lease is opened."""
import types
import unittest
from unittest.mock import Mock, patch

from app.live_audio import LiveAudioError, LiveConfig, XVFLiveSource


class StopOwnershipTests(unittest.TestCase):
    def test_active_failed_close_retains_lease_and_retry_can_finish(self):
        source = XVFLiveSource(LiveConfig('unused-host', 'unused-lease'))
        source._started = True
        source.stream = types.SimpleNamespace(
            active=True, closed=False,
            stop=Mock(side_effect=RuntimeError('injected stop failure')),
            close=Mock(side_effect=RuntimeError('injected close failure')))
        source.lease = types.SimpleNamespace(close=Mock())
        source.route = types.SimpleNamespace(restore=Mock(return_value={}))
        with patch('app.live_audio.endpoint_snapshot', return_value={'status': 'TEST_ONLY'}), \
                patch('app.live_audio.compare_defaults', return_value={'status': 'UNCHANGED'}):
            with self.assertRaisesRegex(LiveAudioError, '(?i)active|lease|close'):
                source.stop()
            source.lease.close.assert_not_called()
            self.assertFalse(source.status()['finished'])
            self.assertIsNone(source._receipt, 'An incomplete stop must remain retryable')

            source.stream.stop.side_effect = None
            def finish_close():
                source.stream.active = False
                source.stream.closed = True
            source.stream.close.side_effect = finish_close
            receipt = source.stop()
            source.lease.close.assert_called_once()
            self.assertTrue(source.status()['finished'])
            self.assertIs(source.stop(), receipt)
            source.lease.close.assert_called_once()
            self.assertTrue(source.status()['fault'], 'The interrupted session must not become a clean pass')


if __name__ == '__main__':
    unittest.main()
