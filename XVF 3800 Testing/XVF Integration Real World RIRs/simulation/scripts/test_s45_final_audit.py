"""Temporary metadata fixtures only; README_S45_FINAL_AUDIT.md."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import s45_final_audit as a


def closed():
    return {
        'supervisor_postpackage_receipt.json': {'status': 'SUPERVISOR_CLOSED', 'ended_utc': '2026-09-09T10:00:00Z'},
        'owned_process.json': {'pid': None, 'closed_utc': '2026-09-09T09:00:00Z'},
        'supervisor_process.json': {'pid': None, 'closed_utc': '2026-09-09T10:00:00Z'},
        'UNRESOLVED_SUPERVISOR_CHILD.json': None,
        'keep_awake.json': {'active': False, 'prior_state_restored': True, 'released_utc': '2026-09-09T09:00:00Z'},
        'supervisor_keep_awake.json': {'active': False, 'prior_state_restored': True, 'released_utc': '2026-09-09T10:00:00Z'},
    }


class ClosureTests(unittest.TestCase):
    def errors(self, markers=None, processes=None, ledger=None, jobs=None):
        return a.closure_errors(closed() if markers is None else markers,
            {'query_succeeded': True, 'processes': processes or []}, ledger or {'passes': []}, jobs or [])

    def test_closed_receipts_are_sufficient_for_receipt_gate_only(self):
        self.assertEqual(self.errors(), [])

    def test_live_supervisor_refuses_pass_despite_closed_receipts(self):
        self.assertTrue(self.errors(processes=[{'ProcessId': 10, 'CommandLine': 'python C:/scripts/s45_execute.py'}]))
        self.assertTrue(self.errors(processes=[{'ProcessId': 11, 'CommandLine': 'python C:/scripts/s45_execute_v2.py'}]))

    def test_related_model_and_native_telemetry_are_live_owners(self):
        for command in ('python -m app.edge_speech_pipeline file G:/Just_Peachy_S4_5/20260909T031300Z/h2/a.wav',
                        'powershell -File Run-S4-Telemetry.ps1 -OutputDirectory G:/Just_Peachy_S4_5/20260909T031300Z/hardware/a'):
            self.assertTrue(self.errors(processes=[{'ProcessId': 12, 'CommandLine': command}]))
        self.assertEqual(self.errors(processes=[{'ProcessId': 12, 'CommandLine': 'python unrelated_user_job.py'}]), [])

    def test_missing_query_or_unknown_recorded_pid_is_not_absence(self):
        self.assertTrue(a.closure_errors(closed(), {'query_succeeded': False}, {'passes': []}, []))
        self.assertTrue(self.errors(processes=[{'ProcessId': 13, 'CommandLine': None}]))

    def test_missing_or_uncleared_owner_and_missing_postreceipt_fail(self):
        for name in ('owned_process.json', 'supervisor_process.json'):
            m = closed(); m[name]['pid'] = 99
            self.assertTrue(self.errors(m))
            m[name] = None
            self.assertTrue(self.errors(m))
        m = closed(); m['supervisor_postpackage_receipt.json'] = None
        self.assertTrue(self.errors(m))

    def test_unresolved_marker_blocks_even_with_no_live_pid(self):
        m = closed(); m['UNRESOLVED_SUPERVISOR_CHILD.json'] = {'pid': 99, 'status': 'UNVERIFIED_ACTIVE_CHILD'}
        self.assertTrue(self.errors(m))

    def test_keepawake_missing_or_active_cannot_be_inferred_released(self):
        for name in ('keep_awake.json', 'supervisor_keep_awake.json'):
            m = closed(); m[name] = None
            self.assertTrue(self.errors(m))
            m = closed(); m[name]['active'] = True
            self.assertTrue(self.errors(m))

    def test_unresolved_attempt_or_model_record_blocks(self):
        self.assertTrue(self.errors(ledger={'passes': [{'status': 'STARTED'}]}))
        self.assertTrue(self.errors(jobs=[{'status': 'STARTED', 'case_id': 'S45_01_01', 'stream': 'O0'}]))
        self.assertEqual(self.errors(jobs=[{'status': 'QUARANTINED'}]), [])

    def test_audit_early_gate_does_not_run_conservation_disk_or_git(self):
        class FakeEvidence:
            bindings = {}
            absent = []
            def load(self, path, expected=None, optional=False):
                return {'passes': []} if Path(path).name == 'physical_ledger.json' else None
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(a, 'REPORT', Path(temp)), patch.object(a, 'HARDWARE', Path(temp) / 'hardware'), \
                 patch.object(a, 'Evidence', FakeEvidence), patch.object(a, 'process_snapshot', return_value={'query_succeeded': True, 'processes': []}), \
                 patch.object(a, 'conservation', side_effect=AssertionError('must not run')) as conservation, \
                 patch.object(a, 'ssd_and_space', side_effect=AssertionError('must not run')) as disk, \
                 patch.object(a, 'git_and_h2_sources', side_effect=AssertionError('must not run')) as git:
                result = a.audit()
                self.assertEqual(result['status'], 'BLOCKED_OR_FAILED')
                self.assertTrue(result['errors'])
                conservation.assert_not_called(); disk.assert_not_called(); git.assert_not_called()
                self.assertFalse(any(Path(temp).iterdir()))


class RestorationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.initial = {'settings': {'PP_AGCGAIN': [84.72903]}, 'identity': {'I2S_INPUT_PACKED': [0], 'USB_BIT_DEPTH': [16]}, 'observe_only': {'foo': [1]}, 'usb_bits': [16]}
        self.receipt = {'status': 'PASS', 'exact_recorded_configuration_match': True, 'hardware_lease_released': True,
                        'audio_handles_closed': True, 'telemetry_process_closed': True, 'packed_input_disabled': True,
                        'readback': {k: copy.deepcopy(self.initial[k]) for k in ('settings', 'identity', 'observe_only')}}
        self.write('initial_state.json', self.initial)
        self.write('restoration.json', self.receipt)

    def write(self, name, value):
        (self.folder / name).write_text(json.dumps(value), encoding='utf-8')

    def test_exact_receipt_passes_but_one_decimal_difference_fails(self):
        self.assertEqual(a.verify_restoration(self.folder, a.Evidence())['status'], 'PASS')
        self.receipt['readback']['settings']['PP_AGCGAIN'] = [84.72902]
        self.write('restoration.json', self.receipt)
        with self.assertRaisesRegex(ValueError, 'Exact initial'):
            a.verify_restoration(self.folder, a.Evidence())

    def test_bare_pass_missing_release_or_wrong_usb_fails(self):
        self.receipt['hardware_lease_released'] = False
        self.write('restoration.json', self.receipt)
        with self.assertRaises(ValueError): a.verify_restoration(self.folder, a.Evidence())
        self.receipt['hardware_lease_released'] = True
        self.initial['usb_bits'] = [24]
        self.write('initial_state.json', self.initial)
        self.write('restoration.json', self.receipt)
        with self.assertRaisesRegex(ValueError, 'USB width'): a.verify_restoration(self.folder, a.Evidence())

    def test_bound_recovery_keeps_original_and_rejects_foreign_binding(self):
        failed = {'status': 'FAIL', 'error': 'preserved original failure'}
        self.write('restoration.json', failed)
        self.receipt.update(original_failure=failed, original_failure_binding=a.digest(self.folder / 'restoration.json'))
        self.write('restoration_recovery.json', self.receipt)
        before = (self.folder / 'restoration.json').read_bytes()
        result = a.verify_restoration(self.folder, a.Evidence())
        self.assertTrue(result['recovery_used'])
        self.assertEqual(before, (self.folder / 'restoration.json').read_bytes())
        self.receipt['original_failure_binding']['path'] = str(self.folder / 'foreign.json')
        self.write('restoration_recovery.json', self.receipt)
        with self.assertRaisesRegex(ValueError, 'points elsewhere'): a.verify_restoration(self.folder, a.Evidence())

    def test_changed_evidence_cannot_be_rebound_silently(self):
        e = a.Evidence(); p = self.folder / 'restoration.json'; e.bind(p)
        self.receipt['extra'] = 'changed'; self.write('restoration.json', self.receipt)
        with self.assertRaisesRegex(ValueError, 'Evidence changed'): e.bind(p)


class BudgetTests(unittest.TestCase):
    def test_diagnostics_references_failed_passes_remain_charged(self):
        ledger = {'passes': [
            {'batch': 'a', 'case_id': 'transport_regression', 'status': 'PASS', 'charged_playback_s': 8},
            {'batch': 'b', 'case_id': 'S45_01_01', 'status': 'FAIL', 'charged_playback_s': 30},
            {'batch': 'c', 'case_id': 'S45_01_01', 'status': 'PASS', 'charged_playback_s': 30},
            {'batch': 'd', 'case_id': 'S45_REF_01', 'status': 'PASS', 'charged_playback_s': 20},
        ]}
        result = a.physical_summary(ledger)
        self.assertEqual(result['charged_active_playback_s'], 88)
        self.assertEqual(result['groups']['canonical']['passes'], 2)
        self.assertEqual(result['passes_missing_captured_frame_count'], 4)
        ledger['passes'].append({'batch': 'e', 'case_id': 'S45_01_01', 'status': 'PASS', 'charged_playback_s': 30})
        with self.assertRaisesRegex(ValueError, 'attempt budget'): a.physical_summary(ledger)

    def test_invalid_or_duplicate_charges_fail(self):
        row = {'batch': 'a', 'case_id': 'S45_01_01', 'status': 'PASS', 'charged_playback_s': 30}
        with self.assertRaisesRegex(ValueError, 'Duplicate'): a.physical_summary({'passes': [row, row]})
        row['charged_playback_s'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'Invalid'): a.physical_summary({'passes': [row]})


class AcceptanceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.report = self.root / 'report'; self.bank = self.root / 'bank'
        self.folder = self.root / 'hardware/batch_one/S45_01_01'
        for p in (self.report, self.bank, self.folder): p.mkdir(parents=True)
        self.scene = {'case_id': 'S45_01_01', 'split': 'development', 'canonical_audio': {'sha256': 'input_hash'}}
        self.manifest = {'scenes': [self.scene]}
        self.write(self.bank / 'SCENE_MANIFEST.json', self.manifest)
        self.case = {'case_id': 'S45_01_01', 'batch': 'batch_one', 'split': 'development', 'code_key': 'frozen_code_key',
            'status': 'PASS', 'audio_integrity_status': 'PASS', 'telemetry_status': 'PASS', 'payload': {'status': 'PASS'},
            'final_recipe_capture': True, 'recipe': 'limiter_and_agc_headroom', 'reserve_task_scored': False, 'input_scene_sha256': 'input_hash'}
        self.contract = {'code_key': 'frozen_code_key', 'recipe': 'limiter_and_agc_headroom', 'final_recipe_capture': True,
                         'scene_manifest_sha256': a.digest(self.bank / 'SCENE_MANIFEST.json')['sha256']}
        self.write(self.report / 'OUTPUT_LEVEL_POLICY.json', {'frozen': True, 'hardware_recipe': 'limiter_and_agc_headroom'})

    def write(self, path, obj): path.write_text(json.dumps(obj), encoding='utf-8')

    def evaluate(self):
        self.write(self.folder / 'case_result.json', self.case)
        self.write(self.folder.parent / 'batch_contract.json', self.contract)
        selection = {'case_id': 'S45_01_01', 'folder': str(self.folder), 'case_result': a.digest(self.folder / 'case_result.json'),
            'code_key': 'frozen_code_key', 'split': 'development', 'input_scene_sha256': 'input_hash', 'task_scoring_allowed': True}
        self.write(self.report / 'ACCEPTED_CAPTURES.json', {'accepted': [selection], 'accepted_count': 1, 'pending_count': 0,
            'scene_manifest': a.digest(self.bank / 'SCENE_MANIFEST.json'), 'excluded_from_240': False, 'reserve_task_scored': False})
        ledger = {'passes': [{'case_id': 'S45_01_01', 'batch': 'batch_one', 'status': 'PASS'}]}
        with patch.object(a, 'REPORT', self.report), patch.object(a, 'BANK', self.bank):
            return a.acceptance(a.Evidence(), self.manifest, None, ledger)

    def test_bound_frozen_recipe_and_contract_pass(self):
        self.assertEqual(self.evaluate()['canonical']['accepted'], 1)

    def test_rehashed_wrong_recipe_or_reserve_flag_cannot_pass(self):
        self.case['recipe'] = 'wrong_recipe'
        with self.assertRaisesRegex(ValueError, 'recipe differs'): self.evaluate()
        self.case['recipe'] = 'limiter_and_agc_headroom'; self.case['reserve_task_scored'] = True
        with self.assertRaisesRegex(ValueError, 'reserve task'): self.evaluate()
        del self.case['reserve_task_scored']
        with self.assertRaisesRegex(ValueError, 'reserve task'): self.evaluate()

    def test_hash_valid_but_foreign_batch_contract_cannot_pass(self):
        for key, value in (('scene_manifest_sha256', 'other_manifest'), ('code_key', 'other_code'),
                           ('final_recipe_capture', False), ('recipe', 'other_recipe')):
            with self.subTest(key=key):
                original = self.contract[key]; self.contract[key] = value
                with self.assertRaises(ValueError): self.evaluate()
                self.contract[key] = original


class NativeCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.session = Path(self.temp.name)
        self.summary = {'state': 'COMPLETED', 'telemetry': {'audio_frames_dropped': 0, 'portaudio_input_overflows': 0, 'raw_capture_reserve_failures': 0}}
        (self.session / 'session_summary.json').write_text(json.dumps(self.summary), encoding='utf-8')
        self.journal = self.session / 'native.pcm16'; self.journal.write_bytes(b'\x00\x00\x01\x00')
        self.row = {'case_id': 'S45_01_01', 'stream': 'O0', 'session_dir': str(self.session), 'adapter': {'samples': 2},
                    'session_summary_binding': a.digest(self.session / 'session_summary.json'),
                    'completion_evidence': {'native_summary': True, 'unique_completion_event': True, 'exact_full_pcm16_samples': 2, 'journal': a.digest(self.journal)}}
        self.events(['session_started', 'session_completed'])

    def events(self, names):
        path = self.session / 'events.jsonl'
        path.write_text(''.join(json.dumps({'event_type': n}) + '\n' for n in names), encoding='utf-8')
        self.row['events_binding'] = a.digest(path)

    def evaluate(self): return a.native_completion(a.Evidence(), self.row, self.summary)

    def test_native_full_journal_count_and_zero_counters_pass(self):
        result = self.evaluate()
        self.assertEqual(result['current_PCM16_journal_bytes'], 4)
        self.assertEqual(result['native_event_count'], 2)

    def test_missing_completion_flags_and_adapter_count_fail(self):
        for key in ('native_summary', 'unique_completion_event'):
            self.row['completion_evidence'][key] = False
            with self.assertRaisesRegex(ValueError, 'flags'): self.evaluate()
            self.row['completion_evidence'][key] = True
        self.row['adapter']['samples'] = 3
        with self.assertRaisesRegex(ValueError, 'sample count'): self.evaluate()

    def test_hash_valid_truncated_journal_and_multiple_spools_fail(self):
        self.journal.write_bytes(b'\x00\x00')
        self.row['completion_evidence']['journal'] = a.digest(self.journal)
        with self.assertRaisesRegex(ValueError, 'byte/sample'): self.evaluate()
        self.journal.write_bytes(b'\x00\x00\x01\x00')
        self.row['completion_evidence']['journal'] = a.digest(self.journal)
        (self.session / 'other.pcm16').write_bytes(b'\x00\x00')
        with self.assertRaisesRegex(ValueError, 'exactly one'): self.evaluate()

    def test_failure_stop_duplicate_or_absent_completion_event_fails(self):
        for events in (['session_started'], ['session_completed', 'session_completed'],
                       ['failure', 'session_completed'], ['session_completed', 'session_stopped']):
            with self.subTest(events=events):
                self.events(events)
                with self.assertRaisesRegex(ValueError, 'failure-free completion'): self.evaluate()

    def test_missing_or_nonzero_drop_evidence_fails(self):
        for key in list(self.summary['telemetry']):
            with self.subTest(key=key):
                self.summary['telemetry'][key] = 1
                with self.assertRaisesRegex(ValueError, 'drop counter'): self.evaluate()
                del self.summary['telemetry'][key]
                with self.assertRaisesRegex(ValueError, 'drop counter'): self.evaluate()
                self.summary['telemetry'][key] = 0


class StorageProviderJoinTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'queried_utc': '2026-09-09T10:00:00Z', 'get_disk_query_error': None,
                         'volumes': [], 'physical_disks': [], 'get_disk_records': []}
        for drive, index, model, serial in [('C:', 2, 'WD_BLACK SN850X', 'WD-SERIAL'),
                                             ('G:', 3, 'KINGSTON SNVS2000G', 'KINGSTON-SERIAL')]:
            self.snapshot['volumes'].append({'drive': drive, 'free_bytes': (a.LIMITS[drive[0] + '_free_gib'] + 1) * 2**30,
                'size_bytes': 2_000_000_000_000, 'file_system': 'NTFS',
                'mapping': [{'partition': 'Disk #' + str(index), 'physical_drive': r'\\.\PHYSICALDRIVE' + str(index),
                             'index': index, 'model': model, 'serial_number': serial, 'win32_status': 'OK'}]})
            self.snapshot['physical_disks'].append({'device_id': str(index), 'friendly_name': model,
                'serial_number': serial, 'health_status': 'Healthy', 'operational_status': ['OK'], 'bus_type': 'NVMe'})
        c = self.snapshot['physical_disks'][0]
        self.snapshot['get_disk_records'] = [{**c, 'number': 2, 'operational_status': ['Online']},
                                             {'number': 4, 'friendly_name': 'Unrelated no-media reader',
                                              'serial_number': 'READER', 'health_status': 'Healthy', 'operational_status': ['No Media']}]

    def evaluate(self):
        with patch.object(a, 'powershell_json', return_value=copy.deepcopy(self.snapshot)) as query:
            result = a.ssd_and_space()
            query.assert_called_once()
            return result

    def test_missing_get_disk3_passes_with_exact_physical_health_join(self):
        result = self.evaluate()
        g = next(v for v in result['volumes'] if v['drive'] == 'G:')['mapping'][0]
        self.assertEqual(g['index'], 3)
        self.assertEqual(g['matched_physical_disk']['serial_number'], 'KINGSTON-SERIAL')
        self.assertEqual(g['operational_status'], ['OK'])
        self.assertIsNone(g['get_disk_supplement'])
        self.assertEqual(g['get_disk_supplement_status'], 'NOT_PRESENT_OPTIONAL')
        self.assertEqual(result['provider_join_status'], 'PASS')

    def test_health_join_uses_trimmed_exact_serial_model_not_device_id(self):
        physical = self.snapshot['physical_disks'][1]
        physical.update(device_id='72', serial_number=' KINGSTON-SERIAL ', friendly_name=' KINGSTON SNVS2000G ')
        result = self.evaluate()
        self.assertEqual(result['volumes'][1]['mapping'][0]['matched_physical_disk']['device_id'], '72')
        physical['serial_number'] = 'KINGSTON- SERIAL'
        with self.assertRaisesRegex(ValueError, 'Unique exact serial/model'): self.evaluate()

    def test_missing_serial_or_model_and_unmatched_identity_block(self):
        original = copy.deepcopy(self.snapshot)
        for section, key, value in [('mapping', 'serial_number', ''), ('mapping', 'model', None),
                                     ('physical', 'serial_number', ''), ('physical', 'friendly_name', 'OTHER MODEL'),
                                     ('physical', 'serial_number', 'OTHER SERIAL')]:
            with self.subTest(section=section, key=key, value=value):
                self.snapshot = copy.deepcopy(original)
                row = self.snapshot['volumes'][1]['mapping'][0] if section == 'mapping' else self.snapshot['physical_disks'][1]
                row[key] = value
                with self.assertRaises(ValueError): self.evaluate()

    def test_absent_or_ambiguous_exact_physical_disk_match_blocks(self):
        original = copy.deepcopy(self.snapshot['physical_disks'])
        self.snapshot['physical_disks'] = original[:1]
        with self.assertRaisesRegex(ValueError, 'Unique exact serial/model'): self.evaluate()
        self.snapshot['physical_disks'] = original + [{**original[1], 'device_id': '99'}]
        with self.assertRaisesRegex(ValueError, 'Unique exact serial/model'): self.evaluate()

    def test_missing_unhealthy_or_mixed_operational_health_blocks(self):
        original = copy.deepcopy(self.snapshot)
        for key, value in [('health_status', None), ('health_status', 'Unhealthy'),
                           ('operational_status', []), ('operational_status', ['Lost Communication']),
                           ('operational_status', ['OK', 'Error'])]:
            with self.subTest(key=key, value=value):
                self.snapshot = copy.deepcopy(original); self.snapshot['physical_disks'][1][key] = value
                with self.assertRaisesRegex(ValueError, 'Get-PhysicalDisk health/OK'): self.evaluate()

    def test_optional_get_disk_present_must_have_exact_identity_healthy_online(self):
        disk = {**self.snapshot['physical_disks'][1], 'number': 3, 'operational_status': ['Online']}
        self.snapshot['get_disk_records'].append(disk)
        self.assertEqual(self.evaluate()['volumes'][1]['mapping'][0]['get_disk_supplement_status'], 'PRESENT_IDENTITY_HEALTH_VERIFIED')
        for key, value in [('serial_number', 'OTHER'), ('friendly_name', 'OTHER'), ('serial_number', None),
                           ('health_status', 'Warning'), ('operational_status', ['Offline']), ('operational_status', [])]:
            with self.subTest(key=key, value=value):
                saved = disk[key]; disk[key] = value
                with self.assertRaises(ValueError): self.evaluate()
                disk[key] = saved
        self.snapshot['get_disk_records'].append(copy.deepcopy(disk))
        with self.assertRaisesRegex(ValueError, 'Ambiguous Get-Disk'): self.evaluate()

    def test_optional_get_disk_provider_unavailable_is_explicit_not_inferred_health(self):
        self.snapshot['get_disk_records'] = []
        self.snapshot['get_disk_query_error'] = 'Mock optional provider query unavailable'
        result = self.evaluate()
        self.assertEqual(result['get_disk_query_error'], 'Mock optional provider query unavailable')
        self.assertTrue(all(v['mapping'][0]['get_disk_supplement'] is None for v in result['volumes']))

    def test_existing_win32_kingston_index_mapping_and_free_floors_remain_required(self):
        original = copy.deepcopy(self.snapshot)
        for change in ('index', 'win32_status', 'mapping', 'free_bytes', 'duplicate_volume'):
            with self.subTest(change=change):
                self.snapshot = copy.deepcopy(original); g = self.snapshot['volumes'][1]
                if change == 'index': g['mapping'][0]['index'] = 8
                elif change == 'win32_status': g['mapping'][0]['win32_status'] = 'Error'
                elif change == 'mapping': g['mapping'] = []
                elif change == 'free_bytes': g['free_bytes'] = a.LIMITS['G_free_gib'] * 2**30 - 1
                else: self.snapshot['volumes'].append(copy.deepcopy(g))
                with self.assertRaises(ValueError): self.evaluate()


class ServicePidReuseTests(unittest.TestCase):
    def setUp(self):
        self.row = {'ProcessId': 66428, 'Name': 'svchost.exe', 'CommandLine': None,
                    'CreationDate': '2026-09-09T10:20:21.896334+00:00', 'ServiceQueryError': None,
                    'AssociatedServices': [{'Name': 'gpsvc', 'State': 'Running', 'ProcessId': 66428,
                                            'PathName': r'C:\WINDOWS\system32\svchost.exe -k GPSvcGroup', 'StartName': 'LocalSystem'}]}
        self.job = {'case_id': 'S45_09_05', 'stream': 'O0', 'owned_process_pid': 66428, 'status': 'COMPLETE',
                    'exit_code': 0, 'model_exited_utc': '2026-09-09T09:58:47.797792+00:00',
                    'completed_utc': '2026-09-09T09:58:47.859159+00:00'}
        self.snapshot = {'query_succeeded': True, 'system_root': r'C:\WINDOWS', 'processes': [self.row]}

    def errors(self, jobs=None):
        return a.closure_errors(closed(), self.snapshot, {'passes': []}, [self.job] if jobs is None else jobs)

    def test_strict_reused_service_pid_records_current_and_historical_basis(self):
        self.assertEqual(self.errors(), [])
        proof = self.snapshot['confirmed_reused_service_pids'][0]
        self.assertEqual(proof['status'], 'CONFIRMED_REUSED_SERVICE_PID')
        self.assertEqual(proof['associated_service']['Name'], 'gpsvc')
        self.assertEqual(proof['historical_completed_model_receipts'][0]['model_exited_utc'], self.job['model_exited_utc'])
        self.row['AssociatedServices'][0]['PathName'] = r'"C:\WINDOWS\System32\svchost.exe" -k GPSvcGroup'
        self.assertEqual(self.errors(), [])

    def test_missing_invalid_naive_or_not_later_creation_blocks(self):
        for value in (None, 'not-a-date', '2026-09-09T10:20:21', self.job['completed_utc'], '2026-09-09T09:00:00Z'):
            with self.subTest(value=value):
                self.row['CreationDate'] = value
                self.assertTrue(self.errors())

    def test_every_matching_historical_receipt_must_complete_exit0_before_reuse(self):
        for change in ({'status': 'STARTED'}, {'exit_code': 1}, {'error': 'failure'}, {'model_exited_utc': None},
                       {'completed_utc': None}, {'completed_utc': '2026-09-09T10:30:00Z'},
                       {'model_exited_utc': '2026-09-09T10:00:00Z'}):
            with self.subTest(change=change):
                self.assertTrue(self.errors([self.job, {**self.job, **change}]))
        self.assertTrue(self.errors([]))

    def test_missing_ambiguous_wrong_pid_or_nonrunning_service_blocks(self):
        original = copy.deepcopy(self.row['AssociatedServices'])
        for value in (None, [], original + copy.deepcopy(original), [{**original[0], 'ProcessId': 7}],
                      [{**original[0], 'State': 'Stopped'}], [{**original[0], 'Name': ''}]):
            with self.subTest(value=value):
                self.row['AssociatedServices'] = value
                self.assertTrue(self.errors())
        self.row['AssociatedServices'] = original; self.row['ServiceQueryError'] = 'Access denied'
        self.assertTrue(self.errors())

    def test_wrong_system_executable_or_unknown_process_name_blocks(self):
        for path in (None, r'C:\Temp\svchost.exe -k x', r'C:\WINDOWS\System32\svchost.exe.evil -k x',
                     r'%SystemRoot%\System32\svchost.exe -k x', r'C:\WINDOWS\System32\..\System32\svchost.exe -k x'):
            with self.subTest(path=path):
                self.row['AssociatedServices'][0]['PathName'] = path
                self.assertTrue(self.errors())
        self.row['AssociatedServices'][0]['PathName'] = r'C:\WINDOWS\System32\svchost.exe -k x'
        self.row['Name'] = 'python.exe'; self.assertTrue(self.errors())
        self.row['Name'] = 'svchost.exe'; self.snapshot['system_root'] = None; self.assertTrue(self.errors())

    def test_related_command_never_uses_service_pid_fallback(self):
        self.row['CommandLine'] = 'python s45_h2_run.py'
        self.assertTrue(any('Live S4.5' in error for error in self.errors()))
        self.assertEqual(self.snapshot['confirmed_reused_service_pids'], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
