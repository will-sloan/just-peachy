"""V6 synthetic metadata checks; README_S6C_EXECUTION_INVENTORY_V6.md."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import argparse,ast,hashlib,json,tempfile,types
import s6c_execution_inventory_v6 as A

def read(p):return json.loads(p.read_bytes())
def replace(p,v):
 p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');return A.base.binding(p,p.read_bytes())
def fixture(root,change=None):
 ns=A.v5.compile_functions(A.HERE/'test_s6c_execution_inventory_v4.py',{'fake','fixture'},dict(A=A.X,Path=Path,deepcopy=deepcopy),A.REPLACEMENTS)
 original_mutations={'journal','closure_error','closure_missing','closure_live','closure_writer','native_schema','native_profile','native_owner','native_tail','native_loads','native_time','cell_epoch','cell_source','cell_gap','cell_profile','cell_offset','admission_owner','launch_argv','outcome_error','outcome_restored','done_cell','done_native','done_artifacts','done_owner','done_flag'}
 reader,j,p,pb,s,db=ns['fixture'](root,change if change in original_mutations else None);folder=Path(j['report_root']);launch=read(folder/'LAUNCH.json');co=dict(pid=12346,creation_time=11.,argv=['synthetic-coordinator']);inv=root/'invocations/one'
 save=A.base.write_new;clb=save(inv/'LAUNCH.json',dict(status='STARTED',owner=co,manifest=pb));lease=dict(**co,kind=A.KIND,manifest=pb,launch=clb)
 if change=='lease_kind':lease['kind']='WRONG'
 archived=save(inv/'QUIET_LEASE_RELEASED.json',lease);qb=dict(archived,path=str(A.REPORT/'PACED_QUIET_OWNER.json'))
 admission=read(folder/'CELL_ADMISSION.json');oldab=A.base.binding(folder/'CELL_ADMISSION.json',(folder/'CELL_ADMISSION.json').read_bytes());admission['quiet_lease']=dict(qb,sha256='2'*64) if change=='cell_lease' else qb;newab=replace(folder/'CELL_ADMISSION.json',admission)
 complete=read(folder/'COMPLETE.json');complete['artifacts']=[newab if b==oldab else b for b in complete['artifacts']];db=replace(folder/'COMPLETE.json',complete)
 spawn=dict(status='SPAWNED_CREATION_UNVERIFIED',pid=12345,creation_time=None,argv=A.X.expected_worker_argv(j,p,pb),manifest=pb,job_key=j['job_key'],job_id=j['job_id'])
 if change=='spawn_pid':spawn['pid']=12344
 if change=='spawn_bool_pid':spawn['pid']=True
 if change=='spawn_creation':spawn['creation_time']=10.
 if change=='spawn_argv':spawn['argv']+=['--job-id','different']
 if change=='spawn_manifest':spawn['manifest']={}
 if change!='no_spawn':save(folder/'SPAWNED_PROCESS.json',spawn)
 remaining=[]
 if change in ('unknown_release','unknown_retained'):remaining=[dict(pid=12345,creation_time=None,alive=None)]
 outcome=dict(status='COMPLETE',owner=co,manifest=pb,requested=1,completed=1,rows=[dict(job_id=j['job_id'],status='COMPLETE_REUSED' if change=='reused_reference' else 'COMPLETE',completion=db)],error=None,remaining_owned=remaining)
 if change=='duplicate_reference':outcome['rows']*=2;outcome['completed']=2
 ob=save(inv/'OUTCOME.json',outcome)
 release=dict(status='RELEASED',released=True,archived_binding=archived)
 c=dict(status='QUIET_LEASE_RELEASED',owner=co,manifest=pb,outcome=ob,lease_release=release)
 if change=='unknown_retained':c['status']='LEASE_RETAINED_OWNED_CLOSURE_UNVERIFIED';release.update(status='RETAINED_OWNED_CLOSURE_UNVERIFIED',released=False)
 if change=='closure_link':c['outcome']={}
 save(inv/'CLOSURE.json',c)
 return reader,j,p,pb,s,db

def checks():
 done=[]
 def good(name,ok=True):assert ok,name;done.append(name)
 # Pure source functions only; no driver/module/model or hardware startup.
 with patch.object(A.v3,'process_state',lambda *args:dict(alive=False,state='FIXTURE_CLOSED')):
  negatives=['journal','closure_error','closure_missing','closure_live','closure_writer','native_schema','native_profile','native_owner','native_tail','native_loads','native_time','cell_epoch','cell_source','cell_gap','cell_profile','cell_offset','admission_owner','launch_argv','outcome_error','outcome_restored','done_cell','done_native','done_artifacts','done_owner','done_flag','lease_kind','cell_lease','spawn_pid','spawn_bool_pid','spawn_creation','spawn_argv','spawn_manifest','no_spawn','unknown_release','unknown_retained','duplicate_reference','closure_link']
  for change in [None,'reused_reference',*negatives]:
   with tempfile.TemporaryDirectory(prefix='s6c_inventory_v6_') as d:
    reader,j,p,pb,s,db=fixture(Path(d),change)
    try:value=A.admit_complete_cell(reader,j,p,pb,s,state=lambda *a:dict(alive=False))
    except (ValueError,KeyError,TypeError):
     if change not in negatives:raise
     good('reject_'+change)
    else:
     good('complete_'+str(change),change not in negatives and value['complete_binding']==db)
     row=A.collect_job(reader,j,p,pb,s);good('normal_spawn_launch_single_attempt_'+str(change),row['status']=='COMPLETE' and row['native_session_complete'])
     physical=[];sessions={};good('repeat_metadata_not_new_attempt_'+str(change),A.v4.add_physical(physical,sessions,row) and not A.v4.add_physical(physical,sessions,deepcopy(row)) and len(physical)==1)
  for change in [None,'bad_argv','terminal_without_launch']:
   with tempfile.TemporaryDirectory(prefix='s6c_inventory_spawn_') as d:
    root=Path(d);(root/'snapshot').mkdir();reader=A.base.MetadataReader(root/'snapshot');j=dict(job_id='j',job_key='k',candidate_id='C085',case_id='case',asr_tap='O0',identity_tap='O1',repetition=1,profile_row=dict(recipe_id='N01'),profile_sha256='p',source={},gallery=None,report_root=str(root/'job'));p=dict(schema=A.CROSS,execution_manifest={});pb={};argv=A.X.expected_worker_argv(j,p,pb|dict(path=str(root/'MANIFEST.json')));pb['path']=str(root/'MANIFEST.json')
    if change=='bad_argv':argv+=['--job-id','other']
    A.base.write_new(root/'job/SPAWNED_PROCESS.json',dict(status='SPAWNED_CREATION_UNVERIFIED',pid=54321,creation_time=None,argv=argv,manifest=pb,job_key='k',job_id='j'))
    if change=='terminal_without_launch':A.base.write_new(root/'job/CELL_OUTCOME.json',dict(status='FAILED'))
    with patch.object(A.v3,'process_state',side_effect=AssertionError('PID-only process lookup forbidden')):row=A.collect_job(reader,j,p,pb,{})
    good('spawn_only_'+str(change),row['creation_time'] is None and row['process_state']['alive'] is None and not row['native_session_complete'] and row['status']=='UNVERIFIED_SPAWN_IDENTITY')
  with tempfile.TemporaryDirectory() as d:
   reader,j,p,pb,s,_=fixture(Path(d),'spawn_argv');row=A.collect_job(reader,j,p,pb,s);good('bad_spawn_argv_known_launch_stays_unverified_attempt',row['status']=='UNVERIFIED_CELL_LINEAGE' and not row['native_session_complete'])
  with tempfile.TemporaryDirectory() as d:
   reader,j,p,pb,s,_=fixture(Path(d),'no_spawn');row=A.collect_job(reader,j,p,pb,s);good('finite_launch_missing_spawn_retained_unverified',row['status']=='UNVERIFIED_CELL_LINEAGE' and row['pid']==12345 and not row['native_session_complete'])
  for live in (True,None):
   with tempfile.TemporaryDirectory() as d:
    reader,j,p,pb,s,_=fixture(Path(d))
    try:A.admit_complete_cell(reader,j,p,pb,s,state=lambda *args:dict(alive=live))
    except ValueError:good('native_current_owner_'+str(live))
    else:raise AssertionError('Unclosed current owner')
   with tempfile.TemporaryDirectory() as d:
    reader,j,p,pb,s,_=fixture(Path(d))
    with patch.object(A.v3,'process_state',lambda *args:dict(alive=live)):
     try:A.admit_complete_cell(reader,j,p,pb,s,state=lambda *args:dict(alive=False))
     except ValueError:good('coordinator_current_owner_'+str(live))
     else:raise AssertionError('Unclosed coordinator owner')
  for missing in ('OUTCOME','CLOSURE'):
   with tempfile.TemporaryDirectory() as d:
    reader,j,p,pb,s,_=fixture(Path(d));inv=Path(d)/'invocations/two';co=dict(pid=12347,creation_time=12.,argv=['later-coordinator']);A.base.write_new(inv/'LAUNCH.json',dict(status='STARTED',owner=co,manifest=pb))
    if missing=='CLOSURE':A.base.write_new(inv/'OUTCOME.json',dict(status='PARTIAL',owner=co,manifest=pb,requested=1,completed=0,rows=[],error='interrupted',remaining_owned=[]))
    records,owners=A.invocation_rows(reader,p,pb);good('missing_'+missing+'_explicit_unknown',any(o['process_state']['alive'] is None for o in owners))
    try:A.admit_complete_cell(reader,j,p,pb,s,state=lambda *a:dict(alive=False))
    except ValueError:good('earlier_complete_later_missing_'+missing+'_reject')
    else:raise AssertionError('Missing later closure silently admitted')
 # Independently compare compiled method AST behavior and unchanged original globals.
 good('original_v4_schema_not_mutated',A.v4.CANONICAL=='s6c-canonical-paired-paced.v1' and A.v4.PINS['s6c_paced_epoch4.py']=='b4b0dc48190654edbdcb6259cf2b8abc08d8675d49367863ff539f7eb54df8a3')
 return done

def main(output):
 done=checks();sources=A.source_bindings();real=[]
 with tempfile.TemporaryDirectory(prefix='s6c_cross_grid_meta_') as d:
  snap=Path(d)/'snap';snap.mkdir();reader=A.base.MetadataReader(snap)
  spec,sb=reader.read(A.REPORT/'EPOCH4_EXECUTION_MANIFEST.json');assert sb['sha256']=='720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945'
  panel,pb=reader.read(A.REPORT/'design/confirmation_plan_v1/PACED_PANEL_PROPOSAL_V1.json');assert pb['sha256']=='f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da'
  selected=A.X.GUARDS['selected_panel'](panel,'cross16_plus4',A.PAIR);routes=A.X.GUARDS['candidate_routes'](spec,A.PAIR);grid=A.X.GUARDS['grid'](A.PAIR,selected)
  assert len(grid)==40 and set(routes)=={('C085','O0'),('C086','O1')};done.append('exact_actual_epoch4_registered_cross40_metadata_only');real=[sb,pb]
  for kind in ['candidate','identity','profile','panel']:
   s=deepcopy(spec);ids=list(A.PAIR);p=deepcopy(panel)
   if kind=='candidate':ids.reverse()
   if kind=='identity':next(x for x in s['profiles'] if x['candidate_id']=='C085')['identity_tap']='O0'
   if kind=='profile':next(x for x in s['profiles'] if x['candidate_id']=='C085')['profile']['tracker']['cues_enabled']=True
   if kind=='panel':p['case_ids']=p['case_ids'][:-1]
   try:q=A.X.GUARDS['selected_panel'](p,'cross16_plus4',ids);A.X.GUARDS['candidate_routes'](s,ids);A.X.GUARDS['grid'](ids,q)
   except ValueError:done.append('actual_metadata_reject_'+kind)
   else:raise AssertionError(kind)
 result=dict(status='PASS_SOURCE_AND_MODEL_FREE_METADATA',checks=len(done),tests=done,sources=sources,actual_metadata=real,test= A.base.binding(Path(__file__),Path(__file__).read_bytes()),preserved_v1=dict(directory=str(A.base.SIM/'staging/s6c/20260910T123540Z/execution_inventory/before_v6_missing_spawn_fallback_v1'),scope='Exact V1 helper/test/README/check receipt retained before conservative missing-spawn fallback and extra current-owner fixtures.'),native_models_started=0,actual_manifests_prepared=0,actual_inventory_runs=0,scope='Synthetic complete/fault chains and actual epoch/panel/profile metadata only. No native cell, PCM, model, trajectory or full inventory read.')
 print(json.dumps(A.base.write_new(output,result)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
