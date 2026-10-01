"""Changed broker-policy binding checks; README_FIELD_RUNTIME_POLICY_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse, copy, json, os
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();args.output.mkdir()
    me=psutil.Process()
    (args.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(
        pid=me.pid,create_time=me.create_time(),affinity=[14])),encoding='utf-8')
    from datetime import datetime, timezone, timedelta
    from field_runtime_policy_v2 import (ROOT,SCHEMA,LIMITS,PROFILES,issue_operation,
        validate_broker_policy,digest)
    from field_local_release_plan_v2 import allocation
    now=datetime(2026,10,2,12,tzinfo=timezone.utc);a=allocation(4,16)
    runtime=dict(schema=SCHEMA,release_id='field-runtime-v1',manager_root=str(ROOT/'field-runtime-v1'),
        recording_roots=[str(ROOT/('field-operator-sessions-v%d'%n)) for n in range(20,24)],
        provisioned_utc=(now-timedelta(hours=1)).isoformat(),allocation=a,limits=copy.deepcopy(LIMITS),
        runtime_manifest_sha256='a'*64,installed_manifest_sha256='b'*64,
        profiles={name:dict(available=True,input_kind='saved' if name.endswith('-saved') else 'microphone',
            manifest_sha256='c'*64,reason='') for name in PROFILES},
        measured_target_bytes=100,measured_host_bytes=200,measured_payload_bytes=400,
        combined_output_cap_bytes=300+a['combined_request_bytes'],
        total_payload_cap_bytes=400+a['combined_request_bytes'],
        storage_semantics=dict(local_backup_before_next=True,pc_copy_deferred_until_connected=True,
            pc_reservation_independent=True,original_preserved=True,copy_not_move=True,
            failed_deleted_unused_credit=False,automatic_replenishment=False,explicit_reprovision_required=True))
    owner=dict(pid=50,start_ticks=100,boot_id='11111111-2222-3333-4444-555555555555')
    modes={'baseline':'baseline','d1-delayed':'delayed','d1-anonymous':'delayed',
        'd1-streaming-saved':'streaming','d1-chunk52-saved':'chunk52'}
    def pair(profile):
        operation=issue_operation(runtime,slot='recording-01',profile=profile,owner=owner,now=now)
        policy=dict(schema='just-peachy.offline-broker-policy.v1',root=operation['root'],
            issued_utc=operation['issued_utc'],expires_utc=operation['expires_utc'],
            allocation=a['broker_allocation'],combined_output_cap_bytes=runtime['combined_output_cap_bytes'],
            total_payload_cap_bytes=runtime['total_payload_cap_bytes'],mode=modes[profile],
            release_manifest_sha256='d'*64,boot_id=owner['boot_id'],host_window_bytes=200,
            target_before_bytes=100,payload_before_bytes=400,runtime_policy_sha256=digest(runtime),
            runtime_operation_sha256=digest(operation),runtime_root=runtime['manager_root'],
            slot=operation['slot'],profile=profile)
        return policy,operation
    for profile in PROFILES:
        policy,operation=pair(profile)
        assert validate_broker_policy(policy,runtime,operation,now=now) is policy
    policy,operation=pair('d1-delayed');rejected=[]
    def reject(name,fn):
        try:fn()
        except (ValueError,RuntimeError):rejected.append(name)
        else:raise AssertionError('Accepted '+name)
    def changed(key,value):
        return validate_broker_policy({**policy,key:value},runtime,operation,now=now)
    changes=dict(schema='just-peachy.operator-broker-policy.v1',root=runtime['recording_roots'][1],
        issued_utc=(now-timedelta(seconds=1)).isoformat(),expires_utc=(now+timedelta(seconds=601)).isoformat(),
        allocation={**a['broker_allocation'],'count':True},
        combined_output_cap_bytes=runtime['combined_output_cap_bytes']+1,
        total_payload_cap_bytes=runtime['total_payload_cap_bytes']+1,mode='streaming',
        release_manifest_sha256='bad',boot_id='22222222-2222-3333-4444-555555555555',
        host_window_bytes=True,target_before_bytes=0,payload_before_bytes=0,
        runtime_policy_sha256='e'*64,runtime_operation_sha256='e'*64,
        runtime_root=str(ROOT/'field-runtime-v2'),slot='recording-02',profile='d1-anonymous')
    for key,value in changes.items():reject(key,lambda k=key,v=value:changed(k,v))
    reject('extra field',lambda:changed('unknown',1))
    reject('expired',lambda:validate_broker_policy(policy,runtime,operation,now=now+timedelta(seconds=600)))
    reject('future',lambda:validate_broker_policy(policy,runtime,operation,now=now-timedelta(seconds=1)))
    reject('operation owner drift',lambda:validate_broker_policy(policy,runtime,{**operation,'owner':{**owner,'pid':51}},now=now))
    result=dict(status='PASS_CHANGED_RUNTIME_BROKER_BINDING',positive_profiles=len(PROFILES),
        rejects=rejected,synthetic_policy_owners=True,native_executed=False,filesystem_loader_executed=False,
        resource_admission_issued=False)
    raw=(json.dumps(result,indent=2)+'\n').encode()
    with (args.output/'RESULT.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    assert (args.output/'RESULT.json').read_bytes()==raw
    print(json.dumps(dict(status=result['status'],positive_profiles=len(PROFILES),rejects=len(rejected))))


if __name__=='__main__':main()

