"""Bound saved-file S7 worker. See README_NATIVE_V2.md; no capture/playback API."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import queue
import shutil
import statistics
import sys
import threading
import time
import wave


def bind(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def read(bound):
    if bind(bound['path']) != bound:
        raise ValueError('Changed bound input: ' + bound['path'])
    return json.loads(Path(bound['path']).read_text(encoding='utf-8-sig'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())


def atomic_heartbeat(path, row):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(row, allow_nan=False) + '\n', encoding='utf-8')
    deadline = time.monotonic() + 3.
    while True:
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            if getattr(exc, 'winerror', None) not in {5, 32, 33} or time.monotonic() >= deadline:
                raise
            time.sleep(.05)


class Protocol:
    """Same supervisor identities and cooperative STOP; progress is work, not a timer."""
    def __init__(self, job_id, environ=None):
        import psutil
        env = os.environ if environ is None else environ
        keys = ['RUN_ID', 'JOB_ID', 'CHILD_RUN_ID', 'HEARTBEAT_PATH', 'COMPLETION_PATH', 'STOP_REQUEST_PATH']
        self.values = {k: env['S6D_' + k] for k in keys}
        if self.values['JOB_ID'] != job_id or self.values['RUN_ID'] != '20260917T141700Z':
            raise ValueError('Supervisor identity mismatch')
        self.identity = {'run_id': self.values['RUN_ID'], 'job_id': job_id,
            'child_run_id': self.values['CHILD_RUN_ID'], 'pid': os.getpid(),
            'creation_time': psutil.Process().create_time()}
        self.progress = 0; self.stage = 'ADMISSION'; self.errors = []
        self.stopped = threading.Event(); self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._loop, name='s7-protocol', daemon=True)

    def start(self):
        self.pulse(); self.thread.start()

    def advance(self, stage, units=1):
        with self.lock:
            self.stage = stage; self.progress += int(units)

    def pulse(self):
        with self.lock:
            row = {**self.identity, 'status': self.stage, 'progress_count': self.progress,
                'utc': datetime.now(timezone.utc).isoformat(), 'queue_age_s': None}
        atomic_heartbeat(self.values['HEARTBEAT_PATH'], row)

    def _loop(self):
        try:
            while not self.stopped.wait(5.): self.pulse()
        except BaseException as exc: self.errors.append(repr(exc))

    def check(self):
        if self.errors: raise RuntimeError('Protocol writer failed: ' + repr(self.errors))
        if Path(self.values['STOP_REQUEST_PATH']).exists():
            raise InterruptedError('Supervisor cooperative STOP_REQUEST')

    def finish(self, result_binding, success):
        self.stopped.set()
        if self.thread.ident is not None: self.thread.join(5.)
        if self.thread.is_alive() or self.errors: raise RuntimeError('Protocol closure failed')
        self.stage = 'COMPLETE' if success else 'FAILED'; self.pulse()
        write(self.values['COMPLETION_PATH'], {**self.identity, 'status': self.stage,
            'result': result_binding, 'physical_tested': False})


class AsyncRows:
    """Bounded consumer handoff: JSON and disk work happen on the writer thread."""
    def __init__(self, path, capacity=32768):
        self.path = Path(path); self.q = queue.Queue(capacity)
        self.accepted = self.completed = self.max_depth = 0
        self.error = None; self.closed = False
        self.thread = threading.Thread(target=self._run, name='s7-consumer-writer', daemon=True)
        self.thread.start()

    def submit(self, row):
        if self.closed or self.error: raise RuntimeError('Consumer writer closed/failed')
        self.q.put_nowait(row); self.accepted += 1
        self.max_depth = max(self.max_depth, self.q.qsize())

    def _run(self):
        try:
            with self.path.open('x', encoding='utf-8', buffering=65536) as f:
                last = time.perf_counter()
                while True:
                    row = self.q.get()
                    if row is None: break
                    f.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
                    self.completed += 1
                    if time.perf_counter() - last >= 1.: f.flush(); last = time.perf_counter()
                f.flush(); os.fsync(f.fileno())
        except BaseException as exc: self.error = repr(exc)

    def close(self, timeout=30.):
        deadline = time.monotonic() + timeout
        if not self.closed:
            self.closed = True
            self.q.put(None, timeout=max(.001, deadline-time.monotonic()))
        self.thread.join(max(0., deadline-time.monotonic()))
        if self.thread.is_alive() or self.error or self.accepted != self.completed:
            raise RuntimeError('Consumer writer failed to drain: ' + str(self.snapshot()))

    def snapshot(self):
        return {'accepted': self.accepted, 'completed': self.completed, 'max_depth': self.max_depth,
            'depth': self.q.qsize(), 'error': self.error, 'closed': self.closed,
            'thread_alive': self.thread.is_alive()}


def baseline_completion(bound):
    """Compile just the unchanged, intake-bound S6D pure closure predicate."""
    if bind(bound['path']) != bound: raise ValueError('Changed closure authority')
    tree = ast.parse(Path(bound['path']).read_text(encoding='utf-8-sig'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'completion_errors')
    ns = {}; exec(compile(ast.Module(body=[function], type_ignores=[]), bound['path'], 'exec'), ns)
    return ns['completion_errors']


def pcm_info(path):
    """Hash original WAV data bytes, never a re-encoded or gain-adjusted signal."""
    digest = hashlib.sha256(); count = 0
    with wave.open(str(path), 'rb') as f:
        if (f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getcomptype()) != (1, 2, 16000, 'NONE'):
            raise ValueError('Exact mono 16 kHz PCM16 input required')
        expected = f.getnframes()
        while True:
            data = f.readframes(65536)
            if not data: break
            digest.update(data); count += len(data)
    if count != expected * 2: raise ValueError('Truncated original PCM input')
    return {'frames': expected, 'pcm_bytes': count, 'pcm_sha256': digest.hexdigest(), 'sample_rate': 16000}


def audit_pcm(job, session):
    original = pcm_info(job['audio']['path'])
    if original != job['expected_pcm']: raise ValueError('Original PCM changed')
    rows = []
    for name in ('audio_spool.pcm16', 'identity_audio_spool.pcm16'):
        b = bind(Path(session) / name)
        if b['bytes'] != original['pcm_bytes'] or b['sha256'] != original['pcm_sha256']:
            raise ValueError('Full source PCM/order mismatch: ' + name)
        rows.append(b)
    return {'status': 'PASS_EXACT_ORIGINAL_PCM_BOTH_JOURNALS', 'expected': original, 'journals': rows,
        'unity_gain': True, 'full_source': True}


def quantiles(values):
    if not values: return {'count': 0, 'p50': None, 'p95': None, 'p99': None, 'max': None, 'min': None}
    values = sorted(values)
    def q(p):
        x = (len(values)-1)*p; a = math.floor(x); b = math.ceil(x)
        return values[a] + (values[b]-values[a])*(x-a)
    return {'count': len(values), 'p50': q(.5), 'p95': q(.95), 'p99': q(.99), 'max': values[-1], 'min': values[0]}


def timing_summary(path, expected_frames):
    origins = []; ends = []; blocks = []; pauses = 0
    with Path(path).open(encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            if row['kind'] == 'source_origin': origins.append(row)
            elif row['kind'] == 'source_end': ends.append(row)
            elif row['kind'] == 'source_block': blocks.append(row)
            elif row['kind'] == 'source_pause': pauses += 1
    if len(origins) != 1 or len(ends) != 1 or not blocks: raise ValueError('Incomplete source trace')
    origin = origins[0]['origin_monotonic_sec']; prev = 0; last_commit = origin
    lates = []; source_ends = []; early = 0; catchup = 0; tol = 1e-6
    for row in blocks:
        if type(row['start_sample']) is not int or type(row['end_sample']) is not int or row['start_sample'] != prev or row['end_sample'] <= prev:
            raise ValueError('Source trace samples are reordered, duplicated or missing')
        end = row['end_sample']; deadline = origin + end/16000
        values = [row[k] for k in ('admission_monotonic_sec', 'append_start_monotonic_sec',
            'asr_append_end_monotonic_sec', 'identity_append_end_monotonic_sec', 'commit_monotonic_sec')]
        if not all(math.isfinite(v) for v in values+[deadline, row['intended_release_monotonic_sec']]):
            raise ValueError('Nonfinite source clocks')
        if abs(row['intended_release_monotonic_sec']-deadline)>tol or any(b+tol<a for a,b in zip(values, values[1:])) or values[-1]+tol<last_commit:
            raise ValueError('Invalid source clock/commit ordering')
        early += int(values[0]+tol < deadline or values[-1]+tol < deadline)
        catchup += int(bool(row['catch_up_mode']))
        lates.append(values[-1]-deadline); source_ends.append(end/16000)
        prev=end; last_commit=values[-1]
    if prev != expected_frames or origins[0]['expected_samples'] != expected_frames or ends[0]['end_sample'] != expected_frames or ends[0]['expected_samples'] != expected_frames or ends[0]['stopped']:
        raise ValueError('Trace does not cover full admitted input')
    steady = [(t,v) for t,v in zip(source_ends, lates) if t >= 5.]
    first = [v for t,v in steady if t < 15.]
    last = [v for t,v in steady if t > source_ends[-1]-10.]
    drift = statistics.median(last)-statistics.median(first) if first and last else None
    ts = [t for t,v in steady]; vs = [v for t,v in steady]
    mean_t = statistics.mean(ts) if ts else 0.
    mean_v = statistics.mean(vs) if vs else 0.
    denom = sum((t-mean_t)**2 for t in ts) if ts else 0
    slope = sum((t-mean_t)*(v-mean_v) for t,v in steady)/denom if denom else None
    q = quantiles(vs)
    return {'status':'DESCRIPTIVE_SOURCE_TIMING', 'source_trace':bind(path), 'source_frames':prev,
        'pacing':origins[0]['pacing'], 'quantile_method':'linear interpolation at (n-1)*p',
        'steady_state_definition':'block end >= 5 source seconds; final short block retained',
        'all_block_lateness_sec':quantiles(lates), 'steady_lateness_sec':q,
        'post_first_block_lateness_sec':quantiles(lates[1:]),
        'end_minus_first_lateness_sec':lates[-1]-lates[0],
        'drift_last10_minus_first10_steady_medians_sec':drift, 'steady_ols_slope_sec_per_source_sec':slope,
        'all_source_points_in_raw_trace':True, 'early_or_future_blocks':early, 'catch_up_blocks':catchup,
        'pauses':pauses, 'timestamp_tolerance_sec':tol,
        'source_timing_flags':{'no_early_or_future_release':early==0, 'steady_p95_le_100ms':q['p95'] is not None and q['p95']<=.1,
            'steady_p99_le_200ms':q['p99'] is not None and q['p99']<=.2,
            'long_drift_le_100ms':drift<=.1 if drift is not None and expected_frames>=1800*16000 else None,
            'no_catch_up':catchup==0, 'no_pause':pauses==0},
        'gate_a_accepted':False, 'scope':'Single execution diagnostics; not paired naming or Gate A acceptance'}


def compact_telemetry(engine):
    t = engine.telemetry()
    fields = ('state','source_duration_sec','asr_cursor_sec','speaker_cursor_sec','elapsed_wall_sec',
        'raw_capture_overflows','dropped_audio_samples','asr_drop_count','speaker_drop_count')
    out = {k:t[k] for k in fields if k in t}
    out['queues'] = {k:v for k,v in (t.get('s6d') or {}).items() if k in {'event_consumer','journal','punctuation','policy'}}
    out['s7_trace'] = t.get('s7_trace')
    return out


def execute_cell(engine, job, output, protocol, completion_errors, timeout):
    """S6D native start/drain/join sequence with bounded asynchronous consumers."""
    import psutil
    process=psutil.Process(); halted=threading.Event(); observer_errors=[]
    consumer=AsyncRows(output/'consumer_events.jsonl'); resource=AsyncRows(output/'resources.jsonl', 256)
    def observe():
        last=time.perf_counter()
        try:
            while not halted.is_set():
                now=time.perf_counter(); m=process.memory_full_info()
                resource.submit({'monotonic_sec':now,'sampling_gap_sec':now-last,'pid':process.pid,
                    'creation_time':process.create_time(),'rss':m.rss,'uss':getattr(m,'uss',None),
                    'cpu_percent':process.cpu_percent(),'threads':process.num_threads(),
                    'telemetry':compact_telemetry(engine), 'consumer_writer':consumer.snapshot()})
                last=now; halted.wait(1.)
        except BaseException as exc: observer_errors.append(repr(exc))
    watcher=threading.Thread(target=observe,name='s7-resource-observer',daemon=True); watcher.start()
    started=time.perf_counter(); startup=None; failure=None; consumed=0; last_frames=0; trace_closed=None; startup_events=[]
    try:
        protocol.check(); protocol.advance('MODEL_AND_SOURCE_STARTUP')
        engine.start_file(Path(job['audio']['path']),realtime=True)
        startup=time.perf_counter()-started; protocol.advance('RUNNING')
        while True:
            protocol.check()
            if observer_errors: raise RuntimeError('Resource observer failed: '+repr(observer_errors))
            if time.perf_counter()-started>timeout: raise TimeoutError('Bound native cell deadline')
            while not engine.events.empty():
                event=engine.events.get(); received=time.perf_counter(); row=event.to_jsonable()
                row['actual_consumed_monotonic_sec']=received; consumer.submit(row); consumed+=1
                if event.event_type in {'research_models_ready','source_started','research_input_route'}:
                    startup_events.append(row)
                trace=getattr(engine,'_s7_trace',None)
                if trace is not None:
                    payload=row.get('payload') or {}
                    trace.record('consumer_receipt', event_type=event.event_type, source_end_sec=event.source_time_sec,
                        receipt_monotonic_sec=received, publication_sequence=payload.get('publication_sequence'),
                        utterance_id=payload.get('utterance_id'), event_id=payload.get('event_id'))
                protocol.advance('RUNNING')
                if consumed%100==0: protocol.check()
            frames=round(engine.telemetry().get('source_duration_sec',0.)*16000)
            if frames>last_frames: protocol.advance('RUNNING',frames-last_frames);last_frames=frames
            finalizer=engine._finalization_thread
            if finalizer is not None and not finalizer.is_alive() and engine.events.empty(): break
            time.sleep(.005)
        engine.wait_for_completion(60.)
        errors=completion_errors(engine,engine.telemetry())
        if errors: raise RuntimeError('; '.join(errors))
        consumer.close(); engine.record_s6d_consumer_closure('S7 actual saved-file event consumer')
        trace=getattr(engine,'_s7_trace',None)
        if trace is not None: trace.close(); trace_closed=trace.snapshot()
        protocol.advance('SOURCE_AUDIT')
    except BaseException as exc:
        failure=repr(exc)
        engine.stop()
        try: engine.wait_for_completion(60.)
        except BaseException as close_exc: failure+='; wait: '+repr(close_exc)
    finally:
        halted.set();watcher.join(5.)
        for writer in (consumer,resource):
            try: writer.close()
            except BaseException as exc: failure=(failure or '')+'; writer: '+repr(exc)
        trace=getattr(engine,'_s7_trace',None)
        if trace is not None and trace_closed is None:
            try: trace.close();trace_closed=trace.snapshot()
            except BaseException as exc: failure=(failure or '')+'; trace: '+repr(exc)
    errors=completion_errors(engine,engine.telemetry())
    if watcher.is_alive(): errors.append('Resource observer thread not closed')
    errors.extend(observer_errors)
    if errors: failure=failure or '; '.join(errors)
    return {'failure':failure,'completion_errors':errors,'telemetry':engine.telemetry(),
        'session_dir':str(engine.session_dir),'event_consumer_drained':engine.events.empty(),
        'consumer_writer':consumer.snapshot(),'resource_writer':resource.snapshot(),
        'resource_observer_closed':not watcher.is_alive(),'s7_trace_closure':trace_closed,
        'consumed_events':consumed,'startup_events':startup_events,'start_file_model_and_source_startup_sec':startup,
        'execution_elapsed_sec':time.perf_counter()-started}


def admit_manifest(manifest, job_id):
    if manifest.get('schema')!='s7-native.v1' or manifest.get('run_id')!='20260917T141700Z': raise ValueError('Wrong native manifest')
    jobs=[j for j in manifest['jobs'] if j['job_id']==job_id]
    if len(jobs)!=1: raise ValueError('Missing/duplicate job')
    job=jobs[0]
    if bind(__file__)!=manifest['helper']: raise ValueError('Wrong frozen native helper')
    root=Path(manifest['source_root']).resolve()/'edge_speech_pipeline'
    for b in manifest['execution_files']:
        if not Path(b['path']).resolve().is_relative_to(root) or bind(b['path'])!=b: raise ValueError('Source epoch changed')
    if read(job['profile_binding'])!=job['profile']: raise ValueError('Profile differs from original bound profile')
    p=job['profile']['input']
    if p['gain']!=1. or p['already_gained'] is not True or p['asr_tap']!=p['identity_tap'] or p['source_block_ms']!=100:
        raise ValueError('Only unity same-tap 100 ms source jobs admitted')
    if job['telemetry'] is not None and bind(job['telemetry']['path'])!=job['telemetry']: raise ValueError('Telemetry changed')
    if job['gallery'] is not None and len(read(job['gallery'])['profiles'])!=15: raise ValueError('Original15 gallery required')
    if bind(job['audio']['path'])!=job['audio']: raise ValueError('Input WAV changed')
    if pcm_info(job['audio']['path'])!=job['expected_pcm']: raise ValueError('Original PCM changed')
    for asset in manifest['assets']:
        if bind(asset['binding']['path'])!=asset['binding'] or asset['sha256']!=asset['binding']['sha256'] or Path(asset['path']).resolve()!=Path(asset['binding']['path']).resolve():
            raise ValueError('Model asset changed')
    return job


def run(manifest_path, job_id):
    manifest=read(bind(manifest_path)); protocol=Protocol(job_id); protocol.start()
    output=None; result=None
    try:
        admitted=time.perf_counter(); job=admit_manifest(manifest,job_id)
        output=Path(job['output']);output.mkdir(parents=True,exist_ok=False)
        for drive,floor in [('C:/',50),('G:/',75)]:
            if shutil.disk_usage(drive).free < floor*1024**3: raise RuntimeError('Disk reserve unavailable')
        protocol.check(); protocol.advance('IMPORT')
        for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'): os.environ[key]='1'
        sys.dont_write_bytecode=True; sys.path.insert(0,manifest['source_root'])
        names=['config','research_profiles','runtime','research_s6d']
        if job.get('s7_settings') is not None: names.append('research_s7')
        modules={n:importlib.import_module('edge_speech_pipeline.'+n) for n in names}
        source=Path(manifest['source_root']).resolve()/'edge_speech_pipeline'
        for n,m in list(sys.modules.items()):
            if n=='edge_speech_pipeline' or n.startswith('edge_speech_pipeline.'):
                if getattr(m,'__file__',None) and not Path(m.__file__).resolve().is_relative_to(source): raise RuntimeError('Wrong application import origin')
        cfg=modules['config'];profiles=modules['research_profiles']
        assets=tuple(cfg.AssetSpec(a['component_id'],Path(a['path']),a['sha256'],a['deployment_relative_path']) for a in manifest['assets'])
        profile=profiles.ResearchProfile.from_dict(job['profile'])
        base=cfg.PipelineConfig(assets=assets,session_root=output/'sessions',profile_root=output/'empty_private_profiles')
        effective=profile.apply(base)
        if effective.input_gain!=1. or any(getattr(effective,k)!=1 for k in ('asr_threads','speaker_threads','punctuation_threads')): raise ValueError('Unity/single-thread condition changed')
        kwargs={'research_profile':profile,'research_gallery':job['gallery']['path'] if job['gallery'] else None,
            'spatial_provider':profiles.JsonSpatialProvider(job['telemetry']['path']) if job['telemetry'] else None,
            's6d_settings':modules['research_s6d'].S6DSettings(**job['settings']) if job.get('settings') else None}
        if job.get('s7_settings') is not None: kwargs['s7_settings']=modules['research_s7'].S7Settings(**job['s7_settings']).validate()
        constructed=time.perf_counter();engine=modules['runtime'].PipelineEngine(base,**kwargs)
        construction=time.perf_counter()-constructed
        result=execute_cell(engine,job,output,protocol,baseline_completion(manifest['closure_authority']),manifest['limits']['cell_timeout_sec'])
        result.update({'schema':'s7-native-cell.v1','job':job,'manifest':bind(manifest_path),'helper':bind(__file__),
            'identity':protocol.identity,'source_admission_import_and_engine_construction_sec':constructed-admitted+construction,
            'engine_construction_sec':construction,'physical_tested':False,'gui_tested':False,'cm5_tested':False,
            'readonly_saved_file_input':True,'gate_a_accepted':False})
        write(output/'EXECUTION_DRAIN.json', {'schema':'s7-native-execution-drain.v1',
            'status':'EXECUTION_DRAINED' if result['failure'] is None else 'EXECUTION_FAILED',
            'postprocessing_complete':False, 'execution_result':result})
        result['execution_drain']=bind(output/'EXECUTION_DRAIN.json')
        if result['failure'] is None:
            try:
                result['source_audit']=audit_pcm(job,engine.session_dir)
                protocol.advance('PCM_AUDIT_COMPLETE')
                trace_path=Path(engine.session_dir)/'s7_clocks.jsonl'
                result['source_timing']=timing_summary(trace_path,job['expected_pcm']['frames']) if job.get('s7_settings') is not None else {'status':'UNAVAILABLE_FROZEN_S6D_SOURCE_NO_S7_TRACE'}
                protocol.advance('TIMING_AUDIT_COMPLETE' if job.get('s7_settings') is not None else 'TIMING_AUDIT_UNAVAILABLE_FROZEN_CONTROL')
                if bind(job['audio']['path'])!=job['audio']: raise ValueError('Input changed during execution')
                protocol.check()
            except BaseException as exc: result['failure']=repr(exc)
        result['status']='COMPLETE' if result['failure'] is None else 'FAILED'
        result['native_tested']=result['status']=='COMPLETE'
        result['outputs']={name:bind(output/name) for name in ('consumer_events.jsonl','resources.jsonl')}
        write(output/'RESULT.json',result)
        protocol.finish(bind(output/'RESULT.json'),result['status']=='COMPLETE')
        if result['status']!='COMPLETE': raise RuntimeError(result['failure'])
        return result
    except BaseException:
        protocol.stopped.set()
        if protocol.thread.ident is not None: protocol.thread.join(5.)
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--job-id',required=True)
    a=p.parse_args();r=run(a.manifest,a.job_id);print(json.dumps({'status':r['status'],'job_id':a.job_id}))
