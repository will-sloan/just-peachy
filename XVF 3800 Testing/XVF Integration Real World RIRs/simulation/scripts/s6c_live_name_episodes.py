"""Additive source-support name episodes; README_S6C_LIVE_NAME_EPISODES.md."""
from __future__ import annotations
import argparse,csv,hashlib,io,json
from collections import Counter,defaultdict
from pathlib import Path
import s6c_name_analysis_v3 as names
core=names.core
RATE=names.RATE
POLICY={
 'schema':'jp_s6c_live_name_episodes.v1',
 'unit':'One maximal contiguous sole-active interval carrying the same assigned metadata identity within one source occurrence.',
 'split':'Split on an assigned-identity change, unresolved/expired state, silence/overlap gap, or occurrence boundary. Confirmation-state changes alone do not split.',
 'clock':'The unchanged V3 modeled-availability timeline with0.75s source-evidence expiry; not phonetic onset or wall-paced latency.',
 'population':'ENROLLED, INTENDED_BUT_UNAVAILABLE, WITHHELD_OR_UNSELECTED and NO_GALLERY_CONTROL remain separate. Complete-reference and incomplete-target support remain separate.',
 'end':'Observed immediate correction only when a contiguous sole-support atom has a correct name. Unknown/expiry is abstention, another wrong identity is replacement, and a support boundary is censored.',
 'retained_rows':'Not read or pooled into these episodes; transcript-row episodes/exposure remain the separate original V3 outputs.',
 'unresolvable_names':'V3 maps undeclared assignments to metadata identity None. Their samples and episodes are explicit subsets of wrong-known exposure, but different foreign IDs/names are not distinguishable and contiguous foreign assignments may merge.',
 'scope':'No model, policy replay, tuning or word/anonymous rescore. Original naming sample partitions are exactly reproduced per turn.'
}

def checked_table(binding):
 raw=Path(binding['path']).read_bytes()
 if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('Changed table bytes')
 return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))

def atomize(timeline,ranges,truth):
 if ranges is None:return None
 if ranges!=names.union(ranges):raise ValueError('Canonical disjoint support intervals required')
 if timeline:
  if timeline[0]['start']!=0 or any(a['end']!=b['start'] for a,b in zip(timeline,timeline[1:])):raise ValueError('Timeline must cover capture without gaps')
  if any(type(x[k]) is not int for x in timeline for k in ('start','end')) or any(x['start']>=x['end'] for x in timeline):raise ValueError('Invalid timeline samples')
 for a,b in ranges:
  if type(a) is not int or type(b) is not int or a<0 or b<=a or not timeline or b>timeline[-1]['end']:raise ValueError('Invalid support samples')
 out=[]
 for r in timeline:
  for a,b in names.intersection([[r['start'],r['end']]],ranges):
   out.append(dict(start_sample=a,end_sample=b,status=names.status_against(r,truth),assigned_identity=r['identity'],assignment_status=r['status']))
 return out

def episodes(timeline,ranges,truth):
 atoms=atomize(timeline,ranges,truth)
 if atoms is None:return None
 merged=[]
 for a in atoms:
  key=(a['status'],a['assigned_identity'],a['assignment_status'])
  if merged and merged[-1]['end_sample']==a['start_sample'] and (merged[-1]['status'],merged[-1]['assigned_identity'],merged[-1]['assignment_status'])==key:merged[-1]['end_sample']=a['end_sample']
  else:merged.append(dict(a))
 out=[]
 for i,a in enumerate(merged):
  if a['status']=='unknown_name':continue
  nxt=merged[i+1] if i+1<len(merged) and merged[i+1]['start_sample']==a['end_sample'] else None
  end='SUPPORT_BOUNDARY_CENSORED' if nxt is None else 'CORRECT_NAME_OBSERVED' if nxt['status']=='correct_name' else 'UNKNOWN_OR_EXPIRED_ABSTENTION' if nxt['status']=='unknown_name' else 'OTHER_WRONG_IDENTITY'
  out.append(dict(a,duration_samples=a['end_sample']-a['start_sample'],duration_sec=(a['end_sample']-a['start_sample'])/RATE,end_status=end))
 return out

def mapping_available(turn):
 return turn['sole'] is not None

def fixtures():
 U=lambda a,b:dict(start=a,end=b,status='UNKNOWN_NAME',identity=None,confirmed=False)
 K=lambda a,b,p='x',c=False:dict(start=a,end=b,status='ASSIGNED_NAME',identity=p,confirmed=c)
 checks=[]
 def check(ok,name):
  if not ok:raise AssertionError(name)
  checks.append(name)
 check(len(episodes([K(0,5),K(5,10,c=True)],[[0,10]],'truth'))==1,'confirmation alone does not split')
 check(len(episodes([K(0,5),K(5,10,'y')],[[0,10]],'truth'))==2,'different wrong identity splits')
 x=episodes([K(0,5),U(5,7),K(7,10)],[[0,10]],'truth')
 check(len(x)==2 and x[0]['end_status']=='UNKNOWN_OR_EXPIRED_ABSTENTION','Unknown interrupts and is abstention')
 check(len(episodes([K(0,10)],[[0,4],[6,10]],'truth'))==2,'sole-support gap splits')
 x=episodes([K(0,5),K(5,10,'truth')],[[0,10]],'truth')
 check(x[0]['end_status']=='CORRECT_NAME_OBSERVED' and x[1]['status']=='correct_name','observed immediate correction classified')
 check(episodes([K(0,10)],[], 'truth')==[],'zero support is no episodes')
 check(episodes([K(0,10)],None,'truth') is None,'unmapped stays missing')
 check(mapping_available(dict(sole=[],activity_available=False)) and not mapping_available(dict(sole=None,activity_available=False)),'V3 false-activity zero remains mapped; only None is missing')
 check(episodes([U(0,10)],[[0,10]],'truth')==[],'Unknown earns no assigned episode')
 check(episodes([K(0,10)],[[2,8]],'truth')[0]['duration_samples']==6,'clip to source support')
 check(episodes([K(0,10)],[[0,10]],'truth')[0]['end_status']=='SUPPORT_BOUNDARY_CENSORED','capture/support boundary is censored')
 line=names.state_timeline([dict(available_at_sec=.1,source_end_sec=.2,known_name='Research X',known_profile_id='p',naming_state='confirmed',display_label='Research X')],16000,{'p':dict(display_name='Research X',metadata_identity='x')})
 es=episodes(line,[[0,16000]],'truth')
 check(len(es)==1 and es[0]['start_sample']==1600 and es[0]['end_sample']==15200 and es[0]['end_status']=='UNKNOWN_OR_EXPIRED_ABSTENTION','actual V3 availability/expiry reused')
 for bad in ([[5,10],[0,4]],[[0,11]]):
  try:episodes([K(0,10)],bad,'truth')
  except ValueError:checks.append('invalid support rejected')
  else:raise AssertionError('Invalid support admitted')
 check(sum(e['duration_samples'] for e in episodes([K(0,5),K(5,10,'truth')],[[0,10]],'truth'))==10,'assigned duration partition')
 foreign=[dict(start=0,end=5,status='UNDECLARED_ASSIGNED_NAME',identity=None,confirmed=False),dict(start=5,end=10,status='UNDECLARED_ASSIGNED_NAME',identity=None,confirmed=False)]
 check(len(episodes(foreign,[[0,10]],'truth'))==1 and episodes(foreign,[[0,10]],'truth')[0]['status']=='wrong_known_name','unresolvable foreign assignments explicitly merge under V3 identity projection')
 return dict(status='PASS',checks=checks,count=len(checks))

def run(args):
 rp=args.name_receipt if args.name_receipt.is_absolute() else core.REPORT/args.name_receipt
 rb=core.bind(rp,args.name_receipt_sha);receipt=core.verified(rb)
 if receipt.get('schema')!='s6c_name_metrics.v3' or receipt.get('status')!='COMPLETE_REQUESTED_NAME_INDEX' or receipt['failed_or_missing'] or receipt['requested']!=receipt['scored']:raise ValueError('Complete source-bound V3 naming receipt required')
 for b in receipt['codes']:core.bind(b['path'],b['sha256'])
 if core.bind(Path(names.__file__)) not in receipt['codes']:raise ValueError('Loaded V3 naming source differs')
 ib=receipt['index'];index=core.verified(ib);bank=core.verified(receipt['bank']);scenes={s['case_id']:s for s in bank['scenes']}
 expected=core.expected_grid(index,set(scenes))
 if index.get('status')!='COMPLETE' or len(index['rows'])!=len(expected) or len(expected)!=receipt['scored']:raise ValueError('Complete exact source grid required')
 covered=[b for b in receipt['tables'] if Path(b['path']).name=='COVERAGE.csv']
 if len(covered)!=1:raise ValueError('One exact coverage table required')
 rows=checked_table(covered[0]);bykey={}
 for row in rows:
  k=(*core.route_key(row),row['case_id'])
  if k in bykey or row['status']!='SCORED':raise ValueError('Duplicate/failed source coverage')
  bykey[k]=row
 if set(bykey)!=expected:raise ValueError('Coverage/index grid mismatch')
 qraw=core.verified(receipt['Q'])['rows'];q={(r['case_id'],r['segment_index']):r for r in qraw}
 if len(q)!=777 or len(qraw)!=777:raise ValueError('Exact777 occurrence map required')
 mb=receipt['scorer_map'];original=core.verified(mb);done=core.verified(receipt['enrollment_completion'])
 if done.get('status')!='COMPLETE' or mb not in done['outputs']:raise ValueError('Original completed gallery-map authority required')
 docs=[]
 for b in receipt['scorer_map_extensions']:
  d=core.verified(b['scorer_map']);c=core.verified(b['completion']);p=core.verified(b['plan'])
  if c.get('status')!='COMPLETE' or b['scorer_map'] not in c['outputs'] or c['plan']!=b['plan'] or d['plan']!=b['plan'] or mb not in p['bindings']:raise ValueError('Gallery extension authority differs')
  docs.append(d)
 scoremap=names.extensions.append_map(mb,original,docs,set(scenes))
 output=core.REPORT/args.output_subdir
 if Path(args.output_subdir).is_absolute() or core.REPORT.resolve() not in output.resolve().parents or output.exists():raise ValueError('Fresh contained output required')
 output.mkdir(parents=True)
 turnrows=[];episoderows=[];sources=[];emptyrows=[];supportcache={};comparisons=0
 for n,item in enumerate(index['rows'],1):
  key=(*core.route_key(item),item['case_id']);base=dict(profile_id=key[0],stream=key[1],identity_tap=key[2],case_id=key[3])
  source_binding=json.loads(bykey[key]['result']);score=core.verified(source_binding);sb=score['source_bindings']
  if (*core.route_key(score),score['case_id'])!=key or score['schema']!='s6c_name_metrics.v3':raise ValueError('Score route/schema mismatch')
  if sb['prediction']!=item['result'] or sb['Q']!=receipt['Q'] or sb['bank']!=receipt['bank'] or sb['codes']!=receipt['codes'] or sb['scorer_gallery_map']!=mb or sb['scorer_map_extensions']!=receipt['scorer_map_extensions'] or sb['registry_sources']!=receipt['registry_sources']:raise ValueError('Score source chain differs')
  value=core.verified(item['result']);core.validate_payload(value,item)
  support_binding=sb['support'];sk=core.digest(support_binding)
  if sk not in supportcache:supportcache[sk]=core.verified(support_binding)['support']
  support=supportcache[sk];names.validate_support(scenes[key[3]],support)
  gallery=names.gallery_for(value,scoremap);profiles={p['profile_id']:p for p in gallery['profiles']}
  if score['actual_gallery']!=gallery['manifest'] or score['gallery_loaded_count']!=len(profiles):raise ValueError('Score actual gallery differs')
  line=names.state_timeline(value['decisions'],round(value['duration_sec']*RATE),profiles)
  turns=names.mapped_turns(value,support,q);prior={t['segment_index']:t for t in score['turns']}
  if len(prior)!=len(score['turns']) or set(prior)!={t['segment_index'] for t in turns}:raise ValueError('Source occurrence identity mismatch')
  population='COMPLETE_REFERENCE' if support['all_speaker_reference_complete'] else 'INCOMPLETE_KNOWN_TARGET'
  for t in turns:
   old=prior[t['segment_index']];roster=names.roster_status(t['metadata_identity'],gallery)
   if any(old[k]!=t[k] for k in ('segment_index','source_id','metadata_identity','activity_available')) or old['roster_status']!=roster:raise ValueError('Turn metadata/roster mismatch')
   mapped=mapping_available(t)
   ranges=t['sole'] if mapped else None;es=episodes(line,ranges,t['metadata_identity'])
   row=dict(**base,population=population,gallery_condition=gallery['gallery_condition'],enrollment_tier=gallery['enrollment_tier'],segment_index=t['segment_index'],source_id=t['source_id'],metadata_identity=t['metadata_identity'],roster_status=roster,whole_clip_bin=t['whole_clip_bin'],activity_available=t['activity_available'],mapped=bool(mapped))
   if mapped:
    origin=t['file_support'][0][0]/RATE if t['file_support'] else None
    actual=names.integrate(line,ranges,t['metadata_identity'],origin)
    for k in ('sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples'):
     if actual[k]!=old[k]:raise ValueError('Original V3 per-turn sample partition changed: '+k)
     row[k]=actual[k];comparisons+=1
    for status in ('correct_name','wrong_known_name'):
     chosen=[e for e in es if e['status']==status]
     if sum(e['duration_samples'] for e in chosen)!=actual[status+'_samples']:raise ValueError('Episode/sample integral differs')
     row[status+'_episodes']=len(chosen);row[status+'_affected_turn']=bool(chosen)
    undeclared=[e for e in es if e['assignment_status']=='UNDECLARED_ASSIGNED_NAME']
    row.update(undeclared_assigned_samples=sum(e['duration_samples'] for e in undeclared),undeclared_assigned_episodes=len(undeclared),undeclared_assigned_affected_turn=bool(undeclared))
    for i,e in enumerate(es):episoderows.append(dict(**row,episode_index=i,**e))
   else:
    if old.get('sole_active_samples') is not None:raise ValueError('Missing support differs from original')
    for k in ('sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples','correct_name_episodes','wrong_known_name_episodes','correct_name_affected_turn','wrong_known_name_affected_turn','undeclared_assigned_samples','undeclared_assigned_episodes','undeclared_assigned_affected_turn'):row[k]=None
   turnrows.append(row)
  if not turns:
   count=sum(x['end']-x['start'] for x in line if x['status']!='UNKNOWN_NAME')
   if not score['strict_empty']['applicable'] or count!=score['strict_empty']['live_assigned_name_samples']:raise ValueError('Empty control mismatch')
   emptyrows.append(dict(**base,capture_samples=round(value['duration_sec']*RATE),assigned_name_samples=count,scope='Source-empty control, not a stranger occurrence'))
  sources.append(dict(**base,name_score=source_binding,prediction=item['result'],support=support_binding))
  if n%240==0:print(json.dumps(dict(phase='LIVE_NAME_EPISODE_SUPPLEMENT',processed=n,requested=len(index['rows']))),flush=True)
 summary=[]
 for route in sorted({core.route_key(r) for r in index['profile_routes']}):
  for pop in ('ALL_KNOWN_TARGET_SUPPORT','COMPLETE_REFERENCE','INCOMPLETE_KNOWN_TARGET'):
   for roster in ('ALL','ENROLLED','INTENDED_BUT_UNAVAILABLE','WITHHELD_OR_UNSELECTED','NO_GALLERY_CONTROL'):
    chosen=[t for t in turnrows if core.route_key(t)==route and (pop=='ALL_KNOWN_TARGET_SUPPORT' or t['population']==pop) and (roster=='ALL' or t['roster_status']==roster)]
    erows=[e for e in episoderows if core.route_key(e)==route and (pop=='ALL_KNOWN_TARGET_SUPPORT' or e['population']==pop) and (roster=='ALL' or e['roster_status']==roster)]
    row=dict(profile_id=route[0],stream=route[1],identity_tap=route[2],population=pop,roster_status=roster,source_turns=len(chosen),mapped_turns=sum(t['mapped'] for t in chosen),unmapped_turns=sum(not t['mapped'] for t in chosen),zero_sole_support_turns=sum(t['mapped'] and t['sole_active_samples']==0 for t in chosen))
    row['activity_unavailable_turns']=sum(not t['activity_available'] for t in chosen)
    for k in ('sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples','correct_name_episodes','wrong_known_name_episodes','correct_name_affected_turn','wrong_known_name_affected_turn','undeclared_assigned_samples','undeclared_assigned_episodes','undeclared_assigned_affected_turn'):row[k]=sum(t.get(k) or 0 for t in chosen)
    row['wrong_known_affected_people']=len({t['metadata_identity'] for t in chosen if t.get('wrong_known_name_affected_turn')})
    row['wrong_episode_end_counts']=dict(Counter(e['end_status'] for e in erows if e['status']=='wrong_known_name'))
    summary.append(row)
 tables={'PROFILE_LIVE_EPISODES.csv':summary,'TURN_LIVE_EPISODES.csv':turnrows,'ASSIGNED_NAME_EPISODES.csv':episoderows,'SOURCE_BINDINGS.csv':sources,'EMPTY_CONTROL_RESULTS.csv':emptyrows}
 for name,rows in tables.items():core.csv_write(output/name,rows)
 result=dict(schema=POLICY['schema'],status='COMPLETE',source_name_receipt=rb,source_index=ib,source_coverage=covered[0],policy=POLICY,cells=len(sources),source_occurrences=len(turnrows),assigned_episodes=len(episoderows),sample_partition_checks=comparisons,empty_cells=len(emptyrows),tests=fixtures(),codes=[core.bind(Path(__file__)),core.bind(Path(__file__).with_name('README_S6C_LIVE_NAME_EPISODES.md'))],tables=[core.bind(output/name) for name in tables],limitations=['Underlying source support and causal timeline retain the existing V3 assumptions.','Native receipt/model bytes are transitively bound through predictions, not independently re-opened by this supplement.','This descriptive episode extension was added after naming outcomes; it is not a new held-out experiment.'])
 core.save(output/'LIVE_NAME_EPISODE_RECEIPT.json',result)
 return {k:result[k] for k in ('status','cells','source_occurrences','assigned_episodes','sample_partition_checks','empty_cells')}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--name-receipt',type=Path);p.add_argument('--name-receipt-sha');p.add_argument('--output-subdir',default='full_n01_live_name_episodes_v1');p.add_argument('--test',action='store_true');a=p.parse_args()
 if not a.test and (a.name_receipt is None or a.name_receipt_sha is None):p.error('Explicit completed naming receipt path and SHA required')
 print(json.dumps(fixtures() if a.test else run(a),indent=2,allow_nan=False))
