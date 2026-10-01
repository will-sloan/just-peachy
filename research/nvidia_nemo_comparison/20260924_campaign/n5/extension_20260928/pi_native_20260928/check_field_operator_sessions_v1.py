"""Changed pure session checks; README_FIELD_OPERATOR_SESSIONS_V1.md."""
import sys
sys.dont_write_bytecode=True
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from pathlib import Path
import json
import time
from datetime import datetime,timezone,timedelta

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(exist_ok=False)
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    (out/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
    from field_operator_session_plan_v1 import allocation,validate_policy,state,next_slot,rebase
    start=time.monotonic();rejects=[]
    def reject(label,call):
        try:call()
        except (ValueError,TypeError,RuntimeError,KeyError):rejects.append(label)
        else:raise AssertionError('Accepted invalid '+label)
    for n in (0,5,True,1.0,'2'):
        reject('count-'+repr(n),lambda n=n:allocation(n))
    plan=allocation(4);records={name:{} for name in plan['slot_names']}
    assert next_slot(plan,records)=='slot-01'
    records['slot-01']={'RESERVED':{}}
    reject('active-session',lambda:next_slot(plan,records))
    records['slot-01']['FAILED']={}
    reject('unclosed-failure',lambda:next_slot(plan,records))
    records['slot-01']['RECOVERED']={}
    assert next_slot(plan,records)=='slot-02'
    records['slot-02']={key:{} for key in ('RESERVED','STAGED','STARTED','CLOSED')}
    assert next_slot(plan,records)=='slot-03'
    for name in ('slot-03','slot-04'):records[name]=dict(records['slot-02'])
    reject('all-consumed-including-failure',lambda:next_slot(plan,records))
    reject('unreserved-close',lambda:state({'CLOSED':{}}))
    reject('start-before-stage',lambda:state({'RESERVED':{},'STARTED':{}}))
    reject('failed-success',lambda:state({**records['slot-02'],'FAILED':{}}))
    reject('unfailed-recovery',lambda:state({'RESERVED':{},'RECOVERED':{}}))
    reject('unknown-state',lambda:state({'IGNORED':{}}))
    reject('missing-slot',lambda:next_slot(plan,{}))
    gap={name:{} for name in plan['slot_names']};gap['slot-02']=dict(records['slot-02'])
    reject('reservation-gap',lambda:next_slot(plan,gap))
    now=datetime.now(timezone.utc)
    policy=dict(schema='just-peachy.operator-session-policy.v1',
        root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-operator-sessions-v1',
        issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=500)).isoformat(),
        allocation=plan,combined_output_cap_bytes=10**10,total_payload_cap_bytes=10**11,
        mode='delayed',release_manifest_sha256='0'*64,boot_id='00000000-0000-0000-0000-000000000000',
        host_window_bytes=2000,target_before_bytes=1000,payload_before_bytes=5000)
    assert validate_policy(policy,now)==policy
    for key,value in [('mode','streaming'),('root',policy['root']+'/../field-operator-sessions-v2'),
                       ('combined_output_cap_bytes',plan['combined_request_bytes']+1),
                       ('total_payload_cap_bytes',plan['combined_request_bytes']+1),
                       ('host_window_bytes',True),('expires_utc',(now+timedelta(seconds=601)).isoformat())]:
        reject(key,lambda key=key,value=value:validate_policy({**policy,key:value},now))
    altered={**plan,'host_maximum_bytes':plan['host_maximum_bytes']-1}
    reject('mirror-allocation-reduction',lambda:validate_policy({**policy,'allocation':altered},now))
    old='/old/root';new='/new/root';original={'path':old+'/code/a.py','digest':'0'*64,
        'text':'mentions '+old+'/code/a.py','other':old+'-suffix'}
    moved=rebase(original,old,new)
    assert moved=={**original,'path':new+'/code/a.py'} and original['path']==old+'/code/a.py'
    reject('rebase-traversal',lambda:rebase(original,old,'/new/../unsafe'))
    result=dict(status='PASS_PURE_SESSION_ALLOCATION_STATE_CONTRACT',rejects=rejects,
        positive_groups=['four-independent-slots','failure-consumes-reservation',
            'closed-session-next-slot','measured-policy','root-value-only-rebase'],
        proposed_allocation=plan,native_ledger_constructed=False,native_dispatch=False,
        fixture_boot_and_digest_only=True,seconds=time.monotonic()-start,owner=owner)
    raw=json.dumps(result,indent=2).encode();assert len(raw)<16384
    (out/'RESULT.json').open('xb').write(raw)
    print(json.dumps(dict(status=result['status'],rejects=len(rejects),seconds=result['seconds'])))
if __name__=='__main__':main()
