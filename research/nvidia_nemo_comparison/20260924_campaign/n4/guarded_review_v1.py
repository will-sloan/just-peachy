"""Review guarded method/score lineage and full evidence; README_GUARDED_BANK_V1.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from common import bind, freeze, load, verify
from guarded_execution_v1 import start_output, save_check, validate_execution, admit_method
from metric_process import pin
from reservation_budget_v1 import require

HERE=Path(__file__).resolve().parent


def review_method(run, g, checks):
    from integrated_bank_v3 import verify_plan
    from scoring_bank_v3 import prediction
    from integrated_scoring_adapter_v3 import read_artifact
    v=validate_execution(run);result=v['result'];plan=verify_plan(result['plan']['path'])
    require(result['status']=='COLLECTED_METHOD_BANK_REQUIRES_REVIEW'
            and result['completed']==result['total']==len(result['cells'])==plan['required']
            and result['failed']==result['not_tested']==0,'Incomplete method bank')
    from controller_projection_v3 import validate_display_history
    jobs={j['job_id']:j for j in plan['jobs']};counts=dict(empty_hypotheses=0,raw_observations=0,final_utterances=0,displays=0)
    for i,(row,b) in enumerate(zip(plan['rows'],result['cells'])):
        g.fast_check();verify(b);cell=load(b['path'])
        require(cell['status']=='COMPLETE_MODELED_APPLICATION_METHODS_ONLY' and cell['controller_closed']
                and not cell['models_loaded'] and not cell['physical_widget_observed'] and not cell['integrated_N4_cells'], 'Method scope differs')
        prediction(cell,row,jobs[row['job_id']])
        pub=read_artifact(cell['outputs']['publication']);proj=read_artifact(cell['outputs']['projection'])
        validate_display_history(pub)
        require(proj['controller_closed'] and not proj['consumer_thread_alive'],'Controller closure differs')
        counts['empty_hypotheses']+=cell['empty_hypothesis']
        for key in ('raw_observations','final_utterances','displays'):counts[key]+=cell[key]
        if (i+1)%128==0:
            checks.append(save_check(g,f'GUARD_{i+1:05d}.json'))
            print(f'Guarded method review {i+1}/{plan["required"]}',flush=True)
    verify(v['terminal'])
    return dict(status='PASS_REVIEWED_MODELED_METHOD_BANK_ONLY',terminal=v['terminal'],plan=result['plan'],
        scope=plan['scope'],completed=plan['required'],counts=counts,all_full_artifacts_and_closures_verified=True,
        complete_Controller_parity=False,physical_widget_observed=False,models_loaded=0,integrated_N4_cells=0)


def review_scores(run, g, checks):
    from scoring_bank_v3 import prediction,verify_bindings
    from review_scoring_bank_v3 import validate_terminal,owners_closed,validate_row,verify_report
    from probe_integrated_scoring import verify_environment
    v=validate_execution(run,kind='scoring');r=v['result'];a=v['admission'];plan=load(a['plan']['path'])
    validate_terminal(r,plan);owners_closed(r['workers'],plan['required'])
    for b in (a['terminal'],a['review'],r['evaluator']):verify(b)
    bundle=admit_method(Path(a['terminal']['path']).parent,Path(a['review']['path']))
    require(bundle['terminal_binding']==a['terminal'] and bundle['terminal']['plan']==a['plan'],'Method/scoring join differs')
    e=load(r['evaluator']['path']);verify_bindings(e)
    known=load(HERE/'SCORING_BANK_IMPLEMENTATION_V1.json')
    require(e['environment']==known['environment'],'Metric environment differs')
    files=verify_environment(e['environment']);require(files==e['environment_files_verified']==known['environment_files_verified'],'Environment census differs')
    prep=load(e['preparation']['path'])
    require(e['preparation']==load(HERE/'PREPARATION_V2_CHECK.json')['preparation']
            and e['truth']==next(b for b in prep['inputs'] if Path(b['path']).name=='EVALUATOR_TRUTH.json')
            and e['strata']==next(b for b in prep['outputs'] if Path(b['path']).name=='EVALUATOR_STRATA.json')
            and plan['context']['manifest']==next(b for b in prep['outputs'] if Path(b['path']).name=='AUDIO_ONLY_480.json'),'Evaluator preparation differs')
    td,sd=load(e['truth']['path']),load(e['strata']['path']);truths={t['job_id']:t for t in td['cells']};strata={s['case_id']:s for s in sd['scenes']}
    require(td['NEVER_PASS_TO_RUNTIME'] is True and sd['NEVER_PASS_TO_RUNTIME'] is True
            and len(truths)==len(td['cells'])==480 and len(strata)==len(sd['scenes'])==240,'Evaluator census differs')
    rows=[]
    for i,(row,b) in enumerate(zip(plan['rows'],r['scores'])):
        g.fast_check();require(Path(b['path'])==run/'cells'/f'{i:05d}.json','Score order differs');verify(b);value=load(b['path'])
        require(value['execution_plan']==v['execution_plan'],'Score execution provenance differs')
        method=bundle['terminal']['cells'][i];job=bundle['jobs'][row['job_id']]
        pred=prediction(load(method['path']),row,job);validate_row(value,row,job,truths[job['job_id']],pred,method);rows.append(value)
        if (i+1)%128==0:
            checks.append(save_check(g,f'GUARD_{i+1:05d}.json'))
            print(f'Guarded score review {i+1}/{plan["required"]}',flush=True)
    verify(r['report']);require(Path(r['report']['path'])==run/'REPORT.json','Foreign report')
    digest=verify_report(load(r['report']['path']),rows,strata,plan['scope'])
    verify(v['terminal']);owners_closed(r['workers'],plan['required'])
    return dict(status='PASS_REVIEWED_MODELED_SCORING_ONLY',scoring_result=v['terminal'],plan=a['plan'],method_review=a['review'],
        report=r['report'],report_content_sha256=digest,reviewed=len(rows),required=plan['required'],scope=plan['scope'],
        all_metric_inputs_and_report_totals_verified=True,metric_alignment_recomputed=False,environment_files_verified=files,
        models_loaded=0,integrated_N4_cells=0,physical_widget_observed=False,N4_accepted=False)


def run(args):
    pin();root=args.run.resolve(strict=True);r=load(root/'RESULT.json')
    pb=r.get('plan') or load(r['admission']['path'])['plan'];verify(pb)
    g=start_output(args.output,pb,args.kind,8*1024**2,args.max_seconds,dict(reviewed_terminal=bind(root/'RESULT.json')))
    checks=[]
    try:
        with g:
            checks.append(save_check(g,'GUARD_INITIAL.json'))
            value=(review_method if args.kind=='method-review' else review_scores)(root,g,checks)
            checks.append(save_check(g,'GUARD_FINAL.json'))
            for b in g.code+[pb]:verify(b)
            g.fast_check()
            freeze(g.output/'RESULT.json',dict(value,utc=datetime.now(timezone.utc).isoformat(),admission=g.admission,
                execution_plan=bind(g.output/'EXECUTION_PLAN.json'),guard_checks=checks))
    except BaseException as exc:
        freeze(g.output/'FAILED.json',dict(status='FAILED_GUARDED_REVIEW_PRESERVED',admission=g.admission,
            error_type=type(exc).__name__,reason=str(exc),guard_checks=checks,integrated_N4_cells=0))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=['method-review','score-review'],required=True)
    for n in ('run','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--max-seconds',type=int,choices=range(60,7201),default=7200)
    run(p.parse_args())
