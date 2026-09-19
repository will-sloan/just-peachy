"""Resumable S5 text scoring and native provenance verification. README_S5.md."""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import time
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'
from s5_common import *
from s5_text_metrics import score_scene
from s45_h2_run import verify_native_completion
from s4_h2_run import fixed_gain_copy

def resolve_native(job, wrapper):
    assert wrapper['job_key'] == job['job_key'] and wrapper['status'] == 'COMPLETE'
    if wrapper.get('reused_receipt'):
        b = wrapper['reused_receipt']
        bind(b['path'], b['sha256'])
        native = read(b['path'])
    else:
        native = wrapper
    assert native['raw_audio'] == job['raw_audio']
    assert native['adapter']['gain_scalar'] == job['gain']
    assert native['status'] == 'COMPLETE' and native['exit_code'] == 0
    return native

def score_job(job, all_scenes, protocol_binding, scorer_code):
    guard = DevelopmentGuard(all_scenes, 'text_' + job['case_id'] + '_' + job['stream'], receipt=False)
    scene = guard.require(job['case_id'], 'text_boundary')
    assert stable_hash(scene) == job['identity']['scene_reference_sha256']
    rp = Path(job['report_dir']) / 'run_receipt.json'
    if not rp.exists() or read(rp)['status'] != 'COMPLETE':
        return {'case_id': job['case_id'], 'stream': job['stream'], 'status': 'PENDING_OR_FAILED', 'guard': guard.flush()}
    wb = bind(rp)
    native = resolve_native(job, read(rp))
    guard.require(job['case_id'], 'raw_audio_verification')
    raw = bind(job['raw_audio']['path'], job['raw_audio']['sha256'])
    ab = native['adapter']['output_binding']
    bind(ab['path'], ab['sha256'])
    # This function checks the existing adapter array and never writes if present.
    adapter = fixed_gain_copy(raw['path'], ab['path'], job['gain'])
    assert adapter['journal_clip_input_samples'] == native['adapter']['journal_clip_input_samples']
    guard.require(job['case_id'], 'full_native_journal_verification')
    completion = verify_native_completion(Path(native['session_dir']), Path(ab['path']))
    old_journal = native['completion_evidence']['journal']
    bind(old_journal['path'], old_journal['sha256'])
    for field in ('metrics_binding', 'events_binding', 'session_summary_binding'):
        bind(native[field]['path'], native[field]['sha256'])
    identity = {'protocol': protocol_binding, 'scorer_code': scorer_code, 'job_key': job['job_key'],
                'native_wrapper': wb, 'metrics': native['metrics_binding'],
                'events': native['events_binding'], 'journal': completion['journal']}
    target = REPORT / 'text_metrics' / job['case_id'] / (job['stream'] + '.json')
    key = stable_hash(identity)
    if target.exists():
        old = read(target)
        assert old['analysis_key'] == key, 'Changed text scoring input or implementation'
        return {'case_id': job['case_id'], 'stream': job['stream'], 'status': 'COMPLETE_REUSED_SCORE',
                'output': bind(target), 'guard': guard.flush()}
    guard.require(job['case_id'], 'text_performance_scoring')
    metrics = read(native['metrics_binding']['path'])
    events = [json.loads(s) for s in Path(native['events_binding']['path']).read_text(encoding='utf-8').splitlines() if s.strip()]
    scored = score_scene(scene, metrics, events, development_ids=guard.allowed, duration_s=native['adapter']['duration_s'])
    scored.update(stream=job['stream'], analysis_key=key, identity=identity,
                  native_completion_verified=completion, reused_historical_job=bool(job['reuse']),
                  native_receipt_path=job['reuse']['receipt']['path'] if job['reuse'] else str(rp),
                  adapter_clamp_input_samples=adapter['journal_clip_input_samples'])
    save(target, scored)
    return {'case_id': job['case_id'], 'stream': job['stream'], 'status': 'COMPLETE',
            'output': bind(target), 'guard': guard.flush()}

def run(require_complete=False, workers=4):
    assert 1 <= workers <= 6
    protocol_binding = bind(REPORT / 'SCORING_PROTOCOL.json')
    contract = read(REPORT / 'execution_contract.json')
    assert protocol_binding == contract['scoring_protocol']
    m = manifest()
    jm = read(REPORT / 'JOB_MANIFEST.json')
    runm = read(REPORT / 'run_manifest.json')
    bind(REPORT / 'JOB_MANIFEST.json', runm['jobs']['sha256'])
    code = [bind(SIM / 'scripts' / n) for n in ('s5_text_metrics.py', 's5_text_panel.py', 's4_h2_analysis.py')]
    code.append(bind(H2 / 'app/scoring/wer.py'))
    started = time.monotonic()
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(score_job, j, m['scenes'], protocol_binding, code) for j in jm['jobs']]
        for f in concurrent.futures.as_completed(futures):
            rows.append(f.result())
            if len(rows) % 30 == 0:
                print(json.dumps({'phase': 'S5_TEXT_SCORE', 'examined': len(rows), 'requested': 360,
                                  'complete': sum(r['status'].startswith('COMPLETE') for r in rows)}), flush=True)
    rows.sort(key=lambda r: (r['case_id'], r['stream']))
    complete = sum(r['status'].startswith('COMPLETE') for r in rows)
    save(REPORT / 'TEXT_PANEL_RECEIPT.json', {'schema': 'jp_s5_text_panel_v1', 'utc': now(),
         'status': 'COMPLETE' if complete == 360 else 'PARTIAL', 'requested': 360, 'complete': complete,
         'workers': workers, 'elapsed_s': time.monotonic() - started, 'scorer_code': code,
         'protocol': protocol_binding, 'reserve_task_accesses': 0, 'rows': rows})
    save(REPORT / 'access/text_panel.json', {'utc': now(), 'reserve_task_accesses': 0, 'component': 'text_panel',
         'guards': [r['guard'] for r in rows], 'scope': 'Before raw/adapter/journal/text reads; native completion reverified on every consumed complete job'})
    if require_complete:
        assert complete == 360, 'Full text panel is not complete'
    print(json.dumps({'phase': 'S5_TEXT_SCORE', 'complete': complete, 'requested': 360}), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    run(args.require_complete, args.workers)
