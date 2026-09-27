"""Supervised saved-evidence parity and resource check; README_GUARDED_BANK_V1.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from common import bind,freeze,load,verify,fingerprint
from guarded_execution_v1 import OWN,code_bindings,start_output,save_check,check_cell
from guarded_method_bank_v1 import collect_one
from metric_process import MetricProcess,pin

HERE=Path(__file__).resolve().parent


class PinnedMetric(MetricProcess):
    def _command(self):
        return [str(HERE.parents[4]/'local/n4/metrics/env/Scripts/python.exe'),'-B',str(HERE/'metric_process.py'),'--worker',self.nonce]


def run(args):
    pin();pb=bind(args.plan);plan=load(pb['path'])
    if plan['scope']!='modes-panel' or plan['required']!=1536:raise ValueError('Exact modes plan required')
    g=start_output(args.output,pb,'probe',512*1024**2,3600,development=True)
    checks=[];boundaries=[];client=None;closures=[];tests=None
    try:
        with g:
            for name in OWN:
                dst=g.output/'source'/name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(HERE/name,dst)
            # Temporary synthetic admissions are removed by their own context before the complete census.
            temp=g.output/'temporary';temp.mkdir();tempfile.tempdir=str(temp)
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in
                ['test_reservation_guard_v1','test_reservation_guard_closure_v2','test_guarded_bank_v1','test_scoring_review_v3'])
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            (g.output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            if not tests.wasSuccessful():raise ValueError('Guarded family regression failed')
            checks.append(save_check(g,'GUARD_INITIAL.json',280*1024**2))
            from integrated_bank_v3 import verify_plan,predict_cell
            from scoring_bank_v3 import prediction
            from review_scoring_bank_v3 import validate_score
            plan=verify_plan(args.plan);jobs={j['job_id']:j for j in plan['jobs']}
            selected=[]
            for composition in ['A0_D0_E0','A0_D0_E1','A3_D1_E0','A3_D1_E1']:
                for mode in ['anonymous_conversation','enrolled_names','selected_focus','selected_closed']:
                    selected.append(next(r for r in plan['rows'] if r['composition']==composition and r['contract']['mode']==mode))
            prep=load(load(HERE/'PREPARATION_V2_CHECK.json')['preparation']['path'])
            tb=next(b for b in prep['inputs'] if Path(b['path']).name=='EVALUATOR_TRUTH.json');verify(tb)
            truths={r['job_id']:r for r in load(tb['path'])['cells']};eb=bind(g.output/'EXECUTION_PLAN.json')
            client=PinnedMetric();client.start()
            for i,row in enumerate(selected):
                g.fast_check(280*1024**2);job=jobs[row['job_id']];root=g.output/'boundaries'/f'{i:02d}'
                old=root/'original';new=root/'guarded';old.mkdir(parents=True);new.mkdir()
                original=predict_cell(row,job,plan['context'],old)
                freeze(old/'RESULT.json',dict(original,plan=pb))
                nb=collect_one(row,job,plan['context'],new,pb,eb);value=load(nb['path']);check_cell(value,row,pb,eb)
                before=prediction(load(old/'RESULT.json'),row,job);after=prediction(value,row,job)
                if before!=after:raise ValueError('Guard wrapper changed numerical prediction')
                # Evaluator truth is only passed here, after both prediction calls completed.
                responses=[client.score(truths[job['job_id']],pred,timeout_seconds=120) for pred in (before,after)]
                if responses[0]['score']!=responses[1]['score'] or responses[0]['input_sha256']!=responses[1]['input_sha256']:
                    raise ValueError('Metric parity differs')
                score=responses[1]['score'];score['metric_status']='SCORED';validate_score(score,truths[job['job_id']],after)
                freeze(root/'PARITY.json',dict(cell_id=row['cell_id'],original=bind(old/'RESULT.json'),guarded=nb,
                    prediction_sha256=fingerprint(after),metric_input_sha256=responses[1]['input_sha256'],
                    score_sha256=fingerprint(score),prediction_equal=True,metrics_equal=True,models_loaded=0,N4_accepted=False))
                boundaries.append(bind(root/'PARITY.json'));print(f'Guarded parity {i+1}/16',flush=True)
            closures.append(client.close());client=None
            checks.append(save_check(g,'GUARD_FINAL.json'))
            for b in g.code+[pb,*boundaries]:verify(b)
            g.fast_check()
            freeze(g.output/'RESULT.json',dict(status='PASS_GUARDED_V3_MODELED_FAMILY_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                owner=g.owner,admission=g.admission,code=g.code,source_snapshots=[bind(g.output/'source'/n) for n in OWN],
                tests=bind(g.output/'tests.txt'),tests_passed=tests.testsRun,boundaries=boundaries,workers=closures,guard_checks=checks,
                supervised_serialized_scope_checked=True,original_prediction_and_metric_code_unchanged=True,
                method_reviewer_and_score_reviewer_still_required=True,GUI_family_qualified=False,models_loaded=0,integrated_N4_cells=0,N4_accepted=False,N5_complete=False))
    except BaseException as exc:
        if client is not None:closures.append(client.close())
        freeze(g.output/'FAILED.json',dict(status='FAILED_GUARDED_FAMILY_PROBE_PRESERVED',owner=g.owner,admission=g.admission,
            error_type=type(exc).__name__,reason=str(exc),tests_run=tests.testsRun if tests else None,boundaries=boundaries,
            workers=closures,guard_checks=checks,N4_accepted=False,N5_complete=False))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('plan','output'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
