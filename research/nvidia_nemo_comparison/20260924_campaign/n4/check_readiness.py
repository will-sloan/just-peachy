"""Read exact upstream contracts and owners; never start or modify a job. README.md."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import json
from common import load,sha,freeze,bind

N2_CONTRACT='f77bd1f3b365b29a73882e11e8b8576fb9ca098f4c15b82f6c58307a78503a2a'
N2_CHAIN='aed20e2259722017bafaf6843304d33aa043a446f14692a20842c110f905fd9e'
N3_PLAN='60b6cef58fdb0f685f6bb74de9f13f5cd85e783910fcee592264881ac4bb4fe3'


def owner_state(owner):
    import psutil
    if not owner:return 'NO_RECORDED_OWNER'
    try:
        p=psutil.Process(owner['pid'])
        return 'ALIVE' if abs(p.create_time()-owner['create_time'])<.001 else 'PID_REUSED'
    except psutil.NoSuchProcess:return 'ABSENT'
    except (psutil.AccessDenied,KeyError,TypeError):return 'UNVERIFIED'


def inspect(local):
    n2=load(local/'n2/numerical-v2/RESULT.json')
    chain=load(local/'n2/numerical-v2/CHAIN_RESULT.json')
    queue=load(local/'n3/numerical-v2/QUEUE_RESULT.json')
    n3_path=local/'n3/numerical-v2/RESULT.json'
    n3=load(n3_path) if n3_path.exists() else {}
    plan_path=local/'n3/plan-v2.json';plan=load(plan_path)
    n2_owner=chain.get('external_coordinator',{}).get('child')
    contracts_match=(n2.get('contract_sha256')==N2_CONTRACT and chain.get('contract_sha256')==N2_CHAIN
                     and sha(plan_path)==N3_PLAN and queue.get('plan_sha256')==N3_PLAN)
    gates=[]
    if not contracts_match:gates.append('UPSTREAM_CONTRACT_CHANGED_REVIEW_REQUIRED')
    if not (n2.get('status')=='COMPLETE' and n2.get('completed')==422 and n2.get('total')==422
            and chain.get('status')=='READY_FOR_REVIEW'):
        gates.append('N2_MATCHED_NUMERICAL_FINAL_CHECKS_PENDING')
    if n3.get('status')!='READY_FOR_REVIEW':gates.append('N3_NUMERICAL_RESULTS_PENDING')
    # Numerical completion is not an interpretation or release acceptance.
    gates.append('N2_N3_FINAL_REVIEW_AND_N4_PROFILE_ADMISSION_NOT_RECORDED')
    return dict(status='NOT_ADMITTED',checked_utc=datetime.now(timezone.utc).isoformat(),
        contracts_match=contracts_match,gates=gates,
        n2=dict(status=n2.get('status'),completed=n2.get('completed'),total=n2.get('total'),
                owner=n2_owner,owner_state=owner_state(n2_owner),
                owner_matches_result_pid=bool(n2_owner and n2_owner['pid']==n2.get('pid')),
                chain_status=chain.get('status')),
        n3=dict(queue_status=queue.get('status'),queue_owner=queue.get('owner'),
                queue_owner_state=owner_state(queue.get('owner')),numerical_status=n3.get('status','NOT_STARTED')),
        n4=dict(inference_started=False,completed_core_cells=0,required_core_cells=7680,
                automatic_N4_queue_registered=False),
        packaging_cutoff_utc=plan['packaging_cutoff_utc'],
        upstream_files_modified=False,model_calls=0,hardware_calls=0,
        shared_ledger_modified=False,own_status_only=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local',type=Path,default=Path('G:/Just_Peachy_N1/20260924_campaign/local'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=inspect(args.local)
    freeze(args.output,result)
    print(json.dumps(result,indent=2))
