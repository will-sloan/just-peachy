"""Bounded independent N00 admission/contrast audit; see README_S6C_N00_REVIEW_V2.md."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
TRACE_IDS=('C001','C002','C011','C012','C021','C022','C025','C026')
COMPLETE=('PRIMARY_NONOVERLAP','COMPLETE_OVERLAP')
CONTRASTS=(('C001','C002'),('C010','C011'),('C011','C012'),('C011','C025'),('C011','C055'),('C055','C056'),('C011','C057'),('C061','C062'))

def binding(p):
 p=Path(p);raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def verified(b):
 p=Path(b['path']);raw=p.read_bytes()
 if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('Changed input '+str(p))
 return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,value):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def csv_read(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csv_write(p,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with Path(p).open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def union_length(intervals):
 total=0.;end=-math.inf
 for a,b in sorted(intervals):
  if b<a or not math.isfinite(a+b):raise ValueError('Invalid clean interval')
  total+=max(0.,b-max(a,end));end=max(end,b)
 return total
def trace(value):
 stats=Counter();examples=[];features={v['evidence_event_id']:v for v in value['features']}
 if len(features)!=len(value['features']):raise ValueError('Duplicate feature identity')
 for d in value['decisions']:
  f=features[d['evidence_id']];duration=d['source_end_sec']-d['source_start_sec'];clean=union_length(d['clean_intervals'])
  if duration<=0 or clean>duration+1e-7:raise ValueError('Invalid clean support')
  fraction=clean/duration;stats['decisions']+=1;stats['source_clean_sec_sum_not_union']+=clean
  stats['zero_clean_support']+=clean<=1e-10;stats['clean_fraction_below_025']+=fraction<.25-1e-8
  stats['clean_fraction_below_050']+=fraction<.5-1e-8
  stats['speech_false']+=not f['speech'];stats['overlap_true']+=f['overlap']
  stats['native_gate_admitted']+=f['admission']['admitted']
  stats['state_'+d['state']]+=1;stats['committed_decisions']+=bool(d['committed'])
  for e in d['lineage']:
   stats['event_'+e['event']]+=1
   if e['event']=='audio_gate_reject':stats['reject_'+e['reason']]+=1
   if e['event']=='evidence_admit':stats['unique_increment_sec_sum']+=e['unique_increment_sec']
  if len(examples)<18:examples.append(dict(evidence_id=d['evidence_id'],source_start_sec=d['source_start_sec'],source_end_sec=d['source_end_sec'],clean_sec=clean,clean_fraction=fraction,native_gate_admitted=f['admission']['admitted'],native_admission_clean_fraction=f['admission']['clean_fraction'],state=d['state'],reason=d['reason'],anonymous_label=d['anonymous_label'],committed=d['committed'],unique_evidence_sec=d['unique_evidence_sec'],disjoint_evidence_count=d['disjoint_evidence_count']))
 return dict(stats),examples

def run(args):
 source=REPORT/'n00_challenge_core_v1';out=(REPORT/args.output_subdir).resolve()
 if not out.is_relative_to(REPORT.resolve()) or out==REPORT.resolve():raise ValueError('Output must remain a new child of the S6C report')
 if out.exists():raise ValueError('Fresh output subdirectory required')
 receipt=read(source/'ANALYSIS_RECEIPT.json')
 if receipt['status']!='COMPLETE_REQUESTED_INDEX':raise ValueError('Complete core receipt required')
 index=verified(receipt['index'])
 if index['status']!='COMPLETE' or len(index['rows'])!=7392 or len(index['profiles'])!=66 or len(index['case_ids'])!=56:raise ValueError('Expected complete frozen N00 panel')
 profiles=read(source/'PROFILE_RESULTS.json');scene=csv_read(source/'SCENE_RESULTS.csv');life=csv_read(source/'TRACK_LIFECYCLE_RESULTS.csv');short=csv_read(source/'SHORT_REPLY_RESULTS.csv')
 keys={(r['profile_id'],r['stream'],r['case_id']) for r in scene}
 if len(keys)!=7392:raise ValueError('Complete scene score keys required')
 source_bindings=[binding(source/p) for p in ('ANALYSIS_RECEIPT.json','PROFILE_RESULTS.json','SCENE_RESULTS.csv','TRACK_LIFECYCLE_RESULTS.csv','SHORT_REPLY_RESULTS.csv')]
 source_bindings+=[receipt['index'],binding(REPORT/'design/REGISTERED_DESIGN_V1.json'),binding(__file__),binding(Path(__file__).with_name('README_S6C_N00_REVIEW_V2.md'))]
 summary=[]
 for pid in sorted(index['profiles']):
  for tap in ('O0','O1'):
   rows=[v for v in profiles if v['profile_id']==pid and v['stream']==tap and v['population']!='ALL_COMPLETE_NONEMPTY'];comp=[v for v in rows if v['population'] in COMPLETE]
   c=Counter()
   for v in comp:
    for k in ('scenes','cp_latest_revised_errors','cp_latest_revised_reference_words','cp_first_display_label_final_words_errors','sole_active_samples','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown'):c[k]+=v[k]
   lc=Counter()
   for v in rows:lc.update(v['lineage_counts'])
   shortrow=next(v for v in short if v['profile_id']==pid and v['stream']==tap and v['duration_bin']=='<1s')
   summary.append(dict(profile_id=pid,stream=tap,**dict(c),unknown_fraction=c['unknown_samples']/c['sole_active_samples'],all_population_decisions=sum(v['decision_count'] for v in rows),all_population_audio_gate_reject=lc['audio_gate_reject'],all_population_track_commits=lc['track_commit'],all_population_capacity_reject=sum(v for k,v in lc.items() if 'capacity' in k and 'reject' in k),short_turns=shortrow['source_turns'],short_contained_turns=shortrow['contained_embedding_turns'],short_any_known_turns=shortrow['any_known_support_turns'],short_correct_modal_turns=shortrow['duration_mapped_correct_modal_turns']))
 bykey={(r['profile_id'],r['stream'],r['case_id']):r for r in scene}
 comparison=[];case_examples=[]
 for parent,child in CONTRASTS:
  for tap in ('O0','O1'):
   pair=[]
   for case in index['case_ids']:
    a,b=bykey[parent,tap,case],bykey[child,tap,case]
    if a['normalized_final_text']!=b['normalized_final_text']:raise ValueError('N00 shared lexical control changed')
    if a['population'] not in COMPLETE:continue
    for metric in ('cp_latest_revised_errors','cp_first_display_label_final_words_errors'):
     delta=int(b[metric])-int(a[metric]);pair.append(dict(parent=parent,child=child,stream=tap,case_id=case,metric=metric,parent_errors=int(a[metric]),child_errors=int(b[metric]),delta_errors=delta,reference_words=int(a['cp_latest_revised_reference_words']),population=a['population']))
   for metric in ('cp_latest_revised_errors','cp_first_display_label_final_words_errors'):
    cells=[v for v in pair if v['metric']==metric];comparison.append(dict(parent=parent,child=child,stream=tap,metric=metric,scenes=len(cells),reference_words=sum(v['reference_words'] for v in cells),delta_errors=sum(v['delta_errors'] for v in cells),wins=sum(v['delta_errors']<0 for v in cells),losses=sum(v['delta_errors']>0 for v in cells),ties=sum(v['delta_errors']==0 for v in cells)))
    for sign in (-1,1):
     selected=sorted([v for v in cells if v['delta_errors']*sign>0],key=lambda v:(-sign*v['delta_errors'],v['case_id']))[:2]
     case_examples.extend({**v,'selection':'outcome_selected_explanatory_not_independent_validation'} for v in selected)
 capacities=[]
 fields=('cp_latest_revised_errors','cp_first_display_label_final_words_errors','known_samples','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown')
 for offset in range(4):
  ids=[f'C{1+offset+4*i:03}' for i in range(5)]
  same=all(all(bykey[ids[0],t,c][k]==bykey[pid,t,c][k] for k in fields) for pid in ids[1:] for t in ('O0','O1') for c in index['case_ids'])
  capacities.append(dict(profiles=ids,capacities=[16,32,64,128,256],same_checked_scene_metrics=same,checked_fields=list(fields),rows_per_profile=112))
 if not all(v['same_checked_scene_metrics'] for v in capacities):raise ValueError('Unexpected capacity divergence; revise report')
 trace_group=defaultdict(Counter);trace_rows=[];prediction_bindings=[];example_traces=[]
 explanatory_keys={(p,v['stream'],v['case_id']) for v in case_examples for p in (v['parent'],v['child'])}
 for row in index['rows']:
  key=(row['candidate_id'],row['stream'],row['case_id'])
  if row['candidate_id'] not in TRACE_IDS and key not in explanatory_keys:continue
  v=verified(row['result']);prediction_bindings.append(row['result'])
  if (v['profile_id'],v['stream'],v['case_id'])!=key or v['status']!='COMPLETE':raise ValueError('Invalid admitted trace')
  stats,examples=trace(v)
  if row['candidate_id'] in TRACE_IDS:
   group=trace_group[key[:2]];group.update(stats);group['cells']+=1;group['cells_with_commit']+=stats.get('event_track_commit',0)>0;group['cells_all_uncommitted_decisions']+=stats.get('committed_decisions',0)==0
   trace_rows.append(dict(profile_id=key[0],stream=key[1],case_id=key[2],**stats))
  if key in explanatory_keys or key in {('C001','O0','S45_01_06'),('C011','O0','S45_01_06')}:
   example_traces.append(dict(profile_id=key[0],stream=key[1],case_id=key[2],binding=row['result'],stats=stats,first_18_decisions=examples,final_tracker_counts=v['snapshot']['tracker'].get('counts'),final_tracker_operations=v['snapshot']['tracker'].get('operations')))
 traces=[dict(profile_id=p,stream=t,**dict(c)) for (p,t),c in sorted(trace_group.items())]
 if len(trace_rows)!=896 or any(v['cells']!=56 for v in traces):raise ValueError('Incomplete eight-profile trace denominator')
 out.mkdir(parents=True)
 csv_write(out/'PROFILE_SCREEN.csv',summary);csv_write(out/'MATCHED_CONTRASTS.csv',comparison);csv_write(out/'EXPLANATORY_CASES.csv',case_examples);csv_write(out/'ADMISSION_BY_PROFILE_TAP.csv',traces);csv_write(out/'ADMISSION_BY_CASE.csv',trace_rows)
 write(out/'EXPLANATORY_TRACES.json',example_traces)
 result=dict(status='PASS',schema='s6c_n00_independent_review.v2',prior_review=binding(REPORT/'independent_review/n00_screen_v1/REVIEW_RECEIPT.json'),correction='All-population counters use four disjoint populations, excluding the inherited ALL_COMPLETE_NONEMPTY aggregate; trace/complete/short/capacity/case arithmetic unchanged.',created_utc=datetime.now(timezone.utc).isoformat(),sources=source_bindings,population_counts_per_profile_tap={v['population']:v['scenes'] for v in profiles if v['profile_id']=='C001' and v['stream']=='O0'},core_outputs=7392,trace_scope=dict(profiles=list(TRACE_IDS),cases=56,taps=2,outputs=896,additional_outcome_selected_trace_outputs=len(prediction_bindings)-896),prediction_bindings=prediction_bindings,capacity_matches=capacities,all_profile_complete_return_status=dict(consistent=sum(v['return_consistent'] for v in summary),inconsistent=sum(v['return_inconsistent'] for v in summary),unknown_per_profile_tap=sorted(set(v['return_unknown'] for v in summary))),interpretation=['C001/C021 are v3 old-voice-gate controls with new clean-support and commitment semantics, not S6B scheduler/tracker equivalence.','N00 legacy gate-only .5s vectors are reconstructed from sparse arrived segmentation support; new tracker clean_fraction=.5 can reject native-admitted vectors.','Reject/commit/retirement counters are mechanism incidence, not person errors; clean seconds summed over observations overlap and must not be interpreted as unique duration.','Zero successful measured returns and high Unknown prevent capacity or spatial-family rejection from this panel alone.','Real/null/nominal cue controls share sparse audio eligibility; equal cpWER does not establish informative cues were available at decisions.','N01 fresh dual evidence and lower-clean-threshold amendments are outcome-informed repairs requiring preserved priors and independently declared comparisons.','Explanatory cases are outcome-selected and not holdout evidence.'],outputs=[binding(p) for p in sorted(out.iterdir())])
 write(out/'REVIEW_RECEIPT.json',result);print(json.dumps(dict(status='PASS',output=str(out),trace_cells=896,additional_explanatory_traces=len(prediction_bindings)-896)))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output-subdir',default='independent_review/n00_screen_v2');run(parser.parse_args())
