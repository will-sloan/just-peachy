"""Model-free enrollment ownership/privacy regression; no capture or USB I/O."""
from pathlib import Path
import queue
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vendor'))
from app.controller import Controller


class FakeThread:
    def __init__(self, alive=False):
        self.alive = alive
        self.joins = []

    def join(self, timeout=None):
        self.joins.append(timeout)

    def is_alive(self):
        return self.alive


class FakeLive:
    def __init__(self, *, restore_failure=False, stays_active=False):
        self.stream = types.SimpleNamespace(active=stays_active)
        self._ring = np.ones((2, 480, 2), np.float32)
        self.finished = False
        self.metadata = {'endpoint': {'endpoint_id': 'synthetic'}, 'route': {'tap': 'O0'}}
        self._receipt = None
        self.restore_failure = restore_failure
        self.stays_active = stays_active
        self.stop_calls = 0
        self.config = types.SimpleNamespace(native_rate=48000)

    def start(self, *, consent=False):
        assert consent is True
        return self.metadata

    def stop(self):
        self.stop_calls += 1
        self.finished = not self.stays_active
        self._receipt = {
            'errors': ['stream_close: injected'] if self.stays_active else [],
            'route_restoration': {'AUDIO_MGR_OP_L': 'FAILED: injected'} if self.restore_failure else {},
        }
        return self._receipt

    def status(self):
        return {'started': True, 'finished': self.finished, 'fault': None,
                'dropped_frames': 0, 'pending_raw_blocks': 0}


class EnrollmentCleanupTests(unittest.TestCase):
    def controller(self, **source_options):
        # Bypass application initialization so these checks cannot enumerate
        # endpoints, acquire leases, load models or touch a personal store.
        c = Controller.__new__(Controller)
        c._enroll_stop = threading.Event()
        c._enroll_thread = FakeThread()
        c._quality_thread = FakeThread()
        c._enroll_live = FakeLive(**source_options)
        c._quality = types.SimpleNamespace(vectors=[np.ones(192, np.float32)])
        c._quality_queue = queue.Queue(20)
        c._enroll_audio = [np.ones(160, np.float32)]
        c._enroll_vector = np.ones(192, np.float32)
        c._enroll_route = {'tap': 'O0'}
        c._enroll_integrity = None
        c.enrollment = {'state': 'READY', 'name': 'Fixture Person', 'can_save': True, 'gaps': 0}
        c.state = 'IDLE'
        c.status = 'Fixture ready'
        c.error = None
        c.store = types.SimpleNamespace(save=Mock(return_value={'id': 'fixture-uuid'}))
        return c

    def assert_discarded(self, c):
        self.assertIsNone(c._enroll_live, 'Stopped raw capture ring remains owned')
        self.assertIsNone(c._quality, 'Unsaved per-segment embeddings remain owned')
        self.assertIsNone(c._quality_queue)
        self.assertIsNone(c._enroll_vector)
        self.assertEqual(c._enroll_audio, [])

    def test_cancel_closed_source_releases_temporary_buffers_and_keeps_receipt(self):
        c = self.controller()
        live = c._enroll_live
        c._do_enrollment_cancel()
        self.assertGreaterEqual(live.stop_calls, 1)
        self.assert_discarded(c)
        self.assertTrue(c._enroll_integrity['ok'])
        self.assertEqual(c.enrollment['state'], 'IDLE')
        self.assertFalse(c.enrollment['can_save'])

    def test_cancel_restore_failure_is_visible_and_does_not_become_success(self):
        c = self.controller(restore_failure=True)
        with self.assertRaisesRegex(RuntimeError, '(?i)integrity|restor|shutdown'):
            c._do_enrollment_cancel()
        self.assert_discarded(c)  # Stream is closed, so audio can be discarded.
        self.assertFalse(c._enroll_integrity['ok'])
        self.assertEqual(c.enrollment['state'], 'ERROR')
        self.assertFalse(c.enrollment['can_save'])
        self.assertEqual(c.enrollment['gaps'], 1)
        self.assertNotIn('temporary audio discarded.', c.status)

    def test_cancel_active_stream_retains_owner_and_audio_until_safe(self):
        c = self.controller(stays_active=True)
        live, quality = c._enroll_live, c._quality
        with self.assertRaisesRegex(RuntimeError, '(?i)active|owner|shutdown'):
            c._do_enrollment_cancel()
        self.assertIs(c._enroll_live, live)
        self.assertIs(c._quality, quality)
        self.assertTrue(c._enroll_live.stream.active)
        self.assertFalse(c.enrollment['can_save'])

    def test_cancel_running_quality_retains_buffers(self):
        c = self.controller()
        c._quality_thread = FakeThread(alive=True)
        live, quality = c._enroll_live, c._quality
        with self.assertRaisesRegex(RuntimeError, '(?i)quality|active'):
            c._do_enrollment_cancel()
        self.assertIs(c._enroll_live, live)
        self.assertIs(c._quality, quality)

    def test_failed_cancel_blocks_replacement_of_active_enrollment(self):
        c = self.controller(stays_active=True)
        live = c._enroll_live
        with self.assertRaises(RuntimeError):
            c._do_enrollment_cancel()
        with self.assertRaisesRegex(RuntimeError, '(?i)active|owner'):
            c._ensure_no_enrollment()
        self.assertIs(c._enroll_live, live)

    def test_save_closed_source_releases_buffers_after_store_commit(self):
        c = self.controller()
        c._enroll_live.stop()
        c._enroll_integrity = {'ok': True, 'reasons': []}
        c._do_enrollment_save()
        c.store.save.assert_called_once()
        self.assert_discarded(c)
        self.assertEqual(c.enrollment['state'], 'SAVED')
        self.assertEqual(c.enrollment['person_id'], 'fixture-uuid')

    def test_save_rejects_live_worker_before_store_mutation(self):
        c = self.controller()
        c._quality_thread = FakeThread(alive=True)
        live, quality = c._enroll_live, c._quality
        with self.assertRaisesRegex(RuntimeError, '(?i)quality|active|worker'):
            c._do_enrollment_save()
        c.store.save.assert_not_called()
        self.assertIs(c._enroll_live, live)
        self.assertIs(c._quality, quality)

    def test_failed_store_commit_keeps_reference_for_retry(self):
        c = self.controller()
        c._enroll_live.stop()
        c._enroll_integrity = {'ok': True, 'reasons': []}
        c.store.save.side_effect = OSError('injected storage failure')
        live, quality = c._enroll_live, c._quality
        with self.assertRaisesRegex(OSError, 'storage failure'):
            c._do_enrollment_save()
        self.assertIs(c._enroll_live, live)
        self.assertIs(c._quality, quality)
        self.assertIsNotNone(c._enroll_vector)

    def test_quality_setup_failure_after_live_start_closes_source(self):
        c = self.controller()
        c.enrollment = {'state': 'IDLE', 'can_save': False}
        c.models = types.SimpleNamespace(enrollment_models=Mock(), speakers=object())
        c.config = object()
        c._stop_session = Mock()
        c._live_config = Mock(return_value={})
        c.route = Mock(return_value={'tap': 'O0'})
        live = c._enroll_live
        c._enroll_live = None
        with patch('app.live_audio.XVFLiveSource', return_value=live), \
                patch('app.controller.EnrollmentQuality', side_effect=RuntimeError('injected quality setup')):
            with self.assertRaisesRegex(RuntimeError, 'quality setup'):
                c._do_enrollment_start('Fixture Person', 15, None)
        self.assertGreaterEqual(live.stop_calls, 1)
        self.assert_discarded(c)
        self.assertEqual(c.enrollment['state'], 'ERROR')

    def test_capture_thread_start_failure_stops_source_and_quality_worker(self):
        c = self.controller()
        c.enrollment = {'state': 'IDLE', 'can_save': False}
        c.models = types.SimpleNamespace(enrollment_models=Mock(), speakers=object())
        c.config = object()
        c._stop_session = Mock()
        c._live_config = Mock(return_value={})
        c.route = Mock(return_value={'tap': 'O0'})
        live = c._enroll_live
        c._enroll_live = None
        quality_thread = FakeThread()
        quality_thread.start = Mock()
        capture_thread = FakeThread()
        capture_thread.start = Mock(side_effect=RuntimeError('injected capture thread start'))
        with patch('app.live_audio.XVFLiveSource', return_value=live), \
                patch('app.controller.EnrollmentQuality', return_value=c._quality), \
                patch('app.controller.threading.Thread', side_effect=[quality_thread, capture_thread]):
            with self.assertRaisesRegex(RuntimeError, 'capture thread start'):
                c._do_enrollment_start('Fixture Person', 15, None)
        self.assertGreaterEqual(live.stop_calls, 1)
        self.assertTrue(quality_thread.joins)
        self.assert_discarded(c)
        self.assertEqual(c.enrollment['state'], 'ERROR')


if __name__ == '__main__':
    unittest.main()
