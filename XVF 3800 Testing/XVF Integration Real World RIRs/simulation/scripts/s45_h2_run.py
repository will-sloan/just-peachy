"""Bounded S4.5 H2 sentinel/dry jobs; no hardware APIs. README_S45_H2_RUN.md."""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

import numpy as np
import soundfile as sf

from s45_common import (BANK, EDGE_PYTHON, H2, HARDWARE, LIMITS, PAYLOAD, REPORT, SIM,
                        Progress, bind, check_storage, launch_allowed, now, read, save,
                        single_thread_env)
from s4_h2_run import (_config_without_models, alignment_for, completed_session,
                       fixed_gain_copy, stable_hash, verified_restoration)
from s4_h2_analysis import analyze_scene, score_text, journal_audio

BASELINE = SIM / 'reports/S0/20260908T181703Z/baseline_manifest.json'
FIX = SIM / 'staging/s45_h2_fix/v3/FIX_RECEIPT.json'
SENTINELS = REPORT / 'SENTINEL_PLAN.json'
DRY_PLAN = REPORT / 'DRY_CONTROL_PLAN.json'
SELECTION = REPORT / 'ACCEPTED_CAPTURES.json'
RELEASE = REPORT / 'H2_RELEASE.json'
STREAMS = ('O0', 'O1')
CODE_NAMES = ('s45_h2_run.py', 's45_common.py', 's4_h2_run.py', 's4_h2_analysis.py', 's4_common.py')


def identity_binding(path, expected=None):
    b = bind(path, expected)
    return {k: b[k] for k in ('path', 'sha256', 'bytes')}


def baseline_contract():
    """Only the recorded two-file lifecycle repair may differ from S0."""
    if os.environ.get('EDGE_SPEECH_ASSET_ROOT'):
        raise RuntimeError('Ambient asset override differs from S0')
    baseline, fix = read(BASELINE), read(FIX)
    assert fix['status'] == 'PASS_MODEL_FREE_REGRESSIONS'
    assert fix['model_jobs_run'] == 0 and fix['scientific_methods_ast_unchanged'] is True
    allowed = {str((H2 / 'app/edge_speech_pipeline' / n).resolve()) for n in ('runtime.py', 'cli.py')}
    changes = {str(Path(r['path']).resolve()): r for r in fix['changed_sources']}
    assert set(changes) == allowed, 'Repair may change only runtime.py and cli.py'
    identity_binding(fix['diff']['path'], fix['diff']['sha256'])
    source_bindings = []
    for row in baseline['source_bindings']:
        path = str(Path(row['path']).resolve())
        if path in changes:
            change = changes[path]
            assert change['before_sha256'] == row['sha256']
            identity_binding(change['original_backup']['path'], row['sha256'])
            assert Path(change['after']['path']).resolve() == Path(path)
            source_bindings.append(identity_binding(path, change['after']['sha256']))
        else:
            source_bindings.append(identity_binding(path, row['sha256']))
    assert allowed <= {r['path'] for r in source_bindings}
    current = _config_without_models()
    science = {k: v for k, v in current.items() if k not in ('session_root', 'profile_root')}
    expected = {k: v for k, v in baseline['config'].items() if k not in ('session_root', 'profile_root')}
    assert science == expected == fix['scientific_config'], 'S0 scientific configuration changed'
    assert Path(baseline['python']).resolve() == EDGE_PYTHON.resolve()
    return {'baseline_manifest': identity_binding(BASELINE), 'durability_fix': identity_binding(FIX),
            'source_identities': source_bindings, 'scientific_config': science,
            'python': str(EDGE_PYTHON), 'mode': 'file --accelerated; CPU; fresh independent session',
            'asset_validation': 'Every CLI internally validates all eight baseline assets. No outer repeated weight hashing.'}


def scene_context():
    path = BANK / 'SCENE_MANIFEST.json'
    manifest, plan = read(path), read(SENTINELS)
    assert manifest['validation']['status'] == 'PASS'
    scenes = {s['case_id']: s for s in manifest['scenes']}
    ids = plan['scene_ids']
    assert plan['selection_before_hardware_or_H2'] is True and plan['reserve_jobs_allowed'] == 0
    assert len(ids) == len(set(ids)) == LIMITS['sentinel_scenes']
    assert collections.Counter(scenes[c]['family_id'] for c in ids) == {f'F{i:02}': 2 for i in range(1, 13)}
    for cid in ids:
        assert scenes[cid]['split'] == 'development' and scenes[cid]['task_scoring_allowed'] is True
    return manifest, scenes, ids


def jobs_started():
    return sorted((REPORT / 'h2').glob('*/*/run_receipt.json')) + sorted((REPORT / 'h2_dry').glob('*/run_receipt.json'))


def dry_candidates(manifest, scenes, sentinel_ids):
    """Balanced deterministic round robin over source strata; no task outcomes."""
    sources = manifest['selected_sources']
    matches = collections.defaultdict(list)
    for cid in sentinel_ids:
        for seg in scenes[cid]['segments']:
            if seg['kind'] == 'utterance':
                matches[seg['source_id']].append(cid)
    groups = collections.defaultdict(list)
    for sid, case_ids in matches.items():
        src = sources[sid]
        assert src['split'] == 'development' and src['usage'] == 'probe' and src['whole_clip'] is True
        assert 'l2' not in src['dataset'].lower(), 'User excluded L2 ARCTIC'
        seconds = src['samples'] / 16000
        short = 'under_1s' if seconds < 1 else '1_to_2s' if seconds <= 2 else 'over_2s'
        groups[(src['dataset'], str(src.get('quality_partition')), short)].append((sid, sorted(set(case_ids))))
    # Favor shorter native clips within a stratum, then source ID; never crop text.
    for group in groups.values():
        group.sort(key=lambda r: (sources[r[0]]['samples'], r[0]))
    chosen, seen_pcm = [], set()
    while groups and len(chosen) < LIMITS['dry_jobs']:
        for key in sorted(list(groups)):
            sid, matches = groups[key].pop(0)
            src = sources[sid]
            pcm_key = src.get('decoded_pcm_sha256', src['decoded_16k_binding']['sha256'])
            if pcm_key not in seen_pcm:
                seen_pcm.add(pcm_key)
                gain = src['preparation_gain']
                gain = gain['scalar'] if isinstance(gain, dict) else gain
                chosen.append({'control_id': f'DRY_{len(chosen)+1:02}', 'source_id': sid,
                               'source': copy.deepcopy(src), 'sentinel_case_ids': matches,
                               'stratum': {'dataset': key[0], 'quality_partition': key[1], 'duration_bin': key[2]},
                               'fixed_gain_scalar': gain,
                               'level_scope': 'Frozen source preparation scalar before RIR/relative-source/family headroom; no output-stream gain or per-utterance retuning.'})
            if not groups[key]:
                del groups[key]
            if len(chosen) == LIMITS['dry_jobs']:
                break
    return chosen


def prepare_plans():
    manifest, scenes, ids = scene_context()
    controls = dry_candidates(manifest, scenes, ids)
    identity = {'scene_manifest': identity_binding(BANK / 'SCENE_MANIFEST.json'),
                'sentinel_plan': identity_binding(SENTINELS), 'controls': controls,
                'selection_rule': 'Round robin corpus / source-quality / whole-clip duration bin; shortest then source ID within each bin; unique decoded PCM.',
                'maximum_jobs': LIMITS['dry_jobs'], 'reserve_jobs_allowed': 0}
    if DRY_PLAN.exists():
        old = read(DRY_PLAN)
        assert old['identity'] == identity, 'Frozen dry plan differs; preserve existing evidence'
        return old
    assert not jobs_started(), 'Dry plan must be frozen before any S4.5 H2 invocation'
    for row in controls:
        src = row['source']['decoded_16k_binding']
        identity_binding(src['path'], src['sha256'])
    plan = {'schema': 'jp_s45_dry_control_plan_v1', 'frozen_utc': now(),
            'selection_before_any_H2': True, 'identity': identity, 'count': len(controls),
            'control_ids': [r['control_id'] for r in controls],
            'comparison_scope': 'Source-domain ASR floor on corresponding whole clips. Multi-turn scene WER is not a paired single-clip treatment effect.'}
    save(DRY_PLAN, plan)
    return plan


def accepted_for(ids, scenes, policy):
    snapshot = read(SELECTION)
    assert snapshot['reserve_task_scored'] is False
    assert snapshot['scene_manifest']['sha256'] == identity_binding(BANK / 'SCENE_MANIFEST.json')['sha256']
    rows = {r['case_id']: r for r in snapshot['accepted']}
    assert len(rows) == len(snapshot['accepted']), 'Duplicate accepted scene'
    out = {}
    for cid in ids:
        row = rows[cid]
        assert row['split'] == 'development' and row['task_scoring_allowed'] is True
        assert row['audio_valid'] is True and row['telemetry_valid'] is True
        folder = Path(row['folder']).resolve()
        assert folder.is_relative_to(HARDWARE.resolve())
        rb = row['case_result']
        assert Path(rb['path']).resolve() == folder / 'case_result.json'
        binding = identity_binding(rb['path'], rb['sha256'])
        c = read(rb['path'])
        assert c['case_id'] == cid and c['status'] == 'PASS' and c['audio_integrity_status'] == 'PASS'
        assert c['telemetry_status'] == 'PASS' and c['final_recipe_capture'] is True
        assert c['recipe'] == policy['hardware_recipe'] and c['code_key'] == row['code_key']
        assert c['payload']['status'] == 'PASS' and c['framing']['marker_error_count'] == 0
        assert c['input_scene_sha256'] == row['input_scene_sha256'] == scenes[cid]['canonical_audio']['sha256']
        assert read(folder / 'configuration.json')['settings']['AEC_ASROUTGAIN'] == [1]
        out[cid] = {'folder': folder, 'capture': c, 'case_result_binding': binding,
                    'selection_record': {k: row[k] for k in ('case_id', 'folder', 'input_scene_sha256', 'code_key', 'split', 'audio_valid', 'telemetry_valid', 'task_scoring_allowed')}}
    return out


def execution_release():
    release = read(RELEASE)
    assert release['status'] == 'AUTHORIZED_OFFLINE_H2'
    assert isinstance(release.get('allow_during_physical_capture'), bool)
    if not release['allow_during_physical_capture']:
        ledger = read(REPORT / 'physical_ledger.json')
        assert not any(r.get('status') == 'STARTED' for r in ledger['passes'])
        for p in HARDWARE.glob('*/restoration.json'):
            verified_restoration(p)
        owned = read(REPORT / 'owned_process.json') if (REPORT / 'owned_process.json').exists() else {}
        assert owned.get('hardware_owner') is None
    return identity_binding(RELEASE)


def load_alignment(explicit, cid, stream, selected):
    folder, capture = selected['folder'], selected['capture']
    evidence = folder / 'audio_metrics.json'
    metrics = read(evidence)
    analysis_receipt = read(folder / 's45_analysis_receipt.json')
    assert analysis_receipt['case_result']['sha256'] == selected['case_result_binding']['sha256']
    identity_binding(evidence, analysis_receipt['audio_metrics']['sha256'])
    assert metrics['input_scene_sha256'] == capture['input_scene_sha256'] and metrics['input_payload'] == capture['payload']
    level_gate = analysis_receipt['task_use_by_output'][stream]
    assert level_gate in ('QUARANTINED_GROSS_SATURATION', 'LIMITED_RESIDUAL_RAILS', 'LEVEL_GATE_NO_RAILS')
    mapping = read(explicit) if explicit else {cid: metrics['output_alignment']}
    alignment = alignment_for(mapping, cid, stream, capture)
    return alignment, identity_binding(evidence), identity_binding(explicit) if explicit else None, level_gate


def dry_scene(control):
    source = control['source']
    return {'case_id': control['control_id'], 'family_id': 'DRY', 'split': 'development',
            'task_scoring_allowed': True, 'transcript_valid': True, 'all_speaker_reference_complete': True,
            'sample_rate_hz': 16000, 'duration_s': source['samples'] / 16000,
            'segments': [{'kind': 'utterance', 'source_id': source['source_id'],
                          'speaker_key': source['identity'], 'source_start_sample': 0,
                          'source_stop_sample': source['samples'], 'transcript': source['transcript'],
                          'dataset': source['dataset'], 'quality_partition': source.get('quality_partition')}],
            'target_references': [], 'overlap_intervals': []}


def analyze_s45(session, scene, input_path, alignment, *, kind):
    scene = copy.deepcopy(scene)
    scene['transcript_valid'] = bool(scene.get('transcript_valid') and scene.get('all_speaker_reference_complete'))
    scene['overlap'] = bool(scene.get('overlap_intervals'))
    metrics = analyze_scene(session, scene, audio_path=input_path,
                            alignment_offset_s=alignment['alignment_offset_s'] if alignment else 0.0)
    metrics['schema_version'] = 'jp_s45_h2_analysis_v1'
    metrics['reference_scope'] = {'all_speaker_reference_complete': scene['all_speaker_reference_complete'],
                                'transcript_valid': scene['transcript_valid'], 'scheduled_overlap': scene['overlap'],
                                'reserve_task_scored': False, 'kind': kind}
    if not scene['all_speaker_reference_complete']:
        metrics['text']['status'] = 'LIMITED'
        metrics['text']['reason'] = 'Untranscribed or uncertain speech in real ambient component; all-speaker WER/CER unavailable'
        metrics['speaker'].pop('reference_turn_evidence', None)
        metrics['reference_scope']['speaker_turn_scores'] = 'LIMITED_UNANNOTATED_AMBIENT_SPEECH'
        targets = sorted(scene.get('target_references', []), key=lambda r: r['start_sample'])
        if targets:
            target = score_text(' '.join(r['transcript'] for r in targets), metrics['text']['hypothesis_normalized'],
                                duration_s=metrics['text']['duration_s'], overlap=scene['overlap'], transcript_valid=True)
            target['status'] = 'LIMITED_TARGET_REFERENCE_ONLY'
            target['scope'] = 'Whole mixed-output hypothesis against annotated target reference; ambient speech can appear as insertions. Never pool with ordinary all-speaker WER.'
            metrics['target_only_text'] = target
    if alignment:
        metrics['source_to_output_turn_scoring'] = {'status': 'DESCRIPTIVE_FILE_SUPPORT_ONLY', **alignment}
    elif kind == 'dry':
        metrics['source_to_output_turn_scoring'] = {'status': 'DRY_NATIVE_FILE_SUPPORT', 'alignment_offset_s': 0.0,
            'scope': 'Whole native source-file bounds; no phonetic word timing or transport latency.'}
    else:
        metrics['speaker'].pop('reference_turn_evidence', None)
        metrics['source_to_output_turn_scoring'] = {'status': 'LIMITED', 'reason': 'No independently qualified processed-output alignment; no nominal delay invented'}
    strata = collections.Counter((s.get('dataset'), s.get('quality_partition')) for s in scene['segments'] if s['kind'] == 'utterance')
    metrics['source_strata'] = [{'dataset': k[0], 'quality_partition': k[1], 'scheduled_utterances': n} for k, n in sorted(strata.items(), key=str)]
    metrics['family_id'] = scene['family_id']
    return metrics


def verify_native_completion(session, input_path):
    summary = read(session / 'session_summary.json')
    assert summary['state'] == 'COMPLETED' and 'reconstruction_provenance' not in summary
    events = [json.loads(line) for line in (session / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    assert sum(e['event_type'] == 'session_completed' for e in events) == 1
    assert not any(e['event_type'] in ('failure', 'session_stopped') for e in events)
    telemetry = summary['telemetry']
    for key in ('audio_frames_dropped', 'portaudio_input_overflows', 'raw_capture_reserve_failures'):
        assert telemetry.get(key, 0) == 0
    spools = sorted(session.glob('*.pcm16'))
    assert len(spools) == 1, 'Expected one native PCM16 journal'
    original = journal_audio(input_path)
    expected = (original * 32768).astype('<i2').tobytes()
    assert spools[0].read_bytes() == expected, 'Native journal does not contain exact complete input PCM16'
    return {'native_summary': True, 'unique_completion_event': True,
            'exact_full_pcm16_samples': len(original), 'journal': identity_binding(spools[0]),
            'tail_scope': 'Full input journal verified; final analysis hop can precede file end. No decision is invented for the short final tail.'}


def counts():
    result = {'intended_output_jobs': 48, 'maximum_dry_jobs': 24,
              'output_jobs_started': 0, 'output_jobs_complete': 0, 'output_jobs_quarantined': 0,
              'output_job_records': 0, 'dry_jobs_started': 0, 'dry_jobs_complete': 0}
    for kind, root, pattern in [('output', REPORT / 'h2', '*/*/run_receipt.json'), ('dry', REPORT / 'h2_dry', '*/run_receipt.json')]:
        for p in root.glob(pattern):
            status = read(p).get('status')
            if kind == 'output':
                result['output_job_records'] += 1
                result['output_jobs_quarantined'] += status == 'QUARANTINED'
            assert status != 'QUARANTINED' or kind == 'output'
            result[kind + '_jobs_started'] += status != 'QUARANTINED'
            result[kind + '_jobs_complete'] += status == 'COMPLETE'
    assert result['output_jobs_started'] <= LIMITS['H2_outputs'] and result['dry_jobs_started'] <= LIMITS['dry_jobs']
    assert result['output_job_records'] <= 48
    result['output_jobs_pending'] = 48 - result['output_job_records']
    result['output_jobs_failed_or_incomplete'] = result['output_jobs_started'] - result['output_jobs_complete']
    return result


def record_quarantine(job, identity, key, analysis_key):
    """Retain an intended output row without opening its model/adapter root."""
    folder = job['folder']; folder.mkdir(parents=True, exist_ok=True)
    receipt_path = folder / 'run_receipt.json'
    if receipt_path.exists():
        prior = read(receipt_path)
        assert prior['job_key'] == key and prior['status'] == 'QUARANTINED'
        assert prior['analysis_identity'] == analysis_key, 'Changed quarantine evidence requires explicit diagnosis'
        identity_binding(folder / 'metrics.json', prior['metrics_binding']['sha256'])
        return
    assert not job['payload_root'].exists(), 'Quarantine cannot hide an existing model payload'
    metrics = {'schema_version': 'jp_s45_h2_analysis_v1', 'state': 'NOT_RUN_QUARANTINED',
               'case_id': job['id'], 'stream': job['stream'], 'kind': 'outputs',
               'level_gate': job['level_gate'], 'model_invocations': 0,
               'text': {'status': 'QUARANTINED', 'wer': None, 'cer': None,
                        'reason': 'Gross saturation in preserved raw output; no task model or reference denominator scored'},
               'fixed_host_gain': job['gain'], 'analysis_provenance': job['analysis_provenance']}
    save(folder / 'metrics.json', metrics)
    save(receipt_path, {'schema': 'jp_s45_h2_job_v1', 'status': 'QUARANTINED', 'job_key': key,
                        'identity': identity, 'kind': 'outputs', 'case_id': job['id'], 'stream': job['stream'],
                        'created_utc': now(), 'raw_audio': job['raw'], 'input_provenance': job['input_provenance'],
                        'level_gate': job['level_gate'], 'model_invocations': 0,
                        'labels_or_transcripts_sent_to_model': False, 'analysis_identity': analysis_key,
                        'metrics_binding': identity_binding(folder / 'metrics.json')})


def run(*, kind='outputs', cases=None, control_ids=None, alignment_json=None, validate_only=False, timeout_s=240):
    manifest, scenes, sentinel_ids = scene_context()
    dry_plan = prepare_plans()
    policy_path = REPORT / 'OUTPUT_LEVEL_POLICY.json'
    policy = read(policy_path)
    assert policy['frozen'] is True and read(REPORT / 'INITIALIZATION_POLICY.json')['frozen'] is True
    assert policy['fixed_host_gain'] == {'O0': 1.4125375446227544, 'O1': 1.0}
    baseline = baseline_contract()
    code = [identity_binding(SIM / 'scripts' / n) for n in CODE_NAMES] + [identity_binding(H2 / 'app/scoring/wer.py')]
    contract = {'schema': 'jp_s45_h2_execution_contract_v1', 'baseline': baseline, 'code': code,
                'scene_manifest': identity_binding(BANK / 'SCENE_MANIFEST.json'),
                'sentinel_plan': identity_binding(SENTINELS), 'dry_plan': identity_binding(DRY_PLAN),
                'output_policy': identity_binding(policy_path), 'limits': {'output_jobs': 48, 'dry_jobs': 24},
                'reserve_jobs': 0, 'scientific_policy_changed': False}
    jobs = []
    if kind == 'outputs':
        assert not control_ids
        ids = cases or sentinel_ids
        assert len(ids) == len(set(ids)) and set(ids) <= set(sentinel_ids), 'Only predeclared development sentinel IDs'
        selected = accepted_for(ids, scenes, policy)
        for cid in ids:
            for stream in STREAMS:
                selection = selected[cid]
                raw = identity_binding(selection['folder'] / (stream + '.wav'), selection['capture']['output_audio'][stream]['sha256'])
                align, analysis_binding, explicit_binding, level_gate = load_alignment(alignment_json, cid, stream, selection)
                jobs.append({'id': cid, 'stream': stream, 'scene': scenes[cid], 'raw': raw,
                             'gain': policy['fixed_host_gain'][stream], 'folder': REPORT / 'h2' / cid / stream,
                             'payload_root': PAYLOAD / 'h2' / cid / stream, 'alignment': align,
                             'level_gate': level_gate,
                             'input_provenance': {'case_result': selection['case_result_binding'], 'accepted_record': selection['selection_record']},
                             'analysis_provenance': {'audio_metrics': analysis_binding, 'alignment_mapping': explicit_binding}})
    else:
        assert kind == 'dry' and not cases
        controls = {r['control_id']: r for r in dry_plan['identity']['controls']}
        ids = control_ids or list(controls)
        assert len(ids) == len(set(ids)) and set(ids) <= set(controls)
        for cid in ids:
            c = controls[cid]
            src = c['source']['decoded_16k_binding']
            jobs.append({'id': cid, 'stream': 'DRY', 'scene': dry_scene(c),
                         'raw': identity_binding(src['path'], src['sha256']), 'gain': c['fixed_gain_scalar'],
                         'folder': REPORT / 'h2_dry' / cid, 'payload_root': PAYLOAD / 'h2_dry' / cid,
                         'alignment': None, 'input_provenance': {'dry_control': c}, 'analysis_provenance': {}})
    if validate_only:
        print(json.dumps({'status': 'VALIDATED_NO_MODEL_JOBS', 'kind': kind, 'intended_jobs': len(jobs),
                          'quarantined_jobs': sum(j.get('level_gate') == 'QUARANTINED_GROSS_SATURATION' for j in jobs),
                          'baseline': baseline['durability_fix']}, indent=2))
        return
    release = execution_release()
    target = REPORT / 'h2'; target.mkdir(exist_ok=True)
    import msvcrt
    with (target / 'runner.lock').open('a+b') as lease:
        lease.seek(0)
        if not lease.read(1): lease.write(b'0'); lease.flush()
        lease.seek(0); msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
        started, status = time.monotonic(), 'FAILED_OR_INTERRUPTED'
        try:
            contract_path = target / 'execution_contract.json'
            if contract_path.exists(): assert read(contract_path) == contract, 'Frozen execution contract changed'
            else: save(contract_path, contract)
            with Progress('H2_' + kind, len(jobs)) as progress:
                for job in jobs:
                    folder, payload = job['folder'], job['payload_root']
                    root, adapter_path = payload / 'empty_data', payload / 'fixed_gain_input.wav'
                    receipt_path = folder / 'run_receipt.json'
                    identity = {'contract_sha256': stable_hash(contract), 'kind': kind, 'id': job['id'],
                                'stream': job['stream'], 'raw_audio_sha256': job['raw']['sha256'],
                                'gain_scalar': job['gain'], 'input_provenance': job['input_provenance']}
                    key = stable_hash(identity)
                    analysis_key = stable_hash({'alignment': job['alignment'], 'provenance': job['analysis_provenance'], 'code': code})
                    progress.case = job['id'] + '/' + job['stream']
                    if job.get('level_gate') == 'QUARANTINED_GROSS_SATURATION':
                        record_quarantine(job, identity, key, analysis_key)
                        progress.done += 1; progress.detail = 'Quarantined grossly saturated stream; zero model invocations'; progress.emit()
                        save(target / 'run_summary.json', {**counts(), 'updated_utc': now(), 'status': 'RUNNING'})
                        continue
                    folder.mkdir(parents=True, exist_ok=True); payload.mkdir(parents=True, exist_ok=True)
                    session = None
                    if receipt_path.exists():
                        receipt = read(receipt_path)
                        assert receipt['job_key'] == key, 'Existing job has incompatible identity'
                        assert receipt.get('exit_code') == 0, 'Prior invocation did not report success; diagnose without blind retry'
                        session = completed_session(root)
                        assert session is not None, 'Prior invocation has no native complete summary; preserve and diagnose'
                        identity_binding(adapter_path, receipt['adapter']['output_binding']['sha256'])
                        if receipt['status'] == 'COMPLETE':
                            identity_binding(session / 'session_summary.json', receipt['session_summary_binding']['sha256'])
                            identity_binding(session / 'events.jsonl', receipt['events_binding']['sha256'])
                            if receipt['analysis_identity'] == analysis_key:
                                identity_binding(folder / 'metrics.json', receipt['metrics_binding']['sha256'])
                                progress.done += 1; progress.detail = 'Reused compatible complete job'; progress.emit(); continue
                    else:
                        if not launch_allowed(timeout_s):
                            status = 'PARTIAL_TIME_BUDGET'; break
                        if (REPORT / 'STOP_REQUEST.json').exists():
                            status = 'PARTIAL_STOP_REQUEST'; break
                        check_storage(); execution_release()
                        current_counts = counts()
                        assert current_counts['output_jobs_started' if kind == 'outputs' else 'dry_jobs_started'] < (48 if kind == 'outputs' else 24)
                        assert not root.exists() or not any(root.iterdir()), 'Unreceipted nonempty model root'
                        adapter = fixed_gain_copy(job['raw']['path'], adapter_path, job['gain'])
                        root.mkdir(exist_ok=True)
                        argv = [str(EDGE_PYTHON), '-m', 'app.edge_speech_pipeline', 'file', str(adapter_path.resolve()), '--accelerated']
                        receipt = {'schema': 'jp_s45_h2_job_v1', 'status': 'STARTED', 'job_key': key, 'identity': identity,
                                   'kind': kind, 'case_id': job['id'], 'stream': job['stream'], 'created_utc': now(),
                                   'raw_audio': job['raw'], 'adapter': adapter, 'argv': argv, 'cwd': str(H2),
                                   'isolated_data_root': str(root), 'initial_profile_files': 0,
                                   'labels_or_transcripts_sent_to_model': False, 'external_asset_hash_passes': 0,
                                   'execution_release': release, 'input_provenance': job['input_provenance']}
                        save(receipt_path, receipt)
                        env = single_thread_env(); env['EDGE_SPEECH_DATA_ROOT'] = str(root)
                        env['PYTHONDONTWRITEBYTECODE'] = '1'; env.pop('EDGE_SPEECH_ASSET_ROOT', None)
                        process, model_start = None, time.monotonic()
                        try:
                            with (folder / 'stdout.jsonl').open('wb') as stdout, (folder / 'stderr.txt').open('wb') as stderr:
                                process = subprocess.Popen(argv, cwd=H2, env=env, stdout=stdout, stderr=stderr,
                                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                                receipt['owned_process_pid'] = process.pid; save(receipt_path, receipt)
                                receipt['exit_code'] = process.wait(timeout=timeout_s)
                            receipt['model_wall_s'] = time.monotonic() - model_start
                            # Persist actual child completion before parsing downstream artifacts.
                            receipt['model_exited_utc'] = now(); save(receipt_path, receipt)
                            assert receipt['exit_code'] == 0, 'CLI failed; do not silently rerun'
                            session = completed_session(root)
                            assert session is not None, 'No complete native session summary'
                            receipt['completion_evidence'] = verify_native_completion(session, adapter_path)
                        except BaseException as exc:
                            if process is not None and process.poll() is None:
                                process.terminate()
                                try: process.wait(timeout=10)
                                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
                            receipt.update(status='FAILED_OR_INTERRUPTED', error=repr(exc), ended_utc=now(), model_wall_s=time.monotonic()-model_start)
                            save(receipt_path, receipt); raise
                        receipt.update(status='MODEL_COMPLETED', session_dir=str(session), model_completed_utc=now())
                        save(receipt_path, receipt)
                    receipt['completion_evidence'] = verify_native_completion(session, adapter_path)
                    metrics = analyze_s45(session, job['scene'], adapter_path, job['alignment'], kind=kind)
                    assert metrics['state'] == 'COMPLETED' and not metrics['failure_events']
                    metrics.update(case_id=job['id'], stream=job['stream'], kind=kind,
                                   raw_output_rail_samples=receipt['adapter']['source_rail_samples'], fixed_host_gain=job['gain'],
                                   analysis_provenance=job['analysis_provenance'])
                    save(folder / 'metrics.json', metrics)
                    receipt.update(status='COMPLETE', session_dir=str(session), completed_utc=now(),
                                   metrics_binding=identity_binding(folder / 'metrics.json'),
                                   session_summary_binding=identity_binding(session / 'session_summary.json'),
                                   events_binding=identity_binding(session / 'events.jsonl'), analysis_identity=analysis_key,
                                   model_success_has_internal_asset_validation=True)
                    receipt.pop('error', None); save(receipt_path, receipt)
                    progress.done += 1; progress.detail = 'Native summary complete and analyzed'; progress.emit()
                    save(target / 'run_summary.json', {**counts(), 'updated_utc': now(), 'status': 'RUNNING'})
                else:
                    status = 'REQUESTED_JOBS_COMPLETE'
        finally:
            save(target / 'run_summary.json', {**counts(), 'updated_utc': now(), 'status': status,
                                             'invocation_wall_s': time.monotonic()-started, 'reserve_jobs': 0})
            lease.seek(0); msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)
    print(json.dumps(read(target / 'run_summary.json'), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-plans', action='store_true', help='Freeze dry controls before any H2 jobs; no model execution')
    parser.add_argument('--kind', choices=['outputs', 'dry'], default='outputs')
    parser.add_argument('--cases', nargs='+', help='Predeclared sentinel IDs; both O0/O1')
    parser.add_argument('--control-ids', nargs='+', help='Predeclared DRY_nn IDs')
    parser.add_argument('--alignment-json', help='Optional explicit mapping; preserve identical mapping on resume')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--timeout-s', type=float, default=240)
    args = parser.parse_args()
    if args.prepare_plans:
        print(json.dumps({'status': 'PLANS_FROZEN_NO_MODELS', 'controls': prepare_plans()['count']}, indent=2))
    else:
        assert math.isfinite(args.timeout_s) and 65 < args.timeout_s <= 600
        run(kind=args.kind, cases=args.cases, control_ids=args.control_ids,
            alignment_json=args.alignment_json, validate_only=args.validate_only, timeout_s=args.timeout_s)


if __name__ == '__main__':
    main()
