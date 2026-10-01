"""Host-only broker mirror allocation checks; README_FIELD_OPERATOR_BROKER_NATIVE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import os
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import json
import time
from datetime import datetime,timezone
def main(output):
    output=Path(output);output.mkdir()
    owner=dict(pid=os.getpid(),create_time=psutil.Process().create_time(),affinity=[14])
    (output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
    import field_operator_broker_streamed_mirror_v1 as mirror
    from field_operator_session_plan_v3 import encoded
    from field_operator_broker_layout_v2 import allocation
    policy=dict(schema='just-peachy.operator-broker-policy.v1',
        root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-operator-sessions-v99999',
        issued_utc='2026-10-01T06:00:00+00:00',expires_utc='2026-10-01T06:10:00+00:00',
        allocation=allocation(2),combined_output_cap_bytes=700000000,
        total_payload_cap_bytes=700000000,mode='delayed',release_manifest_sha256='a'*64,
        boot_id='00000000-0000-0000-0000-000000000000',host_window_bytes=0,target_before_bytes=0,payload_before_bytes=0)
    (output/'RELEASE.json').write_bytes(encoded(policy))
    # Synthetic inventory only. No Pi path, filesystem lock or receipt is claimed.
    base={'RELEASE.json':(1,1,len(encoded(policy)),1),
        'code/example.py':(1,2,100,1),'broker/OWNER.json':(1,3,80,1),
        'recordings/slot-01/control/ADMISSION.json':(1,4,100,1),
        'recordings/slot-02/control/ADMISSION.json':(1,5,100,1)}
    dirs={'','broker','code','recordings','slot-01','slot-02',
          'recordings/slot-01','recordings/slot-01/control',
          'recordings/slot-02','recordings/slot-02/control'}
    current=[base,dirs];original=mirror._inventory
    mirror._inventory=lambda root,deadline:current
    rejected=[];start=time.monotonic()
    try:
        assert mirror.inventory(output,time.monotonic()+10)==(base,dirs)
        for label,files,folders in [
            ('foreign_recording',dict(base,**{'recordings/slot-03/x':(1,8,1,1)}),dirs),
            ('unknown_broker_writer',dict(base,**{'broker/extra.json':(1,8,1,1)}),dirs),
            ('gate_receipt_overflow',dict(base,**{'broker/GATE_RESULT.json':(1,8,16385,1)}),dirs),
            ('unallocated_outer_directory',base,dirs|{'unallocated'}),
            ('recording_file_count',dict(base,**{'recordings/slot-01/f%d'%i:(1,100+i,0,1) for i in range(256)}),dirs),
            ('recording_directory_count',base,dirs|{'recordings/slot-01/d%d'%i for i in range(63)}),
            ('recording_aggregate',dict(base,**{'recordings/slot-01/f%d'%i:(1,100+i,32000000,1) for i in range(5)}),dirs),
            ('code_count',dict(base,**{'code/f%d.py'%i:(1,100+i,1,1) for i in range(64)}),dirs),
            ('ledger_member',dict(base,**{'slot-01/not-a-state.json':(1,9,1,1)}),dirs),
        ]:
            current[:]=[files,folders]
            try:mirror.inventory(output,time.monotonic()+10)
            except (ValueError,RuntimeError):rejected.append(label)
            else:raise AssertionError('Accepted '+label)
        # Two 96MB synthetic archives fit independently, unlike one >146MB child.
        large=dict(base)
        for slot in ('slot-01','slot-02'):
            for i in range(3):large['recordings/'+slot+'/p%d'%i]=(1,200+i,32000000,1)
        current[:]=[large,dirs]
        assert mirror.inventory(output,time.monotonic()+10)==(large,dirs)
        result=dict(status='PASS_PURE_WHOLE_TREE_PARTITION_CONTRACT',positive_groups=2,
            rejects=rejected,elapsed_seconds=time.monotonic()-start,allocation=allocation(2),
            synthetic_inventory=True,native_filesystem=False,copy_or_transfer=False,
            capture_or_models=False,owner=owner)
        (output/'REVIEW.json').open('x').write(json.dumps(result))
        print(json.dumps(result))
    finally:mirror._inventory=original
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    raise SystemExit(main(p.parse_args().output))
