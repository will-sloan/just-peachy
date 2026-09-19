"""Independent actual coverage-buffer reconciliation; see matching README."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse,csv,hashlib,io,json
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/S6C/20260910T123540Z'
EXPECTED='e33667f01216763ddc05decf9b99eaef28462ebccbe341c66f103f59613d6c2c'
SPEC_SHA='769f201ae9d5f116028f0f94a50f35eca0e0324dd85e21dfdc9a97668a1eb244'
REVIEW_SHA='48536f4fd9aa7686f90257fb10c79669655ed212eb56ad1b1fe3f189df785733'
class Audit:
 def __init__(self): self.sources={};self.count=0
 def check(self,ok,message):
  self.count+=1
  if not ok:raise ValueError(message)
 def read(self,path,b=None,sha=None):
  p=Path(path).resolve();raw=p.read_bytes();found={'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
  self.check(len(raw)<=128*2**20,'bounded metadata')
  if b:self.check(found==b,'exact same buffer '+str(p))
  if sha:self.check(found['sha256']==sha,'pinned source '+str(p))
  self.sources[str(p)]=found
  return raw
 def js(self,b):return json.loads(self.read(b['path'],b),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def rows(raw):return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline='')))
def main(output):
 a=Audit();p=REPORT/'candidate_support/working_v2/RECEIPT.json';r=json.loads(a.read(p,sha=EXPECTED));spec=a.js(r['specification']);a.check(r['specification']['sha256']==SPEC_SHA,'spec pin')
 a.read(REPORT/'independent_review/CANDIDATE_SUPPORT_CUES_REVIEW_V3.json',sha=REVIEW_SHA)
 a.read(r['helper']['path'],r['helper']);a.read(r['readme']['path'],r['readme'])
 a.check(r['status']=='COMPLETE_EXPLICIT_SUPPORT_SNAPSHOT' and r['whole_study_complete'] is False,'scoped completion')
 reg=a.js(spec['c_registry']);design=a.js(spec['b_design']);inputs=a.js(spec['input_index'])['rows'];pop={x['case_id'] for x in inputs}
 a.check(len(pop)==240 and len(inputs)==480 and {(x['case_id'],x['stream']) for x in inputs}=={(c,t) for c in pop for t in ['O0','O1']},'canonical population')
 registered=defaultdict(set);details={}
 for x in reg['profiles']:
  c=x['candidate_id'];route=(x['asr_tap'],x['identity_tap']);a.check(route not in registered[c],'unique C route');registered[c].add(route);details[c]=(x['family'],x['parent'],x['recipe_id'],'S6C_NEW')
 a.check(len(registered)==196 and sum(map(len,registered.values()))==388,'C grid')
 historical={f'B{i:02d}' for i in range(40)}|{'B18_C1','B20_C1','B24_FREQUENT','B24_SPARSE'}
 b=[x for x in design['candidates'] if x['candidate_id'].startswith('B')];a.check({x['candidate_id'] for x in b}==historical and len(b)==44,'B set')
 for x in b:registered[x['candidate_id']]={('O0','O0'),('O1','O1')};details[x['candidate_id']]=(x['family'],x['parent'],x['old_profile']['recipe_id'],'PRESERVED_S6B')
 outputs={Path(x['path']).name:x for x in r['outputs']};support=a.js(outputs['AUTHORITY_ROUTE_SUPPORT.json']);table=rows(a.read(outputs['CANDIDATE_SUPPORT_WORKING.csv']['path'],outputs['CANDIDATE_SUPPORT_WORKING.csv']))
 actual={(x['source_id'],x['candidate_id'],x['asr_tap'],x['identity_tap']):x for x in support};a.check(len(actual)==len(support)==742,'unique authority routes')
 expected={};by_source=[];coverage_hashes=defaultdict(list)
 for item in spec['authorities']:
  authority=a.js(item['authority']);a.check(authority['schema']==item['expected_schema'] and authority['status']==item['expected_status'],'authority completion')
  val=authority
  for key in item['coverage_pointer'].split('/')[1:]:val=val[int(key)] if isinstance(val,list) else val[key]
  raw=a.read(val['path'],val);data=rows(raw);coverage_hashes[val['sha256']].append(item['source_id']);seen=set();groups=defaultdict(list)
  for x in data:
   t=x['identity_tap'] if item['identity_mode']=='explicit_column' else x['stream'];key=(x['profile_id'],x['stream'],t,x['case_id'])
   a.check(key not in seen and key[0] in registered and key[1:3] in registered[key[0]] and key[3] in pop,'exact coverage route/scene');seen.add(key);groups[key[:3]].append(x)
  a.check(len(data)==authority['requested'] and sum(x['status']=='SCORED' for x in data)==authority[item['scored_count_field']],'authority counts')
  for route,part in groups.items():
   scored={x['case_id'] for x in part if x['status']=='SCORED'};key=(item['source_id'],)+route
   expected[key]=dict(candidate_id=route[0],asr_tap=route[1],identity_tap=route[2],source_id=item['source_id'],scope_label=item['scope_label'],execution_scope=item['execution_scope'],repetition=item['repetition'],analysis_authority=item['authority'],route_rows=len(part),status_counts=dict(Counter(x['status'] for x in part)),scored_cases=sorted(scored),full_bank_in_this_authority=scored==pop,coverage_binding=val)
   a.check(expected[key]==actual[key],'all authority route fields '+str(key))
  by_source.append(dict(source_id=item['source_id'],requested=len(data),status_counts=dict(Counter(x['status'] for x in data)),routes=len(groups),full_bank_routes=sum(expected[(item['source_id'],)+k]['full_bank_in_this_authority'] for k in groups),declared_execution_scope=item['execution_scope']))
 a.check(expected.keys()==actual.keys(),'authority key equality');a.check({x['candidate_id'] for x in table}==set(registered) and len(table)==240,'240 table rows')
 dist=Counter();missing=[];full=[]
 for x in table:
  c=x['candidate_id'];a.check(json.loads(x['registered_routes'])==[list(t) for t in sorted(registered[c])],'registered routes '+c)
  a.check((x['family'],x['parent'] or None,x['recipe_id'],x['origin'])==details[c],'metadata '+c)
  matches=[v for k,v in expected.items() if k[1]==c];route_rows=[]
  for ar,ir in sorted(registered[c]):
   part=[z for z in matches if (z['asr_tap'],z['identity_tap'])==(ar,ir)];union=set().union(*(set(z['scored_cases']) for z in part)) if part else set();fb=[z['source_id'] for z in part if z['full_bank_in_this_authority']]
   route_rows.append(dict(asr_tap=ar,identity_tap=ir,case_union_count=len(union),authority_references=len(part),scored_authority_references=sum(bool(z['scored_cases']) for z in part),full_bank_authorities=fb,paced_authorities=[z['source_id'] for z in part if z['execution_scope']=='ACTUAL_SOURCE_PACED_NATIVE']))
   dist[(x['origin'],len(union),bool(fb))]+=1
   if fb:full.append([c,ar,ir])
  a.check(json.loads(x['route_support'])==route_rows,'route support '+c)
  label='EXPLICIT_SCORED_AUTHORITIES' if any(z['scored_cases'] for z in matches) else 'DECLARED_AUTHORITIES_WITH_NO_SCORED_CASES' if matches else 'NO_SCORED_AUTHORITY_IN_THIS_SNAPSHOT'
  a.check(x['observed_support']==label and x['physical_inference_count']=='' and x['disposition']=='PENDING_FINAL_SCIENTIFIC_DISPOSITION','missing/no inference/disposition '+c)
  if label!='EXPLICIT_SCORED_AUTHORITIES':missing.append(c)
 a.check(missing==['C083','C084'],'explicit alias support gap only')
 aliases_p=REPORT/'design/SPLIT_ALIAS_DISPOSITION_V1.json';aliases=json.loads(a.read(aliases_p));ar=aliases['aliases'];a.check(aliases['status']=='NOT_EXECUTED_ALIAS_DUPLICATION_SUPERSEDED' and len(ar)==112,'preserved alias declaration');a.check(Counter(x['alias_candidate_id'] for x in ar)==Counter(C083=56,C084=56) and all(x['parent_candidate_id']=='C065' and x['actual_input_conditions_equal_after_profile_id_removal'] for x in ar),'bound aliases')
 # Only immediate report directories and small ANALYSIS_RECEIPT metadata are observed.
 supplied={str(Path(x['authority']['path']).resolve()).casefold() for x in spec['authorities']};observed=[];omitted=[]
 for d in sorted(REPORT.iterdir()):
  if not d.is_dir() or 'core' not in d.name:continue
  q=d/'ANALYSIS_RECEIPT.json'
  if not q.is_file():continue
  raw=a.read(q);v=json.loads(raw);entry=dict(binding=a.sources[str(q.resolve())],status=v.get('status'),requested=v.get('requested'),scored=v.get('scored'),supplied=str(q.resolve()).casefold() in supplied)
  observed.append(entry)
  if not entry['supplied'] and str(v.get('status','')).startswith('COMPLETE'):omitted.append(dict(entry,disposition='SMOKE_SCOPE_ALREADY_SUPERSEDED_FOR_COVERAGE' if d.name=='smoke_core_v1' else 'REVIEW_FOR_ADDITION'))
 a.check(all(x['disposition']=='SMOKE_SCOPE_ALREADY_SUPERSEDED_FOR_COVERAGE' for x in omitted),'no unlisted completed non-smoke core authority')
 result=dict(status='PASS_ACTUAL_COMPACT_SUPPORT_RECONCILIATION',checks=a.count,source_snapshot_sha256=EXPECTED,candidate_count=240,new_candidates=196,new_routes=388,historical_candidates=44,historical_routes=88,authority_count=31,authority_routes=742,per_authority=by_source,route_support_distribution=[dict(origin=k[0],case_union_count=k[1],full_bank_in_at_least_one_authority=k[2],routes=v) for k,v in sorted(dist.items())],missing_scored_candidate_ids=missing,full_bank_routes=len(full),alias_scope='C083/C084 remain unpropagated exact same-tap C065 aliases. Existing112-row disposition is bound, not replayed. C065 now has own240-scene scored support; alias reuse must stay explicit, not relabeled execution.',immediate_core_receipt_observation=observed,completed_omitted_authorities=omitted,needed_completed_authority_additions=[],sources=list(a.sources.values()),helper=bind(Path(__file__)),readme=bind(Path(__file__).with_name('README_S6C_CANDIDATE_SUPPORT_REVIEW_V1.md')),limitations=['Immediate core receipt directory observation only; no arbitrary recursive discovery or future completeness claim.','Scored coverage does not mean every metric is valid. Full bank means all240 cases in one authority; unions do not pool accuracy or establish execution.','Caller execution_scope strings are preserved labels; native receipts/physical inference were not re-audited. Actual native prediction authorities should not be inferred to have identical timing/replay paths from the generic label.','No score or prediction payloads, native logs, audio, models, current resource scans or policy replay.'],whole_study_complete=False)
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(bind(output)))
def bind(p):
 raw=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
