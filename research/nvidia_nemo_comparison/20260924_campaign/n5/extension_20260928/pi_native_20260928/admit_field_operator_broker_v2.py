"""Issue one measured broker admission; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V5.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,base64,hashlib,json,math,sys,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.dont_write_bytecode=True
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('bundle','census','resources','closure','extra','output'):p.add_argument('--'+n,required=True,type=Path)
 p.add_argument('--root-name',required=True);a=p.parse_args()
 a.output.mkdir();me=psutil.Process()
 owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
 (a.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
 from field_operator_session_plan_v3 import encoded,validate_policy
 from field_operator_broker_layout_v2 import allocation
 from field_owner_binding_v1 import pack
 from field_host_budget_v1 import floors
 from mirror_field_operator_broker_v2 import MODULES
 import re
 if not re.fullmatch('field-operator-sessions-v[1-9][0-9]*',a.root_name):raise ValueError('Fresh exact root')
 now=datetime.now(timezone.utc);hard=datetime.fromisoformat('2026-10-01T17:42:44+00:00')
 if now+timedelta(seconds=600)>=hard:raise RuntimeError('Cleanup/backup cannot cross hard deadline')
 if time.time()-a.census.stat().st_mtime>900 or time.time()-a.closure.stat().st_mtime>300 or time.time()-a.extra.stat().st_mtime>300:raise RuntimeError('Fresh complete closure/census required')
 here=Path(__file__).resolve().parent
 def sha(raw):return hashlib.sha256(raw).hexdigest()
 def pin(p):p=Path(p);raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=sha(raw))
 def write(p,raw):p.open('xb').write(raw);assert p.read_bytes()==raw
 r=json.loads(a.resources.read_bytes());native=json.loads(a.closure.read_bytes());extra=json.loads(a.extra.read_bytes())
 if any(row['exact_alive'] is not False for row in extra['pi']+extra['host']):raise ValueError('Prior owner active')
 if extra['utility_pid_absent_after_ssh'] is not True:raise ValueError('Extra utility unresolved')
 pi={}
 for row in native['owners']+extra['pi']:
  o=row['owner'];pi[(o['boot_id'],o['pid'],o['start_ticks'])]=o
 for o in (native['utility_owner'],extra['utility_owner']):pi[(o['boot_id'],o['pid'],o['start_ticks'])]=o
 hosts={}
 for row in extra['host']+r['host_owners']+r['isolated_export_owners']:
  o=row.get('owner',row);hosts[(o['pid'],o['create_time'])]=dict(pid=o['pid'],create_time=o['create_time'])
 for o in hosts.values():
  try:created=psutil.Process(o['pid']).create_time()
  except psutil.NoSuchProcess:created=None
  if created is not None and abs(created-o['create_time'])<.001:raise RuntimeError('Prior host remains')
 bundle=json.loads(a.bundle.read_bytes());files={n:base64.b64decode(v,validate=True) for n,v in bundle['files'].items()}
 if bundle['manifest']['files']!=[dict(path=n,bytes=len(raw),sha256=sha(raw)) for n,raw in sorted(files.items())]:raise ValueError('Original bundle membership/pins')
 config=json.loads(files['broker/CONFIG.json']);template=json.loads(files['broker/TEMPLATE.json'])
 config['preflight_pi_owners']=pack(list(pi.values()))
 template['admission'].update(preflight_pi_owners=config['preflight_pi_owners'],host_window_bytes=r['host_window_bytes'],
  payload_before_bytes=r['payload_bytes'],target_before_bytes=r['target_bytes'])
 files['broker/CONFIG.json']=encoded(config);files['broker/TEMPLATE.json']=encoded(template)
 for name,maximum in [('broker/CONFIG.json',65536),('broker/TEMPLATE.json',131072)]:
  if len(files[name])>maximum:raise ValueError('Exact updated control ceiling')
 manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(raw),sha256=sha(raw)) for n,raw in sorted(files.items())])
 full=allocation(2);root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/'+a.root_name
 # 4MiB explicit preparation capsule primary/backup/restore, plus 4MiB measured-accounting margin.
 margin=8388608;request_bytes=full['combined_request_bytes']
 policy=dict(schema='just-peachy.operator-broker-policy.v1',root=root,issued_utc=now.isoformat(),
  expires_utc=(now+timedelta(seconds=600)).isoformat(),allocation=full,
  combined_output_cap_bytes=math.ceil((r['combined_bytes']+request_bytes+margin)/1048576)*1048576,
  total_payload_cap_bytes=math.ceil((r['payload_bytes']+request_bytes+margin)/1048576)*1048576,
  mode='delayed',release_manifest_sha256=sha(encoded(manifest)),boot_id=config['baseline']['boot_id'],
  host_window_bytes=r['host_window_bytes'],target_before_bytes=r['target_bytes'],payload_before_bytes=r['payload_bytes'])
 validate_policy(policy);floors(4*1048576+full['host_maximum_bytes'])
 request=dict(policy=policy,manifest=manifest,files={n:base64.b64encode(raw).decode() for n,raw in sorted(files.items())})
 rawrequest=encoded(request)
 if len(rawrequest)>4*1048576:raise ValueError('Initializer request ceiling')
 for folder in ('backup','restore'):(a.output/folder).mkdir()
 outputs={'RELEASE.json':encoded(policy),'INITIALIZER_REQUEST.json':rawrequest}
 # Exact readback and independent restoration BEFORE native dispatch.
 for name,raw in outputs.items():
  for folder in (a.output,a.output/'backup',a.output/'restore'):write(folder/name,raw)
 required=set((*MODULES,'dispatch_field_operator_broker_v4','mirror_field_operator_broker_v2','field_operator_broker_host_v2',
  'field_operator_broker_initialize_v1','field_operator_broker_census_v2','dispatch_b01_stack_v2','dispatch_geometry_v2'))
 paths=[here/(n+'.py') for n in sorted(required)]+[a.census,a.resources,a.closure,a.extra,a.bundle,a.output/'INITIALIZER_REQUEST.json',a.output/'RELEASE.json']
 plan=dict(policy=policy,host_pins=[pin(path) for path in paths],coordinator_sha256=pin(here/'dispatch_field_operator_broker_v4.py')['sha256'],
  census=str(a.census),initializer_request=str(a.output/'INITIALIZER_REQUEST.json'),
  python='/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python',
  output=str(a.output/'host'),prior_host_owners=list(hosts.values()),export_unit='jp-field-broker-export-v'+a.root_name.rsplit('v',1)[1]+'.service')
 rawplan=encoded(plan)
 for folder in (a.output,a.output/'backup',a.output/'restore'):write(folder/'PLAN.json',rawplan)
 review=dict(status='ADMITTED_SINGLE_CHANGED_TWO_SESSION_ATTEMPT',issued_utc=policy['issued_utc'],expires_utc=policy['expires_utc'],
  fresh_policy_sha256=sha(encoded(policy)),full_allocation=full,measured_output=r['combined_bytes'],measured_payload=r['payload_bytes'],
  explicit_preparation_and_margin_bytes=margin,old_window_unchanged=True,failed_or_unused_slot_credit=False,
  capsule_files=64,independent_source_readback_restore=True,prior_pi_owners=len(pi),prior_host_owners=len(hosts),
  new_native_attempt=False,quiet_function_only=True,physical_touch=False,accuracy=False)
 write(a.output/'ADMISSION_REVIEW.json',encoded(review))
 actual=sum(p.stat().st_size for p in a.output.rglob('*') if p.is_file())
 if actual+5*65536>4*1048576:raise ValueError('Measured 4MiB admission capsule metadata budget')
 if (datetime.now(timezone.utc)-now).total_seconds()>5:raise TimeoutError('Admission assembly consumed dispatch freshness')
 print(json.dumps(dict(plan=str(a.output/'PLAN.json'),owner_receipt=str(a.output/'DISPATCH_EARLY_OWNER.json'),policy_sha256=review['fresh_policy_sha256'],bytes=actual,expires=policy['expires_utc'])))
if __name__=='__main__':raise SystemExit(main())
