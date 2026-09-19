"""Closed continuous C-epoch4 observations; README_S6C_LONG_DIAGNOSTICS_V1.md."""
from __future__ import annotations
import argparse,ast,gzip,hashlib,importlib,json,math,re,tempfile
from collections import Counter,defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
PINS={'s6c_execution_inventory_v3.py':'8820bc19d88b6706aed93cdf5c879688f66f5b96e9d910124f94d1bebfc39d58',
      's6c_paced_analysis_v1.py':'936b5973091d677b4eb24847e7e3e2d84df614340d3984f10ff31283096b880a'}
for name,sha in PINS.items():
    if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=sha:raise ValueError('Held diagnostic dependency changed: '+name)
V=importlib.import_module('s6c_execution_inventory_v3');B=V.base;REPORT=B.REPORT
if Path(V.__file__).resolve()!=HERE/'s6c_execution_inventory_v3.py':raise ValueError('Wrong held inventory import')
SCHEMA='s6c-continuous-native-observations.v1'
MAX_FILE=1024*2**20;MAX_LINE=8*2**20;MAX_ROWS=1000000;MAX_RETAINED=100000;MAX_PROJECTION_BYTES=128*2**20

def require(ok,message):
    if not ok:raise ValueError(message)

def pure_helpers():
    names={'fail','number','utc_seconds','stats','trajectory_observations','active_context_observations'}
    nodes=[n for n in ast.parse((HERE/'s6c_paced_analysis_v1.py').read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name in names]
    require(len(nodes)==len(names),'Exact pure observation functions required')
    ns=dict(math=math,datetime=datetime,defaultdict=defaultdict)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(HERE/'s6c_paced_analysis_v1.py'),'exec'),ns);return ns

H=pure_helpers();number=H['number'];stats=H['stats'];utc_seconds=H['utc_seconds']

def sources():return [B.binding(p,p.read_bytes()) for p in (Path(__file__),HERE/'README_S6C_LONG_DIAGNOSTICS_V1.md',*(HERE/n for n in PINS))]
def read_bound(reader,b):return reader.read(b['path'],b)
def unique(artifacts,name):
    found=[b for b in artifacts if Path(b['path']).name==name];require(len(found)==1,'One exact native artifact required: '+name);return found[0]

def source_frame(value):
    value=number(value);frame=round(value*16000)
    require(value>=0 and abs(value*16000-frame)<=1e-5,'Native source time is not an integer16k sample boundary')
    return frame

def final_native_checks(final,summary,native,plan,composition):
    require(final['schema_version']=='edge-session-finalization.v3' and final['state']=='COMPLETED' and final['finalization_error'] is None and final['live_lanes_at_finalization']==[] and final['resident_bundle_lease_retained'] is False and final['event_and_transcript_handles_closed'] is True,'Strict native finalization required')
    require(final['source_samples']==final['identity_samples']==composition['duration_samples'],'Native finalizer paired sample totals differ')
    require(summary['state']=='COMPLETED' and summary['research']['profile']==plan['profile_row']['profile'],'Native summary state/profile differs')
    telemetry=native['final_telemetry'];require(telemetry['source_duration_sec']==composition['duration_sec'] and telemetry['asr_cursor_sec']==composition['duration_sec'],'Native full source/ASR cursor differs')
    for k in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):require(telemetry[k]==0,'Native drop/overflow counter is nonzero')
    scheduler=telemetry['scheduler'];require(scheduler['closed'] is True and scheduler['pending_events']==0,'Closed, drained native scheduler required')

def stream_jsonl(binding,consume):
    """Hash precisely the consumed binary bytes, retaining no full source buffer."""
    require(type(binding['bytes']) is int and 0<=binding['bytes']<=MAX_FILE,'Bounded native observation file required')
    h=hashlib.sha256();size=0;lines=0;records=0
    with Path(binding['path']).open('rb') as f:
        while True:
            raw=f.readline(MAX_LINE+1)
            if not raw:break
            require(len(raw)<=MAX_LINE,'Native observation line exceeds admitted bound');h.update(raw);size+=len(raw);lines+=1
            require(size<=binding['bytes'],'Native observation grew beyond binding')
            text=raw.decode('utf-8-sig')
            if text.strip():
                value=json.loads(text,parse_constant=lambda token:(_ for _ in ()).throw(ValueError('Nonfinite JSON token '+token)))
                require(isinstance(value,dict),'Object observation required');consume(value,records);records+=1;require(records<=MAX_ROWS,'Native observation row bound exceeded')
    require(size==binding['bytes'] and h.hexdigest()==binding['sha256'],'Exact consumed native bytes differ')
    return dict(binding=binding,bytes_consumed=size,physical_lines=lines,records=records,full_buffer_retained=False)

def admit_closed(reader,admission_binding,state=None):
    _,ab=read_bound(reader,admission_binding);record=V.validate_outer(reader,Path(ab['path']))
    require(record['admission']==ab and record['wrapper_status']=='NATIVE_COMPLETE_QUIET_LEASE_RELEASED','Actual successful closed continuous wrapper required')
    state=state or V.process_state;require(state(record['owner']['pid'],record['owner']['creation_time'])['alive'] is False,'Continuous owner still live or unavailable')
    plan=record['plan'];require(plan['composition']['sha256']=='bfa18ae06bb224faaad2d4f5096f2e6a0d1aebff5c7c16192d608739d3533bf3','Exact fixed38-piece composition required')
    native,nb=read_bound(reader,record['original_native_result']);spec,_=read_bound(reader,record['actual_execution_manifest']);composition,_=read_bound(reader,record['source_composition'])
    require(composition['source_count']==38 and composition['duration_sec']==1827.426625 and composition['duration_samples']==29238826,'Fixed whole continuous source differs')
    require(native['resident_bundle_loads']==1 and native['resident_sessions_created']==1 and native['live_owned_lanes']==[] and native['hardware_invocations']==0,'Native bundle/session/lane scope differs')
    artifacts=native['native_artifacts'];require(len({B.canonical(b['path']) for b in artifacts})==len(artifacts),'Duplicate native artifact path')
    for name,tap in (('audio_spool.pcm16',plan['profile_row']['asr_tap']),('identity_audio_spool.pcm16',plan['profile_row']['identity_tap'])):
        b=native['native_journals'][name];require(b==unique(artifacts,name) and b['bytes']==2*composition['duration_samples'] and b['sha256']==composition['pcm_sha256'][tap],'Declared native paired source journals differ')
    final,fb=read_bound(reader,unique(artifacts,'session_finalization_v3.json'))
    session=Path(fb['path']).parent
    require(all(Path(b['path']).parent==session for b in artifacts) and B.canonical(session)==B.canonical(native['final_telemetry']['session_dir']),'Native artifacts do not belong to one declared session')
    require(Path(native['process_samples']['path'])==Path(nb['path']).parent/'PROCESS_SAMPLES.jsonl','Native process trajectory path differs')
    summary,sb=read_bound(reader,unique(artifacts,'session_summary.json'))
    final_native_checks(final,summary,native,plan,composition)
    return dict(record=record,plan=plan,native=native,native_binding=nb,spec=spec,composition=composition,finalization=final,finalization_binding=fb,summary=summary,summary_binding=sb,
        events=unique(artifacts,'events.jsonl'),process_samples=native['process_samples'],scope='Exact JSON chain and declared paired PCM bindings. This helper does not reopen PCM/model assets; original native worker verified those bytes at execution.')

class Events:
    def __init__(self,duration,evidence_policy):
        self.duration=number(duration);self.duration_frames=source_frame(duration);self.evidence_policy=evidence_policy;self.counts=Counter();self.origin=None;self.prev=None;self.reversals=[];self.reversal_count=0;self.retained=[];self.admissions=[];self.gates=Counter();self.debts=Counter();self.hops=Counter();self.lifecycle=Counter();self.track_counts=defaultdict(list);self.lifecycle_missing=0;self.reasons=Counter();self.states=Counter();self.ids=set();self.costs=defaultdict(list);self.asr_samples=0;self.asr_end_frame=0;self.dispatches=0;self.tails=0;self.drain=None;self.endpoint=Counter();self.watermarks=Counter();self.watermark_closed=set();self.debt_deficits=defaultdict(list);self.debt_rows=[];self.projection_bytes=0
    def budget(self,value):
        self.projection_bytes+=len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8'))
        require(self.projection_bytes<=MAX_PROJECTION_BYTES,'Native retained projection byte budget exceeded')
    def consume(self,e,index):
        kind=e['event_type'];p=e['payload'];stamp=utc_seconds(e['wall_time_utc']);self.counts[kind]+=1
        if self.prev is not None and stamp<self.prev:
            self.reversal_count+=1
            if len(self.reversals)<100:self.reversals.append(dict(event_index=index,previous_utc=self.prev,utc=stamp))
        self.prev=stamp
        if kind=='source_started':require(self.origin is None,'Duplicate native source start');self.origin=stamp
        if kind in ('research_asr_dispatch','research_asr_tail_dispatch'):
            start=source_frame(p['source_start_sec']);end=source_frame(p['source_end_sec']);require(start==self.asr_end_frame and end>start and end<=self.duration_frames,'Native ASR dispatch source gap/duplicate')
            count=end-start
            if kind=='research_asr_tail_dispatch':
                require(type(p['samples']) is int and p['samples']==count,'Actual native ASR tail sample/span mismatch');self.tails+=1
            else:
                flags=[p[k] for k in ('native_endpoint','advisory_endpoint','reset_requested')]
                require(all(type(v) is bool for v in flags) and flags[2]==(flags[0] or flags[1]),'Native reset OR flags differ')
                for key in ('native_endpoint','advisory_endpoint','reset_requested'):self.endpoint[key]+=p[key]
                self.endpoint['coincident_native_and_advisory']+=flags[0] and flags[1]
            self.asr_samples+=count;self.asr_end_frame=end;self.dispatches+=1
        if kind=='research_asr_drain':
            require(self.drain is None and source_frame(p['source_end_sec'])==self.duration_frames and p['padding_is_observed_audio'] is False and number(p['synthetic_right_padding_sec'])==.66,'One exact native synthetic drain required')
            self.drain=deepcopy(p)
        if kind=='research_embedding_admission':
            fields=('source_end_sec','evidence_kind','reason','tracking_context_age_sec','tracking_context_empty','cue_event')
            self.admissions.append(dict(event_type=kind,payload={k:p[k] for k in fields}));require(len(self.admissions)<=MAX_RETAINED,'Bounded native admission projections exceeded')
            self.gates[p['evidence_kind'],p['reason']]+=1;self.hops[p['evidence_kind'],number(p['selected_hop_sec'])]+=1
            require(type(p['admitted']) is bool and p['admitted']==(p['reason']=='admitted'),'Native gate admitted/reason inconsistency')
            require(p['naming_used_for_schedule'] is False,'Name-dependent schedule outside current native scope')
            for debt in p['track_debts']:
                require(type(debt['due']) is bool,'Actual due-ledger boolean required');self.debts[p['evidence_kind'],'due' if debt['due'] else 'not_due']+=1
                self.debts[p['evidence_kind'],'entries_on_admitted_observation' if p['admitted'] else 'entries_on_rejected_observation']+=1
                for key in ('unique_sec_deficit','disjoint_count_deficit'):self.debt_deficits[key].append(number(debt[key]))
            self.debt_rows.append(dict(source_end_sec=p['source_end_sec'],evidence_kind=p['evidence_kind'],admitted=p['admitted'],reason=p['reason'],track_debts=deepcopy(p['track_debts']),tracking_snapshot_available_at_sec=p['tracking_snapshot_available_at_sec'],tracking_context_age_sec=p['tracking_context_age_sec'],tracking_context_empty=p['tracking_context_empty'],tracking_context_used=p['tracking_context_used'],selected_hop_sec=p['selected_hop_sec']))
            self.budget(self.debt_rows[-1])
        if kind=='research_scheduler_watermark':
            require(p['lane'] in ('speaker','asr') and type(p['lane_closed']) is bool,'Native watermark lane/closure differs')
            require(p['lane'] not in self.watermark_closed,'Native watermark after lane closure')
            self.watermarks[p['lane']]+=1
            if p['lane_closed']:self.watermark_closed.add(p['lane'])
        if kind=='speaker_decision':
            d=p['decision'];self.states[d.get('state','UNOBSERVED')]+=1;self.reasons[d.get('reason','UNOBSERVED')]+=1
            if d.get('tracker_id') is not None:self.ids.add(d['tracker_id'])
            if 'lifecycle_counts' not in d:self.lifecycle_missing+=1
            for k,v in d.get('lifecycle_counts',{}).items():self.track_counts[k].append(number(v))
            for event in d['lineage']:self.lifecycle[event['event']]+=1
            retained={k:deepcopy(d.get(k)) for k in ('decision_id','evidence_id','source_start_sec','source_end_sec','available_at_sec','tracker_id','anonymous_label','display_label','state','known_name','identity','lineage','lifecycle_counts','reason')}
            self.keep(e,index,dict(decision=retained),projection=True)
        elif kind.startswith('transcript_') or kind in ('identity_decision','research_asr_observation'):
            self.keep(e,index,deepcopy(p),projection=False)
        for field in ('compute_ms','model_api_elapsed_ms','full_dispatch_elapsed_ms','segment_model_api_ms','embedding_model_api_ms','gate_compute_ms','scheduler_dispatch_ms','policy_compute_sec','tracker_compute_sec','identity_compute_sec'):
            if p.get(field) is not None:self.costs[kind,field].append(number(p[field]))
    def keep(self,e,index,p,projection):
        require(len(self.retained)<MAX_RETAINED,'Bounded retained transcript/decision observations exceeded')
        source=number(e['source_time_sec']);require(0<=source<=self.duration+1e-6,'Native emitted source cursor outside whole input')
        self.retained.append(dict(event_index=index,event_type=e['event_type'],emitted_wall_time_utc=e['wall_time_utc'],source_time_sec=source,payload=p,payload_projection=projection));self.budget(self.retained[-1])
    def finish(self):
        require(self.origin is not None and self.counts['source_started']==1 and self.counts['session_completed']==1 and not self.counts['failure'],'Native event start/completion/failure mismatch')
        require(self.asr_end_frame==self.duration_frames and self.asr_samples==self.duration_frames and self.tails<=1 and self.drain is not None,'Native event full ASR source/tail/drain coverage differs')
        require(self.watermark_closed=={'speaker','asr'},'Both native scheduler input lanes must close')
        for r in self.retained:
            elapsed=utc_seconds(r['emitted_wall_time_utc'])-self.origin;r.update(emitted_from_source_started_sec=elapsed,emission_minus_source_cursor_sec=elapsed-r['source_time_sec'])
        return dict(event_counts=dict(self.counts),asr_dispatch=dict(blocks=self.dispatches,tail_blocks=self.tails,source_end_sec=self.asr_end_frame/16000,source_frames_from_dispatch_spans=self.asr_samples,final_drain=self.drain,sample_scope='Ordinary block frame counts derive from exact integer16k source endpoints. Tail count is additionally checked against the actual samples field. Synthetic drain padding is excluded.'),endpoint_flags=dict(self.endpoint),scheduler_watermark_counts=dict(self.watermarks),
            speech_context=H['active_context_observations'](self.admissions,self.evidence_policy),admission_gate_counts=[dict(role=k[0],reason=k[1],count=v) for k,v in sorted(self.gates.items())],selected_hops=[dict(role=k[0],hop_sec=k[1],count=v) for k,v in sorted(self.hops.items())],
            debt_ledger_counts=[dict(role=k[0],kind=k[1],count=v) for k,v in sorted(self.debts.items())],debt_deficits={k:stats(v) for k,v in self.debt_deficits.items()},decision_states=dict(self.states),decision_reasons=dict(self.reasons),distinct_observed_track_ids=len(self.ids),observed_lifecycle_event_counts=dict(self.lifecycle),lifecycle_count_observations_present=self.counts['speaker_decision']-self.lifecycle_missing,lifecycle_count_observations_missing=self.lifecycle_missing,observed_decision_track_counts={k:stats(v) for k,v in self.track_counts.items()},
            cost_observations=[dict(event_type=k[0],field=k[1],**stats(v),sum=sum(v)) for k,v in sorted(self.costs.items())],retained_observations=len(self.retained),wall_timestamp_reversal_count=self.reversal_count,first100_wall_reversals=self.reversals,
            scope='Actual native emission order with possibly interleaved source cursors, native gate/role and due-ledger observations. Due entries are acknowledgments at global admitted-window end, not proof that a debtor\'s own voice was delivered. Lifecycle counters are observed after decisions, not a separately sampled hidden tracker state. Inclusive/nested cost fields are separate and must not be added together.')

def trajectory(samples):
    result=H['trajectory_observations'](samples);members=[];complete=0;threads=[]
    require(sum(r.get('phase')=='terminal_after_finalization' for r in samples)==1 and all(r.get('phase')=='periodic' for r in samples[:-1]),'One terminal sample after periodic rows required')
    for row in samples:
        p=row.get('process',{});ok=p.get('complete_process_tree') is True;complete+=ok
        members.append(tuple(sorted((x['pid'],x['creation_time']) for x in p.get('processes',[]))))
        threads.append(sum(x['threads'] for x in p.get('processes',[])) if ok and p.get('processes') and all(type(x.get('threads')) is int for x in p['processes']) else None)
    result.update(periodic_samples=len(samples)-1,terminal_samples=1,complete_tree_samples=complete,incomplete_or_unavailable_tree_samples=len(samples)-complete,observed_membership_changes=sum(a!=b for a,b in zip(members,members[1:])),threads=stats(threads),pss_and_unique_shared_resident='UNAVAILABLE_IN_ORIGINAL_NATIVE_SAMPLER',
        log_growth=stats([r.get('native_event_log_bytes') for r in samples]),first_sample_elapsed_sec=samples[0]['elapsed_from_native_launch_sec'],
        native_event_log_first_to_last_bytes=(samples[-1]['native_event_log_bytes']-samples[0]['native_event_log_bytes']) if all(r.get('native_event_log_bytes') is not None for r in (samples[0],samples[-1])) else None)
    return result

def write_projection(path,rows):
    with path.open('xb') as f:
        with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as z:
            for row in rows:z.write((json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))
    return B.binding(path,path.read_bytes())

def run_one(chain,output):
    native=chain['native'];profile=chain['plan']['profile_row'];events=Events(native['source_duration_sec'],profile['profile']['embedding']['evidence_policy']);event_read=stream_jsonl(chain['events'],events.consume);facts=events.finish()
    require(facts['event_counts']==native['event_counts'],'Stored native event counts differ from consumed actual log')
    samples=[];sample_read=stream_jsonl(chain['process_samples'],lambda row,index:samples.append(row));require(len(samples)==native['process_sample_count'],'Native process sample count differs')
    observations=trajectory(samples);require(samples[-1]['event_counts']==native['event_counts'] and samples[-1]['state']=='COMPLETED' and samples[-1]['event_queue_backlog']==0 and samples[-1]['native_event_log_bytes']==chain['events']['bytes'],'Terminal joined event/queue/log state differs')
    for field in ('source_duration_sec','asr_cursor_sec','speaker_cursor_sec','audio_frames_dropped','scheduler'):
        require(samples[-1]['telemetry'][field]==native['final_telemetry'][field],'Terminal native telemetry differs: '+field)
    telemetry=native['final_telemetry'];scheduler=telemetry['scheduler'];limits=profile['profile']['scheduler']
    require(scheduler['pending_events']==0 and scheduler['closed'] is True,'Native scheduler not drained')
    require(scheduler['total_input_events']<=limits['max_events'] and scheduler['max_pending_events']<=limits['max_pending_events'] and len(scheduler['utterances'])<=limits['max_utterances'],'Native scheduler bounds exceeded')
    for state in ('live','archive'):
        row=facts['observed_decision_track_counts'].get(state)
        if row:require(row['max']<=profile['profile']['tracker']['max_tracks' if state=='live' else 'archive_capacity'],'Observed tracker count exceeds configured bound')
    output.mkdir(parents=True,exist_ok=False)
    tb=write_projection(output/'NATIVE_TEXT_NAME_REVISION_OBSERVATIONS.jsonl.gz',events.retained)
    db=write_projection(output/'NATIVE_ADMISSION_DEBT_CONTEXT_OBSERVATIONS.jsonl.gz',events.debt_rows)
    result=dict(schema=SCHEMA,status='COMPLETE_DIRECT_OBSERVATIONS',profile=profile,actual_execution_epoch='epoch4',source_composition_epoch='epoch2',source_composition=chain['record']['source_composition'],native_result=chain['native_binding'],source_duration_sec=native['source_duration_sec'],source_duration_samples=chain['composition']['duration_samples'],source_pieces=38,inserted_between_piece_silence_sec=74.,
        facts=facts,trajectory=observations,final_telemetry=telemetry,finalization=chain['finalization_binding'],native_summary=chain['summary_binding'],native_text_name_revision_observations=tb,native_admission_debt_context_observations=db,observed_reads=[event_read,sample_read],
        model_startup_sec=native['model_load_sec'],native_elapsed_sec=native['native_elapsed_sec'],total_worker_elapsed_sec=native['total_observed_worker_sec'],resident_bundle_loads=native['resident_bundle_loads'],resident_sessions_created=native['resident_sessions_created'],
        limitations=['One continuous host session over38 previously reset physical captures; cue pieces keep those reset histories.','Native process samples begin after model startup; missing fields and gaps are not interpolated. Sampled maxima do not prove continuous maxima or memory leak absence.','The scheduler final max_pending_events is its internal high-water count; process event_queue_backlog is a different, sampled consumer queue.','Decision-time track counts and rejection-event incidence are observed. Continuous capacity-blocked seconds are unavailable; no interval is filled from sparse decisions.','Actual emitted labels/names are retained without human identity or lexical scoring. No composite-reference WER, correctness/exposure metric, biological identity or all-scenes accuracy claim is created.','UTC emission-minus-source-cursor may be negative under source block-before-sleep publication; it is not GUI/phonetic/physical XVF/CM5 latency.','No model, policy replay, PCM or gallery-private-state query ran in this diagnostic.'])
    return B.write_new(output/'RESULT.json',result)

def output_root(namespace):
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,60}',namespace or ''),'Fresh simple diagnostic namespace required');return REPORT/'long_diagnostics'/namespace

def require_quiet(path=None):
    require(not (Path(path) if path is not None else REPORT/'PACED_QUIET_OWNER.json').exists(),'Shared paced/long lease exists; defer diagnostic observation reads')

def prepare(args):
    require_quiet()
    root=output_root(args.namespace);require(not root.exists(),'Fresh diagnostic namespace required');root.mkdir(parents=True);reader=B.MetadataReader(root);bindings=[];keys=set()
    for path,sha in args.admission:
        raw=Path(path).read_bytes();b=B.binding(path,raw);require(b['sha256']==sha,'Explicit closed admission SHA differs');chain=admit_closed(reader,b);key=chain['native_binding']['path'];require(key not in keys,'Duplicate native session');keys.add(key);bindings.append(b)
    require(bindings,'At least one exact closed continuous admission required')
    return B.write_new(root/'PLAN.json',dict(schema=SCHEMA,status='PREPARED_CLOSED_INPUTS_NO_LOG_SCAN',sources=sources(),admissions=bindings,metadata_sources=reader.sources,output_root=str(root),max_file_bytes=MAX_FILE,max_line_bytes=MAX_LINE,max_retained_records=MAX_RETAINED,max_projection_bytes=MAX_PROJECTION_BYTES))

def run(args):
    require_quiet()
    raw=Path(args.plan[0]).read_bytes();pb=B.binding(args.plan[0],raw);require(pb['sha256']==args.plan[1],'Exact diagnostic plan SHA differs');plan=json.loads(raw);root=Path(plan['output_root'])
    require(root==output_root(root.name) and Path(pb['path'])==root/'PLAN.json' and plan['schema']==SCHEMA and plan['sources']==sources(),'Exact diagnostic plan/source namespace differs')
    require(not (root/'ANALYSIS_RECEIPT.json').exists(),'Preserve completed diagnostic');metadata=root/'execution_metadata';metadata.mkdir(exist_ok=False);reader=B.MetadataReader(metadata);outputs=[]
    for i,b in enumerate(plan['admissions']):
        require_quiet()
        chain=admit_closed(reader,b);outputs.append(run_one(chain,root/f'session_{i+1:02d}'))
        require_quiet()
    require(plan['sources']==sources(),'Diagnostic source changed during reads')
    return B.write_new(root/'ANALYSIS_RECEIPT.json',dict(schema=SCHEMA,status='COMPLETE_DIRECT_OBSERVATIONS',plan=pb,sources=sources(),results=outputs,metadata_sources=reader.sources,sessions=len(outputs),model_calls=0,policy_replays=0,pcm_reads=0,scope='Exact admitted closed continuous sessions only; no canonical-scene/scorer/name mapping API used.'))

def checks():
    passed=[]
    def ok(name,value):require(value,name);passed.append(name)
    def rejects(name,fn):
        try:fn()
        except (KeyError,ValueError):passed.append(name)
        else:raise AssertionError('Invalid fixture admitted: '+name)
    def event(kind,p=None,source=.325,stamp='2026-09-10T00:00:00.050000+00:00'):
        return dict(event_type=kind,wall_time_utc=stamp,source_time_sec=source,payload=p or {})
    def dispatch(start,end,tail=False):
        p=dict(source_start_sec=start,source_end_sec=end,compute_ms=1.)
        if tail:p['samples']=round((end-start)*16000)
        else:p.update(native_endpoint=False,advisory_endpoint=False,reset_requested=False)
        return event('research_asr_tail_dispatch' if tail else 'research_asr_dispatch',p,end)
    def feed(rows,duration=.325,policy='mature_only'):
        e=Events(duration,policy)
        for i,r in enumerate(rows):e.consume(r,i)
        return e,e.finish()
    rows=[event('source_started',source=0,stamp='2026-09-10T00:00:00+00:00'),dispatch(0,.1),dispatch(.2-.1,.2),dispatch(.3-.1,.3),dispatch(.3,.325,True),
        event('research_asr_drain',dict(source_end_sec=.325,synthetic_right_padding_sec=.66,padding_is_observed_audio=False,compute_ms=2.)),
        event('transcript_partial',dict(text='hello',speaker='Unknown')),
        event('research_scheduler_watermark',dict(lane='speaker',lane_closed=True)),event('research_scheduler_watermark',dict(lane='asr',lane_closed=True)),event('session_completed')]
    e,facts=feed(rows);ok('ordinary inferred frames + explicit tail + synthetic drain',facts['asr_dispatch']['source_frames_from_dispatch_spans']==5200 and facts['asr_dispatch']['tail_blocks']==1)
    ok('signed native clock remains negative',e.retained[0]['emission_minus_source_cursor_sec']<0)
    for index,field,value in [(1,'source_start_sec',.01),(4,'samples',399),(4,'samples',True),(5,'padding_is_observed_audio',True),(5,'source_end_sec',.3),(1,'reset_requested',True)]:
        bad=deepcopy(rows);bad[index]['payload'][field]=value;rejects('reject '+str(index)+' '+field+' '+str(value),lambda:feed(bad))
    rejects('missing native drain',lambda:feed([r for r in rows if r['event_type']!='research_asr_drain']))
    rejects('missing source lane close',lambda:feed(rows[:-2]+rows[-1:]))
    rejects('dispatch duplicate',lambda:feed(rows[:2]+[rows[1]]+rows[2:]))
    rejects('noninteger16k span',lambda:source_frame(.1000001))
    rejects('boolean numeric clock',lambda:source_frame(True))
    def admission(role,reason='admitted'):
        return event('research_embedding_admission',dict(source_end_sec=.25,evidence_kind=role,reason=reason,admitted=reason=='admitted',selected_hop_sec=.25,naming_used_for_schedule=False,tracking_context_age_sec=None,tracking_context_empty=True,cue_event=False,tracking_snapshot_available_at_sec=None,tracking_context_used=True,track_debts=[dict(track_id=None,unique_sec_deficit=1.,disjoint_count_deficit=2,due=True)]),.25)
    decision=event('speaker_decision',dict(decision=dict(reason='audio_gate_reject',state='unknown',tracker_id=None,lineage=[dict(event='track_retire',track_id=1),dict(event='audio_gate_reject')])) )
    dual=rows[:-1]+[admission('short'),admission('mature'),decision]+rows[-1:]
    e,facts=feed(dual,policy='dual');ok('dual role dedup and due ledger',facts['speech_context']['shared_dispatches']==1 and sum(r['count'] for r in facts['debt_ledger_counts'] if r['kind']=='due')==2)
    ok('missing reject lifecycle stays unavailable',facts['lifecycle_count_observations_missing']==1 and facts['observed_decision_track_counts']=={} and facts['observed_lifecycle_event_counts']['track_retire']==1 and e.retained[-1]['payload']['decision']['lineage'][0]['event']=='track_retire')
    rejects('missing dual role',lambda:feed(rows[:-1]+[admission('short')]+rows[-1:],policy='dual'))
    bad=deepcopy(dual);bad[-3]['payload']['tracking_context_age_sec']=.1;rejects('inconsistent shared role context',lambda:feed(bad,policy='dual'))
    good=deepcopy(decision);good['payload']['decision']['lifecycle_counts']=dict(live=3,archive=2)
    _,facts=feed(rows[:-1]+[good]+rows[-1:]);ok('actual decision count observations',facts['observed_decision_track_counts']['live']['max']==3 and facts['lifecycle_count_observations_missing']==0)
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'stream.jsonl';p.write_bytes(b'{"a":1}\n{"a":2}\n');b=B.binding(p,p.read_bytes());seen=[];read=stream_jsonl(b,lambda r,i:seen.append(r));ok('exact stream bytes/rows',read['records']==2 and seen==[dict(a=1),dict(a=2)])
        p.write_bytes(b'{"a":1}\n{"a":3}\n')
        rejects('same size changed stream',lambda:stream_jsonl(b,lambda *a:None))
        for raw in (b'{"a":NaN}\n',b'[]\n',b'{"a":1}\nmalformed'):
            p.write_bytes(raw);b=B.binding(p,raw);rejects('invalid stream '+repr(raw),lambda:stream_jsonl(b,lambda *a:None))
        z=write_projection(Path(d)/'projection.gz',[dict(text='hello',name=None)]);ok('exact projected payload roundtrip',json.loads(gzip.decompress(Path(z['path']).read_bytes()))==dict(text='hello',name=None))
        lock=Path(d)/'PACED_QUIET_OWNER.json';require_quiet(lock);lock.write_text('{}');rejects('shared quiet lease refusal',lambda:require_quiet(lock))
        md=Path(d)/'metadata';md.mkdir();reader=B.MetadataReader(md);p.write_text('{}');value,b=reader.read(p);ok('metadata reader parent admission',value=={} and len(reader.sources)==1)
    samples=[dict(phase='periodic',elapsed_from_native_launch_sec=0,process={},telemetry={},event_queue_backlog=None),dict(phase='terminal_after_finalization',elapsed_from_native_launch_sec=3,process={},telemetry={},event_queue_backlog=0)]
    obs=trajectory(samples);ok('missingness + sample gap + phase denominators',obs['samples']==2 and obs['max_sample_gap_sec']==3 and obs['process']['private_resident_uss_bytes']['missing']==2 and obs['event_queue_backlog']['missing']==1 and obs['terminal_samples']==1 and obs['incomplete_or_unavailable_tree_samples']==2)
    for altered in ([samples[0]],[samples[1],samples[0]]):
        rejects('missing/invalid terminal '+str(len(altered)),lambda:trajectory(altered))
    profile=dict(profile_id='SYNTHETIC');plan=dict(profile_row=dict(profile=profile));composition=dict(duration_sec=.325,duration_samples=5200)
    final=dict(schema_version='edge-session-finalization.v3',state='COMPLETED',finalization_error=None,live_lanes_at_finalization=[],resident_bundle_lease_retained=False,event_and_transcript_handles_closed=True,source_samples=5200,identity_samples=5200)
    summary=dict(state='COMPLETED',research=dict(profile=profile));native=dict(final_telemetry=dict(source_duration_sec=.325,asr_cursor_sec=.325,audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0,scheduler=dict(closed=True,pending_events=0)))
    final_native_checks(final,summary,native,plan,composition);ok('supplemental final closure positive',True)
    for field,value in [('finalization_error','failed'),('identity_samples',5199),('event_and_transcript_handles_closed',False),('live_lanes_at_finalization',['worker']),('resident_bundle_lease_retained',True)]:
        bad=dict(final);bad[field]=value;rejects('finalizer '+field,lambda:final_native_checks(bad,summary,native,plan,composition))
    for field,value in [('asr_cursor_sec',.3),('audio_frames_dropped',1),('scheduler',dict(closed=True,pending_events=1))]:
        bad=deepcopy(native);bad['final_telemetry'][field]=value;rejects('terminal '+field,lambda:final_native_checks(final,summary,bad,plan,composition))
    rejects('path traversal output',lambda:output_root('../escape'))
    return dict(check_count=len(passed),checks=passed,status='PASS_MODEL_FREE',sources=sources(),scope='Tiny source-only stream/clock/dispatch/trajectory/finalizer guards. Existing inventory V3 owns the original complete long authority chain. No actual native admission/logs/PCM/models read.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=('checks','prepare','run'));p.add_argument('--output',type=Path);p.add_argument('--namespace');p.add_argument('--admission',nargs=2,action='append',metavar=('PATH','SHA256'));p.add_argument('--plan',nargs=2,metavar=('PATH','SHA256'));a=p.parse_args()
    if a.action=='checks':require(a.output is not None,'Fresh check receipt path required');result=B.write_new(a.output,checks())
    elif a.action=='prepare':require(a.admission,'Exact closed admission arguments required');result=prepare(a)
    else:require(a.plan,'Exact plan argument required');result=run(a)
    print(json.dumps(result))
