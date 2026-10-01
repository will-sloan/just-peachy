"""Changed host-only owner/lifecycle contract; README_FIELD_LOCAL_EXPORT_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
args=p.parse_args();args.output.mkdir()
me=psutil.Process();(args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
from field_local_manager_owners_v1 import decode,lifecycle,encoded,key
source={}
names=['broker/'+n for n in ('STAGE_OWNER.json','GATE_OWNER.json','OWNER.json')]
names+=['recordings/slot-01/'+n for n in ('control/OWNER.json','control/REGISTERED_OWNER.json','parent_control/OWNER.json','source/CHILD_OWNER.json')]
for n in names:
    raw=(args.source/n).read_bytes();source[n]=raw
records={'backups/recording-01/'+n:raw for n,raw in source.items()}
sha='a'*64;stamp='2026-10-01T12:00:00+00:00'
historical=[json.loads(source[n]) for n in names[:3]]
for i,purpose in enumerate(('LOCAL_INSTALL-RESERVE','LOCAL_GATE_BEFORE_ACK','LOCAL_FINISH'),1):
    slot='launches/launch-%02d'%i
    records[slot+'/OWNER.json']=encoded(dict(owner=historical[i-1],policy_sha256=sha,slot=slot,utc=stamp,purpose=purpose))
typed='backups/recording-01/recordings/slot-01/parent_control/OWNERSHIP_CLOSURE.json'
records[typed]=encoded(dict(borrowed=dict(opened=1,closed=1),outer_released=True,controller_closed=True,worker_joined=True,pending_commands=0))
value=decode(records,sha)
assert len(value['records'])==10 and len(value['typed_nonidentity_closures'])==1
assert {key(v) for v in value['identities']}=={key(json.loads(r)) for r in source.values()}
now=datetime.fromisoformat(stamp)
life=dict(schema='just-peachy.current-boot-binding.v1',observed_utc=stamp,boot_id=historical[0]['boot_id'],baseline_owners=historical[:2],install_sha256='b'*64,live_config_sha256='c'*64,display_config_sha256='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b')
hashlife=lambda v:hashlib.sha256(encoded(v)).hexdigest()
assert lifecycle(life,hashlife(life),now=now)==life
rejects=[]
def reject(label,call):
    try:call()
    except (ValueError,RuntimeError,TypeError,KeyError):rejects.append(label)
    else:raise AssertionError('Accepted '+label)
target='launches/launch-01/OWNER.json'
def altered(label,mutate):
    trial=copy.deepcopy(records);v=json.loads(trial[target]);mutate(v);trial[target]=encoded(v)
    reject(label,lambda:decode(trial,sha))
altered('boolean-pid',lambda v:v['owner'].update(pid=True))
altered('zero-ticks',lambda v:v['owner'].update(start_ticks=0))
altered('malformed-boot',lambda v:v['owner'].update(boot_id='x'*36))
altered('extra-owner-field',lambda v:v['owner'].update(extra=0))
altered('wrong-slot',lambda v:v.update(slot='launches/launch-02'))
altered('wrong-policy',lambda v:v.update(policy_sha256='b'*64))
altered('wrong-role',lambda v:v.update(purpose='LOCAL_FINISH'))
altered('extra-envelope',lambda v:v.update(extra=0))
altered('missing-owner',lambda v:v.pop('owner'))
altered('naive-owner-clock',lambda v:v.update(utc='2026-10-01T12:00:00'))
for label,name,raw in [('unknown-path','launches/launch-04/OWNER.json',records[target]),('duplicate-key',target,b'{"pid":1,"pid":2}'),('oversized-owner',target,b' '*16385),('floating-owner',target,b'{"pid":1.0}'),('pending-not-owner','launches/launch-01/OWNER.json.pending',b'{')]:
    trial=copy.deepcopy(records);trial[name]=raw;reject(label,lambda t=trial:decode(t,sha))
for label,changes in [('typed-bool-count',dict(borrowed=dict(opened=True,closed=1))),('typed-bool-pending',dict(pending_commands=False)),('typed-extra',dict(extra=0))]:
    trial=copy.deepcopy(records);v=json.loads(trial[typed]);v.update(changes);trial[typed]=encoded(v)
    reject(label,lambda t=trial:decode(t,sha))
reject('wrong-lifecycle-digest',lambda:lifecycle(life,'f'*64,now=now))
reject('stale-lifecycle',lambda:lifecycle(life,hashlife(life),now=now+timedelta(seconds=121)))
reject('future-lifecycle',lambda:lifecycle(life,hashlife(life),now=now-timedelta(seconds=1)))
for label,change in [('mixed-boot',lambda v:v.update(boot_id='0'*8+'-0000-0000-0000-'+'0'*12)),('duplicate-baseline',lambda v:v.update(baseline_owners=[v['baseline_owners'][0]]*2)),('display-drift',lambda v:v.update(display_config_sha256='d'*64)),('extra-lifecycle',lambda v:v.update(extra=0))]:
    v=copy.deepcopy(life);change(v);reject(label,lambda t=v:lifecycle(t,hashlife(t),now=now))
for n,raw in source.items():assert (args.source/n).read_bytes()==raw
result=dict(status='PASS_CHANGED_HOST_MANAGER_OWNER_AND_BOOT_BINDING',positive_groups=2,decoded_owner_records=len(value['records']),typed_nonidentity_closures=1,unique_identities=len(value['identities']),rejected=rejects,historical_direct_owner_files=7,synthetic_nested_launch_and_lifecycle=True,fixture_clock=True,native_probe=False,process_closure_proven=False,source_unchanged=True,source_pins={n:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for n,raw in source.items()})
(args.output/'RESULT.json').open('x').write(json.dumps(result,indent=2))
print(json.dumps({k:result[k] for k in ('status','positive_groups','decoded_owner_records','unique_identities','rejected')}))
