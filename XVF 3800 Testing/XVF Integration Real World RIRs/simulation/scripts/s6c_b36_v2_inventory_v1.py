"""Explicit new B36 metadata branch; README_S6C_B36_V2_INVENTORY_V1.md."""
from __future__ import annotations
import hashlib,importlib,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
V7_SHA='fc23ff6650a34c927211d142e61b9dcf7afe7ee07e832c51573ae2da0dc3c7a3'
WRAPPER_SHA='130255266206ddb95c917ad5825328782dbeedafa9656814024c1ed1d32e0892'
README_SHA='832bfb49c276c0e3a9ae03413b050098a4584a6964bec1e7525eb2cb42a1cef6'
SCHEMA='s6c-historical-paced-b36-fast.v2'

def require(v,m):
 if not v:raise ValueError(m)

def load(name,sha):
 p=HERE/(name+'.py');raw=p.read_bytes();require(len(raw)<=2**20 and hashlib.sha256(raw).hexdigest()==sha,'Exact held source: '+name)
 m=importlib.import_module(name);require(Path(m.__file__).resolve()==p,'Import origin');return m

def make_inventory(base_inventory=None):
 """Delegates other branches; optional existing recovered-controls namespace."""
 v=load('s6c_execution_inventory_v7',V7_SHA);v.verify_sources();B=load('s6c_paced_b36_fast_v2',WRAPPER_SHA)
 require(B.F.bind(HERE/'README_S6C_PACED_B36_FAST_V2.md')['sha256']==README_SHA,'Held wrapper README')
 base=base_inventory or v;api=types.SimpleNamespace(**vars(base))
 def target(plan):return plan.get('schema')==SCHEMA
 def kind_of(plan):return 'b36' if target(plan) else base.kind_of(plan)
 def sources():
  rows=base.source_bindings()+B.context().source_bindings('b36')+[B.F.bind(__file__),B.F.bind(HERE/'README_S6C_B36_V2_INVENTORY_V1.md')]
  return list({b['path']:b for b in rows}.values())
 def admit_plan(reader,b):
  plan,_=v.bound(reader,b)
  if not target(plan):return base.admit_plan(reader,b)
  plan,pb=B.admit_plan(reader,b);old,ob,spec=v.admit_plan(reader,plan['previous_fast_preparation'])
  require(plan['jobs']==old['jobs'] and len(plan['jobs'])==40 and all(j['profile_id']=='B36' for j in plan['jobs']),'Exact original40 native jobs')
  require(plan['driver']==old['driver'] and plan['historical_epoch']==old['historical_epoch'],'Original S6B native driver/epoch')
  return plan,pb,spec
 def invocation_rows(reader,plan,pb,*,observer_receipts=None):
  if not target(plan):return base.invocation_rows(reader,plan,pb,observer_receipts=observer_receipts)
  if observer_receipts is not None:v.attach_observer_receipts(reader,observer_receipts)
  # Unchanged old historical discovery still preserves partial/failed launches.
  records,owners=v.v4.invocation_rows(reader,plan,pb)
  try:
   proof=B.admit_complete_batch(reader,pb)
   indexed=v.receipts_context(reader);require(sum(b==proof['observer_exit'] for _,b in indexed)==1,'Exact B36 observer exit must belong to explicit attached index')
   require(len(records)==1 and records[0]['launch']==proof['launch'] and records[0]['outcome']==proof['completion'] and records[0]['closure'] is None,'Exact original G invocation with new C closure')
   records[0].update(closure=proof['lease_release'],closure_kind='B36_V2_COORDINATOR_SAME_VOLUME_ARCHIVE',archived_lease=proof['archived_lease'],observer_exit=proof['observer_exit'],original_G_archive_created=False,b36_v2_proof=proof)
   for row in proof['current_child_observations']:
    o=row['owner'];owners.append(dict(branch='B36_V2_NATIVE_CHILD',pid=o['pid'],creation_time=o['creation_time'],process_state=dict(alive=row['observation']['alive'],state='EXACT_CURRENT_OWNER'),source=proof['lease_release']))
  except v.ERRORS as exc:
   for row in records:row['b36_v2_closure_error']=repr(exc)
   owners.append(dict(branch='B36_V2_CLOSURE_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='EXPLICIT_C_ARCHIVE_OR_OBSERVER_UNVERIFIED'),error=repr(exc)))
  return records,owners
 def collect_job(reader,job,plan,pb,spec,*,observer_receipts=None):
  if not target(plan):return base.collect_job(reader,job,plan,pb,spec,observer_receipts=observer_receipts)
  require(job in plan['jobs'],'Actual declared B36 job only')
  # This exact V4 historical function dispatches its worker argv from plan.driver;
  # it has no coordinator/schema literal substitution in this branch.
  row=v.v4.collect_job(reader,job,plan,pb,spec)
  if row is None:return None
  if row['status']=='COMPLETE':
   try:
    records,owners=invocation_rows(reader,plan,pb,observer_receipts=observer_receipts);v.ensure_invocations_closed(records,owners)
    require(all(v.process_state(o['pid'],o['creation_time'])['alive'] is False for o in row['recorded_owned_processes']),'Actual native owner closure')
    proof=records[0]['b36_v2_proof'];by={r['job_id']:r['completion'] for r in proof['completed_cells']}
    require(by[job['job_id']] in row['receipt_bindings'],'Exact new-batch/native completion link')
    row['observer_admission']=dict(invocations=records,wrapper=B.F.bind(B.__file__),source_schema=SCHEMA)
   except v.ERRORS as exc:row.update(status='NATIVE_COMPLETE_OBSERVER_UNVERIFIED',error=repr(exc))
  return row
 def collect_paced_job(reader,job,plan,pb,spec):return collect_job(reader,job,plan,pb,spec)
 api.kind_of=kind_of;api.admit_plan=admit_plan;api.invocation_rows=invocation_rows;api.collect_job=collect_job;api.collect_paced_job=collect_paced_job;api.source_bindings=sources
 api.HISTORICAL={**base.HISTORICAL,SCHEMA:('B36',)}
 ns={**base.collect.__globals__,**vars(api)};old=base.collect;fn=types.FunctionType(old.__code__,ns,old.__name__,old.__defaults__,old.__closure__);fn.__kwdefaults__=old.__kwdefaults__;api.collect=fn
 api.b36_wrapper=B;return api
