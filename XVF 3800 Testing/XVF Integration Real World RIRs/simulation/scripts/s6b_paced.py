"""Matched paced S6B full-engine probes. See README_S6B_PACED.md."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid
import wave

import psutil

DEFAULT_CASES = ('S45_01_06','S45_03_01','S45_04_05','S45_06_07')
NUMERIC_KEYS = ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')


def utc():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def bind(path,expected=None):
    p=Path(path).resolve();before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('Dependency changed while hashing: '+str(p))
    if expected is not None and h.hexdigest()!=expected:raise RuntimeError('Dependency hash mismatch: '+str(p))
    return dict(path=str(p),bytes=before.st_size,sha256=h.hexdigest())
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    for attempt in range(4):
        try:os.replace(temp,path);break
        except OSError as exc:
            if getattr(exc,'winerror',None) not in {5,32,33} or attempt==3:raise
            time.sleep(.02*2**attempt)
def matches(pid,created):
    try:return abs(psutil.Process(pid).create_time()-created)<.001
    except psutil.Error:return False
def tree_bytes(root):
    total=0
    for p in Path(root).rglob('*'):
        try:
            if p.is_file():total+=p.stat().st_size
        except OSError:pass
    return total


def pcm16_hash(path):
    import numpy as np
    import soundfile as sf
    h=hashlib.sha256()
    with sf.SoundFile(path) as f:
        if (f.channels,f.samplerate)!=(1,16000):raise ValueError('Prepared input must be mono16kHz; this driver does not resample')
        samples=f.frames;observed=0
        while True:
            data=f.read(1600,dtype='float32',always_2d=True)
            if not data.size:break
            mono=np.mean(data,axis=1,dtype=np.float32)
            if not np.isfinite(mono).all():raise ValueError('Nonfinite source audio')
            block=np.round(np.clip(mono,-1.0,0.999969)*32768.0).astype('<i2').tobytes()
            observed+=len(block);h.update(block)
    if observed!=samples*2:raise ValueError('WAV PCM body truncated')
    return dict(sha256=h.hexdigest(),samples=samples,duration_sec=samples/16000)


def check_runtime_versions(expected):
    from importlib.metadata import version
    current={name:version(name) for name in ('numpy','onnxruntime','sherpa-onnx')}
    current['python']=sys.version
    if current!=expected:raise RuntimeError('Runtime version mismatch: '+json.dumps(dict(expected=expected,actual=current)))
    return current


def resource_sample(payload,worker_status_root=None):
    # Explicit research-process accounting uses the owned run path in command
    # lines, not a guess that every Python process belongs to this study.
    research={}
    needle=str(payload).lower().replace('/','\\')
    for p in psutil.process_iter(['pid','cmdline','memory_info']):
        try:
            command=' '.join(p.info['cmdline'] or []).lower().replace('/','\\')
            if ('s6b_' in command or needle in command) and p.pid!=os.getpid():
                research[p.pid]={'pid':p.pid,'rss_bytes':p.info['memory_info'].rss,'source':'research command line'}
        except (psutil.Error,TypeError):pass
    if worker_status_root is not None:
        for path in Path(worker_status_root).glob('*.json'):
            status=read(path)
            if not matches(status.get('pid',-1),status.get('creation_time',-1)):continue
            try:
                p=psutil.Process(status['pid'])
                for member in [p]+p.children(recursive=True):
                    research[member.pid]={'pid':member.pid,'rss_bytes':member.memory_info().rss,'source':'epoch worker PID/creation-time tree'}
            except psutil.Error:pass
    return {'available_ram_bytes':psutil.virtual_memory().available,
            'c_free_bytes':psutil.disk_usage('C:/').free,'g_free_bytes':psutil.disk_usage('G:/').free,
            'research_processes':list(research.values()),'research_rss_sum_upper_bound_bytes':sum(x['rss_bytes'] for x in research.values())}
def assert_resources(sample,limits):
    for key,limit in (('available_ram_bytes','host_available_min_bytes'),('c_free_bytes','c_free_min_bytes'),('g_free_bytes','g_free_min_bytes')):
        if sample[key]<limits[limit]:raise RuntimeError('Resource reserve violated: '+key)
    if sample['research_rss_sum_upper_bound_bytes']>limits['research_rss_cap_bytes']:raise RuntimeError('Research RSS cap exceeded')


def sample_tree(process):
    try:members=[process]+process.children(recursive=True)
    except psutil.Error:members=[process]
    rows=[];unreadable=[]
    for p in members:
        try:
            m=p.memory_full_info();c=p.cpu_times();io=p.io_counters()
            rows.append(dict(pid=p.pid,creation_time=p.create_time(),name=p.name(),rss_bytes=m.rss,
                private_resident_uss_bytes=getattr(m,'uss',None),windows_private_commit_bytes=getattr(m,'private',None),
                pss_bytes=getattr(m,'pss',None),threads=p.num_threads(),cpu_seconds=c.user+c.system,
                io_read_bytes=io.read_bytes,io_write_bytes=io.write_bytes))
        except psutil.Error:unreadable.append(p.pid)
    def total(key):return sum(r[key] for r in rows) if rows and not unreadable and all(r[key] is not None for r in rows) else None
    rss,uss=total('rss_bytes'),total('private_resident_uss_bytes')
    return dict(processes=rows,unreadable_pids=unreadable,tree_complete=not unreadable,rss_sum_upper_bound_bytes=rss,private_resident_uss_sum_bytes=uss,
        windows_private_commit_sum_bytes=total('windows_private_commit_bytes'),pss_sum_bytes=total('pss_bytes'),
        nonunique_shared_resident_estimate_bytes=rss-uss if rss is not None and uss is not None else None,
        full_tree_threads=sum(x['threads'] for x in rows),system_available_ram_bytes=psutil.virtual_memory().available,
        system_cpu_percent=psutil.cpu_percent(interval=None))


def prepare(args):
    spec_path=args.report/(args.epoch.upper()+'_EXECUTION_MANIFEST.json');spec=read(spec_path)
    if spec['epoch']!=args.epoch:raise ValueError('Epoch mismatch')
    check_runtime_versions(spec['runtime_versions'])
    metadata_keys=('input_index','gain_index','effective_profile_registry','scene_manifest','challenge_panel')
    for k in metadata_keys:bind(spec[k]['path'],spec[k]['sha256'])
    registry={x['profile_id']:x for x in read(spec['effective_profile_registry']['path'])['profiles']}
    selected=args.profiles.split(',');cases=args.cases.split(',');streams=args.streams.split(',')
    if len(set(selected))!=len(selected) or not 1<=len(selected)<=4 or set(selected)-registry.keys():raise ValueError('Choose1..4 distinct registered profile IDs')
    if len(set(cases))!=len(cases) or not 1<=len(cases)<=8:raise ValueError('Choose1..8 distinct cases')
    if len(set(streams))!=len(streams) or set(streams)-{'O0','O1'}:raise ValueError('Choose O0 and/or O1')
    main={(r['case_id'],r['stream']):r for r in read(spec['input_index']['path'])['rows']}
    alt={(r['case_id'],r['stream']):r for r in read(spec['gain_index']['path'])['rows']}
    scenes={x['case_id']:x for x in read(spec['scene_manifest']['path'])['scenes']}
    b0=args.sim/'staging/s6a/20260909T202250Z/baseline_app/edge_speech_pipeline'
    dependencies={}
    def consume(binding):
        checked=bind(binding['path'],binding['sha256']);dependencies[checked['path']]=checked;return checked
    for row in spec['execution_files']:consume(row)
    for row in spec['assets']:consume(row['binding'])
    for k in metadata_keys:consume(spec[k])
    consume(bind(spec_path));consume(bind(__file__))
    if 'B00' in selected:
        historical=args.sim/'reports/S6A/20260909T202250Z/execution_contract.json'
        consume(bind(historical));baseline_rows=[r for r in read(historical)['snapshot'] if Path(r['snapshot']).suffix=='.py']
        if {Path(r['snapshot']).resolve() for r in baseline_rows}!={p.resolve() for p in b0.glob('*.py')}:raise ValueError('Historical B0 source inventory differs')
        for row in baseline_rows:consume(dict(path=row['snapshot'],sha256=row['sha256']))
    jobs=[];selection=[];pcm_bindings={}
    for case in cases:
        scene=scenes[case]
        segments=scene['segments'];participants=[x.get('participant_id') for x in segments]
        durations=[(x['source_stop_sample']-x['source_start_sample'])/scene['sample_rate_hz'] for x in segments]
        selection.append(dict(case_id=case,family_id=scene['family_id'],family=scene['family'],nominal_render_duration_sec=scene['duration_s'],
            includes_subsecond_source=any(0<x<1 for x in durations),single_participant=len(set(participants))==1,
            includes_return=any(participants[i] in participants[:i-1] for i in range(2,len(participants))),
            scheduled_overlap=bool(scene['overlap_intervals']),predictor_receives_selection_metadata=False))
    # Repetition two reverses method order to reduce fixed warm-up order bias.
    # All methods see the same case/stream order in each repetition. Every job
    # uses a fresh process, model state and empty gallery; no best repeat chosen.
    for repeat in range(1,args.repetitions+1):
        for case in cases:
            for stream in streams:
                for pid in (selected if repeat%2 else list(reversed(selected))):
                    entry=registry[pid];profile=None if pid=='B00' else entry['profile']
                    source=alt[case,stream] if entry.get('recipe_id','').startswith('R6') else main[case,stream]
                    audio=consume(source['audio'])
                    if audio['path'] not in pcm_bindings:pcm_bindings[audio['path']]=pcm16_hash(audio['path'])
                    pcm=pcm_bindings[audio['path']]
                    if source.get('audio_pcm_sha256') and source['audio_pcm_sha256']!=pcm['sha256']:raise ValueError('Indexed PCM body hash mismatch')
                    if abs(pcm['duration_sec']-source['duration_sec'])>1e-8:raise ValueError('Indexed PCM duration mismatch')
                    telemetry=consume(main[case,stream]['telemetry']) if profile and profile['xvf']['mode']!='none' else None
                    if profile and (profile['input']['gain']!=1.0 or not profile['input']['already_gained']):raise ValueError('Paced driver requires indexed already-gained inputs at unity')
                    job=dict(profile_id=pid,recipe_id=entry['recipe_id'],case_id=case,stream=stream,repetition=repeat,
                        profile=profile,app_path=str(b0.parent if pid=='B00' else Path(spec['root'])/'app'),
                        input=audio,input_pcm_sha256=pcm['sha256'],duration_sec=source['duration_sec'],
                        telemetry=telemetry,assets=spec['assets'],epoch=args.epoch,
                        mode='EXACT_IMMUTABLE_B0_DEFAULT' if pid=='B00' else 'FROZEN_EPOCH2_PROFILE',
                        gain_context=source.get('raw_gain_applied_once',source.get('historical_gain_applied_once')),
                        source_sample_rate=16000,realtime=True,clip_policy='whole indexed prepared input; no truncation/resynthesis',
                        original_config_threads_retained=True,inner_numeric_pools=1)
                    job['job_id']=f'{pid}_{case}_{stream}_R{repeat}'
                    job['job_key']=digest(job);jobs.append(job)
    payload=Path('G:/Just_Peachy_S6B')/args.report.name
    sample=resource_sample(payload,args.report/args.epoch/'workers')
    plan=dict(schema='s6b-paced-manifest.v1',epoch=args.epoch,epoch_manifest=bind(spec_path),epoch_execution_digest=spec['execution_digest'],
        driver=bind(__file__),dependencies=list(dependencies.values()),profiles=selected,cases=cases,streams=streams,repetitions=args.repetitions,
        runtime_versions=spec['runtime_versions'],method_order='Listed profile order on odd repetitions, reversed on even repetitions; case/stream order fixed',
        selection=selection,jobs=jobs,total_audio_sec=sum(x['duration_sec'] for x in jobs),worker_limit=1,
        resource_limits=spec['worker_limits'],payload_root=str(payload),output_root=str(args.output.resolve()),
        methodology='Identical whole cases in repeated matched cells; one fresh full-engine process per cell. Cold startup separate from paced source; desktop only.',
        timing='Native event emission/release times are measured; modeled cue/scheduler availability remains separately labelled.',
        memory='USS private resident; RSS-sum upper bound; private commit virtual not resident; PSS unavailable if host omits it.')
    plan['manifest_key']=digest(plan)
    args.output.mkdir(parents=True,exist_ok=True)
    target=args.output/'MANIFEST.json'
    if target.exists() and read(target)!=plan:raise RuntimeError('Existing paced manifest differs; use a new output namespace')
    if not target.exists():save(target,plan)
    save(args.output/'PREPARATION.json',dict(status='PREPARED_NO_MODELS_STARTED',created_utc=utc(),manifest_key=plan['manifest_key'],resource_snapshot=sample,
        expected_paced_audio_minutes=plan['total_audio_sec']/60,expected_jobs=len(jobs),reserve_check_passed=None))
    return plan


def verify(plan):
    for row in plan['dependencies']:bind(row['path'],row['sha256'])
    checked={}
    for job in plan['jobs']:
        for row in (job['input'],job['telemetry']):
            if row is not None and row['path'] not in checked:checked[row['path']]=bind(row['path'],row['sha256'])


def worker(args):
    plan=read(args.manifest);job=next(j for j in plan['jobs'] if j['job_id']==args.job_id)
    check_runtime_versions(plan['runtime_versions'])
    out=Path(plan['output_root'])/'jobs'/job['job_id'];out.mkdir(parents=True,exist_ok=True)
    process=psutil.Process();started=time.perf_counter();engine=None
    # Only frozen APP, explicit assets, audio/profile/provider enter inference.
    # No scene manifest, reference text or participant data is imported here.
    bind(job['input']['path'],job['input']['sha256'])
    if job['telemetry']:bind(job['telemetry']['path'],job['telemetry']['sha256'])
    sys.path.insert(0,job['app_path'])
    from edge_speech_pipeline.config import PipelineConfig,AssetSpec
    from edge_speech_pipeline.runtime import PipelineEngine
    assets=tuple(AssetSpec(r['component_id'],Path(r['path']),r['sha256'],r['deployment_relative_path']) for r in job['assets'])
    config=PipelineConfig(assets=assets,session_root=out/'sessions',profile_root=out/'empty_gallery')
    startup_phase='model_loading';counts=Counter();display=[];source_started=None;session=None
    save(out/'WORKER_IDENTITY.json',dict(pid=process.pid,creation_time=process.create_time(),created_utc=utc(),job_key=job['job_key']))
    save(out/'LIVE.json',dict(phase=startup_phase,elapsed_sec=time.perf_counter()-started,telemetry=None,counts={}))
    try:
        model_started=time.perf_counter();bundle=None
        if job['profile'] is None:engine=PipelineEngine(config)
        else:
            from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
            from edge_speech_pipeline.models import ResidentModelBundle
            profile=ResearchProfile.from_dict(job['profile'])
            provider=JsonSpatialProvider(Path(job['telemetry']['path'])) if job['telemetry'] else None
            bundle=ResidentModelBundle(profile.apply(config))
            engine=PipelineEngine(config,research_profile=profile,spatial_provider=provider,model_bundle=bundle)
        bundle_load_sec=time.perf_counter()-model_started
        launch_started=time.perf_counter();session=engine.start_file(Path(job['input']['path']),realtime=True)
        launch_sec=time.perf_counter()-launch_started
        lastbeat=0.
        def drain():
            nonlocal source_started
            while not engine.events.empty():
                e=engine.events.get();counts[e.event_type]+=1
                if e.event_type=='source_started':source_started=e.wall_time_utc
                if e.event_type in ('transcript_partial','transcript_final','transcript_label_revision'):
                    display.append(dict(event_type=e.event_type,source_time_sec=e.source_time_sec,emitted_wall_time_utc=e.wall_time_utc,
                        observed_by_driver_elapsed_sec=time.perf_counter()-started,payload=dict(e.payload)))
        while engine.state not in {'COMPLETED','FAILED'}:
            drain();elapsed=time.perf_counter()-started
            telemetry=engine.telemetry();telemetry.pop('scheduler',None)
            save(out/'LIVE.json',dict(phase='paced_source',elapsed_sec=elapsed,telemetry=telemetry,counts=dict(counts),
                application_artifact_bytes=tree_bytes(session),native_event_log_bytes=(session/'events.jsonl').stat().st_size,
                native_journal_bytes=(session/'audio_spool.pcm16').stat().st_size))
            if elapsed-lastbeat>=20:
                print(json.dumps(dict(phase='paced',job_id=job['job_id'],elapsed_sec=elapsed,source_sec=telemetry['source_duration_sec'])),flush=True);lastbeat=elapsed
            if elapsed>args.timeout:raise TimeoutError('Paced worker time bound exceeded')
            if (Path(plan['output_root'])/'STOP_NOW').exists():raise InterruptedError('Owned paced STOP_NOW requested')
            time.sleep(.25)
        engine.wait_for_completion(65);drain()
        if engine.state!='COMPLETED':raise RuntimeError('Native engine failed')
        summary=read(session/'session_summary.json');events=[json.loads(x) for x in (session/'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
        t=summary['telemetry'];journal=bind(session/'audio_spool.pcm16')
        expected=round(job['duration_sec']*16000)
        if journal['bytes']!=expected*2 or abs(t['asr_cursor_sec']-job['duration_sec'])>1e-7:raise RuntimeError('Complete native PCM/cursor tail mismatch')
        if job['input_pcm_sha256'] and journal['sha256']!=job['input_pcm_sha256']:raise RuntimeError('Indexed/native PCM differs')
        if any(t.get(k,0)!=0 for k in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures')):raise RuntimeError('Native audio loss reported')
        raw_asr=[e['payload'] for e in events if e['event_type']=='research_asr_observation']
        finals=[e['payload'] for e in events if e['event_type']=='transcript_final']
        spans=[(e['payload']['source_start_sec'],e['payload']['source_end_sec']) for e in events if e['event_type'] in ('research_asr_dispatch','research_asr_tail_dispatch')]
        native_delivery=None
        if spans:
            native_delivery=dict(blocks=len(spans),no_gaps_or_duplicates=all(abs(a[1]-b[0])<1e-7 for a,b in zip(spans,spans[1:])),
                starts_at_zero=abs(spans[0][0])<1e-7,ends_at_full_duration=abs(spans[-1][1]-job['duration_sec'])<1e-7,
                exact_samples=sum(round((b-a)*16000) for a,b in spans)==expected)
            if not all(v for k,v in native_delivery.items() if k!='blocks'):raise RuntimeError('Native dispatch sample delivery failed')
        save(out/'DISPLAY_EVENTS.json',display)
        costs={}
        for kind in sorted(set(e['event_type'] for e in events)):
            selected=[e['payload'] for e in events if e['event_type']==kind]
            numeric={}
            for key in ('compute_ms','model_api_elapsed_ms','postprocess_compute_ms','full_dispatch_elapsed_ms','advisor_compute_ms','gate_compute_ms','scheduler_dispatch_ms','policy_compute_sec'):
                vals=[float(x[key]) for x in selected if key in x and x[key] is not None]
                if vals:numeric[key]=sum(vals)
            if numeric:costs[kind]=dict(count=len(selected),inclusive_nested_values=numeric)
        cpu=process.cpu_times();io=process.io_counters()
        result=dict(status='COMPLETE',job_key=job['job_key'],created_utc=utc(),pid=process.pid,creation_time=process.create_time(),
            full_worker_elapsed_sec=time.perf_counter()-started,bundle_admission_sec=bundle_load_sec,engine_launch_loading_sec=launch_sec,
            source_started_wall_time_utc=source_started,session_dir=str(session),summary=summary,source_duration_sec=job['duration_sec'],
            complete_pcm_samples=expected,native_pcm_exact=True,asr_cursor_complete=True,native_dispatch_delivery=native_delivery,
            baseline_dispatch_instrumentation_unavailable=job['profile'] is None,events=bind(session/'events.jsonl'),journal=journal,
            display_events=bind(out/'DISPLAY_EVENTS.json'),summary_binding=bind(session/'session_summary.json'),
            final_raw_texts=[x['text'] for x in finals],final_labels=[x.get('speaker') for x in finals],raw_asr_observations=len(raw_asr),event_counts=dict(counts),
            costs=costs,cost_scope='Inclusive full dispatch and nested model costs must not be added together; lanes are concurrent. Worker CPU includes observation/export overhead.',
            process_cpu_sec_at_end=cpu.user+cpu.system,process_io_write_bytes_at_end=io.write_bytes,final_artifact_bytes=tree_bytes(session),
            clock_scope='Paced actual native event emission; modeled scheduler/cue clock is separate; no GUI display-latency or historical-wall join claim',
            empty_gallery=True,hardware_calls=0,truth_passed_to_predictor=False,numeric_pools={k:os.environ[k] for k in NUMERIC_KEYS})
        save(out/'WORKER_RESULT.json',result)
    except BaseException:
        if engine is not None:
            engine.stop()
            try:engine.wait_for_completion(65)
            except Exception:pass
        save(out/'WORKER_FAILURE.json',dict(status='FAILED',created_utc=utc(),job_key=job['job_key'],traceback=traceback.format_exc()))
        raise


def stop_owned(owned):
    for pid,created in reversed(list(owned.items())):
        if matches(pid,created):
            try:psutil.Process(pid).terminate()
            except psutil.Error:pass
    until=time.monotonic()+10
    while time.monotonic()<until and any(matches(p,c) for p,c in owned.items()):time.sleep(.1)
    for pid,created in reversed(list(owned.items())):
        if matches(pid,created):
            try:psutil.Process(pid).kill()
            except psutil.Error:pass


def run(args,plan):
    verify(plan);args.output.mkdir(parents=True,exist_ok=True)
    lock=args.output/'COORDINATOR.json';me=psutil.Process()
    if lock.exists():
        previous=read(lock)
        if matches(previous['pid'],previous['creation_time']):raise RuntimeError('A paced coordinator already owns this output')
        lock.rename(args.output/('COORDINATOR_STALE_'+str(time.time_ns())+'.json'))
    with lock.open('x',encoding='utf-8') as f:json.dump(dict(pid=me.pid,creation_time=me.create_time(),manifest_key=plan['manifest_key']),f)
    print(json.dumps(dict(phase='paced_coordinator',pid=me.pid,creation_time=me.create_time(),jobs=len(plan['jobs']),audio_minutes=plan['total_audio_sec']/60)),flush=True)
    try:
        for job in plan['jobs']:
            if (args.output/'STOP_REQUEST').exists() or (args.report/'STOP_REQUEST').exists():break
            out=args.output/'jobs'/job['job_id'];out.mkdir(parents=True,exist_ok=True)
            completed=out/'COMPLETE.json'
            if completed.exists():
                old=read(completed)
                if old['job_key']!=job['job_key']:raise RuntimeError('Completed paced job identity differs')
                for row in old['artifacts']:bind(row['path'],row['sha256'])
                if any(matches(p['pid'],p['creation_time']) for p in old['owned_processes']):raise RuntimeError('Completed job still has live owned process')
                continue
            if (out/'LAUNCH.json').exists():raise RuntimeError('Incomplete attempt preserved; inspect failure and use a new output namespace or an explicit repaired resume manifest')
            sample=resource_sample(plan['payload_root'],args.report/args.epoch/'workers');assert_resources(sample,plan['resource_limits'])
            active_epoch_workers={}
            for status_path in (args.report/args.epoch/'workers').glob('*.json'):
                status=read(status_path)
                if matches(status.get('pid',-1),status.get('creation_time',-1)):
                    active_epoch_workers[status['pid']]=status['creation_time']
            if len(active_epoch_workers)>=plan['resource_limits']['max_workers']:
                raise RuntimeError('No model-worker slot reserved: frozen epoch already has four live workers')
            scoped_bytes=tree_bytes(plan['payload_root'])+tree_bytes(args.report)+tree_bytes(args.sim/'staging/s6b'/args.report.name)
            if scoped_bytes>plan['resource_limits']['new_output_cap_bytes']:raise RuntimeError('New run output cap reached (G payload + C report/staging)')
            bind(plan['driver']['path'],plan['driver']['sha256'])
            argv=[sys.executable,str(Path(__file__).resolve()),'--mode','worker','--manifest',str(args.output/'MANIFEST.json'),'--job-id',job['job_id'],'--timeout',str(args.timeout)]
            owned={};samples=[];started=time.perf_counter()
            with (out/'stdout.log').open('x',encoding='utf-8') as log:
                child=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                process=psutil.Process(child.pid);owned[child.pid]=process.create_time()
                save(out/'LAUNCH.json',dict(pid=child.pid,creation_time=owned[child.pid],job_key=job['job_key'],argv=argv,created_utc=utc()))
                print(json.dumps(dict(phase='paced_launch',job_id=job['job_id'],pid=child.pid,creation_time=owned[child.pid])),flush=True)
                try:
                    beat=0.
                    with (out/'PROCESS_SAMPLES.jsonl').open('x',encoding='utf-8',buffering=1) as trajectory:
                        while child.poll() is None:
                            tree=sample_tree(process)
                            for p in tree['processes']:owned[p['pid']]=p['creation_time']
                            live=read(out/'LIVE.json') if (out/'LIVE.json').exists() else None
                            elapsed=time.perf_counter()-started
                            row=dict(elapsed_sec=elapsed,created_utc=utc(),tree=tree,live=live,coordinator_rss_bytes=me.memory_info().rss)
                            samples.append(row);trajectory.write(json.dumps(row,allow_nan=False)+'\n')
                            if elapsed-beat>=20:
                                current=resource_sample(plan['payload_root'],args.report/args.epoch/'workers');assert_resources(current,plan['resource_limits'])
                                save(args.output/'HEARTBEAT.json',dict(phase='PACED_NATIVE',job_id=job['job_id'],elapsed_sec=elapsed,source_duration_sec=(live or {}).get('telemetry',{}),resources=current,created_utc=utc()))
                                print(json.dumps(dict(phase='paced_heartbeat',job_id=job['job_id'],elapsed_sec=elapsed)),flush=True);beat=elapsed
                            if elapsed>args.timeout+75:raise TimeoutError('Owned worker exceeded coordinator bound')
                            if (args.output/'STOP_NOW').exists():raise InterruptedError('STOP_NOW')
                            time.sleep(.5)
                    if child.returncode!=0:raise RuntimeError('Paced worker failed; see '+str(out/'stdout.log'))
                    result=read(out/'WORKER_RESULT.json')
                    if result['job_key']!=job['job_key'] or result['status']!='COMPLETE':raise RuntimeError('Worker result identity/status invalid')
                    until=time.monotonic()+5
                    while any(matches(p,c) for p,c in owned.items()) and time.monotonic()<until:time.sleep(.1)
                    if any(matches(p,c) for p,c in owned.items()):raise RuntimeError('Owned child survived successful native close')
                    artifacts=[bind(out/'WORKER_RESULT.json'),bind(out/'PROCESS_SAMPLES.jsonl'),result['events'],result['journal'],result['display_events'],result['summary_binding']]
                    save(completed,dict(status='COMPLETE',job_key=job['job_key'],created_utc=utc(),worker=result,artifacts=artifacts,
                        owned_processes=[dict(pid=p,creation_time=c) for p,c in owned.items()],all_owned_processes_closed=True))
                except BaseException:
                    stop_owned(owned)
                    save(out/'FAILURE.json',dict(status='FAILED',created_utc=utc(),job_key=job['job_key'],traceback=traceback.format_exc(),
                        owned_processes=[dict(pid=p,creation_time=c,alive=matches(p,c)) for p,c in owned.items()]))
                    raise
        return summarize(args,plan)
    finally:
        if lock.exists():lock.rename(args.output/('COORDINATOR_CLOSED_'+str(time.time_ns())+'.json'))


def summarize(args,plan):
    rows=[];results={}
    for job in plan['jobs']:
        out=args.output/'jobs'/job['job_id']
        if not (out/'COMPLETE.json').exists():continue
        done=read(out/'COMPLETE.json');worker=done['worker'];results[job['job_id']]=worker
        samples=[json.loads(x) for x in (out/'PROCESS_SAMPLES.jsonl').read_text(encoding='utf-8').splitlines()]
        def peak(key):
            v=[s['tree'].get(key) for s in samples if s['tree'].get(key) is not None];return max(v) if v else None
        def backlog(key):
            values=[max(0.,s['live']['telemetry']['source_duration_sec']-s['live']['telemetry'][key]) for s in samples if (s.get('live') or {}).get('telemetry')]
            return dict(max_sec=max(values) if values else None,last_sec=values[-1] if values else None,trajectory_samples=len(values))
        def memory_trend(key):
            series=[s for s in samples if s['tree'].get(key) is not None]
            paced=[s for s in series if (s.get('live') or {}).get('phase')=='paced_source']
            return dict(first_process_bytes=series[0]['tree'][key] if series else None,last_process_bytes=series[-1]['tree'][key] if series else None,
                first_paced_bytes=paced[0]['tree'][key] if paced else None,last_paced_bytes=paced[-1]['tree'][key] if paced else None,
                paced_delta_bytes=paced[-1]['tree'][key]-paced[0]['tree'][key] if paced else None,
                measured_paced_samples=len(paced),interpretation='One recipe/model bundle in a fresh process; delta alone is not a leak diagnosis')
        row=dict(job_id=job['job_id'],profile_id=job['profile_id'],case_id=job['case_id'],stream=job['stream'],repetition=job['repetition'],
            source_duration_sec=job['duration_sec'],full_worker_elapsed_sec=worker['full_worker_elapsed_sec'],startup_bundle_sec=worker['bundle_admission_sec'],
            startup_engine_launch_sec=worker['engine_launch_loading_sec'],process_cpu_sec=worker['process_cpu_sec_at_end'],
            private_resident_uss_peak_bytes=peak('private_resident_uss_sum_bytes'),rss_sum_upper_bound_peak_bytes=peak('rss_sum_upper_bound_bytes'),
            windows_private_commit_peak_bytes=peak('windows_private_commit_sum_bytes'),pss_peak_bytes=peak('pss_sum_bytes'),
            nonunique_shared_resident_estimate_peak_bytes=peak('nonunique_shared_resident_estimate_bytes'),peak_full_tree_threads=peak('full_tree_threads'),
            minimum_host_available_ram_bytes=min(s['tree']['system_available_ram_bytes'] for s in samples),
            application_artifact_bytes=worker['final_artifact_bytes'],process_write_bytes=worker['process_io_write_bytes_at_end'],
            process_write_bytes_per_audio_second=worker['process_io_write_bytes_at_end']/job['duration_sec'],
            asr_backlog=backlog('asr_cursor_sec'),speaker_backlog=backlog('speaker_cursor_sec'),event_counts=worker['event_counts'],
            sample_count=len(samples),no_pcm_loss=worker['native_pcm_exact'],asr_cursor_complete=worker['asr_cursor_complete'],
            all_owned_processes_closed=done['all_owned_processes_closed'],model_threads='historical config default' if job['profile'] is None else job['profile']['runtime'])
        row['private_resident_uss_trend']=memory_trend('private_resident_uss_sum_bytes')
        row['rss_sum_upper_bound_trend']=memory_trend('rss_sum_upper_bound_bytes')
        row['windows_private_commit_trend']=memory_trend('windows_private_commit_sum_bytes')
        cpu_by_pid={}
        for sample in samples:
            for process in sample['tree']['processes']:
                k=(process['pid'],process['creation_time']);cpu_by_pid[k]=max(cpu_by_pid.get(k,0.),process['cpu_seconds'])
        row['full_tree_cpu_sampled_lower_bound_sec']=sum(cpu_by_pid.values())
        row['incomplete_process_tree_sample_count']=sum(not s['tree']['tree_complete'] for s in samples)
        clock_rows=read(worker['display_events']['path'])
        origin=datetime.fromisoformat(worker['source_started_wall_time_utc']) if worker['source_started_wall_time_utc'] else None
        def lag_quantiles(event_type):
            vals=sorted((datetime.fromisoformat(e['emitted_wall_time_utc'])-origin).total_seconds()-e['source_time_sec'] for e in clock_rows if e['event_type']==event_type) if origin else []
            return dict(count=len(vals),minimum_sec=vals[0] if vals else None,median_sec=vals[len(vals)//2] if vals else None,p95_sec=vals[min(len(vals)-1,int(.95*len(vals)))] if vals else None,maximum_sec=vals[-1] if vals else None)
        row['native_emission_minus_source_cursor_sec']={k:lag_quantiles(k) for k in ('transcript_partial','transcript_final','transcript_label_revision')}
        row['emission_lag_limit']='Relative to current-run source_started UTC; includes pacing/dispatch/release. Not phoneme-to-token latency or GUI latency; wall clock adjustment remains possible.'
        rows.append(row)
    pairs=[]
    groups=defaultdict(list)
    for job in plan['jobs']:
        if job['job_id'] in results:groups[job['profile_id'],job['case_id'],job['stream']].append(job)
    for key,jobs in groups.items():
        first=jobs[0]
        for second in jobs[1:]:
            a,b=results[first['job_id']],results[second['job_id']]
            def display(w):
                return [(x['event_type'],x['source_time_sec'],x['payload'].get('utterance_id',x['payload'].get('utterance_index')),
                         x['payload'].get('text'),x['payload'].get('speaker'),x['payload'].get('latest_label')) for x in read(w['display_events']['path'])]
            def features(w):
                return [e['payload'] for e in (json.loads(x) for x in Path(w['events']['path']).read_text(encoding='utf-8').splitlines() if x.strip()) if e['event_type']=='research_embedding']
            va,vb=features(a),features(b);vector_comparison=None
            if va or vb:
                import math
                spans=lambda v:[(x['source_start_sec'],x['source_end_sec'],x.get('receptive_start_sec'),x.get('receptive_end_sec')) for x in v]
                exact_spans=spans(va)==spans(vb)
                finite=all(math.isfinite(float(z)) for x in va+vb for z in x['normalized_embedding'])
                maximum=max((abs(float(u)-float(v)) for x,y in zip(va,vb) for u,v in zip(x['normalized_embedding'],y['normalized_embedding'])),default=0.) if exact_spans and finite else None
                vector_comparison=dict(counts=[len(va),len(vb)],spans_exact=exact_spans,all_finite=finite,maximum_absolute_difference=maximum,within_1e_minus_6=maximum is not None and maximum<=1e-6)
            pairs.append(dict(profile_id=key[0],case_id=key[1],stream=key[2],repetitions=[first['repetition'],second['repetition']],
                raw_final_words_exact=a['final_raw_texts']==b['final_raw_texts'],final_labels_exact=a['final_labels']==b['final_labels'],
                complete_native_display_sequence_exact=display(a)==display(b),journals_exact=a['journal']['sha256']==b['journal']['sha256'],embedding_parity=vector_comparison,
                inference='All repetitions retained. Timing variability and label changes are observations, not reasons to rerun.'))
    status='COMPLETE' if len(rows)==len(plan['jobs']) else 'PARTIAL_RESUMABLE'
    result=dict(schema='s6b-paced-summary.v1',status=status,created_utc=utc(),manifest=bind(args.output/'MANIFEST.json'),completed_jobs=len(rows),expected_jobs=len(plan['jobs']),
        rows=rows,repetition_comparisons=pairs,remaining_jobs=[j['job_id'] for j in plan['jobs'] if j['job_id'] not in results],
        scope='Desktop paced full engine including observer overhead. No CM5 throughput/2GB/thermal qualification. No best repetition chosen.',
        memory_semantics=dict(uss='private resident',rss='sum upper bound; shared pages duplicated',private_commit='private committed virtual bytes; not resident RAM',
            shared_estimate='RSS-USS nonunique estimate; not PSS',pss='unavailable when null'),
        b0_limit='Exact baseline source and defaults; no v2 internal ASR dispatch trace. Journal/cursor/tail and durable completion verified.',
        clocks='Native event emission is measured; modeled scheduler/cue availability remains distinct. No GUI display timestamp is claimed.')
    save(args.output/'SUMMARY.json',result);save(args.report/'paced'/args.output.name/'SUMMARY.json',result)
    return dict(status=status,complete=len(rows),expected=len(plan['jobs']),summary=str(args.output/'SUMMARY.json'))


def self_test(args):
    import tempfile
    import importlib.util
    import numpy as np
    import soundfile as sf
    if args.report is None:raise ValueError('--report is required for frozen runtime conversion tests')
    spec=read(args.report/(args.epoch.upper()+'_EXECUTION_MANIFEST.json'))
    check_runtime_versions(spec['runtime_versions'])
    rejected=False
    try:check_runtime_versions(spec['runtime_versions']|{'numpy':'deliberate-mismatch'})
    except RuntimeError:rejected=True
    assert rejected
    audio_path=Path(spec['root'])/'app/edge_speech_pipeline/audio.py'
    declared=next(r for r in spec['execution_files'] if Path(r['path'])==audio_path);bind(audio_path,declared['sha256'])
    module_spec=importlib.util.spec_from_file_location('s6b_paced_frozen_audio_fixture',audio_path)
    audio=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(audio)
    conversion_checks=[]
    with tempfile.TemporaryDirectory(prefix='s6b_paced_fixture_') as d:
        p=Path(d)/'dependency';p.write_bytes(b'abcd');original=bind(p)
        bind(p,original['sha256']);p.write_bytes(b'efgh')
        rejected=False
        try:bind(p,original['sha256'])
        except RuntimeError:rejected=True
        assert rejected
        p.write_bytes(b'abcd');assert bind(p,original['sha256'])==original
        target=Path(d)/'status.json';save(target,{'finite':1});assert read(target)=={'finite':1}
        assert not matches(999999999,0)
        tree=sample_tree(psutil.Process());assert tree['rss_sum_upper_bound_bytes']>0
        wav=Path(d)/'pcm.wav';body=b'\x00\x10'*1707
        with wave.open(str(wav),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(body)
        pcm=pcm16_hash(wav);assert pcm['samples']==1707 and pcm['sha256']==hashlib.sha256(body).hexdigest()
        for subtype in ('PCM_16','FLOAT'):
            source_path=Path(d)/(subtype+'.wav');journal_path=Path(d)/(subtype+'.pcm')
            values=np.resize(np.array([-1.2,-1.,-.5,-.5/32768,0.,.5/32768,.5,.999969,1.,1.2],dtype=np.float32),1707)
            sf.write(source_path,values,16000,subtype=subtype);expected=pcm16_hash(source_path)
            journal=audio.AudioJournal(journal_path);source=audio.WavSource(journal,source_path,target_rate=16000,realtime=False,accelerated_factor=0)
            source.start();source.thread.join(timeout=10)
            if source.thread.is_alive():source.stop();raise RuntimeError('Conversion fixture timed out')
            assert journal.finished and journal.fatal_error is None and journal.committed_samples==1707
            assert bind(journal_path)['sha256']==expected['sha256']
            conversion_checks.append(dict(source_subtype=subtype,exact_frozen_entrypoint_equal=True,samples=1707))
    result=dict(status='PASS',tests=10,scope='Six prior model-free guards plus runtime acceptance/rejection and two actual frozen WavSource/AudioJournal PCM16/FLOAT conversion checks; no neural execution',driver=bind(__file__),created_utc=utc(),conversion_checks=conversion_checks,frozen_audio=declared)
    if args.report:save(args.report/'paced/PACED_DRIVER_CHECKS.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('prepare','run','summarize','worker','check'),default='prepare')
    p.add_argument('--sim',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--report',type=Path)
    p.add_argument('--epoch',default='epoch2');p.add_argument('--profiles',default='B00');p.add_argument('--repetitions',type=int,default=2)
    p.add_argument('--cases',default=','.join(DEFAULT_CASES));p.add_argument('--streams',default='O0');p.add_argument('--output',type=Path)
    p.add_argument('--manifest',type=Path);p.add_argument('--job-id');p.add_argument('--timeout',type=float,default=180.)
    args=p.parse_args()
    for key in NUMERIC_KEYS:os.environ[key]='1'
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    sys.dont_write_bytecode=True
    if not 1<=args.repetitions<=3 or not 60<=args.timeout<=600:raise ValueError('Bounded repetitions1..3 and timeout60..600 required')
    if args.mode=='worker':worker(args);return 0
    if args.mode=='check':print(json.dumps(self_test(args),indent=2));return 0
    if args.report is None or args.output is None:p.error('--report and --output required')
    plan=read(args.output/'MANIFEST.json') if args.mode=='summarize' else prepare(args)
    if args.mode=='prepare':
        # Always compare caller selection even when an existing plan is present.
        result=dict(status='PREPARED_NO_MODELS_STARTED',jobs=len(plan['jobs']),audio_minutes=plan['total_audio_sec']/60,manifest=str(args.output/'MANIFEST.json'))
    elif args.mode=='run':result=run(args,plan)
    else:result=summarize(args,plan)
    print(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
