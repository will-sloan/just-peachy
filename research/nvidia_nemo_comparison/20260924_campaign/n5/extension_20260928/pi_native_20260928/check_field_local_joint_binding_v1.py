"""Changed joint binding only; README_FIELD_LOCAL_JOINT_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,json,copy,base64,hashlib
from datetime import datetime,timezone,timedelta
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--capsules',type=Path,required=True)
parser.add_argument('--template',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir()
me=psutil.Process()
(args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
from field_local_joint_contract_v2 import bind,digest
from field_local_release_plan_v2 import allocation,encoded
broker=json.loads((args.capsules/'BUNDLE.json').read_bytes())
manager=json.loads((args.capsules/'MANAGER_BUNDLE.json').read_bytes())
template=json.loads(args.template.read_bytes())
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [args.capsules/'BUNDLE.json',args.capsules/'MANAGER_BUNDLE.json',args.template]}
config=json.loads(base64.b64decode(broker['files']['broker/CONFIG.json']))
child=json.loads(base64.b64decode(broker['files']['broker/TEMPLATE.json']))
release=copy.deepcopy(template)
release.update(schema='just-peachy.local-release-policy.v2',allocation=allocation(1,3),
    root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-local-release-v999',
    recording_roots=['/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-operator-sessions-v999'],
    release_manifest_sha256=digest(encoded(manager['manifest'])),
    installed_manifest_sha256=config['installed_manifest_sha256'],
    mode_registry_sha256=child['admission']['operator_parent']['manifest_sha256'])
# Fixture accounting/time/owners are NEVER a native admission.
release['combined_output_cap_bytes']=release['measured_target_before_bytes']+release['measured_host_before_bytes']+release['allocation']['combined_request_bytes']
release['total_payload_cap_bytes']=release['measured_payload_before_bytes']+release['allocation']['combined_request_bytes']
now=datetime.fromisoformat('2026-10-01T11:22:00+00:00')
operation=dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),purpose='LOCAL_RELEASE_QUALIFICATION')
owners=[dict(pid=123,start_ticks=456,boot_id='00000000-0000-0000-0000-000000000000')]
def repin(value):
 value['manifest']['files']=[dict(path=n,bytes=len(base64.b64decode(body)),sha256=digest(base64.b64decode(body))) for n,body in sorted(value['files'].items())]
def change_config(value,fn):
 cfg=json.loads(base64.b64decode(value['files']['broker/CONFIG.json']));fn(cfg)
 value['files']['broker/CONFIG.json']=base64.b64encode(encoded(cfg)).decode();repin(value)
def run(b=broker,m=manager,r=release,o=operation,ids=owners):
 return bind(b,m,r,o,ids,now=now)
result=run()
assert result['admission_issued'] is False
assert result['full_joint_reservation']['combined_request_bytes']==617760944
assert result['reserve_binding']['launch_slot']=='launch-01'
assert result['gate_binding']['launch_slot']=='launch-02'
assert result['finish_binding']['launch_slot']=='launch-03'
request=result['broker_request']
assert request['policy']['allocation']['count']==1
assert request['policy']['combined_output_cap_bytes']==release['combined_output_cap_bytes']
cfg=json.loads(base64.b64decode(request['files']['broker/CONFIG.json']))
assert cfg['local_manager']==result['gate_binding']
assert cfg['preflight_pi_owners']!=config['preflight_pi_owners']
for row in request['manifest']['files']:
 raw=base64.b64decode(request['files'][row['path']],validate=True)
 assert row['bytes']==len(raw) and row['sha256']==digest(raw)
rejects=[]
def reject(label,fn):
 try:fn()
 except (ValueError,KeyError,TypeError):rejects.append(label)
 else:raise AssertionError('Accepted '+label)
for label,fn in [
 ('boolean-recording-count',lambda c:c['qualification'].update(count=True)),
 ('two-session-driver',lambda c:c['qualification'].update(count=2)),
 ('stale-manager-digest',lambda c:c.update(manager_manifest_sha256='0'*64)),
 ('already-bound-capsule',lambda c:c.update(local_manager={})),
 ('installed-manifest-drift',lambda c:c.update(installed_manifest_sha256='0'*64)),
 ('extra-qualification-field',lambda c:c['qualification'].update(extra=1))]:
 b=copy.deepcopy(broker);change_config(b,fn);reject(label,lambda b=b:run(b=b))
b=copy.deepcopy(broker)
raw=base64.b64decode(b['files']['broker/CONFIG.json'])
b['files']['broker/CONFIG.json']=base64.b64encode(b'{"qualification":null,'+raw[1:]).decode();repin(b)
reject('duplicate-control-key',lambda:run(b=b))
for label,fn in [
 ('foreign-root',lambda r:r.update(root='/tmp/field-local-release-v999')),
 ('output-one-byte-short',lambda r:r.update(combined_output_cap_bytes=r['combined_output_cap_bytes']-1)),
 ('payload-one-byte-short',lambda r:r.update(total_payload_cap_bytes=r['total_payload_cap_bytes']-1)),
 ('manager-policy-digest',lambda r:r.update(release_manifest_sha256='0'*64)),
 ('registry-drift',lambda r:r.update(mode_registry_sha256='0'*64))]:
 r=copy.deepcopy(release);fn(r);reject(label,lambda r=r:run(r=r))
reject('missing-prior-identities',lambda:run(ids=[]))
reject('boolean-owner-pid',lambda:run(ids=[dict(owners[0],pid=True)]))
reject('operation-exceeds-600',lambda:run(o=dict(operation,expires_utc=(now+timedelta(seconds=601)).isoformat())))
m=copy.deepcopy(manager);name=next(iter(m['files']));m['files'][name.upper().replace('.PY','.py')]=m['files'][name];repin(m)
reject('manager-case-alias',lambda:run(m=m))
m=copy.deepcopy(manager);m['manifest']['files'][0]['bytes']=True
reject('boolean-manifest-size',lambda:run(m=m))
m=copy.deepcopy(manager);m['files'][next(iter(m['files']))]='a'*174765
reject('oversized-base64-before-decode',lambda:run(m=m))
m=copy.deepcopy(manager);m['files']['code/../escape.py']=m['files'].pop(next(iter(m['files'])));repin(m)
reject('traversal-member',lambda:run(m=m))
for path,sha in before.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
report=dict(status='PASS_CHANGED_JOINT_BINDING',positive_groups=1,rejected=rejects,
 actual_prepared_capsules=True,synthetic_release_operation_owners=True,source_pins=before,
 output_manifest_sha256=digest(encoded(request['manifest'])),native_execution=False,
 journal_constructor=False,admission_issued=False,source_unchanged=True)
(args.output/'RESULT.json').open('x').write(json.dumps(report));print(json.dumps(report))

