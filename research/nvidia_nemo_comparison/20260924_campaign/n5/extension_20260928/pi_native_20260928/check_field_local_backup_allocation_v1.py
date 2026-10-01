"""Changed complete host-backup accounting; README_FIELD_LOCAL_CAPSULE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,json,copy
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--template',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir()
me=psutil.Process();(a.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
from field_local_release_plan_v1 import allocation as old_allocation
from field_local_release_plan_v2 import allocation,validate_release
original=json.loads(a.template.read_bytes())
cases=[];rejected=[]
for count,launches in ((1,3),(2,6),(4,16)):
    before=old_allocation(count,launches);after=allocation(count,launches)
    assert after['target_maximum_bytes']==before['target_maximum_bytes']
    assert after['broker_allocation']==before['broker_allocation']
    assert after['local_backup_per_recording']==before['local_backup_per_recording']==151114284
    assert after['host_maximum_bytes']-before['host_maximum_bytes']==count*151114284
    assert after['combined_request_bytes']==after['target_maximum_bytes']+after['host_maximum_bytes']
    value=copy.deepcopy(original);value['schema']='just-peachy.local-release-policy.v2';value['allocation']=after
    value['recording_roots']=['/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-operator-sessions-v%d'%(100+i) for i in range(count)]
    value['combined_output_cap_bytes']=value['measured_target_before_bytes']+value['measured_host_before_bytes']+after['combined_request_bytes']
    value['total_payload_cap_bytes']=value['measured_payload_before_bytes']+after['combined_request_bytes']
    assert validate_release(value)==value
    cases.append(dict(recordings=count,launches=launches,target=after['target_maximum_bytes'],host=after['host_maximum_bytes'],combined=after['combined_request_bytes'],extra_host=count*151114284))
    for label,alter in (
        ('old-host-allocation',lambda v:v['allocation'].update(host_maximum_bytes=before['host_maximum_bytes'])),
        ('one-byte-output-short',lambda v:v.update(combined_output_cap_bytes=v['combined_output_cap_bytes']-1)),
        ('one-byte-payload-short',lambda v:v.update(total_payload_cap_bytes=v['total_payload_cap_bytes']-1))):
        changed=copy.deepcopy(value);alter(changed)
        try:validate_release(changed)
        except ValueError:rejected.append(str(count)+'-'+label)
        else:raise AssertionError('Changed full reservation accepted invalid contract')
try:validate_release(original)
except ValueError:rejected.append('old-policy-schema')
else:raise AssertionError('Old policy unexpectedly accepted')
result=dict(status='PASS_CHANGED_DUAL_HOST_BACKUP_ALLOCATION',positive_groups=3,rejected=rejected,cases=cases,synthetic_caps=True,policy_issued=False,native_execution=False)
(a.output/'RESULT.json').open('x').write(json.dumps(result));print(json.dumps(result))
