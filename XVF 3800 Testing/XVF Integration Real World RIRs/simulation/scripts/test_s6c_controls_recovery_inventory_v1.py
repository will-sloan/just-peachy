"""Focused synthetic checks; README_S6C_CONTROLS_RECOVERY_INVENTORY_V1.md."""
import argparse,copy,json,types
from pathlib import Path
from unittest.mock import patch
import s6c_controls_recovery_inventory_v1 as R

def fixture():
 b=lambda p,sha='x',n=1:dict(path=str(p),bytes=n,sha256=sha)
 root=R.REPORT/'runtime_failure_review/external_lease_recovery/fixture';rb=b(root/'RESULT.json');ab=b(root/'ADMISSION.json');authb=b(root/'AUTHORITY.json');ap=b(R.AUDIT,R.AUDIT_SHA)
 mb=b(Path('G:/Just_Peachy_S6C/20260910T123540Z/paced_controls/controls_fast_v1/MANIFEST.json').resolve(),R.MANIFEST_SHA)
 original=Path(mb['path']).parent/'invocations/original';lb=b(original/'LAUNCH.json');cb=b(original/'COMPLETION.json');db=b(root/'DISPATCH_FAILURE.json');sb=b(root/'SCANNER_OUTCOME.json',R.SCANNER_SHA)
 leaseb=b(R.REPORT/'PACED_QUIET_OWNER.json',R.LEASE_SHA,258);archive=b(root/'PRESERVED_ORIGINAL_QUIET_LEASE.json',R.LEASE_SHA,258)
 owners=[dict(pid=i+1,creation_time=float(i+1)) for i in range(162)];observed=[dict(owner=o,observation=dict(alive=False,error=None)) for o in owners];recovery=dict(pid=999,creation_time=999.)
 audit=dict(manifest=mb,launch=lb,completion=cb,failed_dispatcher=db,original_owner=owners[0],rows=[dict(job_id=str(i),owners=observed[2+i*2:4+i*2]) for i in range(80)],expected_archive=str(original/'QUIET_OWNER_CLOSED.json'),preserved_active_lease=leaseb)
 auth=dict(schema='s6c-external-historical-lease-release-authority.v1',status='AUTHORIZED_EXACT_EXTERNAL_LEASE_ARCHIVE',namespace='fixture',root_audit=ap,helper=b(R.HERE/'s6c_external_lease_recovery_v1.py',R.RECOVERY_SHA),readme=b(R.HERE/'README_S6C_EXTERNAL_LEASE_RECOVERY_V1.md',R.RECOVERY_README_SHA),expires_utc='2026-09-13T11:35:40+00:00')
 adm=dict(schema='s6c-external-lease-recovery-admission.v1',status='EXACT_OWNER_BOUND_RECOVERY_ADMITTED',owner=recovery,authority=authb,root_audit=ap,source=auth['helper'],readme=auth['readme'],release_source=b(R.HERE/'s6c_long_native_epoch4_fast_v2.py',R.RELEASE_SHA),failed_observer=sb,original_missing_archive=audit['expected_archive'],created_utc='2026-09-12T06:00:00+00:00',lease=leaseb,requested_archive=archive['path'],original_owners=observed)
 result=dict(schema='s6c-external-historical-lease-recovery.v1',status='EXTERNAL_ARCHIVE_RELEASED',owner=recovery,admission=ab,authority=authb,root_audit=ap,manifest=mb,original_launch=lb,original_completion=cb,original_dispatcher_failure=db,failed_observer=sb,original_coordinator_exit_code=1,original_scanner_status='FAILED',original_missing_archive=audit['expected_archive'],original_archive_created=False,models_started=0,native_sessions_started=0,created_utc='2026-09-12T06:00:01+00:00',lease_release=dict(status='RELEASED',released=True,error=None,source=leaseb,archived_binding=archive,requested_archive=archive['path']),current_original_owner_observations=observed)
 return [result,rb,adm,ab,auth,audit,ap,dict(**owners[0],manifest=mb),dict(owner=owners[1])]

def run(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);v=R.load_v7();checks=[]
 def ok(n,value=True):
  assert value,n;checks.append(n)
 def bad(n,f):
  try:f()
  except (ValueError,KeyError,TypeError):checks.append(n);return
  raise AssertionError(n)
 values=fixture();ok('exact_synthetic_recovery_chain',len(R.validate_result_documents(v,*values))==162)
 faults=[('wrong_result_status',lambda x:x[0].update(status='COMPLETE')),('wrong_manifest',lambda x:x[0]['manifest'].update(sha256='wrong')),('wrong_audit',lambda x:x[6].update(sha256='wrong')),('original_exit_rewritten',lambda x:x[0].update(original_coordinator_exit_code=0)),('observer_success_fabricated',lambda x:x[0].update(original_scanner_status='COMPLETE')),('g_archive_fabricated',lambda x:x[0].update(original_archive_created=True)),('missing_owner',lambda x:x[0]['current_original_owner_observations'].pop()),('live_owner',lambda x:x[0]['current_original_owner_observations'][0]['observation'].update(alive=True)),('unknown_owner',lambda x:x[0]['current_original_owner_observations'][0]['observation'].update(alive=None)),('renamed_but_unverified',lambda x:x[0]['lease_release'].update(status='RELEASED_BINDING_UNVERIFIED')),('release_error',lambda x:x[0]['lease_release'].update(error='denied')),('not_released',lambda x:x[0]['lease_release'].update(released=False)),('archive_bytes_changed',lambda x:x[0]['lease_release']['archived_binding'].update(bytes=259)),('archive_outside_recovery',lambda x:x[0]['lease_release']['archived_binding'].update(path=str(R.REPORT/'elsewhere.json'))),('wrong_recovery_source',lambda x:x[2]['source'].update(sha256='changed')),('wrong_release_source',lambda x:x[2]['release_source'].update(sha256='changed')),('invalid_owner_creation',lambda x:x[0]['owner'].update(creation_time=True)),('expired_admission',lambda x:x[4].update(expires_utc='2026-09-12T05:00:00+00:00')),('housekeeping_not_native',lambda x:x[0].update(native_sessions_started=1))]
 for name,mutate in faults:
  x=copy.deepcopy(values);mutate(x);bad(name,lambda x=x:R.validate_result_documents(v,*x))
 api=R.make_inventory(values[1]);ok('original_collect_code_object',api.collect.__code__ is v.collect.__code__)
 ok('original_v7_globals_unchanged',v.collect.__globals__['invocation_rows'] is v.invocation_rows and v.admit_observer_index is not api.admit_observer_index)
 ok('unrelated_apis_unchanged',api.admit_plan is v.admit_plan and api.admit_complete_cell is v.admit_complete_cell)
 result,rb,adm,ab,auth,audit,*_=values
 job=dict(job_id='j',job_key='key');plan=dict(jobs=[job]);audit=copy.deepcopy(audit);audit['rows']=[dict(job_id='j',completion=audit['completion'])]
 owners=[dict(pid=i+1,creation_time=float(i+1),process_state=dict(alive=False)) for i in range(163)]
 c=dict(binding=rb,manifest=audit['manifest'],plan=plan,audit=audit,result=result,owners=owners,rows={'j':audit['rows'][0]})
 reader=types.SimpleNamespace(controls_recovery_context=c)
 record=dict(launch=audit['launch'],outcome=audit['completion'],closure=None,status='COMPLETE',reported_completed=80)
 native=dict(status='COMPLETE',native_session_complete=True,recorded_owned_processes=[dict(pid=3,creation_time=3.)],receipt_bindings=[audit['completion']],physical_id='existing_native')
 fake=types.SimpleNamespace(invocation_rows=lambda *a:([copy.deepcopy(record)],[]),collect_job=lambda *a:copy.deepcopy(native))
 with patch.object(v,'historical_api',return_value=fake),patch.object(v,'process_state',return_value=dict(alive=False)),patch.object(Path,'exists',return_value=False):
  records,current=api.invocation_rows(reader,plan,audit['manifest']);ok('producer_complete_failure_history_preserved',records[0]['status']=='COMPLETE' and records[0]['original_coordinator_exit_code']==1 and records[0]['original_scanner_status']=='FAILED' and records[0]['observer_error']==R.ERROR and records[0]['original_closure'] is None)
  row=api.collect_job(reader,job,plan,audit['manifest'],{});ok('same_native_physical_identity_no_new_attempt',row['physical_id']=='existing_native' and row['native_session_complete'] is True and row['observer_admission']['external_recovery']==rb)
  fake.invocation_rows=lambda *a:([copy.deepcopy(record),copy.deepcopy(record)],[]);bad('extra_invocation_rejected',lambda:api.invocation_rows(reader,plan,audit['manifest']))
  fake.invocation_rows=lambda *a:([copy.deepcopy(record)],[])
  with patch.object(v,'process_state',return_value=dict(alive=None)):bad('unknown_current_parent_rejected',lambda:api.invocation_rows(reader,plan,audit['manifest']))
  bad('missing_explicit_context_rejected',lambda:api.invocation_rows(types.SimpleNamespace(),plan,audit['manifest']))
  native['status']='FAILED';bad('failed_native_never_upgraded',lambda:api.collect_job(reader,job,plan,audit['manifest'],{}))
  native['status']='COMPLETE'
  with patch.object(Path,'exists',return_value=True):bad('active_lease_rejected',lambda:api.invocation_rows(reader,plan,audit['manifest']))
  with patch.object(v,'collect_job',return_value={'unchanged':'other'}) as delegated:ok('unrelated_native_branch_delegated',api.collect_job(reader,{}, {},{'sha256':'other'}, {})=={'unchanged':'other'} and delegated.call_count==1)
 sources=[R.binding(R.__file__),R.binding(__file__),R.binding(R.HERE/'README_S6C_CONTROLS_RECOVERY_INVENTORY_V1.md')]
 receipt=dict(schema='s6c-controls-recovery-inventory-checks.v1',status='PASS_SYNTHETIC_METADATA_ONLY',checks=len(checks),names=checks,sources=sources,actual_admission=False,actual_inventory=False,models=0,scope='Synthetic exact-document and private-namespace faults; no real lease,80cell metadata, native payload or process-state query.')
 return v.base.write_new(out/'SOURCE_CHECKS.json',receipt)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
