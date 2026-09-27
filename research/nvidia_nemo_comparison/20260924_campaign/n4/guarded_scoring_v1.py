"""Unchanged V3 metrics behind a fresh resource envelope; README_GUARDED_BANK_V1.md."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import time

from common import bind, freeze, load, verify
from guarded_execution_v1 import start_output, save_check, admit_method
from metric_process import MetricProcess, MetricProcessError, pin
from scoring_bank_v3 import prediction, unavailable, writer_lock
from scoring_report import report

HERE=Path(__file__).resolve().parent


def run(args):
    pin(); terminal=load(args.run/'RESULT.json');pb=terminal['plan'];verify(pb)
    g=start_output(args.output,pb,'scoring',512*1024**2,args.max_seconds,
        dict(terminal=bind(args.run/'RESULT.json'),review=bind(args.review),cell_timeout_seconds=args.cell_timeout))
    output=g.output;eb=bind(output/'EXECUTION_PLAN.json');rows=[];scores=[];checks=[];closures=[];client=None;stop=None
    try:
        with writer_lock(g.local/'n4/metric-scoring.owner.lock'),g:
            checks.append(save_check(g,'GUARD_INITIAL.json',32*1024**2))
            bundle=admit_method(args.run,args.review);plan=bundle['plan'];terminal=bundle['terminal']
            from probe_integrated_scoring import verify_environment
            env=load(HERE/'METRIC_ENVIRONMENT.json')['environment'];files=verify_environment(env)
            prep_binding=load(HERE/'PREPARATION_V2_CHECK.json')['preparation'];verify(prep_binding);prep=load(prep_binding['path'])
            tb=next(b for b in prep['inputs'] if Path(b['path']).name=='EVALUATOR_TRUTH.json')
            sb=next(b for b in prep['outputs'] if Path(b['path']).name=='EVALUATOR_STRATA.json')
            for b in (tb,sb):verify(b)
            if plan['context']['manifest']!=next(b for b in prep['outputs'] if Path(b['path']).name=='AUDIO_ONLY_480.json'):raise ValueError('Evaluator manifest differs')
            td,sd=load(tb['path']),load(sb['path']);truths={t['job_id']:t for t in td['cells']};strata={s['case_id']:s for s in sd['scenes']}
            if not td['NEVER_PASS_TO_RUNTIME'] or not sd['NEVER_PASS_TO_RUNTIME'] or len(truths)!=480 or len(td['cells'])!=480 or len(strata)!=240:raise ValueError('Evaluator boundary/census differs')
            freeze(output/'EVALUATOR.json',dict(environment=env,environment_files_verified=files,truth=tb,strata=sb,preparation=prep_binding))
            errors=0
            for i,row in enumerate(plan['rows']):
                job=bundle['jobs'][row['job_id']];truth=truths[row['job_id']];seconds=None;digest=None
                if truth['frames']!=job['frames'] or truth['tap']!=job['tap']:raise ValueError('Truth/audio geometry differs')
                if stop:score=unavailable(truth,'COMPLETE',stop)
                else:
                    try:
                        g.fast_check(32*1024**2)
                        if i and i%128==0:checks.append(save_check(g,f'GUARD_{i:05d}.json',32*1024**2))
                    except (ValueError,TimeoutError):stop='RESOURCE_OR_TIME_STOP';score=unavailable(truth,'COMPLETE',stop)
                    else:
                        before=time.monotonic()
                        try:
                            cell=terminal['cells'][i];verify(cell);pred=prediction(load(cell['path']),row,job)
                            if client is None:client=MetricProcess();client.start()
                            policy=load(g.policy_binding['path'])
                            reserve=(datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12)-datetime.now(timezone.utc)).total_seconds()
                            budget=min(args.cell_timeout,args.max_seconds-(time.monotonic()-g.started),reserve)
                            if budget<=0:raise MetricProcessError('TIME_BUDGET','Scoring cutoff reached')
                            response=client.score(truth,pred,timeout_seconds=budget)
                            score=response['score'];score['metric_status']='SCORED';digest=response['input_sha256'];errors=0
                        except (ValueError,KeyError,OSError,MetricProcessError) as exc:
                            reason=exc.status if isinstance(exc,MetricProcessError) else 'INPUT_VALIDATION_ERROR'
                            score=unavailable(truth,'COMPLETE',reason);errors+=1
                            if client is not None:closures.append(client.close());client=None
                            if errors>=3:stop='STOPPED_AFTER_THREE_CONSECUTIVE_METRIC_ERRORS'
                        seconds=time.monotonic()-before
                value=dict(cell_id=row['cell_id'],job_id=job['job_id'],case_id=truth['case_id'],tap=job['tap'],
                    composition=row['composition'],mode=row['contract']['mode'],score=score,method_result=terminal['cells'][i],
                    metric_input_sha256=digest,metric_seconds=seconds,execution_plan=eb,integrated_N4_cells=0)
                path=output/'cells'/f'{i:05d}.json';freeze(path,value);scores.append(bind(path));rows.append(value)
                if (i+1)%128==0:print(f'Guarded metrics {i+1}/{plan["required"]}',flush=True)
            if client is not None:closures.append(client.close());client=None
            summary=report(rows,strata,scope=plan['scope']);size=len(json.dumps(summary,ensure_ascii=False).encode())
            g.fast_check(size+8*1024**2);freeze(output/'REPORT.json',summary)
            checks.append(save_check(g,'GUARD_FINAL.json',4*1024**2))
            for b in g.code+[pb,eb,tb,sb,bundle['terminal_binding']]:verify(b)
            missing=sum(r['score']['metric_status']!='SCORED' for r in rows)
            freeze(output/'RESULT.json',dict(status='SCORED_MODELED_BANK_REQUIRES_REVIEW' if not missing else 'PARTIAL_MODELED_BANK_SCORING',
                utc=datetime.now(timezone.utc).isoformat(),admission=g.admission,execution_plan=eb,plan=pb,
                scores=scores,report=bind(output/'REPORT.json'),evaluator=bind(output/'EVALUATOR.json'),required=plan['required'],
                prediction_completed=terminal['completed'],prediction_failed=terminal['failed'],prediction_not_tested=terminal['not_tested'],
                metrics_unavailable_for_complete_predictions=missing,workers=closures,stop_reason=stop,guard_checks=checks,integrated_N4_cells=0))
    except BaseException as exc:
        if client is not None:closures.append(client.close())
        freeze(output/'FAILED.json',dict(status='FAILED_SCORING_PRESERVED',error_type=type(exc).__name__,reason=str(exc),
            admission=g.admission,execution_plan=eb,accounted=len(rows),required=load(pb['path'])['required'],
            unaccounted=load(pb['path'])['required']-len(rows),scores=scores,workers=closures,guard_checks=checks,integrated_N4_cells=0))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('run','review','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--max-seconds',type=int,choices=range(60,14401),default=14400)
    p.add_argument('--cell-timeout',type=int,choices=range(1,121),default=120)
    run(p.parse_args())
