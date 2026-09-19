"""Offline workflow tests: real temporary evidence files, no audio or XVF access."""
import copy
import itertools
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

from measurement_app import core, reference
from measurement_app import reference_calibration as calibration
from measurement_app import speaker_reference as speaker


class ImmediateThread:
    """Execute mocked playback synchronously; never create an audio thread."""
    def __init__(self, target, args=(), daemon=False):
        self.target, self.args = target, args
    def start(self):
        self.target(*self.args)
    def is_alive(self):
        return False
    def join(self, timeout=None):
        pass


class ReferenceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.base = Path(self.temp)
        sources = self.base / 'measurement_app'
        sources.mkdir()
        for name in ('reference.py', 'reference_calibration.py', 'speaker_reference.py',
                     'core.py', 'playback.py', 'excitation.py'):
            (sources / name).write_text('# offline source fixture\n', encoding='utf-8')
        self.assets = self.base / 'assets'
        self.assets.mkdir()
        (self.assets / 'signal_timing.json').write_text('{"fixture": true}', encoding='utf-8')
        self.wave = .1 * np.sin(2 * np.pi * 700 * np.arange(4800) / 48000)
        self.stimulus_path = self.assets / 'fixture.wav'
        sf.write(self.stimulus_path, self.wave, 48000, subtype='FLOAT')
        self.stimulus = {'id': 'fixture', 'path': str(self.stimulus_path),
                         'sha256': core.sha(self.stimulus_path), 'duration_seconds': .1}
        self.inventory = [
            {'index': 7, 'name': 'Speakers (Realtek)', 'hostapi_name': 'Windows WASAPI',
             'max_output_channels': 2, 'max_input_channels': 0},
            {'index': 9, 'name': 'Reference USB interface', 'hostapi_name': 'Windows WASAPI',
             'max_input_channels': 2, 'max_output_channels': 0},
        ]
        self.ref_config = {'enabled': True, 'device_index': 9,
            'device_name': 'Reference USB interface', 'hostapi_name': 'Windows WASAPI',
            'channel': 1, 'sample_rate_hz': 48000, 'microphone_model': 'Fixture microphone',
            'microphone_serial': 'TEST-1', 'interface_gain_note': 'fixed mark',
            'placement_note': 'On axis at speaker height', 'distance_to_speaker_m': 1.0,
            'calibration_file_path': None, 'calibration_record': None,
            'sensitivity_pa_per_fs': None}
        self.start_error = None
        self.finish_error = None
        self.ready = True
        self.capture_frames = 12 * 48000
        self.capture_receipt = {'enabled': True, 'status': 'PASS', 'stream_closed': True,
            'frames': self.capture_frames, 'start_monotonic_ns': 1_000_000_000,
            'end_monotonic_ns': 13_000_000_000, 'quality': {}}
        self.play_receipt = {'completed': True, 'drained': True, 'stream_closed': True,
            'frames_written': len(self.wave), 'source_frames': len(self.wave),
            'underflows': [], 'callback_status_events': [],
            'start_monotonic_ns': 2_000_000_000, 'end_monotonic_ns': 2_100_000_000,
            'source_frame_continuity': {'contiguous': True, 'all_source_frames_submitted': True,
                'submitted_source_frames': len(self.wave), 'expected_source_frames': len(self.wave)}}
        self.recorders = []
        self.counter = itertools.count()
        self.stack.enter_context(patch.object(calibration, 'BASE', self.base))
        self.stack.enter_context(patch.object(speaker, 'BASE', self.base))
        self.stack.enter_context(patch.object(speaker, 'ASSETS', self.assets))
        self.stack.enter_context(patch.object(reference, 'devices', return_value=self.inventory))
        self.stack.enter_context(patch.object(speaker, 'devices', return_value=self.inventory))
        self.stack.enter_context(patch.object(speaker, 'get_excitation', return_value=self.stimulus))
        self.stack.enter_context(patch.object(speaker, 'ReferenceCapture', side_effect=self.capture_factory))
        self.stack.enter_context(patch.object(speaker.threading, 'Thread', ImmediateThread))
        self.play = self.stack.enter_context(patch.object(speaker, 'separate_playback', side_effect=self.playback))
        self.control = self.stack.enter_context(patch.object(speaker, 'Control', side_effect=AssertionError('No XVF control allowed')))
        self.stack.enter_context(patch.object(core, 'Control', side_effect=AssertionError('No XVF control allowed')))
        # A mistaken call into a real PortAudio entry point must fail the test.
        for name in ('query_devices', 'query_hostapis', 'check_input_settings',
                     'check_output_settings', 'InputStream', 'OutputStream', 'RawStream'):
            self.stack.enter_context(patch.object(reference.sd, name, side_effect=AssertionError('Hardware forbidden')))
        # Advance past each bounded wait without sleeping or consulting real time.
        self.stack.enter_context(patch.object(speaker.time, 'monotonic', side_effect=itertools.count(0, 20)))
        self.speaker_freeze = self.stack.enter_context(patch.object(speaker, 'freeze', wraps=core.freeze))
        self.calibration_freeze = self.stack.enter_context(patch.object(calibration, 'freeze', wraps=core.freeze))

    def capture_factory(self, folder, config, stop):
        owner = self
        class Capture:
            def __init__(self):
                self.folder, self.config = Path(folder), copy.deepcopy(config)
                self.started = self.finished = False
            def start(self):
                self.started = True
                self.folder.mkdir(parents=True)
                if owner.start_error:
                    raise owner.start_error
                return self
            def wait_ready(self, timeout):
                return owner.ready
            def finish(self):
                self.finished = True
                if owner.finish_error:
                    raise owner.finish_error
                if owner.capture_receipt['stream_closed']:
                    samples = .1 * np.sin(2 * np.pi * 1000 * np.arange(owner.capture_frames) / 48000)
                    sf.write(self.folder / 'selected_reference.wav', samples, 48000, subtype='FLOAT')
                return copy.deepcopy(owner.capture_receipt)
        capture = Capture()
        self.recorders.append(capture)
        return capture

    def playback(self, index, wave, gain, channel, stop, receipt):
        receipt.update(copy.deepcopy(self.play_receipt))

    def calibration_body(self):
        return {'schema_version': 3, 'reference': copy.deepcopy(self.ref_config),
                'operator_confirmed': True, 'known_spl_db': 94, 'frequency_hz': 1000}

    def speaker_body(self):
        return {'schema_version': 3, 'reference': copy.deepcopy(self.ref_config),
                'playback_device_index': 7, 'playback_device_name': 'Speakers (Realtek)',
                'playback_channel': 'left', 'playback_gain_db': -18, 'excitation_id': 'fixture',
                'setup': {'speaker': {'connection': 'wired'}}}

    def acquire(self, kind='speaker', stop=None):
        folder = self.base / ('RUN_' + str(next(self.counter)))
        folder.mkdir()
        stop = stop or threading.Event()
        if kind == 'speaker':
            request = speaker.validate_speaker_reference(self.speaker_body())
            result = speaker.acquire_speaker_reference(request, folder, stop, Mock())
        else:
            request = calibration.validate_calibration_request(self.calibration_body())
            result = calibration.acquire_calibration(request, folder, stop, Mock(), capture_factory=self.capture_factory)
        return result, folder

    def test_external_speaker_reference_is_independent_and_preserves_source(self):
        result, folder = self.acquire()
        self.assertEqual(result['status'], 'REVIEW')
        self.assertTrue(result['capture_integrity_pass'])
        self.assertFalse(result['scientific_measurement_qualified'])
        self.assertFalse(result['source_correction_generated'])
        self.control.assert_not_called()
        self.play.assert_called_once()
        self.assertEqual(core.sha(folder / 'excitation_original.wav'), self.stimulus['sha256'])
        original, rate = sf.read(folder / 'excitation_original.wav')
        applied, _ = sf.read(folder / 'electrical_source_selected.wav')
        np.testing.assert_allclose(applied, original * 10 ** (-18 / 20), rtol=1e-6, atol=1e-9)
        self.assertEqual(rate, 48000)
        contract = json.loads((folder / 'source_reference_contract.json').read_text())
        self.assertEqual(contract['source_original_sha256'], self.stimulus['sha256'])
        self.assertFalse(contract['speaker_correction_generated'])
        self.assertFalse(contract['frequency_response_correction_applied'])
        self.assertFalse(contract['reference_clock_shared_with_playback'])
        self.assertTrue((folder / 'SHA256SUMS.txt').exists())

    def test_calibrator_is_reference_only_and_binds_sensitivity_to_input(self):
        result, folder = self.acquire('calibration')
        self.assertEqual(result['status'], 'PASS')
        self.play.assert_not_called()
        self.control.assert_not_called()
        scale = json.loads((folder / 'calibration.json').read_text())
        self.assertAlmostEqual(scale['pa_per_fs'], (20e-6 * 10 ** (94 / 20)) / (.1 / np.sqrt(2)), places=5)
        self.assertFalse(scale['frequency_response_correction_applied'])
        self.assertFalse(scale['physical_calibrator_and_coupling_verified'])
        self.assertEqual(scale['input_configuration']['microphone_serial'], 'TEST-1')
        self.assertEqual(result['calibration_record'], str((folder / 'calibration.json').resolve()))

    def test_stop_never_produces_accepted_measurement(self):
        for kind in ('speaker', 'calibration'):
            with self.subTest(kind=kind):
                stop = threading.Event(); stop.set()
                result, folder = self.acquire(kind, stop)
                self.assertEqual(result['status'], 'RETAKE')
                self.assertFalse(result['scientific_measurement_qualified'])
                self.assertFalse((folder / 'calibration.json').exists())

    def test_input_not_ready_prevents_speaker_playback(self):
        self.ready = False
        result, _ = self.acquire()
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.play.assert_not_called()
        self.assertTrue(self.recorders[-1].finished)

    def test_start_exception_retains_recorder_for_cleanup(self):
        for kind in ('speaker', 'calibration'):
            with self.subTest(kind=kind):
                self.start_error = RuntimeError('opened input then failed')
                result, _ = self.acquire(kind)
                self.assertEqual(result['status'], 'INVESTIGATE')
                self.assertTrue(self.recorders[-1].finished)

    def test_unclosed_reference_never_freezes_evidence(self):
        self.capture_receipt.update(status='FAIL', stream_closed=False, error='close failed')
        for kind in ('speaker', 'calibration'):
            with self.subTest(kind=kind):
                result, folder = self.acquire(kind)
                self.assertEqual(result['status'], 'INVESTIGATE')
                self.assertTrue(result['hardware_logger_still_active'])
                self.assertFalse((folder / 'SHA256SUMS.txt').exists())

    def test_finish_exception_never_freezes_evidence(self):
        self.finish_error = RuntimeError('finish failed before closure was established')
        for kind in ('speaker', 'calibration'):
            with self.subTest(kind=kind):
                result, folder = self.acquire(kind)
                self.assertNotEqual(result['status'], 'PASS')
                self.assertFalse((folder / 'SHA256SUMS.txt').exists())

    def test_playback_failure_cannot_be_hidden_by_clean_reference(self):
        self.play_receipt.update(completed=False, frames_written=0, error='startup failed')
        result, _ = self.acquire()
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.assertFalse(result['capture_integrity_pass'])

    def test_playback_close_failure_blocks_sealing_after_thread_exit(self):
        self.play_receipt.update(completed=False, stream_closed=False, cleanup_errors=['output close failed'])
        result, folder = self.acquire()
        self.assertTrue(result['hardware_logger_still_active'])
        self.assertFalse((folder / 'SHA256SUMS.txt').exists())

    def test_short_reference_cannot_claim_full_speaker_capture_integrity(self):
        self.capture_frames = 100
        self.capture_receipt.update(frames=100, end_monotonic_ns=1_002_083_333)
        result, _ = self.acquire()
        self.assertFalse(result['capture_integrity_pass'])
        self.assertNotEqual(result['status'], 'REVIEW')

    def test_full_frame_count_does_not_replace_host_interval_coverage(self):
        self.capture_receipt['start_monotonic_ns'] = 2_050_000_000
        result, _ = self.acquire()
        self.assertTrue(result['checks']['reference_minimum_frame_count'])
        self.assertFalse(result['checks']['reference_host_interval_coverage'])
        self.assertFalse(result['capture_integrity_pass'])

    def test_live_playback_writer_prevents_freeze(self):
        class StuckThread(ImmediateThread):
            def is_alive(self):
                return True
        with patch.object(speaker.threading, 'Thread', StuckThread):
            result, folder = self.acquire()
        self.assertEqual(result['status'], 'RETAKE')
        self.assertTrue(result['hardware_logger_still_active'])
        self.assertFalse((folder / 'SHA256SUMS.txt').exists())

    def test_output_status_failure_cannot_be_hidden_by_completion_flag(self):
        self.play_receipt['callback_status_events'] = [{'status_flags': ['output_underflow']}]
        result, _ = self.acquire()
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.assertFalse(result['checks']['playback'])
        self.assertFalse(result['capture_integrity_pass'])

    def test_failed_reference_quality_never_yields_calibration(self):
        self.capture_receipt.update(status='FAIL', error='reference input overflow')
        result, folder = self.acquire('calibration')
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.assertIsNone(result['calibration'])
        self.assertFalse((folder / 'calibration.json').exists())

    def test_calibrator_requires_the_full_analysis_window(self):
        self.capture_frames = 7 * 48000
        self.capture_receipt['frames'] = self.capture_frames
        result, folder = self.acquire('calibration')
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.assertIsNone(result['calibration_record'])
        self.assertFalse((folder / 'calibration.json').exists())

    def test_input_identity_and_channel_are_validated_before_capture(self):
        for change in ({'device_name': 'Wrong mic'}, {'hostapi_name': 'MME'}, {'channel': 3}, {'channel': True}):
            with self.subTest(change=change):
                body = self.speaker_body(); body['reference'].update(change)
                with self.assertRaises(ValueError):
                    speaker.validate_speaker_reference(body)
        self.assertEqual(self.recorders, [])
        self.play.assert_not_called()

    def test_speaker_geometry_is_required_but_room_geometry_is_optional(self):
        valid = speaker.validate_speaker_reference(self.speaker_body())
        self.assertFalse(valid['routine_xvf_capture'])
        for change in ({'distance_to_speaker_m': 0}, {'distance_to_speaker_m': float('nan')},
                       {'distance_to_speaker_m': True}, {'placement_note': '   '}):
            with self.subTest(change=change):
                body = self.speaker_body(); body['reference'].update(change)
                with self.assertRaises(ValueError):
                    speaker.validate_speaker_reference(body)

    def test_bluetooth_setup_is_rejected_server_side(self):
        body = self.speaker_body(); body['setup']['speaker']['connection'] = 'bluetooth'
        with self.assertRaises(ValueError):
            speaker.validate_speaker_reference(body)

    def test_calibrator_requires_confirmation_and_explicit_finite_level(self):
        for change in ({'operator_confirmed': False}, {'operator_confirmed': 1},
                       {'known_spl_db': None}, {'known_spl_db': float('inf')},
                       {'frequency_hz': True}, {'frequency_hz': 0}):
            with self.subTest(change=change):
                body = self.calibration_body(); body.update(change)
                with self.assertRaises(ValueError):
                    calibration.validate_calibration_request(body)
        self.assertEqual(self.recorders, [])


if __name__ == '__main__':
    unittest.main()
