"""Changed role-binding checks only; README_FIELD_LOCAL_SUPERVISOR_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,json,hashlib,copy
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(exist_ok=False)
me=psutil.Process()
(a.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
from field_local_release_files_v4 import validate_started_observation
names=('broker/ENVELOPE.json','broker/OWNER.json','broker/GATE_OWNER.json')
raw={name:(a.source/name).read_bytes() for name in names}
assert all(len(v)<=16384 for v in raw.values())
data={name:json.loads(v) for name,v in raw.items()}
owner=data['broker/OWNER.json'];gate=data['broker/GATE_OWNER.json'];env=data['broker/ENVELOPE.json']
assert env['gate_owner']==gate and env['properties']['MainPID']==str(owner['pid'])
values=dict(MainPID=env['properties']['MainPID'],ActiveState='active')
# ENVELOPE has no ActiveState field: this field is an explicit synthetic fixture.
assert validate_started_observation(owner,gate,gate,values)
rejected=[]
def reject(name,o,g,c,v):
    try:validate_started_observation(o,g,c,v)
    except (ValueError,RuntimeError):rejected.append(name)
    else:raise AssertionError('Expected rejection: '+name)
v=dict(values,MainPID=str(gate['pid']));reject('gate-is-not-service-mainpid',owner,gate,gate,v)
reject('inactive-unit',owner,gate,gate,dict(values,ActiveState='inactive'))
reject('extra-service-field',owner,gate,gate,dict(values,Other='x'))
reject('integer-mainpid',owner,gate,gate,dict(values,MainPID=owner['pid']))
o=dict(owner,boot_id='00000000-0000-0000-0000-000000000000');reject('foreign-boot',o,gate,gate,values)
reject('shared-pid',owner,dict(gate,pid=owner['pid']),gate,values)
reject('bool-pid',dict(owner,pid=True),gate,gate,values)
reject('zero-start-tick',dict(owner,start_ticks=0),gate,gate,values)
reject('extra-owner-field',dict(owner,extra=1),gate,gate,values)
reject('missing-owner-field',{k:v for k,v in owner.items() if k!='pid'},gate,gate,values)
assert all((a.source/n).read_bytes()==v for n,v in raw.items())
result=dict(status='PASS_CHANGED_HISTORICAL_ROLE_BINDING',positive_groups=1,rejected=rejected,
    historical_broker=owner,historical_gate=gate,
    historical_pins={n:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in raw.items()},
    active_state_fixture=True,current_native_identity_checked=False,native_execution=False,
    journal_constructor=False,source_bytes_unchanged=True)
(a.output/'RESULT.json').open('x').write(json.dumps(result))
print(json.dumps(dict(status=result['status'],positive_groups=1,rejections=len(rejected))))
