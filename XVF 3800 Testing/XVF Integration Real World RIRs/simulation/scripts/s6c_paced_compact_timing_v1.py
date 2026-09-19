"""Bound descriptive paced observations; see README_S6C_PACED_COMPACT_TIMING_V1.md."""
from __future__ import annotations
import argparse,hashlib,json,math,os
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
NAME_FIELDS={
 'first_any_decision_delay_sec':'first_any_decision_status',
 'first_correct_decision_delay_sec':'first_correct_decision_status',
 'first_confirmed_correct_decision_delay_sec':'first_confirmed_correct_decision_status',
 'first_stable_retained_row_delay_sec':'first_stable_retained_row_status'}
DENOMINATORS={
 'group_metrics':'Cells with a finite scalar versus cells with null; resource-peak counts are cells, not process samples.',
 'event_lags':'Original emission records of each event type, with finite lag versus null lag; not cells or utterances.',
 'name_delays':'Original turn occurrences within the exact roster/reference/attainability and censoring-status bin, with finite delay versus null.',
 'observation_counts':'Per-cell original stored sample counts, separated by trajectory/external observer and original metric key. Null means count unavailable. Observer counts are not added or deduplicated across sources.'}
def require(ok,message):
 if not ok:raise ValueError(message)
def binding(path,raw=None):
 p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read_bound(b):
 p=Path(b['path']).resolve();require(p.is_relative_to(REPORT),'Report metadata only')
 require(p.stat().st_size<=32*2**20,'Bounded metadata input')
 raw=p.read_bytes();require(len(raw)<=32*2**20 and binding(p,raw)==b,'Exact input bytes')
 return json.loads(raw)
def number(value):
 if value is None:return None
 require(type(value) in (int,float) and math.isfinite(value),'Finite number or explicit null required')
 return value
def stats(values):
 values=list(values);valid=sorted(number(v) for v in values if v is not None)
 def q(p):
  if not valid:return None
  rank=(len(valid)-1)*p;i=int(rank);f=rank-i
  return valid[i]*(1-f)+valid[min(i+1,len(valid)-1)]*f
 return dict(observed=len(valid),missing=len(values)-len(valid),min=valid[0] if valid else None,max=valid[-1] if valid else None,mean=sum(valid)/len(valid) if valid else None,p50=q(.5),p95=q(.95))
def seconds(start,end):
 if start is None or end is None:return None
 a=datetime.fromisoformat(start.replace('Z','+00:00'));b=datetime.fromisoformat(end.replace('Z','+00:00'))
 require(a.tzinfo is not None and b.tzinfo is not None,'Aware event UTC timestamps required')
 return (b-a).total_seconds()
def peak(*values):
 vals=[number(x) for x in values if x is not None]
 return max(vals) if vals else None
def path_identity(value):
 require(isinstance(value,str) and value and Path(value).is_absolute(),'Explicit absolute native identity path')
 return os.path.normcase(str(Path(value).resolve()))
def admit_unique_native(native,seen):
 result=native['native_result'];sha=result['sha256']
 require(isinstance(sha,str) and __import__('re').fullmatch(r'[0-9a-f]{64}',sha),'Exact native SHA256 identity')
 keys={('result_path',path_identity(result['path'])),('result_sha256',sha),('session_dir',path_identity(native['native_session_dir']))}
 require(not keys.intersection(seen),'No repeated native result path, content hash or actual session')
 seen.update(keys)
def observation_counts(cell):
 trajectory=cell.get('trajectory') or {};measured=cell.get('measured_cell') or {}
 def count(value):
  require(value is None or (type(value) is int and value>=0),'Nonnegative integer sample count or explicit null')
  return value
 def metric_counts(obj):
  return {key:{field:count(value.get(field)) for field in ('observed','missing')} for key,value in obj.items() if isinstance(value,dict) and ('observed' in value or 'missing' in value)}
 backlog=trajectory.get('event_queue_backlog')
 return dict(trajectory_samples=count(trajectory.get('samples',trajectory.get('sample_count'))),
  trajectory_null_live_samples=count(trajectory.get('null_live_samples')),
  trajectory_missing_telemetry_samples=count(trajectory.get('missing_telemetry_samples')),
  trajectory_incomplete_tree_samples=count(trajectory.get('incomplete_tree_samples')),
  measured_phase_process_samples=count((measured.get('phase_observations') or {}).get('process_samples')),
  trajectory_process=metric_counts(trajectory.get('process') or {}),
  external_process=metric_counts(cell.get('external_process_statistics') or {}),
  trajectory_telemetry=metric_counts(trajectory.get('telemetry') or {}),
  trajectory_backlog=metric_counts(trajectory.get('backlog') or {}),
  trajectory_event_queue_backlog={field:count(backlog.get(field)) for field in ('observed','missing')} if isinstance(backlog,dict) else None)
def summarize_cell(cell,native,input_id,cohort,cell_binding,analysis_binding):
 require(cell['status']=='COMPLETE' and native['status']=='COMPLETE','Actual completed source rows')
 require(cell['native_result']==native['native_result'],'Exact analysis/normalized native binding')
 proofs=native.get('proof_bindings')
 require(isinstance(proofs,list) and analysis_binding in proofs and cell_binding in proofs,'Exact consumed analysis and measurement must be normalized proofs')
 historical='job' in cell
 job=cell['job'] if historical else cell
 require(job.get('profile_id',job.get('candidate_id'))==native['candidate_id'],'Candidate join')
 require(job['case_id']==native['case_id'] and job['repetition']==native['repetition'],'Case/repetition join')
 jid=job['job_id'];require(jid==native['job_id'],'Exact native job')
 if not historical:
  require(job['asr_tap']==native['asr_tap'] and job['identity_tap']==native['identity_tap'],'Canonical ASR/identity tap join')
 path_identity(native['native_session_dir'])
 actual=cell.get('actual_emission',{}) if historical else cell.get('actual_events',{})
 emissions=actual.get('rows',[]) if historical else actual.get('emissions',[])
 start=actual.get('source_started') or {}
 names=cell.get('actual_name_emissions')
 clock=(names or {}).get('clock',{})
 end=(actual.get('session_completed') or {}).get('wall_time_utc') if historical else clock.get('session_completed_utc')
 duration=number(native['source_duration_sec']);require(duration>0,'Positive actual source duration')
 interval=seconds(start.get('wall_time_utc'),end)
 costs=cell.get('native_worker_costs',{});measured=cell.get('measured_cell',{})
 trajectory=cell.get('trajectory',{});process=trajectory.get('process',{});external=cell.get('external_process_statistics',{})
 def pmax(obj,key):return (obj.get(key) or {}).get('max')
 values=dict(source_to_completed_utc_sec=interval,source_to_completed_utc_ratio=interval/duration if interval is not None else None,
  canonical_completed_cell_wall_sec=measured.get('completed_cell_wall_sec'),canonical_native_elapsed_sec=measured.get('native_elapsed_sec'),canonical_model_startup_sec=measured.get('model_startup_sec'),
  historical_full_worker_elapsed_sec=costs.get('full_worker_elapsed_sec'),historical_bundle_admission_sec=costs.get('bundle_admission_sec'),historical_engine_launch_loading_sec=costs.get('engine_launch_loading_sec'),
  sampled_rss_sum_upper_bound_bytes=peak(pmax(process,'rss_sum_upper_bound_bytes'),pmax(external,'rss_sum_upper_bound_bytes')),
  sampled_private_resident_uss_sum_bytes=peak(pmax(process,'private_resident_uss_bytes'),pmax(process,'private_resident_uss_sum_bytes'),pmax(external,'private_resident_uss_bytes')),
  sampled_windows_private_commit_sum_bytes=peak(pmax(process,'windows_private_commit_bytes'),pmax(process,'windows_private_commit_sum_bytes'),pmax(external,'windows_private_commit_bytes')),
  trajectory_max_sample_gap_sec=trajectory.get('max_sample_gap_sec'))
 for value in values.values():number(value)
 event_values=defaultdict(list)
 for e in emissions:event_values[e['event_type']].append(number(e.get('emission_minus_source_cursor_sec')))
 reversals=actual.get('wall_order_reversals',[]) if historical else actual.get('wall_timestamp_reversals',[])
 require(isinstance(reversals,list),'Original reversal list')
 row=dict(input_id=input_id,cohort=cohort,job_id=jid,candidate_id=native['candidate_id'],case_id=native['case_id'],asr_tap=native['asr_tap'],identity_tap=native['identity_tap'],condition_sha256=native['condition_sha256'],condition=native['condition'],repetition=native['repetition'],source_duration_sec=duration,owner_closed=native['owner_closed'],tail_complete=native['tail_complete'],continuous=native['continuous'],measurement=cell_binding,native_result=native['native_result'],parity_status=cell.get('parity',{}).get('status'),metrics=values,event_lag_summaries={k:stats(v) for k,v in event_values.items()},wall_timestamp_reversal_count=len(reversals),name_metric_scope=(names or {}).get('status','NOT_AVAILABLE_HISTORICAL_GENERATION'),name_clock_valid=clock.get('valid'),name_turn_count=len(names.get('turns',[])) if names is not None else None)
 row.update(analysis=analysis_binding,native_session_dir=native['native_session_dir'],observation_counts=observation_counts(cell))
 return row,event_values,(names or {}).get('turns',[])
def group_key(row):
 return tuple(row[k] for k in ('input_id','cohort','candidate_id','asr_tap','identity_tap','condition_sha256','repetition'))
def run(args):
 require(__import__('re').fullmatch(r'[A-Za-z0-9_-]{1,64}',args.namespace or ''),'Simple fresh output namespace')
 sp=Path(args.spec).resolve();sb=binding(sp);require(sb['sha256']==args.spec_sha256,'Explicit spec SHA')
 spec=read_bound(sb);require(spec['schema']=='s6c-paced-compact-timing-inputs.v1' and spec['status']=='EXPLICIT_COMPLETE596_INPUTS' and spec['expected_cells']==596,'Exact full paced scope')
 out=REPORT/'paced_compact_timing'/args.namespace;require(not out.exists(),'Preserve prior output');out.mkdir(parents=True)
 require(len(spec['inputs'])==16 and len({x['input_id'] for x in spec['inputs']})==16,'Exact sixteen analysis populations')
 allrows=[];bygroup={};sources=[sb];seen=set();cohorts=Counter()
 for item in spec['inputs']:
  require(item['cohort'] in ('main','cadence_gate','arrival','cross'),'Explicit cohort')
  analysis=read_bound(item['analysis']);normalization=read_bound(item['normalization'])
  require(analysis['status']=='COMPLETE' and normalization['status']=='COMPLETE_METADATA_NORMALIZATION','Complete original analysis/normalization')
  norm_binding=normalization['outputs']['runtime_rows'];norm=read_bound(norm_binding)
  require(len({r['job_id'] for r in norm})==len(norm),'Unique normalized job IDs')
  byjob={r['job_id']:r for r in norm};refs=analysis.get('cell_measurements',analysis.get('measurements'))
  require(isinstance(refs,list) and len(refs)==analysis['completed']==analysis['requested'],'Exact original analyzed cardinality')
  sources.extend([item['analysis'],item['normalization'],norm_binding])
  for ref in refs:
   cell=read_bound(ref);jid=(cell.get('job') or cell)['job_id'];native=byjob[jid]
   row,events,turns=summarize_cell(cell,native,item['input_id'],item['cohort'],ref,item['analysis'])
   admit_unique_native(native,seen)
   require(row['continuous'] is False,'Paced cells cannot become long sessions')
   allrows.append(row);sources.append(ref);cohorts[item['cohort']]+=1
   key=group_key(row)
   if key not in bygroup:bygroup[key]=dict(rows=[],events=defaultdict(list),names={})
   group=bygroup[key];group['rows'].append(row)
   for kind,values in events.items():group['events'][kind].extend(values)
   for turn in turns:
    nk=(turn.get('roster_status'),turn.get('reference_status'),turn.get('correct_name_attainable_in_actual_gallery'))
    if nk not in group['names']:group['names'][nk]=dict(count=0,delays={f:defaultdict(list) for f in NAME_FIELDS})
    ng=group['names'][nk];ng['count']+=1
    for field,status_field in NAME_FIELDS.items():ng['delays'][field][str(turn.get(status_field,'MISSING_STATUS'))].append(number(turn.get(field)))
 require(len(allrows)==596 and cohorts==Counter(main=520,cadence_gate=24,arrival=12,cross=40),'Exact original cohort cardinalities')
 groups=[]
 for key,group in sorted(bygroup.items()):
  rows=group['rows'];first=rows[0]
  result={k:first[k] for k in ('input_id','cohort','candidate_id','asr_tap','identity_tap','condition_sha256','condition','repetition')}
  result.update(cells=len(rows),distinct_cases=len({x['case_id'] for x in rows}),owner_closed_counts=dict(Counter(str(x['owner_closed']) for x in rows)),tail_complete_counts=dict(Counter(str(x['tail_complete']) for x in rows)),parity_status_counts=dict(Counter(str(x['parity_status']) for x in rows)),wall_timestamp_reversal_count=sum(x['wall_timestamp_reversal_count'] for x in rows),metrics={k:stats(x['metrics'][k] for x in rows) for k in first['metrics']},event_lags={k:stats(v) for k,v in sorted(group['events'].items())},name_metric_scope_counts=dict(Counter(x['name_metric_scope'] for x in rows)),name_clock_valid_counts=dict(Counter(str(x['name_clock_valid']) for x in rows)),name_groups=[])
  for (roster,reference,attainable),ng in sorted(group['names'].items(),key=lambda x:str(x[0])):
   result['name_groups'].append(dict(roster_status=roster,reference_status=reference,correct_name_attainable_in_actual_gallery=attainable,turn_occurrences=ng['count'],delays={field:{status:stats(vals) for status,vals in sorted(bins.items())} for field,bins in ng['delays'].items()}))
  groups.append(result)
 def save(name,value):
  p=out/name;raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
  with p.open('xb') as f:f.write(raw)
  return binding(p,raw)
 outputs=[save('CELL_SUMMARIES.json',allrows),save('GROUP_SUMMARIES.json',groups)]
 lines=['# Actual paced timing observations','', 'All596 original paced cells are projected from bound completed scientific analyses and normalized native rows. Main520, cadence24, arrival12 and cross40 stay separate; each exact condition/tap/repetition stays separate. Repeats are not independent scenes. This is descriptive observation, not selection or final S6C acceptance.','',
 'UTC source-to-completion includes pacing, scheduling and finalization. Its ratio to source duration is not pure algorithm RTF or device latency. Canonical native and outer-cell intervals and historical worker/admission intervals are separately defined and are never added. Event lag means UTC emission minus that event’s source cursor; it is not phonetic onset, GUI latency or partial-transcript accuracy. Missing metrics remain null. Percentiles use linear interpolation and are descriptive, especially for tiny repeated panels.','',
 'RSS sums are sampled upper bounds with possible shared-page double counting; USS and Windows private commit remain different measures. Maxima use the maximum available recorded observer peak, never a sum of observer maxima. Sampling gaps and wall timestamp reversals remain reported. Raw buffers stay locally bound.','',
 'Name delays are grouped by exact roster/reference/attainability and original censoring status. Unavailable or censored turns are not zero-delay successes. Historical generations have no C actual-name metric. Source/tail completeness is not word accuracy.','',
 '| Input / candidate / taps / repetition | Cells | Source→complete UTC ratio p50 / p95 | Event cursor lag: partial p50 / p95 (s) | RSS sampled peak max (MiB) |',
 '| --- | ---: | ---: | ---: | ---: |']
 lines[2:2]=['Denominators: grouped scalar metric observed/missing counts refer to cells; event lag counts refer to original emissions of that type; name-delay counts refer to turn occurrences in each declared status bin. Per-cell observation_counts retains original process/telemetry sample counts separately for each observer and metric. Unavailable counts remain null; overlapping observer sample counts are never added.','']
 def fmt(v):return 'NA' if v is None else f'{v:.3f}'
 for g in groups:
  ratio=g['metrics']['source_to_completed_utc_ratio'];ev=g['event_lags'].get('transcript_partial',{});mem=g['metrics']['sampled_rss_sum_upper_bound_bytes']['max']
  label=f"{g['input_id']} / {g['candidate_id']} / {g['asr_tap']}→{g['identity_tap']} / r{g['repetition']}"
  lines.append(f"| {label} | {g['cells']} | {fmt(ratio['p50'])} / {fmt(ratio['p95'])} | {fmt(ev.get('p50'))} / {fmt(ev.get('p95'))} | {fmt(mem/2**20 if mem is not None else None)} |")
 p=out/'PACED_TIMING_OBSERVATIONS.md';p.write_text('\n'.join(lines)+'\n',encoding='utf-8');outputs.append(binding(p))
 receipt=dict(schema='s6c-paced-compact-timing-result.v1',status='COMPLETE_DESCRIPTIVE596_PROJECTION',created_utc=datetime.now(timezone.utc).isoformat(),cells=len(allrows),groups=len(groups),cohort_cells=dict(cohorts),outputs=outputs,sources=sources,source=binding(__file__),readme=binding(HERE/'README_S6C_PACED_COMPACT_TIMING_V1.md'),new_neural_calls=0,new_policy_or_scoring_calls=0,raw_event_audio_model_files_read=0,scope='Read existing bound per-cell analysis/normalized JSON only. No new native sessions, timing qualification or operating selection. Repetition and original status/censoring distinctions retained.')
 receipt['denominator_definitions']=DENOMINATORS
 return save('RESULT.json',receipt)
def checks():
 checks=[]
 def ok(name,truth):require(truth,name);checks.append(name)
 def bad(name,fn):
  try:fn()
  except (ValueError,TypeError):checks.append(name);return
  raise AssertionError(name)
 ok('all_missing_stays_null',stats([None,None])==dict(observed=0,missing=2,min=None,max=None,mean=None,p50=None,p95=None))
 x=stats([1,None,3]);ok('linear_quantiles_and_denominators',x['observed']==2 and x['missing']==1 and x['p50']==2 and abs(x['p95']-2.9)<1e-12)
 ok('single_observation',stats([4])['p95']==4)
 bad('nonfinite_rejected',lambda:stats([float('nan')]))
 bad('bool_rejected',lambda:number(True))
 bad('naive_clock_rejected',lambda:seconds('2026-01-01T00:00:00','2026-01-01T00:00:01'))
 ok('aware_offsets_match',seconds('2026-01-01T00:00:00Z','2025-12-31T19:00:02-05:00')==2)
 ok('reversed_clock_preserved',seconds('2026-01-01T00:00:02Z','2026-01-01T00:00:00Z')==-2)
 ok('observer_peaks_not_added',peak(3,None,4)==4 and peak(None) is None)
 base=dict(input_id='main',cohort='main',candidate_id='C088',asr_tap='O0',identity_tap='O0',condition_sha256='a',repetition=1)
 for field,value in [('input_id','arrival'),('cohort','arrival'),('identity_tap','O1'),('condition_sha256','b'),('repetition',2)]:
  ok('separate_'+field,group_key(base)!=group_key(dict(base,**{field:value})))
 ab=dict(path=str(REPORT/'fixture/ANALYSIS.json'),bytes=2,sha256='a'*64)
 cb=dict(path=str(REPORT/'fixture/CELL.json'),bytes=3,sha256='b'*64)
 nb=dict(path=str(REPORT/'fixture/NATIVE.json'),bytes=4,sha256='c'*64)
 native=dict(base,status='COMPLETE',native_result=nb,case_id='S45_01_01',job_id='fixture_r1',source_duration_sec=45,
  owner_closed=True,tail_complete=True,continuous=False,condition={},proof_bindings=[ab,cb],native_session_dir=str(REPORT/'fixture/session1'))
 cell=dict(status='COMPLETE',native_result=nb,candidate_id='C088',case_id='S45_01_01',job_id='fixture_r1',
  repetition=1,asr_tap='O0',identity_tap='O0',actual_events={'wall_timestamp_reversals':[{'original':'retained'}]},
  trajectory={'samples':3,'process':{'rss_sum_upper_bound_bytes':{'observed':2,'missing':1,'max':8}}},
  external_process_statistics={'rss_sum_upper_bound_bytes':{'observed':4,'missing':2,'max':9}})
 def summarize(c=cell,n=native,a=ab,b=cb):return summarize_cell(c,n,'main','main',b,a)[0]
 row=summarize()
 ok('exact_proof_join_and_session_retained',row['analysis']==ab and row['measurement']==cb and row['native_session_dir']==native['native_session_dir'])
 ok('separate_resource_sample_denominators',row['observation_counts']['trajectory_process']['rss_sum_upper_bound_bytes']==dict(observed=2,missing=1) and row['observation_counts']['external_process']['rss_sum_upper_bound_bytes']==dict(observed=4,missing=2) and row['metrics']['sampled_rss_sum_upper_bound_bytes']==9)
 ok('unavailable_sample_counts_stay_null',row['observation_counts']['trajectory_missing_telemetry_samples'] is None)
 ok('original_reversal_and_unknown_name_semantics',row['wall_timestamp_reversal_count']==1 and row['name_clock_valid'] is None)
 bad('canonical_asr_tap_mismatch_rejected',lambda:summarize(c=dict(cell,asr_tap='O1')))
 bad('canonical_identity_tap_mismatch_rejected',lambda:summarize(c=dict(cell,identity_tap='O1')))
 bad('absent_normalized_proofs_rejected',lambda:summarize(n={k:v for k,v in native.items() if k!='proof_bindings'}))
 bad('missing_analysis_proof_rejected',lambda:summarize(n=dict(native,proof_bindings=[cb])))
 bad('missing_measurement_proof_rejected',lambda:summarize(n=dict(native,proof_bindings=[ab])))
 bad('different_analysis_bytes_rejected',lambda:summarize(a=dict(ab,bytes=3)))
 bad('different_measurement_sha_rejected',lambda:summarize(b=dict(cb,sha256='d'*64)))
 bad('native_result_mismatch_rejected',lambda:summarize(c=dict(cell,native_result=dict(nb,bytes=5))))
 seen=set();admit_unique_native(native,seen)
 bad('same_native_path_rejected',lambda:admit_unique_native(dict(native,native_result=dict(nb,sha256='d'*64),native_session_dir=str(REPORT/'fixture/session2')),seen))
 bad('copied_native_content_rejected',lambda:admit_unique_native(dict(native,native_result=dict(nb,path=str(REPORT/'fixture/COPY.json')),native_session_dir=str(REPORT/'fixture/session2')),seen))
 bad('same_native_session_rejected',lambda:admit_unique_native(dict(native,native_result=dict(nb,path=str(REPORT/'fixture/NATIVE2.json'),sha256='d'*64)),seen))
 second=dict(native,repetition=2,job_id='fixture_r2',native_result=dict(nb,path=str(REPORT/'fixture/NATIVE2.json'),sha256='d'*64),native_session_dir=str(REPORT/'fixture/session2'))
 admit_unique_native(second,seen);ok('distinct_physical_repetition_retained',len(seen)==6)
 bad('missing_native_session_rejected',lambda:admit_unique_native(dict(native,native_session_dir=None),set()))
 bad('boolean_sample_count_rejected',lambda:observation_counts({'trajectory':{'samples':True}}))
 bad('negative_sample_count_rejected',lambda:observation_counts({'trajectory':{'process':{'rss':{'observed':-1,'missing':0}}}}))
 historical=dict(cell,job={k:cell[k] for k in ('case_id','job_id','repetition')},trajectory={'sample_count':5,'null_live_samples':1,'missing_telemetry_samples':2},actual_emission={'wall_order_reversals':[]})
 historical['job']['profile_id']='C088'
 h=summarize(c=historical)
 ok('historical_original_count_keys_retained',h['observation_counts']['trajectory_samples']==5 and h['observation_counts']['trajectory_null_live_samples']==1 and h['observation_counts']['trajectory_missing_telemetry_samples']==2)
 return dict(status='PASS_FOCUSED_DESCRIPTIVE_BOUNDARY_CHECKS',checks=len(checks),names=checks,actual_projection=False,new_neural_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['checks','run']);p.add_argument('--spec',type=Path);p.add_argument('--spec-sha256');p.add_argument('--namespace');a=p.parse_args()
 print(json.dumps(checks() if a.action=='checks' else run(a),indent=2,allow_nan=False))
