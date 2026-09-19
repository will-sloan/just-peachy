"""Full anonymous paired failure audit; README_S6C_FULL_ANONYMOUS_REVIEW_V1.md."""
import argparse
import ast
from collections import Counter
from datetime import datetime,timezone
from fractions import Fraction
import csv,gzip,hashlib,io,json,math
from pathlib import Path

SIM=Path(__file__).resolve().parents[1];REPORT=SIM/'reports/S6C/20260910T123540Z'
SOURCE=REPORT/'full_n01_anonymous_core_v3/ANALYSIS_RECEIPT.json'
SOURCE_SHA='72af65710f4bbc45733bd6f145fbd4eb67ce558b8c3bbdad01b9c2c807c4e094'
OUT=REPORT/'full_anonymous_component_review_v1'
PAIRS=[('C117','C118'),('C065','C079'),('C119','C120'),('C121','C122')]
COMPLETE={'PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'}

def need(ok,msg):
 if not ok:raise ValueError(msg)

def binding(p,raw=None):
 p=Path(p);raw=p.read_bytes() if raw is None else raw
 return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

class Reader:
 def __init__(self):self.bindings={};self.cache={}
 def raw(self,b):
  p=Path(b['path']);key=str(p.resolve())
  if key not in self.cache:self.cache[key]=p.read_bytes()
  raw=self.cache[key];actual=binding(p,raw)
  need(actual['sha256']==b['sha256'] and ('bytes' not in b or actual['bytes']==b['bytes']),'Changed bound input: '+key)
  self.bindings[key]=actual;return raw
 def json(self,b):
  raw=self.raw(b);return json.loads(gzip.decompress(raw) if str(b['path']).endswith('.gz') else raw)
 def table(self,receipt,name):
  rows=[b for b in receipt['tables'] if Path(b['path']).name==name];need(len(rows)==1,'One exact table required')
  return list(csv.DictReader(io.StringIO(self.raw(rows[0]).decode('utf-8-sig'))))

def write_new(path,value):
 with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')

def prepare():
 need(not OUT.exists(),'Fresh review namespace required');OUT.mkdir(parents=True)
 plan=dict(schema='s6c-full-anonymous-adverse-selection.v1',created_utc=datetime.now(timezone.utc).isoformat(),source=dict(path=str(SOURCE),sha256=SOURCE_SHA),
  pairs=PAIRS,taps=['O0','O1'],population=sorted(COMPLETE),selection_metric='maximum positive right-minus-left latest-revised complete-scene cpWER',
  exact_selection='Compare integer (right_errors-left_errors)/shared_reference_words as fractions; tie ascending case_id. One scene per pair/tap, at most8 paired examples. No positive delta means no adverse example.',
  output_scope='Aggregate80 population rows from small bound scene table, retain16 complete rows and population-specific denominators; inspect at most16 selected score/prediction objects and selected reference support. No native event/audio/model scan.',
  helper=binding(__file__),readme=binding(Path(__file__).with_name('README_S6C_FULL_ANONYMOUS_REVIEW_V1.md')))
 write_new(OUT/'PLAN.json',plan);print(json.dumps(binding(OUT/'PLAN.json')))

def value(text):
 if text=='':return None
 if text.startswith('{') or text.startswith('['):return json.loads(text)
 try:
  n=float(text);need(math.isfinite(n),'Nonfinite table value');return int(n) if n.is_integer() else n
 except ValueError:
  if text in ('nan','NaN','inf','-inf','Infinity'):raise
  return text

def selection(rows,left,right,tap):
 a={r['case_id']:r for r in rows if r['profile_id']==left and r['stream']==tap and r['population'] in COMPLETE}
 b={r['case_id']:r for r in rows if r['profile_id']==right and r['stream']==tap and r['population'] in COMPLETE}
 need(len(a)==len(b)==203 and set(a)==set(b),'Complete paired203-scene population required')
 options=[]
 for cid in sorted(a):
  ar,br=a[cid],b[cid];n=ar['cp_latest_revised_reference_words']
  need(n==br['cp_latest_revised_reference_words'] and n>0,'Exact positive paired cp denominator')
  delta=Fraction(br['cp_latest_revised_errors']-ar['cp_latest_revised_errors'],n)
  if delta>0:options.append((delta,cid,ar,br))
 return sorted(options,key=lambda x:(-x[0],x[1]))[0] if options else None

def reconcile(rd,receipt,rows):
 code=next(b for b in receipt['codes'] if Path(b['path']).name=='s6b_analysis.py');tree=ast.parse(rd.raw(code))
 ns={'math':math,'Counter':Counter}
 wanted={'finite','rate','pool'};nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
 need({n.name for n in nodes}==wanted,'Exact inherited aggregate helpers required')
 exec(compile(ast.Module(body=nodes,type_ignores=[]),code['path'],'exec'),ns)
 checks=0;pooled=[]
 for expected in receipt['results']:
  rs=[r for r in rows if (r['profile_id'],r['stream'])==(expected['profile_id'],expected['stream']) and
    (r['population'] in COMPLETE if expected['population']=='ALL_COMPLETE_NONEMPTY' else r['population']==expected['population'])]
  actual=ns['pool'](rs,expected['profile_id'],expected['stream'],expected['population'])
  need(set(actual)==set(expected),'Aggregate key set changed')
  for k,v in actual.items():
   ev=expected[k]
   need(math.isclose(v,ev,abs_tol=1e-9,rel_tol=1e-12) if isinstance(v,float) else v==ev,'Aggregate mismatch '+str((expected['profile_id'],expected['stream'],expected['population'],k)));checks+=1
  pooled.append(actual)
 return pooled,checks

def fields(r):
 keys=['population','word_errors','word_reference_words','cp_first_final_errors','cp_latest_revised_errors','cp_first_display_label_final_words_errors','cp_latest_revised_reference_words',
  'source_turns','unknown_turns','sole_active_samples','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown']
 return {k:r[k] for k in keys}

def run():
 planraw=(OUT/'PLAN.json').read_bytes();plan=json.loads(planraw);need(plan['helper']==binding(__file__),'Held review helper changed')
 need(plan['pairs']==[list(p) for p in PAIRS] and plan['source']['sha256']==SOURCE_SHA,'Prospective selection changed')
 rd=Reader();receipt=rd.json(plan['source']);need(receipt['status']=='COMPLETE_REQUESTED_INDEX' and receipt['requested']==receipt['scored']==3840 and receipt['unscored']==0,'Complete3840 scores required')
 rows=[{k:value(v) for k,v in r.items()} for r in rd.table(receipt,'SCENE_RESULTS.csv')]
 keys=[(r['profile_id'],r['stream'],r['identity_tap'],r['case_id']) for r in rows]
 wanted={(p,t,t,cid) for pair in PAIRS for p in pair for t in ('O0','O1') for cid in receipt['case_ids']}
 need(len(keys)==len(set(keys))==3840 and set(keys)==wanted,'Exact3840 unique same-tap routes required')
 pooled,checks=reconcile(rd,receipt,rows)
 denoms=[]
 for r in pooled:
  returns=sum(r[k] for k in ['return_consistent','return_inconsistent','return_unknown'])
  if r['population']=='ALL_COMPLETE_NONEMPTY':need((r['scenes'],r['word_reference_words'],r['source_turns'],returns)==(203,6016,693,292),'Complete denominator mismatch')
  elif r['population']=='INCOMPLETE_REFERENCE':need((r['scenes'],r['source_turns'],returns)==(26,84,32),'Incomplete denominator mismatch')
  elif r['population']=='PRIMARY_NONOVERLAP':need((r['scenes'],r['word_reference_words'])==(156,4560),'Primary denominator mismatch')
  elif r['population']=='STRICT_EMPTY_REFERENCE':need(r['scenes']==11 and r['word_rate'] is None,'Empty denominator mismatch')
  denoms.append(dict(profile_id=r['profile_id'],tap=r['stream'],population=r['population'],scenes=r['scenes'],reference_words=r.get('word_reference_words'),turns=r['source_turns'],returns=returns))
 coverage=rd.table(receipt,'COVERAGE.csv');bycov={(r['profile_id'],r['stream'],r['identity_tap'],r['case_id']):r for r in coverage}
 need(len(bycov)==len(coverage)==3840 and set(bycov)==wanted,'Coverage grid mismatch')
 index=rd.json(receipt['index']);predmap={(r['candidate_id'],r['stream'],r['identity_tap'],r['case_id']):r for r in index['rows']}
 need(len(predmap)==len(index['rows'])==3840 and set(predmap)==wanted,'Prediction index grid mismatch')
 bank=rd.json(receipt['bank']);scenes={s['case_id']:s for s in bank['scenes']}
 examples=[]
 for left,right in PAIRS:
  for tap in ('O0','O1'):
   selected=selection(rows,left,right,tap)
   if selected is None:examples.append(dict(left=left,right=right,tap=tap,status='NO_POSITIVE_COMPLETE_SCENE_CP_HARM'));continue
   delta,cid,lr,rr=selected;objects=[]
   for pid in (left,right):
    key=pid,tap,tap,cid;c=bycov[key];need(c['status']=='SCORED','Selected score missing')
    sb=json.loads(c['result']);score=rd.json(sb);pb=predmap[key]['result'];pred=rd.json(pb)
    need(score['analysis_identity']['prediction']==pb and score['analysis_identity']['bank']==receipt['bank'],'Score prediction/reference chain mismatch')
    support=rd.json(score['analysis_identity']['support'])
    need((score['profile_id'],score['stream'],score['identity_tap'],score['case_id'])==key and pred['status']=='COMPLETE','Selected identity/completion mismatch')
    # Compact excerpts are deliberately exported only for selected adverse scenes.
    finals={k:pred[k] for k in ['final_transcripts_first','final_transcripts_latest','final_transcripts_first_display']}
    objects.append(dict(profile_id=pid,score_binding=sb,prediction_binding=pb,support_binding=score['analysis_identity']['support'],
      neural_source_binding=score['neural_source_binding'],metrics=fields(lr if pid==left else rr),finals=finals,
      turns=[{k:t[k] for k in ['segment_index','speaker_key','source_id','whole_clip_bin','sole_active_samples','unknown_samples','label_samples','modal_label','return_status','duration_mapping_status','modal_duration_mapped_correct']} for t in score['turns']],
      source_identity=pred['identity'].get('source'),transcript_event_counts=score['transcript_event_counts']))
   a,b=objects
   words=lambda x:[(r['utterance_index'],r['text']) for r in x['finals']['final_transcripts_latest']]
   need(words(a)==words(b),'Paired ASR content differs; cannot attribute cp change solely to labels')
   need(a['neural_source_binding']==b['neural_source_binding'],'Paired neural source differs')
   ref=[dict(segment_index=i,speaker_key=s['speaker_key'],source_id=s['source_id'],start_sample=s['source_start_sample'],stop_sample=s['source_stop_sample'],text=s['transcript']) for i,s in enumerate(scenes[cid]['segments']) if s.get('kind')=='utterance']
   examples.append(dict(left=left,right=right,tap=tap,case_id=cid,status='SELECTED_POSITIVE_COMPLETE_SCENE_HARM',population=lr['population'],
    latest_cp_delta_fraction=[delta.numerator,delta.denominator],latest_cp_delta=float(delta),same_raw_ASR_words=True,same_native_source=True,reference_utterances=ref,off=a,real=b))
 result=dict(status='PASS_FULL_ANONYMOUS_SOURCE_BOUND_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),plan=binding(OUT/'PLAN.json',planraw),
  source=plan['source'],aggregate_fields_reconciled=checks,population_rows_reconciled=len(pooled),complete_population_rows=[r for r in pooled if r['population']=='ALL_COMPLETE_NONEMPTY'],
  population_denominators=denoms,selected_adverse_examples=examples,source_bindings=list(rd.bindings.values()),
  limits=['Descriptive selected worst-case examples after observed full-bank outcomes; not a random sample, confidence interval or global winner selection.',
   'Anonymous labels can be permuted; a changed label number alone is not an error. cp uses global per-scene text assignment; turn/Unknown/return diagnostics are separate.',
   'Complete203/693turn/292return and incomplete26/84turn/32return populations remain separate. ASR text is identical in each selected pair; observed harm concerns attribution.',
   'No native event/audio/model rescans. One pre-selection score from the first coverage row was inspected solely to identify schema, without inspecting its pair or using it for selection.',
   'Inherited source support is approximate and modeled availability differs from paced display latency. No enrolled naming/gallery metrics or hardware conclusions.'])
 write_new(OUT/'RESULT.json',result)
 summary=summary_md(result)
 with (OUT/'FAILURE_EXAMPLES.md').open('x',encoding='utf-8') as f:f.write(summary)
 write_new(OUT/'PUBLICATION.json',dict(status='COMPLETE_BOUNDED_REVIEW',artifacts=[binding(OUT/n) for n in ('RESULT.json','FAILURE_EXAMPLES.md')],helper=binding(__file__)))
 print(json.dumps(dict(status=result['status'],fields=checks,examples=len(examples),result=binding(OUT/'RESULT.json'))))

def summary_md(result):
 lines=['# Full-bank anonymous adverse examples','',
  'All80 inherited population aggregate rows reconcile from3,840 bound scene rows. The16 complete-population rows each retain203 scenes,6016 words,693 turns and292 return opportunities. Separate incomplete rows retain26 scenes,84 turns and32 returns; primary156/4560 and strict-empty11 remain distinct.','',
  'Selection was fixed before pair inspection: largest positive real-minus-off latest-revised scene cpWER, exact fraction then ascending case ID, separately for each pair/tap. These are selected failures, not typical performance or a ranking. All selected pairs use identical actual native source and raw final ASR words.','',
  '| Off → real | Tap | Scene | Latest cp errors / words | Unknown sole samples | Return consistent / inconsistent / unknown |','|---|---|---|---|---|---|']
 for e in result['selected_adverse_examples']:
  if e['status']!='SELECTED_POSITIVE_COMPLETE_SCENE_HARM':continue
  a=e['off']['metrics'];b=e['real']['metrics'];n=a['cp_latest_revised_reference_words']
  triple=lambda r:'/'.join(str(r[k]) for k in ('return_consistent','return_inconsistent','return_unknown'))
  lines.append(f"|{e['left']} → {e['right']}|{e['tap']}|{e['case_id']}|{a['cp_latest_revised_errors']} → {b['cp_latest_revised_errors']} / {n}|{a['unknown_samples']} → {b['unknown_samples']}|{triple(a)} → {triple(b)}|")
 for e in result['selected_adverse_examples']:
  if e['status']!='SELECTED_POSITIVE_COMPLETE_SCENE_HARM':continue
  lines += ['',f"## {e['left']} → {e['right']}, {e['tap']}, {e['case_id']}",'']
  off=e['off'];real=e['real'];a=off['metrics'];b=real['metrics']
  lines.append(f"Latest cp worsens by {b['cp_latest_revised_errors']-a['cp_latest_revised_errors']} errors over {a['cp_latest_revised_reference_words']} reference words ({e['latest_cp_delta']*100:.2f} percentage points). First-final errors {a['cp_first_final_errors']} → {b['cp_first_final_errors']}; first-display-label/final-word errors {a['cp_first_display_label_final_words_errors']} → {b['cp_first_display_label_final_words_errors']}. No lexical change occurred.")
  for u,v in zip(off['finals']['final_transcripts_latest'],real['finals']['final_transcripts_latest']):
   label=lambda row:row.get('anonymous_label',row.get('speaker_label',row.get('speaker','MISSING_LABEL_FIELD')))
   if label(u)!=label(v):lines.append(f"- Final utterance {u['utterance_index']}: {label(u)} → {label(v)}. Recognized excerpt: {u['text'][:170]!r}.")
  for u,v in zip(off['turns'],real['turns']):
   need(u['segment_index']==v['segment_index'],'Turn excerpt alignment differs')
   if any(u[k]!=v[k] for k in ('modal_label','return_status','unknown_samples','modal_duration_mapped_correct')):
    lines.append(f"- Reference turn {u['segment_index']} ({u['speaker_key']}, {u['whole_clip_bin']}): modal {u['modal_label']} → {v['modal_label']}; return {u['return_status']} → {v['return_status']}; Unknown support {u['unknown_samples']} → {v['unknown_samples']} samples. Mapped-modal correctness {u['modal_duration_mapped_correct']} → {v['modal_duration_mapped_correct']}.")
 lines += ['', 'Anonymous track numbers alone have no ground-truth identity meaning; inspect their grouping and reference mapping. Global cp assignment, live Unknown support and return consistency can move in different directions. Complete/incomplete/empty denominators and modeled/paced timing must not be pooled indiscriminately. Exact score, prediction, source support and reference bindings and compact raw objects are retained in RESULT.json. No full native-event scan, new inference or winner promotion occurred.','']
 return '\n'.join(lines)

def tests():
 rows=[]
 for i in range(203):
  for pid in ('a','b'):rows.append(dict(case_id=f'c{i:03}',profile_id=pid,stream='O0',population='PRIMARY_NONOVERLAP',cp_latest_revised_reference_words=10,cp_latest_revised_errors=1 if pid=='a' else 2))
 need(selection(rows,'a','b','O0')[1]=='c000','Deterministic tie order')
 need(selection(list(reversed(rows)),'a','b','O0')[1]=='c000','Input order invariant')
 for r in rows:
  if r['profile_id']=='b':r['cp_latest_revised_errors']=1
 need(selection(rows,'a','b','O0') is None,'No harm is not fabricated')
 bad=list(rows);bad.pop()
 try:selection(bad,'a','b','O0')
 except ValueError:pass
 else:raise AssertionError('Missing paired scene accepted')
 return dict(status='PASS',checks=4,model_calls=0)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run','test']);a=p.parse_args()
 if a.mode=='test':print(json.dumps(tests()))
 else:globals()[a.mode]()
