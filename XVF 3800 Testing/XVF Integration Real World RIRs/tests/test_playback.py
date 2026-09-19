"""Offline callback tests: these tests never open an audio endpoint."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from measurement_app import playback as p
import numpy as np


def timing(at=0):
    return SimpleNamespace(outputBufferDacTime=10 + at / p.RATE,
                           currentTime=9.85 + at / p.RATE)


def flags(*enabled):
    return SimpleNamespace(**{name: name in enabled for name in p.STATUS_NAMES})


class CallbackTests(unittest.TestCase):
    def test_variable_buffers_preserve_every_source_frame_and_zero_tail(self):
        source = np.arange(22, dtype=np.float32).reshape(11, 2) / 22
        player = p._CallbackPlayer(source, threading.Event())
        output = []
        at = 0
        for frames in (3, 5, 7):
            block = np.full((frames, 2), 99, dtype=np.float32)
            if at + frames >= len(source):
                with self.assertRaises(p.sd.CallbackStop):
                    player(block, frames, timing(at), flags())
            else:
                player(block, frames, timing(at), flags())
            output.append(block)
            at += frames
        rendered = np.concatenate(output)
        np.testing.assert_array_equal(rendered[:len(source)], source)
        np.testing.assert_array_equal(rendered[len(source):], 0)
        result = player.summarize()
        self.assertEqual(result['frames_written'], 11)
        self.assertTrue(result['source_frame_continuity']['contiguous'])
        self.assertTrue(result['source_frame_continuity']['all_source_frames_submitted'])
        self.assertLess(max(abs(v) for v in result['output_dac_timestamp_gap_error_s']), 1e-12)

    def test_cancel_stops_at_previous_source_frame_and_zeroes_full_buffer(self):
        stop = threading.Event()
        player = p._CallbackPlayer(np.ones((20, 1), np.float32), stop)
        player(np.empty((4, 1), np.float32), 4, timing(), flags())
        stop.set()
        block = np.full((5, 1), 99, np.float32)
        with self.assertRaises(p.sd.CallbackStop):
            player(block, 5, timing(4), flags('output_underflow'))
        np.testing.assert_array_equal(block, 0)
        result = player.summarize()
        self.assertEqual(result['frames_written'], 4)
        self.assertEqual(result['underflows'], [4])
        self.assertTrue(result['callback_receipts'][-1]['cancelled'])
        self.assertFalse(result['source_frame_continuity']['all_source_frames_submitted'])

    def test_callback_failure_is_preserved_and_never_leaves_garbage(self):
        player = p._CallbackPlayer(np.ones((20, 1), np.float32), threading.Event())
        block = np.full((5, 1), 99, np.float32)
        with self.assertRaises(p.sd.CallbackAbort):
            player(block, 5, object(), flags())
        self.assertIsInstance(player.error, AttributeError)
        self.assertEqual(player.position, 0)
        np.testing.assert_array_equal(block, 0)

    def test_receipt_capacity_failure_preserves_prior_frames(self):
        player = p._CallbackPlayer(np.ones((20, 1), np.float32), threading.Event(), max_callbacks=1)
        player(np.empty((2, 1), np.float32), 2, timing(), flags('priming_output', 'output_overflow'))
        block = np.full((2, 1), 99, np.float32)
        with self.assertRaises(p.sd.CallbackAbort):
            player(block, 2, timing(2), flags())
        np.testing.assert_array_equal(block, 0)
        result = player.summarize()
        self.assertEqual(result['frames_written'], 2)
        self.assertEqual(result['callback_count'], 1)
        self.assertEqual(result['callback_status_events'][0]['status_flags'], ['output_overflow', 'priming_output'])
        self.assertIn('capacity', str(player.error))


class PlaybackLifecycleTests(unittest.TestCase):
    def setUp(self):
        # Lifecycle tests mock COM as well as PortAudio. Only the separate COM
        # tests exercise its reference-count contract, using a mock Ole32 API.
        self.com_api = Mock()
        self.com_api.CoInitializeEx.return_value = 0
        self.com_patch = patch.object(p, '_load_ole32', return_value=self.com_api)
        self.com_patch.start()
        self.addCleanup(self.com_patch.stop)

    def test_finished_callback_required_and_requested_latency_recorded(self):
        made = []

        class FakeStream:
            latency = .16
            def __init__(self, **kw):
                self.kw = kw
                self.closed = False
                made.append(self)
            def start(self):
                at = 0
                while True:
                    block = np.zeros((4, 2), np.float32)
                    try:
                        self.kw['callback'](block, 4, timing(at), flags())
                    except p.sd.CallbackStop:
                        self.kw['finished_callback']()
                        break
                    at += 4
            def close(self):
                self.closed = True

        receipt = {}
        with patch.object(p, 'START_DELAY_S', 0), \
             patch.object(p.sd, 'query_devices', return_value={'name': 'mock', 'max_output_channels': 2}), \
             patch.object(p.sd, 'check_output_settings'), \
             patch.object(p.sd, 'OutputStream', FakeStream):
            p.separate_playback(14, np.linspace(-.4, .4, 11), -6, 'right', threading.Event(), receipt)
        self.assertTrue(receipt['completed'])
        self.assertTrue(receipt['drained'])
        self.assertEqual(receipt['frames_written'], 11)
        self.assertEqual(receipt['actual_stream_latency_s'], .16)
        self.assertEqual(made[0].kw['latency'], .15)
        self.assertEqual(made[0].kw['blocksize'], 0)
        self.assertTrue(made[0].closed)
        self.assertTrue(receipt['com_apartment']['reference_released'])

    def test_start_and_cleanup_failures_are_both_preserved(self):
        class BrokenStream:
            latency = .15
            def __init__(self, **kw): pass
            def start(self): raise RuntimeError('start failure')
            def close(self): raise RuntimeError('close failure')

        receipt = {}
        with patch.object(p, 'START_DELAY_S', 0), \
             patch.object(p.sd, 'query_devices', return_value={'max_output_channels': 2}), \
             patch.object(p.sd, 'check_output_settings'), \
             patch.object(p.sd, 'OutputStream', BrokenStream):
            p.separate_playback(14, np.zeros(12), 0, 'left', threading.Event(), receipt)
        self.assertFalse(receipt['completed'])
        self.assertIn('start failure', receipt['error'])
        self.assertIn('close failure', receipt['cleanup_errors'][0])
        self.assertEqual(receipt['frames_written'], 0)
        self.com_api.CoUninitialize.assert_called_once()

    def test_invalid_audio_never_opens_stream(self):
        for wave in (np.array([np.nan]), np.ones((2, 2)), np.array([]), np.array([1.01])):
            receipt = {}
            with patch.object(p, 'START_DELAY_S', 0), \
                 patch.object(p.sd, 'query_devices', return_value={'max_output_channels': 2}), \
                 patch.object(p.sd, 'OutputStream') as stream:
                p.separate_playback(14, wave, 0, 'left', threading.Event(), receipt)
            self.assertFalse(receipt['completed'])
            self.assertIn('error', receipt)
            stream.assert_not_called()

    def test_cancel_before_playback_never_queries_audio(self):
        stop = threading.Event()
        stop.set()
        receipt = {}
        with patch.object(p.sd, 'query_devices') as query:
            p.separate_playback(14, np.ones(12), 0, 'left', stop, receipt)
        query.assert_not_called()
        self.assertTrue(receipt['cancelled_before_playback'])
        self.assertFalse(receipt['completed'])


class ComApartmentTests(unittest.TestCase):
    def test_success_and_same_model_calls_are_each_balanced_once(self):
        for hresult in (0, 1):
            api = Mock()
            api.CoInitializeEx.return_value = hresult
            receipt = {}
            with patch.object(p, '_load_ole32', return_value=api), patch.object(p.os, 'name', 'nt'):
                apartment = p._ComApartment(receipt)
                apartment.open()
                api.CoInitializeEx.assert_called_once_with(None, 2)
                api.CoUninitialize.assert_not_called()
                apartment.close()
                apartment.close()
            api.CoUninitialize.assert_called_once()
            self.assertTrue(receipt['com_apartment']['reference_released'])

    def test_existing_different_apartment_is_never_uninitialized(self):
        api = Mock()
        api.CoInitializeEx.return_value = -2147417850  # RPC_E_CHANGED_MODE
        receipt = {}
        with patch.object(p, '_load_ole32', return_value=api), patch.object(p.os, 'name', 'nt'):
            apartment = p._ComApartment(receipt)
            apartment.open()
            apartment.close()
        api.CoUninitialize.assert_not_called()
        self.assertFalse(receipt['com_apartment']['reference_acquired'])
        self.assertEqual(receipt['com_apartment']['result'], 'using_existing_different_model')

    def test_com_failure_prevents_endpoint_query_and_stream_open(self):
        api = Mock()
        api.CoInitializeEx.return_value = -2147467259  # E_FAIL
        receipt = {}
        with patch.object(p, '_load_ole32', return_value=api), patch.object(p.os, 'name', 'nt'), \
             patch.object(p, 'START_DELAY_S', 0), patch.object(p.sd, 'query_devices') as query, \
             patch.object(p.sd, 'OutputStream') as stream:
            p.separate_playback(14, np.zeros(12), 0, 'left', threading.Event(), receipt)
        query.assert_not_called()
        stream.assert_not_called()
        api.CoUninitialize.assert_not_called()
        self.assertIn('0x80004005', receipt['error'])

    def test_stream_closed_before_balancing_com_on_failed_start(self):
        order = []
        api = Mock()
        api.CoInitializeEx.side_effect = lambda *args: order.append('initialize') or 0
        api.CoUninitialize.side_effect = lambda: order.append('uninitialize')

        class BrokenStream:
            latency = .16
            def __init__(self, **kw): order.append('open')
            def start(self):
                order.append('start')
                raise RuntimeError('start failure')
            def close(self): order.append('close')

        receipt = {}
        with patch.object(p, '_load_ole32', return_value=api), patch.object(p.os, 'name', 'nt'), \
             patch.object(p, 'START_DELAY_S', 0), \
             patch.object(p.sd, 'query_devices', return_value={'max_output_channels': 2}), \
             patch.object(p.sd, 'check_output_settings'), patch.object(p.sd, 'OutputStream', BrokenStream):
            p.separate_playback(14, np.zeros(12), 0, 'left', threading.Event(), receipt)
        self.assertEqual(order, ['initialize', 'open', 'start', 'close', 'uninitialize'])
        self.assertFalse(receipt['completed'])
        self.assertIn('start failure', receipt['error'])


if __name__ == '__main__':
    unittest.main()
