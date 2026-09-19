"""Independent completed N03 table review; see README_S6C_N03_COMPONENT_REVIEW_V1.md."""
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction
import argparse,csv,datetime,hashlib,io,json,math
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
PINS={'full_n03_native_core_v3/ANALYSIS_RECEIPT.json':'10d38193dfa630bc06dd15d582f1d9086493ce104cc5b45535be01844e238517','full_n03_comparisons_v1/COMPARISON_RECEIPT.json':'6b23a862569c3f9f25cf85a7301f2aeb08009e08a15374d6c883dddc6fd2fe14','full_n03_results_v1/RESULT.json':'32e8616d0e067268175eb4909fd9a697914955be7d034c848d48f0b5555b229a'}
COMPLETE={'PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'}
SCALAR=['source_turns','supported_turns','unknown_turns','sole_active_samples','known_samples','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown','embedding_calls','embedding_total_window_sec','embedding_union_sec','embedding_availability_missing','segmentation_calls','decision_count','policy_wall_sec','final_utterances']
csv.field_size_limit(32*1024**2)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(d):return json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def bind(p,raw=None):
 p=Path(p);raw=p.read_bytes() if raw is None else raw;return dict(path=str(p.resolve()),bytes=len(raw),sha256=sha(raw))
def number(x):return None if x=='' or x is None else float(x)
def matches(x,y):
 if x is None or y is None:return x is None and y is None
 return math.isclose(float(x),float(y),rel_tol=1e-11,abs_tol=1e-8)
def chosen(rows,pop):return [r for r in rows if r['population'] in COMPLETE] if pop=='ALL_COMPLETE_NONEMPTY' else [r for r in rows if r['population']==pop]
class Audit:
 def __init__(self):self.checks=0;self.sources={};self.cache={}
 def check(self,yes,msg):
  self.checks+=1
  if not yes:raise ValueError(msg)
 def read(self,b):
  key=b['path']
  if key in self.cache:self.check(self.sources[key]==b,'repeated binding');return self.cache[key]
  raw=Path(key).read_bytes();self.check(bind(key,raw)==b,'exact buffer '+key);self.sources[key]=b;self.cache[key]=raw;return raw
 def doc(self,b):return json.loads(self.read(b))
 def table(self,doc,name):
  b=next(x for x in doc.get('tables',doc.get('artifacts',[])) if Path(x['path']).name==name+'.csv')
  return list(csv.DictReader(io.StringIO(self.read(b).decode('utf-8-sig'),newline=''),strict=True))
 def pinned(self,rel):
  p=REPORT/rel;raw=p.read_bytes();self.check(sha(raw)==PINS[rel],'pinned '+rel);b=bind(p,raw);self.sources[b['path']]=b;self.cache[b['path']]=raw;return json.loads(raw)
def run(out):
 a=Audit();core=a.pinned('full_n03_native_core_v3/ANALYSIS_RECEIPT.json');cmp=a.pinned('full_n03_comparisons_v1/COMPARISON_RECEIPT.json');summary=a.pinned('full_n03_results_v1/RESULT.json')
 a.check(core['status']=='COMPLETE_REQUESTED_INDEX' and core['requested']==core['scored']==480 and core['unscored']==0,'480 complete score outputs')
 a.check(cmp['requested_contrasts']==9 and cmp['paired_rows']==126 and cmp['unique_scores']==2400,'9 comparisons exact declared scope')
 parent=a.doc(summary['source_receipts']['C065']);a.check(parent['status']=='COMPLETE_REQUESTED_INDEX','completed parent')
 scenes=a.table(core,'SCENE_RESULTS');selected=a.table(cmp,'SELECTED_SCENE_RESULTS');pairs=a.table(cmp,'PAIRED_COMPARISONS');turns=a.table(core,'TURN_RESULTS')+a.table(parent,'TURN_RESULTS')
 profiles=a.table(core,'PROFILE_RESULTS')+a.table(parent,'PROFILE_RESULTS');short=a.table(core,'SHORT_REPLY_RESULTS')+a.table(parent,'SHORT_REPLY_RESULTS');life=a.table(core,'TRACK_LIFECYCLE_RESULTS')+a.table(parent,'TRACK_LIFECYCLE_RESULTS');cost=a.table(core,'RECIPE_COST_RESULTS')
 turns=[r for r in turns if r['profile_id'] in ['C065','C067']];profiles=[r for r in profiles if r['profile_id'] in ['C065','C067']];short=[r for r in short if r['profile_id'] in ['C065','C067']];life=[r for r in life if r['profile_id'] in ['C065','C067']]
 by={(r['profile_id'],r['stream'],r['identity_tap'],r['case_id']):r for r in selected};a.check(len(by)==len(selected)==2400,'unique selected routes');cases=set(core['case_ids']);a.check(len(cases)==240,'240 cases')
 for pid in ['B00','B01','B36','C065','C067']:
  for tap in ['O0','O1']:a.check({k[3] for k in by if k[:3]==(pid,tap,tap)}==cases,'full registered route '+pid+tap)
 for r in scenes:
  other=by[r['profile_id'],r['stream'],r['identity_tap'],r['case_id']];a.check(all(other[k]==v for k,v in r.items()),'N03 selected scientific cells unchanged')
 inp=a.doc(core['input_index']);imap={(r['case_id'],r['stream']):r for r in inp['rows']};a.check(len(imap)==480,'canonical480 declarations')
 hist=Counter()
 for r in scenes:
  duration=imap[r['case_id'],r['stream']]['duration_sec'];a.check(float(r['duration_sec'])==duration,'exact original full source duration');hist[str(duration)]+=1
 a.check(hist==Counter({'44.6954375':472,'46.6954375':2,'99.6954375':6}),'nonuniform duration histogram')
 denominators=[]
 for tap in ['O0','O1']:
  rs=[r for r in scenes if r['stream']==tap]
  for pop,n in [('PRIMARY_NONOVERLAP',156),('COMPLETE_OVERLAP',47),('INCOMPLETE_REFERENCE',26),('STRICT_EMPTY_REFERENCE',11),('ALL_COMPLETE_NONEMPTY',203)]:
   group=chosen(rs,pop);ts=chosen([t for t in turns if t['profile_id']=='C067' and t['stream']==tap],pop);a.check(len(group)==n,'population scene count')
   den=dict(stream=tap,population=pop,scenes=n,duration_sec=math.fsum(float(r['duration_sec']) for r in group),source_turns=len(ts),returns=sum(t['return_status']!='FIRST' for t in ts),word_reference_words=sum(int(r['word_reference_words'] or 0) for r in group))
   if pop=='ALL_COMPLETE_NONEMPTY':a.check((den['source_turns'],den['returns'],den['word_reference_words'])==(693,292,6016),'complete denominators')
   if pop=='PRIMARY_NONOVERLAP':a.check(den['word_reference_words']==4560 and matches(den['duration_sec']-156*44.6954375,167),'primary duration167extra seconds')
   if pop=='INCOMPLETE_REFERENCE':a.check((den['source_turns'],den['returns'])==(84,32),'incomplete separate turns/returns')
   denominators.append(den)
 # Independently pool all profile populations from exact scene values, never calling the scorer.
 for p in profiles:
  rs=chosen([r for r in selected if r['profile_id']==p['profile_id'] and r['stream']==p['stream']],p['population'])
  a.check(int(p['scenes'])==len(rs) and matches(p['duration_sec'],math.fsum(float(r['duration_sec']) for r in rs)),'profile scenes/duration')
  for k in SCALAR:a.check(matches(p[k],math.fsum(float(r[k] or 0) for r in rs)),'profile additive '+k)
  for prefix in ['word','char','cp_first_final','cp_latest_revised','cp_first_display_label_final_words']:
   valid=[r for r in rs if r[prefix+'_errors']!=''];a.check(int(p[prefix+'_scored_scenes'])==len(valid),'metric valid scenes')
   for suffix in ['errors','substitutions','deletions','insertions','reference_characters' if prefix=='char' else 'reference_words']:
    k=prefix+'_'+suffix;vals=[number(r[k]) for r in rs if r[k]!=''];a.check(matches(number(p[k]),math.fsum(vals) if vals else None),'profile metric '+k)
   den=number(p[prefix+('_reference_characters' if prefix=='char' else '_reference_words')]);num=number(p[prefix+'_errors']);rate=num/den if den else None
   if prefix=='word' and p['population']=='STRICT_EMPTY_REFERENCE':rate=None
   a.check(matches(number(p[prefix+'_rate']),rate),'profile metric rate')
  for k,num,den in [('unknown_fraction','unknown_samples','sole_active_samples'),('mixed_fraction_all_sole','false_merge_samples','sole_active_samples'),('mixed_fraction_known','false_merge_samples','known_samples')]:a.check(matches(number(p[k]),float(p[num])/float(p[den]) if float(p[den]) else None),'support fraction')
  for k in ['lineage_counts','transcript_event_counts']:
   total=Counter()
   for r in rs:total.update(json.loads(r[k]))
   a.check(dict(total)==json.loads(p[k]),'profile event totals')
 # Turn support is disjoint within each occurrence; categories remain explicit rather than unknown=incorrect.
 for t in turns:a.check(int(t['known_samples'])+int(t['unknown_samples'])==int(t['sole_active_samples']),'turn sample partition')
 for p in short:
  ts=[t for t in turns if (t['profile_id'],t['stream'],t['whole_clip_bin'])==(p['profile_id'],p['stream'],p['duration_bin'])];ts=chosen(ts,p['population'])
  a.check(len(ts)==int(p['source_turns']) and len({t['case_id'] for t in ts})==int(p['scene_count']),'short turn population')
  checks={'any_known_support_turns':sum(t['any_known_label_present']=='True' for t in ts),'duration_mapped_correct_modal_turns':sum(t['modal_duration_mapped_correct']=='True' for t in ts),'duration_mapped_incorrect_modal_turns':sum(t['modal_duration_mapped_correct']=='False' for t in ts),'duration_mapping_unavailable_or_unknown_turns':sum(t['modal_duration_mapped_correct']=='' for t in ts),'contained_embedding_turns':sum(int(t['contained_embedding_count'] or 0)>0 for t in ts)}
  for k,v in checks.items():a.check(int(p[k])==v,'short evidence/mapping '+k)
  for k in ['sole_active_samples','known_samples','unknown_samples','duration_mapped_correct_samples']:a.check(int(p[k])==sum(int(t[k] or 0) for t in ts),'short support '+k)
  for target,src in [('contained_evidence_wait','first_contained_embedding_available_wait_sec'),('known_support_wait','first_known_label_support_wait_sec'),('correct_mapped_support_wait','first_correct_mapped_support_wait_sec')]:
   q=json.loads(p[target]);observed=sorted(float(t[src]) for t in ts if t[src]!='');a.check((q['count'],q['observed'],q['missing'])==(len(ts),len(observed),len(ts)-len(observed)),'wait censoring')
   for label,frac in [('p50',.5),('p90',.9),('p95',.95)]:
    pos=(len(observed)-1)*frac;lo=math.floor(pos);hi=math.ceil(pos);val=observed[lo]+(observed[hi]-observed[lo])*(pos-lo) if observed else None;a.check(matches(q[label],val),'observed wait quantile')
 # All126 point rows and room denominators, using exact left/right routes.
 for p in pairs:
  lr=[r for r in selected if (r['profile_id'],r['stream'],r['identity_tap'])==(p['left_profile'],p['left_stream'],p['left_identity_tap'])];rr={r['case_id']:r for r in selected if (r['profile_id'],r['stream'],r['identity_tap'])==(p['right_profile'],p['right_stream'],p['right_identity_tap'])};prefix=p['metric'];group=[(l,rr[l['case_id']]) for l in chosen(lr,p['population']) if l[prefix+'_errors']!='' and rr[l['case_id']][prefix+'_errors']!='']
  a.check(int(p['matched_scene_count'])==int(p['left_scene_count'])==int(p['right_scene_count'])==240 and int(p['paired_scenes'])==len(group),'paired population')
  for l,r in group:a.check(l['population']==r['population'] and l[prefix+'_reference_words']==r[prefix+'_reference_words'],'paired exact denominator')
  den=sum(int(l[prefix+'_reference_words']) for l,r in group);le=sum(int(l[prefix+'_errors']) for l,r in group);re=sum(int(r[prefix+'_errors']) for l,r in group)
  for k,v in [('reference_words',den),('left_errors',le),('right_errors',re),('right_minus_left_errors',re-le)]:a.check(int(p[k])==v,'paired counts '+k)
  a.check(matches(number(p['right_minus_left_pp']),100*(re-le)/den if den else None),'paired right-left sign')
  for room in json.loads(p['rooms']):
   g=[(l,r) for l,r in group if l['room']==room['room']];a.check(room['scenes']==len(g) and room['reference_words']==sum(int(l[prefix+'_reference_words']) for l,r in g) and room['left_errors']==sum(int(l[prefix+'_errors']) for l,r in g) and room['right_errors']==sum(int(r[prefix+'_errors']) for l,r in g),'room denominator/counter')
  if prefix=='word':a.check(int(p['lexical_changed_scenes'])==sum(l['normalized_final_text']!=r['normalized_final_text'] for l,r in group),'word sequence comparisons')
 a.check(len(pairs)==126 and len({p['comparison_id'] for p in pairs})==9,'all requested comparisons')
 for tap in ['O0','O1']:
  a.check(all(by['C065',tap,tap,c]['normalized_final_text']==by['C067',tap,tap,c]['normalized_final_text'] for c in cases),'all240 same-tap final words unchanged')
 # Source-bound summary headline/cost/lifecycle/counterexamples independently reconstructed.
 for row in summary['complete_population']:
  rs=chosen([r for r in selected if r['profile_id']==row['profile_id'] and r['stream']==row['stream']],'ALL_COMPLETE_NONEMPTY')
  for k,v in row.items():
   if k in ['profile_id','stream']:continue
   calc=len(rs) if k=='scenes' else (100*sum(int(r['unknown_samples']) for r in rs)/sum(int(r['sole_active_samples']) for r in rs) if k=='unknown_percent' else (100*sum(int(r['false_merge_samples']) for r in rs)/sum(int(r['sole_active_samples']) for r in rs) if k=='mixed_percent_all_sole' else math.fsum(float(r[k]) for r in rs)))
   a.check(matches(v,calc),'summary complete headline '+k)
 for row in summary['short_turns']:
  p=next(p for p in short if p['profile_id']==row['profile_id'] and p['stream']==row['stream'] and p['population']=='ALL_COMPLETE_NONEMPTY' and p['duration_bin']==row['duration_bin']);a.check(all(p[k]==str(v) for k,v in row.items()),'summary short table')
 for row in summary['lifecycle_all240']:
  ls=[r for r in life if r['profile_id']==row['profile_id'] and r['stream']==row['stream']];calc=dict(scenes=len(ls),maximum_peak_live=max(int(r['peak_live']) for r in ls),maximum_peak_archive=max(int(r['peak_archive']) for r in ls),blocked_unique_evidence_sec=math.fsum(float(r['blocked_unique_evidence_sec']) for r in ls),cumulative_retirements_sum=sum(int(r['final_cumulative_retirements']) for r in ls),lifetime_external_ids_sum=sum(int(r['final_lifetime_external_ids']) for r in ls))
  a.check(all(matches(row[k],v) for k,v in calc.items()),'summary lifecycle')
 a.check(len({r['neural_source_key'] for r in cost})==len(cost)==480,'cost distinct native source receipts')
 for r in cost:a.check(r['recipe_costs']==by['C067',r['stream'],r['identity_tap'],r['case_id']]['recipe_costs'],'native cost source equality')
 for row in summary['native_nested_cost_all240']:
  rs=[r for r in selected if r['profile_id']==row['profile_id'] and r['stream']==row['stream']];costs=[json.loads(r['recipe_costs']) for r in rs]
  a.check(row['source_cells']==len(rs)==240 and matches(row['source_duration_sec'],math.fsum(float(r['duration_sec']) for r in rs)),'cost duration/denominator')
  for k,v in row.items():
   if '.' not in k:continue
   section,field=k.split('.');values=[c[section][field] for c in costs if isinstance(c.get(section),dict) and field in c[section]];a.check(v['observed_cells']==len(values) and v['unavailable_cells']==240-len(values) and matches(v['sum'],math.fsum(values)),'nested cost independently observed sum '+k)
 examples=[]
 for tap in ['O0','O1']:
  rows=chosen([r for r in selected if r['profile_id']=='C067' and r['stream']==tap],'ALL_COMPLETE_NONEMPTY')
  diffs=[(Fraction(int(r['cp_latest_revised_errors'])-int(by['C065',tap,tap,r['case_id']]['cp_latest_revised_errors']),int(r['word_reference_words'])),r['case_id']) for r in rows]
  selected_examples=[('largest_observed_harm',v,c) for v,c in sorted(diffs,key=lambda x:(-x[0],x[1]))[:2]]+[('largest_observed_benefit',v,c) for v,c in sorted(diffs,key=lambda x:(x[0],x[1]))[:2]]
  for direction,delta,case in selected_examples:
   row=next(x for x in summary['selected_extreme_case_examples'] if x['selection']==direction and x['stream']==tap and x['case_id']==case);a.check(matches(row['delta_pp'],float(delta)*100),'deterministic selected extreme')
   evidence=dict(selection=direction,case_id=case,stream=tap,delta_pp=float(delta)*100,metric_scope='Observed latest cp error rate, exact Fraction then case ID. Post-outcome descriptive selection, not typical or independent validation.',same_normalized_words=by['C065',tap,tap,case]['normalized_final_text']==by['C067',tap,tap,case]['normalized_final_text'],native_root_cause_status='NOT_INFERRED_FROM_SCORE_TABLES',turns=[])
   for side,pid in [('left','C065'),('right','C067')]:
    original=by[pid,tap,tap,case];a.check(all(original[k]==v for k,v in row[side].items()),'example exact scalar cells');evidence[side]=row[side]
    for t in turns:
     if (t['profile_id'],t['stream'],t['case_id'])==(pid,tap,case):evidence['turns'].append({k:t[k] for k in ['profile_id','segment_index','source_id','whole_clip_bin','modal_label','return_status','sole_active_samples','known_samples','unknown_samples','predicted_labels','contained_embedding_count','first_contained_embedding_available_wait_sec','first_known_label_support_wait_sec','duration_mapping_status','modal_duration_mapped_correct']})
   examples.append(evidence)
 # Uncertainty is admitted and its observed denominator/sign checked; never regenerate bootstrap.
 ub=next(b for b in cmp['artifacts'] if Path(b['path']).name=='PAIRED_UNCERTAINTY.json');unc=a.doc(ub)
 for u in unc['comparisons']:
  a.check(u['replicates']==2000 and u['included_primary_scenes']==u['requested_primary_scenes']==156 and u['matched_block_count']==116 and u['observed_rooms']==5 and u['excluded_whole_blocks']==[],'uncertainty population')
  p=next(p for p in pairs if p['comparison_id']==u['comparison_id'] and p['metric']=='word' and p['population']=='PRIMARY_NONOVERLAP');observed=u['primary_on_included_blocks'];a.check(observed['paired_scenes']==156 and observed['O0']['errors']==int(p['left_errors']) and observed['O1']['errors']==int(p['right_errors']) and matches(observed['O1_minus_O0_wer_pp'],float(p['right_minus_left_pp'])),'uncertainty exact point adapter')
 result=dict(status='PASS_INDEPENDENT_FULL_N03_TABLE_REVIEW',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=a.checks,sources=list(a.sources.values()),code=bind(Path(__file__)),readme=bind(HERE/'README_S6C_N03_COMPONENT_REVIEW_V1.md'),routes=core['full240_confirmed_routes'],duration_histogram_views=dict(hist),duration_nonuniform_case_ids=['S45_03_11','S45_06_01','S45_06_06','S45_06_11'],population_denominators=denominators,profile_rows_checked=len(profiles),short_rows_checked=len(short),turn_rows_checked=len(turns),comparison_rows_checked=len(pairs),uncertainty_observed_points_checked=len(unc['comparisons']),summary_complete_rows=summary['complete_population'],summary_short_rows=summary['short_turns'],summary_native_nested_cost=summary['native_nested_cost_all240'],adverse_and_benefit_examples=examples,limits=['Exact completed CSV/JSON buffers only; no original audio/native events/predictions/per-output rescoring or policy/model execution.','Numeric scientific score and source-support fields are inherited; this audit reconciles them and their meanings, not new recognizer accuracy measurements.','ALL_COMPLETE lexical counts combine primary serialized WER and complete-overlap MIMO counts; report separate named populations. Incomplete and11 strict-empty scenes retained separately.','Short evidence waits are source-span-contained evidence availability; their observed-only quantiles and censored missing counts are not guaranteed live identity or display latencies.','Native costs are nested model/API/full-dispatch values; missing embedding sections remain unavailable. Concurrent lane times are not added to imply host wall or CPU.','Actual score-table changes do not establish scheduler/model causal mechanisms. Extreme examples were selected after results and are not representative.','Primary-word uncertainty points/denominators are reconciled; bootstrap samples/intervals are source-bound and not recomputed. cp uncertainty is not claimed.'])
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(bind(out)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',required=True,type=Path);run(p.parse_args().output)
