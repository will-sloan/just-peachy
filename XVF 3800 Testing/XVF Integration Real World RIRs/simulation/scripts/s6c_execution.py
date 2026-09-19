"""Frozen actual S6C native jobs, ownership and resume. README_S6C_EXECUTION.md."""
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

for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
from s6c_common import *

_WORKER={}

def freeze(epoch,registry_path=None):
    registry_path=Path(registry_path) if registry_path else REPORT/'EFFECTIVE_PROFILE_REGISTRY_V1.json'
    target=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json')
    if target.exists():
        spec=read(target)
        for b in spec['execution_files']:bind(b['path'],b['sha256'])
        if spec['effective_profile_registry']!=bind(registry_path):raise ValueError('Existing epoch has different registry')
        return spec
    admit_work(full=True)
    registry=read(registry_path)
    if registry['status']!='VALIDATED_REAL_V3_API':raise ValueError('Validated actual profiles required')
    root=STAGING/epoch
    if root.exists():raise ValueError('Unreceipted epoch directory exists; diagnose, do not overwrite')
    shutil.copytree(APP,root/'app/edge_speech_pipeline',ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo'))
    (root/'scripts').mkdir()
    core=('s6c_common.py','s6c_execution.py','s6c_profiles.py','s6c_replay.py','s6c_jobs.py','s6c_cue_variants.py',
          's6c_native_replay_v3.py','s6c_policy_matrix.py','s6c_policy_matrix_v2.py','s6c_calibrated_profiles.py','s6c_rescue_design.py')
    for name in core:shutil.copy2(SIM/'scripts'/name,root/'scripts'/name)
    for p in (SIM/'scripts').glob('README_S6C*.md'):shutil.copy2(p,root/'scripts'/p.name)
    # Resolve installed asset paths from the actual H2 checkout; the frozen
    # worker receives explicit AssetSpecs, never snapshot-relative defaults.
    sys.path.insert(0,str(H2/'app'))
    from edge_speech_pipeline.config import PipelineConfig
    assets=[]
    for asset in PipelineConfig().assets:
        row=asdict(asset);row['path']=str(row['path']);row['binding']=bind(asset.path,asset.sha256);assets.append(row)
    from importlib.metadata import version
    files=[bind(p) for p in sorted(root.rglob('*.py'))]
    spec=dict(schema='jp_s6c_execution_epoch.v1',epoch=epoch,created_utc=utc(),root=str(root),
        execution_files=files,documentation_files=[bind(p) for p in sorted(root.rglob('*.md'))],
        assets=assets,versions={name:version(name) for name in ('onnxruntime','sherpa-onnx','numpy','psutil')},
        python=sys.version,profiles=registry['profiles'],effective_profile_registry=bind(registry_path),
        input_index=bind(S6B/'INPUT_INDEX.json'),registered_design=bind(REPORT/'design/REGISTERED_DESIGN_V1.json'),
        panel=bind(REPORT/'design/REGISTERED_PANEL_V1.json'),scene_manifest=bind(BANK),
        state_policy='New native decoder, tracker, identity, queues and utterances per scene; weights resident per worker; one active lease per bundle',
        resources=dict(max_workers=4,inner_threads=1,c_reserve_bytes=RESERVE['C:'],g_reserve_bytes=RESERVE['G:'],new_payload_cap_bytes=CAP),
        ordinary_conditions_truth_oracle_inputs=False,
        nominal_geometry_diagnostic='Explicit oracle-like numeric cue condition only, never a deployable or independent-performance claim',hardware_playback=False)
    spec['gallery_index']=bind(REPORT/'RESEARCH_GALLERY_INDEX.json') if (REPORT/'RESEARCH_GALLERY_INDEX.json').exists() else None
    spec['cue_variant_index']=bind(REPORT/'CUE_VARIANT_INDEX_V1.json') if (REPORT/'CUE_VARIANT_INDEX_V1.json').exists() else None
    spec['component_readiness']=bind(REPORT/'COMPONENT_PLUMBING_READY_V2.json')
    spec['registration_amendment']=bind(REPORT/'design/C_ONLY_CALIBRATION_AMENDMENT_V1.json')
    spec['rescue_registration']=registry.get('rescue_registration')
    spec['execution_digest']=digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')})
    save(target,spec,immutable=True)
    return spec

def worker_init(spec_path):
    import psutil
    spec=read(spec_path)
    for b in spec['execution_files']:bind(b['path'],b['sha256'])
    sys.path.insert(0,str(Path(spec['root'])/'app'))
    from edge_speech_pipeline.config import PipelineConfig,AssetSpec
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.runtime import PipelineEngine
    from edge_speech_pipeline.models import ResidentModelBundle
    from edge_speech_pipeline.research_identity_v3 import ResearchGallery
    assets=tuple(AssetSpec(r['component_id'],Path(r['path']),r['sha256'],r['deployment_relative_path']) for r in spec['assets'])
    process=psutil.Process()
    root=PAYLOAD/spec['epoch']/'workers'/(str(process.pid)+'_'+str(round(process.create_time()*1000)))
    cfg=PipelineConfig(assets=assets,session_root=root/'sessions',profile_root=root/'unused_isolated_profiles')
    status=REPORT/spec['epoch']/'workers'/(root.name+'.json')
    _WORKER.update(spec=spec,config=cfg,Profile=ResearchProfile,Provider=JsonSpatialProvider,Engine=PipelineEngine,
        Bundle=ResidentModelBundle,Gallery=ResearchGallery,bundle=None,bundle_key=None,model_loads=0,galleries={},status=status,
        pid=process.pid,creation_time=process.create_time())
    save(status,dict(status='READY',pid=process.pid,creation_time=process.create_time(),utc=utc()))

def extract(events):
    import numpy as np
    vectors=[];features=[];observations=[];seg=[];asr=[];counts={};costs={}
    for e in events:
        kind=e['event_type'];p=e['payload']
        counts[kind]=counts.get(kind,0)+1
        if kind=='research_embedding':
            vector=p.get('normalized_embedding',p.get('vector'))
            if vector is None:raise ValueError('Actual embedding vector absent')
            vectors.append(vector)
            feature={k:v for k,v in p.items() if k not in ('normalized_embedding','vector','decision')}
            feature['available_at_sec']=p.get('available_at_sec',p.get('modeled_available_at_sec'))
            feature['index']=len(features);features.append(feature)
        elif kind=='research_embedding_observation':observations.append(p)
        elif kind=='research_segmentation':seg.append(dict(p,available_at_sec=p.get('available_at_sec',p.get('modeled_available_at_sec'))))
        elif kind=='research_asr_observation':asr.append(p)
        if kind.startswith('research_'):
            cost=costs.setdefault(kind,dict(calls=0));cost['calls']+=1
            for key in ('compute_ms','full_dispatch_elapsed_ms','model_api_elapsed_ms','scheduler_dispatch_ms','gate_compute_ms','embedding_compute_ms','segment_compute_ms'):
                if key in p:cost[key.replace('_ms','_sec')]=cost.get(key.replace('_ms','_sec'),0)+float(p[key])/1000
    if len(vectors)!=len(observations):raise ValueError('Raw v3 embedding observation count differs from actual calls')
    for i,(vector,row) in enumerate(zip(vectors,observations)):
        if not np.array_equal(np.asarray(vector,np.float32),np.asarray(row['vector'],np.float32)):
            raise ValueError('Actual embedding / scheduler observation vector differs')
        if row['source_end_sec']!=features[i]['source_end_sec']:raise ValueError('Embedding support differs')
    costs['event_counts']=counts
    costs['scope']='Model/API/full dispatch are nested inclusive costs; do not add them or concurrent lane wall times.'
    return np.asarray(vectors,np.float32).reshape(-1,192),features,[{k:v for k,v in p.items() if k!='vector'} for p in observations],seg,asr,costs

def worker_job(job):
    import psutil
    import numpy as np
    w=_WORKER;process=psutil.Process();engine=None
    folder=Path(job['folder']);folder.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();cpu0=process.cpu_times()
    receipt=dict(status='STARTED',job_key=job['job_key'],identity=job['identity'],case_id=job['case_id'],
        candidate_id=job['candidate_id'],asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],recipe_id=job['recipe_id'],
        pid=process.pid,creation_time=process.create_time(),started_utc=utc(),execution_mode='PACED_NATIVE' if job['realtime'] else 'NEW_NATIVE_INFERENCE',
        hardware_invocations=0,cue_condition=job['identity']['cue_condition'],
        reference_truth_sent_to_predictor=job['identity']['cue_condition']=='NOMINAL_GEOMETRY_DIAGNOSTIC',
        reference_scope='Only explicitly registered nominal cue diagnostic may contain truth-derived angles; no person IDs, transcripts or early packets enter predictor')
    try:
        save(folder/'attempt_receipt.json',receipt)
        save(w['status'],dict(receipt,phase='INPUT_ADMISSION'))
        for key in ('asr_audio','identity_audio'):bind(job[key]['path'],job[key]['sha256'])
        profile=w['Profile'].from_dict(job['profile']);config=profile.apply(w['config'])
        bundle_key=digest({k:v for k,v in asdict(config).items() if k not in ('assets','session_root','profile_root')})
        admission_started=time.perf_counter()
        if w['bundle_key']!=bundle_key:
            w['bundle']=None;w['bundle']=w['Bundle'](config);w['bundle_key']=bundle_key;w['model_loads']+=1
        bundle_time=time.perf_counter()-admission_started
        provider=None
        if job.get('telemetry'):
            bind(job['telemetry']['path'],job['telemetry']['sha256'])
            provider=w['Provider'](Path(job['telemetry']['path']))
        gallery=None
        gallery_started=time.perf_counter();gallery_cache_hit=False
        if job.get('gallery'):
            bind(job['gallery']['path'],job['gallery']['sha256'])
            key=job['gallery']['sha256']
            gallery_cache_hit=key in w['galleries']
            if key not in w['galleries']:
                w['galleries'][key]=w['Gallery'](job['gallery']['path'],config.asset('redimnet2_b2_fp32').sha256,profile.identity.max_gallery_profiles)
            gallery=w['galleries'][key]
        gallery_admission_sec=time.perf_counter()-gallery_started
        engine=w['Engine'](w['config'],research_profile=profile,spatial_provider=provider,model_bundle=w['bundle'],research_gallery=gallery)
        native0=time.perf_counter()
        session=engine.start_paired_files(Path(job['asr_audio']['path']),Path(job['identity_audio']['path']),realtime=job['realtime'],accelerated_factor=0)
        save(w['status'],dict(receipt,status='RUNNING',phase='NATIVE_FILE',session_dir=str(session),utc=utc()))
        engine.wait_for_completion(timeout=max(720.,job['duration_sec']*1.75+profile.runtime.lane_drain_timeout_sec+120.))
        native_elapsed=time.perf_counter()-native0
        if engine.state!='COMPLETED':raise RuntimeError('Native engine state '+engine.state)
        events=[json.loads(line) for line in (session/'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        if sum(e['event_type']=='session_completed' for e in events)!=1 or any(e['event_type']=='failure' for e in events):
            raise RuntimeError('Native session completion/failure events invalid')
        summary=read(session/'session_summary.json')
        finalization=read(session/'session_finalization_v3.json')
        if (finalization['state']!='COMPLETED' or finalization['live_lanes_at_finalization'] or
            finalization['resident_bundle_lease_retained'] or not finalization['event_and_transcript_handles_closed'] or finalization['finalization_error'] is not None):
            raise RuntimeError('Durable native closure is incomplete')
        for key in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):
            if summary['telemetry'][key]!=0:raise RuntimeError('Native audio loss: '+key)
        # Journal names are explicit native routing outputs, not guessed tap files.
        journals={p.name:bind(p) for p in session.glob('*.pcm16')}
        expected_bytes=round(job['duration_sec']*16000)*2
        if set(journals)!={'audio_spool.pcm16','identity_audio_spool.pcm16'} or any(v['bytes']!=expected_bytes for v in journals.values()):
            raise RuntimeError('Incomplete or unexpected paired journal')
        if journals['audio_spool.pcm16']['sha256']!=job['asr_pcm_sha256'] or journals['identity_audio_spool.pcm16']['sha256']!=job['identity_pcm_sha256']:
            raise RuntimeError('Named paired journal route/PCM/gain mismatch')
        vectors,features,observations,seg,asr,costs=extract(events)
        vector_file=folder/'vectors.npz';np.savez_compressed(vector_file,vectors=vectors)
        evidence=dict(schema='jp_s6c_actual_neural_evidence.v1',job_key=job['job_key'],identity=job['identity'],
            vectors=bind(vector_file),features=features,embedding_observations=observations,segmentation=seg,asr_observations=asr,costs=costs,
            duration_sec=job['duration_sec'],native_events=bind(session/'events.jsonl'),native_summary=bind(session/'session_summary.json'),
            full_native_journals=journals,source_asr=job['asr_audio'],source_identity=job['identity_audio'],
            frontend='actual native fixed-weight Pyannote/ReDim/Sherpa with shared v3 tracker/name scheduler',created_utc=utc())
        save(folder/'evidence.json',evidence,immutable=True)
        receipt.update(status='COMPLETE',evidence=bind(folder/'evidence.json'),vectors=bind(vector_file),events=evidence['native_events'],
            summary=evidence['native_summary'],session_dir=str(session),journals=journals,native_elapsed_sec=native_elapsed,
            finalization=bind(session/'session_finalization_v3.json'),
            bundle_admission_sec=bundle_time,worker_model_bundle_loads=w['model_loads'],
            gallery_cache_hit=gallery_cache_hit,gallery_admission_sec=gallery_admission_sec,
            gallery_cost_scope='Original loaded_elapsed_sec in repeated resident receipt is one-time provenance, not new per-job load cost',
            gallery_load_receipts=[e['payload'] for e in events if e['event_type']=='research_gallery_loaded'],
            actual_counts=costs['event_counts'],audio_duration_sec=job['duration_sec'],
            source_speed='paced at source speed' if job['realtime'] else 'accelerated file; not measured board/CM5 latency')
    except Exception as exc:
        receipt.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
        if engine is not None and engine.state not in ('COMPLETED','FAILED','IDLE'):
            engine.stop()
            try:engine.wait_for_completion(timeout=30.)
            except Exception:pass
    finally:
        cpu1=process.cpu_times()
        receipt.update(finished_utc=utc(),elapsed_sec=time.perf_counter()-started,
            process_cpu_sec=cpu1.user+cpu1.system-cpu0.user-cpu0.system,rss_end_bytes=process.memory_info().rss)
        save(folder/'attempt_receipt.json',receipt)
        if receipt['status']=='COMPLETE':save(folder/'run_receipt.json',receipt,immutable=True)
        save(w['status'],dict(status='READY' if receipt['status']=='COMPLETE' else 'FAILED',pid=process.pid,
            creation_time=process.create_time(),last_job=job['job_key'],utc=utc()))
    return dict(job_key=job['job_key'],candidate_id=job['candidate_id'],case_id=job['case_id'],recipe_id=job['recipe_id'],
        asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],status=receipt['status'],elapsed_sec=receipt['elapsed_sec'],
        audio_duration_sec=job['duration_sec'],receipt=bind(folder/('run_receipt.json' if receipt['status']=='COMPLETE' else 'attempt_receipt.json')),
        error=receipt.get('error'))

def job_identity(spec,profile_row,asr_audio,identity_audio,telemetry,gallery,realtime):
    return dict(schema='jp_s6c_native_job.v1',execution_digest=spec['execution_digest'],profile=profile_row['profile'],
        cue_condition=profile_row['cue_condition'],gallery_condition=profile_row['gallery_condition'],enrollment_tier=profile_row['enrollment_tier'],
        asr_audio=asr_audio,identity_audio=identity_audio,telemetry=telemetry,gallery=gallery,
        gain=dict(O0='historical +3dB already applied once',O1='unity',adapter=1.),
        origin='same canonical capture sample-zero pair; no per-utterance alignment',realtime=realtime,
        fresh_state=True,inner_threads=1,provider='CPUExecutionProvider/cpu')

def make_job(spec,profile_row,case_id,stage,realtime=False,attempt='v1',gallery=None,telemetry=None):
    inputs=verified(spec['input_index'])['rows']
    lookup={(r['case_id'],r['stream']):r for r in inputs}
    asr=lookup[case_id,profile_row['asr_tap']];speaker=lookup[case_id,profile_row['identity_tap']]
    if asr['duration_sec']!=speaker['duration_sec']:raise ValueError('Paired capture frame origins/length mismatch')
    if profile_row['gallery_condition']!='NONE' and gallery is None:raise ValueError('Naming condition requires explicit admitted research gallery')
    if profile_row['cue_condition']!='CUES_OFF' and telemetry is None:
        if profile_row['cue_condition']=='REAL_ALIGNED_CUES':telemetry=asr['telemetry']
        else:raise ValueError('Explicit frozen diagnostic telemetry required')
    identity=job_identity(spec,profile_row,asr['audio'],speaker['audio'],telemetry,gallery,realtime)
    key=digest(identity)
    return dict(job_key=key,identity=identity,profile=profile_row['profile'],candidate_id=profile_row['candidate_id'],
        recipe_id=profile_row['recipe_id'],case_id=case_id,asr_tap=profile_row['asr_tap'],identity_tap=profile_row['identity_tap'],
        asr_audio=asr['audio'],identity_audio=speaker['audio'],asr_pcm_sha256=asr['audio_pcm_sha256'],identity_pcm_sha256=speaker['audio_pcm_sha256'],
        duration_sec=asr['duration_sec'],telemetry=telemetry,gallery=gallery,realtime=realtime,
        folder=str(PAYLOAD/spec['epoch']/stage/profile_row['candidate_id']/case_id/(profile_row['asr_tap']+'_'+profile_row['identity_tap'])/attempt))

def validate_job(spec,job,input_lookup=None,check_assets=True):
    """Validate the same declared dependencies before both reuse and execution."""
    if digest(job['identity'])!=job['job_key'] or job['identity']['execution_digest']!=spec['execution_digest']:
        raise ValueError('Native job digest/epoch mismatch')
    target=Path(job['folder']).resolve();allowed=(PAYLOAD/spec['epoch']).resolve()
    if allowed not in target.parents:raise ValueError('Job outputs must stay within this S6C epoch payload')
    for key in ('profile','asr_audio','identity_audio','telemetry','gallery','realtime'):
        if job[key]!=job['identity'][key]:raise ValueError('Top-level job/identity mismatch: '+key)
    profiles=[p for p in spec['profiles'] if p['candidate_id']==job['candidate_id'] and p['asr_tap']==job['asr_tap'] and p['identity_tap']==job['identity_tap']]
    if len(profiles)!=1 or profiles[0]['profile']!=job['profile'] or profiles[0]['recipe_id']!=job['recipe_id']:
        raise ValueError('Job is not the declared frozen candidate/profile')
    if profiles[0]['cue_condition']!=job['identity']['cue_condition'] or profiles[0]['gallery_condition']!=job['identity']['gallery_condition']:
        raise ValueError('Condition provenance differs from registered frozen profile')
    if (profiles[0]['gallery_condition']=='NONE')!=(job['gallery'] is None):raise ValueError('Gallery condition mismatch')
    if (profiles[0]['cue_condition']=='CUES_OFF')!=(job['telemetry'] is None):raise ValueError('Cue condition mismatch')
    if job['identity']!=job_identity(spec,profiles[0],job['asr_audio'],job['identity_audio'],job['telemetry'],job['gallery'],job['realtime']):
        raise ValueError('Native identity constants differ from actual execution behavior')
    if input_lookup is None:input_lookup={(r['case_id'],r['stream']):r for r in verified(spec['input_index'])['rows']}
    for key,tap,pcm in (('asr_audio','asr_tap','asr_pcm_sha256'),('identity_audio','identity_tap','identity_pcm_sha256')):
        inp=input_lookup[job['case_id'],job[tap]]
        if job[key]!=inp['audio'] or job[pcm]!=inp['audio_pcm_sha256'] or job['duration_sec']!=inp['duration_sec']:
            raise ValueError('Job differs from canonical admitted source: '+key)
        bind(job[key]['path'],job[key]['sha256'])
    if job['telemetry']:bind(job['telemetry']['path'],job['telemetry']['sha256'])
    if profiles[0]['cue_condition']=='REAL_ALIGNED_CUES' and job['telemetry']!=input_lookup[job['case_id'],job['asr_tap']]['telemetry']:
        raise ValueError('Real cue route differs from actual capture telemetry')
    if profiles[0]['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):
        if not spec.get('cue_variant_index'):raise ValueError('Epoch has no frozen diagnostic cue assignments')
        variants=verified(spec['cue_variant_index'])['rows']
        match=[r for r in variants if r['case_id']==job['case_id'] and r['stream']==job['asr_tap'] and r['condition']==profiles[0]['cue_condition']]
        if len(match)!=1 or match[0]['telemetry']!=job['telemetry']:raise ValueError('Diagnostic cue source differs from frozen condition')
    if job['gallery']:
        if not spec.get('gallery_index'):raise ValueError('Epoch has no frozen research gallery assignments')
        assignments=verified(spec['gallery_index'])['rows']
        matches=[r for r in assignments if r['gallery_condition']==profiles[0]['gallery_condition'] and r['enrollment_tier']==profiles[0]['enrollment_tier'] and r.get('case_id') in (None,job['case_id'])]
        if len(matches)!=1 or matches[0]['manifest']!=job['gallery']:raise ValueError('Gallery roster/tier/case assignment differs from frozen index')
        gallery=verified(job['gallery'])
        gallery_root=Path(gallery['profile_root']).resolve()
        if PAYLOAD.resolve() not in gallery_root.parents:raise ValueError('Campaign galleries must be in this isolated S6C payload')
        expected_backend=next(r['sha256'] for r in spec['assets'] if r['component_id']=='redimnet2_b2_fp32')
        if gallery['backend_sha256']!=expected_backend:raise ValueError('Gallery backend differs')
        for row in gallery['profiles']:
            for key in ('metadata','vector'):bind(row[key]['path'],row[key]['sha256'])
        if gallery.get('provenance_binding'):bind(gallery['provenance_binding']['path'],gallery['provenance_binding']['sha256'])
    if check_assets:
        for asset in spec['assets']:bind(asset['path'],asset['sha256'])

def verify_job(job):
    path=Path(job['folder'])/'run_receipt.json'
    if not path.exists():return None
    receipt=read(path)
    if receipt['status']!='COMPLETE' or receipt['job_key']!=job['job_key'] or receipt['identity']!=job['identity']:
        raise ValueError('Native resume identity mismatch: '+str(path))
    for key in ('asr_audio','identity_audio'):bind(job[key]['path'],job[key]['sha256'])
    for key in ('evidence','vectors','events','summary','finalization'):bind(receipt[key]['path'],receipt[key]['sha256'])
    for b in receipt['journals'].values():bind(b['path'],b['sha256'])
    if set(receipt['journals'])!={'audio_spool.pcm16','identity_audio_spool.pcm16'}:
        raise ValueError('Unexpected cached journal set')
    for name,key in (('audio_spool.pcm16','asr_pcm_sha256'),('identity_audio_spool.pcm16','identity_pcm_sha256')):
        if receipt['journals'][name]['sha256']!=job[key] or receipt['journals'][name]['bytes']!=round(job['duration_sec']*16000)*2:
            raise ValueError('Cached named input route differs')
    return dict(job_key=job['job_key'],candidate_id=job['candidate_id'],case_id=job['case_id'],recipe_id=job['recipe_id'],
        asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],status='COMPLETE_REUSED',elapsed_sec=receipt['elapsed_sec'],
        audio_duration_sec=job['duration_sec'],receipt=bind(path))

def run(spec_path,jobs_path,workers):
    import msvcrt
    import psutil
    spec=read(spec_path);job_manifest=read(jobs_path);jobs=job_manifest['jobs']
    if Path(__file__).resolve().parent!=Path(spec['root'])/'scripts':raise ValueError('Run the frozen execution script, not live source')
    for b in spec['execution_files']:bind(b['path'],b['sha256'])
    for asset in spec['assets']:bind(asset['path'],asset['sha256'])
    input_lookup={(r['case_id'],r['stream']):r for r in verified(spec['input_index'])['rows']}
    if not 1<=workers<=4:raise ValueError('One to four workers')
    if any(j['realtime'] for j in jobs) and workers!=1:raise ValueError('Paced runs require one quiet worker')
    if len({j['job_key'] for j in jobs})!=len(jobs):raise ValueError('Duplicate jobs in invocation')
    admit_work(full=True)
    invocation=utc().replace(':','').replace('-','').split('.')[0]+'_'+str(os.getpid())
    inv=REPORT/spec['epoch']/'invocations'/invocation;inv.mkdir(parents=True)
    rows=[];todo=[];active={};started=time.perf_counter();stop=threading.Event();samples=[]
    process=psutil.Process();identity=dict(pid=process.pid,creation_time=process.create_time(),argv=sys.argv)
    def heartbeat():
        while not stop.is_set():
            try:
                sample=resources();sample['owned_processes']=[]
                for child in process.children(recursive=True):
                    try:sample['owned_processes'].append(dict(pid=child.pid,creation_time=child.create_time(),rss_bytes=child.memory_info().rss,threads=child.num_threads()))
                    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                samples.append(sample)
                elapsed=time.perf_counter()-started;new=[r for r in rows if r['status']=='COMPLETE']
                rate=sum(r['elapsed_sec'] for r in new)/len(new)/workers if new else None
                pending=max(0,len(jobs)-len(rows)-len(active))
                value=dict(status='RUNNING',phase=job_manifest.get('stage','NATIVE'),epoch=spec['epoch'],utc=utc(),
                    owner=identity,requested=len(jobs),completed=len(rows),new_native_jobs=len(new),reused=len(rows)-len(new),
                    active=list(active.values()),pending=pending,elapsed_sec=elapsed,
                    eta_range_sec=None if rate is None else [pending*rate*.8,pending*rate*1.3],resources=sample)
                save(REPORT/'HEARTBEAT.json',value);save(inv/'progress.json',value)
            except Exception as exc:
                # Optional status failure is visible; durable native receipts
                # remain strict and are never replaced by observer assertions.
                with (inv/'observer_errors.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(utc=utc(),error=repr(exc)))+'\n')
            stop.wait(20.)
    with (REPORT/'coordinator.lock').open('a+b') as lease:
        lease.seek(0)
        if not lease.read(1):lease.write(b'0');lease.flush()
        lease.seek(0);msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
        monitor=threading.Thread(target=heartbeat,daemon=True)
        failure=None
        try:
            save(inv/'owner.json',dict(identity,workers=workers,started_utc=utc(),jobs=bind(jobs_path),execution_manifest=bind(spec_path)))
            for job in jobs:
                validate_job(spec,job,input_lookup,check_assets=False)
                hit=verify_job(job)
                if hit:rows.append(hit)
                else:
                    if (Path(job['folder'])/'attempt_receipt.json').exists():raise RuntimeError('Prior incomplete/failed attempt requires diagnosed named retry: '+job['folder'])
                    todo.append(job)
            monitor.start()
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(spec_path),)) as pool:
                pending={};iterator=iter(todo);exhausted=False
                while True:
                    while len(pending)<workers and not exhausted and failure is None:
                        quota=admit_work(full=True)
                        job=next(iterator,None)
                        if job is None:exhausted=True;break
                        # A conservative upper bound includes both journals,
                        # duplicate embedded event JSON, segmentation frames,
                        # summaries/observer samples and active worker jobs.
                        reservation=sum(max(32*2**20,j['duration_sec']*512*1024) for j in pending.values())
                        reservation+=max(32*2**20,job['duration_sec']*512*1024)
                        if quota['new_payload_bytes']+reservation>CAP:raise RuntimeError('New payload reservation reaches S6C cap')
                        pending[pool.submit(worker_job,job)]=job
                        active[job['job_key']]={k:job[k] for k in ('candidate_id','case_id','asr_tap','identity_tap','recipe_id')}
                    if not pending:break
                    done,_=concurrent.futures.wait(pending,timeout=20.,return_when=concurrent.futures.FIRST_COMPLETED)
                    for future in done:
                        job=pending.pop(future);active.pop(job['job_key'],None)
                        try:row=future.result()
                        except Exception as exc:
                            failure=repr(exc);raise
                        rows.append(row);save(inv/'rows.json',dict(rows=rows,utc=utc()))
                        print(json.dumps(dict(completed=len(rows),requested=len(jobs),**{k:row[k] for k in ('status','candidate_id','case_id','asr_tap','identity_tap')})),flush=True)
                        if row['status']=='FAILED':failure='Native failure preserved: '+row['receipt']['path']
                    if failure is not None and not pending:break
            complete=sum(r['status'].startswith('COMPLETE') for r in rows)
            result=dict(status='COMPLETE' if complete==len(jobs) else 'PARTIAL_RESUMABLE',requested=len(jobs),completed=complete,
                rows=rows,epoch=spec['epoch'],stage=job_manifest.get('stage'),jobs=bind(jobs_path),execution_manifest=bind(spec_path),
                elapsed_sec=time.perf_counter()-started,error=failure,worker_pool_joined=True,finished_utc=utc())
            save(inv/'completion.json',result)
            save(Path(jobs_path).with_name(Path(jobs_path).stem+'_RESULTS.json'),result)
            stop.set()
            if monitor.is_alive():monitor.join(timeout=30.)
            save(REPORT/'HEARTBEAT.json',dict(status=result['status'],phase='NATIVE_INVOCATION_CLOSED',completion=bind(inv/'completion.json'),utc=utc()))
            return {k:v for k,v in result.items() if k!='rows'}
        except Exception as exc:
            stop.set()
            if monitor.is_alive():monitor.join(timeout=30.)
            partial=dict(status='PARTIAL_RESUMABLE',requested=len(jobs),completed=sum(r['status'].startswith('COMPLETE') for r in rows),
                rows=rows,epoch=spec['epoch'],stage=job_manifest.get('stage'),jobs=bind(jobs_path),execution_manifest=bind(spec_path),
                error=repr(exc),traceback=traceback.format_exc(),finished_utc=utc(),
                resume_note='Owned active jobs join on exception; durable successful worker receipts are re-admitted on exact resume. Incomplete/failed attempts require named diagnosed retry.')
            save(inv/'completion.json',partial)
            save(REPORT/'HEARTBEAT.json',dict(status='PARTIAL_RESUMABLE',phase='NATIVE_EXCEPTION_CLOSED',completion=bind(inv/'completion.json'),utc=utc()))
            raise
        finally:
            stop.set()
            if monitor.is_alive():monitor.join(timeout=30.)
            save(inv/'resources.json',dict(samples=samples))
            save(inv/'closure.json',dict(owner=identity,utc=utc(),remaining_owned_children=[dict(pid=p.pid,creation_time=p.create_time()) for p in process.children(recursive=True)],
                active_records=list(active.values()),scope='Only owned ProcessPool workers joined; no unrelated processes touched'))
            lease.seek(0);msvcrt.locking(lease.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('freeze','run'));p.add_argument('--epoch',default='epoch1')
    p.add_argument('--jobs');p.add_argument('--workers',type=int,default=4);p.add_argument('--registry');a=p.parse_args()
    value=freeze(a.epoch,a.registry) if a.mode=='freeze' else run(REPORT/(a.epoch.upper()+'_EXECUTION_MANIFEST.json'),a.jobs,a.workers)
    print(json.dumps(dict(status='FROZEN',epoch=value['epoch'],files=len(value['execution_files'])) if a.mode=='freeze' else value,indent=2))
