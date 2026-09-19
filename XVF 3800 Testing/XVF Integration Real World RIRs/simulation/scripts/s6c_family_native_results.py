"""Compact actual-native family gate interpretation; README_S6C_FAMILY_NATIVE_RESULTS.md."""
from collections import Counter
from pathlib import Path
import csv,io,json,argparse
import s6c_analysis_v3 as core

IDS=['C065','C079']+['C%03d'%x for x in range(117,131)]
def table(receipt,name):
 rows=[b for b in receipt['tables'] if Path(b['path']).name==name]
 if len(rows)!=1:raise ValueError('Unique bound source table required')
 b=rows[0];raw=Path(b['path']).read_bytes()
 import hashlib
 if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('Changed exact table buffer')
 return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))),b
def key(r):return r['profile_id'],r['stream'],r['identity_tap'],r['case_id']
def number(x):return None if x in ('',None) else float(x)
def paired(native,cached):
 if key(native)!=key(cached):raise ValueError('Declared cell identity differs')
 for f in ('population','word_reference_words','cp_latest_revised_reference_words','source_turns','sole_active_samples','identity_tap'):
  if native[f]!=cached[f]:raise ValueError('Paired source population/support differs: '+f)
 out={k:native[k] for k in ('profile_id','stream','identity_tap','case_id','population','word_reference_words','cp_latest_revised_reference_words','source_turns','sole_active_samples')}
 out['normalized_final_text_equal']=native['normalized_final_text']==cached['normalized_final_text']
 for metric in ('word_errors','cp_first_final_errors','cp_latest_revised_errors','cp_first_display_label_final_words_errors','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown','embedding_calls','segmentation_calls'):
  a,b=number(native[metric]),number(cached[metric]);out['native_'+metric]=a;out['cached_'+metric]=b;out['native_minus_cached_'+metric]=a-b if a is not None and b is not None else None
 return out
def fixtures():
 fields=('profile_id','stream','identity_tap','case_id','population','word_reference_words','cp_latest_revised_reference_words','source_turns','sole_active_samples','normalized_final_text','word_errors','cp_first_final_errors','cp_latest_revised_errors','cp_first_display_label_final_words_errors','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown','embedding_calls','segmentation_calls')
 a={k:'1' for k in fields};b=dict(a,word_errors='2',cp_latest_revised_errors='')
 p=paired(a,b);assert p['native_minus_cached_word_errors']==-1 and p['native_minus_cached_cp_latest_revised_errors'] is None
 for field in ('case_id','sole_active_samples','population'):
  try:paired(a,dict(b,**{field:'different'}))
  except ValueError:pass
  else:raise AssertionError('Changed paired authority accepted')
 return dict(status='PASS',checks=4)
def run(args):
 rb=core.bind(core.REPORT/'family_gate6_native_core_v3/ANALYSIS_RECEIPT.json');native=core.verified(rb)
 cb=core.bind(core.REPORT/'fresh_family_rescue_core_v2/ANALYSIS_RECEIPT.json');cached=core.verified(cb)
 for r in (native,cached):
  if r['status']!='COMPLETE_REQUESTED_INDEX' or r['unscored']:raise ValueError('Complete source scoring required')
 if native['scored']!=192 or len(native['case_ids'])!=6:raise ValueError('Exact16-family-condition six-case two-tap native gate required')
 ns,nsb=table(native,'SCENE_RESULTS.csv');nl,nlb=table(native,'TRACK_LIFECYCLE_RESULTS.csv');cs,csb=table(cached,'SCENE_RESULTS.csv')
 want={(p,t,t,c) for p in IDS for t in ('O0','O1') for c in native['case_ids']}
 for rows in (ns,nl):
  if len(rows)!=192 or {key(r) for r in rows}!=want:raise ValueError('Native compact grid differs')
 source={key(r):r for r in cs if key(r) in want}
 if set(source)!=want:raise ValueError('Earlier candidate panel has missing exact cells')
 comparisons=[paired(r,source[key(r)]) for r in ns]
 summary=[]
 for pid in IDS:
  for tap in ('O0','O1'):
   life=[r for r in nl if r['profile_id']==pid and r['stream']==tap];scene=[r for r in ns if r['profile_id']==pid and r['stream']==tap];deltas=[r for r in comparisons if r['profile_id']==pid and r['stream']==tap]
   counts=Counter()
   for r in life:counts.update(json.loads(r['lineage_counts']))
   row=dict(profile_id=pid,stream=tap,cells=6,actual_decisions=sum(int(r['decisions']) for r in life),peak_live=max(int(r['peak_live']) for r in life),peak_archive=max(int(r['peak_archive']) for r in life),
    final_retirements_sum=sum(int(r['final_cumulative_retirements']) for r in life),final_lifetime_ids_sum=sum(int(r['final_lifetime_external_ids']) for r in life),blocked_unique_evidence_sec=sum(float(r['blocked_unique_evidence_sec']) for r in life),
    lineage_counts=dict(counts),normalized_text_changed_cells=sum(not r['normalized_final_text_equal'] for r in deltas),actual_embedding_calls=sum(int(r['embedding_calls']) for r in scene))
   for metric in ('word_errors','cp_first_final_errors','cp_latest_revised_errors','cp_first_display_label_final_words_errors','unknown_samples','embedding_calls'):
    vals=[r['native_minus_cached_'+metric] for r in deltas];row[metric+'_paired_cells']=sum(v is not None for v in vals);row[metric+'_changed_cells']=sum(v is not None and v!=0 for v in vals);row['native_minus_cached_'+metric]=sum(v for v in vals if v is not None)
   summary.append(row)
 out=core.REPORT/args.output_subdir
 if out.exists() or core.REPORT.resolve() not in out.resolve().parents:raise ValueError('Fresh contained report directory required')
 out.mkdir(parents=True);core.csv_write(out/'FAMILY_ACTIVATION_AND_COMPARISON.csv',summary);core.csv_write(out/'PAIRED_NATIVE_VS_CACHED_CELLS.csv',comparisons)
 result=dict(status='COMPLETE_192_NATIVE_CELL_DESCRIPTIVE_REVIEW',native_core=rb,cached_panel_core=cb,source_tables=[nsb,nlb,csb],cases=native['case_ids'],profiles=IDS,summary=summary,fixtures=fixtures(),
  semantics='Native source integration/reachability check, not another independent accuracy sample. Per-profile totals span12 cells; per-tap rows span6. The comparison matches the same declared candidate/tap/case/reference support against earlier cached policy results; actual fresh inference and measured availability can differ. It does not assert bit-exact vectors, profile bytes or clocks from score tables alone.',
  limitations=['A lineage event counts an attempted/executed branch, not a correct-person benefit.','Absent release/promotion/structural repair events are unsupported outcome paths, not global empirical rejection.','Zero counts in a Counter dictionary mean the named event was not retained in these checked decision lineages; native event-log logging itself is not re-audited here.','Unknown/mixed sample deltas are source-support diagnostics, not live phonetic delay.','These duplicated six scenes must not be added to full-bank accuracy denominators.'],
  artifacts=[core.bind(p) for p in sorted(out.glob('*.csv'))],source=core.bind(__file__),readme=core.bind(Path(__file__).with_name('README_S6C_FAMILY_NATIVE_RESULTS.md')))
 core.save(out/'FAMILY_NATIVE_REVIEW_RECEIPT.json',result);return core.bind(out/'FAMILY_NATIVE_REVIEW_RECEIPT.json')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-subdir',default='family_gate6_native_results_v1');p.add_argument('--test',action='store_true');a=p.parse_args()
 print(json.dumps(fixtures() if a.test else run(a),indent=2))
