"""Frozen, resident-model S6B neural execution and exact resume. README_S6B_EXECUTION.md."""
from __future__ import annotations
import argparse
import concurrent.futures
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import traceback

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
from s6b_common import *

_WORKER={}
_QUOTA_CACHE={'checked':0.,'bytes':0}

def csv_write(path,rows):
    import csv
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)

def freeze(epoch='epoch1'):
    target=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json')
    if target.exists():
        spec=read(target)
        for row in spec['execution_files']:bind(row['path'],row['sha256'])
        return spec
    recipes=read(REPORT/'NEURAL_RECIPE_REGISTRY.json')
    if recipes['status']!='VALIDATED': raise ValueError('Validated recipe registry required')
    root=STAGING/epoch
    if root.exists(): raise ValueError('Unreceipted epoch folder exists')
    shutil.copytree(APP,root/'app/edge_speech_pipeline',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (root/'scripts').mkdir()
    for p in (SIM/'scripts').glob('s6b*.py'): shutil.copy2(p,root/'scripts'/p.name)
    sys.path.insert(0,str(H2/'app'))
    from edge_speech_pipeline.config import PipelineConfig
    assets=[]
    for asset in PipelineConfig().assets:
        assets.append(dict(**asdict(asset),binding=bind(asset.path,asset.sha256)))
        assets[-1]['path']=str(assets[-1]['path'])
    execution=[bind(p) for p in sorted(root.rglob('*.py'))]
    from importlib.metadata import version
    runtime_versions={name:version(name) for name in ('onnxruntime','sherpa-onnx','numpy')}
    runtime_versions['python']=sys.version
    spec=dict(schema='jp_s6b_execution_epoch_v1',epoch=epoch,created_utc=utc(),root=str(root),runtime_versions=runtime_versions,
        execution_files=execution,assets=assets,recipes=recipes['recipes'],recipe_registry=bind(REPORT/'NEURAL_RECIPE_REGISTRY.json'),
        predictor_interface='actual frozen application incremental scheduler/tracker with fixed actual neural weights',
        worker_limits=dict(max_workers=4,inner_pools=1,host_available_min_bytes=16*2**30,research_rss_cap_bytes=40*2**30,
            c_free_min_bytes=50*2**30,g_free_min_bytes=75*2**30,new_output_cap_bytes=120*2**30),
        input_index=bind(REPORT/'INPUT_INDEX.json'),gain_index=bind(REPORT/'GAIN_INPUT_INDEX.json'),
        effective_profile_registry=bind(REPORT/'EFFECTIVE_PROFILE_REGISTRY.json'),challenge_panel=bind(REPORT/'design/CHALLENGE_PANEL.json'),
        scene_manifest=bind(BANK),
        state_scope='resident immutable model objects; fresh decoder stream, endpoint, speaker/tracker and transcript state for every scene',
        documentation_excluded_from_inference_identity=True)
    spec['execution_digest']=digest({k:spec[k] for k in ('execution_files','assets','recipes','state_scope','runtime_versions')})
    save(target,spec);return spec

def worker_init(spec_path):
    import psutil
    spec=read(spec_path)
    for b in spec['execution_files']:bind(b['path'],b['sha256'])
    sys.path.insert(0,str(Path(spec['root'])/'app'))
    from edge_speech_pipeline.config import PipelineConfig,AssetSpec
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.runtime import PipelineEngine
    from edge_speech_pipeline.models import ResidentModelBundle
    pid=os.getpid();p=psutil.Process(pid);worker_root=PAYLOAD/spec['epoch']/'workers'/str(pid)
    assets=tuple(AssetSpec(**{k:r[k] for k in ('component_id','path','sha256','deployment_relative_path')}) for r in spec['assets'])
    # AssetSpec paths are concrete even when the app is imported from a snapshot.
    assets=tuple(AssetSpec(a.component_id,Path(a.path),a.sha256,a.deployment_relative_path) for a in assets)
    config=PipelineConfig(assets=assets,session_root=worker_root/'sessions',profile_root=worker_root/'empty_profiles')
    _WORKER.update(spec=spec,config=config,ResearchProfile=ResearchProfile,JsonSpatialProvider=JsonSpatialProvider,
        PipelineEngine=PipelineEngine,ResidentModelBundle=ResidentModelBundle,bundle=None,bundle_key=None,loads=0,
        status_path=REPORT/spec['epoch']/'workers'/(str(pid)+'.json'),pid=pid,creation_time=p.create_time())
    save(_WORKER['status_path'],dict(status='READY',pid=pid,creation_time=p.create_time(),utc=utc(),argv=sys.argv))

def extract_events(events):
    """Preserve actual neural emissions, without inserting task truth."""
    import numpy as np
    embeddings=[];vectors=[];asr=[];segs=[];costs={}
    for e in events:
        kind=e['event_type'];p=e['payload']
        if kind=='research_embedding':
            vector=p.get('normalized_embedding',p.get('vector'))
            if vector is None: raise ValueError('Actual embedding vector missing')
            row={k:v for k,v in p.items() if k not in ('normalized_embedding','vector','decision')}
            row['index']=len(vectors)
            row['available_at_sec']=p.get('available_at_sec',p.get('modeled_available_at_sec'))
            row['speech']=p.get('speech',True);row['overlap']=p.get('overlap',False)
            embeddings.append(row);vectors.append(vector)
        elif kind=='research_segmentation':
            segs.append(dict(p,available_at_sec=p.get('available_at_sec',p.get('modeled_available_at_sec'))))
        elif kind=='research_asr_observation':
            asr.append(dict(p))
    # A v2 native run exports input observations independently of scheduler outputs.
    if not asr:
        for e in events:
            if e['event_type'] not in ('transcript_partial','transcript_final'):continue
            p=e['payload'];end=float(e['source_time_sec'])
            asr.append(dict(kind='asr',event_id=p.get('event_id','asr_'+str(len(asr))),
                utterance_id=str(p.get('utterance_id',p.get('utterance_index'))),text=p['text'],
                final=e['event_type']=='transcript_final',source_start_sec=p.get('source_start_sec',0.),source_end_sec=end,
                available_at_sec=p.get('available_at_sec',p.get('modeled_available_at_sec')),display_text=p.get('display_text'),
                punctuation=p.get('punctuation')))
    if any(r.get('available_at_sec') is None for r in embeddings+segs+asr): raise ValueError('Explicit causal availability missing')
    for kind in ('research_asr_dispatch','research_asr_tail_dispatch','research_asr_drain','research_segmentation','research_embedding',
                 'research_asr_full_dispatch_cost','research_speaker_dispatch_cost','research_embedding_admission','research_asr_reset',
                 'research_models_ready','research_resident_bundle'):
        selected=[e['payload'] for e in events if e['event_type']==kind]
        costs[kind]=dict(calls=len(selected),compute_sec=sum(float(p.get('compute_ms',0))/1000 for p in selected))
        for field in ('postprocess_compute_ms','model_api_elapsed_ms','full_dispatch_elapsed_ms','decode_compute_ms','advisor_compute_ms',
                      'segment_compute_ms','embedding_compute_ms','gate_compute_ms','scheduler_dispatch_ms'):
            if any(field in p for p in selected):costs[kind][field.replace('_ms','_sec')]=sum(float(p.get(field,0))/1000 for p in selected)
        for field in ('model_load_elapsed_sec','bundle_admission_elapsed_sec'):
            if any(field in p for p in selected):costs[kind][field]=sum(float(p.get(field,0) or 0) for p in selected)
    finals=[e['payload'] for e in events if e['event_type']=='transcript_final']
    costs['punctuation']=dict(calls=sum(bool(p.get('punctuation')) for p in finals),
        compute_sec=sum(float((p.get('punctuation') or {}).get('compute_ms',0))/1000 for p in finals))
    from collections import Counter
    costs['observed_operations']=dict(event_counts=dict(Counter(e['event_type'] for e in events)),
        admission_reasons=dict(Counter(str(e['payload'].get('reason','unspecified')) for e in events if e['event_type']=='research_embedding_admission')))
    costs['accounting_scope']='Full dispatch is inclusive of nested model/gate/policy/export work. Do not add inclusive totals to nested phases or sum concurrent lane wall times into real-time latency.'
    return np.asarray(vectors,np.float32).reshape((-1,192)),embeddings,segs,asr,costs

def worker_job(job):
    import psutil
    import numpy as np
    w=_WORKER;process=psutil.Process();folder=Path(job['folder']);folder.mkdir(parents=True,exist_ok=True)
    status=dict(status='RUNNING',pid=w['pid'],creation_time=w['creation_time'],case_id=job['case_id'],stream=job['stream'],recipe_id=job['recipe_id'],utc=utc())
    save(w['status_path'],status)
    started=time.perf_counter();cpu0=process.cpu_times();engine=None
    receipt=dict(status='STARTED',job_key=job['job_key'],identity=job['identity'],case_id=job['case_id'],stream=job['stream'],recipe_id=job['recipe_id'],
        pid=w['pid'],creation_time=w['creation_time'],started_utc=utc(),truth_sent_to_predictor=False,hardware_invocations=0)
    save(folder/'attempt_receipt.json',receipt)
    try:
        bind(job['audio']['path'],job['audio']['sha256'])
        profile=w['ResearchProfile'].from_dict(job['profile'])
        config=profile.apply(w['config'])
        config_key=digest({k:v for k,v in asdict(config).items() if k not in ('session_root','profile_root','assets')})
        load_start=time.perf_counter()
        if w['bundle_key']!=config_key:
            w['bundle']=None
            w['bundle']=w['ResidentModelBundle'](config)
            w['bundle_key']=config_key;w['loads']+=1
        load_seconds=time.perf_counter()-load_start
        if job['telemetry']:bind(job['telemetry']['path'],job['telemetry']['sha256'])
        provider=w['JsonSpatialProvider'](Path(job['telemetry']['path'])) if job['telemetry'] else None
        if provider is not None and provider.sha256!=job['telemetry']['sha256']:raise ValueError('Provider consumed different telemetry bytes')
        engine=w['PipelineEngine'](w['config'],research_profile=profile,spatial_provider=provider,model_bundle=w['bundle'])
        native_cpu0=process.cpu_times();native_started=time.perf_counter()
        session=engine.start_file(Path(job['audio']['path']),realtime=False,accelerated_factor=0)
        engine.wait_for_completion(timeout=360)
        native_elapsed=time.perf_counter()-native_started;native_cpu1=process.cpu_times()
        if engine.state!='COMPLETED': raise RuntimeError('Native engine not completed: '+engine.state)
        events=[json.loads(line) for line in (session/'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        if sum(e['event_type']=='session_completed' for e in events)!=1 or any(e['event_type']=='failure' for e in events):raise ValueError('Native completion events invalid')
        summary=read(session/'session_summary.json')
        for key in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):
            if summary['telemetry'][key]!=0:raise ValueError('Native dropped audio: '+key)
        journal=bind(session/'audio_spool.pcm16')
        if journal['bytes']!=round(job['duration_sec']*16000)*2: raise ValueError('Full native input journal missing tail')
        if job.get('audio_pcm_sha256') and journal['sha256']!=job['audio_pcm_sha256']:raise ValueError('Native input gain/PCM parity failed')
        vectors,features,segs,asr,costs=extract_events(events)
        costs['native_full_engine']=dict(elapsed_sec=native_elapsed,
            process_cpu_sec=native_cpu1.user+native_cpu1.system-native_cpu0.user-native_cpu0.system,
            separate_bundle_admission_sec=load_seconds,
            scope='start_file through completed native finalization, including native journals/export/EOF; excludes downstream evidence-cache extraction; desktop accelerated, not hardware latency')
        npz=folder/'vectors.npz';np.savez_compressed(npz,vectors=vectors)
        evidence=dict(schema='jp_s6b_actual_neural_evidence_v1',job_key=job['job_key'],identity=job['identity'],
            vectors=bind(npz),features=features,segmentation=segs,asr_observations=asr,costs=costs,
            duration_sec=job['duration_sec'],native_events=bind(session/'events.jsonl'),native_summary=bind(session/'session_summary.json'),
            full_native_journal=journal,source_input=job['audio'],frontend='actual fixed Pyannote/ReDim/Sherpa native methods',
            reference_oracle_inputs=False,created_utc=utc())
        save(folder/'evidence.json',evidence)
        receipt.update(status='COMPLETE',evidence=bind(folder/'evidence.json'),vectors=bind(npz),events=evidence['native_events'],
            summary=evidence['native_summary'],session_dir=str(session),full_journal=journal,
            initial_or_changed_recipe_model_load_sec=load_seconds,resident_bundle_load_count=w['loads'],
            actual_neural_counts={k:v['calls'] for k,v in costs.items() if isinstance(v,dict) and 'calls' in v},audio_duration_sec=job['duration_sec'])
    except Exception as exc:
        receipt.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
        if engine is not None and engine.state not in ('COMPLETED','FAILED','IDLE'):
            engine.stop()
            try:engine.wait_for_completion(timeout=15)
            except Exception:pass
    finally:
        cpu1=process.cpu_times()
        receipt.update(finished_utc=utc(),full_engine_wall_sec=time.perf_counter()-started,
            full_process_cpu_sec=cpu1.user+cpu1.system-cpu0.user-cpu0.system,
            cost_scope='Complete process CPU and elapsed for native session including frontend/gates/tracking/revisions/export/EOF; resident model load separately recorded; concurrent CPU is not wall latency')
        save(folder/'attempt_receipt.json',receipt)
        if receipt['status']=='COMPLETE':save(folder/'run_receipt.json',receipt)
        save(w['status_path'],dict(status='READY' if receipt['status']=='COMPLETE' else 'FAILED',pid=w['pid'],creation_time=w['creation_time'],last_job=job['job_key'],utc=utc()))
    return dict(case_id=job['case_id'],stream=job['stream'],recipe_id=job['recipe_id'],status=receipt['status'],
        receipt=bind(folder/('run_receipt.json' if receipt['status']=='COMPLETE' else 'attempt_receipt.json')),
        full_engine_wall_sec=receipt['full_engine_wall_sec'],audio_duration_sec=job['duration_sec'],error=receipt.get('error'))

def make_job(spec,recipe,main,alternate):
    inp=alternate[main['case_id'],main['stream']] if recipe.get('gain_variant')=='minus3' else main
    telemetry=main['telemetry'] if recipe['profile']['xvf']['mode']!='none' else None
    identity=dict(schema='jp_s6b_neural_recipe_job_v1',execution_digest=spec['execution_digest'],
        recipe_id=recipe['recipe_id'],profile=recipe['profile'],audio=inp['audio'],
        input_gain=1.,gain_once=inp.get('raw_gain_applied_once',inp.get('historical_gain_applied_once')),
        telemetry=telemetry,provider='CPUExecutionProvider/cpu',state='fresh stream and session; resident immutable model weights',
        context_policy='exact causal source spans and full EOF drain',inner_pools=1)
    key=digest(identity)
    return dict(case_id=main['case_id'],stream=main['stream'],recipe_id=recipe['recipe_id'],identity=identity,job_key=key,
        audio=inp['audio'],audio_pcm_sha256=inp.get('audio_pcm_sha256'),duration_sec=inp['duration_sec'],telemetry=telemetry,
        profile=recipe['profile'],folder=str(PAYLOAD/spec['epoch']/'neural'/recipe['recipe_id']/main['case_id']/main['stream']))

def build_jobs(spec,panel,recipe_ids):
    inputs=read(spec['input_index']['path'])['rows']
    alternate={(r['case_id'],r['stream']):r for r in read(spec['gain_index']['path'])['rows']}
    ids=set(read(spec['challenge_panel']['path'])['case_ids']) if panel in ('pilot','challenge') else {r['case_id'] for r in inputs}
    if panel=='pilot':
        scenes=read(spec['scene_manifest']['path'])['scenes']
        ids={min(s['case_id'] for s in scenes if s['case_id'] in ids and s['family_id']==family) for family in ('F01','F03','F04','F06')}
    jobs=[]
    for recipe in spec['recipes']:
        if recipe_ids and recipe['recipe_id'] not in recipe_ids:continue
        for main in inputs:
            if main['case_id'] not in ids:continue
            jobs.append(make_job(spec,recipe,main,alternate))
    return jobs

def verify_cached(job):
    path=Path(job['folder'])/'run_receipt.json'
    if not path.exists():return None
    bind(job['audio']['path'],job['audio']['sha256'])
    if job['telemetry']:bind(job['telemetry']['path'],job['telemetry']['sha256'])
    rec=read(path)
    if rec['status']!='COMPLETE' or rec['job_key']!=job['job_key'] or rec['identity']!=job['identity']:raise ValueError('Exact cache identity mismatch: '+str(path))
    for key in ('evidence','vectors','events','summary','full_journal'):bind(rec[key]['path'],rec[key]['sha256'])
    return dict(case_id=job['case_id'],stream=job['stream'],recipe_id=job['recipe_id'],status='COMPLETE_REUSED',receipt=bind(path),
        full_engine_wall_sec=0.,audio_duration_sec=job['duration_sec'])

def resources():
    import psutil
    p=psutil.Process();tree=[p]+p.children(recursive=True);rows=[]
    for child in tree:
        try:
            m=child.memory_full_info();c=child.cpu_times()
            rows.append(dict(pid=child.pid,creation_time=child.create_time(),rss=m.rss,uss=getattr(m,'uss',None),
                private_commit=getattr(m,'private',None),threads=child.num_threads(),cpu_sec=c.user+c.system))
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    if time.monotonic()-_QUOTA_CACHE['checked']>60:
        total=0
        for root in (REPORT,STAGING,PAYLOAD):
            for parent,dirs,files in os.walk(root):
                for name in files:
                    try:total+=(Path(parent)/name).stat().st_size
                    except FileNotFoundError:pass
        _QUOTA_CACHE.update(checked=time.monotonic(),bytes=total)
    return dict(utc=utc(),new_output_bytes=_QUOTA_CACHE['bytes'],available_ram_bytes=psutil.virtual_memory().available,c_free_bytes=shutil.disk_usage('C:/').free,
        g_free_bytes=shutil.disk_usage('G:/').free,processes=rows,research_rss_upper_bound_bytes=sum(r['rss'] for r in rows))

def allowed(sample):
    from datetime import datetime,timezone,timedelta
    deadline=datetime(2026,9,9,23,8,40,tzinfo=timezone.utc)+timedelta(hours=24,minutes=-45)
    return (datetime.now(timezone.utc)<deadline and sample['available_ram_bytes']>=16*2**30 and sample['c_free_bytes']>=50*2**30
        and sample['g_free_bytes']>=75*2**30 and sample['research_rss_upper_bound_bytes']<40*2**30 and sample['new_output_bytes']<120*2**30
        and not (REPORT/'STOP_REQUEST').exists() and not (REPORT/'STOP_REQUEST.json').exists())

def run(epoch,panel,recipe_ids,workers=4,limit=None):
    import msvcrt
    import psutil
    spec_path=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json');spec=read(spec_path)
    if Path(__file__).resolve().parent!=Path(spec['root'])/'scripts':raise ValueError('Execute the frozen script with JP_S6B_SIM set; live code is not an execution epoch')
    for b in spec['execution_files']:bind(b['path'],b['sha256'])
    for key in ('input_index','gain_index','effective_profile_registry','challenge_panel','recipe_registry','scene_manifest'):
        bind(spec[key]['path'],spec[key]['sha256'])
    jobs=build_jobs(spec,panel,recipe_ids)
    if limit:jobs=jobs[:limit]
    root=REPORT/epoch;root.mkdir(exist_ok=True);rows=[];todo=[];samples=[];active={};started=time.perf_counter()
    invocation=utc().replace(':','').replace('-','').split('.')[0]+'_'+str(os.getpid())
    inv=root/'invocations'/invocation;inv.mkdir(parents=True)
    with (REPORT/'coordinator.lock').open('a+b') as lease:
        lease.seek(0)
        if not lease.read(1):lease.write(b'0');lease.flush()
        lease.seek(0);msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
        stop=threading.Event()
        def heartbeat():
            while not stop.is_set():
                s=resources();samples.append(s)
                new=[r for r in rows if r['status']=='COMPLETE'];elapsed=time.perf_counter()-started
                completed=sum(r['status'].startswith('COMPLETE') for r in rows)
                value=dict(status='RUNNING',phase='NEURAL_RECIPES',epoch=epoch,panel=panel,utc=utc(),pid=os.getpid(),creation_time=psutil.Process().create_time(),
                    requested=len(jobs),attempted=len(rows)+len(active),completed=completed,failed=sum(r['status']=='FAILED' for r in rows),
                    reused=sum(r['status']=='COMPLETE_REUSED' for r in rows),pending=len(jobs)-len(rows)-len(active),
                    processed_audio_hours=sum(r['audio_duration_sec'] for r in rows if r['status'].startswith('COMPLETE'))/3600,
                    elapsed_sec=elapsed,estimated_remaining_sec=(len(jobs)-len(rows))*sum(r['full_engine_wall_sec'] for r in new)/len(new)/workers if new else None,
                    active=list(active.values()),resources=s,launch_allowed=allowed(s))
                save(REPORT/'HEARTBEAT.json',value);save(inv/'progress.json',value)
                stop.wait(20)
        thread=threading.Thread(target=heartbeat,daemon=True)
        try:
            save(inv/'coordinator.json',dict(pid=os.getpid(),creation_time=psutil.Process().create_time(),argv=sys.argv,started_utc=utc(),workers=workers))
            for job in jobs:
                hit=verify_cached(job)
                if hit:rows.append(hit)
                else:
                    if (Path(job['folder'])/'attempt_receipt.json').exists():raise ValueError('A prior failed/incomplete attempt requires diagnosis before an explicitly versioned retry')
                    todo.append(job)
            thread.start()
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(spec_path),)) as pool:
                pending={};iterator=iter(todo)
                while True:
                    while len(pending)<workers and allowed(resources()):
                        job=next(iterator,None)
                        if job is None:break
                        future=pool.submit(worker_job,job);pending[future]=job
                        active[job['job_key']]={k:job[k] for k in ('case_id','stream','recipe_id')}
                    if not pending:break
                    done,_=concurrent.futures.wait(pending,timeout=20,return_when=concurrent.futures.FIRST_COMPLETED)
                    for future in done:
                        job=pending.pop(future);active.pop(job['job_key'],None)
                        row=future.result();rows.append(row)
                        save(inv/'rows.json',dict(rows=rows,utc=utc()))
                        print(json.dumps(dict(completed=len(rows),requested=len(jobs),**{k:row[k] for k in ('status','case_id','stream','recipe_id')})),flush=True)
                        if row['status']=='FAILED':raise RuntimeError('Native job failed; preserved exact attempt: '+str(row['receipt']['path']))
            complete=sum(r['status'].startswith('COMPLETE') for r in rows)
            completed_keys={read(r['receipt']['path'])['job_key'] for r in rows}
            result=dict(status='COMPLETE' if complete==len(jobs) else 'PARTIAL_RESUMABLE',requested=len(jobs),completed=complete,
                panel=panel,epoch=epoch,recipes=recipe_ids,rows=rows,created_utc=utc(),elapsed_sec=time.perf_counter()-started,
                pending=[{k:j[k] for k in ('case_id','stream','recipe_id','job_key')} for j in jobs if j['job_key'] not in completed_keys],
                execution_manifest=bind(spec_path),worker_pool_joined=True)
            save(inv/'completion.json',result);save(root/(panel.upper()+'_NEURAL_INDEX.json'),result)
            save(REPORT/'HEARTBEAT.json',dict(status=result['status'],phase='NEURAL_INVOCATION_FINISHED',epoch=epoch,panel=panel,
                requested=len(jobs),completed=complete,pending=len(result['pending']),utc=utc(),completion=bind(inv/'completion.json'),resources=resources()))
            return {k:v for k,v in result.items() if k not in ('rows','pending')}
        finally:
            stop.set()
            if thread.is_alive():thread.join(timeout=30)
            save(inv/'resources.json',dict(samples=samples))
            save(inv/'cleanup.json',dict(utc=utc(),coordinator_pid=os.getpid(),active_records=list(active.values()),scope='ProcessPool context joins only owned workers'))
            lease.seek(0);msvcrt.locking(lease.fileno(),msvcrt.LK_UNLCK,1)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('freeze','run'))
    p.add_argument('--epoch',default='epoch1');p.add_argument('--panel',choices=('pilot','challenge','all'),default='challenge')
    p.add_argument('--recipes',nargs='*');p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int)
    args=p.parse_args()
    if not 1<=args.workers<=4:raise ValueError('One to four workers allowed')
    result=freeze(args.epoch) if args.mode=='freeze' else run(args.epoch,args.panel,args.recipes,args.workers,args.limit)
    print(json.dumps(result if args.mode=='run' else dict(epoch=result['epoch'],files=len(result['execution_files']),recipes=len(result['recipes'])),indent=2))

if __name__=='__main__':main()
