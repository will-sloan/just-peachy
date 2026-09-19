"""Tiny B36 inventory facade guards; README_S6C_B36_V2_INVENTORY_V1.md."""
import argparse,copy,json,types
from pathlib import Path
from unittest.mock import patch
import s6c_b36_v2_inventory_v1 as R

def run(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);api=R.make_inventory();v=R.load('s6c_execution_inventory_v7',R.V7_SHA);B=api.b36_wrapper;checks=[]
 def ok(n,x):assert x,n;checks.append(n)
 def bad(n,f):
  try:f()
  except (ValueError,KeyError,TypeError):checks.append(n);return
  raise AssertionError(n)
 p=B.PAYLOAD/'paced_controls/b36_fast_v2/MANIFEST.json';pb=B.F.bind(p);assert pb['sha256']=='a19d8b5bebdc425256f8f546072b018ff5c65665a23ffab3064e75fafe7294b1'
 reader=v.base.MetadataReader(out);plan,pb,spec=api.admit_plan(reader,pb)
 ok('actual_prepared40_metadata_admitted',len(plan['jobs'])==40 and all(j['profile_id']=='B36' for j in plan['jobs']))
 ok('new_schema_explicit',plan['schema']==R.SCHEMA and api.kind_of(plan)=='b36' and R.SCHEMA in api.HISTORICAL and R.SCHEMA not in v.HISTORICAL)
 ok('held_collect_code_identical',api.collect.__code__ is v.collect.__code__)
 ok('original_native_collector_still_original',v.v4.collect_job.__module__=='s6c_execution_inventory_v4')
 ok('unrelated_apis_identical',api.admit_complete_cell is v.admit_complete_cell and api.admit_observer_index is v.admit_observer_index)
 ok('original_V7_global_bindings_preserved',v.collect.__globals__['kind_of'] is v.kind_of and api.kind_of is not v.kind_of)
 b=lambda name:dict(path=str(out/name),bytes=1,sha256=name)
 lb,cb,sb,ab,rb=[b(n) for n in ('LAUNCH.json','COMPLETION.json','SCANNER_OUTCOME.json','ARCHIVED.json','LEASE_RELEASE.json')]
 record=dict(launch=lb,outcome=cb,closure=None,status='COMPLETE',reported_completed=40)
 parent=dict(branch='parent',pid=1,creation_time=1.,process_state=dict(alive=False),source=lb)
 proof=dict(status='B36_NATIVE_BATCH_COMPLETE_WITH_EXPLICIT_C_ARCHIVE',manifest=pb,cells=40,launch=lb,completion=cb,lease_release=rb,archived_lease=ab,observer_exit=sb,completed_cells=[dict(job_id=j['job_id'],completion=b(j['job_id'])) for j in plan['jobs']],current_child_observations=[dict(owner=dict(pid=2,creation_time=2.),observation=dict(alive=False,error=None))])
 fake=types.SimpleNamespace(fast_observer_receipts=[({},sb)])
 job=plan['jobs'][0];row=dict(status='COMPLETE',native_session_complete=True,physical_id='original_attempt',recorded_owned_processes=[dict(pid=2,creation_time=2.)],receipt_bindings=[proof['completed_cells'][0]['completion']])
 with patch.object(v.v4,'invocation_rows',side_effect=lambda *a:([copy.deepcopy(record)],[copy.deepcopy(parent)])),patch.object(v.v4,'collect_job',side_effect=lambda *a:copy.deepcopy(row)),patch.object(B,'admit_complete_batch',return_value=proof),patch.object(v,'process_state',return_value=dict(alive=False)):
  records,owners=api.invocation_rows(fake,plan,pb);ok('new_C_closure_separate_from_G',records[0]['closure']==rb and records[0]['archived_lease']==ab and records[0]['original_G_archive_created'] is False)
  actual=api.collect_job(fake,job,plan,pb,spec);ok('physical_identity_and_native_completion_preserved',actual['status']=='COMPLETE' and actual['physical_id']==row['physical_id'] and actual['native_session_complete'] is True)
  fake.fast_observer_receipts=[];actual=api.collect_job(fake,job,plan,pb,spec);ok('missing_index_preserves_native_unverified',actual['status']=='NATIVE_COMPLETE_OBSERVER_UNVERIFIED' and actual['physical_id']==row['physical_id'] and actual['native_session_complete'] is True)
  fake.fast_observer_receipts=[({},sb),({},sb)];ok('duplicate_observer_rejected',api.collect_job(fake,job,plan,pb,spec)['status']=='NATIVE_COMPLETE_OBSERVER_UNVERIFIED')
  fake.fast_observer_receipts=[({},sb)]
  with patch.object(B,'admit_complete_batch',side_effect=ValueError('failed release')):ok('failed_release_never_upgrades_native',api.collect_job(fake,job,plan,pb,spec)['status']=='NATIVE_COMPLETE_OBSERVER_UNVERIFIED')
  with patch.object(v,'process_state',return_value=dict(alive=None)):ok('unknown_native_owner_not_closed',api.collect_job(fake,job,plan,pb,spec)['status']=='NATIVE_COMPLETE_OBSERVER_UNVERIFIED')
  row['status']='PARTIAL_CLOSED_WITHOUT_FINAL_RESULT';row['native_session_complete']=False;ok('partial_native_preserved',api.collect_job(fake,job,plan,pb,spec)['status']==row['status'])
  with patch.object(v.v4,'collect_job',return_value=None):ok('not_launched_not_counted',api.collect_job(fake,job,plan,pb,spec) is None)
  bad('undeclared_job_rejected',lambda:api.collect_job(fake,{},plan,pb,spec))
  with patch.object(v,'collect_job',return_value={'other':'unchanged'}) as call:ok('unrelated_branch_delegated',api.collect_job(fake,{}, {},{}, {})=={'other':'unchanged'} and call.call_count==1)
 ok('old_modules_restored_after_fixtures',v.v4.collect_job.__module__=='s6c_execution_inventory_v4')
 return v.base.write_new(out/'SOURCE_CHECKS.json',dict(status='PASS_SOURCE_PREPARED_METADATA_AND_TINY_GUARDS',checks=len(checks),names=checks,sources=api.source_bindings()+[B.F.bind(__file__)],prepared_manifest=pb,actual_prepare=False,actual_batch_admission=False,actual_inventory=False,native_calls=0,scope='Exact newly prepared40 metadata only. Actual release/observer/native rows were synthetic; no runtime payload, PCM/models or global enumeration.'))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
