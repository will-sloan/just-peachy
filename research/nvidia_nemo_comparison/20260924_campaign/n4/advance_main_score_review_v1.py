"""One guarded scoring-to-review handoff. README_SCORE_REVIEW_ADVANCE_V1.md."""
import argparse
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import shutil
import time

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from review_scoring_bank import require
from review_scoring_bank_v3 import guard, shared_allowance, owners_closed, validate_terminal
from scoring_bank_v3 import writer_lock, verify_bindings, qualification as scoring_qualification

HERE = Path(__file__).resolve().parent
LOCAL = HERE.parents[4] / 'local'
OWN = ('advance_main_score_review_v1.py', 'test_score_review_advance_v1.py',
       'README_SCORE_REVIEW_ADVANCE_V1.md')
QUALIFICATION = 'SCORE_REVIEW_ADVANCE_CHECK_V1.json'


def code_bindings():
    return [bind(HERE/n) for n in OWN + ('common.py', 'metric_process.py',
        'scoring_bank_v3.py', 'review_scoring_bank_v3.py')] + [bind(HERE.parent/'supervision/supervisor.py')]


def ready(watch, worker, lookup=exact_process):
    """No dispatch until the same successful host, launcher and driver all exit."""
    require(worker['run_id'] == watch['run_id'], 'Supervisor ownership changed')
    require(dict(pid=worker['pid'], create_time=worker['create_time']) == watch['supervisor'],
            'Supervisor identity changed')
    require(dict(pid=worker.get('child_pid'), create_time=worker.get('child_create_time')) == watch['launcher'],
            'Launcher identity changed')
    require(worker.get('child_launch_pending') is False, 'Unresolved child launch')
    if worker['status'] in ('STARTING', 'RUNNING'):
        require(0 <= time.time()-worker['heartbeat_unix'] < 120, 'Scoring supervision heartbeat stale')
        require(lookup(watch['supervisor']) is not None, 'Active supervision owner disappeared')
        return False
    require(worker['status'] == 'COMPLETED' and worker.get('exit_code') == 0,
            'Scoring did not finish successfully')
    return all(lookup(watch[key]) is None for key in ('supervisor', 'launcher', 'driver'))


def validate_success(result, admission_binding, plan, score_root):
    validate_terminal(result, plan)
    require(plan['scope'] == 'main' and plan['required'] == 7680
            and result['required'] == 7680, 'Complete main population required')
    require(result['admission'] == admission_binding and result.get('stop_reason') is None,
            'Scoring admission or stop reason differs')
    require(result['prediction_completed'] == 7680 and result['prediction_failed'] == 0
            and result['prediction_not_tested'] == 0
            and result['metrics_unavailable_for_complete_predictions'] == 0,
            'Scoring has failed, missing or untested rows')
    require(all(Path(b['path']) == score_root/'cells'/f'{i:05d}.json'
                for i,b in enumerate(result['scores'])), 'Score order or location differs')
    require(Path(result['report']['path']) == score_root/'REPORT.json', 'Foreign scoring report')


def qualification():
    qb=bind(HERE/QUALIFICATION); q=load(qb['path'])
    require(q['status']=='PASS_SCORE_REVIEW_ADVANCE_DEVELOPMENT_ONLY' and q['code']==code_bindings(),
            'Handoff source is not qualified')
    verify(q['private_receipt']); r=load(q['private_receipt']['path'])
    require(r['passed'] is True and r['tests_run']==q['tests_passed'] and r['code']==q['code']
            and exact_process(r['owner']) is None, 'Handoff test owner remains active or tests differ')
    verify_bindings(q); return qb


def run(output):
    process=pin(); started=time.monotonic(); state=LOCAL/'supervision'
    score_root=LOCAL/'n4/integrated-main-scores-v3'
    target=LOCAL/'n4/integrated-main-score-review-v3'
    require(not output.exists() and output.resolve().is_relative_to((LOCAL/'n4').resolve()),
            'Fresh private handoff output required')
    with writer_lock(LOCAL/'n4/main-score-review-advance.owner.lock'):
        qb=qualification(); sq=scoring_qualification(); worker=load(state/'worker.json')
        specb=bind(LOCAL/'n4/integrated-main-scoring-worker-v3.json'); spec=load(specb['path'])
        require(load(state/'worker_spec.json')==spec and worker['status']=='RUNNING',
                'Expected active scoring worker required')
        ab=bind(score_root/'ADMISSION.json'); a=load(ab['path']); verify_bindings(a)
        require(a['qualification']==sq and a['maximum_output_bytes']==512*1024**2,
                'Scoring qualification or bound differs')
        watch=dict(run_id=worker['run_id'], supervisor=dict(pid=worker['pid'],create_time=worker['create_time']),
            launcher=dict(pid=worker['child_pid'],create_time=worker['child_create_time']),driver=a['owner'])
        launcher=exact_process(watch['launcher']); driver=exact_process(watch['driver'])
        require(launcher is not None and driver is not None and launcher.cmdline()==spec['argv']
                and launcher.ppid()==watch['supervisor']['pid'] and driver.ppid()==launcher.pid,
                'Actual scoring launcher/driver ancestry differs')
        require(all(exact_process(watch[k]).cpu_affinity()==[14] for k in watch if k!='run_id'),
                'Scoring owner affinity changed')
        require(not target.exists(), 'Preserve existing review')
        guard(output,LOCAL,started,18000); resources=shared_allowance(LOCAL)
        freeze(output/'ADMISSION.json',dict(utc=datetime.now(timezone.utc).isoformat(),owner=identity(process),
            watch=watch,scoring_admission=ab,scoring_spec=specb,qualification=qb,scoring_qualification=sq,
            code=code_bindings(),resources=resources,maximum_seconds=18000,poll_seconds=60,
            maximum_output_bytes=8*1024**2,N4_accepted=False))
        for name in OWN:
            (output/'source').mkdir(exist_ok=True); shutil.copyfile(HERE/name,output/'source'/name)
        dispatched=False
        try:
            while True:
                guard(output,LOCAL,started,18000)
                verify(ab); verify(specb); verify(qb)
                require(load(state/'worker_spec.json')==spec, 'Another worker replaced the scorer')
                worker=load(state/'worker.json')
                if ready(watch,worker): break
                time.sleep(60)
            verify_bindings(a); plan=load(a['plan']['path']); resultb=bind(score_root/'RESULT.json')
            result=load(resultb['path']); validate_success(result,ab,plan,score_root)
            owners_closed(result['workers'],7680)
            for b in result['scores']+[result['report']]: verify(b)
            verify(resultb); qualification(); scoring_qualification(); shared_allowance(LOCAL)
            guard(output,LOCAL,started,18000)
            require(not target.exists(), 'Review appeared before dispatch; preserve it')
            # Recheck after the potentially long hash/inventory interval. The
            # supervisor also holds its own writer/lifetime locks during start.
            require(ready(watch,load(state/'worker.json')) and load(state/'worker_spec.json')==spec,
                    'Scoring ownership changed before review dispatch')
            for name in ('worker.json','worker_spec.json','worker.log','campaign.json'):
                shutil.copyfile(state/name,output/('PREVIOUS_'+name))
            argv=[str(LOCAL/'n4/metrics/env/Scripts/python.exe'),'-B',str(HERE/'review_scoring_bank_v3.py'),
                  '--run',str(score_root),'--output',str(target)]
            nextspec=output/'review_worker.json'; freeze(nextspec,dict(argv=argv,cwd=str(HERE.parents[3])))
            module_spec=importlib.util.spec_from_file_location('jp_score_review_supervisor',HERE.parent/'supervision/supervisor.py')
            module=importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
            freeze(output/'READY.json',dict(utc=datetime.now(timezone.utc).isoformat(),scoring_result=resultb,
                scoring_admission=ab,review_spec=bind(nextspec),all_exact_scoring_owners_exited=True,N4_accepted=False))
            dispatched=True  # Any ambiguous start is preserved, never retried.
            record=module.start(state,nextspec)
            freeze(output/'RESULT.json',dict(status='DISPATCHED_INDEPENDENT_MAIN_SCORE_REVIEW',
                utc=datetime.now(timezone.utc).isoformat(),scoring_result=resultb,review_spec=bind(nextspec),
                supervisor_start=record,review_passed=False,N4_accepted=False,N5_complete=False))
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='SCORE_REVIEW_HANDOFF_STOPPED_PRESERVED',
                utc=datetime.now(timezone.utc).isoformat(),error_type=type(exc).__name__,reason=str(exc),
                dispatch_attempted=dispatched,N4_accepted=False))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
