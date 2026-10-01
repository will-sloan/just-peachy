"""Fresh read-only manager PC copy. README_FINAL_MANAGER_COPY_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,hashlib,json,sys,os,math,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.dont_write_bytecode=True

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('source-evidence','output','census','precheck','prior'):p.add_argument('--'+n,required=True,type=Path)
 a=p.parse_args();a.output.mkdir()
 me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
 (a.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
 from field_local_manager_receiver_v2 import session
 from field_local_auxiliary_v1 import STDLIB,analyze
 from field_local_release_plan_v2 import encoded
 from field_owner_binding_v1 import pack,decode
 from field_operator_broker_host_v2 import ssh_phase,closed_owners
 from field_host_budget_v1 import floors
 from dispatch_b01_stack_v2 import SSH
 from dispatch_field_local_joint_v2 import PREFLIGHT
 here=Path(__file__).resolve().parent
 if time.time()-a.precheck.stat().st_mtime>120 or time.time()-a.census.stat().st_mtime>900:raise ValueError('Fresh full host review/census')
 request=json.loads((a.source_evidence/'admission/MANAGER_REQUEST.json').read_bytes())
 release=request['policy'];prior=decode(json.loads(a.prior.read_bytes()))
 base=request['baseline'];allowners={ (v['boot_id'],v['pid'],v['start_ticks']):v for v in prior }
 baseline={(v['boot_id'],v['pid'],v['start_ticks']) for v in base['owners']}
 def walk(v):
  if isinstance(v,dict):
   yield v
   for child in v.values():yield from walk(child)
  elif isinstance(v,list):
   for child in v:yield from walk(child)
 # Only actual receipts in the one executed source operation, not host fixtures.
 for file in a.source_evidence.rglob('*.json'):
  if file.stat().st_size>1048576:continue
  for v in walk(json.loads(file.read_bytes())):
   if set(v)=={'pid','start_ticks','boot_id'} and (v['boot_id'],v['pid'],v['start_ticks']) not in baseline:
    allowners[(v['boot_id'],v['pid'],v['start_ticks'])]=v
 external=[json.loads((a.source_evidence/rel).read_bytes()) for rel in
  ('admission/INSTALL_OWNER.json','broker-copy-mirror/broker/GATE_OWNER.json','admission/FINISH_OWNER.json','admission/REOPEN_OWNER.json')]
 sourcepins={};counter=[0];phaseowners=[]
 def write(name,v,raw=False):
  b=v if raw else encoded(v)
  if len(b)>65536:raise ValueError('Bounded receiver setup receipt')
  current=[x for x in a.output.iterdir() if x.is_file()]
  if len(current)>=32 or sum(x.stat().st_size for x in current)+len(b)>262144:raise ValueError('Independent setup aggregate')
  q=a.output/name
  with q.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
  assert q.read_bytes()==b
 def probe():
  counter[0]+=1;label='PREFLIGHT_%d'%counter[0]
  r=ssh_phase(['python3','-u','-B','-c',PREFLIGHT],
    payload=encoded(dict(boot_id=base['boot_id'],baseline_owners=base['owners'],prior=list(allowners.values()),pins=request['physical_pins']))+b'\n',
    timeout=30,maximum=16384)
  write(label+'_STDOUT.bin',r['stdout'],True);write(label+'_STDERR.bin',r['stderr'],True)
  write(label+'_PHASE.json',{k:v for k,v in r.items() if k not in ('stdout','stderr')})
  rows=[json.loads(v) for v in r['stdout'].splitlines()]
  if rows:
   o=rows[0]['owner'];write(label+'_OWNER.json',o);phaseowners.append(o)
   c=closed_owners([o]);write(label+'_CLOSURE.json',c);phaseowners.append(c['utility_owner'])
   for v in (o,c['utility_owner']):allowners[(v['boot_id'],v['pid'],v['start_ticks'])]=v
  if r['returncode'] or r['fault'] or not r['readers_joined'] or not r['ssh_reaped'] or len(rows)!=2:raise RuntimeError('Current native closure failed')
  stamp=datetime.fromisoformat(rows[1]['lifecycle']['observed_utc']);received=datetime.now(timezone.utc)
  delta=(stamp-received).total_seconds()
  if not -120<=delta<=5:raise ValueError('Actual clock drift')
  began=time.monotonic()
  while datetime.now(timezone.utc)<stamp:
   if time.monotonic()-began>5:raise TimeoutError('Clock barrier')
   time.sleep(.01)
  write(label+'_CLOCK.json',dict(native=stamp.isoformat(),host_received=received.isoformat(),wait=time.monotonic()-began))
  return rows[1]
 observed=probe()
 sys.path.insert(0,str(here.parent))
 from window_guard import payload_inventory
 from dispatch_geometry_v2 import LOCAL
 used=0
 for rel in ('n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928'):
  inv=payload_inventory(LOCAL/rel)
  assert not inv['errors'] and not inv['reparse_not_traversed'];used+=inv['total_logical_bytes']
 c=json.loads(a.census.read_bytes())['calculation'];payload=c['existing_bytes']+c['retained_reservations_bytes']+observed['target_bytes']+max(0,used-c['window_used_bytes'])
 now=datetime.now(timezone.utc);end=now+timedelta(seconds=600)
 assert end<=datetime.fromisoformat('2026-10-01T16:14:58+00:00')
 full=155669036+2097152;floors(full)
 policy=dict(schema='just-peachy.manager-readonly-pc-copy-policy.v1',issued_utc=now.isoformat(),expires_utc=end.isoformat(),
  target_payload_writes=False,capture=False,measured_host_bytes=used,measured_target_bytes=observed['target_bytes'],
  measured_payload_bytes=payload,full_independent_host_bytes=full,metadata_bytes=2097152,
  combined_output_cap_bytes=math.ceil((used+observed['target_bytes']+full+1048576)/1048576)*1048576,
  total_payload_cap_bytes=math.ceil((payload+full+1048576)/1048576)*1048576,
  previous_failed_destination_preserved=True,old_policy_reused=False,unused_credit=False,source_policy_sha256=request['policy_sha256'])
 write('RESOURCE_POLICY.json',policy)
 write('RESOURCE_POLICY_BACKUP.json',policy);write('RESOURCE_POLICY_RESTORE.json',policy)
 modules={};todo=['field_local_manager_export_v2']
 while todo:
  n=todo.pop()
  if n in modules:continue
  source=(here/(n+'.py')).read_text();modules[n]=source
  for node in ast.walk(ast.parse(source)):
   names=[v.name.split('.')[0] for v in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else [])
   todo.extend(v for v in names if v not in STDLIB and v not in modules)
 sha=lambda v:hashlib.sha256(v).hexdigest()
 pins={n:sha(s.encode()) for n,s in modules.items()};analyze(modules,pins)
 life=observed['lifecycle']
 admission=dict(schema='just-peachy.manager-export-admission.v1',phase='census',issued_utc=now.isoformat(),expires_utc=end.isoformat(),
  unit='jp-field-manager-census-v3.service',manager_binding=dict(schema='just-peachy.manager-tree-binding.v1',
   policy=release,policy_sha256=request['policy_sha256'],manifest=request['manifest']),
  lifecycle=life,lifecycle_sha256=sha(encoded(life)),module_sha256=pins,external_owners=external,
  closed_owners=pack(list(allowners.values())),mirror_maximum_bytes=155669036)
 result=session(a.output/'manager-copy',a.output/'manager-copy-closure',owner,admission,modules,
  (here/'field_local_auxiliary_v1.py').read_text(),(here/'field_local_manager_bootstrap_v1.py').read_text(),SSH,
  lifecycle_refresh=lambda:probe()['lifecycle'])
 write('RESULT.json',dict(status='PASS_SEPARATE_COMPLETE_MANAGER_PC_COPY',copy=result,preflight_owners=phaseowners,
  original_failed_trial_unchanged=True,production_ready=False))
 print(json.dumps(dict(status='PASS_SEPARATE_COMPLETE_MANAGER_PC_COPY',data=result['result'])))
 return 0
if __name__=='__main__':raise SystemExit(main())
