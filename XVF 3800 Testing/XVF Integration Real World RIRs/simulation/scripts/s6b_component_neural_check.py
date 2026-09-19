"""Bounded actual-neural S6B prefix/resident/component smoke. See matching README."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'

import numpy as np
import soundfile as sf


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
def rows(path):return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def compare(left,right,cutoff=None):
    def select(data,kind):
        return [x['payload'] for x in data if x['event_type']==kind and (cutoff is None or x['payload'].get('source_end_sec',x.get('source_time_sec',0))<=cutoff+1e-9)]
    result={}
    a,b=select(left,'research_asr_observation'),select(right,'research_asr_observation')
    keys=('event_id','utterance_id','text','final','source_start_sec','source_end_sec')
    result['raw_asr_events']={'left':len(a),'right':len(b),'equal':[{k:x.get(k) for k in keys} for x in a]==[{k:x.get(k) for k in keys} for x in b]}
    a,b=select(left,'research_embedding'),select(right,'research_embedding')
    spans=lambda values:[(x['source_start_sec'],x['source_end_sec'],x['receptive_start_sec'],x['receptive_end_sec']) for x in values]
    span_equal=spans(a)==spans(b)
    finite=all(np.all(np.isfinite(x['normalized_embedding'])) for x in a+b)
    delta=max((float(np.max(np.abs(np.asarray(x['normalized_embedding'])-np.asarray(y['normalized_embedding'])))) for x,y in zip(a,b)),default=0.) if span_equal and finite else None
    result['embeddings']={'left':len(a),'right':len(b),'spans_equal':span_equal,'finite':finite,'max_abs_difference':delta,'equal_within_1e6':span_equal and finite and delta<=1e-6}
    a,b=select(left,'research_segmentation'),select(right,'research_segmentation')
    segkeys=('source_start_sec','source_end_sec','speech','overlap','speech_frames','overlap_frames')
    result['segmentation']={'left':len(a),'right':len(b),'equal':[{k:x.get(k) for k in segkeys} for x in a]==[{k:x.get(k) for k in segkeys} for x in b]}
    a,b=select(left,'speaker_decision'),select(right,'speaker_decision')
    dkeys=('source_start_sec','source_end_sec','anonymous_label','state','committed','unique_evidence_sec','disjoint_evidence_count')
    result['tracker_decisions']={'left':len(a),'right':len(b),'equal':[{k:x.get(k) for k in dkeys} for x in a]==[{k:x.get(k) for k in dkeys} for x in b]}
    def display(data):
        selected=[]
        for kind in ('transcript_partial','transcript_final','transcript_label_revision'):
            for x in select(data,kind):
                selected.append((x.get('event_id'),kind,x.get('utterance_id'),x.get('source_end_sec'),x.get('text'),x.get('speaker'),x.get('latest_label'),x.get('first_final_label')))
        return sorted(selected)
    result['native_display_semantics']={'equal':display(left)==display(right),'left':len(display(left)),'right':len(display(right)),
        'limitation':'Measured upstream compute differs across runs; labels are reported separately, not hidden behind vector parity'}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--endpoint-input',type=Path,required=True)
    parser.add_argument('--telemetry',type=Path)
    parser.add_argument('--source-app',type=Path)
    parser.add_argument('--jobs',default='R0_A,R0_B,R0_REPEAT,R3_SHORT_LONG,R5,R0_ENDPOINT,R7')
    parser.add_argument('--receipt-name',default='COMPONENT_NEURAL_SMOKE.json')
    parser.add_argument('--repair-of',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    source_app=args.source_app or args.repo/'Software Validation from Datasets/Evaluation Tool/app/edge_speech_pipeline'
    snapshot=args.output/'app/edge_speech_pipeline';snapshot.mkdir(parents=True)
    bindings={}
    for path in sorted(source_app.iterdir()):
        if path.is_file() and path.suffix in ('.py','.md'):
            shutil.copyfile(path,snapshot/path.name);bindings[path.name]=sha(snapshot/path.name)
    registry_path=args.report/'NEURAL_RECIPE_REGISTRY.json'
    shutil.copyfile(registry_path,args.output/'NEURAL_RECIPE_REGISTRY.json')
    recipes={r['recipe_id']:r for r in json.loads((args.output/'NEURAL_RECIPE_REGISTRY.json').read_text())['recipes']}
    sys.path.insert(0,str(snapshot.parent))
    from edge_speech_pipeline import config as cfg
    # Snapshot paths alone are relocated. This does not change defaults/weights.
    cfg.REPOSITORY_ROOT=args.repo
    cfg.EVALUATION_ROOT=args.repo/'Software Validation from Datasets/Evaluation Tool'
    from edge_speech_pipeline.models import ResidentModelBundle
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.runtime import PipelineEngine
    import psutil
    process=psutil.Process()
    receipt={'schema_version':'s6b-neural-component-smoke.v1','status':'RUNNING','pid':os.getpid(),'process_create_time':process.create_time(),
        'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'app_snapshot':str(snapshot),'app_sha256':bindings,
        'runner_sha256':sha(__file__),'registry_sha256':sha(args.output/'NEURAL_RECIPE_REGISTRY.json'),
        'inputs':{str(p):sha(p) for p in (args.input,args.endpoint_input)},'jobs':[],
        'pool_environment':{k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},
        'scope':'bounded real graphs on chosen audio prefixes; no accuracy-driven selection or full-bank claim'}
    if args.repair_of:
        receipt['repair_of']={'path':str(args.repair_of),'sha256':sha(args.repair_of),
            'reason':'Prospective .5sec early-window contiguous clean threshold .5→.45 because valid-convolution frame support leaves an unknown trailing edge; clean fraction .8 and all other declared recipe settings retained'}
    save(args.output/'RECEIPT.json',receipt)
    if args.telemetry:
        receipt['telemetry_binding']={'path':str(args.telemetry),'sha256':sha(args.telemetry)}
        shutil.copyfile(args.telemetry,args.output/'telemetry.jsonl')
        args.telemetry=args.output/'telemetry.jsonl'
    print(json.dumps({'pid':os.getpid(),'create_time':process.create_time(),'output':str(args.output)}),flush=True)
    audio,rate=sf.read(args.input,dtype='float32');endpoint,erate=sf.read(args.endpoint_input,dtype='float32')
    if rate!=16000 or erate!=16000 or audio.ndim!=1 or endpoint.ndim!=1 or len(audio)<18*16000:
        raise ValueError('prepared mono16k input must have at least18 seconds')
    length=18*16000+107
    first=np.pad(audio[:length],(0,max(0,length-len(audio))))
    other=first.copy();other[12*16000:]=0
    endpoint=np.pad(endpoint[:length],(0,max(0,length-len(endpoint))))
    for name,data in (('prefix_a',first),('prefix_b',other),('endpoint',endpoint)):
        sf.write(args.output/(name+'.wav'),data,16000,subtype='PCM_16')
    plans=[('R0_A','R0','prefix_a'),('R0_B','R0','prefix_b'),('R0_REPEAT','R0','prefix_a'),
           ('R3_SHORT_LONG','R3_SHORT_LONG','prefix_a'),('R5','R5','prefix_a'),('R0_ENDPOINT','R0_ENDPOINT','endpoint'),('R7','R7','prefix_a')]
    requested=args.jobs.split(',')
    if len(set(requested))!=len(requested) or set(requested)-{x[0] for x in plans}:
        raise ValueError('unknown or duplicate bounded smoke job selection')
    plans=[x for x in plans if x[0] in requested]
    bundle=None;bundle_id=None;all_events={}
    class EmptyProvider:
        sha256=None
        def evidence(self,start,now):return None
    for job_id,recipe_id,input_id in plans:
        profile=ResearchProfile.from_dict(recipes[recipe_id]['profile'])
        config=cfg.PipelineConfig(session_root=args.output/job_id,profile_root=args.output/'empty_gallery')
        if bundle_id!=recipe_id:
            bundle=None
            import gc;gc.collect()
            bundle=ResidentModelBundle(profile.apply(config));bundle_id=recipe_id
        provider=JsonSpatialProvider(args.telemetry) if args.telemetry and profile.xvf.mode!='none' else EmptyProvider() if profile.xvf.mode!='none' else None
        engine=PipelineEngine(config,research_profile=profile,spatial_provider=provider,model_bundle=bundle)
        start=time.perf_counter();directory=engine.start_file(args.output/(input_id+'.wav'),realtime=False,accelerated_factor=1000.)
        heartbeat=start
        while engine.state not in {'COMPLETED','FAILED'}:
            now=time.perf_counter()
            if now-start>120:
                engine.stop();engine.wait_for_completion(30);raise TimeoutError('bounded native fixture exceeded120sec')
            if now-heartbeat>=20:
                save(args.output/'HEARTBEAT.json',{'pid':os.getpid(),'job':job_id,'telemetry':engine.telemetry()});heartbeat=now
                print(json.dumps({'job':job_id,'elapsed_sec':now-start,'state':engine.state}),flush=True)
            time.sleep(.02)
        engine.wait_for_completion(60)
        if engine.state!='COMPLETED':raise RuntimeError('native fixture failed: '+str(directory))
        events=rows(directory/'events.jsonl');all_events[job_id]=events
        finals=rows(directory/'labelled_transcript.jsonl');counts=Counter(x['event_type'] for x in events)
        vectors=[x['payload'] for x in events if x['event_type']=='research_embedding']
        admissions=[x['payload'] for x in events if x['event_type']=='research_embedding_admission']
        pcm=np.fromfile(directory/'audio_spool.pcm16',dtype='<i2')
        input_pcm=sf.read(args.output/(input_id+'.wav'),dtype='int16')[0]
        costs=[x['payload'] for x in events if x['event_type']=='research_asr_full_dispatch_cost']
        row={'job_id':job_id,'recipe_id':recipe_id,'profile_sha256':profile.digest(),'session_dir':str(directory),'elapsed_sec':time.perf_counter()-start,
            'samples':len(pcm),'journal_exact':np.array_equal(pcm,input_pcm),'events':dict(counts),
            'embedding_lengths_sec':dict(Counter(round(x['source_end_sec']-x['source_start_sec'],6) for x in vectors)),
            'admission_reasons':dict(Counter(x['reason'] for x in admissions)),
            'endpoint_advisor_reasons':dict(Counter((x.get('advisor') or {}).get('reason','disabled') for x in costs)),
            'raw_final_words':[x['text'] for x in finals],'final_speakers':[x['speaker'] for x in finals],
            'summary_sha256':sha(directory/'session_summary.json'),'events_sha256':sha(directory/'events.jsonl'),
            'native_total_samples_complete':len(pcm)==length,'telemetry':{k:v for k,v in engine.telemetry().items() if k!='scheduler'}}
        receipt['jobs'].append(row);save(args.output/'RECEIPT.json',receipt)
        print(json.dumps({k:row[k] for k in ('job_id','elapsed_sec','samples','embedding_lengths_sec','events')}),flush=True)
    if {'R0_A','R0_B'}<=all_events.keys():receipt['prefix_comparison']=compare(all_events['R0_A'],all_events['R0_B'],12.)
    if {'R0_A','R0_REPEAT'}<=all_events.keys():receipt['resident_repeat_comparison']=compare(all_events['R0_A'],all_events['R0_REPEAT'])
    receipt['snapshot_unchanged']=all(sha(snapshot/name)==value for name,value in bindings.items())
    receipt['status']='COMPLETE'
    receipt['completed_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    receipt['resource_scope']='one process, sequential fresh streams; poolthreads1, no hardware; native display differences disclosed separately'
    save(args.output/'RECEIPT.json',receipt)
    shutil.copyfile(args.output/'RECEIPT.json',args.report/args.receipt_name)
    print(json.dumps({'status':receipt['status'],'prefix':receipt.get('prefix_comparison'),'resident':receipt.get('resident_repeat_comparison')}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
