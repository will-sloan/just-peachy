"""Changed production-policy checks; README_FIELD_RUNTIME_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from pathlib import Path
import json
import os


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(); args.output.mkdir()
    me = psutil.Process()
    (args.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(
        pid=me.pid, create_time=me.create_time(), affinity=[14])), encoding='utf-8')
    from datetime import datetime, timezone, timedelta
    import copy
    from field_runtime_policy_v1 import (ROOT, SCHEMA, LIMITS, PROFILES, validate,
        issue_operation, validate_operation, next_slot, digest)
    from field_local_release_plan_v2 import allocation
    now = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
    a = allocation(4, 16)
    profiles = {name: dict(available=True, input_kind='saved' if name.endswith('-saved') else 'microphone',
        manifest_sha256='a'*64, reason='') for name in PROFILES}
    policy = dict(schema=SCHEMA, release_id='field-runtime-v1',
        manager_root=str(ROOT/'field-runtime-v1'),
        recording_roots=[str(ROOT/('field-operator-sessions-v%d' % n)) for n in range(20, 24)],
        provisioned_utc=(now-timedelta(hours=1)).isoformat(), allocation=a, limits=copy.deepcopy(LIMITS),
        runtime_manifest_sha256='b'*64, installed_manifest_sha256='c'*64, profiles=profiles,
        measured_target_bytes=100, measured_host_bytes=200, measured_payload_bytes=400,
        combined_output_cap_bytes=300+a['combined_request_bytes'],
        total_payload_cap_bytes=400+a['combined_request_bytes'],
        storage_semantics=dict(local_backup_before_next=True, pc_copy_deferred_until_connected=True,
            pc_reservation_independent=True, original_preserved=True, copy_not_move=True,
            failed_deleted_unused_credit=False, automatic_replenishment=False, explicit_reprovision_required=True))
    owner=dict(pid=50,start_ticks=100,boot_id='11111111-2222-3333-4444-555555555555')
    assert validate(policy) is policy and a['combined_request_bytes']==2453742272
    op=issue_operation(policy,slot='recording-01',profile='d1-delayed',owner=owner,now=now)
    assert validate_operation(op,policy,now=now+timedelta(seconds=599)) is op
    assert op['expires_utc']==(now+timedelta(seconds=600)).isoformat()
    records={s:None for s in a['recording_slots']}
    assert next_slot(policy,records)=='recording-01'
    records['recording-01']=dict(state='CLOSED_LOCAL_BACKED',local_backup_sha256='d'*64,pc_backup_sha256=None)
    assert next_slot(policy,records)=='recording-02'
    records['recording-02']=dict(state='FAILED_PRESERVED_LOCAL_BACKED',local_backup_sha256='e'*64,pc_backup_sha256=None)
    assert next_slot(policy,records)=='recording-03'
    # This validates only a state shape; the native ledger must obtain its own facts.
    rejected=[]
    def reject(name,fn):
        try:fn()
        except (ValueError,RuntimeError):rejected.append(name)
        else:raise AssertionError('Accepted invalid '+name)
    def changed(field,value):
        p=copy.deepcopy(policy);p[field]=value;return validate(p)
    reject('bool recording count',lambda:changed('allocation',{**a,'recordings':True}))
    reject('independent PC mirror removed',lambda:changed('allocation',{**a,'host_local_backup_per_recording':0}))
    reject('output one byte short',lambda:changed('combined_output_cap_bytes',policy['combined_output_cap_bytes']-1))
    reject('payload one byte short',lambda:changed('total_payload_cap_bytes',policy['total_payload_cap_bytes']-1))
    reject('traversal root',lambda:changed('manager_root',str(ROOT)+'/../field-runtime-v1'))
    reject('duplicate recording roots',lambda:changed('recording_roots',[policy['recording_roots'][0]]*4))
    reject('GPU enabled',lambda:changed('limits',{**LIMITS,'gpu':True}))
    reject('automatic capture',lambda:changed('limits',{**LIMITS,'automatic_capture':True}))
    reject('automatic replenishment',lambda:changed('storage_semantics',{**policy['storage_semantics'],'automatic_replenishment':True}))
    p=copy.deepcopy(policy);p['profiles']['d1-streaming-saved']['input_kind']='microphone'
    reject('saved mode relabeled live',lambda:validate(p))
    p2=copy.deepcopy(policy);p2['profiles']['d1-anonymous']=dict(available=False,input_kind='microphone',manifest_sha256=None,reason='Awaiting installed binding')
    validate(p2)
    reject('unavailable no fallback',lambda:issue_operation(p2,slot='recording-01',profile='d1-anonymous',owner=owner,now=now))
    reject('unknown profile',lambda:issue_operation(policy,slot='recording-01',profile='other',owner=owner,now=now))
    reject('601 second operation',lambda:issue_operation(policy,slot='recording-01',profile='d1-delayed',owner=owner,now=now,seconds=601))
    reject('bool operation seconds',lambda:issue_operation(policy,slot='recording-01',profile='d1-delayed',owner=owner,now=now,seconds=True))
    reject('expired operation',lambda:validate_operation(op,policy,now=now+timedelta(seconds=600)))
    reject('future operation',lambda:validate_operation(op,policy,now=now-timedelta(seconds=1)))
    reject('changed policy pin',lambda:validate_operation({**op,'policy_sha256':'f'*64},policy,now=now))
    reject('different source root',lambda:validate_operation({**op,'root':policy['recording_roots'][1]},policy,now=now))
    reject('bool native PID',lambda:validate_operation({**op,'owner':{**owner,'pid':True}},policy,now=now))
    reject('bad boot UUID',lambda:validate_operation({**op,'owner':{**owner,'boot_id':'-'*36}},policy,now=now))
    reject('old research operation',lambda:validate_operation(dict(issued_utc=now.isoformat(),expires_utc=op['expires_utc'],purpose='LOCAL_RELEASE_QUALIFICATION'),policy,now=now))
    active=copy.deepcopy(records);active['recording-02']['state']='FAILED_OPEN'
    reject('unclosed failed source',lambda:next_slot(policy,active))
    gap=copy.deepcopy(records);gap['recording-01']=None
    reject('deleted slot credit',lambda:next_slot(policy,gap))
    missing=copy.deepcopy(records);missing['recording-01']['local_backup_sha256']=None
    reject('PC pending cannot waive local copy',lambda:next_slot(policy,missing))
    exhausted={s:dict(state='CLOSED_LOCAL_BACKED',local_backup_sha256='d'*64,pc_backup_sha256=None) for s in a['recording_slots']}
    reject('finite exhausted',lambda:next_slot(policy,exhausted))
    result=dict(status='PASS_CHANGED_OFFLINE_RUNTIME_POLICY',positive_groups=3,rejects=rejected,
        full_four_recording_sixteen_launch_reservation=a['combined_request_bytes'],
        policy_sha256=digest(policy),native_executed=False,resource_admission_issued=False,
        synthetic_owner_profiles_counters=True,pc_copy_may_wait_but_local_copy_required=True)
    raw=(json.dumps(result,indent=2)+'\n').encode()
    with (args.output/'RESULT.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    assert (args.output/'RESULT.json').read_bytes()==raw
    print(json.dumps(dict(status=result['status'],positive_groups=3,rejects=len(rejected))))


if __name__=='__main__':
    main()
