"""Resume-safe sequential S4 H2 file jobs. Never opens an audio endpoint or USB."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import soundfile as sf

from s4_common import BANK, EDGE_PYTHON, H2, REPORT, SIM, Progress, bind, check_storage, now, read, save
from s4_h2_analysis import analyze_scene
from s4_capture_selection import accepted_cases, SELECTION_PATH

BASELINE = SIM / 'reports/S0/20260908T181703Z/baseline_manifest.json'
STREAMS = ('O0', 'O1')


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str).encode()).hexdigest()


def _config_without_models():
    """Read the unchanged config module directly; do not import its runtime package."""
    spec = importlib.util.spec_from_file_location('_s4_bound_h2_config', H2 / 'app/edge_speech_pipeline/config.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return json.loads(json.dumps(dataclasses.asdict(module.PipelineConfig()), default=str))


def baseline_contract():
    if os.environ.get('EDGE_SPEECH_ASSET_ROOT'):
        raise RuntimeError('Ambient EDGE_SPEECH_ASSET_ROOT differs from the bound S0 baseline')
    baseline = read(BASELINE)
    assert Path(baseline['python']).resolve() == EDGE_PYTHON.resolve()
    bindings = [bind(row['path'], row['sha256']) for row in baseline['source_bindings']]
    current = _config_without_models()
    expected = baseline['config']
    for key in expected:
        if key not in ('session_root', 'profile_root'):
            assert current[key] == expected[key], 'H2 config changed since S0: ' + key
    identity = {'baseline_manifest_sha256': bind(BASELINE)['sha256'],
                'source_identities': [{'path': r['path'], 'sha256': r['sha256']} for r in bindings],
                'scientific_config': {k: v for k, v in current.items() if k not in ('session_root', 'profile_root')},
                'python': str(EDGE_PYTHON), 'mode': 'file --accelerated; CPU baseline; fresh independent scene',
                'asset_validation': 'Each unmodified CLI invocation validates all eight configured asset hashes internally; no external repeat weight hashing.'}
    return identity, bindings


def verified_restoration(path):
    """Accept a diagnosed recovery only when bound to the preserved failed receipt."""
    path = Path(path).resolve()
    original = read(path)
    receipt, effective_path = original, path
    original_binding = None
    if original['status'] != 'PASS':
        assert original['status'] == 'FAIL', 'Restoration did not establish a completed outcome'
        effective_path = path.with_name('restoration_recovery.json')
        receipt = read(effective_path)
        assert receipt['status'] == 'PASS', 'Hardware restoration recovery failed'
        reference = receipt['original_failure_binding']
        assert Path(reference['path']).resolve() == path, 'Recovery references a different restoration failure'
        original_binding = bind(path, reference['sha256'])
        assert receipt['original_failure'] == original, 'Recovery embeds different failure evidence'
    assert receipt.get('exact_recorded_configuration_match') is True, 'Exact restoration not established'
    for key in ('hardware_lease_released', 'audio_handles_closed', 'telemetry_process_closed', 'packed_input_disabled'):
        assert receipt.get(key) is True, 'Hardware release not established: ' + key
    initial = read(path.with_name('initial_state.json'))
    for key in ('settings', 'identity', 'observe_only'):
        assert receipt['readback'][key] == initial[key], 'Restoration readback differs from exact initial ' + key
    assert receipt['readback']['identity']['I2S_INPUT_PACKED'] == [0]
    assert receipt['readback']['identity']['USB_BIT_DEPTH'] == initial['usb_bits']
    return {**bind(effective_path), 'verified_exact_initial_readback': True,
            'recovery_used': effective_path != path, 'original_failure_binding': original_binding}


def hardware_released(hardware):
    hardware = Path(hardware)
    verified = verified_restoration(hardware / 'restoration.json')
    if (REPORT / 'physical_ledger.json').exists():
        ledger = read(REPORT / 'physical_ledger.json')
        assert not any(p.get('status') == 'STARTED' for p in ledger['passes']), 'A physical pass has no completion receipt'
    # A previously unsafe batch cannot be hidden by pointing to a later good one.
    for path in (REPORT / 'hardware').glob('*/restoration.json'):
        verified_restoration(path)
    return verified


def fixed_gain_copy(source, destination, gain):
    if not isinstance(gain, (int, float)) or not math.isfinite(gain) or gain <= 0:
        raise ValueError('Fixed output gain must be a positive finite scalar')
    audio, rate = sf.read(source, dtype='float32', always_2d=True)
    if rate != 16000 or audio.shape[1] != 1:
        raise ValueError('H2 needs explicit 16 kHz mono; never average six diagnostic channels')
    output = (audio[:, 0].astype(np.float64) * gain).astype(np.float32)
    if not np.isfinite(output).all():
        raise ValueError('Nonfinite adapter input/output')
    peak = float(np.max(np.abs(output))) if len(output) else 0.0
    if peak > 1.0:
        raise ValueError('Frozen host gain exceeds PCM16 numerical headroom; no automatic gain retuning')
    destination = Path(destination)
    if destination.exists():
        old, old_rate = sf.read(destination, dtype='float32')
        if old_rate != rate or old.ndim != 1 or not np.array_equal(old, output):
            raise RuntimeError('Incompatible existing adapter file; preserve evidence')
    else:
        temp = destination.with_name(destination.stem + '.tmp.wav')
        sf.write(temp, output, rate, subtype='FLOAT')
        os.replace(temp, destination)
    return {'gain_scalar': gain, 'gain_db': 20 * math.log10(gain), 'channels': 1, 'rate_hz': rate,
            'samples': len(output), 'duration_s': len(output) / rate, 'peak_fs': peak,
            'input_subtype': sf.info(source).subtype, 'adapter_subtype': 'FLOAT',
            'journal_clip_input_samples': int(np.count_nonzero((output < -1) | (output > .999969))),
            'source_rail_samples': int(np.count_nonzero((audio[:, 0] <= -1) | (audio[:, 0] >= 1 - 2 / 2**23))),
            'gain_location': 'host adapter only; raw preadapter XVF captures preserved',
            'output_binding': bind(destination)}


def completed_session(data_root):
    sessions = sorted((Path(data_root) / 'edge_speech_sessions').glob('*/session_summary.json'))
    if not sessions:
        return None
    if len(sessions) != 1:
        raise RuntimeError('Expected exactly one independent session per ordinary output job')
    summary = read(sessions[0])
    return sessions[0].parent if summary.get('state') == 'COMPLETED' else None


def recover_completed_job(receipt, job_key, data_root):
    """A completed model job can finish metrics after interruption without rerunning."""
    if receipt['job_key'] != job_key:
        raise RuntimeError('Existing H2 job identity differs; preserve the existing run')
    session = completed_session(data_root)
    if receipt.get('status') == 'COMPLETE' and not session:
        raise RuntimeError('Complete receipt lost its completed session evidence')
    if session:
        return session
    raise RuntimeError('Prior H2 invocation is incomplete or failed; preserve evidence and diagnose before any additional model job')


def alignment_for(mapping, case_id, stream, capture):
    """Only accept a supplied measured delay; never fit a delay to expected labels."""
    row = mapping.get(case_id, {}).get(stream) if mapping else None
    if not row:
        return None
    delay = row.get('processed_output_minus_recaptured_input_s')
    if not isinstance(delay, (int, float)) or not math.isfinite(delay) or not row.get('evidence'):
        raise ValueError('Alignment needs finite processed_output_minus_recaptured_input_s and explicit evidence')
    offset = capture['payload']['capture_minus_source_offset_samples'] / 16000 + .05 + delay
    return {'alignment_offset_s': offset, 'recaptured_input_offset_s': capture['payload']['capture_minus_source_offset_samples'] / 16000,
            'rir_retained_margin_s': .05, 'processed_output_delay_s': delay, 'evidence': row['evidence'],
            'uncertainty_s': row.get('uncertainty_s'),
            'scope': 'Descriptive input/output alignment and retained RIR convention; file support is not exact phonetic timing or full physical latency.'}


def output_counts(root):
    result = {'planned_canonical_scenes': 24, 'planned_ordinary_output_jobs': 48, 'complete': 0, 'failed_or_incomplete': 0, 'jobs_started': 0}
    for path in Path(root).glob('S4_*/O*/run_receipt.json'):
        row = read(path)
        result['jobs_started'] += 1
        result['complete' if row.get('status') == 'COMPLETE' else 'failed_or_incomplete'] += 1
    assert result['jobs_started'] <= 48, 'Maximum 48 ordinary S4 output jobs'
    return result


def run(case_ids=None, *, hardware=None, alignment_json=None, validate_only=False, timeout_s=240):
    selection = accepted_cases()
    if hardware is not None and any(row['folder'].parent.resolve() != Path(hardware).resolve() for row in selection.values()):
        raise ValueError('--hardware cannot override authoritative accepted capture selection')
    batches = sorted({row['folder'].parent for row in selection.values()})
    restore = {'accepted_selection': bind(SELECTION_PATH), 'restorations': [hardware_released(batch) for batch in batches]}
    manifest_path = BANK / 'SCENE_MANIFEST.json'
    manifest = read(manifest_path)
    assert manifest['validation']['status'] == 'PASS' and len(manifest['scenes']) == 24
    scenes = {s['case_id']: s for s in manifest['scenes']}
    selected = list(case_ids) if case_ids else list(scenes)
    assert len(selected) == len(set(selected)) and set(selected) <= set(scenes)
    policy_path = REPORT / 'OUTPUT_LEVEL_POLICY.json'
    policy = read(policy_path)
    assert policy['frozen'] and read(REPORT / 'INITIALIZATION_POLICY.json')['frozen']
    gains = policy['fixed_host_gain']
    assert set(STREAMS) <= set(gains) and gains['O1'] == 1, 'Preserve O1 raw level; O0 fixed gain only'
    baseline, source_bindings = baseline_contract()
    code = [bind(SIM / 'scripts' / name) for name in ('s4_h2_run.py', 's4_h2_analysis.py')]
    code.append(bind(H2 / 'app/scoring/wer.py'))
    code.append(bind(SIM / 'scripts/s4_capture_selection.py'))
    contract = {'baseline': baseline, 'runner_code': [{'path': b['path'], 'sha256': b['sha256']} for b in code],
                'scene_manifest_sha256': bind(manifest_path)['sha256'],
                'output_policy_sha256': bind(policy_path)['sha256'],
                'accepted_capture_selection_sha256': bind(SELECTION_PATH)['sha256'],
                'fixed_host_gain': gains}
    alignment = read(alignment_json) if alignment_json else {}
    captures = {}
    for cid in selected:
        c = selection[cid]['case_result']
        assert c['status'] == 'PASS' and c['audio_integrity_status'] == 'PASS'
        assert c['final_recipe_capture'] is True and c['recipe'] == policy['hardware_recipe']
        assert c['input_scene_sha256'] == scenes[cid]['canonical_audio']['sha256']
        assert c['payload']['status'] == 'PASS' and c['framing']['marker_error_count'] == 0
        configuration = read(selection[cid]['folder'] / 'configuration.json')['settings']
        assert configuration['AEC_ASROUTGAIN'] == [1], 'Do not combine an XVF ASR gain and a host gain'
        captures[cid] = c
    if validate_only:
        print(json.dumps({'status': 'VALIDATED_NO_MODEL_JOBS', 'requested_scenes': selected, 'outputs': 2 * len(selected)}, indent=2))
        return
    target = REPORT / 'h2'
    target.mkdir(exist_ok=True)
    # This lock owns only the offline runner, not the XVF. No audio APIs are called.
    import msvcrt
    lease = (target / 'runner.lock').open('a+b')
    lease.seek(0)
    if lease.read(1) == b'':
        lease.write(b'0'); lease.flush()
    lease.seek(0)
    msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
    started = time.monotonic()
    invocation_status = 'FAILED_OR_INTERRUPTED'
    try:
        if (target / 'execution_contract.json').exists():
            assert read(target / 'execution_contract.json') == contract, 'S4 H2 contract changed after jobs began'
        else:
            save(target / 'execution_contract.json', contract)
        save(target / 'baseline_source_bindings.json', source_bindings)
        jobs = [(cid, stream) for cid in selected for stream in STREAMS]
        with Progress('H2_sequential_file_jobs', len(jobs)) as progress:
            for cid, stream in jobs:
                check_storage()
                progress.case = cid + '/' + stream
                scene, capture = scenes[cid], captures[cid]
                source = selection[cid]['folder'] / (stream + '.wav')
                source_bound = bind(source, capture['output_audio'][stream]['sha256'])
                folder = target / cid / stream
                folder.mkdir(parents=True, exist_ok=True)
                root = folder / 'empty_data'
                input_path = folder / ('input_' + stream + '_fixed_gain.wav')
                identity = {'contract_sha256': stable_hash(contract), 'case_id': cid, 'stream': stream,
                            'raw_audio_sha256': source_bound['sha256'], 'gain_scalar': gains[stream]}
                job_key = stable_hash(identity)
                align = alignment_for(alignment, cid, stream, capture)
                analysis_identity = stable_hash({'alignment': align, 'scorer_code_sha256': code[1]['sha256']})
                receipt_path = folder / 'run_receipt.json'
                session = None
                if receipt_path.exists():
                    receipt = read(receipt_path)
                    session = recover_completed_job(receipt, job_key, root)
                    bind(input_path, receipt['adapter']['output_binding']['sha256'])
                    if receipt.get('status') == 'COMPLETE':
                        bind(session / 'session_summary.json', receipt['session_summary_binding']['sha256'])
                        bind(session / 'events.jsonl', receipt['events_binding']['sha256'])
                    if receipt.get('status') == 'COMPLETE' and (folder / 'metrics.json').exists() and receipt.get('analysis_identity') == analysis_identity:
                        bind(folder / 'metrics.json', receipt['metrics_binding']['sha256'])
                        progress.done += 1; progress.detail = 'Reused compatible completed job'; progress.emit()
                        continue
                else:
                    if root.exists() and any(root.iterdir()):
                        raise RuntimeError('Unreceipted nonempty isolated data root; preserve and diagnose')
                    assert output_counts(target)['jobs_started'] < 48
                    adapter = fixed_gain_copy(source, input_path, gains[stream])
                    root.mkdir(exist_ok=True)
                    assert not list(root.iterdir())
                    argv = [str(EDGE_PYTHON), '-m', 'app.edge_speech_pipeline', 'file', str(input_path.resolve()), '--accelerated']
                    receipt = {'schema': 'jp_s4_h2_job_v1', 'status': 'STARTED', 'job_key': job_key, 'identity': identity,
                               'case_id': cid, 'stream': stream, 'created_utc': now(), 'raw_audio': source_bound,
                               'adapter': adapter, 'argv': argv, 'cwd': str(H2), 'isolated_data_root': str(root.resolve()),
                               'initial_profile_files': 0, 'hardware_restoration': restore,
                               'labels_or_transcripts_sent_to_model': False, 'external_asset_hash_passes': 0}
                    save(receipt_path, receipt)
                    env = os.environ.copy()
                    env['EDGE_SPEECH_DATA_ROOT'] = str(root.resolve())
                    env['PYTHONDONTWRITEBYTECODE'] = '1'
                    env.pop('EDGE_SPEECH_ASSET_ROOT', None)
                    progress.detail = 'Unchanged H2 CPU baseline, fresh empty session'; progress.emit()
                    model_start = time.monotonic()
                    process = None
                    try:
                        with (folder / 'stdout.jsonl').open('wb') as out, (folder / 'stderr.txt').open('wb') as err:
                            process = subprocess.Popen(argv, cwd=H2, env=env, stdout=out, stderr=err,
                                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                            receipt['owned_process_pid'] = process.pid
                            save(receipt_path, receipt)
                            exit_code = process.wait(timeout=timeout_s)
                        receipt['exit_code'] = exit_code
                        session = completed_session(root)
                        if exit_code != 0 or session is None:
                            raise RuntimeError('H2 CLI failed or did not complete; stop affected execution, do not repeat blindly')
                    except BaseException as exc:
                        if process is not None and process.poll() is None:
                            # Stop only the child this runner just created, never other jobs.
                            process.terminate()
                            try:
                                process.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                process.kill(); process.wait(timeout=10)
                        receipt.update(status='FAILED_OR_INTERRUPTED', error=repr(exc), model_wall_s=time.monotonic()-model_start, ended_utc=now())
                        save(receipt_path, receipt)
                        raise
                    receipt.update(status='MODEL_COMPLETED', model_wall_s=time.monotonic()-model_start, session_dir=str(session), model_completed_utc=now())
                    save(receipt_path, receipt)
                # Scoring occurs after the H2 process and cannot influence its decisions.
                metrics = analyze_scene(session, scene, audio_path=input_path, alignment_offset_s=align['alignment_offset_s'] if align else 0.0)
                if align is None:
                    metrics['speaker'].pop('reference_turn_evidence', None)
                    metrics['source_to_output_turn_scoring'] = {'status': 'LIMITED', 'reason': 'No independently evidenced processed-output delay supplied; no nominal shift invented'}
                else:
                    metrics['source_to_output_turn_scoring'] = {'status': 'DESCRIPTIVE_FILE_SUPPORT_ONLY', **align}
                metrics.update(case_id=cid, stream=stream, raw_output_rail_samples=receipt['adapter']['source_rail_samples'],
                               fixed_host_gain=receipt['adapter']['gain_scalar'])
                telemetry = metrics['telemetry']
                assert metrics['state'] == 'COMPLETED' and not metrics['failure_events']
                assert not any(telemetry.get(k, 0) for k in ('audio_frames_dropped', 'portaudio_input_overflows', 'raw_capture_reserve_failures'))
                save(folder / 'metrics.json', metrics)
                receipt.update(status='COMPLETE', session_dir=str(session), completed_utc=now(),
                               metrics_binding=bind(folder / 'metrics.json'), session_summary_binding=bind(session / 'session_summary.json'),
                               events_binding=bind(session / 'events.jsonl'), analysis_identity=analysis_identity,
                               model_success_has_internal_asset_validation=True)
                save(receipt_path, receipt)
                save(target / 'run_summary.json', {**output_counts(target), 'updated_utc': now(), 'current_invocation_wall_s': time.monotonic()-started,
                                                 'model_wall_s_all_receipts': sum(read(p).get('model_wall_s', 0) for p in target.glob('S4_*/O*/run_receipt.json'))})
                progress.done += 1; progress.detail = 'Completed and analyzed'; progress.emit()
        invocation_status = 'REQUESTED_JOBS_COMPLETE'
        print(json.dumps({**output_counts(target), 'status': invocation_status, 'wall_s': time.monotonic()-started}, indent=2))
    finally:
        try:
            save(target / 'run_summary.json', {**output_counts(target), 'updated_utc': now(), 'last_invocation_status': invocation_status,
                                             'current_invocation_wall_s': time.monotonic()-started,
                                             'model_wall_s_all_receipts': sum(read(p).get('model_wall_s', 0) for p in target.glob('S4_*/O*/run_receipt.json'))})
        finally:
            lease.seek(0)
            msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
            lease.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', nargs='+', help='Exact canonical IDs, e.g. S4_01; both outputs always run')
    parser.add_argument('--hardware', help='Optional consistency check only; cannot override accepted selection')
    parser.add_argument('--alignment-json', help='Optional case→stream→measured output delay/evidence mapping')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--timeout-s', type=float, default=240)
    args = parser.parse_args()
    run(args.cases, hardware=args.hardware, alignment_json=args.alignment_json,
        validate_only=args.validate_only, timeout_s=args.timeout_s)
