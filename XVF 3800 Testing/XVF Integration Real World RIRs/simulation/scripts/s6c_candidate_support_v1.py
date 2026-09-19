"""Exact analysis support inventory. See README_S6C_CANDIDATE_SUPPORT_V1.md."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,csv,hashlib,io,json,re,tempfile
SCHEMA='s6c-candidate-support-spec.v1'
LIMIT=128*2**20
HISTORICAL_IDS={f'B{i:02d}' for i in range(40)}|{'B18_C1','B20_C1','B24_FREQUENT','B24_SPARSE'}
def require(ok,message):
 if not ok:raise ValueError(message)
def binding(p,raw=None):
 p=Path(p).resolve();raw=p.read_bytes() if raw is None else raw
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
class Reader:
 def __init__(self):self.buffers={};self.sources=[]
 def raw(self,b):
  require(set(b)=={'path','bytes','sha256'} and Path(b['path']).is_absolute(),'Exact absolute binding required')
  require(type(b['bytes']) is int and 0<=b['bytes']<=LIMIT and re.fullmatch('[a-f0-9]{64}',b['sha256']),'Bounded exact source required')
  k=str(Path(b['path']).resolve()).casefold()
  if k in self.buffers:
   prior,raw=self.buffers[k];require(prior==b,'Conflicting repeated binding');return raw
  raw=Path(b['path']).read_bytes();require(binding(b['path'],raw)==b,'Changed exact source '+b['path'])
  self.buffers[k]=(b,raw);self.sources.append(b);return raw
 def json(self,b):return json.loads(self.raw(b),parse_constant=lambda v:require(False,'Nonfinite JSON'))
def pointer(value,path):
 require(isinstance(path,str) and path.startswith('/'),'Explicit JSON pointer required')
 for part in path[1:].split('/'):
  part=part.replace('~1','/').replace('~0','~');value=value[int(part)] if isinstance(value,list) else value[part]
 return value
def registry(c,b):
 groups=defaultdict(list)
 for r in c['profiles']:
  key=r['candidate_id'];require(re.fullmatch(r'C\d{3}',key),'Exact C identity required');groups[key].append(r)
 require(set(groups)=={f'C{i:03d}' for i in range(1,197)} and len(c['profiles'])==388,'Final 196-C/388-route scope differs')
 result={}
 for key,rows in groups.items():
  routes=[(r['asr_tap'],r['identity_tap']) for r in rows]
  require(len(routes)==len(set(routes)),'Duplicate registered C route')
  require(all(t in ('O0','O1') for pair in routes for t in pair),'Unsupported source route')
  result[key]=dict(origin='S6C_NEW',family=rows[0]['family'],parent=rows[0]['parent'],recipe_id=rows[0]['recipe_id'],routes=sorted(routes),effective_rows=rows)
 historical=[r for r in b['candidates'] if r['candidate_id'].startswith('B')]
 require({r['candidate_id'] for r in historical}==HISTORICAL_IDS and len(historical)==44,'Exact 44 historical controls required')
 for r in historical:
  result[r['candidate_id']]=dict(origin='PRESERVED_S6B',family=r['family'],parent=r['parent'],recipe_id=r['old_profile']['recipe_id'],routes=[('O0','O0'),('O1','O1')],effective_rows=[r['old_profile']])
 return result
def parse_coverage(raw,identity_mode):
 require(identity_mode in ('explicit_column','historical_same_tap'),'Explicit route schema required')
 reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
 fields=reader.fieldnames or [];require(len(fields)==len(set(fields)) and {'profile_id','stream','case_id','status'}<=set(fields),'Exact unique coverage header required')
 require(('identity_tap' in fields)==(identity_mode=='explicit_column'),'Identity column/schema differs')
 rows=[];seen=set()
 for r in reader:
  require(None not in r and all(v is not None for v in r.values()),'Ragged coverage row')
  identity=r['identity_tap'] if identity_mode=='explicit_column' else r['stream'];key=r['profile_id'],r['stream'],identity,r['case_id']
  require(key not in seen,'Duplicate route/scene within one authority');seen.add(key)
  require(r['status'] in ('SCORED','UNSCORED','FAILED','ERROR'),'Explicit supported coverage status required')
  rows.append(dict(candidate_id=key[0],asr_tap=key[1],identity_tap=key[2],case_id=key[3],status=r['status']))
 return rows
def summarize(rows,population,registered,scope):
 grouped=defaultdict(list)
 for r in rows:
  require(r['candidate_id'] in registered,'Unknown candidate')
  require((r['asr_tap'],r['identity_tap']) in registered[r['candidate_id']]['routes'],'Unregistered route')
  require(r['case_id'] in population,'Unknown canonical case')
  grouped[r['candidate_id'],r['asr_tap'],r['identity_tap']].append(r)
 out=[]
 for key,part in sorted(grouped.items()):
  scored={r['case_id'] for r in part if r['status']=='SCORED'}
  out.append(dict(candidate_id=key[0],asr_tap=key[1],identity_tap=key[2],source_id=scope['source_id'],scope_label=scope['scope_label'],execution_scope=scope['execution_scope'],repetition=scope['repetition'],analysis_authority=scope['authority'],route_rows=len(part),status_counts=dict(Counter(r['status'] for r in part)),scored_cases=sorted(scored),full_bank_in_this_authority=scored==population))
 return out
def write_json(p,value):
 with p.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
 return binding(p)
def write_csv(p,rows):
 fields=list(rows[0])
 with p.open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
  for row in rows:w.writerow({k:json.dumps(v,sort_keys=True,separators=(',',':')) if isinstance(v,(dict,list,tuple)) else '' if v is None else v for k,v in row.items()})
 return binding(p)
def run(spec_b,output):
 reader=Reader();spec=reader.json(spec_b);require(spec['schema']==SCHEMA and spec['status']=='APPROVED_EXPLICIT_SUPPORT_SNAPSHOT','Explicit support snapshot required')
 require(not output.exists(),'Fresh output directory required')
 candidates=registry(reader.json(spec['c_registry']),reader.json(spec['b_design']))
 inputs=reader.json(spec['input_index'])['rows'];pairs={(r['case_id'],r['stream']) for r in inputs};population={x[0] for x in pairs}
 require(len(inputs)==len(pairs)==480 and len(population)==240 and pairs=={(c,t) for c in population for t in ('O0','O1')},'Original 240-scene/two-tap source population required')
 summaries=[];seen=set();authority_paths=set();authority_hashes=set();coverage_paths=set();coverage_contents=defaultdict(list)
 for item in spec['authorities']:
  require(re.fullmatch('[A-Za-z0-9_-]{1,80}',item['source_id']) and item['source_id'] not in seen,'Unique simple authority ID required');seen.add(item['source_id'])
  require(type(item['repetition']) is int and item['repetition']>=0 and item['scope_label'] and item['execution_scope'],'Explicit repetition/scope labels required')
  identity=str(Path(item['authority']['path']).resolve()).casefold();sha=item['authority']['sha256']
  require(identity not in authority_paths and sha not in authority_hashes,'Duplicate authority alias');authority_paths.add(identity);authority_hashes.add(sha)
  authority=reader.json(item['authority']);require(authority.get('schema')==item['expected_schema'] and authority.get('status')==item['expected_status'] and item['expected_status'].startswith('COMPLETE'),'Exact completed analysis authority required')
  cb=pointer(authority,item['coverage_pointer']);require(Path(cb['path']).name=='COVERAGE.csv','Coverage pointer must bind exact coverage CSV')
  coverage_identity=str(Path(cb['path']).resolve()).casefold()
  require(coverage_identity not in coverage_paths,'Duplicate coverage table path alias');coverage_paths.add(coverage_identity);coverage_contents[cb['sha256']].append(item['source_id'])
  rows=parse_coverage(reader.raw(cb),item['identity_mode']);require(rows and len(rows)==authority['requested'],'Authority coverage count differs')
  scored=sum(r['status']=='SCORED' for r in rows)
  require(scored==authority[item['scored_count_field']],'Authority scored count differs')
  part=summarize(rows,population,candidates,item)
  for row in part:row['coverage_binding']=cb
  summaries.extend(part)
 output.mkdir(parents=True)
 rows=[]
 for key,reg in sorted(candidates.items()):
  support=[x for x in summaries if x['candidate_id']==key];route_rows=[]
  for a,i in reg['routes']:
   matches=[x for x in support if (x['asr_tap'],x['identity_tap'])==(a,i)]
   union=set().union(*(set(x['scored_cases']) for x in matches)) if matches else set()
   route_rows.append(dict(asr_tap=a,identity_tap=i,case_union_count=len(union),authority_references=len(matches),scored_authority_references=sum(bool(x['scored_cases']) for x in matches),full_bank_authorities=[x['source_id'] for x in matches if x['full_bank_in_this_authority']],paced_authorities=[x['source_id'] for x in matches if x['execution_scope']=='ACTUAL_SOURCE_PACED_NATIVE']))
  rows.append(dict(candidate_id=key,origin=reg['origin'],family=reg['family'],parent=reg['parent'],recipe_id=reg['recipe_id'],registered_routes=reg['routes'],route_support=route_rows,observed_support='EXPLICIT_SCORED_AUTHORITIES' if any(x['scored_cases'] for x in support) else 'DECLARED_AUTHORITIES_WITH_NO_SCORED_CASES' if support else 'NO_SCORED_AUTHORITY_IN_THIS_SNAPSHOT',disposition='PENDING_FINAL_SCIENTIFIC_DISPOSITION',physical_inference_count=None,count_scope='Case unions are coverage only, never a pooled accuracy result or count of native/model executions.'))
 outputs=[write_csv(output/'CANDIDATE_SUPPORT_WORKING.csv',rows),write_json(output/'AUTHORITY_ROUTE_SUPPORT.json',summaries)]
 result=dict(schema='s6c-candidate-support-snapshot.v1',status='COMPLETE_EXPLICIT_SUPPORT_SNAPSHOT',whole_study_complete=False,specification=spec_b,sources=reader.sources,helper=binding(__file__),readme=binding(Path(__file__).with_name('README_S6C_CANDIDATE_SUPPORT_V1.md')),candidates=len(rows),new_candidates=196,historical_candidates=44,authorities=len(seen),authority_routes=len(summaries),equal_coverage_content_groups=[dict(sha256=sha,source_ids=ids,scope='Equal coverage-table content from distinct paths and authorities; clocks/repetitions remain separate.') for sha,ids in sorted(coverage_contents.items()) if len(ids)>1],outputs=outputs,model_calls=0,policy_replays=0,score_payload_reads=0,scope='Completed explicitly supplied coverage authorities only. No automatic source discovery, outcome ranking, inference counting, alias propagation or final candidate selection. Registered missing support remains visible. Original analysis clocks/populations/repetitions remain separate.')
 return write_json(output/'RECEIPT.json',result)
def checks():
 checks=[]
 def bad(name,fn):
  try:fn()
  except (ValueError,KeyError):checks.append(name);return
  raise AssertionError(name)
 raw=b'profile_id,stream,identity_tap,case_id,status\nC001,O0,O0,X,SCORED\n'
 rows=parse_coverage(raw,'explicit_column');reg={'C001':dict(routes=[('O0','O0')])};scope=dict(source_id='x',scope_label='fixture',execution_scope='SYNTHETIC_TEST',repetition=0,authority={})
 assert summarize(rows,{'X','Y'},reg,scope)[0]['full_bank_in_this_authority'] is False;checks.append('subset is not full bank')
 assert summarize(rows,{'X'},reg,scope)[0]['full_bank_in_this_authority'] is True;checks.append('one authority exact population')
 for name,data in [('duplicate',raw+raw.splitlines(keepends=True)[1]),('ragged',raw+b'C001,O0\n'),('unknown status',raw.replace(b'SCORED',b'COMPLETE'))]:
  bad(name,lambda data=data:parse_coverage(data,'explicit_column'))
 bad('identity schema mismatch',lambda:parse_coverage(raw,'historical_same_tap'))
 bad('unknown scene',lambda:summarize(rows,{'Y'},reg,scope))
 bad('unknown candidate',lambda:summarize(rows,{'X'},{},scope))
 bad('unregistered route',lambda:summarize(rows,{'X'},{'C001':dict(routes=[('O0','O1')])},scope))
 changed=[dict(rows[0],status='FAILED')];assert summarize(changed,{'X'},reg,scope)[0]['scored_cases']==[];checks.append('failed does not become scored')
 historical=raw.replace(b',identity_tap',b'').replace(b'O0,O0',b'O0');assert parse_coverage(historical,'historical_same_tap')[0]['identity_tap']=='O0';checks.append('explicit inherited same-tap schema')
 with tempfile.TemporaryDirectory(prefix='s6c_support_checks_') as td:
  p=Path(td)/'test.json';p.write_bytes(b'{}');b=binding(p);r=Reader();assert r.json(b)=={};p.write_bytes(b'[]');assert r.json(b)=={};checks.append('same verified buffer retained')
  bad('changed input bytes',lambda:Reader().json(b));bad('conflicting buffer declaration',lambda:r.raw(binding(p)))
 return dict(status='PASS_PURE_CHECKS',checks=checks,model_calls=0,actual_score_reads=0)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['checks','run']);p.add_argument('--spec',nargs=2);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.action=='checks':result=write_json(a.output,dict(checks(),helper=binding(__file__),readme=binding(Path(__file__).with_name('README_S6C_CANDIDATE_SUPPORT_V1.md'))))
 else:
  require(a.spec,'Exact specification path SHA required');b=binding(a.spec[0]);require(b['sha256']==a.spec[1],'Caller specification hash differs');result=run(b,a.output)
 print(json.dumps(result))

