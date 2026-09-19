"""External reference tests use synthetic audio and mocked PortAudio only."""
import json
import math
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from measurement_app import reference as r
import numpy as np
import soundfile as sf


INVENTORY = [{'index': 7, 'name': 'Measurement USB Microphone', 'hostapi_name': 'Windows WASAPI',
              'max_input_channels': 4, 'max_output_channels': 0}]


def configuration(**overrides):
    result = {'enabled': True, 'device_index': 7, 'device_name': INVENTORY[0]['name'],
              'hostapi_name': 'Windows WASAPI', 'channel': 2, 'sample_rate_hz': 48000,
              'duration_seconds': 2, 'microphone_model': 'Test microphone',
              'microphone_serial': 'ABC', 'interface_gain_note': 'Gain mark 3'}
    result.update(overrides)
    return result


def flags(*names):
    return SimpleNamespace(**{key: key in names for key in r.STATUS_NAMES})


def timing(at=0):
    return SimpleNamespace(inputBufferAdcTime=10 + at / 48000, currentTime=10.16 + at / 48000)


class ValidationTests(unittest.TestCase):
    def test_disabled_does_not_enumerate_or_inspect_stale_paths(self):
        with patch.object(r, 'devices', side_effect=AssertionError('Hardware enumeration forbidden')):
            self.assertEqual(r.validate_reference(None), {'enabled': False})
            self.assertEqual(r.validate_reference({'enabled': False, 'calibration_record': 'missing.json'}), {'enabled': False})

    def test_identity_and_channel_are_exact_and_never_silently_rebound(self):
        valid = r.validate_reference(configuration(), INVENTORY)
        self.assertEqual(valid['opened_channels'], 2)
        for changes in ({'device_index': 8}, {'device_name': 'Other'}, {'hostapi_name': 'MME'},
                        {'channel': 5}, {'channel': 0}, {'channel': True}, {'channel': 9},
                        {'sample_rate_hz': 44100}, {'duration_seconds': 331},
                        {'duration_seconds': float('nan')}, {'sensitivity_pa_per_fs': 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                r.validate_reference(configuration(**changes), INVENTORY)

    def test_endpoint_policy_rejects_defaults_xvf_and_loopbacks(self):
        for name in ['Microsoft Sound Mapper - Input', 'Primary Sound Capture Driver', 'Default Input',
                     'XVF3800', 'XMOS USB Audio', 'Echo (X USB)', 'Stereo Mix (Realtek)',
                     'Microphone Loopback', 'What U Hear']:
            with self.subTest(name=name):
                self.assertIsNotNone(r.reference_endpoint_problem({**INVENTORY[0], 'name': name}))
        self.assertIsNone(r.reference_endpoint_problem(INVENTORY[0]))
        self.assertIsNotNone(r.reference_endpoint_problem({**INVENTORY[0], 'max_input_channels': 0}))

    def test_unknown_model_is_explicit_and_manual_scale_remains_optional(self):
        c = r.validate_reference(configuration(microphone_model=' '), INVENTORY)
        self.assertIn('Unknown', c['microphone_model'])
        self.assertIsNone(c['sensitivity_pa_per_fs'])

    def test_record_binding_requires_exact_mic_interface_gain_and_explicit_scale(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calibration.json'
            base = r.validate_reference(configuration(), INVENTORY)
            record = {'pa_per_fs': 3.5, 'input_configuration': {k: base[k] for k in r.BINDING_KEYS}}
            record['input_configuration']['device_index'] = 999  # Renumbered endpoint is allowed.
            path.write_text(json.dumps(record), encoding='utf-8')
            c = configuration(calibration_record=str(path), sensitivity_pa_per_fs=3.5)
            self.assertEqual(r.validate_reference(c, INVENTORY)['sensitivity_pa_per_fs'], 3.5)
            for changes in ({'sensitivity_pa_per_fs': None}, {'sensitivity_pa_per_fs': 3.6},
                            {'microphone_model': 'Other'}, {'microphone_serial': 'DEF'},
                            {'interface_gain_note': 'Gain mark 4'}, {'channel': 1}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    r.validate_reference({**c, **changes}, INVENTORY)
            del record['input_configuration']['microphone_serial']
            path.write_text(json.dumps(record), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'microphone_serial'):
                r.validate_reference(c, INVENTORY)

    def test_calibration_size_extension_and_json_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calibration.json'
            path.write_text('{"pa_per_fs": NaN}', encoding='utf-8')
            with self.assertRaises(ValueError):
                r.validate_reference(configuration(calibration_record=str(path), sensitivity_pa_per_fs=1), INVENTORY)
            with patch.object(r, 'MAX_CALIBRATION_BYTES', 4), self.assertRaisesRegex(ValueError, '10 MB'):
                r.validate_reference(configuration(calibration_file_path=str(path)), INVENTORY)
            bad = Path(directory) / 'calibration.exe'
            bad.write_bytes(b'original')
            with self.assertRaises(ValueError):
                r.validate_reference(configuration(calibration_file_path=str(bad)), INVENTORY)
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                r.validate_reference(configuration(calibration_file_path=str(Path(directory) / 'missing.cal')), INVENTORY)


class ReferenceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'reference'
        self.com = Mock()
        self.stop = threading.Event()
        self.chunks = [np.array([[0, -.1], [0, .2], [0, -.3]], np.float32),
                       np.array([[0, .4], [0, -.2], [0, .1], [0, 0]], np.float32)]
        self.status = flags()
        self.start_error = self.close_error = None
        self.instances = []
        test = self

        class FakeStream:
            def __init__(self, **kwargs):
                self.kwargs = kwargs; self.channels = kwargs['channels']; self.samplerate = kwargs['samplerate']
                self.latency = .16; self.active = False; self.stop_count = self.close_count = 0
                test.instances.append(self)

            def start(self):
                if test.start_error:
                    raise test.start_error
                self.active = True
                at = 0
                for block in test.chunks:
                    try:
                        self.kwargs['callback'](block, len(block), timing(at), test.status)
                    except (r.sd.CallbackStop, r.sd.CallbackAbort):
                        self.active = False; self.kwargs['finished_callback'](); break
                    at += len(block)

            def stop(self, ignore_errors=False):
                self.stop_count += 1; self.active = False; self.kwargs['finished_callback']()

            def close(self, ignore_errors=False):
                self.close_count += 1
                if test.close_error:
                    raise test.close_error
                self.active = False

        for name, value in [('devices', Mock(return_value=INVENTORY)),
                            ('_ComApartment', Mock(return_value=self.com))]:
            patcher = patch.object(r, name, value); patcher.start(); self.addCleanup(patcher.stop)
        for name, value in [('check_input_settings', Mock()), ('InputStream', FakeStream)]:
            patcher = patch.object(r.sd, name, value); patcher.start(); self.addCleanup(patcher.stop)

    def capture(self, **changes):
        return r.ReferenceCapture(self.folder, configuration(**changes), self.stop)

    def test_variable_callbacks_archive_exact_float_channels_and_selected_only_qc(self):
        capture = self.capture().start()
        self.assertTrue(capture.wait_ready(0))
        result = capture.finish()
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(result['stream_closed'])
        self.assertEqual(result['frames'], 7)
        original, rate = sf.read(self.folder / 'reference_original.wav', dtype='float32', always_2d=True)
        selected, _ = sf.read(self.folder / 'selected_reference.wav', dtype='float32')
        expected = np.concatenate(self.chunks)
        np.testing.assert_array_equal(original, expected)
        np.testing.assert_array_equal(selected, expected[:, 1])
        self.assertEqual(rate, 48000)
        self.assertEqual(sf.info(self.folder / 'reference_original.wav').subtype, 'FLOAT')
        metadata = json.loads((self.folder / 'capture.json').read_text())
        self.assertEqual([row['first_frame'] for row in metadata['callback_times']], [0, 3])
        self.assertEqual([row['received_frames'] for row in metadata['callback_times']], [3, 4])
        self.assertLessEqual(result['start_monotonic_ns'], metadata['first_callback_monotonic_ns'])
        self.assertGreaterEqual(result['end_monotonic_ns'], metadata['last_callback_monotonic_ns'])
        self.assertEqual(self.instances[0].kwargs['latency'], .15)
        self.assertIsNone(result['quality']['user_scale_estimated_spl_db'])
        self.assertFalse(result['quality']['absolute_spl_calibration_verified'])
        self.com.open.assert_called_once(); self.com.close.assert_called_once()
        before = {p.name: p.read_bytes() for p in self.folder.iterdir() if p.is_file()}
        self.assertIs(capture.finish(), result)
        self.assertEqual(self.instances[0].close_count, 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir() if p.is_file()})

    def test_selected_zero_channel_fails_but_original_evidence_is_kept(self):
        self.chunks = [np.array([[.1, 0], [-.1, 0]], np.float32)]
        result = self.capture().start().finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(result['quality']['checks']['nonzero'])
        self.assertTrue((self.folder / 'reference_original.wav').is_file())

    def test_nonfinite_or_clipping_fails_without_rewriting_values(self):
        self.chunks = [np.array([[0, np.nan], [0, 1], [0, -.2]], np.float32)]
        result = self.capture().start().finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(result['quality']['checks']['all_finite'])
        self.assertFalse(result['quality']['checks']['not_near_full_scale'])
        saved, _ = sf.read(self.folder / 'reference_original.wav', dtype='float32', always_2d=True)
        np.testing.assert_array_equal(saved, self.chunks[0])

    def test_callback_status_is_preserved_and_fails_quality(self):
        self.status = flags('input_overflow')
        result = self.capture().start().finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('input_overflow', result['quality']['callback_status_events'][0]['status_flags'])

    def test_duration_capacity_stops_and_retains_only_allocated_frames(self):
        self.chunks = [np.tile(np.array([[0, .2], [0, -.2]], np.float32), (30, 1))]
        result = self.capture(duration_seconds=.001).start().finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['frames'], 48)
        self.assertTrue(result['quality']['duration_bound_reached'])
        metadata = json.loads((self.folder / 'capture.json').read_text())
        self.assertEqual(metadata['callback_times'][0]['received_frames'], 60)
        self.assertEqual(metadata['callback_times'][0]['retained_frames'], 48)

    def test_cancellation_preserves_partial_audio_and_is_not_a_pass(self):
        capture = self.capture().start()
        self.stop.set()
        result = capture.finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(result['quality']['stop_requested'])
        self.assertTrue(result['stream_closed'])
        self.assertTrue((self.folder / 'reference_original.wav').exists())

    def test_no_first_buffer_is_not_ready_or_pass(self):
        self.chunks = []
        capture = self.capture().start()
        self.assertFalse(capture.wait_ready(0))
        result = capture.finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['frames'], 0)
        self.assertFalse((self.folder / 'reference_original.wav').exists())

    def test_bad_callback_shape_keeps_error_and_prevents_false_pass(self):
        self.chunks = [np.zeros((5, 3), np.float32)]
        result = self.capture().start().finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('buffer shape', result['error'])

    def test_start_error_can_be_finished_on_owner_thread_and_com_is_balanced(self):
        self.start_error = RuntimeError('start failed')
        capture = self.capture()
        with self.assertRaisesRegex(RuntimeError, 'start failed'):
            capture.start()
        result = capture.finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(result['stream_closed'])
        self.assertIn('start failed', result['error'])
        self.com.close.assert_called_once()

    def test_failed_close_keeps_writer_liveness_and_does_not_archive_or_release_com(self):
        self.close_error = RuntimeError('close failed')
        result = self.capture().start().finish()
        self.assertFalse(result['stream_closed'])
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('close failed', result['error'])
        self.com.close.assert_not_called()
        self.assertFalse((self.folder / 'reference_original.wav').exists())
        self.assertFalse((self.folder / 'capture.json').exists())

    def test_finish_on_wrong_thread_cannot_close_or_consume_owner_cleanup(self):
        capture = self.capture().start()
        other = []
        worker = threading.Thread(target=lambda: other.append(capture.finish()))
        worker.start(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(other[0]['stream_closed'])
        self.assertEqual(self.instances[0].close_count, 0)
        self.assertEqual(capture.finish()['status'], 'PASS')
        self.com.close.assert_called_once()

    def test_calibration_snapshots_are_distinct_original_bytes_and_not_applied_to_audio(self):
        frequency = Path(self.temp.name) / 'manufacturer.cal'
        frequency.write_bytes(b'1000, 0.7\r\n2000, -1.2\r\n')
        record = Path(self.temp.name) / 'sensitivity.json'
        c = r.validate_reference(configuration(), INVENTORY)
        record.write_text(json.dumps({'pa_per_fs': 5, 'input_configuration': {k: c[k] for k in r.BINDING_KEYS}}), encoding='utf-8')
        result = self.capture(calibration_file_path=str(frequency), calibration_record=str(record), sensitivity_pa_per_fs=5).start().finish()
        self.assertEqual(result['status'], 'PASS')
        for source, target in [(frequency, 'frequency_response_original.cal'), (record, 'calibration_record_original.json')]:
            self.assertEqual(source.read_bytes(), (self.folder / 'calibration' / target).read_bytes())
        provenance = json.loads((self.folder / 'calibration' / 'provenance.json').read_text())
        self.assertEqual(len(provenance['files']), 2)
        for item in provenance['files']:
            self.assertEqual(item['sha256'], r.sha(self.folder / item['snapshot_path']))
        self.assertFalse(provenance['frequency_response_applied'])
        self.assertFalse(provenance['sensitivity_applied_to_audio'])
        selected, _ = sf.read(self.folder / 'selected_reference.wav', dtype='float32')
        np.testing.assert_array_equal(selected, np.concatenate(self.chunks)[:, 1])
        self.assertIsNotNone(result['quality']['user_scale_estimated_spl_db'])

    def test_record_changed_after_validation_is_rechecked_before_opening_audio(self):
        record_path = Path(self.temp.name) / 'sensitivity.json'
        c = r.validate_reference(configuration(), INVENTORY)
        record = {'pa_per_fs': 5, 'input_configuration': {k: c[k] for k in r.BINDING_KEYS}}
        record_path.write_text(json.dumps(record), encoding='utf-8')
        real_validate = r.validate_reference

        def validate_then_change(config):
            validated = real_validate(config, INVENTORY)
            record['input_configuration']['interface_gain_note'] = 'Changed gain'
            record_path.write_text(json.dumps(record), encoding='utf-8')
            return validated

        capture = self.capture(calibration_record=str(record_path), sensitivity_pa_per_fs=5)
        with patch.object(r, 'validate_reference', side_effect=validate_then_change):
            with self.assertRaisesRegex(ValueError, 'interface_gain_note'):
                capture.start()
        self.assertFalse(self.instances)
        result = capture.finish()
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(result['stream_closed'])
        self.assertFalse((self.folder / 'reference_original.wav').exists())


class SensitivityTests(unittest.TestCase):
    @staticmethod
    def tone(frequency=1000, amplitude=.2, seconds=2):
        return amplitude * np.sin(2 * np.pi * frequency * np.arange(int(48000 * seconds)) / 48000)

    def test_known_tone_derives_pressure_scale_without_modifying_samples(self):
        tone = self.tone() + .01
        original = tone.copy()
        result = r.estimate_sensitivity(tone, 48000, 94, 1000)
        expected = 20e-6 * 10 ** (94 / 20) / (.2 / math.sqrt(2))
        self.assertAlmostEqual(result['pa_per_fs'], expected, places=10)
        self.assertAlmostEqual(result['db_spl_at_rms_1'], 94 - 20 * math.log10(.2 / math.sqrt(2)), places=10)
        self.assertFalse(result['physical_calibrator_and_coupling_verified'])
        self.assertFalse(result['frequency_response_correction_applied'])
        np.testing.assert_array_equal(tone, original)

    def test_invalid_zero_clipped_nonfinite_short_and_wrong_frequency_are_rejected(self):
        for samples in [np.zeros(96000), np.ones(96000) * .2, self.tone(amplitude=1),
                        np.full(96000, np.nan), self.tone(seconds=1), self.tone(frequency=500),
                        np.ones((96000, 1)) * .2]:
            with self.subTest(shape=samples.shape), self.assertRaises(ValueError):
                r.estimate_sensitivity(samples, 48000, 94, 1000)
        for level in [None, True, float('nan'), 39, 141]:
            with self.subTest(level=level), self.assertRaises(ValueError):
                r.estimate_sensitivity(self.tone(), 48000, level, 1000)

    def test_strong_broadband_contamination_fails_tonality(self):
        samples = self.tone(amplitude=.1) + np.random.default_rng(123).normal(0, .1, 96000)
        with self.assertRaisesRegex(ValueError, 'stable calibrator'):
            r.estimate_sensitivity(samples, 48000, 94, 1000)

    def test_level_step_is_rejected_despite_correct_frequency_and_tonality(self):
        samples = self.tone(seconds=4)
        samples[96000:] *= 10 ** (-.6 / 20)
        with self.assertRaisesRegex(ValueError, 'one-second AC RMS spread exceeds 0.5 dB'):
            r.estimate_sensitivity(samples, 48000, 94, 1000)
        samples[96000:] *= 10 ** (.2 / 20)
        result = r.estimate_sensitivity(samples, 48000, 94, 1000)
        self.assertAlmostEqual(result['one_second_level_spread_db'], .4, places=8)
        self.assertEqual(result['maximum_allowed_one_second_level_spread_db'], .5)


if __name__ == '__main__':
    unittest.main()
