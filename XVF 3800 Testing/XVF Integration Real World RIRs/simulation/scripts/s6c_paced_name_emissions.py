"""Additive native wall-emission metrics; README_S6C_PACED_NAME_EMISSIONS.md."""
from __future__ import annotations
import argparse, hashlib, json, math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import s6c_name_analysis_v3 as names

RATE=16000
POLICY=dict(schema='s6c_paced_name_emissions.v1',stable_retained_row_sec=.5,
 clock='Native event UTC minus the unique source_started UTC; occurrence origin is its mapped file-support start added to that origin. This is nominal playback-relative emitted delay, not actual phonetic or GUI latency.',
 decision='First emitted naming result from a speaker_decision whose actual source span intersects exactly one complete-reference occurrence and positive sole support. Mixed, repeated-occurrence, incomplete, missing and zero-support spans are unqualified. Delayed processing after a turn remains possible.',
 retained='Each emitted transcript row is held until its next native emission or the exact session_finalization_v3.finished_utc closure. Only its most recent arrived ASR span classifies the interval; no final-span backfill. Stable means .5 contiguous wall seconds of a confirmed correct name on this retained row, not continuous live active speech.',
 missing='No qualified event is right-censored at closed observation. Incomplete/missing/zero sole support have distinct unavailable statuses. All occurrences remain in output.',
 no_invented_expiry='No wall-time expiry is invented for emitted decisions. Runtime .75s modeled-source freshness remains solely in unchanged V3 metrics.',
 clock_failure='Backward relevant UTC timestamps invalidate these wall metrics; records/counts remain. No sorting, clamping, clock interpolation or substitution.',
 authority='Caller must supply exact admitted closed canonical paced native events, original support/Q, resolved loaded gallery and same-native prediction. This pure API performs no model/payload IO or source-admission replacement.')

def need(ok,message):
 if not ok:raise ValueError(message)

def number(x):return type(x) in (int,float) and math.isfinite(x)

def timestamp(x):
 t=datetime.fromisoformat(x.replace('Z','+00:00'))
 need(t.tzinfo is not None,'Timezone-aware native UTC required')
 return t

def source_span(payload,length):
 a,b=payload.get('source_start_sec'),payload.get('source_end_sec')
 if not(number(a) and number(b) and 0<=a<b<=length/RATE+1e-9):return None
 return [[round(a*RATE),min(length,round(b*RATE))]]

def attribute(span,turns,complete):
 if not complete:return 'INCOMPLETE_REFERENCE',None
 if any(t['active_ranges'] is None or t['sole'] is None for t in turns):return 'UNAVAILABLE_ALIGNMENT',None
 if span is None:return 'UNAVAILABLE_ARRIVED_SOURCE_SPAN',None
 hits=[t for t in turns if names.samples(names.intersection(span,t['active_ranges']))>0]
 if not hits:return 'NO_REFERENCE_ACTIVE_SUPPORT',None
 if len(hits)!=1:return 'MULTIPLE_SOURCE_OCCURRENCES',None
 t=hits[0]
 if names.samples(names.intersection(span,t['sole']))<=0:return 'NO_SOLE_SUPPORT',None
 return 'ONE_SOLE_SOURCE_OCCURRENCE',t

def wall_context(events,finalization=None):
 starts=[(i,e) for i,e in enumerate(events) if e['event_type']=='source_started']
 ends=[(i,e) for i,e in enumerate(events) if e['event_type']=='session_completed']
 need(len(starts)==len(ends)==1,'Exactly one source origin and completed session required')
 si,start=starts[0];ei,end=ends[0];need(si<ei,'Completion before source start')
 relevant={'source_started','speaker_decision','identity_decision','transcript_partial','transcript_final','transcript_label_revision','session_completed'}
 rows=[]
 for i,e in enumerate(events):
  if e['event_type'] not in relevant:continue
  need(si<=i<=ei,'Relevant emission outside source/completion markers')
  rows.append((i,e,timestamp(e['wall_time_utc'])))
 stamps=[t for _,_,t in rows]
 origin=timestamp(start['wall_time_utc']);terminal=timestamp(end['wall_time_utc'])
 if finalization is not None:
  need(finalization['state']=='COMPLETED' and finalization['finalization_error'] is None and not finalization['live_lanes_at_finalization'] and not finalization['resident_bundle_lease_retained'] and finalization['event_and_transcript_handles_closed'] is True,'Exact successful finalization required')
  terminal=timestamp(finalization['finished_utc']);need(terminal>=timestamp(end['wall_time_utc']),'Closure precedes session completion')
 horizon=(terminal-origin).total_seconds()
 reversals=[dict(previous_line=a[0]+1,line=b[0]+1,delta_sec=(b[2]-a[2]).total_seconds()) for a,b in zip(rows,rows[1:]) if b[2]<a[2]]
 return dict(valid=not reversals and horizon>=0,origin_utc=start['wall_time_utc'],session_completed_utc=end['wall_time_utc'],end_utc=finalization['finished_utc'] if finalization is not None else end['wall_time_utc'],horizon_sec=horizon,reversals=reversals),[(i,e,(t-origin).total_seconds()) for i,e,t in rows]

def row_intervals(records,horizon,turns,profiles,complete,length):
 """Native-order records for one row; no expiry or across-row state merge."""
 output=[];current=None;first_display=None;last=None;span=None;latest_readable=False
 for line,e,now in records:
  p=e['payload'];asr=e['event_type'] in ('transcript_partial','transcript_final')
  if asr:need(isinstance(p.get('text'),str),'Actual ASR emission text must be a string')
  readable=asr and bool(p['text'].strip())
  if current is None and not readable:continue
  if current is not None:output.append(dict(start_sec=last,end_sec=now,**current))
  if asr:span=source_span(p,length);latest_readable=readable
  ref,t=attribute(span,turns,complete) if latest_readable else ('NO_READABLE_NATIVE_TEXT',None)
  state=names.named(p,profiles,transcript=True)
  status='no_readable_text' if not latest_readable else names.status_against(state,t['metadata_identity']) if t is not None else 'unqualified_reference'
  current=dict(reference_status=ref,segment_index=t['segment_index'] if t is not None else None,
   reference_identity=t['metadata_identity'] if t is not None else None,name_status=status,assigned_state=state,
   arrived_span=span,latest_text_is_readable=latest_readable,event_line=line+1,event_type=e['event_type'],event_id=p.get('event_id'),revision_scope=p.get('revision_scope'))
  if first_display is None:first_display=now
  last=now
 if current is not None:output.append(dict(start_sec=last,end_sec=horizon,**current))
 need(all(x['end_sec']>=x['start_sec'] for x in output),'Backward row clock')
 return output,first_display

def stable_runs(intervals):
 runs=[]
 for x in intervals:
  if x['end_sec']<=x['start_sec']:continue
  valid=x['name_status']=='correct_name' and x['assigned_state']['confirmed']
  if not valid:continue
  if runs and runs[-1]['end_sec']==x['start_sec'] and runs[-1]['segment_index']==x['segment_index'] and runs[-1]['reference_identity']==x['reference_identity']:
   runs[-1]['end_sec']=x['end_sec']
  else:runs.append(dict(start_sec=x['start_sec'],end_sec=x['end_sec'],segment_index=x['segment_index'],reference_identity=x['reference_identity']))
 return [dict(x,criterion_attainment_sec=x['start_sec']+POLICY['stable_retained_row_sec']) for x in runs if round(x['end_sec']-x['start_sec'],6)>=POLICY['stable_retained_row_sec']]

def analyze(events,value,support,gallery,q,admission,finalization):
 """Caller binds each returned cell to its exact native/core source chain."""
 need(admission.get('source_kind')=='CANONICAL_SINGLE_SCENE_PAIR' and admission.get('realtime') is True and admission.get('native_session_complete') is True,'Admitted closed canonical source-paced cell required')
 need(admission.get('source_offset_samples')==0 and admission.get('inserted_gap_samples')==0,'Compositions require a separate metric definition')
 need(admission.get('case_id')==value['case_id'] and admission.get('profile_id')==value['profile_id'] and admission.get('asr_tap')==value['stream'] and admission.get('identity_tap')==value['identity_tap'],'Admitted route differs')
 length=round(value['duration_sec']*RATE);turns=names.mapped_turns(value,support,q)
 profiles={p['profile_id']:p for p in gallery['profiles']};need(len(profiles)==len(gallery['profiles']),'Duplicate gallery identities')
 clock,rows=wall_context(events,finalization);complete=support['all_speaker_reference_complete']
 counters=Counter(e['event_type'] for _,e,_ in rows)
 base=dict(schema=POLICY['schema'],case_id=value['case_id'],profile_id=value['profile_id'],stream=value['stream'],identity_tap=value['identity_tap'],policy=POLICY,clock=clock,
  input_admission=admission,source_occurrences=len(turns),all_speaker_reference_complete=complete,event_counts=dict(counters),gallery_condition=gallery['gallery_condition'],enrollment_tier=gallery['enrollment_tier'],
  retained_span_mapping='As in unchanged V3 names, ASR arrived-span sample times are on the common paired origin and are intersected once with identity-tap mapped source activity. This is identity-attribution support, not ASR word alignment; split-route supports are intentionally not remapped through both taps.')
 if not clock['valid']:
  return dict(base,status='UNAVAILABLE_WALL_CLOCK_ORDER',turns=[dict(segment_index=t['segment_index'],source_id=t['source_id'],status='UNAVAILABLE_WALL_CLOCK_ORDER') for t in turns],decisions=[],retained_rows=[],intervals=[])
 decisions=[];byrow=defaultdict(list);seen=set()
 for line,e,now in rows:
  p=e['payload'];kind=e['event_type']
  if kind=='speaker_decision':
   d=p.get('decision',p);eid=d.get('evidence_id',p.get('input_event_id'));need(eid is not None and eid not in seen,'One unique speaker decision per evidence ID');seen.add(eid)
   span=source_span(d,length);ref,t=attribute(span,turns,complete);state=names.named(d,profiles)
   decisions.append(dict(event_line=line+1,evidence_id=eid,wall_from_source_start_sec=now,modeled_available_at_sec=d.get('available_at_sec'),
    native_compute_finished_elapsed_sec=p.get('compute_finished_elapsed_sec'),source_span=span,reference_status=ref,
    segment_index=t['segment_index'] if t is not None else None,reference_identity=t['metadata_identity'] if t is not None else None,
    name_status=names.status_against(state,t['metadata_identity']) if t is not None else 'unqualified_reference',assigned_state=state,
    query_executed=d.get('identity',{}).get('query_executed'),evidence_kind=d.get('evidence_kind')))
  elif kind in ('transcript_partial','transcript_final','transcript_label_revision'):
   uid=p.get('utterance_id');need(uid is not None,'Native transcript row ID required');byrow[str(uid)].append((line,e,now))
 expected=[d['evidence_id'] for d in value['decisions']]
 need([d['evidence_id'] for d in decisions]==expected,'Native decision ID/order differs from admitted same-native prediction')
 resultrows=[];intervalrows=[];attainments=[]
 for uid,recs in byrow.items():
  intervals,first=row_intervals(recs,clock['horizon_sec'],turns,profiles,complete,length)
  if first is None:
   resultrows.append(dict(utterance_id=uid,status='NO_READABLE_NATIVE_ROW'));continue
  totals=Counter()
  for x in intervals:totals[x['name_status']]+=x['end_sec']-x['start_sec']
  stable=stable_runs(intervals);correct=[x['start_sec'] for x in intervals if x['name_status']=='correct_name']
  qualified=[x for x in intervals if x['segment_index'] is not None and x['end_sec']>x['start_sec']]
  attainable=[x for x in qualified if x['reference_identity'] in gallery['available_identities']]
  missing='UNQUALIFIED_REFERENCE' if not qualified else 'CORRECT_NAME_UNAVAILABLE_IN_ACTUAL_GALLERY' if not attainable else 'RIGHT_CENSORED_AT_TERMINAL_CLOSURE'
  need(abs(sum(totals.values())-(clock['horizon_sec']-first))<1e-7,'Retained wall-row partition differs')
  resultrows.append(dict(utterance_id=uid,status='SCORED_NATIVE_EMISSION_ROW',first_emitted_sec=first,observation_horizon_sec=clock['horizon_sec'],retained_row_sec=clock['horizon_sec']-first,
   exposure_row_sec=dict(totals),first_correct_from_first_emission_sec=min(correct)-first if correct else None,
   first_stable_attainment_from_first_emission_sec=min(x['criterion_attainment_sec'] for x in stable)-first if stable else None,
   qualified_reference_row_sec=sum(x['end_sec']-x['start_sec'] for x in qualified),correct_name_attainable_row_sec=sum(x['end_sec']-x['start_sec'] for x in attainable),
   roster_row_sec={status:sum(x['end_sec']-x['start_sec'] for x in qualified if names.roster_status(x['reference_identity'],gallery)==status) for status in ('ENROLLED','WITHHELD_OR_UNSELECTED','INTENDED_BUT_UNAVAILABLE','NO_GALLERY_CONTROL')},
   row_lifetime_below_stable_criterion=clock['horizon_sec']-first<POLICY['stable_retained_row_sec'],
   first_correct_status='OBSERVED' if correct else missing,first_stable_status='OBSERVED' if stable else missing))
  intervalrows.extend(dict(x,utterance_id=uid) for x in intervals);attainments.extend(dict(x,utterance_id=uid) for x in stable)
 results=[]
 for t in turns:
  origin=t['file_support'][0][0]/RATE if t['file_support'] else None
  eligible=[d for d in decisions if d['segment_index']==t['segment_index']]
  r=dict(segment_index=t['segment_index'],source_id=t['source_id'],metadata_identity=t['metadata_identity'],roster_status=names.roster_status(t['metadata_identity'],gallery),
   activity_available=t['activity_available'],sole_active_samples=names.samples(t['sole']) if t['sole'] is not None else None,nominal_occurrence_start_sec=origin,qualified_decision_emissions=len(eligible))
  status='INCOMPLETE_REFERENCE' if not complete else 'UNAVAILABLE_ALIGNMENT' if t['sole'] is None or origin is None else 'NO_SOLE_SUPPORT' if not t['sole'] else 'QUALIFIED_REFERENCE'
  r['reference_status']=status
  r['correct_name_attainable_in_actual_gallery']=t['metadata_identity'] in gallery['available_identities']
  for metric,criteria in [('first_any_decision',lambda d:d['name_status'] in ('correct_name','wrong_known_name')),('first_correct_decision',lambda d:d['name_status']=='correct_name'),('first_confirmed_correct_decision',lambda d:d['name_status']=='correct_name' and d['assigned_state']['confirmed'])]:
   hits=[d['wall_from_source_start_sec'] for d in eligible if criteria(d)]
   r[metric+'_delay_sec']=min(hits)-origin if hits and origin is not None else None
   r[metric+'_status']='OBSERVED' if hits else status if status!='QUALIFIED_REFERENCE' else 'NO_QUALIFIED_DECISION_EMISSION' if not eligible else 'CORRECT_NAME_UNAVAILABLE_IN_ACTUAL_GALLERY' if metric!='first_any_decision' and not r['correct_name_attainable_in_actual_gallery'] else 'RIGHT_CENSORED_AT_TERMINAL_CLOSURE'
  hits=[x['criterion_attainment_sec'] for x in attainments if x['segment_index']==t['segment_index']]
  r['first_stable_retained_row_delay_sec']=min(hits)-origin if hits and origin is not None else None
  row_qualified=any(x['segment_index']==t['segment_index'] and x['end_sec']>x['start_sec'] for x in intervalrows)
  r['first_stable_retained_row_status']='OBSERVED' if hits else status if status!='QUALIFIED_REFERENCE' else 'NO_QUALIFIED_RETAINED_ROW' if not row_qualified else 'CORRECT_NAME_UNAVAILABLE_IN_ACTUAL_GALLERY' if not r['correct_name_attainable_in_actual_gallery'] else 'RIGHT_CENSORED_AT_TERMINAL_CLOSURE'
  r['closed_observation_delay_sec']=clock['horizon_sec']-origin if status=='QUALIFIED_REFERENCE' else None
  results.append(r)
 return dict(base,status='COMPLETE_SCOPED_NATIVE_EMISSION_METRICS',turns=results,decisions=decisions,retained_rows=resultrows,intervals=intervalrows,stable_retained_runs=attainments,
  qualified_decision_emissions=sum(d['segment_index'] is not None for d in decisions),unqualified_decision_emissions=sum(d['segment_index'] is None for d in decisions),
  strict_empty=dict(applicable=not turns,assigned_decision_emissions=sum(d['assigned_state']['status']!='UNKNOWN_NAME' for d in decisions) if not turns else None,
   assigned_name_retained_row_sec=sum(x['end_sec']-x['start_sec'] for x in intervalrows if x['latest_text_is_readable'] and x['assigned_state']['status']!='UNKNOWN_NAME') if not turns else None,
   assigned_name_retained_rows=len({x['utterance_id'] for x in intervalrows if x['latest_text_is_readable'] and x['assigned_state']['status']!='UNKNOWN_NAME'}) if not turns else None,
   assigned_name_readable_emissions=sum(x['latest_text_is_readable'] and x['assigned_state']['status']!='UNKNOWN_NAME' for x in intervalrows) if not turns else None,
   scope='Assigned outputs with no deliberate reference source, without fabricated identity or WER. Readable emission count includes partial/final/revision row states. Retained row-seconds may overlap across rows and are not session-wall seconds.'))

def fixtures():
 t=dict(segment_index=0,metadata_identity='a',active_ranges=[[0,16000]],sole=[[0,16000]])
 need(attribute([[0,8000]],[t],True)[0]=='ONE_SOLE_SOURCE_OCCURRENCE','Single source');n=1
 for turns,complete,wanted in [([t],False,'INCOMPLETE_REFERENCE'),([dict(t,sole=None)],True,'UNAVAILABLE_ALIGNMENT'),([t,dict(t,segment_index=1)],True,'MULTIPLE_SOURCE_OCCURRENCES'),([dict(t,sole=[])],True,'NO_SOLE_SUPPORT')]:
  need(attribute([[0,8000]],turns,complete)[0]==wanted,wanted);n+=1
 need(attribute([[20000,24000]],[t],True)[0]=='NO_REFERENCE_ACTIVE_SUPPORT','Silence');n+=1
 s=dict(status='ASSIGNED_NAME',identity='a',confirmed=True)
 def x(a,b,**kw):return dict(start_sec=a,end_sec=b,segment_index=0,reference_identity='a',name_status='correct_name',assigned_state=s,**kw)
 need(stable_runs([x(0,.25),x(.25,.5)])[0]['criterion_attainment_sec']==.5,'Attainment not onset');n+=1
 need(not stable_runs([x(0,.2),x(.3,.6)]),'Gap cannot bridge');n+=1
 need(not stable_runs([x(0,.2),dict(x(.2,.6),name_status='unknown_name')]),'Unknown breaks');n+=1
 need(not stable_runs([dict(x(0,1),assigned_state=dict(s,confirmed=False))]),'Tentative not stable');n+=1
 need(len(stable_runs([x(0,.5),dict(x(.5,1),segment_index=1)]))==2,'Occurrence boundary');n+=1
 def e(kind,sec,p=None):return dict(event_type=kind,wall_time_utc=f'2026-01-01T00:00:{sec:06.3f}+00:00',payload=p or {})
 clock,_=wall_context([e('source_started',0),e('session_completed',2)]);need(clock['valid'] and clock['horizon_sec']==2,'Actual wall origin');n+=1
 clock,_=wall_context([e('source_started',0),e('speaker_decision',1),e('speaker_decision',.5),e('session_completed',2)]);need(not clock['valid'],'Backward clock remains unavailable');n+=1
 for events in ([e('session_completed',2)],[e('source_started',0),e('source_started',1),e('session_completed',2)]):
  try:wall_context(events)
  except ValueError:n+=1
  else:raise AssertionError('Invalid wall authority')
 profiles={'p':dict(display_name='A',metadata_identity='a')}
 p=dict(utterance_id='u',text='x',source_start_sec=0,source_end_sec=.5,latest_label='A',latest_known_name='A',latest_known_profile_id='p',latest_naming_state='confirmed')
 records=[(1,e('transcript_partial',1,p),1),(2,e('transcript_label_revision',1.25,dict(p,text=None,source_start_sec=None,source_end_sec=None,latest_label='Unknown',latest_known_name=None,latest_known_profile_id=None)),1.25)]
 intervals,start=row_intervals(records,2,[t],profiles,True,16000)
 need(intervals[1]['arrived_span']==[[0,8000]] and intervals[1]['name_status']=='unknown_name','Revision retains arrived span');n+=1
 need(abs(sum(x['end_sec']-x['start_sec'] for x in intervals)-1)<1e-12,'Wall row closes');n+=1
 blank=dict(p,text=' ',source_end_sec=.75)
 empty_records=[records[0],(2,e('transcript_final',1.25,blank),1.25),(3,e('transcript_label_revision',1.5,dict(p,text=None)),1.5)]
 empty_intervals,_=row_intervals(empty_records,2,[t],profiles,True,16000)
 need(empty_intervals[1]['name_status']=='no_readable_text' and empty_intervals[1]['arrived_span']==[[0,12000]],'Empty actual ASR clears readable state and updates span');n+=1
 need(empty_intervals[2]['name_status']=='no_readable_text' and not stable_runs(empty_intervals),'Revision cannot resurrect old readable text');n+=1
 for text in (None,17):
  try:row_intervals([(0,e('transcript_partial',1,dict(p,text=text)),1)],2,[t],profiles,True,16000)
  except ValueError:n+=1
  else:raise AssertionError('Nonstring actual ASR text admitted')
 closure=dict(state='COMPLETED',finalization_error=None,live_lanes_at_finalization=[],resident_bundle_lease_retained=False,event_and_transcript_handles_closed=True,finished_utc='2026-01-01T00:00:02.100+00:00')
 value=dict(case_id='x',profile_id='c',stream='O0',identity_tap='O0',duration_sec=1.,decisions=[dict(evidence_id='embedding:1')])
 support=dict(output_mappings={'O0':dict(source_with_rir_to_output_offset_samples=0)},all_speaker_reference_complete=True,
  turns=[dict(segment_index=0,source_id='s',whole_clip_bin='1_to_2s',activity_available=True,file_support=[[0,16000]],active_ranges=[[0,16000]])])
 gallery=dict(profiles=[dict(profile_id='p',display_name='A',metadata_identity='a')],available_identities=['a'],intended_identities=['a'],gallery_condition='FIXED_ROTATION_A',enrollment_tier=15)
 admission=dict(source_kind='CANONICAL_SINGLE_SCENE_PAIR',realtime=True,native_session_complete=True,source_offset_samples=0,inserted_gap_samples=0,case_id='x',profile_id='c',asr_tap='O0',identity_tap='O0')
 d=dict(evidence_id='embedding:1',source_start_sec=0.,source_end_sec=.25,available_at_sec=.2,known_name='A',known_profile_id='p',display_label='A',naming_state='confirmed')
 events=[e('source_started',0),e('speaker_decision',.25,d),e('transcript_partial',.3,p),e('session_completed',2)]
 out=analyze(events,value,support,gallery,{('x',0):dict(source_id='s',identity='a')},admission,closure)
 need(out['turns'][0]['first_correct_decision_delay_sec']==.25,'Actual emission not modeled availability');n+=1
 need(abs(out['turns'][0]['first_stable_retained_row_delay_sec']-.8)<1e-6,'Full API causal stable attainment');n+=1
 need(out['clock']['end_utc']==closure['finished_utc'],'Terminal closure horizon');n+=1
 mixed=dict(support,all_speaker_reference_complete=False)
 out=analyze(events,value,mixed,gallery,{('x',0):dict(source_id='s',identity='a')},admission,closure)
 need(out['turns'][0]['first_correct_decision_status']=='INCOMPLETE_REFERENCE' and out['retained_rows'][0]['first_correct_status']=='UNQUALIFIED_REFERENCE','Incomplete excluded from eligible never');n+=1
 absent=dict(gallery,available_identities=[],profiles=[])
 out=analyze(events,value,support,absent,{('x',0):dict(source_id='s',identity='a')},admission,closure)
 need(out['turns'][0]['first_correct_decision_status']=='CORRECT_NAME_UNAVAILABLE_IN_ACTUAL_GALLERY','Absent identity cannot attain correct');n+=1
 late=[events[0],events[1],e('transcript_partial',1.9,p),events[-1]]
 out=analyze(late,value,support,gallery,{('x',0):dict(source_id='s',identity='a')},admission,closure)
 need(out['retained_rows'][0]['row_lifetime_below_stable_criterion'] and out['retained_rows'][0]['first_stable_status']=='RIGHT_CENSORED_AT_TERMINAL_CLOSURE','Short row lifetime censored');n+=1
 out=analyze(events,value,dict(support,turns=[]),gallery,{},admission,closure)
 need(out['strict_empty']['assigned_decision_emissions']==1 and out['strict_empty']['assigned_name_retained_rows']==1 and out['strict_empty']['assigned_name_readable_emissions']==1 and abs(out['strict_empty']['assigned_name_retained_row_sec']-1.8)<1e-9,'Empty controls retain assigned row exposure');n+=1
 need(out['retained_rows'][0]['first_correct_status']=='UNQUALIFIED_REFERENCE' and not out['stable_retained_runs'],'Empty never becomes fake correct identity');n+=1
 need(stable_runs([x(.2,.7)])[0]['criterion_attainment_sec']==.7,'UTC microsecond exact threshold');n+=1
 return dict(status='PASS',checks=n,models=0,predictions_scored=0)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--self-test',action='store_true',required=True);ap.add_argument('--output');a=ap.parse_args();r=fixtures()
 r['sources']=[dict(path=str(p),bytes=len(p.read_bytes()),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (Path(__file__),Path(__file__).with_name('README_S6C_PACED_NAME_EMISSIONS.md'),Path(names.__file__))]
 if a.output:
  with Path(a.output).open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
 print(json.dumps(r))
