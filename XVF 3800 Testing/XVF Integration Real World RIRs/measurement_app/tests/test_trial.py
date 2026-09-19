"""Offline v2 metadata, trial reservation, storage and pass-lifetime regressions.

Only temporary fixture files are created. Device control, inventory and audio
capture are replaced; no production take is modified or acquired by these tests.
"""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from measurement_app import acquisition, core, trial
import numpy as np


def setup_fixture():
    return {
        'room_name': 'Living room', 'position_name': 'Front seat',
        'source': {'distance_to_array_m': 1.2, 'azimuth_lab_deg': 0},
        'device': {'orientation': 'FLAT'},
        'obstruction': {'present': False, 'notes': None},
        'clutter_state': 'unknown',
    }


def request_fixture(mode='measure', domain='raw'):
    return {'schema_version': 2, 'mode': mode, 'domain': domain,
            'duration_seconds': 5, 'playback_gain_db': -18, 'reference': {'enabled': False},
            'playback_channel': 'left', 'excitation_id': 'offline-fixture',
            'playback_device_index': 14, 'setup': setup_fixture()}


def file_snapshot(folder):
    return {str(path.relative_to(folder)): core.sha(path)
            for path in folder.rglob('*') if path.is_file()}


class SetupValidationTests(unittest.TestCase):
    def test_krk_hardware_and_optional_reference_metadata_survive_validation_and_storage(self):
        req=request_fixture()
        req['setup'].update(hardware_context={'revision':'krk-emm6-2026-09-06','primary_rir_channels':['MIC0','MIC1','MIC2','MIC3']},
            speaker={'model_user_reported':'KRK GoAux 4','connection':'wired','arc_state_user_reported':'off',
                     'eq_lf':'flat','eq_hf':'flat','interface_output_level_user_note':'interface mark 0','orientation_user_note':'fixed arrow'},
            calibration={'reference_optional':True,'source_correction_applied':False,'reference_record':None})
        before=copy.deepcopy(req['setup'])
        with tempfile.TemporaryDirectory() as temp:
            folder=trial.reserve_trial(req,Path(temp))
            stored=json.loads((folder/'request.json').read_text())['setup']
        for name in ['speaker','calibration','hardware_context']:self.assertEqual(stored[name],before[name])
        self.assertFalse(req['reference']['enabled'])

    def test_krk_campaign_rejects_bluetooth_before_inventory(self):
        req=request_fixture();req['schema_version']=3
        req['setup'].update(hardware_context={'revision':'krk-emm6-2026-09-06'},speaker={'connection':'bluetooth'})
        with patch.object(acquisition,'devices',side_effect=AssertionError('Inventory forbidden')):
            with self.assertRaisesRegex(ValueError,'wired'):acquisition.validate_request(req)

    def test_krk_campaign_rejects_named_bluetooth_endpoint_even_if_setup_says_wired(self):
        req=request_fixture();req['schema_version']=3
        req['setup'].update(hardware_context={'revision':'krk-emm6-2026-09-06'},speaker={'connection':'wired'})
        endpoint={'index':14,'name':'Bluetooth speaker','hostapi_name':'Windows WASAPI','max_output_channels':2}
        with patch.object(acquisition,'devices',return_value=[endpoint]),patch.object(acquisition,'get_excitation',return_value={}):
            with self.assertRaisesRegex(ValueError,'Bluetooth'):acquisition.validate_request(req)

    def test_required_geometry_keeps_zero_and_signed_angle_without_input_mutation(self):
        for angle in (0, -180, 180, -37.5):
            value = setup_fixture()
            value['source']['azimuth_lab_deg'] = angle
            before = copy.deepcopy(value)
            normalized = trial.validate_setup(value, required=True)
            self.assertEqual(normalized['source']['azimuth_lab_deg'], angle)
            self.assertEqual(normalized['source']['distance_to_array_m'], 1.2)
            self.assertEqual(value, before)

    def test_missing_required_values_rejected_instead_of_becoming_defaults(self):
        for field in ('room_name', 'position_name', 'distance_to_array_m', 'azimuth_lab_deg'):
            for missing in (None, '', '   '):
                value = setup_fixture()
                target = value['source'] if field in value['source'] else value
                target[field] = missing
                with self.subTest(field=field, value=missing), self.assertRaises((ValueError, TypeError)):
                    trial.validate_setup(value, required=True)

    def test_nonphysical_and_nonfinite_geometry_rejected(self):
        invalid = [('distance_to_array_m', v) for v in (0, -1, True, float('nan'), float('inf'))]
        invalid += [('azimuth_lab_deg', v) for v in (True, -180.01, 180.01, float('nan'), float('-inf'))]
        for field, bad in invalid:
            value = setup_fixture()
            value['source'][field] = bad
            with self.subTest(field=field, value=bad), self.assertRaises((ValueError, TypeError)):
                trial.validate_setup(value, required=True)

    def test_obstruction_and_pose_are_independent(self):
        value = setup_fixture()
        value['obstruction'] = {'present': True, 'notes': 'Object between source and array'}
        blocked = trial.validate_setup(value, required=True)
        self.assertEqual(blocked['device']['orientation'], 'FLAT')
        self.assertTrue(blocked['obstruction']['present'])
        self.assertEqual(blocked['clutter_state'], 'unknown')
        self.assertIn('Object', blocked['obstruction']['notes'])

    def test_measure_validation_happens_before_inventory(self):
        invalid = request_fixture()
        invalid['setup']['room_name'] = None
        with patch.object(acquisition, 'devices', side_effect=AssertionError('Inventory forbidden')), \
             patch.object(acquisition, 'get_excitation', side_effect=AssertionError('Excitation work forbidden')):
            with self.assertRaises((ValueError, TypeError)):
                acquisition.validate_request(invalid, require_metadata=True)


class TemporaryTrialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='xvf_trial_offline_')
        self.runs = Path(self.temporary.name) / 'runs'
        self.runs.mkdir()
        self.addCleanup(self.temporary.cleanup)


class ReservationTests(TemporaryTrialTests):
    def test_named_record_without_pose_keeps_unknown_condition_and_geometry(self):
        req = request_fixture(mode='record')
        req['setup'] = {'room_name': 'Living room', 'position_name': 'Front seat'}
        folder = trial.reserve_trial(req, self.runs)
        self.assertEqual(folder.name, 'JPXVF_P1_R01_T01_D01_S01_UNK_NAT_CU_R01')
        metadata = json.loads((folder / '00_admin' / 'trial_metadata.json').read_text())
        self.assertNotIn(metadata['setup']['device'].get('orientation'), ('FLAT', 'UPRIGHT'))
        self.assertIsNone(metadata['setup']['source']['distance_to_array_m'])
        self.assertIsNone(metadata['setup']['source']['azimuth_lab_deg'])
        self.assertIsNone(metadata['setup']['obstruction'].get('present'))

    def test_canonical_id_keeps_geometry_in_metadata_and_unknown_clutter_unknown(self):
        req = request_fixture()
        folder = trial.reserve_trial(req, self.runs)
        self.assertEqual(folder.name, 'JPXVF_P1_R01_T01_D01_S01_F00_NAT_CU_R01')
        self.assertTrue(folder.is_dir())
        self.assertTrue((folder / 'request.json').is_file())
        self.assertTrue((folder / '00_admin' / 'trial_metadata.json').is_file())
        saved = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['setup']['source']['distance_to_array_m'], 1.2)
        self.assertEqual(saved['setup']['source']['azimuth_lab_deg'], 0)
        self.assertEqual(saved['setup']['clutter_state'], 'unknown')
        self.assertNotIn('1.2', folder.name)

    def test_room_position_registry_and_planned_repeat_are_stable(self):
        first = trial.reserve_trial(request_fixture(), self.runs)
        changed_geometry = request_fixture()
        changed_geometry['setup']['source'].update(distance_to_array_m=1.3, azimuth_lab_deg=2)
        second = trial.reserve_trial(changed_geometry, self.runs)
        self.assertEqual(second.name, first.name[:-3] + 'R02')
        different_position = request_fixture()
        different_position['setup']['position_name'] = 'Rear seat'
        third = trial.reserve_trial(different_position, self.runs)
        self.assertIn('_R01_T01_D01_S02_', third.name)
        self.assertTrue(third.name.endswith('_R01'))
        different_room = request_fixture()
        different_room['setup']['room_name'] = 'Kitchen'
        fourth = trial.reserve_trial(different_room, self.runs)
        self.assertIn('_R02_T01_D01_S01_', fourth.name)

    def test_pose_and_obstruction_generate_independent_condition_tokens(self):
        flat_blocked = request_fixture()
        flat_blocked['setup']['obstruction']['present'] = True
        blocked_folder = trial.reserve_trial(flat_blocked, self.runs)
        upright_clear = request_fixture()
        upright_clear['setup']['device']['orientation'] = 'UPRIGHT'
        upright_clear['setup']['clutter_state'] = 'clear'
        clear_folder = trial.reserve_trial(upright_clear, self.runs)
        self.assertIn('_F00_NAT_C2_', blocked_folder.name)
        self.assertIn('_UPR_NAT_C0_', clear_folder.name)
        metadata = json.loads((clear_folder / '00_admin' / 'trial_metadata.json').read_text())
        self.assertFalse(metadata['setup']['obstruction']['present'])
        self.assertEqual(metadata['setup']['source']['azimuth_lab_deg'], 0)

    def test_fault_retake_preserves_planned_repeat_and_prior_files(self):
        req = request_fixture()
        original = trial.reserve_trial(req, self.runs)
        (original / '02_raw').mkdir(exist_ok=True)
        (original / '02_raw' / 'fixture.raw').write_bytes(b'original evidence')
        core.freeze(original)
        before = file_snapshot(original)
        retake_request = request_fixture()
        retake_request['retake_of'] = original.name
        retry = trial.reserve_trial(retake_request, self.runs)
        self.assertEqual(retry.name, original.name + '__TAKE02')
        self.assertEqual(before, file_snapshot(original))
        self.assertEqual(trial.reserve_trial(request_fixture(), self.runs).name, original.name[:-3] + 'R02')

    def test_retakes_cannot_target_an_outside_path(self):
        for invalid in ('../outside', '..\\outside', 'C:\\outside', 'missing_canonical_id'):
            request = request_fixture()
            request['retake_of'] = invalid
            before = file_snapshot(self.runs)
            with self.subTest(retake=invalid), self.assertRaises((ValueError, FileNotFoundError)):
                trial.reserve_trial(request, self.runs)
            self.assertEqual(before, file_snapshot(self.runs))

    def test_parallel_reservation_never_reuses_or_overwrites_a_folder(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            folders = list(pool.map(lambda _: trial.reserve_trial(request_fixture(), self.runs), range(2)))
        self.assertEqual(len(set(folders)), 2)
        # Production calls run under the inter-process device lease. This direct
        # out-of-contract race checks the last-resort exclusive mkdir guarantee,
        # not deterministic planned-repeat allocation without that lease.
        for folder in folders:
            self.assertTrue((folder / 'request.json').is_file())
            metadata = json.loads((folder / '00_admin' / 'trial_metadata.json').read_text())
            self.assertEqual(metadata['run_id'], folder.name)

    def test_frozen_legacy_take_remains_byte_for_byte_unchanged(self):
        legacy = self.runs / 'TAKE_20260905T223303_130671Z_fixture'
        legacy.mkdir()
        core.write_json(legacy / 'request.json', {'mode': 'record', 'setup': {'distance_m': None}})
        core.write_json(legacy / 'result.json', {'status': 'RETAKE'})
        core.freeze(legacy)
        before = file_snapshot(legacy)
        trial.reserve_trial(request_fixture(), self.runs)
        self.assertEqual(before, file_snapshot(legacy))


class AggregationTests(TemporaryTrialTests):
    def fake_capture(self, outcomes, stop_after=None):
        self.calls = []

        def capture(req, folder, stop, update):
            index = len(self.calls)
            self.calls.append((copy.deepcopy(req), Path(folder)))
            folder = Path(folder)
            folder.mkdir(parents=True, exist_ok=False)
            status = outcomes[index]
            good = status in ('PASS', 'REVIEW')
            result = {
                'run_id': folder.name, 'status': status,
                'capture_integrity_pass': good or status == 'RETAKE',
                'scientific_measurement_qualified': False,
                'checks': {'known_sequence': True, 'playback': good or status == 'RETAKE'},
                'error': 'fixture capture failure' if status == 'INVESTIGATE' else None,
                'message': 'Offline capture fixture', 'stopped': False,
                'acoustic_marker_review': 'RETAKE' if status == 'RETAKE' else 'REVIEW',
                'hardware_logger_still_active': False,
                'quality': {'acoustic_markers': {'status': 'RETAKE' if status == 'RETAKE' else 'REVIEW'}},
            }
            core.write_json(folder / 'request.json', req)
            core.write_json(folder / 'result.json', result)
            core.write_json(folder / 'quality.json', result['quality'])
            (folder / 'REPORT.txt').write_text('Offline report', encoding='utf-8')
            (folder / 'source').mkdir()
            (folder / 'source' / 'core.py').write_text('# Offline decoder identity fixture\n', encoding='utf-8')
            core.save_counts(folder / 'native_packed.wav', np.zeros((6, 2), np.int32), 48000, 24)
            core.save_counts(folder / 'microphones_4ch.wav', np.ones((2, 4), np.int32) * 12, 16000, 24)
            for mic in range(4):
                core.save_counts(folder / f'MIC{mic}.wav', np.ones((2, 1), np.int32) * (mic + 1) * 2, 16000, 24)
            core.freeze(folder)
            if stop_after == index:
                stop.set()
            return result

        return capture

    def run_trial(self, outcomes, mode='measure', domain='both', stop_after=None):
        req = request_fixture(mode, domain)
        folder = trial.reserve_trial(req, self.runs)
        capture = self.fake_capture(outcomes, stop_after)
        result = trial.acquire_trial(req, folder, threading.Event(), lambda **kw: None, capture=capture)
        return folder, result

    def test_both_domains_are_two_ordered_passes_with_separate_evidence(self):
        folder, result = self.run_trial(['REVIEW', 'REVIEW'])
        self.assertEqual([req['domain'] for req, _ in self.calls], ['raw', 'amplified'])
        self.assertEqual([path.relative_to(folder).as_posix() for _, path in self.calls],
                         ['02_raw/pass_01_raw', '02_raw/pass_02_amplified'])
        self.assertEqual(result['status'], 'REVIEW')
        self.assertTrue(result['capture_integrity_pass'])
        self.assertFalse(result['scientific_measurement_qualified'])
        self.assertTrue((folder / '03_derived').is_dir())
        self.assertTrue((folder / '00_admin' / 'trial_metadata.json').is_file())
        for _, source in self.calls:
            derived = folder / '03_derived' / source.name
            provenance = json.loads((derived / 'provenance.json').read_text())
            self.assertEqual(provenance['processing_contract_version'], 2)
            self.assertEqual(provenance['native_packed_sha256'], core.sha(source / 'native_packed.wav'))
            self.assertEqual(provenance['source_code_sha256']['core.py'], core.sha(source / 'source' / 'core.py'))
            self.assertEqual({row['derived'] for row in provenance['files']},
                             {'MIC0.wav', 'MIC1.wav', 'MIC2.wav', 'MIC3.wav', 'qc_summary.json'})
            for row in provenance['files']:
                self.assertEqual(core.sha(folder / row['source']), row['source_sha256'])
                self.assertEqual(core.sha(derived / row['derived']), row['derived_sha256'])
                self.assertEqual(row['source_sha256'], row['derived_sha256'])

    def test_single_domain_never_runs_an_unrequested_second_pass(self):
        for domain in ('raw', 'amplified'):
            folder, result = self.run_trial(['PASS'], mode='record', domain=domain)
            self.assertEqual([req['domain'] for req, _ in self.calls], [domain])
            self.assertEqual(result['status'], 'PASS')
            self.assertTrue(result['capture_integrity_pass'])

    def test_first_marker_failure_or_capture_failure_prevents_second_pass(self):
        for failure in ('RETAKE', 'INVESTIGATE'):
            folder, result = self.run_trial([failure])
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(result['status'], failure)
            self.assertFalse(result['capture_integrity_pass'])
            self.assertFalse((folder / '02_raw' / 'pass_02_amplified').exists())

    def test_second_pass_failure_cannot_be_hidden_by_first_pass_success(self):
        folder, result = self.run_trial(['REVIEW', 'INVESTIGATE'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.assertFalse(result['capture_integrity_pass'])
        first = json.loads((folder / '02_raw' / 'pass_01_raw' / 'result.json').read_text())
        self.assertEqual(first['status'], 'REVIEW')

    def test_stop_between_passes_retains_first_pass_and_skips_second(self):
        folder, result = self.run_trial(['REVIEW'], stop_after=0)
        self.assertEqual(len(self.calls), 1)
        self.assertNotEqual(result['status'], 'PASS')
        self.assertFalse(result['capture_integrity_pass'])
        self.assertFalse((folder / '02_raw' / 'pass_02_amplified').exists())

    def test_active_child_writer_prevents_next_pass_and_trial_seal(self):
        req = request_fixture(domain='both')
        folder = trial.reserve_trial(req, self.runs)
        calls = []
        def capture(request, target, stop, update):
            calls.append(target)
            Path(target).mkdir(parents=True)
            return {'status': 'INVESTIGATE', 'capture_integrity_pass': False,
                    'hardware_logger_still_active': True, 'message': 'Writer still active'}
        result = trial.acquire_trial(req, folder, threading.Event(), lambda **kw: None, capture=capture)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['status'], 'INVESTIGATE')
        self.assertTrue(result['hardware_logger_still_active'])
        self.assertFalse((folder / 'SHA256SUMS.txt').exists())
        self.assertFalse((folder / '02_raw' / 'pass_02_amplified').exists())

    def test_frozen_trial_cannot_be_reacquired_or_modified(self):
        req = request_fixture()
        folder = trial.reserve_trial(req, self.runs)
        core.freeze(folder)
        before = file_snapshot(folder)
        capture = Mock(side_effect=AssertionError('Cannot capture into a frozen trial'))
        with self.assertRaises(FileExistsError):
            trial.acquire_trial(req, folder, threading.Event(), lambda **kw: None, capture=capture)
        capture.assert_not_called()
        self.assertEqual(before, file_snapshot(folder))


class WriterLivenessTests(unittest.TestCase):
    def test_lingering_playback_prevents_control_restoration_and_freeze(self):
        after_capture = [False]
        control = Mock()
        control.identify.return_value = {'USB_BIT_DEPTH': [24, 24], 'AUDIO_MGR_MIC_GAIN': [4], 'AUDIO_MGR_SYS_DELAY': [-32]}
        values = {'AUDIO_MGR_OP_ALL': [0] * 12, 'AUDIO_MGR_OP_PACKED': [0, 0],
                  'AUDIO_MGR_OP_UPSAMPLE': [1, 1], 'GPO_PORT_PIN_INDEX': [0, 4],
                  'GPO_PIN_ACTIVE_LEVEL': [1], 'GPO_PIN_PWM_DUTY': [0],
                  'GPO_PIN_FLASH_MASK': [4294967295]}
        def read(name):
            if after_capture[0]:
                self.fail('Control called after capture while playback is still alive')
            return values[name]
        def command(*args):
            if after_capture[0]:
                self.fail('Control called after capture while playback is still alive')
            return ''
        control.values.side_effect = read
        control.query.side_effect = command
        control.set.side_effect = command
        telemetry = Mock()
        telemetry.start.return_value = telemetry
        telemetry.latest = {field: {} for field in acquisition.DEFAULT_FIELDS}
        telemetry.wait.return_value = {'status': 'PASS'}
        playback_thread = Mock()
        playback_thread.is_alive.return_value = True
        def capture(seconds, bits, payload, stop, on_started, progress):
            on_started()
            after_capture[0] = True
            raise RuntimeError('Simulated capture failure with stalled playback thread')
        with tempfile.TemporaryDirectory(prefix='xvf_writer_offline_') as tmp, \
             patch.object(acquisition, 'validate_request', side_effect=lambda value: value), \
             patch.object(acquisition, 'Control', return_value=control), \
             patch.object(acquisition, 'get_excitation', return_value={'id': 'fixture', 'path': 'fixture.wav'}), \
             patch.object(acquisition.sf, 'read', return_value=(np.zeros(480, np.float64), 48000)), \
             patch.object(acquisition.shutil, 'copy2'), patch.object(acquisition, 'save_counts'), \
             patch.object(acquisition, 'xvf_endpoints', return_value=({'index': 34}, {'index': 33})), \
             patch.object(acquisition, 'create_telemetry_logger', return_value=telemetry), \
             patch.object(acquisition.threading, 'Thread', return_value=playback_thread), \
             patch.object(acquisition, 'capture_native', side_effect=capture), \
             patch.object(acquisition, 'freeze') as freeze:
            result = acquisition.acquire(request_fixture(), Path(tmp) / 'owned', threading.Event(), lambda **kw: None)
            self.assertTrue(result['hardware_logger_still_active'])
            self.assertFalse(result['capture_integrity_pass'])
            freeze.assert_not_called()
            self.assertTrue(after_capture[0])


if __name__ == '__main__':
    unittest.main()
