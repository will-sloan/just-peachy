"""Bounded native cadence incidence audit; README_S6C_NATIVE_CADENCE_AUDIT.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import hashlib
import io
import json
import math
from pathlib import Path
import time

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
PAYLOAD=Path('G:/Just_Peachy_S6C/20260910T123540Z')
EPOCH_SHA='1f7f0e10186eb1187d05d9be258372d6dfbe39ec3741c2ce2976a2ca3d005cdb'
SOURCES={'C065':'n01_panel_core_v2','C071':'n07_off_panel_core_v2','C082':'n07_real_panel_core_v3'}
SCHEMA='jp_s6c_native_cadence_audit.v1'
def fail(message):raise ValueError(message)
def dumps(x):return json.dumps(x,sort_keys=True,allow_nan=False,separators=(',',':'))
def bind(path):
    path=Path(path);raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(binding):
    path=Path(binding['path']);raw=path.read_bytes()
    if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:fail('Changed exact input bytes: '+str(path))
    return json.loads(raw,parse_constant=lambda x:fail('Nonfinite JSON '+x))
def write(path,value):
    path=Path(path)
    with path.open('x',encoding='utf-8') as f:f.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
def number(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):fail('Finite numeric observation required')
    return float(x)
def within(path,root):
    p=Path(path).resolve()
    if not p.is_relative_to(root.resolve()):fail('Outside admitted root: '+str(p))
    return p
def metadata(binding):return dict(path=binding['path'],bytes=binding['bytes'],sha256=binding['sha256'])
def prepare():
    out=REPORT/'cadence_audit_v1'
    if out.exists():fail('Preserve existing audit namespace')
    sources=[];grids=[]
    for cid,folder in SOURCES.items():
        cb=bind(REPORT/folder/'ANALYSIS_RECEIPT.json');core=read(cb)
        if core['status']!='COMPLETE_REQUESTED_INDEX' or core['requested']!=112 or core['scored']!=112 or core['unscored']:fail('Completed112 core required')
        index=read(core['index'])
        if index['status']!='COMPLETE' or index['requested']!=112 or index['completed']!=112 or len(index['source_indices'])!=1:fail('Complete unique native source index required')
        native_binding=index['source_indices'][0];native=read(native_binding)
        if native['status']!='COMPLETE' or native['requested']!=112 or native['completed']!=112:fail('Native112 completion required')
        epoch_binding=index['execution_manifest']
        if epoch_binding['sha256']!=EPOCH_SHA or native['execution_manifest']!=epoch_binding:fail('Exact epoch2 required')
        epoch=read(epoch_binding);rows=native['rows'];keys={(z['case_id'],z['asr_tap'],z['identity_tap']) for z in rows}
        if len(rows)!=112 or len(keys)!=112 or any(z['candidate_id']!=cid or z['status'] not in {'COMPLETE','COMPLETE_REUSED'} or z['asr_tap']!=z['identity_tap'] for z in rows):fail('Native scope/duplicate/route failure')
        if set(z[1] for z in keys)!={'O0','O1'} or len({z[0] for z in keys})!=56:fail('Exact56 both-tap grid required')
        code_rows=[b for b in epoch['execution_files'] if Path(b['path']).name in {'research_evidence_v3.py','research_scheduler_v3.py'}]
        if len(code_rows)!=2:fail('Frozen cadence/scheduler code bindings required')
        for binding in code_rows:
            raw=Path(binding['path']).read_bytes()
            if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:fail('Frozen method source changed')
        grids.append(keys);sources.append(dict(candidate_id=cid,core=cb,prediction_index=core['index'],native_index=native_binding,epoch=epoch_binding,method_source=code_rows))
    if not all(x==grids[0] for x in grids):fail('Paired source grids differ')
    out.mkdir();plan=dict(schema=SCHEMA,status='PREPARED_NO_EVENT_SCAN',sources=sources,expected_native_cells=336,
        source=bind(__file__),readme=bind(Path(__file__).with_name('README_S6C_NATIVE_CADENCE_AUDIT.md')),
        scope='Exact completed native logs, streamed once; model/audio/vector payloads remain transitively bound and are not reopened. All comparisons exploratory.')
    write(out/'PLAN.json',plan);return bind(out/'PLAN.json')

class Accumulator:
    def __init__(self,profile,duration):
        self.profile=profile;self.duration=duration;self.events=Counter();self.reasons=Counter();self.roles=Counter();self.flags=Counter()
        self.numeric={};self.costs=defaultdict(Counter);self.opportunities={};self.admitted={};self.embedding=set()
        self.examples={};self.dispatch_spans=[];self.lane_ready={};self.event_fields=defaultdict(set)
    def stat(self,key,value):
        if value is None:
            d=self.numeric.setdefault(key,dict(observed=0,missing=0,sum=0.,min=None,max=None));d['missing']+=1;return
        v=number(value);d=self.numeric.setdefault(key,dict(observed=0,missing=0,sum=0.,min=None,max=None))
        d['observed']+=1;d['sum']+=v;d['min']=v if d['min'] is None else min(d['min'],v);d['max']=v if d['max'] is None else max(d['max'],v)
    def consume(self,event):
        kind=event['event_type'];p=event.get('payload',{});self.events[kind]+=1
        if not isinstance(p,dict):fail('Event payload not object')
        if kind in {'research_embedding_admission','research_speaker_dispatch_cost','research_scheduler_watermark'}:self.event_fields[kind].update(p)
        for field in ('compute_ms','model_api_elapsed_ms','full_dispatch_elapsed_ms','gate_compute_ms','scheduler_dispatch_ms','postprocess_compute_ms'):
            if field in p and p[field] is not None:self.costs[kind][field]+=number(p[field])/1000
        if kind=='research_embedding_admission':
            role=p['evidence_kind'];end=number(p['source_end_sec']);start=number(p['source_start_sec']);key=(end,role)
            if role not in {'short','mature'} or start<0 or end>self.duration+1e-7 or end<start or key in self.opportunities:fail('Invalid/duplicate role opportunity')
            if type(p['admitted']) is not bool or p['admitted']!=(p['reason']=='admitted'):fail('Admission reason/boolean mismatch')
            if p['naming_used_for_schedule'] is not False:fail('Unexpected name-fed schedule')
            debts=p['track_debts'];seen=set();due=0;real=0
            for debt in debts:
                tid=debt['track_id']
                if tid in seen:fail('Duplicate track debt in one opportunity')
                seen.add(tid)
                if type(debt['due']) is not bool or number(debt['unique_sec_deficit'])<0 or number(debt['disjoint_count_deficit'])<0:fail('Invalid debt metadata')
                due+=debt['due'];real+=tid is not None
            self.roles[role]+=1;self.reasons[role+'/'+p['reason']]+=1
            self.flags['role_opportunities_with_any_due']+=due>0
            self.flags['due_track_role_pairs']+=due
            self.flags['real_track_role_pairs']+=real
            self.flags['placeholder_track_role_pairs']+=len(debts)-real
            self.flags['due_entries_acknowledged_by_admitted_role']+=due if p['admitted'] else 0
            self.flags['cue_event_role_opportunities']+=bool(p['cue_event'])
            self.flags['cue_event_admitted_roles']+=bool(p['cue_event']) and p['admitted']
            self.flags['uncertainty_trigger_role_opportunities']+=bool(p['uncertainty_trigger'])
            self.flags['admitted_roles_with_due_and_cue']+=p['admitted'] and due>0 and bool(p['cue_event'])
            self.flags['admitted_roles_with_cue_without_due']+=p['admitted'] and due==0 and bool(p['cue_event'])
            self.flags['admitted_roles_with_no_due_no_cue']+=p['admitted'] and due==0 and not p['cue_event']
            base=self.profile['embedding']['short_hop_sec' if role=='short' else 'mature_hop_sec']
            sparse=max(base,self.profile['embedding']['sparse_hop_sec'])
            since=p.get('since_last_role_sec')
            if since is not None:
                number(since)
                self.flags['admitted_earlier_than_sparse_budget']+=p['admitted'] and since<sparse-1e-9
                self.flags['cue_marked_admitted_earlier_than_sparse']+=p['admitted'] and p['cue_event'] and since<sparse-1e-9
            stamp=p.get('tracking_snapshot_available_at_sec');age=p.get('tracking_context_age_sec')
            if stamp is not None and (number(stamp)>end+1e-7 or age is None or abs(number(age)-(end-stamp))>1e-7):fail('Future/inconsistent released tracking context')
            if stamp is None and age is not None:fail('Context age without stamp')
            self.stat('role_context_age_sec',age)
            for field in ('selected_hop_sec','clean_fraction','estimated_clean_sec','contiguous_clean_sec','selected_rms'):self.stat(field,p.get(field))
            shared={k:p.get(k) for k in ('cue_event','track_debts','tracking_snapshot_available_at_sec','tracking_context_age_sec','tracking_context_empty','tracking_context_used')}
            self.opportunities[key]=shared
            if p['admitted']:self.admitted[key]=(start,end)
            for label,condition in [('first_due_admitted',bool(due) and p['admitted']),('first_cue',bool(p['cue_event'])),('first_budget_skip',p['reason']=='cadence_budget'),('first_context_older_1sec',age is not None and age>1)]:
                if condition and label not in self.examples:self.examples[label]={k:v for k,v in p.items() if k not in {'clean_intervals','track_debts'}}|{'debt_entries':debts[:4],'debt_entries_total':len(debts)}
        elif kind=='research_embedding':
            key=(number(p['source_end_sec']),p['evidence_kind'])
            if key not in self.admitted or key in self.embedding or self.admitted[key]!=(p['source_start_sec'],p['source_end_sec']):fail('Actual embedding/admitted support mismatch')
            self.embedding.add(key)
        elif kind=='research_speaker_dispatch_cost':
            self.dispatch_spans.append((number(p['source_start_sec']),number(p['source_end_sec'])))
        elif kind=='research_scheduler_watermark':
            if p['lane_closed']:
                self.lane_ready[p['lane']]=number(p['modeled_lane_ready_sec'])
            else:
                self.stat('modeled_watermark_lag_'+p['lane'],number(p['modeled_lane_ready_sec'])-number(p['lower_bound_sec']))
    def finish(self,receipt,summary):
        if dict(self.events)!=receipt['actual_counts']:fail('Exact native event counts differ')
        if set(self.admitted)!=self.embedding:fail('Admitted role missing actual embedding')
        ends=sorted({key[0] for key in self.opportunities});expected=math.floor(self.duration*16000/round(self.profile['embedding']['hop_sec']*16000)+1e-8)
        if len(ends)!=expected or len(self.opportunities)!=expected*2:fail('Incomplete dual-role source opportunity grid')
        for end in ends:
            a=self.opportunities[end,'short'];b=self.opportunities[end,'mature']
            if a!=b:fail('Shared dispatch context differs between roles')
            self.flags['shared_dispatches_with_due']+=any(d['due'] for d in a['track_debts'])
            self.flags['shared_dispatches_with_cue_event']+=bool(a['cue_event'])
            self.flags['shared_dispatches_empty_context']+=bool(a['tracking_context_empty'])
            self.stat('dispatch_context_age_sec',a['tracking_context_age_sec'])
        spans=self.dispatch_spans
        if len(spans)!=expected or any(abs(a[1]-b[0])>1e-7 for a,b in zip(spans,spans[1:])) or spans and abs(spans[0][0])>1e-7:fail('Speaker source dispatch gap/duplicate')
        telemetry=summary['telemetry'];scheduler=telemetry['scheduler']
        if summary['state']!='COMPLETED' or scheduler['closed'] is not True or scheduler['pending_events']!=0:fail('Unclosed native scheduler')
        if self.profile['embedding']['cadence_policy']=='uncertainty':
            if telemetry['s6c_schedule_empty_context_dispatches']!=self.flags['shared_dispatches_empty_context']:fail('Empty-context summary mismatch')
            age=self.numeric['dispatch_context_age_sec']['max'] or 0.
            if abs(telemetry['s6c_schedule_max_observed_context_age_sec']-age)>1e-7:fail('Context age summary mismatch')
        for d in self.numeric.values():d['mean']=d['sum']/d['observed'] if d['observed'] else None
        return dict(event_counts=dict(self.events),role_opportunities=dict(self.roles),reasons=dict(self.reasons),flags=dict(self.flags),
            numeric=self.numeric,inclusive_costs_sec={k:dict(v) for k,v in self.costs.items()},source_dispatches=expected,
            actual_embedding_calls=len(self.embedding),examples=self.examples,logged_fields={k:sorted(v) for k,v in self.event_fields.items()},
            queue=dict(final_pending=scheduler['pending_events'],observed_max_pending=scheduler.get('max_pending_events'),
                configured_max_pending=scheduler['state_bounds']['max_pending_events'],asr_final_lag_sec=telemetry.get('asr_lag_sec'),
                speaker_final_lag_sec=telemetry.get('speaker_lag_sec'),peak_journal_lag_sec=None,
                scope='Actual scheduler maintained max pending count; not journal backlog or OS queue. Final lags are not peak lags.'),
            terminal=dict(analyzed_through_sec=telemetry['speaker_analyzed_through_sec'],unanalyzed_short_tail_sec=telemetry['speaker_unanalyzed_short_tail_sec'],
                modeled_closed_lane_ready=self.lane_ready),target_track_chosen_count=None,sole_cue_causal_admission_count=None)

def stream_exact(binding,acc):
    path=Path(binding['path']);h=hashlib.sha256();count=0
    with path.open('rb') as f:
        for raw in f:
            count+=len(raw);h.update(raw)
            if len(raw)>16*2**20:fail('Oversize event line')
            if not raw.strip():continue
            acc.consume(json.loads(raw,parse_constant=lambda x:fail('Nonfinite JSON '+x)))
    if count!=binding['bytes'] or h.hexdigest()!=binding['sha256']:fail('Changed exact streamed event bytes')
    return dict(binding=binding,streamed_bytes=count,sha256=h.hexdigest())
def streamed(binding,acc):
    within(binding['path'],PAYLOAD/'epoch2')
    return stream_exact(binding,acc)
def run(plan_binding):
    plan=read(plan_binding)
    if plan['source']!=bind(__file__) or plan['readme']!=bind(Path(__file__).with_name('README_S6C_NATIVE_CADENCE_AUDIT.md')):fail('Audit source changed after plan')
    out=Path(plan_binding['path']).parent
    if (out/'RESULT.json').exists():fail('Preserve completed audit')
    started=time.perf_counter();records=[];grids=[]
    for source in plan['sources']:
        core=read(source['core']);pred=read(source['prediction_index']);native=read(source['native_index']);epoch=read(source['epoch'])
        if core['index']!=source['prediction_index'] or source['native_index'] not in pred['source_indices'] or source['epoch']['sha256']!=EPOCH_SHA:fail('Source chain mismatch')
        grid=set()
        for row in native['rows']:
            rb=row['receipt'];within(rb['path'],PAYLOAD/'epoch2');rec=read(rb);ident=rec['identity']
            if rec['status']!='COMPLETE' or rec['job_key']!=row['job_key'] or rec['candidate_id']!=source['candidate_id'] or ident['execution_digest']!=epoch['execution_digest']:fail('Native receipt identity/status mismatch')
            for k in ('case_id','asr_tap','identity_tap','recipe_id'):
                if rec[k]!=row[k]:fail('Native row field mismatch '+k)
            key=(rec['case_id'],rec['asr_tap'],rec['identity_tap'])
            if key in grid or key[1]!=key[2]:fail('Duplicate or unexpected split route')
            grid.add(key);profile=ident['profile']
            if profile['input']['asr_tap']!=key[1] or profile['input']['identity_tap']!=key[2] or ident['gallery'] is not None or ident['gallery_condition']!='NONE':fail('Unexpected native route/gallery')
            expected=[z for z in epoch['profiles'] if z['candidate_id']==source['candidate_id'] and z['asr_tap']==key[1] and z['identity_tap']==key[2]]
            if len(expected)!=1 or expected[0]['profile']!=profile or expected[0]['cue_condition']!=ident['cue_condition']:fail('Frozen native profile/cue mismatch')
            acc=Accumulator(profile,rec['audio_duration_sec']);event_binding=streamed(rec['events'],acc);summary=read(rec['summary']);data=acc.finish(rec,summary)
            records.append(dict(candidate_id=rec['candidate_id'],case_id=rec['case_id'],tap=key[1],receipt=rb,events=event_binding,summary=rec['summary'],
                duration_sec=rec['audio_duration_sec'],native_elapsed_sec=rec['native_elapsed_sec'],worker_elapsed_sec=rec['elapsed_sec'],process_cpu_sec=rec.get('process_cpu_sec'),
                profile=profile['embedding'],tracker_cues=profile['tracker']['cues_enabled'],data=data))
            if len(records)%28==0:print(json.dumps(dict(phase='NATIVE_CADENCE_AUDIT',read=len(records),requested=336,elapsed_sec=time.perf_counter()-started)),flush=True)
        if len(grid)!=112:fail('Expected112 native cells')
        grids.append(grid)
    if len(records)!=336 or not all(g==grids[0] for g in grids):fail('Paired source grid incomplete')
    compact=[]
    for cid in SOURCES:
        for tap in ['O0','O1']:
            cells=[z for z in records if z['candidate_id']==cid and z['tap']==tap]
            flags=Counter();reasons=Counter();events=Counter();costs=defaultdict(Counter);numeric=defaultdict(list)
            for z in cells:
                a=z['data'];flags.update(a['flags']);reasons.update(a['reasons']);events.update(a['event_counts'])
                for kind,values in a['inclusive_costs_sec'].items():costs[kind].update(values)
                for key,value in a['numeric'].items():numeric[key].append(value)
            stats={k:dict(observed=sum(d['observed'] for d in v),missing=sum(d['missing'] for d in v),
                sum=sum(d['sum'] for d in v),min=min((d['min'] for d in v if d['min'] is not None),default=None),
                max=max((d['max'] for d in v if d['max'] is not None),default=None)) for k,v in numeric.items()}
            for v in stats.values():v['mean']=v['sum']/v['observed'] if v['observed'] else None
            compact.append(dict(candidate_id=cid,tap=tap,native_cells=len(cells),source_duration_sec=sum(z['duration_sec'] for z in cells),
                source_dispatches=sum(z['data']['source_dispatches'] for z in cells),actual_embedding_calls=sum(z['data']['actual_embedding_calls'] for z in cells),
                flags=dict(flags),reasons=dict(reasons),event_counts=dict(events),numeric=stats,inclusive_costs_sec={k:dict(v) for k,v in costs.items()},
                scheduler_peak_pending=max((z['data']['queue']['observed_max_pending'] for z in cells if z['data']['queue']['observed_max_pending'] is not None),default=None),
                scheduler_peak_pending_missing_cells=sum(z['data']['queue']['observed_max_pending'] is None for z in cells),
                worker_elapsed_sum_sec=sum(z['worker_elapsed_sec'] for z in cells),native_elapsed_sum_sec=sum(z['native_elapsed_sec'] for z in cells),
                process_cpu_sum_sec=sum(z['process_cpu_sec'] for z in cells),peak_journal_lag_sec=None,target_track_chosen_count=None,sole_cue_causal_admission_count=None))
    write(out/'NATIVE_CELLS.json',dict(schema=SCHEMA,rows=records))
    result=dict(schema=SCHEMA,status='COMPLETE_336_BOUND_NATIVE_CELLS',plan=plan_binding,cells=336,summary=compact,cells_binding=bind(out/'NATIVE_CELLS.json'),elapsed_sec=time.perf_counter()-started,
        source=bind(__file__),readme=bind(Path(__file__).with_name('README_S6C_NATIVE_CADENCE_AUDIT.md')),neural_calls=0,
        scope='Role diagnostics are counted separately from shared source dispatches. Due ledger entries acknowledged on an admitted role are not named/identified target selections. All due entries receive the same global admitted-window ledger update. Cue/onset/cosine causes are not separately logged, so sole-cue causal credit is unavailable. Model/API/full-dispatch costs are nested; concurrent lanes and batch timings are not additive wall time or CM5 latency. Empty and stale released context are observations, not future evidence.')
    write(out/'RESULT.json',result);return bind(out/'RESULT.json')
def tests():
    import tempfile
    count=0
    p=dict(embedding=dict(short_hop_sec=.25,mature_hop_sec=.5,sparse_hop_sec=1,hop_sec=.25,cadence_policy='uncertainty'))
    diag=dict(event_type='research_embedding_admission',payload=dict(evidence_kind='short',source_start_sec=0.,source_end_sec=.5,admitted=True,reason='admitted',naming_used_for_schedule=False,
        track_debts=[dict(track_id=1,unique_sec_deficit=1.,disjoint_count_deficit=1,due=True)],cue_event=False,uncertainty_trigger=True,
        since_last_role_sec=.5,tracking_snapshot_available_at_sec=.25,tracking_context_age_sec=.25,tracking_context_empty=False,tracking_context_used=True,selected_hop_sec=.25,clean_fraction=1.,estimated_clean_sec=.5,contiguous_clean_sec=.5,selected_rms=.1))
    a=Accumulator(p,1.);a.consume(diag);count+=1
    try:a.consume(diag)
    except ValueError:count+=1
    else:fail('Duplicate fixture')
    for field,value in [('source_end_sec',2.),('admitted',False),('tracking_snapshot_available_at_sec',.6),('tracking_context_age_sec',-.1),('naming_used_for_schedule',True)]:
        d=json.loads(json.dumps(diag));d['payload'][field]=value
        try:Accumulator(p,1.).consume(d)
        except ValueError:count+=1
        else:fail('Guard fixture '+field)
    with tempfile.TemporaryDirectory() as folder:
        q=Path(folder)/'x.json';q.write_text('{}');b=bind(q);q.write_text('[]')
        try:read(b)
        except ValueError:count+=1
        else:fail('Same-length changed bytes fixture')
        q.write_text(dumps(diag)+'\n');b=bind(q);a=Accumulator(p,1.);stream_exact(b,a)
        if a.events['research_embedding_admission']!=1:fail('Actual stream parse fixture')
        count+=1
        bad=dict(b,sha256='0'*64)
        try:stream_exact(bad,Accumulator(p,1.))
        except ValueError:count+=1
        else:fail('Changed stream hash accepted')
        q.write_text('{broken}\n');b=bind(q)
        try:stream_exact(b,Accumulator(p,1.))
        except json.JSONDecodeError:count+=1
        else:fail('Malformed event accepted')
    a=Accumulator(p,1.)
    try:a.consume(dict(event_type='research_embedding',payload=dict(source_start_sec=0.,source_end_sec=.5,evidence_kind='short')))
    except ValueError:count+=1
    else:fail('Unadmitted actual embedding accepted')
    return dict(status='PASS',checks=count,neural_calls=0)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['tests','prepare','run']);parser.add_argument('--plan',type=Path);parser.add_argument('--sha256')
    args=parser.parse_args()
    if args.action=='tests':result=tests()
    elif args.action=='prepare':result=prepare()
    else:
        if not args.plan or not args.sha256:parser.error('run requires exact --plan and --sha256')
        b=bind(args.plan)
        if b['sha256']!=args.sha256:fail('Wrong planned audit bytes')
        result=run(b)
    print(json.dumps(result,indent=2,allow_nan=False))
if __name__=='__main__':main()
