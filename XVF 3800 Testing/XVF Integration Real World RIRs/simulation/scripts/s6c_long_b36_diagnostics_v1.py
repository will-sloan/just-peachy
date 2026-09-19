"""Closed original B36 continuous observations; README_S6C_LONG_B36_DIAGNOSTICS_V1.md."""
from __future__ import annotations
import argparse, ast, hashlib, importlib.util, json, math, os, re, sys, tempfile, time, traceback
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent; SIM=HERE.parent
REPORT=SIM/'reports/S6C/20260910T123540Z'
SCHEMA='s6c-original-b36-continuous-diagnostics.v1'
EDGE=SIM.parents[2]/'.edge-speech-env/python.exe'
PINS={
's6c_execution_inventory_v5.py':'aee67604429f12013058ed94c74c3d3965c1e8e55299c87dfb6760394513aad8',
's6c_historical_paced_analysis_v1.py':'982e1c7b2bf38fdc7a92a023cff0e73e2cbccf2072233924e6eaa5e84657a712',
's6c_long_b36_v1.py':'09b809f6301e696054c4563fdad0d48072ae22716bafcf9002a33bdffd866c66'}
PURE_NAMES=('require','finite','stamp','emitted_observations','process_observations')
DURATION=1827.426625; FRAMES=29238826; RATE=16000
JSON_CAP=128*2**20; LINE_CAP=32*2**20; STREAM_CAP=2**30
TRANSCRIPT={'transcript_partial','transcript_final','transcript_label_revision'}
KEEP=TRANSCRIPT|{'speaker_decision','source_started','session_completed'}

def require(ok,message):
    if not ok: raise ValueError(message)
def finite(x): return type(x) in (int,float) and math.isfinite(x)
def natural(x): return type(x) is int and x>=0
def utc(): return datetime.now(timezone.utc).isoformat()
def binding(path,raw):
    return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read_small(path,expected=None,cap=JSON_CAP):
    path=Path(path).resolve(); before=path.stat(); require(before.st_size<=cap,'Bounded input size exceeded')
    raw=path.read_bytes(); after=path.stat()
    require((before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'Input changed during read')
    b=binding(path,raw); require(len(raw)==before.st_size,'Input length changed')
    if expected is not None: require(b=={k:expected[k] for k in ('path','bytes','sha256')},'Exact consumed buffer differs')
    return raw,b
def load_json(path,expected=None):
    raw,b=read_small(path,expected); return json.loads(raw.decode('utf-8-sig')),b
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as f: f.write(raw);f.flush();os.fsync(f.fileno())
    return binding(path,raw)
def own_sources():
    rows=[]
    for name in (Path(__file__).name,'README_S6C_LONG_B36_DIAGNOSTICS_V1.md',*PINS):
        raw,b=read_small(HERE/name)
        if name in PINS:require(b['sha256']==PINS[name],'Held source changed: '+name)
        rows.append(b)
    return rows
def pure_api():
    raw,b=read_small(HERE/'s6c_historical_paced_analysis_v1.py')
    require(b['sha256']==PINS[Path(b['path']).name],'Historical observation source differs')
    by={n.name:n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}
    nodes=[deepcopy(by[n]) for n in PURE_NAMES]
    ns=dict(datetime=datetime,math=math)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<exact historical observation functions>','exec'),ns)
    proof={n:hashlib.sha256(ast.dump(by[n],include_attributes=False).encode()).hexdigest() for n in PURE_NAMES}
    return ns,proof
def inventory():
    own_sources();path=HERE/'s6c_execution_inventory_v5.py'
    spec=importlib.util.spec_from_file_location('_s6c_b36_diagnostics_inventory',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    require(Path(mod.__file__).resolve()==path,'Wrong metadata import')
    require(not any(k=='edge_speech_pipeline' or k.startswith('edge_speech_pipeline.') for k in sys.modules),'No native APP import allowed')
    return mod
def no_quiet():
    require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Defer analysis while any paced quiet lease exists')
def output(name):
    require(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,60}',name),'Simple fresh output name required')
    return REPORT/'long_b36_diagnostics'/name

def require_closed(row,records,owners,spawns):
    require(row['status']=='COMPLETE' and row['native_session_complete'] is True,'Complete original native and outer result required')
    require(row['process_state']['alive'] is False,'Native current closure unverified')
    require(len(records)==len(spawns)==1,'Exactly one recorded physical invocation/spawn required for this source namespace')
    require(records[0]['status']=='NATIVE_COMPLETE' and records[0]['closure_status']=='NATIVE_COMPLETE_QUIET_RELEASED','Complete native and released quiet lease required')
    require(owners and all(o['process_state']['alive'] is False and finite(o['creation_time']) and o['creation_time']>0 for o in owners),'Current coordinator/child closure unavailable')
    require(spawns[0][0]['pid']==row['pid'],'Physical spawn/native owner mismatch')
    recorded={(o['pid'],o['creation_time']) for o in row['recorded_owned_processes']}
    observed={(o['pid'],o['creation_time']) for o in owners}
    require(recorded<=observed,'Recorded native owner missing from current closure checks')
    return dict(logical_sessions=1,physical_spawns=1,source_pieces_not_sessions=38,native=row,
                invocations=records,current_owners=owners,spawn_bindings=[b for _,b in spawns],
                scope='Recorded PID+creation identities closed at this check; no claim of exhaustive OS descendant discovery.')

def closed(inv,reader,manifest):
    plan,pb,a,g=inv.admit_long(reader,manifest)
    row=inv.admit_long_native(reader,plan,pb,a,g)
    records,owners,spawns=inv.long_invocations(reader,plan,pb)
    fact=require_closed(row,records,owners,spawns)
    return plan,pb,a,fact

def stats(values):
    valid=[v for v in values if v is not None]
    require(all(finite(v) for v in valid),'Nonfinite observed statistic')
    return dict(observed=len(valid),missing=len(values)-len(valid),min=min(valid) if valid else None,max=max(valid) if valid else None,
                first=valid[0] if valid else None,last=valid[-1] if valid else None)

def sample_point(value):
    require(finite(value) and value>=0,'Finite nonnegative source endpoint required')
    n=round(value*RATE);require(abs(n/RATE-value)<=1e-6,'Source endpoint not on sample clock');return n

class EventFacts:
    """Stream all exact lines; retain lightweight emission projection, no vectors/frame arrays."""
    def __init__(self,frames=FRAMES):
        self.frames=frames;self.projection=[];self.counts=Counter();self.costs=defaultdict(lambda:defaultdict(float));self.cost_count=Counter()
        self.spans=[];self.tail=[];self.drain=[];self.decisions=[];self.admissions=[];self.watermarks=[]
        self.lineage=Counter();self.states=Counter();self.reasons=Counter();self.ids=set();self.raw_asr=0;self.finals=[]
        self.native_endpoints=0;self.advisory_endpoints=0;self.resets=0;self.coincident=0
        self.last_event_line=0
    def add(self,e,line):
        require(type(e) is dict and isinstance(e['event_type'],str) and type(e['payload']) is dict,'Original event object required')
        require(finite(e['source_time_sec']) and e['source_time_sec']>=0,'Source cursor unavailable/nonfinite')
        kind=e['event_type'];p=e['payload'];self.counts[kind]+=1;self.last_event_line=line
        self.projection.append({k:deepcopy(e[k]) for k in ('event_type','source_time_sec','wall_time_utc')}|dict(payload=deepcopy(p) if kind in KEEP else {}))
        require(len(self.projection)==line,'Blank/native event lines unsupported; exact event positions required')
        for key in ('compute_ms','model_api_elapsed_ms','postprocess_compute_ms','full_dispatch_elapsed_ms','advisor_compute_ms','gate_compute_ms','scheduler_dispatch_ms','policy_compute_sec'):
            if key in p and p[key] is not None:
                require(finite(p[key]) and p[key]>=0,'Invalid measured cost')
                self.costs[kind][key]+=p[key]
        self.cost_count[kind]+=1
        if kind in ('research_asr_dispatch','research_asr_tail_dispatch'):
            start,end=sample_point(p['source_start_sec']),sample_point(p['source_end_sec'])
            require(0<=start<end<=self.frames,'ASR dispatch outside declared source')
            require(start==(self.spans[-1][1] if self.spans else 0),'ASR dispatch gap/duplicate/reordering')
            self.spans.append((start,end))
            if kind=='research_asr_tail_dispatch':
                require(natural(p['samples']) and p['samples']==end-start,'Tail sample count invalid')
                self.tail.append(dict(event_line=line,**deepcopy(p)))
            else:
                for k in ('native_endpoint','advisory_endpoint','reset_requested'):require(type(p[k]) is bool,'Endpoint/reset flag must be Boolean')
                require(p['reset_requested']==(p['native_endpoint'] or p['advisory_endpoint']),'Original reset OR differs')
                self.native_endpoints+=p['native_endpoint'];self.advisory_endpoints+=p['advisory_endpoint'];self.resets+=p['reset_requested'];self.coincident+=p['native_endpoint'] and p['advisory_endpoint']
        elif kind=='research_asr_drain':
            require(sample_point(p['source_end_sec'])==self.frames and p['padding_is_observed_audio'] is False and p['synthetic_right_padding_sec']==.66,'Exact original ASR drain/padding required')
            self.drain.append(dict(event_line=line,**deepcopy(p)))
        elif kind=='research_asr_observation':
            self.raw_asr+=1
        elif kind=='research_embedding_admission':
            require(type(p['admitted']) is bool and isinstance(p['reason'],str),'Actual original admission flags required')
            self.admissions.append(dict(event_line=line,wall_time_utc=e['wall_time_utc'],source_cursor_sec=e['source_time_sec'],payload=deepcopy(p)))
        elif kind=='research_scheduler_watermark':
            self.watermarks.append(dict(event_line=line,wall_time_utc=e['wall_time_utc'],source_cursor_sec=e['source_time_sec'],payload=deepcopy(p)))
        elif kind=='speaker_decision':
            d=p['decision'];require(type(d) is dict and isinstance(d['lineage'],list),'Original S6B decision/lineage required')
            self.decisions.append(d);self.states[str(d['state'])]+=1;self.reasons[str(d['reason'])]+=1
            if d['tracker_id'] is not None:self.ids.add(d['tracker_id'])
            for op in d['lineage']:self.lineage[op['event']]+=1
        elif kind in TRANSCRIPT:
            if kind!='transcript_label_revision':require(isinstance(p['text'],str),'Native text must remain an actual string')
            if kind=='transcript_final':self.finals.append(p)
    def finish(self,native):
        require(dict(self.counts)==native['event_counts'],'Actual native event-count dictionary differs')
        require(self.spans and self.spans[-1][1]==self.frames,'ASR whole-source dispatch incomplete')
        require(len(self.tail)<=1 and len(self.drain)==1,'Exactly one drain and at most one source tail required')
        if self.tail:require(sample_point(self.tail[0]['source_end_sec'])==self.frames,'Tail does not end full source')
        delivery=dict(blocks=len(self.spans),no_gaps_or_duplicates=True,starts_at_zero=True,ends_at_full_duration=True,exact_samples=sum(b-a for a,b in self.spans)==self.frames)
        require(delivery==native['native_dispatch_delivery'],'Reconstructed dispatch proof differs')
        require(self.raw_asr==native['raw_asr_observations'],'Raw ASR count differs')
        require([x['text'] for x in self.finals]==native['final_raw_texts'] and [x.get('speaker') for x in self.finals]==native['final_labels'],'Actual final-emission list differs')
        cost={k:dict(count=self.cost_count[k],inclusive_nested_values=dict(v)) for k,v in self.costs.items()}
        require(set(cost)==set(native['costs']),'Actual native cost event types differ')
        for k,row in cost.items():
            want=native['costs'][k];require(row['count']==want['count'] and set(row['inclusive_nested_values'])==set(want['inclusive_nested_values']),'Cost count/field scope differs')
            for key,v in row['inclusive_nested_values'].items():require(math.isclose(v,want['inclusive_nested_values'][key],rel_tol=1e-12,abs_tol=1e-8),'Exact-order inclusive cost sum differs')
        return dict(event_counts=dict(self.counts),native_dispatch_delivery=delivery,tail=self.tail,drain=self.drain,
            endpoint_flags=dict(native=self.native_endpoints,advisory=self.advisory_endpoints,coincident=self.coincident,reset_requested=self.resets),
            raw_asr_observations=self.raw_asr,decision_count=len(self.decisions),distinct_observed_track_ids=len(self.ids),observed_track_ids=sorted(self.ids),
            decision_states=dict(self.states),decision_reasons=dict(self.reasons),lineage_events=dict(self.lineage),
            evidence_admission_observations=len(self.admissions),admission_reasons=dict(Counter(x['payload']['reason'] for x in self.admissions)),
            evidence_debt_due_flags=sum(x['payload'].get('evidence_debt_due') is True for x in self.admissions),
            evidence_debt_flag_missing=sum('evidence_debt_due' not in x['payload'] for x in self.admissions),
            direct_cue_flags=sum(x['payload'].get('cue_event') is True for x in self.admissions),
            admission_hops_sec=stats([x['payload'].get('selected_hop_sec') for x in self.admissions]),inclusive_costs=cost,
            unavailable=dict(per_track_debt=None,released_tracking_context_age_sec=None,active_archive_retirement_counts=None,known_name_correctness=None,wrong_known_exposure=None,wer=None),
            scope='Original S6B admission debt is the logged global since-observation flag, not S6C per-track debt. Distinct observed IDs are not simultaneous live count; lineage observations are not a reconstructed tracker snapshot. No gallery/person truth, WER or continuous correctness score.')

def stream(path,expected,consume,cap=STREAM_CAP):
    path=Path(path).resolve();before=path.stat();require(before.st_size<=cap,'Stream size cap exceeded')
    h=hashlib.sha256();size=0;lines=0
    with path.open('rb') as f:
        while True:
            raw=f.readline(LINE_CAP+1)
            if not raw:break
            require(len(raw)<=LINE_CAP,'Bounded event line exceeded');h.update(raw);size+=len(raw)
            require(raw.strip(),'Blank line would change event-position semantics')
            lines+=1;consume(json.loads(raw.decode('utf-8-sig' if lines==1 else 'utf-8')),lines)
    after=path.stat();require((before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'Stream changed during read')
    b=dict(path=str(path),bytes=size,sha256=h.hexdigest())
    require(size==before.st_size,'Stream byte count differs')
    if expected is not None:require(b=={k:expected[k] for k in ('path','bytes','sha256')},'Consumed stream binding differs')
    return b,lines

def validate_summary(summary,native,job,emission):
    require(summary==native['summary'] and summary['state']=='COMPLETED','Actual native summary/state differs')
    require(summary['assets']==[dict(component_id=a['component_id'],sha256=a['sha256']) for a in job['assets']],'Actual model identities differ')
    require(summary['research']['profile']==job['profile'] and summary['research']['telemetry_sha256'] is None and summary['research']['effective_config']['input_gain']==1.,'Original profile/cue/gain differs')
    t=summary['telemetry'];require(t['source_duration_sec']==DURATION and t['asr_cursor_sec']==DURATION,'Full original source/ASR cursor required')
    require(all(type(t[k]) in (int,float) and t[k]==0 for k in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures')),'Audio-loss evidence missing/nonzero')
    s=t['scheduler'];require(s['schema_version']=='edge-scheduler-snapshot.v2' and s['closed'] is True and s['pending_events']==0 and all(v=='closed' for v in s['watermarks'].values()),'Original scheduler not fully drained')
    start=emission['source_started']['payload']
    require(start['mode']=='wav' and Path(start['path']).resolve()==Path(job['input']['path']).resolve() and start['pipeline_sample_rate']==RATE and start['channels']==1,'Actual source path/rate/channel differs')
    return dict(actual_source=start,summary_telemetry=deepcopy(t),research=deepcopy(summary['research']),models=deepcopy(summary['assets']),
                scheduler_scope='Original bounded final scheduler snapshot and retained utterances; final retained counts are not lifetime/live peaks.')

def trajectory(samples,outer,api,owned):
    counts={k:outer[k] for k in ('periodic_process_samples','terminal_process_samples','process_samples')}
    require(all(natural(v) for v in counts.values()) and counts['terminal_process_samples']==1 and counts['process_samples']==counts['periodic_process_samples']+1,'Exact declared trajectory counts required')
    require(len(samples)==counts['process_samples'] and samples,'Trajectory total differs')
    periodic=samples[:-1];terminal=samples[-1]
    require(all(x['phase']=='periodic' for x in periodic) and terminal['phase']=='terminal_after_child_exit','One final terminal record only')
    require(terminal['child_returncode']==0 and terminal['live'] is None,'Terminal closure record must not contain synthetic LIVE')
    require(finite(terminal['elapsed_sec']) and terminal['elapsed_sec']>=0 and (not periodic or terminal['elapsed_sec']>=periodic[-1]['elapsed_sec']),'Terminal clock precedes periodic record')
    ts={(x['pid'],x['creation_time']) for x in terminal['owned_processes']}
    require(ts==owned and len(ts)==len(terminal['owned_processes']) and all(x['alive'] is False for x in terminal['owned_processes']),'Terminal recorded closure differs')
    result=api['process_observations'](periodic,owned) if periodic else None
    return dict(counts=counts,periodic=result,terminal=terminal,coordinator_rss_bytes=stats([x.get('coordinator_rss_bytes') for x in periodic]),
                scope='Original process-observation function applied only to actual periodic rows. Terminal closure is separate, never an invented process or LIVE sample. Child memory excludes coordinator; coordinator RSS is separate. Peaks are sampled, gaps include global directory-scan overhead.')

def observer(events,snapshot,live_path,periodic_count,reader):
    counts=Counter(e['event'] for e in events);raws=[];seen=set()
    require(snapshot['live_calls']==sum(snapshot['live_calls_by_path'].values())<=periodic_count,'Read-call versus periodic denominator differs')
    require(all(Path(k).resolve()==Path(live_path).resolve() for k in snapshot['live_calls_by_path']),'Observer tracked an unrelated LIVE')
    require(snapshot['missing_live_json_calls']==sum(snapshot['missing_live_json_by_path'].values())==counts['optional_live_json_missing'],'Missing optional LIVE count differs')
    require(snapshot['failed_calls']==counts['live_snapshot_failed'],'Declared failed reads differ')
    for e in events:
        if e['event']=='optional_live_json_missing':
            require(e['sample_value'] is None and Path(e['path']).resolve()==Path(live_path).resolve(),'Optional missing sample scope differs')
        if 'raw_binding' in e:
            b=e['raw_binding'];require(b['path'] not in seen,'Duplicate retained snapshot');seen.add(b['path'])
            raw,actual=reader(b)
            if 'bytes' in e:require(e['bytes']==len(raw),'Retained convenience byte count differs')
            if 'sha256' in e:require(e['sha256']==actual['sha256'],'Retained convenience hash differs')
            raws.append(actual)
    require(len(raws)==snapshot['captured_snapshots'] and sum(b['bytes'] for b in raws)==snapshot['captured_bytes'],'Exact retained anomaly count/bytes differ')
    return dict(snapshot=snapshot,event_counts=dict(counts),retained_raw_bindings=raws,
                scope='Reader calls, missing-JSON calls and periodic trajectory rows have separate denominators. Missing JSON is not a native failure. No prefix parsing, interpolation, prior-value reuse or continuous telemetry claim.')

def prepare(args):
    no_quiet();inv=inventory();out=output(args.name);require(not out.exists(),'Fresh analysis namespace required')
    _,mb=read_small(args.manifest);require(mb['sha256']==args.manifest_sha256,'Explicit manifest SHA differs')
    out.mkdir(parents=True);reader=inv.base.MetadataReader(out)
    try:
        plan,pb,a,closure=closed(inv,reader,mb);_,proof=pure_api()
        return save(out/'PLAN.json',dict(schema=SCHEMA,status='PREPARED_CLOSED_NATIVE_DIAGNOSTICS',name=args.name,created_utc=utc(),manifest=pb,sources=own_sources(),pure_function_ast_sha256=proof,closure=closure,metadata_sources=reader.sources,
           scope='Preparation reads only exact source/completion/owner metadata. No payload, PCM, model, policy or score computation.'))
    except Exception:
        save(out/'PREPARATION_FAILURE.json',dict(status='FAILED_PRESERVED',error=traceback.format_exc(),manifest=mb,metadata_sources=reader.sources));raise

def run(args):
    no_quiet();require(Path(sys.executable).resolve()==EDGE.resolve(),'Exact EDGE interpreter required')
    request,rb=load_json(args.plan);require(rb['sha256']==args.plan_sha256,'Exact plan SHA required')
    out=output(request['name']);require(Path(rb['path'])==out/'PLAN.json' and request['schema']==SCHEMA and request['status']=='PREPARED_CLOSED_NATIVE_DIAGNOSTICS' and request['sources']==own_sources(),'Analysis source/plan drift')
    require(not (out/'RESULT.json').exists() and not (out/'FAILURE.json').exists(),'Preserve prior analysis attempt')
    inv=inventory();reader=inv.base.MetadataReader(out);consumed=[];produced=[];started=time.perf_counter()
    try:
        plan,pb,a,closure=closed(inv,reader,request['manifest']);api,proof=pure_api();require(proof==request['pure_function_ast_sha256'],'Pure observation code differs')
        job=plan['jobs'][0];outer,ob=reader.read(closure['native']['continuous_result']['path'],closure['native']['continuous_result'])
        native,nb=reader.read(outer['native_result']['path'],outer['native_result'])
        summary,sb=load_json(native['summary_binding']['path'],native['summary_binding']);consumed.append(sb)
        display,db=load_json(native['display_events']['path'],native['display_events']);consumed.append(db)
        no_quiet();facts=EventFacts();eb,n=stream(native['events']['path'],native['events'],facts.add);consumed.append(eb)
        factual=facts.finish(native);emission=api['emitted_observations'](facts.projection,display,native)
        summaryfacts=validate_summary(summary,native,job,emission)
        samples=[];tb=next(b for b in outer['artifacts'] if Path(b['path']).name=='PROCESS_SAMPLES.jsonl')
        consumed.append(stream(tb['path'],tb,lambda x,i:samples.append(x),JSON_CAP)[0])
        owned={(x['pid'],x['creation_time']) for x in outer['owned_processes']}
        process=trajectory(samples,outer,api,owned)
        ip=Path(closure['invocations'][0]['admission']['path']).parent
        observations=[];obsb,_=stream(ip/'OBSERVER_EVENTS.jsonl',None,lambda x,i:observations.append(x),JSON_CAP);consumed.append(obsb)
        def raw_reader(b):
            require(Path(b['path']).resolve().parent==ip/'rejected_snapshots','Rejected snapshot outside exact observer root')
            raw,bb=read_small(b['path'],b,65537);consumed.append(bb);return raw,bb
        obs=observer(observations,outer['observer_stats'],Path(plan['output_root'])/'jobs'/job['job_id']/'LIVE.json',outer['periodic_process_samples'],raw_reader)
        for name,value in (('ACTUAL_EMISSIONS.json',emission),('ORIGINAL_ADMISSIONS_AND_WATERMARKS.json',dict(admissions=facts.admissions,watermarks=facts.watermarks)),('PROCESS_OBSERVATIONS.json',process)):
            produced.append(save(out/name,value))
        no_quiet()
        return save(out/'RESULT.json',dict(schema=SCHEMA,status='COMPLETE_OBSERVATIONS_ONLY',created_utc=utc(),plan=rb,manifest=pb,profile_id='B36',tap=job['stream'],actual_execution_epoch='S6B_epoch2',source_composition_epoch='S6C_epoch2',source_kind='EXISTING_CONTINUOUS_COMPOSITION',duration_sec=DURATION,source_samples=FRAMES,logical_sessions=1,physical_spawns=1,
            source_input=job['input'],pcm_body_declaration=native['journal'],pcm_scope='Native result and reviewed outer completion bind exact PCM body. PCM and model files not reopened by this diagnostic; no fresh byte-level PCM verification claim.',
            native_result=nb,outer_result=ob,closure=closure,summary=summaryfacts,events=factual,observer=obs,process=process,
            native_cost_fields={k:native[k] for k in ('full_worker_elapsed_sec','bundle_admission_sec','engine_launch_loading_sec','process_cpu_sec_at_end','process_io_write_bytes_at_end','cost_scope','clock_scope')},
            output_bindings=produced,consumed_payloads=consumed,metadata_sources=reader.sources,pure_function_ast_sha256=proof,elapsed_sec=time.perf_counter()-started,new_neural_calls=0,policy_replay=False,scene_score=False,
            limitations=['One dependent continuous composition, not38 independent sessions.','Emission UTC minus source cursor is source-attributed processing time, not phonetic/current-speaker/GUI latency.','Modeled lane availability and actual wall emission remain separate.','No source/person correctness or C naming API on historical schemas.','Lifetime observed ID count does not reconstruct active/retired/archive population.','Original30s drain,65s join and bounded state limits unchanged; only successfully admitted complete session is summarized.','All measured phase costs remain nested and lanes concurrent; no summing nested compute into whole-worker time.']))
    except Exception:
        save(out/'FAILURE.json',dict(schema=SCHEMA,status='FAILED_PRESERVED',plan=rb,error=traceback.format_exc(),consumed_payloads=consumed,produced=produced,metadata_sources=reader.sources));raise

def checks():
    results=[]
    def good(name,fn):fn();results.append(dict(name=name,status='PASS'))
    def bad(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError,AssertionError,FileExistsError):results.append(dict(name=name,status='PASS_REJECTED'));return
        raise AssertionError('Expected rejection: '+name)
    api,proof=pure_api()
    ts='2026-09-10T00:00:00+00:00'
    def e(kind,p=None,source=0.):return dict(event_type=kind,payload=p or {},wall_time_utc=ts,source_time_sec=source)
    row=dict(status='COMPLETE',native_session_complete=True,pid=1,creation_time=2.,process_state=dict(alive=False),recorded_owned_processes=[dict(pid=1,creation_time=2.)])
    records=[dict(status='NATIVE_COMPLETE',closure_status='NATIVE_COMPLETE_QUIET_RELEASED')]
    owners=[dict(pid=1,creation_time=2.,process_state=dict(alive=False)),dict(pid=2,creation_time=3.,process_state=dict(alive=False))]
    spawns=[(dict(pid=1),{})]
    good('complete exact one physical session',lambda:require_closed(row,records,owners,spawns))
    for state in (True,None):
        changed=deepcopy(owners);changed[-1]['process_state']['alive']=state
        bad('coordinator closure '+str(state),lambda changed=changed:require_closed(row,records,changed,spawns))
    bad('partial native',lambda:require_closed({**row,'status':'NATIVE_COMPLETE_OBSERVER_PARTIAL'},records,owners,spawns))
    bad('failed release',lambda:require_closed(row,[dict(status='NATIVE_COMPLETE',closure_status='FAILED_OR_RELEASE_UNVERIFIED')],owners,spawns))
    bad('extra physical attempt',lambda:require_closed(row,records,owners,spawns*2))
    bad('spawn mismatch',lambda:require_closed(row,records,owners,[(dict(pid=8),{})]))
    bad('missing recorded owner',lambda:require_closed(row,records,owners[1:],spawns))
    for val in (True,-1,float('nan'),.00003):bad('sample endpoint '+repr(val),lambda val=val:sample_point(val))
    good('integer source sample boundary',lambda:require(sample_point(7/RATE)==7,'sample'))
    def fixture():
        facts=EventFacts(1607)
        rows=[e('source_started'),e('research_asr_dispatch',dict(source_start_sec=0.,source_end_sec=.1,native_endpoint=True,advisory_endpoint=True,reset_requested=True),.1),
              e('research_asr_tail_dispatch',dict(source_start_sec=.1,source_end_sec=1607/RATE,samples=7),1607/RATE),
              e('research_asr_drain',dict(source_end_sec=1607/RATE,synthetic_right_padding_sec=.66,padding_is_observed_audio=False),1607/RATE),e('session_completed')]
        for i,r in enumerate(rows,1):facts.add(r,i)
        native=dict(event_counts=dict(facts.counts),native_dispatch_delivery=dict(blocks=2,no_gaps_or_duplicates=True,starts_at_zero=True,ends_at_full_duration=True,exact_samples=True),raw_asr_observations=0,final_raw_texts=[],final_labels=[],costs={})
        return facts,rows,native
    f,rs,native=fixture();good('seven sample tail and native OR reset',lambda:require(f.finish(native)['endpoint_flags']==dict(native=1,advisory=1,coincident=1,reset_requested=1),'OR'))
    for key,val in [('samples',True),('samples',6),('source_start_sec',.09),('source_end_sec',.2)]:
        def reject_tail(key=key,val=val):
            f=EventFacts(1607);f.add(rs[0],1);f.add(rs[1],2);v=deepcopy(rs[2]);v['payload'][key]=val;f.add(v,3)
        bad('tail mutation '+key+str(val),reject_tail)
    bad('drain missing',lambda:(setattr(f,'drain',[]),f.finish(native)))
    f,rs,native=fixture();bad('wrong event counts',lambda:f.finish({**native,'event_counts':{}}))
    r=deepcopy(rs[1]);r['payload']['reset_requested']=False;bad('wrong reset OR',lambda:EventFacts(1607).add(r,1))
    decision=e('speaker_decision',dict(decision=dict(state='provisional',reason='original_common_scheduler_control',tracker_id=1,lineage=[dict(event='track_create',track_id=1)])))
    facts=EventFacts();facts.add(decision,1);good('original lineage not C lifecycle counts',lambda:require(facts.lineage['track_create']==1 and facts.ids=={1},'lineage'))
    partial=e('transcript_partial',dict(text='',speaker='Speaker_1'));facts.add(partial,2)
    good('empty actual string preserved',lambda:require(facts.projection[-1]['payload']['text']=='','text'))
    bad('nonstring transcript text',lambda:EventFacts().add(e('transcript_final',dict(text=None)),1))
    display=[dict(event_type='transcript_partial',source_time_sec=.123456789,emitted_wall_time_utc=ts,payload=dict(text='x'))]
    events=[e('source_started'),e('transcript_partial',dict(text='x'),.123457),e('session_completed')]
    good('exact native display rounding',lambda:api['emitted_observations'](events,display,dict(source_started_wall_time_utc=ts)))
    changed=deepcopy(display);changed[0]['payload']['text']='wrong';bad('changed display text',lambda:api['emitted_observations'](events,changed,dict(source_started_wall_time_utc=ts)))
    owned={(1,2.)};terminal=dict(phase='terminal_after_child_exit',elapsed_sec=2.,child_returncode=0,live=None,owned_processes=[dict(pid=1,creation_time=2.,alive=False)])
    sample=dict(phase='periodic',elapsed_sec=1.,tree=dict(processes=[],tree_complete=False),live=None,coordinator_rss_bytes=12)
    outer=dict(periodic_process_samples=1,terminal_process_samples=1,process_samples=2)
    good('terminal separate from missing periodic sample',lambda:require(trajectory([sample,terminal],outer,api,owned)['periodic']['sample_count']==1,'sample'))
    for name,change in [('count',dict(process_samples=3)),('boolean count',dict(periodic_process_samples=True))]:
        bad(name,lambda change=change:trajectory([sample,terminal],outer|change,api,owned))
    for key,val in [('live',{}),('child_returncode',1),('elapsed_sec',0.)]:
        bad('terminal '+key,lambda key=key,val=val:trajectory([sample,terminal|{key:val}],outer,api,owned))
    good('no periodic samples stays unavailable',lambda:require(trajectory([terminal],dict(periodic_process_samples=0,terminal_process_samples=1,process_samples=1),api,owned)['periodic'] is None,'missing'))
    stats0=dict(live_calls=0,live_calls_by_path={},missing_live_json_calls=0,missing_live_json_by_path={},failed_calls=0,captured_snapshots=0,captured_bytes=0)
    good('observer zero calls explicit',lambda:observer([],stats0,'LIVE.json',1,None))
    bad('observer missing call mismatch',lambda:observer([],stats0|dict(missing_live_json_calls=1),'LIVE.json',1,None))
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'events.jsonl';raw=(json.dumps(e('x'))+'\n').encode();p.write_bytes(raw);b=binding(p,raw);rows=[]
        good('exact single stream consumed',lambda:require(stream(p,b,lambda x,i:rows.append((i,x)))[1]==1,'stream'))
        bad('stream hash mutation',lambda:stream(p,b|dict(sha256='0'*64),lambda x,i:None))
        p.write_bytes(b'\n');bad('blank event line',lambda:stream(p,None,lambda x,i:None))
        p.write_bytes(b'{}');bad('bounded JSON cap',lambda:read_small(p,cap=1))
        p.write_bytes(b'{}');j=binding(p,b'{}');good('same-buffer JSON binding',lambda:load_json(p,j))
        bad('immutable output',lambda:save(p,{}))
    return results,proof

def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    p.add_argument('action',choices=('checks','prepare','run'));p.add_argument('--output',type=Path)
    p.add_argument('--name');p.add_argument('--manifest',type=Path);p.add_argument('--manifest-sha256');p.add_argument('--plan',type=Path);p.add_argument('--plan-sha256');a=p.parse_args()
    if a.action=='checks':
        require(a.output is not None,'Fresh checks --output required');rows,proof=checks()
        return save(a.output,dict(schema=SCHEMA,status='PASS_MODEL_FREE_SOURCE_CHECKS',created_utc=utc(),check_count=len(rows),checks=rows,source_bindings=own_sources(),pure_function_ast_sha256=proof,new_neural_calls=0,real_native_payloads_read=0,actual_metadata_admission=False))
    if a.action=='prepare':
        require(a.name and a.manifest and a.manifest_sha256,'Explicit name/manifest/SHA required');return prepare(a)
    require(a.plan and a.plan_sha256,'Explicit plan/SHA required');return run(a)
if __name__=='__main__':print(json.dumps(main(),allow_nan=False))
