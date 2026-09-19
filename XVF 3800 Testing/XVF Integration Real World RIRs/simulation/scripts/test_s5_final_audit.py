"""Synthetic/temp-file tests only; never calls the real S5 audit, SSD, processes or models."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

import s5_final_audit as a


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding='utf-8')
    return a.Evidence().bind(path)


def native_fixture(root):
    cid = 'DEV'; scene = {'case_id': cid, 'split': 'development', 'task_scoring_allowed': True,
                         'all_speaker_reference_complete': True}
    payload = root/'payload'; attempt = root/'report/attempt_1'; attempt.mkdir(parents=True)
    data = payload/'attempt_1/empty_data'; session = data/'edge_speech_sessions/test'; session.mkdir(parents=True)
    rawp, adapterp = root/'raw.wav', data.parent/'fixed_gain_input.wav'
    sf.write(rawp, np.array([0, .1, -.2], dtype=np.float32), 16000, subtype='PCM_24')
    raw = sf.read(rawp, dtype='float32')[0]
    adapter = (raw.astype(np.float64)*a.GAINS['O0']).astype(np.float32)
    sf.write(adapterp, adapter, 16000, subtype='FLOAT')
    pcm = np.round(np.clip(adapter, -1, .999969)*32768).astype('<i2')
    spool = session/'audio.pcm16'; spool.write_bytes(pcm.tobytes())
    ev = a.Evidence(); rawb, ab = ev.bind(rawp), ev.bind(adapterp)
    science = {k: i*.1 for i, k in enumerate(a.POLICY_KEYS)}
    science['assets'] = [{'component_id': f'asset{i}', 'sha256': str(i)*64} for i in range(8)]
    cfg = {'baseline': {'python': 'fixture_python.exe'}}
    job = {'case_id': cid, 'stream': 'O0', 'job_key': 'testkey', 'identity': {'fixture': 'identity'},
           'payload_root': str(payload), 'raw_audio': rawb, 'gain': a.GAINS['O0'], 'input_provenance': {'fixture': 'capture'}}
    tele = {'state': 'COMPLETED', 'source_duration_sec': 3/16000, 'asr_cursor_sec': 3/16000, 'speaker_cursor_sec': 3/16000,
            'speaker_analyzed_through_sec': 0, 'speaker_unanalyzed_short_tail_sec': 3/16000,
            'audio_frames_dropped': 0, 'portaudio_input_overflows': 0, 'raw_capture_reserve_failures': 0,
            'elapsed_wall_sec': 1., 'session_dir': str(session)}
    events = [{'event_type': 'session_created', 'source_time_sec': 0, 'payload': {'session_dir': str(session), 'xvf_result_effects_enabled': False}},
              {'event_type': 'session_started', 'source_time_sec': 0, 'payload': {}},
              {'event_type': 'source_started', 'source_time_sec': 0, 'payload': {'mode': 'wav', 'path': str(adapterp), 'channels': 1,
                'native_sample_rate': 16000, 'pipeline_sample_rate': 16000}},
              {'event_type': 'session_completed', 'source_time_sec': 3/16000, 'payload': {'telemetry': dict(tele)}}]
    summary = {'schema_version': 'edge-speech-session.v1', 'state': 'COMPLETED', 'telemetry': {**tele, 'elapsed_wall_sec': 1.1},
               'assets': science['assets'], 'scientific_policy': {k: science[k] for k in a.POLICY_KEYS}, 'xvf': {'result_effects_enabled': False}}
    speaker = {'emitted_final_labels': [], 'decision_label_counts': {}, 'decision_label_switches': 0, 'embedding_calls_successful': 0,
               'embedding_calls_rejected': None, 'reconciled_labels': None, 'naming_accuracy': None,
               'reconciliation_status': 'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE'}
    metrics = {'case_id': cid, 'stream': 'O0', 'fixed_host_gain': job['gain'], 'state': 'COMPLETED',
               'event_counts': dict(Counter(e['event_type'] for e in events)), 'telemetry': summary['telemetry'],
               'scientific_policy': summary['scientific_policy'], 'final_transcripts': [], 'failure_events': [],
               'speaker': speaker, 'reference_scope': {'reserve_task_scored': False, 'all_speaker_reference_complete': True}}
    native = {'schema': 'jp_s5_native_attempt_v1', 'status': 'COMPLETE', 'exit_code': 0, 'case_id': cid, 'stream': 'O0',
              'identity': job['identity'], 'job_key': job['job_key'], 'raw_audio': rawb, 'input_provenance': job['input_provenance'],
              'adapter': {'gain_scalar': job['gain'], 'output_binding': ab, 'samples': 3, 'duration_s': 3/16000, 'channels': 1, 'rate_hz': 16000},
              'attempt_number': 1, 'isolated_data_root': str(data), 'owned_process_pid': 123, 'owned_process_creation_time': 100.,
              'initial_profile_files': 0, 'labels_or_transcripts_sent_to_model': False, 'model_success_has_internal_asset_validation': True,
              'cwd': str(a.H2), 'session_dir': str(session),
              'argv': ['fixture_python.exe', '-m', 'app.edge_speech_pipeline', 'file', str(adapterp), '--accelerated'],
              'completion_evidence': {'native_summary': True, 'unique_completion_event': True, 'exact_full_pcm16_samples': 3, 'journal': ev.bind(spool)},
              'model_wall_s': 2., 'model_exited_utc': '2026-09-09T13:00:05+00:00', 'completed_utc': '2026-09-09T13:00:06+00:00'}
    def refresh():
        native['session_summary_binding'] = put(session/'session_summary.json', summary)
        native['metrics_binding'] = put(attempt/'metrics.json', metrics)
        ep = session/'events.jsonl'; ep.write_text('\n'.join(json.dumps(e) for e in events)+'\n', encoding='utf-8')
        native['events_binding'] = a.Evidence().bind(ep)
        (attempt/'stdout.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n'+json.dumps({**summary['telemetry'], 'elapsed_wall_sec': 1.2}, indent=2), encoding='utf-8')
        put(attempt/'attempt_receipt.json', native)
    refresh()
    ctx = {'scenes': {cid: scene}, 'science': science, 'contract': cfg}
    return ctx, job, native, attempt/'attempt_receipt.json', events, summary, metrics, refresh


class NativeTests(unittest.TestCase):
    def run_fixture(self, change=None):
        with tempfile.TemporaryDirectory() as d:
            items = native_fixture(Path(d))
            if change:
                change(*items)
            return a.verify_native(a.Evidence(), items[0], items[1], items[2], items[3], reused=False)

    def test_exact_full_native_success(self):
        r = self.run_fixture(); self.assertEqual(r['status'], 'VERIFIED_NATIVE_COMPLETE')
        self.assertEqual(r['decoded_samples'], 3)

    def test_missing_required_drop_counter_fails(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            for tele in [s['telemetry'], m['telemetry'], e[-1]['payload']['telemetry']]: tele.pop('audio_frames_dropped', None)
            refresh()
        with self.assertRaises((ValueError, KeyError)): self.run_fixture(change)

    def test_summary_event_telemetry_mismatch(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            e[-1]['payload']['telemetry']['asr_cursor_sec'] = 0; refresh()
        with self.assertRaises(ValueError): self.run_fixture(change)

    def test_missing_exported_policy_key(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            s['scientific_policy'].pop('clustering_threshold'); refresh()
        with self.assertRaises(ValueError): self.run_fixture(change)

    def test_wrong_asset_identity(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            s['assets'] = deepcopy(s['assets']); s['assets'][0]['sha256'] = 'f'*64; refresh()
        with self.assertRaises(ValueError): self.run_fixture(change)

    def test_reconstructed_summary_refused(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            s['reconstruction_provenance'] = {}; refresh()
        with self.assertRaises(ValueError): self.run_fixture(change)

    def test_tampered_pcm_even_with_rebound_hash(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            path = Path(n['completion_evidence']['journal']['path']); path.write_bytes(b'\0\0'*3)
            n['completion_evidence']['journal'] = a.Evidence().bind(path); refresh()
        with self.assertRaises(ValueError): self.run_fixture(change)

    def test_second_gain_rejected(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            path = Path(n['adapter']['output_binding']['path']); values, rate = sf.read(path, dtype='float32')
            sf.write(path, values*j['gain'], rate, subtype='FLOAT'); n['adapter']['output_binding'] = a.Evidence().bind(path); refresh()
        with self.assertRaises(ValueError): self.run_fixture(change)

    def test_wrong_event_source_path(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            e[2]['payload']['path'] = 'another_file.wav'; refresh()
        with self.assertRaises(ValueError): self.run_fixture(change)

    def test_stdout_mismatch(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            (p.parent/'stdout.jsonl').write_text('{}', encoding='utf-8')
        with self.assertRaises((ValueError, KeyError)): self.run_fixture(change)

    def test_failed_receipt_not_empty_success(self):
        def change(ctx, j, n, p, e, s, m, refresh): n['exit_code'] = 1
        with self.assertRaises(ValueError): self.run_fixture(change)

    def test_existing_o1_positive_rail_keeps_exact_native_clamp(self):
        def change(ctx, j, n, p, e, s, m, refresh):
            j['stream'] = n['stream'] = m['stream'] = 'O1'
            j['gain'] = n['adapter']['gain_scalar'] = m['fixed_host_gain'] = 1.
            rawp = Path(j['raw_audio']['path']); ap = Path(n['adapter']['output_binding']['path'])
            sf.write(rawp, np.array([.9999997615814209, -1., 0.], np.float32), 16000, subtype='PCM_24')
            values = sf.read(rawp, dtype='float32')[0]; sf.write(ap, values, 16000, subtype='FLOAT')
            j['raw_audio'] = n['raw_audio'] = a.Evidence().bind(rawp); n['adapter']['output_binding'] = a.Evidence().bind(ap)
            spool = Path(n['completion_evidence']['journal']['path'])
            spool.write_bytes(np.round(np.clip(values, -1, .999969)*32768).astype('<i2').tobytes())
            n['completion_evidence']['journal'] = a.Evidence().bind(spool); refresh()
        self.assertEqual(self.run_fixture(change)['status'], 'VERIFIED_NATIVE_COMPLETE')

    def test_reserve_refused_before_native_access(self):
        ctx = {'scenes': {'R': {'split': 'reserve', 'task_scoring_allowed': False}}}
        with patch.object(a.Evidence, 'ref', side_effect=AssertionError('File opened')) as read:
            with self.assertRaises(PermissionError): a.verify_native(a.Evidence(), ctx, {'case_id': 'R'}, {}, Path('none'), reused=False)
            read.assert_not_called()


class MetadataTests(unittest.TestCase):
    def test_complete_representation_needs_backend_and_model(self):
        plan = {'windows': [{'window_id': 'W', 'case_id': 'A', 'outputs': {'O0': {'interval_samples': [0, 8000]}, 'O1': {'interval_samples': [1, 8001]}}}]}
        run = {'models_loaded': 1, 'backend': {'provider': 'fixture'}, 'completed_paired_windows': 1,
               'windows': [{'window_id': 'W', 'case_id': 'A', 'output': out, 'status': 'COMPLETE', 'interval_samples': bounds}
                           for out, bounds in [('O0', [0, 8000]), ('O1', [1, 8001])]]}
        a.validate_representation_rows(plan, run)
        run['models_loaded'] = 0
        with self.assertRaises(ValueError): a.validate_representation_rows(plan, run)
        run['models_loaded'] = 1; run.pop('backend')
        with self.assertRaises(ValueError): a.validate_representation_rows(plan, run)

    def test_representation_duplicate_missing_or_wrong_interval(self):
        plan = {'windows': [{'window_id': 'W', 'case_id': 'A', 'outputs': {'O0': {'interval_samples': [0, 8000]}, 'O1': {'interval_samples': [0, 8000]}}}]}
        row = {'window_id': 'W', 'case_id': 'A', 'output': 'O0', 'status': 'COMPLETE', 'interval_samples': [0, 8000]}
        run = {'models_loaded': 1, 'backend': {'provider': 'fixture'}, 'completed_paired_windows': 1, 'windows': [row, deepcopy(row)]}
        with self.assertRaises(ValueError): a.validate_representation_rows(plan, run)
        run['windows'][1]['output'] = 'O1'; run['windows'][1]['interval_samples'] = [2, 8002]
        with self.assertRaises(ValueError): a.validate_representation_rows(plan, run)

    def manifest(self):
        bank = {'scenes': [{'case_id': cid, 'split': 'development', 'task_scoring_allowed': True} for cid in ('A', 'B')]}
        contract = {'frozen': True}; jobs = []
        for i, scene in enumerate(bank['scenes']):
            order = ['O0', 'O1'] if i == 0 else ['O1', 'O0']
            for out in order:
                identity = {'contract_sha256': a.stable(contract), 'case_id': scene['case_id'], 'stream': out,
                            'raw_audio_sha256': '1'*64, 'gain_scalar': a.GAINS[out], 'input_case_result_sha256': '2'*64,
                            'scene_reference_sha256': a.stable(scene)}
                jobs.append({'case_id': scene['case_id'], 'stream': out, 'raw_audio': {'sha256': '1'*64},
                             'input_provenance': {'case_result': {'sha256': '2'*64}}, 'identity': identity, 'job_key': a.stable(identity),
                             'gain': a.GAINS[out], 'order_index': len(jobs), 'pair_order': order, 'reuse': None})
        return {'jobs': jobs, 'development_ids': ['A', 'B'], 'requested': 4, 'reserve_jobs': 0, 'compatible_reuse': 0, 'new_planned': 4}, bank, contract

    def test_counterbalanced_exact_pairs(self):
        m, b, c = self.manifest(); self.assertEqual(len(a.validate_manifest(m, b, c, expected_scenes=2)[1]), 4)
        m['jobs'][2], m['jobs'][3] = m['jobs'][3], m['jobs'][2]
        with self.assertRaises(ValueError): a.validate_manifest(m, b, c, expected_scenes=2)

    def test_duplicate_pair_and_mutated_reference(self):
        m, b, c = self.manifest(); m['jobs'][1] = m['jobs'][0]
        with self.assertRaises(ValueError): a.validate_manifest(m, b, c, expected_scenes=2)
        m, b, c = self.manifest(); b['scenes'][0]['new_reference'] = 'changed'
        with self.assertRaises(ValueError): a.validate_manifest(m, b, c, expected_scenes=2)

    def test_representation_and_support_access_schemas(self):
        r = {'reserve_model_accesses': 0, 'reserve_audio_accesses': 0, 'reserve_performance_accesses': 0,
             'permitted_calls': [{'case_id': 'A', 'operation': 'embedding_window', 'count': 2}]}
        self.assertEqual(a.validate_access(r, {'A'})['recorded_operation_rows'], 1)
        r['permitted_calls'][0]['case_id'] = 'R'
        with self.assertRaises(ValueError): a.validate_access(r, {'A'})
        with self.assertRaises(ValueError): a.validate_access({}, {'A'})
        with self.assertRaises(ValueError): a.validate_access({'reserve_task_accesses': 1}, {'A'})

    def test_nested_guard_reserve_claim_not_trusted(self):
        r = {'reserve_task_accesses': 0, 'guards': [{'reserve_task_accesses': 1}]}
        with self.assertRaises(ValueError): a.validate_access(r, {'A'})

    def test_unexpected_task_directory_names_refused(self):
        with tempfile.TemporaryDirectory() as d, patch.object(a, 'REPORT', Path(d)/'report'), patch.object(a, 'PAYLOAD', Path(d)/'payload'):
            (a.REPORT/'h2/RESERVE/O0').mkdir(parents=True)
            with self.assertRaises(ValueError): a.unexpected_task_paths({'jobs': [{'case_id': 'A', 'stream': 'O0'}]})

    def test_no_live_process_and_reused_pid(self):
        r = {'owned_process_pid': 123, 'owned_process_creation_time': 100.}
        snap = {'query_succeeded': True, 'processes': []}
        self.assertFalse(a.process_closure(snap, [r])['errors'])
        snap['processes'] = [{'ProcessId': 123, 'CreationDate': '1970-01-01T00:03:20+00:00', 'CommandLine': None}]
        self.assertEqual(len(a.process_closure(snap, [r])['confirmed_pid_reuse']), 1)

    def test_same_generation_or_relevant_unrecorded_owner_blocks(self):
        snap = {'query_succeeded': True, 'processes': [{'ProcessId': 123, 'CreationDate': '1970-01-01T00:01:40+00:00', 'CommandLine': None}]}
        self.assertTrue(a.process_closure(snap, [{'owned_process_pid': 123, 'owned_process_creation_time': 100.}])['errors'])
        snap['processes'] = [{'ProcessId': 999, 'CommandLine': 'python.exe s5_runner.py'}]
        self.assertTrue(a.process_closure(snap, [])['errors'])

    def test_nonfinite_recorded_creation_refused(self):
        snap = {'query_succeeded': True, 'processes': [{'ProcessId': 123, 'CreationDate': '1970-01-01T00:01:40+00:00', 'CommandLine': None}]}
        with self.assertRaises(ValueError): a.process_closure(snap, [{'owned_process_pid': 123, 'owned_process_creation_time': float('nan')}])

    def test_historical_missing_creation_needs_later_current_creation(self):
        snap = {'query_succeeded': True, 'processes': [{'ProcessId': 123, 'CreationDate': '2026-09-09T14:00:00+00:00', 'CommandLine': None}]}
        old = {'owned_process_pid': 123, 'model_exited_utc': '2026-09-09T13:00:00+00:00'}
        self.assertFalse(a.process_closure(snap, [old])['errors'])
        old['model_exited_utc'] = '2026-09-09T15:00:00+00:00'
        self.assertTrue(a.process_closure(snap, [old])['errors'])

    def test_partial_audit_never_calls_wave_or_host_checks(self):
        ctx = {'manifest': {'development_ids': []}, 'jobs': []}
        with tempfile.TemporaryDirectory() as d, patch.object(a, 'SIM', Path(d)), patch.object(a, 'context', return_value=ctx), \
             patch.object(a, 'unexpected_task_paths'), patch.object(a, 'reserve_evidence', return_value={}), \
             patch.object(a, 'job_records', return_value=([], [], [])) as jobs, patch.object(a, 'verify_native', side_effect=AssertionError), \
             patch.object(a, 'process_snapshot', side_effect=AssertionError), patch.object(a, 'resources', side_effect=AssertionError):
            scripts = a.SIM/'scripts'; scripts.mkdir()
            for name in a.CODE_NAMES: (scripts/name).write_text('fixture')
            put(a.SIM/'staging/s5_final_audit/TEST_RECEIPT.json', {'status': 'PASS_MODEL_FREE_FIXTURES', 'code': []})
            r = a.audit(require_complete=False)
            self.assertEqual(r['status'], 'PARTIAL_METADATA_ONLY_NOT_FINAL')
            self.assertEqual(jobs.call_args.kwargs, {'full': False})


if __name__ == '__main__':
    unittest.main()
