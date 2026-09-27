"""Retest the five sealed metric timeouts. See README_METRIC_TIMEOUT_RETEST_V1.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from common import bind, fingerprint, freeze, load, verify
from metric_process import MetricProcess, MetricProcessError, exact_process, identity, pin
from scoring_bank_v3 import admit, prediction, qualification, verify_bindings, writer_lock
from review_scoring_bank_v3 import (code_bindings as review_code, guard, owners_closed,
                                    require, shared_allowance, validate_row)

HERE=Path(__file__).resolve().parent
EXPECTED=(888,889,1417,1424,6568)


def code_bindings():
    return review_code()+[bind(HERE/n) for n in
        ('retest_metric_timeouts_v1.py','README_METRIC_TIMEOUT_RETEST_V1.md')]


def run(output):
    process=pin(); started=time.monotonic(); local=HERE.parents[4]/'local'
    parent=local/'n4/integrated-main-scores-v3'
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()),
            'Fresh private N4 retest output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        qb=qualification(); q=load(qb['path']); rb=bind(parent/'RESULT.json'); result=load(rb['path'])
        verify(result['admission']); admission=load(result['admission']['path'])
        require(exact_process(admission['owner']) is None, 'Original scorer remains active')
        owners_closed(result['workers'],7680)
        require(result['status']=='PARTIAL_MODELED_BANK_SCORING' and result['stop_reason'] is None
            and result['required']==result['prediction_completed']==len(result['scores'])==7680
            and result['prediction_failed']==result['prediction_not_tested']==0
            and result['metrics_unavailable_for_complete_predictions']==5,
            'Only the exact complete-prediction five-timeout parent is supported')
        require(admission['qualification']==qb and admission['code']==q['scoring_code']
                and admission['cell_timeout_seconds']==60, 'Parent scorer/configuration differs')
        verify_bindings(admission)
        failed=[]
        for i,b in enumerate(result['scores']):
            require(Path(b['path'])==parent/'cells'/f'{i:05d}.json','Foreign score order or location')
            verify(b); row=load(b['path'])
            if row['score']['metric_status']!='SCORED':
                require(row['score']['metric_status']=='TIMEOUT'
                    and row['score']['execution_status']=='COMPLETE', 'Unexpected non-timeout failure')
                failed.append((i,b,row))
        require(tuple(i for i,_,_ in failed)==EXPECTED, 'Missing/foreign timeout population')
        bundle=admit(Path(admission['terminal']['path']).parent,Path(admission['review']['path']))
        require(bundle['terminal_binding']==admission['terminal']
                and bundle['terminal']['plan']==admission['plan'], 'Parent method join differs')
        from probe_integrated_scoring import verify_environment
        require(verify_environment(admission['environment'])==admission['environment_files_verified'],
                'Metric environment changed')
        truths={r['job_id']:r for r in load(admission['truth']['path'])['cells']}
        require(len(truths)==480 and load(admission['truth']['path'])['NEVER_PASS_TO_RUNTIME'] is True,
                'Evaluator-only complete truth required')
        guard(output,local,started,1200); resources=shared_allowance(local); code=code_bindings()
        freeze(output/'ADMISSION.json',dict(owner=identity(process),parent_result=rb,
            parent_admission=result['admission'],code=code,qualification=qb,resources=resources,
            indices=list(EXPECTED),cell_timeout_seconds=120,maximum_seconds=1200,
            maximum_output_bytes=8*1024**2,cpu_affinity=process.cpu_affinity(),N4_accepted=False))
        client=None; closures=[]; checked=[]; failures=[]
        try:
            for i,previous,old in failed:
                guard(output,local,started,1200);verify(previous)
                row=bundle['plan']['rows'][i];job=bundle['jobs'][row['job_id']]
                method=bundle['terminal']['cells'][i];verify(method)
                require(old['method_result']==method and old['cell_id']==row['cell_id'],
                        'Timeout method provenance differs')
                pred=prediction(load(method['path']),row,job);truth=truths[job['job_id']]
                input_digest=fingerprint(dict(truth=truth,prediction=pred))
                before=time.monotonic();print(f'Retesting {i:05d} at 120 seconds',flush=True)
                try:
                    if client is None:client=MetricProcess();client.start()
                    response=client.score(truth,pred,timeout_seconds=120)
                    require(response['input_sha256']==input_digest,'Retest input digest differs')
                    score=response['score'];score['metric_status']='SCORED'
                    value=dict(old,score=score,metric_input_sha256=input_digest,
                               metric_seconds=time.monotonic()-before)
                    validate_row(value,row,job,truth,pred,method)
                    path=output/'cells'/f'{i:05d}.json';freeze(path,value)
                    checked.append(dict(index=i,previous=previous,score=bind(path),input_sha256=input_digest,
                                        elapsed_seconds=value['metric_seconds']))
                    print(f'PASS {i:05d}',flush=True)
                except MetricProcessError as exc:
                    if client is not None:closures.append(client.close());client=None
                    record=dict(index=i,previous=previous,method_result=method,input_sha256=input_digest,
                        metric_status=exc.status,elapsed_seconds=time.monotonic()-before)
                    freeze(output/'failed-cells'/f'{i:05d}.json',record);failures.append(record)
                    print(f'PRESERVED {i:05d} {exc.status}',flush=True)
            if client is not None:closures.append(client.close());client=None
            owners_closed(closures,5);guard(output,local,started,1200);shared_allowance(local)
            for b in code+[rb,result['admission'],admission['truth']]:verify(b)
            freeze(output/'RESULT.json',dict(status='PASS_FIVE_TIMEOUT_RETESTS_ONLY' if not failures
                else 'PARTIAL_FIVE_TIMEOUT_RETESTS_PRESERVED',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),parent_result=rb,checked=checked,failures=failures,
                required=5,scored=len(checked),workers=closures,elapsed_seconds=time.monotonic()-started,
                original_metric_implementation_unchanged=True,original_prediction_artifacts_reused=True,
                full_scoring_bank_repaired=False,independent_full_score_review_completed=False,
                N4_accepted=False,N5_complete=False))
        except BaseException as exc:
            if client is not None:closures.append(client.close())
            freeze(output/'FAILED.json',dict(status='FAILED_TIMEOUT_RETEST_PRESERVED',
                error_type=type(exc).__name__,reason=str(exc),admission=bind(output/'ADMISSION.json'),
                checked=checked,failures=failures,workers=closures,N4_accepted=False))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
