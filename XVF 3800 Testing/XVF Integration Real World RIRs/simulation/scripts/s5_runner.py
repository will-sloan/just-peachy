"""One-worker native H2 runner with bounded retries and ownership. README_S5.md."""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import psutil
from s5_common import *
from s45_h2_run import baseline_contract, verify_native_completion, analyze_s45
from s4_h2_run import fixed_gain_copy, completed_session

def same_process(pid, creation_time):
    try:
        return abs(psutil.Process(pid).create_time() - creation_time) < .001
    except psutil.NoSuchProcess:
        return False

def terminate_owned(process, creation_time):
    """Never terminate by PID alone, including after a restart."""
    if process.poll() is None and same_process(process.pid, creation_time):
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if same_process(process.pid, creation_time):
                process.kill()
                process.wait(timeout=10)

def verify_complete(receipt, job):
    assert receipt['job_key'] == job['job_key'], 'Job identity changed'
    assert receipt['status'] == 'COMPLETE'
    native = read(receipt['reused_receipt']['path']) if receipt.get('reused_receipt') else receipt
    if receipt.get('reused_receipt'):
        bind(receipt['reused_receipt']['path'], receipt['reused_receipt']['sha256'])
    assert native['status'] == 'COMPLETE' and native['exit_code'] == 0
    assert native['raw_audio'] == job['raw_audio'] and native['adapter']['gain_scalar'] == job['gain']
    for field in ('session_summary_binding', 'events_binding', 'metrics_binding'):
        bind(native[field]['path'], native[field]['sha256'])
    bind(native['adapter']['output_binding']['path'], native['adapter']['output_binding']['sha256'])
    return native

def permitted_attempt(existing, job):
    if not existing:
        return 1
    for r in existing:
        assert r['job_key'] == job['job_key'], 'Prior attempt has incompatible identity'
        if r.get('owned_process_pid') and same_process(r['owned_process_pid'], r['owned_process_creation_time']):
            raise RuntimeError('Prior owned process still alive; do not overlap or retry')
    if len(existing) >= 2:
        return None
    return 2

class Monitor:
    def __init__(self, jobs):
        self.jobs = jobs
        self.start = time.monotonic()
        self.stop = threading.Event()
        self.current = None
        self.process = None
        self.creation = None
        self.stage = 'H2_NATIVE'
        self.error = None
        self.max_ram = 0
        self.samples = 0
        self.lock = threading.Lock()
    def snapshot(self):
        counts = {'requested': len(self.jobs), 'reused_complete': 0, 'new_complete': 0,
                  'failed': 0, 'quarantined': 0, 'attempts': 0, 'audio_s_complete': 0.0, 'fresh_model_wall_s': 0.0}
        for job in self.jobs:
            p = Path(job['report_dir']) / 'run_receipt.json'
            if p.exists():
                r = read(p)
                if r['status'] == 'COMPLETE':
                    counts['reused_complete' if r.get('reused_receipt') else 'new_complete'] += 1
                    counts['audio_s_complete'] += r['audio_duration_s']
                    if not r.get('reused_receipt'):
                        counts['fresh_model_wall_s'] += r.get('model_wall_s', 0)
                counts['failed'] += r['status'] == 'FAILED'
                counts['quarantined'] += r['status'] == 'QUARANTINED'
            counts['attempts'] += len(list(Path(job['report_dir']).glob('attempt_*/attempt_receipt.json')))
        counts['complete'] = counts['reused_complete'] + counts['new_complete']
        counts['remaining'] = len(self.jobs) - counts['complete'] - counts['failed'] - counts['quarantined']
        elapsed = time.monotonic() - self.start
        throughput = counts['new_complete'] / elapsed if elapsed else 0
        return {'utc': now(), 'phase': self.stage, 'status': 'RUNNING' if not self.stop.is_set() else self.stage,
                'current': self.current, 'elapsed_invocation_s': elapsed,
                'elapsed_s5_s': (dt.datetime.now(dt.timezone.utc) - START).total_seconds(),
                'new_jobs_per_minute': 60 * throughput,
                'eta_s': counts['remaining'] / throughput if throughput else None,
                'max_sampled_owned_process_tree_rss_bytes': self.max_ram, 'ram_samples': self.samples,
                'model_workers': 1, 'reserve_task_jobs': 0, 'error': self.error, **counts}
    def emit(self):
        with self.lock:
            row = self.snapshot()
            save(REPORT / 'status.json', row)
            with (REPORT / 'heartbeat.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(row) + '\n')
            print(json.dumps(row), flush=True)
    def loop(self):
        last_emit = 0
        while not self.stop.wait(2):
            try:
                if self.process and self.creation and same_process(self.process.pid, self.creation):
                    p = psutil.Process(self.process.pid)
                    tree = [p] + p.children(recursive=True)
                    rss = sum(x.memory_info().rss for x in tree if x.is_running())
                    self.max_ram = max(self.max_ram, rss)
                    self.samples += 1
                    with (REPORT / 'resource_samples.jsonl').open('a', encoding='utf-8') as f:
                        f.write(json.dumps({'utc': now(), 'job': self.current, 'pid': p.pid, 'creation_time': self.creation,
                                'tree_pids': [x.pid for x in tree], 'tree_rss_bytes': rss,
                                'available_ram_bytes': psutil.virtual_memory().available}) + '\n')
                    if rss >= 40 * 2**30 or psutil.virtual_memory().available < 8 * 2**30:
                        self.error = 'Owned model RAM cap or OS headroom violated'
                        terminate_owned(self.process, self.creation)
                if time.monotonic() - last_emit >= 20:
                    self.emit()
                    last_emit = time.monotonic()
            except psutil.NoSuchProcess:
                pass
            except Exception as exc:
                self.error = repr(exc)
    def __enter__(self):
        self.emit()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        return self
    def __exit__(self, typ, val, tb):
        self.stop.set()
        self.thread.join(5)
        if val:
            self.error = repr(val)
            self.stage = 'FAILED_OR_INTERRUPTED'
        self.emit()

def timing_evidence(session, model_wall):
    events = [json.loads(x) for x in (session / 'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    return {'model_child_wall_s': model_wall,
            'event_time_fields': sorted({k for e in events[:5] for k in e if 'time' in k}),
            'first_event': {k: v for k, v in events[0].items() if k != 'payload'} if events else None,
            'last_event': {k: v for k, v in events[-1].items() if k != 'payload'} if events else None,
            'scope': 'Child wall includes startup/inference/finalization. Exported native event times retained for decomposition; accelerated processing is not live latency.'}

def run_attempt(job, scene, number, monitor, guard):
    folder = Path(job['report_dir']) / f'attempt_{number}'
    payload = Path(job['payload_root']) / f'attempt_{number}'
    assert not folder.exists() and not payload.exists(), 'Preserve existing attempt'
    folder.mkdir(parents=True)
    payload.mkdir(parents=True)
    root = payload / 'empty_data'
    adapter_path = payload / 'fixed_gain_input.wav'
    guard.require(job['case_id'], 'new_adapter_audio')
    bind(job['raw_audio']['path'], job['raw_audio']['sha256'])
    adapter = fixed_gain_copy(job['raw_audio']['path'], adapter_path, job['gain'])
    # Preserve the unchanged native PCM16 clamp, including existing raw rails.
    # fixed_gain_copy already refuses gain-generated values beyond full scale.
    root.mkdir()
    argv = [str(EDGE_PYTHON), '-m', 'app.edge_speech_pipeline', 'file', str(adapter_path), '--accelerated']
    receipt = {'schema': 'jp_s5_native_attempt_v1', 'status': 'STARTED', 'case_id': job['case_id'],
               'stream': job['stream'], 'job_key': job['job_key'], 'identity': job['identity'], 'attempt_number': number,
               'created_utc': now(), 'raw_audio': job['raw_audio'], 'adapter': adapter,
               'argv': argv, 'cwd': str(H2), 'isolated_data_root': str(root),
               'initial_profile_files': 0, 'labels_or_transcripts_sent_to_model': False,
               'input_provenance': job['input_provenance'], 'analysis_provenance': job['analysis_provenance'],
               'queue_wait_since_s5_start_s': (dt.datetime.now(dt.timezone.utc) - START).total_seconds(),
               'queue_wait_scope': 'Elapsed from S5 coordinator start; includes preparation and preceding serial jobs'}
    rp = folder / 'attempt_receipt.json'
    save(rp, receipt)
    env = single_thread_env()
    env['EDGE_SPEECH_DATA_ROOT'] = str(root)
    env.pop('EDGE_SPEECH_ASSET_ROOT', None)
    process = None
    start = time.monotonic()
    try:
        guard.require(job['case_id'], 'model_invocation')
        guard.flush()
        with (folder / 'stdout.jsonl').open('wb') as out, (folder / 'stderr.txt').open('wb') as err:
            process = subprocess.Popen(argv, cwd=H2, env=env, stdout=out, stderr=err,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            creation = psutil.Process(process.pid).create_time()
            receipt.update(owned_process_pid=process.pid, owned_process_creation_time=creation)
            save(rp, receipt)
            monitor.process, monitor.creation = process, creation
            receipt['exit_code'] = process.wait(timeout=240)
        receipt['model_wall_s'] = time.monotonic() - start
        receipt['model_exited_utc'] = now()
        save(rp, receipt)
        assert receipt['exit_code'] == 0, 'Native H2 child failed'
        session = completed_session(root)
        assert session is not None, 'Missing complete native summary'
        guard.require(job['case_id'], 'native_completion_verification')
        receipt['completion_evidence'] = verify_native_completion(session, adapter_path)
        guard.require(job['case_id'], 'legacy_native_metrics')
        metrics = analyze_s45(session, scene, adapter_path, job['alignment'], kind='outputs')
        assert metrics['state'] == 'COMPLETED' and not metrics['failure_events']
        metrics.update(case_id=job['case_id'], stream=job['stream'], kind='outputs',
                       raw_output_rail_samples=adapter['source_rail_samples'], fixed_host_gain=job['gain'],
                       analysis_provenance=job['analysis_provenance'])
        save(folder / 'metrics.json', metrics)
        receipt.update(status='COMPLETE', session_dir=str(session), completed_utc=now(),
                       metrics_binding=bind(folder / 'metrics.json'),
                       session_summary_binding=bind(session / 'session_summary.json'),
                       events_binding=bind(session / 'events.jsonl'),
                       model_success_has_internal_asset_validation=True,
                       audio_duration_s=adapter['duration_s'],
                       timing=timing_evidence(session, receipt['model_wall_s']))
    except BaseException as exc:
        if process is not None:
            terminate_owned(process, receipt['owned_process_creation_time'])
        receipt.update(status='FAILED', error=repr(exc), model_wall_s=time.monotonic() - start, ended_utc=now())
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            save(rp, receipt)
            raise
    finally:
        monitor.process = None
        monitor.creation = None
        save(rp, receipt)
    return receipt

def run():
    import msvcrt
    report_manifest = read(REPORT / 'run_manifest.json')
    for key in ('contract', 'jobs'):
        bind(report_manifest[key]['path'], report_manifest[key]['sha256'])
    contract = read(REPORT / 'execution_contract.json')
    assert baseline_contract() == contract['baseline']
    for row in contract['code']:
        bind(row['path'], row['sha256'])
    for key in ('scoring_protocol', 'decision_protocol', 'recipes'):
        bind(contract[key]['path'], contract[key]['sha256'])
    m = manifest()
    guard = DevelopmentGuard(m['scenes'], 'runner')
    jobs = read(REPORT / 'JOB_MANIFEST.json')['jobs']
    assert len(jobs) == 360 and {j['case_id'] for j in jobs} == guard.allowed
    with (REPORT / 'runner.lock').open('a+b') as lease:
        lease.seek(0)
        if not lease.read(1):
            lease.write(b'0')
            lease.flush()
        lease.seek(0)
        msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with Monitor(jobs) as monitor:
                consecutive_failures = 0
                for index, job in enumerate(jobs):
                    scene = guard.require(job['case_id'], 'job_boundary')
                    monitor.current = job['case_id'] + '/' + job['stream']
                    folder = Path(job['report_dir'])
                    folder.mkdir(parents=True, exist_ok=True)
                    rp = folder / 'run_receipt.json'
                    if rp.exists():
                        r = read(rp)
                        if r['status'] == 'COMPLETE':
                            guard.require(job['case_id'], 'resume_native_receipt')
                            verify_complete(r, job)
                            continue
                    if job['reuse']:
                        guard.require(job['case_id'], 'reuse_native_receipt')
                        b = job['reuse']['receipt']
                        bind(b['path'], b['sha256'])
                        old = read(b['path'])
                        r = {'status': 'COMPLETE', 'case_id': job['case_id'], 'stream': job['stream'],
                             'job_key': job['job_key'], 'identity': job['identity'], 'reused_receipt': b,
                             'audio_duration_s': old['adapter']['duration_s'],
                             'historical_model_wall_s': old['model_wall_s'], 'new_model_invocations': 0,
                             'reuse_verified': job['reuse'], 'completed_utc': now()}
                        save(rp, r)
                        verify_complete(r, job)
                        continue
                    if job['level_gate'] == 'QUARANTINED_GROSS_SATURATION':
                        save(rp, {'status': 'QUARANTINED', 'job_key': job['job_key'], 'model_invocations': 0})
                        continue
                    attempts = [read(p) for p in sorted(folder.glob('attempt_*/attempt_receipt.json'))]
                    complete = next((r for r in attempts if r['status'] == 'COMPLETE'), None)
                    if complete:
                        save(rp, complete)
                        verify_complete(complete, job)
                        continue
                    while (number := permitted_attempt(attempts, job)) is not None:
                        if not launch_allowed() or (REPORT / 'STOP_REQUEST.json').exists():
                            monitor.stage = 'PARTIAL_STOP_OR_TIME_BUDGET'
                            return
                        if monitor.error:
                            raise RuntimeError(monitor.error)
                        resources(scan=index % 12 == 0)
                        result = run_attempt(job, scene, number, monitor, guard)
                        attempts.append(result)
                        if result['status'] == 'COMPLETE':
                            save(rp, result)
                            consecutive_failures = 0
                            break
                    else:
                        save(rp, {'status': 'FAILED', 'job_key': job['job_key'], 'identity': job['identity'],
                                  'case_id': job['case_id'], 'stream': job['stream'],
                                  'attempt_receipts': [bind(p) for p in sorted(folder.glob('attempt_*/attempt_receipt.json'))]})
                        consecutive_failures += 1
                        if consecutive_failures >= 2:
                            raise RuntimeError('Two consecutive jobs exhausted identical retries; systemic diagnosis required')
                    guard.flush()
                monitor.current = None
                monitor.stage = 'H2_PANEL_FINISHED'
        finally:
            guard.flush()
            save(REPORT / 'RUNNER_CLEANUP.json', {'utc': now(), 'runner_pid': os.getpid(),
                 'runner_creation_time': psutil.Process().create_time(),
                 'owned_child_remaining': False, 'hardware_accesses': 0,
                 'scope': 'Every started native child waited to exit or exact identity terminated; no unrelated process/service changes'})
            lease.seek(0)
            msvcrt.locking(lease.fileno(), msvcrt.LK_UNLCK, 1)

if __name__ == '__main__':
    run()
