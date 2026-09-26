"""Preserve and test the full-history boundary. README_INTEGRATED_HISTORY_V3.md."""
import argparse
from datetime import datetime,timezone,timedelta
import io
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from paced_slot import process_census
from scoring_bank import writer_lock,verify_bindings
from review_scoring_bank import shared_allowance
from integrated_bank_plan_v3 import code_bindings

HERE=Path(__file__).resolve().parent


def failure_details(exc):
    details=[];tb=exc.__traceback__
    while tb:
        f=tb.tb_frame;v=f.f_locals
        if f.f_code.co_name=='put' and hasattr(v.get('self'),'bytes'):
            details.append(dict(function='put',publication_bytes=v['self'].bytes,
                                events_already_recorded=len(v['self'].rows)))
        if f.f_code.co_name=='save_private' and isinstance(v.get('text'),bytes):
            details.append(dict(function='save_private',expanded_bytes=len(v['text']),limit=v.get('limit')))
        tb=tb.tb_next
    return dict(error_type=type(exc).__name__,error=str(exc),limits=details)


def guard(output,local,started,seconds):
    if time.monotonic()-started>=seconds:raise TimeoutError('Probe time budget reached')
    policy=load(local/'supervision/campaign.json')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    for drive,floor in [('C:/',50),('G:/',75)]:
        if shutil.disk_usage(drive).free<floor*1024**3+256*1024**2:raise ValueError('Probe drive reserve unavailable')
    if output.exists() and sum(p.stat().st_size for p in output.rglob('*') if p.is_file())>256*1024**2:
        raise ValueError('Probe output budget reached')


def run(output):
    process=pin();started=time.monotonic()
    local=Path('G:/Just_Peachy_N1/20260924_campaign/local')
    terminal_binding=bind(local/'n4/integrated-main-v2/RESULT.json');terminal=load(terminal_binding['path'])
    if exact_process(terminal['owner']) is not None:raise ValueError('Original method worker remains active')
    worker=load(local/'supervision/worker.json')
    if exact_process(dict(pid=worker['pid'],create_time=worker['create_time'])) is not None:
        raise ValueError('Original supervisor remains active')
    verify(terminal['plan']);plan=load(terminal['plan']['path']);verify_bindings(plan['context'])
    if terminal['completed']!=1382 or terminal['error']!="ValueError('Publication trace budget exceeded')":
        raise ValueError('Unexpected original failure')
    source=load(plan['context']['source_receipt']['path']);root=Path(source['prototype'])
    for rel,b in source['files'].items():verify(dict(path=str(root/rel),**b))
    sys.path[:0]=[str(root),str(root/'vendor')]
    if output.exists() or not output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,1200);inventory=shared_allowance(local);code=code_bindings()
        if inventory['total_logical_bytes']+6*1024**3+256*1024**2>50*1024**3:raise ValueError('Shared probe allowance unavailable')
        freeze(output/'ADMISSION.json',dict(owner=identity(process),terminal=terminal_binding,plan=terminal['plan'],
            code=code,inventory=inventory,census=process_census(local),max_seconds=1200,max_output_bytes=256*1024**2,models_loaded=0,integrated_N4_cells=0))
        for b in code:
            path=output/'sources'/Path(b['path']).name;path.parent.mkdir(exist_ok=True)
            if path.exists():raise ValueError('Duplicate source basename')
            shutil.copyfile(b['path'],path)
        tests=None;checks=[]
        try:
            from integrated_bank_v2 import predict_cell as original_predict,WORKERS
            from integrated_bank_v3 import predict_cell
            from method_artifact_v3 import read_replay
            jobs={j['job_id']:j for j in plan['jobs']};row=plan['rows'][terminal['completed']]
            failed=output/'original-reproduction';failed.mkdir()
            try:original_predict(row,jobs[row['job_id']],plan['context'],failed)
            except ValueError as exc:
                detail=failure_details(exc)
                if str(exc)!='Publication trace budget exceeded':raise
                freeze(output/'ORIGINAL_FAILURE.json',detail)
            else:raise ValueError('Original failure did not reproduce')
            if any(t.name in WORKERS for t in threading.enumerate()):raise ValueError('Original failed replay leaked worker')
            # First repair the exact production boundary before broad development checks.
            selected=[r for r in plan['rows'] if r['job_id'] in ('N2_S45_03_04_O0','N2_S45_03_04_O1')
                      and r['contract']['variant']=='A1' and r['contract']['diarization']=='D1']
            # Add the largest sealed A1 input-event file, without reading evaluator truth.
            candidates={r['parents'][0]['result']['path']:r['parents'][0]['result'] for r in plan['rows'] if r['contract']['variant']=='A1'}
            largest=max((load(b['path']) for b in candidates.values()),key=lambda c:c['events_expanded']['uncompressed_bytes'])['job']['job_id']
            selected += [r for r in plan['rows'] if r['job_id']==largest and r['contract']['variant']=='A1'
                         and r['contract']['diarization']=='D1' and r not in selected]
            for i,row in enumerate(selected):
                guard(output,local,started,1200);path=output/'boundaries'/f'{i:02d}';path.mkdir(parents=True)
                result=predict_cell(row,jobs[row['job_id']],plan['context'],path)
                pub=read_replay(result['outputs']['publication']);proj=read_replay(result['outputs']['projection'])
                if not result['controller_closed'] or pub['worker_counts']['thread_alive'] or proj['consumer_thread_alive']:
                    raise ValueError('Boundary did not close')
                freeze(path/'RESULT.json',dict(result=result,development_only=True,original_plan=terminal['plan']))
                checks.append(bind(path/'RESULT.json'))
                print('Boundary passed '+str(i+1)+'/'+str(len(selected)),flush=True)
            import test_integrated_history_v3 as regression
            regression.BOUNDARY_OUTPUT=output/'clock-boundaries'
            scratch=output/'temporary-fixtures';scratch.mkdir();tempfile.tempdir=str(scratch)
            suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(regression),
                unittest.defaultTestLoader.loadTestsFromName('test_integrated_prefix_reuse')])
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            if not tests.wasSuccessful():raise ValueError('History derivative tests failed')
            guard(output,local,started,1200)
            for b in code+[terminal_binding,*checks]:verify(b)
            freeze(output/'RESULT.json',dict(status='PASS_INTEGRATED_HISTORY_BOUND_DERIVATIVE_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),
                original_failure=bind(output/'ORIGINAL_FAILURE.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                boundaries=checks,clock_boundaries=[bind(p) for p in sorted((output/'clock-boundaries').glob('*/BOUNDARY_RESULT.json'))],
                elapsed_seconds=time.monotonic()-started,models_loaded=0,physical_widget_observed=False,integrated_N4_cells=0))
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_HISTORY_PROBE_PRESERVED',**failure_details(exc),
                admission=bind(output/'ADMISSION.json'),boundaries=checks,tests_run=tests.testsRun if tests else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
