"""Scorer-only S6C identity and retained-name exposure. README_S6C_NAME_ANALYSIS.md."""
from __future__ import annotations
import argparse,bisect,math
from collections import Counter,defaultdict
from pathlib import Path
import s6c_analysis as core
from s6a_support_metrics import mapped_ranges,union,intersection,subtract,samples,validate_support

RATE=16000
POLICY=dict(schema='s6c_name_metrics.v2',source_evidence_expiry_sec=.75,
 stable_contiguous_correct_confirmed_sec=.5,
 reference='Corpus-qualified frozen source metadata identity, never anonymous Hungarian assignment',
 stable='At least0.5 contiguous seconds of correct confirmed name on sole-active source support. Preset descriptive criterion, not runtime confirmation rule.',
 timeline='Modeled availability and estimated source support, not phonetic latency. Silence/overlap interrupts contiguous support.',
 exposure='Retained transcript rows integrated separately, classified using the most recent arrived ASR source span; no final-span backfill or word-time inference.')

def named(row,profiles,*,transcript=False):
 prefix='latest_' if transcript else ''
 name=row.get(prefix+'known_name');pid=row.get(prefix+'known_profile_id')
 state=row.get(prefix+'naming_state',row.get('naming_state','unresolved'))
 label=row.get('latest_label',row.get('display_label'))
 if name is None and pid is None:return dict(status='UNKNOWN_NAME',identity=None,confirmed=False)
 if not isinstance(name,str) or not name or pid not in profiles or profiles[pid]['display_name']!=name:
  return dict(status='UNDECLARED_ASSIGNED_NAME',identity=None,confirmed=False)
 if label is not None and label not in (name,name+' (tentative)'):
  raise ValueError('Published name metadata contradicts actual display label')
 return dict(status='ASSIGNED_NAME',identity=profiles[pid]['metadata_identity'],confirmed=state=='confirmed')

def gallery_for(value,scoremap):
 ident=value.get('identity',{});binding=ident.get('gallery')
 if binding is None:
  if any(d.get('known_name') or d.get('known_profile_id') for d in value['decisions']):raise ValueError('Named prediction lacks actual gallery binding')
  return dict(gallery_condition='NONE',enrollment_tier=None,case_id=None,intended_identities=[],available_identities=[],unavailable_identities=[],profiles=[],eligibility='NO_GALLERY_CONTROL',manifest=None)
 if 'manifest' in binding:binding=binding['manifest']
 settings=ident.get('profile',{}).get('metadata',{})
 condition=value.get('gallery_condition',ident.get('gallery_condition',settings.get('gallery_condition')))
 tier=value.get('enrollment_tier',ident.get('enrollment_tier',settings.get('enrollment_tier')))
 matches=[r for r in scoremap['rows'] if r['manifest']==binding and r['gallery_condition']==condition and r['enrollment_tier']==tier and r['case_id'] in (None,value['case_id'])]
 if len(matches)!=1:raise ValueError('Exact actual gallery condition/tier/case must resolve one scorer-only map row')
 row=matches[0]
 actual=core.verified(binding)
 if sorted((p['profile_id'],p['display_name']) for p in actual['profiles'])!=sorted((p['profile_id'],p['display_name']) for p in row['profiles']):raise ValueError('Scorer map differs from actual loaded gallery profiles')
 loaded=value.get('snapshot',{}).get('scheduler',{}).get('identity',{}).get('gallery')
 if loaded is None or loaded.get('manifest')!=binding or loaded.get('loaded_count')!=len(row['profiles']):raise ValueError('Actual resolver load receipt is required and must match scorer roster, including explicit count0 galleries')
 return row

def mapped_turns(value,support,q):
 tap=value.get('identity_tap',value['stream']);length=round(value['duration_sec']*RATE)
 shift=support['output_mappings'][tap]['source_with_rir_to_output_offset_samples']
 rows=[]
 for t in support['turns']:
  truth=q[value['case_id'],t['segment_index']]
  if truth['source_id']!=t['source_id']:raise ValueError('Q occurrence/support source identity differs')
  mapped={k:mapped_ranges(t[k],shift,length) if shift is not None else None for k in ('file_support','active_ranges')}
  rows.append(dict(segment_index=t['segment_index'],source_id=t['source_id'],metadata_identity=truth['identity'],whole_clip_bin=t['whole_clip_bin'],activity_available=t['activity_available'],**mapped))
 if shift is not None:
  for t in rows:t['sole']=subtract(t['active_ranges'],union([r for o in rows if o is not t for r in o['active_ranges']]))
 else:
  for t in rows:t['sole']=None
 return sorted(rows,key=lambda t:(t['file_support'][0][0] if t['file_support'] else math.inf,t['segment_index']))

def roster_status(identity,gallery):
 if gallery['gallery_condition']=='NONE':return 'NO_GALLERY_CONTROL'
 if identity in gallery['available_identities']:return 'ENROLLED'
 if identity in gallery['intended_identities']:return 'INTENDED_BUT_UNAVAILABLE'
 return 'WITHHELD_OR_UNSELECTED'

def state_timeline(decisions,length,profiles):
 stamps=[round(d['available_at_sec']*RATE) for d in decisions]
 if stamps!=sorted(stamps):raise ValueError('Name decisions not in actual causal availability order')
 boundaries=sorted({0,length}|{x for d,t in zip(decisions,stamps) for x in (t,round((d['source_end_sec']+POLICY['source_evidence_expiry_sec'])*RATE)) if 0<x<length})
 rows=[]
 for a,b in zip(boundaries,boundaries[1:]):
  i=bisect.bisect_right(stamps,a)-1
  state=named(decisions[i],profiles) if i>=0 and a<round((decisions[i]['source_end_sec']+POLICY['source_evidence_expiry_sec'])*RATE) else dict(status='UNKNOWN_NAME',identity=None,confirmed=False)
  rows.append(dict(start=a,end=b,**state))
 return rows

def status_against(state,truth):
 if state['status']=='UNKNOWN_NAME':return 'unknown_name'
 if state['status']=='ASSIGNED_NAME' and state['identity']==truth:return 'correct_name'
 return 'wrong_known_name'

def integrate(timeline,ranges,truth,origin):
 counts=Counter();correct=[];confirmed=[];known=[]
 for row in timeline:
  pieces=intersection([[row['start'],row['end']]],ranges)
  n=samples(pieces);status=status_against(row,truth);counts[status]+=n
  if status!='unknown_name':known.extend(pieces)
  if status=='correct_name':
   correct.extend(pieces)
   if row['confirmed']:confirmed.extend(pieces)
 stable=[(a,b) for a,b in union(confirmed) if b-a>=round(POLICY['stable_contiguous_correct_confirmed_sec']*RATE)]
 first=lambda rs:(min(a for a,b in rs)/RATE-origin if rs and origin is not None else None)
 result=dict(sole_active_samples=samples(ranges),correct_name_samples=counts['correct_name'],wrong_known_name_samples=counts['wrong_known_name'],unknown_name_samples=counts['unknown_name'],
  first_any_name_wait_sec=first(known),first_correct_name_wait_sec=first(correct),first_confirmed_correct_name_wait_sec=first(confirmed),first_stable_correct_name_wait_sec=(first(stable)+POLICY['stable_contiguous_correct_confirmed_sec']) if stable else None,
  retrospective_stable_interval_onset_wait_sec=first(stable),
  stable_name_observation_sec=sum(b-a for a,b in stable)/RATE)
 assert sum(result[k] for k in ('correct_name_samples','wrong_known_name_samples','unknown_name_samples'))==result['sole_active_samples']
 for key in ('first_any_name','first_correct_name','first_confirmed_correct_name','first_stable_correct_name'):
  result[key+'_status']='OBSERVED' if result[key+'_wait_sec'] is not None else 'NO_SOLE_SUPPORT' if not ranges else 'RIGHT_CENSORED_AT_END_OF_OBSERVED_SUPPORT'
 result['censor_wait_sec']=max(b for a,b in ranges)/RATE-origin if ranges and origin is not None else None
 return result

def single_reference(span,turns,complete):
 if not complete:return 'INCOMPLETE_REFERENCE',None
 if any(t['active_ranges'] is None for t in turns):return 'UNAVAILABLE_ALIGNMENT',None
 if span is None:return 'UNAVAILABLE_ARRIVED_SOURCE_SPAN',None
 people={t['metadata_identity'] for t in turns if samples(intersection(span,t['active_ranges']))>0}
 return ('ONE_REFERENCE_PERSON',next(iter(people))) if len(people)==1 else ('MULTIPLE_REFERENCE_PEOPLE',None) if people else ('NO_REFERENCE_ACTIVE_SUPPORT',None)

def retained_exposure(value,turns,profiles,complete):
 events=value.get('transcript_events',[]);groups=defaultdict(list)
 for n,e in enumerate(events):
  if e.get('event_type') not in ('transcript_partial','transcript_final','transcript_label_revision'):continue
  uid=e.get('utterance_id',e.get('utterance_index'))
  if uid is None or not core.numeric(e.get('available_at_sec')):raise ValueError('Readable transcript event lacks ID/time')
  groups[str(uid)].append((n,e))
 horizon=max([value['duration_sec']]+[e['available_at_sec'] for e in events if core.numeric(e.get('available_at_sec'))]+[d['available_at_sec'] for d in value['decisions']])
 result=[];changes=[]
 final_ids={str(x['utterance_index']) for x in value['final_transcripts_first']}
 for uid in sorted(set(groups)|final_ids):
  ordered=sorted(groups[uid],key=lambda ne:(ne[1]['available_at_sec'],ne[0]));state=None;last=None;span=None;exposure=Counter();started=None;last_status=None;local_changes=0;wrong_runs=[];wrong_start=None;first_correct=None
  def classify(s,sp):
   refstatus,person=single_reference(sp,turns,complete)
   return (status_against(s,person) if person is not None else 'empty_reference_assigned_name' if complete and not turns and s['status']!='UNKNOWN_NAME' else 'unidentifiable_reference'),refstatus,person
  for _,e in ordered:
   now=e['available_at_sec'];kind=e['event_type']
   readable=kind in ('transcript_partial','transcript_final') and bool(str(e.get('text','')).strip())
   if state is None and not readable:continue
   if state is not None:
    oldstatus,_,_=classify(state,span);exposure[oldstatus]+=now-last
   if readable:
    a,b=e.get('source_start_sec'),e.get('source_end_sec')
    span=[[round(a*RATE),round(b*RATE)]] if core.numeric(a) and core.numeric(b) and b>a else None
   before=state;state=named(e,profiles,transcript=True);afterstatus,rs,person=classify(state,span)
   if started is None:started=now
   if afterstatus=='correct_name' and first_correct is None:first_correct=now
   if afterstatus=='wrong_known_name' and wrong_start is None:wrong_start=now
   if afterstatus!='wrong_known_name' and wrong_start is not None:
    wrong_runs.append(dict(start_sec=wrong_start,end_sec=now,duration_sec=now-wrong_start,end_reason='CORRECTED' if afterstatus=='correct_name' else 'RETRACTED_OR_REFERENCE_CHANGED',right_censored=False));wrong_start=None
   if kind=='transcript_label_revision':
    local_changes+=1
    changes.append(dict(utterance_id=uid,available_at_sec=now,revision_scope=e.get('revision_scope','UNSPECIFIED'),before_name_status=last_status,after_name_status=afterstatus,reference_status=rs,reference_identity=person,wrong_name_introduced=last_status!='wrong_known_name' and afterstatus=='wrong_known_name',correct_name_lost=last_status=='correct_name' and afterstatus!='correct_name',words_changed=bool(e.get('changes_words',False))))
   last=now;last_status=afterstatus
  if state is None:
   result.append(dict(utterance_id=uid,is_final=uid in final_ids,status='UNAVAILABLE_NO_READABLE_EVENT',exposure_available=False));continue
  status,rs,person=classify(state,span);exposure[status]+=horizon-last
  if wrong_start is not None:wrong_runs.append(dict(start_sec=wrong_start,end_sec=horizon,duration_sec=horizon-wrong_start,end_reason='END_OF_OBSERVATION',right_censored=True))
  total=horizon-started
  if abs(sum(exposure.values())-total)>1e-7:raise ValueError('Retained-row exposure does not close')
  result.append(dict(utterance_id=uid,is_final=uid in final_ids,status='SCORED_RETAINED_ROW',exposure_available=True,first_display_time_sec=started,observation_horizon_sec=horizon,retained_row_sec=total,
    correct_name_row_sec=exposure['correct_name'],wrong_known_name_row_sec=exposure['wrong_known_name'],unknown_name_row_sec=exposure['unknown_name'],unidentifiable_reference_row_sec=exposure['unidentifiable_reference'],empty_reference_assigned_name_row_sec=exposure['empty_reference_assigned_name'],
    first_correct_name_from_display_wait_sec=first_correct-started if first_correct is not None else None,first_correct_name_status='OBSERVED' if first_correct is not None else 'RIGHT_CENSORED_AT_RETAINED_ROW_HORIZON',
    final_arrived_span_reference_status=rs,final_arrived_span_identity=person,revision_events=local_changes,wrong_name_episodes=wrong_runs))
 return result,changes

def analyze(value,support,gallery,q):
 profiles={p['profile_id']:p for p in gallery['profiles']}
 if len(profiles)!=len(gallery['profiles']):raise ValueError('Duplicate gallery profile ID')
 turns=mapped_turns(value,support,q);timeline=state_timeline(value['decisions'],round(value['duration_sec']*RATE),profiles)
 turn_results=[]
 for t in turns:
  base={k:t[k] for k in ('segment_index','source_id','metadata_identity','whole_clip_bin','activity_available')};base['roster_status']=roster_status(t['metadata_identity'],gallery)
  if t['sole'] is None:base.update(status='UNAVAILABLE_ALIGNMENT',sole_active_samples=None)
  else:
   origin=t['file_support'][0][0]/RATE if t['file_support'] else None
   base.update(status='SCORED_KNOWN_SOURCE_SUPPORT' if support['all_speaker_reference_complete'] else 'LIMITED_KNOWN_TARGET_SUPPORT',**integrate(timeline,t['sole'],t['metadata_identity'],origin))
   base.update(mapped_file_support_samples=samples(t['file_support']),active_samples=samples(t['active_ranges']),excluded_other_source_overlap_samples=samples(t['active_ranges'])-samples(t['sole']))
  turn_results.append(base)
 people=[]
 for person in sorted({t['metadata_identity'] for t in turns}):
  chosen=[t for t in turns if t['metadata_identity']==person];base=dict(metadata_identity=person,roster_status=roster_status(person,gallery),occurrences=len(chosen))
  if any(t['sole'] is None for t in chosen):base.update(status='UNAVAILABLE_ALIGNMENT',sole_active_samples=None)
  else:
   ranges=union([r for t in chosen for r in t['sole']]);files=union([r for t in chosen for r in t['file_support']]);origin=files[0][0]/RATE if files else None
   base.update(status='SCORED_CHRONOLOGICAL_PERSON',**integrate(timeline,ranges,person,origin))
  people.append(base)
 queries=[];seen_tracks=set();seen_people=set();last_query={}
 resolver=value.get('snapshot',{}).get('scheduler',{}).get('identity',{})
 retirements=resolver.get('recent_retirement_records',[])
 complete_retirements=resolver.get('retired_name_states',0)==len(retirements)
 for d in value['decisions']:
  detail=d.get('identity',{})
  if not detail.get('query_executed'):continue
  track=d.get('tracker_id');span=[[round(d['source_start_sec']*RATE),round(d['source_end_sec']*RATE)]]
  rs,person=single_reference(span,turns,support['all_speaker_reference_complete']);state=named(d,profiles)
  first=track not in seen_tracks
  reset=any(r['track_id']==track and last_query.get(track,-math.inf)<r['available_at_sec']<=d['available_at_sec'] for r in retirements)
  cold=True if first or reset else False if complete_retirements else None
  queries.append(dict(available_at_sec=d['available_at_sec'],source_start_sec=d['source_start_sec'],source_end_sec=d['source_end_sec'],tracker_id=track,
   cold_track_query=cold,cold_warm_status='COLD_NEW_OR_RETIRED_NAME_STATE' if cold is True else 'WARM_RETAINED_NAME_STATE' if cold is False else 'UNAVAILABLE_TRUNCATED_RETIREMENT_HISTORY',first_query_for_lifetime_tracker_id=first,
   first_query_for_reference_person=person not in seen_people if person is not None else None,reference_status=rs,reference_identity=person,
   assigned_name_status=status_against(state,person) if person is not None else 'UNIDENTIFIABLE_REFERENCE',roster_status=roster_status(person,gallery) if person is not None else None,
   unique_clean_sec=detail.get('unique_clean_sec'),disjoint_count=detail.get('disjoint_count'),evidence_kind=detail.get('evidence_kind'),query_executed=True))
  seen_tracks.add(track);last_query[track]=d['available_at_sec']
  if person is not None:seen_people.add(person)
 rows,changes=retained_exposure(value,turns,profiles,support['all_speaker_reference_complete'])
 return dict(schema=POLICY['schema'],case_id=value['case_id'],profile_id=value['profile_id'],stream=value['stream'],identity_tap=value.get('identity_tap',value['stream']),
  gallery_condition=gallery['gallery_condition'],enrollment_tier=gallery['enrollment_tier'],actual_gallery=gallery['manifest'],gallery_loaded_count=len(profiles),gallery_eligibility=gallery['eligibility'],
  turns=turn_results,people=people,queries=queries,retained_rows=rows,name_revisions=changes,policy=POLICY,
  accounting=dict(source_occurrences=len(turn_results),reference_people=len(people),actual_name_queries=len(queries),retained_readable_rows=sum(r['exposure_available'] for r in rows),missing_readable_rows=sum(not r['exposure_available'] for r in rows)),
  strict_empty=dict(applicable=not turns,full_capture_samples=round(value['duration_sec']*RATE) if not turns else None,live_assigned_name_samples=sum(x['end']-x['start'] for x in timeline if x['status']!='UNKNOWN_NAME') if not turns else None,retained_assigned_name_row_sec=sum(x.get('empty_reference_assigned_name_row_sec',0.) for x in rows) if not turns else None,scope='Canonical source-empty control; diagnostic assigned-name output without a deliberate reference speaker, not a verified statement about every environmental sound.'),
  scope='Scorer-only frozen metadata identity. Source support and row exposure are separate denominators; incomplete ambient people remain unknown reference. No Q fitting, anonymous remapping, word timestamps or real-time/CM5 claim.')

def fixtures():
 p={'p':dict(profile_id='p',display_name='Research Person 001',metadata_identity='a')}
 d=dict(known_name='Research Person 001',known_profile_id='p',display_label='Research Person 001',naming_state='confirmed',available_at_sec=.25,source_end_sec=.25)
 line=state_timeline([d],32000,p);a=integrate(line,[[0,32000]],'a',0.)
 assert a['correct_name_samples']==12000 and a['unknown_name_samples']==20000 and a['first_stable_correct_name_wait_sec']==.75 and a['retrospective_stable_interval_onset_wait_sec']==.25
 wrong=integrate(line,[[0,32000]],'stranger',0.);assert wrong['wrong_known_name_samples']==12000 and wrong['first_correct_name_status'].startswith('RIGHT_CENSORED')
 short=integrate(line,[[4000,8000]],'a',0.);assert short['first_correct_name_wait_sec']==.25 and short['first_stable_correct_name_wait_sec'] is None
 assert named({'known_name':None,'known_profile_id':None},p)['status']=='UNKNOWN_NAME'
 assert named({**d,'known_profile_id':'foreign'},p)['status']=='UNDECLARED_ASSIGNED_NAME'
 g=dict(gallery_condition='FIXED_ROTATION_A',available_identities=['a'],intended_identities=['a','b'])
 assert [roster_status(x,g) for x in ('a','b','c')]==['ENROLLED','INTENDED_BUT_UNAVAILABLE','WITHHELD_OR_UNSELECTED']
 ts=[dict(metadata_identity='a',active_ranges=[[0,16000]]),dict(metadata_identity='b',active_ranges=[[16000,32000]])]
 e=dict(utterance_id='u',text='words',latest_label='Research Person 001',latest_known_name='Research Person 001',latest_known_profile_id='p',latest_naming_state='confirmed')
 value=dict(duration_sec=3.,decisions=[],final_transcripts_first=[dict(utterance_index='u')],transcript_events=[dict(e,event_type='transcript_partial',available_at_sec=.5,source_start_sec=0.,source_end_sec=.5),dict(e,event_type='transcript_final',available_at_sec=2.,source_start_sec=0.,source_end_sec=2.)])
 rows,changes=retained_exposure(value,ts,p,True)
 assert rows[0]['correct_name_row_sec']==1.5 and rows[0]['unidentifiable_reference_row_sec']==1. and rows[0]['retained_row_sec']==2.5
 value['transcript_events'][1]=dict(e,event_type='transcript_label_revision',available_at_sec=2.,source_start_sec=1.,source_end_sec=2.,revision_scope='bounded_post_association_name')
 rows,changes=retained_exposure(value,ts,p,True)
 assert rows[0]['correct_name_row_sec']==2.5 and changes[0]['reference_identity']=='a'
 rows,_=retained_exposure({**value,'transcript_events':[]},ts,p,True);assert not rows[0]['exposure_available']
 rows,_=retained_exposure(value,[],p,True);assert rows[0]['empty_reference_assigned_name_row_sec']==2.5 and rows[0]['unidentifiable_reference_row_sec']==0
 from unittest.mock import patch
 binding=dict(path='fixture',bytes=1,sha256='fixture');gallery=dict(manifest=binding,gallery_condition='A',enrollment_tier=5,case_id=None,profiles=[])
 v=dict(case_id='case',decisions=[],identity=dict(gallery=binding,gallery_condition='A',enrollment_tier=5),snapshot={})
 with patch.object(core,'verified',return_value=dict(profiles=[])):
  try:gallery_for(v,dict(rows=[gallery]))
  except ValueError:pass
  else:raise AssertionError('Declared gallery without actual loader evidence accepted')
  v['snapshot']=dict(scheduler=dict(identity=dict(gallery=dict(manifest=binding,loaded_count=0))))
  assert gallery_for(v,dict(rows=[gallery]))==gallery
 return dict(status='PASS',checks=['exact source-expiry integration and denominator closure','stranger known-name exposure is false acceptance','stable criterion attainment follows retrospective interval onset by0.5s','short observed name is distinct from stable criterion','anonymous remains unknown name','undeclared assigned name preserved as error','unavailable intended roster differs from withheld stranger','later multi-person final span does not backfill earlier partial exposure','revision evidence span does not replace arrived ASR span','missing readable events remain unavailable','canonical source-empty assigned names have a distinct visible denominator','declared gallery without actual load receipt rejected','explicit zero-loaded gallery is admitted only with actual load receipt'])

def run(args):
 report=core.REPORT;index_path=args.index if args.index.is_absolute() else report/args.index
 ib=core.bind(index_path);index=core.verified(ib)
 mb=core.bind(report/'enrollment/SCORER_GALLERY_MAP.json');scoremap=core.verified(mb)
 if scoremap.get('status')!='COMPLETE' or scoremap.get('runtime_input') is not False:raise ValueError('Completed evaluator-only gallery map required')
 completion=core.read(report/'enrollment/ENROLLMENT_COMPLETION.json')
 if mb not in completion['outputs']:raise ValueError('Gallery map lacks completed enrollment binding')
 plan=core.verified(scoremap['plan']);qb=plan['query_manifest'];qraw=core.verified(qb)['rows'];q={(r['case_id'],r['segment_index']):r for r in qraw}
 if len(q)!=777 or len(qraw)!=777:raise ValueError('All777 unique Q occurrences required')
 bankb=core.bind(core.BANK,core.BANK_SHA);bank=core.verified(bankb);scenes={s['case_id']:s for s in bank['scenes']}
 expected=core.expected_grid(index,set(scenes));inputs=core.verified(core.bind(core.S6B/'INPUT_INDEX.json',core.INPUT_SHA))['rows'];inputrows={(r['case_id'],r['stream']):r for r in inputs}
 if args.require_complete and (index.get('status')!='COMPLETE' or len(index['rows'])!=len(expected)):raise ValueError('Complete exact declared prediction grid required')
 output=report/args.output_subdir
 if Path(args.output_subdir).is_absolute() or report.resolve() not in output.resolve().parents or output.exists():raise ValueError('Fresh contained output child required')
 output.mkdir(parents=True)
 code=[core.bind(Path(__file__)),core.bind(Path(__file__).with_name('README_S6C_NAME_ANALYSIS.md'))]+[core.bind(core.SIM/'scripts'/n) for n in core.CODES]
 records=[];coverage=[];tables=defaultdict(list)
 for item in index['rows']:
  pid,tap,itap=core.route_key(item);cid=item['case_id'];base=dict(profile_id=pid,stream=tap,identity_tap=itap,case_id=cid)
  try:
   if item.get('status','COMPLETE') not in ('COMPLETE','COMPLETE_REUSED'):raise ValueError('Unsuccessful prediction is not zero name exposure')
   value=core.verified(item['result']);core.validate_payload(value,item);sb=inputrows[cid,itap]['support'];support=core.verified(sb)['support'];validate_support(scenes[cid],support)
   result=analyze(value,support,gallery_for(value,scoremap),q)
   result['source_bindings']=dict(prediction=item['result'],support=sb,scorer_gallery_map=mb,Q=qb,bank=bankb,codes=code)
   target=output/'scores'/pid/cid/(tap+'_ASR_'+itap+'_ID.json');core.save(target,result);records.append(result);coverage.append(dict(**base,status='SCORED',result=core.bind(target)))
   for key in ('turns','people','queries','retained_rows','name_revisions'):
    tables[key].extend({**base,'gallery_condition':result['gallery_condition'],'enrollment_tier':result['enrollment_tier'],**r} for r in result[key])
   if result['strict_empty']['applicable']:tables['EMPTY_CONTROL_RESULTS'].append({**base,**result['strict_empty']})
  except Exception as exc:coverage.append(dict(**base,status='FAILED_ANALYSIS',error=type(exc).__name__+': '+str(exc)))
 present={(r['profile_id'],r['stream'],r['identity_tap'],r['case_id']) for r in coverage}
 for p,t,i,c in sorted(expected-present):coverage.append(dict(profile_id=p,stream=t,identity_tap=i,case_id=c,status='MISSING_PREDICTION'))
 # Pool duration numerators and explicit counts; never average per-turn rates.
 summary=[]
 for pid,tap,itap in sorted({core.route_key(r) for r in index['profile_routes']}):
  chosen=[r for r in records if (r['profile_id'],r['stream'],r['identity_tap'])==(pid,tap,itap)]
  for roster in ('ALL','ENROLLED','INTENDED_BUT_UNAVAILABLE','WITHHELD_OR_UNSELECTED','NO_GALLERY_CONTROL'):
   turns=[t for r in chosen for t in r['turns'] if roster=='ALL' or t['roster_status']==roster]
   row=dict(profile_id=pid,stream=tap,identity_tap=itap,roster_status=roster,scored_scenes=len(chosen),source_turns=len(turns),unmapped_turns=sum(t.get('sole_active_samples') is None for t in turns))
   for k in ('sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples'):row[k]=sum(t.get(k) or 0 for t in turns)
   for key in ('first_any_name','first_correct_name','first_confirmed_correct_name','first_stable_correct_name'):
    xs=[t.get(key+'_wait_sec') for t in turns];row[key+'_observed_turns']=sum(core.numeric(x) for x in xs);row[key+'_missing_turns']=len(xs)-row[key+'_observed_turns'];row[key+'_conditional_wait_sec']=core.inherited.quantiles(xs)
   summary.append(row)
 tables['PROFILE_NAME_RESULTS']=summary;tables['COVERAGE']=coverage
 for name,rows in tables.items():core.csv_write(output/(name.upper()+'.csv'),rows)
 success=index.get('status')=='COMPLETE' and len(records)==len(expected) and all(r['status']=='SCORED' for r in coverage)
 receipt=dict(schema=POLICY['schema'],status='COMPLETE_REQUESTED_NAME_INDEX' if success else 'PARTIAL_WITH_FAILURES',index=ib,scorer_map=mb,enrollment_completion=core.bind(report/'enrollment/ENROLLMENT_COMPLETION.json'),Q=qb,bank=bankb,codes=code,policy=POLICY,
  requested=len(expected),scored=len(records),failed_or_missing=len(expected)-len(records),source_occurrence_outputs=sum(r['accounting']['source_occurrences'] for r in records),tables=[core.bind(output/(n.upper()+'.csv')) for n in tables],tests=fixtures(),prior_executor_lineage=core.bind(report/'independent_review/name_scorer_executor_v1/SOURCE_LINEAGE.json'))
 core.save(output/'NAME_ANALYSIS_RECEIPT.json',receipt)
 if args.require_complete and not success:raise RuntimeError('Name analysis incomplete; inspect preserved COVERAGE')
 return {k:receipt[k] for k in ('status','requested','scored','failed_or_missing','source_occurrence_outputs')}

if __name__=='__main__':
 import json
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=Path);p.add_argument('--output-subdir',default='name_analysis_v1');p.add_argument('--require-complete',action='store_true');p.add_argument('--test',action='store_true');a=p.parse_args()
 if not a.test and a.index is None:p.error('--index required')
 print(json.dumps(fixtures() if a.test else run(a),indent=2,allow_nan=False))
