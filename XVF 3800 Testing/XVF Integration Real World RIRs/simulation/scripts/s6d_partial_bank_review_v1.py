"""Inspect closed per-case transport inside an interrupted batch; see README."""
import argparse,datetime,json
from pathlib import Path
import s6d_closed_capture_review_v1 as A

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=R/'partial_bank_review_v1/MAIN_FIRST16_TRANSPORT.json')
    args=ap.parse_args();out=args.output.resolve()
    A.require(out.is_relative_to(R) and not out.exists(),'Fresh bounded report required')
    batch=R/'hardware_batches/bank_v2_P_MAIN6_B1'
    summary=A.read(batch/'SUMMARY.json')
    A.require(summary['status']=='BLOCKED' and summary['restoration']=='FAIL','Original failure must remain explicit')
    A.require(summary['executed_source_bytes_unchanged_after_batch'] is True,'Source epoch incomplete')
    planpath=R/'runner/bank_queue_v3/groups/P_MAIN6_B1/CAPTURE_PLAN.json'
    A.require(A.bind(planpath)['sha256']=='94de4e88acd2577956bc4dc715f3d6f0fd65fdce12572950e6fffaca0f85876e','Original plan changed')
    plan=A.read(planpath);attempts={x['attempt_id']:x for x in plan['attempts']}
    contract=A.read(R/'physical_preparation_v2/QUALIFICATION_ANALYSIS_CONTRACT.json')
    ledger=A.read(R/'physical_ledger.json');rows={x['attempt_id']:x for x in ledger['passes']}
    refs=summary['completed_attempts']
    wanted={f'P_MAIN6_S45_01_{n:02d}' for n in range(1,17)}
    A.require(len(refs)==16,'Exact16 completed references')
    results=[]
    for ref in refs:
        case=A.read(A.verify(ref)['path']);ident=case['attempt']['attempt_id']
        A.require(ident in wanted and rows[ident]['status']=='PASS' and rows[ident]['result']==ref,'Exact charged PASS provenance')
        results.append(A.inspect_case(ref,attempts[ident],contract['route_checks']['profiles']['P_MAIN6']))
    A.require({x['attempt_id'] for x in results}==wanted,'Exact16 unique cases')
    A.require(rows['P_MAIN6_S45_01_17']['status']=='FAIL','Failed attempt cannot be reclassified')
    receipt=dict(status='PER_CASE_TRANSPORT_VERIFIED_BATCH_RECOVERY_PENDING',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source=A.bind(__file__),readme=A.bind(Path(__file__).with_name('README_S6D_PARTIAL_BANK_REVIEW_V1.md')),inspection_dependency=A.bind(A.__file__),
        original_plan=A.bind(planpath),original_summary=A.bind(batch/'SUMMARY.json'),original_restoration=A.bind(batch/'restoration.json'),
        captures=16,attempts=results,batch_restoration_accepted=False,post_QA_complete=False,
        failed_attempt_preserved='P_MAIN6_S45_01_17',new_model_calls=0,hardware_calls=0,
        scope='Whole source/packed input/native framing/six derivatives/callbacks and per-case telemetry closure verified for16 existing PASS captures. Interrupted batch restoration and post-QA are separate unresolved gates; no final catalog or efficacy authority.')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=receipt['status'],captures=16,receipt=A.bind(out))))

if __name__=='__main__':main()

