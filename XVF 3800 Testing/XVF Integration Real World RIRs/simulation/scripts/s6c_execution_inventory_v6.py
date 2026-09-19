"""Cross-route physical metadata extension; README_S6C_EXECUTION_INVENTORY_V6.md."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import argparse,ast,hashlib,importlib,json,math,re,types
HERE=Path(__file__).resolve().parent
PINS={'s6c_execution_inventory_v5.py':'aee67604429f12013058ed94c74c3d3965c1e8e55299c87dfb6760394513aad8','s6c_paced_cross_routes_v1.py':'0989758d797b5308573d5546114cb170b2b0b4e7e50a0fc507698c571f7992d3'}
for n,h in PINS.items():
 if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h:raise ValueError('Held V6 dependency differs: '+n)
v5=importlib.import_module('s6c_execution_inventory_v5');v4=v5.v4;v3=v5.v3;base=v5.base
if Path(v5.__file__).resolve()!=HERE/'s6c_execution_inventory_v5.py':raise ValueError('Wrong V5 import')
REPORT=v5.REPORT;PAYLOAD=v5.PAYLOAD;require=v5.require;bound=v5.bound
SCHEMA='s6c-execution-inventory-additive.v6';CROSS='s6c-cross-route-paired-paced.v1';KIND='S6C_CROSS_ROUTE_PACED_EPOCH4'
PAIR=['C085','C086'];ROUTES={'C085':('O0','O1'),'C086':('O1','O0')}
REPLACEMENTS={'s6c_paced_epoch4.py':'s6c_paced_cross_routes_v1.py','s6c-canonical-paced-cell-result.v1':'s6c-cross-route-paced-cell-result.v1','paced_candidates':'paced_cross_routes'}
NAMES={'admit_plan','expected_worker_argv','validate_launch','native_result_metadata','metadata_chain','admit_complete_cell','admit_paced_index','row_base','collect_job'}
def source_bindings():return [base.binding(p,p.read_bytes()) for p in (Path(__file__),HERE/'README_S6C_EXECUTION_INVENTORY_V6.md',*(HERE/n for n in PINS))]+v5.source_bindings()
def cross_api():
 guards=dict(v4.GUARDS)
 ns=dict(Path=Path,math=math,deepcopy=deepcopy,require=require,PAIR=PAIR,ROUTES=ROUTES,C=types.SimpleNamespace(selected_panel=guards['selected_panel']))
 v5.compile_functions(HERE/'s6c_paced_cross_routes_v1.py',{'candidate_routes','selected_panel','grid'},ns)
 for n in ('candidate_routes','selected_panel','grid'):guards[n]=ns[n]
 env={**vars(v4),'CANONICAL':CROSS,'PINS':{**v4.PINS,**PINS},'GUARDS':guards}
 v5.compile_functions(HERE/'s6c_execution_inventory_v4.py',NAMES,env,REPLACEMENTS)
 return types.SimpleNamespace(**{n:env[n] for n in NAMES},GUARDS=guards,base=base,HERE=HERE,CANONICAL=CROSS)
X=cross_api()
def admit_plan(reader,b):
 value,_=bound(reader,b)
 if value['schema']!=CROSS:return v5.admit_plan(reader,b)
 plan,pb,spec=X.admit_plan(reader,b)
 require(plan['candidates']==PAIR and len(plan['jobs'])==40 and plan['panel_mode']=='cross16_plus4','Exact40 cross grid required')
 require(plan['worker_limit']==plan['inner_threads']==1,'One worker/inner thread required')
 total=0.
 for j in plan['jobs']:
  source,_=bound(reader,j['source']);total+=source['duration_sec']
  require(j['timeout_sec']==max(720.,source['duration_sec']*1.75+j['profile_row']['profile']['runtime']['lane_drain_timeout_sec']+120.),'Exact cross worker timeout differs')
 require(total==plan['total_source_sec'],'Cross total source denominator differs')
 return plan,pb,spec

def spawn_read(reader,job,plan,pb):
 path=Path(job['report_root'])/'SPAWNED_PROCESS.json'
 if not path.exists():return None
 value,sb=reader.read(path)
 require(type(value['pid']) is int and value['pid']>0 and value['creation_time'] is None,'Successful Popen PID must be explicit, creation unavailable')
 require(value['status']=='SPAWNED_CREATION_UNVERIFIED' and value['manifest']==pb and value['job_key']==job['job_key'] and value['job_id']==job['job_id'],'Spawn job authority differs')
 return value,sb

def spawn_argv(value,job,plan,pb):X.validate_launch(value,job,plan,pb)

def unknown_spawn(job,plan,pb,value,sb,error=None):
 # Build the same declared columns without querying/reinterpreting a PID-only identity.
 ns=dict(X.row_base.__globals__);ns['owner']=lambda value:value;ns['v3']=types.SimpleNamespace(process_state=lambda *args:dict(alive=None,state='UNVERIFIED_PROCESS_IDENTITY'))
 fn=types.FunctionType(X.row_base.__code__,ns);row=fn(job,value,sb,pb,True)
 row.update(physical_id=base.digest(['cross_popen_unverified_creation',sb['path'],value['pid']]),creation_time=None,branch='CROSS_ROUTE_SINGLE_SCENE_PACED_NATIVE',status='UNVERIFIED_SPAWN_IDENTITY',epoch_manifest=plan['execution_manifest'],source=job['source'],source_asr=None,source_identity=None,profile_sha256=job['profile_sha256'],native_session_complete=False,session_evidence='SUCCESSFUL_POPEN_ONLY_NOT_PROVEN_MODEL_SESSION',error=error or 'Successful Popen; finite creation identity unavailable',receipt_bindings=[pb,sb])
 return row

def invocation_rows(reader,plan,pb):
 jobs={j['job_id']:j for j in plan['jobs']};records=[];owners=[]
 for path in sorted((Path(plan['report_root'])/'invocations').glob('*/LAUNCH.json')):
  launch,lb=reader.read(path);o=v4.owner(launch['owner']);require(launch['status']=='STARTED' and launch['manifest']==pb,'Cross coordinator launch differs')
  owners.append(dict(branch='CROSS_COORDINATOR',pid=o['pid'],creation_time=o['creation_time'],process_state=v3.process_state(o['pid'],o['creation_time']),source=lb));record=dict(launch=lb,status='STARTED',row_reference_counts=None,completed_references=None,closure=None)
  if path.with_name('OUTCOME.json').exists():
   value,vb=reader.read(path.with_name('OUTCOME.json'));v3.same_owner(o,value['owner']);require(value['manifest']==pb and value['requested']==len(jobs) and value['status'] in ('COMPLETE','PARTIAL'),'Cross coordinator outcome differs')
   refs=value['rows'];require(len(refs)==value['completed'] and len({x['job_id'] for x in refs})==len(refs),'Unique outcome cell references required')
   for x in refs:
    require(x['job_id'] in jobs and x['status'] in ('COMPLETE','COMPLETE_REUSED'),'Outcome reference status differs');c,cb=bound(reader,x['completion']);j=jobs[x['job_id']]
    require(c['job_key']==j['job_key'] and c['status']=='COMPLETE' and Path(cb['path'])==Path(j['report_root'])/'COMPLETE.json','Outcome completion binding differs')
   if value['status']=='COMPLETE':require(value['completed']==len(jobs) and value['error'] is None,'Whole plan completion differs')
   record.update(outcome=vb,status=value['status'],completed_references=len(refs),row_reference_counts=dict(Counter(x['status'] for x in refs)))
   remaining=value['remaining_owned'];ids=[]
   for r in remaining:
    require(type(r['pid']) is int and r['pid']>0,'Recorded child PID invalid');ids.append((r['pid'],r['creation_time']))
    if r['creation_time'] is None:state=dict(alive=None,state='UNVERIFIED_PROCESS_IDENTITY')
    else:v4.owner(r);state=v3.process_state(r['pid'],r['creation_time'])
    owners.append(dict(branch='CROSS_RECORDED_CHILD',pid=r['pid'],creation_time=r['creation_time'],process_state=state,source=vb))
   require(len(ids)==len(set(ids)),'Duplicate recorded remaining owner')
   cp=path.with_name('CLOSURE.json')
   if cp.exists():
    c,cb=reader.read(cp);v3.same_owner(o,c['owner']);require(c['manifest']==pb and c['outcome']==vb,'Cross closure source differs');record.update(closure=cb,closure_status=c['status'])
    release=c['lease_release']
    if c['status']=='QUIET_LEASE_RELEASED':
     require(release['status']=='RELEASED' and release['released'] is True and all(r['creation_time'] is not None and r['alive'] is False for r in remaining),'Released lease contradicts owned uncertainty')
     lease,ab=bound(reader,release['archived_binding']);v3.same_owner(o,lease)
     require(lease['kind']==KIND and lease['manifest']==pb and lease['launch']==lb and Path(ab['path']).parent==path.parent,'Released exact cross lease differs');record['archived_lease']=ab
    else:
     require(release['status']!='RELEASED' and release['released'] is not True,'Named retained closure contradicts release')
     owners.append(dict(branch='CROSS_QUIET_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='RELEASE_UNVERIFIED'),source=cb))
  if record.get('outcome') is None or record.get('closure') is None:
   missing='OUTCOME' if record.get('outcome') is None else 'CLOSURE'
   record['closure_missing']=missing;owners.append(dict(branch='CROSS_INVOCATION_CLOSURE_MISSING',pid=None,creation_time=None,process_state=dict(alive=None,state='UNVERIFIED_MISSING_'+missing),source=lb))
  records.append(record)
 return records,owners

def closed_lease(reader,job,plan,pb):
 admission,ab=reader.read(Path(job['report_root'])/'CELL_ADMISSION.json');qb=admission['quiet_lease'];require(Path(qb['path'])==REPORT/'PACED_QUIET_OWNER.json','Cell quiet owner path differs')
 records,owners=invocation_rows(reader,plan,pb);matches=[]
 for r in records:
  archived=r.get('archived_lease')
  if archived and (archived['bytes'],archived['sha256'])==(qb['bytes'],qb['sha256']):matches.append(r)
 require(len(matches)==1,'Completed cell lacks unique bound released coordinator lease')
 return matches[0],owners

def admit_complete_cell(reader,job,plan,pb,spec,state=None):
 if plan['schema']!=CROSS:return v5.admit_complete_cell(reader,job,plan,pb,spec,state)
 value=X.admit_complete_cell(reader,job,plan,pb,spec,state);spawn=spawn_read(reader,job,plan,pb);require(spawn is not None,'Cross completed cell requires pre-identity spawn record')
 s,sb=spawn;spawn_argv(s,job,plan,pb);require(s['pid']==value['cell']['owner']['pid'] and s['argv']==value['cell']['owner']['argv'],'Spawn/native identity differs')
 lease,owners=closed_lease(reader,job,plan,pb);require(all(o['process_state']['alive'] is False for o in owners),'Cross coordinator or retained child current closure unavailable');value.update(spawn_binding=sb,coordinator_lease_chain=lease,coordinator_owner_observations=owners)
 return value

def admit_paced_index(reader,b,plan,pb):return X.admit_paced_index(reader,b,plan,pb) if plan['schema']==CROSS else v5.admit_paced_index(reader,b,plan,pb)

def collect_job(reader,job,plan,pb,spec):
 spawn=spawn_read(reader,job,plan,pb);folder=Path(job['report_root']);lp=folder/'LAUNCH.json'
 if spawn is None:
  if lp.exists():
   launch,lb=reader.read(lp);v4.owner(launch);require(launch['job_key']==job['job_key'],'Unverified launch belongs to another job');row=X.row_base(job,launch,lb,pb,True);row.update(branch='CROSS_ROUTE_SINGLE_SCENE_PACED_NATIVE',status='UNVERIFIED_CELL_LINEAGE',error='Finite LAUNCH exists but mandatory successful Popen record is missing');return row
  return X.collect_job(reader,job,plan,pb,spec)
 value,sb=spawn
 if not lp.exists():
  try:spawn_argv(value,job,plan,pb);error=None
  except (KeyError,ValueError,TypeError) as exc:error=repr(exc)
  extra=[n for n in ('CELL_ADMISSION.json','CELL_RESULT.json','CELL_OUTCOME.json','FAILURE.json','COMPLETE.json') if (folder/n).exists()]
  return unknown_spawn(job,plan,pb,value,sb,error or ('Terminal/worker metadata without finite launch: '+','.join(extra) if extra else None))
 launch,lb=reader.read(lp)
 try:
  spawn_argv(value,job,plan,pb);X.validate_launch(launch,job,plan,pb);v4.owner(launch);require(value['pid']==launch['pid'] and value['argv']==launch['argv'],'Spawn/launch mismatch')
  row=X.collect_job(reader,job,plan,pb,spec)
  if row['status']=='COMPLETE':admit_complete_cell(reader,job,plan,pb,spec)
  row.update(branch='CROSS_ROUTE_SINGLE_SCENE_PACED_NATIVE');row['receipt_bindings'].append(sb);return row
 except (KeyError,ValueError,TypeError,OSError,RuntimeError) as exc:
  # Successful spawn is retained, but a contradictory chain cannot prove model completion.
  try:
   v4.owner(launch);require(launch['pid']==value['pid'],'Different spawned PID');row=X.row_base(job,launch,lb,pb,True);row.update(branch='CROSS_ROUTE_SINGLE_SCENE_PACED_NATIVE',status='UNVERIFIED_CELL_LINEAGE',error=repr(exc));row['receipt_bindings'].append(sb);return row
  except (ValueError,KeyError,TypeError):return unknown_spawn(job,plan,pb,value,sb,repr(exc))

def additive(original,admissions,reader,declared,issues,rows,bysession,discovered):
 cross=[];ordinary=[]
 for b in admissions:
  doc,_=bound(reader,b);(cross if doc['schema']==CROSS else ordinary).append(b)
 result=v5.additive(original,ordinary,reader,declared,issues,rows,bysession,discovered);summaries=[];new=[];before=len(issues)
 found={base.canonical(p) for p in (REPORT/'paced_cross_routes').glob('*/MANIFEST.json')};supplied={base.canonical(b['path']) for b in cross}
 if found-supplied:issues.append(dict(scope='CROSS_MANIFEST_NOT_ADMITTED',paths=sorted(found-supplied)))
 for b in cross:
  try:
   plan,pb,spec=admit_plan(reader,b);counts=Counter()
   try:inv,owners=invocation_rows(reader,plan,pb);result['owner_observations']+=owners
   except (KeyError,ValueError,TypeError,OSError,RuntimeError) as exc:
    inv=[];issues.append(dict(manifest=pb,coordinator_error=repr(exc)));result['owner_observations'].append(dict(branch='CROSS_COORDINATOR_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='UNVERIFIED_COORDINATOR_LINEAGE')))
   for j in plan['jobs']:
    try:row=collect_job(reader,j,plan,pb,spec)
    except (KeyError,ValueError,TypeError,OSError,RuntimeError) as exc:issues.append(dict(manifest=pb,job_id=j['job_id'],error=repr(exc)));counts['UNVERIFIED_METADATA']+=1;continue
    if row is None:counts['NOT_LAUNCHED']+=1;continue
    counts[row['status']]+=1
    if row['status'].startswith('UNVERIFIED'):issues.append(dict(manifest=pb,job_id=j['job_id'],error=row['error']))
    if v4.add_physical(rows,bysession,row):new.append(row)
    result['owner_observations'].append(dict(branch='CROSS_PHYSICAL_OWNER',pid=row['pid'],creation_time=row['creation_time'],process_state=row['process_state'],sources=row['receipt_bindings']))
    for o in row.get('recorded_owned_processes',[]):v4.owner(o);result['owner_observations'].append(dict(branch='CROSS_NATIVE_RECORDED_OWNER',pid=o['pid'],creation_time=o['creation_time'],process_state=v3.process_state(o['pid'],o['creation_time']),sources=row['receipt_bindings']))
    declared.add(row['output_bindings'],row['receipt_bindings'][-1],'CROSS_NATIVE_DECLARED_OUTPUTS')
   index=None;ip=Path(plan['report_root'])/'PACED_INDEX.json'
   if ip.exists():value,ib=reader.read(ip);value,ib=admit_paced_index(reader,ib,plan,pb);index=dict(binding=ib,row_references=len(value['rows']),status_counts=dict(Counter(x['status'] for x in value['rows'])),not_new_inference=True)
   summaries.append(dict(manifest=pb,requested_cells=40,observed_status_counts=dict(counts),invocations=inv,paced_index=index,actual_epoch='epoch4',source_kind='CANONICAL_SINGLE_SCENE_PAIR',physical_attempts=sum(x['receipt_bindings'][0]==pb for x in new)));declared.add(plan,pb,'CROSS_EXPLICIT_ADMISSION')
  except (KeyError,ValueError,TypeError,OSError,RuntimeError) as exc:issues.append(dict(manifest=b,error=repr(exc)))
 if len(issues)>before:result['owner_observations'].append(dict(branch='CROSS_LINEAGE_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='UNVERIFIED_CROSS_LINEAGE')))
 result['cross_paced_v6']=dict(schema=SCHEMA,plans=summaries,physical_attempts=len(new),status_counts=dict(Counter(x['status'] for x in new)),complete_logical_cells=sum(x['status']=='COMPLETE' for x in new),native_sessions_with_complete_receipts=sum(x['native_session_complete'] for x in new),unverified_successful_spawns=sum(x['status']=='UNVERIFIED_SPAWN_IDENTITY' for x in new),source_bindings=source_bindings(),scope='One successful spawn plus its matching launch is one attempt. Spawn-only evidence is not model inference. Reused COMPLETE references do not add physical attempts. Single-scene cross routes are never long compositions.')
 for b in source_bindings():
  raw=Path(b['path']).read_bytes();target=reader.output/'source_snapshots'/Path(b['path']).name
  if target.exists():require(target.read_bytes()==raw,'Source snapshot conflict')
  else:target.write_bytes(raw)
 return result

def collect(args):
 require(args.paced_manifest and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.version or ''),'Explicit manifests/fresh simple version required');admissions=[]
 for p,sha in args.paced_manifest:
  raw=Path(p).read_bytes();b=base.binding(p,raw);require(b['sha256']==sha,'Explicit manifest hash differs');admissions.append(b)
 require(len({base.canonical(b['path']) for b in admissions})==len(admissions),'Duplicate manifest arguments');before=source_bindings()
 with v3.patched_base():
  original=base.collect_auxiliary;base.collect_auxiliary=lambda *a:additive(original,admissions,*a)
  try:result=base.collect(args)
  finally:base.collect_auxiliary=original
 require(source_bindings()==before,'V6 sources changed during metadata collection')
 return base.write_new(Path(result['snapshot']['path']).parent/'INVENTORY_V6_RECEIPT.json',dict(schema=SCHEMA,status='COMPLETE_SCOPED_ADAPTER_COLLECTION',sources=before,admitted_manifests=admissions,inventory=result['snapshot'],result=result,model_calls=0,scope='No whole-study completion claim; all inherited missing/current-owner flags retained.'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['collect']);p.add_argument('--version',required=True);p.add_argument('--paced-manifest',nargs=2,action='append',required=True);print(json.dumps(collect(p.parse_args()),indent=2))
