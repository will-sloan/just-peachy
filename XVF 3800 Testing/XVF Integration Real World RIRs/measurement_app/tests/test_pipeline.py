"""Exercise actual acquire serialization/QC/restoration with no hardware.

The six-channel fixture is independently encoded into native stereo slots.
Only device control, telemetry transport and the native audio boundary are
replaced. PCM24 serialization, demultiplexing, statistics, outcomes and hash
sealing run through production code in a temporary directory.
"""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from measurement_app import acquisition, core
import numpy as np
import soundfile as sf


class MemoryControl:
    def __init__(self, folder, wrong_array=False, mic_gain=4):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.state = {'AUDIO_MGR_OP_ALL': [6, 3] * 6, 'AUDIO_MGR_OP_PACKED': [0, 0],
                      'AUDIO_MGR_OP_UPSAMPLE': [0, 0], 'GPO_PORT_PIN_INDEX': [0, 4],
                      'USB_BIT_DEPTH': [24, 24], 'I2S_DAC_DSP_ENABLE': [0],
                      'AUDIO_MGR_MIC_GAIN':[mic_gain], 'AUDIO_MGR_SYS_DELAY':[-32]}
        self.pins = {
            3: {'GPO_PIN_ACTIVE_LEVEL': [1], 'GPO_PIN_PWM_DUTY': [100], 'GPO_PIN_FLASH_MASK': [4294967295]},
            4: {'GPO_PIN_ACTIVE_LEVEL': [1], 'GPO_PIN_PWM_DUTY': [100 if wrong_array else 0], 'GPO_PIN_FLASH_MASK': [4294967295]},
        }
        self.original_state = copy.deepcopy(self.state)
        self.original_pins = copy.deepcopy(self.pins)
        self.operations = []
        self.forbid_calls = False

    def check(self, name):
        if self.forbid_calls:
            raise AssertionError('Control after an unclosed telemetry writer: ' + name)
        self.operations.append(name)

    def identify(self):
        self.check('identify')
        return {name:copy.deepcopy(self.state[name]) for name in ['USB_BIT_DEPTH','AUDIO_MGR_MIC_GAIN','AUDIO_MGR_SYS_DELAY']}

    def values(self, name):
        self.check('read ' + name)
        if name.startswith('GPO_PIN_'):
            return copy.deepcopy(self.pins[self.state['GPO_PORT_PIN_INDEX'][1]][name])
        return copy.deepcopy(self.state[name])

    def set(self, name, values):
        self.check('write ' + name)
        if name.startswith('GPO_PIN_'):
            self.pins[self.state['GPO_PORT_PIN_INDEX'][1]][name] = list(values)
        else:
            self.state[name] = list(values)

    def query(self, name, *args):
        self.check('query ' + name)
        if name == '--dump-params':
            return 'Offline fixture; no device commands were issued.\n'
        if name == 'GPO_PIN_VAL':
            port, pin, enabled = args
            if port != 0:
                raise AssertionError('Unexpected fixture GPIO port')
            self.pins[pin]['GPO_PIN_PWM_DUTY'] = [enabled * 100]
            return ''
        raise AssertionError('Unexpected fixture command: ' + name)


class MemoryTelemetry:
    def __init__(self, closes=True):
        self.latest = {name: {} for name in acquisition.DEFAULT_FIELDS}
        self.rows = []
        self.closes = closes
        self.stop_reasons = []

    def start(self): return self
    def stop(self, reason): self.stop_reasons.append(reason)
    def wait(self, timeout): return {'status': 'PASS'} if self.closes else None


class ActualAcquisitionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='xvf_pipeline_offline_')
        self.base = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def run_pipeline(self, domain='raw', corrupt_reference=False, wrong_array=False, telemetry_closes=True,
                     mode='record', marker_status='REVIEW', external_reference=None, schema_version=None, mic_gain=4, changed_gain=None):
        controls = []
        telemetry = MemoryTelemetry(telemetry_closes)
        expected = {}
        category = 1 if domain == 'raw' else 3
        fixture_wave = .1 * np.sin(np.arange(480) * np.pi / 12)
        fixture_path = self.base / 'offline_excitation.wav'
        sf.write(fixture_path, fixture_wave, 48000, subtype='FLOAT')

        def control_factory(folder):
            control = MemoryControl(folder, wrong_array, mic_gain)
            controls.append(control)
            return control

        def capture(seconds, bits, payload, stop, on_started, progress):
            self.assertEqual(bits, 24)
            self.assertEqual(controls[0].state['AUDIO_MGR_OP_ALL'],
                             [10, 1, category, 0, category, 2, 6, 3, category, 1, category, 3])
            self.assertEqual(controls[0].state['AUDIO_MGR_OP_PACKED'], [1, 1])
            self.assertEqual(controls[0].pins[3]['GPO_PIN_PWM_DUTY'], [100 if mode == 'measure' else 0])
            on_started()
            if mode == 'measure':
                emitted = np.rint(fixture_wave.astype(np.float32).astype(np.float64)
                                  * 10 ** (-18 / 20) * 2 ** 23).astype(np.int32)
                np.testing.assert_array_equal(payload[72000:72480, 0], emitted)
                np.testing.assert_array_equal(payload[:72000, 0], 0)
                np.testing.assert_array_equal(payload[72480:, 0], 0)
            else:
                np.testing.assert_array_equal(payload[:, 0], 0)
            np.testing.assert_array_equal(payload[0::3, 1], payload[1::3, 1])
            np.testing.assert_array_equal(payload[0::3, 1], payload[2::3, 1])
            reference = payload[::3, 1]
            count = len(reference)
            index = np.arange(count, dtype=np.int32)
            processed = ((index % 37) - 18) * 400
            mics = np.column_stack([(((index * (mic + 1)) % (51 + mic * 2)) - 25) * 16 * (mic + 1)
                                    for mic in range(4)]).astype(np.int32)
            expected['decoded'] = np.column_stack([reference, processed, mics])
            # Independent channel-to-wire mapping, not production pack/decode.
            native = np.empty((count * 3, 2), dtype=np.int32)
            native[0::3, 0] = reference
            native[0::3, 1] = processed
            native[1::3, 0] = mics[:, 0] | 1
            native[1::3, 1] = mics[:, 1] | 1
            native[2::3, 0] = mics[:, 2] | 1
            native[2::3, 1] = mics[:, 3] | 1
            if corrupt_reference:
                native[40000 * 3, 0] ^= 2
            start = 1_000_000_000
            end = start + round(seconds * 1e9)
            for field in acquisition.DEFAULT_FIELDS:
                telemetry.rows.extend({'command': field, 'host_line_arrival_monotonic_ns': timestamp,
                                       'host_response_end_monotonic_ns': timestamp}
                                      for timestamp in (start - 1_000_000, end + 1_000_000))
            meta = {'start_monotonic_ns': start, 'end_monotonic_ns': end,
                    'callback_flags': [], 'callback_errors': [],
                    'captured_frames': len(native), 'native_rate_hz': 48000,
                    'container_bits': 24, 'stop_requested': False}
            progress(1)
            if changed_gain is not None:controls[0].state['AUDIO_MGR_MIC_GAIN']=[changed_gain]
            if not telemetry_closes:
                controls[0].forbid_calls = True
            return native, meta

        request = {'mode': mode, 'duration_seconds': 5, 'domain': domain,
                   'playback_gain_db': -18, 'setup': {}}
        inventory = []
        if mode == 'measure':
            request.update(schema_version=2, playback_device_index=33, playback_channel='left',
                           excitation_id='offline_fixture', setup={
                               'room_name': 'Offline room', 'position_name': 'Offline position',
                               'source': {'distance_to_array_m': 1.2, 'azimuth_lab_deg': 0},
                               'device': {'orientation': 'FLAT'}, 'obstruction': {'present': False},
                               'clutter_state': 'unknown'})
            inventory = [{'index': 33, 'name': 'Output (XVF3800 Voice Processor)',
                          'hostapi_name': 'Windows WDM-KS', 'max_output_channels': 2}]
        if schema_version is not None:request['schema_version']=schema_version
        reference = Mock()
        reference.start.return_value=reference
        reference.wait_ready.return_value=True
        def finish_reference():
            if external_reference is not None and not external_reference.get('stream_closed',False):controls[0].forbid_calls=True
            return external_reference
        reference.finish.side_effect=finish_reference
        folder = self.base / ('trial_' + domain)
        with patch.object(acquisition, 'validate_reference', return_value={'enabled':external_reference is not None}), \
             patch.object(acquisition, 'ReferenceCapture', return_value=reference), \
             patch.object(acquisition, 'Control', side_effect=control_factory), \
             patch.object(acquisition, 'devices', return_value=inventory), \
             patch.object(acquisition, 'xvf_endpoints', return_value=({'index': 34}, {'index': 33})), \
             patch.object(acquisition, 'get_excitation', return_value={'id': 'offline_fixture', 'path': str(fixture_path)}), \
             patch.object(acquisition, 'marker_qc', return_value={'status': marker_status, 'offline_fixture': True}), \
             patch.object(acquisition, 'create_telemetry_logger', return_value=telemetry) as logger, \
             patch.object(acquisition, 'capture_native', side_effect=capture) as audio:
            result = acquisition.acquire(request, folder, threading.Event(), lambda **kw: None)
        return folder, result, controls[0], telemetry, expected, audio, logger

    def assert_seal(self, folder):
        manifest = folder / 'SHA256SUMS.txt'
        self.assertTrue(manifest.is_file())
        lines = manifest.read_text().splitlines()
        self.assertGreater(len(lines), 10)
        for line in lines:
            digest, relative = line.split('  ', 1)
            self.assertEqual(core.sha(folder / relative), digest, relative)

    def test_raw_and_amplified_full_pipeline_preserve_all_channels_and_restore(self):
        for domain in ('raw', 'amplified'):
            with self.subTest(domain=domain):
                folder, result, control, telemetry, expected, audio, logger = self.run_pipeline(domain)
                self.assertEqual(result['status'], 'PASS')
                self.assertTrue(result['capture_integrity_pass'])
                self.assertFalse(result['scientific_measurement_qualified'])
                self.assertTrue(all(result['checks'].values()))
                self.assertEqual(control.state, control.original_state)
                self.assertEqual(control.pins, control.original_pins)
                self.assertEqual(telemetry.stop_reasons, ['audio_capture_ended'])
                for mic in range(4):
                    samples, rate = sf.read(folder / f'MIC{mic}.wav', dtype='int32', always_2d=True)
                    self.assertEqual(rate, 16000)
                    self.assertEqual(sf.info(folder / f'MIC{mic}.wav').subtype, 'PCM_24')
                    np.testing.assert_array_equal(samples[:, 0] >> 8, expected['decoded'][:, mic + 2])
                decoded, rate = sf.read(folder / 'decoded_six_channels.wav', dtype='int32', always_2d=True)
                np.testing.assert_array_equal(decoded >> 8, expected['decoded'])
                self.assertEqual(result['quality']['continuity']['mismatches'], 0)
                self.assert_seal(folder)

    def test_corrupt_data_with_valid_framing_is_retained_and_fails_integrity(self):
        folder, result, control, telemetry, expected, audio, logger = self.run_pipeline(corrupt_reference=True)
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.assertFalse(result['capture_integrity_pass'])
        self.assertEqual(result['quality']['marker_error_count'], 0)
        self.assertEqual(result['quality']['continuity']['mismatches'], 1)
        self.assertEqual(control.state, control.original_state)
        self.assertEqual(control.pins, control.original_pins)
        self.assertTrue((folder / 'native_packed.wav').is_file())
        self.assert_seal(folder)

    def test_measurement_serializes_exact_excitation_on_left_and_requires_review(self):
        folder, result, control, telemetry, expected, audio, logger = self.run_pipeline(mode='measure')
        self.assertEqual(result['status'], 'REVIEW')
        self.assertTrue(result['capture_integrity_pass'])
        self.assertTrue(result['same_clock_playback'])
        self.assertFalse(result['scientific_measurement_qualified'])
        self.assertEqual(core.sha(folder / 'excitation_original.wav'), core.sha(self.base / 'offline_excitation.wav'))
        self.assertEqual(control.state, control.original_state)
        self.assertEqual(control.pins, control.original_pins)
        self.assert_seal(folder)

    def test_measurement_marker_retake_is_not_overridden_by_exact_digital_capture(self):
        folder, result, control, telemetry, expected, audio, logger = self.run_pipeline(mode='measure', marker_status='RETAKE')
        self.assertTrue(result['capture_integrity_pass'])
        self.assertEqual(result['quality']['continuity']['mismatches'], 0)
        self.assertEqual(result['status'], 'RETAKE')
        self.assertEqual(result['acoustic_marker_review'], 'RETAKE')
        self.assertFalse(result['scientific_measurement_qualified'])
        self.assert_seal(folder)

    def test_array_guard_fails_before_audio_or_telemetry_and_preserves_failure(self):
        folder, result, control, telemetry, expected, audio, logger = self.run_pipeline(wrong_array=True)
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.assertIn('array selection', result['error'])
        audio.assert_not_called()
        logger.assert_not_called()
        self.assertEqual(control.state, control.original_state)
        self.assertEqual(control.pins, control.original_pins)
        self.assertFalse((folder / 'native_packed.wav').exists())
        self.assert_seal(folder)

    def test_external_reference_must_pass_and_bracket_the_xvf_host_interval(self):
        receipt={'status':'PASS','stream_closed':True,'frames':300000,'start_monotonic_ns':0,'end_monotonic_ns':10_000_000_000}
        folder,result,*_=self.run_pipeline(external_reference=receipt)
        self.assertEqual(result['status'],'PASS')
        self.assertTrue(result['checks']['reference_capture'])
        self.assertTrue(result['checks']['reference_host_interval_coverage'])
        self.assertFalse(result['quality']['reference']['sample_synchronized_with_xvf'])
        self.assertTrue((folder/'reference_result.json').is_file())

    def test_v3_fixed_gain_delay_is_read_back_and_never_written(self):
        folder,result,control,*_=self.run_pipeline('amplified',schema_version=3,mic_gain=10)
        self.assertEqual(result['status'],'PASS')
        self.assertTrue((folder/'capture_gain_delay_lock.json').is_file())
        self.assertTrue((folder/'gain_delay_after_capture.json').is_file())
        self.assertIn('read AUDIO_MGR_MIC_GAIN',control.operations)
        self.assertIn('read AUDIO_MGR_SYS_DELAY',control.operations)
        self.assertNotIn('write AUDIO_MGR_MIC_GAIN',control.operations)
        self.assertNotIn('write AUDIO_MGR_SYS_DELAY',control.operations)
        self.assert_seal(folder)

    def test_v3_gain_mismatch_blocks_before_recording_without_retuning(self):
        folder,result,control,telem,expected,audio,logger=self.run_pipeline('amplified',schema_version=3,mic_gain=4)
        self.assertEqual(result['status'],'INVESTIGATE')
        self.assertIn('gain/delay changed',result['error'])
        audio.assert_not_called();logger.assert_not_called()
        self.assertEqual(control.operations,['identify'])
        self.assertEqual(control.state['AUDIO_MGR_MIC_GAIN'],[4])
        self.assert_seal(folder)

    def test_v3_post_capture_gain_mismatch_cannot_pass(self):
        folder,result,control,*_=self.run_pipeline('amplified',schema_version=3,mic_gain=10,changed_gain=5)
        self.assertEqual(result['status'],'INVESTIGATE')
        self.assertFalse(result['capture_integrity_pass'])
        self.assertIn('changed during capture',result['error'])
        self.assertTrue((folder/'microphones_4ch.wav').is_file())
        self.assertEqual(control.state['AUDIO_MGR_MIC_GAIN'],[5])
        self.assert_seal(folder)

    def test_external_reference_failure_is_not_hidden_by_good_xvf_data(self):
        receipt={'status':'FAIL','stream_closed':True,'start_monotonic_ns':0,'end_monotonic_ns':10_000_000_000}
        folder,result,control,*_=self.run_pipeline(external_reference=receipt)
        self.assertEqual(result['status'],'INVESTIGATE')
        self.assertTrue(result['checks']['known_sequence'])
        self.assertFalse(result['checks']['reference_capture'])
        self.assertEqual(control.state,control.original_state)
        self.assert_seal(folder)

    def test_reference_interval_gap_is_not_a_successful_reference_capture(self):
        receipt={'status':'PASS','stream_closed':True,'start_monotonic_ns':0,'end_monotonic_ns':2_000_000_000}
        folder,result,*_=self.run_pipeline(external_reference=receipt)
        self.assertEqual(result['status'],'INVESTIGATE')
        self.assertFalse(result['checks']['reference_host_interval_coverage'])

    def test_unclosed_external_reference_prevents_control_and_freeze(self):
        receipt={'status':'FAIL','stream_closed':False,'start_monotonic_ns':0,'end_monotonic_ns':10_000_000_000}
        folder,result,*_=self.run_pipeline(external_reference=receipt)
        self.assertTrue(result['hardware_logger_still_active'])
        self.assertFalse((folder/'SHA256SUMS.txt').exists())
        self.assertNotIn('Control after an unclosed',str(result['error']))

    def test_unclosed_telemetry_blocks_followup_control_and_sealing(self):
        folder, result, control, telemetry, expected, audio, logger = self.run_pipeline(telemetry_closes=False)
        self.assertTrue(result['hardware_logger_still_active'])
        self.assertFalse(result['capture_integrity_pass'])
        self.assertNotEqual(result['status'], 'PASS')
        self.assertFalse((folder / 'SHA256SUMS.txt').exists())
        self.assertTrue((folder / 'native_packed.wav').exists())
        self.assertIn('did not stop', result['error'])
        self.assertNotIn('Control after an unclosed', result['error'])


if __name__ == '__main__':
    unittest.main()
