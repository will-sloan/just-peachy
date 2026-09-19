"""Tiny exact metadata/observer tests; README_S6C_EXECUTION_INVENTORY_V7.md."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import argparse,hashlib,json,tempfile,types
import s6c_execution_inventory_v7 as A

def fixture(root,kind='cross',change=None):
 api=A.paced_api(kind);v=A.FAST[kind]
 x=types.SimpleNamespace(**{**vars(A.v4),**vars(api),'CANONICAL':v['schema'],'GUARDS':A.v6.X.GUARDS if kind=='cross' else A.v4.GUARDS if kind=='canonical' else A.v5.S.GUARDS})
 test=types.SimpleNamespace(**{**vars(A.v6),'X':x,'KIND':v['kind'],'REPLACEMENTS':{'s6c-canonical-paced-cell-result.v1':v['cell']}})
 testns=dict(A=test,Path=Path,deepcopy=deepcopy,read=lambda p:json.loads(p.read_bytes()),replace=lambda p,v:replace(p,v))
 A.v5.compile_functions(A.HERE/'test_s6c_execution_inventory_v6.py',{'fixture'},testns)
 original=A.base.write_new
 def save(p,value):
  if Path(p).name=='LAUNCH.json' and Path(p).parent.name=='one':
   value['owner']['argv']=[str(A.F.EDGE),str(A.HERE/v['wrapper']),'run','--manifest',value['manifest']['path'],'--quiet-admission',str(root/'QUIET.json')]
   value['quiet_admission']=dict(path=str(root/'QUIET.json'),bytes=2,sha256='0'*64)
  return original(p,value)
 with patch.object(A.base,'write_new',save):r,j,p,pb,s,db=testns['fixture'](root,change)
 p['observer_policy']=A.source_policy()
 s['execution_files']=[dict(path='frozen/s6c_common.py',bytes=3,sha256='5'*64)]
 def meter():return {str(x):dict(calls=1,successful=1,failed=0,total_wall_sec=.1,total_cpu_sec=.1,max_wall_sec=.1,last_bytes=0,last_error=None) for x in (A.REPORT,A.base.STAGING,A.PAYLOAD)}
 cell=json.loads((Path(j['report_root'])/'CELL_RESULT.json').read_bytes());co=json.loads((root/'invocations/one/LAUNCH.json').read_bytes())['owner']
 docs=[]
 for entry,o,jid in (('worker',cell['owner'],j['job_id']),('run',co,None)):
  docs.append((dict(schema='s6c.fast_resource_observer_exit.v1',status='RESTORED',error=None,entry=entry,job_id=jid,owner=deepcopy(o),manifest=pb,wrapper=A.F.bind(A.HERE/v['wrapper']),policy=p['observer_policy'],installations=[dict(common=s['execution_files'][0],restored=True,protected_admission_unchanged=True,original_callable='tree_bytes',scanner_callable='ScanMeter(tree_bytes)',scan_observations=meter())]),dict(path=str(A.REPORT/'observer_fast_v1/attempts'/('fixture_'+entry+'.json')),bytes=1,sha256='9'*64)))
 r.fast_observer_receipts=docs
 return r,j,p,pb,s,db

def replace(p,value):
 p.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');return A.base.binding(p,p.read_bytes())

def checks():
 done=[]
 def good(name,value=True):assert value,name;done.append(name)
 def reject(name,fn):
  try:fn()
  except (ValueError,KeyError,TypeError,OSError):good(name)
  else:raise AssertionError('Admitted invalid '+name)
 A.verify_sources();good('all_current_held_sources_and_readmes')
 for kind in ('canonical','sentinel','cross'):
  for change in (None,'missing_observer','wrong_policy','not_restored','wrong_common','wrong_owner','wrong_wrapper','wrong_manifest','wrong_job','duplicate_receipt','missing_scans','scan_nan','missing_outcome','wrong_quiet_argv'):
   with tempfile.TemporaryDirectory(prefix='s6c_v7_metadata_') as tmp,patch.object(A.v3,'process_state',lambda *a:dict(alive=False,state='SYNTHETIC_CLOSED')):
    r,j,p,pb,s,db=fixture(Path(tmp),kind);original=A.bound
    def bound(reader,b):return (s,b) if b=={} else original(reader,b)
    docs=r.fast_observer_receipts
    if change=='missing_observer':del r.fast_observer_receipts
    elif change=='wrong_policy':docs[0][0]['policy']={}
    elif change=='not_restored':docs[0][0]['installations'][0]['restored']=False
    elif change=='wrong_common':docs[0][0]['installations'][0]['common']={}
    elif change=='wrong_owner':docs[0][0]['owner']['creation_time']=float('nan')
    elif change=='wrong_wrapper':docs[0][0]['wrapper']={}
    elif change=='wrong_manifest':docs[0][0]['manifest']={}
    elif change=='wrong_job':docs[0][0]['job_id']='wrong'
    elif change=='duplicate_receipt':docs.append(deepcopy(docs[0]))
    elif change=='missing_scans':docs[0][0]['installations'][0]['scan_observations']={}
    elif change=='scan_nan':next(iter(docs[0][0]['installations'][0]['scan_observations'].values()))['total_wall_sec']=float('nan')
    elif change=='missing_outcome':(Path(tmp)/'invocations/one/OUTCOME.json').unlink();(Path(tmp)/'invocations/one/CLOSURE.json').unlink()
    elif change=='wrong_quiet_argv':docs[1][0]['owner']['argv'][-1]=str(Path(tmp)/'other.json')
    with patch.object(A,'bound',bound):
     call=lambda:A.admit_complete_cell(r,j,p,pb,s,state=lambda *a:dict(alive=False))
     if change:reject(kind+'_'+change,call)
     else:
      value=call();good(kind+'_complete_exact_native_artifact_chain',value['complete_binding']==db and value['native_binding'] in value['artifacts'])
      row=A.collect_job(r,j,p,pb,s);good(kind+'_one_complete_attempt',row['status']=='COMPLETE' and row['native_session_complete'])
     if change in ('missing_observer','not_restored','missing_outcome'):
      row=A.collect_job(r,j,p,pb,s);good(kind+'_retain_native_completion_'+change,row['status']=='NATIVE_COMPLETE_OBSERVER_UNVERIFIED' and row['native_session_complete'])
 # Same physical attempt is never counted again from an index/reference.
 row=dict(physical_id='a',session_dir='G:/synthetic/session',status='FAILED',pid=123,creation_time=1.,job_key='j',worker_model_bundle_loads=1)
 merged,dup=A.merge_physical([row],[deepcopy(row)]);good('exact_duplicate_reference_not_new_attempt',merged==[row] and dup==['a'])
 reject('conflicting_attempt_not_silently_replaced',lambda:A.merge_physical([row],[dict(row,status='COMPLETE')]))
 reject('same_session_different_attempt',lambda:A.merge_physical([row],[dict(row,physical_id='b')]))
 row2=dict(row,physical_id='b',session_dir=None,status='UNVERIFIED_SPAWN_IDENTITY',creation_time=None,worker_model_bundle_loads=None)
 good('unknown_spawn_preserved',A.merge_physical([row],[row2])[0]==[row,row2])
 summary=A.base.summarize([row,dict(row,physical_id='c',session_dir='G:/other',worker_model_bundle_loads=2),row2]);good('per_worker_max_not_cumulative_sum',summary['cumulative_worker_bundle_loads_observed']==2 and summary['attempts_without_session_path']==1)
 for protection in (True,False):
  with tempfile.TemporaryDirectory(prefix='s6c_v7_failed_native_') as tmp,patch.object(A.v3,'process_state',lambda *a:dict(alive=False,state='SYNTHETIC_CLOSED')):
   api=A.paced_api('canonical');proxy=types.SimpleNamespace(**{**vars(A.v4),**vars(api)})
   ns=dict(A=proxy,Path=Path,deepcopy=deepcopy);A.v5.compile_functions(A.HERE/'test_s6c_execution_inventory_v4.py',{'fake','fixture'},ns)
   r,j,p,pb,s,_=ns['fixture'](Path(tmp),'failed_after_native');p['observer_policy']=A.source_policy();out=Path(j['report_root'])/'CELL_OUTCOME.json';value=json.loads(out.read_bytes());value['protected_functions_restored']=protection;replace(out,value)
   row=A.collect_job(r,j,p,pb,s);good('failed_outer_retains_complete_native_'+str(protection),row['native_session_complete'] is True and row['status']==('FAILED_OUTER_NATIVE_COMPLETE' if protection else 'FAILED_OUTER_NATIVE_COMPLETE_PROTECTION_UNVERIFIED'))
   reject('failed_outer_never_closed_cell_'+str(protection),lambda:A.admit_complete_cell(r,j,p,pb,s,state=lambda *a:dict(alive=False)))
 reject('closed_api_requires_invocation',lambda:A.ensure_invocations_closed([],[]))
 reject('closed_api_unknown_owner',lambda:A.ensure_invocations_closed([dict(outcome={},closure={})],[dict(process_state=dict(alive=None))]))
 prior=[dict(pid=123,creation_time=1.,process_state=dict(alive=True)),dict(pid=None,creation_time=None,process_state=dict(alive=None))]
 owners=A.refreshed_prior_owners(prior,lambda *a:dict(alive=False));good('earlier_live_not_current_live',owners[0]['process_state']['alive'] is False and prior[0]['process_state']['alive'] is True);good('prior_missing_lineage_remains_unknown',owners[1]['process_state']['alive'] is None)
 # No native STARTED means no physical attempt, even when an outer admission exists.
 with tempfile.TemporaryDirectory(prefix='s6c_v7_outer_') as tmp:
  good('continuous_outer_admission_not_native_attempt',A.collect_long_c(None,dict(report_root=tmp),{},[dict(admission={})])==[])
 # Isolated historical-long chain, compiled from the previously reviewed tiny fixture.
 for change in (None,'failed_outcome_with_complete_result','native_admission_wrong_lease','coordinator_omits_native_owner','named_complete_with_retained_lease'):
  with tempfile.TemporaryDirectory(prefix='s6c_v7_long_') as tmp,patch.object(A.v3,'process_state',lambda *a:dict(alive=False,state='SYNTHETIC_CLOSED')):
   root=Path(tmp);dummy=A.base.MetadataReader(root);api,g=A.long_b36_api(dummy)
   proxy=types.SimpleNamespace(**{**vars(A.v5),**vars(api),'LONG':A.FAST['long_b36']['schema'],'LONG_RESULT':'s6c-exact-historical-b36-continuous-fast-result.v1'})
   ns=dict(A=proxy,Path=Path,deepcopy=deepcopy);A.v5.compile_functions(A.HERE/'test_s6c_execution_inventory_v5.py',{'fake','long_fixture'},ns,{'S6C_EXACT_HISTORICAL_B36_CONTINUOUS':'S6C_EXACT_HISTORICAL_B36_CONTINUOUS_FAST'})
   r,j,p,pb,g=ns['long_fixture'](root,change)
   if change:reject('historical_long_'+change,lambda:(api.admit_long_native(r,p,pb,{},g),api.long_invocations(r,p,pb)))
   else:
    row=api.admit_long_native(r,p,pb,{},g);good('historical_long_exact_old_native_chain',row['status']=='COMPLETE' and row['native_session_complete'])
    reject('historical_long_cannot_bypass_observer_context',lambda:A.admit_long_native(r,p,pb,{},g))
 # Strict finalization/journal metadata applies to the separate continuous schema too.
 with tempfile.TemporaryDirectory(prefix='s6c_v7_long_final_') as tmp:
  r,j,p,pb,s,_=fixture(Path(tmp));cell=json.loads((Path(j['report_root'])/'CELL_RESULT.json').read_bytes());native,_=A.bound(r,cell['native_result']);source,_=A.bound(r,j['source'])
  plan=dict(profile_row=dict(asr_tap=j['asr_tap'],identity_tap=j['identity_tap']),duration_sec=source['duration_sec'],duration_samples=source['duration_samples'],pcm_sha256=source['pcm_sha256'])
  A.long_native_identity(r,native,plan,native['owner']);good('continuous_exact_paired_journal_finalization')
  bad=deepcopy(native);bad['final_telemetry']['asr_cursor_sec']=0;reject('continuous_missing_tail',lambda:A.long_native_identity(r,bad,plan,bad['owner']))
  bad=deepcopy(native);bad['native_journals']['identity_audio_spool.pcm16']['sha256']='2'*64;reject('continuous_wrong_identity_journal',lambda:A.long_native_identity(r,bad,plan,bad['owner']))
 return dict(status='PASS_MODEL_FREE',checks=len(done),names=done,models=0,payload_reads=0,full_inventory_runs=0)

def actual_metadata(output):
 reader=A.base.MetadataReader(output);rows=[]
 # Explicit finite prepared authorities; filenames carry no execution claim.
 names=[*(A.REPORT/'paced_candidates'/('c'+x+'_main_fast_v1')/'MANIFEST.json' for x in ('065','067','076','079','088','091','117','118','121','122')),
  A.REPORT/'paced_candidates/uncertainty_gate6_fast_v1/MANIFEST.json',A.REPORT/'paced_arrival_sentinel/arrival_boundary_fast_v1/MANIFEST.json',A.REPORT/'paced_cross_routes/cross_panel_fast_v1/MANIFEST.json',A.PAYLOAD/'paced_controls/controls_fast_v1/MANIFEST.json',A.PAYLOAD/'paced_controls/b36_fast_v1/MANIFEST.json',A.REPORT/'long_b36/b36_o0_continuous_fast_v1/MANIFEST.json',*(A.REPORT/'long_native_epoch4'/('epoch4_long_c'+x+'_o0_fast_v1')/'MANIFEST.json' for x in ('065','088','091'))]
 for path in names:
  _,b=reader.read(path);v=A.admit_plan(reader,b);plan=v[0];rows.append(dict(manifest=b,kind=A.kind_of(plan),requested=len(plan['jobs']) if 'jobs' in plan else 1,profile_or_candidates=plan.get('candidates',plan.get('profiles',plan.get('profile_row',{}).get('candidate_id'))),status='ACTUAL_PREPARED_METADATA_ADMITTED_NOT_EXECUTION_REVIEW'))
 return rows,reader.sources

def actual_failed_cell(output):
 reader=A.base.MetadataReader(output);path=A.REPORT/'paced_candidates/c065_main_fast_v1/MANIFEST.json';_,b=reader.read(path)
 assert b['sha256']=='f6e3f08de020b6d15cbdce0337cbcd2e6f7a29463ceb9f3fd54dd5450cf9bc2a'
 plan,pb,spec=A.admit_plan(reader,b);jobs=[j for j in plan['jobs'] if j['job_id']=='C065_S45_01_16_O0_O0_r1'];assert len(jobs)==1
 row=A.collect_job(reader,jobs[0],plan,pb,spec)
 assert row['status']=='FAILED_OUTER_NATIVE_COMPLETE_PROTECTION_UNVERIFIED' and row['native_session_complete'] is True and row['protected_functions_restored'] is False and row['closed_cell_analysis_eligible'] is False
 assert row['worker_model_bundle_loads']==1 and row['audio_duration_sec']==44.6954375 and row['process_state']['alive'] is False
 try:A.admit_complete_cell(reader,jobs[0],plan,pb,spec)
 except (ValueError,KeyError,TypeError,OSError):pass
 else:raise AssertionError('Actual failed outer cell admitted as successful')
 proof,pb2=reader.read(A.REPORT/'runtime_failure_review/FIRST_C065_FAILURE_CLOSURE_V2.json');assert pb2['sha256']=='3c90af6cfea91d8b4b1676d6ecbecc70885abfd0e7cc1c5bd62e59d068a44a1d'
 return dict(status='ONE_FAILED_PHYSICAL_ATTEMPT_ONE_NATIVE_COMPLETE_ZERO_ACCEPTED_CELLS',physical=row,root_owned_closure_proof=pb2,scope='One explicitly requested closed failure only. Native metadata/journal declarations/finalization inspected; no event/PCM/model/trajectory bytes or whole inventory. Root closure census is carried, not independently repeated.'),reader.sources

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',type=Path,required=True);p.add_argument('--actual-prepared-metadata',action='store_true');p.add_argument('--actual-failed-cell',action='store_true');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
 before=A.source_bindings()+[A.F.bind(__file__),*[A.F.bind(A.HERE/n) for n in ('test_s6c_execution_inventory_v4.py','test_s6c_execution_inventory_v5.py','test_s6c_execution_inventory_v6.py')]]
 result=checks();rows,sources=actual_metadata(args.output) if args.actual_prepared_metadata else ([],[])
 failed,failed_sources=actual_failed_cell(args.output) if args.actual_failed_cell else (None,[])
 after=A.source_bindings()+[A.F.bind(__file__),*[A.F.bind(A.HERE/n) for n in ('test_s6c_execution_inventory_v4.py','test_s6c_execution_inventory_v5.py','test_s6c_execution_inventory_v6.py')]]
 assert before==after,'Sources changed during checks'
 result.update(sources_unchanged=True,actual_prepared=rows,actual_failed_cell=failed,metadata_sources=sources+failed_sources,source_bindings=before,scope='Bounded metadata and synthetic guards; optional exact one-cell failed-native accounting is separately labeled. No whole inventory, PCM/model/event/trajectory read or storage walk.')
 print(json.dumps(A.base.write_new(args.output/'SOURCE_CHECKS.json',result),indent=2))
if __name__=='__main__':main()
