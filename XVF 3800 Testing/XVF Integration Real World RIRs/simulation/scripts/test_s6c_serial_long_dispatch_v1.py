"""Tiny serial long admission/closure guards; README_S6C_SERIAL_LONG_DISPATCH_V1.md."""
from __future__ import annotations
import argparse,ast,copy,json,tempfile,types
from pathlib import Path
from unittest.mock import patch
import s6c_serial_long_dispatch_v1 as L

def run(output):
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);checks=[]
 def ck(name,v=True):
  if not v:raise AssertionError(name)
  checks.append(name)
 def bad(name,fn):
  try:fn()
  except (ValueError,KeyError,OSError):ck(name)
  else:raise AssertionError(name)
 ctx=L.execution_context();old=next(n for n in ast.parse(L.pinned('s6c_paced_dispatch_v3.py').read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='run')
 original_quiet=next(n for n in ast.walk(old) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='quiet')
 class Reverse(ast.NodeTransformer):
  def visit_Constant(self,n):
   v={'serial_long_dispatcher':'serial_paced_dispatcher','README_S6C_SERIAL_LONG_DISPATCH_V1.md':'README_S6C_PACED_DISPATCH_V3.md','s6c-serial-long-dispatch-result.v1':'s6c-serial-paced-dispatch-result.v1'}
   return ast.copy_location(ast.Constant(v[n.value]),n) if isinstance(n.value,str) and n.value in v else n
  def visit_Expr(self,n):
   if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='ensure_start':return None
   return self.generic_visit(n)
  def visit_Assign(self,n):
   if len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='quiet':return copy.deepcopy(original_quiet)
   return self.generic_visit(n)
 ck('exact_original_run_AST_after_declared_changes',ast.dump(Reverse().visit(copy.deepcopy(ctx._run_ast)))==ast.dump(old))
 for n in ('launch','save','save_heartbeat','state','finite_owner','same_owner','replace_heartbeat'):ck('original_'+n,getattr(ctx,n) is getattr(L.D,n))
 ck('private_original_globals',L.D.__file__!=ctx.__file__ and L.D.run.__globals__['admit'] is L.D.admit)
 items,plans=L.fixed_items();ck('actual_five_prepared_exact_order',[i['candidate_id'] for i in items]==['C065','C067','C088','C091','B36'])
 ck('same_source_each',len({p['composition']['sha256'] for p in plans})==1 and all(i['source_sec']==L.DURATION for i in items))
 ck('unchanged_C_and_B_reserves',[i['minimum_remaining_sec'] for i in items]==[L.DURATION+780]*4+[L.DURATION+205])
 for i,p in zip(items,plans):L.unstarted(i,p)
 ck('actual_preparations_unstarted')
 # The dispatcher itself is only an orchestrator, not a second model worker.
 ns=dict(Path=Path);node=next(n for n in ast.parse(L.pinned(L.C_HELPER).read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='worker_command');exec(compile(ast.Module(body=[node],type_ignores=[]),'<original-worker-command>','exec'),ns)
 ck('original_quiet_detector_allows_nonmodel_dispatcher',ns['worker_command']([str(L.D.EDGE),'-B',str(Path(L.__file__)),'run','--queue','q','h','--authority','a','h']) is False)
 with tempfile.TemporaryDirectory(prefix='s6c_long_dispatch_') as temp:
  root=Path(temp).resolve();report=root/'report';payload=root/'payload';stage=root/'stage'
  with patch.object(L,'REPORT',report),patch.object(L,'PAYLOAD',payload),patch.object(L,'STAGING',stage):
   # Run the original historical quiet detector against only synthetic processes.
   processes=[];quiet_ns=dict(Path=Path,os=types.SimpleNamespace(getpid=lambda:999),psutil=types.SimpleNamespace(process_iter=lambda fields:processes),owner_state=lambda pid,created:dict(alive=True,error=None),require=L.require,REPORT=report,L=types.SimpleNamespace(worker_command=ns['worker_command']))
   quiet_node=next(n for n in ast.parse(L.pinned('s6c_long_b36_v1.py').read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='quiet');exec(compile(ast.Module(body=[quiet_node],type_ignores=[]),'<original-historical-quiet>','exec'),quiet_ns)
   def process(argv):return types.SimpleNamespace(pid=100,info=dict(cmdline=argv,create_time=20.))
   processes[:]=[process([str(L.D.EDGE),'-B',str(Path(L.__file__)),'run','--queue','q','h','--authority','a','h'])]
   ck('original_B36_quiet_allows_exact_serial_parent',quiet_ns['quiet']()==[])
   for script,action in [('s6c_long_dispatch_v1.py','run'),(L.C_HELPER,'run'),(L.B_HELPER,'worker')]:
    processes[:]=[process([str(L.D.EDGE),'-B',str(L.HERE/script),action])];bad('original_B36_quiet_rejects_'+script,quiet_ns['quiet'])
   for is_b in (False,True):
    family='B36' if is_b else 'C065';base=report/family;base.mkdir(parents=True);native=base/'native';native.mkdir();inv=base/'invocations/one';inv.mkdir(parents=True)
    mb=L.D.save(base/'MANIFEST.json',{'fixture':family});qb=L.D.save(base/'quiet.json',{'fixture':'quiet'})
    helper=L.D.binding(L.HERE/(L.B_HELPER if is_b else L.C_HELPER));argv=[str(L.D.EDGE),'-B',helper['path'],'run','--manifest',mb['path'],'--quiet-admission',qb['path']];owner=dict(pid=100,creation_time=20.,argv=argv)
    item=dict(candidate_id=family,item_id=family,manifest=mb,helper=helper,cells=1,output_root=str(base))
    composition={'bound':'same'};journal={'path':str(native/'audio_spool.pcm16'),'bytes':L.FRAMES*2,'sha256':'pcm'}
    counters={str(p):dict(calls=1,successful=1,failed=0,last_bytes=0,total_wall_sec=0.,total_cpu_sec=0.,max_wall_sec=0.) for p in (report,payload,stage)}
    if is_b:
     job=dict(job_id='B36_CONTINUOUS_O0_R1',job_key='exact',input_pcm_sha256='pcm');out=payload/family/'jobs'/job['job_id'];out.mkdir(parents=True);session=out/'sessions/one';session.mkdir(parents=True)
     childowner=dict(pid=101,creation_time=21.,argv=[str(L.D.EDGE),str(L.HERE/L.B_HELPER),'worker','--manifest',mb['path'],'--owner-lease',str(report/'PACED_QUIET_OWNER.json')]);states=[dict(pid=101,creation_time=21.,alive=False)]
     journal={**journal,'path':str(session/'audio_spool.pcm16')}
     n=dict(status='COMPLETE',job_key='exact',**childowner,source_duration_sec=L.DURATION,complete_pcm_samples=L.FRAMES,native_pcm_exact=True,asr_cursor_complete=True,journal=journal,empty_gallery=True,hardware_calls=0,truth_passed_to_predictor=False,numeric_pools={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},session_dir=str(session),events={'path':str(session/'events.jsonl')},summary_binding={'path':str(session/'session_summary.json')},display_events={'path':str(out/'DISPLAY_EVENTS.json')},summary={'telemetry':{'asr_cursor_sec':L.DURATION,'source_duration_sec':L.DURATION}},native_dispatch_delivery={k:True for k in ('no_gaps_or_duplicates','starts_at_zero','ends_at_full_duration','exact_samples')})
     n['baseline_dispatch_instrumentation_unavailable']=False
     nb=L.D.save(out/'WORKER_RESULT.json',n);rs='s6c-exact-historical-b36-continuous-fast-result.v1';cb=L.D.save(out/'CONTINUOUS_OUTCOME.json',dict(schema=rs,status='NATIVE_COMPLETE',manifest=mb,native_result=nb,job_key='exact',error=None,original_worker_function_unchanged=True,owner=childowner))
     plan=dict(report_root=str(base),output_root=str(payload/family),jobs=[job],composition=composition,historical_epoch={'bound':'epoch'},fast_observer={'sources':[helper]})
     result=dict(schema=rs,status='COMPLETE_NATIVE_AND_OWNED_CHILD_CLOSED',manifest=mb,owner=owner,job=job,original_worker_unchanged=True,all_owned_processes_closed=True,composition=composition,historical_epoch=plan['historical_epoch'],source_duration_sec=L.DURATION,source_duration_samples=L.FRAMES,owned_processes=states,native_result=nb,native_outcome=cb,native_owner=childowner)
     rb=L.D.save(base/'RESULT.json',result);leasevalue=dict(**owner,manifest=mb,quiet_admission=qb,kind='S6C_EXACT_HISTORICAL_B36_CONTINUOUS_FAST')
     leasebytes=(json.dumps(leasevalue,indent=2)+'\n').encode();archive=inv/'QUIET_LEASE_RELEASED.json';archive.write_bytes(leasebytes);lb=L.D.binding(archive);source={**lb,'path':str(report/'PACED_QUIET_OWNER.json')}
     admission=dict(status='STARTED',owner=owner,manifest=mb,quiet_admission=qb,quiet_lease=source)
     L.D.save(out/'CONTINUOUS_ADMISSION.json',dict(owner=childowner,manifest=mb,job=job,quiet_lease=source));L.D.save(out/'LAUNCH.json',dict(**childowner,manifest=mb,job_key=job['job_key']))
     ab=L.D.save(inv/'ADMISSION.json',admission);outcome=dict(status='NATIVE_COMPLETE',owner=owner,manifest=mb,error=None,native_result=nb,continuous_result=rb,owned_processes=states);ob=L.D.save(inv/'NATIVE_OUTCOME.json',outcome)
     closure={**outcome,'status':'NATIVE_COMPLETE_QUIET_RELEASED','pre_release_outcome':ob}
     scan=dict(schema='s6c-historical-fast-observer-outcome.v1',status='NATIVE_COMPLETE',coordinator_pid=100,sources_before=[helper],sources_after=[helper],sources_unchanged=True,storage_scans=counters)
     scanpath=base/'observer_invocations/one/SCANNER_OUTCOME.json'
    else:
     row=dict(candidate_id='C065',asr_tap='O0',identity_tap='O0');common={'bound':'common','path':'s6c_common.py'};eb=L.D.save(base/'epoch.json',{'execution_files':[common]})
     plan=dict(profile_row=row,gallery=None,gallery_row=None,gallery_index=None,composition=composition,execution_manifest=eb,imports={'bound':'imports'},report_root=str(native),pcm_sha256={'O0':'pcm'},observer_policy={'bound':'policy'})
     co={**owner,'argv':owner['argv'][2:]};admission=dict(status='ADMITTED_NOT_YET_COMPLETED',owner=co,manifest=mb,quiet_admission=qb);ab=L.D.save(inv/'ADMISSION.json',admission)
     leasevalue=dict(**co,manifest=mb,kind='S6C_EPOCH4_LONG_NATIVE',admission=ab);archive=inv/'QUIET_LEASE_RELEASED.json';archive.write_text(json.dumps(leasevalue));lb=L.D.binding(archive);source={**lb,'path':str(report/'PACED_QUIET_OWNER.json')}
     fb=L.D.save(native/'session_finalization_v3.json',dict(state='COMPLETED',finalization_error=None,live_lanes_at_finalization=[],resident_bundle_lease_retained=False,event_and_transcript_handles_closed=True))
     identity={**journal,'path':str(native/'identity_audio_spool.pcm16')}
     n=dict(schema='s6c_continuous_paced_native.v1',status='COMPLETE',owner=co,profile=row,composition=composition,source_duration_sec=L.DURATION,long_session_gallery_condition=None,gallery_index=None,resident_bundle_loads=1,resident_sessions_created=1,live_owned_lanes=[],hardware_invocations=0,final_telemetry={'asr_cursor_sec':L.DURATION},native_journals={'audio_spool.pcm16':journal,'identity_audio_spool.pcm16':identity},native_artifacts=[journal,identity,fb]);nb=L.D.save(native/'RESULT.json',n)
     outcome=dict(status='NATIVE_COMPLETE_RELEASE_PENDING',owner=co,manifest=mb,admission=ab,error=None,protected_functions_restored=True,original_result_not_rewritten=True,profile_row=row,gallery=None,source_composition=composition,source_composition_epoch='epoch2',actual_execution_epoch='epoch4',actual_execution_manifest=eb,imports=plan['imports'],original_native_result=nb);ob=L.D.save(inv/'NATIVE_OUTCOME.json',outcome)
     closure={**outcome,'status':'NATIVE_COMPLETE_QUIET_LEASE_RELEASED','pre_release_outcome':ob}
     L.D.save(base/'OBSERVER_BASELINE.json',dict(manifest=mb,paths=[]));scanpath=report/'observer_fast_v2/attempts/one.json'
     scan=dict(schema='s6c.fast_resource_observer_exit.v1',status='RESTORED',policy=plan['observer_policy'],installations=[dict(common=common,restored=True,protected_admission_unchanged=True,original_callable='tree_bytes',scanner_callable='ScanMeter(tree_bytes)',scan_observations=counters)])
    closure['lease_release']=dict(status='RELEASED',released=True,error=None,source=source,requested_archive=str(archive),archived_binding=lb);closurepath=inv/'CLOSURE.json';L.D.save(closurepath,closure)
    scan.update(owner=owner,manifest=mb,wrapper=helper,entry='run',error=None);L.D.save(scanpath,scan)
    inspect=lambda o:dict(alive=False,error=None)
    proof=L.completion(item,plan,owner,qb,inspect);ck('positive_full_private_chain_'+family,proof['cells']==1 and proof['status']=='ORIGINAL_LONG_SESSION_COMPLETE_AND_OWNERS_CLOSED')
    for label,mutate in [('error',lambda d:d.update(error='failure')),('status',lambda d:d.update(status='FAILED')),('manifest',lambda d:d.update(manifest={'wrong':True})),('unreleased',lambda d:d['lease_release'].update(status='FAILED')),('archive_source',lambda d:d['lease_release']['source'].update(sha256='other'))]:
     wrong=copy.deepcopy(closure);mutate(wrong);closurepath.write_text(json.dumps(wrong));bad('reject_'+family+'_'+label,lambda:L.completion(item,plan,owner,qb,inspect));closurepath.write_text(json.dumps(closure))
    bad('reject_'+family+'_live_owner',lambda:L.completion(item,plan,owner,qb,lambda o:dict(alive=True,error=None)))
    bad('reject_'+family+'_unknown_owner',lambda:L.completion(item,plan,owner,qb,lambda o:dict(alive=None,error='denied')))
    bad('reject_'+family+'_quiet_mismatch',lambda:L.completion(item,plan,owner,{'different':True},inspect))
    wrong=copy.deepcopy(scan);wrong['error']='observer failure';scanpath.write_text(json.dumps(wrong));bad('reject_'+family+'_observer_failure',lambda:L.completion(item,plan,owner,qb,inspect));scanpath.write_text(json.dumps(scan))
    bad('reject_'+family+'_previous_invocation',lambda:L.unstarted(item,plan))
    quiet_value=L.quiet_payload(item,plan,L.D.DEADLINE,{'authority':True},{'queue':True},owner)
    ck('exact_'+family+'_quiet_status',quiet_value['status']==('AUTHORIZED_FOR_QUIET_LONG_B36' if is_b else 'AUTHORIZED_FOR_QUIET_LONG_NATIVE'))
    ck('exact_'+family+'_quiet_manifest',quiet_value.get('manifest')==mb if is_b else quiet_value.get('manifest_sha256')==mb['sha256'])
    if is_b:
     F=L.module('s6c_historical_fast_observer_v1.py');fake_process=types.SimpleNamespace(pid=100,create_time=lambda:20.,cmdline=lambda:argv)
     fake_api=types.SimpleNamespace(_original=types.SimpleNamespace(psutil=types.SimpleNamespace(Process=lambda:fake_process)),_fast_meter=types.SimpleNamespace(rows=counters),run=lambda args:dict(status='NATIVE_COMPLETE'))
     emitted=base/'original_execute_roundtrip';emitted.mkdir()
     with patch.object(F,'lineage',return_value=({'namespace':'fixture','output_root':str(base)},mb)),patch.object(F,'adapt',return_value=fake_api),patch.object(F,'roots',return_value=(emitted,base)),patch.object(F,'source_bindings',return_value=[helper]):
      F.execute('long_b36',types.SimpleNamespace(action='run',manifest=mb['path'],quiet_admission=qb['path']))
     paths=list((emitted/'observer_invocations').glob('*/SCANNER_OUTCOME.json'));actual,_=L.D.read(paths[0]);ck('actual_original_shared_execute_emits_NATIVE_COMPLETE',len(paths)==1 and actual['status']=='NATIVE_COMPLETE' and actual['sources_before']==[helper] and actual['storage_scans']==counters)
     original=scanpath.read_bytes();wrong=copy.deepcopy(scan);wrong['status']='COMPLETE';scanpath.write_text(json.dumps(wrong));bad('reject_paced_status_for_long_B36',lambda:L.completion(item,plan,owner,qb,inspect));scanpath.write_bytes(original)
     childpath=out/'CONTINUOUS_ADMISSION.json';raw=childpath.read_bytes();wrong,_=L.D.read(childpath);wrong['owner']['argv']=['wrong'];childpath.write_text(json.dumps(wrong));bad('reject_B36_child_admission_command',lambda:L.completion(item,plan,owner,qb,inspect));childpath.write_bytes(raw)
 prior=[L.D.binding(L.STAGING/'long_dispatch'/folder/name) for folder in ('before_fixture_variable_fix_v1','before_fixture_B36_field_fix_v2') for name in ('test_s6c_long_dispatch_v1.py','FAILURE_NOTE.txt')]
 prior.extend(L.D.binding(L.STAGING/'long_dispatch/before_preserved_filename_fix_v1'/n) for n in ('test_s6c_serial_long_dispatch_v1.py','FAILURE_NOTE.txt'))
 return L.D.save(output/'SOURCE_CHECKS.json',dict(status='PASS_SOURCE_PRIVATE_FIXTURES_AND_FIVE_PREPARED_METADATA',checks=len(checks),names=checks,sources=L.sources()+[L.D.binding(__file__)],preserved_fixture_corrections=prior,preserved_draft=L.D.binding(L.STAGING/'long_dispatch/before_original_long_schema_repair_v1/SOURCE_INDEX.json'),actual_manifests=[i['manifest'] for i in items],native_calls=0,actual_queue_preparation=0,scope='No native models, PCM, events, actual session outputs, authority creation or launch; private synthetic closures only.'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
