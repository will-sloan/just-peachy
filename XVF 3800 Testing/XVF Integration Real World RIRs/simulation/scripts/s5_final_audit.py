"""Independent S5 native/provenance/closure audit. No model or hardware execution."""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time

import numpy as np
import soundfile as sf

from s5_common import BANK, H2, PAYLOAD, PRIOR, REPORT, REPO, RUN_ID, SIM, GAINS, MANIFEST_SHA
from s45_native_review import Evidence, json_stream, verify_audio, verify_event_metrics
from s45_final_audit import powershell_json, ssd_and_space

RIR_SHA = '468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546'
V10_SHA = 'b9427c76a98965ab418ef252ec0d480b979945d85d4aa0e4e2de6dd41514a67b'
S0_SHA = 'f7620b82685a34a002a7b2a93365c58493ac9265d07c1dd52f761939ab8eda42'
FIX_SHA = 'e805a9c8fbc4fa87a84c859fb4b05bbf01d89097502492b8d4077f4f87773166'
POLICY_KEYS = ('identity_score_threshold', 'identity_margin_threshold', 'identity_minimum_evidence_sec', 'clustering_threshold')
CODE_NAMES = ('s5_final_audit.py', 'test_s5_final_audit.py', 'README_S5_FINAL_AUDIT.md',
              's45_native_review.py', 's45_final_audit.py', 's5_common.py')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str).encode()).hexdigest()


def same_binding(a, b):
    return Path(a['path']).resolve() == Path(b['path']).resolve() and a['sha256'] == b['sha256'] and (
        'bytes' not in a or 'bytes' not in b or a['bytes'] == b['bytes'])


def within(path, directory):
    return Path(path).resolve().is_relative_to(Path(directory).resolve())


def guard(cid, scenes):
    scene = scenes.get(cid)
    if scene is None or scene.get('split') != 'development' or scene.get('task_scoring_allowed') is not True:
        raise PermissionError('Reserve/unknown task path refused BEFORE open: '+str(cid))
    return scene


def reference(ev, value):
    ev.ref(value)
    return ev.read(value['path'], value['sha256'])


def validate_manifest(manifest, bank, contract, *, expected_scenes=180):
    scenes = {s['case_id']: s for s in bank['scenes']}
    require(len(scenes) == len(bank['scenes']), 'Duplicate canonical scene IDs')
    allowed = sorted(k for k, s in scenes.items() if s.get('split') == 'development' and s.get('task_scoring_allowed') is True)
    require(len(allowed) == expected_scenes, 'Development denominator changed')
    jobs = manifest['jobs']
    expected = [(cid, out) for i, cid in enumerate(allowed) for out in (('O0', 'O1') if i % 2 == 0 else ('O1', 'O0'))]
    require([(j['case_id'], j['stream']) for j in jobs] == expected, 'Exact pair inventory/counterbalanced order changed')
    require(manifest['development_ids'] == allowed and manifest['requested'] == 2*expected_scenes and manifest['reserve_jobs'] == 0,
            'Manifest denominator/reserve declaration differs')
    for i, job in enumerate(jobs):
        scene = guard(job['case_id'], scenes)
        identity = {'contract_sha256': stable(contract), 'case_id': job['case_id'], 'stream': job['stream'],
                    'raw_audio_sha256': job['raw_audio']['sha256'], 'gain_scalar': GAINS[job['stream']],
                    'input_case_result_sha256': job['input_provenance']['case_result']['sha256'], 'scene_reference_sha256': stable(scene)}
        require(job['identity'] == identity and job['job_key'] == stable(identity), 'Job/reference/recipe identity mismatch')
        require(job['gain'] == GAINS[job['stream']] and job['order_index'] == i, 'Gain/order index differs')
        require(job['pair_order'] == list(expected[2*(i//2)+k][1] for k in (0, 1)), 'Pair order differs')
        if expected_scenes == 180:
            require(Path(job['report_dir']).resolve() == (REPORT/'h2'/job['case_id']/job['stream']).resolve(), 'Unexpected job report root')
            require(Path(job['payload_root']).resolve() == (PAYLOAD/'h2'/job['case_id']/job['stream']).resolve(), 'Unexpected payload root')
    reused = [j for j in jobs if j.get('reuse')]
    require(manifest['compatible_reuse'] == len(reused) and manifest['new_planned'] == len(jobs)-len(reused), 'Reuse/new denominator mismatch')
    if expected_scenes == 180:
        require(len(reused) == 48 and len(jobs)-len(reused) == 312, 'Expected48 reused/312 fresh planned')
    return scenes, jobs


def verify_baseline(ev, contract):
    baseline = contract['baseline']
    require(baseline['baseline_manifest']['sha256'] == S0_SHA and baseline['durability_fix']['sha256'] == FIX_SHA,
            'S0 or active v3 durability authority differs')
    s0, fix = reference(ev, baseline['baseline_manifest']), reference(ev, baseline['durability_fix'])
    require(fix['schema'] == 'jp_s45_h2_durability_fix_v3' and fix['status'] == 'PASS_MODEL_FREE_REGRESSIONS', 'Unqualified lifecycle fix')
    require(baseline['python'] == s0['python'] and baseline['mode'] == 'file --accelerated; CPU; fresh independent session', 'Runtime/provider contract differs')
    science = {k: v for k, v in s0['config'].items() if k not in ('session_root', 'profile_root')}
    require(science == fix['scientific_config'] == baseline['scientific_config'], 'Scientific config changed')
    require(len(science['assets']) == len({a['component_id'] for a in science['assets']}) == 8, 'Eight distinct baseline assets required')
    sources = {str(Path(s['path']).resolve()): s for s in baseline['source_identities']}
    changes = {str(Path(s['path']).resolve()): s for s in fix['changed_sources']}
    require({Path(k).name for k in changes} == {'runtime.py', 'cli.py'}, 'Unauthorized baseline change set')
    for old in s0['source_bindings']:
        path = str(Path(old['path']).resolve()); expected = old['sha256']
        if path in changes:
            change = changes[path]
            require(change['before_sha256'] == expected, 'Durability original source does not match S0')
            ev.ref(change['original_backup']); expected = change['after']['sha256']
        require(path in sources and sources[path]['sha256'] == expected, 'Current source is not S0 plus authorized v3 lifecycle fix')
    for source in baseline['source_identities'] + contract['code']:
        ev.ref(source)
    historical = reference(ev, contract['historical_contract'])
    require(historical['baseline'] == baseline, 'Historical and current scientific baseline differ')
    return science, s0, historical


def context(ev):
    run = ev.read(REPORT/'run_manifest.json')
    require(run['run_id'] == RUN_ID and run['hardware_invocations'] == 0 and run.get('protocol_frozen_utc'), 'Run identity/protocol/hardware declaration differs')
    contract = reference(ev, run['contract']); manifest = reference(ev, run['jobs'])
    require(Path(run['contract']['path']).resolve() == (REPORT/'execution_contract.json').resolve() and
            Path(run['jobs']['path']).resolve() == (REPORT/'JOB_MANIFEST.json').resolve(), 'Current contract/manifest authority path differs')
    for key in ('scoring_protocol', 'decision_protocol', 'recipes'):
        ev.ref(contract[key])
        require(Path(contract[key]['path']).resolve().parent == REPORT.resolve(), 'Protocol path outside current report')
    require(contract['scene_manifest']['sha256'] == MANIFEST_SHA and Path(contract['scene_manifest']['path']).resolve() == (BANK/'SCENE_MANIFEST.json').resolve(), 'Canonical manifest authority changed')
    bank = reference(ev, contract['scene_manifest'])
    require(bank['validation']['status'] == 'PASS' and len(bank['scenes']) == 240, 'Frozen canonical bank is not PASS240')
    scenes, jobs = validate_manifest(manifest, bank, contract)
    science, s0, historical = verify_baseline(ev, contract)
    accepted = reference(ev, contract['accepted_selection'])
    selected = {s['case_id']: s for s in accepted['accepted']}
    require(accepted['accepted_count'] == len(selected) == 240 and accepted['reserve_task_scored'] is False, 'Historical accepted selection changed')
    for source in (bank['sources_binding'], bank['noise_binding'], bank['legacy_development_sources_binding']):
        ev.ref(source)
    policy = ev.read(PRIOR/'OUTPUT_LEVEL_POLICY.json')
    recipes = reference(ev, contract['recipes'])
    require(recipes['fixed_host_gain'] == GAINS == policy['fixed_host_gain'] and recipes['prior_frozen_capture_policy'] == policy and
            recipes['gain_once_only'] is True and recipes['raw_audio_preserved'] is True, 'Output recipe preservation differs')
    return {'run': run, 'contract': contract, 'bank': bank, 'manifest': manifest, 'scenes': scenes,
            'jobs': jobs, 'science': science, 's0': s0, 'historical': historical, 'selected': selected, 'policy': policy}


def unexpected_task_paths(ctx):
    """Inventory names only; never open an unexpected/reserve task file."""
    expected = {(j['case_id'], j['stream']) for j in ctx['jobs']}
    unexpected = []
    for base in (REPORT/'h2', PAYLOAD/'h2'):
        if not base.exists():
            continue
        for case in base.iterdir():
            if not case.is_dir():
                continue
            for stream in case.iterdir():
                if stream.is_dir() and (case.name, stream.name) not in expected:
                    unexpected.append(str(stream))
    for base in (REPORT/'text_metrics', REPORT/'support/outputs'):
        if base.exists():
            for case in base.iterdir():
                if case.is_dir() and case.name not in ctx['manifest']['development_ids']:
                    unexpected.append(str(case))
    require(not unexpected, 'Unapproved task directory names refused before read: '+repr(unexpected))


def verify_capture(ev, ctx, job):
    scene = guard(job['case_id'], ctx['scenes'])
    selected = ctx['selected'][job['case_id']]
    selection = job['input_provenance']['accepted_record']
    require(all(selection[k] == selected[k] for k in selection), 'Job accepted record differs from frozen selection')
    require(selection['split'] == 'development' and selection['task_scoring_allowed'] is True and
            selection['audio_valid'] is True and selection['telemetry_valid'] is True, 'Unqualified accepted development capture')
    cb = job['input_provenance']['case_result']
    require(same_binding(cb, selected['case_result']), 'Selected case receipt mismatch')
    capture = reference(ev, cb)
    require(capture['case_id'] == job['case_id'] and capture['input_scene_sha256'] == scene['canonical_audio']['sha256'] == selection['input_scene_sha256'], 'Capture/source identity differs')
    require(capture['status'] == capture['audio_integrity_status'] == capture['telemetry_status'] == capture['payload']['status'] == 'PASS', 'Accepted transport is not PASS')
    require(capture['recipe'] == ctx['policy']['hardware_recipe'] and capture['final_recipe_capture'] is True and capture['reserve_task_scored'] is False,
            'Capture recipe or reserve prohibition changed')
    require(same_binding(job['raw_audio'], capture['output_audio'][job['stream']]), 'Raw audio does not match accepted output')
    require(Path(job['raw_audio']['path']).resolve() == (Path(selection['folder'])/(job['stream']+'.wav')).resolve(), 'Raw output path differs from selected capture')
    analysis = reference(ev, job['analysis_provenance']['audio_metrics'])
    require(analysis['case_id'] == job['case_id'], 'Saved output alignment analysis belongs to another case')
    return capture


def telemetry_contract(summary, events, metrics, stdout, science, adapter):
    """Stricter than the runtime helper: explicit counters, terminal cursors and policy shape."""
    result = verify_event_metrics(events, summary, metrics, stdout)
    require(summary['schema_version'] == 'edge-speech-session.v1', 'Unknown native summary schema')
    require(summary['xvf']['result_effects_enabled'] is False and events[0]['payload']['xvf_result_effects_enabled'] is False, 'Unexpected XVF result effect in offline H2')
    require(summary['assets'] == [{'component_id': a['component_id'], 'sha256': a['sha256']} for a in science['assets']], 'Native8 asset identities differ')
    require(summary['scientific_policy'] == {k: science[k] for k in POLICY_KEYS}, 'Exported policy is missing or changed')
    tele = summary['telemetry']; duration = adapter['duration_s']; samples = adapter['samples']
    require(tele['state'] == 'COMPLETED', 'Native telemetry terminal state differs')
    for key in ('source_duration_sec', 'asr_cursor_sec', 'speaker_cursor_sec'):
        require(math.isfinite(tele[key]) and abs(tele[key]-duration) < 1e-6, 'Incomplete native source cursor: '+key)
    require(abs(duration-samples/16000) < 1e-10, 'Adapter sample/duration mismatch')
    analyzed, tail = tele['speaker_analyzed_through_sec'], tele['speaker_unanalyzed_short_tail_sec']
    require(0 <= tail < .25+1e-8 and abs(analyzed+tail-duration) < 1e-6 and abs(analyzed/.25-round(analyzed/.25)) < 1e-7,
            'Short final analysis tail bookkeeping differs')
    return {**result, 'decoded_samples': samples, 'decoded_audio_s': duration, 'speaker_unanalyzed_short_tail_s': tail}


def verify_native(ev, ctx, job, native, native_path, *, reused):
    scene = guard(job['case_id'], ctx['scenes'])
    require(native['status'] == 'COMPLETE' and native['exit_code'] == 0 and not native.get('error') and not native.get('summary_recovery_receipt'), 'No native successful completion')
    require(native['case_id'] == job['case_id'] and native['stream'] == job['stream'], 'Native output/case differs')
    require(native['raw_audio'] == job['raw_audio'] and native['adapter']['gain_scalar'] == job['gain'], 'Native raw/gain identity differs')
    require(native['input_provenance'] == job['input_provenance'], 'Native input provenance differs')
    if reused:
        expected_identity = {'contract_sha256': stable(ctx['historical']), 'kind': 'outputs', 'id': job['case_id'],
                             'stream': job['stream'], 'raw_audio_sha256': job['raw_audio']['sha256'],
                             'gain_scalar': job['gain'], 'input_provenance': job['input_provenance']}
        require(native['schema'] == 'jp_s45_h2_job_v1' and native['identity'] == expected_identity and native['job_key'] == stable(expected_identity), 'Historical identity/config differs')
        root = Path(native['isolated_data_root'])
        require(root.parent == Path(native['adapter']['output_binding']['path']).parent and within(root, Path('G:/Just_Peachy_S4_5/20260909T031300Z/h2')/job['case_id']/job['stream']), 'Historical session root differs')
    else:
        require(native['schema'] == 'jp_s5_native_attempt_v1' and native['identity'] == job['identity'] and native['job_key'] == job['job_key'], 'Fresh native identity differs')
        require(native['attempt_number'] in (1, 2), 'Unbounded model attempt')
        root = Path(job['payload_root'])/f"attempt_{native['attempt_number']}"/'empty_data'
        require(Path(native['isolated_data_root']).resolve() == root.resolve(), 'Fresh isolated root differs')
        require(native.get('owned_process_creation_time') is not None, 'Fresh process generation identity missing')
    require(native['initial_profile_files'] == 0 and native['labels_or_transcripts_sent_to_model'] is False and native['model_success_has_internal_asset_validation'] is True,
            'Isolation/truth/asset validation contract missing')
    require(Path(native['cwd']).resolve() == H2.resolve(), 'Native working directory differs')
    ap = native['adapter']['output_binding']; session = Path(native['session_dir']).resolve()
    require(Path(ap['path']).resolve() == (root.parent/'fixed_gain_input.wav').resolve(), 'Explicit adapter path outside isolated job')
    require(within(session, root/'edge_speech_sessions') and session.parent == (root/'edge_speech_sessions').resolve(), 'Session outside exact isolated root')
    require(native['argv'] == [ctx['contract']['baseline']['python'], '-m', 'app.edge_speech_pipeline', 'file', ap['path'], '--accelerated'], 'Explicit accelerated mono file argv differs')
    for key, filename in [('session_summary_binding', 'session_summary.json'), ('events_binding', 'events.jsonl')]:
        require(Path(native[key]['path']).resolve() == session/filename, 'Native receipt points outside its session')
    require(Path(native['metrics_binding']['path']).resolve().parent == Path(native_path).resolve().parent, 'Native metrics path not beside receipt')
    summary = reference(ev, native['session_summary_binding']); metrics = reference(ev, native['metrics_binding'])
    events_binding = ev.ref(native['events_binding'])
    events = [json.loads(line) for line in Path(events_binding['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    ev.ref(native['events_binding'])
    stdout_path = Path(native_path).parent/'stdout.jsonl'; ev.bind(stdout_path)
    stdout = json_stream(stdout_path.read_text(encoding='utf-8-sig')); ev.bind(stdout_path)
    source_event = next((e for e in events if e['event_type'] == 'source_started'), None)
    require(source_event is not None and source_event['payload']['mode'] == 'wav' and
            Path(source_event['payload']['path']).resolve() == Path(ap['path']).resolve() and
            source_event['payload']['native_sample_rate'] == source_event['payload']['pipeline_sample_rate'] == 16000 and
            source_event['payload']['channels'] == 1, 'Native event source differs from exact adapter')
    require(Path(summary['telemetry']['session_dir']).resolve() == session and
            Path(events[0]['payload']['session_dir']).resolve() == session, 'Native session/event directory mismatch')
    raw_binding, adapter_binding = ev.ref(job['raw_audio']), ev.ref(ap)
    with sf.SoundFile(raw_binding['path']) as source:
        require(source.samplerate == 16000 and source.channels == 1 and source.subtype == 'PCM_24', 'Raw preserved output format differs')
        raw = source.read(dtype='float32', always_2d=True)
    with sf.SoundFile(adapter_binding['path']) as source:
        require(source.samplerate == 16000 and source.channels == 1 and source.subtype == 'FLOAT', 'Adapter format differs')
        adapter = source.read(dtype='float32', always_2d=True)
    ce = native['completion_evidence']
    require(ce['native_summary'] is True and ce['unique_completion_event'] is True and ce['exact_full_pcm16_samples'] == len(adapter), 'Recorded completion contract differs')
    journal = ev.ref(ce['journal']); jp = Path(journal['path']).resolve()
    require(jp.parent == session and list(session.glob('*.pcm16')) == [jp] and journal['bytes'] == 2*len(adapter), 'Exact full native journal absent/ambiguous')
    pcm = jp.read_bytes(); verify_audio(raw, adapter, pcm, job['gain']); ev.ref(ce['journal']); ev.ref(ap); ev.ref(job['raw_audio'])
    require(native['adapter']['samples'] == len(adapter) and native['adapter']['channels'] == 1 and native['adapter']['rate_hz'] == 16000, 'Adapter shape metadata differs')
    require(metrics['case_id'] == job['case_id'] and metrics['stream'] == job['stream'] and metrics['fixed_host_gain'] == job['gain'], 'Metric case/output/gain differs')
    details = telemetry_contract(summary, events, metrics, stdout, ctx['science'], native['adapter'])
    require(metrics['reference_scope']['reserve_task_scored'] is False and metrics['reference_scope']['all_speaker_reference_complete'] == scene['all_speaker_reference_complete'], 'Metric reference/reserve scope differs')
    duration = float(native['model_wall_s'])
    require(math.isfinite(duration) and duration >= 0, 'Recorded model child wall invalid')
    return {'case_id': job['case_id'], 'stream': job['stream'], 'status': 'VERIFIED_NATIVE_COMPLETE',
            'origin': 'reused_s45' if reused else 'fresh_s5', 'native_receipt': ev.bind(native_path),
            'native_summary': native['session_summary_binding'], 'journal': journal, 'model_child_wall_s': duration,
            'owned_process_pid': native['owned_process_pid'], 'owned_process_creation_time': native.get('owned_process_creation_time'),
            'model_exited_utc': native['model_exited_utc'], 'completed_utc': native['completed_utc'], **details}


def job_records(ev, ctx, *, full):
    rows, process_receipts, attempts_inventory = [], [], []
    last_progress = time.monotonic()
    for job in ctx['jobs']:
        guard(job['case_id'], ctx['scenes'])
        folder = Path(job['report_dir']); rp = folder/'run_receipt.json'
        dirs = sorted(folder.glob('attempt_*')) if folder.exists() else []
        require(all(p.is_dir() and p.name in ('attempt_1', 'attempt_2') for p in dirs) and len(dirs) <= 2, 'Unexpected attempt directory/cap')
        attempts = []
        for path in dirs:
            ap = path/'attempt_receipt.json'
            require(ap.exists(), 'Unreceipted attempt directory: '+str(path))
            item = ev.read(ap)
            require(item['job_key'] == job['job_key'] and item['identity'] == job['identity'] and
                    item['case_id'] == job['case_id'] and item['stream'] == job['stream'], 'Attempt identity differs')
            require(item['attempt_number'] == int(path.name[-1]), 'Attempt number differs')
            attempts.append(item); process_receipts.append(item)
            attempts_inventory.append({'case_id': job['case_id'], 'stream': job['stream'], 'attempt': item['attempt_number'],
                                       'status': item['status'], 'receipt': ev.bind(ap), 'exit_code': item.get('exit_code'), 'error': item.get('error')})
        require([a['attempt_number'] for a in attempts] == list(range(1, len(attempts)+1)), 'Attempt sequence gap')
        if not rp.exists():
            rows.append({'case_id': job['case_id'], 'stream': job['stream'], 'status': 'PENDING'}); continue
        wrapper = ev.read(rp)
        require(wrapper['job_key'] == job['job_key'], 'Wrapper job key differs')
        if wrapper['status'] == 'COMPLETE':
            require(wrapper['identity'] == job['identity'], 'Wrapper identity differs')
            reused = bool(job.get('reuse'))
            if reused:
                require(not attempts and wrapper.get('new_model_invocations') == 0 and same_binding(wrapper['reused_receipt'], job['reuse']['receipt']), 'Reused job has changed pointer or fresh invocation')
                native_path = Path(wrapper['reused_receipt']['path']); native = reference(ev, wrapper['reused_receipt'])
                require(native_path.resolve() == (PRIOR/'h2'/job['case_id']/job['stream']/'run_receipt.json').resolve(), 'Historical receipt path differs')
                process_receipts.append(native)
            else:
                require(not wrapper.get('reused_receipt') and attempts, 'Fresh completed job has no bounded attempt')
                matching = [a for a in attempts if a['status'] == 'COMPLETE']
                require(len(matching) == 1 and wrapper == matching[0], 'Wrapper differs from unique successful native attempt')
                require(all(a['status'] == 'FAILED' and a.get('error') for a in attempts[:-1]), 'Retry did not follow preserved failure')
                native = wrapper; native_path = folder/f"attempt_{wrapper['attempt_number']}"/'attempt_receipt.json'
            if full:
                verify_capture(ev, ctx, job)
                rows.append(verify_native(ev, ctx, job, native, native_path, reused=reused))
            else:
                rows.append({'case_id': job['case_id'], 'stream': job['stream'], 'status': 'COMPLETE_METADATA_ONLY', 'origin': 'reused_s45' if reused else 'fresh_s5'})
        elif wrapper['status'] == 'FAILED':
            require(not job.get('reuse') and len(attempts) == 2 and all(a['status'] == 'FAILED' and a.get('error') for a in attempts), 'Terminal failure lacks two preserved failed attempts')
            require(len(wrapper['attempt_receipts']) == 2, 'Terminal failure omits attempt bindings')
            for b, d in zip(wrapper['attempt_receipts'], dirs):
                require(Path(b['path']).resolve() == (d/'attempt_receipt.json').resolve(), 'Failure receipt binds wrong attempt')
                ev.ref(b)
            rows.append({'case_id': job['case_id'], 'stream': job['stream'], 'status': 'VERIFIED_TERMINAL_FAILED', 'receipt': ev.bind(rp)})
        elif wrapper['status'] == 'QUARANTINED':
            require(job['level_gate'] == 'QUARANTINED_GROSS_SATURATION' and wrapper['model_invocations'] == 0 and not attempts, 'Quarantine hides model invocation or wrong frozen level')
            rows.append({'case_id': job['case_id'], 'stream': job['stream'], 'status': 'VERIFIED_QUARANTINED', 'receipt': ev.bind(rp)})
        else:
            rows.append({'case_id': job['case_id'], 'stream': job['stream'], 'status': 'PENDING_'+str(wrapper['status'])})
        if full and (len(rows) == 1 or len(rows) % 30 == 0 or time.monotonic()-last_progress >= 20):
            progress = {'status': 'AUDIT_IN_PROGRESS_NOT_FINAL', 'utc': utc(), 'native_rows_examined': len(rows),
                        'requested': len(ctx['jobs']), 'last_case': job['case_id'], 'last_stream': job['stream']}
            path = REPORT/'FINAL_AUDIT_PROGRESS.json'; temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(progress), encoding='utf-8'); temp.replace(path)
            print(json.dumps(progress), flush=True); last_progress = time.monotonic()
    return rows, process_receipts, attempts_inventory


def conservation(ev, ctx):
    contract = ctx['contract']; workbook = contract['workbook']
    require(workbook['sha256'] == V10_SHA, 'V10 master authority differs')
    ev.ref(workbook)
    rir = ev.bind(SIM/'rir_library/v1/RIR_MANIFEST.json', RIR_SHA)
    review = ev.read(REPORT/'INPUT_COVERAGE_REVIEW.json')
    discrepancy = next((x for x in review['documented_input_discrepancies'] if x['field'] == 'S5 prompt RIR-manifest SHA-256'), None)
    require(discrepancy is not None and discrepancy['established_value'] == RIR_SHA and discrepancy['stated_hex_characters'] == len(discrepancy['stated_value']) == 57,
            'Malformed prompt hash correction is not preserved accurately')
    for path in (workbook['path'], rir['path'], ctx['contract']['scene_manifest']['path']):
        rows = [x for x in review['input_bindings'] if Path(x['path']).resolve() == Path(path).resolve()]
        require(len(rows) == 1, 'Coverage review authority binding missing')
        ev.ref(rows[0])
    correction = ev.read(REPORT/'PREFLIGHT_CORRECTION.json')
    require(correction['new_models_before_correction'] == correction['new_full_panel_comparisons_before_correction'] == 0 and correction['scientific_protocol_changed'] is False,
            'Prelaunch rail assertion correction declaration changed')
    old_key = correction['prior_contract_sha256']
    require(re.fullmatch('[a-f0-9]{64}', old_key), 'Malformed archived preflight identity')
    archived = ev.read(REPORT/'preflight_archive'/('execution_contract_'+old_key+'.json'))
    require(stable(archived) == old_key and archived['baseline'] == contract['baseline'] and archived['scoring_protocol'] == contract['scoring_protocol'],
            'Preflight correction changed science/protocol or lost its original contract')
    return {'status': 'PASS', 'V10': ev.ref(workbook), 'RIR_manifest': rir, 'S0_baseline': ev.ref(contract['baseline']['baseline_manifest']),
            'v3_lifecycle_fix': ev.ref(contract['baseline']['durability_fix']),
            'malformed_prompt_sha_documentation': ev.bind(REPORT/'INPUT_COVERAGE_REVIEW.json'),
            'preflight_rail_assertion_correction': ev.bind(REPORT/'PREFLIGHT_CORRECTION.json'),
            'archived_preflight_contract': ev.bind(REPORT/'preflight_archive'/('execution_contract_'+old_key+'.json')),
            'scope': 'Current manifest/master/config/source bytes and all reused native receipts are bound. No121-wave or model-weight rehash; previous qualified conservation evidence remains historical.'}


def validate_access(row, allowed, *, protocol_sha=None):
    """Validate recorded application guards, without pretending this is OS access tracing."""
    zeros = ('reserve_task_accesses', 'reserve_task_model_accesses', 'reserve_performance_scoring_accesses',
             'reserve_task_performance_accesses', 'reserve_task_model_calls', 'reserve_scoring_calls',
             'reserve_model_accesses', 'reserve_audio_accesses', 'reserve_performance_accesses')
    present = [key for key in zeros if key in row]
    require(present and all(type(row[k]) is int and row[k] == 0 for k in present), 'Missing/nonzero reserve access declaration')
    if 'allowed_development_cases' in row:
        require(set(row['allowed_development_cases']) == set(allowed), 'Access receipt allowlist differs')
    if 'allowed_development_count' in row:
        require(row['allowed_development_count'] == len(allowed), 'Support allowlist count differs')
    if row.get('scoring_protocol_sha256') is not None and protocol_sha is not None:
        require(row['scoring_protocol_sha256'] == protocol_sha, 'Access receipt protocol differs')
    for item in row.get('accesses', []) + row.get('permitted_calls', []):
        require(item['case_id'] in allowed, 'Recorded task access outside development')
        require(type(item['count']) is int and item['count'] >= 0, 'Invalid access-call count')
    for child in row.get('guards', []):
        validate_access(child, allowed, protocol_sha=protocol_sha)
    return {'component': row.get('component', row.get('schema')), 'reserve_task_accesses': 0,
            'metadata_rows_parsed': row.get('metadata_rows_parsed'), 'guard_records': len(row.get('guards', [])),
            'recorded_operation_rows': len(row.get('accesses', [])) + len(row.get('permitted_calls', [])),
            'denied_before_open': row.get('denied_before_open', row.get('refused_before_access', row.get('denied_before_access', [])))}


def reserve_evidence(ev, ctx, *, require_all):
    allowed = set(ctx['manifest']['development_ids']); rows, missing = [], []
    names = ('prepare.json', 'runner.json', 'text_panel.json', 'support_freeze.json', 'support_metrics.json')
    for name in names:
        path = REPORT/'access'/name
        if not path.exists():
            missing.append(str(path)); continue
        data = ev.read(path)
        rows.append({'receipt': ev.bind(path), **validate_access(data, allowed, protocol_sha=ctx['contract']['scoring_protocol']['sha256'])})
    rep = REPORT/'representation'
    if (rep/'RESERVE_ACCESS.json').exists():
        path = rep/'RESERVE_ACCESS.json'; data = ev.read(path)
        rows.append({'receipt': ev.bind(path), **validate_access(data, allowed, protocol_sha=ctx['contract']['scoring_protocol']['sha256'])})
    elif (rep/'RESULTS.json').exists():
        result = ev.read(rep/'RESULTS.json')
        require(str(result.get('status', '')).startswith('SKIPPED') and result.get('plan_binding'), 'Representation access evidence missing')
        plan = reference(ev, result['plan_binding']); validate_access(plan['access'], allowed)
        require(not plan['windows'], 'Representation skipped despite nonempty frozen plan without execution/access evidence')
        rows.append({'receipt': ev.bind(rep/'RESULTS.json'), 'component': 'representation_skipped', 'reserve_task_accesses': 0})
    else:
        missing.append(str(rep/'RESERVE_ACCESS.json'))
    if require_all:
        require(not missing, 'Required final component access receipts absent: '+repr(missing))
    return {'status': 'VERIFIED_RECORDED_APPLICATION_GUARDS' if not missing else 'PARTIAL_MISSING_COMPONENT_RECEIPTS',
            'development_cases': len(allowed), 'protected_reserve_cases': len(ctx['scenes'])-len(allowed),
            'reserve_task_model_accesses': 0, 'reserve_task_performance_accesses': 0,
            'components': rows, 'missing': missing,
            'duplicate_last_invocation_not_counted': str(REPORT/'access/support_last_invocation.json'),
            'scope': 'Allowlist code, recorded component guards, and task-directory name inventory. Metadata parsing of reserve rows is permitted. No OS-wide file-access trace; absent component receipts never silently mean zero.'}


def validate_representation_rows(plan, run):
    """Verify successful window rows, not just claimed aggregate counters."""
    require(run['models_loaded'] == 1 and isinstance(run.get('backend'), dict) and run['backend'], 'COMPLETE representation lacks actual backend/model evidence')
    windows = {w['window_id']: w for w in plan['windows']}
    require(len(windows) == len(plan['windows']), 'Duplicate frozen representation window ID')
    expected = {(key, out) for key in windows for out in ('O0', 'O1')}
    actual = [(r['window_id'], r['output']) for r in run['windows']]
    require(len(actual) == len(set(actual)) and set(actual) == expected, 'Representation missing/duplicate/unplanned output windows')
    for row in run['windows']:
        window = windows[row['window_id']]
        require(row['status'] == 'COMPLETE' and row['case_id'] == window['case_id'] and
                row['interval_samples'] == window['outputs'][row['output']]['interval_samples'], 'Representation window case/interval/status mismatch')
    require(run['completed_paired_windows'] == len(windows), 'Representation claimed completed-pair count differs')


def representation_evidence(ev, ctx):
    folder = REPORT/'representation'
    plan = ev.read(folder/'WINDOW_PLAN.json')
    copy = dict(plan); semantic = copy.pop('plan_sha256')
    require(stable(copy) == semantic, 'Representation plan content changed')
    require(plan['status'] == 'FROZEN_BEFORE_EMBEDDINGS_AND_COSINES', 'Representation plan not predeclared')
    require(plan['contract_semantic_sha256'] == stable(ctx['contract']), 'Representation contract differs')
    ev.ref(plan['code_binding']); ev.ref(plan['README_binding'])
    for item in plan['input_bindings']:
        ev.ref(item)
    counts = Counter()
    for window in plan['windows']:
        guard(window['case_id'], ctx['scenes']); counts[(window['case_id'], window['participant_id'])] += 1
        for output in ('O0', 'O1'):
            require(window['outputs'][output]['gain'] == GAINS[output], 'Representation gain differs')
            a, b = window['outputs'][output]['interval_samples']; require(b-a == 8000 and a >= 0, 'Representation interval changed')
    require(len(plan['windows']) <= 1000 and max(counts.values(), default=0) <= 4, 'Representation caps exceeded')
    result = ev.read(folder/'RESULTS.json')
    if not plan['windows']:
        require(str(result['status']).startswith('SKIPPED'), 'Empty representation plan did not produce skipped status')
        return {'status': 'SKIPPED_NO_WINDOWS', 'plan': ev.bind(folder/'WINDOW_PLAN.json'), 'result': ev.bind(folder/'RESULTS.json')}, []
    run = ev.read(folder/'RUN_RECEIPT.json')
    require(run['status'] in ('COMPLETE', 'FAILED_SPECIFIC_CONTRACT_OR_WINDOW') and run.get('ended_utc'), 'Representation execution unresolved')
    require(run['canonical_H2_state_modified'] is False and run['session_or_enrollment_created'] is False, 'Representation modified canonical/enrollment state')
    require(same_binding(run['window_plan_binding'], ev.bind(folder/'WINDOW_PLAN.json')), 'Representation used different plan')
    require(0 <= run['model_invocations'] <= 2*len(plan['windows']) and run['models_loaded'] in (0, 1), 'Representation invocation/model cap')
    if run['status'] == 'COMPLETE':
        validate_representation_rows(plan, run)
        ev.ref(run['results_binding'])
        require(same_binding(run['results_binding'], ev.bind(folder/'RESULTS.json')), 'Representation result binding points elsewhere')
        require(result['completed_paired_windows'] == len(plan['windows']) and run['model_invocations'] == 2*len(plan['windows']), 'Representation completion count differs')
    backend = run.get('backend')
    if backend:
        require({(str(Path(b['path']).resolve()), b['sha256']) for b in backend['source_bindings']} ==
                {(str(Path(b['path']).resolve()), b['sha256']) for b in ctx['contract']['baseline']['source_identities']}, 'Representation backend source set differs')
        for source in backend['source_bindings']:
            ev.ref(source)
        asset = next(a for a in ctx['science']['assets'] if a['component_id'] == 'redimnet2_b2_fp32')
        require(backend['asset_binding']['sha256'] == asset['sha256'] and Path(backend['asset_binding']['path']).resolve() == Path(asset['path']).resolve(), 'Representation embedding asset differs')
        require(backend['provider'] == ['CPUExecutionProvider'] and backend['speaker_threads'] == ctx['science']['speaker_threads'], 'Representation runtime differs')
        require(all(ctx['s0']['versions'][k] == v for k, v in backend['versions'].items()), 'Representation runtime versions differ')
    closure = ev.read(folder/'PROCESS_CLOSURE.json')
    require(closure['status'] == 'PASS_OWNED_PROCESS_NOT_ACTIVE' and closure['observed_tool_exit_code'] == 0 and
            closure['same_owned_process_present'] is False and closure['owned_pid'] == run['pid'] and
            closure['owned_creation_time'] == run['process_creation_time'] and
            same_binding(closure['run_receipt_binding'], ev.bind(folder/'RUN_RECEIPT.json')), 'Representation external closure evidence differs')
    return {'status': run['status'], 'plan': ev.bind(folder/'WINDOW_PLAN.json'), 'run': ev.bind(folder/'RUN_RECEIPT.json'),
            'result': ev.bind(folder/'RESULTS.json'), 'model_invocations': run['model_invocations'],
            'external_process_closure': ev.bind(folder/'PROCESS_CLOSURE.json'),
            'native_h2_sessions_created': 0, 'reserve_task_accesses': 0,
            'scope': 'Separate bounded oracle-window diagnostic. Model asset internally validated; this audit does not rehash model weights.'}, [
                {'owned_process_pid': run['pid'], 'owned_process_creation_time': run['process_creation_time'],
                 'model_exited_utc': run['ended_utc'], 'owner_kind': 'representation_script', 'receipt_status': run['status']}]


def panel_freshness(ev, ctx, native_rows):
    """Bind actual final panel outputs and compare application guards with their receipts."""
    expected = {(j['case_id'], j['stream']) for j in ctx['jobs']}
    success = {(j['case_id'], j['stream']) for j in native_rows if j['status'] == 'VERIFIED_NATIVE_COMPLETE'}
    text_path = REPORT/'TEXT_PANEL_RECEIPT.json'; text = ev.read(text_path)
    require(text['requested'] == 360 and text['complete'] == len(success), 'Text panel is stale relative to native completions')
    require(same_binding(text['protocol'], ctx['contract']['scoring_protocol']), 'Text panel protocol differs')
    require(len(text['rows']) == 360 and {(r['case_id'], r['stream']) for r in text['rows']} == expected, 'Text panel pairs incomplete/duplicate')
    actual_text = {(r['case_id'], r['stream']) for r in text['rows'] if r['status'].startswith('COMPLETE')}
    require(actual_text == success, 'Text panel successful population differs')
    access = ev.read(REPORT/'access/text_panel.json')
    require(access['guards'] == [r['guard'] for r in text['rows']], 'Text access receipt differs from final panel guards')
    for row in text['rows']:
        guard(row['case_id'], ctx['scenes'])
        if row['status'].startswith('COMPLETE'):
            require(Path(row['output']['path']).resolve() == (REPORT/'text_metrics'/row['case_id']/(row['stream']+'.json')).resolve(), 'Text result path differs')
            ev.ref(row['output'])
    for code in text['scorer_code']:
        ev.ref(code)
    support_path = REPORT/'support/SUPPORT_PANEL_RECEIPT.json'; support = ev.read(support_path)
    require(support['requested_outputs'] == 360 and support['completed_outputs'] == len(success) and
            support['shared_scene_records'] == 180 and support['real_noise_scene_records'] == 39, 'Support panel stale or wrong coverage')
    require(same_binding(support['scoring_protocol'], ctx['contract']['scoring_protocol']), 'Support panel protocol differs')
    require(len(support['rows']) == 360 and {(r['case_id'], r['stream']) for r in support['rows']} == expected, 'Support panel pairs incomplete/duplicate')
    require({(r['case_id'], r['stream']) for r in support['rows'] if r['status'] == 'COMPLETE'} == success, 'Support successful population differs')
    frozen = reference(ev, support['frozen_support_index'])
    require(frozen['count'] == 180 and {r['case_id'] for r in frozen['scenes']} == set(ctx['manifest']['development_ids']) and frozen['reserve_support_task_count'] == 0,
            'Frozen support population differs')
    require(same_binding(frozen['scoring_protocol'], ctx['contract']['scoring_protocol']) and same_binding(frozen['job_manifest'], ctx['run']['jobs']), 'Support input authority differs')
    for row in support['rows']:
        guard(row['case_id'], ctx['scenes'])
        if row['status'] == 'COMPLETE':
            require(Path(row['result']['path']).resolve() == (REPORT/'support/outputs'/row['case_id']/(row['stream']+'.json')).resolve(), 'Support result path differs')
            ev.ref(row['result'])
    for code in support['codes']:
        ev.ref(code)
    return {'status': 'PASS_FINAL_PANELS_MATCH_NATIVE_SUCCESS_SET', 'native_successful_outputs': len(success),
            'text_panel': ev.bind(text_path), 'support_panel': ev.bind(support_path), 'frozen_support': ev.ref(support['frozen_support_index']),
            'scope': 'Exact final panel coverage/protocol/current code and output bindings; scientific score arithmetic is audited separately by the results coordinator.'}


def process_snapshot(recorded):
    ids = ','.join(str(int(r['owned_process_pid'])) for r in recorded if r.get('owned_process_pid'))
    script = r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$recorded=@(__PIDS__)
$rows=@(Get-CimInstance Win32_Process | Where-Object {
 ($_.ProcessId -in $recorded) -or
 ($_.CommandLine -match 's5_(runner|representation)\.py' -or
  ($_.CommandLine -match '20260909T130308Z' -and $_.CommandLine -match 'app\.edge_speech_pipeline'))
} | Select-Object ProcessId,ParentProcessId,Name,CommandLine,@{n='CreationDate';e={if($_.CreationDate){$_.CreationDate.ToUniversalTime().ToString('o')}else{$null}}})
@{query_succeeded=$true;queried_utc=[DateTime]::UtcNow.ToString('o');processes=$rows}|ConvertTo-Json -Depth 5 -Compress
""".replace('__PIDS__', ids)
    return powershell_json(script)


def process_closure(snapshot, recorded):
    require(snapshot.get('query_succeeded') is True, 'Process snapshot unavailable')
    errors, reused = [], []
    for live in snapshot['processes']:
        command = live.get('CommandLine') or ''
        if re.search(r's5_(runner|representation)\.py', command, re.I) or (RUN_ID in command and 'app.edge_speech_pipeline' in command):
            errors.append('Relevant S5 owner remains active: '+str(live['ProcessId'])); continue
        records = [r for r in recorded if r.get('owned_process_pid') == live['ProcessId']]
        if not records:
            continue
        try:
            created = dt.datetime.fromisoformat(live['CreationDate'].replace('Z', '+00:00')).timestamp()
        except (TypeError, KeyError, ValueError):
            errors.append('Historical PID exists with unknown creation: '+str(live['ProcessId'])); continue
        for row in records:
            known = row.get('owned_process_creation_time')
            if known is not None:
                require(math.isfinite(float(known)) and float(known) > 0, 'Invalid recorded process creation time')
                if abs(float(known)-created) < .001:
                    errors.append('Original recorded process generation still active: '+str(live['ProcessId']))
                else:
                    reused.append({'pid': live['ProcessId'], 'current_creation_utc': live['CreationDate'], 'historical_creation_epoch': known,
                                   'basis': 'Different process creation time; PID reused, no process control'})
            else:
                exited = row.get('model_exited_utc') or row.get('completed_utc')
                try:
                    ended = dt.datetime.fromisoformat(exited.replace('Z', '+00:00')).timestamp()
                except (AttributeError, TypeError, ValueError):
                    ended = None
                if ended is None or created <= ended:
                    errors.append('Historical process generation cannot be distinguished: '+str(live['ProcessId']))
                else:
                    reused.append({'pid': live['ProcessId'], 'current_creation_utc': live['CreationDate'], 'historical_exit_utc': exited,
                                   'basis': 'Current creation strictly after bound historical completion; original creation unavailable'})
    return {'status': 'PASS_NO_RECORDED_OR_RELEVANT_OWNER_OBSERVED' if not errors else 'BLOCKED_ACTIVE_OR_UNVERIFIED_OWNER',
            'errors': errors, 'snapshot': snapshot, 'confirmed_pid_reuse': reused, 'recorded_process_records': len(recorded),
            'distinct_historical_pids': len({r['owned_process_pid'] for r in recorded if r.get('owned_process_pid')}),
            'scope': 'Read-only point-in-time CIM PID+creation observation. No signal/termination, no future-state claim. Historical missing creation is explicit.'}


def storage_bytes():
    roots = [REPORT, PAYLOAD] + sorted((SIM/'staging').glob('s5_*'))
    roots += sorted((SIM/'scripts').glob('s5_*.py')) + sorted((SIM/'scripts').glob('test_s5_*.py'))
    roots += sorted((SIM/'scripts').glob('README_S5*.md')) + sorted((SIM/'handoffs').glob('S5*'+RUN_ID+'*'))
    seen, totals, reparse = set(), [], []
    for root in roots:
        if not root.exists():
            continue
        pending = [root]; count = size = 0
        while pending:
            path = pending.pop(); info = path.lstat(); key = str(path.resolve()).casefold()
            if key in seen:
                continue
            seen.add(key)
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
                reparse.append(str(path)); continue
            if path.is_dir():
                pending.extend(path.iterdir())
            else:
                count += 1; size += info.st_size
        totals.append({'root': str(root), 'logical_bytes': size, 'files': count})
    require(not reparse, 'Unresolved reparse points in bounded new-output scope: '+repr(reparse))
    total = sum(r['logical_bytes'] for r in totals)
    require(total < 40*2**30, 'S5 new-output40GiB budget exceeded')
    return {'bounded_new_logical_bytes': total, 'roots': totals,
            'scope': 'S5 payload/report/staging/code/README/handoff logical files only; excludes existing datasets/RIR/hardware/model trees, allocated-block overhead and this not-yet-written audit receipt.'}


def runtime_versions(ctx):
    code = "import importlib.metadata as m,json,sys;print(json.dumps({'python':sys.version.split()[0],'versions':{k:m.version(k) for k in ['numpy','scipy','soundfile','sounddevice','onnxruntime','sherpa-onnx','psutil']}}))"
    completed = subprocess.run([ctx['contract']['baseline']['python'], '-c', code], capture_output=True, check=True, timeout=30,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    result = json.loads(completed.stdout.decode('utf-8'))
    require(result['python'] == ctx['s0']['python_version'] and all(v == ctx['s0']['versions'][k] for k, v in result['versions'].items()), 'Current native environment versions differ from S0')
    return {**result, 'scope': 'Read-only package metadata subprocess; no native model import/asset download/inference'}


def resources(ev, ctx):
    import psutil
    prior = ev.read(REPORT/'RESOURCE_PREFLIGHT.json'); current = ssd_and_space()
    for volume in current['volumes']:
        old = next(v for v in prior['ssd']['volumes'] if v['drive'] == volume['drive'])
        ident = lambda v: sorted((m['serial_number'].strip(), m['model'].strip()) for m in v['mapping'])
        require(ident(old) == ident(volume), 'SSD volume hardware identity changed')
    path = REPORT/'resource_samples.jsonl'; ev.bind(path)
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]; ev.bind(path)
    require(rows, 'Model process RAM sample evidence missing')
    peak = max(r['tree_rss_bytes'] for r in rows); available_min = min(r['available_ram_bytes'] for r in rows)
    require(peak < 40*2**30 and available_min >= 8*2**30, 'Recorded model RAM/OS floor violation')
    memory = dict(psutil.virtual_memory()._asdict())
    require(memory['available'] >= 8*2**30, 'Current available OS RAM floor')
    return {'status': 'PASS', 'ssd': current, 'current_ram': memory, 'new_storage': storage_bytes(),
            'sampled_model_tree_peak_rss_bytes': peak, 'sampled_available_ram_min_bytes': available_min,
            'model_ram_samples': len(rows), 'ram_sample_binding': ev.bind(path),
            'ram_scope': 'Observed samples, not continuous absolute peak. Offline host resources are not CM5 fit.', 'native_runtime': runtime_versions(ctx)}


def git_observation(ev):
    initial = ev.read(REPORT/'GIT_PREFLIGHT.json')
    def call(*args):
        return subprocess.run(['git', '--no-optional-locks', *args], cwd=REPO, capture_output=True, check=True, timeout=30,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.decode('utf-8')
    head, branch = call('rev-parse', 'HEAD').strip(), call('branch', '--show-current').strip()
    require(head == initial['head'] and branch == initial['branch'], 'Git branch/HEAD changed during S5')
    return {'observed_utc': utc(), 'head': head, 'branch': branch, 'status_porcelain': call('status', '--porcelain'),
            'tracked_diff_stat': call('diff', '--stat'), 'scope': 'Read-only Git observation; exact scientific source hashes checked separately. No staging/commit/push/cleanup.'}


def write_result(result, *, final):
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    name = 'FINAL_AUDIT' if final else 'FINAL_AUDIT_PARTIAL'
    immutable = REPORT/(name+'_'+stamp+'.json')
    payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False).encode('utf-8')
    with immutable.open('xb') as stream:
        stream.write(payload)
    current = REPORT/(name+'.json'); temporary = current.with_suffix('.tmp')
    temporary.write_bytes(payload); temporary.replace(current)
    return {'path': str(current), 'versioned_path': str(immutable), 'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}


def audit(*, require_complete=False):
    """Full mode only after every inference/diagnostic process exits. Partial is metadata only."""
    started = time.monotonic(); ev = Evidence(); errors = []
    result = {'schema': 'jp_s5_final_audit_v1', 'run_id': RUN_ID, 'started_utc': utc(),
              'mode': 'FULL_REQUIRE_TERMINAL' if require_complete else 'PARTIAL_METADATA_ONLY',
              'status': 'BLOCKED', 'errors': errors, 'model_invocations_by_audit': 0, 'hardware_accesses_by_audit': 0}
    try:
        for name in CODE_NAMES:
            ev.bind(SIM/'scripts'/name)
        test = ev.read(SIM/'staging/s5_final_audit/TEST_RECEIPT.json')
        require(test['status'] == 'PASS_MODEL_FREE_FIXTURES', 'Final audit fixture receipt absent/unqualified')
        for item in test['code']:
            ev.ref(item)
        ctx = context(ev); unexpected_task_paths(ctx)
        # Metadata disposition check comes BEFORE any waveform verification.
        rows, processes, attempts = job_records(ev, ctx, full=False)
        result.update(metadata_dispositions=dict(Counter(r['status'] for r in rows)), intended_jobs=360,
                      intended_development_scenes=180, intended_reuse=48, intended_fresh=312, attempts=attempts)
        if not require_complete:
            result.update(status='PARTIAL_METADATA_ONLY_NOT_FINAL', jobs=rows,
                          reserve_protection=reserve_evidence(ev, ctx, require_all=False),
                          scope='No waveform, live process, SSD or runtime-version validation in this partial mode; no final completion claim.')
        else:
            require(not any(r['status'].startswith('PENDING') for r in rows), 'Canonical panel has pending/unresolved rows')
            cleanup = ev.read(REPORT/'RUNNER_CLEANUP.json')
            require(cleanup['hardware_accesses'] == 0 and cleanup.get('utc'), 'Runner cleanup metadata missing')
            processes.append({'owned_process_pid': cleanup['runner_pid'], 'owned_process_creation_time': cleanup['runner_creation_time'],
                              'model_exited_utc': cleanup['utc'], 'owner_kind': 'S5_runner'})
            rep, rep_processes = representation_evidence(ev, ctx); processes += rep_processes
            before = process_closure(process_snapshot(processes), processes)
            require(not before['errors'], 'Full audit refuses active/unverified model owners: '+repr(before['errors']))
            result['process_closure_before'] = before
            rows, _, attempts = job_records(ev, ctx, full=True)
            result.update(jobs=rows, attempts=attempts, representation=rep, conservation=conservation(ev, ctx),
                          reserve_protection=reserve_evidence(ev, ctx, require_all=True), panel_freshness=panel_freshness(ev, ctx, rows),
                          resources=resources(ev, ctx), git=git_observation(ev))
            success = [r for r in rows if r['status'] == 'VERIFIED_NATIVE_COMPLETE']
            result['counts'] = {'requested': 360, 'verified_native_complete': len(success),
                                'reused_native_complete': sum(r['origin'] == 'reused_s45' for r in success),
                                'fresh_native_complete': sum(r['origin'] == 'fresh_s5' for r in success),
                                'terminal_failed': sum(r['status'] == 'VERIFIED_TERMINAL_FAILED' for r in rows),
                                'quarantined': sum(r['status'] == 'VERIFIED_QUARANTINED' for r in rows),
                                'fresh_attempt_receipts': len(attempts), 'failed_attempts': sum(r['status'] == 'FAILED' for r in attempts)}
            result['native_totals'] = {origin: {'jobs': sum(r['origin'] == origin for r in success),
                'decoded_samples': sum(r['decoded_samples'] for r in success if r['origin'] == origin),
                'decoded_audio_s': sum(r['decoded_audio_s'] for r in success if r['origin'] == origin),
                'model_child_wall_s': sum(r['model_child_wall_s'] for r in success if r['origin'] == origin)} for origin in ('reused_s45', 'fresh_s5')}
            after = process_closure(process_snapshot(processes), processes)
            require(not after['errors'], 'Relevant owner appeared during audit')
            result['process_closure_after'] = after
            result['status'] = 'PASS_ALL_360_NATIVE' if len(success) == 360 else 'VERIFIED_TERMINAL_COVERAGE_WITH_FAILURES'
            result['scope'] = 'Independent fullraw/fixedadapter/PCM16/nativeevents/summary/metrics/baseline and final host observations. No reserve performance or model re-execution. Native failures remain visible, never zero-error outputs.'
    except Exception as exc:
        errors.append(type(exc).__name__+': '+str(exc))
        if not require_complete:
            result['status'] = 'PARTIAL_METADATA_OBSERVATION_UNAVAILABLE_NOT_FINAL'
    result.update(ended_utc=utc(), audit_wall_s=time.monotonic()-started, consumed_bindings=list(ev.rows.values()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-complete', action='store_true', help='Full immutable native/resource audit only after all S5 inference exits')
    args = parser.parse_args()
    result = audit(require_complete=args.require_complete)
    output = write_result(result, final=args.require_complete)
    print(json.dumps({'status': result['status'], 'errors': result['errors'], 'counts': result.get('counts'), 'output': output}, indent=2))
    if result['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
