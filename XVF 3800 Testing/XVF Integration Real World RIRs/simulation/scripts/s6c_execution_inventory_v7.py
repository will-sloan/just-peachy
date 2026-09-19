"""Explicit fast-observer physical accounting; README_S6C_EXECUTION_INVENTORY_V7.md."""
from __future__ import annotations
import argparse,ast,hashlib,importlib,json,math,re,types
from collections import Counter
from copy import deepcopy
from pathlib import Path

HERE=Path(__file__).resolve().parent
PINS={
 's6c_execution_inventory_v6.py':'9109a38c9f62ad6aca11a4e60ef57eb9e8712bb43dde10b08d485d03a068921f',
 's6c_historical_fast_observer_v1.py':'579963cb5e873a0a08504bb4f022ea8a92a158886d36abfd87ee4a0f9cd6d299',
 # The final held wrapper hashes are populated before any admission is enabled.
 's6c_paced_epoch4_fast_v1.py':'c13ed3849fb86aeb50341d823c2969b5084cd6e90aa8fee4c24785405e8d20c4',
 's6c_long_native_epoch4_fast_v1.py':'0160a9a09c54183d2896dc6363e66ed67f1f0e049d7dcdddd4c7d22e6cb6b166',
 's6c_paced_arrival_sentinel_fast_v1.py':'63a26b59729e1ed0bd248f459de057b47bf3384b00b0dc1db5b4812a92838a57',
 's6c_paced_cross_routes_fast_v1.py':'b7552b44a8e24a6387969fb1a08d16bf3e7eded5ddd728e4bdb1181d2274f1ea',
 's6c_paced_controls_fast_v1.py':'49313592295cfd544c8b1c21e029b78a288ea6e2aa05d8419c1581b8c95af32a',
 's6c_paced_b36_fast_v1.py':'a92ec01f3df563274c8a4ce6694844c921fa3c58039cf9e34c270aea57e546fb',
 's6c_long_b36_fast_v1.py':'6e18e18a4d133364c4b2a568339dac0365dd752a4ab090d23713bafd9102694e'}
PINS['README_S6C_PACED_EPOCH4_FAST_V1.md']='20ff05726ee9168726ca0ae997edd3d2e2f93e589cf38b858bf6e700bce6b785'
PINS['README_S6C_LONG_NATIVE_EPOCH4_FAST_V1.md']='8fd1882e7af4adc1be651c15723fd72ff1285edb482156afbaadc7a7430ea927'
PINS['README_S6C_PACED_ARRIVAL_SENTINEL_FAST_V1.md']='8fea9db2866a394c63e0da1456c2631bcd325bb58bdef5dcf305562d5cdb9adb'
PINS['README_S6C_PACED_CROSS_ROUTES_FAST_V1.md']='b8d7f18bf3c8313b3cbf40a3d02ce3d027ec8562c937001cbac61c7c42f00860'
PINS['README_S6C_PACED_CONTROLS_FAST_V1.md']='fea3ab28847732e6a56453f67631f726fadb49ca6fa45283d3471f0175d7bfe1'
PINS['README_S6C_PACED_B36_FAST_V1.md']='3b63c4c116548c3e894359db56329e276afd971b6ad2d9de64a88d5780b08ecf'
PINS['README_S6C_LONG_B36_FAST_V1.md']='19c2ee62a4708333df2d973778e6323db9ed72054334caebcff46037f5721ff9'
PINS['README_S6C_HISTORICAL_FAST_OBSERVER_V1.md']='9bf140e925fec6b7027386aee8eb10ba6ffa255229ec8c2db6471e5d6ad23a97'
for n in ('s6c_execution_inventory_v6.py','s6c_historical_fast_observer_v1.py'):
 if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=PINS[n]:raise ValueError('Held source differs: '+n)
v6=importlib.import_module('s6c_execution_inventory_v6');v5=v6.v5;v4=v6.v4;v3=v6.v3;base=v6.base
F=importlib.import_module('s6c_historical_fast_observer_v1')
REPORT=v6.REPORT;PAYLOAD=v6.PAYLOAD;CANONICAL=v4.CANONICAL;require=v4.require;bound=v4.bound
process_state=v3.process_state
HISTORICAL={**v4.HISTORICAL,'s6c-historical-paced-controls-fast.v1':('B00','B01'),'s6c-historical-paced-b36-fast.v1':('B36',)}
SCHEMA='s6c-execution-inventory-additive.v7'
FAST={
 'canonical':dict(wrapper='s6c_paced_epoch4_fast_v1.py',schema=CANONICAL,family='paced_candidates',cell='s6c-canonical-paced-cell-result.v1',kind='S6C_CANONICAL_PACED_EPOCH4'),
 'sentinel':dict(wrapper='s6c_paced_arrival_sentinel_fast_v1.py',schema=v5.SENTINEL,family='paced_arrival_sentinel',cell='s6c-paced-arrival-sentinel-cell-result.v1',kind='S6C_PACED_ARRIVAL_SENTINEL'),
 'cross':dict(wrapper='s6c_paced_cross_routes_fast_v1.py',schema=v6.CROSS,family='paced_cross_routes',cell='s6c-cross-route-paced-cell-result.v1',kind='S6C_CROSS_ROUTE_PACED_EPOCH4'),
 'controls':dict(wrapper='s6c_paced_controls_fast_v1.py',schema='s6c-historical-paced-controls-fast.v1',family='paced_controls'),
 'b36':dict(wrapper='s6c_paced_b36_fast_v1.py',schema='s6c-historical-paced-b36-fast.v1',family='paced_controls'),
 'long_b36':dict(wrapper='s6c_long_b36_fast_v1.py',schema='s6c-exact-historical-b36-continuous-fast.v1',family='long_b36'),
 'long_c':dict(wrapper='s6c_long_native_epoch4_fast_v1.py',schema='s6c-epoch4-long-native-admission.v1',family='long_native_epoch4')}
NAMES={'admit_plan','expected_worker_argv','validate_launch','native_result_metadata','metadata_chain','admit_complete_cell','admit_paced_index','row_base','collect_job'}
ERRORS=(ValueError,KeyError,TypeError,OSError,RuntimeError)

def verify_sources():
 for n,h in PINS.items():require(re.fullmatch('[a-f0-9]{64}',h) and F.bind(HERE/n)['sha256']==h,'Unheld fast source: '+n)

def source_bindings():
 verify_sources();return [F.bind(p) for p in [Path(__file__),HERE/'README_S6C_EXECUTION_INVENTORY_V7.md',*(HERE/n for n in PINS)]]

def kind_of(plan):
 for k,v in FAST.items():
  if plan['schema']!=v['schema']:continue
  if k in ('controls','b36','long_b36'):return k
  if 'observer_policy' in plan:return k
 return None

def source_policy():
 ns=dict(Path=Path,__file__=str(HERE/FAST['long_c']['wrapper']),bind=F.bind,FAST_SCAN_SHA=PINS['s6c_historical_fast_observer_v1.py'],FAST_SCAN_README_SHA='9bf140e925fec6b7027386aee8eb10ba6ffa255229ec8c2db6471e5d6ad23a97')
 v5.compile_functions(HERE/FAST['long_c']['wrapper'],{'observer_policy'},ns)
 return ns['observer_policy']()

def paced_api(kind):
 v=FAST[kind];guards=v4.GUARDS if kind=='canonical' else v5.S.GUARDS if kind=='sentinel' else v6.X.GUARDS
 replacements={'s6c_paced_epoch4.py':v['wrapper'],'s6c-canonical-paced-cell-result.v1':v['cell'],'paced_candidates':v['family']}
 if kind=='sentinel':replacements['f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da']='13490a4773b5be366b6a7d7e47013f8cd3ab9a8d34a3f9d99f33c539a24f2d4b'
 ns={**vars(v4),'CANONICAL':v['schema'],'GUARDS':guards,'PINS':{**v4.PINS,**PINS}}
 v5.compile_functions(HERE/'s6c_execution_inventory_v4.py',NAMES,ns,replacements)
 # The stronger cross invocation/lease checks work for every paired schema.
 ins={**vars(v6),'KIND':v['kind']}
 v5.compile_functions(HERE/'s6c_execution_inventory_v6.py',{'invocation_rows','closed_lease'},ins)
 ns.update(invocation_rows=ins['invocation_rows'],closed_lease=ins['closed_lease'])
 return types.SimpleNamespace(**{n:ns[n] for n in NAMES|{'invocation_rows','closed_lease'}})

def historical_api():
 ns={**vars(v4),'HISTORICAL':{FAST['controls']['schema']:('B00','B01'),FAST['b36']['schema']:('B36',)},'PINS':{**v4.PINS,**PINS}}
 replacements={'s6c_paced_controls.py':FAST['controls']['wrapper'],'s6c_paced_b36_v1.py':FAST['b36']['wrapper']}
 v5.compile_functions(HERE/'s6c_execution_inventory_v4.py',NAMES|{'invocation_rows'},ns,replacements)
 return types.SimpleNamespace(**{n:ns[n] for n in NAMES|{'invocation_rows'}})

def long_b36_api(reader):
 guards=v5.long_guards(reader);ns={**vars(v5),'LONG':FAST['long_b36']['schema'],'LONG_RESULT':'s6c-exact-historical-b36-continuous-fast-result.v1'}
 names={'long_argv','long_row','admit_long_native','long_invocations','unverified_spawn_row'}
 v5.compile_functions(HERE/'s6c_execution_inventory_v5.py',names,ns,{'s6c_long_b36_v1.py':FAST['long_b36']['wrapper'],'S6C_EXACT_HISTORICAL_B36_CONTINUOUS':'S6C_EXACT_HISTORICAL_B36_CONTINUOUS_FAST'})
 return types.SimpleNamespace(**{n:ns[n] for n in names}),guards

def validate_fast_sources(plan,kind):
 v=FAST[kind];require(Path(plan.get('namespace',Path(plan['output_root']).name) if kind in ('controls','b36') else plan['namespace']).name.endswith('_fast_v1'),'Fresh explicit fast namespace required')
 if kind in ('controls','b36','long_b36'):require(plan['fast_observer']['sources']==F.source_bindings(kind),'Historical exact observer sources differ')
 else:
  require(plan['observer_policy']==source_policy(),'Exact observer policy differs')
  sources=plan['dependencies'] if kind=='long_c' else plan['sources']
  for n in (v['wrapper'],FAST['long_c']['wrapper'],'s6c_historical_fast_observer_v1.py'):
   matches=[b for b in sources if Path(b['path']).name==n];require(len(matches)==1 and matches[0]==F.bind(HERE/n),'Required exact fast dependency differs: '+n)

def admit_plan(reader,b):
 plan,pb=bound(reader,b);kind=kind_of(plan)
 if kind is None:return v6.admit_plan(reader,b)
 verify_sources();validate_fast_sources(plan,kind)
 if kind in ('canonical','sentinel','cross'):
  admitted,pb,spec=paced_api(kind).admit_plan(reader,b)
  if kind=='sentinel':require(plan['candidates']==['C088','C105'] and len(plan['jobs'])==12 and plan['panel_mode']=='arrival_sentinel','Exact12 arrival sentinel')
  if kind=='cross':require(plan['candidates']==['C085','C086'] and len(plan['jobs'])==40 and plan['panel_mode']=='cross16_plus4','Exact40 cross pair')
  require(plan['worker_limit']==plan['inner_threads']==1 and plan['pending_cell_bytes']==512*2**20 and plan['max_run_sec']==28800,'Paired observer limits differ')
  total=0.
  for j in plan['jobs']:
   s,_=bound(reader,j['source']);total+=s['duration_sec'];require(j['timeout_sec']==max(720.,s['duration_sec']*1.75+j['profile_row']['profile']['runtime']['lane_drain_timeout_sec']+120.),'Paired timeout differs')
  require(total==plan['total_source_sec'],'Full paired source denominator differs')
  return admitted,pb,spec
 if kind in ('controls','b36','long_b36'):
  original,ob,*extra=v6.admit_plan(reader,plan['original_prepared_manifest']);name=plan['namespace'] if kind=='long_b36' else Path(plan['output_root']).name
  ns={**vars(F),'long_sources':lambda:original['sources']+F.source_bindings(kind)};v5.compile_functions(HERE/'s6c_historical_fast_observer_v1.py',{'projection'},ns)
  require(plan==ns['projection'](kind,original,ob,name,plan['created_utc']),'Exact original jobs and observer-only projection differ')
  root=Path(plan['report_root'] if kind=='long_b36' else plan['output_root']);require(Path(pb['path'])==root/'MANIFEST.json','Historical fast manifest location differs')
  if kind=='long_b36':return plan,pb,extra[0]
  return historical_api().admit_plan(reader,pb)
 return admit_long_plan(reader,pb)

def admit_long_plan(reader,b):
 plan,pb=bound(reader,b);v4.digest_guard(plan,'plan_key');validate_fast_sources(plan,'long_c')
 namespace=plan['namespace'];require(re.fullmatch(r'epoch4_[A-Za-z0-9_-]{1,64}',namespace) and namespace.endswith('_fast_v1'),'Exact continuous namespace')
 require(Path(pb['path'])==REPORT/'long_native_epoch4'/namespace/'MANIFEST.json','Continuous admission location')
 v3.expected_binding(plan['composition'],v3.EXPECTED_COMPOSITION,v3.COMPOSITION_SHA);v3.expected_binding(plan['execution_manifest'],v3.EXPECTED_EPOCH,v3.EPOCH4_SHA)
 spec,eb=bound(reader,plan['execution_manifest']);composition,cb=bound(reader,plan['composition']);row=plan['profile_row']
 require(plan['actual_execution_epoch']=='epoch4' and plan['source_composition_epoch']=='epoch2' and spec['epoch']=='epoch4','Separate source/native epoch')
 require(spec['execution_digest']==base.digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')}),'Native execution digest')
 require(sum(r==row for r in spec['profiles'])==1 and base.digest(row)==plan['profile_sha256'],'Exact registered continuous row')
 require(plan['report_root']==str(REPORT/'long_session'/namespace) and plan['payload_root']==str(PAYLOAD/'long_session'/namespace),'Continuous native output roots')
 for k in ('audio','pcm_sha256','telemetry','duration_sec','duration_samples'):require(plan[k]==composition[k],'Exact continuous source '+k)
 require(plan['duration_sec']==1827.426625 and plan['duration_samples']==29238826 and plan['worker_limit']==1 and plan['pending_output_reserve_bytes']==4*2**30 and plan['max_wall_sec']==7200,'Continuous exact limits')
 from datetime import datetime,timezone
 require(datetime.fromisoformat(plan['deadline_utc'].replace('Z','+00:00'))<=datetime(2026,9,13,11,35,40,tzinfo=timezone.utc),'Continuous deadline reserve differs')
 require(plan['allowed_overrides']==['load_composition','admit_work','process_sample'],'Continuous native override boundary differs')
 require(row['cue_condition'] in ('CUES_OFF','REAL_ALIGNED_CUES') and row['gallery_condition'] in ('NONE','FIXED_ROTATION_A','FIXED_ROTATION_B'),'Continuous fixed roster/cues')
 if plan['gallery'] is None:require(row['gallery_condition']=='NONE' and row['profile']['identity']['mode']=='none','Explicit no-gallery route')
 else:
  require(plan['gallery_index']==spec['gallery_index'],'Exact continuous gallery index');index,_=bound(reader,plan['gallery_index']);matches=[r for r in index['rows'] if r['case_id'] is None and r['gallery_condition']==row['gallery_condition'] and r['enrollment_tier']==row['enrollment_tier']]
  require(matches==[plan['gallery_row']] and matches[0]['manifest']==plan['gallery'],'Exact continuous fixed gallery')
 return plan,pb,spec

def admit_long(reader,b):
 plan,_=bound(reader,b)
 if kind_of(plan)!='long_b36':return v5.admit_long(reader,b)
 plan,pb,a=admit_plan(reader,b);_,g=long_b36_api(reader)
 return plan,pb,a,g

def long_invocations(reader,plan,pb,*,observer_receipts=None):
 if kind_of(plan)!='long_b36':return v5.long_invocations(reader,plan,pb)
 api,_=long_b36_api(reader);_,_,spawns=api.long_invocations(reader,plan,pb)
 records,owners=invocation_rows(reader,plan,pb,observer_receipts=observer_receipts)
 return records,owners,spawns

def admit_long_native(reader,plan,pb,a,g,*,observer_receipts=None):
 if kind_of(plan)!='long_b36':return v5.admit_long_native(reader,plan,pb,a,g)
 api,_=long_b36_api(reader);row=api.admit_long_native(reader,plan,pb,a,g)
 if row['status']=='COMPLETE':
  records,owners,_=long_invocations(reader,plan,pb,observer_receipts=observer_receipts);ensure_invocations_closed(records,owners)
  require(all(process_state(o['pid'],o['creation_time'])['alive'] is False for o in row['recorded_owned_processes']),'Native B36 owned closure unavailable')
  row['observer_admission']=dict(invocations=records)
 return row

def collect_job(reader,job,plan,pb,spec,*,observer_receipts=None):
 if kind_of(plan) is None:
  return (v6.collect_job if plan['schema']==v6.CROSS else v5.S.collect_job if plan['schema']==v5.SENTINEL else v4.collect_job)(reader,job,plan,pb,spec)
 if observer_receipts is not None:attach_observer_receipts(reader,observer_receipts)
 return collect_paced_job(reader,job,plan,pb,spec)

def attach_observer_receipts(reader,bindings):
 require(bindings is not None,'Explicit bound observer receipts/index required')
 records=[];seen=set()
 for b in bindings:
  d,db=bound(reader,b);key=(base.canonical(db['path']),db['sha256']);require(key not in seen,'Duplicate observer receipt');seen.add(key)
  require(d['schema'] in ('s6c.fast_resource_observer_exit.v1','s6c-historical-fast-observer-outcome.v1'),'Actual observer exit schema required');v4.owner(d['owner']);records.append((d,db))
 reader.fast_observer_receipts=records;return records

def admit_observer_index(reader,b):
 d,db=bound(reader,b);require(d['schema']=='s6c-fast-observer-index.v1' and d['status']=='COMPLETE_METADATA_ENUMERATION','Explicit observer index schema/status')
 attach_observer_receipts(reader,d['receipts']);reader.fast_observer_index=db;return d,db

def receipts_context(reader,bindings=None):
 if bindings is not None:return attach_observer_receipts(reader,bindings)
 require(hasattr(reader,'fast_observer_receipts'),'Fast closed admission requires explicit observer receipt context')
 return reader.fast_observer_receipts

def command_fields(argv,wrapper):
 require(isinstance(argv,list) and argv,'Explicit owner argv required');where=[i for i,x in enumerate(argv) if base.canonical(x)==base.canonical(HERE/wrapper)]
 require(len(where)==1 and where[0] in (0,1,2),'Exact observer wrapper argv required');i=where[0]
 if i:require(base.canonical(argv[0])==base.canonical(F.EDGE) and (i==1 or argv[1]=='-B'),'Exact EDGE command prefix')
 tail=argv[i+1:];require(tail and tail[0] in ('run','worker','prepare','source_checks'),'Known entry action');entry=tail[0];tail=tail[1:]
 require(len(tail)%2==0,'Exact explicit option/value command')
 fields={}
 for k,v in zip(tail[::2],tail[1::2]):require(k.startswith('--') and k not in fields,'Duplicate/positional command option');fields[k]=v
 return entry,fields

def observer_exit(reader,plan,pb,owner,entry,job_id=None,bindings=None):
 kind=kind_of(plan);wrapper=FAST[kind]['wrapper'];matches=[]
 for d,b in receipts_context(reader,bindings):
  if d.get('manifest')==pb and d.get('entry')==entry and d.get('job_id')==job_id and (d['owner']['pid'],d['owner']['creation_time'])==(owner['pid'],owner['creation_time']):matches.append((d,b))
 require(len(matches)==1,'One exact post-entry observer receipt required');d,b=matches[0];v3.same_owner(owner,d['owner'])
 require(d['wrapper']==F.bind(HERE/wrapper),'Actual observer wrapper binding');action,args=command_fields(d['owner']['argv'],wrapper)
 require(action==entry and base.canonical(args['--manifest'])==base.canonical(pb['path']),'Observer action/manifest argv')
 if entry=='worker':require(args.get('--job-id')==job_id and base.canonical(args['--owner-lease'])==base.canonical(REPORT/'PACED_QUIET_OWNER.json') and set(args)=={'--manifest','--job-id','--owner-lease'},'Exact worker observer argv')
 else:require(set(args)=={'--manifest','--quiet-admission'},'Exact run observer argv')
 if kind in ('controls','b36','long_b36'):
  require(d['schema']=='s6c-historical-fast-observer-outcome.v1' and d['sources_before']==d['sources_after']==F.source_bindings(kind) and d['sources_unchanged'] is True and d['coordinator_pid']==owner['pid'],'Historical isolated observer source/owner proof')
  expected_root=REPORT/FAST[kind]['family']/Path(plan['report_root'] if 'report_root' in plan else plan['output_root']).name/'observer_invocations'
  require(expected_root in Path(b['path']).parents and Path(b['path']).name=='SCANNER_OUTCOME.json','Historical observer receipt namespace')
  scan_counters(d['storage_scans'])
 else:
  require(d['schema']=='s6c.fast_resource_observer_exit.v1' and d['status']=='RESTORED' and d['error'] is None and d['policy']==plan['observer_policy'],'Required exact restored observer policy')
  require(Path(b['path']).parent==REPORT/'observer_fast_v1/attempts','Exact observer exit namespace')
  require(d['installations'],'Actual scanner installation required')
  spec,_=bound(reader,plan['execution_manifest']);common=[x for x in spec['execution_files'] if Path(x['path']).name=='s6c_common.py'];require(len(common)==1,'One actual frozen common')
  for r in d['installations']:
   require(r['common']==common[0] and r['restored'] is True and r['protected_admission_unchanged'] is True and r['original_callable']=='tree_bytes' and r['scanner_callable']=='ScanMeter(tree_bytes)','Exact common installation/restoration')
   scan_counters(r['scan_observations'])
 return d,b

def scan_counters(rows):
 require(isinstance(rows,dict) and rows,'Actual observer scan counters required')
 allowed={base.canonical(p) for p in (REPORT,base.STAGING,PAYLOAD)}
 require({base.canonical(p) for p in rows}==allowed,'Exact three resource roots required')
 for r in rows.values():
  for k in ('calls','successful','failed'):require(type(r[k]) is int and r[k]>=0,'Integer scan counter required')
  require(r['calls']==r['successful']+r['failed'] and r['successful']>0 and type(r['last_bytes']) is int and r['last_bytes']>=0,'Actual admitted scan counter relationship')
  for k in ('total_wall_sec','total_cpu_sec','max_wall_sec'):require(type(r[k]) in (float,int) and math.isfinite(r[k]) and r[k]>=0,'Finite measured scan clock required')

def ensure_invocations_closed(records,owners):
 require(records,'Actual coordinator invocation required')
 require(all(r.get('outcome') is not None and r.get('closure') is not None for r in records),'Every observed invocation requires final outcome/closure')
 require(all(o['process_state']['alive'] is False for o in owners),'Current recorded owner/lease closure unavailable')

def invocation_rows(reader,plan,pb,*,observer_receipts=None):
 kind=kind_of(plan)
 if kind is None:return (v6.invocation_rows if plan['schema']==v6.CROSS else v5.S.invocation_rows if plan['schema']==v5.SENTINEL else v4.invocation_rows)(reader,plan,pb)
 if kind in ('canonical','sentinel','cross'):records,owners=paced_api(kind).invocation_rows(reader,plan,pb)
 elif kind in ('controls','b36'):records,owners=historical_api().invocation_rows(reader,plan,pb)
 elif kind=='long_b36':records,owners,_=long_b36_api(reader)[0].long_invocations(reader,plan,pb)
 else:return long_c_invocations(reader,plan,pb,observer_receipts=observer_receipts)
 for r in records:
  first=r.get('launch',r.get('admission'));d,_=bound(reader,first);owner=d.get('owner',d)
  if r.get('outcome') is None or r.get('closure') is None:owners.append(dict(branch='FAST_INVOCATION_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='MISSING_OUTCOME_OR_CLOSURE'),source=first));continue
  try:
   obs,ob=observer_exit(reader,plan,pb,owner,'run',bindings=observer_receipts);r['observer_exit']=ob
   _,args=command_fields(obs['owner']['argv'],FAST[kind]['wrapper']);require(base.canonical(args['--quiet-admission'])==base.canonical(d['quiet_admission']['path']),'Observer and coordinator quiet-admission argv differ')
   if kind in ('controls','b36','long_b36'):require(obs['error'] is None and obs['status'] not in ('FAILED','RUNNING'),'Failed historical observer remains unverified')
  except ERRORS as exc:r['observer_error']=repr(exc);owners.append(dict(branch='FAST_OBSERVER_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='OBSERVER_EXIT_UNVERIFIED'),source=first))
 return records,owners

def admit_complete_cell(reader,job,plan,pb,spec,state=None,*,observer_receipts=None):
 kind=kind_of(plan)
 if kind is None:return v6.admit_complete_cell(reader,job,plan,pb,spec,state)
 require(kind in ('canonical','sentinel','cross'),'Closed canonical cell API never coerces historical/continuous schema')
 api=paced_api(kind);value=api.admit_complete_cell(reader,job,plan,pb,spec,state)
 _,ob=observer_exit(reader,plan,pb,value['cell']['owner'],'worker',job['job_id'],observer_receipts)
 records,owners=invocation_rows(reader,plan,pb,observer_receipts=observer_receipts);ensure_invocations_closed(records,owners)
 lease,_=api.closed_lease(reader,job,plan,pb)
 if kind=='cross':
  path=Path(job['report_root'])/'SPAWNED_PROCESS.json';spawn,sb=reader.read(path);require(spawn['status']=='SPAWNED_CREATION_UNVERIFIED' and spawn['creation_time'] is None and spawn['manifest']==pb and spawn['job_key']==job['job_key'] and spawn['pid']==value['cell']['owner']['pid'],'Exact pre-identity cross spawn');api.validate_launch(spawn,job,plan,pb);require(spawn['argv']==value['cell']['owner']['argv'],'Exact cross spawned command');value['spawn_binding']=sb
 value.update(observer_exit=ob,observer_policy=plan['observer_policy'],coordinator_invocations=records,coordinator_owner_observations=owners,coordinator_lease_chain=lease)
 return value

def admit_paced_index(reader,b,plan,pb):
 kind=kind_of(plan)
 return paced_api(kind).admit_paced_index(reader,b,plan,pb) if kind in ('canonical','sentinel','cross') else v6.admit_paced_index(reader,b,plan,pb)

def long_c_invocations(reader,plan,pb,*,observer_receipts=None):
 ns={**vars(v3),'LONG_SHA':PINS[FAST['long_c']['wrapper']],'LONG_README_SHA':F.bind(HERE/'README_S6C_LONG_NATIVE_EPOCH4_FAST_V1.md')['sha256']}
 v5.compile_functions(HERE/'s6c_execution_inventory_v3.py',{'validate_outer'},ns,{'s6c_long_native_epoch4.py':FAST['long_c']['wrapper'],'README_S6C_LONG_NATIVE_EPOCH4.md':'README_S6C_LONG_NATIVE_EPOCH4_FAST_V1.md'})
 records=[];owners=[]
 for p in sorted(Path(pb['path']).parent.glob('invocations/*/ADMISSION.json')):
  value=ns['validate_outer'](reader,p);require(value['manifest']==pb,'Exact long manifest');o=value['owner'];record=dict(value);record['outcome']=value['native_outcome'];records.append(record)
  owners.append(dict(branch='FAST_CONTINUOUS_OWNER',pid=o['pid'],creation_time=o['creation_time'],process_state=v3.process_state(o['pid'],o['creation_time']),source=value['admission']))
  if value['closure'] is None or value['wrapper_status']!='NATIVE_COMPLETE_QUIET_LEASE_RELEASED':owners.append(dict(branch='FAST_CONTINUOUS_CLOSURE_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='NATIVE_OR_LEASE_INCOMPLETE')));continue
  try:
   obs,ob=observer_exit(reader,plan,pb,o,'run',bindings=observer_receipts);record['observer_exit']=ob
   a,_=bound(reader,value['admission']);_,args=command_fields(obs['owner']['argv'],FAST['long_c']['wrapper']);require(base.canonical(args['--quiet-admission'])==base.canonical(a['quiet_admission']['path']),'Long observer quiet admission differs')
   native,_=bound(reader,value['original_native_result']);long_native_identity(reader,native,plan,value['owner'])
  except ERRORS as exc:record['observer_error']=repr(exc);owners.append(dict(branch='FAST_CONTINUOUS_OBSERVER_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='OBSERVER_EXIT_UNVERIFIED')))
 return records,owners

def long_native_identity(reader,native,plan,owner):
 v3.same_owner(owner,native['owner'])
 require(native['resident_bundle_loads']==native['resident_sessions_created']==1 and not native['live_owned_lanes'] and native['hardware_invocations']==0 and native['final_telemetry']['asr_cursor_sec']==plan['duration_sec'],'Complete one-session continuous native scope')
 required={'audio_spool.pcm16':plan['profile_row']['asr_tap'],'identity_audio_spool.pcm16':plan['profile_row']['identity_tap']}
 require(set(native['native_journals'])==set(required),'Actual paired long journals')
 for name,tap in required.items():
  b=native['native_journals'][name];require(b['bytes']==plan['duration_samples']*2 and b['sha256']==plan['pcm_sha256'][tap] and Path(b['path']).name==name and b in native['native_artifacts'],'Long declared whole-source journal differs')
 finals=[b for b in native['native_artifacts'] if Path(b['path']).name=='session_finalization_v3.json'];require(len(finals)==1,'One exact long finalization')
 f,_=bound(reader,finals[0]);require(f['state']=='COMPLETED' and f['finalization_error'] is None and not f['live_lanes_at_finalization'] and not f['resident_bundle_lease_retained'] and f['event_and_transcript_handles_closed'] is True,'Actual long finalization differs')

def validate_outer(reader,path,*,observer_receipts=None):
 admission,_=reader.read(Path(path));plan,pb=bound(reader,admission['manifest'])
 if kind_of(plan)!='long_c':return v3.validate_outer(reader,Path(path))
 admit_long_plan(reader,pb)
 records,owners=long_c_invocations(reader,plan,pb,observer_receipts=observer_receipts)
 ensure_invocations_closed(records,owners)
 matches=[r for r in records if base.canonical(r['admission']['path'])==base.canonical(path)]
 require(len(matches)==1,'One exact continuous outer admission')
 return matches[0]

def collect_long_c(reader,plan,pb,records):
 """Only actual STARTED receipts create physical rows; outer admission never does."""
 rows=[]
 for path in sorted(Path(plan['report_root']).glob('native/*/*/*/STARTED.json')):
  start,sb=reader.read(path);o=v4.owner(start['owner']);profile=start['profile']
  require(profile==plan['profile_row'] and start['composition']==plan['composition'],'Actual continuous start source/profile')
  action,fields=command_fields(o['argv'],FAST['long_c']['wrapper'])
  require(action=='run' and set(fields)=={'--manifest','--quiet-admission'} and base.canonical(fields['--manifest'])==base.canonical(pb['path']),'Actual continuous start command')
  matches=[r for r in records if (r['owner']['pid'],r['owner']['creation_time'])==(o['pid'],o['creation_time'])]
  require(len(matches)==1,'Actual start has no unique outer native owner');outer=matches[0]
  n=None;nb=None;status='STARTED';outputs={};session=None;native_complete=False
  if path.with_name('RESULT.json').exists():
   n,nb=reader.read(path.with_name('RESULT.json'));v3.same_owner(o,n['owner'])
   require(n['schema']=='s6c_continuous_paced_native.v1' and n['status']=='COMPLETE' and n['profile']==profile and n['composition']==plan['composition'],'Actual native continuous result')
   require(n['source_duration_sec']==plan['duration_sec'] and not n['live_owned_lanes'] and n['resident_sessions_created']==1,'Actual complete continuous scope')
   require(nb==outer['original_native_result'],'Native/outer result binding')
   sessions={base.canonical(Path(b['path']).parent) for b in n['native_journals'].values()};require(len(sessions)==1,'One continuous native session')
   session=sessions.pop();native_complete=True;status='COMPLETE' if outer.get('observer_exit') and outer['wrapper_status']=='NATIVE_COMPLETE_QUIET_LEASE_RELEASED' else 'NATIVE_COMPLETE_OBSERVER_UNVERIFIED'
   outputs=dict(native_artifacts=n['native_artifacts'],journals=n['native_journals'],process_samples=n['process_samples'])
  elif path.with_name('FAILURE.json').exists():
   n,nb=reader.read(path.with_name('FAILURE.json'));v3.same_owner(o,n['owner']);require(n['status']=='FAILED','Explicit continuous failure');status='FAILED'
  if status=='STARTED' and process_state(o['pid'],o['creation_time'])['alive'] is False:status='PARTIAL_CLOSED_WITHOUT_FINAL_RESULT'
  size,missing=base.count_bytes(outputs)
  rows.append(dict(physical_id=base.digest(['long_native',str(path.parent),o['pid'],o['creation_time'],start['utc']]),branch='CONTINUOUS_HOST_PACED_NATIVE',status=status,epoch='epoch4',source_composition_epoch='epoch2',epoch_manifest=plan['execution_manifest'],source_composition=plan['composition'],candidate_id=profile['candidate_id'],profile_id=profile['profile']['profile_id'],recipe_id=profile['recipe_id'],case_id=None,asr_tap=profile['asr_tap'],identity_tap=profile['identity_tap'],execution_mode='CONTINUOUS_NATIVE_SYNTHETIC_CONCATENATION',job_key=None,inference_dependency_key=None,pid=o['pid'],creation_time=o['creation_time'],process_state=process_state(o['pid'],o['creation_time']),session_dir=session,native_session_complete=native_complete,session_evidence='BOUND_ACTUAL_LONG_NATIVE_RESULT' if native_complete else 'ACTUAL_NATIVE_START_ONLY',started_utc=start['utc'],finished_utc=(n or {}).get('created_utc',(n or {}).get('utc')),elapsed_sec=(n or {}).get('total_observed_worker_sec',(n or {}).get('elapsed_sec')),native_elapsed_sec=(n or {}).get('native_elapsed_sec'),process_cpu_sec=None,audio_duration_sec=(n or {}).get('source_duration_sec'),worker_model_bundle_loads=(n or {}).get('resident_bundle_loads'),bundle_admission_sec=(n or {}).get('model_load_sec'),gallery_manifest=start.get('gallery'),gallery_cache_hit=False if start.get('gallery') and native_complete else None,gallery_admission_sec=None,real_gallery_load_observed=bool(start.get('gallery')) and bool((n or {}).get('gallery_load_receipt')),actual_counts=(n or {}).get('event_counts'),output_bindings=outputs,declared_output_bytes=size if outputs else None,bindings_missing_byte_counts=missing,receipt_bindings=[pb,sb]+[b for b in (nb,outer['admission'],outer['closure'],outer.get('observer_exit')) if b],error=(n or {}).get('error')))
 return rows

def missing_fast_manifests(admitted):
 supplied={base.canonical(b['path']) for b in admitted};found=set()
 for root in (REPORT/'paced_candidates',REPORT/'paced_arrival_sentinel',REPORT/'paced_cross_routes',PAYLOAD/'paced_controls',REPORT/'long_b36',REPORT/'long_native_epoch4'):
  for version in ('v1','v2'):found.update(base.canonical(p) for p in root.glob('*_fast_'+version+'/MANIFEST.json'))
 return [dict(scope='FAST_PREPARED_MANIFEST_NOT_ADMITTED',paths=sorted(found-supplied),meaning='Not inferred executed or failed; explicit current coverage gap')] if found-supplied else []

def unverified_long_starts(reader,plan,pb,error):
 rows=[]
 for path in sorted(Path(plan['report_root']).glob('native/*/*/*/STARTED.json')):
  start,sb=reader.read(path);o=start.get('owner',{});pid=o.get('pid');created=o.get('creation_time');valid=v3.finite_owner(pid,created)
  rows.append(dict(physical_id=base.digest(['long_native',str(path.parent),pid,created,start.get('utc')]),branch='CONTINUOUS_HOST_PACED_NATIVE',status='UNVERIFIED_NATIVE_START_LINEAGE',epoch='epoch4',source_composition_epoch='epoch2',candidate_id=plan['profile_row']['candidate_id'],profile_id=plan['profile_row']['profile']['profile_id'],recipe_id=plan['profile_row']['recipe_id'],case_id=None,asr_tap=plan['profile_row']['asr_tap'],identity_tap=plan['profile_row']['identity_tap'],job_key=None,inference_dependency_key=None,pid=pid,creation_time=created if valid else None,reported_owner=o,process_state=process_state(pid,created) if valid else dict(alive=None,state='UNVERIFIED_REPORTED_NATIVE_OWNER'),session_dir=None,native_session_complete=False,session_evidence='ACTUAL_STARTED_METADATA_ONLY_NOT_VALIDATED_MODEL_COMPLETION',receipt_bindings=[pb,sb],error=error))
 return rows

def fallback_spawn(reader,job,plan,pb,kind,error):
 folder=Path(job['report_root']) if kind in ('canonical','sentinel','cross') else Path(plan['output_root'])/'jobs'/job['job_id']
 if (folder/'LAUNCH.json').exists():
  d,b=reader.read(folder/'LAUNCH.json');v4.owner(d);row=v4.row_base(job,d,b,pb,kind in ('canonical','sentinel','cross'));row.update(status='UNVERIFIED_CELL_LINEAGE',error=error);return row
 if kind=='cross' and (folder/'SPAWNED_PROCESS.json').exists():
  d,b=reader.read(folder/'SPAWNED_PROCESS.json');require(type(d['pid']) is int and d['pid']>0 and d['creation_time'] is None and d['manifest']==pb and d['job_key']==job['job_key'],'Exact unverified spawn');row=v6.unknown_spawn(job,plan,pb,d,b,error);return row
 return None

def failed_native_after_protection(reader,job,plan,pb,spec,api):
 """Accounting only: a failed outer guard cannot erase a bound native result."""
 folder=Path(job['report_root']);failure=folder/'CELL_OUTCOME.json'
 if not failure.exists():return None
 f,fb=reader.read(failure)
 if f.get('status')!='FAILED' or not f.get('native_result'):return None
 launch,lb=reader.read(folder/'LAUNCH.json');api.validate_launch(launch,job,plan,pb);v4.owner(launch);v3.same_owner(launch,f['owner'])
 require(f['manifest']==pb and f['job_key']==job['job_key'] and f['owner']['argv']==launch['argv'] and isinstance(f['error'],str) and f['error'] and type(f['protected_functions_restored']) is bool,'Failed actual native outcome source/owner/error differs')
 source,_=bound(reader,job['source']);native,nb,kb=api.native_result_metadata(reader,f['native_result'],job,source,spec,f['owner'])
 row=api.row_base(job,launch,lb,pb,True)
 row.update(status='FAILED_OUTER_NATIVE_COMPLETE' if f['protected_functions_restored'] else 'FAILED_OUTER_NATIVE_COMPLETE_PROTECTION_UNVERIFIED',native_session_complete=True,protected_functions_restored=f['protected_functions_restored'],closed_cell_analysis_eligible=False,error=f['error'],epoch_manifest=plan['execution_manifest'],session_dir=base.canonical(Path(next(iter(native['native_journals'].values()))['path']).parent),session_evidence='BOUND_NATIVE_COMPLETE_UNDER_FAILED_OUTER_NO_PROTECTION_PARITY_CLAIM',audio_duration_sec=native['source_duration_sec'],worker_model_bundle_loads=native['resident_bundle_loads'],bundle_admission_sec=native['model_load_sec'],native_elapsed_sec=native['native_elapsed_sec'],elapsed_sec=native['total_observed_worker_sec'],actual_counts=native.get('event_counts'),output_bindings=dict(native_artifacts=native['native_artifacts'],process_samples=native['process_samples']),recorded_owned_processes=[f['owner']],receipt_bindings=[pb,lb,fb,nb,kb])
 row['declared_output_bytes'],row['bindings_missing_byte_counts']=base.count_bytes(row['output_bindings'])
 return row

def collect_paced_job(reader,job,plan,pb,spec):
 kind=kind_of(plan);api=paced_api(kind) if kind in ('canonical','sentinel','cross') else historical_api();row=None
 try:
  row=api.collect_job(reader,job,plan,pb,spec)
  if row is None:return fallback_spawn(reader,job,plan,pb,kind,'Spawn-only evidence; no finite launch')
  if row['status']=='COMPLETE':
   if kind in ('canonical','sentinel','cross'):proof=admit_complete_cell(reader,job,plan,pb,spec);row['observer_admission']=dict(worker=proof['observer_exit'],invocations=proof['coordinator_invocations'])
   else:
    records,owners=invocation_rows(reader,plan,pb);ensure_invocations_closed(records,owners)
    require(all(v3.process_state(x['pid'],x['creation_time'])['alive'] is False for x in row['recorded_owned_processes']),'Historical native owner closure');row['observer_admission']=dict(invocations=records)
  return row
 except ERRORS as exc:
  if row is not None and row.get('native_session_complete'):
   row.update(status='NATIVE_COMPLETE_OBSERVER_UNVERIFIED',error=repr(exc));return row
  if kind in ('canonical','sentinel','cross'):
   try:
    failed=failed_native_after_protection(reader,job,plan,pb,spec,api)
    if failed is not None:return failed
   except ERRORS:pass
  row=fallback_spawn(reader,job,plan,pb,kind,repr(exc))
  if row is not None:return row
  raise

def merge_physical(prior,added):
 rows=list(prior);byid={r['physical_id']:r for r in rows};require(len(byid)==len(rows),'Prior duplicate physical IDs');sessions={base.canonical(r['session_dir']):r['physical_id'] for r in rows if r.get('session_dir')}
 require(len(sessions)==sum(bool(r.get('session_dir')) for r in rows),'Prior duplicate native session paths');duplicates=[]
 for row in added:
  key=row['physical_id']
  if key in byid:require(byid[key]==row,'Conflicting prior/new physical attempt; explicit corrected prior required');duplicates.append(key);continue
  if row.get('session_dir'):s=base.canonical(row['session_dir']);require(s not in sessions,'Native session double-counted across attempts');sessions[s]=key
  byid[key]=row;rows.append(row)
 return rows,duplicates

def refreshed_prior_owners(prior,inspect=None):
 inspect=inspect or process_state
 # Earlier live/inspection observations remain in the bound prior summary;
 # they are not mislabeled as current. Missing lineage identities stay unknown.
 return [dict(pid=o['pid'],creation_time=o['creation_time'],branch='PRIOR_IDENTITY_CURRENT_CHECK',process_state=inspect(o['pid'],o['creation_time']) if v3.finite_owner(o['pid'],o['creation_time']) else dict(alive=None,state='PRIOR_UNVERIFIED_IDENTITY_OR_LINEAGE')) for o in prior]

def collect(args):
 require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Active/preserved quiet lease blocks post-closure inventory')
 verify_sources();require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.version or ''),'Fresh inventory namespace')
 out=REPORT/'execution_inventory'/args.version;require(not out.exists(),'Preserve existing inventory');out.mkdir(parents=True);reader=base.MetadataReader(out)
 def explicit(pair):
  d,b=reader.read(pair[0]);require(b['sha256']==pair[1],'Explicit input SHA differs');return d,b
 prior,pb=explicit(args.prior_inventory);require(prior['schema']=='s6c-execution-inventory.v1','Exact prior whole-study inventory schema');prior_rows,prb=bound(reader,prior['outputs']['physical_json']);require(len(prior_rows)==prior['unique_physical_attempts_observed'],'Prior physical count differs')
 _,ib=explicit(args.observer_index);admit_observer_index(reader,ib)
 require(len({base.canonical(x[0]) for x in args.manifest})==len(args.manifest),'Duplicate explicit manifest arguments')
 new=[];summaries=[];issues=[];owners=[];admitted=[]
 for pair in args.manifest:
  require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'New quiet lease blocks further inventory admission')
  _,mb=explicit(pair);plan,mb,spec=admit_plan(reader,mb);kind=kind_of(plan);require(kind is not None,'Append only explicit fast manifests; old executions reside in prior inventory');admitted.append(mb)
  counts=Counter();records=[];observed=[]
  try:records,observed=invocation_rows(reader,plan,mb);owners+=observed
  except ERRORS as exc:issues.append(dict(manifest=mb,error=repr(exc)));owners.append(dict(pid=None,creation_time=None,process_state=dict(alive=None,state='INVOCATION_UNVERIFIED')))
  if kind in ('canonical','sentinel','cross','controls','b36'):
   for job in plan['jobs']:
    try:row=collect_paced_job(reader,job,plan,mb,spec)
    except ERRORS as exc:issues.append(dict(manifest=mb,job_id=job['job_id'],error=repr(exc)));counts['UNVERIFIED_METADATA']+=1;continue
    if row is None:counts['NOT_LAUNCHED']+=1;continue
    new.append(row);counts[row['status']]+=1
  elif kind=='long_b36':
   api,g=long_b36_api(reader);a=g['authorities']();path=Path(plan['output_root'])/'jobs'/plan['jobs'][0]['job_id']/'LAUNCH.json'
   if path.exists():
    try:
     row=api.admit_long_native(reader,plan,mb,a,g)
     try:ensure_invocations_closed(records,observed)
     except ERRORS as exc:
      if row.get('native_session_complete'):row.update(status='NATIVE_COMPLETE_OBSERVER_UNVERIFIED',error=repr(exc))
      else:raise
     new.append(row);counts[row['status']]+=1
    except ERRORS as exc:row=fallback_spawn(reader,plan['jobs'][0],plan,mb,kind,repr(exc));new.append(row);counts[row['status']]+=1
   else:
    _,_,spawns=api.long_invocations(reader,plan,mb)
    for value,sb in spawns:row=api.unverified_spawn_row(plan,mb,value,sb);new.append(row);counts[row['status']]+=1
    if not spawns:
     folder=path.parent;require(not any((folder/n).exists() for n in ('WORKER_RESULT.json','CONTINUOUS_ADMISSION.json','CONTINUOUS_OUTCOME.json','WORKER_FAILURE.json')),'Native terminal metadata without owned launch/spawn')
     counts['NOT_LAUNCHED']+=1
  else:
   try:current=collect_long_c(reader,plan,mb,records)
   except ERRORS as exc:
    issues.append(dict(manifest=mb,error=repr(exc)));current=unverified_long_starts(reader,plan,mb,repr(exc))
   new+=current;counts.update(r['status'] for r in current)
   if not current:counts['NO_ACTUAL_NATIVE_START_OBSERVED']+=1
  index=None;ip=Path(plan.get('report_root',plan.get('output_root')))/'PACED_INDEX.json'
  if ip.exists() and kind in ('canonical','sentinel','cross'):
   _,b=reader.read(ip);d,b=admit_paced_index(reader,b,plan,mb);index=dict(binding=b,row_references=len(d['rows']),status_counts=dict(Counter(r['status'] for r in d['rows'])),new_physical_attempts=0)
  summaries.append(dict(manifest=mb,kind=kind,status_counts=dict(counts),invocations=records,paced_index=index))
 rows,duplicates=merge_physical(prior_rows,new)
 issues+=missing_fast_manifests(admitted)
 for r in rows:
  owners.append(dict(pid=r['pid'],creation_time=r['creation_time'],branch='PHYSICAL_CURRENT_CHECK',process_state=v3.process_state(r['pid'],r['creation_time'])))
  for o in r.get('recorded_owned_processes',[]):owners.append(dict(pid=o['pid'],creation_time=o['creation_time'],branch='RECORDED_CHILD_CURRENT_CHECK',process_state=v3.process_state(o['pid'],o['creation_time'])))
 owners+=refreshed_prior_owners(prior['owner_identity_summary'])
 closure=base.closure_scope(owners,prior.get('unmatched_session_directories',[]),prior.get('native_index_reference_coverage',{}).get('not_in_receipt_snapshot',[]))
 physical=base.write_new(out/'PHYSICAL_EXECUTIONS.json',rows);metadata=base.write_new(out/'METADATA_SOURCES.json',reader.sources)
 result=dict(schema='s6c-execution-inventory.v1',adapter_schema=SCHEMA,status='WHOLE_STUDY_COUNTING_WITH_EXPLICIT_PRIOR_AND_FAST_APPEND',audit_status='INCOMPLETE_WITH_FLAGS' if issues or prior.get('audit_status')!='PASS_WITH_SCOPE_LIMITS' or closure['status']!='CLOSED' else 'PASS_WITH_SCOPE_LIMITS',created_utc=F.utc(),prior_inventory=pb,prior_physical_rows=prb,prior_issues=prior.get('issues',[]),prior_rejected_native_receipts=prior.get('rejected_native_receipts',[]),prior_auxiliary=prior.get('auxiliary'),prior_process_closure=prior.get('process_closure'),prior_audit_status=prior.get('audit_status'),prior_native_index_reference_coverage=prior.get('native_index_reference_coverage'),prior_unmatched_session_directories=prior.get('unmatched_session_directories'),prior_index_reference_accounting={k:prior.get(k) for k in ('native_index_row_references','prediction_index_output_references','repeated_prediction_index_references')},appended_fast_manifests=admitted,fast_plans=summaries,observer_index=ib,unique_physical_attempts_observed=len(rows),prior_physical_attempts=len(prior_rows),new_physical_attempts=len(rows)-len(prior_rows),exact_duplicate_physical_rows=duplicates,summary=base.summarize(rows),complete_native_sessions_observed=len({base.canonical(r['session_dir']) for r in rows if (r.get('native_session_complete') is True or r['status']=='COMPLETE') and r.get('session_dir')}),owner_identity_summary=owners,process_closure=closure,issues=issues,outputs=dict(physical_json=physical,metadata_sources=metadata),source_bindings=source_bindings(),scope='All prior physical rows, failures and unknowns retained. New exact fast attempts append once; reused index references add no execution. Source metadata/payload declarations only. Prior enumeration/coverage gaps remain flags; this is never final S6C acceptance.',models=0)
 result['prior_owner_identity_summary']=prior['owner_identity_summary']
 result['branch_summaries']={branch:base.summarize([r for r in rows if r['branch']==branch]) for branch in sorted({r['branch'] for r in rows})}
 return base.write_new(out/'EXECUTION_INVENTORY.json',result)

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['collect']);p.add_argument('--version',required=True);p.add_argument('--prior-inventory',nargs=2,required=True);p.add_argument('--observer-index',nargs=2,required=True);p.add_argument('--manifest',nargs=2,action='append',required=True);print(json.dumps(collect(p.parse_args()),indent=2))

# Explicit additive metadata contexts. No native/observer module is imported.
CONTEXT_PATH=base.STAGING/'inventory_v7/fast_v1_context_v4/s6c_execution_inventory_v7.py'
PINS[str(CONTEXT_PATH)]='55e8cff6f3803196e11e7387e3a458c8630cd8c198f5884e9d53bc7e7b209827'
V2_WRAPPERS={'canonical':'s6c_paced_epoch4_fast_v2.py','long_c':'s6c_long_native_epoch4_fast_v2.py','sentinel':'s6c_paced_arrival_sentinel_fast_v2.py','cross':'s6c_paced_cross_routes_fast_v2.py'}
PINS.update({'s6c_paced_epoch4_fast_v2.py':'a8776724003fa2a642575892327b7c3e88eaddf29606881b302b05157c12b270','s6c_long_native_epoch4_fast_v2.py':'079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67'})
PINS['README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md']='60b1a9011b212233f061c879dabde6ead5a9ac9bc183cb446e1200fb6081e0ce'
PINS['README_S6C_PACED_EPOCH4_FAST_V2.md']='852ddeffb85facb327ae871befce50a983fb45bd950dec426f6ce33329b6af27'
PINS.update({'s6c_paced_arrival_sentinel_fast_v2.py':'d456f9423fe365a330eac0b5b7b372ae12731c49b7b37ab530b3ad707c2c091a','s6c_paced_cross_routes_fast_v2.py':'db4b7db3db45a4685b693dfab3b24cf38e321fee9a5fd56606ae1f3f5852fd5f','README_S6C_PACED_ARRIVAL_SENTINEL_FAST_V2.md':'ecddcf5c66b2b8eb150aa1138d1ae0a3bc0e155134cf55b78b06f85029f64e81','README_S6C_PACED_CROSS_ROUTES_FAST_V2.md':'d02a870c1852e5d39dd3f0333297b36290fd5e98923500e1af44ef9743c53166'})
_V1=types.SimpleNamespace(**{n:globals()[n] for n in ('admit_plan','admit_long_plan','admit_complete_cell','admit_paced_index','invocation_rows','collect_job','collect_paced_job','validate_outer','collect_long_c')})
_V2_CONTEXT=None

def protected_policy_v2():
 import struct
 path=HERE/'s6c_long_native_epoch4_fast_v2.py';tree=ast.parse(path.read_bytes())
 constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('PINS','PROTECTED')}
 ns=dict(Path=Path,types=types,struct=struct,json=json,hashlib=hashlib,__file__=str(path),digest=base.digest,bind=F.bind,**constants)
 v5.compile_functions(path,{'structural_code_value','structural_code_sha256','protected_guard_policy'},ns)
 return ns['protected_guard_policy']()

def fast_version(plan):
 kind=kind_of(plan)
 if kind not in ('canonical','sentinel','cross','long_c'):return 1
 if str(plan.get('namespace','')).endswith('_fast_v2'):
  require(kind in V2_WRAPPERS,'Explicit fast_v2 family source not yet admitted');return 2
 require('protected_guard_policy' not in plan,'New protection policy cannot relabel a fast_v1 namespace')
 return 1

def v2_context():
 global _V2_CONTEXT
 verify_sources()
 if _V2_CONTEXT is None:
  values={**globals(),'FAST':deepcopy(FAST)}
  for kind,name in V2_WRAPPERS.items():values['FAST'][kind]['wrapper']=name
  substitutions={'_fast_v1':'_fast_v2','observer_fast_v1/attempts':'observer_fast_v2/attempts'}
  for kind,name in V2_WRAPPERS.items():
   substitutions[FAST[kind]['wrapper']]=name
   substitutions['README_'+FAST[kind]['wrapper'][:-3].upper()+'.md']='README_'+name[:-3].upper()+'.md'
  nodes=ast.parse(CONTEXT_PATH.read_bytes());names={n.name for n in nodes.body if isinstance(n,ast.FunctionDef)}
  v5.compile_functions(CONTEXT_PATH,names,values,substitutions)
  original=values['validate_fast_sources']
  def validate(plan,kind):
   original(plan,kind);policy=protected_policy_v2();require(plan.get('protected_guard_policy')==policy,'Exact new structural guard policy required')
   if kind=='long_c':require(plan['native_function_code_sha256']==policy['original_structural_code_sha256']['native'],'Long native structural fingerprint differs')
  values['validate_fast_sources']=validate
  _V2_CONTEXT=types.SimpleNamespace(**{n:values[n] for n in names})
 return _V2_CONTEXT

def admit_plan(reader,b):
 plan,_=bound(reader,b)
 return (v2_context() if fast_version(plan)==2 else _V1).admit_plan(reader,b)

def admit_long_plan(reader,b):
 plan,_=bound(reader,b)
 return (v2_context() if fast_version(plan)==2 else _V1).admit_long_plan(reader,b)

def admit_complete_cell(reader,job,plan,pb,spec,state=None,*,observer_receipts=None):
 return (v2_context() if fast_version(plan)==2 else _V1).admit_complete_cell(reader,job,plan,pb,spec,state,observer_receipts=observer_receipts)

def admit_paced_index(reader,b,plan,pb):
 return (v2_context() if fast_version(plan)==2 else _V1).admit_paced_index(reader,b,plan,pb)

def invocation_rows(reader,plan,pb,*,observer_receipts=None):
 return (v2_context() if fast_version(plan)==2 else _V1).invocation_rows(reader,plan,pb,observer_receipts=observer_receipts)

def collect_job(reader,job,plan,pb,spec,*,observer_receipts=None):
 return (v2_context() if fast_version(plan)==2 else _V1).collect_job(reader,job,plan,pb,spec,observer_receipts=observer_receipts)

def collect_paced_job(reader,job,plan,pb,spec):
 return (v2_context() if fast_version(plan)==2 else _V1).collect_paced_job(reader,job,plan,pb,spec)

def validate_outer(reader,path,*,observer_receipts=None):
 admission,_=reader.read(Path(path));plan,_=bound(reader,admission['manifest'])
 return (v2_context() if fast_version(plan)==2 else _V1).validate_outer(reader,path,observer_receipts=observer_receipts)

def collect_long_c(reader,plan,pb,records):
 return (v2_context() if fast_version(plan)==2 else _V1).collect_long_c(reader,plan,pb,records)

if __name__=='__main__':main()
