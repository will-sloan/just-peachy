"""Fixed-competitor E-duration results. README_S6C_COMMON_DURATION_RESULTS_V2.md."""
from collections import defaultdict,Counter
from pathlib import Path
import argparse,csv,io,json,math,hashlib
import tempfile
import s6c_analysis_v3 as core
REPORT=core.REPORT
IDS={'C141':('A',5),'C142':('A',15),'C143':('A',30),'C144':('B',5),'C145':('B',15),'C146':('B',30)}
SAMPLE_KEYS=('sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples')
WAIT_KEYS=('first_any_name_wait_sec','first_correct_name_wait_sec','first_confirmed_correct_name_wait_sec','first_stable_correct_name_wait_sec')
def table(receipt,name):
 matches=[b for b in receipt['tables'] if Path(b['path']).name==name]
 if len(matches)!=1:raise ValueError('Exactly one bound table required '+name)
 b=matches[0];raw=Path(b['path']).read_bytes()
 if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('Changed exact completed table bytes')
 return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))),b
def val(row,key):
 value=row.get(key)
 if value is None or value=='':return None
 result=float(value)
 if not math.isfinite(result):raise ValueError('Nonfinite source metric')
 return result
def corpus(person):
 if person.startswith('CMU_ARCTIC_'):return 'CMU ARCTIC'
 if person.startswith('HIFITTS_'):return 'HiFiTTS'
 if person.startswith('CV_'):return 'Common Voice'
 raise ValueError('Unexpected frozen corpus identity')
def aggregate(rows):
 out=dict(source_occurrences=len(rows),reference_people=len({r['metadata_identity'] for r in rows}),
  missing_source_support_turns=sum(val(r,'sole_active_samples') is None for r in rows))
 for key in SAMPLE_KEYS:
  xs=[val(r,key) for r in rows];out[key]=int(sum(x for x in xs if x is not None))
 for key in WAIT_KEYS:
  xs=[val(r,key) for r in rows];out[key+'_summary']=core.inherited.quantiles(xs)
  out[key+'_statuses']=dict(Counter(r.get(key.replace('_wait_sec','_status'),'MISSING_STATUS') for r in rows))
  out[key+'_observed']=sum(x is not None for x in xs);out[key+'_missing']=sum(x is None for x in xs)
 return out
def turn_key(r):return r['case_id'],int(r['segment_index']),r['source_id'],r['metadata_identity']
def paired(left,right):
 a={turn_key(r):r for r in left};b={turn_key(r):r for r in right}
 if len(a)!=len(left) or len(b)!=len(right) or set(a)!=set(b):raise ValueError('Tier source occurrence populations differ')
 for k in a:
  if a[k]['roster_status']!=b[k]['roster_status']:raise ValueError('Tier changes known/stranger roster membership')
  if val(a[k],'sole_active_samples')!=val(b[k],'sole_active_samples'):raise ValueError('Tier source-support denominator differs')
 la,rb=aggregate(left),aggregate(right);out=dict(paired_occurrences=len(a),paired_people=la['reference_people'])
 for key in SAMPLE_KEYS:out['left_'+key]=la[key];out['right_'+key]=rb[key];out['right_minus_left_'+key]=rb[key]-la[key]
 delays=[]
 for key in WAIT_KEYS:
  both=[(val(a[k],key),val(b[k],key)) for k in a if val(a[k],key) is not None and val(b[k],key) is not None]
  only_left=sum(val(a[k],key) is not None and val(b[k],key) is None for k in a)
  only_right=sum(val(a[k],key) is None and val(b[k],key) is not None for k in a)
  delays.append(dict(metric=key,paired_occurrences=len(a),both_observed=len(both),left_only_observed=only_left,right_only_observed=only_right,
   neither_observed=len(a)-len(both)-only_left-only_right,
   conditional_right_minus_left_wait_sec=core.inherited.quantiles([v-u for u,v in both]),
   interpretation='Conditional only on both observed; missing/never/censored are separate counts, not zero latency.'))
 return out,delays
def fixtures():
 r=dict(case_id='c',segment_index='0',source_id='s',metadata_identity='CMU_ARCTIC_a',roster_status='ENROLLED',sole_active_samples='10',correct_name_samples='2',wrong_known_name_samples='3',unknown_name_samples='5',first_confirmed_correct_name_wait_sec='.4')
 s=dict(r,correct_name_samples='3',wrong_known_name_samples='2',first_confirmed_correct_name_wait_sec='')
 v,d=paired([r],[s]);assert v['right_minus_left_correct_name_samples']==1
 row=next(x for x in d if x['metric']=='first_confirmed_correct_name_wait_sec');assert row['left_only_observed']==1 and row['both_observed']==0
 for bad in [dict(s,source_id='other'),dict(s,roster_status='WITHHELD_OR_UNSELECTED'),dict(s,sole_active_samples='11')]:
  try:paired([r],[bad])
  except ValueError:pass
  else:raise AssertionError('Unmatched tier population admitted')
 return dict(status='PASS',checks=['paired exposure uses pooled sample counts','censored name wait is not zero','source occurrence substitution rejected','roster substitution rejected','support denominator mismatch rejected'])
def buffer_fixtures():
 with tempfile.TemporaryDirectory(prefix='s6c_duration_buffer_') as folder:
  path=Path(folder)/'TURNS.csv';raw=b'value\n1\n';path.write_bytes(raw)
  binding=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());receipt=dict(tables=[binding])
  rows,b=table(receipt,'TURNS.csv');assert rows==[{'value':'1'}] and b==binding
  path.write_bytes(b'value\n2\n')
  try:table(receipt,'TURNS.csv')
  except ValueError:pass
  else:raise AssertionError('Same-size changed source buffer accepted')
  path.write_bytes(raw+b'3\n')
  try:table(receipt,'TURNS.csv')
  except ValueError:pass
  else:raise AssertionError('Changed source length accepted')
  try:table(dict(tables=[binding,binding]),'TURNS.csv')
  except ValueError:pass
  else:raise AssertionError('Duplicate table authority accepted')
 return dict(status='PASS',checks=['exact verified buffer parsed','same-size changed bytes reject','changed length rejects','duplicate table authority rejects'])
def run(args):
 np=REPORT/args.names_subdir/'NAME_ANALYSIS_RECEIPT.json';cp=REPORT/args.core_subdir/'ANALYSIS_RECEIPT.json'
 nb=core.bind(np);cb=core.bind(cp);nr=core.verified(nb);cr=core.verified(cb)
 if nr['status']!='COMPLETE_REQUESTED_NAME_INDEX' or nr['failed_or_missing'] or cr['status']!='COMPLETE_REQUESTED_INDEX' or cr['unscored']:raise ValueError('Complete paired source receipts required')
 if nr['index']!=cr['index'] or nr['requested']!=2880 or cr['requested']!=2880:raise ValueError('Exact same six-profile240-case/two-tap full bank required')
 index=core.verified(nr['index']);cases=set(index['case_ids'])
 if len(cases)!=240 or {core.route_key(r) for r in index['profile_routes']}!={(p,t,t) for p in IDS for t in ('O0','O1')}:raise ValueError('Exact common-duration full-bank routes required')
 turns,tb=table(nr,'TURNS.csv');retained,rb=table(nr,'RETAINED_ROWS.csv')
 if any(r['profile_id'] not in IDS or r['stream']!=r['identity_tap'] or r['case_id'] not in cases for r in turns):raise ValueError('Unexpected source turn route')
 for r in turns:
  side,tier=IDS[r['profile_id']]
  if r['gallery_condition']!='COMMON30_FIXED_ROSTER_'+side or int(r['enrollment_tier'])!=tier:raise ValueError('Condition/tier substitution')
  nums=[val(r,k) for k in SAMPLE_KEYS]
  if nums[0] is not None and (any(x is None for x in nums) or nums[0]!=sum(nums[1:])):raise ValueError('Correct/wrong/Unknown source partition differs')
 groups={(p,t):[r for r in turns if r['profile_id']==p and r['stream']==t] for p in IDS for t in ('O0','O1')}
 if any(len(rows)!=777 for rows in groups.values()):raise ValueError('All777 source occurrences per full-bank route must remain')
 summary=[];strata=[];within=[];deltas=[];delay_rows=[];retained_summary=[]
 for (pid,tap),rows in groups.items():
  side,tier=IDS[pid];base=dict(profile_id=pid,stream=tap,roster=side,tier=tier,gallery_available_people=14,gallery_available_corpus_people='9 CMU ARCTIC;5 HiFiTTS',scored_scenes=240)
  for status in ('ALL','ENROLLED','WITHHELD_OR_UNSELECTED','INTENDED_BUT_UNAVAILABLE'):
   chosen=[r for r in rows if status=='ALL' or r['roster_status']==status]
   summary.append(dict(**base,roster_status=status,**aggregate(chosen)))
   for co in ('CMU ARCTIC','HiFiTTS','Common Voice'):
    crs=[r for r in chosen if corpus(r['metadata_identity'])==co]
    strata.append(dict(**base,roster_status=status,corpus=co,**aggregate(crs)))
  visible=[r for r in retained if r['profile_id']==pid and r['stream']==tap]
  rr=dict(**base,retained_rows=len(visible),exposure_available_rows=sum(r['exposure_available']=='True' for r in visible),exposure_missing_rows=sum(r['exposure_available']!='True' for r in visible))
  for k in ('retained_row_sec','correct_name_row_sec','wrong_known_name_row_sec','unknown_name_row_sec','unidentifiable_reference_row_sec','empty_reference_assigned_name_row_sec'):
   rr[k]=sum(val(r,k) or 0 for r in visible)
  retained_summary.append(rr)
 for side,profiles in [('A',['C141','C142','C143']),('B',['C144','C145','C146'])]:
  for tap in ('O0','O1'):
   for li,ri in [(0,1),(1,2),(0,2)]:
    left,right=profiles[li],profiles[ri];allleft,allright=groups[left,tap],groups[right,tap]
    for status in ('ALL','ENROLLED','WITHHELD_OR_UNSELECTED'):
     la=[r for r in allleft if status=='ALL' or r['roster_status']==status];rb2=[r for r in allright if status=='ALL' or r['roster_status']==status]
     delta,delay=paired(la,rb2);base=dict(roster=side,stream=tap,left_profile=left,right_profile=right,left_tier=IDS[left][1],right_tier=IDS[right][1],roster_status=status)
     deltas.append(dict(**base,**delta));delay_rows.extend(dict(**base,**r) for r in delay)
    for person in sorted({r['metadata_identity'] for r in allleft}):
     la=[r for r in allleft if r['metadata_identity']==person];rb2=[r for r in allright if r['metadata_identity']==person]
     delta,_=paired(la,rb2);within.append(dict(roster=side,stream=tap,left_profile=left,right_profile=right,metadata_identity=person,corpus=corpus(person),roster_status=la[0]['roster_status'],**delta))
 out=REPORT/args.output_subdir
 if out.exists() or Path(args.output_subdir).is_absolute() or REPORT.resolve() not in out.resolve().parents:raise ValueError('Fresh contained output namespace required')
 out.mkdir(parents=True)
 tables={'TIER_PROFILE_RESULTS.csv':summary,'CORPUS_TIER_RESULTS.csv':strata,'WITHIN_PERSON_TIER_DELTA.csv':within,'POOLED_TIER_DELTA.csv':deltas,'PAIRED_NAME_DELAY_RESULTS.csv':delay_rows,'RETAINED_ROW_EXPOSURE.csv':retained_summary}
 for name,rows in tables.items():core.csv_write(out/name,rows)
 result=dict(status='COMPLETE_SOURCE_BOUND_DESCRIPTIVE_COMPARISON',core=cb,names=nb,index=nr['index'],source_tables=[tb,rb],source_occurrences=len(turns),profiles=6,routes=12,scenes_per_route=240,source_occurrences_per_route=777,
  tests=fixtures(),buffer_tests=buffer_fixtures(),sources=[core.bind(Path(__file__)),core.bind(Path(__file__).with_name('README_S6C_COMMON_DURATION_RESULTS_V2.md')),*nr['codes']],
  artifacts=[core.bind(out/n) for n in tables],neural_calls=0,rescored_predictions=0,
  scope='Fixed14-person roster and competitors per side at each5/15/30 tier. Known/withheld populations and exact source support are matched; source-to-XVF domain mismatch persists. Nested enrollment duration changes speech content/native centroid too, not a duration-only physical intervention. Common Voice remains withheld here: no CV enrollment-duration inference.All240-scene development confirmation; the previous56-scene panel was already inspected. This is not an untouched holdout.',
  uncertainty='No new inferential confidence intervals. Per-person/turn differences and observed/censored delay partitions are descriptive; source occurrences/people are dependent.')
 core.save(out/'DURATION_RESULTS_RECEIPT.json',result)
 return core.bind(out/'DURATION_RESULTS_RECEIPT.json')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--names-subdir',default='full_n01_common_duration_names_v3');p.add_argument('--core-subdir',default='full_n01_common_duration_core_v3');p.add_argument('--output-subdir',default='full_common_duration_results_v2');p.add_argument('--test',action='store_true');a=p.parse_args()
 print(json.dumps(dict(original=fixtures(),exact_buffer=buffer_fixtures()) if a.test else run(a),indent=2))
