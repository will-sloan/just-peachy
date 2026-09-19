"""B36 V2 private source/grid/closure checks; README_S6C_PACED_B36_FAST_V2.md."""
from __future__ import annotations
import argparse,ast,copy,json,tempfile,types
from pathlib import Path
from unittest.mock import patch
import s6c_paced_b36_fast_v2 as B

def run(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=False);checks=[]
 def ck(n,v=True):
  if not v:raise AssertionError(n)
  checks.append(n)
 def bad(n,fn):
  try:fn()
  except (ValueError,KeyError,OSError):ck(n)
  else:raise AssertionError(n)
 before=copy.deepcopy(B.F.VARIANTS);c=B.context();old_api=B.F.adapt('b36');api=c.adapt('b36')
 node=copy.deepcopy(api._release_run_ast);count=[]
 class Reverse(ast.NodeTransformer):
  def visit_Expr(self,n):
   if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='archive_finished_lease':
    ck('exact_new_release_arguments',ast.dump(n)==ast.dump(ast.parse('archive_finished_lease(lock,invocation,plan,args,me)').body[0]));count.append(1)
    return ast.copy_location(ast.parse("lock.rename(invocation/'QUIET_OWNER_CLOSED.json')").body[0],n)
   return self.generic_visit(n)
 node=Reverse().visit(node);ns=dict(old_api.run.__globals__);exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(B.HERE/B.F.VARIANTS['b36']['parent']),'exec'),ns)
 ck('only_final_runtime_call_delta',len(count)==1 and ns['run'].__code__.co_code==old_api.run.__code__.co_code and ns['run'].__code__.co_consts==old_api.run.__code__.co_consts and ns['run'].__code__.co_names==old_api.run.__code__.co_names)
 ck('original_globals_not_patched',B.F.VARIANTS==before and old_api.run.__globals__['__file__']!=api.run.__globals__['__file__'])
 ck('new_schema_and_actual_coordinator',api.SCHEMA==B.SCHEMA and api.run.__globals__['__file__']==str(Path(B.__file__).resolve()))
 inventory=ast.parse((B.HERE/'s6c_execution_inventory_v7.py').read_bytes())
 counter=copy.deepcopy(next(n for n in inventory.body if isinstance(n,ast.FunctionDef) and n.name=='scan_counters'))
 class CounterRoots(ast.NodeTransformer):
  def visit_Call(self,n):
   if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='base' and n.func.attr=='canonical':
    return ast.copy_location(ast.parse('str(Path(p).resolve())',mode='eval').body,n)
   return self.generic_visit(n)
  def visit_Attribute(self,n):
   if isinstance(n.value,ast.Name) and n.value.id=='base' and n.attr=='STAGING':return ast.copy_location(ast.parse('STAGING',mode='eval').body,n)
   return self.generic_visit(n)
 actual_counter=next(n for n in ast.parse(Path(B.__file__).read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='scan_counters')
 ck('exact_V7_counter_AST_with_local_root_expressions',ast.dump(CounterRoots().visit(counter))==ast.dump(actual_counter))
 for name in ('converted_jobs','validate_plan_structure','dependencies','resources','sample_tree','alive','source_authority'):
  a=getattr(api,name);b=getattr(old_api,name);ck('original_'+name,a.__code__.co_code==b.__code__.co_code and a.__code__.co_consts==b.__code__.co_consts)
 parent,pb=B.F.read_bound(B.PARENT);original,ob=B.F.read_bound(parent['original_prepared_manifest']['path'],parent['original_prepared_manifest'])
 projected=c.projection('b36',original,ob,'fixture_fast_v2','2026-09-12T00:00:00Z')
 ck('actual40jobs_exact',projected['jobs']==parent['jobs'] and len(projected['jobs'])==40)
 for field in ('driver','historical_epoch','panel','cases','streams','repeat_case_sets','timeout_sec','deadline_utc','runtime_versions','resource_limits'):
  ck('actual_metadata_'+field,projected[field]==parent[field])
 ck('new_policy_and_source_bindings',projected['lease_archival_policy']==B.archival_policy() and projected['coordinator']==B.F.bind(B.__file__) and B.F.bind(B.__file__) in projected['fast_observer']['sources'])
 bad('reject_old_namespace',lambda:B.roots('b36','b36_fast_v1'))
 bad('reject_other_family',lambda:B.roots('controls','other_fast_v2'))
 with tempfile.TemporaryDirectory(prefix='s6c_b36_release_') as temp:
  root=Path(temp).resolve()
  for fault in (None,'partial','live','changed_lease','existing_G_archive'):
   report=root/str(fault)/'report';payload=root/str(fault)/'payload'
   with patch.object(B,'REPORT',report),patch.object(B,'PAYLOAD',payload):
    croot,out=B.roots('b36','fixture_fast_v2');inv=out/'invocations/one';inv.mkdir(parents=True);report.mkdir(parents=True)
    jobs=[dict(job_id=f'job{i}',job_key=f'key{i}') for i in range(40)]
    plan=dict(output_root=str(out),jobs=jobs,driver={'path':'unchanged driver'},lease_archival_policy=B.archival_policy())
    mb=B.F.save(out/'MANIFEST.json',plan);quiet=B.F.save(root/str(fault)/'quiet.json',dict(status='AUTHORIZED_FOR_QUIET_PACED',manifest_sha256=mb['sha256'],all_other_model_hil_work_stopped=True,all_heavy_analysis_stopped=True))
    argv=[str(B.R.EDGE),'-B',str(Path(B.__file__).resolve()),'run','--manifest',mb['path'],'--quiet-admission',quiet['path']]
    owner=dict(pid=123,creation_time=1.,argv=argv);me=types.SimpleNamespace(pid=123,create_time=lambda:1.,cmdline=lambda:argv)
    lock=report/'PACED_QUIET_OWNER.json';lease=B.F.save(lock,dict(pid=124 if fault=='changed_lease' else 123,creation_time=1.,manifest=mb))
    B.F.save(inv/'LAUNCH.json',dict(status='STARTED',pid=123,creation_time=1.,manifest=mb,coordinator=B.F.bind(B.__file__),native_driver=plan['driver'],quiet_admission=quiet))
    B.F.save(inv/'COMPLETION.json',dict(status='PARTIAL' if fault=='partial' else 'COMPLETE',completed=39 if fault=='partial' else 40,requested=40,error=None,manifest=mb))
    for i,j in enumerate(jobs):B.F.save(out/'jobs'/j['job_id']/'COMPLETE.json',dict(status='COMPLETE',job_key=j['job_key'],all_owned_processes_closed=True,owned_processes=[dict(pid=1000+i,creation_time=2.+i)]))
    if fault=='existing_G_archive':B.F.save(inv/'QUIET_OWNER_CLOSED.json',{'existing':'do not overwrite'})
    args=types.SimpleNamespace(manifest=Path(mb['path']),quiet_admission=Path(quiet['path']))
    def closed(owners,*a,**k):
     if fault=='live':raise ValueError('injected live child')
     return [dict(owner=o,observation=dict(alive=False,error=None)) for o in owners]
    with patch.object(B.R,'all_closed',closed):
     if fault:bad('release_rejects_'+fault,lambda:B.archive_finished_lease(lock,inv,plan,args,me))
     else:B.archive_finished_lease(lock,inv,plan,args,me)
    release_path=croot/'invocations/one/LEASE_RELEASE.json';release,rb=B.F.read_bound(release_path)
    if fault:
     ck('failure_preserves_lease_'+fault,B.F.bind(lock)==lease and release['status']=='RETAINED_OR_RELEASE_UNVERIFIED' and release['error']);continue
    ck('private_success_exact_C_archive',not lock.exists() and release['status']=='RELEASED' and release['lease_release']['archived_binding']['sha256']==lease['sha256'] and not (inv/'QUIET_OWNER_CLOSED.json').exists())
    sources=B.context().source_bindings('b36');scan_path=croot/'observer_invocations/one/SCANNER_OUTCOME.json'
    counters={str(p):dict(calls=1,successful=1,failed=0,last_bytes=0,total_wall_sec=0.,total_cpu_sec=0.,max_wall_sec=0.) for p in (report,B.STAGING,payload)}
    scan=dict(schema='s6c-historical-fast-observer-outcome.v1',coordinator_pid=owner['pid'],storage_scans=counters,status='COMPLETE',error=None,manifest=mb,entry='run',owner=owner,wrapper=B.F.bind(B.__file__),sources_before=sources,sources_after=sources,sources_unchanged=True)
    B.F.save(scan_path,scan)
    with patch.object(B,'admit_plan',return_value=(plan,mb)):
     proof=B.admit_complete_batch(B.F.Reader(),mb,inspect=lambda o:dict(alive=False,error=None));ck('private_closed_batch_API',proof['cells']==40 and proof['status']=='B36_NATIVE_BATCH_COMPLETE_WITH_EXPLICIT_C_ARCHIVE')
     bad('closed_API_rejects_live_coordinator',lambda:B.admit_complete_batch(B.F.Reader(),mb,inspect=lambda o:dict(alive=True,error=None)))
     saved=release_path.read_bytes();changed=copy.deepcopy(release);changed['original_G_archive_created']=True;release_path.write_text(json.dumps(changed))
     bad('closed_API_rejects_G_archive_fabrication',lambda:B.admit_complete_batch(B.F.Reader(),mb,inspect=lambda o:dict(alive=False,error=None)));release_path.write_bytes(saved)
     def corrupt_scan(label,change):
      wrong=copy.deepcopy(scan);change(wrong);scan_path.write_text(json.dumps(wrong))
      bad('closed_API_rejects_observer_'+label,lambda:B.admit_complete_batch(B.F.Reader(),mb,inspect=lambda o:dict(alive=False,error=None)))
      scan_path.write_text(json.dumps(scan))
     for field in ('schema','coordinator_pid','storage_scans'):
      corrupt_scan('missing_'+field,lambda d,k=field:d.pop(k))
     corrupt_scan('wrong_schema',lambda d:d.update(schema='wrong'))
     corrupt_scan('wrong_pid',lambda d:d.update(coordinator_pid=124))
     corrupt_scan('noninteger_pid',lambda d:d.update(coordinator_pid=123.))
     corrupt_scan('missing_root',lambda d:d['storage_scans'].pop(str(report)))
     corrupt_scan('wrong_root',lambda d:d['storage_scans'].__setitem__(str(root/'unexpected'),d['storage_scans'].pop(str(report))))
     for field,value,label in (('calls',2,'count_relationship'),('calls',True,'bool_count'),('successful',0,'zero_success'),('failed',-1,'negative_count'),('last_bytes',-1,'negative_bytes'),('total_wall_sec',float('nan'),'nan_clock'),('total_cpu_sec',float('inf'),'infinite_clock'),('max_wall_sec',True,'bool_clock')):
      corrupt_scan(label,lambda d,k=field,v=value:d['storage_scans'][str(report)].__setitem__(k,v))
 return B.F.save(output/'SOURCE_CHECKS.json',dict(schema='s6c-b36-release-v2-checks.v1',status='PASS_SOURCE_METADATA_AND_PRIVATE_FIXTURES',checks=len(checks),names=checks,sources=[B.F.bind(B.__file__),B.F.bind(__file__),B.F.bind(B.HERE/'README_S6C_PACED_B36_FAST_V2.md'),B.F.bind(B.F.__file__),B.F.bind(B.R.__file__),B.F.bind(B.HERE/'s6c_execution_inventory_v7.py'),B.F.bind(B.STAGING/'b36_v2/before_observer_guards_v1/SOURCE_INDEX.json'),B.F.bind(B.STAGING/'b36_v2/before_staging_constant_fix_v1/s6c_paced_b36_fast_v2.py'),B.F.bind(B.STAGING/'b36_v2/before_staging_constant_fix_v1/test_s6c_paced_b36_fast_v2.py'),B.F.bind(B.STAGING/'b36_v2/before_staging_constant_fix_v1/FAILURE_NOTE.txt'),pb,ob],native_calls=0,actual_preparations=0,actual_recoveries=0,scope='Actual prior two compact manifests/source bytes plus private synthetic40-cell closure. No actual runtime cells, PCM, models or storage traversal.'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
