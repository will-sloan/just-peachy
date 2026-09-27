"""Modes runner with explicit guarded provenance; README_GUARDED_BANK_V1.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from common import bind, freeze, load, verify
from guarded_execution_v1 import start_output, save_check
from metric_process import pin

PEAK = 280*1024**2


def collect_one(row, job, context, output, plan_binding, execution_binding, *, predict=None):
    if predict is None:
        from integrated_bank_v3 import predict_cell
        predict = predict_cell
    value = predict(row, job, context, output)
    freeze(output/'RESULT.json', dict(value, plan=plan_binding, execution_plan=execution_binding))
    return bind(output/'RESULT.json')


def run(args):
    pin(); pb = bind(args.plan); plan = load(pb['path'])
    if plan['scope'] != 'modes-panel' or plan['required'] != 1536 or plan['context'].get('reuse_review'):
        raise ValueError('Require the complete original 1,536-case modes plan without prefix reuse')
    guard = start_output(args.output, pb, 'method', 1536*1024**2, args.max_seconds)
    output = guard.output; eb = bind(output/'EXECUTION_PLAN.json'); completed=[]; checks=[]; started=False; current=None
    from integrated_bank_v3 import verify_plan
    from supervisor import lock, atomic
    try:
        with lock(guard.local/'n4/integrated-method-bank.owner.lock'), guard:
            checks.append(save_check(guard, 'GUARD_INITIAL.json', PEAK))
            plan = verify_plan(args.plan); jobs = {j['job_id']:j for j in plan['jobs']}
            for i, row in enumerate(plan['rows']):
                current=row['cell_id']; started=False; guard.fast_check(PEAK)
                cell=output/'cells'/f'{i:05d}';cell.mkdir(parents=True);started=True
                completed.append(collect_one(row,jobs[row['job_id']],plan['context'],cell,pb,eb));started=False
                atomic(output/'PROGRESS.json',dict(owner=guard.owner,completed=len(completed),required=1536,
                    utc=datetime.now(timezone.utc).isoformat(),integrated_N4_cells=0))
                if (i+1)%128 == 0:
                    checks.append(save_check(guard,f'GUARD_{i+1:05d}.json',PEAK));verify(pb)
                    print(f'Guarded modes {i+1}/1536',flush=True)
            checks.append(save_check(guard,'GUARD_FINAL.json'))
            for b in guard.code+[pb,eb]:verify(b)
            guard.fast_check(2*1024**2)
            freeze(output/'RESULT.json',dict(status='COLLECTED_METHOD_BANK_REQUIRES_REVIEW',
                utc=datetime.now(timezone.utc).isoformat(),owner=guard.owner,plan=pb,execution_plan=eb,
                admission=guard.admission,completed=len(completed),total=1536,failed=0,not_tested=0,
                cells=completed,guard_checks=checks,integrated_N4_cells=0))
    except BaseException as exc:
        freeze(output/'RESULT.json',dict(status='FAILED_PRESERVED',utc=datetime.now(timezone.utc).isoformat(),
            owner=guard.owner,plan=pb,execution_plan=eb,admission=guard.admission,completed=len(completed),
            total=1536,failed=int(started),not_tested=1536-len(completed)-int(started),
            failed_cell=current if started else None,blocked_before_cell=None if started else current,
            error=repr(exc),cells=completed,guard_checks=checks,integrated_N4_cells=0))
        raise


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-seconds',type=int,choices=range(60,14401),default=14400)
    run(p.parse_args())
