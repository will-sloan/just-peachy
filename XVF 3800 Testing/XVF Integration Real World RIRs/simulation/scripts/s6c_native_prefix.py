"""Bounded actual paired-audio prefix checks. See README_S6C_NATIVE_PREFIX.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
import traceback
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
from s6c_common import REPORT,PAYLOAD,EDGE,admit_work,bind,digest,read,save,utc,verified


def pcm(wave):
    import numpy as np
    return np.round(np.clip(np.asarray(wave,dtype=np.float32),-1.,.999969)*32768.).astype('<i2').tobytes()


def sources():
    return [bind(Path(__file__)),bind(Path(__file__).with_name('README_S6C_NATIVE_PREFIX.md')),
            bind(Path(__file__).with_name('s6c_common.py'))]


def load_epoch(path,assets=False):
    from importlib.metadata import version
    spec=read(path)
    if spec['schema']!='jp_s6c_execution_epoch.v1':raise ValueError('Unsupported frozen epoch')
    if Path(sys.executable).resolve()!=EDGE.resolve() or sys.version!=spec['python']:
        raise ValueError('Use exact admitted EDGE Python')
    for name,wanted in spec['versions'].items():
        if version(name)!=wanted:raise ValueError('Runtime version differs: '+name)
    for b in spec['execution_files']:bind(b['path'],b['sha256'])
    if assets:
        for a in spec['assets']:bind(a['path'],a['sha256'])
    return spec


def prepare(args):
    import numpy as np
    import soundfile as sf
    epoch=REPORT/(args.epoch.upper()+'_EXECUTION_MANIFEST.json')
    spec=load_epoch(epoch)
    output=REPORT/'native_prefix'/args.version
    payload=PAYLOAD/'native_prefix'/args.version
    if output.exists() or payload.exists():raise ValueError('Fresh prefix namespace required; no overwrite or accuracy retry')
    candidates=[p for p in spec['profiles'] if p['candidate_id']==args.candidate
                and p['asr_tap']=='O0' and p['identity_tap']=='O1']
    if len(candidates)!=1:raise ValueError('One explicitly admitted O0-ASR/O1-ID profile required')
    row=candidates[0]
    if row['recipe_id']!='N01' or row['cue_condition']!='CUES_OFF' or row['gallery_condition']!='NONE':
        raise ValueError('Prefix probe is exact N01 dual, cues off, gallery none')
    items=verified(spec['input_index'])['rows']
    inputs={tap:next(r for r in items if r['case_id']==args.case and r['stream']==tap) for tap in ('O0','O1')}
    if inputs['O0']['duration_sec']!=inputs['O1']['duration_sec']:raise ValueError('Paired original lengths differ')
    duration=inputs['O0']['duration_sec'];cut=round(args.prefix_sec*16000)
    if not 8<=args.prefix_sec<duration-3 or duration>60:raise ValueError('Require 8+s prefix, 3+s different future, and whole clip <=60s')
    admit_work(full=False);output.mkdir(parents=True);payload.mkdir(parents=True)
    waves={};bindings={}
    for tap,item in inputs.items():
        original=bind(item['audio']['path'],item['audio']['sha256'])
        wave,sr=sf.read(original['path'],dtype='float32',always_2d=True)
        if sr!=16000 or wave.shape!=(round(duration*16000),1) or not np.all(np.isfinite(wave)):
            raise ValueError('Prepared input must be finite mono16k whole clip')
        wave=wave[:,0]
        if hashlib.sha256(pcm(wave)).hexdigest()!=item['audio_pcm_sha256']:raise ValueError('Input quantization differs from admitted native PCM')
        changed=wave.copy();changed[cut:]=-wave[cut:][::-1]
        if np.array_equal(wave[cut:],changed[cut:]):raise ValueError('Counterfactual future must differ')
        path=payload/(tap+'_different_future.wav')
        sf.write(path,changed,16000,subtype='FLOAT')
        reread,rate=sf.read(path,dtype='float32')
        if rate!=16000 or not np.array_equal(reread,changed):raise ValueError('Counterfactual WAV roundtrip differs')
        prefix=pcm(wave[:cut]);prefix_path=payload/(tap+'_shared_prefix.pcm16')
        with prefix_path.open('xb') as handle:handle.write(prefix);handle.flush();os.fsync(handle.fileno())
        if pcm(changed[:cut])!=prefix:raise ValueError('Counterfactual prefix changed')
        bindings[tap]=dict(original=original,changed=bind(path),shared_prefix=bind(prefix_path),
            original_pcm_sha256=hashlib.sha256(pcm(wave)).hexdigest(),changed_pcm_sha256=hashlib.sha256(pcm(changed)).hexdigest(),
            prefix_float32_sha256=hashlib.sha256(wave[:cut].astype('<f4').tobytes()).hexdigest(),
            original_suffix_pcm_sha256=hashlib.sha256(pcm(wave[cut:])).hexdigest(),
            changed_suffix_pcm_sha256=hashlib.sha256(pcm(changed[cut:])).hexdigest())
        waves[tap]=wave
    manifest=dict(schema='s6c_native_prefix_manifest.v1',status='PREPARED',created_utc=utc(),epoch=bind(epoch),
        driver_sources=sources(),profile=row['profile'],candidate_id=row['candidate_id'],case_id=args.case,
        duration_sec=duration,prefix_sec=cut/16000,prefix_samples=cut,inputs=bindings,payload_root=str(payload),
        report_root=str(output),runs=['original','changed'],source_transform='After the common prefix only: reverse then negate each prepared tap independently; whole original duration retained; no new gain.',
        inference_scope='Two fresh native paired sessions, one resident model bundle, exact same fixed profile; no truth/cue/gallery inputs.',
        common_replay_scope='After neural prefix matching, identical supports use common max observed readiness; future observations are held behind the checkpoint, then incrementally submitted. This is a shared-policy causality fixture, not native latency.')
    save(output/'MANIFEST.json',manifest,immutable=True)
    return bind(output/'MANIFEST.json')


def before_cut(row,cut):
    return row['source_end_sec']<=cut+1e-9 and row.get('receptive_end_sec',row['source_end_sec'])<=cut+1e-9


def compare(a,b,tolerance=0.,path='$'):
    """Reject nonfinite values; bounded exact structural/numeric comparison."""
    issues=[];max_error=0.
    def visit(x,y,p):
        nonlocal max_error
        if isinstance(x,bool) or isinstance(y,bool):
            if type(x)!=type(y) or x!=y:issues.append(p+':bool')
        elif isinstance(x,(int,float)) and isinstance(y,(int,float)):
            if not math.isfinite(x) or not math.isfinite(y):issues.append(p+':nonfinite')
            else:
                delta=abs(x-y);max_error=max(max_error,delta)
                if delta>tolerance:issues.append(p+':numeric')
        elif isinstance(x,dict) and isinstance(y,dict):
            if set(x)!=set(y):issues.append(p+':keys')
            for k in sorted(set(x)&set(y)):visit(x[k],y[k],p+'.'+k)
        elif isinstance(x,list) and isinstance(y,list):
            if len(x)!=len(y):issues.append(p+':length')
            for i,(u,v) in enumerate(zip(x,y)):visit(u,v,p+f'[{i}]')
        elif x!=y:issues.append(p+':value')
    visit(a,b,path)
    return dict(pass_=not issues,difference_count=len(issues),first_differences=issues[:30],max_numeric_error=max_error,tolerance=tolerance)


def unique(rows):
    keys=[(r['kind'],r['event_id']) for r in rows]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate native observation identity')
    spans=[(r['source_start_sec'],r['source_end_sec'],r.get('receptive_start_sec'),r.get('receptive_end_sec'),r.get('evidence_kind'))
           for r in rows if r['kind']=='embedding']
    if len(spans)!=len(set(spans)):raise ValueError('Duplicate vector support/role')
    return {k:r for k,r in zip(keys,rows)}


def neural_rows(events):
    rows=[];segframes=[];actual_vectors=[];native_labels=[]
    for e in events:
        p=e['payload'];kind=e['event_type']
        if kind in ('research_embedding_observation','research_asr_observation'):rows.append(deepcopy(p))
        elif kind=='research_embedding':actual_vectors.append(p['normalized_embedding'])
        elif kind=='research_segmentation':
            eid=p.get('event_id',f'seg:{len(segframes)+1:08d}')
            rows.append(dict(kind='segmentation',event_id=eid,source_start_sec=p['source_start_sec'],source_end_sec=p['source_end_sec'],
                available_at_sec=p.get('available_at_sec',p.get('modeled_available_at_sec')),speech=p['speech'],overlap=p['overlap']))
            segframes.append({k:v for k,v in p.items() if k.endswith('_frames') or k in
                ('source_start_sec','source_end_sec','receptive_start_sec','receptive_end_sec','left_padding_sec','post_policy')})
        elif kind.startswith('transcript_'):
            native_labels.append(dict(event_type=kind,source_time_sec=e['source_time_sec'],payload=p))
    observed=[r['vector'] for r in rows if r['kind']=='embedding']
    if not compare(actual_vectors,observed)['pass_']:raise ValueError('Raw model / delivered embedding observations differ')
    unique(rows)
    return rows,segframes,native_labels


def projection(rows):
    return [{k:v for k,v in r.items() if k not in ('available_at_sec','punctuation','asr_decode_ms')} for r in rows]


def clean_policy(value):
    if isinstance(value,dict):
        return {k:clean_policy(v) for k,v in value.items() if k not in (
            'policy_compute_sec','tracker_compute_sec','identity_compute_sec','scheduler_state_overhead_sec','policy_total_sec',
            'asr_decode_ms','compute_ms')}
    if isinstance(value,list):return [clean_policy(v) for v in value]
    return value


def replay_pair(profile,run_rows,cut):
    from edge_speech_pipeline.research_scheduler_v3 import build_s6c_policy
    prefix=[[r for r in rows if before_cut(r,cut)] for rows in run_rows]
    lookup=[unique(rows) for rows in prefix]
    if set(lookup[0])!=set(lookup[1]):return dict(status='UNAVAILABLE_PREFIX_EVENT_IDENTITIES_DIFFER',runs=[])
    ready={k:max(lookup[0][k]['available_at_sec'],lookup[1][k]['available_at_sec']) for k in lookup[0]}
    checkpoint=max(ready.values(),default=cut)
    outputs=[]
    for n,rows in enumerate(run_rows):
        policy=build_s6c_policy(profile)
        head=[];tail=[]
        for raw in rows:
            row=deepcopy(raw);key=(row['kind'],row['event_id'])
            if key in ready:row['available_at_sec']=ready[key];head.append(row)
            else:row['available_at_sec']=max(row['available_at_sec'],checkpoint+1e-6);tail.append(row)
        records=[]
        def deliver(items):
            ordered=sorted(items,key=lambda r:(r['available_at_sec'],{'segmentation':0,'embedding':1,'asr':2}[r['kind']],r['event_id']))
            for instant,group in itertools.groupby(ordered,key=lambda r:r['available_at_sec']):
                for row in group:records.extend(policy.push(row,'asr' if row['kind']=='asr' else 'speaker'))
                bound=math.nextafter(instant,math.inf)
                records.extend(policy.advance({'speaker':bound,'asr':bound}))
        deliver(head)
        # Preserve references to actual returned records, not a detached copy.
        returned_prefix=list(records);serialized_before=digest(returned_prefix)
        stored_prefix=deepcopy(returned_prefix)
        snapshot_before=deepcopy(policy.snapshot()['utterances'])
        deliver(tail);records.extend(policy.finish())
        if digest(returned_prefix)!=serialized_before:raise ValueError('Prior returned event dictionaries mutated after future delivery')
        outputs.append(dict(prefix_records=clean_policy(stored_prefix),prefix_utterances=snapshot_before,
            completed_utterances=policy.snapshot()['utterances'],prefix_event_count=len(head),future_event_count=len(tail),
            prior_returned_records_immutable=True))
    return dict(status='COMPLETE',common_checkpoint_sec=checkpoint,comparison=compare(outputs[0]['prefix_records'],outputs[1]['prefix_records']),
        utterance_comparison=compare(outputs[0]['prefix_utterances'],outputs[1]['prefix_utterances']),runs=outputs)


def run(args):
    import numpy as np
    import psutil
    manifest_path=REPORT/'native_prefix'/args.version/'MANIFEST.json';m=read(manifest_path)
    for b in m['driver_sources']:bind(b['path'],b['sha256'])
    spec=load_epoch(m['epoch']['path'],assets=True);bind(m['epoch']['path'],m['epoch']['sha256'])
    root=Path(m['report_root']);payload=Path(m['payload_root'])
    if (root/'STARTED.json').exists():raise ValueError('Run already attempted; preserve it and use a reviewed new namespace')
    for item in m['inputs'].values():
        for key in ('original','changed','shared_prefix'):bind(item[key]['path'],item[key]['sha256'])
    resource=admit_work(full=False);proc=psutil.Process()
    owner=dict(pid=proc.pid,creation_time=proc.create_time(),cmdline=proc.cmdline())
    save(root/'STARTED.json',dict(status='STARTED',utc=utc(),owner=owner,manifest=bind(manifest_path),resources=resource),immutable=True)
    sys.path.insert(0,str(Path(spec['root'])/'app'))
    from edge_speech_pipeline.config import PipelineConfig,AssetSpec
    from edge_speech_pipeline.research_profiles import ResearchProfile
    from edge_speech_pipeline.runtime import PipelineEngine
    from edge_speech_pipeline.models import ResidentModelBundle
    assets=tuple(AssetSpec(r['component_id'],Path(r['path']),r['sha256'],r['deployment_relative_path']) for r in spec['assets'])
    profile=ResearchProfile.from_dict(m['profile'])
    base=PipelineConfig(assets=assets,session_root=payload/'sessions',profile_root=payload/'unused_profiles')
    config=profile.apply(base)
    model_started=time.perf_counter();bundle=ResidentModelBundle(config);load_seconds=time.perf_counter()-model_started
    receipts=[];all_rows=[];all_seg=[];all_labels=[];engine=None
    try:
        for run_name in m['runs']:
            native_start=time.perf_counter();cpu0=proc.cpu_times();heartbeat_stop=threading.Event()
            def beat():
                while not heartbeat_stop.wait(20.):
                    save(root/'HEARTBEAT.json',dict(status='RUNNING',run=run_name,utc=utc(),owner=owner,
                        elapsed_sec=time.perf_counter()-native_start,state=engine.state if engine else None))
            heartbeat=threading.Thread(target=beat,name='s6c-prefix-observer',daemon=True);heartbeat.start()
            try:
                engine=PipelineEngine(base,research_profile=profile,model_bundle=bundle)
                session=engine.start_paired_files(Path(m['inputs']['O0'][run_name]['path']),Path(m['inputs']['O1'][run_name]['path']),
                    realtime=False,accelerated_factor=0)
                engine.wait_for_completion(max(720.,m['duration_sec']*2+profile.runtime.lane_drain_timeout_sec+120.))
                closure=read(session/'session_finalization_v3.json')
                if engine.state!='COMPLETED' or closure['state']!='COMPLETED' or closure['live_lanes_at_finalization'] or closure['resident_bundle_lease_retained'] or not closure['event_and_transcript_handles_closed']:
                    raise RuntimeError('Native closure not complete/closed')
                journals={}
                for tap,name in (('O0','audio_spool.pcm16'),('O1','identity_audio_spool.pcm16')):
                    b=bind(session/name,m['inputs'][tap][run_name+'_pcm_sha256'])
                    if b['bytes']!=round(m['duration_sec']*16000)*2:raise ValueError('Incomplete paired PCM journal')
                    raw=(session/name).read_bytes()[:m['prefix_samples']*2]
                    if hashlib.sha256(raw).hexdigest()!=m['inputs'][tap]['shared_prefix']['sha256']:raise ValueError('Native paired prefix bytes differ')
                    journals[tap]=b
                events=[json.loads(line) for line in (session/'events.jsonl').read_text(encoding='utf-8').splitlines()]
                if sum(e['event_type']=='session_completed' for e in events)!=1 or any(e['event_type']=='failure' for e in events):raise ValueError('Native completion events invalid')
                if abs(engine.telemetry()['asr_cursor_sec']-m['duration_sec'])>1e-9:raise ValueError('ASR cursor incomplete')
                rows,seg,labels=neural_rows(events);all_rows.append(rows);all_seg.append(seg);all_labels.append(labels)
                cpu1=proc.cpu_times()
                r=dict(status='COMPLETE',run=run_name,native_elapsed_sec=time.perf_counter()-native_start,
                    process_cpu_sec=cpu1.user+cpu1.system-cpu0.user-cpu0.system,events=bind(session/'events.jsonl'),
                    summary=bind(session/'session_summary.json'),closure=bind(session/'session_finalization_v3.json'),journals=journals,
                    short_embeddings=sum(r.get('evidence_kind')=='short' for r in rows),mature_embeddings=sum(r.get('evidence_kind')=='mature' for r in rows),
                    segmentation_calls=len(seg),raw_asr_observations=sum(r['kind']=='asr' for r in rows),resident_sessions_created=bundle.sessions_created,
                    same_speaker_models_instance=id(bundle.speaker_models),native_labels=labels)
                save(root/(run_name+'_NATIVE_RECEIPT.json'),r,immutable=True);receipts.append(r)
            finally:
                heartbeat_stop.set();heartbeat.join(2.)
        cut=m['prefix_sec'];prefix=[[r for r in rows if before_cut(r,cut)] for rows in all_rows]
        # Compare each lane independently: native cross-thread JSONL arrival order is not an input dependency.
        comparisons={}
        for kind in ('embedding','segmentation','asr'):
            selected=[sorted((r for r in rows if r['kind']==kind),key=lambda r:r['event_id']) for rows in prefix]
            projected=[projection(s) for s in selected]
            if kind=='embedding':
                vectors=[[r.pop('vector') for r in s] for s in projected]
                comparisons['embedding_vectors']=compare(vectors[0],vectors[1],1e-6)
            comparisons[kind]=dict(compare(projected[0],projected[1]),counts=[len(x) for x in selected])
        seg=[[r for r in rows if before_cut(r,cut)] for rows in all_seg]
        seg_support=[[{k:v for k,v in r.items() if not k.endswith('_frames')} for r in s] for s in seg]
        seg_values=[[{k:v for k,v in r.items() if k.endswith('_frames')} for r in s] for s in seg]
        comparisons['segmentation_frame_support']=compare(seg_support[0],seg_support[1])
        comparisons['segmentation_frames']=dict(compare(seg_values[0],seg_values[1],1e-6),counts=[len(x) for x in seg])
        native=[[dict(event_type=r['event_type'],source_time_sec=r['source_time_sec'],
            **{k:r['payload'].get(k) for k in ('utterance_id','text','first_display_label','first_final_label','latest_label','tracker_id')})
            for r in labels if r['payload'].get('source_end_sec',r['source_time_sec'])<=cut] for labels in all_labels]
        native_label_check=compare(native[0],native[1])
        replay=replay_pair(profile,all_rows,cut);save(root/'COMMON_AVAILABILITY_REPLAY.json',replay,immutable=True)
        roles=[{r.get('evidence_kind') for r in rows if r['kind']=='embedding'} for rows in prefix]
        nonempty=all(all(c>0 for c in comparisons[k]['counts']) for k in ('embedding','segmentation','asr'))
        status='PASS' if nonempty and all(c['pass_'] for c in comparisons.values()) and all({'short','mature'}<=role for role in roles) and replay.get('comparison',{}).get('pass_') and replay.get('utterance_comparison',{}).get('pass_') else 'DIFFERENCES_RECORDED'
        result=dict(schema='s6c_actual_native_prefix_result.v1',status=status,finished_utc=utc(),owner=owner,manifest=bind(manifest_path),
            run_receipts=[bind(root/(n+'_NATIVE_RECEIPT.json')) for n in m['runs']],comparisons=comparisons,
            both_prefix_evidence_roles=[sorted(x) for x in roles],common_replay=bind(root/'COMMON_AVAILABILITY_REPLAY.json'),
            all_prefix_lanes_nonempty=nonempty,
            native_label_comparison=native_label_check,native_label_scope='Measured compute/readiness and conservative native watermark release differ across executions; native label differences remain separately disclosed, not erased by common replay.',
            model_bundle_loads=1,resident_sessions_created=bundle.sessions_created,actual_model_bundle_load_sec=load_seconds,
            live_owned_lanes=[t.name for t in threading.enumerate() if t.name.startswith(('edge-','s6c-')) and t.is_alive()],
            neural_sessions=2,hardware_invocations=0,private_gallery_access=False,
            limits='Bounded one-case two-session empirical prefix check only. No whole-bank causality theorem, identity accuracy, live latency or CM5 equivalence. Source supports ending after the cut excluded; common replay is a separately declared checkpoint schedule.')
        if result['live_owned_lanes']:raise RuntimeError('Owned native lanes remain alive')
        save(root/'RESULT.json',result,immutable=True);return {k:v for k,v in result.items() if k not in ('run_receipts','owner')}
    except Exception as exc:
        save(root/'FAILURE.json',dict(status='FAILED',error=repr(exc),traceback=traceback.format_exc(),owner=owner,
            engine_state=engine.state if engine else None,completed_runs=len(receipts),utc=utc()),immutable=True)
        raise


def checks():
    import numpy as np
    rows=[]
    def ok(name,condition):
        if not condition:raise AssertionError(name)
        rows.append(name)
    ok('nonfinite values fail comparison',not compare([float('nan')],[float('nan')])['pass_'])
    ok('structural differences fail',not compare([1],[1,2])['pass_'])
    ok('numeric tolerance is bounded',compare([1.],[1.+5e-7],1e-6)['pass_'] and not compare([1.],[1.+2e-6],1e-6)['pass_'])
    ok('future receptive support excluded',not before_cut(dict(source_end_sec=12.,receptive_end_sec=12.1),12.))
    ok('actual ending-at-cut support admitted',before_cut(dict(source_end_sec=12.,receptive_end_sec=12.),12.))
    objects=[{'value':1}];retained=list(objects);before=digest(retained);objects[0]['value']=2
    ok('shallow retention detects mutation of returned dictionaries',digest(retained)!=before)
    ok('native PCM quantization and positive clipping',np.frombuffer(pcm(np.array([-1.,0.,.5,1.],np.float32)),dtype='<i2').tolist()==[-32768,0,16384,32767])
    try:unique([dict(kind='asr',event_id='a')]*2)
    except ValueError:rows.append('duplicate observation identity rejected')
    else:raise AssertionError('duplicate admitted')
    return dict(status='PASS',tests=rows,neural_invocations=0,sources=sources())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=('prepare','run','check'),required=True)
    p.add_argument('--epoch',default='epoch1');p.add_argument('--version',default='v3');p.add_argument('--case',default='S45_01_01')
    p.add_argument('--candidate',default='C085');p.add_argument('--prefix-sec',type=float,default=12.)
    a=p.parse_args()
    if not a.version.replace('_','').isalnum():p.error('Simple version name required')
    result=checks() if a.mode=='check' else prepare(a) if a.mode=='prepare' else run(a)
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)


if __name__=='__main__':main()
