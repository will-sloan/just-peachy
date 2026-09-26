"""Guarded model-free released-session checks; README_RESTART_SESSION.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import identity, pin
from probe_application_delivery import inputs as prior_inputs
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_restart_session as tests

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('restart_source_capture.py','restart_session_closure.py','test_restart_session.py',
     'probe_restart_session.py','README_RESTART_SESSION.md')


def inputs():
    admitted=prior_inputs();q=load(HERE/'APPLICATION_CLOSURE_CHECK_V2.json')
    verify(q['private_receipt']);receipt=load(q['private_receipt']['path'])
    verify(receipt['admission']);historical=load(receipt['admission']['path'])
    cases=historical['cases']
    require(len(cases)==9,'Expected nine qualified historical sessions')
    registry={}
    for b in admitted['code']+q['code']+[bind(HERE/n) for n in OWN]:
        verify(b);require(b['path'] not in registry or registry[b['path']]==b,'Conflicting qualified binding')
        registry[b['path']]=b
    for case in cases:
        for key in ('finalization','consumer','archive'):verify(case[key])
    admitted.update(code=list(registry.values()),historical_admission=receipt['admission'],cases=cases)
    return admitted


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private release-session probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        checkpoint=lambda:guard(output,LOCAL,started,720)
        checkpoint();inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Source snapshot differs');snapshots.append(bind(target))
        try:
            admitted=inputs()
            freeze(output/'ADMISSION.json',dict(owner=identity(process),source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,**{k:v for k,v in admitted.items() if k!='prototype'},
                actual_application_or_audio_file_started=False,actual_restart_pair=False))
            context=dict(output=output,prototype=admitted['prototype'],checkpoint=checkpoint,cases=admitted['cases'])
            tests.CONTEXT.update(context);tests.prior.CONTEXT.update(context);tests.prior.source_tests.CONTEXT.update(context)
            tests.historical.CONTEXT.update(context)
            sys.path[:0]=[str(admitted['prototype']),str(admitted['prototype']/'vendor'),str(HERE.parents[3])]
            from controller_projection import forbid_inference
            stream=io.StringIO()
            with forbid_inference():
                outcome=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                    unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartSessionTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(outcome.wasSuccessful() and outcome.testsRun==22 and not outcome.skipped,'Released-session development checks failed')
            for b in admitted['code']+snapshots:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            checkpoint()
            freeze(output/'RESULT.json',dict(status='PASS_RELEASED_SESSION_DEVELOPMENT_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),
                tests_passed=outcome.testsRun,D1_after=after,
                synthetic_prefix_delivery=bind(output/'SYNTHETIC_PREFIX_DELIVERY.json'),
                synthetic_prefix_engine=bind(output/'SYNTHETIC_PREFIX_ENGINE.json'),
                actual_application_or_audio_file_started=False,actual_GUI_or_model_started=False,
                actual_restart_pair=False,engine_capture_runtime_not_exercised=True,
                same_controller_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 22 released-session checks; runtime capture and actual restart pair remain',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RELEASE_SESSION_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
