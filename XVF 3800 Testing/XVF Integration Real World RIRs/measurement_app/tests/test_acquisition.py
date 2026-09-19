"""Hardware-free evidence integrity tests; audio/control APIs are never called.

Known PCM bytes and independently formed packing groups verify the format.
Adversarial continuity cases distinguish intact framing from intact data.
"""
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from measurement_app import acquisition, core
import numpy as np
import soundfile as sf


class PCM24Tests(unittest.TestCase):
    def test_known_signed_little_endian_bytes(self):
        values = np.array([[-8388608, -65537], [-256, -1], [0, 1], [65536, 8388607]], dtype=np.int32)
        expected = bytes.fromhex('000080 fffffe 00ffff ffffff 000000 010000 000001 ffff7f')
        self.assertEqual(core.pack_pcm24(values), expected)
        np.testing.assert_array_equal(core.unpack_pcm24(expected), values)

    def test_rejects_count_overflow_before_narrowing(self):
        for value in [-8388609, 8388608, 2**32, -(2**32)]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    core.pack_pcm24(np.array([value], dtype=np.int64))

    def test_pcm24_wav_preserves_all_count_bits(self):
        values = np.array([[-8388608, -255], [-1, 0], [1, 257], [8388607, 65537]], dtype=np.int32)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'precision.wav'
            core.save_counts(path, values, 16000, 24)
            samples, rate = sf.read(path, dtype='int32', always_2d=True)
            self.assertEqual(rate, 16000)
            self.assertEqual(sf.info(path).subtype, 'PCM_24')
            np.testing.assert_array_equal(samples >> 8, values)


class PackedFramingTests(unittest.TestCase):
    def test_golden_six_channel_order_and_signed_counts(self):
        # Independent explicit wire frames; native stereo frames carry slots 0/1, 2/3, 4/5.
        native = np.array([[0, 2], [5, 7], [9, 11], [-12, -10], [-7, -5], [-3, -1]], dtype=np.int32)
        expected = np.array([[0, 2, 4, 6, 8, 10], [-12, -10, -8, -6, -4, -2]], dtype=np.int32)
        decoded, quality = core.decode_packed(native, 24)
        np.testing.assert_array_equal(decoded, expected)
        self.assertEqual(quality['payload_bits'], 23)
        self.assertEqual(quality['marker_error_count'], 0)
        self.assertFalse(quality['internal_repair_performed'])

    def test_startup_crop_and_partial_tail_are_explicit(self):
        native = np.array([[0, 0], [0, 0], [2, 4], [7, 9], [11, 13], [20, 22]], dtype=np.int32)
        decoded, quality = core.decode_packed(native, 16)
        np.testing.assert_array_equal(decoded, [[2, 4, 6, 8, 10, 12]])
        self.assertEqual(quality['startup_frames_excluded'], 2)
        self.assertEqual(quality['trailing_frames'], 1)

    def test_one_stereo_side_marker_corruption_is_detected_without_repair(self):
        native = np.array([[0, 2], [5, 7], [9, 11], [12, 14], [17, 18], [21, 23]], dtype=np.int32)
        decoded, quality = core.decode_packed(native, 24)
        self.assertEqual(len(decoded), 2)
        self.assertEqual(quality['marker_error_count'], 1)
        self.assertEqual(quality['first_marker_errors'], [4])

    def test_no_marker_pattern_rejects_capture(self):
        with self.assertRaises(RuntimeError):
            core.decode_packed(np.zeros((120, 2), dtype=np.int32), 24)


class ContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(61903)
        cls.source = np.zeros(80000, dtype=np.int32)
        cls.source[16000:-16000] = rng.integers(-100000, 100000, size=48000, dtype=np.int32) & -2

    def decoded(self, column):
        data = np.zeros((len(column), 6), dtype=np.int32)
        data[:, 0] = column
        return data

    def test_known_delay_with_complete_active_sequence_passes(self):
        capture = np.concatenate([np.zeros(900, dtype=np.int32), self.source[:-900]])
        quality = acquisition.sentinel_qc(self.decoded(capture), self.source)
        self.assertEqual(quality['status'], 'PASS')
        self.assertEqual(quality['source_minus_capture_sample_offset'], -900)
        self.assertEqual(quality['mismatches'], 0)
        self.assertTrue(quality['complete_active_source_captured'])

    def test_single_changed_data_word_fails_even_when_framing_would_be_intact(self):
        capture = self.source.copy()
        capture[55000] ^= 2
        quality = acquisition.sentinel_qc(self.decoded(capture), self.source)
        self.assertEqual(quality['status'], 'FAIL')
        self.assertEqual(quality['mismatches'], 1)

    def test_dropped_and_duplicated_collection_groups_fail(self):
        for capture in [np.delete(self.source, 55000), np.insert(self.source, 55000, self.source[55000])]:
            with self.subTest(length=len(capture)):
                self.assertEqual(acquisition.sentinel_qc(self.decoded(capture), self.source)['status'], 'FAIL')

    def test_exact_prefix_with_missing_active_tail_does_not_pass(self):
        quality = acquisition.sentinel_qc(self.decoded(self.source[:60000]), self.source)
        self.assertEqual(quality['status'], 'FAIL')
        self.assertEqual(quality['mismatches'], 0)
        self.assertFalse(quality['complete_active_source_captured'])

    def test_missing_active_head_does_not_pass(self):
        quality = acquisition.sentinel_qc(self.decoded(self.source[18000:]), self.source)
        self.assertEqual(quality['status'], 'FAIL')
        self.assertFalse(quality['complete_active_source_captured'])

    def test_repeated_alignment_anchor_is_ambiguous(self):
        capture = self.source.copy()
        capture[50000:50064] = self.source[32000:32064]
        quality = acquisition.sentinel_qc(self.decoded(capture), self.source)
        self.assertEqual(quality['status'], 'FAIL')
        self.assertIn('ambiguous', quality['reason'])


# Acoustic marker tests live in test_markers.py, including real V2 assets and adversarial timing.

class RequestValidationTests(unittest.TestCase):
    def test_shared_endpoint_policy_allows_named_realtek_and_unique_xvf_wdm(self):
        endpoints = [
            {'index': 1, 'name': 'Speakers (Realtek(R) Audio)', 'hostapi_name': 'Windows WASAPI', 'max_output_channels': 2},
            {'index': 2, 'name': 'Output (XVF3800 Voice Processor)', 'hostapi_name': 'Windows WDM-KS', 'max_output_channels': 2},
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint['name']):
                self.assertIsNone(core.playback_endpoint_problem(endpoint, endpoints))
                with patch.object(acquisition, 'get_excitation', return_value={'id': 'fixture'}), patch.object(acquisition, 'devices', return_value=endpoints):
                    validated = acquisition.validate_request({'mode': 'measure', 'excitation_id': 'fixture', 'playback_device_index': endpoint['index']})
                self.assertEqual(validated['playback_device_index'], endpoint['index'])

    def test_shared_endpoint_policy_rejects_default_routes_and_truncated_xvf_aliases(self):
        canonical = {'index': 1, 'name': 'Output (XVF3800 Voice Processor)', 'hostapi_name': 'Windows WDM-KS', 'max_output_channels': 2}
        for name in ['Microsoft Sound Mapper - Output', 'Primary Sound Driver', 'Speakers (XVF3800 Voice Processor)', 'Echo Cancelling Speakerphone (X', 'Speakers (XMOS USB Audio)']:
            alias = {'index': 2, 'name': name, 'hostapi_name': 'MME', 'max_output_channels': 2}
            endpoints = [canonical, alias]
            with self.subTest(name=name):
                self.assertIsNotNone(core.playback_endpoint_problem(alias, endpoints))
                with patch.object(acquisition, 'get_excitation', return_value={'id': 'fixture'}), patch.object(acquisition, 'devices', return_value=endpoints):
                    with self.assertRaises(ValueError):
                        acquisition.validate_request({'mode': 'measure', 'excitation_id': 'fixture', 'playback_device_index': 2})

    def test_duplicate_xvf_wdm_outputs_are_ambiguous(self):
        endpoints = [{'index': index, 'name': 'Output (XVF3800 Voice Processor)', 'hostapi_name': 'Windows WDM-KS', 'max_output_channels': 2} for index in [1, 2]]
        self.assertIsNotNone(core.playback_endpoint_problem(endpoints[0], endpoints))

    def test_reserved_xvf_right_channel_is_rejected(self):
        endpoints = [{'index': 1, 'name': 'Output (XVF3800 Voice Processor)', 'hostapi_name': 'Windows WDM-KS', 'max_output_channels': 2}]
        with patch.object(acquisition, 'get_excitation', return_value={'id': 'fixture'}), patch.object(acquisition, 'devices', return_value=endpoints):
            with self.assertRaisesRegex(ValueError, 'reserved'):
                acquisition.validate_request({'mode': 'measure', 'excitation_id': 'fixture', 'playback_device_index': 1, 'playback_channel': 'right'})

    def test_unknown_setup_values_stay_null_without_hardware_enumeration(self):
        with patch.object(acquisition, 'devices', side_effect=AssertionError('hardware inventory forbidden')):
            request = acquisition.validate_request({'mode': 'record', 'setup': {'distance_m': None, 'yaw_deg': None}})
        self.assertIsNone(request['setup']['distance_m'])
        self.assertIsNone(request['setup']['yaw_deg'])

    def test_nonfinite_numbers_and_invalid_ranges_are_rejected(self):
        for key, value in [('duration_seconds', float('nan')), ('duration_seconds', 0), ('duration_seconds', 301), ('playback_gain_db', float('inf')), ('playback_gain_db', 1), ('playback_gain_db', -61)]:
            with self.subTest(key=key, value=value):
                with self.assertRaises((ValueError, TypeError)):
                    acquisition.validate_request({'mode': 'record', key: value})

    def test_stale_endpoint_name_is_rejected_before_playback(self):
        endpoints = [{'index': 7, 'name': 'Different speaker', 'max_output_channels': 2}]
        with patch.object(acquisition, 'get_excitation', return_value={'id': 'fixture'}), patch.object(acquisition, 'devices', return_value=endpoints):
            with self.assertRaisesRegex(ValueError, 'changed'):
                acquisition.validate_request({'mode': 'measure', 'excitation_id': 'fixture', 'playback_device_index': 7, 'playback_device_name': 'Saved speaker'})


class OutcomeTests(unittest.TestCase):
    def test_failed_playback_cannot_be_hidden_by_failed_markers(self):
        outcome=acquisition.choose_outcome('measure',{'known_sequence':True,'playback':False},marker_status='RETAKE',failure_details={'playback':'Startup failed; zero frames written'})
        self.assertEqual(outcome['status'],'INVESTIGATE')
        self.assertFalse(outcome['capture_integrity_pass'])
        self.assertEqual(outcome['failed_checks'],['playback'])
        self.assertIn('zero frames',outcome['message'])

    def test_capture_error_precedes_marker_failure(self):
        outcome=acquisition.choose_outcome('measure',{'playback':True},error='USB readback failed',marker_status='RETAKE')
        self.assertEqual(outcome['status'],'INVESTIGATE')
        self.assertIn('USB readback failed',outcome['message'])

    def test_only_clean_capture_with_bad_markers_is_marker_retake(self):
        outcome=acquisition.choose_outcome('measure',{'playback':True,'known_sequence':True},marker_status='RETAKE')
        self.assertEqual(outcome['status'],'RETAKE')
        self.assertTrue(outcome['capture_integrity_pass'])

    def test_stop_is_partial_retake_and_no_checks_is_investigate(self):
        self.assertEqual(acquisition.choose_outcome('measure',{'playback':False},error='failure',stopped=True)['status'],'RETAKE')
        self.assertEqual(acquisition.choose_outcome('record',{})['status'],'INVESTIGATE')

    def test_record_message_is_about_audio_and_metrics_and_measure_is_review(self):
        outcome=acquisition.choose_outcome('record',{'known_sequence':True})
        self.assertEqual(outcome['status'],'PASS')
        self.assertIn('direction/energy',outcome['message'])
        self.assertNotIn('RIR',outcome['message'])
        self.assertEqual(acquisition.choose_outcome('measure',{'known_sequence':True},marker_status='REVIEW')['status'],'REVIEW')

class CaptureLifecycleTests(unittest.TestCase):
    def fake_capture(self, hook=None, stop=None):
        vector = np.array([[0, 2], [5, 7], [9, 11]] * 4, dtype=np.int32)
        encoded = core.pack_pcm24(vector)
        class FakeStream:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.samplerate = 48000
                self.latency = (.04, .04)
                self.blocksize = 0
            def __enter__(self):
                timing = SimpleNamespace(inputBufferAdcTime=1.0, outputBufferDacTime=1.08, currentTime=1.04)
                try:
                    self.kwargs['callback'](encoded, bytearray(len(encoded)), len(vector), timing, False)
                except core.sd.CallbackStop:
                    pass
                self.kwargs['finished_callback']()
                return self
            def __exit__(self, *args):
                return False
            def abort(self):
                self.kwargs['finished_callback']()
        with patch.object(core, 'xvf_endpoints', return_value=({'index': 1}, {'index': 2})), \
             patch.object(core.sd, 'check_input_settings'), \
             patch.object(core.sd, 'check_output_settings'), \
             patch.object(core.sd, 'RawStream', FakeStream):
            return core.capture_native(5, 24, on_started=hook, stop_event=stop), vector

    def test_failed_startup_hook_retains_already_captured_frames(self):
        def fails():
            raise RuntimeError('simulated control readback failure')
        (raw, metadata), expected = self.fake_capture(hook=fails)
        np.testing.assert_array_equal(raw, expected)
        self.assertTrue(any('startup hook' in error for error in metadata['callback_errors']))

    def test_cancelled_capture_is_marked_partial(self):
        stop = threading.Event()
        stop.set()
        (raw, metadata), _ = self.fake_capture(stop=stop)
        self.assertTrue(metadata['stop_requested'])
        self.assertLess(len(raw), 5 * 48000)


if __name__ == '__main__':
    unittest.main()
