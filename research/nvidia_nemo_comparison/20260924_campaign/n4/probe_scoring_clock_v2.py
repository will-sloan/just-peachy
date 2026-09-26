"""Qualify an isolated evaluator derivative. See README_SCORING_CLOCK_V2.md."""
import argparse
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import shutil
import sys
import time
import unittest

from common import bind, fingerprint, freeze, load, verify
from integrated_scoring_adapter_v2 import convert, read_artifact, read_component_events
from metric_process import MetricProcess, exact_process, identity, pin
from paced_slot import observe_owner, process_census, validate_supervision
from probe_integrated_scoring import verify_environment
from review_scoring_bank_v2 import code_bindings, guard, owners_closed, require, shared_allowance, validate_score
from scoring_bank_v2 import code_bindings as scoring_code, prediction, validate_implementation, verify_bindings, writer_lock

HERE=Path(__file__).resolve().parent


def active_bank(local):
    """Observe the existing run; do not admit its prefix for production scoring."""
    root=local/'n4/integrated-main-v2'
    plan_binding=bind(local/'n4/integrated-main-plan-v2.json')
    plan=load(plan_binding['path']); context=plan['context']
    qualification_path=HERE/'INTEGRATED_BANK_CLOCK_CHECK_V2.json'
    validate_implementation(context,load(qualification_path),bind(qualification_path))
    verify_bindings(context)
    if (root/'RESULT.json').exists():
        terminal=load(root/'RESULT.json')
        require(exact_process(terminal['owner']) is None, 'Terminal method owner remains active')
        return dict(plan=plan_binding,terminal=bind(root/'RESULT.json'),census=process_census(local))
    progress=load(root/'PROGRESS.json'); worker=load(local/'supervision/worker.json')
    owner=progress['owner']; supervisor=dict(pid=worker['pid'],create_time=worker['create_time'])
    observations={who['pid']:observe_owner(who) for who in (owner,supervisor)}
    validate_supervision(worker,owner,observations,time.time())
    spec_binding=bind(local/'n4/integrated-main-worker-v2.json');spec=load(spec_binding['path'])
    require(exact_process(owner).cmdline()==spec['argv'], 'Active method worker command differs')
    require(progress['status']=='RUNNING' and progress['total']==plan['required']==7680
            and 0<=(datetime.now(timezone.utc)-datetime.fromisoformat(progress['heartbeat_utc'])).total_seconds()<90,
            'Active method progress is stale or inconsistent')
    return dict(plan=plan_binding,worker_spec=spec_binding,progress=progress,supervision=worker,
                observations=observations,census=process_census(local))


def run(output):
    process=pin(); started=time.monotonic()
    public=load(HERE/'SCORING_BANK_IMPLEMENTATION_V1.json'); parent_binding=public['private_metric_probe']
    verify(parent_binding);parent=load(parent_binding['path']);verify(parent['admission'])
    admission=load(parent['admission']['path']);local=Path(parent_binding['path']).parents[2]
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()), 'Fresh private output required')
    require(parent['status']=='PASS_51_OWNED_PROCESS_SCORING_CHECKS' and len(parent['checks'])==51,
            'Original saved score population differs')
    require(exact_process(admission['owner']) is None,'Saved scoring probe remains active')
    owners_closed([parent['closure']],51)
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,1200);inventory=shared_allowance(local)
        bank_start=active_bank(local);files=verify_environment(admission['environment'])
        verify(admission['truth']);verify_bindings(admission['code'])
        code=code_bindings();boundary_qualification=load(HERE/'INTEGRATED_BANK_CLOCK_CHECK_V2.json')
        verify_bindings(boundary_qualification)
        boundary_parent=load(boundary_qualification['private_receipt']['path'])
        require(len(boundary_parent['boundary_results'])==4,'Four sealed boundary cases required')
        truths={r['job_id']:r for r in load(admission['truth']['path'])['cells']}
        require(len(truths)==480,'Truth population differs')
        freeze(output/'ADMISSION.json',dict(owner=identity(process),parent=parent_binding,code=code,
            scoring_code=scoring_code(),environment=admission['environment'],environment_files_verified=files,
            truth=admission['truth'],inventory=inventory,bank_start=bank_start,
            boundary_parent=boundary_qualification['private_receipt'],maximum_seconds=1200,
            maximum_output_bytes=8*1024**2,models_loaded=0,integrated_N4_cells=0,
            resource_scope='CPU14 BelowNormal non-controlled development; no latency/resource acceptance'))
        for b in code:
            source=Path(b['path']);target=output/'sources'/source.name
            target.parent.mkdir(exist_ok=True)
            require(not target.exists(),'Duplicate source basename');shutil.copyfile(source,target)
            require(bind(target)['sha256']==b['sha256'],'Source snapshot differs')
        checked=[];boundary_checks=[];client=None;closure=None;tests=None
        try:
            # Temporary synthetic data stays on G: under this admitted private output.
            scratch=output/'temporary-fixtures';scratch.mkdir()
            os.environ['TEMP']=os.environ['TMP']=str(scratch)
            import tempfile
            tempfile.tempdir=str(scratch)
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
                ('test_scoring_bank_v2','test_scoring_review_v2','test_scoring_clock_v2'))
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful(),'Derivative regression tests failed')
            for check in parent['checks']:
                guard(output,local,started,1200);verify(check['expected']);saved=load(check['expected']['path'])
                for b in [*saved['inputs'],saved['consumer_closure']]:verify(b)
                asr,speaker=[load(b['path']) for b in saved['inputs']];job=asr['job'];truth=truths[job['job_id']]
                require(speaker['job']==job and load(saved['consumer_closure']['path'])['full_event_consumer_drained'],
                        'Saved prediction join/closure differs')
                pub=read_artifact(saved['publication']);proj=read_artifact(saved['projection'])
                pred=convert(pub,proj,read_component_events(speaker),job,pub['contract']['diarization'])
                require(check['input_sha256']==fingerprint(dict(truth=truth,prediction=pred))
                        and check['score_sha256']==fingerprint(saved['score']) and check['exact_score_equal'] is True,
                        'Saved input/score parity differs')
                validate_score(saved['score'],truth,pred)
                checked.append(dict(expected=check['expected'],input_sha256=check['input_sha256'],score_sha256=check['score_sha256']))
            print('PASS: regression suite and 51 saved score/input reviews',flush=True)
            client=MetricProcess();client.start()
            for i,b in enumerate(boundary_parent['boundary_results']):
                guard(output,local,started,1200);verify(b);saved=load(b['path']);cell=saved['result']
                require(saved['development_only'] is True and saved['actual_original_480_audio_job'] is True,
                        'Boundary development provenance differs')
                verify_bindings(cell);job=load(saved['inputs'][0]['path'])['job'];truth=truths[job['job_id']]
                pred=prediction(cell,cell,job)
                response=client.score(truth,pred,timeout_seconds=min(120,1200-(time.monotonic()-started)))
                score=response['score'];score['metric_status']='SCORED'
                require(response['input_sha256']==fingerprint(dict(truth=truth,prediction=pred)),'Boundary metric input differs')
                validate_score(score,truth,pred)
                path=output/'boundary-scores'/f'{i:02d}.json'
                freeze(path,dict(source=b,input_sha256=response['input_sha256'],score=score,integrated_N4_cells=0))
                boundary_checks.append(dict(source=b,score=bind(path),input_sha256=response['input_sha256'],
                    artifact_expanded_bytes={k:v['expanded_bytes'] for k,v in cell['outputs'].items()}))
            closure=client.close();client=None;owners_closed([closure],4)
            bank_end=active_bank(local);require(bank_end['plan']==bank_start['plan'],'Active bank plan changed')
            guard(output,local,started,1200);shared_allowance(local)
            for b in code+[parent_binding,admission['truth'],boundary_qualification['private_receipt']]:verify(b)
            require(not any(n=='torch' or n=='method_artifact_v2' or n.startswith(('edge_speech_pipeline',
                'application_publication','component_d1_replay')) for n in sys.modules),'Predictor imported into evaluator')
            freeze(output/'RESULT.json',dict(status='PASS_SCORING_CLOCK_DERIVATIVE_DEVELOPMENT_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),
                tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,saved_reviews=checked,
                boundary_checks=boundary_checks,closure=closure,bank_end=bank_end,
                elapsed_seconds=time.monotonic()-started,models_loaded=0,integrated_N4_cells=0,
                production_bank_admitted=False,production_bank_scored=False,physical_widget_observed=False))
            print('PASS: four full saved boundary conversions and bounded metric scores',flush=True)
        except BaseException as exc:
            if client is not None:closure=client.close()
            freeze(output/'FAILED.json',dict(status='FAILED_SCORING_DERIVATIVE_PROBE_PRESERVED',
                error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json'),saved_reviews=len(checked),
                boundary_checks=boundary_checks,closure=closure,tests_run=tests.testsRun if tests else None,integrated_N4_cells=0))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
