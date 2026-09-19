"""Independent completed N08/N10 compact review; README_S6C_N08_N10_COMPONENT_REVIEW_V1.md."""
from pathlib import Path
from collections import Counter
from fractions import Fraction
import argparse,csv,datetime,hashlib,io,json,math
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
PINS={'full_n08_n10_native_core_v3/ANALYSIS_RECEIPT.json':'bd19ed5f87b07b82b5c7fb9f095437603b20261f1d8944bb9767e8b7d99fbdae',
 'full_n08_n10_comparisons_v1/COMPARISON_RECEIPT.json':'9db7ca29da8604778cf97ed42b3bfeb396cf40c7b1d44755a41a11685cfb6cd2',
 'full_n08_n10_results_v1/RESULT.json':'a3d0baab3c7e8e54435a5b99ee228ef22af2c4b362fcd63a4d296aa11ea75902'}
PIDS=('C065','C072','C074');COMPLETE={'PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'}
POPS={'PRIMARY_NONOVERLAP':156,'COMPLETE_OVERLAP':47,'INCOMPLETE_REFERENCE':26,'STRICT_EMPTY_REFERENCE':11,'ALL_COMPLETE_NONEMPTY':203}
SCALAR=('source_turns','supported_turns','unknown_turns','sole_active_samples','known_samples','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown','embedding_calls','embedding_total_window_sec','embedding_union_sec','embedding_availability_missing','segmentation_calls','decision_count','policy_wall_sec','final_utterances')
csv.field_size_limit(32*1024**2)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def binding(p,raw=None):
 p=Path(p);raw=p.read_bytes() if raw is None else raw
 return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def number(x):return None if x is None or x=='' else float(x)
def equal(x,y):
 if x is None or y is None:return x is None and y is None
 return math.isclose(float(x),float(y),rel_tol=1e-11,abs_tol=1e-8)
def choose(rows,pop):return [r for r in rows if r['population'] in COMPLETE] if pop=='ALL_COMPLETE_NONEMPTY' else [r for r in rows if r['population']==pop]
class Audit:
 def __init__(self):self.count=0;self.sources={};self.cache={}
 def check(self,ok,label):
  self.count+=1
  if not ok:raise ValueError(label)
 def raw(self,b):
  key=b['path']
  if key not in self.cache:
   raw=Path(key).read_bytes();self.check(binding(key,raw)==b,'exact buffer '+key);self.cache[key]=raw;self.sources[key]=b
  else:self.check(self.sources[key]==b,'repeated exact authority')
  return self.cache[key]
 def obj(self,b):return json.loads(self.raw(b))
 def pin(self,rel):
  p=REPORT/rel;b=binding(p);self.check(b['sha256']==PINS[rel],'pinned '+rel);return self.obj(b)
 def table(self,doc,name):
  found=[x for x in doc.get('tables',doc.get('artifacts',[])) if Path(x['path']).name==name+'.csv'];self.check(len(found)==1,'unique table '+name)
  reader=csv.DictReader(io.StringIO(self.raw(found[0]).decode('utf-8-sig'),newline=''),strict=True)
  self.check(len(reader.fieldnames)==len(set(reader.fieldnames)),'unique header')
  rows=list(reader);self.check(all(None not in r and None not in r.values() for r in rows),'whole rows');return rows
def run(output):
 if output.exists():raise FileExistsError(output)
 if (REPORT/'PACED_QUIET_OWNER.json').exists():raise ValueError('Defer compact table reads during active quiet lease')
 a=Audit();core=a.pin(next(k for k in PINS if '/ANALYSIS_' in k));cmp=a.pin(next(k for k in PINS if '/COMPARISON_' in k));summary=a.pin('full_n08_n10_results_v1/RESULT.json')
 a.check((core['status'],core['requested'],core['scored'],core['unscored'])==('COMPLETE_REQUESTED_INDEX',960,960,0),'complete960')
 a.check((cmp['requested_contrasts'],cmp['paired_rows'],cmp['unique_scores'])==(18,252,2880),'comparison scope18')
 parent=a.obj(summary['source_receipts']['C065']);a.check(parent['status']=='COMPLETE_REQUESTED_INDEX' and parent['unscored']==0,'complete parent')
 tables={}
 for name in ('SCENE_RESULTS','PROFILE_RESULTS','SHORT_REPLY_RESULTS','TURN_RESULTS','TRACK_LIFECYCLE_RESULTS'):
  tables[name]=[r for doc in (parent,core) for r in a.table(doc,name) if r['profile_id'] in PIDS]
 scenes=tables['SCENE_RESULTS'];profiles=tables['PROFILE_RESULTS'];short=tables['SHORT_REPLY_RESULTS'];turns=tables['TURN_RESULTS'];life=tables['TRACK_LIFECYCLE_RESULTS']
 selected=a.table(cmp,'SELECTED_SCENE_RESULTS');pairs=a.table(cmp,'PAIRED_COMPARISONS')
 by={(r['profile_id'],r['stream'],r['identity_tap'],r['case_id']):r for r in selected};cases=set(core['case_ids'])
 a.check(len(cases)==240 and len(by)==len(selected)==2880,'unique six-profile full selection')
 for pid in ('B00','B01','B36',*PIDS):
  for tap in ('O0','O1'):a.check({k[3] for k in by if k[:3]==(pid,tap,tap)}==cases,'complete exact same-tap route')
 for row in scenes:a.check(all(by[row['profile_id'],row['stream'],row['identity_tap'],row['case_id']][k]==v for k,v in row.items()),'selected C scientific payload unchanged')
 inp=a.obj(core['input_index']);imap={(r['case_id'],r['stream']):r for r in inp['rows']};hist=Counter()
 for row in scenes:
  d=imap[row['case_id'],row['stream']]['duration_sec'];a.check(float(row['duration_sec'])==d,'exact source duration');hist[str(d)]+=1
 a.check(hist==Counter({'44.6954375':1416,'46.6954375':6,'99.6954375':18}),'three-profile nonuniform duration histogram')
 denominators=[]
 for pid in PIDS:
  for tap in ('O0','O1'):
   for pop,n in POPS.items():
    rs=choose([r for r in scenes if (r['profile_id'],r['stream'])==(pid,tap)],pop);ts=choose([r for r in turns if (r['profile_id'],r['stream'])==(pid,tap)],pop)
    den=dict(profile_id=pid,stream=tap,population=pop,scenes=len(rs),source_turns=len(ts),returns=sum(t['return_status']!='FIRST' for t in ts),word_reference_words=sum(int(r['word_reference_words'] or 0) for r in rs),duration_sec=math.fsum(float(r['duration_sec']) for r in rs))
    a.check(len(rs)==n,'population grid')
    if pop=='ALL_COMPLETE_NONEMPTY':a.check((den['word_reference_words'],den['source_turns'],den['returns'])==(6016,693,292),'complete denominators')
    if pop=='INCOMPLETE_REFERENCE':a.check((den['source_turns'],den['returns'])==(84,32),'incomplete denominators')
    if pop=='PRIMARY_NONOVERLAP':a.check(den['word_reference_words']==4560 and equal(den['duration_sec']-156*44.6954375,167),'primary exact duration/words')
    denominators.append(den)
 for p in profiles:
  rs=choose([r for r in scenes if (r['profile_id'],r['stream'])==(p['profile_id'],p['stream'])],p['population'])
  a.check(int(p['scenes'])==len(rs) and equal(p['duration_sec'],math.fsum(float(r['duration_sec']) for r in rs)),'profile duration/count')
  for k in SCALAR:a.check(equal(p[k],math.fsum(float(r[k] or 0) for r in rs)),'profile scalar '+k)
  for prefix in ('word','char','cp_first_final','cp_latest_revised','cp_first_display_label_final_words'):
   a.check(int(p[prefix+'_scored_scenes'])==sum(r[prefix+'_errors']!='' for r in rs),'metric available scenes')
   for suffix in ('errors','substitutions','deletions','insertions','reference_characters' if prefix=='char' else 'reference_words'):
    k=prefix+'_'+suffix;values=[number(r[k]) for r in rs if r[k]!=''];a.check(equal(number(p[k]),math.fsum(values) if values else None),'metric additive '+k)
   den=number(p[prefix+('_reference_characters' if prefix=='char' else '_reference_words')]);err=number(p[prefix+'_errors']);rate=err/den if den else None
   a.check(equal(number(p[prefix+'_rate']),rate),'metric pooled rate')
  for field,n,d in [('unknown_fraction','unknown_samples','sole_active_samples'),('mixed_fraction_all_sole','false_merge_samples','sole_active_samples'),('mixed_fraction_known','false_merge_samples','known_samples')]:a.check(equal(number(p[field]),float(p[n])/float(p[d]) if float(p[d]) else None),'support fraction')
 for t in turns:a.check(int(t['known_samples'])+int(t['unknown_samples'])==int(t['sole_active_samples']),'turn support partition')
 for p in short:
  ts=choose([t for t in turns if (t['profile_id'],t['stream'],t['whole_clip_bin'])==(p['profile_id'],p['stream'],p['duration_bin'])],p['population'])
  a.check(len(ts)==int(p['source_turns']) and len({t['case_id'] for t in ts})==int(p['scene_count']),'short scene/turn denominator')
  counts={'any_known_support_turns':sum(t['any_known_label_present']=='True' for t in ts),'duration_mapped_correct_modal_turns':sum(t['modal_duration_mapped_correct']=='True' for t in ts),'duration_mapped_incorrect_modal_turns':sum(t['modal_duration_mapped_correct']=='False' for t in ts),'duration_mapping_unavailable_or_unknown_turns':sum(t['modal_duration_mapped_correct']=='' for t in ts),'contained_embedding_turns':sum(int(t['contained_embedding_count'] or 0)>0 for t in ts)}
  for k,v in counts.items():a.check(int(p[k])==v,'short evidence/mapping')
  for k in ('sole_active_samples','known_samples','unknown_samples','duration_mapped_correct_samples'):a.check(int(p[k])==sum(int(t[k] or 0) for t in ts),'short sample sums')
  for target,source in [('contained_evidence_wait','first_contained_embedding_available_wait_sec'),('known_support_wait','first_known_label_support_wait_sec'),('correct_mapped_support_wait','first_correct_mapped_support_wait_sec')]:
   q=json.loads(p[target]);observed=sorted(float(t[source]) for t in ts if t[source]!='');a.check((q['count'],q['observed'],q['missing'])==(len(ts),len(observed),len(ts)-len(observed)),'short censoring')
   for label,frac in [('p50',.5),('p90',.9),('p95',.95)]:
    pos=(len(observed)-1)*frac;lo=math.floor(pos);hi=math.ceil(pos);v=observed[lo]+(observed[hi]-observed[lo])*(pos-lo) if observed else None;a.check(equal(q[label],v),'short observed quantile')
 for p in pairs:
  left=[r for r in selected if (r['profile_id'],r['stream'],r['identity_tap'])==(p['left_profile'],p['left_stream'],p['left_identity_tap'])];right={r['case_id']:r for r in selected if (r['profile_id'],r['stream'],r['identity_tap'])==(p['right_profile'],p['right_stream'],p['right_identity_tap'])};prefix=p['metric'];group=[(l,right[l['case_id']]) for l in choose(left,p['population']) if l[prefix+'_errors']!='' and right[l['case_id']][prefix+'_errors']!='']
  a.check(int(p['matched_scene_count'])==int(p['left_scene_count'])==int(p['right_scene_count'])==240 and int(p['paired_scenes'])==len(group),'paired scope')
  for l,z in group:a.check(l['population']==z['population'] and l[prefix+'_reference_words']==z[prefix+'_reference_words'],'paired exact denominator')
  den=sum(int(l[prefix+'_reference_words']) for l,z in group);le=sum(int(l[prefix+'_errors']) for l,z in group);re=sum(int(z[prefix+'_errors']) for l,z in group)
  for k,v in [('reference_words',den),('left_errors',le),('right_errors',re),('right_minus_left_errors',re-le)]:a.check(int(p[k])==v,'paired sums')
  a.check(equal(number(p['right_minus_left_pp']),100*(re-le)/den if den else None),'paired sign')
  for room in json.loads(p['rooms']):
   group_room=[(l,z) for l,z in group if l['room']==room['room']];a.check(room['scenes']==len(group_room) and room['reference_words']==sum(int(l[prefix+'_reference_words']) for l,z in group_room) and room['left_errors']==sum(int(l[prefix+'_errors']) for l,z in group_room) and room['right_errors']==sum(int(z[prefix+'_errors']) for l,z in group_room),'room sums')
  if prefix=='word':a.check(int(p['lexical_changed_scenes'])==sum(l['normalized_final_text']!=z['normalized_final_text'] for l,z in group),'paired text change')
 a.check(len(pairs)==252 and len({p['comparison_id'] for p in pairs})==18,'18 contrasts/252 metric rows')
 for row in summary['complete_population']:
  rs=choose([r for r in scenes if (r['profile_id'],r['stream'])==(row['profile_id'],row['stream'])],'ALL_COMPLETE_NONEMPTY')
  for k,v in row.items():
   if k in ('profile_id','stream'):continue
   calc=len(rs) if k=='scenes' else (100*sum(int(r['unknown_samples']) for r in rs)/sum(int(r['sole_active_samples']) for r in rs) if k=='unknown_percent' else (100*sum(int(r['false_merge_samples']) for r in rs)/sum(int(r['sole_active_samples']) for r in rs) if k=='mixed_percent_all_sole' else math.fsum(float(r[k]) for r in rs)))
   a.check(equal(v,calc),'summary headline')
 a.check(summary['all_profile_population_rows']==profiles,'summary all profile rows exact')
 for row in summary['short_turns']:a.check(row in short,'summary short row exact')
 for row in summary['lifecycle_all240']:
  ls=[r for r in life if (r['profile_id'],r['stream'])==(row['profile_id'],row['stream'])];calc=dict(scenes=len(ls),maximum_peak_live=max(int(r['peak_live']) for r in ls),maximum_peak_archive=max(int(r['peak_archive']) for r in ls),blocked_unique_evidence_sec=math.fsum(float(r['blocked_unique_evidence_sec']) for r in ls),cumulative_retirements_sum=sum(int(r['final_cumulative_retirements']) for r in ls),lifetime_external_ids_sum=sum(int(r['final_lifetime_external_ids']) for r in ls))
  a.check(all(equal(row[k],v) for k,v in calc.items()),'summary lifecycle')
  for field in ('lineage_counts','activation_counts'):
   total=Counter()
   for r in ls:total.update(json.loads(r[field]))
   a.check(row[field]==dict(total),'summary lifecycle logged counters')
 for row in summary['native_nested_cost_all240']:
  rs=[r for r in scenes if (r['profile_id'],r['stream'])==(row['profile_id'],row['stream'])];costs=[json.loads(r['recipe_costs']) for r in rs]
  a.check(row['source_cells']==len(rs)==240 and equal(row['source_duration_sec'],math.fsum(float(r['duration_sec']) for r in rs)),'cost source denominator')
  for k,v in row.items():
   if '.' not in k:continue
   section,field=k.split('.');values=[c[section][field] for c in costs if isinstance(c.get(section),dict) and c[section].get(field) is not None];a.check(v['observed_cells']==len(values) and v['unavailable_cells']==240-len(values) and equal(v['sum'],math.fsum(values)),'observed nested cost')
 cost_rows=[r for doc in (parent,core) for r in a.table(doc,'RECIPE_COST_RESULTS')]
 for pid in PIDS:
  for tap in ('O0','O1'):
   cost=[r for r in cost_rows if r['stream']==tap and pid in json.loads(r['profile_reusers'])]
   a.check(len(cost)==len({r['neural_source_key'] for r in cost})==240,'240 distinct native-cost sources per requested route')
   for row in cost:
    scene=by[pid,tap,tap,row['case_id']]
    a.check(row['recipe_costs']==scene['recipe_costs'] and row['duration_sec']==scene['duration_sec'],'native cost table/source-cell equality')
 word_empty=[];empty_examples=[]
 for row in summary['word_and_empty_changes']:
  pid,tap=row['profile_id'],row['stream'];paired=[(by['C065',tap,tap,c],by[pid,tap,tap,c]) for c in sorted(cases)];empty=[(l,z) for l,z in paired if l['population']=='STRICT_EMPTY_REFERENCE']
  calc=dict(cases=11,left_insertions=sum(int(l['empty_insertions']) for l,z in empty),right_insertions=sum(int(z['empty_insertions']) for l,z in empty),left_nonempty_final_text_cases=sum(bool(l['normalized_final_text'].strip()) for l,z in empty),right_nonempty_final_text_cases=sum(bool(z['normalized_final_text'].strip()) for l,z in empty))
  a.check(row['cases']==240 and row['normalized_final_text_equal_cells']==sum(l['normalized_final_text']==z['normalized_final_text'] for l,z in paired) and row['normalized_final_text_changed_cells']==sum(l['normalized_final_text']!=z['normalized_final_text'] for l,z in paired),'full-bank word equal/changed')
  a.check(row['strict_empty']==calc and len(empty)==11,'all11 empty counters');word_empty.append(row)
  for l,z in empty:
   if l['normalized_final_text']!=z['normalized_final_text']:
    empty_examples.append(dict(profile_id=pid,stream=tap,case_id=l['case_id'],left_text=l['normalized_final_text'],right_text=z['normalized_final_text'],left_insertions=int(l['empty_insertions']),right_insertions=int(z['empty_insertions']),left_row_sha256=hashlib.sha256(canonical(l)).hexdigest(),right_row_sha256=hashlib.sha256(canonical(z)).hexdigest(),scope='Exact scored-final-text empty-control witness; no new native-log or reset verification.'))
 examples=[]
 for pid in ('C072','C074'):
  for tap in ('O0','O1'):
   for metric in ('word_errors','cp_latest_revised_errors'):
    denominator='word_reference_words' if metric=='word_errors' else 'cp_latest_revised_reference_words'
    values=[(Fraction(int(by[pid,tap,tap,c][metric])-int(by['C065',tap,tap,c][metric]),int(by[pid,tap,tap,c][denominator])),c) for c in cases if by[pid,tap,tap,c]['population'] in COMPLETE]
    extremes=[('largest_observed_harm',v,c) for v,c in sorted(values,key=lambda x:(-x[0],x[1]))[:2]]+[('largest_observed_benefit',v,c) for v,c in sorted(values,key=lambda x:(x[0],x[1]))[:2]]
    for direction,delta,c in extremes:
     owner=next(r for r in summary['selected_extreme_case_examples'] if (r['right_profile'],r['stream'],r['metric'],r['selection'],r['case_id'])==(pid,tap,metric,direction,c));a.check(equal(owner['signed_delta_pp'],100*float(delta)),'deterministic signed extreme')
     e=dict(profile_id=pid,stream=tap,metric=metric,selection=direction,case_id=c,delta_pp=100*float(delta),observed_direction='harm' if delta>0 else 'benefit' if delta<0 else 'equal',source_scope='Exact scored CSV witnesses; post-result extrema, not typical outcomes or causal mechanism evidence.',turns=[])
     for side,p in [('left','C065'),('right',pid)]:
      original=by[p,tap,tap,c];a.check(all(original[k]==v for k,v in owner[side].items()),'extreme exact scalar fields');e[side]=dict(owner[side],normalized_final_text=original['normalized_final_text'],row_sha256=hashlib.sha256(canonical(original)).hexdigest())
      for t in turns:
       if (t['profile_id'],t['stream'],t['case_id'])==(p,tap,c):e['turns'].append({k:t[k] for k in ('profile_id','segment_index','source_id','whole_clip_bin','modal_label','return_status','sole_active_samples','known_samples','unknown_samples','predicted_labels','contained_embedding_count','duration_mapping_status','modal_duration_mapped_correct')})
     e['same_scored_final_text']=e['left']['normalized_final_text']==e['right']['normalized_final_text'];examples.append(e)
 ub=next(x for x in cmp['artifacts'] if Path(x['path']).name=='PAIRED_UNCERTAINTY.json');unc=a.obj(ub)
 for u in unc['comparisons']:
  a.check(u['replicates']==2000 and u['included_primary_scenes']==u['requested_primary_scenes']==156 and u['matched_block_count']==116 and u['observed_rooms']==5 and u['excluded_whole_blocks']==[],'uncertainty denominator')
  p=next(p for p in pairs if p['comparison_id']==u['comparison_id'] and p['metric']=='word' and p['population']=='PRIMARY_NONOVERLAP');v=u['primary_on_included_blocks'];a.check(v['paired_scenes']==156 and v['O0']['errors']==int(p['left_errors']) and v['O1']['errors']==int(p['right_errors']) and equal(v['O1_minus_O0_wer_pp'],float(p['right_minus_left_pp'])),'uncertainty exact observed point')
 a.check(len(unc['comparisons'])==18,'18 uncertainty groups')
 result=dict(status='PASS_INDEPENDENT_FULL_N08_N10_TABLE_REVIEW',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=a.count,code=binding(__file__),readme=binding(HERE/'README_S6C_N08_N10_COMPONENT_REVIEW_V1.md'),sources=list(a.sources.values()),population_denominators=denominators,profile_rows_checked=len(profiles),short_rows_checked=len(short),turn_rows_checked=len(turns),comparison_rows_checked=len(pairs),uncertainty_observed_points_checked=18,summary_complete_rows=summary['complete_population'],summary_short_rows=summary['short_turns'],summary_native_nested_cost=summary['native_nested_cost_all240'],word_and_empty_changes=word_empty,empty_changed_examples=empty_examples,adverse_and_benefit_examples=examples,limits=['Original completed core/selected-comparison CSV and compact JSON only. No audio, vectors, predictions, native events, neural/policy/scoring run.','Historical selected text/scores retain completed comparison authority; the sealed original53MB historical table was not reread. Current C065/C072/C074 selected cells independently equal original core CSV buffers.','ALL_COMPLETE lexical counts combine primary serialized and overlap MIMO values. They are not a single serialized-WER or phonetic clipping metric.','Complete203/6016/693/292, incomplete26/84/32 and empty11 populations remain separate. Unknown support is not synonymous with incorrect assignment.','Cost sections are observed/missing nested timing sums, not total CPU/wall or paced throughput. Different batches and reused panel cells remain inherited source conditions.','Short evidence waits are observed-only contained evidence/support values with censored missingness, not guaranteed display or wall latency.','Extrema follow the owner declared Fraction/tie order. A zero signed difference is labeled observed_direction equal, even where the owner selection label says largest harm/benefit.','Bootstrap samples and intervals are bound, not rerun; only primary-word observed point, block and room denominators reconciled. No cp intervals inferred.'])
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(binding(output)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',required=True,type=Path);run(p.parse_args().output)
