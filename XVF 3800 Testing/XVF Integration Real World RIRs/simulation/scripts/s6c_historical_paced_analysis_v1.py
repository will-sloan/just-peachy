"""Closed historical paced observations; README_S6C_HISTORICAL_PACED_ANALYSIS_V1.md."""
from __future__ import annotations
import argparse, ast, gzip, hashlib, importlib, itertools, json, math, os, re, sys, tempfile, time
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent; SIM=HERE.parent
REPORT=SIM/'reports/S6C/20260910T123540Z'
EDGE=SIM.parents[2]/'.edge-speech-env/python.exe'
INVENTORY_SHA='426a4eaada68e51d0e6af6decd8b9b56fa3c9660b3cca005f959862c03177876'
SCHEMA='jp_s6c_historical_paced_analysis.v1'
RESEARCH_CLOCK_EXCLUSIONS={'policy_compute_sec','modeled_available_at_sec','compute_finished_elapsed_sec',
    'release_watermark_lower_bound_sec','release_after_all_lanes_closed'}

def require(ok,message):
    if not ok: raise ValueError(message)

def finite(x): return type(x) in (int,float) and math.isfinite(x)
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def binding(p,raw=None):
    p=Path(p).resolve(); raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def utc(): return datetime.now(timezone.utc).isoformat()
def stamp(x):
    d=datetime.fromisoformat(x.replace('Z','+00:00'));require(d.tzinfo is not None,'Timezone-aware native UTC required');return d
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    return binding(p)

class Reader:
    """Each exact payload buffer is verified once and reused only with the same binding."""
    def __init__(self): self.cache={};self.sources=[]
    def raw(self,b):
        p=Path(b['path']).resolve();key=str(p).casefold()
        require(type(b['bytes']) is int and 0<=b['bytes']<=256*2**20,'Bounded declared file required')
        if key in self.cache:
            prior,raw=self.cache[key];require(prior==b,'Conflicting source binding');return raw
        raw=p.read_bytes();require(binding(p,raw)==b,'Changed exact payload: '+str(p))
        self.cache[key]=(b,raw);self.sources.append(b);return raw
    def json(self,b):return json.loads(self.raw(b),parse_constant=lambda x:require(False,'Nonfinite JSON'))
    def lines(self,b):return [json.loads(s,parse_constant=lambda x:require(False,'Nonfinite JSON')) for s in self.raw(b).decode('utf-8-sig').splitlines() if s.strip()]

def inventory():
    require(binding(HERE/'s6c_execution_inventory_v4.py')['sha256']==INVENTORY_SHA,'Held V4 inventory changed')
    m=importlib.import_module('s6c_execution_inventory_v4');require(Path(m.__file__).resolve()==HERE/'s6c_execution_inventory_v4.py','Inventory import origin differs');return m

def selected_jobs(plan,generation):
    require(generation in ('baseline','research'),'Explicit generation required')
    result=[j for j in plan['jobs'] if (j['profile_id']=='B00')==(generation=='baseline')]
    require(result and all(j['profile_id'] in ('B00','B01','B36') for j in result),'Historical generation has no admitted jobs')
    require(all(j['telemetry'] is None and j['realtime'] is True for j in result),'Only original unity/cues-off paced controls supported')
    return result

def closed_metadata(inv,reader,plan,pb):
    require(plan['schema'] in inv.HISTORICAL,'Canonical/sentinel/continuous sources need separate adapters')
    records,owners=inv.invocation_rows(reader,plan,pb)
    require(records and any(r['status']=='COMPLETE' and r['reported_completed']==len(plan['jobs']) for r in records),'Completed whole historical manifest required')
    require(all(r.get('closure') is not None for r in records),'Every historical invocation needs archived quiet lease')
    require(all(o['process_state']['alive'] is False for o in owners),'Historical coordinator live or closure unavailable')
    rows=[]
    for job in plan['jobs']:
        row=inv.collect_job(reader,job,plan,pb,{})
        require(row is not None and row['status']=='COMPLETE' and row['native_session_complete'] is True,'Every historical cell must be complete')
        require(all(inv.v3.process_state(o['pid'],o['creation_time'])['alive'] is False for o in row['recorded_owned_processes']),'Recorded historical worker live/unverified')
        rows.append(row)
    return dict(invocations=records,coordinator_observations=owners,physical_cells=rows)

def authority_code(plan,spec,reader,generation):
    """Read code/metadata only; no model assets, PCM or historical APP substitution."""
    replay=[b for b in spec['execution_files'] if Path(b['path']).name=='s6b_replay.py']
    extract=[b for b in spec['execution_files'] if Path(b['path']).name=='s6b_execution.py']
    require(len(replay)==len(extract)==1,'Exactly bound original replay/extractor required')
    rb=reader.raw(replay[0]);eb=reader.raw(extract[0])
    if generation=='baseline':
        authority=plan['historical_baseline_authority'];sealed=reader.json(plan['source_sealed_index'])
        old=authority['sealed_paced_manifest'];members=[{k:r[k] for k in ('path','bytes','sha256')} for r in sealed['artifacts'] if Path(r['path']).resolve()==Path(old['path']).resolve()]
        require(members==[old],'Original baseline authority is not sealed')
        prior=reader.json(old);contract_b=authority['execution_contract'];require(contract_b in prior['dependencies'],'Baseline contract not bound by sealed manifest')
        contract=reader.json(contract_b);root=SIM/'staging/s6a/20260909T202250Z/baseline_app/edge_speech_pipeline'
        snapshots=[s for s in contract['snapshot'] if Path(s['snapshot']).suffix=='.py']
        require({Path(s['snapshot']).resolve() for s in snapshots}=={p.resolve() for p in root.glob('*.py')},'Original baseline source inventory differs')
        for s in snapshots:
            b=dict(path=str(Path(s['snapshot']).resolve()),bytes=s['bytes'],sha256=s['sha256']);reader.raw(b)
    else:
        root=Path(spec['root'])/'app'
        app=[b for b in spec['execution_files'] if Path(b['path']).resolve().is_relative_to(root)]
        require({Path(b['path']).resolve() for b in app}=={p.resolve() for p in root.rglob('*.py')},'Exact frozen S6B APP inventory differs')
        for b in app:reader.raw(b)
    return rb,eb

def pure_adapters(replay_raw,extract_raw):
    """Original function bodies; only historical file reads become supplied buffers."""
    rtree=ast.parse(replay_raw);etree=ast.parse(extract_raw)
    funcs={n.name:n for n in rtree.body if isinstance(n,ast.FunctionDef)}
    old=deepcopy(funcs['historical']);require(len(old.body)>=3 and isinstance(old.body[0],ast.Assign) and isinstance(old.body[1],ast.Assign),'Original historical I/O shape differs')
    require(ast.unparse(old.body[0].targets[0])=='events' and ast.unparse(old.body[1].targets[0])=='features','Historical I/O prefix differs')
    old.name='historical_buffers';old.args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='events'),ast.arg(arg='features')],kwonlyargs=[],kw_defaults=[],defaults=[]);old.body=old.body[2:]
    nodes=[deepcopy(funcs[n]) for n in ('scheduler_inputs','run_scheduler')]+[old]
    nodes+=[deepcopy(n) for n in etree.body if isinstance(n,ast.FunctionDef) and n.name=='extract_events'];require(len(nodes)==4,'Exact four original adapters required')
    ns=dict(deepcopy=deepcopy,itertools=itertools,math=math,time=time)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<bound historical paced adapters>','exec'),ns)
    ns['historical_attribution_ast_sha256']=hashlib.sha256(ast.dump(ast.Module(body=old.body,type_ignores=[]),include_attributes=False).encode()).hexdigest()
    return ns

def research_classes(spec):
    require(not any(n=='edge_speech_pipeline' or n.startswith('edge_speech_pipeline.') for n in sys.modules),'Fresh research-only process required; no other APP may be imported')
    root=Path(spec['root'])/'app';sys.path.insert(0,str(root))
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.research_tracking_v2 import S6BTracker
    from edge_speech_pipeline.research_scheduler import CausalScheduler
    for name,module in list(sys.modules.items()):
        if name=='edge_speech_pipeline' or name.startswith('edge_speech_pipeline.'):
            require(Path(module.__file__).resolve().is_relative_to(root),'Imported a substituted APP')
    return ResearchProfile,JsonSpatialProvider,S6BTracker,CausalScheduler

def baseline_features(events):
    rows=[]
    for e in events:
        if e['event_type']!='speaker_decision':continue
        p=e['payload'];span=p['spatial_evidence'];end=e['source_time_sec'];start=max(0.,end-.5)
        require(span['provider']=='none' and span['source_clock']=='audio_sample_clock','Baseline spatial placeholder changed')
        require(abs(span['source_start_sec']-start)<=1e-6 and abs(span['source_end_sec']-end)<=1e-6,'Actual baseline embedding window differs')
        rows.append(dict(index=len(rows),source_start_sec=span['source_start_sec'],source_end_sec=span['source_end_sec'],available_at_sec=None,speech=True,overlap=False,
            evidence_scope='Actual emitted baseline decision window; native code embeds once per decision. Vector and causal modeled availability unlogged.'))
    return dict(features=rows)

def logical(value):
    if isinstance(value,dict):return {k:logical(v) for k,v in value.items() if k not in RESEARCH_CLOCK_EXCLUSIONS}
    if isinstance(value,list):return [logical(v) for v in value]
    return value

def same_shared(actual,expected):
    if isinstance(actual,dict):return isinstance(expected,dict) and all(k in expected and same_shared(v,expected[k]) for k,v in actual.items())
    if isinstance(actual,list):return isinstance(expected,list) and len(actual)==len(expected) and all(same_shared(a,b) for a,b in zip(actual,expected))
    return type(actual)==type(expected) and actual==expected

def research_prediction(events,summary,job,api,classes):
    import numpy as np
    vectors,features,seg,asr,costs=api['extract_events'](events)
    require(np.isfinite(vectors).all(),'Nonfinite actual vector')
    require(len(asr)==sum(e['event_type']=='research_asr_observation' for e in events) and all(e.get('event_id') for e in asr),'Actual independent research ASR observations required; no transcript fallback')
    value=api['run_scheduler'](classes[0].from_dict(job['profile']),None,dict(features=features,segmentation=seg,asr_observations=asr,costs=costs),vectors,classes)
    actual=[e['payload']['decision'] for e in events if e['event_type']=='speaker_decision']
    require(value['decisions']==actual,'Original scheduler/native decisions differ')
    transcript=[e['payload'] for e in events if e['event_type'].startswith('transcript_')]
    require(same_shared(logical(value['transcript_events']),logical(transcript)),'Original scheduler/native transcript sequence differs')
    want=[u for u in summary['telemetry']['scheduler']['utterances'] if u['is_final']]
    got=[u for u in value['snapshot']['scheduler']['utterances'] if u['is_final']]
    require(logical(got)==logical(want),'Original scheduler/native final retained utterances differ')
    return value,dict(status='PASS_EXACT_SHARED_NATIVE_PARITY',decisions=len(actual),transcript_events=len(transcript),excluded_execution_fields=sorted(RESEARCH_CLOCK_EXCLUSIONS)),vectors

def emitted_observations(events,display,worker):
    starts=[e for e in events if e['event_type']=='source_started'];ends=[e for e in events if e['event_type']=='session_completed']
    require(len(starts)==len(ends)==1 and not any(e['event_type']=='failure' for e in events),'Actual source/completion events differ')
    origin=stamp(starts[0]['wall_time_utc']);require(starts[0]['wall_time_utc']==worker['source_started_wall_time_utc'],'Worker source origin differs')
    expected=[dict(event_type=e['event_type'],source_time_sec=e['source_time_sec'],emitted_wall_time_utc=e['wall_time_utc'],payload=e['payload']) for e in events if e['event_type'] in ('transcript_partial','transcript_final','transcript_label_revision')]
    observed=[dict(event_type=e['event_type'],source_time_sec=round(e['source_time_sec'],6),emitted_wall_time_utc=e['emitted_wall_time_utc'],payload=e['payload']) for e in display]
    require(expected==observed,'Bound native display collection differs from actual event file')
    rows=[];prior=None;reversals=[]
    for i,e in enumerate(events):
        now=stamp(e['wall_time_utc'])
        if prior is not None and now<prior:reversals.append(i+1)
        prior=now
        if e['event_type'] in ('speaker_decision','transcript_partial','transcript_final','transcript_label_revision'):
            elapsed=(now-origin).total_seconds();rows.append(dict(event_line=i+1,event_type=e['event_type'],wall_time_utc=e['wall_time_utc'],from_source_started_sec=elapsed,source_cursor_sec=e['source_time_sec'],emission_minus_source_cursor_sec=elapsed-e['source_time_sec'],payload=e['payload']))
    return dict(rows=rows,source_started=starts[0],session_completed=ends[0],wall_order_reversals=reversals,
        scope='Actual emitted UTC relative to current source start, not GUI or phonetic latency; native source cursor file is rounded to6 decimals. Backward clocks remain flagged, no interpolation or normalization. No historical-schema C name metric or invented finalization timestamp.')

def process_observations(samples,owned):
    require(samples,'Actual historical trajectory is required');times=[]
    for row in samples:
        t=row['elapsed_sec'];require(finite(t) and t>=0 and (not times or t>=times[-1]),'Nonmonotonic observation time');times.append(t)
        require(all((p['pid'],p['creation_time']) in owned for p in row['tree']['processes']),'Sampled process omitted from closure')
    def stats(xs):
        xs=[x for x in xs if x is not None];require(all(finite(x) for x in xs),'Nonfinite sample')
        return dict(observed=len(xs),missing=len(samples)-len(xs),min=min(xs) if xs else None,max=max(xs) if xs else None,first=xs[0] if xs else None,last=xs[-1] if xs else None)
    fields=('rss_sum_upper_bound_bytes','private_resident_uss_sum_bytes','windows_private_commit_sum_bytes','pss_sum_bytes','system_available_ram_bytes')
    live=[r.get('live') for r in samples];telemetry=[(x or {}).get('telemetry') for x in live]
    lag={}
    for k in ('asr_cursor_sec','speaker_cursor_sec'):
        xs=[t['source_duration_sec']-t[k] if t is not None and k in t and 'source_duration_sec' in t else None for t in telemetry]
        lag[k]=stats(xs)
    cpu={}
    for row in samples:
        for p in row['tree']['processes']:
            x=p['cpu_seconds'];require(finite(x) and x>=0,'Finite process CPU counter required');key=(p['pid'],p['creation_time']);cpu[key]=max(cpu.get(key,0),x)
    return dict(sample_count=len(samples),null_live_samples=sum(x is None for x in live),missing_telemetry_samples=sum(x is None for x in telemetry),incomplete_tree_samples=sum(not r['tree']['tree_complete'] for r in samples),max_sample_gap_sec=max((b-a for a,b in zip(times,times[1:])),default=None),process={k:stats([r['tree'].get(k) for r in samples]) for k in fields},backlog=lag,sampled_cpu_counter_sum_sec=sum(cpu.values()),
        scope='Observed historical samples, no fabricated terminal sample or continuous maxima. Tree-complete is the original sampler flag: descendant-enumeration errors may fall back to root-only sampling without being flagged. RSS upper bound, USS private resident and private commit distinct. CPU totals include each observed process lifetime counter and are not interval-only CPU. Missing LIVE/telemetry stays missing; resource gaps include observer directory-scan overhead.')

def cell_chain(inv,mreader,job,plan,pb):
    row=inv.collect_job(mreader,job,plan,pb,{})
    require(row and row['status']=='COMPLETE','Complete historical cell required')
    folder=Path(plan['output_root'])/'jobs'/job['job_id']
    complete,cb=mreader.read(folder/'COMPLETE.json');native,nb=mreader.read(folder/'WORKER_RESULT.json');launch,lb=mreader.read(folder/'LAUNCH.json')
    require(complete['worker']==native,'Historical worker payload differs')
    owned={(o['pid'],o['creation_time']) for o in complete['owned_processes']};require(len(owned)==len(complete['owned_processes']),'Duplicate owned process')
    require(all(inv.v3.process_state(p,c)['alive'] is False for p,c in owned),'Owned historical child live/unverified')
    expected=[nb,next(b for b in complete['artifacts'] if Path(b['path'])==folder/'PROCESS_SAMPLES.jsonl'),native['events'],native['journal'],native['display_events'],native['summary_binding']]
    require(complete['artifacts']==expected and len({b['path'] for b in expected})==6,'Exact historical artifact list differs')
    session=Path(native['session_dir']).resolve();require(session.is_relative_to(folder/'sessions'),'Session outside owned historical namespace')
    for k,name in (('events','events.jsonl'),('summary_binding','session_summary.json'),('journal','audio_spool.pcm16')):require(Path(native[k]['path']).resolve()==session/name,'Native payload path differs')
    require(Path(native['display_events']['path']).resolve()==folder/'DISPLAY_EVENTS.json','Native display path differs')
    return row,native,nb,cb,expected[1],owned,lb

def convert(inv,mreader,job,plan,pb,spec,api,classes):
    row,native,nb,cb,trajectory_b,owned,lb=cell_chain(inv,mreader,job,plan,pb);reader=Reader()
    events=reader.lines(native['events']);summary=reader.json(native['summary_binding']);display=reader.json(native['display_events']);samples=reader.lines(trajectory_b)
    require(summary==native['summary'] and summary['state']=='COMPLETED','Actual summary/native state differs')
    require(dict(Counter(e['event_type'] for e in events))==native['event_counts'],'Actual event counts differ')
    require(all(summary['telemetry'][k]==0 for k in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures')),'Observed historical audio loss')
    require(abs(summary['telemetry']['asr_cursor_sec']-job['duration_sec'])<=1e-7,'Complete actual ASR cursor required')
    require(summary['assets']==[dict(component_id=a['component_id'],sha256=a['sha256']) for a in job['assets']],'Native summary model identities differ')
    actual=emitted_observations(events,display,native);start=actual['source_started']['payload']
    require(start['mode']=='wav' and Path(start['path']).resolve()==Path(job['input']['path']).resolve() and start['pipeline_sample_rate']==16000 and start['channels']==1,'Actual historical source mode/path/rate differs')
    vectors=None
    if job['profile_id']=='B00':
        require('research' not in summary,'Original default baseline acquired a research profile')
        value=api['historical_buffers'](events,baseline_features(events));parity=dict(status='EXACT_ORIGINAL_ATTRIBUTION_FROM_CURRENT_NATIVE_EVENTS',attribution_body_ast_sha256=api['historical_attribution_ast_sha256'],shared_scheduler='UNAVAILABLE_ORIGINAL_BASELINE',vector_parity=None)
    else:
        require(summary['research']['profile']==job['profile'] and summary['research']['telemetry_sha256'] is None and summary['research']['effective_config']['input_gain']==1.,'Actual historical research config/cue/gain differs')
        require(native['baseline_dispatch_instrumentation_unavailable'] is False and native['native_dispatch_delivery'] is not None and all(native['native_dispatch_delivery'][k] is True for k in ('no_gaps_or_duplicates','starts_at_zero','ends_at_full_duration','exact_samples')),'Actual full research dispatch proof required')
        value,parity,vectors=research_prediction(events,summary,job,api,classes)
    identity=dict(schema=SCHEMA,profile=job['profile'],source=nb,actual_native_events=native['events'],complete=cb,manifest=pb,asr_tap=job['stream'],identity_tap=job['stream'],repetition=job['repetition'],actual_generation='S6A_B00_DEFAULT' if job['profile_id']=='B00' else 'S6B_epoch2',converter=binding(__file__),analysis_truth_dependency=False)
    value.update(schema='jp_s6c_prediction.v1',status='COMPLETE',identity=identity,prediction_key=digest(identity),profile_id=job['profile_id'],candidate_id=job['profile_id'],recipe_id=job['recipe_id'],case_id=job['case_id'],stream=job['stream'],identity_tap=job['stream'],repetition=job['repetition'],duration_sec=job['duration_sec'],oracle_like=False,
        execution_mode='ACTUAL_HISTORICAL_SOURCE_PACED_NATIVE',timing_scope='Actual wall emission in separate measurement. B00 retains original source-cursor label attribution; its feature availability/vector traces are unavailable. Research modeled support uses exact frozen S6B scheduler with native event parity.',created_utc=utc())
    result=dict(status='COMPLETE',job=job,native_result=nb,completion=cb,launch=lb,consumed_payloads=reader.sources,actual_emission=actual,trajectory=process_observations(samples,owned),parity=parity,native_worker_costs={k:native.get(k) for k in ('full_worker_elapsed_sec','bundle_admission_sec','engine_launch_loading_sec','process_cpu_sec_at_end','process_io_write_bytes_at_end','costs','cost_scope')},journal=native['journal'],native_dispatch_delivery=native['native_dispatch_delivery'],baseline_dispatch_unavailable=native['baseline_dispatch_instrumentation_unavailable'],
        missing_baseline_traces=['raw_embedding_vectors','causal_modeled_embedding_availability','research_ASR_dispatch','common_scheduler_snapshot'] if job['profile_id']=='B00' else [],scope='Exact bound historical native event/display/summary/process buffers; original PCM/model bytes remain transitively admitted, not reopened. No C naming API, long composition or CM5 claim.')
    return result,value,vectors

def sources():return [binding(HERE/n) for n in ('s6c_historical_paced_analysis_v1.py','README_S6C_HISTORICAL_PACED_ANALYSIS_V1.md','s6c_execution_inventory_v4.py')]
def output(name):
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,60}',name or ''),'Simple fresh output name required');return REPORT/'historical_paced_analysis'/name
def no_quiet():require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Actual paced quiet lease remains; defer analysis')

def prepare(args):
    no_quiet();inv=inventory();out=output(args.name);require(not out.exists(),'Preserve prior output namespace')
    b=binding(args.manifest);require(b['sha256']==args.manifest_sha256,'Caller manifest hash differs')
    out.mkdir(parents=True)
    reader=inv.base.MetadataReader(out);plan,pb,spec=inv.admit_plan(reader,b);jobs=selected_jobs(plan,args.generation);closed=closed_metadata(inv,reader,plan,pb)
    r=Reader();authority_code(plan,spec,r,args.generation)
    value=dict(schema=SCHEMA,status='PREPARED_CLOSED_NATIVE_NO_INFERENCE',created_utc=utc(),name=args.name,generation=args.generation,manifest=pb,sources=sources(),selected_jobs=[j['job_id'] for j in jobs],whole_manifest_cells=len(plan['jobs']),metadata_sources=reader.sources,source_code_reads=r.sources,closure=closed)
    return save(out/'PLAN.json',value)

def run(args):
    no_quiet();require(Path(sys.executable).resolve()==EDGE.resolve(),'Exact EDGE interpreter required')
    rb=binding(args.plan);require(rb['sha256']==args.plan_sha256,'Exact prepared analysis plan required');reader=Reader();request=reader.json(rb);out=output(request['name'])
    require(Path(rb['path'])==out/'PLAN.json' and request['schema']==SCHEMA and request['status']=='PREPARED_CLOSED_NATIVE_NO_INFERENCE' and request['sources']==sources(),'Analysis plan/source identity differs')
    require(not (out/'RESULT.json').exists() and not (out/'FAILURE.json').exists(),'Preserve prior completed or failed analysis')
    inv=inventory();meta=inv.base.MetadataReader(out);produced=[];measurements=[];repeat=[];seen={};started=time.perf_counter()
    try:
        plan,pb,spec=inv.admit_plan(meta,request['manifest']);jobs=selected_jobs(plan,request['generation']);require([j['job_id'] for j in jobs]==request['selected_jobs'],'Selected historical generation grid differs');closed=closed_metadata(inv,meta,plan,pb)
        code=Reader();raw,extract=authority_code(plan,spec,code,request['generation']);require(code.sources==request['source_code_reads'],'Prepared exact source inventory changed');api=pure_adapters(raw,extract)
        require(not any(n=='edge_speech_pipeline' or n.startswith('edge_speech_pipeline.') for n in sys.modules),'Fresh generation-isolated process required')
        classes=research_classes(spec) if request['generation']=='research' else None
        for job in jobs:
            no_quiet();measurement,value,vectors=convert(inv,meta,job,plan,pb,spec,api,classes)
            key=(job['profile_id'],job['case_id'],job['stream'])
            if key in seen:
                old,ov=seen[key];current=measurement['actual_emission']['rows'];prior=old['actual_emission']['rows']
                signature=lambda rows:[(r['event_type'],r['source_cursor_sec'],logical(r['payload'])) for r in rows if r['event_type'].startswith('transcript_')]
                vcomparison=None
                if vectors is not None and ov is not None:
                    spans=lambda f:[(x['source_start_sec'],x['source_end_sec']) for x in f]
                    same=spans(value['features'])==old['feature_spans'];vcomparison=dict(counts=[len(ov),len(vectors)],spans_exact=same,max_absolute_difference=float(abs(ov-vectors).max()) if same and ov.shape==vectors.shape and vectors.size else 0. if same and ov.shape==vectors.shape else None)
                repeat.append(dict(profile_id=key[0],case_id=key[1],stream=key[2],repetitions=[old['job']['repetition'],job['repetition']],raw_final_words_exact=[x['text'] for x in old['finals']]==[x['text'] for x in value['final_transcripts_latest']],latest_final_labels_exact=[x['speaker'] for x in old['finals']]==[x['speaker'] for x in value['final_transcripts_latest']],display_sequence_exact=signature(prior)==signature(current),journal_exact=old['journal']['sha256']==measurement['journal']['sha256'],embedding_parity=vcomparison,scope='Dependent repeats, all retained; vector absence on B00 is unavailable, not equal. Timing/label variation is not an accuracy retry trigger.'))
            else:seen[key]={**measurement,'feature_spans':[(x['source_start_sec'],x['source_end_sec']) for x in value['features']],'finals':value['final_transcripts_latest']},vectors
            mb=save(out/'cells'/(job['job_id']+'.json'),measurement);measurements.append(mb)
            p=out/'predictions'/(job['job_id']+'.json.gz');p.parent.mkdir(exist_ok=True)
            with p.open('xb') as f:f.write(gzip.compress(json.dumps(value,separators=(',',':'),allow_nan=False).encode(),mtime=0))
            produced.append(dict(candidate_id=job['profile_id'],profile_id=job['profile_id'],case_id=job['case_id'],stream=job['stream'],identity_tap=job['stream'],recipe_id=job['recipe_id'],repetition=job['repetition'],status='COMPLETE',result=binding(p),measurement=mb))
            print(json.dumps(dict(phase='HISTORICAL_PACED_ANALYSIS',completed=len(produced),requested=len(jobs),generation=request['generation'])),flush=True)
        indices=[]
        for rep in sorted({j['repetition'] for j in jobs}):
            rows=[r for r in produced if r['repetition']==rep];cases=sorted({r['case_id'] for r in rows});routes=sorted({(r['candidate_id'],r['stream']) for r in rows})
            require(len(rows)==len(cases)*len(routes) and len({(r['candidate_id'],r['stream'],r['case_id']) for r in rows})==len(rows),'Uniform complete repetition grid required')
            indices.append(save(out/('REPETITION_'+str(rep)+'_PREDICTION_INDEX.json'),dict(schema=SCHEMA,status='COMPLETE',requested=len(rows),completed=len(rows),case_ids=cases,profile_routes=[dict(candidate_id=p,stream=t,identity_tap=t) for p,t in routes],rows=rows,generation=request['generation'],repetition=rep,source_manifest=pb,scope='One actual historical paced repetition; no independent-scene pooling across repeats or full-bank sources.')))
        return save(out/'RESULT.json',dict(schema=SCHEMA,status='COMPLETE',created_utc=utc(),plan=rb,requested=len(jobs),completed=len(produced),measurements=measurements,indices=indices,repetition_comparisons=repeat,closure=closed,metadata_sources=meta.sources,code_sources=code.sources,elapsed_sec=time.perf_counter()-started,new_neural_calls=0,policy_replay=request['generation']=='research',scope='Closed actual historical paced observations and generation-correct score-compatible predictions. No actual C name metric, long-source or final S6C completion claim.'))
    except Exception as exc:
        save(out/'FAILURE.json',dict(schema=SCHEMA,status='FAILED_PRESERVED',error=repr(exc),plan=rb,produced=produced,measurements=measurements,metadata_sources=meta.sources));raise

def checks():
    checks=[]
    def bad(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):checks.append(name);return
        raise AssertionError(name+' accepted')
    for name in ('../escape','a/b',''):bad('namespace '+repr(name),lambda name=name:output(name))
    plan=dict(jobs=[dict(profile_id=p,telemetry=None,realtime=True) for p in ('B00','B01','B36')])
    assert [j['profile_id'] for j in selected_jobs(plan,'baseline')]==['B00'];checks.append('baseline generation isolated')
    assert [j['profile_id'] for j in selected_jobs(plan,'research')]==['B01','B36'];checks.append('research generation isolated')
    bad('unsupported generation',lambda:selected_jobs(plan,'mixed'))
    bad('cue route',lambda:selected_jobs(dict(jobs=[dict(profile_id='B01',telemetry={},realtime=True)]),'research'))
    events=[dict(event_type='speaker_decision',source_time_sec=1.,payload=dict(spatial_evidence=dict(source_start_sec=.5,source_end_sec=1.,provider='none',source_clock='audio_sample_clock')))]
    assert baseline_features(events)['features'][0]['available_at_sec'] is None;checks.append('baseline unlogged availability remains null')
    changed=deepcopy(events);changed[0]['payload']['spatial_evidence']['source_start_sec']=.25;bad('changed baseline window',lambda:baseline_features(changed))
    assert same_shared({'label':'A'},{'label':'A','clock':2}) and not same_shared({'label':'A'},{'label':'B'});checks.append('shared field equality rejects changed labels')
    assert logical({'label':'A','policy_compute_sec':1})=={'label':'A'};checks.append('only explicit execution clocks excluded')
    sample=dict(elapsed_sec=1.,tree=dict(processes=[],tree_complete=False),live=None)
    measured=process_observations([sample],set());assert measured['sample_count']==1 and measured['backlog']['asr_cursor_sec']['max'] is None and measured['process']['rss_sum_upper_bound_bytes']['max'] is None;checks.append('missing telemetry/resource not zero')
    bad('backward trajectory',lambda:process_observations([sample,dict(sample,elapsed_sec=.5)],set()))
    bad('empty trajectory',lambda:process_observations([],set()))
    origin='2026-09-10T00:00:00+00:00'
    ev=lambda k,t,wall,p:dict(event_type=k,source_time_sec=t,wall_time_utc=wall,payload=p)
    stream=[ev('source_started',0.,origin,{}),ev('transcript_final',.123457,'2026-09-10T00:00:01+00:00',dict(text='hi',speaker='Unknown')),ev('session_completed',1.,'2026-09-10T00:00:02+00:00',{})]
    disp=[dict(event_type='transcript_final',source_time_sec=.123456789,emitted_wall_time_utc=stream[1]['wall_time_utc'],payload=stream[1]['payload'])]
    worker=dict(source_started_wall_time_utc=origin)
    got=emitted_observations(stream,disp,worker);assert got['rows'][0]['emission_minus_source_cursor_sec']==1-.123457;checks.append('Actual emitted time and original six-decimal serialization preserved')
    altered=deepcopy(disp);altered[0]['payload']['text']='other';bad('Changed native/display text',lambda:emitted_observations(stream,altered,worker))
    altered=deepcopy(stream);altered[1]['wall_time_utc']='2026-09-09T23:59:59+00:00';dd=deepcopy(disp);dd[0]['emitted_wall_time_utc']=altered[1]['wall_time_utc']
    observed=emitted_observations(altered,dd,worker);assert observed['wall_order_reversals']==[2] and observed['rows'][0]['from_source_started_sec']==-1;checks.append('Actual backward UTC flagged without sorting or clamping')
    bad('Missing native source start',lambda:emitted_observations(stream[1:],disp,worker))
    bad('Duplicate native completion',lambda:emitted_observations(stream+[stream[-1]],disp,worker))
    bad('Timezone-naive native clock',lambda:stamp('2026-09-10T00:00:00'))
    bad('Unrecorded sampled owner',lambda:process_observations([dict(sample,tree=dict(processes=[dict(pid=1,creation_time=1.,cpu_seconds=1.)],tree_complete=True))],set()))
    with tempfile.TemporaryDirectory(prefix='s6c_historical_paced_buffer_') as td:
        p=Path(td)/'one.json';p.write_bytes(b'{"a":1}');b=binding(p);r=Reader();assert r.json(b)=={'a':1};p.write_bytes(b'{"a":2}')
        assert r.json(b)=={'a':1};checks.append('Parsed exact verified buffer retained once per cell')
        bad('Changed disk bytes on new admission',lambda:Reader().json(b))
        bad('Conflicting repeated declaration',lambda:r.raw(binding(p)))
        p.write_bytes(b'{"a":NaN}');bad('Nonfinite JSON',lambda:Reader().json(binding(p)))
    return dict(status='PASS_PURE_CHECKS',checks=checks,model_calls=0,actual_paced_cells=0)


def source_checks():
    """Prepared manifest metadata plus original attribution AST; no cell events."""
    inv=inventory();records=[];asts=[]
    with tempfile.TemporaryDirectory(prefix='s6c_historical_paced_metadata_') as td:
        reader=inv.base.MetadataReader(td)
        for name in ('controls_v1','b36_v1'):
            path=inv.base.PAYLOAD/'paced_controls'/name/'MANIFEST.json';plan,pb,spec=inv.admit_plan(reader,binding(path))
            for generation in (('baseline','research') if name=='controls_v1' else ('research',)):
                r=Reader();raw,extract=authority_code(plan,spec,r,generation);api=pure_adapters(raw,extract)
                jobs=selected_jobs(plan,generation);records.append(dict(manifest=pb,generation=generation,jobs=len(jobs),sources=r.sources))
                tree=ast.parse(raw);original=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='historical')
                expected=hashlib.sha256(ast.dump(ast.Module(body=original.body[2:],type_ignores=[]),include_attributes=False).encode()).hexdigest()
                require(expected==api['historical_attribution_ast_sha256'],'Original attribution body differs');asts.append(expected)
                events=[dict(event_type='speaker_decision',source_time_sec=1.,payload=dict(anonymous_label='Speaker 1')),dict(event_type='transcript_partial',source_time_sec=1.,payload=dict(utterance_index=1,text='he',speaker='Speaker 1')),dict(event_type='transcript_final',source_time_sec=2.,payload=dict(utterance_index=1,text='hello',speaker='Speaker 2'))]
                x=api['historical_buffers'](events,dict(features=[]));require(x['final_transcripts_latest'][0]['speaker']=='Speaker 2' and x['final_transcripts_first_display'][0]['speaker']=='Speaker 1' and not x['transcript_events'],'Historical first-display attribution differs')
        consumed=[x['source'] for x in reader.sources]
    require([r['jobs'] for r in records]==[40,40,40],'Actual prepared generation grid differs')
    return dict(status='PASS_PREPARED_METADATA_AND_ORIGINAL_AST',records=records,metadata_sources=consumed,attribution_ast_hashes=asts,actual_cell_reads=0,model_calls=0,policy_replays=0,scope='Three generation admissions from two already prepared historical manifests; no native completion or actual paced analysis claimed.')

def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);sub=p.add_subparsers(dest='action',required=True)
    for command in ('checks','source-checks'):
        checker=sub.add_parser(command);checker.add_argument('--output',type=Path)
    a=sub.add_parser('prepare');a.add_argument('--manifest',type=Path,required=True);a.add_argument('--manifest-sha256',required=True);a.add_argument('--generation',choices=('baseline','research'),required=True);a.add_argument('--name',required=True)
    a=sub.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--plan-sha256',required=True)
    a=p.parse_args()
    if a.action in ('checks','source-checks'):
        result=checks() if a.action=='checks' else source_checks();result['source_bindings']=sources()
        return save(a.output,result) if a.output else result
    return prepare(a) if a.action=='prepare' else run(a)

if __name__=='__main__':print(json.dumps(main(),indent=2,allow_nan=False))
