"""Bounded S4_18/O1 completion-summary recovery. See README_S4_H2_RECOVERY.md."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import unittest

import numpy as np

from s4_common import REPORT, H2, bind, now, read, save
from s4_h2_analysis import journal_audio
from s4_h2_run import baseline_contract, stable_hash

CASE_ID, STREAM = 'S4_18', 'O1'
SESSION_NAME = 'edge_wav_20260909T013655Z_c62a4b6f'
RECOVERY_PATH = REPORT / 'H2_SUMMARY_RECOVERY.json'


def json_sequence(text):
    decoder = json.JSONDecoder(); values = []; offset = 0
    while offset < len(text):
        while offset < len(text) and text[offset].isspace(): offset += 1
        if offset == len(text): break
        value, offset = decoder.raw_decode(text, offset)
        values.append(value)
    return values


def validate_primary(receipt, summary_bytes, events, stdout_values, spool, expected, labelled, session):
    if summary_bytes != b'': raise ValueError('Only the diagnosed zero-byte summary can be recovered')
    if receipt.get('status') != 'FAILED_OR_INTERRUPTED' or receipt.get('exit_code') != 0:
        raise ValueError('Require preserved post-exit-zero runner failure')
    if not receipt.get('error', '').startswith('JSONDecodeError('):
        raise ValueError('This recovery does not cover other runner failures')
    if any(e.get('event_type') in {'failure', 'fatal', 'session_failed', 'session_stopped', 'session_aborted', 'source_stopped'} for e in events):
        raise ValueError('Failure/stopped event cannot be repaired as a completed job')
    completed = [e for e in events if e.get('event_type') == 'session_completed']
    if len(completed) != 1 or not events or events[-1] != completed[0]:
        raise ValueError('Require exactly one terminal completion event')
    if [v for v in stdout_values if 'event_type' in v] != events:
        raise ValueError('Journal and stdout events must agree exactly')
    telemetry_rows = [v for v in stdout_values if 'event_type' not in v]
    if len(telemetry_rows) != 1:
        raise ValueError('Require one independently emitted final stdout telemetry object')
    telemetry = completed[0]['payload']['telemetry']
    strip_elapsed = lambda row: {k: v for k, v in row.items() if k != 'elapsed_wall_sec'}
    if strip_elapsed(telemetry) != strip_elapsed(telemetry_rows[0]):
        raise ValueError('Final telemetry disagrees with completion event')
    if telemetry_rows[0]['elapsed_wall_sec'] < telemetry['elapsed_wall_sec']:
        raise ValueError('Stdout final telemetry predates the completion evidence')
    if telemetry.get('state') != 'COMPLETED' or telemetry.get('session_dir') != str(session):
        raise ValueError('Completion state/session identity mismatch')
    duration = len(expected) / 16000
    if len(expected) != receipt['adapter']['samples'] or not np.array_equal(spool, expected):
        raise ValueError('PCM16 journal is incomplete or differs from the exact adapter conversion')
    for key in ('source_duration_sec', 'asr_cursor_sec', 'speaker_cursor_sec'):
        if abs(telemetry[key] - duration) > 1e-9:
            raise ValueError('Completed source/model cursor does not cover the full adapter')
    for key in ('audio_frames_dropped', 'portaudio_input_overflows', 'raw_capture_reserve_failures'):
        if telemetry.get(key) != 0: raise ValueError('No-drop completion gate failed: ' + key)
    finals = [e for e in events if e['event_type'] == 'transcript_final']
    if len(finals) != len(labelled): raise ValueError('Final transcript journal is incomplete')
    for event, row in zip(finals, labelled):
        if any(row.get(key) != value for key, value in event['payload'].items()):
            raise ValueError('Labelled transcript does not preserve final event payload')
        if abs(row['source_end_sec'] - event['source_time_sec']) > 1e-6:
            raise ValueError('Final transcript source time mismatch')
    return completed[0], {'exit_code_zero': True, 'unique_terminal_completion': True,
                         'event_count': len(events), 'journal_stdout_events_exact': True,
                         'final_telemetry_matches_except_later_elapsed_wall': True,
                         'full_source_and_model_cursors': True, 'zero_drop_failure_counters': True,
                         'spool_samples': len(spool), 'spool_exact_adapter_pcm16': True,
                         'final_transcript_rows': len(finals), 'final_transcript_payloads_exact': True}


def run(execute=False):
    folder = REPORT / 'h2' / CASE_ID / STREAM
    session = folder / 'empty_data/edge_speech_sessions' / SESSION_NAME
    receipt_path = folder / 'run_receipt.json'
    receipt = read(receipt_path)
    if receipt.get('case_id') != CASE_ID or receipt.get('stream') != STREAM:
        raise ValueError('This helper is bounded to the diagnosed S4_18/O1 invocation')
    contract_path = REPORT / 'h2/execution_contract.json'; contract = read(contract_path)
    baseline, _ = baseline_contract()
    if baseline != contract['baseline']:
        raise ValueError('Original S0 baseline/source/config identity changed')
    for item in contract['runner_code']: bind(item['path'], item['sha256'])
    if receipt['identity']['contract_sha256'] != stable_hash(contract) or receipt['job_key'] != stable_hash(receipt['identity']):
        raise ValueError('Frozen execution/job identity mismatch')
    if receipt['identity']['gain_scalar'] != contract['fixed_host_gain'][STREAM] or receipt['labels_or_transcripts_sent_to_model'] is not False:
        raise ValueError('Gain or no-ground-truth-input contract mismatch')
    if Path(receipt['isolated_data_root']).resolve() != (folder / 'empty_data').resolve():
        raise ValueError('Isolated root changed')
    if list((folder / 'empty_data/edge_speech_sessions').iterdir()) != [session]:
        raise ValueError('Require one original model session, never a replacement model run')
    adapter = folder / 'input_O1_fixed_gain.wav'
    bind(adapter, receipt['adapter']['output_binding']['sha256'])
    bind(receipt['raw_audio']['path'], receipt['raw_audio']['sha256'])
    events_path, stdout_path = session / 'events.jsonl', folder / 'stdout.jsonl'
    labelled_path = session / 'labelled_transcript.jsonl'
    events = json_sequence(events_path.read_text(encoding='utf-8-sig'))
    stdout = json_sequence(stdout_path.read_text(encoding='utf-8-sig'))
    labelled = json_sequence(labelled_path.read_text(encoding='utf-8-sig'))
    spool = np.fromfile(session / 'audio_spool.pcm16', dtype='<i2')
    expected = (journal_audio(adapter) * 32768).astype('<i2')
    completed, validation = validate_primary(receipt, (session / 'session_summary.json').read_bytes(), events, stdout, spool, expected, labelled, session)
    validation.update(source_config_baseline_unchanged=True, frozen_execution_code_unchanged=True)
    source_paths = {'events': events_path, 'stdout': stdout_path, 'labelled_transcript': labelled_path,
                    'audio_spool': session / 'audio_spool.pcm16', 'adapter': adapter,
                    'execution_contract': contract_path,
                    'original_runtime': H2 / 'app/edge_speech_pipeline/runtime.py',
                    'original_cli': H2 / 'app/edge_speech_pipeline/cli.py',
                    'original_models': H2 / 'app/edge_speech_pipeline/models.py',
                    'original_asset_validator': H2 / 'app/edge_speech_pipeline/assets.py'}
    sources = {key: bind(path) for key, path in source_paths.items()}
    config = contract['baseline']['scientific_config']
    assets = [{'component_id': a['component_id'], 'sha256': a['sha256']} for a in config['assets']]
    if len(assets) != 8: raise ValueError('Unexpected bound asset inventory')
    asset_scope = ('Expected identities from bound original configuration. No asset-validation event exists in this baseline. '
                   'Successful validation is inferred from the unchanged model constructors: two speaker assets and six ASR/punctuation assets '
                   'are SHA-validated before session_started; validation failure raises. Recovery does not rehash model weights or fabricate an asset event.')
    if not execute:
        print(json.dumps({'status': 'VALIDATED_NO_WRITES', 'validation': validation, 'asset_evidence_scope': asset_scope}, indent=2))
        return
    if RECOVERY_PATH.exists() or (folder / 'recovery_evidence').exists():
        raise ValueError('Recovery evidence already exists; preserve and review before any repeat')
    # Take the same offline-runner lease; never open the XVF hardware lease.
    import msvcrt
    lease = (REPORT / 'h2/runner.lock').open('r+b'); lease.seek(0)
    msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        if read(receipt_path) != receipt or (session / 'session_summary.json').read_bytes() != b'':
            raise ValueError('Original failure changed during validation')
        preserved = folder / 'recovery_evidence'; preserved.mkdir()
        empty_copy = preserved / 'session_summary.original_empty.json'
        failed_copy = preserved / 'run_receipt.original_failed.json'
        empty_copy.write_bytes(b''); failed_copy.write_bytes(receipt_path.read_bytes())
        sources.update(original_empty_summary=bind(empty_copy), original_failed_run_receipt=bind(failed_copy))
        created = now()
        summary = {'schema_version': 'edge-speech-session.v1', 'state': 'COMPLETED',
                   'telemetry': completed['payload']['telemetry'], 'assets': assets,
                   'scientific_policy': {k: config[k] for k in ('identity_score_threshold', 'identity_margin_threshold', 'identity_minimum_evidence_sec', 'clustering_threshold')},
                   'xvf': {'contract_available': True, 'result_effects_enabled': False},
                   'reconstruction_provenance': {'status': 'DERIVED_FROM_PRIMARY_COMPLETION_EVIDENCE', 'reconstructed_utc': created,
                       'original_runtime_summary_was_written': False, 'original_summary_bytes': 0,
                       'telemetry_source': 'Exact terminal session_completed event; later stdout telemetry cross-checked except elapsed time.',
                       'asset_evidence_scope': asset_scope, 'source_bindings': sources,
                       'original_summary_elapsed_wall_sec': None, 'model_rerun': False}}
        save(session / 'session_summary.json', summary)
        derived = bind(session / 'session_summary.json')
        recovery = {'schema': 'jp_s4_h2_summary_recovery_v1', 'status': 'RECOVERED_FROM_COMPLETION_EVIDENCE',
                    'created_utc': created, 'case_id': CASE_ID, 'stream': STREAM, 'session_dir': str(session),
                    'source_bindings': sources, 'derived_summary': derived, 'validation': validation,
                    'original_completion_event_utc': completed['wall_time_utc'], 'asset_evidence_scope': asset_scope,
                    'cause': {'confidence': 'HIGH_IMPLEMENTATION_EVIDENCE_WITHOUT_DIRECT_THREAD_TRACE',
                              'diagnosis': 'Original CLI can exit when the daemon watcher announces COMPLETED before the summary write and handle closure finish.',
                              'evidence': ['runtime.py:236 daemon watcher', 'runtime.py:463-465 sets COMPLETED and emits completion before _write_summary',
                                           'runtime.py:513 non-atomic write_text can truncate before writing', 'cli.py:45-54 returns on COMPLETED without joining the watcher'],
                              'observed': 'Exit zero, complete matching journals and full PCM16 spool, but original summary was zero bytes.'},
                    'no_model_rerun': True, 'frozen_execution_code_unchanged': True, 'hardware_accessed': False,
                    'recovery_code': bind(Path(__file__))}
        save(RECOVERY_PATH, recovery)
        active = copy.deepcopy(receipt)
        active.pop('error', None); active.pop('ended_utc', None)
        active.update(status='MODEL_COMPLETED', session_dir=str(session), model_completed_utc=completed['wall_time_utc'],
                      original_failure_receipt=bind(failed_copy), summary_recovery_receipt=bind(RECOVERY_PATH),
                      summary_recovered_utc=created,
                      original_failure_provenance={'status': receipt['status'], 'error': receipt['error'], 'ended_utc': receipt['ended_utc']})
        save(receipt_path, active)
        for key, path in source_paths.items(): bind(path, sources[key]['sha256'])
        for item in contract['runner_code']: bind(item['path'], item['sha256'])
        print(json.dumps({'status': recovery['status'], 'recovery_receipt': str(RECOVERY_PATH), 'active_receipt_status': active['status'],
                          'no_model_rerun': True, 'validation': validation}, indent=2))
    finally:
        lease.seek(0); msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1); lease.close()


class RecoveryTests(unittest.TestCase):
    def fixture(self):
        telemetry = {'state': 'COMPLETED', 'session_dir': 'session', 'elapsed_wall_sec': 1.0,
                     'source_duration_sec': .000125, 'asr_cursor_sec': .000125, 'speaker_cursor_sec': .000125,
                     'audio_frames_dropped': 0, 'portaudio_input_overflows': 0, 'raw_capture_reserve_failures': 0}
        events = [{'event_type': 'session_completed', 'payload': {'telemetry': telemetry}}]
        stdout = copy.deepcopy(events) + [{**telemetry, 'elapsed_wall_sec': 1.01}]
        receipt = {'status': 'FAILED_OR_INTERRUPTED', 'exit_code': 0, 'error': 'JSONDecodeError(test)', 'adapter': {'samples': 2}}
        return [receipt, b'', events, stdout, np.array([1, 2]), np.array([1, 2]), [], 'session']

    def test_completed_primary_evidence_is_accepted(self):
        _, result = validate_primary(*self.fixture()); self.assertTrue(result['spool_exact_adapter_pcm16'])

    def test_nonempty_corruption_and_nonzero_exit_are_rejected(self):
        for change in ('bytes', 'exit', 'error'):
            args = self.fixture()
            if change == 'bytes': args[1] = b'{broken'
            elif change == 'exit': args[0]['exit_code'] = 2
            else: args[0]['error'] = 'different failure'
            with self.assertRaises(ValueError): validate_primary(*args)

    def test_duplicate_completion_or_failure_is_rejected(self):
        for row in ({'event_type': 'failure'}, self.fixture()[2][0]):
            args = self.fixture(); args[2].insert(0, row)
            with self.assertRaises(ValueError): validate_primary(*args)

    def test_missing_journal_or_divergent_telemetry_is_rejected(self):
        for change in ('events', 'telemetry', 'spool', 'cursor', 'drops'):
            args = self.fixture()
            if change == 'events': args[3].pop(0)
            elif change == 'telemetry': args[3][-1]['state'] = 'RUNNING'
            elif change == 'spool': args[4] = np.array([1])
            elif change == 'cursor':
                args[2][0]['payload']['telemetry']['asr_cursor_sec'] = 0
                args[3] = copy.deepcopy(args[2]) + [copy.deepcopy(args[2][0]['payload']['telemetry'])]
            else:
                args[2][0]['payload']['telemetry']['audio_frames_dropped'] = 1
                args[3] = copy.deepcopy(args[2]) + [copy.deepcopy(args[2][0]['payload']['telemetry'])]
            with self.assertRaises(ValueError): validate_primary(*args)

    def test_stdout_sequence_accepts_indented_final_object(self):
        self.assertEqual(json_sequence('{"event_type":"x"}\n{\n "state": "COMPLETED"\n}\n'), [{'event_type': 'x'}, {'state': 'COMPLETED'}])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryTests))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    run(execute=args.execute)
